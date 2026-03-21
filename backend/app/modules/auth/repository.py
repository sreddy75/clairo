"""Data access layer for authentication entities.

This module provides repositories for:
- TenantRepository: Tenant CRUD operations
- UserRepository: Base user identity operations
- PracticeUserRepository: Practice user profile operations
- InvitationRepository: Invitation CRUD and token lookup

All repositories use async SQLAlchemy and respect RLS policies.

Usage:
    from app.modules.auth.repository import TenantRepository, UserRepository

    tenant_repo = TenantRepository(session)
    tenant = await tenant_repo.get_by_slug("my-practice")

    user_repo = UserRepository(session)
    user = await user_repo.get_by_email("user@example.com")
"""

import re
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.modules.auth.models import (
    Invitation,
    PracticeUser,
    SubscriptionStatus,
    SubscriptionTier,
    Tenant,
    User,
    UserRole,
    UserType,
)


def generate_slug(name: str) -> str:
    """Generate a URL-safe slug from a name.

    Args:
        name: The name to convert to a slug.

    Returns:
        A lowercase, hyphenated slug.
    """
    # Convert to lowercase and replace spaces with hyphens
    slug = name.lower().strip()
    # Remove special characters except hyphens
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    # Replace spaces and multiple hyphens with single hyphen
    slug = re.sub(r"[\s-]+", "-", slug)
    # Remove leading/trailing hyphens
    slug = slug.strip("-")
    return slug


class TenantRepository:
    """Repository for Tenant CRUD operations.

    Provides methods for creating, reading, updating, and deleting
    tenants (accounting practices).

    Attributes:
        session: Async database session.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository.

        Args:
            session: Async database session.
        """
        self._session = session

    async def get_by_id(self, tenant_id: uuid.UUID) -> Tenant | None:
        """Get a tenant by ID.

        Args:
            tenant_id: The tenant's UUID.

        Returns:
            The tenant if found, None otherwise.
        """
        result = await self._session.execute(select(Tenant).where(Tenant.id == tenant_id))
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Tenant | None:
        """Get a tenant by slug.

        Args:
            slug: The tenant's URL-safe slug.

        Returns:
            The tenant if found, None otherwise.
        """
        result = await self._session.execute(select(Tenant).where(Tenant.slug == slug))
        return result.scalar_one_or_none()

    async def create(
        self,
        name: str,
        slug: str | None = None,
        settings: dict[str, Any] | None = None,
        subscription_status: SubscriptionStatus = SubscriptionStatus.TRIAL,
        tier: SubscriptionTier = SubscriptionTier.STARTER,
        mfa_required: bool = False,
    ) -> Tenant:
        """Create a new tenant.

        Args:
            name: Practice name.
            slug: URL-safe slug (auto-generated if not provided).
            settings: Tenant settings dictionary.
            subscription_status: Initial subscription status.
            tier: Subscription tier (defaults to starter).
            mfa_required: Whether MFA is required for all users.

        Returns:
            The created tenant.
        """
        if slug is None:
            slug = generate_slug(name)

        # Ensure slug is unique by appending random suffix if needed
        base_slug = slug
        counter = 0
        while await self.get_by_slug(slug) is not None:
            counter += 1
            slug = f"{base_slug}-{counter}"

        tenant = Tenant(
            id=uuid.uuid4(),
            name=name,
            slug=slug,
            settings=settings or {},
            subscription_status=subscription_status,
            tier=tier,
            mfa_required=mfa_required,
            is_active=True,
        )
        self._session.add(tenant)
        await self._session.flush()
        await self._session.refresh(tenant)
        return tenant

    async def update(
        self,
        tenant_id: uuid.UUID,
        **updates: Any,
    ) -> Tenant | None:
        """Update a tenant.

        Args:
            tenant_id: The tenant's UUID.
            **updates: Fields to update.

        Returns:
            The updated tenant if found, None otherwise.
        """
        allowed_fields = {
            "name",
            "slug",
            "settings",
            "subscription_status",
            "mfa_required",
            "is_active",
        }
        filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}

        if not filtered_updates:
            return await self.get_by_id(tenant_id)

        await self._session.execute(
            update(Tenant).where(Tenant.id == tenant_id).values(**filtered_updates)
        )
        await self._session.flush()
        return await self.get_by_id(tenant_id)

    async def deactivate(self, tenant_id: uuid.UUID) -> bool:
        """Deactivate a tenant (soft delete).

        Args:
            tenant_id: The tenant's UUID.

        Returns:
            True if deactivated, False if not found.
        """
        tenant = await self.get_by_id(tenant_id)
        if tenant is None:
            return False

        tenant.is_active = False
        await self._session.flush()
        return True


