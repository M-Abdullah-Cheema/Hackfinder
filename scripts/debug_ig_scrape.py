"""
Instagram scrape smoke test.

Modes:
  1) Extraction only (no DB) — proves Instagram parsing works:
       python scripts/debug_ig_scrape.py --no-db
  2) Full scrape_task (needs Supabase):
       python scripts/debug_ig_scrape.py
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

os.environ.setdefault(
    "PLAYWRIGHT_BROWSERS_PATH",
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "ms-playwright"),
)


async def extract_only(url: str) -> list[dict]:
    """Run the improved Playwright extraction without touching the database."""
    from tasks.workflows import (
        _extract_posts_from_api_payload,
        _normalize_ig_url,
    )
    from core.pipeline_config import AUTH_STATE_PATH
    from playwright.async_api import async_playwright

    target = _normalize_ig_url(url)
    posts: list[dict] = []
    seen: set[str] = set()

    def add(batch: list[dict]) -> None:
        for p in batch:
            pid = p.get("platform_post_id")
            if pid and pid not in seen:
                seen.add(pid)
                posts.append(p)

    state_path = AUTH_STATE_PATH
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        try:
            ctx_kwargs = {
                "user_agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "viewport": {"width": 1280, "height": 900},
                "locale": "en-US",
            }
            if os.path.exists(state_path) and os.path.getsize(state_path) > 10:
                context = await browser.new_context(
                    storage_state=state_path, **ctx_kwargs
                )
                print(f"[auth] loaded {state_path}")
            else:
                context = await browser.new_context(**ctx_kwargs)
                print("[auth] MISSING state.json")

            page = await context.new_page()
            await page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
            )

            captured: list[dict] = []

            async def on_response(response):
                try:
                    u = response.url
                    if response.status == 200 and any(
                        t in u
                        for t in (
                            "web_profile_info",
                            "graphql/query",
                            "api/v1/feed/user",
                            "polaris",
                        )
                    ):
                        data = await response.json()
                        if isinstance(data, dict):
                            captured.append(data)
                except Exception:
                    pass

            page.on("response", on_response)
            print(f"[nav] {target}")
            await page.goto(target, wait_until="domcontentloaded", timeout=60_000)
            await asyncio.sleep(3)
            for _ in range(4):
                await page.mouse.wheel(0, 1800)
                await asyncio.sleep(1.2)

            print(f"[nav] landed on {page.url}")
            if "accounts/login" in (page.url or ""):
                print("[auth] LOGIN WALL — re-run login.py")
                return []

            for data in captured:
                add(_extract_posts_from_api_payload(data))
            print(f"[api] captured payloads={len(captured)} posts={len(posts)}")

            grid = await page.evaluate(
                """
                () => {
                  const out = [], seen = new Set();
                  for (const a of document.querySelectorAll('a[href*="/p/"], a[href*="/reel/"]')) {
                    const href = a.getAttribute('href') || '';
                    const m = href.match(/\\/(p|reel)\\/([^\\/?#]+)/);
                    if (!m || seen.has(m[2])) continue;
                    seen.add(m[2]);
                    const img = a.querySelector('img');
                    out.push({
                      shortcode: m[2],
                      image_url: img ? (img.src || '') : '',
                      alt: img ? (img.alt || '') : '',
                    });
                  }
                  return out.slice(0, 8);
                }
                """
            )
            add(
                [
                    {
                        "platform_post_id": f"ig_{g['shortcode']}",
                        "caption": g.get("alt") or "",
                        "image_urls": [g["image_url"]] if g.get("image_url") else [],
                    }
                    for g in (grid or [])
                ]
            )
            print(f"[dom] grid_links={len(grid or [])} total_posts={len(posts)}")
        finally:
            await browser.close()

    return posts


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    no_db = "--no-db" in sys.argv
    url = args[0] if args else "https://www.instagram.com/gdgcloud.islamabad/"

    if no_db:
        print(f"[*] Extraction-only mode for: {url}")
        posts = asyncio.run(extract_only(url))
        for p in posts:
            cap = (p.get("caption") or "")[:60].encode("ascii", "ignore").decode()
            print(
                f"  - {p['platform_post_id']} | imgs={len(p.get('image_urls') or [])} | {cap!r}"
            )
        print(f"[*] Total posts: {len(posts)}")
        return 0 if posts else 1

    from tasks.workflows import scrape_task

    print(f"[*] Full scrape_task for: {url}")
    result = scrape_task.run(url)
    print(f"[*] Result UUID: {result}")
    return 0 if result else 1


if __name__ == "__main__":
    raise SystemExit(main())
