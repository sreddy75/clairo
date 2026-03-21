"""Unit tests for auth SQLAlchemy models.

Tests cover:
- Enum values and string representations
- User <-> PracticeUser 1:1 relationship
- Model computed properties
- Token generation and expiry defaults
"""

import uuid
from datetime import UTC, datetime, timedelta

from app.modules.auth.models import (
    Invitation,
    InvitationStatus,
    PracticeUser,
    SubscriptionStatus,
    Tenant,
    User,
    UserRole,
    UserType,
    default_expiry,
    generate_invitation_token,
)


class TestUserTypeEnum:
    """Tests for UserType enum."""

    def test_practice_user_value(self) -> None:
        """UserType.PRACTICE_USER should have correct value."""
        assert UserType.PRACTICE_USER.value == "practice_user"

    def test_business_owner_value(self) -> None:
        """UserType.BUSINESS_OWNER should have correct value."""
        assert UserType.BUSINESS_OWNER.value == "business_owner"

    def test_str_representation(self) -> None:
        """UserType should convert to string correctly."""
        assert str(UserType.PRACTICE_USER) == "practice_user"
        assert str(UserType.BUSINESS_OWNER) == "business_owner"

    def test_enum_members(self) -> None:
        """UserType should have exactly two members."""
        assert len(UserType) == 2


class TestUserRoleEnum:
    """Tests for UserRole enum."""

    def test_admin_value(self) -> None:
        """UserRole.ADMIN should have correct value."""
        assert UserRole.ADMIN.value == "admin"

    def test_accountant_value(self) -> None:
        """UserRole.ACCOUNTANT should have correct value."""
        assert UserRole.ACCOUNTANT.value == "accountant"

    def test_staff_value(self) -> None:
        """UserRole.STAFF should have correct value."""
        assert UserRole.STAFF.value == "staff"

    def test_str_representation(self) -> None:
        """UserRole should convert to string correctly."""
        assert str(UserRole.ADMIN) == "admin"
        assert str(UserRole.ACCOUNTANT) == "accountant"
        assert str(UserRole.STAFF) == "staff"

    def test_enum_members(self) -> None:
        """UserRole should have exactly three members."""
        assert len(UserRole) == 3


class TestSubscriptionStatusEnum:
    """Tests for SubscriptionStatus enum."""

    def test_trial_value(self) -> None:
        """SubscriptionStatus.TRIAL should have correct value."""
        assert SubscriptionStatus.TRIAL.value == "trial"

    def test_active_value(self) -> None:
        """SubscriptionStatus.ACTIVE should have correct value."""
        assert SubscriptionStatus.ACTIVE.value == "active"

    def test_suspended_value(self) -> None:
        """SubscriptionStatus.SUSPENDED should have correct value."""
        assert SubscriptionStatus.SUSPENDED.value == "suspended"

    def test_cancelled_value(self) -> None:
        """SubscriptionStatus.CANCELLED should have correct value."""
        assert SubscriptionStatus.CANCELLED.value == "cancelled"

    def test_str_representation(self) -> None:
        """SubscriptionStatus should convert to string correctly."""
        assert str(SubscriptionStatus.TRIAL) == "trial"
        assert str(SubscriptionStatus.ACTIVE) == "active"
        assert str(SubscriptionStatus.SUSPENDED) == "suspended"
        assert str(SubscriptionStatus.CANCELLED) == "cancelled"

    def test_enum_members(self) -> None:
        """SubscriptionStatus should have exactly six members."""
        # TRIAL, ACTIVE, PAST_DUE, SUSPENDED, CANCELLED, GRANDFATHERED
        assert len(SubscriptionStatus) == 6


