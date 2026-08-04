import json
import logging
import os

from pydantic import ValidationError

from core.ai_schemas import ExtractedOpportunity

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a precise global events extraction assistant. "
    "Analyze social posts, OCR flyer text, or calendar copy and extract structured "
    "opportunity fields. Prefer real city/country and UTC datetimes when stated. "
    "Fill taxonomy as Domain -> subcategory -> format "
    "(domain: Tech/Recreational/Community/Cultural/Other; "
    "subcategory: short label like AI/ML, Cloud, Music, Sports; "
    "format: In-Person/Virtual/Hybrid). "
    "Convert local times to UTC when timezone is clear; "
    "otherwise leave start/end null rather than guessing coordinates. "
    "If a detail is missing, leave it null — never invent lat/lng. "
    "Respond with a single JSON object only (no markdown)."
)


class AIRouter:
    """Structured extraction via Groq (default) or Gemini."""

    def __init__(self):
        self.provider = os.getenv("AI_PROVIDER", "groq").strip().lower()
        self.system_prompt = SYSTEM_PROMPT

        if self.provider == "gemini":
            from google import genai

            self.gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            self.model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        else:
            from openai import AsyncOpenAI

            api_key = os.getenv("GROQ_API_KEY", "").strip()
            if not api_key or api_key.startswith("your_"):
                raise ValueError(
                    "GROQ_API_KEY is missing. Get one at https://console.groq.com/keys "
                    "and add it to your .env file."
                )
            self.groq_client = AsyncOpenAI(
                api_key=api_key,
                base_url="https://api.groq.com/openai/v1",
            )
            # Fast + generous free daily limit; override with GROQ_MODEL if needed
            self.model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

    async def extract_structured_data(self, sanitized_text: str) -> ExtractedOpportunity | None:
        try:
            if self.provider == "gemini":
                return await self._extract_gemini(sanitized_text)
            return await self._extract_groq(sanitized_text)
        except ValidationError as e:
            logger.error("LLM response failed schema validation: %s", e)
            return None
        except Exception as e:
            logger.error("%s API error: %s", self.provider, e)
            return None

    async def _extract_groq(self, sanitized_text: str) -> ExtractedOpportunity | None:
        schema = ExtractedOpportunity.model_json_schema()
        logger.info("Sending payload to Groq (%s) for structured extraction...", self.model)

        response = await self.groq_client.chat.completions.create(
            model=self.model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": self.system_prompt},
                {
                    "role": "user",
                    "content": (
                        "Extract the opportunity data from this text into JSON matching "
                        "this JSON Schema:\n"
                        f"{json.dumps(schema)}\n\n"
                        f"Text:\n{sanitized_text}"
                    ),
                },
            ],
        )
        content = response.choices[0].message.content or ""
        return ExtractedOpportunity.model_validate_json(content)

    async def _extract_gemini(self, sanitized_text: str) -> ExtractedOpportunity | None:
        from google.genai import types

        logger.info("Sending payload to Gemini (%s) for structured extraction...", self.model)
        response = await self.gemini_client.aio.models.generate_content(
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
