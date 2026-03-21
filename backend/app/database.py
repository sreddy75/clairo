"""Async SQLAlchemy database configuration.

This module provides:
- DeclarativeBase for all SQLAlchemy models
- Async engine with connection pooling
- AsyncSession factory for dependency injection
- Common mixins for timestamps and multi-tenancy

Usage:
    from app.database import get_db, BaseModel, TenantMixin

    class MyModel(BaseModel, TenantMixin):
        __tablename__ = "my_table"
        name: Mapped[str] = mapped_column(String(255))
"""

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import DateTime, MetaData, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config import get_settings

# Naming convention for constraints (required for Alembic migrations)
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models.

    Provides:
    - Consistent naming convention for constraints
    - Type annotation support
    - Common metadata configuration
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    # Enable type annotations for mapped columns
    type_annotation_map: ClassVar[dict[type, Any]] = {
        uuid.UUID: UUID(as_uuid=True),
        datetime: DateTime(timezone=True),
    }


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps.

    Automatically sets created_at on insert and updates updated_at on each update.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TenantMixin:
    """Mixin for multi-tenant tables.

    Adds tenant_id column with index for efficient tenant-scoped queries.
    Use with Row-Level Security (RLS) policies in PostgreSQL.
    """

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )


class BaseModel(Base, TimestampMixin):
    """Abstract base model with UUID primary key and timestamps.

    All domain models should inherit from this class.
    For tenant-scoped models, also inherit from TenantMixin.

    Example:
        class User(BaseModel):
            __tablename__ = "users"
            email: Mapped[str] = mapped_column(String(255), unique=True)

        class Client(BaseModel, TenantMixin):
            __tablename__ = "clients"
            name: Mapped[str] = mapped_column(String(255))
    """

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


def create_engine_from_settings() -> Any:
    """Create async SQLAlchemy engine from settings.

    Returns:
        AsyncEngine: Configured async database engine.
    """
    settings = get_settings()
    db_settings = settings.database

    return create_async_engine(
        db_settings.url,
        pool_size=db_settings.pool_size,
        max_overflow=db_settings.max_overflow,
        pool_timeout=db_settings.pool_timeout,
        pool_recycle=db_settings.pool_recycle,
        echo=db_settings.echo,
        # Async-specific settings
        pool_pre_ping=True,  # Verify connections before use
    )


# Global engine instance (lazy initialization)
_engine = None


def get_engine() -> Any:
    """Get or create the async database engine.

    Returns:
        AsyncEngine: The async database engine.
    """
    global _engine
    if _engine is None:
        _engine = create_engine_from_settings()
    return _engine


# Session factory (lazy initialization)
_async_session_factory = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the async session factory.

    Returns:
        async_sessionmaker: Factory for creating AsyncSession instances.
    """
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions.

    Provides an async session with automatic commit/rollback handling.
    On success, the session is committed. On exception, it's rolled back.

    Usage:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()

    Yields:
        AsyncSession: Database session for the request.
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for database sessions outside FastAPI.

    Use this for background tasks, scripts, or tests where you need
    a database session without the FastAPI dependency injection.

    Usage:
        async with get_db_context() as db:
            result = await db.execute(select(Item))
            items = result.scalars().all()

    Yields:
        AsyncSession: Database session for the context.
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_celery_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for database sessions in Celery tasks.

    Creates a fresh engine and session for each task to avoid event loop
    conflicts. The asyncpg driver binds connections to specific event loops,
    so we need a fresh connection pool for each Celery task invocation.

    Usage:
        async with get_celery_db_context() as db:
            result = await db.execute(select(Item))
            items = result.scalars().all()

    Yields:
        AsyncSession: Database session for the Celery task.
    """
    # Create a fresh engine for this event loop
    engine = create_engine_from_settings()
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await engine.dispose()


async def init_db() -> None:
    """Initialize database connection.

    Call this during application startup to verify database connectivity.
    """
    engine = get_engine()
    async with engine.begin() as conn:
        # Verify connection by running a simple query
        await conn.execute(text("SELECT 1"))


async def close_db() -> None:
    """Close database connections.

    Call this during application shutdown to clean up resources.
    """
    global _engine, _async_session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_factory = None
