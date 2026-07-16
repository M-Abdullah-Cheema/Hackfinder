import traceback
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from core.models import CrawlingJob, JobStatus

class JobManager:
    """Handles the strict lifecycle of crawling jobs."""
    
    @staticmethod
    async def create_job(session: AsyncSession, source_id: int) -> str:
        """Instantiates a new PENDING job and returns its UUID."""
        job = CrawlingJob(source_id=source_id, status=JobStatus.PENDING)
        session.add(job)
        await session.commit()
        return str(job.id)

    @staticmethod
    async def mark_running(session: AsyncSession, job_id: str):
        """Flips state to RUNNING and locks in the start time."""
        await session.execute(
            update(CrawlingJob)
            .where(CrawlingJob.id == job_id)
            .values(status=JobStatus.RUNNING, started_at=datetime.now(timezone.utc))
        )
        await session.commit()

    @staticmethod
    async def mark_completed(session: AsyncSession, job_id: str):
        """Flips state to COMPLETED and locks in the end time."""
        await session.execute(
            update(CrawlingJob)
            .where(CrawlingJob.id == job_id)
            .values(status=JobStatus.COMPLETED, ended_at=datetime.now(timezone.utc))
        )
        await session.commit()

    @staticmethod
    async def mark_failed(session: AsyncSession, job_id: str, error_message: str):
        """Captures the stack trace and cleanly fails the job."""
        await session.execute(
            update(CrawlingJob)
            .where(CrawlingJob.id == job_id)
            .values(
                status=JobStatus.FAILED, 
                error_log=error_message, 
                ended_at=datetime.now(timezone.utc)
            )
        )
        await session.commit()

    @staticmethod
    async def clean_stale_jobs(session: AsyncSession):
        """Prevents task locking: Resets jobs stuck in RUNNING state back to PENDING."""
        result = await session.execute(
            update(CrawlingJob)
            .where(CrawlingJob.status == JobStatus.RUNNING)
            .values(status=JobStatus.PENDING, error_log="System Reset: Job was abandoned.")
        )
        await session.commit()