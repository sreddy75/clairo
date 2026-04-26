"""Business logic services for authentication.

This module provides:
- AuthService: Registration, login, session management
- UserService: User CRUD and role management
- InvitationService: Invitation lifecycle management

All services follow the repository pattern and include audit logging.

Usage:
    from app.modules.auth.service import AuthService

    service = AuthService(
        session=db_session,
        clerk_client=clerk_client,
    )
    result = await service.register_user(
        clerk_id="user_abc123",
        request=RegisterRequest(tenant_name="My Practice"),
    )
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditService
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.core.logging import get_logger

from .clerk import ClerkClient, ClerkUser, get_clerk_client
from .models import (
    Invitation,
    PracticeUser,
    SubscriptionTier,
    Tenant,
    User,
    UserRole,
    UserType,
)
from .repository import (
    InvitationRepository,
    PracticeUserRepository,
    TenantRepository,
    UserRepository,
)
from .schemas import RegisterRequest


# Import email service lazily to avoid circular imports
def _get_email_service() -> "EmailService":
    from app.modules.notifications import get_email_service

    return get_email_service()


logger = get_logger(__name__)

# Type annotation for email service
if False:  # TYPE_CHECKING equivalent
    from app.modules.notifications import EmailService


# Permission definitions by role
ROLE_PERMISSIONS: dict[UserRole, list[str]] = {
    UserRole.ADMIN: [
        "tenant.view",
        "tenant.update",
        "users.view",
        "users.invite",
        "users.update_role",
        "users.deactivate",
        "clients.view",
        "clients.create",
        "clients.update",
        "clients.delete",
        "bas.view",
        "bas.create",
        "bas.update",
        "bas.submit",
        "reports.view",
        "reports.create",
        "integrations.view",
        "integrations.manage",
    ],
    UserRole.ACCOUNTANT: [
        "tenant.view",
        "users.view",
        "clients.view",
        "clients.create",
        "clients.update",
        "bas.view",
        "bas.create",
        "bas.update",
        "bas.submit",
        "reports.view",
        "reports.create",
        "integrations.view",
    ],
    UserRole.STAFF: [
        "tenant.view",
        "users.view",
        "clients.view",
        "bas.view",
        "reports.view",
    ],
}


@dataclass
class RegistrationResult:
    """Result of user registration."""

    user: User
    practice_user: PracticeUser
    tenant: Tenant
    is_new_tenant: bool


class AuthService:
    """Service for authentication operations.

    Handles user registration, session management, and user sync
    with Clerk authentication provider.

    Attributes:
        session: Async database session.
        user_repo: User repository.
        practice_user_repo: Practice user repository.
        tenant_repo: Tenant repository.
        invitation_repo: Invitation repository.
        clerk_client: Clerk API client.
        audit_service: Audit logging service.
    """

    def __init__(
        self,
        session: AsyncSession,
        user_repo: UserRepository | None = None,
        practice_user_repo: PracticeUserRepository | None = None,
        tenant_repo: TenantRepository | None = None,
        invitation_repo: InvitationRepository | None = None,
        clerk_client: ClerkClient | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        """Initialize the auth service.

        Args:
            session: Async database session.
            user_repo: User repository (created if not provided).
            practice_user_repo: Practice user repository (created if not provided).
            tenant_repo: Tenant repository (created if not provided).
            invitation_repo: Invitation repository (created if not provided).
            clerk_client: Clerk API client (created if not provided).
            audit_service: Audit logging service (created if not provided).
        """
        self.session = session
        self.user_repo = user_repo or UserRepository(session)
        self.practice_user_repo = practice_user_repo or PracticeUserRepository(session)
        self.tenant_repo = tenant_repo or TenantRepository(session)
        self.invitation_repo = invitation_repo or InvitationRepository(session)
        self.clerk_client = clerk_client or get_clerk_client()
        self.audit_service = audit_service or AuditService(session)

    async def _get_clerk_user(self, clerk_id: str) -> ClerkUser:
        """Fetch user info from Clerk.

        Args:
            clerk_id: Clerk user ID.

        Returns:
            Clerk user data.
        """
        return await self.clerk_client.get_user(clerk_id)

    async def register_user(
        self,
        clerk_id: str,
        request: RegisterRequest,
    ) -> RegistrationResult:
        """Register a new user after Clerk authentication.

        This method handles both:
        1. New tenant creation (when tenant_name is provided)
        2. Joining existing tenant via invitation (when invitation_token provided)

        Args:
            clerk_id: Clerk user ID from the JWT.
            request: Registration request with tenant name or invitation token.

        Returns:
            Registration result with user, practice user, and tenant.

        Raises:
            ConflictError: If email is already registered.
            NotFoundError: If invitation token is invalid.
            ValidationError: If invitation is expired or revoked.
        """
        # Fetch user info from Clerk
        clerk_user = await self._get_clerk_user(clerk_id)
        email = clerk_user.primary_email

        if email is None:
            raise ValidationError("Email is required for registration")

        # Check if user already exists
        existing_user = await self.user_repo.get_by_email(email)
        if existing_user is not None:
            raise ConflictError(
                message="Email is already registered",
                resource_type="User",
                conflict_field="email",
            )

        # Check if already registered in any practice
        existing_practice_user = await self.practice_user_repo.get_by_clerk_id(clerk_id)
        if existing_practice_user is not None:
            raise ConflictError(
                message="User is already registered with a practice",
                resource_type="PracticeUser",
                conflict_field="clerk_id",
            )

        # Handle invitation-based registration
        if request.invitation_token:
            return await self._register_with_invitation(
                clerk_id=clerk_id,
                email=email,
                invitation_token=request.invitation_token,
            )

        # Handle new tenant creation
        if request.tenant_name:
            return await self._register_new_tenant(
                clerk_id=clerk_id,
                email=email,
                tenant_name=request.tenant_name,
                tier=request.tier or SubscriptionTier.STARTER,
            )

        raise ValidationError("Either tenant_name or invitation_token is required for registration")

    async def _register_with_invitation(
        self,
        clerk_id: str,
        email: str,
        invitation_token: str,
    ) -> RegistrationResult:
        """Register a user via invitation.

        Args:
            clerk_id: Clerk user ID.
            email: User's email address.
            invitation_token: Invitation token.

        Returns:
            Registration result.

        Raises:
            NotFoundError: If invitation not found.
            ValidationError: If invitation is invalid.
        """
        # Look up invitation
        invitation = await self.invitation_repo.get_by_token(invitation_token)
        if invitation is None:
            raise NotFoundError(
                resource_type="Invitation",
                message="Invalid invitation token",
            )

        # Check invitation status
        if invitation.is_expired:
            raise ValidationError("Invitation has expired")

        if invitation.accepted_at is not None:
            raise ValidationError("Invitation has already been accepted")

        if invitation.revoked_at is not None:
            raise ValidationError("Invitation has been revoked")

        # Verify email matches (optional - depending on business rules)
        if invitation.email.lower() != email.lower():
            raise ValidationError("Email does not match invitation")

        # Get the tenant
        tenant = await self.tenant_repo.get_by_id(invitation.tenant_id)
        if tenant is None or not tenant.is_active:
            raise NotFoundError(
                resource_type="Tenant",
                message="Tenant not found or inactive",
            )

        # Create user and practice user
        user = await self.user_repo.create(
            email=email,
            user_type=UserType.PRACTICE_USER,
        )

        practice_user = await self.practice_user_repo.create(
            user_id=user.id,
            tenant_id=tenant.id,
            clerk_id=clerk_id,
            role=invitation.role,
            mfa_enabled=False,
        )

        # Mark invitation as accepted
        await self.invitation_repo.mark_accepted(
            invitation_id=invitation.id,
            accepted_by=practice_user.id,
        )

        # Update Clerk user metadata with tenant_id and role
        await self.clerk_client.update_user_metadata(
            clerk_id=clerk_id,
            public_metadata={
                "tenant_id": str(tenant.id),
                "role": invitation.role.value,
            },
        )

        # Audit log
        await self.audit_service.log_event(
            event_type="auth.registration",
            event_category="auth",
            actor_id=user.id,
            actor_email=email,
            tenant_id=tenant.id,
            resource_type="user",
            resource_id=user.id,
            action="create",
            outcome="success",
            metadata={
                "registration_type": "invitation",
                "role": invitation.role.value,
            },
        )

        logger.info(
            "User registered via invitation",
            user_id=str(user.id),
            tenant_id=str(tenant.id),
            role=invitation.role.value,
        )

        return RegistrationResult(
            user=user,
            practice_user=practice_user,
            tenant=tenant,
            is_new_tenant=False,
        )

    async def _register_new_tenant(
        self,
        clerk_id: str,
        email: str,
        tenant_name: str,
        tier: SubscriptionTier = SubscriptionTier.STARTER,
    ) -> RegistrationResult:
        """Register a user with a new tenant.

        Args:
            clerk_id: Clerk user ID.
            email: User's email address.
            tenant_name: Name for the new tenant.
            tier: Subscription tier for the new tenant.

        Returns:
            Registration result.
        """
        # Create tenant
        tenant = await self.tenant_repo.create(
            name=tenant_name,
            tier=tier,
        )

        # Create user
        user = await self.user_repo.create(
            email=email,
            user_type=UserType.PRACTICE_USER,
        )

        # Create practice user as admin (first user is always admin)
        practice_user = await self.practice_user_repo.create(
            user_id=user.id,
            tenant_id=tenant.id,
            clerk_id=clerk_id,
            role=UserRole.ADMIN,
            mfa_enabled=False,
        )

        # Update Clerk user metadata with tenant_id and role
        await self.clerk_client.update_user_metadata(
            clerk_id=clerk_id,
            public_metadata={
                "tenant_id": str(tenant.id),
                "role": UserRole.ADMIN.value,
            },
        )

        # Audit log
        await self.audit_service.log_event(
            event_type="auth.registration",
            event_category="auth",
            actor_id=user.id,
            actor_email=email,
            tenant_id=tenant.id,
            resource_type="user",
            resource_id=user.id,
            action="create",
            outcome="success",
            metadata={
                "registration_type": "new_tenant",
                "role": UserRole.ADMIN.value,
                "tenant_name": tenant_name,
            },
        )

        logger.info(
            "New tenant registered",
            user_id=str(user.id),
            tenant_id=str(tenant.id),
            tenant_name=tenant_name,
        )

        # Send welcome email (fire and forget - don't block registration)
        try:
            clerk_user = await self._get_clerk_user(clerk_id)
            user_name = clerk_user.first_name or email.split("@")[0]
            email_service = _get_email_service()
            await email_service.send_welcome_email(
                to=email,
                user_name=user_name,
                practice_name=tenant_name,
            )
        except Exception as e:
            # Log but don't fail registration if email fails
            logger.warning(
                "Failed to send welcome email",
                error=str(e),
                user_id=str(user.id),
                email=email,
            )

        return RegistrationResult(
            user=user,
            practice_user=practice_user,
            tenant=tenant,
            is_new_tenant=True,
        )

    async def get_current_user(
        self,
        clerk_id: str,
    ) -> PracticeUser | None:
        """Get current user by Clerk ID.

        Args:
            clerk_id: Clerk user ID from the JWT.

        Returns:
            Practice user with relationships loaded, or None if not found.
        """
        return await self.practice_user_repo.get_by_clerk_id(
            clerk_id,
            load_relations=True,
        )

    async def sync_user_from_clerk(
        self,
        clerk_id: str,
    ) -> PracticeUser | None:
        """Sync user data from Clerk.

        Updates local user data with latest from Clerk
        (e.g., MFA status changes).

        Args:
            clerk_id: Clerk user ID.

        Returns:
            Updated practice user or None if not found.
        """
        practice_user = await self.practice_user_repo.get_by_clerk_id(clerk_id)
        if practice_user is None:
            return None

        # Fetch latest from Clerk
        clerk_user = await self._get_clerk_user(clerk_id)

        # Update MFA status if changed
        if clerk_user.has_mfa_enabled != practice_user.mfa_enabled:
            await self.practice_user_repo.update(
                practice_user.id,
                mfa_enabled=clerk_user.has_mfa_enabled,
            )

        # Update last login
        await self.practice_user_repo.update_last_login(practice_user.id)

        return await self.practice_user_repo.get_by_clerk_id(
            clerk_id,
            load_relations=True,
        )

    async def handle_logout(
        self,
        practice_user_id: uuid.UUID,
        logout_all: bool = False,
    ) -> None:
        """Handle user logout.

        Logs the logout event for audit purposes.
        Actual session invalidation is handled by Clerk.

        Args:
            practice_user_id: Practice user ID.
            logout_all: Whether logging out from all devices.
        """
        practice_user = await self.practice_user_repo.get_by_id(
            practice_user_id,
            load_relations=True,
        )

        if practice_user is None:
            return

        # Audit log
        await self.audit_service.log_event(
            event_type="auth.logout",
            event_category="auth",
            actor_id=practice_user.user_id,
            tenant_id=practice_user.tenant_id,
            resource_type="session",
            action="logout",
            outcome="success",
            metadata={
                "logout_type": "all" if logout_all else "current",
            },
        )

        logger.info(
            "User logged out",
            practice_user_id=str(practice_user_id),
            logout_all=logout_all,
        )

    def get_permissions_for_role(self, role: UserRole) -> list[str]:
        """Get permissions for a role.

        Args:
            role: User role.

        Returns:
            List of permission strings.
        """
        return ROLE_PERMISSIONS.get(role, [])

    async def update_tenant_settings(
        self,
        tenant_id: uuid.UUID,
        update_data: "TenantUpdate",
        actor_id: uuid.UUID | None = None,
        actor_email: str | None = None,
    ) -> Tenant:
        """Update tenant settings.

        Args:
            tenant_id: Tenant UUID.
            update_data: Update request schema.
            actor_id: ID of the actor making changes.
            actor_email: Email of the actor making changes.

        Returns:
            Updated tenant.

        Raises:
            NotFoundError: If tenant not found.
        """

        tenant = await self.tenant_repo.get_by_id(tenant_id)
        if tenant is None:
            raise NotFoundError(
                resource_type="Tenant",
                resource_id=str(tenant_id),
            )

        # Build update dict from provided fields
        update_dict: dict[str, Any] = {}
        old_values: dict[str, Any] = {}

        if update_data.name is not None and update_data.name != tenant.name:
            old_values["name"] = tenant.name
            update_dict["name"] = update_data.name

        if update_data.mfa_required is not None and update_data.mfa_required != tenant.mfa_required:
            old_values["mfa_required"] = tenant.mfa_required
            update_dict["mfa_required"] = update_data.mfa_required

        if update_data.settings is not None:
            old_values["settings"] = tenant.settings
            update_dict["settings"] = update_data.settings

        # Only update if there are changes
        if update_dict:
            updated_tenant = await self.tenant_repo.update(tenant_id, **update_dict)

            # Audit log
            await self.audit_service.log_event(
                event_type="tenant.settings.changed",
                event_category="auth",
                actor_type="user",
                actor_id=actor_id,
                actor_email=actor_email,
                tenant_id=tenant_id,
                resource_type="tenant",
                resource_id=tenant_id,
                action="update",
                outcome="success",
                old_values=old_values,
                new_values=update_dict,
            )

            logger.info(
                "Tenant settings updated",
                tenant_id=str(tenant_id),
                fields_updated=list(update_dict.keys()),
                updated_by=str(actor_id) if actor_id else None,
            )

            return updated_tenant

        return tenant

    async def accept_terms(
        self,
        user_id: uuid.UUID,
        version: str,
        ip_address: str | None = None,
        tenant_id: uuid.UUID | None = None,
    ) -> "User":
        """Record the user's acceptance of Terms of Service.

        Args:
            user_id: The user accepting the terms.
            version: The ToS version being accepted.
            ip_address: IP address at time of acceptance.

        Returns:
            Updated User with ToS fields set.
        """
        from app.core.constants import TOS_CURRENT_VERSION

        if version != TOS_CURRENT_VERSION:
            from app.core.exceptions import ValidationError

            raise ValidationError(
                f"Version mismatch: expected {TOS_CURRENT_VERSION}, got {version}"
            )

        user = await self.user_repo.get_by_id(user_id)
        if not user:
            from app.core.exceptions import NotFoundError

            raise NotFoundError(f"User {user_id} not found")

        now = datetime.now(UTC)
        user.tos_accepted_at = now
        user.tos_version_accepted = version
        user.tos_accepted_ip = ip_address
        await self.session.flush()

        if self.audit_service and tenant_id:
            await self.audit_service.log_event(
                event_type="user.tos.accepted",
                event_category="auth",
                actor_type="user",
                actor_id=user_id,
                actor_email=user.email,
                actor_ip=ip_address,
                tenant_id=tenant_id,
                resource_type="user",
                resource_id=user_id,
                action="update",
                outcome="success",
                new_values={"tos_version": version},
                metadata={"version": version, "ip_address": ip_address},
            )

        return user


class UserService:
    """Service for user management operations.

    Handles user CRUD, role changes, and deactivation.

    Attributes:
        session: Async database session.
        practice_user_repo: Practice user repository.
        user_repo: Base user repository.
        audit_service: Audit logging service.
        actor_id: ID of the user performing actions.
        actor_email: Email of the user performing actions.
        tenant_id: Current tenant ID for audit logging.
    """

    def __init__(
        self,
        session: AsyncSession,
        actor_id: uuid.UUID | None = None,
        actor_email: str | None = None,
        tenant_id: uuid.UUID | None = None,
    ) -> None:
        """Initialize the user service.

        Args:
            session: Async database session.
            actor_id: ID of the user performing actions.
            actor_email: Email of the user performing actions.
            tenant_id: Current tenant ID for scoping.
        """
        self.session = session
        self.actor_id = actor_id
        self.actor_email = actor_email
        self.tenant_id = tenant_id
        self.practice_user_repo = PracticeUserRepository(session)
        self.user_repo = UserRepository(session)
        self.audit_service = AuditService(session)

    async def get_user(
        self,
        practice_user_id: uuid.UUID,
    ) -> PracticeUser | None:
        """Get a user by practice user ID.

        Args:
            practice_user_id: Practice user UUID.

        Returns:
            Practice user with relationships loaded, or None if not found.
        """
        return await self.practice_user_repo.get_by_id(
            practice_user_id,
            load_relations=True,
        )

    async def list_tenant_users(
        self,
        tenant_id: uuid.UUID,
        active_only: bool = True,
    ) -> list[PracticeUser]:
        """List all users for a tenant.

        Args:
            tenant_id: Tenant UUID.
            active_only: Whether to return only active users.

        Returns:
            List of practice users.
        """
        return await self.practice_user_repo.list_by_tenant(
            tenant_id,
            active_only=active_only,
        )

    async def update_role(
        self,
        practice_user_id: uuid.UUID,
        new_role: UserRole,
    ) -> PracticeUser | None:
        """Update a user's role.

        Args:
            practice_user_id: Practice user UUID.
            new_role: New role to assign.

        Returns:
            Updated practice user or None if not found.

        Raises:
            NotFoundError: If user not found.
        """
        practice_user = await self.practice_user_repo.get_by_id(
            practice_user_id,
            load_relations=True,
        )
        if practice_user is None:
            raise NotFoundError(
                resource_type="User",
                resource_id=str(practice_user_id),
            )

        old_role = practice_user.role

        # Don't update if role is the same
        if old_role == new_role:
            return practice_user

        updated = await self.practice_user_repo.update(
            practice_user_id,
            role=new_role,
        )

        # Audit log
        await self.audit_service.log_event(
            event_type="user.role.changed",
            event_category="auth",
            actor_id=self.actor_id,
            actor_email=self.actor_email,
            tenant_id=practice_user.tenant_id,
            resource_type="user",
            resource_id=practice_user.user_id,
            action="update",
            outcome="success",
            old_values={"role": old_role.value if old_role else None},
            new_values={"role": new_role.value},
            metadata={
                "changed_by": str(self.actor_id) if self.actor_id else None,
            },
        )

        logger.info(
            "User role changed",
            practice_user_id=str(practice_user_id),
            old_role=str(old_role),
            new_role=str(new_role),
            changed_by=str(self.actor_id) if self.actor_id else None,
        )

        return updated

    async def deactivate_user(
        self,
        practice_user_id: uuid.UUID,
        reason: str,
    ) -> PracticeUser | None:
        """Deactivate a user.

        This sets the base User's is_active to False, preventing
        the user from accessing the system.

        Args:
            practice_user_id: Practice user UUID.
            reason: Reason for deactivation (for audit).

        Returns:
            Updated practice user or None if not found.

        Raises:
            NotFoundError: If user not found.
            ValidationError: If trying to deactivate the last admin.
        """
        practice_user = await self.practice_user_repo.get_by_id(
            practice_user_id,
            load_relations=True,
        )
        if practice_user is None:
            raise NotFoundError(
                resource_type="User",
                resource_id=str(practice_user_id),
            )

        # Check if user is already deactivated
        if not practice_user.user.is_active:
            return practice_user

        # Check if this is the last admin (prevent lockout)
        if practice_user.role == UserRole.ADMIN:
            active_admins = await self._count_active_admins(practice_user.tenant_id)
            if active_admins <= 1:
                raise ValidationError(
                    "Cannot deactivate the last admin user. Promote another user to admin first."
                )

        # Deactivate the base user
        await self.user_repo.update(
            practice_user.user_id,
            is_active=False,
        )

        # Audit log
        await self.audit_service.log_event(
            event_type="user.deactivated",
            event_category="auth",
            actor_id=self.actor_id,
            actor_email=self.actor_email,
            tenant_id=practice_user.tenant_id,
            resource_type="user",
            resource_id=practice_user.user_id,
            action="deactivate",
            outcome="success",
            metadata={
                "reason": reason,
                "deactivated_by": str(self.actor_id) if self.actor_id else None,
            },
        )

        logger.info(
            "User deactivated",
            practice_user_id=str(practice_user_id),
            reason=reason,
            deactivated_by=str(self.actor_id) if self.actor_id else None,
        )

        # Refresh and return
        return await self.practice_user_repo.get_by_id(
            practice_user_id,
            load_relations=True,
        )

    async def activate_user(
        self,
        practice_user_id: uuid.UUID,
    ) -> PracticeUser | None:
        """Activate a previously deactivated user.

        This sets the base User's is_active to True.

        Args:
            practice_user_id: Practice user UUID.

        Returns:
            Updated practice user or None if not found.

        Raises:
            NotFoundError: If user not found.
        """
        practice_user = await self.practice_user_repo.get_by_id(
            practice_user_id,
            load_relations=True,
        )
        if practice_user is None:
            raise NotFoundError(
                resource_type="User",
                resource_id=str(practice_user_id),
            )

        # Check if user is already active
        if practice_user.user.is_active:
            return practice_user

        # Activate the base user
        await self.user_repo.update(
            practice_user.user_id,
            is_active=True,
        )

        # Audit log
        await self.audit_service.log_event(
            event_type="user.activated",
            event_category="auth",
            actor_id=self.actor_id,
            actor_email=self.actor_email,
            tenant_id=practice_user.tenant_id,
            resource_type="user",
            resource_id=practice_user.user_id,
            action="activate",
            outcome="success",
            metadata={
                "activated_by": str(self.actor_id) if self.actor_id else None,
            },
        )

        logger.info(
            "User activated",
            practice_user_id=str(practice_user_id),
            activated_by=str(self.actor_id) if self.actor_id else None,
        )

        # Refresh and return
        return await self.practice_user_repo.get_by_id(
            practice_user_id,
            load_relations=True,
        )

    async def _count_active_admins(self, tenant_id: uuid.UUID) -> int:
        """Count active admin users in a tenant.

        Args:
            tenant_id: Tenant UUID.

        Returns:
            Number of active admin users.
        """
        users = await self.practice_user_repo.list_by_tenant(
            tenant_id,
            active_only=True,
        )
        return sum(1 for u in users if u.role == UserRole.ADMIN)


class InvitationService:
    """Service for invitation management.

    Handles invitation creation, lookup, and lifecycle.

    Attributes:
        session: Async database session.
        invitation_repo: Invitation repository.
        audit_service: Audit logging service.
    """

    def __init__(
        self,
        session: AsyncSession,
        actor_id: uuid.UUID | None = None,
        actor_email: str | None = None,
    ) -> None:
        """Initialize the invitation service.

        Args:
            session: Async database session.
            actor_id: ID of the user performing actions.
            actor_email: Email of the user performing actions.
        """
        self.session = session
        self.actor_id = actor_id
        self.actor_email = actor_email
        self.invitation_repo = InvitationRepository(session)
        self.audit_service = AuditService(session)

    async def get_by_token(self, token: str) -> Invitation | None:
        """Get invitation by token.

        Args:
            token: Invitation token.

        Returns:
            Invitation if found, None otherwise.
        """
        return await self.invitation_repo.get_by_token(token)

    async def list_pending(self, tenant_id: uuid.UUID) -> list[Invitation]:
        """List pending invitations for a tenant.

        Args:
            tenant_id: Tenant UUID.

        Returns:
            List of pending invitations.
        """
        return await self.invitation_repo.list_by_tenant(
            tenant_id,
            pending_only=True,
        )

    async def revoke(
        self,
        invitation_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> Invitation | None:
        """Revoke an invitation.

        Args:
            invitation_id: Invitation UUID.
            tenant_id: Tenant UUID (for verification).

        Returns:
            Revoked invitation or None if not found.
        """
        invitation = await self.invitation_repo.get_by_id(invitation_id)
        if invitation is None or invitation.tenant_id != tenant_id:
            return None

        revoked = await self.invitation_repo.revoke(invitation_id)

        if revoked:
            # Audit log
            await self.audit_service.log_event(
                event_type="invitation.revoked",
                event_category="auth",
                actor_id=self.actor_id,
                actor_email=self.actor_email,
                tenant_id=tenant_id,
                resource_type="invitation",
                resource_id=invitation_id,
                action="revoke",
                outcome="success",
            )

        return revoked

    async def create_invitation(
        self,
        tenant_id: uuid.UUID,
        invited_by: uuid.UUID,
        email: str,
        role: UserRole,
        expires_in_days: int = 7,
    ) -> Invitation:
        """Create a new invitation.

        Args:
            tenant_id: Tenant UUID.
            invited_by: Practice user ID creating the invitation.
            email: Email to invite.
            role: Role to assign on acceptance.
            expires_in_days: Days until expiration.

        Returns:
            Created invitation.

        Raises:
            ConflictError: If email already has pending invitation or is registered.
        """
        import secrets
        from datetime import timedelta

        # Check for existing pending invitation
        existing = await self.invitation_repo.get_by_email_and_tenant(email, tenant_id)
        if existing is not None:
            raise ConflictError(
                message="An invitation for this email already exists",
                resource_type="invitation",
                conflict_field="email",
            )

        # Check if user already exists in this tenant
        practice_user_repo = PracticeUserRepository(self.session)
        users = await practice_user_repo.list_by_tenant(tenant_id, active_only=False)
        for user in users:
            if user.email.lower() == email.lower():
                raise ConflictError(
                    message="User already exists in this tenant",
                    resource_type="user",
                    conflict_field="email",
                )

        # Generate unique token
        token = secrets.token_urlsafe(32)

        # Calculate expiration
        expires_at = datetime.now(UTC) + timedelta(days=expires_in_days)

        # Create invitation
        invitation = await self.invitation_repo.create(
            tenant_id=tenant_id,
            invited_by=invited_by,
            email=email.lower(),
            role=role,
            token=token,
            expires_at=expires_at,
        )

        # Audit log
        await self.audit_service.log_event(
            event_type="user.invitation.created",
            event_category="auth",
            actor_id=self.actor_id,
            actor_email=self.actor_email,
            tenant_id=tenant_id,
            resource_type="invitation",
            resource_id=invitation.id,
            action="create",
            outcome="success",
            metadata={
                "invited_email": email,
                "invited_role": role.value,
                "expires_at": expires_at.isoformat(),
            },
        )

        logger.info(
            "Invitation created",
            invitation_id=str(invitation.id),
            tenant_id=str(tenant_id),
            email=email,
            role=role.value,
        )

        # Send invitation email
        try:
            # Get tenant and inviter details for the email
            tenant_repo = TenantRepository(self.session)
            tenant = await tenant_repo.get_by_id(tenant_id)
            tenant_name = tenant.name if tenant else "Unknown Practice"

            # Build invitation URL from config
            from app.config import get_settings

            frontend_url = get_settings().frontend_url.rstrip("/")
            invitation_url = f"{frontend_url}/invitation?token={token}"

            email_service = _get_email_service()
            await email_service.send_team_invitation(
                to=email,
                inviter_name=self.actor_email or "A team member",
                practice_name=tenant_name,
                invitation_url=invitation_url,
                role=role.value,
            )
        except Exception as e:
            # Log but don't fail invitation creation if email fails
            logger.warning(
                "Failed to send invitation email",
                error=str(e),
                invitation_id=str(invitation.id),
                email=email,
            )

        return invitation

    async def list_all(
        self,
        tenant_id: uuid.UUID,
        pending_only: bool = False,
    ) -> list[Invitation]:
        """List all invitations for a tenant.

        Args:
            tenant_id: Tenant UUID.
            pending_only: Whether to return only pending invitations.

        Returns:
            List of invitations.
        """
        return await self.invitation_repo.list_by_tenant(
            tenant_id,
            pending_only=pending_only,
        )

    async def accept_invitation(
        self,
        token: str,
        accepted_by: uuid.UUID,
    ) -> Invitation | None:
        """Accept an invitation.

        Args:
            token: Invitation token.
            accepted_by: Practice user ID accepting.

        Returns:
            Updated invitation or None if invalid.

        Raises:
            ValidationError: If invitation is expired or already used.
        """
        invitation = await self.invitation_repo.get_by_token(token)
        if invitation is None:
            raise NotFoundError(
                resource_type="Invitation",
                message="Invitation not found or expired",
            )

        # Check if already accepted
        if invitation.accepted_at is not None:
            raise ValidationError("Invitation has already been used")

        # Check if revoked
        if invitation.revoked_at is not None:
            raise ValidationError("Invitation has been revoked")

        # Check expiration
        if invitation.expires_at < datetime.now(UTC):
            raise ValidationError("Invitation has expired")

        # Mark as accepted
        updated = await self.invitation_repo.mark_accepted(
            invitation.id,
            accepted_by=accepted_by,
        )

        if updated:
            # Audit log
            await self.audit_service.log_event(
                event_type="user.invitation.accepted",
                event_category="auth",
                actor_id=accepted_by,
                tenant_id=invitation.tenant_id,
                resource_type="invitation",
                resource_id=invitation.id,
                action="accept",
                outcome="success",
            )

            logger.info(
                "Invitation accepted",
                invitation_id=str(invitation.id),
                tenant_id=str(invitation.tenant_id),
                accepted_by=str(accepted_by),
            )

        return updated

    async def get_valid_invitation(self, token: str) -> Invitation | None:
        """Get a valid (not expired, not used, not revoked) invitation.

        Args:
            token: Invitation token.

        Returns:
            Valid invitation or None.
        """
        invitation = await self.invitation_repo.get_by_token(token)
        if invitation is None:
            return None

        # Check validity
        if invitation.accepted_at is not None:
            return None
        if invitation.revoked_at is not None:
            return None
        if invitation.expires_at < datetime.now(UTC):
            return None

        return invitation
