"""Unit tests for MagicLinkService.

Tests cover:
- Token generation (magic link and refresh tokens)
- Token hashing
- Token verification
- Session creation and refresh
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.portal.auth.magic_link import (
    MAGIC_LINK_TOKEN_BYTES,
    MagicLinkService,
    generate_secure_token,
    hash_token,
)
from app.modules.portal.enums import InvitationStatus
from app.modules.portal.exceptions import (
    InvitationAlreadyAcceptedError,
    InvitationExpiredError,
    InvitationInvalidTokenError,
    InvitationNotFoundError,
    PortalAuthenticationError,
    PortalSessionExpiredError,
    PortalSessionRevokedError,
)

# =============================================================================
# Token Utility Tests
# =============================================================================


class TestGenerateSecureToken:
    """Tests for generate_secure_token function."""

    def test_generates_url_safe_token(self):
        """Token should be URL-safe base64 encoded."""
        token = generate_secure_token()
        # URL-safe tokens contain only alphanumeric, hyphen, underscore
        assert all(c.isalnum() or c in "-_" for c in token)

    def test_generates_unique_tokens(self):
        """Each call should generate a unique token."""
        tokens = [generate_secure_token() for _ in range(100)]
        assert len(set(tokens)) == 100

    def test_token_has_sufficient_length(self):
        """Token should have sufficient entropy."""
        token = generate_secure_token(MAGIC_LINK_TOKEN_BYTES)
        # 32 bytes = ~43 base64 characters
        assert len(token) >= 40

    def test_custom_byte_length(self):
        """Should respect custom byte length."""
        token_16 = generate_secure_token(16)
        token_64 = generate_secure_token(64)
        assert len(token_16) < len(token_64)


class TestHashToken:
    """Tests for hash_token function."""

    def test_produces_sha256_hash(self):
        """Should produce a valid SHA-256 hex digest."""
        token = "test_token"
        hashed = hash_token(token)
        # SHA-256 produces 64 hex characters
        assert len(hashed) == 64
        assert all(c in "0123456789abcdef" for c in hashed)

    def test_deterministic_hashing(self):
        """Same input should produce same hash."""
        token = "my_secure_token"
        hash1 = hash_token(token)
        hash2 = hash_token(token)
        assert hash1 == hash2

    def test_different_inputs_different_hashes(self):
        """Different inputs should produce different hashes."""
        hash1 = hash_token("token1")
        hash2 = hash_token("token2")
        assert hash1 != hash2


# =============================================================================
# MagicLinkService Token Generation Tests
# =============================================================================


class TestMagicLinkServiceTokenGeneration:
    """Tests for MagicLinkService token generation methods."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_session):
        """Create MagicLinkService instance."""
        return MagicLinkService(mock_session)

    def test_generate_magic_link_token(self, service):
        """Should generate token and its hash."""
        token, token_hash = service.generate_magic_link_token()

        assert token is not None
        assert token_hash is not None
        assert len(token) >= 40
        assert len(token_hash) == 64
        assert hash_token(token) == token_hash

    def test_generate_refresh_token(self, service):
        """Should generate refresh token and its hash."""
        token, token_hash = service.generate_refresh_token()

        assert token is not None
        assert token_hash is not None
        assert hash_token(token) == token_hash


# =============================================================================
# MagicLinkService Invitation Tests
# =============================================================================


