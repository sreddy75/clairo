"""Test factories for auth module entities.

Provides factory_boy factories for:
- TenantFactory
- UserFactory
- PracticeUserFactory
- InvitationFactory

These factories create test instances for unit and integration tests.
They can be used standalone or with async SQLAlchemy sessions.

Usage:
    # Standalone (for unit tests)
    tenant = TenantFactory()
    user = UserFactory(email="test@example.com")

    # With SQLAlchemy session (for integration tests)
    tenant = TenantFactory()
    db_session.add(tenant)
    await db_session.flush()
"""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

import factory
from factory import Faker, LazyAttribute, LazyFunction

from app.modules.auth.models import (
    Invitation,
    PracticeUser,
    SubscriptionStatus,
    Tenant,
    User,
    UserRole,
    UserType,
)


class TenantFactory(factory.Factory):
    """Factory for creating Tenant instances.

    Creates a tenant with default values suitable for testing.
    The slug is auto-generated from a UUID to ensure uniqueness.

    Usage:
        tenant = TenantFactory()
        tenant = TenantFactory(name="Custom Practice")
        tenant = TenantFactory(subscription_status=SubscriptionStatus.ACTIVE)
    """

    class Meta:
        model = Tenant

    id = LazyFunction(uuid.uuid4)
    name = Faker("company")
    slug = LazyAttribute(lambda o: f"practice-{uuid.uuid4().hex[:12]}")
    settings = LazyFunction(lambda: {})
    subscription_status = SubscriptionStatus.TRIAL
    mfa_required = False
    is_active = True


class ActiveTenantFactory(TenantFactory):
    """Factory for creating active subscription tenants."""

    subscription_status = SubscriptionStatus.ACTIVE


class SuspendedTenantFactory(TenantFactory):
    """Factory for creating suspended tenants."""

    subscription_status = SubscriptionStatus.SUSPENDED
    is_active = False


class UserFactory(factory.Factory):
    """Factory for creating base User instances.

    Creates a user identity with default PRACTICE_USER type.
    This is the shared identity - profile data is in separate factories.

    Usage:
        user = UserFactory()
        user = UserFactory(email="specific@example.com")
        user = UserFactory(user_type=UserType.BUSINESS_OWNER)
    """

    class Meta:
        model = User

    id = LazyFunction(uuid.uuid4)
    email = LazyFunction(lambda: f"user-{uuid.uuid4().hex[:8]}@example.com")
    user_type = UserType.PRACTICE_USER
    is_active = True


class BusinessOwnerFactory(UserFactory):
    """Factory for creating business owner users."""

    user_type = UserType.BUSINESS_OWNER


class InactiveUserFactory(UserFactory):
    """Factory for creating inactive users."""

    is_active = False


class PracticeUserFactory(factory.Factory):
    """Factory for creating PracticeUser profile instances.

    Creates a practice user profile with default ACCOUNTANT role.
    Requires tenant_id and user_id to be provided or uses UUIDs.

    Usage:
        # With explicit IDs
        practice_user = PracticeUserFactory(
            user_id=user.id,
            tenant_id=tenant.id,
        )

        # With generated IDs (for unit tests)
        practice_user = PracticeUserFactory()
    """

    class Meta:
        model = PracticeUser

    id = LazyFunction(uuid.uuid4)
    user_id = LazyFunction(uuid.uuid4)
    tenant_id = LazyFunction(uuid.uuid4)
    clerk_id = LazyAttribute(lambda o: f"user_{uuid.uuid4().hex[:16]}")
    role = UserRole.ACCOUNTANT
    mfa_enabled = False
    last_login_at = None


class AdminPracticeUserFactory(PracticeUserFactory):
    """Factory for creating admin practice users."""

    role = UserRole.ADMIN


class StaffPracticeUserFactory(PracticeUserFactory):
    """Factory for creating staff practice users."""

    role = UserRole.STAFF


