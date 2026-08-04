"""Lightweight RSS / iCal feed adapters (no paid API keys required)."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional
from xml.etree import ElementTree as ET

import aiohttp

from scrapers.api_integrations.base import BaseEventFeed, NormalizedEvent

logger = logging.getLogger(__name__)


def _text(el: Optional[ET.Element]) -> str:
    if el is None or el.text is None:
        return ""
    return el.text.strip()


def _parse_rss_date(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError, IndexError):
        return None


def _parse_ical_dt(value: str) -> Optional[datetime]:
    value = (value or "").strip()
    if not value:
        return None
    # Strip TZID=...: prefix variants
    if ":" in value and value.upper().startswith("TZID"):
        value = value.split(":", 1)[-1]
    try:
        if value.endswith("Z"):
            return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        if "T" in value:
            dt = datetime.strptime(value[:15], "%Y%m%dT%H%M%S")
            return dt.replace(tzinfo=timezone.utc)
        dt = datetime.strptime(value[:8], "%Y%m%d")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


class RssEventFeed(BaseEventFeed):
    source_name = "rss"

    def __init__(self, feed_url: str, source_name: str | None = None):
        self.feed_url = feed_url
        if source_name:
            self.source_name = source_name

    async def fetch(self) -> list[NormalizedEvent]:
        async with aiohttp.ClientSession() as session:
            async with session.get(self.feed_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                resp.raise_for_status()
                body = await resp.text()

        root = ET.fromstring(body)
        channel = root.find("channel")
        items = channel.findall("item") if channel is not None else root.findall(".//item")
        events: list[NormalizedEvent] = []

        for item in items:
            title = _text(item.find("title")) or "Untitled"
            link = _text(item.find("link"))
            guid = _text(item.find("guid")) or link or title
            description = _text(item.find("description"))
            pub = _parse_rss_date(_text(item.find("pubDate")))
            events.append(
                NormalizedEvent(
                    title=title,
                    source_name=self.source_name,
                    external_id=guid,
                    registration_url=link or None,
                    description=description or None,
                    start_datetime_utc=pub,
                    organization_name=self.source_name,
                    raw={"feed_url": self.feed_url},
                )
            )
        logger.info("RSS feed %s → %d items", self.feed_url, len(events))
        return events


class ICalFeed(BaseEventFeed):
    source_name = "ical"

    def __init__(self, feed_url: str, source_name: str | None = None):
        self.feed_url = feed_url
        if source_name:
            self.source_name = source_name

    async def fetch(self) -> list[NormalizedEvent]:
        async with aiohttp.ClientSession() as session:
            async with session.get(self.feed_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                resp.raise_for_status()
                body = await resp.text()

        events: list[NormalizedEvent] = []
        blocks = re.split(r"BEGIN:VEVENT", body, flags=re.IGNORECASE)
        for block in blocks[1:]:
            fields: dict[str, str] = {}
            for raw_line in block.splitlines():
                line = raw_line.strip()
                if not line or ":" not in line:
                    continue
                key, value = line.split(":", 1)
                key = key.split(";", 1)[0].upper()
                fields[key] = value

            uid = fields.get("UID") or fields.get("SUMMARY") or ""
            if not uid:
                continue
            events.append(
                NormalizedEvent(
                    title=fields.get("SUMMARY", "Untitled"),
                    source_name=self.source_name,
                    external_id=uid,
                    registration_url=fields.get("URL"),
                    description=fields.get("DESCRIPTION"),
                    start_datetime_utc=_parse_ical_dt(fields.get("DTSTART", "")),
                    end_datetime_utc=_parse_ical_dt(fields.get("DTEND", "")),
                    organization_name=self.source_name,
                    raw={"feed_url": self.feed_url, "location": fields.get("LOCATION")},
                )
            )
        logger.info("iCal feed %s → %d events", self.feed_url, len(events))
        return events