class UserRepository:
    """Repository for base User identity operations.

    Provides methods for managing user identities across tenants.
    Users have a single identity but can have multiple practice profiles.

    Attributes:
        session: Async database session.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository.

        Args:
            session: Async database session.
        """
        self._session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """Get a user by ID.

        Args:
            user_id: The user's UUID.

        Returns:
            The user if found, None otherwise.
        """
        result = await self._session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """Get a user by email address.

        Args:
            email: The user's email address.

        Returns:
            The user if found, None otherwise.
        """
        result = await self._session.execute(select(User).where(User.email == email.lower()))
        return result.scalar_one_or_none()

    async def create(
        self,
        email: str,
        user_type: UserType = UserType.PRACTICE_USER,
        is_active: bool = True,
    ) -> User:
        """Create a new user.

        Args:
            email: User's email address.
            user_type: Type of user.
            is_active: Whether the user is active.

        Returns:
            The created user.
        """
        user = User(
            id=uuid.uuid4(),
            email=email.lower(),
            user_type=user_type,
            is_active=is_active,
        )
        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def update(
        self,
        user_id: uuid.UUID,
        **updates: Any,
    ) -> User | None:
        """Update a user.

        Args:
            user_id: The user's UUID.
            **updates: Fields to update.

        Returns:
            The updated user if found, None otherwise.
        """
        allowed_fields = {"email", "user_type", "is_active"}
        filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}

        if not filtered_updates:
            return await self.get_by_id(user_id)

        await self._session.execute(
            update(User).where(User.id == user_id).values(**filtered_updates)
        )
        await self._session.flush()
        return await self.get_by_id(user_id)


class PracticeUserRepository:
    """Repository for PracticeUser profile operations.

    Provides methods for managing practice user profiles, which link
    users to tenants with specific roles and permissions.

    Attributes:
        session: Async database session.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository.

        Args:
            session: Async database session.
        """
        self._session = session

    async def get_by_id(
        self,
        practice_user_id: uuid.UUID,
        load_relations: bool = False,
    ) -> PracticeUser | None:
        """Get a practice user by ID.

        Args:
            practice_user_id: The practice user's UUID.
            load_relations: Whether to eagerly load user and tenant.

        Returns:
            The practice user if found, None otherwise.
        """
        query = select(PracticeUser).where(PracticeUser.id == practice_user_id)

        if load_relations:
            query = query.options(
                joinedload(PracticeUser.user),
                joinedload(PracticeUser.tenant),
            )

        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_clerk_id(
        self,
        clerk_id: str,
        load_relations: bool = True,
    ) -> PracticeUser | None:
        """Get a practice user by Clerk ID.

        Args:
            clerk_id: The Clerk user ID.
            load_relations: Whether to eagerly load user and tenant.

        Returns:
            The practice user if found, None otherwise.
        """
        query = select(PracticeUser).where(PracticeUser.clerk_id == clerk_id)

        if load_relations:
            query = query.options(
                joinedload(PracticeUser.user),
                joinedload(PracticeUser.tenant),
            )

        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_user_and_tenant(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> PracticeUser | None:
        """Get a practice user by user ID and tenant ID.

        Args:
            user_id: The user's UUID.
            tenant_id: The tenant's UUID.

        Returns:
            The practice user if found, None otherwise.
        """
        result = await self._session.execute(
            select(PracticeUser)
            .where(
                PracticeUser.user_id == user_id,
                PracticeUser.tenant_id == tenant_id,
            )
            .options(
                joinedload(PracticeUser.user),
                joinedload(PracticeUser.tenant),
            )
        )
        return result.scalar_one_or_none()

    async def list_by_tenant(
        self,
        tenant_id: uuid.UUID,
        active_only: bool = True,
    ) -> list[PracticeUser]:
        """List all practice users for a tenant.

        Args:
            tenant_id: The tenant's UUID.
            active_only: Whether to return only active users.

        Returns:
            List of practice users.
        """
        query = (
            select(PracticeUser)
            .where(PracticeUser.tenant_id == tenant_id)
            .options(joinedload(PracticeUser.user))
        )

        if active_only:
            query = query.join(User).where(User.is_active == True)

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def create(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        clerk_id: str,
        role: UserRole = UserRole.ACCOUNTANT,
        mfa_enabled: bool = False,
    ) -> PracticeUser:
        """Create a new practice user profile.

        Args:
            user_id: The user's UUID.
            tenant_id: The tenant's UUID.
            clerk_id: The Clerk user ID.
            role: User's role in the practice.
            mfa_enabled: Whether MFA is enabled.

        Returns:
            The created practice user.
        """
        practice_user = PracticeUser(
            id=uuid.uuid4(),
            user_id=user_id,
            tenant_id=tenant_id,
            clerk_id=clerk_id,
            role=role,
            mfa_enabled=mfa_enabled,
            last_login_at=None,
        )
        self._session.add(practice_user)
        await self._session.flush()
        await self._session.refresh(practice_user)
        return practice_user

    async def update(
        self,
        practice_user_id: uuid.UUID,
        **updates: Any,
    ) -> PracticeUser | None:
        """Update a practice user.

        Args:
            practice_user_id: The practice user's UUID.
            **updates: Fields to update.

        Returns:
            The updated practice user if found, None otherwise.
        """
        allowed_fields = {"role", "mfa_enabled", "last_login_at"}
        filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}

        if not filtered_updates:
            return await self.get_by_id(practice_user_id)

        await self._session.execute(
            update(PracticeUser)
            .where(PracticeUser.id == practice_user_id)
            .values(**filtered_updates)
        )
        await self._session.flush()
        return await self.get_by_id(practice_user_id, load_relations=True)

    async def update_last_login(
        self,
        practice_user_id: uuid.UUID,
    ) -> None:
        """Update the last login timestamp.

        Args:
            practice_user_id: The practice user's UUID.
        """
        await self._session.execute(
            update(PracticeUser)
            .where(PracticeUser.id == practice_user_id)
            .values(last_login_at=datetime.now(UTC))
        )
        await self._session.flush()


