from datetime import datetime
import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F9FF"
    "\U00002600-\U000027BF"
    "\U0001FA00-\U0001FAFF"
    "]+",
    flags=re.UNICODE,
)
_HASHTAG_RE = re.compile(r"#\w+")
_HANDLE_RE = re.compile(r"@[\w.]+")
_CTA_RE = re.compile(
    r"\b(register now|link in bio|apply now|swipe up|dm us|follow us|"
    r"like and share|click (here|the link)|comment below)\b",
    re.I,
)
_JUNK_ORG = re.compile(
    r"^(unknown|n/?a|none|null|follow|register|untitled|org|host)\b",
    re.I,
)


def _clean_label(value: str, *, max_len: int) -> str:
    text = (value or "").strip()
    text = _EMOJI_RE.sub(" ", text)
    text = _HASHTAG_RE.sub(" ", text)
    text = _HANDLE_RE.sub(" ", text)
    text = _CTA_RE.sub(" ", text)
    text = re.sub(r"[|•·]+", " - ", text)
    text = re.sub(r"[!?]{2,}", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -\t\n\r!?.:,;")
    # Drop dangling connectors left after stripping handles/CTAs
    text = re.sub(r"\b(by|from|via|with)\s*$", "", text, flags=re.I).strip(" -")
    text = re.sub(r"^\s*(by|from|via)\b\s*", "", text, flags=re.I).strip(" -")
    if len(text) > max_len:
        text = text[: max_len - 1].rstrip() + "…"
    return text


def _clean_org(value: str) -> str:
    cleaned = _clean_label(value, max_len=60)
    if not cleaned or _JUNK_ORG.match(cleaned) or len(cleaned) < 2:
        return "Unknown"
    return cleaned


class ExtractedOpportunity(BaseModel):
    """Strict schema the LLM must return when extracting global event data."""

    title: str = Field(
        description=(
            "Short formal event name only (max ~80 chars). "
            "No hashtags, emojis, CTAs, or full captions."
        )
    )
    category: Literal[
        "Hackathon", "Internship", "Workshop", "Job", "Scholarship", "Other"
    ] = Field(description="Legacy category used by the existing UI filters.")
    organization_name: str = Field(
        description=(
            "Host organization only (university, company, club). "
            "Never an @handle, never the whole caption."
        )
    )

    application_deadline: Optional[datetime] = Field(
        default=None,
        description="Final deadline to apply/register in ISO-8601 if mentioned.",
    )
    registration_url: Optional[str] = Field(
        default=None,
        description=(
            "Full registration/apply URL if present in the text "
            "(bit.ly, lu.ma, forms.gle, eventbrite, etc.). "
            "Never invent a URL. Prefer https:// links."
        ),
    )
    is_remote: bool = Field(
        default=False,
        description="True if online/remote. False if physical/on-site.",
    )

    city: Optional[str] = Field(
        default=None,
        description="City name only (e.g. Islamabad, Santa Clara). Null if unknown.",
    )
    country: Optional[str] = Field(
        default=None, description="Country where the event happens, if known."
    )
    latitude: Optional[float] = Field(
        default=None,
        description="Always null — coordinates are filled by geocoder, not the LLM.",
    )
    longitude: Optional[float] = Field(
        default=None,
        description="Always null — coordinates are filled by geocoder, not the LLM.",
    )
    start_datetime_utc: Optional[datetime] = Field(
        default=None,
        description="Event start time converted to UTC if a date/time is present.",
    )
    end_datetime_utc: Optional[datetime] = Field(
        default=None,
        description="Event end time converted to UTC if present.",
    )
    local_timezone: Optional[str] = Field(
        default=None,
        description="IANA timezone string if known, e.g. Asia/Karachi or America/New_York.",
    )
    domain: Optional[
        Literal["Tech", "Recreational", "Community", "Cultural", "Other"]
    ] = Field(
        default="Tech",
        description="Top-level domain taxonomy for global discovery.",
    )
    subcategory: Optional[str] = Field(
        default=None,
        description=(
            "Mid-level taxonomy under domain, e.g. AI/ML, Cloud, Startup, Sports, "
            "Music, Volunteering. Prefer short labels."
        ),
    )
    format: Optional[Literal["In-Person", "Virtual", "Hybrid"]] = Field(
        default=None,
        description="Delivery format of the event.",
    )

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        cleaned = _clean_label(v, max_len=80)
        return cleaned or "Untitled Event"

    @field_validator("organization_name")
    @classmethod
    def _org(cls, v: str) -> str:
        return _clean_org(v)

    @field_validator("city", "country", "subcategory", mode="before")
    @classmethod
    def _optional_str(cls, v):
        if v is None:
            return None
        text = _clean_label(str(v), max_len=60)
        return text or None

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def _drop_coords(cls, v):
        # Geocoder owns coordinates — ignore LLM guesses
        return None
