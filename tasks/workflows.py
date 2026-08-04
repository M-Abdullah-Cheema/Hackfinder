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

# Prefer the standard Windows Playwright browser install path
if sys.platform == "win32":
    os.environ.setdefault(
        "PLAYWRIGHT_BROWSERS_PATH",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "ms-playwright"),
    )

# ==========================================
# WINDOWS: Point pytesseract at the .exe
# ==========================================
if sys.platform == "win32":
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def _run_async(coro):
    """
    Run an async coroutine safely inside Celery on Windows.

    Always create a fresh loop per task, then dispose the SQLAlchemy async
    engine so the next task does not reuse connections bound to a closed loop.
    """
    from core.database import engine

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        try:
            loop.run_until_complete(engine.dispose())
        except Exception:
            pass
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:
            pass
        loop.close()


async def _sync_postgis_location(session, final) -> None:
    """Keep geography(location) aligned with lat/lng when PostGIS is available."""
    if final.latitude is None or final.longitude is None or final.id is None:
        return
    from sqlalchemy import text

    try:
        await session.execute(
            text(
                """
                UPDATE final_opportunities
                SET location = ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
                WHERE id = :id
                """
            ),
            {"lng": final.longitude, "lat": final.latitude, "id": final.id},
        )
    except Exception as exc:
        logger.debug("PostGIS location sync skipped: %s", exc)
        asyncio.set_event_loop(asyncio.new_event_loop())


def _normalize_ig_url(url: str) -> str:
    """Strip tracking params and normalize Instagram profile URLs."""
    cleaned = url.strip()
    cleaned = re.sub(r"[?#].*$", "", cleaned)
    if not cleaned.endswith("/"):
        cleaned += "/"
    return cleaned


