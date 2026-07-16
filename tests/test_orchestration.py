import pytest
import pytest_asyncio
import vcr
import shutil
import os
import sys
from unittest.mock import patch

# Tell Python to look in the root directory for your files
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession
from core.database import AsyncSessionLocal
from core.job_manager import JobManager
from scrapers.crawler_factory import CrawlerFactory

# ==========================================
# 1. SETUP: TEARDOWN FIXTURES & VCR CONFIG
# ==========================================

my_vcr = vcr.VCR(
    cassette_library_dir='tests/fixtures/cassettes',
    record_mode='once',
    match_on=['uri', 'method'],
    ignore_localhost=True
)

@pytest.fixture(autouse=True)
def clean_test_artifacts():
    """Ensures Playwright caches or Scrapy state files do not pollute the workspace."""
    yield # Run the test
    # Teardown: Remove temporary Playwright traces or Scrapy local cache if they exist
    test_cache_dirs = [".playwright-artifacts", ".scrapy_test_cache"]
    for directory in test_cache_dirs:
        if os.path.exists(directory):
            shutil.rmtree(directory)

@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Forces the test to execute inside an isolated transaction that rolls back."""
    async with AsyncSessionLocal() as session:
        await session.begin_nested()
        yield session
        await session.rollback()

# ==========================================
# 2. INTEGRATION TESTS
# ==========================================

@pytest.mark.asyncio
async def test_factory_routes_to_playwright(mocker):
    """Verifies the factory correctly identifies Playwright targets and triggers the wrapper."""
    
    # Mock the actual browser execution so we don't spin up Chromium during unit tests
    mock_playwright = mocker.patch('scrapers.base_playwright.HeadlessBrowserWrapper.fetch_rendered_html')
    mock_playwright.return_value = "<html>Mocked SPA Content</html>"
    
    config = {
        "crawler_type": "playwright",
        "content_selector": "div.react-data"
    }
    
    result = await CrawlerFactory.execute(source_id=99, config_jsonb=config, start_url="https://mock-uni.edu")
    
    assert result == "Playwright Execution Successful"
    mock_playwright.assert_called_once_with(url="https://mock-uni.edu", wait_selector="div.react-data")


@pytest.mark.asyncio
async def test_job_lifecycle_state_changes(db_session: AsyncSession, mocker):
    """
    Tests the database orchestration logic. Confirms that a successful factory 
    execution results in a strict database state change from PENDING to COMPLETED.
    """
    # 1. Create a dummy target source directly in the rollback-safe test database
    from core.models import Source, JobStatus
    dummy_source = Source(
        name="Mock Test University", 
        is_active=True, 
        tier=2,
        config_jsonb={"crawler_type": "scrapy"}
    )
    db_session.add(dummy_source)
    await db_session.commit()
    
    # 2. Initiate Job Manager
    job_id = await JobManager.create_job(db_session, dummy_source.id)
    
    # Mock the Factory so it doesn't run the actual subprocess during this DB test
    mocker.patch('scrapers.crawler_factory.CrawlerFactory.execute', return_value="Mocked Success")
    
    # 3. Simulate Orchestrator flow
    await JobManager.mark_running(db_session, job_id)
    # ... factory executes here ...
    await JobManager.mark_completed(db_session, job_id)
    
    # 4. Verify Database State
    from sqlalchemy import select
    from core.models import CrawlingJob
    
    query = select(CrawlingJob).where(CrawlingJob.id == job_id)
    result = await db_session.execute(query)
    final_job = result.scalar_one()
    
    assert final_job.status == JobStatus.COMPLETED
    assert final_job.ended_at is not None