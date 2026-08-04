# HackFinder — Project Handoff Document

> **Purpose:** This document is a complete handoff for another AI or developer to understand what exists, how it works, what was built, and what still needs to be done.
>
> **Repository:** https://github.com/M-Abdullah-Cheema/Hackfinder  
> **Local path:** `c:\Users\muham\Hackathon_Scraper`

---

## 1. Project Summary

**HackFinder** is an AI-powered aggregator for hackathons, workshops, internships, and scholarships targeted at Islamabad's tech community (GDG Cloud, Google Devs ISB, AWS NUST, etc.).

It:
1. **Scrapes** Instagram (and has Scrapy spiders for LinkedIn/static web)
2. **Runs OCR** on flyer images in posts
3. **Extracts structured data** via Gemini AI
4. **Deduplicates** using pgvector semantic similarity
5. **Serves** clean opportunity cards through a Next.js frontend

---

## 2. Tech Stack

### Backend
| Layer | Technology |
|-------|------------|
| Language | Python 3.12+ |
| Web API | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.0 (async) |
| Database | PostgreSQL on **Supabase** |
| Vector search | **pgvector** (HNSW index, 1536-dim embeddings) |
| Task queue | **Celery** + **Redis** |
| Scraping (social) | **Playwright** (headless Chromium) |
| Scraping (web) | **Scrapy** |
| OCR | **Tesseract** via `pytesseract` + Pillow |
| AI extraction | **Google Gemini** (`gemini-2.0-flash`) via `google-genai` |
| Validation | **Pydantic v2** |
| Package manager | **Poetry** (`pyproject.toml`) |

### Frontend
| Layer | Technology |
|-------|------------|
| Framework | **Next.js 16** (App Router, Turbopack) |
| UI | **React 19** + **Tailwind CSS v4** |
| Fonts | Archivo Black, Space Grotesk, DM Mono (via `next/font`) |
| Design | Neo-brutalist + retro keycap + grid-paper aesthetic |

### Infrastructure
| Service | Purpose |
|---------|---------|
| Supabase | Managed PostgreSQL + pgvector extension |
| Redis | Celery broker and result backend |
| Docker | Redis container; Dockerfile exists but is outdated |

---

## 3. High-Level Architecture

```mermaid
flowchart TB
    subgraph Sources
        IG[Instagram Profiles]
        LI[LinkedIn Pages]
        WEB[Static Web Portals]
    end

    subgraph Pipeline["Celery Pipeline (tasks/workflows.py)"]
        S1[scrape_task<br/>Playwright]
        S2[ocr_task<br/>Tesseract]
        S3[ai_task<br/>Gemini]
        S4[dedup_task<br/>pgvector]
        S1 --> S2 --> S3 --> S4
    end

    subgraph Database["Supabase PostgreSQL"]
        SRC[(sources)]
        STG[(scraped_opportunities)]
        FIN[(final_opportunities)]
        USR[(users / user_preferences)]
    end

    subgraph API["FastAPI (api/main.py)"]
        OPP[GET /api/opportunities]
        CAT[GET /api/opportunities/categories]
        ORG[GET /api/opportunities/organizations]
        SRCAPI[CRUD /api/v1/sources]
    end

    subgraph Frontend["Next.js (frontend/)"]
        UI[HackFinder UI<br/>localhost:3000]
    end

    IG --> S1
    LI --> Scrapy[Scrapy Spiders]
    WEB --> Scrapy
    Scrapy --> STG

    S1 --> STG
    S2 --> STG
    S3 --> FIN
    S4 --> FIN

    SRC --> S1
    FIN --> OPP
    OPP --> UI
    CAT --> UI
    ORG --> UI
```

---

## 4. End-to-End Workflow

### A. Real scraping pipeline (Celery chain)

Triggered by `scripts/trigger_pipeline.py`:

```
scrape_task → ocr_task → ai_task → dedup_task
```

| Step | Task | Input | Output | Queue |
|------|------|-------|--------|-------|
| 1 | `scrape_task` | Instagram `target_url` | UUID of `ScrapedOpportunity` | `scrapers` |
| 2 | `ocr_task` | UUID | Same UUID (text appended) | `ocr_tasks` |
| 3 | `ai_task` | UUID | Structured dict (title, org, category, URL) | `ai_extraction` |
| 4 | `dedup_task` | AI dict | `"SUCCESS"` / `"DUPLICATE"` / `"SKIPPED"` | `deliveries` |

