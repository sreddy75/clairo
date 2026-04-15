"""SQLAlchemy models for authentication and multi-tenancy.

This module defines:
- Enums: UserType, UserRole, SubscriptionStatus, InvitationStatus
- Models: Tenant, User (base identity), PracticeUser (profile), Invitation

Design Pattern: Shared Identity + Separate Profiles
The `users` table is the single source of identity for all user types.
Profile tables (`practice_users`, `client_users`) contain type-specific attributes.

RLS (Row-Level Security):
- RLS is enforced on `practice_users` and `invitations` tables
- The `users` table is NOT tenant-scoped (shared identity across tenant lookups)
- RLS uses PostgreSQL session variable `app.current_tenant_id`
"""

import enum
import secrets
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, func, text
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.modules.admin.models import FeatureFlagOverride
    from app.modules.billing.models import BillingEvent, UsageAlert, UsageSnapshot
    from app.modules.notifications.models import Notification
    from app.modules.onboarding.models import BulkImportJob, EmailDrip, OnboardingProgress

# =============================================================================
# Enums
# =============================================================================


class UserType(str, enum.Enum):
    """Type of user in the system.

    Determines which profile table contains the user's details:
    - PRACTICE_USER: Accountant/staff, uses practice_users table, Clerk auth
    - BUSINESS_OWNER: Client user, uses client_users table, magic link auth (Layer 2)
    """

    PRACTICE_USER = "practice_user"
    BUSINESS_OWNER = "business_owner"

    def __str__(self) -> str:
        """Return the enum value as string."""
        return self.value


class UserRole(str, enum.Enum):
    """Roles for practice users within a tenant.

    Roles determine access permissions:
    - ADMIN: Full access including user management and tenant settings
    - ACCOUNTANT: Full access to client and BAS operations
    - STAFF: Read-only access to client data

    Note: Business owners don't have roles - they have fixed permissions per client.
    """

    ADMIN = "admin"
    ACCOUNTANT = "accountant"
    STAFF = "staff"

    def __str__(self) -> str:
        """Return the enum value as string."""
        return self.value


class SubscriptionTier(str, enum.Enum):
    """Subscription pricing tier.

    Determines feature access and client limits.
    """

    STARTER = "starter"  # $99/mo, 25 clients, basic AI
    PROFESSIONAL = "professional"  # $299/mo, 100 clients, full features
    GROWTH = "growth"  # $599/mo, 250 clients, API access
    ENTERPRISE = "enterprise"  # Custom pricing, unlimited

    def __str__(self) -> str:
        """Return the enum value as string."""
        return self.value


class SubscriptionStatus(str, enum.Enum):
    """Tenant subscription status.

    Controls tenant access and feature availability.
    """

    TRIAL = "trial"
    ACTIVE = "active"
    PAST_DUE = "past_due"  # Payment failed, grace period
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    GRANDFATHERED = "grandfathered"  # Existing users, no payment required

    def __str__(self) -> str:
        """Return the enum value as string."""
        return self.value


class InvitationStatus(str, enum.Enum):
    """Derived status for invitations.

    Note: This is computed, not stored. Status is determined by:
    - pending: not accepted, not revoked, not expired
    - accepted: accepted_at is set
    - revoked: revoked_at is set
    - expired: expires_at < now
    """

    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"
    EXPIRED = "expired"

    def __str__(self) -> str:
        """Return the enum value as string."""
        return self.value


# =============================================================================
# Helper Functions
# =============================================================================


def generate_invitation_token() -> str:
    """Generate a secure random invitation token.

    Uses secrets.token_urlsafe which is cryptographically secure.

    Returns:
        A 43-character URL-safe base64 token (32 bytes of entropy).
    """
    return secrets.token_urlsafe(32)


def default_expiry() -> datetime:
    """Generate default expiry date (7 days from now).

    Returns:
        A timezone-aware datetime 7 days in the future.
    """
    return datetime.now(UTC) + timedelta(days=7)


# =============================================================================
# Models
# =============================================================================


