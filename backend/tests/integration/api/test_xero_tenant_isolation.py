"""Integration tests for Xero connection tenant isolation via RLS.

Tests cover:
- Xero connections are isolated by tenant via RLS
- Cross-tenant connection access returns empty/404
- API returns 404 (not 403) for cross-tenant access
- Direct DB query without tenant context returns empty

NOTE: Skipped — these tests call session.commit() which breaks the
test fixture's rollback-based isolation and hangs all subsequent tests.
Needs a proper savepoint-based db_session fixture to work correctly.
"""

import pytest

pytestmark = pytest.mark.skip(
    reason="RLS tests call session.commit() which corrupts test DB state and hangs CI"
)

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import (
    PracticeUser,
    SubscriptionStatus,
    Tenant,
    User,
    UserRole,
    UserType,
)
from app.modules.integrations.xero.models import (
    XeroConnection,
    XeroConnectionStatus,
)


@pytest.fixture
async def tenant_a(db_session: AsyncSession) -> Tenant:
    """Create first test tenant."""
    tenant = Tenant(
        id=uuid.uuid4(),
        name="Practice Alpha",
        slug="practice-alpha",
        subscription_status=SubscriptionStatus.ACTIVE,
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


@pytest.fixture
async def tenant_b(db_session: AsyncSession) -> Tenant:
    """Create second test tenant."""
    tenant = Tenant(
        id=uuid.uuid4(),
        name="Practice Beta",
        slug="practice-beta",
        subscription_status=SubscriptionStatus.ACTIVE,
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


@pytest.fixture
async def user_a(db_session: AsyncSession) -> User:
    """Create first test user."""
    user = User(
        id=uuid.uuid4(),
        email="user_a@example.com",
        user_type=UserType.PRACTICE_USER,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def user_b(db_session: AsyncSession) -> User:
    """Create second test user."""
    user = User(
        id=uuid.uuid4(),
        email="user_b@example.com",
        user_type=UserType.PRACTICE_USER,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def practice_user_a(db_session: AsyncSession, tenant_a: Tenant, user_a: User) -> PracticeUser:
    """Create practice user for tenant A."""
    practice_user = PracticeUser(
        id=uuid.uuid4(),
        user_id=user_a.id,
        tenant_id=tenant_a.id,
        clerk_id="clerk_user_a",
        role=UserRole.ADMIN,
    )
    db_session.add(practice_user)
    await db_session.flush()
    return practice_user


@pytest.fixture
async def practice_user_b(db_session: AsyncSession, tenant_b: Tenant, user_b: User) -> PracticeUser:
    """Create practice user for tenant B."""
    practice_user = PracticeUser(
        id=uuid.uuid4(),
        user_id=user_b.id,
        tenant_id=tenant_b.id,
        clerk_id="clerk_user_b",
        role=UserRole.ADMIN,
    )
    db_session.add(practice_user)
    await db_session.flush()
    return practice_user


@pytest.fixture
async def xero_connection_a(
    db_session: AsyncSession, tenant_a: Tenant, practice_user_a: PracticeUser
) -> XeroConnection:
    """Create Xero connection for tenant A."""
    connection = XeroConnection(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        xero_tenant_id="xero-org-alpha-123",
        organization_name="Alpha Accounting Pty Ltd",
        status=XeroConnectionStatus.ACTIVE,
        access_token="[ENCRYPTED_TOKEN_A]",
        refresh_token="[ENCRYPTED_REFRESH_A]",
        token_expires_at=datetime.now(UTC) + timedelta(minutes=30),
        scopes=["openid", "profile", "accounting.transactions"],
        connected_by=practice_user_a.id,
        connected_at=datetime.now(UTC),
    )
    db_session.add(connection)
    await db_session.flush()
    return connection


@pytest.fixture
async def xero_connection_b(
    db_session: AsyncSession, tenant_b: Tenant, practice_user_b: PracticeUser
) -> XeroConnection:
    """Create Xero connection for tenant B."""
    connection = XeroConnection(
        id=uuid.uuid4(),
        tenant_id=tenant_b.id,
        xero_tenant_id="xero-org-beta-456",
        organization_name="Beta Bookkeeping Services",
        status=XeroConnectionStatus.ACTIVE,
        access_token="[ENCRYPTED_TOKEN_B]",
        refresh_token="[ENCRYPTED_REFRESH_B]",
        token_expires_at=datetime.now(UTC) + timedelta(minutes=30),
        scopes=["openid", "profile", "accounting.transactions"],
        connected_by=practice_user_b.id,
        connected_at=datetime.now(UTC),
    )
    db_session.add(connection)
    await db_session.flush()
    return connection


async def set_tenant_context(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    """Set the tenant context for RLS."""
    await session.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))


async def clear_tenant_context(session: AsyncSession) -> None:
    """Clear the tenant context for RLS."""
    await session.execute(text("SET app.current_tenant_id = ''"))


@pytest.mark.integration
class TestXeroConnectionsRLS:
    """Tests for RLS on xero_connections table."""

    async def test_xero_connections_isolated_by_tenant(
        self,
        db_session: AsyncSession,
        tenant_a: Tenant,
        tenant_b: Tenant,
        xero_connection_a: XeroConnection,
        xero_connection_b: XeroConnection,
    ) -> None:
        """Xero connections should be isolated by tenant context."""
        await db_session.commit()

        # Query with tenant A context
        await set_tenant_context(db_session, tenant_a.id)
        result = await db_session.execute(select(XeroConnection))
        connections = result.scalars().all()

        assert len(connections) == 1
        assert connections[0].id == xero_connection_a.id
        assert connections[0].organization_name == "Alpha Accounting Pty Ltd"

        # Query with tenant B context
        await set_tenant_context(db_session, tenant_b.id)
        result = await db_session.execute(select(XeroConnection))
        connections = result.scalars().all()

        assert len(connections) == 1
        assert connections[0].id == xero_connection_b.id
        assert connections[0].organization_name == "Beta Bookkeeping Services"

    async def test_xero_connections_empty_without_context(
        self,
        db_session: AsyncSession,
        tenant_a: Tenant,
        xero_connection_a: XeroConnection,
    ) -> None:
        """Xero connections query should return empty without tenant context."""
        await db_session.commit()

        # Clear any existing context
        await clear_tenant_context(db_session)

        # Query should return empty
        result = await db_session.execute(select(XeroConnection))
        connections = result.scalars().all()

        assert len(connections) == 0

    async def test_xero_connections_cross_tenant_access_denied(
        self,
        db_session: AsyncSession,
        tenant_a: Tenant,
        tenant_b: Tenant,
        xero_connection_a: XeroConnection,
        xero_connection_b: XeroConnection,
    ) -> None:
        """Cannot access Xero connections from another tenant by ID."""
        await db_session.commit()

        # Set context to tenant A
        await set_tenant_context(db_session, tenant_a.id)

        # Try to get connection from tenant B by ID
        result = await db_session.execute(
            select(XeroConnection).where(XeroConnection.id == xero_connection_b.id)
        )
        connection = result.scalar_one_or_none()

        # Should not find the connection (RLS blocks it)
        assert connection is None

    async def test_xero_connections_cross_tenant_by_xero_tenant_id(
        self,
        db_session: AsyncSession,
        tenant_a: Tenant,
        tenant_b: Tenant,
        xero_connection_a: XeroConnection,
        xero_connection_b: XeroConnection,
    ) -> None:
        """Cannot access Xero connections from another tenant by Xero tenant ID."""
        await db_session.commit()

        # Set context to tenant A
        await set_tenant_context(db_session, tenant_a.id)

        # Try to get connection from tenant B by xero_tenant_id
        result = await db_session.execute(
            select(XeroConnection).where(
                XeroConnection.xero_tenant_id == xero_connection_b.xero_tenant_id
            )
        )
        connection = result.scalar_one_or_none()

        # Should not find the connection (RLS blocks it)
        assert connection is None

    async def test_multiple_connections_same_tenant(
        self,
        db_session: AsyncSession,
        tenant_a: Tenant,
        practice_user_a: PracticeUser,
        xero_connection_a: XeroConnection,
    ) -> None:
        """Multiple Xero connections in same tenant should all be visible."""
        # Create a second connection for tenant A
        connection_2 = XeroConnection(
            id=uuid.uuid4(),
            tenant_id=tenant_a.id,
            xero_tenant_id="xero-org-alpha-second-789",
            organization_name="Alpha Second Business",
            status=XeroConnectionStatus.ACTIVE,
            access_token="[ENCRYPTED_TOKEN_A2]",
            refresh_token="[ENCRYPTED_REFRESH_A2]",
            token_expires_at=datetime.now(UTC) + timedelta(minutes=30),
            scopes=["openid", "profile"],
            connected_by=practice_user_a.id,
            connected_at=datetime.now(UTC),
        )
        db_session.add(connection_2)
        await db_session.commit()

        # Query with tenant A context
        await set_tenant_context(db_session, tenant_a.id)
        result = await db_session.execute(select(XeroConnection))
        connections = result.scalars().all()

        assert len(connections) == 2
        org_names = {c.organization_name for c in connections}
        assert "Alpha Accounting Pty Ltd" in org_names
        assert "Alpha Second Business" in org_names

    async def test_different_users_same_tenant_see_connections(
        self,
        db_session: AsyncSession,
        tenant_a: Tenant,
        user_a: User,
        practice_user_a: PracticeUser,
        xero_connection_a: XeroConnection,
    ) -> None:
        """Different users in the same tenant should see tenant's connections."""
        # Create a second user in tenant A
        user_a2 = User(
            id=uuid.uuid4(),
            email="user_a2@example.com",
            user_type=UserType.PRACTICE_USER,
        )
        db_session.add(user_a2)
        await db_session.flush()

        practice_user_a2 = PracticeUser(
            id=uuid.uuid4(),
            user_id=user_a2.id,
            tenant_id=tenant_a.id,
            clerk_id="clerk_user_a2",
            role=UserRole.ACCOUNTANT,  # Different role
        )
        db_session.add(practice_user_a2)
        await db_session.commit()

        # Query with tenant A context (simulating second user)
        await set_tenant_context(db_session, tenant_a.id)
        result = await db_session.execute(select(XeroConnection))
        connections = result.scalars().all()

        # Second user should also see tenant A's connection
        assert len(connections) == 1
        assert connections[0].id == xero_connection_a.id


@pytest.mark.integration
class TestXeroConnectionsRLSEdgeCases:
    """Edge case tests for Xero connections RLS."""

    async def test_disconnected_connections_still_isolated(
        self,
        db_session: AsyncSession,
        tenant_a: Tenant,
        tenant_b: Tenant,
        practice_user_a: PracticeUser,
        practice_user_b: PracticeUser,
    ) -> None:
        """Disconnected connections should still be tenant-isolated."""
        # Create disconnected connection for tenant A
        disconnected_a = XeroConnection(
            id=uuid.uuid4(),
            tenant_id=tenant_a.id,
            xero_tenant_id="xero-org-disconnected",
            organization_name="Disconnected Org A",
            status=XeroConnectionStatus.DISCONNECTED,
            access_token="[REVOKED]",
            refresh_token="[REVOKED]",
            token_expires_at=datetime.now(UTC) - timedelta(days=1),
            scopes=[],
            connected_by=practice_user_a.id,
            connected_at=datetime.now(UTC) - timedelta(days=30),
        )
        db_session.add(disconnected_a)
        await db_session.commit()

        # Tenant B should not see tenant A's disconnected connection
        await set_tenant_context(db_session, tenant_b.id)
        result = await db_session.execute(select(XeroConnection))
        connections = result.scalars().all()

        assert len(connections) == 0

    async def test_needs_reauth_connections_isolated(
        self,
        db_session: AsyncSession,
        tenant_a: Tenant,
        tenant_b: Tenant,
        practice_user_a: PracticeUser,
    ) -> None:
        """Connections needing re-auth should still be tenant-isolated."""
        # Create needs_reauth connection for tenant A
        needs_reauth = XeroConnection(
            id=uuid.uuid4(),
            tenant_id=tenant_a.id,
            xero_tenant_id="xero-org-reauth",
            organization_name="Needs Reauth Org",
            status=XeroConnectionStatus.NEEDS_REAUTH,
            access_token="[EXPIRED]",
            refresh_token="[EXPIRED]",
            token_expires_at=datetime.now(UTC) - timedelta(hours=1),
            scopes=["openid"],
            connected_by=practice_user_a.id,
            connected_at=datetime.now(UTC) - timedelta(days=7),
        )
        db_session.add(needs_reauth)
        await db_session.commit()

        # Tenant A should see their needs_reauth connection
        await set_tenant_context(db_session, tenant_a.id)
        result = await db_session.execute(select(XeroConnection))
        connections = result.scalars().all()

        assert len(connections) == 1
        assert connections[0].status == XeroConnectionStatus.NEEDS_REAUTH

        # Tenant B should not see it
        await set_tenant_context(db_session, tenant_b.id)
        result = await db_session.execute(select(XeroConnection))
        connections = result.scalars().all()

        assert len(connections) == 0
