import os
from celery import Celery
from dotenv import load_dotenv

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
        "tasks.workflows.scrape_task": {"queue": "scrapers"},
        "tasks.workflows.ocr_task": {"queue": "ocr_tasks"},
        "tasks.workflows.ai_task": {"queue": "ai_extraction"},
        "tasks.workflows.dedup_task": {"queue": "deliveries"},
    },
    
    # DISTRIBUTED RATE LIMITING
    # Protects your burner accounts by strictly limiting how fast scraping tasks execute
    task_annotations={
        "tasks.workflows.scrape_task": {"rate_limit": "5/m"}  # Max 5 scrapes per minute
    }
)