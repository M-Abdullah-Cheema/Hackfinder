# IMPORT THIS FIRST so the script knows about Redis!
from core.celery_app import celery_app 

from celery import chain
from tasks.workflows import scrape_task, ocr_task, ai_task, dedup_task

# Chain the tasks together
master_pipeline = chain(
    scrape_task.s("https://www.linkedin.com/company/gdgislamabad/posts/"),
    ocr_task.s(),
    ai_task.s(),
    dedup_task.s()
)

# Send the chain to Redis/Celery
result = master_pipeline.apply_async()
print(f"Job submitted to Celery! Task ID: {result.id}")

