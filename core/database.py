from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from core.config import settings

# 1. The Async Engine: Manages the actual connections to PostgreSQL
engine = create_async_engine(
    settings.database_url,
    echo=False,         # Set to True if you want your terminal to print out every SQL query it runs
    pool_size=20,       # Keep 20 connections constantly open and ready for Scrapy workers
    max_overflow=10,    # Allow 10 extra temporary connections if there's a massive spike in scraping
    connect_args={
        "ssl": "require",
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    },
)

# 2. The SessionMaker: Yields individual, safe database sessions to your Scrapy pipelines
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)