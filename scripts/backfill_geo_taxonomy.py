"""
Backfill PostGIS location + taxonomy defaults for existing final_opportunities rows.

Usage:
    python scripts/backfill_geo_taxonomy.py
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from sqlalchemy import select, text

load_dotenv()

from core.database import AsyncSessionLocal, engine
from core.models import FinalOpportunity


async def main() -> None:
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(select(FinalOpportunity))).scalars().all()
        updated = 0
        for row in rows:
            changed = False
            if not row.city and row.latitude and row.longitude:
                # leave city alone if unknown
                pass
            if not row.domain:
                row.domain = "Tech"
                changed = True
            if not row.subcategory:
                row.subcategory = row.category or "Other"
                changed = True
            if not row.format:
                row.format = "In-Person"
                changed = True
            if not row.city and (row.organization_name or "").lower().find("islamabad") >= 0:
                row.city = "Islamabad"
                row.country = row.country or "Pakistan"
                row.latitude = row.latitude or 33.6844
                row.longitude = row.longitude or 73.0479
                row.local_timezone = row.local_timezone or "Asia/Karachi"
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
                  AND (location IS NULL)
                """
            )
        )
        await session.commit()

    await engine.dispose()
    print(f"[OK] Backfilled taxonomy on {updated} rows and synced PostGIS locations.")


if __name__ == "__main__":
    asyncio.run(main())
