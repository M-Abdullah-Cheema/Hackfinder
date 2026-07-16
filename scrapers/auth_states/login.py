"""
One-time Playwright login helper.

Run this script, log in to Instagram in the browser window that opens,
then press Enter. Your session is saved to state.json.

Usage:
    python scrapers/auth_states/login.py
"""
import asyncio
import os
from playwright.async_api import async_playwright

STATE_PATH = os.path.join(os.path.dirname(__file__), "state.json")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()
        await page.goto("https://www.instagram.com/accounts/login/", wait_until="networkidle")

        print("\n👤 Please log in to Instagram in the browser window.")
        print("   Once you can see your Instagram feed, press Enter here.\n")
        input("   >>> Press Enter when logged in: ")

        await context.storage_state(path=STATE_PATH)
        await browser.close()

        print(f"\n✅ Session saved to: {STATE_PATH}")
        print("   You can now run the scraping pipeline normally.\n")


if __name__ == "__main__":
    asyncio.run(main())
