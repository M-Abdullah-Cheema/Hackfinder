"""Generate semantic vectors for dedup. Gemini preferred when billed; FastEmbed fallback."""
from __future__ import annotations

import logging
import math
import os
from typing import Optional

logger = logging.getLogger(__name__)

TARGET_DIMS = 1536
_fastembed_model = None


def _pad_or_trim(values: list[float], dims: int = TARGET_DIMS) -> list[float]:
    if len(values) == dims:
        return values
    if len(values) > dims:
        values = values[:dims]
    else:
        values = values + [0.0] * (dims - len(values))
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


def _local_semantic_embedding(text: str) -> list[float]:
    """
    Real local embeddings via FastEmbed (BGE small, 384-d), padded to 1536
    so the existing pgvector column/index keep working.
    """
    global _fastembed_model
    from fastembed import TextEmbedding

    if _fastembed_model is None:
        _fastembed_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        logger.info("Loaded FastEmbed model BAAI/bge-small-en-v1.5")

    vectors = list(_fastembed_model.embed([text]))
    if not vectors:
        raise RuntimeError("FastEmbed returned no vectors")
    return _pad_or_trim([float(x) for x in vectors[0]])


def _gemini_key_usable(api_key: str) -> bool:
    """
    Gemini embedding API needs a Google AI Studio / Vertex key.
    Keys starting with 'AQ.' are typically other Google product tokens and fail embeddings.
    """
    if not api_key or api_key.startswith("your_"):
        return False
    if api_key.startswith("AQ."):
        logger.warning(
            "GEMINI_API_KEY looks like an AI Studio browser token (AQ.…). "
            "For Gemini embeddings, create an API key at https://aistudio.google.com/apikey "
            "(enable billing) and set EMBEDDING_PROVIDER=gemini."
        )
        return False
    return True


class EmbeddingEngine:
    """Generates 1536-dimensional vectors (Gemini when configured, else FastEmbed)."""

    def __init__(self):
        self.model = "gemini-embedding-001"
        self._client = None
        provider = (os.getenv("EMBEDDING_PROVIDER") or "auto").strip().lower()
        api_key = (os.getenv("GEMINI_API_KEY") or "").strip()

        want_gemini = provider in {"gemini", "auto"}
        force_local = provider in {"fastembed", "local"}

        if force_local:
            logger.info("EMBEDDING_PROVIDER=%s — using FastEmbed only", provider)
        elif want_gemini and _gemini_key_usable(api_key):
            try:
                from google import genai

                self._client = genai.Client(api_key=api_key)
                logger.info("Gemini embeddings enabled (%s)", self.model)
            except Exception as exc:
                logger.warning("Gemini embedding client unavailable: %s", exc)
        elif provider == "gemini":
            logger.warning(
                "EMBEDDING_PROVIDER=gemini but no usable GEMINI_API_KEY — falling back to FastEmbed"
            )

    async def generate_vector(
        self, title: str, org_name: str, category: str
    ) -> Optional[list[float]]:
        semantic_payload = (
            f"Opportunity: {title}. "
            f"Host Organization: {org_name}. "
            f"Classification: {category}."
        )

        if self._client is not None:
            try:
                from google.genai import types

                response = await self._client.aio.models.embed_content(
                    model=self.model,
                    contents=[semantic_payload],
                    config=types.EmbedContentConfig(output_dimensionality=TARGET_DIMS),
                )
                return list(response.embeddings[0].values)
            except Exception as e:
                logger.warning("Gemini embedding failed (%s); using FastEmbed", e)

        try:
            logger.info("Using FastEmbed local semantic embedding")
            return _local_semantic_embedding(semantic_payload)
        except Exception as e:
            logger.error("Local embedding failed: %s", e)
            return None
