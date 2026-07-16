import os
import logging
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


class EmbeddingEngine:
    """Generates 1536-dimensional semantic vectors using Gemini's embedding model."""

    def __init__(self):
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = "gemini-embedding-001"

    async def generate_vector(self, title: str, org_name: str, category: str) -> list[float] | None:
        """
        Builds a stable semantic payload from the three most reliable fields
        (title, org, category) and returns a 1536-dim float vector.

        output_dimensionality=1536 keeps the existing pgvector column schema
        unchanged — no database migration required.
        """
        semantic_payload = (
            f"Opportunity: {title}. "
            f"Host Organization: {org_name}. "
            f"Classification: {category}."
        )

        try:
            response = await self.client.aio.models.embed_content(
                model=self.model,
                contents=[semantic_payload],
                config=types.EmbedContentConfig(output_dimensionality=1536),
            )
            return response.embeddings[0].values

        except Exception as e:
            logger.error(f"❌ Gemini embedding failed: {e}")
            return None
