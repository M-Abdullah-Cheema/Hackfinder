"""
FastAPI server that exposes the FinalOpportunity table to the Next.js frontend.

Run with:
    uvicorn api.main:app --reload --port 8002

Also exposes the Target Registry (sources) API on the same port.
The legacy admin entrypoint (main.py at the root) remains available on port 8000.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.routers import sources
from core.database import AsyncSessionLocal
from core.models import FinalOpportunity

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Hackathon Aggregator – Public API",
    description="Serves deduplicated, AI-structured opportunities to the Next.js frontend.",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sources.router)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


class OpportunityOut(BaseModel):
    id: int
    title: str
    organization_name: str
    category: str
    registration_url: Optional[str] = None
    platform_post_id: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    city: Optional[str] = None
    country: Optional[str] = None
    start_datetime_utc: Optional[datetime] = None
    end_datetime_utc: Optional[datetime] = None
    local_timezone: Optional[str] = None
    domain: Optional[str] = None
    subcategory: Optional[str] = None
    format: Optional[str] = None

    model_config = {"from_attributes": True}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


@app.get("/")
async def root():
    return {"status": "ok", "message": "Hackathon Aggregator API is running."}


@app.get("/api/opportunities", response_model=list[OpportunityOut])
async def get_opportunities(
    category: Optional[str] = Query(
        default=None,
        description="Filter by category (e.g. Hackathon, Workshop, Internship)",
    ),
    organization_name: Optional[str] = Query(
        default=None,
        description="Filter by organization name (partial, case-insensitive)",
    ),
    city: Optional[str] = Query(default=None, description="Filter by city (partial)"),
    country: Optional[str] = Query(default=None, description="Filter by country (partial)"),
    domain: Optional[str] = Query(default=None, description="Filter by domain taxonomy"),
    subcategory: Optional[str] = Query(default=None, description="Filter by subcategory"),
    lat: Optional[float] = Query(default=None, description="Center latitude for radius search"),
    lng: Optional[float] = Query(default=None, description="Center longitude for radius search"),
    radius_km: float = Query(
        default=50.0,
        ge=0.5,
        le=2000.0,
        description="Search radius in km when lat/lng provided",
    ),
    limit: int = Query(default=100, ge=1, le=500, description="Max records to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    db: AsyncSession = Depends(get_db),
):
    """
    Return deduplicated opportunities with optional category/org/geo filters.
    When lat+lng are provided, prefers PostGIS ST_DWithin, else bbox + Haversine.
    """
    query = select(FinalOpportunity)

    if category:
        query = query.where(FinalOpportunity.category == category)

    if organization_name:
        query = query.where(
            FinalOpportunity.organization_name.ilike(f"%{organization_name}%")
        )

    if city:
        query = query.where(FinalOpportunity.city.ilike(f"%{city}%"))

    if country:
        query = query.where(FinalOpportunity.country.ilike(f"%{country}%"))

    if domain:
        query = query.where(FinalOpportunity.domain.ilike(domain))

    if subcategory:
        query = query.where(FinalOpportunity.subcategory.ilike(f"%{subcategory}%"))

    used_postgis = False
    if lat is not None and lng is not None:
        from sqlalchemy import text

        try:
            # Narrow by PostGIS first, then apply remaining filters in Python/ORM on IDs
            geo_result = await db.execute(
                text(
                    """
                    SELECT id FROM final_opportunities
                    WHERE location IS NOT NULL
                      AND ST_DWithin(
                            location,
                            ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                            :radius_m
                      )
                    ORDER BY id DESC
                    LIMIT :lim OFFSET :off
                    """
                ),
                {
                    "lng": lng,
                    "lat": lat,
                    "radius_m": radius_km * 1000.0,
                    "lim": limit,
                    "off": offset,
                },
            )
            geo_ids = [row[0] for row in geo_result.all()]
            used_postgis = True
            if not geo_ids:
                return []
            query = query.where(FinalOpportunity.id.in_(geo_ids))
        except Exception:
            used_postgis = False
            await db.rollback()
            lat_delta = radius_km / 111.0
            lng_delta = radius_km / (111.0 * max(0.2, abs(math.cos(math.radians(lat)))))
            query = query.where(
                and_(
                    FinalOpportunity.latitude.is_not(None),
                    FinalOpportunity.longitude.is_not(None),
                    FinalOpportunity.latitude.between(lat - lat_delta, lat + lat_delta),
                    FinalOpportunity.longitude.between(lng - lng_delta, lng + lng_delta),
                )
            )

    if not used_postgis:
        query = query.order_by(FinalOpportunity.id.desc()).limit(limit).offset(offset)
    else:
        query = query.order_by(FinalOpportunity.id.desc())

    try:
        result = await db.execute(query)
        rows = list(result.scalars().all())
    except Exception as exc:
        logger.exception("Failed to load opportunities: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Database unreachable. Switch to phone hotspot and retry.",
        ) from exc

    if lat is not None and lng is not None and not used_postgis:
        rows = [
            row
            for row in rows
            if row.latitude is not None
            and row.longitude is not None
            and _haversine_km(lat, lng, row.latitude, row.longitude) <= radius_km
        ]

    return rows


@app.get("/api/opportunities/categories", response_model=list[str])
async def get_categories(db: AsyncSession = Depends(get_db)):
    """Return a sorted list of all distinct categories present in the table."""
    from sqlalchemy import distinct

    result = await db.execute(
        select(distinct(FinalOpportunity.category)).order_by(FinalOpportunity.category)
    )
    return [row[0] for row in result.all()]


@app.get("/api/opportunities/organizations", response_model=list[str])
async def get_organizations(db: AsyncSession = Depends(get_db)):
    """Return a sorted list of all distinct organization names."""
    from sqlalchemy import distinct

    result = await db.execute(
        select(distinct(FinalOpportunity.organization_name)).order_by(
            FinalOpportunity.organization_name
        )
    )
    return [row[0] for row in result.all()]