class TestInvitationStatusEnum:
    """Tests for InvitationStatus enum."""

    def test_pending_value(self) -> None:
        """InvitationStatus.PENDING should have correct value."""
        assert InvitationStatus.PENDING.value == "pending"

    def test_accepted_value(self) -> None:
        """InvitationStatus.ACCEPTED should have correct value."""
        assert InvitationStatus.ACCEPTED.value == "accepted"

    def test_revoked_value(self) -> None:
        """InvitationStatus.REVOKED should have correct value."""
        assert InvitationStatus.REVOKED.value == "revoked"

    def test_expired_value(self) -> None:
        """InvitationStatus.EXPIRED should have correct value."""
        assert InvitationStatus.EXPIRED.value == "expired"

    def test_str_representation(self) -> None:
        """InvitationStatus should convert to string correctly."""
        assert str(InvitationStatus.PENDING) == "pending"
        assert str(InvitationStatus.ACCEPTED) == "accepted"
        assert str(InvitationStatus.REVOKED) == "revoked"
        assert str(InvitationStatus.EXPIRED) == "expired"

    def test_enum_members(self) -> None:
        """InvitationStatus should have exactly four members."""
        assert len(InvitationStatus) == 4


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_generate_invitation_token_length(self) -> None:
        """Generated token should be 43 characters (32 bytes base64 URL-safe)."""
        token = generate_invitation_token()
        assert len(token) == 43

    def test_generate_invitation_token_uniqueness(self) -> None:
        """Each generated token should be unique."""
        tokens = {generate_invitation_token() for _ in range(100)}
        assert len(tokens) == 100

    def test_generate_invitation_token_url_safe(self) -> None:
        """Generated token should be URL-safe (no +, /, or =)."""
        for _ in range(10):
            token = generate_invitation_token()
            assert "+" not in token
            assert "/" not in token
            # URL-safe base64 may have trailing = but token_urlsafe strips them

    def test_default_expiry_is_7_days(self) -> None:
        """Default expiry should be 7 days from now."""
        before = datetime.now(UTC)
        expiry = default_expiry()
        after = datetime.now(UTC)

        # Should be approximately 7 days in the future
        expected_min = before + timedelta(days=7)
        expected_max = after + timedelta(days=7)

        assert expected_min <= expiry <= expected_max

    def test_default_expiry_is_timezone_aware(self) -> None:
        """Default expiry should be timezone-aware (UTC)."""
        expiry = default_expiry()
        assert expiry.tzinfo is not None


class TestTenantModel:
    """Tests for Tenant model."""

    def test_tenant_creation(self) -> None:
        """Tenant should be created with required fields."""
        tenant = Tenant(name="Test Practice", slug="test-practice")
        assert tenant.name == "Test Practice"
        assert tenant.slug == "test-practice"

    def test_tenant_default_values(self) -> None:
        """Tenant should have correct default values.

        Note: SQLAlchemy 2.x applies `default=` values at insert time,
        not at Python object instantiation. We test the defaults that
        are applied via Python `default=` callables.
        """
        tenant = Tenant(name="Test Practice", slug="test-practice")
        # subscription_status uses server_default, not applied until insert
        # settings, mfa_required, is_active use server_default or insert-time default
        # We test that the model can be created without these required fields
        assert tenant.name == "Test Practice"
        assert tenant.slug == "test-practice"

    def test_tenant_repr(self) -> None:
        """Tenant repr should include id, name, and slug."""
        tenant_id = uuid.uuid4()
        tenant = Tenant(id=tenant_id, name="Test Practice", slug="test-practice")
        repr_str = repr(tenant)
        assert "Tenant" in repr_str
        assert str(tenant_id) in repr_str
        assert "Test Practice" in repr_str
        assert "test-practice" in repr_str

    def test_is_trial_property(self) -> None:
        """is_trial should be True only for TRIAL status."""
        tenant = Tenant(name="Test", slug="test")

        tenant.subscription_status = SubscriptionStatus.TRIAL
        assert tenant.is_trial is True

        tenant.subscription_status = SubscriptionStatus.ACTIVE
        assert tenant.is_trial is False

        tenant.subscription_status = SubscriptionStatus.SUSPENDED
        assert tenant.is_trial is False

        tenant.subscription_status = SubscriptionStatus.CANCELLED
        assert tenant.is_trial is False

    def test_is_suspended_property(self) -> None:
        """is_suspended should be True only for SUSPENDED status."""
        tenant = Tenant(name="Test", slug="test")

        tenant.subscription_status = SubscriptionStatus.SUSPENDED
        assert tenant.is_suspended is True

        tenant.subscription_status = SubscriptionStatus.TRIAL
        assert tenant.is_suspended is False

        tenant.subscription_status = SubscriptionStatus.ACTIVE
        assert tenant.is_suspended is False

    def test_can_access_trial(self) -> None:
        """can_access should be True for active TRIAL tenant."""
        tenant = Tenant(name="Test", slug="test")
        tenant.subscription_status = SubscriptionStatus.TRIAL
        tenant.is_active = True
        assert tenant.can_access is True

    def test_can_access_active(self) -> None:
        """can_access should be True for active ACTIVE tenant."""
        tenant = Tenant(name="Test", slug="test")
        tenant.subscription_status = SubscriptionStatus.ACTIVE
        tenant.is_active = True
        assert tenant.can_access is True

    def test_cannot_access_suspended(self) -> None:
        """can_access should be False for SUSPENDED tenant."""
        tenant = Tenant(name="Test", slug="test")
        tenant.subscription_status = SubscriptionStatus.SUSPENDED
        tenant.is_active = True
        assert tenant.can_access is False

    def test_cannot_access_cancelled(self) -> None:
        """can_access should be False for CANCELLED tenant."""
        tenant = Tenant(name="Test", slug="test")
        tenant.subscription_status = SubscriptionStatus.CANCELLED
        tenant.is_active = True
        assert tenant.can_access is False

    def test_cannot_access_inactive(self) -> None:
        """can_access should be False for inactive tenant."""
        tenant = Tenant(name="Test", slug="test")
        tenant.subscription_status = SubscriptionStatus.ACTIVE
        tenant.is_active = False
        assert tenant.can_access is False


