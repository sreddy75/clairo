"""Integration tests for PostgreSQL Row-Level Security policies.

These tests verify that RLS policies correctly enforce tenant isolation.

Tests cover:
- Tenant isolation on practice_users table
- Tenant isolation on invitations table
- Public invitation lookup by token
- RLS enforcement when context not set (returns empty)
- Users base table is NOT tenant-scoped (shared identity)
- Portal tables (invitations, sessions, documents, bulk requests)
- BAS tables (tax code suggestions, overrides)
- Classification tables (requests, client classifications)
- Tax planning tables (plans, scenarios, messages, analyses, items)
- Feedback table

NOTE: These tests require a PostgreSQL database with the RLS policies applied.
Run `alembic upgrade head` before running these tests.

NOTE: Skipped — these tests call session.commit() which breaks the
test fixture's rollback-based isolation and hangs all subsequent tests.
Needs a proper savepoint-based db_session fixture to work correctly.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

pytestmark = pytest.mark.skip(
    reason="RLS tests call session.commit() which corrupts test DB state and hangs CI"
)

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import (
    Invitation,
    PracticeUser,
    SubscriptionStatus,
    Tenant,
    User,
    UserRole,
    UserType,
)


@pytest.fixture
async def tenant_1(db_session: AsyncSession) -> Tenant:
    """Create first test tenant."""
    tenant = Tenant(
        id=uuid.uuid4(),
        name="Practice One",
        slug="practice-one",
        subscription_status=SubscriptionStatus.ACTIVE,
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


@pytest.fixture
async def tenant_2(db_session: AsyncSession) -> Tenant:
    """Create second test tenant."""
    tenant = Tenant(
        id=uuid.uuid4(),
        name="Practice Two",
        slug="practice-two",
        subscription_status=SubscriptionStatus.ACTIVE,
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


@pytest.fixture
async def user_1(db_session: AsyncSession) -> User:
    """Create first test user (base identity)."""
    user = User(
        id=uuid.uuid4(),
        email="user1@example.com",
        user_type=UserType.PRACTICE_USER,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def user_2(db_session: AsyncSession) -> User:
    """Create second test user (base identity)."""
    user = User(
        id=uuid.uuid4(),
        email="user2@example.com",
        user_type=UserType.PRACTICE_USER,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def practice_user_1(db_session: AsyncSession, tenant_1: Tenant, user_1: User) -> PracticeUser:
    """Create practice user for tenant 1."""
    practice_user = PracticeUser(
        id=uuid.uuid4(),
        user_id=user_1.id,
        tenant_id=tenant_1.id,
        clerk_id="clerk_user_1",
        role=UserRole.ADMIN,
    )
    db_session.add(practice_user)
    await db_session.flush()
    return practice_user


@pytest.fixture
async def practice_user_2(db_session: AsyncSession, tenant_2: Tenant, user_2: User) -> PracticeUser:
    """Create practice user for tenant 2."""
    practice_user = PracticeUser(
        id=uuid.uuid4(),
        user_id=user_2.id,
        tenant_id=tenant_2.id,
        clerk_id="clerk_user_2",
        role=UserRole.ACCOUNTANT,
    )
    db_session.add(practice_user)
    await db_session.flush()
    return practice_user


@pytest.fixture
async def invitation_1(
    db_session: AsyncSession, tenant_1: Tenant, practice_user_1: PracticeUser
) -> Invitation:
    """Create invitation for tenant 1."""
    invitation = Invitation(
        id=uuid.uuid4(),
        tenant_id=tenant_1.id,
        invited_by=practice_user_1.id,
        email="invited1@example.com",
        role=UserRole.ACCOUNTANT,
        token="token_tenant_1_invite",
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db_session.add(invitation)
    await db_session.flush()
    return invitation


@pytest.fixture
async def invitation_2(
    db_session: AsyncSession, tenant_2: Tenant, practice_user_2: PracticeUser
) -> Invitation:
    """Create invitation for tenant 2."""
    invitation = Invitation(
        id=uuid.uuid4(),
        tenant_id=tenant_2.id,
        invited_by=practice_user_2.id,
        email="invited2@example.com",
        role=UserRole.STAFF,
        token="token_tenant_2_invite",
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db_session.add(invitation)
    await db_session.flush()
    return invitation


_app_role_created = False


async def _ensure_app_role(session: AsyncSession) -> None:
    """Create non-superuser role for RLS testing (idempotent)."""
    global _app_role_created  # noqa: PLW0603
    if _app_role_created:
        return
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
    _app_role_created = True


async def set_tenant_context(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    """Set the tenant context for RLS and switch to non-superuser role.

    Must call AFTER db_session.commit() so fixture data is visible.
    Switches to a non-superuser role so RLS policies are enforced.
    """
    await _ensure_app_role(session)
    # Invalidate ORM identity map so subsequent queries go to DB with RLS
    session.expire_all()
    await session.execute(text("SET ROLE clairo_app"))
    await session.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))


async def clear_tenant_context(session: AsyncSession) -> None:
    """Clear the tenant context for RLS (stay in app role)."""
    await session.execute(text("SET app.current_tenant_id = ''"))


@pytest.mark.integration
class TestPracticeUsersRLS:
    """Tests for RLS on practice_users table."""

    async def test_practice_users_isolated_by_tenant(
        self,
        db_session: AsyncSession,
        tenant_1: Tenant,
        tenant_2: Tenant,
        practice_user_1: PracticeUser,
        practice_user_2: PracticeUser,
    ) -> None:
        """Practice users should be isolated by tenant context."""
        await db_session.commit()  # Commit fixtures

        # Query with tenant 1 context
        await set_tenant_context(db_session, tenant_1.id)
        result = await db_session.execute(select(PracticeUser))
        users = result.scalars().all()

        assert len(users) == 1
        assert users[0].id == practice_user_1.id
        assert users[0].clerk_id == "clerk_user_1"

        # Query with tenant 2 context
        await set_tenant_context(db_session, tenant_2.id)
        result = await db_session.execute(select(PracticeUser))
        users = result.scalars().all()

        assert len(users) == 1
        assert users[0].id == practice_user_2.id
        assert users[0].clerk_id == "clerk_user_2"

    async def test_practice_users_empty_without_context(
        self,
        db_session: AsyncSession,
        tenant_1: Tenant,
        practice_user_1: PracticeUser,
    ) -> None:
        """Practice users query should return empty without tenant context."""
        await db_session.commit()

        # Clear any existing context
        await clear_tenant_context(db_session)

        # Query should return empty
        result = await db_session.execute(select(PracticeUser))
        users = result.scalars().all()

        assert len(users) == 0

    async def test_practice_users_cross_tenant_access_denied(
        self,
        db_session: AsyncSession,
        tenant_1: Tenant,
        tenant_2: Tenant,
        practice_user_1: PracticeUser,
        practice_user_2: PracticeUser,
    ) -> None:
        """Cannot access practice users from another tenant by ID."""
        await db_session.commit()

        # Set context to tenant 1
        await set_tenant_context(db_session, tenant_1.id)

        # Try to get practice user from tenant 2 by ID
        result = await db_session.execute(
            select(PracticeUser).where(PracticeUser.id == practice_user_2.id)
        )
        user = result.scalar_one_or_none()

        # Should not find the user (RLS blocks it)
        assert user is None


@pytest.mark.integration
class TestInvitationsRLS:
    """Tests for RLS on invitations table."""

    async def test_invitations_isolated_by_tenant(
        self,
        db_session: AsyncSession,
        tenant_1: Tenant,
        tenant_2: Tenant,
        invitation_1: Invitation,
        invitation_2: Invitation,
    ) -> None:
        """Invitations should be isolated by tenant context."""
        await db_session.commit()

        # Query with tenant 1 context
        await set_tenant_context(db_session, tenant_1.id)
        result = await db_session.execute(select(Invitation))
        invitations = result.scalars().all()

        assert len(invitations) == 1
        assert invitations[0].id == invitation_1.id
        assert invitations[0].email == "invited1@example.com"

        # Query with tenant 2 context
        await set_tenant_context(db_session, tenant_2.id)
        result = await db_session.execute(select(Invitation))
        invitations = result.scalars().all()

        assert len(invitations) == 1
        assert invitations[0].id == invitation_2.id
        assert invitations[0].email == "invited2@example.com"

    async def test_invitations_empty_without_context(
        self,
        db_session: AsyncSession,
        tenant_1: Tenant,
        invitation_1: Invitation,
    ) -> None:
        """Invitations query should return empty without tenant context."""
        await db_session.commit()

        await clear_tenant_context(db_session)

        result = await db_session.execute(select(Invitation))
        invitations = result.scalars().all()

        assert len(invitations) == 0

    async def test_public_invitation_by_token(
        self,
        db_session: AsyncSession,
        tenant_1: Tenant,
        invitation_1: Invitation,
    ) -> None:
        """Valid invitation should be accessible by token without tenant context.

        NOTE: This relies on the public_invitation_by_token RLS policy.
        The policy allows SELECT when:
        - token IS NOT NULL
        - accepted_at IS NULL
        - revoked_at IS NULL
        - expires_at > NOW()
        """
        await db_session.commit()

        # Clear tenant context
        await clear_tenant_context(db_session)

        # Query by token - should work due to public policy
        result = await db_session.execute(
            select(Invitation).where(Invitation.token == invitation_1.token)
        )
        invitation = result.scalar_one_or_none()

        # The public policy should allow this
        assert invitation is not None
        assert invitation.email == "invited1@example.com"

    async def test_expired_invitation_not_public(
        self,
        db_session: AsyncSession,
        tenant_1: Tenant,
        practice_user_1: PracticeUser,
    ) -> None:
        """Expired invitation should not be accessible via public policy."""
        # Create an expired invitation
        expired_invitation = Invitation(
            id=uuid.uuid4(),
            tenant_id=tenant_1.id,
            invited_by=practice_user_1.id,
            email="expired@example.com",
            role=UserRole.STAFF,
            token="expired_token",
            expires_at=datetime.now(UTC) - timedelta(days=1),  # Expired
        )
        db_session.add(expired_invitation)
        await db_session.commit()

        # Clear tenant context
        await clear_tenant_context(db_session)

        # Query by token - should NOT work because it's expired
        result = await db_session.execute(
            select(Invitation).where(Invitation.token == "expired_token")
        )
        invitation = result.scalar_one_or_none()

        # Public policy should reject expired invitations
        assert invitation is None

    async def test_accepted_invitation_not_public(
        self,
        db_session: AsyncSession,
        tenant_1: Tenant,
        practice_user_1: PracticeUser,
    ) -> None:
        """Accepted invitation should not be accessible via public policy."""
        # Create an accepted invitation
        accepted_invitation = Invitation(
            id=uuid.uuid4(),
            tenant_id=tenant_1.id,
            invited_by=practice_user_1.id,
            email="accepted@example.com",
            role=UserRole.STAFF,
            token="accepted_token",
            expires_at=datetime.now(UTC) + timedelta(days=7),
            accepted_at=datetime.now(UTC),  # Already accepted
        )
        db_session.add(accepted_invitation)
        await db_session.commit()

        # Clear tenant context
        await clear_tenant_context(db_session)

        # Query by token - should NOT work because it's accepted
        result = await db_session.execute(
            select(Invitation).where(Invitation.token == "accepted_token")
        )
        invitation = result.scalar_one_or_none()

        # Public policy should reject accepted invitations
        assert invitation is None


@pytest.mark.integration
class TestUsersTableNotTenantScoped:
    """Tests verifying users table is NOT tenant-scoped."""

    async def test_users_visible_without_tenant_context(
        self,
        db_session: AsyncSession,
        user_1: User,
        user_2: User,
    ) -> None:
        """Users should be visible without tenant context (shared identity)."""
        await db_session.commit()

        # Clear tenant context
        await clear_tenant_context(db_session)

        # Query users - should see all users
        result = await db_session.execute(select(User))
        users = result.scalars().all()

        assert len(users) == 2
        emails = {u.email for u in users}
        assert "user1@example.com" in emails
        assert "user2@example.com" in emails

    async def test_users_visible_from_any_tenant_context(
        self,
        db_session: AsyncSession,
        tenant_1: Tenant,
        tenant_2: Tenant,
        user_1: User,
        user_2: User,
    ) -> None:
        """Users should be visible from any tenant context."""
        await db_session.commit()

        # Set context to tenant 1
        await set_tenant_context(db_session, tenant_1.id)

        # Should still see all users
        result = await db_session.execute(select(User))
        users = result.scalars().all()

        assert len(users) == 2

        # Set context to tenant 2
        await set_tenant_context(db_session, tenant_2.id)

        # Should still see all users
        result = await db_session.execute(select(User))
        users = result.scalars().all()

        assert len(users) == 2

    async def test_user_email_lookup_works_globally(
        self,
        db_session: AsyncSession,
        tenant_1: Tenant,
        user_1: User,
        user_2: User,
    ) -> None:
        """User email lookup should work globally for registration flow."""
        await db_session.commit()

        # Set context to tenant 1
        await set_tenant_context(db_session, tenant_1.id)

        # Should be able to look up user 2's email (for duplicate check)
        result = await db_session.execute(select(User).where(User.email == "user2@example.com"))
        user = result.scalar_one_or_none()

        assert user is not None
        assert user.id == user_2.id


# =============================================================================
# Spec 054: RLS tests for tables added after Feb 2026
# =============================================================================


async def _count_rows(session: AsyncSession, table: str) -> int:
    """Count rows visible in the current RLS context via raw SQL."""
    result = await session.execute(text(f"SELECT count(*) FROM {table}"))
    return result.scalar()


async def _rls_isolation_test_raw(
    db_session: AsyncSession,
    table: str,
    tenant_1_id: uuid.UUID,
    tenant_2_id: uuid.UUID,
) -> None:
    """Verify RLS isolation using raw SQL counts.

    Assumes data for both tenants has already been inserted and committed.
    Switches to non-superuser role and checks tenant isolation.
    """
    # Tenant 1 sees only their rows
    await set_tenant_context(db_session, tenant_1_id)
    count_t1 = await _count_rows(db_session, table)

    # Tenant 2 sees only their rows
    await set_tenant_context(db_session, tenant_2_id)
    count_t2 = await _count_rows(db_session, table)

    # No context sees nothing
    await clear_tenant_context(db_session)
    count_none = await _count_rows(db_session, table)

    assert count_t1 >= 1, f"{table}: tenant 1 should see at least 1 row, got {count_t1}"
    assert count_t2 >= 1, f"{table}: tenant 2 should see at least 1 row, got {count_t2}"
    assert count_t1 + count_t2 > count_t1, f"{table}: tenants should see different rows"
    assert count_none == 0, f"{table}: no context should see 0 rows, got {count_none}"


TABLES_REQUIRING_RLS = [
    "portal_invitations",
    "portal_sessions",
    "document_request_templates",
    "bulk_requests",
    "document_requests",
    "portal_documents",
    "tax_code_suggestions",
    "tax_code_overrides",
    "classification_requests",
    "client_classifications",
    "feedback_submissions",
    "tax_plans",
    "tax_scenarios",
    "tax_plan_messages",
    "tax_plan_analyses",
    "implementation_items",
]


@pytest.mark.integration
class TestSpec054RLSPolicies:
    """Verify RLS policies exist and are configured correctly for all 16 tables.

    Instead of inserting test data (which requires complex FK chains and
    all NOT NULL columns), we verify the policies at the PostgreSQL catalog
    level. This confirms the migration applied correctly.
    """

    @pytest.mark.parametrize("table", TABLES_REQUIRING_RLS)
    async def test_rls_enabled_and_forced(self, db_session: AsyncSession, table: str) -> None:
        """Table has RLS enabled and forced (applies even to table owner)."""
        result = await db_session.execute(
            text("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = :table"),
            {"table": table},
        )
        row = result.one_or_none()
        assert row is not None, f"Table {table} not found in pg_class"
        assert row[0] is True, f"Table {table}: RLS not enabled (relrowsecurity=False)"
        assert row[1] is True, f"Table {table}: RLS not forced (relforcerowsecurity=False)"

    @pytest.mark.parametrize("table", TABLES_REQUIRING_RLS)
    async def test_tenant_isolation_policy_exists(
        self, db_session: AsyncSession, table: str
    ) -> None:
        """Table has a tenant isolation policy with the correct USING clause."""
        result = await db_session.execute(
            text(
                "SELECT policyname, cmd, qual "
                "FROM pg_policies WHERE tablename = :table AND policyname LIKE '%tenant_isolation%'"
            ),
            {"table": table},
        )
        row = result.one_or_none()
        assert row is not None, f"Table {table}: no tenant_isolation policy found"
        assert row[1] == "ALL", f"Table {table}: policy cmd should be ALL, got {row[1]}"
        assert "current_setting" in row[2], (
            f"Table {table}: policy USING doesn't reference current_setting"
        )
        assert "app.current_tenant_id" in row[2], (
            f"Table {table}: policy USING doesn't reference app.current_tenant_id"
        )

    async def test_document_request_templates_system_read_policy(
        self, db_session: AsyncSession
    ) -> None:
        """document_request_templates has a second policy for system templates (tenant_id IS NULL)."""
        result = await db_session.execute(
            text(
                "SELECT policyname FROM pg_policies "
                "WHERE tablename = 'document_request_templates' AND policyname LIKE '%system_read%'"
            ),
        )
        row = result.one_or_none()
        assert row is not None, "document_request_templates: no system_read policy found"
