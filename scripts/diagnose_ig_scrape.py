"""
Deep Instagram scrape diagnostic — saves artifacts under scripts/_ig_debug/

Usage:
    python scripts/diagnose_ig_scrape.py
    python scripts/diagnose_ig_scrape.py https://www.instagram.com/gdgcloud.islamabad/
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(
    os.environ.get("LOCALAPPDATA", ""), "ms-playwright"
)
# Never use broken placeholder proxies during diagnose
os.environ["USE_PLAYWRIGHT_PROXY"] = "0"
os.environ["PROXY_API_KEY"] = ""

from core.pipeline_config import AUTH_STATE_PATH
from core.proxy_rotation import pick_user_agent
from playwright.async_api import async_playwright


OUT_DIR = os.path.join(os.path.dirname(__file__), "_ig_debug")


async def diagnose(url: str) -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report: dict = {"url": url, "stamp": stamp}

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        try:
            state_ok = os.path.exists(AUTH_STATE_PATH) and os.path.getsize(AUTH_STATE_PATH) > 10
            report["auth_state_path"] = AUTH_STATE_PATH
            report["auth_state_ok"] = state_ok
            report["auth_state_bytes"] = (
                os.path.getsize(AUTH_STATE_PATH) if state_ok else 0
            )

            ctx_kwargs = {
                "user_agent": pick_user_agent(),
                "viewport": {"width": 1280, "height": 900},
                "locale": "en-US",
                "timezone_id": "Asia/Karachi",
            }
            if state_ok:
                context = await browser.new_context(
                    storage_state=AUTH_STATE_PATH, **ctx_kwargs
                )
            else:
                context = await browser.new_context(**ctx_kwargs)

            await context.set_extra_http_headers(
                {"Accept-Language": "en-US,en;q=0.9"}
            )
            page = await context.new_page()
            await page.add_init_script(
                """
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                """
            )

            api_hits: list[dict] = []

            async def on_response(response):
                try:
                    u = response.url
                    interesting = any(
                        t in u
                        for t in (
                            "web_profile_info",
                            "graphql/query",
                            "api/v1/feed/user",
                            "api/v1/users/web_profile_info",
                            "polaris",
                        )
                    )
                    if interesting:
                        api_hits.append(
                            {
                                "status": response.status,
                                "url": u[:180],
                                "ctype": (response.headers.get("content-type") or "")[:60],
                            }
                        )
                except Exception:
                    pass

            page.on("response", on_response)

            print(f"[nav] goto {url}")
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            except Exception as exc:
                report["goto_error"] = str(exc)
                print(f"[nav] goto error: {exc}")

            await asyncio.sleep(4)
            for _ in range(5):
                await page.mouse.wheel(0, 2000)
                await asyncio.sleep(1.0)

            # Cookie / consent banners
            for sel in [
                'button:has-text("Allow all cookies")',
                'button:has-text("Accept")',
                'button:has-text("Allow essential and optional cookies")',
                'button:has-text("Decline optional cookies")',
            ]:
                try:
                    btn = page.locator(sel).first
                    if await btn.count() > 0 and await btn.is_visible():
                        await btn.click(timeout=2000)
                        report["clicked_consent"] = sel
                        await asyncio.sleep(1.5)
                        break
                except Exception:
                    pass

            final_url = page.url
            title = await page.title()
            report["final_url"] = final_url
            report["title"] = title

            login_signals = {
                "url_has_login": "accounts/login" in (final_url or ""),
                "url_has_challenge": "challenge" in (final_url or ""),
                "username_input": await page.locator('input[name="username"]').count(),
                "password_input": await page.locator('input[name="password"]').count(),
            }
            report["login_signals"] = login_signals

            body_text = await page.evaluate(
                "() => (document.body && document.body.innerText || '').slice(0, 2500)"
            )
            report["body_text_sample"] = body_text
            report["body_mentions"] = {
                "log_in": "log in" in body_text.lower() or "log in" in body_text.lower(),
                "signup": "sign up" in body_text.lower(),
                "posts": "posts" in body_text.lower(),
                "followers": "followers" in body_text.lower(),
                "something_went_wrong": "something went wrong" in body_text.lower(),
                "try_again": "try again" in body_text.lower(),
                "suspended": "suspended" in body_text.lower(),
            }

            dom_stats = await page.evaluate(
                """
                () => {
                  const anchors = Array.from(
                    document.querySelectorAll('a[href*="/p/"], a[href*="/reel/"]')
                  ).map(a => a.getAttribute('href'));
                  const imgs = document.querySelectorAll('img').length;
                  const articles = document.querySelectorAll('article').length;
                  const main = !!document.querySelector('main');
                  return {
                    post_anchors: anchors.slice(0, 20),
                    post_anchor_count: anchors.length,
                    img_count: imgs,
                    article_count: articles,
                    has_main: main,
                    html_len: document.documentElement.outerHTML.length,
                  };
                }
                """
            )
            report["dom_stats"] = dom_stats
            report["api_hits"] = api_hits
            report["api_hit_count"] = len(api_hits)

            shot = os.path.join(OUT_DIR, f"{stamp}_screenshot.png")
            html_path = os.path.join(OUT_DIR, f"{stamp}_page.html")
            await page.screenshot(path=shot, full_page=True)
            html = await page.content()
            with open(html_path, "w", encoding="utf-8") as fh:
                fh.write(html)
            report["screenshot"] = shot
            report["html_path"] = html_path

            # Quick regex on HTML for shortcodes
            shortcodes = re.findall(r"/(?:p|reel)/([A-Za-z0-9_-]{5,})", html)
            report["shortcodes_in_html"] = list(dict.fromkeys(shortcodes))[:15]

        finally:
            await browser.close()

    report_path = os.path.join(OUT_DIR, f"{stamp}_report.json")
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)

    print(json.dumps({k: v for k, v in report.items() if k != "body_text_sample"}, indent=2))
    print(f"\n[body sample]\n{(report.get('body_text_sample') or '')[:800]}")
    print(f"\n[saved] {report_path}")
    return 0 if (report.get("dom_stats") or {}).get("post_anchor_count", 0) > 0 else 1


if __name__ == "__main__":
    target = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "https://www.instagram.com/gdgcloud.islamabad/"
    )
    raise SystemExit(asyncio.run(diagnose(target)))
