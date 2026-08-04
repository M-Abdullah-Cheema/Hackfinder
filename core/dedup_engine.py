"""Hybrid temporal + spatial + semantic deduplication for HackFinder Global."""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import and_, or_, select

from core.database import AsyncSessionLocal
from core.models import FinalOpportunity

logger = logging.getLogger(__name__)

# ~1 degree latitude ≈ 111 km
KM_PER_DEG_LAT = 111.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class DeduplicationEngine:
    def __init__(
        self,
        similarity_threshold: float = 0.08,
        spatial_radius_km: float = 5.0,
        temporal_window_hours: int = 48,
    ):
        # 0.08 cosine distance ≈ 92% similarity
        self.similarity_threshold = similarity_threshold
        self.spatial_radius_km = spatial_radius_km
        self.temporal_window = timedelta(hours=temporal_window_hours)

    async def evaluate_incoming_record(
        self, record_data: dict, vector: list[float] | None
    ) -> bool:
        """
        Returns True if a conflict is detected and merged, False if unique.

        Order:
          A) Exact platform_post_id / registration_url
          B) Same-day (±window) + nearby geo candidates, then pgvector
          C) Global pgvector fallback when geo/time missing
        """
        async with AsyncSessionLocal() as session:
            if await self._tier_a_exact(session, record_data):
                return True
            if vector is None:
                logger.info(
                    "No embedding for %r — skipping semantic tiers B/C",
                    record_data.get("title"),
                )
                return False
            if await self._tier_b_spatial_temporal(session, record_data, vector):
                return True
            if await self._tier_c_semantic_global(session, record_data, vector):
                return True
            return False

    async def _tier_a_exact(self, session, record_data: dict) -> bool:
        reg_url = record_data.get("registration_url")
        clauses = [FinalOpportunity.platform_post_id == record_data["platform_post_id"]]
        if reg_url:
            clauses.append(FinalOpportunity.registration_url == reg_url)

        result = await session.execute(select(FinalOpportunity).where(or_(*clauses)))
        exact = result.scalars().first()
        if exact:
            logger.info("Exact duplicate (Tier A): %s", record_data.get("title"))
            await self._merge_records(session, exact, record_data)
            return True
        return False

    async def _tier_b_spatial_temporal(
        self, session, record_data: dict, vector: list[float]
    ) -> bool:
        start = self._parse_dt(record_data.get("start_datetime_utc"))
        lat = record_data.get("latitude")
        lng = record_data.get("longitude")

        # Without both time and geo, skip to Tier C
        if start is None or lat is None or lng is None:
            return False

        window_start = start - self.temporal_window
        window_end = start + self.temporal_window
        radius_m = self.spatial_radius_km * 1000.0

        # Prefer PostGIS ST_DWithin on geography(location); fall back to bbox + Haversine
        candidates = await self._candidates_postgis(
            session, lat, lng, radius_m, window_start, window_end, vector
        )
        if candidates is None:
            candidates = await self._candidates_bbox(
                session, lat, lng, window_start, window_end, vector
            )

        for candidate in candidates:
            if candidate.latitude is None or candidate.longitude is None:
                continue
            dist = _haversine_km(lat, lng, candidate.latitude, candidate.longitude)
            if dist <= self.spatial_radius_km:
                logger.warning(
                    "Spatial/temporal semantic collision (Tier B, %.2f km): %s",
                    dist,
                    candidate.title,
                )
                await self._merge_records(session, candidate, record_data)
                return True
        return False

    async def _candidates_postgis(
        self, session, lat, lng, radius_m, window_start, window_end, vector
    ):
        from sqlalchemy import text

        try:
            sql = text(
                """
                SELECT id FROM final_opportunities
                WHERE start_datetime_utc IS NOT NULL
                  AND start_datetime_utc >= :ws
                  AND start_datetime_utc <= :we
                  AND location IS NOT NULL
                  AND embedding IS NOT NULL
                  AND ST_DWithin(
                        location,
                        ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                        :radius_m
                  )
                  AND (embedding <=> CAST(:vec AS vector)) < :threshold
                ORDER BY embedding <=> CAST(:vec AS vector)
                LIMIT 5
                """
            )
            # pgvector literal
            vec_literal = "[" + ",".join(str(float(x)) for x in vector) + "]"
            result = await session.execute(
                sql,
                {
                    "ws": window_start,
                    "we": window_end,
                    "lng": lng,
                    "lat": lat,
                    "radius_m": radius_m,
                    "vec": vec_literal,
                    "threshold": self.similarity_threshold,
                },
            )
            ids = [row[0] for row in result.all()]
            if not ids:
                return []
            rows = await session.execute(
                select(FinalOpportunity).where(FinalOpportunity.id.in_(ids))
            )
            return list(rows.scalars().all())
        except Exception as exc:
            logger.info("PostGIS ST_DWithin path unavailable (%s); using bbox fallback", exc)
            try:
                await session.rollback()
            except Exception:
                pass
            return None

    async def _candidates_bbox(
        self, session, lat, lng, window_start, window_end, vector
    ):
        lat_delta = self.spatial_radius_km / KM_PER_DEG_LAT
        lng_delta = self.spatial_radius_km / (
            KM_PER_DEG_LAT * max(0.2, abs(math.cos(math.radians(lat))))
        )
        query = (
            select(FinalOpportunity)
            .where(
                and_(
                    FinalOpportunity.start_datetime_utc.is_not(None),
                    FinalOpportunity.start_datetime_utc >= window_start,
                    FinalOpportunity.start_datetime_utc <= window_end,
                    FinalOpportunity.latitude.is_not(None),
                    FinalOpportunity.longitude.is_not(None),
                    FinalOpportunity.latitude.between(lat - lat_delta, lat + lat_delta),
                    FinalOpportunity.longitude.between(lng - lng_delta, lng + lng_delta),
                    FinalOpportunity.embedding.is_not(None),
                    FinalOpportunity.embedding.cosine_distance(vector)
                    < self.similarity_threshold,
                )
            )
            .order_by(FinalOpportunity.embedding.cosine_distance(vector))
            .limit(5)
        )
        result = await session.execute(query)
        return list(result.scalars().all())
    async def _tier_c_semantic_global(
        self, session, record_data: dict, vector: list[float]
    ) -> bool:
        """Fallback when geo/time unavailable — previous global vector match behavior."""
        query = (
            select(FinalOpportunity)
            .where(
                and_(
                    FinalOpportunity.embedding.is_not(None),
                    FinalOpportunity.embedding.cosine_distance(vector)
                    < self.similarity_threshold,
                )
            )
            .order_by(FinalOpportunity.embedding.cosine_distance(vector))
            .limit(1)
        )
        result = await session.execute(query)
        match = result.scalars().first()
        if match:
            logger.warning("Semantic collision (Tier C fallback): %s", match.title)
            await self._merge_records(session, match, record_data)
            return True
        return False

    async def _merge_records(
        self, session, existing: FinalOpportunity, incoming: dict
    ) -> None:
        changed = False
        fillable = (
            "registration_url",
            "city",
            "country",
            "latitude",
            "longitude",
            "start_datetime_utc",
            "end_datetime_utc",
            "local_timezone",
            "domain",
            "subcategory",
            "format",
        )
        for key in fillable:
            incoming_val = incoming.get(key)
            if incoming_val is None:
                continue
            if getattr(existing, key, None) in (None, ""):
                setattr(existing, key, incoming_val)
                changed = True

        if changed:
            await session.commit()
            logger.info("Merged missing fields into parent record id=%s", existing.id)

    @staticmethod
    def _parse_dt(value) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value
        if isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                return None
        return None
