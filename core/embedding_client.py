"""Generate semantic vectors for dedup. Prefers Gemini; falls back to local hash vector."""
from __future__ import annotations

import hashlib
import logging
import math
import os
import struct

logger = logging.getLogger(__name__)


def _local_hash_embedding(text: str, dims: int = 1536) -> list[float]:
    """Deterministic pseudo-embedding so inserts work without Gemini quota."""
    digest = hashlib.sha512(text.encode("utf-8")).digest()
    # Expand with repeated hashing for 1536 floats
    raw = bytearray()
    block = digest
    while len(raw) < dims * 4:
        block = hashlib.sha512(block + text.encode("utf-8")).digest()
        raw.extend(block)
    values = [
        struct.unpack("f", bytes(raw[i : i + 4]))[0]
        for i in range(0, dims * 4, 4)
    ]
    # Sanitize non-finite values from float unpack of hash bytes
    values = [0.0 if not math.isfinite(v) else v for v in values]
    # L2 normalize
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


class EmbeddingEngine:
    """Generates 1536-dimensional vectors (Gemini preferred, local fallback)."""

    def __init__(self):
        self.model = "gemini-embedding-001"
        self._client = None
        api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
        if api_key and not api_key.startswith("your_"):
            try:
                from google import genai

                self._client = genai.Client(api_key=api_key)
            except Exception as exc:
                logger.warning("Gemini embedding client unavailable: %s", exc)

    async def generate_vector(
        self, title: str, org_name: str, category: str
    ) -> list[float] | None:
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
                    config=types.EmbedContentConfig(output_dimensionality=1536),
                )
                return response.embeddings[0].values
            except Exception as e:
                logger.warning("Gemini embedding failed (%s); using local fallback", e)

        logger.info("Using local hash embedding fallback")
        return _local_hash_embedding(semantic_payload)
