"""
FastAPI server that exposes the FinalOpportunity table to the Next.js frontend.

Run with:
    uvicorn api.main:app --reload --port 8001

Also exposes the Target Registry (sources) API on the same port.
The legacy admin entrypoint (main.py at the root) remains available on port 8000.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import FastAPI, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.routers import sources
from core.database import AsyncSessionLocal
from core.models import FinalOpportunity

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Hackathon Aggregator – Public API",
    description="Serves deduplicated, AI-structured opportunities to the Next.js frontend.",
    version="1.0.0",
)

# ── CORS: allow the Next.js dev server and any production origin ───────────────
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


# ── Dependency ─────────────────────────────────────────────────────────────────
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


# ── Response schema (Pydantic) ─────────────────────────────────────────────────
class OpportunityOut(BaseModel):
    id: int
    title: str
    organization_name: str
    category: str
    registration_url: Optional[str] = None
    platform_post_id: str

    model_config = {"from_attributes": True}


# ── Routes ─────────────────────────────────────────────────────────────────────
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
    limit: int = Query(default=100, ge=1, le=500, description="Max records to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    db: AsyncSession = Depends(get_db),
):
    """
    Return all deduplicated opportunities from the final table.

    Supports optional filtering by category and organization name, plus
    standard limit/offset pagination.
    """
    query = select(FinalOpportunity)

    if category:
        query = query.where(FinalOpportunity.category == category)

    if organization_name:
        query = query.where(
            FinalOpportunity.organization_name.ilike(f"%{organization_name}%")
        )

    query = query.order_by(FinalOpportunity.id.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    rows = result.scalars().all()
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
        select(distinct(FinalOpportunity.organization_name))
        .order_by(FinalOpportunity.organization_name)
    )
    return [row[0] for row in result.all()]
