"""
Trigger Instagram scrapes (each fans out OCR→AI→dedup for every staged post).

Usage:
    python scripts/trigger_pipeline.py

Prerequisites:
    1. Redis running
    2. Celery worker:
         python -m celery -A core.celery_app.celery_app worker -Q scrapers,ocr_tasks,ai_extraction,deliveries -l info -P solo
    3. Instagram session: python scrapers/auth_states/login.py
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

    print(f"[*] Auth OK — dispatching {len(INSTAGRAM_TARGETS)} target(s)...")
    print("    (targets are staggered ~8s apart to reduce Instagram checkpoints)\n")

    result = trigger_all_sources.delay()
    payload = result.get(timeout=180)

    if payload.get("status") == "auth_missing":
        print("[FAIL] Worker reported missing Instagram auth.")
        return 1

    print(f"[OK] Dispatched {payload.get('dispatched', 0)} scrape task(s):\n")
    for item in payload.get("chains", []):
        print(f"  - {item['url']}")
        print(f"    task_id: {item.get('task_id') or item.get('chain_id')}\n")

    if payload.get("pending_task_id"):
        print(f"[*] Also queued pending staged promotion: {payload['pending_task_id']}")

    print("[*] Monitor worker logs or run:")
    print("    python scripts/check_live_pipeline.py")
    print("    python scripts/process_staged.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