class Tenant(Base, TimestampMixin):
    """Accounting practice (organization) entity.

    A tenant represents an accounting practice that uses Clairo.
    All tenant-scoped data is isolated via PostgreSQL Row-Level Security.

    Attributes:
        id: Unique identifier (UUID).
        name: Display name of the practice.
        slug: URL-friendly unique identifier.
        settings: JSON configuration (MFA settings, preferences, etc.).
        subscription_status: Current subscription state.
        mfa_required: Whether MFA is mandatory for all users.
        is_active: Whether the tenant can access the platform.
        created_at: When the tenant was created.
        updated_at: When the tenant was last modified.

    Relationships:
        practice_users: All practice users belonging to this tenant.
        invitations: All invitations for this tenant.
    """

    __tablename__ = "tenants"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Tenant identification
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Display name of the accounting practice",
    )
    slug: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="URL-friendly unique identifier",
    )

    # Configuration
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="Tenant-specific configuration",
    )

    # Subscription
    subscription_status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(
            SubscriptionStatus,
            name="subscription_status",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=SubscriptionStatus.TRIAL,
        server_default="trial",
        index=True,
        comment="Current subscription state",
    )

    # Subscription tier (Spec 019)
    tier: Mapped[SubscriptionTier] = mapped_column(
        Enum(
            SubscriptionTier,
            name="subscription_tier",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=SubscriptionTier.PROFESSIONAL,
        server_default="professional",
        index=True,
        comment="Subscription pricing tier",
    )

    # Stripe integration
    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
        comment="Stripe customer ID",
    )
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Stripe subscription ID",
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Current billing period end date",
    )

    # Client tracking
    client_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Denormalized client count for limit checks",
    )

    # Usage tracking (Spec 020)
    ai_queries_month: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="AI chat completions this billing period",
    )
    documents_month: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Documents processed this billing period",
    )
    usage_month_reset: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Date when monthly counters were last reset",
    )

    # Owner email for billing
    owner_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Primary contact email for billing",
    )

    # Security settings
    mfa_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Whether MFA is mandatory for all users",
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
        comment="Whether the tenant can access the platform",
    )

    # Relationships
    practice_users: Mapped[list["PracticeUser"]] = relationship(
        "PracticeUser",
        back_populates="tenant",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    invitations: Mapped[list["Invitation"]] = relationship(
        "Invitation",
        back_populates="tenant",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    billing_events: Mapped[list["BillingEvent"]] = relationship(
        "BillingEvent",
        back_populates="tenant",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    # Usage tracking relationships (Spec 020)
    usage_snapshots: Mapped[list["UsageSnapshot"]] = relationship(
        "UsageSnapshot",
        back_populates="tenant",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    usage_alerts: Mapped[list["UsageAlert"]] = relationship(
        "UsageAlert",
        back_populates="tenant",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    # Onboarding relationships (Spec 021)
    onboarding_progress: Mapped["OnboardingProgress | None"] = relationship(
        "OnboardingProgress",
        back_populates="tenant",
        uselist=False,  # 1:1 relationship
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    import_jobs: Mapped[list["BulkImportJob"]] = relationship(
        "BulkImportJob",
        back_populates="tenant",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    email_drips: Mapped[list["EmailDrip"]] = relationship(
        "EmailDrip",
        back_populates="tenant",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    # Feature flag overrides (Spec 022)
    feature_flag_overrides: Mapped[list["FeatureFlagOverride"]] = relationship(
        "FeatureFlagOverride",
        back_populates="tenant",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<Tenant(id={self.id}, name={self.name}, slug={self.slug})>"

    @property
    def is_trial(self) -> bool:
        """Check if tenant is in trial period."""
        return self.subscription_status == SubscriptionStatus.TRIAL

    @property
    def is_suspended(self) -> bool:
        """Check if tenant is suspended."""
        return self.subscription_status == SubscriptionStatus.SUSPENDED

    @property
    def can_access(self) -> bool:
        """Check if tenant can access the platform.

        Access is granted if the tenant is active AND subscription
        status is TRIAL, ACTIVE, PAST_DUE (grace period), or GRANDFATHERED.
        """
        return self.is_active and self.subscription_status in {
            SubscriptionStatus.TRIAL,
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.PAST_DUE,
            SubscriptionStatus.GRANDFATHERED,
        }

    @property
    def is_grandfathered(self) -> bool:
        """Check if tenant has grandfathered status (no payment required)."""
        return self.subscription_status == SubscriptionStatus.GRANDFATHERED


class User(Base, TimestampMixin):
    """Base user identity entity.

    This is the single source of truth for ALL user types in the system.
    It contains only core identity fields; type-specific attributes are
    stored in profile tables (PracticeUser, ClientUser).

    Design Pattern: Shared Identity + Separate Profiles
    - PRACTICE_USER -> PracticeUser profile (accountants, Clerk auth)
    - BUSINESS_OWNER -> ClientUser profile (clients, magic link auth - Layer 2)

    Note: This table is NOT tenant-scoped. Email uniqueness is enforced
    globally to enable cross-tenant user lookup during registration.

    Attributes:
        id: Unique identifier (UUID).
        email: User's email address (unique across all user types).
        user_type: Discriminator for profile table lookup.
        is_active: Whether the user can access the platform.
        created_at: When the user was created.
        updated_at: When the user was last modified.

    Relationships:
        practice_profile: PracticeUser profile (if user_type=PRACTICE_USER).
    """

    __tablename__ = "users"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # User identity
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Email address (unique across all user types)",
    )

    # User type discriminator
    user_type: Mapped[UserType] = mapped_column(
        Enum(
            UserType,
            name="user_type",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        index=True,
        comment="Type of user (determines profile table)",
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
        comment="Whether the user can access the platform",
    )

    # Terms of Service acceptance
    tos_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the user accepted the Terms of Service",
    )
    tos_version_accepted: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="ToS version string accepted (e.g. 1.0)",
    )
    tos_accepted_ip: Mapped[str | None] = mapped_column(
        INET,
        nullable=True,
        comment="IP address at time of ToS acceptance",
    )

    # Relationships (1:1 with profile tables)
    practice_profile: Mapped["PracticeUser | None"] = relationship(
        "PracticeUser",
        back_populates="user",
        uselist=False,
        lazy="joined",
    )
    # client_profile: Mapped["ClientUser | None"] = relationship(...)  # Layer 2

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<User(id={self.id}, email={self.email}, type={self.user_type})>"

    @property
    def is_practice_user(self) -> bool:
        """Check if user is a practice user (accountant/staff)."""
        return self.user_type == UserType.PRACTICE_USER

    @property
    def is_business_owner(self) -> bool:
        """Check if user is a business owner (client portal)."""
        return self.user_type == UserType.BUSINESS_OWNER


class PracticeUser(Base, TimestampMixin):
    """Practice user profile for accountants/staff.

    Contains practice-specific attributes for users authenticated via Clerk.
    Has a 1:1 relationship with User where user_type=PRACTICE_USER.

    This model is tenant-scoped with RLS enforced at the database level.

    Attributes:
        id: Unique identifier (UUID).
        user_id: Foreign key to base User (unique, 1:1).
        tenant_id: Foreign key to the tenant (RLS enforced).
        clerk_id: Unique identifier from Clerk.
        role: User's role within the tenant (Admin/Accountant/Staff).
        mfa_enabled: Whether the user has MFA configured.
        last_login_at: Timestamp of the last successful login.
        created_at: When the profile was created.
        updated_at: When the profile was last modified.

    Relationships:
        user: Base User identity.
        tenant: The tenant this practice user belongs to.
        invitations_sent: Invitations created by this user.
    """

    __tablename__ = "practice_users"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # 1:1 relationship with base User
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
        comment="Foreign key to base User (1:1)",
    )

    # Tenant association (RLS enforced)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Foreign key to tenant (RLS enforced)",
    )

    # Clerk integration
    clerk_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique identifier from Clerk",
    )

    # Authorization
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="user_role",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=UserRole.ACCOUNTANT,
        server_default="accountant",
        index=True,
        comment="Role within the tenant",
    )

    # Display
    display_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Cached display name from Clerk. Falls back to email when NULL.",
    )

    # Security
    mfa_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Whether the user has MFA configured",
    )

    # Activity tracking
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of the last successful login",
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="practice_profile",
        lazy="joined",
    )
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="practice_users",
        lazy="joined",
    )
    invitations_sent: Mapped[list["Invitation"]] = relationship(
        "Invitation",
        back_populates="inviter",
        foreign_keys="Invitation.invited_by",
        lazy="selectin",
    )
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification",
        back_populates="user",
        foreign_keys="Notification.user_id",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<PracticeUser(id={self.id}, clerk_id={self.clerk_id}, role={self.role})>"

    @property
    def email(self) -> str:
        """Get email from base User."""
        return self.user.email

    @property
    def is_admin(self) -> bool:
        """Check if user has admin role."""
        return self.role == UserRole.ADMIN

    @property
    def can_manage_users(self) -> bool:
        """Check if user can manage other users.

        Only admins can manage users (invite, role change, deactivate).
        """
        return self.role == UserRole.ADMIN

    @property
    def can_write_clients(self) -> bool:
        """Check if user can create/update clients.

        Admins and accountants can write client data.
        Staff have read-only access.
        """
        return self.role in {UserRole.ADMIN, UserRole.ACCOUNTANT}

    @property
    def can_lodge_bas(self) -> bool:
        """Check if user can lodge BAS.

        Admins and accountants can lodge BAS.
        Staff have read-only access.
        """
        return self.role in {UserRole.ADMIN, UserRole.ACCOUNTANT}