**`scrape_task` details:**
- Launches Playwright with anti-detection flags
- Loads Instagram session from `scrapers/auth_states/state.json` if present
- Intercepts Instagram internal API responses (`web_profile_info`, `graphql/query`)
- Falls back to DOM `<script>` tag regex extraction
- Auto-creates a `Source` row on first run
- Saves to `scraped_opportunities` table

**`ocr_task` details:**
- Downloads images via `scrapers/processors/image_fetcher.py`
- Runs Tesseract OCR (`--psm 3`)
- Appends OCR text to `extracted_text` field

**`ai_task` details:**
- Sends caption + OCR text to Gemini via `core/llm_router.py`
- Returns validated `ExtractedOpportunity` Pydantic object as dict

**`dedup_task` details:**
- Generates 1536-dim embedding via `core/embedding_client.py`
- Runs two-tier dedup in `core/dedup_engine.py` (exact match + cosine similarity)
- Inserts unique records into `final_opportunities`

### B. Frontend data flow

```
Browser (localhost:3000)
  → fetchOpportunities() in frontend/src/lib/api.ts
  → GET http://localhost:8002/api/opportunities
  → FastAPI reads final_opportunities table
  → JSON returned to React page
```

### C. Source registry (admin API)

Scraping targets are registered in the `sources` table via:

- `POST /api/v1/sources/` — create target (requires `target_url`)
- `GET /api/v1/sources/active` — list active targets for scraper queue
- `PATCH /api/v1/sources/{id}` — update/pause target

---

## 5. Directory Structure

```
Hackathon_Scraper/
├── api/
│   ├── main.py              # Public API (opportunities + mounts sources router) — port 8002
│   └── routers/
│       └── sources.py       # Target registry CRUD
├── core/
│   ├── config.py            # Pydantic settings (.env loader)
│   ├── database.py          # Async SQLAlchemy engine (Supabase pooler settings)
│   ├── models.py            # All SQLAlchemy models
│   ├── schemas.py           # Pydantic schemas for Source API
│   ├── celery_app.py        # Celery + Redis config, queue routing
│   ├── llm_router.py        # Gemini structured extraction
│   ├── ai_schemas.py        # ExtractedOpportunity schema for AI output
│   ├── dedup_engine.py      # pgvector deduplication logic
│   ├── embedding_client.py  # Vector embedding generation
│   └── job_manager.py       # CrawlingJob lifecycle for Scrapy fleet
├── tasks/
│   └── workflows.py         # Celery tasks: scrape, ocr, ai, dedup
├── scrapers/
│   ├── orchestrator.py      # Scrapy fleet runner (subprocess per source)
│   ├── base_playwright.py   # Playwright wrapper
│   ├── crawler_factory.py
│   ├── auth_states/         # Instagram session cookies (state.json — gitignored)
│   ├── bot/                 # Scrapy project
│   │   ├── spiders/         # instagram, linkedin, devpost, base_spider
│   │   ├── pipelines.py
│   │   └── settings.py
│   └── processors/          # OCR, image fetcher, data pipeline
├── frontend/                # Next.js 16 app
│   └── src/
│       ├── app/page.tsx     # Main UI (neo-brutalist redesign)
│       ├── app/globals.css  # Design system utilities
│       └── lib/api.ts       # API client
├── scripts/
│   ├── seed_opportunities.py    # Insert 12 sample FinalOpportunity rows
│   ├── test_db_connection.py    # Supabase connectivity diagnostic
│   ├── trigger_pipeline.py      # Fire Celery chains for 5 Instagram accounts
│   └── seed_db.py
├── tests/
│   ├── test_sources.py      # Schema + API integration tests (3 tests)
│   ├── test_spider.py
│   └── test_orchestration.py
├── main.py                  # Legacy admin API entry (sources only) — port 8000
├── init_db.py               # DROP + CREATE all tables (destructive!)
├── monitor.py
├── test_celery.py
├── pyproject.toml
├── Dockerfile               # Outdated — still references placeholder spider
├── .env.example             # Template (committed)
└── .env                     # Real secrets (NOT committed, gitignored)
```