class TestMagicLinkServiceInvitation:
    """Tests for invitation creation and verification."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_session):
        """Create MagicLinkService instance with mocked repos."""
        svc = MagicLinkService(mock_session)
        svc.invitation_repo = AsyncMock()
        svc.session_repo = AsyncMock()
        return svc

    @pytest.fixture
    def sample_invitation(self):
        """Create sample invitation for testing."""
        invitation = MagicMock()
        invitation.id = uuid4()
        invitation.tenant_id = uuid4()
        invitation.connection_id = uuid4()
        invitation.email = "client@example.com"
        invitation.status = InvitationStatus.SENT.value
        invitation.expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        return invitation

    async def test_create_invitation_success(self, service):
        """Should create invitation with magic link token."""
        tenant_id = uuid4()
        connection_id = uuid4()
        email = "client@example.com"
        invited_by = uuid4()

        # Mock no existing invitation
        service.invitation_repo.get_pending_by_connection.return_value = None
        service.invitation_repo.create.return_value = MagicMock(
            id=uuid4(),
            tenant_id=tenant_id,
            connection_id=connection_id,
            email=email,
        )

        invitation, token = await service.create_invitation(
            tenant_id=tenant_id,
            connection_id=connection_id,
            email=email,
            invited_by=invited_by,
        )

        assert invitation is not None
        assert token is not None
        assert len(token) >= 40
        service.invitation_repo.create.assert_called_once()

    async def test_create_invitation_expires_existing(self, service, sample_invitation):
        """Should expire existing pending invitation."""
        # Mock existing pending invitation
        service.invitation_repo.get_pending_by_connection.return_value = sample_invitation
        service.invitation_repo.update.return_value = sample_invitation
        service.invitation_repo.create.return_value = MagicMock()

        await service.create_invitation(
            tenant_id=sample_invitation.tenant_id,
            connection_id=sample_invitation.connection_id,
            email="new@example.com",
            invited_by=uuid4(),
        )

        # Should have expired the old invitation
        service.invitation_repo.update.assert_called()
        call_args = service.invitation_repo.update.call_args
        assert call_args[0][0] == sample_invitation.id
        assert call_args[0][1]["status"] == InvitationStatus.EXPIRED.value

    async def test_verify_magic_link_token_success(self, service, sample_invitation):
        """Should verify valid token and return invitation."""
        token = generate_secure_token()
        token_hash = hash_token(token)
        sample_invitation.token_hash = token_hash

        service.invitation_repo.get_by_token_hash.return_value = sample_invitation

        result = await service.verify_magic_link_token(token)

        assert result == sample_invitation
        service.invitation_repo.get_by_token_hash.assert_called_once_with(token_hash)

    async def test_verify_magic_link_token_invalid_format(self, service):
        """Should reject tokens with invalid format."""
        with pytest.raises(InvitationInvalidTokenError):
            await service.verify_magic_link_token("short")

    async def test_verify_magic_link_token_not_found(self, service):
        """Should reject unknown tokens."""
        service.invitation_repo.get_by_token_hash.return_value = None

        with pytest.raises(InvitationNotFoundError):
            await service.verify_magic_link_token(generate_secure_token())

    async def test_verify_magic_link_token_expired(self, service, sample_invitation):
        """Should reject expired invitations."""
        sample_invitation.status = InvitationStatus.SENT.value
        sample_invitation.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        service.invitation_repo.get_by_token_hash.return_value = sample_invitation
        service.invitation_repo.update.return_value = sample_invitation

        with pytest.raises(InvitationExpiredError):
            await service.verify_magic_link_token(generate_secure_token())

    async def test_verify_magic_link_token_already_accepted(self, service, sample_invitation):
        """Should reject already-used invitations."""
        sample_invitation.status = InvitationStatus.ACCEPTED.value
        service.invitation_repo.get_by_token_hash.return_value = sample_invitation

        with pytest.raises(InvitationAlreadyAcceptedError):
            await service.verify_magic_link_token(generate_secure_token())


# =============================================================================
# MagicLinkService Session Tests
# =============================================================================


class TestMagicLinkServiceSession:
    """Tests for session management."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_session):
        """Create MagicLinkService instance with mocked repos."""
        with patch("app.modules.portal.auth.magic_link.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                security=MagicMock(
                    secret_key=MagicMock(
                        get_secret_value=lambda: "test-secret-key-32chars-minimum!"
                    ),
                    algorithm="HS256",
                ),
                frontend_url="http://localhost:3000",
            )
            svc = MagicLinkService(mock_session)
            svc.invitation_repo = AsyncMock()
            svc.session_repo = AsyncMock()
            return svc

    @pytest.fixture
    def sample_session(self):
        """Create sample session for testing."""
        session = MagicMock()
        session.id = uuid4()
        session.connection_id = uuid4()
        session.tenant_id = uuid4()
        session.revoked = False
        session.expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        return session

    async def test_create_session_success(self, service):
        """Should create session with token pair."""
        connection_id = uuid4()
        tenant_id = uuid4()

        service.session_repo.create.return_value = MagicMock(
            id=uuid4(),
            connection_id=connection_id,
            tenant_id=tenant_id,
        )

        session, tokens = await service.create_session(
            connection_id=connection_id,
            tenant_id=tenant_id,
        )

        assert session is not None
        assert tokens.access_token is not None
        assert tokens.refresh_token is not None
        assert tokens.access_expires_at > datetime.now(timezone.utc)
        service.session_repo.create.assert_called_once()

    def test_create_session_tokens(self, service):
        """Should create valid JWT tokens."""
        connection_id = uuid4()
        tenant_id = uuid4()
        refresh_token = generate_secure_token()
        expires_at = datetime.now(timezone.utc) + timedelta(days=30)

        tokens = service.create_session_tokens(
            connection_id=connection_id,
            tenant_id=tenant_id,
            session_id=uuid4(),
            refresh_token=refresh_token,
            session_expires_at=expires_at,
        )

        assert tokens.access_token.count(".") == 2  # JWT format
        assert tokens.refresh_token == refresh_token
        assert tokens.access_expires_at > datetime.now(timezone.utc)

    async def test_refresh_session_success(self, service, sample_session):
        """Should refresh session with new access token."""
        refresh_token = generate_secure_token()
        token_hash = hash_token(refresh_token)
        sample_session.refresh_token_hash = token_hash

        service.session_repo.get_by_refresh_token_hash.return_value = sample_session
        service.session_repo.update.return_value = sample_session

        tokens = await service.refresh_session(refresh_token)

        assert tokens.access_token is not None
        assert tokens.refresh_token == refresh_token
        service.session_repo.update.assert_called_once()

    async def test_refresh_session_invalid_token(self, service):
        """Should reject invalid refresh token."""
        service.session_repo.get_by_refresh_token_hash.return_value = None

        with pytest.raises(PortalAuthenticationError):
            await service.refresh_session(generate_secure_token())

    async def test_refresh_session_revoked(self, service, sample_session):
        """Should reject revoked session."""
        sample_session.revoked = True
        sample_session.revoke_reason = "User logged out"
        service.session_repo.get_by_refresh_token_hash.return_value = sample_session

        with pytest.raises(PortalSessionRevokedError):
            await service.refresh_session(generate_secure_token())

    async def test_refresh_session_expired(self, service, sample_session):
        """Should reject expired session."""
        sample_session.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        service.session_repo.get_by_refresh_token_hash.return_value = sample_session

        with pytest.raises(PortalSessionExpiredError):
            await service.refresh_session(generate_secure_token())

    async def test_revoke_session(self, service, sample_session):
        """Should revoke session."""
        service.session_repo.revoke.return_value = sample_session

        result = await service.revoke_session(sample_session.id, "User logout")

        assert result is True
        service.session_repo.revoke.assert_called_once_with(sample_session.id, "User logout")

    async def test_revoke_all_sessions(self, service):
        """Should revoke all sessions for connection."""
        connection_id = uuid4()
        service.session_repo.revoke_all_for_connection.return_value = 3

        count = await service.revoke_all_sessions(connection_id)

        assert count == 3
        service.session_repo.revoke_all_for_connection.assert_called_once()


# =============================================================================
# MagicLinkService URL Tests
# =============================================================================


class TestMagicLinkServiceUrl:
    """Tests for URL generation."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_session):
        """Create MagicLinkService instance."""
        with patch("app.modules.portal.auth.magic_link.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                security=MagicMock(
                    secret_key=MagicMock(get_secret_value=lambda: "test-secret"),
                    algorithm="HS256",
                ),
                frontend_url="https://app.clairo.com",
            )
            return MagicLinkService(mock_session)

    def test_build_magic_link_url(self, service):
        """Should build complete magic link URL."""
        token = "test_token_abc123"
        url = service.build_magic_link_url(token)

        assert url == "https://app.clairo.com/portal/verify?token=test_token_abc123"

    def test_build_magic_link_url_custom_base(self, service):
        """Should use custom base URL when provided."""
        token = "test_token"
        url = service.build_magic_link_url(token, base_url="https://custom.example.com")

        assert url == "https://custom.example.com/portal/verify?token=test_token"
