"""Local conftest for integration/api tests.

Provides an `auth_headers` fixture that creates a real PracticeUser in the
database so that `get_current_practice_user` can look it up by clerk_id.

The global `auth_headers` fixture in tests/conftest.py uses a static user_id
("test-user-id") that is NOT a valid clerk_id in the DB, causing 404s in
endpoints that call get_current_practice_user. This override creates a matching
DB record so these endpoints work correctly.
"""

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import (
    PracticeUser,
    SubscriptionStatus,
    SubscriptionTier,
    Tenant,
    User,
    UserRole,
    UserType,
)


@pytest_asyncio.fixture
async def auth_tenant(db_session: AsyncSession) -> Tenant:
    """Create a test tenant used for auth_headers."""
    tenant = Tenant(
        id=uuid4(),
        name="Auth Test Practice",
        slug=f"auth-test-{uuid4().hex[:8]}",
        tier=SubscriptionTier.PROFESSIONAL,
        subscription_status=SubscriptionStatus.ACTIVE,
        owner_email=f"owner-{uuid4().hex[:8]}@auth-test.com",
        client_count=0,
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


@pytest_asyncio.fixture
async def auth_practice_user(
    db_session: AsyncSession,
    auth_tenant: Tenant,
) -> PracticeUser:
    """Create a practice user for auth_headers."""
    clerk_id = f"clerk_{uuid4().hex[:12]}"
    base_user = User(
        id=uuid4(),
        email=f"auth-user-{uuid4().hex[:8]}@test.com",
        user_type=UserType.PRACTICE_USER,
        is_active=True,
    )
    db_session.add(base_user)
    await db_session.flush()

    practice_user = PracticeUser(
        id=uuid4(),
        tenant_id=auth_tenant.id,
        user_id=base_user.id,
        clerk_id=clerk_id,
        role=UserRole.ADMIN,
    )
    db_session.add(practice_user)
    await db_session.flush()
    return practice_user


@pytest.fixture
def auth_headers(
    auth_practice_user: PracticeUser,
    auth_tenant: Tenant,
) -> dict[str, str]:
    """Auth headers backed by a real DB user.

    Overrides the global auth_headers fixture so that endpoints calling
    get_current_practice_user can find the user by clerk_id.
    """
    from app.core.security import create_access_token

    token = create_access_token(
        user_id=auth_practice_user.clerk_id,
        tenant_id=str(auth_tenant.id),
        roles=["admin"],
    )
    return {"Authorization": f"Bearer {token}"}
