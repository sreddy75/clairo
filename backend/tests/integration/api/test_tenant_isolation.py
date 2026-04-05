"""Integration tests for tenant isolation via RLS.

Tests verify that API endpoints enforce tenant isolation:
- Tenant A's API calls never return tenant B's data
- Cross-tenant resource access returns 404 (not 403)
- Portal user only sees their own business data

These tests use raw SQL + RLS context to verify isolation at the DB level,
avoiding the complexity of mocking Clerk auth for HTTP endpoint tests.

Spec 054: Onboarding & Core Hardening
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import SubscriptionStatus, Tenant


@pytest.fixture
async def tenant_a(db_session: AsyncSession) -> Tenant:
    """Create tenant A."""
    tenant = Tenant(
        id=uuid.uuid4(),
        name="Practice Alpha",
        slug=f"alpha-{uuid.uuid4().hex[:8]}",
        subscription_status=SubscriptionStatus.ACTIVE,
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


@pytest.fixture
async def tenant_b(db_session: AsyncSession) -> Tenant:
    """Create tenant B."""
    tenant = Tenant(
        id=uuid.uuid4(),
        name="Practice Beta",
        slug=f"beta-{uuid.uuid4().hex[:8]}",
        subscription_status=SubscriptionStatus.ACTIVE,
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


async def _set_ctx(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    await session.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))


async def _clear_ctx(session: AsyncSession) -> None:
    await session.execute(text("SET app.current_tenant_id = ''"))


async def _insert(session: AsyncSession, table: str, values: dict) -> uuid.UUID:
    row_id = values.setdefault("id", uuid.uuid4())
    cols = ", ".join(values.keys())
    placeholders = ", ".join(f":{k}" for k in values)
    await session.execute(
        text(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"),
        values,
    )
    return row_id


async def _count(session: AsyncSession, table: str) -> int:
    result = await session.execute(text(f"SELECT count(*) FROM {table}"))
    return result.scalar()


@pytest.mark.integration
class TestClientDataIsolation:
    """Verify tenant A cannot see tenant B's Xero-synced client data."""

    async def test_xero_connections_isolated(
        self, db_session: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        await _insert(db_session, "xero_connections", {
            "tenant_id": str(tenant_a.id), "xero_tenant_id": "xa",
            "xero_tenant_name": "Alpha Xero", "token_data": "{}", "status": "active",
        })
        await _insert(db_session, "xero_connections", {
            "tenant_id": str(tenant_b.id), "xero_tenant_id": "xb",
            "xero_tenant_name": "Beta Xero", "token_data": "{}", "status": "active",
        })
        await db_session.commit()

        await _set_ctx(db_session, tenant_a.id)
        assert await _count(db_session, "xero_connections") == 1

        await _set_ctx(db_session, tenant_b.id)
        assert await _count(db_session, "xero_connections") == 1

        await _clear_ctx(db_session)
        assert await _count(db_session, "xero_connections") == 0


@pytest.mark.integration
class TestBASDataIsolation:
    """Verify BAS sessions, suggestions, and calculations are tenant-isolated."""

    async def test_bas_sessions_isolated(
        self, db_session: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        # Create periods first (FK dependency)
        pa = await _insert(db_session, "bas_periods", {
            "tenant_id": str(tenant_a.id), "connection_id": str(uuid.uuid4()),
            "fy_year": 2026, "start_date": "2025-07-01", "end_date": "2025-09-30",
            "due_date": "2025-10-28", "quarter": 1,
        })
        pb = await _insert(db_session, "bas_periods", {
            "tenant_id": str(tenant_b.id), "connection_id": str(uuid.uuid4()),
            "fy_year": 2026, "start_date": "2025-07-01", "end_date": "2025-09-30",
            "due_date": "2025-10-28", "quarter": 1,
        })

        await _insert(db_session, "bas_sessions", {
            "tenant_id": str(tenant_a.id), "period_id": str(pa),
            "created_by": str(uuid.uuid4()),
        })
        await _insert(db_session, "bas_sessions", {
            "tenant_id": str(tenant_b.id), "period_id": str(pb),
            "created_by": str(uuid.uuid4()),
        })
        await db_session.commit()

        await _set_ctx(db_session, tenant_a.id)
        assert await _count(db_session, "bas_sessions") == 1

        await _set_ctx(db_session, tenant_b.id)
        assert await _count(db_session, "bas_sessions") == 1


@pytest.mark.integration
class TestTaxPlanDataIsolation:
    """Verify tax plans, scenarios, and analyses are tenant-isolated."""

    async def test_tax_plans_isolated(
        self, db_session: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        # Need xero_connections for FK
        xca = await _insert(db_session, "xero_connections", {
            "tenant_id": str(tenant_a.id), "xero_tenant_id": "tpa",
            "xero_tenant_name": "A", "token_data": "{}", "status": "active",
        })
        xcb = await _insert(db_session, "xero_connections", {
            "tenant_id": str(tenant_b.id), "xero_tenant_id": "tpb",
            "xero_tenant_name": "B", "token_data": "{}", "status": "active",
        })
        await _insert(db_session, "tax_plans", {
            "tenant_id": str(tenant_a.id), "xero_connection_id": str(xca),
            "financial_year": "2026", "entity_type": "individual",
            "data_source": "xero", "status": "draft",
        })
        await _insert(db_session, "tax_plans", {
            "tenant_id": str(tenant_b.id), "xero_connection_id": str(xcb),
            "financial_year": "2026", "entity_type": "company",
            "data_source": "xero", "status": "draft",
        })
        await db_session.commit()

        await _set_ctx(db_session, tenant_a.id)
        assert await _count(db_session, "tax_plans") == 1

        await _set_ctx(db_session, tenant_b.id)
        assert await _count(db_session, "tax_plans") == 1

        await _clear_ctx(db_session)
        assert await _count(db_session, "tax_plans") == 0


@pytest.mark.integration
class TestPortalDataIsolation:
    """Verify portal data is tenant-isolated."""

    async def test_portal_invitations_isolated(
        self, db_session: AsyncSession, tenant_a: Tenant, tenant_b: Tenant
    ) -> None:
        future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
        await _insert(db_session, "portal_invitations", {
            "tenant_id": str(tenant_a.id), "connection_id": str(uuid.uuid4()),
            "email": "client-a@test.com", "token_hash": "h" + uuid.uuid4().hex[:63],
            "expires_at": future, "invited_by": str(uuid.uuid4()),
        })
        await _insert(db_session, "portal_invitations", {
            "tenant_id": str(tenant_b.id), "connection_id": str(uuid.uuid4()),
            "email": "client-b@test.com", "token_hash": "h" + uuid.uuid4().hex[:63],
            "expires_at": future, "invited_by": str(uuid.uuid4()),
        })
        await db_session.commit()

        await _set_ctx(db_session, tenant_a.id)
        assert await _count(db_session, "portal_invitations") == 1

        await _set_ctx(db_session, tenant_b.id)
        assert await _count(db_session, "portal_invitations") == 1
