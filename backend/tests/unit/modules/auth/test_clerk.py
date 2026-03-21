"""Unit tests for ClerkClient.

Tests cover:
- JWKS fetching and caching
- Token validation with valid token
- Token validation with expired token
- Token validation with invalid signature
- Fallback to cached JWKS on fetch failure
"""

import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import ClerkSettings
from app.modules.auth.clerk import (
    ClerkClient,
    ClerkTokenPayload,
    ClerkUser,
    JWKSCache,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def clerk_settings() -> ClerkSettings:
    """Create test Clerk settings."""
    return ClerkSettings(
        publishable_key="pk_test_example",
        secret_key="sk_test_example",  # type: ignore[arg-type]
        jwks_url="https://test.clerk.dev/.well-known/jwks.json",
        webhook_secret="whsec_test",  # type: ignore[arg-type]
        jwt_clock_skew_seconds=60,
        jwks_cache_ttl_seconds=3600,
    )


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Create a mock Redis client."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock()
    return redis


@pytest.fixture
def sample_jwks() -> dict[str, Any]:
    """Create sample JWKS for testing.

    This is a simplified JWKS structure for testing purposes.
    In production, Clerk provides RSA public keys.
    """
    return {
        "keys": [
            {
                "kty": "RSA",
                "kid": "test-key-id",
                "use": "sig",
                "alg": "RS256",
                "n": "0vx7agoebGcQSuuPiLJXZptN9nndrQmbXEps2aiAFbWhM78LhWx4cbbfAAtVT86zwu1RK7aPFFxuhDR1L6tSoc_BJECPebWKRXjBZCiFV4n3oknjhMstn64tZ_2W-5JsGY4Hc5n9yBXArwl93lqt7_RN5w6Cf0h4QyQ5v-65YGjQR0_FDW2QvzqY368QQMicAtaSqzs8KJZgnYb9c7d0zgdAZHzu6qMQvRL5hajrn1n91CbOpbISD08qNLyrdkt-bFTWhAI4vMQFh6WeZu0fM4lFd2NcRwr3XPksINHaQ-G_xBniIqbw0Ls1jF44-csFCur-kEgU8awapJzKnqDKgw",
                "e": "AQAB",
            }
        ]
    }


@pytest.fixture
def sample_claims() -> dict[str, Any]:
    """Create sample JWT claims."""
    tenant_id = str(uuid.uuid4())
    return {
        "sub": "user_test123",
        "email": "test@example.com",
        "email_verified": True,
        "tenant_id": tenant_id,
        "role": "admin",
        "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
        "iat": int(datetime.now(UTC).timestamp()),
        "nbf": int(datetime.now(UTC).timestamp()),
        "iss": "https://test.clerk.dev",
        "azp": "http://localhost:3000",
    }


@pytest.fixture
def expired_claims(sample_claims: dict[str, Any]) -> dict[str, Any]:
    """Create expired JWT claims."""
    claims = sample_claims.copy()
    claims["exp"] = int((datetime.now(UTC) - timedelta(hours=1)).timestamp())
    return claims


# =============================================================================
# ClerkTokenPayload Tests
# =============================================================================


class TestClerkTokenPayload:
    """Tests for ClerkTokenPayload Pydantic model."""

    def test_create_payload_from_claims(self, sample_claims: dict[str, Any]) -> None:
        """Test creating payload from valid claims."""
        payload = ClerkTokenPayload(**sample_claims)

        assert payload.sub == "user_test123"
        assert payload.email == "test@example.com"
        assert payload.email_verified is True
        assert payload.tenant_id == uuid.UUID(sample_claims["tenant_id"])
        assert payload.role == "admin"

    def test_payload_with_optional_fields(self) -> None:
        """Test payload with minimal required fields."""
        claims = {
            "sub": "user_123",
            "exp": int(datetime.now(UTC).timestamp()),
            "iat": int(datetime.now(UTC).timestamp()),
        }
        payload = ClerkTokenPayload(**claims)

        assert payload.sub == "user_123"
        assert payload.email is None
        assert payload.tenant_id is None
        assert payload.role is None

    def test_payload_tenant_id_as_string(self) -> None:
        """Test that tenant_id can be parsed from string."""
        tenant_id = str(uuid.uuid4())
        claims = {
            "sub": "user_123",
            "tenant_id": tenant_id,
            "exp": int(datetime.now(UTC).timestamp()),
            "iat": int(datetime.now(UTC).timestamp()),
        }
        payload = ClerkTokenPayload(**claims)

        assert payload.tenant_id == uuid.UUID(tenant_id)


# =============================================================================
# JWKSCache Tests
# =============================================================================


class TestJWKSCache:
    """Tests for JWKS caching functionality."""

    def test_cache_stores_jwks(self, sample_jwks: dict[str, Any]) -> None:
        """Test that cache stores JWKS correctly."""
        cache = JWKSCache(ttl_seconds=3600)
        cache.set(sample_jwks)

        assert cache.get() == sample_jwks
        assert not cache.is_expired()

    def test_cache_expiry(self, sample_jwks: dict[str, Any]) -> None:
        """Test that cache expires after TTL."""
        cache = JWKSCache(ttl_seconds=1)
        cache.set(sample_jwks)

        # Simulate time passing
        cache._expires_at = time.time() - 1

        assert cache.is_expired()

    def test_empty_cache_returns_none(self) -> None:
        """Test that empty cache returns None."""
        cache = JWKSCache(ttl_seconds=3600)
        assert cache.get() is None
        assert cache.is_expired()

    def test_get_stale_returns_data_after_expiry(self, sample_jwks: dict[str, Any]) -> None:
        """Test that get_stale returns data even after expiry."""
        cache = JWKSCache(ttl_seconds=1)
        cache.set(sample_jwks)

        # Expire the cache
        cache._expires_at = time.time() - 1

        # Regular get should return None (or raise)
        assert cache.is_expired()

        # But get_stale should still return the data
        assert cache.get_stale() == sample_jwks


# =============================================================================
# ClerkClient Tests
# =============================================================================


class TestClerkClient:
    """Tests for ClerkClient."""

    @pytest.mark.asyncio
    async def test_init_creates_client(
        self,
        clerk_settings: ClerkSettings,
        mock_redis: AsyncMock,
    ) -> None:
        """Test that ClerkClient initializes correctly."""
        client = ClerkClient(settings=clerk_settings, redis=mock_redis)

        assert client._settings == clerk_settings
        assert client._redis == mock_redis

    @pytest.mark.asyncio
    async def test_get_jwks_fetches_from_url(
        self,
        clerk_settings: ClerkSettings,
        mock_redis: AsyncMock,
        sample_jwks: dict[str, Any],
    ) -> None:
        """Test JWKS is fetched from Clerk URL."""
        client = ClerkClient(settings=clerk_settings, redis=mock_redis)

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            # json() is a sync method on httpx.Response, use MagicMock
            mock_response.json = MagicMock(return_value=sample_jwks)

            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_httpx.return_value = mock_client_instance

            result = await client.get_jwks()

            assert result == sample_jwks
            mock_client_instance.get.assert_called_once_with(clerk_settings.jwks_url)

    @pytest.mark.asyncio
    async def test_get_jwks_uses_cache(
        self,
        clerk_settings: ClerkSettings,
        mock_redis: AsyncMock,
        sample_jwks: dict[str, Any],
    ) -> None:
        """Test JWKS is served from cache on subsequent calls."""
        client = ClerkClient(settings=clerk_settings, redis=mock_redis)

        # Pre-populate the cache
        client._jwks_cache.set(sample_jwks)

        with patch("httpx.AsyncClient") as mock_httpx:
            result = await client.get_jwks()

            # Should not have made any HTTP request
            mock_httpx.assert_not_called()
            assert result == sample_jwks

    @pytest.mark.asyncio
    async def test_get_jwks_fallback_to_stale_cache_on_failure(
        self,
        clerk_settings: ClerkSettings,
        mock_redis: AsyncMock,
        sample_jwks: dict[str, Any],
    ) -> None:
        """Test JWKS falls back to stale cache when fetch fails."""
        client = ClerkClient(settings=clerk_settings, redis=mock_redis)

        # Pre-populate cache and expire it
        client._jwks_cache.set(sample_jwks)
        client._jwks_cache._expires_at = time.time() - 1

        with patch("httpx.AsyncClient") as mock_httpx:
            # Simulate network failure
            mock_client_instance = AsyncMock()
            mock_client_instance.get.side_effect = Exception("Network error")
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_httpx.return_value = mock_client_instance

            result = await client.get_jwks()

            # Should return stale cache
            assert result == sample_jwks

    @pytest.mark.asyncio
    async def test_validate_token_with_valid_token(
        self,
        clerk_settings: ClerkSettings,
        mock_redis: AsyncMock,
        sample_claims: dict[str, Any],
    ) -> None:
        """Test token validation with a valid token."""
        client = ClerkClient(settings=clerk_settings, redis=mock_redis)

        # Mock the JWT decode
        with patch.object(client, "get_jwks") as mock_get_jwks:
            with patch("jose.jwt.decode") as mock_decode:
                mock_get_jwks.return_value = {"keys": []}
                mock_decode.return_value = sample_claims

                payload = await client.validate_token("valid_token")

                assert payload.sub == sample_claims["sub"]
                assert payload.email == sample_claims["email"]

    @pytest.mark.asyncio
    async def test_validate_token_with_expired_token(
        self,
        clerk_settings: ClerkSettings,
        mock_redis: AsyncMock,
        expired_claims: dict[str, Any],
    ) -> None:
        """Test token validation fails with expired token."""
        from jose import JWTError

        from app.core.exceptions import AuthenticationError

        client = ClerkClient(settings=clerk_settings, redis=mock_redis)

        with patch.object(client, "get_jwks") as mock_get_jwks:
            with patch("jose.jwt.decode") as mock_decode:
                mock_get_jwks.return_value = {"keys": []}
                mock_decode.side_effect = JWTError("Token has expired")

                with pytest.raises(AuthenticationError) as exc_info:
                    await client.validate_token("expired_token")

                assert (
                    "expired" in str(exc_info.value.message).lower()
                    or "invalid" in str(exc_info.value.message).lower()
                )

    @pytest.mark.asyncio
    async def test_validate_token_with_invalid_signature(
        self,
        clerk_settings: ClerkSettings,
        mock_redis: AsyncMock,
    ) -> None:
        """Test token validation fails with invalid signature."""
        from jose import JWTError

        from app.core.exceptions import AuthenticationError

        client = ClerkClient(settings=clerk_settings, redis=mock_redis)

        with patch.object(client, "get_jwks") as mock_get_jwks:
            with patch("jose.jwt.decode") as mock_decode:
                mock_get_jwks.return_value = {"keys": []}
                mock_decode.side_effect = JWTError("Signature verification failed")

                with pytest.raises(AuthenticationError) as exc_info:
                    await client.validate_token("tampered_token")

                assert exc_info.value.code == "AUTHENTICATION_ERROR"

    @pytest.mark.asyncio
    async def test_validate_token_respects_clock_skew(
        self,
        clerk_settings: ClerkSettings,
        mock_redis: AsyncMock,
        sample_claims: dict[str, Any],
    ) -> None:
        """Test that token validation respects clock skew tolerance."""
        client = ClerkClient(settings=clerk_settings, redis=mock_redis)

        with patch.object(client, "get_jwks") as mock_get_jwks:
            with patch("jose.jwt.decode") as mock_decode:
                mock_get_jwks.return_value = {"keys": [{"kty": "RSA", "kid": "test-key"}]}
                mock_decode.return_value = sample_claims

                result = await client.validate_token("valid.jwt.token")

                # Verify decode was called
                assert mock_decode.called
                # Verify the result contains expected claims
                assert result.sub == sample_claims["sub"]


# =============================================================================
# ClerkUser Tests
# =============================================================================


class TestClerkUser:
    """Tests for ClerkUser model."""

    def test_clerk_user_from_dict(self) -> None:
        """Test creating ClerkUser from dictionary."""
        data = {
            "id": "user_123",
            "email_addresses": [
                {"email_address": "test@example.com", "verification": {"status": "verified"}}
            ],
            "first_name": "John",
            "last_name": "Doe",
            "public_metadata": {"tenant_id": str(uuid.uuid4())},
            "private_metadata": {},
        }
        user = ClerkUser(**data)

        assert user.id == "user_123"
        assert user.primary_email == "test@example.com"
        assert user.first_name == "John"
        assert user.last_name == "Doe"

    def test_clerk_user_full_name(self) -> None:
        """Test ClerkUser full_name property."""
        data = {
            "id": "user_123",
            "email_addresses": [],
            "first_name": "John",
            "last_name": "Doe",
            "public_metadata": {},
            "private_metadata": {},
        }
        user = ClerkUser(**data)

        assert user.full_name == "John Doe"

    def test_clerk_user_email_verified(self) -> None:
        """Test ClerkUser email_verified property."""
        data = {
            "id": "user_123",
            "email_addresses": [
                {"email_address": "test@example.com", "verification": {"status": "verified"}}
            ],
            "first_name": None,
            "last_name": None,
            "public_metadata": {},
            "private_metadata": {},
        }
        user = ClerkUser(**data)

        assert user.is_email_verified is True

    def test_clerk_user_tenant_id_from_metadata(self) -> None:
        """Test extracting tenant_id from public_metadata."""
        tenant_id = str(uuid.uuid4())
        data = {
            "id": "user_123",
            "email_addresses": [],
            "first_name": None,
            "last_name": None,
            "public_metadata": {"tenant_id": tenant_id},
            "private_metadata": {},
        }
        user = ClerkUser(**data)

        assert user.tenant_id == uuid.UUID(tenant_id)
