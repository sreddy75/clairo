"""Pytest fixtures for Clairo backend tests.

This module provides shared fixtures for all test types:
- Unit tests: Mocked dependencies
- Integration tests: Real database with transaction rollback
- E2E tests: Full stack with test client

Usage:
    def test_something(db_session, test_client):
        # db_session: AsyncSession with automatic rollback
        # test_client: httpx AsyncClient for API tests
        pass
"""

from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings
from app.database import get_db
from app.modules.action_items import models as action_items_models  # noqa: F401
from app.modules.agents import models as agents_models  # noqa: F401

# ==============================================================================
# Import all models to ensure SQLAlchemy relationships are resolved
# ==============================================================================
# This is required because some models have forward references to other models
# (e.g., XeroConnection references Insight). By importing all models here,
# we ensure that all model classes are registered before any tests run.
# noqa comments suppress unused import warnings - these imports are for side effects
import app.modules.admin.models as admin_models  # noqa: F401
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.bas import models as bas_models  # noqa: F401
from app.modules.billing import models as billing_models  # noqa: F401
from app.modules.insights import models as insights_models  # noqa: F401
from app.modules.integrations.xero import models as xero_models  # noqa: F401
from app.modules.knowledge import models as knowledge_models  # noqa: F401
from app.modules.notifications import models as notifications_models  # noqa: F401
from app.modules.onboarding import models as onboarding_models  # noqa: F401
from app.modules.portal import models as portal_models  # noqa: F401
from app.modules.quality import models as quality_models  # noqa: F401
from app.modules.tax_planning import models as tax_planning_models  # noqa: F401
from app.modules.triggers import models as triggers_models  # noqa: F401

# Models added in later specs — import models.py directly to register
# SQLAlchemy classes without triggering router/service imports that pull
# in heavy dependencies (minio, anthropic, etc.)
try:
    import app.modules.portal.models as portal_models  # noqa: F401
except Exception:
    pass
try:
    import app.modules.bas.classification_models as classification_models  # noqa: F401
except Exception:
    pass
try:
    import app.modules.feedback.models as feedback_models  # noqa: F401
except Exception:
    pass
try:
    import app.modules.tax_planning.models as tax_planning_models  # noqa: F401
except Exception:
    pass

# ==============================================================================
# Database Fixtures
# ==============================================================================


@pytest_asyncio.fixture
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create a test database engine.

    Function-scoped to avoid event loop conflicts between session-scoped
    fixtures and function-scoped tests. Tables are managed by alembic
    migrations — run `alembic upgrade head` before running tests.
    """
    settings = get_settings()
    engine = create_async_engine(
        settings.database.url,
        echo=False,
        pool_pre_ping=True,
    )

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(
    test_engine: AsyncEngine,
) -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session with automatic rollback.

    Each test gets its own session with a transaction that is rolled back
    after the test completes. This ensures test isolation without needing
    to recreate the database for each test.
    """
    connection = await test_engine.connect()
    transaction = await connection.begin()

    session_factory = async_sessionmaker(
        bind=connection,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    session = session_factory()

    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()


# ==============================================================================
# Application Fixtures
# ==============================================================================


@pytest_asyncio.fixture
async def test_client(
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP client for API testing.

    Overrides the database dependency to use the test session,
    ensuring all API operations use the same transaction that will
    be rolled back.
    """
    from app.main import app

    # Override the database dependency
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        yield client

    # Clean up overrides
    app.dependency_overrides.clear()


@pytest.fixture
def anyio_backend() -> str:
    """Specify the async backend for anyio tests."""
    return "asyncio"


# ==============================================================================
# Authentication Fixtures
# ==============================================================================


@pytest.fixture
def test_user_data() -> dict[str, Any]:
    """Provide test user data."""
    return {
        "id": "test-user-id",
        "email": "test@example.com",
        "tenant_id": "test-tenant-id",
        "roles": ["user"],
    }


@pytest.fixture
def test_admin_data() -> dict[str, Any]:
    """Provide test admin user data."""
    return {
        "id": "test-admin-id",
        "email": "admin@example.com",
        "tenant_id": "test-tenant-id",
        "roles": ["admin", "user"],
    }


@pytest.fixture
def auth_token(test_user_data: dict[str, Any]) -> str:
    """Create an authentication token for testing."""
    from app.core.security import create_access_token

    return create_access_token(
        user_id=test_user_data["id"],
        tenant_id=test_user_data["tenant_id"],
        roles=test_user_data["roles"],
    )


@pytest.fixture
def auth_headers(auth_token: str) -> dict[str, str]:
    """Provide authentication headers for API requests."""
    return {"Authorization": f"Bearer {auth_token}"}


# ==============================================================================
# Utility Fixtures
# ==============================================================================


@pytest.fixture
def mock_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Override settings for testing.

    Usage:
        def test_something(mock_settings, monkeypatch):
            monkeypatch.setenv("DEBUG", "false")
            # Test with modified settings
    """
    # Clear the settings cache so new settings are loaded
    from app.config import get_settings

    get_settings.cache_clear()