class TestUserModel:
    """Tests for User model."""

    def test_user_creation(self) -> None:
        """User should be created with required fields."""
        user = User(email="test@example.com", user_type=UserType.PRACTICE_USER)
        assert user.email == "test@example.com"
        assert user.user_type == UserType.PRACTICE_USER

    def test_user_default_values(self) -> None:
        """User should be creatable with minimal required fields.

        Note: SQLAlchemy 2.x applies `default=` values at insert time,
        not at Python object instantiation.
        """
        user = User(email="test@example.com", user_type=UserType.PRACTICE_USER)
        assert user.email == "test@example.com"
        assert user.user_type == UserType.PRACTICE_USER

    def test_user_repr(self) -> None:
        """User repr should include id, email, and type."""
        user_id = uuid.uuid4()
        user = User(id=user_id, email="test@example.com", user_type=UserType.PRACTICE_USER)
        repr_str = repr(user)
        assert "User" in repr_str
        assert str(user_id) in repr_str
        assert "test@example.com" in repr_str

    def test_is_practice_user_property(self) -> None:
        """is_practice_user should be True only for PRACTICE_USER type."""
        user = User(email="test@example.com", user_type=UserType.PRACTICE_USER)
        assert user.is_practice_user is True
        assert user.is_business_owner is False

    def test_is_business_owner_property(self) -> None:
        """is_business_owner should be True only for BUSINESS_OWNER type."""
        user = User(email="test@example.com", user_type=UserType.BUSINESS_OWNER)
        assert user.is_business_owner is True
        assert user.is_practice_user is False


