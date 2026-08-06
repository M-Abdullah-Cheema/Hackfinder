import json
import logging
import os

from pydantic import ValidationError

from core.ai_schemas import ExtractedOpportunity

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a precise global events extraction assistant.\n"
    "Extract ONE structured opportunity from social posts, OCR flyer text, or calendar copy.\n"
    "\n"
    "QUALITY RULES:\n"
    "- title: short formal event name only (e.g. 'Build with AI 2026'). "
    "Never copy the full caption, hashtags, emojis, or CTAs like 'Register now'.\n"
    "- organization_name: the host only (e.g. 'GDG Cloud Islamabad', 'lablab.ai'). "
    "Never @handles, never multiple rambling lines.\n"
    "- registration_url: copy any real apply/register link from the text "
    "(bit.ly, lu.ma, forms.gle, eventbrite, google forms, linktr.ee). "
    "Never invent URLs. Leave null only when no link exists.\n"
    "- Prefer the flyer/OCR headline over caption fluff when both exist.\n"
    "- city/country: real place names when stated (venue city). "
    "For virtual-only events with no city, leave city null and set is_remote=true.\n"
    "- latitude/longitude: ALWAYS null (a separate geocoder fills map pins).\n"
    "- Dates: convert to UTC when timezone is clear; else leave start/end null "
    "(do not invent dates).\n"
    "- Taxonomy: domain Tech/Recreational/Community/Cultural/Other; "
    "subcategory short (AI/ML, Cloud, Startup…); format In-Person/Virtual/Hybrid.\n"
    "- If a field is unknown, use null — never invent URLs, cities, or orgs.\n"
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
            # Stronger default for cleaner titles; override with GROQ_MODEL if rate-limited
            self.model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    async def extract_structured_data(self, sanitized_text: str) -> ExtractedOpportunity | None:
        # Cap payload — noisy Instagram captions + OCR can blow context / confuse small models
        text = (sanitized_text or "").strip()
        if len(text) > 6000:
            text = text[:6000] + "\n…[truncated]"

        try:
            if self.provider == "gemini":
                return await self._extract_gemini(text)
            return await self._extract_groq(text)
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
                        "Extract ONE opportunity as JSON matching this schema.\n"
                        "Remember: short title, host org only, lat/lng must be null.\n"
                        f"Schema:\n{json.dumps(schema)}\n\n"
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
            contents=(
                "Extract ONE opportunity as JSON. "
                "Short title, host org only, lat/lng null.\n\n"
                f"{sanitized_text}"
            ),
            config=types.GenerateContentConfig(
                system_instruction=self.system_prompt,
                response_mime_type="application/json",
                response_schema=ExtractedOpportunity,
                temperature=0.0,
            ),
        )
        return ExtractedOpportunity.model_validate_json(response.text)
