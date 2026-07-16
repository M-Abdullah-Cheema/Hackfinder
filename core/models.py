import enum
import uuid
import os
from datetime import datetime, timezone

from sqlalchemy import Index, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import String, Text, DateTime, Integer, Boolean, JSON
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy import Enum as SQLEnum
from pgvector.sqlalchemy import Vector  # Import Vector for semantic search
from cryptography.fernet import Fernet  # Import Fernet for military-grade encryption
from sqlalchemy.types import TypeDecorator

class Base(DeclarativeBase):
    pass

class ScrapedItem(Base):
    __tablename__ = "scraped_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(String, unique=True, index=True)
    title: Mapped[str] = mapped_column(String, nullable=True)
    raw_content: Mapped[str] = mapped_column(Text, nullable=True)
    
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )

class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    target_url: Mapped[str] = mapped_column(String, nullable=False)
    config_jsonb: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    tier: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    __table_args__ = (
        Index("ix_scheduler_queue", "is_active", "tier"),
    )

class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class CrawlingJob(Base):
    __tablename__ = "crawling_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    status: Mapped[JobStatus] = mapped_column(SQLEnum(JobStatus), default=JobStatus.PENDING, index=True)
    error_log: Mapped[str] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

class ScrapedOpportunity(Base):
    __tablename__ = "scraped_opportunities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    platform_post_id: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=True)
    image_urls: Mapped[list[str]] = mapped_column(JSON, nullable=True, default=list)
    # Tracks whether the attached images have been run through the OCR engine
    ocr_processed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

# ==========================================
# PHASE 8 - FINAL PRODUCTION TABLE
# ==========================================
class FinalOpportunity(Base):
    __tablename__ = "final_opportunities"
    
    # Standard metadata definitions
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    organization_name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    registration_url: Mapped[str] = mapped_column(String, nullable=True, index=True)
    platform_post_id: Mapped[str] = mapped_column(String, unique=True, index=True)

    # 1536-dimensional coordinates for text-embedding-3-small
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=True)

    # High-Performance HNSW Index configuration for rapid similarity lookups
    __table_args__ = (
        Index(
            "ix_semantic_similarity_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"}
        ),
    )

# ==========================================
# NEW: PHASE 10 - USERS & PREFERENCES
# ==========================================
# Generates a temporary key if one isn't in your .env file
# In production, you will lock this down to a permanent secret key!
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
f = Fernet(ENCRYPTION_KEY.encode())

class EncryptedString(TypeDecorator):
    """Custom SQLAlchemy type that automatically encrypts data before saving to the DB."""
    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return f.encrypt(value.encode()).decode()
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return f.decrypt(value.encode()).decode()
        return value

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String, nullable=True, unique=True, index=True)
    
    # Encrypted to protect user privacy and prevent webhook hijacking
    telegram_chat_id: Mapped[str] = mapped_column(EncryptedString, nullable=True)
    discord_webhook_url: Mapped[str] = mapped_column(EncryptedString, nullable=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class UserPreference(Base):
    __tablename__ = "user_preferences"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    
    # What kind of opportunities do they want to be notified about?
    target_category: Mapped[str] = mapped_column(String, nullable=True, index=True)
    target_organization: Mapped[str] = mapped_column(String, nullable=True, index=True)