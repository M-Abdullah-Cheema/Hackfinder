import os
from celery import Celery
from dotenv import load_dotenv

from core.pipeline_config import SCRAPE_INTERVAL_SECONDS

load_dotenv()

# Initialize Celery, point it to Redis, and INCLUDE the tasks folder
celery_app = Celery(
    "hackathon_scraper",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    include=['tasks.workflows']  # This tells the worker where your tasks live
)

# Configure the queues and worker settings
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Define explicitly isolated queues for different resource intensities
    task_routes={
        "tasks.workflows.trigger_all_sources": {"queue": "scrapers"},
        "tasks.workflows.scrape_task": {"queue": "scrapers"},
        "tasks.workflows.ocr_task": {"queue": "ocr_tasks"},
        "tasks.workflows.prefilter_task": {"queue": "ai_extraction"},
        "tasks.workflows.ai_task": {"queue": "ai_extraction"},
        "tasks.workflows.dedup_task": {"queue": "deliveries"},
        "tasks.workflows.feed_ingest_task": {"queue": "scrapers"},
        "tasks.workflows.process_pending_staged": {"queue": "ai_extraction"},
        "tasks.workflows.backfill_geo_task": {"queue": "deliveries"},
        "tasks.workflows.backfill_links_task": {"queue": "deliveries"},
    },
    
    # DISTRIBUTED RATE LIMITING
    # Protects burner Instagram accounts from burst scrapes / checkpointing
    task_annotations={
        "tasks.workflows.scrape_task": {"rate_limit": "3/m"},
        "tasks.workflows.ai_task": {"rate_limit": "20/m"},
    },

    # Celery Beat — automatic background scraping every SCRAPE_INTERVAL_SECONDS (default 6h)
    beat_schedule={
        "scrape-instagram-periodic": {
            "task": "tasks.workflows.trigger_all_sources",
            "schedule": float(SCRAPE_INTERVAL_SECONDS),
        },
    },
)