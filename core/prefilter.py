"""Cheap keyword / signal pre-filter before expensive AI extraction."""
from __future__ import annotations

import re
from typing import Iterable

# Keep broad enough for tech + early global domains; refine with ML later.
POSITIVE_KEYWORDS: tuple[str, ...] = (
    "hackathon",
    "workshop",
    "meetup",
    "conference",
    "seminar",
    "webinar",
    "internship",
    "fellowship",
    "scholarship",
    "bootcamp",
    "job fair",
    "career fair",
    "register",
    "registration",
    "rsvp",
    "apply now",
    "call for",
    "cfp",
    "deadline",
    "event",
    "summit",
    "demo day",
    "pitch",
    "accelerator",
    "incubator",
    "community",
    "networking",
    "speaker",
    "panel",
    "talk",
    "session",
    "luma",
    "eventbrite",
    "meetup.com",
)

NEGATIVE_KEYWORDS: tuple[str, ...] = (
    "giveaway only",
    "follow for follow",
    "meme",
    "birthday party",
    "personal annoucement",  # common typo variants still caught loosely below
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def score_opportunity_text(text: str, extra_keywords: Iterable[str] | None = None) -> int:
    """Return a simple relevance score (>=1 means keep)."""
    normalized = _normalize(text)
    if not normalized or len(normalized) < 40:
        return 0

    score = 0
    keywords = list(POSITIVE_KEYWORDS)
    if extra_keywords:
        keywords.extend(k.lower() for k in extra_keywords)

    for kw in keywords:
        if kw in normalized:
            score += 1

    for bad in NEGATIVE_KEYWORDS:
        if bad in normalized:
            score -= 2

    # Strong signal: explicit URL / form link
    if "http://" in normalized or "https://" in normalized or "forms.gle" in normalized:
        score += 1

    return score


def is_likely_opportunity(text: str, min_score: int = 1) -> bool:
    return score_opportunity_text(text) >= min_score