---

## 6. Database Schema

| Table | Purpose | Key fields |
|-------|---------|------------|
| `sources` | Scraping targets registry | `name`, `target_url`, `config_jsonb`, `is_active`, `tier` |
| `scraped_opportunities` | Staging table (raw scrape) | `platform_post_id`, `extracted_text`, `image_urls`, `ocr_processed` |
| `final_opportunities` | Production table (UI reads this) | `title`, `organization_name`, `category`, `registration_url`, `embedding` |
| `crawling_jobs` | Scrapy job tracking | `source_id`, `status`, `error_log` |
| `scraped_items` | Legacy generic scrape table | `url`, `title`, `raw_content` |
| `users` | User accounts (Phase 10) | `email`, encrypted `telegram_chat_id`, `discord_webhook_url` |
| `user_preferences` | Notification filters | `target_category`, `target_organization` |

**Important:** `Source.target_url` and `SourceCreate.target_url` are **required**. URL validation supports Instagram, LinkedIn, and static web URLs (see `core/schemas.py`).

**Supabase connection requirements:**
- Use **Transaction pooler** URI on port **6543**
- Prefix: `postgresql+asyncpg://`
- `core/database.py` sets `statement_cache_size=0` (required for pgbouncer)
- Enable **pgvector** extension in Supabase before running `init_db.py`

---

## 7. API Endpoints

### Public API — `api/main.py` (run on port **8002**)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Health check |
| GET | `/api/opportunities` | List opportunities (filter: `category`, `organization_name`, `limit`, `offset`) |
| GET | `/api/opportunities/categories` | Distinct categories |
| GET | `/api/opportunities/organizations` | Distinct organizations |
| POST | `/api/v1/sources/` | Register scraping target |
| GET | `/api/v1/sources/active` | Active sources for scraper queue |
| PATCH | `/api/v1/sources/{id}` | Update source |

Interactive docs: `http://localhost:8002/docs`

### Legacy admin API — `main.py` (port 8000, sources only)

Same sources router, no opportunities endpoints.

---

## 8. Environment Variables

Copy `.env.example` → `.env`:

```env
DATABASE_URL=postgresql+asyncpg://postgres.PROJECT_REF:PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres
REDIS_URL=redis://localhost:6379/0
GEMINI_API_KEY=your_gemini_api_key_here
PROXY_API_KEY=your_proxy_api_key_here
SCRAPY_CONCURRENCY=16
SCRAPE_INTERVAL_SECONDS=21600
ENCRYPTION_KEY=optional_for_user_notifications
```

Frontend (`frontend/.env.local`):

```env
NEXT_PUBLIC_API_URL=http://localhost:8002
```

**Common `.env` mistakes that break DB connection:**
- Duplicate prefix: `DATABASE_URL=DATABASE_URL=postgresql+...` ❌
- Space before `@` in password: `password @host` ❌
- Using port 5432 session pooler instead of 6543 transaction pooler

---

## 9. How to Run Locally

### Prerequisites
- Python 3.12+
- Node.js 18+
- Redis (Docker: `docker run -p 6379:6379 redis`)
- Tesseract OCR installed (Windows: `C:\Program Files\Tesseract-OCR\tesseract.exe`)
- Playwright browsers: `python -m playwright install chromium`
- Supabase project with pgvector enabled

### Setup (first time)

```powershell
cd c:\Users\muham\Hackathon_Scraper

# Backend deps
pip install -r requirements.txt   # OR: poetry install

# Test DB connection
python scripts/test_db_connection.py   # expect [OK] pooler-6543

# Create tables (WARNING: drops existing tables)
python init_db.py

# Seed sample data for UI
python scripts/seed_opportunities.py

# Frontend deps
cd frontend
npm install
```

### Run services (5 terminals for live data)

