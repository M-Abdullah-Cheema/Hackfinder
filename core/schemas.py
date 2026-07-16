import enum
import re
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict

class PlatformType(str, enum.Enum):
    LINKEDIN = "linkedin"
    INSTAGRAM = "instagram"
    STATIC_WEB = "static_web"

class SourceConfigSchema(BaseModel):
    """Defines structural validation rules for both legacy web scraping and social feeds."""
    
    platform_type: PlatformType = Field(
        default=PlatformType.STATIC_WEB, 
        description="The targeting ecosystem: linkedin, instagram, or static_web"
    )
    max_post_age_days: int = Field(
        default=7, 
        ge=1, 
        le=30, 
        description="Ignore posts older than this threshold to prevent processing historic debt"
    )
    extract_images_for_ocr: bool = Field(
        default=False, 
        description="Set to True to instruct the pipeline to gather image URLs for downstream OCR"
    )

    crawler_type: str = Field(default="scrapy", description="Set to 'playwright' for heavy SPA/Social timelines")
    session_cookies: Dict[str, Any] = Field(default_factory=dict, description="Auth cookies (e.g., li_at token)")
    proxy_required: bool = Field(default=True)

    allowed_domains: Optional[List[str]] = Field(default_factory=list)
    max_depth: Optional[int] = Field(default=2, ge=1, le=10)
    title_selector: Optional[str] = Field(default=None)
    content_selector: Optional[str] = Field(default=None)

    model_config = ConfigDict(extra="allow")

class SourceBase(BaseModel):
    """The base structure for a scraping source with strict structural URL normalization."""
    name: str = Field(..., description="A unique, human-readable name for this target")
    target_url: str = Field(..., description="The direct URL to the group, company page, profile, or portal")
    config_jsonb: SourceConfigSchema
    is_active: bool = Field(default=True)
    tier: int = Field(default=1, ge=1, le=5)

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        return v.strip().title()

    @field_validator("target_url")
    @classmethod
    def validate_and_normalize_url(cls, v: str) -> str:
        url_clean = v.strip().lower()

        linkedin_pattern = r"^https://(www\.)?linkedin\.com/(company|groups|in)/[a-zA-Z0-9\-_]+/?(.*)$"
        instagram_pattern = r"^https://(www\.)?instagram\.com/[a-zA-Z0-9\._]+/?$"

        if "linkedin.com" in url_clean:
            if not re.match(linkedin_pattern, url_clean):
                raise ValueError(
                    "Invalid LinkedIn URL structure. Must match: https://www.linkedin.com/[company|groups|in]/{handle}/"
                )
            if "/company/" in url_clean and not url_clean.endswith("/posts") and not url_clean.endswith("/posts/"):
                url_clean = url_clean.rstrip("/") + "/posts/"
            return url_clean

        elif "instagram.com" in url_clean:
            if not re.match(instagram_pattern, url_clean):
                raise ValueError(
                    "Invalid Instagram URL structure. Must match: https://www.instagram.com/{handle}/"
                )
            return url_clean

        if not url_clean.startswith("http://") and not url_clean.startswith("https://"):
            raise ValueError("Institutional web portals must begin with http:// or https://")
            
        return url_clean

class SourceCreate(SourceBase):
    """Schema used when creating a brand new target."""
    pass

class SourceUpdate(BaseModel):
    """Schema used when modifying an existing target (all fields optional)."""
    name: Optional[str] = None
    target_url: Optional[str] = None
    config_jsonb: Optional[SourceConfigSchema] = None
    is_active: Optional[bool] = None
    tier: Optional[int] = Field(None, ge=1, le=5)

class SourceResponse(SourceBase):
    id: int
    
    model_config = ConfigDict(from_attributes=True)