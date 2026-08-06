"""
Promote already-staged Instagram posts that never reached final_opportunities.

Does NOT re-scrape Instagram — only runs OCR → prefilter → Groq → dedup
for pending ScrapedOpportunity rows.

Usage:
    python scripts/process_staged.py
    python scripts/process_staged.py 80
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

# Must register the Redis-backed app before using shared_task.delay()
from core.celery_app import celery_app  # noqa: F401
from tasks.workflows import process_pending_staged


def main() -> int:
    limit = 40
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except ValueError:
            print("Usage: python scripts/process_staged.py [limit]")
            return 1

    print(f"[*] Queueing up to {limit} pending staged posts for OCR/AI/dedup...")
    result = process_pending_staged.delay(limit)
    print(f"[OK] Task id: {result.id}")
    print("    Watch the Celery worker for fan-out of post pipelines.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
