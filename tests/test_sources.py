import os
import sys
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

# 🛠️ THE FIX: Tell Python to look in the root directory for your files
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import your application components
from main import app
from api.routers.sources import get_db
from core.database import AsyncSessionLocal
from core.schemas import SourceCreate

# ==========================================================
# 1. FIXTURES: The Transactional Isolation Rig
# [Keep the rest of your file exactly the same from here down]
# ==========================================================

# ==========================================================
# 1. FIXTURES: The Transactional Isolation Rig
# ==========================================================

@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Forces every single test to execute inside an isolated transaction

    that rolls back completely upon completion. Your live database
    remains completely pristine and untouched.
    """
    async with AsyncSessionLocal() as session:
        # Begin a local nested transaction (Savepoint)
        await session.begin_nested()
        yield session
        # Roll back absolutely everything that happened during the test
        await session.rollback()

@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession):
    """Mocks the FastAPI application layer and overrides the live database

    dependency with our isolated, rollback-safe test session.
    """
    # Override FastAPI's database connection engine on the fly
    async def _get_test_db():
        yield db_session
    
    app.dependency_overrides[get_db] = _get_test_db
    
    # Use httpx AsyncClient to hit endpoints without booting a live network port
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
        
    # Clean up the dependency override after the test concludes
    app.dependency_overrides.clear()


# ==========================================================
# 2. UNIT TESTS: Schema Edge Case Protection
# ==========================================================

def test_schema_rejects_out_of_bounds_depth():
    """Ensure our Pydantic gatekeeper blocks crawler configurations

    that attempt to use an illegal crawling depth.
    """
    with pytest.raises(Exception):
        SourceCreate(
            name="Fragile University Portal",
            target_url="https://uni.edu.pk",
            config_jsonb={
                "allowed_domains": ["uni.edu.pk"],
                "max_depth": 99  # ❌ Critical Failure: Limit is 10
            }
        )

def test_schema_auto_scrubs_messy_strings():
    """Ensure our field validators successfully scrub unformatted strings

    into clean, normalized definitions before database insertion.
    """
    source = SourceCreate(
        name="   punjab tech community   ",  # Messy trailing spaces & lower case
        target_url="https://punjab.tech",
        config_jsonb={"allowed_domains": ["punjab.tech"]}
    )
    # The name should be completely cleaned up automatically
    assert source.name == "Punjab Tech Community"


# ==========================================================
# 3. INTEGRATION TESTS: FastAPI Async Endpoint Testing
# ==========================================================

@pytest.mark.asyncio
async def test_create_and_retrieve_active_source_workflow(client: AsyncClient):
    """Verifies the complete transactional lifecycle: posting a new target

    via the API, checking database persistence, and pulling it down 
    via the active crawling queue endpoint.
    """
    # 1. Send a POST request to add a new Pakistani regional target
    new_target_payload = {
        "name": "NUST Regional Tracker",
        "target_url": "https://nust.edu.pk",
        "config_jsonb": {
            "allowed_domains": ["nust.edu.pk"],
            "max_depth": 2,
            "download_delay": 4
        },
        "is_active": True,
        "tier": 2
    }
    
    post_response = await client.post("/api/v1/sources/", json=new_target_payload)
    assert post_response.status_code == 201
    post_data = post_response.json()
    assert post_data["name"] == "Nust Regional Tracker"  # Auto-cleaned name checking
    
    # 2. Query the active crawler queue to ensure it serves this new target
    get_response = await client.get("/api/v1/sources/active")
    assert get_response.status_code == 200
    
    active_queue = get_response.json()
    # Confirm our newly posted target is present in the active queue list
    assert any(item["name"] == "Nust Regional Tracker" for item in active_queue)