def _extract_posts_from_api_payload(data: dict) -> list[dict]:
    """Parse common Instagram GraphQL / web_profile_info payload shapes."""
    posts: list[dict] = []

    def _from_edges(edges: list) -> None:
        for edge in edges[:8]:
            node = edge.get("node", edge) if isinstance(edge, dict) else {}
            shortcode = node.get("shortcode") or node.get("code")
            if not shortcode:
                continue

            caption = ""
            caption_edges = (
                node.get("edge_media_to_caption", {}).get("edges", [])
                if isinstance(node.get("edge_media_to_caption"), dict)
                else []
            )
            if caption_edges:
                caption = caption_edges[0].get("node", {}).get("text", "") or ""
            elif isinstance(node.get("caption"), dict):
                caption = node["caption"].get("text", "") or ""
            elif isinstance(node.get("caption"), str):
                caption = node["caption"]

            image_urls: list[str] = []
            if "edge_sidecar_to_children" in node:
                for child in node["edge_sidecar_to_children"].get("edges", [])[:4]:
                    img = child.get("node", {}).get("display_url")
                    if img:
                        image_urls.append(img)
            else:
                img = (
                    node.get("display_url")
                    or node.get("display_uri")
                    or (node.get("image_versions2", {}) or {})
                    .get("candidates", [{}])[0]
                    .get("url")
                )
                if img:
                    image_urls.append(img)

            posts.append(
                {
                    "platform_post_id": f"ig_{shortcode}",
                    "caption": caption,
                    "image_urls": image_urls,
                }
            )

    # Shape A: web_profile_info / classic graphql user timeline
    user_node = (
        data.get("data", {}).get("user")
        or data.get("graphql", {}).get("user")
        or data.get("data", {}).get("user", {})
    )
    if isinstance(user_node, dict):
        edges = (
            user_node.get("edge_owner_to_timeline_media", {}).get("edges", [])
            or user_node.get("edge_felix_video_timeline", {}).get("edges", [])
        )
        if edges:
            _from_edges(edges)

    # Shape B: newer xdt_* GraphQL connections
    data_root = data.get("data", {})
    if isinstance(data_root, dict):
        for key, value in data_root.items():
            if not isinstance(value, dict):
                continue
            edges = value.get("edges") or value.get("media", {}).get("edges")
            if edges:
                _from_edges(edges)

    return posts


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

        target_url_norm = _normalize_ig_url(target_url)
        username_match = re.search(r"instagram\.com/([^/?#]+)", target_url_norm)
        if not username_match:
            raise ValueError(f"Cannot parse Instagram username from: {target_url}")
        username = username_match.group(1)

        # ── 1. Playwright scrape FIRST (don't block on flaky DB) ───────────
        from core.pipeline_config import AUTH_STATE_PATH

        state_path = AUTH_STATE_PATH
        os.makedirs(os.path.dirname(state_path), exist_ok=True)

        posts: list[dict] = []
        seen_ids: set[str] = set()

        def _add_posts(batch: list[dict]) -> None:
            for post in batch:
                pid = post.get("platform_post_id")
                if not pid or pid in seen_ids:
                    continue
                seen_ids.add(pid)
                posts.append(post)

        async with async_playwright() as p:
            from core.proxy_rotation import pick_user_agent, playwright_proxy

            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )

            try:
                ctx_kwargs = {
                    "user_agent": pick_user_agent(),
                    "viewport": {"width": 1280, "height": 900},
                    "locale": "en-US",
                }
                proxy_cfg = playwright_proxy()
                if proxy_cfg and os.getenv("USE_PLAYWRIGHT_PROXY", "0") == "1":
                    ctx_kwargs["proxy"] = proxy_cfg
                    logger.info("[proxy] Playwright context using upstream proxy")

                if os.path.exists(state_path) and os.path.getsize(state_path) > 10:
                    context = await browser.new_context(
                        storage_state=state_path, **ctx_kwargs
                    )
                    logger.info("[auth] Loaded saved Instagram session for %s", username)
                else:
                    context = await browser.new_context(**ctx_kwargs)
                    logger.warning(
                        "[auth] No saved Instagram session. "
                        "Run: python scrapers/auth_states/login.py"
                    )

                await context.set_extra_http_headers(
                    {
                        "Accept-Language": "en-US,en;q=0.9",
                        "Accept": (
                            "text/html,application/xhtml+xml,application/xml;"
                            "q=0.9,*/*;q=0.8"
                        ),
                    }
                )

                page = await context.new_page()
                await page.add_init_script(
                    """
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    window.chrome = { runtime: {} };
                    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                    """
                )

                captured_api_data: list[dict] = []

                async def handle_response(response):
                    try:
                        url = response.url
                        interesting = any(
                            token in url
                            for token in (
                                "web_profile_info",
                                "graphql/query",
                                "api/v1/users/web_profile_info",
                                "api/v1/feed/user",
                                "polaris",
                            )
                        )
                        if interesting and response.status == 200:
                            ctype = (response.headers.get("content-type") or "").lower()
                            if "json" in ctype or "javascript" in ctype:
                                data = await response.json()
                                if isinstance(data, dict):
                                    captured_api_data.append(data)
                    except Exception:
                        pass

                page.on("response", handle_response)

                logger.info("[nav] Opening %s", target_url_norm)
                try:
                    await page.goto(
                        target_url_norm, wait_until="domcontentloaded", timeout=60_000
                    )
                except Exception as exc:
                    logger.warning("[nav] goto timed out (%s); continuing", exc)

                # Let client JS / XHR settle, then scroll to trigger lazy media
                await asyncio.sleep(3)
                for _ in range(4):
                    await page.mouse.wheel(0, 1800)
                    await asyncio.sleep(1.2)

                # Detect login / challenge / suspended walls
                current_url = page.url or ""
                body_snip = ""
                try:
                    body_snip = (
                        await page.evaluate(
                            "() => (document.body && document.body.innerText || '').slice(0, 1200)"
                        )
                        or ""
                    )
                except Exception:
                    pass
                body_l = body_snip.lower()
                login_wall = (
                    "accounts/login" in current_url
                    or "challenge" in current_url
                    or "accounts/suspended" in current_url
                    or await page.locator('input[name="username"]').count() > 0
                    or "confirm you're human" in body_l
                    or "confirm you’re human" in body_l
                    or "suspended" in current_url
                )
                if login_wall:
                    logger.error(
                        "[auth] Instagram blocked scrape for %s (url=%s). "
                        "Body hint: %r. Complete human verification, then re-save session: "
                        "python scrapers/auth_states/login.py",
                        username,
                        current_url,
                        body_snip[:180],
                    )
                    try:
                        await context.storage_state(path=state_path)
                    except Exception:
                        pass
                    await browser.close()
                    return None

                try:
                    await context.storage_state(path=state_path)
                except Exception:
                    pass

                # ── 2a. Parse intercepted API responses ────────────────────
                for data in captured_api_data:
                    try:
                        _add_posts(_extract_posts_from_api_payload(data))
                    except Exception as exc:
                        logger.warning("[parse] API payload failed: %s", exc)

                # ── 2b. DOM grid links (most reliable on modern IG) ────────
                if len(posts) < 3:
                    logger.info("[dom] Extracting posts from profile grid links...")
                    try:
                        grid_posts = await page.evaluate(
                            """
                            () => {
                              const out = [];
                              const seen = new Set();
                              const anchors = document.querySelectorAll(
                                'a[href*="/p/"], a[href*="/reel/"]'
                              );
                              for (const a of anchors) {
                                const href = a.getAttribute('href') || '';
                                const m = href.match(/\\/(p|reel)\\/([^\\/?#]+)/);
                                if (!m || seen.has(m[2])) continue;
                                seen.add(m[2]);
                                const img = a.querySelector('img');
                                out.push({
                                  shortcode: m[2],
                                  image_url: img ? (img.src || img.getAttribute('src') || '') : '',
                                  alt: img ? (img.alt || '') : '',
                                });
                              }
                              return out.slice(0, 8);
                            }
                            """
                        )
                        batch = []
                        for item in grid_posts or []:
                            img = (item.get("image_url") or "").strip()
                            alt = (item.get("alt") or "").strip()
                            batch.append(
                                {
                                    "platform_post_id": f"ig_{item['shortcode']}",
                                    "caption": alt,
                                    "image_urls": [img] if img else [],
                                }
                            )
                        _add_posts(batch)
                        logger.info("[dom] Grid extracted %d candidate post(s)", len(batch))
                    except Exception as exc:
                        logger.warning("[dom] Grid extraction failed: %s", exc)

                # ── 2c. Script-tag JSON fallback ───────────────────────────
                if not posts:
                    logger.info("[dom] Falling back to embedded script JSON...")
                    try:
                        scripts_text = await page.evaluate(
                            """
                            () => {
                              const chunks = [];
                              for (const s of document.querySelectorAll('script')) {
                                const t = s.textContent || '';
                                if (
                                  t.includes('shortcode') ||
                                  t.includes('display_url') ||
                                  t.includes('xdt_api')
                                ) {
                                  chunks.push(t.slice(0, 200000));
                                }
                              }
                              return chunks.join('\\n');
                            }
                            """
                        )
                        shortcodes = re.findall(
                            r'"shortcode"\s*:\s*"([^"]{5,})"', scripts_text or ""
                        )
                        display_urls = re.findall(
                            r'"display_url"\s*:\s*"(https[^"]+)"', scripts_text or ""
                        )
                        captions = re.findall(
                            r'"text"\s*:\s*"([^"]{10,})"', scripts_text or ""
                        )
                        batch = []
                        for i, sc in enumerate(shortcodes[:8]):
                            raw_url = display_urls[i] if i < len(display_urls) else None
                            img_url = (
                                raw_url.replace("\\u0026", "&") if raw_url else None
                            )
                            cap = (
                                captions[i].replace("\\n", "\n")
                                if i < len(captions)
                                else ""
                            )
                            batch.append(
                                {
                                    "platform_post_id": f"ig_{sc}",
                                    "caption": cap,
                                    "image_urls": [img_url] if img_url else [],
                                }
                            )
                        _add_posts(batch)
                    except Exception as exc:
                        logger.warning("[dom] Script JSON fallback failed: %s", exc)

                # ── 2d. Enrich first few posts by opening permalink pages ─
                if posts:
                    enrich_limit = min(3, len(posts))
                    for i in range(enrich_limit):
                        sc = posts[i]["platform_post_id"].replace("ig_", "", 1)
                        post_url = f"https://www.instagram.com/p/{sc}/"
                        try:
                            await page.goto(
                                post_url, wait_until="domcontentloaded", timeout=30_000
                            )
                            await asyncio.sleep(1.5)
                            details = await page.evaluate(
                                """
                                () => {
                                  const img = document.querySelector('article img');
                                  const caps = Array.from(
                                    document.querySelectorAll('article h1, article span')
                                  )
                                    .map(el => (el.textContent || '').trim())
                                    .filter(t => t.length > 20);
                                  return {
                                    image_url: img ? img.src : '',
                                    caption: caps[0] || '',
                                  };
                                }
                                """
                            )
                            if details:
                                if details.get("image_url") and not posts[i]["image_urls"]:
                                    posts[i]["image_urls"] = [details["image_url"]]
                                if details.get("caption") and (
                                    not posts[i].get("caption")
                                    or len(details["caption"])
                                    > len(posts[i].get("caption") or "")
                                ):
                                    posts[i]["caption"] = details["caption"]
                        except Exception as exc:
                            logger.warning("[enrich] Failed for %s: %s", sc, exc)

            finally:
                await browser.close()

        if not posts:
            logger.warning(
                "[fail] Zero posts extracted from %s. "
                "Re-authenticate with: python scrapers/auth_states/login.py",
                target_url_norm,
            )
            return None

        # ── 2. Ensure Source row + persist ScrapedOpportunity ──────────────
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Source).where(
                    (Source.target_url == target_url)
                    | (Source.target_url == target_url_norm)
                    | (Source.name == f"instagram_{username}")
                )
            )
            source = result.scalars().first()
            if not source:
                source = Source(
                    name=f"instagram_{username}",
                    target_url=target_url_norm,
                    is_active=True,
                    tier=1,
                    config_jsonb={"platform": "instagram", "username": username},
                )
                session.add(source)
                await session.commit()
                await session.refresh(source)
            source_id = source.id

            first_saved_id = None

            for post in posts:
                existing = await session.execute(
                    select(ScrapedOpportunity).where(
                        ScrapedOpportunity.platform_post_id
                        == post["platform_post_id"]
                    )
                )
                if existing.scalars().first():
                    logger.info(
                        "[skip] Already staged: %s", post["platform_post_id"]
                    )
                    if first_saved_id is None:
                        # Still return an existing UUID so OCR/AI can run
                        row = await session.execute(
                            select(ScrapedOpportunity).where(
                                ScrapedOpportunity.platform_post_id
                                == post["platform_post_id"]
                            )
                        )
                        existing_row = row.scalars().first()
                        if existing_row:
                            first_saved_id = str(existing_row.id)
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
                    logger.error(
                        "[db] flush failed for %s: %s",
                        post["platform_post_id"],
                        exc,
                    )
                    await session.rollback()
                    continue

            await session.commit()

        logger.info(
            "[ok] scrape_task complete. Staged %d post(s) from %s. Returning UUID: %s",
            len(posts),
            target_url_norm,
            first_saved_id,
        )
        return first_saved_id

    return _run_async(_execute())


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

        try:
            import pytesseract
            from scrapers.processors.image_fetcher import ImageProcessor
        except Exception as exc:
            logger.warning(
                "[ocr] OCR deps unavailable (%s). Continuing with caption text only.",
                exc,
            )
            return opportunity_id

        async with AsyncSessionLocal() as session:
            record = await session.get(ScrapedOpportunity, opportunity_id)
            if not record:
                raise ValueError(f"ScrapedOpportunity {opportunity_id} not found.")

            image_urls = record.image_urls or []
            if not image_urls:
                logger.info("[ocr] No images for %s — skipping OCR.", opportunity_id)
                record.ocr_processed = True
                await session.commit()
                return opportunity_id

            ocr_blocks = []
            for url in image_urls:
                try:
                    logger.info("[ocr] Downloading image: %s…", url[:60])
                    processed = await ImageProcessor.fetch_and_preprocess(url)
                    if processed is None:
                        continue
                    raw_text = pytesseract.image_to_string(processed, config="--psm 3")
                    clean = " ".join(raw_text.split()).strip()
                    if clean:
                        ocr_blocks.append(clean)
                        logger.info("[ocr] Extracted %d chars.", len(clean))
                except Exception as exc:
                    logger.warning("[ocr] Image failed (%s): %s", url[:40], exc)

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
            logger.info("[ocr] Complete for %s.", opportunity_id)
            return opportunity_id

    return _run_async(_execute())


