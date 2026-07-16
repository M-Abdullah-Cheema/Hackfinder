import asyncio
import logging
import os
import re
import sys

from celery import shared_task
from sqlalchemy import select

from core.database import AsyncSessionLocal
from core.models import ScrapedOpportunity, Source, FinalOpportunity

logger = logging.getLogger(__name__)

# ==========================================
# WINDOWS: Point pytesseract at the .exe
# ==========================================
if sys.platform == "win32":
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


# ==========================================
# TASK 1: Scrape & Stage
# ==========================================
@shared_task(bind=True, max_retries=3, retry_backoff=True)
def scrape_task(self, target_url: str):
    """
    Uses Playwright to scrape an Instagram profile. Intercepts the internal
    Instagram API response to reliably extract post shortcodes, captions,
    and image URLs. Saves the latest post to ScrapedOpportunity and returns
    the UUID of the staged record.
    """
    async def _execute():
        from playwright.async_api import async_playwright

        username_match = re.search(r"instagram\.com/([^/?#]+)", target_url)
        if not username_match:
            raise ValueError(f"Cannot parse Instagram username from: {target_url}")
        username = username_match.group(1)

        # ── 1. Ensure a Source row exists ──────────────────────────────────
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Source).where(Source.target_url == target_url)
            )
            source = result.scalars().first()
            if not source:
                source = Source(
                    name=f"instagram_{username}",
                    target_url=target_url,
                    is_active=True,
                    tier=1,
                    config_jsonb={"platform": "instagram", "username": username},
                )
                session.add(source)
                await session.commit()
                await session.refresh(source)
            source_id = source.id

        # ── 2. Playwright scrape ───────────────────────────────────────────
        state_path = os.path.join("scrapers", "auth_states", "state.json")
        os.makedirs(os.path.dirname(state_path), exist_ok=True)

        posts = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )

            ctx_kwargs = {
                "user_agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "viewport": {"width": 1280, "height": 800},
                "locale": "en-US",
            }

            if os.path.exists(state_path) and os.path.getsize(state_path) > 10:
                context = await browser.new_context(storage_state=state_path, **ctx_kwargs)
                logger.info(f"🔐 Loaded saved auth state for {username}")
            else:
                context = await browser.new_context(**ctx_kwargs)
                logger.warning(
                    "⚠️  No saved Instagram session found. "
                    "Results may be limited. Run scrapers/auth_states/login.py to authenticate."
                )

            await context.set_extra_http_headers({
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            })

            page = await context.new_page()

            # Mask automation fingerprints
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            """)

            # Intercept Instagram's internal profile API
            captured_api_data = []

            async def handle_response(response):
                try:
                    url = response.url
                    if (
                        ("web_profile_info" in url or "graphql/query" in url)
                        and response.status == 200
                    ):
                        data = await response.json()
                        captured_api_data.append(data)
                        logger.debug(f"📡 Captured API response from: {url[:80]}")
                except Exception:
                    pass

            page.on("response", handle_response)

            logger.info(f"🌐 Navigating to {target_url}")
            try:
                await page.goto(target_url, wait_until="networkidle", timeout=45_000)
            except Exception as e:
                logger.warning(f"Page load timed out ({e}). Proceeding with captured data.")

            await asyncio.sleep(2)

            # Save updated auth state
            try:
                await context.storage_state(path=state_path)
            except Exception:
                pass

            # ── 2a. Parse intercepted API responses ────────────────────────
            for data in captured_api_data:
                try:
                    # Path 1: web_profile_info endpoint
                    user_node = (
                        data.get("data", {}).get("user")
                        or data.get("graphql", {}).get("user")
                    )
                    if user_node:
                        edges = (
                            user_node
                            .get("edge_owner_to_timeline_media", {})
                            .get("edges", [])
                        )
                        for edge in edges[:5]:
                            node = edge.get("node", {})
                            shortcode = node.get("shortcode")
                            if not shortcode:
                                continue

                            caption_edges = (
                                node.get("edge_media_to_caption", {}).get("edges", [])
                            )
                            caption = (
                                caption_edges[0]["node"]["text"]
                                if caption_edges
                                else ""
                            )

                            image_urls = []
                            if "edge_sidecar_to_children" in node:
                                for child in node["edge_sidecar_to_children"].get("edges", [])[:4]:
                                    img = child["node"].get("display_url")
                                    if img:
                                        image_urls.append(img)
                            else:
                                img = node.get("display_url")
                                if img:
                                    image_urls.append(img)

                            posts.append({
                                "platform_post_id": f"ig_{shortcode}",
                                "caption": caption,
                                "image_urls": image_urls,
                            })
                except Exception as exc:
                    logger.warning(f"Failed to parse API response: {exc}")

            # ── 2b. DOM fallback (embedded JSON in <script> tags) ──────────
            if not posts:
                logger.info("🔄 Falling back to DOM script extraction...")
                try:
                    scripts_text = await page.evaluate("""
                        () => {
                            for (const s of document.querySelectorAll('script')) {
                                const t = s.textContent || '';
                                if (t.includes('shortcode') && t.includes('display_url')) {
                                    return t.slice(0, 100000);
                                }
                            }
                            return '';
                        }
                    """)

                    shortcodes = re.findall(r'"shortcode"\s*:\s*"([^"]{5,})"', scripts_text)
                    display_urls = re.findall(r'"display_url"\s*:\s*"(https[^"]+)"', scripts_text)
                    captions = re.findall(r'"text"\s*:\s*"([^"]{10,})"', scripts_text)

                    for i, sc in enumerate(shortcodes[:5]):
                        raw_url = display_urls[i] if i < len(display_urls) else None
                        img_url = raw_url.replace("\\u0026", "&") if raw_url else None
                        cap = captions[i].replace("\\n", "\n") if i < len(captions) else ""
                        posts.append({
                            "platform_post_id": f"ig_{sc}",
                            "caption": cap,
                            "image_urls": [img_url] if img_url else [],
                        })
                except Exception as exc:
                    logger.warning(f"DOM fallback failed: {exc}")

            await browser.close()

        if not posts:
            logger.warning(
                f"❌ Zero posts extracted from {target_url}. "
                "Instagram may be blocking this session. "
                "Authenticate by visiting instagram.com in a browser, exporting cookies, "
                "and saving them to scrapers/auth_states/state.json."
            )
            return None

        # ── 3. Persist to ScrapedOpportunity ──────────────────────────────
        async with AsyncSessionLocal() as session:
            first_saved_id = None

            for post in posts:
                existing = await session.execute(
                    select(ScrapedOpportunity).where(
                        ScrapedOpportunity.platform_post_id == post["platform_post_id"]
                    )
                )
                if existing.scalars().first():
                    logger.info(f"⏩ Skipping already-staged post: {post['platform_post_id']}")
                    continue

                record = ScrapedOpportunity(
                    source_id=source_id,
                    platform_post_id=post["platform_post_id"],
                    extracted_text=post.get("caption", ""),
                    image_urls=post.get("image_urls", []),
                )
                session.add(record)
                try:
                    await session.flush()
                    if first_saved_id is None:
                        first_saved_id = str(record.id)
                except Exception as exc:
                    logger.error(f"DB flush failed for {post['platform_post_id']}: {exc}")
                    await session.rollback()
                    continue

            await session.commit()

        logger.info(
            f"✅ scrape_task complete. Staged {len(posts)} post(s) from {target_url}. "
            f"Returning UUID: {first_saved_id}"
        )
        return first_saved_id

    return asyncio.run(_execute())


# ==========================================
# TASK 2: OCR Processing
# ==========================================
@shared_task(bind=True, max_retries=5, retry_backoff=True)
def ocr_task(self, opportunity_id: str):
    """
    Downloads each image URL stored in a ScrapedOpportunity record, runs
    Tesseract OCR on it in-memory, and appends the extracted text to the
    record's extracted_text field.
    """
    async def _execute():
        if opportunity_id is None:
            logger.warning("ocr_task received None — skipping.")
            return None

        import pytesseract
        from scrapers.processors.image_fetcher import ImageProcessor

        async with AsyncSessionLocal() as session:
            record = await session.get(ScrapedOpportunity, opportunity_id)
            if not record:
                raise ValueError(f"ScrapedOpportunity {opportunity_id} not found.")

            image_urls = record.image_urls or []
            if not image_urls:
                logger.info(f"📭 No images attached to {opportunity_id}. Skipping OCR.")
                record.ocr_processed = True
                await session.commit()
                return opportunity_id

            ocr_blocks = []
            for url in image_urls:
                logger.info(f"🖼️  Downloading image for OCR: {url[:60]}…")
                processed = await ImageProcessor.fetch_and_preprocess(url)
                if processed is None:
                    continue

                # psm 3 = fully automatic page segmentation, no OSD
                raw_text = pytesseract.image_to_string(processed, config="--psm 3")
                clean = " ".join(raw_text.split()).strip()
                if clean:
                    ocr_blocks.append(clean)
                    logger.info(f"📝 OCR extracted {len(clean)} chars from image.")

            if ocr_blocks:
                combined = "\n".join(ocr_blocks)
                existing = record.extracted_text or ""
                record.extracted_text = (
                    f"{existing}\n\n--- FLYER TEXT (OCR) ---\n{combined}"
                    if existing
                    else f"--- FLYER TEXT (OCR) ---\n{combined}"
                )

            record.ocr_processed = True
            await session.commit()
            logger.info(f"✅ OCR complete for {opportunity_id}.")
            return opportunity_id

    return asyncio.run(_execute())


# ==========================================
# TASK 3: AI Structuring
# ==========================================
@shared_task(bind=True, max_retries=5, retry_backoff=True)
def ai_task(self, opportunity_id: str):
    """
    Reads the combined caption + OCR text from a ScrapedOpportunity record
    and sends it to OpenAI via the Instructor-patched client to extract a
    structured ExtractedOpportunity object (title, category, org, URL, etc.).

    Returns a dict so the next task (dedup_task) has everything it needs
    without a second database round-trip.
    """
    async def _execute():
        if opportunity_id is None:
            logger.warning("ai_task received None — skipping.")
            return None

        from core.llm_router import AIRouter

        async with AsyncSessionLocal() as session:
            record = await session.get(ScrapedOpportunity, opportunity_id)
            if not record:
                raise ValueError(f"ScrapedOpportunity {opportunity_id} not found.")

            raw_text = (record.extracted_text or "").strip()

        if not raw_text:
            logger.warning(f"⚠️ No text to process for {opportunity_id}. Skipping AI step.")
            return None

        router = AIRouter()
        extracted = await router.extract_structured_data(raw_text)

        if extracted is None:
            logger.error(f"❌ AI extraction returned None for {opportunity_id}.")
            return None

        result = {
            "opportunity_id": opportunity_id,
            "title": extracted.title,
            "organization_name": extracted.organization_name,
            "category": extracted.category,
            "registration_url": str(extracted.registration_url) if extracted.registration_url else None,
            "is_remote": extracted.is_remote,
        }
        logger.info(
            f"🧠 AI extracted: [{extracted.category}] {extracted.title} "
            f"by {extracted.organization_name}"
        )
        return result

    return asyncio.run(_execute())


# ==========================================
# TASK 4: Deduplication & Final Insert
# ==========================================
@shared_task(bind=True, max_retries=3, retry_backoff=True)
def dedup_task(self, ai_result):
    """
    Receives the structured dict from ai_task, runs two-tier deduplication
    (exact match + pgvector cosine similarity), and if the record is unique,
    generates an embedding and commits a FinalOpportunity to Supabase.

    ai_result is the dict returned by ai_task:
        {
            "opportunity_id": str,
            "title": str,
            "organization_name": str,
            "category": str,
            "registration_url": str | None,
            "is_remote": bool,
        }
    """
    async def _execute():
        if ai_result is None:
            logger.warning("dedup_task received None — pipeline ended early.")
            return "SKIPPED"

        from core.dedup_engine import DeduplicationEngine
        from core.embedding_client import EmbeddingEngine

        opportunity_id = ai_result.get("opportunity_id")
        title = ai_result.get("title", "Untitled")
        org = ai_result.get("organization_name", "Unknown")
        category = ai_result.get("category", "Other")
        reg_url = ai_result.get("registration_url")

        # Retrieve the platform_post_id from the staging table
        async with AsyncSessionLocal() as session:
            record = await session.get(ScrapedOpportunity, opportunity_id)
            platform_post_id = record.platform_post_id if record else opportunity_id

        record_data = {
            "title": title,
            "organization_name": org,
            "category": category,
            "registration_url": reg_url,
            "platform_post_id": platform_post_id,
        }

        # ── Tier A + Tier B deduplication ─────────────────────────────────
        embedding_engine = EmbeddingEngine()
        vector = await embedding_engine.generate_vector(title, org, category)

        if vector is None:
            logger.error(f"❌ Could not generate embedding for '{title}'. Aborting insert.")
            return "EMBEDDING_FAILED"

        dedup_engine = DeduplicationEngine()
        is_duplicate = await dedup_engine.evaluate_incoming_record(record_data, vector)

        if is_duplicate:
            logger.info(f"🔁 Duplicate detected for '{title}'. Merged and skipped.")
            return "DUPLICATE"

        # ── Unique — commit to FinalOpportunity ───────────────────────────
        async with AsyncSessionLocal() as session:
            final = FinalOpportunity(
                title=title,
                organization_name=org,
                category=category,
                registration_url=reg_url,
                platform_post_id=platform_post_id,
                embedding=vector,
            )
            session.add(final)
            await session.commit()

        logger.info(
            f"🎉 New opportunity saved to final table: [{category}] '{title}' "
            f"by {org} (post: {platform_post_id})"
        )
        return "SUCCESS"

    return asyncio.run(_execute())
