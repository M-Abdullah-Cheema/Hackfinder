"""
Trigger the full 4-stage Celery pipeline for every Instagram target.

Usage:
    python scripts/trigger_pipeline.py

Prerequisites:
    1. Redis running: docker run -p 6379:6379 redis
    2. Celery workers started:
         celery -A core.celery_app worker -Q scrapers       -c 2 --loglevel=info
         celery -A core.celery_app worker -Q ocr_tasks      -c 4 --loglevel=info
         celery -A core.celery_app worker -Q ai_extraction  -c 4 --loglevel=info
         celery -A core.celery_app worker -Q deliveries     -c 4 --loglevel=info
    3. (Optional) Provide Instagram session: see scrapers/auth_states/README.md
"""

from celery import chain
from core.celery_app import celery_app  # noqa: F401 – ensures tasks are registered
from tasks.workflows import scrape_task, ocr_task, ai_task, dedup_task

INSTAGRAM_TARGETS = [
    "https://www.instagram.com/gdgcloud.islamabad/?hl=en",
    "https://www.instagram.com/googledevs_isb/?hl=en",
    "https://www.instagram.com/insideimagineart/?hl=en",
    "https://www.instagram.com/change.mechanics/?hl=en",
    "https://www.instagram.com/awssbgnust/?hl=en",
]

if __name__ == "__main__":
    print("🚀 Dispatching scrape pipelines for all Instagram targets...\n")

    for url in INSTAGRAM_TARGETS:
        pipeline = chain(
            scrape_task.s(url),
            ocr_task.s(),
            ai_task.s(),
            dedup_task.s(),
        )
        result = pipeline.delay()
        print(f"  ✅ Pipeline dispatched for: {url}")
        print(f"     Task chain ID: {result.id}\n")

    print("✔ All pipelines dispatched. Monitor progress with:")
    print("  celery -A core.celery_app flower  (or inspect your worker logs)")
