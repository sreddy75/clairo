"""Alembic migration environment for Clairo.

This module configures Alembic for async SQLAlchemy migrations.
It supports both online (connected) and offline (SQL script) migrations.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import get_settings
from app.database import Base

# Import all models so they are registered with Base.metadata
# This is required for Alembic autogenerate to detect them
from app.modules.auth.models import Invitation, PracticeUser, Tenant, User  # noqa: F401
from app.modules.onboarding.models import (  # noqa: F401
    BulkImportJob,
    EmailDrip,
    OnboardingProgress,
)
from app.modules.integrations.xero.models import *  # noqa: F401, F403

# Alembic Config object
config = context.config

# Configure logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate support
target_metadata = Base.metadata


def get_database_url() -> str:
    """Get database URL from application settings.

    Returns:
        Database URL for async migrations (postgresql+asyncpg://).
    """
    settings = get_settings()
    url = settings.database.url

    # Ensure URL uses asyncpg driver for async migrations
    # Railway provides postgresql:// but we need postgresql+asyncpg://
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)

    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine.
    Calls to context.execute() emit the given string to the script output.
    """
    url = get_database_url()

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with the given connection.

    Args:
        connection: Database connection for migrations.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine.

    Creates an async Engine and associates a connection with the context.
    """
    # Get database URL and configure engine
    url = get_database_url()

    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = url

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Wraps the async migration runner for the sync Alembic interface.
    """
    asyncio.run(run_async_migrations())


# Determine which mode to run
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