```powershell
# Terminal 1 — API
python -m uvicorn api.main:app --reload --port 8002

# Terminal 2 — Frontend
cd frontend
npm run dev

# Terminal 3 — Redis
docker run -p 6379:6379 redis

# Terminal 4 — Celery worker (all 4 pipeline queues)
python -m celery -A core.celery_app worker -Q scrapers,ocr_tasks,ai_extraction,deliveries --loglevel=info --concurrency=2

# Terminal 5 — Celery Beat (automatic re-scrape every 6 hours)
python -m celery -A core.celery_app beat --loglevel=info
```

### Enable live Instagram scraping (one-time)

```powershell
# Step 1: Save Instagram session cookies
python scrapers/auth_states/login.py

# Step 2: Pre-flight check (Redis, auth, env vars)
python scripts/check_live_pipeline.py

# Step 3: Trigger first live scrape manually
python scripts/trigger_pipeline.py
```

After Beat is running, pipelines re-trigger automatically every `SCRAPE_INTERVAL_SECONDS` (default 21600 = 6 hours).

> **Note:** `scripts/seed_opportunities.py` inserts **static demo data**. The UI shows live data only after the Celery pipeline writes to `final_opportunities`.

### URLs
- **Website:** http://localhost:3000
- **API docs:** http://localhost:8002/docs

---

## 10. Why Live Data May Not Appear (Root Causes)

| # | Cause | Symptom | Fix |
|---|-------|---------|-----|
| 1 | **Missing `state.json`** | `scrape_task` returns `None`, no new posts | Run `python scrapers/auth_states/login.py` |
| 2 | **No Celery Beat** | Data only updates when you manually trigger | Run `celery beat` (see section 9) |
| 3 | **Seed data only** | UI shows 12 static cards from seed script | Run live pipeline; new rows append to `final_opportunities` |
| 4 | **Worker/Redis down** | Tasks stuck in queue, nothing processes | Start Redis + worker on all 4 queues |

Diagnostic command: `python scripts/check_live_pipeline.py`

---

## 11. What Has Been Done ✅

### Backend
- [x] SQLAlchemy models for full pipeline + user preferences
- [x] Supabase async connection with pooler-safe settings
- [x] FastAPI public API (`api/main.py`) with CORS for Next.js
- [x] Sources registry API with `target_url` validation, proper error handling (409/500)
- [x] Celery 4-stage pipeline: scrape → OCR → AI → dedup
- [x] Playwright Instagram scraper with API interception + DOM fallback
- [x] Gemini structured extraction (`core/llm_router.py`)
- [x] pgvector deduplication engine
- [x] Scrapy spiders for Instagram, LinkedIn, Devpost, base dynamic spider
- [x] Scrapy orchestrator with job lifecycle tracking
- [x] DB init script, seed script, connection diagnostic script
- [x] Tests for sources schema + API (`tests/test_sources.py` — 3/3 pass when DB reachable)
- [x] **Celery Beat scheduler** — auto re-scrape every 6h via `trigger_all_sources` (`core/celery_app.py`)
- [x] **`trigger_all_sources` task** — dispatches all Instagram pipeline chains (`tasks/workflows.py`)
- [x] **Shared pipeline config** — `core/pipeline_config.py` (targets, auth check, interval)
- [x] **Pre-flight diagnostic** — `scripts/check_live_pipeline.py`
- [x] **Instagram login helper** — `scrapers/auth_states/login.py`
- [x] Frontend API default port fixed to **8002**

### Frontend
- [x] Next.js 16 App Router setup
- [x] Opportunity listing with category + organization filters
- [x] Neo-brutalist UI redesign blending:
  - 3D keyboard keycaps (HELLO-style hero)
  - Grid-paper mint background
  - Retro window chrome for filter panel (`FILTERS.EXE`)
  - Segmented nav tabs (Sui Overflow style)
  - Navy stats strip
  - Hard shadows, thick borders throughout
- [x] API client with env-based base URL

### DevOps / Repo
- [x] Pushed to GitHub: https://github.com/M-Abdullah-Cheema/Hackfinder
- [x] `.gitignore` excludes `.env`, `node_modules`, `.next`, secrets
- [x] `.env.example` committed as template

---

## 12. What Still Needs To Be Done ❌

