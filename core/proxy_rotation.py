"""Proxy rotation helpers for Scrapy + Playwright (ScraperAPI / residential)."""
from __future__ import annotations

import logging
import os
import random
import urllib.parse
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _env(*keys: str, default: str = "") -> str:
    for key in keys:
        value = os.getenv(key, "").strip()
        if value:
            return value
    return default


def scraperapi_key() -> str:
    key = _env("PROXY_API_KEY", "SCRAPERAPI_KEY")
    # Ignore common placeholders so Instagram does not route through a fake proxy
    if not key or key.lower() in {"proxy_api_key", "your_scraperapi_key_here", "changeme"}:
        return ""
    if key.startswith("your_"):
        return ""
    return key


def residential_proxy_config() -> Optional[dict[str, str]]:
    """
    Bright Data / Oxylabs / Smartproxy style credentials from env.

    PROXY_SERVER=http://host:port
    PROXY_USERNAME=...
    PROXY_PASSWORD=...
    """
    server = _env("PROXY_SERVER", "RESIDENTIAL_PROXY_SERVER")
    if not server:
        return None
    return {
        "server": server,
        "username": _env("PROXY_USERNAME", "RESIDENTIAL_PROXY_USERNAME"),
        "password": _env("PROXY_PASSWORD", "RESIDENTIAL_PROXY_PASSWORD"),
    }


def wrap_url_via_scraperapi(target_url: str, *, render: bool = True) -> Optional[str]:
    """Return a ScraperAPI gateway URL, or None if no API key is configured."""
    key = scraperapi_key()
    if not key or key.startswith("your_"):
        return None
    base = _env("SCRAPERAPI_URL", default="https://api.scraperapi.com/")
    payload = {
        "api_key": key,
        "url": target_url,
        "render": "true" if render else "false",
        "country_code": _env("PROXY_COUNTRY", default="us"),
    }
    return f"{base}?{urllib.parse.urlencode(payload)}"


def playwright_proxy() -> Optional[dict[str, str]]:
    """
    Proxy dict for Playwright browser.new_context(proxy=...).

    Preference order:
      1) Residential PROXY_SERVER credentials
      2) ScraperAPI proxy endpoint (http://scraperapi:KEY@proxy-server.scraperapi.com:8001)
    """
    residential = residential_proxy_config()
    if residential and residential.get("server"):
        cfg: dict[str, str] = {"server": residential["server"]}
        if residential.get("username"):
            cfg["username"] = residential["username"]
        if residential.get("password"):
            cfg["password"] = residential["password"]
        logger.info("[proxy] Using residential proxy for Playwright")
        return cfg

    key = scraperapi_key()
    if key and not key.startswith("your_"):
        # ScraperAPI official Playwright/proxy mode
        logger.info("[proxy] Using ScraperAPI proxy for Playwright")
        return {
            "server": "http://proxy-server.scraperapi.com:8001",
            "username": "scraperapi",
            "password": key,
        }

    return None


def scrapy_proxy_meta(force_social: bool = False) -> dict[str, Any]:
    """
    Build Scrapy request.meta + headers for proxy routing.
    Returns empty dict when no proxy is configured (direct connect).
    """
    residential = residential_proxy_config()
    if residential and residential.get("server"):
        import base64

        user = residential.get("username", "")
        password = residential.get("password", "")
        auth = base64.b64encode(f"{user}:{password}".encode()).decode()
        return {
            "proxy": residential["server"],
            "proxy_auth_header": f"Basic {auth}",
        }

    key = scraperapi_key()
    if key and not key.startswith("your_"):
        # Route via authenticated proxy endpoint
        return {
            "proxy": f"http://scraperapi:{urllib.parse.quote(key)}@proxy-server.scraperapi.com:8001",
        }

    if force_social:
        logger.warning(
            "[proxy] Social scrape requested but PROXY_API_KEY / PROXY_SERVER unset — direct connect"
        )
    return {}


def pick_user_agent() -> str:
    agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    ]
    return random.choice(agents)
