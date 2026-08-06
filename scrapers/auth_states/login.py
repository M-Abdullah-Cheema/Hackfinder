"""
Playwright Instagram login / OTP / human-check helper.

Opens a visible browser with your existing session (if any). Complete:
  - password login
  - Gmail/email security code (OTP)
  - "Confirm you're human" checkpoint

Session is saved only when Instagram no longer looks blocked
(unless you type force).

Usage:
    python scrapers/auth_states/login.py
"""
from __future__ import annotations

import asyncio
import os
from playwright.async_api import async_playwright

STATE_PATH = os.path.join(os.path.dirname(__file__), "state.json")


def _blocked(url: str, body: str) -> bool:
    u = (url or "").lower()
    b = (body or "").lower()
    needles = (
        "accounts/login",
        "accounts/suspended",
        "/challenge",
        "confirm you're human",
        "confirm you’re human",
        "enter the code",
        "security code",
        "we sent a code",
        "check your email",
        "suspicious login",
    )
    return any(n in u or n in b for n in needles)


async def main() -> int:
    os.environ.setdefault(
        "PLAYWRIGHT_BROWSERS_PATH",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "ms-playwright"),
    )

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        ctx_kwargs = {
            "viewport": {"width": 1280, "height": 900},
            "locale": "en-US",
            "timezone_id": "Asia/Karachi",
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        }

        if os.path.exists(STATE_PATH) and os.path.getsize(STATE_PATH) > 10:
            context = await browser.new_context(storage_state=STATE_PATH, **ctx_kwargs)
            print(f"[auth] Loaded existing session from {STATE_PATH}")
        else:
            context = await browser.new_context(**ctx_kwargs)
            print("[auth] No existing session — starting fresh login")

        page = await context.new_page()
        await page.goto("https://www.instagram.com/", wait_until="domcontentloaded")

        print(
            "\nIn the browser, finish EVERY step Instagram shows:\n"
            "  1) Username / password\n"
            "  2) Gmail / email OTP (security code)\n"
            "  3) Confirm you're human → Continue\n"
            "  4) Wait until the normal HOME FEED is visible\n\n"
            "Then come back here:\n"
            "  - Press Enter to save (only if feed looks good)\n"
            "  - Or type force then Enter to save anyway\n"
        )
        answer = input(">>> Press Enter when ready (or 'force'): ").strip().lower()

        final_url = page.url or ""
        try:
            body = await page.evaluate(
                "() => (document.body && document.body.innerText || '').slice(0, 800)"
            )
        except Exception:
            body = ""

        if answer != "force" and _blocked(final_url, body or ""):
            print(
                "\n[FAIL] Still on login / OTP / human-check / suspended.\n"
                f"  url={final_url}\n"
                "  Session was NOT overwritten. Finish the challenge and run again.\n"
            )
            await browser.close()
            return 1

        await context.storage_state(path=STATE_PATH)
        await browser.close()
        print(f"\n[ok] Current URL: {final_url}")
        print(f"[OK] Session saved to: {STATE_PATH}")
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
