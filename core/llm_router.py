import os
import logging
from pydantic import ValidationError
from google import genai
from google.genai import types
from core.ai_schemas import ExtractedOpportunity

logger = logging.getLogger(__name__)


class AIRouter:
    """Handles structured extraction using the Gemini API with native JSON schema output."""

    def __init__(self):
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = "gemini-2.0-flash"

        self.system_prompt = (
            "You are a highly precise data extraction assistant specializing in the Pakistani "
            "university and technical community ecosystem (e.g., NUST, FAST, LUMS, GDG). "
            "Analyze the provided social media post and OCR text. Extract the details perfectly. "
            "If a detail is missing, do not invent it—leave it as null."
        )

    async def extract_structured_data(self, sanitized_text: str) -> ExtractedOpportunity | None:
        """
        Sends the cleaned caption + OCR text to Gemini and returns a validated
        ExtractedOpportunity Pydantic object.

        Uses Gemini's native response_schema support so the model is forced to
        return valid JSON that matches the schema — no post-processing needed.
        """
        try:
            logger.info("🧠 Sending payload to Gemini for structured extraction...")

            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=f"Extract the opportunity data from this text:\n\n{sanitized_text}",
                config=types.GenerateContentConfig(
                    system_instruction=self.system_prompt,
                    response_mime_type="application/json",
                    response_schema=ExtractedOpportunity,
                    temperature=0.0,
                ),
            )

            return ExtractedOpportunity.model_validate_json(response.text)

        except ValidationError as e:
            logger.error(f"❌ Gemini response failed schema validation: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Gemini API error: {e}")
            return None
