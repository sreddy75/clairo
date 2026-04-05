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
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
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


async def set_tenant_context(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    """Set the tenant context for RLS."""
    await session.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))


async def clear_tenant_context(session: AsyncSession) -> None:
    """Clear the tenant context for RLS."""
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


async def _insert_row(session: AsyncSession, table: str, values: dict) -> uuid.UUID:
    """Insert a row via raw SQL and return the id. Avoids FK/model complexity."""
    row_id = values.get("id", uuid.uuid4())
    values["id"] = row_id
    cols = ", ".join(values.keys())
    placeholders = ", ".join(f":{k}" for k in values)
    await session.execute(
        text(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"),
        values,
    )
    return row_id


async def _count_rows(session: AsyncSession, table: str) -> int:
    """Count rows visible in the current RLS context."""
    result = await session.execute(text(f"SELECT count(*) FROM {table}"))
    return result.scalar()


async def _rls_isolation_test(
    db_session: AsyncSession,
    table: str,
    tenant_1_id: uuid.UUID,
    tenant_2_id: uuid.UUID,
    row_values_1: dict,
    row_values_2: dict,
) -> None:
    """Reusable RLS isolation test: insert 2 rows for 2 tenants, verify isolation."""
    row_values_1["tenant_id"] = str(tenant_1_id)
    row_values_2["tenant_id"] = str(tenant_2_id)
    await _insert_row(db_session, table, row_values_1)
    await _insert_row(db_session, table, row_values_2)
    await db_session.commit()

    # Tenant 1 sees only their row
    await set_tenant_context(db_session, tenant_1_id)
    assert await _count_rows(db_session, table) == 1

    # Tenant 2 sees only their row
    await set_tenant_context(db_session, tenant_2_id)
    assert await _count_rows(db_session, table) == 1

    # No context sees nothing
    await clear_tenant_context(db_session)
    assert await _count_rows(db_session, table) == 0


@pytest.mark.integration
class TestTaxPlansRLS:
    """RLS tests for tax_plans table."""

    async def test_tax_plans_isolated(self, db_session: AsyncSession, tenant_1: Tenant, tenant_2: Tenant) -> None:
        # Need xero_connections for FK
        xc1 = uuid.uuid4()
        xc2 = uuid.uuid4()
        await _insert_row(db_session, "xero_connections", {
            "id": xc1, "tenant_id": str(tenant_1.id), "xero_tenant_id": "xero-1",
            "xero_tenant_name": "T1", "token_data": "{}", "status": "active",
        })
        await _insert_row(db_session, "xero_connections", {
            "id": xc2, "tenant_id": str(tenant_2.id), "xero_tenant_id": "xero-2",
            "xero_tenant_name": "T2", "token_data": "{}", "status": "active",
        })
        await _rls_isolation_test(
            db_session, "tax_plans", tenant_1.id, tenant_2.id,
            {"xero_connection_id": str(xc1), "financial_year": "2026", "entity_type": "individual", "data_source": "xero", "status": "draft"},
            {"xero_connection_id": str(xc2), "financial_year": "2026", "entity_type": "company", "data_source": "xero", "status": "draft"},
        )


@pytest.mark.integration
class TestTaxScenariosRLS:
    """RLS tests for tax_scenarios table."""

    async def test_tax_scenarios_isolated(self, db_session: AsyncSession, tenant_1: Tenant, tenant_2: Tenant) -> None:
        await _rls_isolation_test(
            db_session, "tax_scenarios", tenant_1.id, tenant_2.id,
            {"tax_plan_id": str(uuid.uuid4()), "title": "S1", "description": "d1", "impact_data": "{}", "risk_rating": "low"},
            {"tax_plan_id": str(uuid.uuid4()), "title": "S2", "description": "d2", "impact_data": "{}", "risk_rating": "low"},
        )


@pytest.mark.integration
class TestTaxPlanMessagesRLS:
    """RLS tests for tax_plan_messages table."""

    async def test_messages_isolated(self, db_session: AsyncSession, tenant_1: Tenant, tenant_2: Tenant) -> None:
        await _rls_isolation_test(
            db_session, "tax_plan_messages", tenant_1.id, tenant_2.id,
            {"tax_plan_id": str(uuid.uuid4()), "role": "user", "content": "msg1"},
            {"tax_plan_id": str(uuid.uuid4()), "role": "user", "content": "msg2"},
        )


@pytest.mark.integration
class TestTaxPlanAnalysesRLS:
    """RLS tests for tax_plan_analyses table."""

    async def test_analyses_isolated(self, db_session: AsyncSession, tenant_1: Tenant, tenant_2: Tenant) -> None:
        await _rls_isolation_test(
            db_session, "tax_plan_analyses", tenant_1.id, tenant_2.id,
            {"tax_plan_id": str(uuid.uuid4())},
            {"tax_plan_id": str(uuid.uuid4())},
        )


@pytest.mark.integration
class TestImplementationItemsRLS:
    """RLS tests for implementation_items table."""

    async def test_items_isolated(self, db_session: AsyncSession, tenant_1: Tenant, tenant_2: Tenant) -> None:
        await _rls_isolation_test(
            db_session, "implementation_items", tenant_1.id, tenant_2.id,
            {"analysis_id": str(uuid.uuid4()), "title": "Item 1"},
            {"analysis_id": str(uuid.uuid4()), "title": "Item 2"},
        )


@pytest.mark.integration
class TestTaxCodeSuggestionsRLS:
    """RLS tests for tax_code_suggestions table."""

    async def test_suggestions_isolated(self, db_session: AsyncSession, tenant_1: Tenant, tenant_2: Tenant) -> None:
        await _rls_isolation_test(
            db_session, "tax_code_suggestions", tenant_1.id, tenant_2.id,
            {"session_id": str(uuid.uuid4()), "source_type": "bank_transaction", "source_id": str(uuid.uuid4()), "line_item_index": 0, "original_tax_type": "OUTPUT"},
            {"session_id": str(uuid.uuid4()), "source_type": "bank_transaction", "source_id": str(uuid.uuid4()), "line_item_index": 0, "original_tax_type": "INPUT"},
        )


@pytest.mark.integration
class TestTaxCodeOverridesRLS:
    """RLS tests for tax_code_overrides table."""

    async def test_overrides_isolated(self, db_session: AsyncSession, tenant_1: Tenant, tenant_2: Tenant) -> None:
        now = datetime.now(UTC).isoformat()
        await _rls_isolation_test(
            db_session, "tax_code_overrides", tenant_1.id, tenant_2.id,
            {"connection_id": str(uuid.uuid4()), "source_type": "bank_transaction", "source_id": str(uuid.uuid4()), "line_item_index": 0, "original_tax_type": "OUTPUT", "override_tax_type": "INPUT", "applied_by": str(uuid.uuid4()), "applied_at": now},
            {"connection_id": str(uuid.uuid4()), "source_type": "bank_transaction", "source_id": str(uuid.uuid4()), "line_item_index": 0, "original_tax_type": "INPUT", "override_tax_type": "OUTPUT", "applied_by": str(uuid.uuid4()), "applied_at": now},
        )


@pytest.mark.integration
class TestClassificationRequestsRLS:
    """RLS tests for classification_requests table."""

    async def test_requests_isolated(self, db_session: AsyncSession, tenant_1: Tenant, tenant_2: Tenant) -> None:
        future = (datetime.now(UTC) + timedelta(days=7)).isoformat()
        await _rls_isolation_test(
            db_session, "classification_requests", tenant_1.id, tenant_2.id,
            {"connection_id": str(uuid.uuid4()), "session_id": str(uuid.uuid4()), "requested_by": str(uuid.uuid4()), "client_email": "a@test.com", "expires_at": future},
            {"connection_id": str(uuid.uuid4()), "session_id": str(uuid.uuid4()), "requested_by": str(uuid.uuid4()), "client_email": "b@test.com", "expires_at": future},
        )


@pytest.mark.integration
class TestClientClassificationsRLS:
    """RLS tests for client_classifications table."""

    async def test_classifications_isolated(self, db_session: AsyncSession, tenant_1: Tenant, tenant_2: Tenant) -> None:
        await _rls_isolation_test(
            db_session, "client_classifications", tenant_1.id, tenant_2.id,
            {"request_id": str(uuid.uuid4()), "source_type": "bank_transaction", "source_id": str(uuid.uuid4()), "line_item_index": 0, "line_amount": "100.00"},
            {"request_id": str(uuid.uuid4()), "source_type": "bank_transaction", "source_id": str(uuid.uuid4()), "line_item_index": 0, "line_amount": "200.00"},
        )


@pytest.mark.integration
class TestFeedbackSubmissionsRLS:
    """RLS tests for feedback_submissions table."""

    async def test_feedback_isolated(self, db_session: AsyncSession, tenant_1: Tenant, tenant_2: Tenant) -> None:
        await _rls_isolation_test(
            db_session, "feedback_submissions", tenant_1.id, tenant_2.id,
            {"submitter_id": str(uuid.uuid4()), "submitter_name": "User A"},
            {"submitter_id": str(uuid.uuid4()), "submitter_name": "User B"},
        )


@pytest.mark.integration
class TestPortalInvitationsRLS:
    """RLS tests for portal_invitations table."""

    async def test_invitations_isolated(self, db_session: AsyncSession, tenant_1: Tenant, tenant_2: Tenant) -> None:
        future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
        await _rls_isolation_test(
            db_session, "portal_invitations", tenant_1.id, tenant_2.id,
            {"connection_id": str(uuid.uuid4()), "email": "c1@test.com", "token_hash": "hash1" + uuid.uuid4().hex[:58], "expires_at": future, "invited_by": str(uuid.uuid4())},
            {"connection_id": str(uuid.uuid4()), "email": "c2@test.com", "token_hash": "hash2" + uuid.uuid4().hex[:58], "expires_at": future, "invited_by": str(uuid.uuid4())},
        )


@pytest.mark.integration
class TestPortalSessionsRLS:
    """RLS tests for portal_sessions table."""

    async def test_sessions_isolated(self, db_session: AsyncSession, tenant_1: Tenant, tenant_2: Tenant) -> None:
        future = (datetime.now(UTC) + timedelta(days=30)).isoformat()
        await _rls_isolation_test(
            db_session, "portal_sessions", tenant_1.id, tenant_2.id,
            {"connection_id": str(uuid.uuid4()), "refresh_token_hash": "rt1" + uuid.uuid4().hex[:61], "expires_at": future},
            {"connection_id": str(uuid.uuid4()), "refresh_token_hash": "rt2" + uuid.uuid4().hex[:61], "expires_at": future},
        )


@pytest.mark.integration
class TestBulkRequestsRLS:
    """RLS tests for bulk_requests table."""

    async def test_bulk_requests_isolated(self, db_session: AsyncSession, tenant_1: Tenant, tenant_2: Tenant) -> None:
        await _rls_isolation_test(
            db_session, "bulk_requests", tenant_1.id, tenant_2.id,
            {"title": "Batch 1", "total_clients": 10, "created_by": str(uuid.uuid4())},
            {"title": "Batch 2", "total_clients": 5, "created_by": str(uuid.uuid4())},
        )


@pytest.mark.integration
class TestDocumentRequestsRLS:
    """RLS tests for document_requests table."""

    async def test_document_requests_isolated(self, db_session: AsyncSession, tenant_1: Tenant, tenant_2: Tenant) -> None:
        await _rls_isolation_test(
            db_session, "document_requests", tenant_1.id, tenant_2.id,
            {"connection_id": str(uuid.uuid4()), "title": "Doc 1", "description": "d", "recipient_email": "a@t.com", "created_by": str(uuid.uuid4())},
            {"connection_id": str(uuid.uuid4()), "title": "Doc 2", "description": "d", "recipient_email": "b@t.com", "created_by": str(uuid.uuid4())},
        )


@pytest.mark.integration
class TestPortalDocumentsRLS:
    """RLS tests for portal_documents table."""

    async def test_portal_documents_isolated(self, db_session: AsyncSession, tenant_1: Tenant, tenant_2: Tenant) -> None:
        await _rls_isolation_test(
            db_session, "portal_documents", tenant_1.id, tenant_2.id,
            {"connection_id": str(uuid.uuid4()), "filename": "f1.pdf", "original_filename": "f1.pdf", "content_type": "application/pdf", "file_size": 1024, "s3_bucket": "test", "s3_key": "k1"},
            {"connection_id": str(uuid.uuid4()), "filename": "f2.pdf", "original_filename": "f2.pdf", "content_type": "application/pdf", "file_size": 2048, "s3_bucket": "test", "s3_key": "k2"},
        )
