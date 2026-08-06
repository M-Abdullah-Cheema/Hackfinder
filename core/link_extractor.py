"""Extract and normalize registration / apply URLs from social + OCR text."""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse

# Prefer real registration destinations over social/profile noise
_PREFERRED = (
    "bit.ly",
    "tinyurl.com",
    "t.co",
    "goo.gl",
    "forms.gle",
    "docs.google.com",
    "lu.ma",
    "luma.com",
    "eventbrite.",
    "meetup.com",
    "devpost.com",
    "hackerearth.com",
    "mlh.io",
    "linktr.ee",
    "linktree.com",
    "notion.site",
    "typeform.com",
    "airtable.com",
    "zoom.us",
    "discord.gg",
    "discord.com",
    "partiful.com",
    "hopin.com",
    "socradar",
    "apply.",
    "register.",
)

_BLOCKED = (
    "instagram.com",
    "facebook.com",
    "fb.me",
    "twitter.com",
    "x.com",
    "tiktok.com",
    "youtube.com",
    "youtu.be",
    "linkedin.com",
    "wa.me",
    "whatsapp.com",
)

# Full URLs + bare short links people paste without scheme
_URL_RE = re.compile(
    r"(?i)\b("
    r"https?://[^\s<>\"']+"
    r"|bit\.ly/[A-Za-z0-9_-]+"
    r"|forms\.gle/[A-Za-z0-9_-]+"
    r"|lu\.ma/[A-Za-z0-9_-]+"
    r"|linktr\.ee/[A-Za-z0-9_.-]+"
    r"|t\.co/[A-Za-z0-9]+"
    r")"
)


def _normalize(raw: str) -> str:
    url = raw.strip().rstrip(").,;]>'\"")
    if not url:
        return ""
    # Reject truncated / caption-junk "URLs"
    if "..." in url or " " in url or "link in bio" in url.lower():
        return ""
    if not re.match(r"(?i)^https?://", url):
        url = "https://" + url
    return url


def is_junk_url(url: str | None) -> bool:
    if not url:
        return True
    normalized = _normalize(url)
    if not normalized:
        return True
    return _score(normalized) < 0


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def _score(url: str) -> int:
    host = _host(url)
    path = (urlparse(url).path or "").lower()
    if any(b in host for b in _BLOCKED):
        return -100
    score = 0
    for pref in _PREFERRED:
        if pref in host or pref in url.lower():
            score += 50
            break
    if any(k in path for k in ("register", "apply", "signup", "rsvp", "form", "ticket")):
        score += 20
    if any(k in host for k in ("register", "apply", "event")):
        score += 15
    return score


def extract_registration_url(text: str | None) -> Optional[str]:
    """Return the best registration-like URL found in free text, or None."""
    if not text:
        return None
    candidates: list[tuple[int, str]] = []
    for match in _URL_RE.finditer(text):
        url = _normalize(match.group(1))
        if not url:
            continue
        score = _score(url)
        if score < 0:
            continue
        candidates.append((score, url))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    best_score, best = candidates[0]
    # Accept preferred links always; other http(s) only if they look like apply/register
    if best_score >= 50 or best_score >= 20:
        return best
    # Fallback: first non-blocked http link
    for score, url in candidates:
        if score >= 0 and _host(url):
            return url
    return None


def instagram_post_url(platform_post_id: str | None) -> Optional[str]:
    """Fallback deep-link to the source Instagram post."""
    if not platform_post_id:
        return None
    pid = platform_post_id.strip()
    if pid.startswith("ig_seed_"):
        return None
    if pid.startswith("ig_"):
        code = pid[3:]
        if code:
            return f"https://www.instagram.com/p/{code}/"
    return None


def resolve_registration_url(
    *,
    llm_url: str | None,
    text: str | None,
    platform_post_id: str | None = None,
) -> Optional[str]:
    """
    Prefer LLM URL when it looks real, else regex from caption/OCR,
    else Instagram post permalink so cards always have a useful link.
    """
    for candidate in (llm_url, extract_registration_url(text)):
        if not candidate:
            continue
        url = _normalize(str(candidate))
        if not url:
            continue
        if _score(url) < 0:
            continue
        return url
    return instagram_post_url(platform_post_id)
