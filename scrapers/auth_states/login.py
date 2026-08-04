"""
One-time Playwright login / checkpoint helper.

Opens a visible Chrome window with your existing Instagram session (if any).
Complete login or the "Confirm you're human" challenge, then press Enter
so the fresh session is saved to state.json.

Usage:
    python scrapers/auth_states/login.py
"""
import asyncio
import os
from playwright.async_api import async_playwright

STATE_PATH = os.path.join(os.path.dirname(__file__), "state.json")


async def main():
    os.environ.setdefault(
        "PLAYWRIGHT_BROWSERS_PATH",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "ms-playwright"),
    )

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        ctx_kwargs = {
            "viewport": {"width": 1280, "height": 800},
            "locale": "en-US",
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
            "\nIn the browser window:\n"
            "  1) If you see 'Confirm you're human' — click Continue and finish it.\n"
            "  2) If you see a login form — log in normally.\n"
            "  3) When you can see the Instagram home feed OR a profile grid with posts,\n"
            "     come back here and press Enter.\n"
        )
        input(">>> Press Enter when Instagram is usable: ")

        final_url = page.url or ""
        body = ""
        try:
            body = await page.evaluate(
                "() => (document.body && document.body.innerText || '').slice(0, 500)"
            )
        except Exception:
            pass

        if (
            "accounts/suspended" in final_url
            or "accounts/login" in final_url
            or "confirm you're human" in body.lower()
            or "confirm you’re human" in body.lower()
        ):
            print(
                "\n[WARN] Still looks blocked/logged-out.\n"
                f"  url={final_url}\n"
                "  Finish the checkpoint fully, then run this script again.\n"
            )
        else:
            print(f"\n[ok] Current URL looks usable: {final_url}")

        await context.storage_state(path=STATE_PATH)
        await browser.close()
        print(f"[OK] Session saved to: {STATE_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
