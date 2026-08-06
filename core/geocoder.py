"""City/country → lat/lng resolution with local aliases + Nominatim fallback."""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Fast path for common HackFinder cities (no network).
CITY_ALIASES: dict[str, tuple[float, float, str, str]] = {
    # Pakistan
    "islamabad": (33.6844, 73.0479, "Islamabad", "Pakistan"),
    "rawalpindi": (33.5651, 73.0169, "Rawalpindi", "Pakistan"),
    "karachi": (24.8607, 67.0011, "Karachi", "Pakistan"),
    "lahore": (31.5204, 74.3587, "Lahore", "Pakistan"),
    "peshawar": (34.0151, 71.5249, "Peshawar", "Pakistan"),
    "faisalabad": (31.4504, 73.1350, "Faisalabad", "Pakistan"),
    "multan": (30.1575, 71.5249, "Multan", "Pakistan"),
    "nust": (33.6425, 72.9928, "Islamabad", "Pakistan"),
    "i-9": (33.6580, 73.0620, "Islamabad", "Pakistan"),
    "i-9/3": (33.6580, 73.0620, "Islamabad", "Pakistan"),
    # Regional / global hubs often in LabLab / tech posts
    "dubai": (25.2048, 55.2708, "Dubai", "United Arab Emirates"),
    "abu dhabi": (24.4539, 54.3773, "Abu Dhabi", "United Arab Emirates"),
    "bengaluru": (12.9716, 77.5946, "Bengaluru", "India"),
    "bangalore": (12.9716, 77.5946, "Bengaluru", "India"),
    "mumbai": (19.0760, 72.8777, "Mumbai", "India"),
    "delhi": (28.6139, 77.2090, "New Delhi", "India"),
    "new delhi": (28.6139, 77.2090, "New Delhi", "India"),
    "hyderabad": (17.3850, 78.4867, "Hyderabad", "India"),
    "singapore": (1.3521, 103.8198, "Singapore", "Singapore"),
    "london": (51.5074, -0.1278, "London", "United Kingdom"),
    "san francisco": (37.7749, -122.4194, "San Francisco", "United States"),
    "new york": (40.7128, -74.0060, "New York", "United States"),
    "seattle": (47.6062, -122.3321, "Seattle", "United States"),
    "austin": (30.2672, -97.7431, "Austin", "United States"),
    "santa clara": (37.3541, -121.9552, "Santa Clara", "United States"),
    "toronto": (43.6532, -79.3832, "Toronto", "Canada"),
    "berlin": (52.5200, 13.4050, "Berlin", "Germany"),
}


def _norm(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def _cache_path() -> Path:
    root = Path(__file__).resolve().parent.parent / "scrapers" / "auth_states"
    root.mkdir(parents=True, exist_ok=True)
    return root / "geocode_cache.json"


def _load_cache() -> dict:
    path = _cache_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(cache: dict) -> None:
    try:
        _cache_path().write_text(json.dumps(cache, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("Could not write geocode cache: %s", exc)


def _countries_match(stated: str | None, canon: str) -> bool:
    if not stated:
        return True
    abbrev = {
        "pk": "pakistan",
        "us": "united states",
        "usa": "united states",
        "uk": "united kingdom",
        "uae": "united arab emirates",
        "in": "india",
    }
    left = abbrev.get(_norm(stated), _norm(stated))
    right = _norm(canon)
    return left == right or left in right or right in left


def _alias_lookup(city: str, country: str | None) -> Optional[dict]:
    key = _norm(city)
    if not key:
        return None
    hit = CITY_ALIASES.get(key)
    if not hit:
        # Venue fluff like "Based Coworking Islamabad" / "I-9/3"
        for alias, coords in CITY_ALIASES.items():
            if alias in key or key.startswith(alias):
                hit = coords
                break
    if not hit:
        return None
    lat, lng, canon_city, canon_country = hit
    if not _countries_match(country, canon_country):
        return None
    return {
        "latitude": lat,
        "longitude": lng,
        "city": canon_city,
        "country": country or canon_country,
        "source": "alias",
    }


def _nominatim_lookup(city: str, country: str | None) -> Optional[dict]:
    if os.getenv("GEOCODER_ENABLED", "1").strip() in {"0", "false", "no"}:
        return None

    query = ", ".join(part for part in [city, country] if part)
    if not query.strip():
        return None

    cache = _load_cache()
    cache_key = _norm(query)
    if cache_key in cache:
        return {**cache[cache_key], "source": "cache"}

    # Respect Nominatim usage policy: identify app + 1 req/sec
    user_agent = os.getenv(
        "NOMINATIM_USER_AGENT",
        "HackFinder/1.0 (hackathon aggregator; local-dev)",
    )
    params = urllib.parse.urlencode(
        {"q": query, "format": "json", "limit": 1, "addressdetails": 1}
    )
    url = f"https://nominatim.openstreetmap.org/search?{params}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": user_agent, "Accept": "application/json"},
    )
    try:
        time.sleep(1.05)
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        logger.warning("Nominatim geocode failed for %r: %s", query, exc)
        return None

    if not data:
        return None

    item = data[0]
    try:
        lat = float(item["lat"])
        lng = float(item["lon"])
    except (KeyError, TypeError, ValueError):
        return None

    address = item.get("address") or {}
    result = {
        "latitude": lat,
        "longitude": lng,
        "city": (
            address.get("city")
            or address.get("town")
            or address.get("village")
            or city
        ),
        "country": address.get("country") or country,
        "source": "nominatim",
    }
    cache[cache_key] = {
        "latitude": result["latitude"],
        "longitude": result["longitude"],
        "city": result["city"],
        "country": result["country"],
    }
    _save_cache(cache)
    return result


def geocode(
    city: str | None,
    country: str | None = None,
    *,
    allow_network: bool = True,
) -> Optional[dict]:
    """
    Resolve city (+ optional country) to coordinates.

    Returns dict with latitude, longitude, city, country, source — or None.
    Never invents pins without a city/place string.
    """
    city_n = (city or "").strip()
    if not city_n:
        return None

    # Skip clearly non-places
    bad = {"online", "virtual", "remote", "zoom", "worldwide", "global", "tba", "tbd"}
    if _norm(city_n) in bad:
        return None

    alias = _alias_lookup(city_n, country)
    if alias:
        return alias

    if allow_network:
        return _nominatim_lookup(city_n, country)
    return None


def enrich_coords(
    *,
    city: str | None,
    country: str | None,
    latitude: float | None,
    longitude: float | None,
    is_remote: bool = False,
) -> dict:
    """
    Fill missing lat/lng from city/country. Preserves existing coords.
    Remote/virtual events keep null coords unless a physical city is stated.
    """
    out = {
        "city": city,
        "country": country,
        "latitude": latitude,
        "longitude": longitude,
    }
    if latitude is not None and longitude is not None:
        return out

    if is_remote and not city:
        return out

    hit = geocode(city, country)
    if not hit:
        return out

    out["latitude"] = hit["latitude"]
    out["longitude"] = hit["longitude"]
    out["city"] = out["city"] or hit.get("city")
    out["country"] = out["country"] or hit.get("country")
    logger.info(
        "[geo] %s → (%.4f, %.4f) via %s",
        out["city"],
        out["latitude"],
        out["longitude"],
        hit.get("source"),
    )
    return out
