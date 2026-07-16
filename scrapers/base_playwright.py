import os
import json
from playwright.async_api import async_playwright

class HeadlessBrowserWrapper:
    """
    Advanced Playwright wrapper equipped with session-cookie injection 
    and authentication state preservation for social media scraping.
    """

    @staticmethod
    async def fetch_rendered_html(url: str, wait_selector: str = None, session_cookies: dict = None) -> str:
        async with async_playwright() as p:
            # 1. Initialize browser instance with anti-fingerprinting parameters
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"]
            )
            
            # Define persistent storage location for session states
            state_path = "scrapers/auth_states/state.json"
            os.makedirs(os.path.dirname(state_path), exist_ok=True)

            # 2. Inject raw session dictionary objects if supplied dynamically via config_jsonb
            if session_cookies:
                context = await browser.new_context()
                formatted_cookies = [
                    {
                        "name": name, 
                        "value": value, 
                        "domain": ".linkedin.com" if "linkedin" in url else ".instagram.com", 
                        "path": "/"
                    }
                    for name, value in session_cookies.items()
                ]
                await context.add_cookies(formatted_cookies)
            
            # 3. Fallback: Automatically load a locally cached authentication state snapshot if it exists
            elif os.path.exists(state_path) and os.path.getsize(state_path) > 0:
                context = await browser.new_context(storage_state=state_path)
            else:
                context = await browser.new_context()

            page = await context.new_page()
            
            # Set structural window viewports to mimic real human monitors
            await page.set_viewport_size({"width": 1280, "height": 800})
            
            # 4. Navigate and parse target
            print(f"🤖 Navigating Headless Session to: {url}")
            await page.goto(url, wait_until="networkidle")

            if wait_selector:
                try:
                    await page.wait_for_selector(wait_selector, timeout=10000)
                except Exception:
                    print(f"⚠️ Timeout waiting for selector: {wait_selector}. Capturing raw DOM snapshot.")

            # 5. Silently save updated session state cookies for next iteration
            await context.storage_state(path=state_path)
            
            html_content = await page.content()
            await browser.close()
            
            return html_content