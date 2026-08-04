"""Shared contract for Eventbrite / Meetup / Luma / RSS / iCal adapters."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class NormalizedEvent:
    """Canonical event shape before staging / AI enrichment."""

    title: str
    source_name: str
    external_id: str
    registration_url: Optional[str] = None
    description: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    start_datetime_utc: Optional[datetime] = None
    end_datetime_utc: Optional[datetime] = None
    local_timezone: Optional[str] = None
    domain: str = "Tech"
    format: Optional[str] = None
    organization_name: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("start_datetime_utc", "end_datetime_utc"):
            value = payload.get(key)
            if isinstance(value, datetime):
                payload[key] = value.isoformat()
        return payload

    @property
    def platform_post_id(self) -> str:
        return f"{self.source_name}:{self.external_id}"


class BaseEventFeed(ABC):
    """Fetch + normalize events from a remote calendar/API source."""

    source_name: str = "generic"

    @abstractmethod
    async def fetch(self) -> list[NormalizedEvent]:
        raise NotImplementedError