class Invitation(Base):
    """User invitation entity.

    Represents a pending invitation for a new user to join a tenant.
    Invitations have an expiration date and can be revoked.

    This model is tenant-scoped with RLS enforced at the database level.
    However, a special policy allows public read access by token for
    the invitation acceptance flow.

    Attributes:
        id: Unique identifier (UUID).
        tenant_id: Foreign key to the tenant.
        invited_by: Foreign key to the practice user who created the invitation.
        email: Email address of the invitee.
        role: Role to assign upon acceptance.
        token: Unique token for invitation URL.
        expires_at: When the invitation expires.
        accepted_at: When the invitation was accepted (null if pending).
        accepted_by: Foreign key to the practice user who accepted (null if pending).
        revoked_at: When the invitation was revoked (null if not revoked).
        created_at: When the invitation was created.

    Relationships:
        tenant: The tenant this invitation is for.
        inviter: The practice user who created the invitation.
    """

    __tablename__ = "invitations"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Tenant association (RLS enforced)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Foreign key to tenant (RLS enforced)",
    )

    # Inviter
    invited_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practice_users.id", ondelete="SET NULL"),
        nullable=False,
        comment="Practice user who created the invitation",
    )

    # Invitation details
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Email address of the invitee",
    )

    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="user_role",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=UserRole.ACCOUNTANT,
        server_default="accountant",
        comment="Role to assign upon acceptance",
    )

    # Security token
    token: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
        default=generate_invitation_token,
        comment="Unique token for invitation URL",
    )

    # Lifecycle timestamps
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=default_expiry,
        index=True,
        comment="When the invitation expires",
    )

    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the invitation was accepted",
    )

    accepted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practice_users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Practice user who accepted the invitation",
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the invitation was revoked",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="invitations",
        lazy="joined",
    )
    inviter: Mapped["PracticeUser"] = relationship(
        "PracticeUser",
        back_populates="invitations_sent",
        foreign_keys=[invited_by],
        lazy="joined",
    )

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<Invitation(id={self.id}, email={self.email}, status={self.status})>"

    @property
    def status(self) -> InvitationStatus:
        """Compute the current status of the invitation.

        Status is derived from the state of lifecycle timestamps:
        1. If accepted_at is set -> ACCEPTED
        2. If revoked_at is set -> REVOKED
        3. If expires_at < now -> EXPIRED
        4. Otherwise -> PENDING
        """
        if self.accepted_at is not None:
            return InvitationStatus.ACCEPTED
        if self.revoked_at is not None:
            return InvitationStatus.REVOKED
        if datetime.now(UTC) > self.expires_at:
            return InvitationStatus.EXPIRED
        return InvitationStatus.PENDING

    @property
    def is_valid(self) -> bool:
        """Check if the invitation can still be accepted.

        An invitation is valid only if its status is PENDING.
        """
        return self.status == InvitationStatus.PENDING

    @property
    def is_expired(self) -> bool:
        """Check if the invitation has expired.

        Compares the expiry timestamp against the current UTC time.
        """
        return datetime.now(UTC) > self.expires_at