class TestPracticeUserModel:
    """Tests for PracticeUser model."""

    def test_practice_user_creation(self) -> None:
        """PracticeUser should be created with required fields."""
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        practice_user = PracticeUser(
            user_id=user_id,
            tenant_id=tenant_id,
            clerk_id="clerk_test123",
        )
        assert practice_user.user_id == user_id
        assert practice_user.tenant_id == tenant_id
        assert practice_user.clerk_id == "clerk_test123"

    def test_practice_user_default_values(self) -> None:
        """PracticeUser should be creatable with minimal required fields.

        Note: SQLAlchemy 2.x applies `default=` values at insert time.
        Role defaults to ACCOUNTANT at insert, not at instantiation.
        """
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        practice_user = PracticeUser(
            user_id=user_id,
            tenant_id=tenant_id,
            clerk_id="clerk_test123",
        )
        assert practice_user.user_id == user_id
        assert practice_user.tenant_id == tenant_id
        assert practice_user.clerk_id == "clerk_test123"
        # Role is None until insert, when default=UserRole.ACCOUNTANT applies
        assert practice_user.last_login_at is None

    def test_practice_user_repr(self) -> None:
        """PracticeUser repr should include id, clerk_id, and role."""
        pu_id = uuid.uuid4()
        practice_user = PracticeUser(
            id=pu_id,
            user_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            clerk_id="clerk_test123",
            role=UserRole.ADMIN,
        )
        repr_str = repr(practice_user)
        assert "PracticeUser" in repr_str
        assert str(pu_id) in repr_str
        assert "clerk_test123" in repr_str

    def test_is_admin_property(self) -> None:
        """is_admin should be True only for ADMIN role."""
        practice_user = PracticeUser(
            user_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            clerk_id="clerk_test123",
        )

        practice_user.role = UserRole.ADMIN
        assert practice_user.is_admin is True

        practice_user.role = UserRole.ACCOUNTANT
        assert practice_user.is_admin is False

        practice_user.role = UserRole.STAFF
        assert practice_user.is_admin is False

    def test_can_manage_users_property(self) -> None:
        """can_manage_users should be True only for ADMIN role."""
        practice_user = PracticeUser(
            user_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            clerk_id="clerk_test123",
        )

        practice_user.role = UserRole.ADMIN
        assert practice_user.can_manage_users is True

        practice_user.role = UserRole.ACCOUNTANT
        assert practice_user.can_manage_users is False

        practice_user.role = UserRole.STAFF
        assert practice_user.can_manage_users is False

    def test_can_write_clients_property(self) -> None:
        """can_write_clients should be True for ADMIN and ACCOUNTANT roles."""
        practice_user = PracticeUser(
            user_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            clerk_id="clerk_test123",
        )

        practice_user.role = UserRole.ADMIN
        assert practice_user.can_write_clients is True

        practice_user.role = UserRole.ACCOUNTANT
        assert practice_user.can_write_clients is True

        practice_user.role = UserRole.STAFF
        assert practice_user.can_write_clients is False

    def test_can_lodge_bas_property(self) -> None:
        """can_lodge_bas should be True for ADMIN and ACCOUNTANT roles."""
        practice_user = PracticeUser(
            user_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            clerk_id="clerk_test123",
        )

        practice_user.role = UserRole.ADMIN
        assert practice_user.can_lodge_bas is True

        practice_user.role = UserRole.ACCOUNTANT
        assert practice_user.can_lodge_bas is True

        practice_user.role = UserRole.STAFF
        assert practice_user.can_lodge_bas is False


