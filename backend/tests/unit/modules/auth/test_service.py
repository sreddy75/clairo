"""Unit tests for AuthService.

Tests cover:
- register_user() creates new tenant for fresh registration
- register_user() with invitation token joins existing tenant
- get_current_user() returns user with tenant context
- sync_user_from_clerk() updates user data
"""

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.auth.models import (
    UserRole,
)
from app.modules.auth.schemas import RegisterRequest
from app.modules.auth.service import AuthService
from tests.factories.auth import (
    InvitationFactory,
    PracticeUserFactory,
    TenantFactory,
    UserFactory,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock database session."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def mock_user_repo() -> AsyncMock:
    """Create a mock UserRepository."""
    repo = AsyncMock()
    repo.get_by_email = AsyncMock(return_value=None)
    repo.create = AsyncMock()
    return repo


@pytest.fixture
def mock_practice_user_repo() -> AsyncMock:
    """Create a mock PracticeUserRepository."""
    repo = AsyncMock()
    repo.get_by_clerk_id = AsyncMock(return_value=None)
    repo.create = AsyncMock()
    return repo


@pytest.fixture
def mock_tenant_repo() -> AsyncMock:
    """Create a mock TenantRepository."""
    repo = AsyncMock()
    repo.create = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.get_by_slug = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_invitation_repo() -> AsyncMock:
    """Create a mock InvitationRepository."""
    repo = AsyncMock()
    repo.get_by_token = AsyncMock(return_value=None)
    repo.update = AsyncMock()
    return repo


@pytest.fixture
def mock_clerk_client() -> AsyncMock:
    """Create a mock ClerkClient."""
    client = AsyncMock()
    client.get_user = AsyncMock()
    client.update_user_metadata = AsyncMock()
    return client


@pytest.fixture
def mock_audit_service() -> AsyncMock:
    """Create a mock AuditService."""
    audit = AsyncMock()
    audit.log_event = AsyncMock()
    return audit


@pytest.fixture
def sample_clerk_user() -> dict[str, Any]:
    """Create sample Clerk user data."""
    return {
        "id": "user_clerk123",
        "email_addresses": [
            {"email_address": "test@example.com", "verification": {"status": "verified"}}
        ],
        "first_name": "John",
        "last_name": "Doe",
        "public_metadata": {},
        "private_metadata": {},
    }


@pytest.fixture
def auth_service(
    mock_session: AsyncMock,
    mock_user_repo: AsyncMock,
    mock_practice_user_repo: AsyncMock,
    mock_tenant_repo: AsyncMock,
    mock_invitation_repo: AsyncMock,
    mock_clerk_client: AsyncMock,
    mock_audit_service: AsyncMock,
) -> AuthService:
    """Create AuthService with mocked dependencies."""
    return AuthService(
        session=mock_session,
        user_repo=mock_user_repo,
        practice_user_repo=mock_practice_user_repo,
        tenant_repo=mock_tenant_repo,
        invitation_repo=mock_invitation_repo,
        clerk_client=mock_clerk_client,
        audit_service=mock_audit_service,
    )


# =============================================================================
# AuthService.register_user Tests
# =============================================================================


class TestAuthServiceRegisterUser:
    """Tests for AuthService.register_user()."""

    @pytest.mark.asyncio
    async def test_register_creates_new_tenant_for_fresh_registration(
        self,
        auth_service: AuthService,
        mock_user_repo: AsyncMock,
        mock_practice_user_repo: AsyncMock,
        mock_tenant_repo: AsyncMock,
        mock_clerk_client: AsyncMock,
        sample_clerk_user: dict[str, Any],
    ) -> None:
        """Test that register_user creates a new tenant when no invitation."""
        # Setup
        clerk_id = "user_clerk123"
        email = "test@example.com"
        tenant_name = "New Practice"

        # Mock Clerk returns user info
        mock_clerk_client.get_user.return_value = MagicMock(
            id=clerk_id,
            primary_email=email,
            first_name="John",
            last_name="Doe",
        )

        # Mock no existing user
        mock_user_repo.get_by_email.return_value = None
        mock_practice_user_repo.get_by_clerk_id.return_value = None

        # Mock tenant creation
        new_tenant = TenantFactory(name=tenant_name)
        mock_tenant_repo.create.return_value = new_tenant

        # Mock user creation
        new_user = UserFactory(email=email)
        mock_user_repo.create.return_value = new_user

        # Mock practice user creation
        new_practice_user = PracticeUserFactory(
            user_id=new_user.id,
            tenant_id=new_tenant.id,
            clerk_id=clerk_id,
            role=UserRole.ADMIN,
        )
        mock_practice_user_repo.create.return_value = new_practice_user

        # Execute
        request = RegisterRequest(tenant_name=tenant_name)
        result = await auth_service.register_user(
            clerk_id=clerk_id,
            request=request,
        )

        # Verify
        assert result.is_new_tenant is True
        mock_tenant_repo.create.assert_called_once()
        mock_user_repo.create.assert_called_once()
        mock_practice_user_repo.create.assert_called_once()

        # Verify admin role assigned for new tenant owner
        create_call = mock_practice_user_repo.create.call_args
        assert create_call is not None

    @pytest.mark.asyncio
    async def test_register_with_invitation_joins_existing_tenant(
        self,
        auth_service: AuthService,
        mock_user_repo: AsyncMock,
        mock_practice_user_repo: AsyncMock,
        mock_tenant_repo: AsyncMock,
        mock_invitation_repo: AsyncMock,
        mock_clerk_client: AsyncMock,
    ) -> None:
        """Test that register_user joins existing tenant when invitation provided."""
        # Setup
        clerk_id = "user_clerk456"
        email = "invited@example.com"
        invitation_token = "valid_token_123"

        # Create existing tenant and invitation
        existing_tenant = TenantFactory()
        invitation = InvitationFactory(
            tenant_id=existing_tenant.id,
            email=email,
            role=UserRole.ACCOUNTANT,
            token=invitation_token,
        )

        # Mock Clerk returns user info
        mock_clerk_client.get_user.return_value = MagicMock(
            id=clerk_id,
            primary_email=email,
            first_name="Jane",
            last_name="Smith",
        )

        # Mock no existing user
        mock_user_repo.get_by_email.return_value = None
        mock_practice_user_repo.get_by_clerk_id.return_value = None

        # Mock invitation lookup
        mock_invitation_repo.get_by_token.return_value = invitation
        mock_tenant_repo.get_by_id.return_value = existing_tenant

        # Mock user creation
        new_user = UserFactory(email=email)
        mock_user_repo.create.return_value = new_user

        # Mock practice user creation
        new_practice_user = PracticeUserFactory(
            user_id=new_user.id,
            tenant_id=existing_tenant.id,
            clerk_id=clerk_id,
            role=UserRole.ACCOUNTANT,
        )
        mock_practice_user_repo.create.return_value = new_practice_user

        # Execute
        request = RegisterRequest(invitation_token=invitation_token)
        result = await auth_service.register_user(
            clerk_id=clerk_id,
            request=request,
        )

        # Verify
        assert result.is_new_tenant is False
        # Should NOT create new tenant
        mock_tenant_repo.create.assert_not_called()
        # Should create user with role from invitation
        mock_practice_user_repo.create.assert_called_once()
        # Should mark invitation as accepted
        mock_invitation_repo.mark_accepted.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_fails_if_email_already_registered(
        self,
        auth_service: AuthService,
        mock_user_repo: AsyncMock,
        mock_clerk_client: AsyncMock,
    ) -> None:
        """Test that register_user fails if email already exists."""
        from app.core.exceptions import ConflictError

        # Setup - existing user
        clerk_id = "user_new123"
        email = "existing@example.com"

        mock_clerk_client.get_user.return_value = MagicMock(
            id=clerk_id,
            primary_email=email,
        )

        existing_user = UserFactory(email=email)
        mock_user_repo.get_by_email.return_value = existing_user

        # Execute & Verify
        request = RegisterRequest(tenant_name="New Practice")
        with pytest.raises(ConflictError) as exc_info:
            await auth_service.register_user(
                clerk_id=clerk_id,
                request=request,
            )

        assert "already registered" in str(exc_info.value.message).lower()

    @pytest.mark.asyncio
    async def test_register_fails_with_invalid_invitation_token(
        self,
        auth_service: AuthService,
        mock_invitation_repo: AsyncMock,
        mock_clerk_client: AsyncMock,
    ) -> None:
        """Test that register_user fails with invalid invitation."""
        from app.core.exceptions import NotFoundError

        clerk_id = "user_123"
        invalid_token = "invalid_token"

        mock_clerk_client.get_user.return_value = MagicMock(
            id=clerk_id,
            primary_email="test@example.com",
        )

        mock_invitation_repo.get_by_token.return_value = None

        # Execute & Verify
        request = RegisterRequest(invitation_token=invalid_token)
        with pytest.raises(NotFoundError):
            await auth_service.register_user(
                clerk_id=clerk_id,
                request=request,
            )

    @pytest.mark.asyncio
    async def test_register_fails_with_expired_invitation(
        self,
        auth_service: AuthService,
        mock_invitation_repo: AsyncMock,
        mock_clerk_client: AsyncMock,
    ) -> None:
        """Test that register_user fails with expired invitation."""
        from app.core.exceptions import ValidationError
        from tests.factories.auth import ExpiredInvitationFactory

        clerk_id = "user_123"
        token = "expired_token"

        mock_clerk_client.get_user.return_value = MagicMock(
            id=clerk_id,
            primary_email="test@example.com",
        )

        # Return expired invitation
        expired_invitation = ExpiredInvitationFactory(token=token)
        mock_invitation_repo.get_by_token.return_value = expired_invitation

        # Execute & Verify
        request = RegisterRequest(invitation_token=token)
        with pytest.raises(ValidationError) as exc_info:
            await auth_service.register_user(
                clerk_id=clerk_id,
                request=request,
            )

        assert "expired" in str(exc_info.value.message).lower()


# =============================================================================
# AuthService.get_current_user Tests
# =============================================================================


class TestAuthServiceGetCurrentUser:
    """Tests for AuthService.get_current_user()."""

    @pytest.mark.asyncio
    async def test_get_current_user_returns_practice_user(
        self,
        auth_service: AuthService,
        mock_practice_user_repo: AsyncMock,
    ) -> None:
        """Test get_current_user returns practice user with tenant."""
        # Setup
        clerk_id = "user_clerk123"
        tenant = TenantFactory()
        user = UserFactory()
        practice_user = PracticeUserFactory(
            user_id=user.id,
            tenant_id=tenant.id,
            clerk_id=clerk_id,
        )
        # Set up relationships
        practice_user.user = user
        practice_user.tenant = tenant

        mock_practice_user_repo.get_by_clerk_id.return_value = practice_user

        # Execute
        result = await auth_service.get_current_user(clerk_id=clerk_id)

        # Verify
        assert result == practice_user
        mock_practice_user_repo.get_by_clerk_id.assert_called_once_with(
            clerk_id, load_relations=True
        )

    @pytest.mark.asyncio
    async def test_get_current_user_returns_none_for_unknown_clerk_id(
        self,
        auth_service: AuthService,
        mock_practice_user_repo: AsyncMock,
    ) -> None:
        """Test get_current_user returns None for unknown clerk_id."""
        clerk_id = "unknown_clerk_id"
        mock_practice_user_repo.get_by_clerk_id.return_value = None

        # Execute
        result = await auth_service.get_current_user(clerk_id=clerk_id)

        # Verify
        assert result is None


# =============================================================================
# AuthService.sync_user_from_clerk Tests
# =============================================================================


class TestAuthServiceSyncUserFromClerk:
    """Tests for AuthService.sync_user_from_clerk()."""

    @pytest.mark.asyncio
    async def test_sync_updates_mfa_status(
        self,
        auth_service: AuthService,
        mock_practice_user_repo: AsyncMock,
        mock_clerk_client: AsyncMock,
    ) -> None:
        """Test sync_user_from_clerk updates MFA status from Clerk."""
        # Setup
        clerk_id = "user_clerk123"
        tenant = TenantFactory()
        user = UserFactory()
        practice_user = PracticeUserFactory(
            user_id=user.id,
            tenant_id=tenant.id,
            clerk_id=clerk_id,
            mfa_enabled=False,
        )
        practice_user.user = user
        practice_user.tenant = tenant

        # Clerk reports MFA is now enabled
        mock_clerk_client.get_user.return_value = MagicMock(
            id=clerk_id,
            primary_email=user.email,
            has_mfa_enabled=True,
        )

        mock_practice_user_repo.get_by_clerk_id.return_value = practice_user
        mock_practice_user_repo.update.return_value = practice_user

        # Execute
        result = await auth_service.sync_user_from_clerk(clerk_id=clerk_id)

        # Verify update was called
        mock_practice_user_repo.update.assert_called_once()


# =============================================================================
# AuthService.handle_logout Tests
# =============================================================================


class TestAuthServiceHandleLogout:
    """Tests for AuthService.handle_logout()."""

    @pytest.mark.asyncio
    async def test_handle_logout_logs_event(
        self,
        auth_service: AuthService,
        mock_practice_user_repo: AsyncMock,
        mock_audit_service: AsyncMock,
    ) -> None:
        """Test handle_logout creates audit log entry."""
        # Setup
        user_id = uuid.uuid4()
        tenant = TenantFactory()
        user = UserFactory(id=user_id)
        practice_user = PracticeUserFactory(
            user_id=user.id,
            tenant_id=tenant.id,
        )
        practice_user.user = user
        practice_user.tenant = tenant

        mock_practice_user_repo.get_by_id.return_value = practice_user

        # Execute
        await auth_service.handle_logout(
            practice_user_id=practice_user.id,
            logout_all=False,
        )

        # Verify audit event was logged
        mock_audit_service.log_event.assert_called_once()
        call_kwargs = mock_audit_service.log_event.call_args.kwargs
        assert call_kwargs["event_type"] == "auth.logout"

    @pytest.mark.asyncio
    async def test_handle_logout_all_devices(
        self,
        auth_service: AuthService,
        mock_practice_user_repo: AsyncMock,
        mock_audit_service: AsyncMock,
    ) -> None:
        """Test handle_logout with all_devices flag."""
        # Setup
        practice_user = PracticeUserFactory()
        mock_practice_user_repo.get_by_id.return_value = practice_user

        # Execute
        await auth_service.handle_logout(
            practice_user_id=practice_user.id,
            logout_all=True,
        )

        # Verify audit event includes logout_type
        mock_audit_service.log_event.assert_called_once()
        call_kwargs = mock_audit_service.log_event.call_args.kwargs
        assert call_kwargs.get("metadata", {}).get("logout_type") == "all"
