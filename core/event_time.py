"""Shared helpers for upcoming-event filtering."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_upcoming_opportunity(
    *,
    start_datetime_utc: Optional[datetime],
    end_datetime_utc: Optional[datetime],
    now: Optional[datetime] = None,
    include_undated: bool = True,
) -> bool:
    """
    True for events that are still useful:
      - end time in the future (ongoing), or
      - start time at/after the start of today (UTC), or
      - no dates known (include_undated).
    Clearly past events are excluded.
    """
    now = now or datetime.now(timezone.utc)
    start = _as_utc(start_datetime_utc)
    end = _as_utc(end_datetime_utc)
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if end is not None and end >= now:
        return True
    if start is not None and start >= start_of_today:
        return True
    if start is not None and end is None and start < start_of_today:
        return False
    if end is not None and end < now:
        return False
    if start is None and end is None:
        return include_undated
    return False


def row_is_upcoming(row: Any, *, include_undated: bool = True) -> bool:
    return is_upcoming_opportunity(
        start_datetime_utc=getattr(row, "start_datetime_utc", None),
        end_datetime_utc=getattr(row, "end_datetime_utc", None),
        include_undated=include_undated,
    )
