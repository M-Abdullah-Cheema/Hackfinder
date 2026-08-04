"""External calendar / event API adapters for HackFinder Global ingestion."""

from scrapers.api_integrations.base import BaseEventFeed, NormalizedEvent
from scrapers.api_integrations.calendar_apis import EventbriteFeed, LumaFeed, MeetupFeed
from scrapers.api_integrations.rss_ical import ICalFeed, RssEventFeed

__all__ = [
    "BaseEventFeed",
    "NormalizedEvent",
    "RssEventFeed",
    "ICalFeed",
    "EventbriteFeed",
    "MeetupFeed",
    "LumaFeed",
]
