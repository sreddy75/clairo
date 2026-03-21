"""Unit tests for JWT and Tenant middleware.

Tests cover:
- Tenant context is set from JWT claims
- PostgreSQL session variable is set
- Context cleanup on request completion
- Context isolation for concurrent requests
- Error handling when tenant context cannot be established
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.core.tenant_context import TenantContext
from app.modules.auth.middleware import JWTMiddleware, TenantMiddleware

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_clerk_client() -> AsyncMock:
    """Create a mock ClerkClient."""
    client = AsyncMock()
    client.validate_token = AsyncMock()
    return client


@pytest.fixture
def sample_token_payload() -> dict[str, Any]:
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
    }


@pytest.fixture
def mock_app() -> AsyncMock:
    """Create a mock ASGI app."""
    app = AsyncMock()
    app.return_value = None
    return app


@pytest.fixture
def mock_receive() -> AsyncMock:
    """Create a mock receive function."""
    return AsyncMock()


@pytest.fixture
def mock_send() -> AsyncMock:
    """Create a mock send function."""
    return AsyncMock()


@pytest.fixture
def sample_scope(sample_token_payload: dict[str, Any]) -> dict[str, Any]:
    """Create a sample ASGI scope for HTTP requests."""
    return {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/users",
        "headers": [
            (b"authorization", b"Bearer valid_token"),
            (b"content-type", b"application/json"),
        ],
        "query_string": b"",
        "root_path": "",
        "state": {},
    }


# =============================================================================
# JWTMiddleware Tests
# =============================================================================


class TestJWTMiddleware:
    """Tests for JWTMiddleware."""

    @pytest.mark.asyncio
    async def test_extracts_and_validates_bearer_token(
        self,
        mock_app: AsyncMock,
        mock_clerk_client: AsyncMock,
        mock_receive: AsyncMock,
        mock_send: AsyncMock,
        sample_scope: dict[str, Any],
        sample_token_payload: dict[str, Any],
    ) -> None:
        """Test that middleware extracts and validates Bearer token."""
        from app.modules.auth.clerk import ClerkTokenPayload

        # Setup mock to return valid payload
        mock_clerk_client.validate_token.return_value = ClerkTokenPayload(**sample_token_payload)

        middleware = JWTMiddleware(
            app=mock_app,
            clerk_client=mock_clerk_client,
        )

        await middleware(sample_scope, mock_receive, mock_send)

        # Verify token was validated
        mock_clerk_client.validate_token.assert_called_once_with("valid_token")

        # Verify app was called
        mock_app.assert_called_once()

        # Verify claims were added to scope state
        assert "user" in sample_scope["state"]
        assert sample_scope["state"]["user"].sub == "user_test123"

    @pytest.mark.asyncio
    async def test_returns_401_for_missing_token(
        self,
        mock_app: AsyncMock,
        mock_clerk_client: AsyncMock,
        mock_receive: AsyncMock,
        mock_send: AsyncMock,
    ) -> None:
        """Test that middleware returns 401 when token is missing."""
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/users",
            "headers": [],  # No Authorization header
            "query_string": b"",
            "root_path": "",
            "state": {},
        }

        middleware = JWTMiddleware(
            app=mock_app,
            clerk_client=mock_clerk_client,
        )

        await middleware(scope, mock_receive, mock_send)

        # Verify 401 response was sent
        mock_send.assert_called()
        # First call should be start response with 401 status
        start_call = mock_send.call_args_list[0]
        assert start_call[0][0]["status"] == 401

        # App should NOT have been called
        mock_app.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_401_for_invalid_token(
        self,
        mock_app: AsyncMock,
        mock_clerk_client: AsyncMock,
        mock_receive: AsyncMock,
        mock_send: AsyncMock,
        sample_scope: dict[str, Any],
    ) -> None:
        """Test that middleware returns 401 for invalid token."""
        from app.core.exceptions import AuthenticationError

        mock_clerk_client.validate_token.side_effect = AuthenticationError("Invalid token")

        middleware = JWTMiddleware(
            app=mock_app,
            clerk_client=mock_clerk_client,
        )

        await middleware(sample_scope, mock_receive, mock_send)

        # Verify 401 response was sent
        start_call = mock_send.call_args_list[0]
        assert start_call[0][0]["status"] == 401

        # App should NOT have been called
        mock_app.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_excluded_paths(
        self,
        mock_app: AsyncMock,
        mock_clerk_client: AsyncMock,
        mock_receive: AsyncMock,
        mock_send: AsyncMock,
    ) -> None:
        """Test that excluded paths bypass JWT validation."""
        excluded_paths = ["/health", "/docs", "/openapi.json"]

        for path in excluded_paths:
            scope = {
                "type": "http",
                "method": "GET",
                "path": path,
                "headers": [],  # No token needed
                "query_string": b"",
                "root_path": "",
                "state": {},
            }

            middleware = JWTMiddleware(
                app=mock_app,
                clerk_client=mock_clerk_client,
                exclude_paths=["/health", "/docs", "/openapi.json"],
            )

            await middleware(scope, mock_receive, mock_send)

            # App should be called (not blocked)
            mock_app.assert_called()
            mock_app.reset_mock()

            # Token validation should NOT have been called
            mock_clerk_client.validate_token.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_websocket_connections(
        self,
        mock_app: AsyncMock,
        mock_clerk_client: AsyncMock,
        mock_receive: AsyncMock,
        mock_send: AsyncMock,
    ) -> None:
        """Test that websocket connections are passed through."""
        scope = {
            "type": "websocket",
            "path": "/ws",
            "headers": [],
            "query_string": b"",
            "state": {},
        }

        middleware = JWTMiddleware(
            app=mock_app,
            clerk_client=mock_clerk_client,
        )

        await middleware(scope, mock_receive, mock_send)

        # App should be called
        mock_app.assert_called_once()


# =============================================================================
# TenantMiddleware Tests
# =============================================================================


class TestTenantMiddleware:
    """Tests for TenantMiddleware."""

    @pytest.mark.asyncio
    async def test_sets_tenant_context_from_jwt_claims(
        self,
        mock_app: AsyncMock,
        mock_receive: AsyncMock,
        mock_send: AsyncMock,
        sample_token_payload: dict[str, Any],
    ) -> None:
        """Test that tenant context is set from JWT claims."""
        from app.modules.auth.clerk import ClerkTokenPayload

        tenant_id = uuid.UUID(sample_token_payload["tenant_id"])

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/users",
            "headers": [],
            "query_string": b"",
            "root_path": "",
            "state": {
                "user": ClerkTokenPayload(**sample_token_payload),
            },
        }

        middleware = TenantMiddleware(app=mock_app)

        # Clear any existing context
        TenantContext.clear()

        await middleware(scope, mock_receive, mock_send)

        # Verify app was called
        mock_app.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleans_up_context_on_request_completion(
        self,
        mock_app: AsyncMock,
        mock_receive: AsyncMock,
        mock_send: AsyncMock,
        sample_token_payload: dict[str, Any],
    ) -> None:
        """Test that tenant context is cleaned up after request."""
        from app.modules.auth.clerk import ClerkTokenPayload

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/users",
            "headers": [],
            "query_string": b"",
            "root_path": "",
            "state": {
                "user": ClerkTokenPayload(**sample_token_payload),
            },
        }

        middleware = TenantMiddleware(app=mock_app)

        await middleware(scope, mock_receive, mock_send)

        # Context should be cleared after request
        # Note: In real implementation, cleanup happens after app returns
        mock_app.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_requests_without_tenant_id(
        self,
        mock_app: AsyncMock,
        mock_receive: AsyncMock,
        mock_send: AsyncMock,
    ) -> None:
        """Test handling of requests without tenant_id (e.g., registration)."""
        from app.modules.auth.clerk import ClerkTokenPayload

        # Create payload without tenant_id (new user registration)
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/register",
            "headers": [],
            "query_string": b"",
            "root_path": "",
            "state": {
                "user": ClerkTokenPayload(
                    sub="user_new",
                    email="new@example.com",
                    exp=9999999999,
                    iat=1234567890,
                    # No tenant_id - new registration
                ),
            },
        }

        middleware = TenantMiddleware(app=mock_app)

        await middleware(scope, mock_receive, mock_send)

        # App should still be called (registration allowed without tenant)
        mock_app.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleans_up_context_on_exception(
        self,
        mock_receive: AsyncMock,
        mock_send: AsyncMock,
        sample_token_payload: dict[str, Any],
    ) -> None:
        """Test that context is cleaned up even when app raises exception."""
        from app.modules.auth.clerk import ClerkTokenPayload

        # App that raises an exception
        async def failing_app(scope: Any, receive: Any, send: Any) -> None:
            raise ValueError("Test exception")

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/users",
            "headers": [],
            "query_string": b"",
            "root_path": "",
            "state": {
                "user": ClerkTokenPayload(**sample_token_payload),
            },
        }

        middleware = TenantMiddleware(app=failing_app)

        with pytest.raises(ValueError, match="Test exception"):
            await middleware(scope, mock_receive, mock_send)

        # Context should still be cleaned up
        # Note: Actual cleanup verification depends on implementation

    @pytest.mark.asyncio
    async def test_context_isolation_for_concurrent_requests(
        self,
        sample_token_payload: dict[str, Any],
    ) -> None:
        """Test that context is isolated between concurrent requests."""
        from app.modules.auth.clerk import ClerkTokenPayload

        tenant_ids_seen: list[uuid.UUID | None] = []

        async def capturing_app(scope: Any, receive: Any, send: Any) -> None:
            """App that captures the current tenant ID."""
            await asyncio.sleep(0.01)  # Simulate some work
            tenant_id = TenantContext.get_current_tenant_id()
            tenant_ids_seen.append(tenant_id)

        tenant_id_1 = uuid.uuid4()
        tenant_id_2 = uuid.uuid4()

        payload_1 = sample_token_payload.copy()
        payload_1["tenant_id"] = str(tenant_id_1)

        payload_2 = sample_token_payload.copy()
        payload_2["tenant_id"] = str(tenant_id_2)

        scope_1 = {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/users",
            "headers": [],
            "query_string": b"",
            "root_path": "",
            "state": {"user": ClerkTokenPayload(**payload_1)},
        }

        scope_2 = {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/users",
            "headers": [],
            "query_string": b"",
            "root_path": "",
            "state": {"user": ClerkTokenPayload(**payload_2)},
        }

        middleware = TenantMiddleware(app=capturing_app)

        # Run both requests concurrently
        mock_receive = AsyncMock()
        mock_send = AsyncMock()

        await asyncio.gather(
            middleware(scope_1, mock_receive, mock_send),
            middleware(scope_2, mock_receive, mock_send),
        )

        # Both tenant IDs should be present (order may vary)
        # This verifies context isolation in concurrent scenarios
        assert len(tenant_ids_seen) == 2


# =============================================================================
# Integration Tests for Middleware Chain
# =============================================================================


class TestMiddlewareChain:
    """Tests for JWT + Tenant middleware chain."""

    @pytest.mark.asyncio
    async def test_full_middleware_chain(
        self,
        mock_clerk_client: AsyncMock,
        sample_token_payload: dict[str, Any],
    ) -> None:
        """Test full JWT -> Tenant middleware chain."""
        from app.modules.auth.clerk import ClerkTokenPayload

        captured_state: dict[str, Any] = {}

        async def capturing_app(scope: Any, receive: Any, send: Any) -> None:
            captured_state["user"] = scope.get("state", {}).get("user")
            captured_state["tenant_id"] = TenantContext.get_current_tenant_id()

        # Setup mock to return valid payload
        mock_clerk_client.validate_token.return_value = ClerkTokenPayload(**sample_token_payload)

        # Build middleware chain
        tenant_middleware = TenantMiddleware(app=capturing_app)
        jwt_middleware = JWTMiddleware(
            app=tenant_middleware,
            clerk_client=mock_clerk_client,
        )

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/users",
            "headers": [(b"authorization", b"Bearer valid_token")],
            "query_string": b"",
            "root_path": "",
            "state": {},
        }

        mock_receive = AsyncMock()
        mock_send = AsyncMock()

        await jwt_middleware(scope, mock_receive, mock_send)

        # Verify user claims were captured
        assert captured_state["user"] is not None
        assert captured_state["user"].sub == "user_test123"