class MFAEnabledPracticeUserFactory(PracticeUserFactory):
    """Factory for creating practice users with MFA enabled."""

    mfa_enabled = True


class InvitationFactory(factory.Factory):
    """Factory for creating Invitation instances.

    Creates an invitation with default 7-day expiry and ACCOUNTANT role.

    Usage:
        invitation = InvitationFactory(
            tenant_id=tenant.id,
            invited_by=practice_user.id,
        )
    """

    class Meta:
        model = Invitation

    id = LazyFunction(uuid.uuid4)
    tenant_id = LazyFunction(uuid.uuid4)
    invited_by = LazyFunction(uuid.uuid4)
    email = LazyFunction(lambda: f"invited-{uuid.uuid4().hex[:8]}@example.com")
    role = UserRole.ACCOUNTANT
    token = LazyFunction(lambda: secrets.token_urlsafe(32))
    expires_at = LazyFunction(lambda: datetime.now(UTC) + timedelta(days=7))
    accepted_at = None
    accepted_by = None
    revoked_at = None


class AdminInvitationFactory(InvitationFactory):
    """Factory for creating admin invitations."""

    role = UserRole.ADMIN


class StaffInvitationFactory(InvitationFactory):
    """Factory for creating staff invitations."""

    role = UserRole.STAFF


class ExpiredInvitationFactory(InvitationFactory):
    """Factory for creating expired invitations."""

    expires_at = LazyFunction(lambda: datetime.now(UTC) - timedelta(days=1))


class AcceptedInvitationFactory(InvitationFactory):
    """Factory for creating accepted invitations."""

    accepted_at = LazyFunction(lambda: datetime.now(UTC))
    accepted_by = LazyFunction(uuid.uuid4)


class RevokedInvitationFactory(InvitationFactory):
    """Factory for creating revoked invitations."""

    revoked_at = LazyFunction(lambda: datetime.now(UTC))


# =============================================================================
# Composite Factory Helpers
# =============================================================================


def create_tenant_with_admin() -> tuple[Tenant, User, PracticeUser]:
    """Create a complete tenant setup with admin user.

    Creates a tenant with a fully linked admin user including
    base User identity and PracticeUser profile.

    Returns:
        Tuple of (Tenant, User, PracticeUser)

    Usage:
        tenant, user, practice_user = create_tenant_with_admin()
    """
    tenant = TenantFactory()
    user = UserFactory()
    practice_user = AdminPracticeUserFactory(
        user_id=user.id,
        tenant_id=tenant.id,
    )
    return tenant, user, practice_user


def create_user_with_profile(
    tenant_id: uuid.UUID,
    role: UserRole = UserRole.ACCOUNTANT,
) -> tuple[User, PracticeUser]:
    """Create a user with linked practice profile.

    Creates a base User identity with a PracticeUser profile
    linked to the specified tenant.

    Args:
        tenant_id: Tenant to associate the user with.
        role: Role for the practice user.

    Returns:
        Tuple of (User, PracticeUser)

    Usage:
        user, practice_user = create_user_with_profile(tenant.id, UserRole.ADMIN)
    """
    user = UserFactory()
    practice_user = PracticeUserFactory(
        user_id=user.id,
        tenant_id=tenant_id,
        role=role,
    )
    return user, practice_user


def create_invitation_for_tenant(
    tenant_id: uuid.UUID,
    invited_by: uuid.UUID,
    email: str | None = None,
    role: UserRole = UserRole.ACCOUNTANT,
) -> Invitation:
    """Create an invitation for a specific tenant.

    Args:
        tenant_id: Tenant to create invitation for.
        invited_by: Practice user creating the invitation.
        email: Optional specific email address.
        role: Role to assign on acceptance.

    Returns:
        Invitation instance.
    """
    kwargs: dict = {
        "tenant_id": tenant_id,
        "invited_by": invited_by,
        "role": role,
    }
    if email:
        kwargs["email"] = email

    return InvitationFactory(**kwargs)
