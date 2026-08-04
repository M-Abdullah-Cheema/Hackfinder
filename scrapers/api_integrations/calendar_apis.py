"""Eventbrite / Meetup / Luma API feed adapters (activate when tokens are set)."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

import aiohttp

from scrapers.api_integrations.base import BaseEventFeed, NormalizedEvent

logger = logging.getLogger(__name__)


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


class EventbriteFeed(BaseEventFeed):
    source_name = "eventbrite"

    def __init__(self, organization_id: str, token: str | None = None):
        self.organization_id = organization_id
        self.token = (token or os.getenv("EVENTBRITE_API_TOKEN", "")).strip()

    async def fetch(self) -> list[NormalizedEvent]:
        if not self.token:
            logger.warning(
                "Eventbrite skipped (org=%s): set EVENTBRITE_API_TOKEN",
                self.organization_id,
            )
            return []

        url = (
            f"https://www.eventbriteapi.com/v3/organizations/"
            f"{self.organization_id}/events/"
        )
        params = {"status": "live", "expand": "venue", "page_size": 50}
        headers = {"Authorization": f"Bearer {self.token}"}

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=40)
            ) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    logger.error("Eventbrite HTTP %s: %s", resp.status, body[:300])
                    return []
                data = await resp.json()

        events: list[NormalizedEvent] = []
        for item in data.get("events", []):
            venue = item.get("venue") or {}
            address = venue.get("address") or {}
            lat = venue.get("latitude") or address.get("latitude")
            lng = venue.get("longitude") or address.get("longitude")
            try:
                lat_f = float(lat) if lat is not None else None
                lng_f = float(lng) if lng is not None else None
            except (TypeError, ValueError):
                lat_f = lng_f = None

            online = bool(item.get("online_event"))
            events.append(
                NormalizedEvent(
                    title=(item.get("name") or {}).get("text") or "Untitled",
                    source_name=self.source_name,
                    external_id=str(item.get("id")),
                    registration_url=item.get("url"),
                    description=(item.get("description") or {}).get("text"),
                    city=address.get("city"),
                    country=address.get("country"),
                    latitude=lat_f,
                    longitude=lng_f,
                    start_datetime_utc=_parse_iso((item.get("start") or {}).get("utc")),
                    end_datetime_utc=_parse_iso((item.get("end") or {}).get("utc")),
                    local_timezone=(item.get("start") or {}).get("timezone"),
                    domain="Tech",
                    format="Virtual" if online else "In-Person",
                    organization_name=f"Eventbrite:{self.organization_id}",
                    raw={"organization_id": self.organization_id},
                )
            )
        logger.info("Eventbrite org %s → %d events", self.organization_id, len(events))
        return events


class MeetupFeed(BaseEventFeed):
    """Meetup GraphQL Pro API — requires MEETUP_API_TOKEN (Bearer)."""

    source_name = "meetup"

    def __init__(self, group_urlname: str, token: str | None = None):
        self.group_urlname = group_urlname
        self.token = (token or os.getenv("MEETUP_API_TOKEN", "")).strip()

    async def fetch(self) -> list[NormalizedEvent]:
        if not self.token:
            logger.warning(
                "Meetup skipped (group=%s): set MEETUP_API_TOKEN",
                self.group_urlname,
            )
            return []

        query = """
        query ($urlname: String!) {
          groupByUrlname(urlname: $urlname) {
            name
            upcomingEvents(input: { first: 40 }) {
              edges {
                node {
                  id
                  title
                  eventUrl
                  description
                  dateTime
                  endTime
                  timezone
                  venue {
                    city
                    country
                    lat
                    lon
                  }
                  isOnline
                }
              }
            }
          }
        }
        """
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        payload = {"query": query, "variables": {"urlname": self.group_urlname}}

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.meetup.com/gql",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=40),
            ) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    logger.error("Meetup HTTP %s: %s", resp.status, body[:300])
                    return []
                data = await resp.json()

        group = ((data.get("data") or {}).get("groupByUrlname")) or {}
        edges = ((group.get("upcomingEvents") or {}).get("edges")) or []
        org_name = group.get("name") or self.group_urlname
        events: list[NormalizedEvent] = []

        for edge in edges:
            node: dict[str, Any] = edge.get("node") or {}
            venue = node.get("venue") or {}
            events.append(
                NormalizedEvent(
                    title=node.get("title") or "Untitled",
                    source_name=self.source_name,
                    external_id=str(node.get("id")),
                    registration_url=node.get("eventUrl"),
                    description=node.get("description"),
                    city=venue.get("city"),
                    country=venue.get("country"),
                    latitude=venue.get("lat"),
                    longitude=venue.get("lon"),
                    start_datetime_utc=_parse_iso(node.get("dateTime")),
                    end_datetime_utc=_parse_iso(node.get("endTime")),
                    local_timezone=node.get("timezone"),
                    domain="Community",
                    format="Virtual" if node.get("isOnline") else "In-Person",
                    organization_name=org_name,
                    raw={"group_urlname": self.group_urlname},
                )
            )
        logger.info("Meetup group %s → %d events", self.group_urlname, len(events))
        return events


class LumaFeed(BaseEventFeed):
    """Public Luma calendar feed via calendar_api_id (no key required for public calendars)."""

    source_name = "luma"

    def __init__(self, calendar_api_id: str, api_key: str | None = None):
        self.calendar_api_id = calendar_api_id
        self.api_key = (api_key or os.getenv("LUMA_API_KEY", "")).strip()

    async def fetch(self) -> list[NormalizedEvent]:
        url = "https://api.lu.ma/calendar/get-items"
        params = {"calendar_api_id": self.calendar_api_id, "period": "future"}
        headers: dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=40)
            ) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    logger.error("Luma HTTP %s: %s", resp.status, body[:300])
                    return []
                data = await resp.json()

        entries = data.get("entries") or data.get("items") or []
        events: list[NormalizedEvent] = []
        for entry in entries:
            event = entry.get("event") or entry
            geo = event.get("geo_address_info") or {}
            coords = event.get("coordinate") or {}
            events.append(
                NormalizedEvent(
                    title=event.get("name") or "Untitled",
                    source_name=self.source_name,
                    external_id=str(event.get("api_id") or event.get("id") or event.get("url")),
                    registration_url=event.get("url")
                    or (
                        f"https://lu.ma/{event.get('url')}"
                        if event.get("url")
                        else None
                    ),
                    description=event.get("description") or event.get("description_md"),
                    city=geo.get("city") or geo.get("city_state"),
                    country=geo.get("country"),
                    latitude=coords.get("latitude") or geo.get("latitude"),
                    longitude=coords.get("longitude") or geo.get("longitude"),
                    start_datetime_utc=_parse_iso(event.get("start_at")),
                    end_datetime_utc=_parse_iso(event.get("end_at")),
                    local_timezone=event.get("timezone"),
                    domain="Tech",
                    format="Virtual" if event.get("location_type") == "online" else "In-Person",
                    organization_name=self.calendar_api_id,
                    raw={"calendar_api_id": self.calendar_api_id},
                )
            )
        logger.info("Luma calendar %s → %d events", self.calendar_api_id, len(events))
        return events
