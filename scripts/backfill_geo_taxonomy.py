"""
Backfill PostGIS location + taxonomy for existing final_opportunities.

Geocodes rows that have a city but missing lat/lng (alias map + Nominatim).

Usage:
    python scripts/backfill_geo_taxonomy.py
"""
from __future__ import annotations

import asyncio
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from sqlalchemy import select, text

load_dotenv()

from core.database import AsyncSessionLocal, engine
from core.geocoder import CITY_ALIASES, enrich_coords
from core.models import FinalOpportunity


def _infer_city_from_text(*parts: str | None) -> tuple[str | None, str | None]:
    blob = " ".join(p for p in parts if p).lower()
    for alias, (_lat, _lng, city, country) in CITY_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", blob):
            return city, country
    return None, None


async def main() -> None:
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(select(FinalOpportunity))).scalars().all()
        updated = 0
        geocoded = 0
        for row in rows:
            changed = False
            if not row.domain:
                row.domain = "Tech"
                changed = True
            if not row.subcategory:
                row.subcategory = row.category or "Other"
                changed = True
            if not row.format:
                row.format = "In-Person"
                changed = True

            if not row.city:
                inferred_city, inferred_country = _infer_city_from_text(
                    row.title, row.organization_name, row.city, row.country
                )
                if inferred_city:
                    row.city = inferred_city
                    row.country = row.country or inferred_country
                    if inferred_country == "Pakistan":
                        row.local_timezone = row.local_timezone or "Asia/Karachi"
                    changed = True

            if row.city and (row.latitude is None or row.longitude is None):
                geo = enrich_coords(
                    city=row.city,
                    country=row.country,
                    latitude=row.latitude,
                    longitude=row.longitude,
                    is_remote=(row.format or "").lower() == "virtual" and not row.city,
                )
                if geo.get("latitude") is not None and geo.get("longitude") is not None:
                    row.latitude = geo["latitude"]
                    row.longitude = geo["longitude"]
                    row.city = geo.get("city") or row.city
                    row.country = geo.get("country") or row.country
                    geocoded += 1
                    changed = True

            if changed:
                updated += 1
        await session.commit()

        await session.execute(
            text(
                """
                UPDATE final_opportunities
                SET location = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography
                WHERE latitude IS NOT NULL
                  AND longitude IS NOT NULL
                """
            )
        )
        await session.commit()

    await engine.dispose()
    print(
        f"[OK] Updated {updated} rows ({geocoded} geocoded) and synced PostGIS locations."
    )


if __name__ == "__main__":
    asyncio.run(main())