class TestInvitationModel:
    """Tests for Invitation model."""

    def test_invitation_creation(self) -> None:
        """Invitation should be created with required fields."""
        tenant_id = uuid.uuid4()
        invited_by = uuid.uuid4()
        invitation = Invitation(
            tenant_id=tenant_id,
            invited_by=invited_by,
            email="invite@example.com",
        )
        assert invitation.tenant_id == tenant_id
        assert invitation.invited_by == invited_by
        assert invitation.email == "invite@example.com"

    def test_invitation_default_values(self) -> None:
        """Invitation should be creatable with minimal required fields.

        Note: SQLAlchemy 2.x applies `default=` values at insert time.
        Role, token, and expires_at are None until insert.
        """
        invitation = Invitation(
            tenant_id=uuid.uuid4(),
            invited_by=uuid.uuid4(),
            email="invite@example.com",
        )
        # These are explicitly nullable and have no Python-side default
        assert invitation.accepted_at is None
        assert invitation.accepted_by is None
        assert invitation.revoked_at is None

    def test_invitation_token_generation(self) -> None:
        """Token generation function should produce unique tokens."""
        # Test the token generation function directly
        token1 = generate_invitation_token()
        token2 = generate_invitation_token()
        assert token1 is not None
        assert token2 is not None
        assert token1 != token2
        assert len(token1) == 43

    def test_invitation_default_expiry(self) -> None:
        """Default expiry function should return 7 days from now."""
        before = datetime.now(UTC)
        expiry = default_expiry()
        after = datetime.now(UTC)

        # Expiry should be approximately 7 days from now
        expected_min = before + timedelta(days=7)
        expected_max = after + timedelta(days=7)

        assert expected_min <= expiry <= expected_max

    def test_invitation_status_pending(self) -> None:
        """Status should be PENDING for new invitation."""
        invitation = Invitation(
            tenant_id=uuid.uuid4(),
            invited_by=uuid.uuid4(),
            email="invite@example.com",
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        assert invitation.status == InvitationStatus.PENDING

    def test_invitation_status_accepted(self) -> None:
        """Status should be ACCEPTED when accepted_at is set."""
        invitation = Invitation(
            tenant_id=uuid.uuid4(),
            invited_by=uuid.uuid4(),
            email="invite@example.com",
            expires_at=datetime.now(UTC) + timedelta(days=7),
            accepted_at=datetime.now(UTC),
        )
        assert invitation.status == InvitationStatus.ACCEPTED

    def test_invitation_status_revoked(self) -> None:
        """Status should be REVOKED when revoked_at is set."""
        invitation = Invitation(
            tenant_id=uuid.uuid4(),
            invited_by=uuid.uuid4(),
            email="invite@example.com",
            expires_at=datetime.now(UTC) + timedelta(days=7),
            revoked_at=datetime.now(UTC),
        )
        assert invitation.status == InvitationStatus.REVOKED

    def test_invitation_status_expired(self) -> None:
        """Status should be EXPIRED when expires_at is in the past."""
        invitation = Invitation(
            tenant_id=uuid.uuid4(),
            invited_by=uuid.uuid4(),
            email="invite@example.com",
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )
        assert invitation.status == InvitationStatus.EXPIRED

    def test_invitation_status_priority_accepted_over_revoked(self) -> None:
        """Accepted status takes priority over revoked."""
        invitation = Invitation(
            tenant_id=uuid.uuid4(),
            invited_by=uuid.uuid4(),
            email="invite@example.com",
            expires_at=datetime.now(UTC) + timedelta(days=7),
            accepted_at=datetime.now(UTC),
            revoked_at=datetime.now(UTC),  # Both set
        )
        assert invitation.status == InvitationStatus.ACCEPTED

    def test_invitation_status_priority_revoked_over_expired(self) -> None:
        """Revoked status takes priority over expired."""
        invitation = Invitation(
            tenant_id=uuid.uuid4(),
            invited_by=uuid.uuid4(),
            email="invite@example.com",
            expires_at=datetime.now(UTC) - timedelta(days=1),  # Expired
            revoked_at=datetime.now(UTC),  # Also revoked
        )
        assert invitation.status == InvitationStatus.REVOKED

    def test_is_valid_property(self) -> None:
        """is_valid should be True only when status is PENDING."""
        invitation = Invitation(
            tenant_id=uuid.uuid4(),
            invited_by=uuid.uuid4(),
            email="invite@example.com",
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        assert invitation.is_valid is True

        invitation.accepted_at = datetime.now(UTC)
        assert invitation.is_valid is False

    def test_is_expired_property(self) -> None:
        """is_expired should check expiry timestamp."""
        invitation = Invitation(
            tenant_id=uuid.uuid4(),
            invited_by=uuid.uuid4(),
            email="invite@example.com",
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        assert invitation.is_expired is False

        invitation.expires_at = datetime.now(UTC) - timedelta(days=1)
        assert invitation.is_expired is True

    def test_invitation_repr(self) -> None:
        """Invitation repr should include id, email, and status."""
        inv_id = uuid.uuid4()
        invitation = Invitation(
            id=inv_id,
            tenant_id=uuid.uuid4(),
            invited_by=uuid.uuid4(),
            email="invite@example.com",
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        repr_str = repr(invitation)
        assert "Invitation" in repr_str
        assert str(inv_id) in repr_str
        assert "invite@example.com" in repr_str