# ==========================================
# TASK 3a: Cheap pre-filter (before AI)
# ==========================================
@shared_task(bind=True, max_retries=2, retry_backoff=True)
def prefilter_task(self, opportunity_id: str):
    """
    Drop low-signal posts before spending Gemini quota.
    Returns opportunity_id to continue the chain, or None to stop.
    """
    async def _execute():
        if opportunity_id is None:
            logger.warning("prefilter_task received None — skipping.")
            return None

        from core.prefilter import is_likely_opportunity, score_opportunity_text

        async with AsyncSessionLocal() as session:
            record = await session.get(ScrapedOpportunity, opportunity_id)
            if not record:
                raise ValueError(f"ScrapedOpportunity {opportunity_id} not found.")
            raw_text = (record.extracted_text or "").strip()

        score = score_opportunity_text(raw_text)
        if not is_likely_opportunity(raw_text):
            logger.info(
                "[prefilter] Dropped %s (score=%s) — not opportunity-like.",
                opportunity_id,
                score,
            )
            return None

        logger.info("[prefilter] Kept %s (score=%s).", opportunity_id, score)
        return opportunity_id

    return _run_async(_execute())


# ==========================================
# TASK 3b: AI Structuring
# ==========================================
@shared_task(bind=True, max_retries=5, retry_backoff=True)
def ai_task(self, opportunity_id: str):
    """
    Reads the combined caption + OCR text from a ScrapedOpportunity record
    and extracts a structured ExtractedOpportunity (global schema).

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

        def _iso(dt):
            return dt.isoformat() if dt is not None else None

        # Infer format from is_remote when model omits format
        fmt = getattr(extracted, "format", None)
        if not fmt:
            fmt = "Virtual" if extracted.is_remote else "In-Person"

        result = {
            "opportunity_id": opportunity_id,
            "title": extracted.title,
            "organization_name": extracted.organization_name,
            "category": extracted.category,
            "registration_url": str(extracted.registration_url) if extracted.registration_url else None,
            "is_remote": extracted.is_remote,
            "city": getattr(extracted, "city", None),
            "country": getattr(extracted, "country", None),
            "latitude": getattr(extracted, "latitude", None),
            "longitude": getattr(extracted, "longitude", None),
            "start_datetime_utc": _iso(getattr(extracted, "start_datetime_utc", None)),
            "end_datetime_utc": _iso(getattr(extracted, "end_datetime_utc", None)),
            "local_timezone": getattr(extracted, "local_timezone", None),
            "domain": getattr(extracted, "domain", None) or "Tech",
            "subcategory": getattr(extracted, "subcategory", None),
            "format": fmt,
        }
        logger.info(
            f"🧠 AI extracted: [{extracted.category}] {extracted.title} "
            f"by {extracted.organization_name}"
        )
        return result

    return _run_async(_execute())


# ==========================================
# TASK 4: Deduplication & Final Insert
# ==========================================
@shared_task(bind=True, max_retries=3, retry_backoff=True)
def dedup_task(self, ai_result):
    """
    Receives the structured dict from ai_task, runs hybrid deduplication
    (exact + spatial/temporal + pgvector), and inserts FinalOpportunity if unique.
    """
    async def _execute():
        if ai_result is None:
            logger.warning("dedup_task received None — pipeline ended early.")
            return "SKIPPED"

        from datetime import datetime, timezone

        from core.dedup_engine import DeduplicationEngine
        from core.embedding_client import EmbeddingEngine

        opportunity_id = ai_result.get("opportunity_id")
        title = ai_result.get("title", "Untitled")
        org = ai_result.get("organization_name", "Unknown")
        category = ai_result.get("category", "Other")
        reg_url = ai_result.get("registration_url")

        def _parse_optional_dt(value):
            if not value:
                return None
            if isinstance(value, datetime):
                return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
            try:
                dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except ValueError:
                return None

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
            "city": ai_result.get("city"),
            "country": ai_result.get("country"),
            "latitude": ai_result.get("latitude"),
            "longitude": ai_result.get("longitude"),
            "start_datetime_utc": _parse_optional_dt(ai_result.get("start_datetime_utc")),
            "end_datetime_utc": _parse_optional_dt(ai_result.get("end_datetime_utc")),
            "local_timezone": ai_result.get("local_timezone"),
            "domain": ai_result.get("domain") or "Tech",
            "subcategory": ai_result.get("subcategory"),
            "format": ai_result.get("format"),
        }

        embedding_engine = EmbeddingEngine()
        vector = await embedding_engine.generate_vector(title, org, category)

        if vector is None:
            logger.warning(
                "Embedding unavailable for '%s' — inserting without vector "
                "(exact-match dedup only).",
                title,
            )

        dedup_engine = DeduplicationEngine()
        is_duplicate = await dedup_engine.evaluate_incoming_record(record_data, vector)

        if is_duplicate:
            logger.info(f"🔁 Duplicate detected for '{title}'. Merged and skipped.")
            return "DUPLICATE"

        async with AsyncSessionLocal() as session:
            final = FinalOpportunity(
                title=title,
                organization_name=org,
                category=category,
                registration_url=reg_url,
                platform_post_id=platform_post_id,
                latitude=record_data["latitude"],
                longitude=record_data["longitude"],
                city=record_data["city"],
                country=record_data["country"],
                start_datetime_utc=record_data["start_datetime_utc"],
                end_datetime_utc=record_data["end_datetime_utc"],
                local_timezone=record_data["local_timezone"],
                domain=record_data["domain"],
                subcategory=record_data["subcategory"],
                format=record_data["format"],
                embedding=vector,
            )
            session.add(final)
            await session.flush()
            await _sync_postgis_location(session, final)
            await session.commit()

        logger.info(
            f"🎉 New opportunity saved to final table: [{category}] '{title}' "
            f"by {org} (post: {platform_post_id})"
        )
        return "SUCCESS"

    return _run_async(_execute())


# ==========================================
# TASK 0: Scheduler — dispatch all Instagram pipelines
# ==========================================
def _dispatch_pipeline(target_url: str):
    """Build and enqueue the scrape → OCR → prefilter → AI → dedup chain."""
    from celery import chain

    return chain(
        scrape_task.s(target_url),
        ocr_task.s(),
        prefilter_task.s(),
        ai_task.s(),
        dedup_task.s(),
    ).delay()


@shared_task(name="tasks.workflows.trigger_all_sources")
def trigger_all_sources():
    """
    Dispatches Instagram scrape chains and optional calendar/API feed ingest.

    Called manually via scripts/trigger_pipeline.py or automatically by Celery Beat.
    """
    from core.pipeline_config import (
        AUTH_STATE_PATH,
        INSTAGRAM_TARGETS,
        configured_feed_count,
        instagram_auth_ready,
    )

    chains = []
    status = "ok"

    if not instagram_auth_ready():
        logger.error(
            "Instagram auth missing at %s. Run: python scrapers/auth_states/login.py",
            AUTH_STATE_PATH,
        )
        status = "auth_missing"
    else:
        for url in INSTAGRAM_TARGETS:
            result = _dispatch_pipeline(url)
            chains.append({"url": url, "chain_id": result.id})
            logger.info("Pipeline dispatched for %s (chain_id=%s)", url, result.id)

    feed_job = None
    if configured_feed_count() > 0:
        feed_job = feed_ingest_task.delay()
        logger.info("Feed ingest dispatched (task_id=%s)", feed_job.id)
    else:
        logger.info("No calendar/API feeds configured — skipping feed_ingest_task")

    logger.info("trigger_all_sources complete — %d Instagram pipeline(s) queued", len(chains))
    return {
        "status": status,
        "dispatched": len(chains),
        "chains": chains,
        "feed_task_id": getattr(feed_job, "id", None),
    }


@shared_task(name="tasks.workflows.feed_ingest_task", bind=True, max_retries=2)
def feed_ingest_task(self):
    """
    Pull Eventbrite / Meetup / Luma / RSS / iCal feeds and promote structured
    events into final_opportunities (skipping Gemini when fields are already complete).
    """
    async def _execute():
        from core.dedup_engine import DeduplicationEngine
        from core.embedding_client import EmbeddingEngine
        from core.pipeline_config import (
            EVENTBRITE_ORG_IDS,
            ICAL_FEED_URLS,
            LUMA_CALENDAR_IDS,
            MEETUP_GROUP_URLNAMES,
            RSS_FEED_URLS,
        )
        from scrapers.api_integrations import (
            EventbriteFeed,
            ICalFeed,
            LumaFeed,
            MeetupFeed,
            RssEventFeed,
        )

        feeds = []
        for org_id in EVENTBRITE_ORG_IDS:
            feeds.append(EventbriteFeed(org_id))
        for group in MEETUP_GROUP_URLNAMES:
            feeds.append(MeetupFeed(group))
        for cal_id in LUMA_CALENDAR_IDS:
            feeds.append(LumaFeed(cal_id))
        for url in RSS_FEED_URLS:
            feeds.append(RssEventFeed(url))
        for url in ICAL_FEED_URLS:
            feeds.append(ICalFeed(url))

        if not feeds:
            return {"status": "noop", "inserted": 0, "duplicates": 0, "staged": 0}

        # Ensure a registry Source exists for FK on scraped_opportunities
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Source).where(Source.name == "Api Feeds")
            )
            source = result.scalars().first()
            if not source:
                source = Source(
                    name="Api Feeds",
                    target_url="https://feeds.local/hackfinder",
                    config_jsonb={"platform_type": "rss"},
                    is_active=True,
                    tier=1,
                )
                session.add(source)
                await session.commit()
                await session.refresh(source)
            source_id = source.id

        embedding_engine = EmbeddingEngine()
        dedup_engine = DeduplicationEngine()
        inserted = duplicates = staged = 0

        for feed in feeds:
            try:
                events = await feed.fetch()
            except Exception as exc:
                logger.error("Feed %s failed: %s", getattr(feed, "source_name", feed), exc)
                continue

            for event in events:
                text_blob = "\n".join(
                    part
                    for part in [event.title, event.organization_name, event.description or ""]
                    if part
                )
                async with AsyncSessionLocal() as session:
                    existing = await session.execute(
                        select(ScrapedOpportunity).where(
                            ScrapedOpportunity.platform_post_id == event.platform_post_id
                        )
                    )
                    row = existing.scalars().first()
                    if not row:
                        row = ScrapedOpportunity(
                            source_id=source_id,
                            platform_post_id=event.platform_post_id,
                            extracted_text=text_blob,
                            image_urls=[],
                            ocr_processed=True,
                            city=event.city,
                            country=event.country,
                            latitude=event.latitude,
                            longitude=event.longitude,
                            start_datetime_utc=event.start_datetime_utc,
                            end_datetime_utc=event.end_datetime_utc,
                            local_timezone=event.local_timezone,
                            domain=event.domain,
                            format=event.format,
                            registration_url=event.registration_url,
                        )
                        session.add(row)
                        await session.commit()
                        staged += 1

                category = "Workshop"
                title_l = (event.title or "").lower()
                if "hack" in title_l:
                    category = "Hackathon"
                elif "intern" in title_l:
                    category = "Internship"
                elif "job" in title_l or "hiring" in title_l:
                    category = "Job"

                record_data = {
                    "title": event.title,
                    "organization_name": event.organization_name or event.source_name,
                    "category": category,
                    "registration_url": event.registration_url,
                    "platform_post_id": event.platform_post_id,
                    "city": event.city,
                    "country": event.country,
                    "latitude": event.latitude,
                    "longitude": event.longitude,
                    "start_datetime_utc": event.start_datetime_utc,
                    "end_datetime_utc": event.end_datetime_utc,
                    "local_timezone": event.local_timezone,
                    "domain": event.domain or "Tech",
                    "subcategory": None,
                    "format": event.format,
                }
                vector = await embedding_engine.generate_vector(
                    record_data["title"],
                    record_data["organization_name"],
                    category,
                )
                if vector is None:
                    continue

                is_dup = await dedup_engine.evaluate_incoming_record(record_data, vector)
                if is_dup:
                    duplicates += 1
                    continue

                async with AsyncSessionLocal() as session:
                    final = FinalOpportunity(
                        title=record_data["title"],
                        organization_name=record_data["organization_name"],
                        category=category,
                        registration_url=record_data["registration_url"],
                        platform_post_id=record_data["platform_post_id"],
                        latitude=record_data["latitude"],
                        longitude=record_data["longitude"],
                        city=record_data["city"],
                        country=record_data["country"],
                        start_datetime_utc=record_data["start_datetime_utc"],
                        end_datetime_utc=record_data["end_datetime_utc"],
                        local_timezone=record_data["local_timezone"],
                        domain=record_data["domain"],
                        subcategory=record_data["subcategory"],
                        format=record_data["format"],
                        embedding=vector,
                    )
                    session.add(final)
                    await session.flush()
                    await _sync_postgis_location(session, final)
                    await session.commit()
                    inserted += 1

        summary = {
            "status": "ok",
            "inserted": inserted,
            "duplicates": duplicates,
            "staged": staged,
            "feeds": len(feeds),
        }
        logger.info("feed_ingest_task complete: %s", summary)
        return summary

    return _run_async(_execute())