class InvitationRepository:
    """Repository for Invitation CRUD operations.

    Provides methods for managing team member invitations.

    Attributes:
        session: Async database session.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository.

        Args:
            session: Async database session.
        """
        self._session = session

    async def get_by_id(self, invitation_id: uuid.UUID) -> Invitation | None:
        """Get an invitation by ID.

        Args:
            invitation_id: The invitation's UUID.

        Returns:
            The invitation if found, None otherwise.
        """
        result = await self._session.execute(
            select(Invitation).where(Invitation.id == invitation_id)
        )
        return result.scalar_one_or_none()

    async def get_by_token(self, token: str) -> Invitation | None:
        """Get an invitation by token.

        Args:
            token: The invitation token.

        Returns:
            The invitation if found, None otherwise.
        """
        result = await self._session.execute(
            select(Invitation)
            .where(Invitation.token == token)
            .options(joinedload(Invitation.tenant))
        )
        return result.scalar_one_or_none()

    async def get_by_email_and_tenant(
        self,
        email: str,
        tenant_id: uuid.UUID,
    ) -> Invitation | None:
        """Get a pending invitation by email and tenant.

        Args:
            email: The invited email address.
            tenant_id: The tenant's UUID.

        Returns:
            The invitation if found and pending, None otherwise.
        """
        result = await self._session.execute(
            select(Invitation).where(
                Invitation.email == email.lower(),
                Invitation.tenant_id == tenant_id,
                Invitation.accepted_at == None,
                Invitation.revoked_at == None,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_tenant(
        self,
        tenant_id: uuid.UUID,
        pending_only: bool = False,
    ) -> list[Invitation]:
        """List all invitations for a tenant.

        Args:
            tenant_id: The tenant's UUID.
            pending_only: Whether to return only pending invitations.

        Returns:
            List of invitations.
        """
        query = select(Invitation).where(Invitation.tenant_id == tenant_id)

        if pending_only:
            query = query.where(
                Invitation.accepted_at == None,
                Invitation.revoked_at == None,
                Invitation.expires_at > datetime.now(UTC),
            )

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def create(
        self,
        tenant_id: uuid.UUID,
        invited_by: uuid.UUID,
        email: str,
        role: UserRole,
        token: str,
        expires_at: datetime,
    ) -> Invitation:
        """Create a new invitation.

        Args:
            tenant_id: The tenant's UUID.
            invited_by: The practice user who sent the invitation.
            email: The invited email address.
            role: The role to assign on acceptance.
            token: The invitation token.
            expires_at: When the invitation expires.

        Returns:
            The created invitation.
        """
        invitation = Invitation(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            invited_by=invited_by,
            email=email.lower(),
            role=role,
            token=token,
            expires_at=expires_at,
            accepted_at=None,
            accepted_by=None,
            revoked_at=None,
        )
        self._session.add(invitation)
        await self._session.flush()
        await self._session.refresh(invitation)
        return invitation

    async def update(
        self,
        invitation_id: uuid.UUID,
        **updates: Any,
    ) -> Invitation | None:
        """Update an invitation.

        Args:
            invitation_id: The invitation's UUID.
            **updates: Fields to update.

        Returns:
            The updated invitation if found, None otherwise.
        """
        allowed_fields = {"accepted_at", "accepted_by", "revoked_at"}
        filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}

        if not filtered_updates:
            return await self.get_by_id(invitation_id)

        await self._session.execute(
            update(Invitation).where(Invitation.id == invitation_id).values(**filtered_updates)
        )
        await self._session.flush()
        return await self.get_by_id(invitation_id)

    async def mark_accepted(
        self,
        invitation_id: uuid.UUID,
        accepted_by: uuid.UUID,
    ) -> Invitation | None:
        """Mark an invitation as accepted.

        Args:
            invitation_id: The invitation's UUID.
            accepted_by: The practice user who accepted.

        Returns:
            The updated invitation if found, None otherwise.
        """
        return await self.update(
            invitation_id,
            accepted_at=datetime.now(UTC),
            accepted_by=accepted_by,
        )

    async def revoke(self, invitation_id: uuid.UUID) -> Invitation | None:
        """Revoke an invitation.

        Args:
            invitation_id: The invitation's UUID.

        Returns:
            The updated invitation if found, None otherwise.
        """
        return await self.update(
            invitation_id,
            revoked_at=datetime.now(UTC),
        )
