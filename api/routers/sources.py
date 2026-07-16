from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from typing import List

# Import your core engine files
from core.database import AsyncSessionLocal
from core.models import Source
from core.schemas import SourceCreate, SourceUpdate, SourceResponse

# Create the router
router = APIRouter(prefix="/api/v1/sources", tags=["Target Registry"])

# Dependency: This securely opens and closes a database session for every API request
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# ==========================================
# 1. CREATE: Add a new scraping target
# ==========================================
@router.post("/", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(source_in: SourceCreate, db: AsyncSession = Depends(get_db)):
    # Pydantic already validated 'source_in'. We just dump it into the SQLAlchemy model.
    new_source = Source(**source_in.model_dump())
    db.add(new_source)
    try:
        await db.commit()
        await db.refresh(new_source)
        return new_source
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Source with this name already exists.",
        )
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create source.",
        )

# ==========================================
# 2. READ: The highly optimized queue for the Scraper
# ==========================================
@router.get("/active", response_model=List[SourceResponse])
async def get_active_sources(db: AsyncSession = Depends(get_db)):
    """The scraper hits this endpoint to know what to do today."""
    
    # Notice the clean SQLAlchemy 2.0 async syntax. No synchronous blocking!
    # We query only active targets and order them by priority tier.
    query = select(Source).where(Source.is_active == True).order_by(Source.tier.asc())
    result = await db.execute(query)
    
    # .scalars().all() strips away the SQLAlchemy wrapper and returns pure Python objects
    return result.scalars().all()

# ==========================================
# 3. UPDATE: Toggle active status or update rules
# ==========================================
@router.patch("/{source_id}", response_model=SourceResponse)
async def update_source(source_id: int, source_update: SourceUpdate, db: AsyncSession = Depends(get_db)):
    """Used to instantly pause a scraper if the target website layout changes."""
    
    # 1. Find the target
    query = select(Source).where(Source.id == source_id)
    result = await db.execute(query)
    db_source = result.scalar_one_or_none()
    
    if not db_source:
        raise HTTPException(status_code=404, detail="Source not found")

    # 2. Apply only the fields that were provided in the request
    update_data = source_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_source, key, value)

    try:
        await db.commit()
        await db.refresh(db_source)
        return db_source
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Source with this name already exists.",
        )
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update source.",
        )
