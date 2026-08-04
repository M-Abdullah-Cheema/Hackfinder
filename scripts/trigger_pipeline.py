"""
Trigger the full 4-stage Celery pipeline for every Instagram target.

Usage:
    python scripts/trigger_pipeline.py

Prerequisites:
    1. Redis running: docker run -p 6379:6379 redis
    2. Celery worker listening on all queues:
         python -m celery -A core.celery_app worker -Q scrapers,ocr_tasks,ai_extraction,deliveries --loglevel=info --concurrency=2
    3. Instagram session saved: python scrapers/auth_states/login.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.celery_app import celery_app  # noqa: F401 — registers tasks
from core.pipeline_config import AUTH_STATE_PATH, INSTAGRAM_TARGETS, instagram_auth_ready
from tasks.workflows import trigger_all_sources


def main() -> int:
    print("[*] HackFinder live pipeline trigger\n")

    if not instagram_auth_ready():
        print(f"[FAIL] Instagram auth not found at: {AUTH_STATE_PATH}")
        print("       Run this first:  python scrapers/auth_states/login.py")
        return 1

    print(f"[*] Auth OK — dispatching {len(INSTAGRAM_TARGETS)} target(s)...\n")

    # Run synchronously in-process for immediate feedback (still async via Celery)
    result = trigger_all_sources.delay()
    payload = result.get(timeout=30)

    if payload.get("status") == "auth_missing":
        print("[FAIL] Worker reported missing Instagram auth.")
        return 1

    print(f"[OK] Dispatched {payload.get('dispatched', 0)} pipeline chain(s):\n")
    for chain in payload.get("chains", []):
        print(f"  - {chain['url']}")
        print(f"    chain_id: {chain['chain_id']}\n")

    print("[*] Monitor worker logs or run:")
    print("    python scripts/check_live_pipeline.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