### Critical / High Priority
- [ ] **Run Instagram login once** — `python scrapers/auth_states/login.py` (user action required)
- [ ] **First live pipeline run** — verify end-to-end on your machine with worker + Redis running
- [ ] **Update Dockerfile** — Still references placeholder `my_spider`; needs Celery + Playwright + Tesseract layers
- [ ] **Production deployment** — No Vercel/Railway/Fly.io config yet

### Medium Priority
- [ ] **Wire Scrapy orchestrator to Celery** — `scrapers/orchestrator.py` runs Scrapy via subprocess separately from Celery Instagram pipeline
- [ ] **LinkedIn + static web scraping** — Spiders exist but not integrated into main Celery chain
- [ ] **User notifications (Phase 10)** — `User` and `UserPreference` models exist; Telegram/Discord delivery not wired
- [ ] **API error handling on frontend endpoints** — `/api/opportunities` returns raw 500 on DB failure (no graceful JSON error)
- [ ] **README.md at project root** — Missing; only frontend README exists

### Low Priority / Polish
- [ ] **Embeddings in seed data** — `seed_opportunities.py` inserts `embedding=None`; dedup untested with seed data
- [ ] **Flower monitoring** — Mentioned in trigger script but not set up
- [ ] **Poetry vs pip** — Project uses Poetry lockfile but setup was done via pip on Windows
- [ ] **Remove duplicate FastAPI entrypoints** — `main.py` (port 8000) vs `api/main.py` (port 8002) causes confusion

---

## 13. Known Issues & Gotchas

| Issue | Details |
|-------|---------|
| Supabase on campus WiFi | NUST network may block/interfere with PostgreSQL SSL; use hotspot/VPN |
| `.env` formatting | Must be single `DATABASE_URL=`, no spaces, port 6543 |
| `init_db.py` is destructive | Drops ALL tables before recreating |
| Old API on port 8001 | Stale uvicorn process may block port; use 8002 or kill process |
| Playwright download | 37MB wheel may stall on slow connections |
| Tesseract path | Hardcoded for Windows in `tasks/workflows.py` line 20 |
| Instagram blocking | Without `state.json` cookies, scrape_task returns None |
| pgvector extension | Must be enabled manually in Supabase SQL editor: `CREATE EXTENSION vector;` |

---

## 14. Testing

```powershell
# Pre-flight for live pipeline
python scripts/check_live_pipeline.py

# All sources tests (needs live Supabase)
python -m pytest tests/test_sources.py -v

# DB connection only
python scripts/test_db_connection.py

# Celery smoke test
python test_celery.py
```

---

## 15. Key Files to Read First (for another AI)

If you're picking up this project, read in this order:

1. `PROJECT_HANDOFF.md` (this file)
2. `core/models.py` — database schema
3. `tasks/workflows.py` — main pipeline logic
4. `api/main.py` — public API
5. `frontend/src/app/page.tsx` — UI
6. `core/schemas.py` — Source validation rules
7. `core/pipeline_config.py` — Instagram targets + Beat interval
8. `scripts/trigger_pipeline.py` — manual pipeline trigger
9. `scripts/check_live_pipeline.py` — live data pre-flight
10. `.env.example` — required configuration

---

## 16. Instagram Targets (`core/pipeline_config.py`)

```
https://www.instagram.com/gdgcloud.islamabad/
https://www.instagram.com/googledevs_isb/
https://www.instagram.com/insideimagineart/
https://www.instagram.com/change.mechanics/
https://www.instagram.com/awssbgnust/
```

---

## 17. Example: Register a Source via API

```json
POST http://localhost:8002/api/v1/sources/

{
  "name": "GDG Cloud Islamabad",
  "target_url": "https://www.instagram.com/gdgcloudislamabad/",
  "config_jsonb": {
    "platform_type": "instagram",
    "extract_images_for_ocr": true
  },
  "is_active": true,
  "tier": 1
}
```

---

## 18. Category Color Map (Frontend)

| Category | Color |
|----------|-------|
| Hackathon | Yellow `#FFE566` |
| Workshop | Blue `#5BB8FF` |
| Internship | Pink `#FF7EB3` |
| Job | Lime `#B8F55A` |
| Scholarship | Orange `#FFB347` |
| Other | Gray |

---

*Last updated: July 2026*  
*Generated for AI/developer handoff.*
