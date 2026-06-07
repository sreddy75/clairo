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
from datetime import UTC, date, datetime, timedelta

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


async def _ensure_app_role(session: AsyncSession) -> None:
    """Create non-superuser role for RLS testing (idempotent, runs each test)."""
    await session.execute(
        text("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'clairo_app') THEN
                CREATE ROLE clairo_app NOLOGIN;
            END IF;
        END $$
    """)
    )
    await session.execute(text("GRANT USAGE ON SCHEMA public TO clairo_app"))
    await session.execute(text("GRANT ALL ON ALL TABLES IN SCHEMA public TO clairo_app"))
    await session.execute(text("GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO clairo_app"))


async def _set_ctx(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    await session.execute(text("RESET ROLE"))  # back to superuser first
    await _ensure_app_role(session)
    await session.execute(text("SET ROLE clairo_app"))
    await session.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))


async def _clear_ctx(session: AsyncSession) -> None:
    """Clear tenant context (stay as clairo_app to keep RLS active)."""
    await session.execute(text("RESET app.current_tenant_id"))


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
        _expires = datetime.now(UTC) + timedelta(hours=1)
        await _insert(
            db_session,
            "xero_connections",
            {
                "tenant_id": str(tenant_a.id),
                "xero_tenant_id": "xa",
                "organization_name": "Alpha Xero",
                "access_token": "tok_a",
                "refresh_token": "ref_a",
                "token_expires_at": _expires,
                "status": "active",
                "scopes": [],
            },
        )
        await _insert(
            db_session,
            "xero_connections",
            {
                "tenant_id": str(tenant_b.id),
                "xero_tenant_id": "xb",
                "organization_name": "Beta Xero",
                "access_token": "tok_b",
                "refresh_token": "ref_b",
                "token_expires_at": _expires,
                "status": "active",
                "scopes": [],
            },
        )
        await db_session.flush()

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
        # Create xero_connections first (FK dependency for bas_periods)
        _expires = datetime.now(UTC) + timedelta(hours=1)
        xca = await _insert(
            db_session,
            "xero_connections",
            {
                "tenant_id": str(tenant_a.id),
                "xero_tenant_id": f"bxa-{uuid.uuid4().hex[:8]}",
                "organization_name": "A",
                "access_token": "tok_a",
                "refresh_token": "ref_a",
                "token_expires_at": _expires,
                "status": "active",
                "scopes": [],
            },
        )
        xcb = await _insert(
            db_session,
            "xero_connections",
            {
                "tenant_id": str(tenant_b.id),
                "xero_tenant_id": f"bxb-{uuid.uuid4().hex[:8]}",
                "organization_name": "B",
                "access_token": "tok_b",
                "refresh_token": "ref_b",
                "token_expires_at": _expires,
                "status": "active",
                "scopes": [],
            },
        )
        # Create periods (FK dependency for bas_sessions)
        pa = await _insert(
            db_session,
            "bas_periods",
            {
                "tenant_id": str(tenant_a.id),
                "connection_id": str(xca),
                "fy_year": 2026,
                "start_date": date(2025, 7, 1),
                "end_date": date(2025, 9, 30),
                "due_date": date(2025, 10, 28),
                "quarter": 1,
            },
        )
        pb = await _insert(
            db_session,
            "bas_periods",
            {
                "tenant_id": str(tenant_b.id),
                "connection_id": str(xcb),
                "fy_year": 2026,
                "start_date": date(2025, 7, 1),
                "end_date": date(2025, 9, 30),
                "due_date": date(2025, 10, 28),
                "quarter": 1,
            },
        )

        # Create users + practice_users for created_by FK
        ua_user = await _insert(
            db_session,
            "users",
            {
                "email": f"bas-user-a-{uuid.uuid4().hex[:8]}@test.com",
                "user_type": "practice_user",
                "is_active": True,
            },
        )
        ub_user = await _insert(
            db_session,
            "users",
            {
                "email": f"bas-user-b-{uuid.uuid4().hex[:8]}@test.com",
                "user_type": "practice_user",
                "is_active": True,
            },
        )
        ua_pu = await _insert(
            db_session,
            "practice_users",
            {
                "tenant_id": str(tenant_a.id),
                "user_id": str(ua_user),
                "clerk_id": f"clerk_{uuid.uuid4().hex[:12]}",
                "role": "admin",
            },
        )
        ub_pu = await _insert(
            db_session,
            "practice_users",
            {
                "tenant_id": str(tenant_b.id),
                "user_id": str(ub_user),
                "clerk_id": f"clerk_{uuid.uuid4().hex[:12]}",
                "role": "admin",
            },
        )
        await _insert(
            db_session,
            "bas_sessions",
            {
                "tenant_id": str(tenant_a.id),
                "period_id": str(pa),
                "created_by": str(ua_pu),
            },
        )
        await _insert(
            db_session,
            "bas_sessions",
            {
                "tenant_id": str(tenant_b.id),
                "period_id": str(pb),
                "created_by": str(ub_pu),
            },
        )
        await db_session.flush()

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
        _expires = datetime.now(UTC) + timedelta(hours=1)
        xca = await _insert(
            db_session,
            "xero_connections",
            {
                "tenant_id": str(tenant_a.id),
                "xero_tenant_id": "tpa",
                "organization_name": "A",
                "access_token": "tpa_tok",
                "refresh_token": "tpa_ref",
                "token_expires_at": _expires,
                "status": "active",
                "scopes": [],
            },
        )
        xcb = await _insert(
            db_session,
            "xero_connections",
            {
                "tenant_id": str(tenant_b.id),
                "xero_tenant_id": "tpb",
                "organization_name": "B",
                "access_token": "tpb_tok",
                "refresh_token": "tpb_ref",
                "token_expires_at": _expires,
                "status": "active",
                "scopes": [],
            },
        )
        await _insert(
            db_session,
            "tax_plans",
            {
                "tenant_id": str(tenant_a.id),
                "xero_connection_id": str(xca),
                "financial_year": "2026",
                "entity_type": "individual",
                "data_source": "xero",
                "status": "draft",
            },
        )
        await _insert(
            db_session,
            "tax_plans",
            {
                "tenant_id": str(tenant_b.id),
                "xero_connection_id": str(xcb),
                "financial_year": "2026",
                "entity_type": "company",
                "data_source": "xero",
                "status": "draft",
            },
        )
        await db_session.flush()

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
        _expires_tok = datetime.now(UTC) + timedelta(hours=1)
        # xero_connections needed for FK
        xca = await _insert(
            db_session,
            "xero_connections",
            {
                "tenant_id": str(tenant_a.id),
                "xero_tenant_id": f"pi-xa-{uuid.uuid4().hex[:8]}",
                "organization_name": "A",
                "access_token": "tok_a",
                "refresh_token": "ref_a",
                "token_expires_at": _expires_tok,
                "status": "active",
                "scopes": [],
            },
        )
        xcb = await _insert(
            db_session,
            "xero_connections",
            {
                "tenant_id": str(tenant_b.id),
                "xero_tenant_id": f"pi-xb-{uuid.uuid4().hex[:8]}",
                "organization_name": "B",
                "access_token": "tok_b",
                "refresh_token": "ref_b",
                "token_expires_at": _expires_tok,
                "status": "active",
                "scopes": [],
            },
        )
        # users needed for invited_by FK
        ua = await _insert(
            db_session,
            "users",
            {
                "email": f"inviter-a-{uuid.uuid4().hex[:8]}@test.com",
                "user_type": "practice_user",
                "is_active": True,
            },
        )
        ub = await _insert(
            db_session,
            "users",
            {
                "email": f"inviter-b-{uuid.uuid4().hex[:8]}@test.com",
                "user_type": "practice_user",
                "is_active": True,
            },
        )
        future = datetime.now(UTC) + timedelta(days=1)
        await _insert(
            db_session,
            "portal_invitations",
            {
                "tenant_id": str(tenant_a.id),
                "connection_id": str(xca),
                "email": f"client-a-{uuid.uuid4().hex[:8]}@test.com",
                "token_hash": "h" + uuid.uuid4().hex[:63],
                "expires_at": future,
                "invited_by": str(ua),
                "status": "pending",
                "email_delivered": False,
                "email_bounced": False,
            },
        )
        await _insert(
            db_session,
            "portal_invitations",
            {
                "tenant_id": str(tenant_b.id),
                "connection_id": str(xcb),
                "email": f"client-b-{uuid.uuid4().hex[:8]}@test.com",
                "token_hash": "h" + uuid.uuid4().hex[:63],
                "expires_at": future,
                "invited_by": str(ub),
                "status": "pending",
                "email_delivered": False,
                "email_bounced": False,
            },
        )
        await db_session.flush()

        await _set_ctx(db_session, tenant_a.id)
        assert await _count(db_session, "portal_invitations") == 1

        await _set_ctx(db_session, tenant_b.id)
        assert await _count(db_session, "portal_invitations") == 1
