from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ExtractedOpportunity(BaseModel):
    """Strict schema the LLM must return when extracting global event data."""

    title: str = Field(description="The formal name of the event, hackathon, or opportunity.")
    category: Literal[
        "Hackathon", "Internship", "Workshop", "Job", "Scholarship", "Other"
    ] = Field(description="Legacy category used by the existing UI filters.")
    organization_name: str = Field(
        description="The university, company, or society hosting the event."
    )

    application_deadline: Optional[datetime] = Field(
        default=None,
        description="Final deadline to apply/register in ISO-8601 if mentioned.",
    )
    registration_url: Optional[str] = Field(
        default=None,
        description="URL where a user can apply or register.",
    )
    is_remote: bool = Field(
        default=False,
        description="True if online/remote. False if physical/on-site.",
    )

    city: Optional[str] = Field(
        default=None, description="City where the event happens, if known."
    )
    country: Optional[str] = Field(
        default=None, description="Country where the event happens, if known."
    )
    latitude: Optional[float] = Field(
        default=None, description="Latitude if confidently known; otherwise null."
    )
    longitude: Optional[float] = Field(
        default=None, description="Longitude if confidently known; otherwise null."
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
