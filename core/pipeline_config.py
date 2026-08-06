"""Shared pipeline configuration for Instagram + calendar/API feeds."""
from __future__ import annotations

import os

# Default Instagram targets (Islamabad tech + global hackathon orgs)
INSTAGRAM_TARGETS: list[str] = [
    "https://www.instagram.com/gdgcloud.islamabad/?hl=en",
    "https://www.instagram.com/googledevs_isb/?hl=en",
    "https://www.instagram.com/insideimagineart/?hl=en",
    "https://www.instagram.com/change.mechanics/?hl=en",
    "https://www.instagram.com/awssbgnust/?hl=en",
    "https://www.instagram.com/lablab.ai/?hl=en",
]

# How often Celery Beat re-triggers the full pipeline (default: 6 hours)
SCRAPE_INTERVAL_SECONDS: int = int(os.getenv("SCRAPE_INTERVAL_SECONDS", "21600"))

AUTH_STATE_PATH: str = os.path.join("scrapers", "auth_states", "state.json")


def _csv_env(name: str) -> list[str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


# Optional calendar / API feed configuration (comma-separated env values)
EVENTBRITE_ORG_IDS: list[str] = _csv_env("EVENTBRITE_ORG_IDS")
MEETUP_GROUP_URLNAMES: list[str] = _csv_env("MEETUP_GROUP_URLNAMES")
LUMA_CALENDAR_IDS: list[str] = _csv_env("LUMA_CALENDAR_IDS")
RSS_FEED_URLS: list[str] = _csv_env("RSS_FEED_URLS")
ICAL_FEED_URLS: list[str] = _csv_env("ICAL_FEED_URLS")


def instagram_auth_ready() -> bool:
    """Return True when Playwright storage state exists and is non-empty."""
    return os.path.exists(AUTH_STATE_PATH) and os.path.getsize(AUTH_STATE_PATH) > 10


def configured_feed_count() -> int:
    return (
        len(EVENTBRITE_ORG_IDS)
        + len(MEETUP_GROUP_URLNAMES)
        + len(LUMA_CALENDAR_IDS)
        + len(RSS_FEED_URLS)
        + len(ICAL_FEED_URLS)
    )
