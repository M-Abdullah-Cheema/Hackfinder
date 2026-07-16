import asyncio
import sys
import os
import subprocess
import traceback
from sqlalchemy import select

# Ensure we can import core modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import AsyncSessionLocal
from core.models import Source
from core.job_manager import JobManager

async def run_crawler_fleet():
    """Fetches active sources, creates tracking jobs, and executes spiders safely."""
    
    async with AsyncSessionLocal() as session:
        # 1. Clean up any zombie jobs from previous unexpected crashes
        print("🧹 Sweeping for stale/abandoned jobs...")
        await JobManager.clean_stale_jobs(session)
        
        # 2. Fetch the active targets from Phase 1
        query = select(Source).where(Source.is_active == True)
        result = await session.execute(query)
        active_sources = result.scalars().all()

        if not active_sources:
            print("📭 No active targets found. Exiting.")
            return

        print(f"🚀 Found {len(active_sources)} active targets. Initiating fleet...")

        for source in active_sources:
            # 3. Create a trackable job record
            job_id = await JobManager.create_job(session, source.id)
            
            try:
                # 4. Mark job as running
                await JobManager.mark_running(session, job_id)
                print(f"🔄 [RUNNING] Target: {source.name} | Job ID: {job_id}")

                # 5. Execute the Scrapy process synchronously, wait for it to finish
                # We pass the target ID so the spider knows exactly what to pull
                process = subprocess.run(
                    ["poetry", "run", "scrapy", "crawl", "base_dynamic", "-a", f"source_id={source.id}"],
                    cwd=os.path.dirname(__file__), # Ensure it runs in the scrapers folder
                    capture_output=True,
                    text=True,
                    check=True # Raises exception if Scrapy crashes (e.g. syntax error, middleware crash)
                )

                # 6. Mark job explicitly as completed on success
                await JobManager.mark_completed(session, job_id)
                print(f"✅ [COMPLETED] Target: {source.name}")

            except subprocess.CalledProcessError as e:
                # Catch Scrapy-level crashes (e.g. fatal Python errors in the spider)
                error_trace = f"Subprocess Crash:\nSTDOUT:\n{e.stdout}\n\nSTDERR:\n{e.stderr}"
                await JobManager.mark_failed(session, job_id, error_trace)
                print(f"❌ [FAILED] Target: {source.name}. Error logged to database.")
                
            except Exception as e:
                # Catch absolute fatal system errors, grab the stack trace
                error_trace = traceback.format_exc()
                await JobManager.mark_failed(session, job_id, error_trace)
                print(f"🚨 [FATAL CRASH] Target: {source.name}. Traceback logged to database.")

if __name__ == "__main__":
    asyncio.run(run_crawler_fleet())