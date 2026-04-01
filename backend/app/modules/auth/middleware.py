"""Authentication and tenant middleware.

This module provides:
- JWTMiddleware: Validates JWT tokens from Authorization header
- TenantMiddleware: Sets tenant context for RLS enforcement

Middleware execution order (bottom to top in add_middleware):
1. JWTMiddleware validates token and extracts claims
2. TenantMiddleware sets PostgreSQL session variable for RLS

Usage:
    from app.modules.auth.middleware import JWTMiddleware, TenantMiddleware

    app.add_middleware(TenantMiddleware)
    app.add_middleware(JWTMiddleware, clerk_client=clerk_client)
"""

import json

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.exceptions import AuthenticationError
from app.core.logging import get_logger
from app.core.tenant_context import TenantContext

from .clerk import ClerkClient, ClerkTokenPayload

logger = get_logger(__name__)


# Paths that don't require authentication
DEFAULT_EXCLUDE_PATHS = [
    "/health",
    "/healthz",
    "/ready",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/auth/webhook",  # Clerk webhooks
    "/api/v1/auth/invitations/token",  # Public invitation lookup
    "/api/v1/admin/knowledge",  # Knowledge base admin endpoints (dev only - add auth later)
    "/api/v1/features/tiers",  # Public pricing tiers endpoint
    "/api/v1/public/stats",  # Public landing page stats
    "/api/v1/webhooks/stripe",  # Stripe webhooks (billing)
    "/api/v1/integrations/xero/webhooks",  # Xero webhooks (HMAC-SHA256 verified)
    # Client portal uses magic link auth, not Clerk JWT
    "/api/v1/client-portal/auth",  # Magic link verify, request-link, refresh, logout, me
    "/api/v1/client-portal/health",  # Portal health check
    "/api/v1/portal/health",  # Portal health check (accountant-facing)
    "/api/v1/portal/dashboard",  # Client portal dashboard (portal JWT)
    "/api/v1/portal/requests",  # Client portal requests (portal JWT)
    "/api/v1/portal/documents",  # Client portal documents (portal JWT)
    "/api/v1/client-portal/classify",  # Client transaction classification (portal JWT, Spec 047)
]

# Paths that require auth but not tenant context (e.g., registration, onboarding)
TENANT_OPTIONAL_PATHS = [
    "/api/v1/auth/register",
    "/api/v1/onboarding",
]


class JWTMiddleware:
    """ASGI middleware for JWT validation.

    Validates Bearer tokens from Authorization header using Clerk's JWKS.
    On success, adds the validated claims to scope["state"]["user"].
    On failure, returns 401 Unauthorized response.

    Attributes:
        app: Next ASGI application in chain.
        clerk_client: Clerk client for token validation.
        exclude_paths: Paths that bypass authentication.
    """

    def __init__(
        self,
        app: ASGIApp,
        clerk_client: ClerkClient,
        exclude_paths: list[str] | None = None,
    ) -> None:
        """Initialize the middleware.

        Args:
            app: Next ASGI application.
            clerk_client: Clerk client for token validation.
            exclude_paths: Paths that bypass authentication.
        """
        self.app = app
        self.clerk_client = clerk_client
        self.exclude_paths = exclude_paths or DEFAULT_EXCLUDE_PATHS

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        """Process the request.

        Args:
            scope: ASGI scope.
            receive: ASGI receive callable.
            send: ASGI send callable.
        """
        # Only process HTTP requests
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Skip OPTIONS requests (CORS preflight)
        method = scope.get("method", "")
        if method == "OPTIONS":
            await self.app(scope, receive, send)
            return

        # Check if path is excluded
        path = scope.get("path", "")
        if self._is_excluded_path(path):
            await self.app(scope, receive, send)
            return

        # Extract and validate token
        try:
            token = self._extract_token(scope)
            if token is None:
                await self._send_401_response(
                    send,
                    "Missing authentication token",
                    scope,
                )
                return

            # Validate the token
            payload = await self._validate_token(token)

            # Add user claims to scope state
            if "state" not in scope:
                scope["state"] = {}
            scope["state"]["user"] = payload

        except AuthenticationError as e:
            logger.warning(
                "Authentication failed",
                path=path,
                error=str(e.message),
            )
            await self._send_401_response(send, e.message, scope)
            return

        except Exception as e:
            logger.error(
                "Unexpected authentication error during token validation",
                path=path,
                error=str(e),
            )
            await self._send_401_response(send, "Authentication failed", scope)
            return

        # Continue to next middleware/app (outside try-except to not catch downstream errors)
        await self.app(scope, receive, send)

    def _is_excluded_path(self, path: str) -> bool:
        """Check if path is excluded from authentication.

        Args:
            path: Request path.

        Returns:
            True if path is excluded.
        """
        for excluded in self.exclude_paths:
            if path == excluded or path.startswith(excluded + "/"):
                return True
        return False

    def _extract_token(self, scope: Scope) -> str | None:
        """Extract Bearer token from Authorization header or query parameter.

        Checks the Authorization header first (Bearer scheme). Falls back to
        the ``token`` query parameter for SSE connections where the browser's
        EventSource API cannot send custom headers.

        Args:
            scope: ASGI scope.

        Returns:
            Token string or None if not found.
        """
        # 1. Try Authorization header first (preferred)
        headers = scope.get("headers", [])
        for name, value in headers:
            if name.lower() == b"authorization":
                auth_value = value.decode("utf-8")
                if auth_value.startswith("Bearer "):
                    return auth_value[7:]

        # 2. Fallback: check for token query parameter (SSE / EventSource)
        query_string = scope.get("query_string", b"").decode("utf-8")
        if query_string:
            from urllib.parse import parse_qs

            params = parse_qs(query_string)
            token_values = params.get("token")
            if token_values:
                return token_values[0]

        return None

    async def _validate_token(self, token: str) -> ClerkTokenPayload:
        """Validate token using Clerk client.

        Args:
            token: JWT token string.

        Returns:
            Validated token payload.

        Raises:
            AuthenticationError: If token is invalid.
        """
        return await self.clerk_client.validate_token(token)

    async def _send_401_response(
        self,
        send: Send,
        message: str,
        scope: Scope | None = None,
    ) -> None:
        """Send a 401 Unauthorized response.

        Args:
            send: ASGI send callable.
            message: Error message.
            scope: ASGI scope for extracting origin header.
        """
        body = json.dumps(
            {
                "error": {
                    "code": "AUTHENTICATION_ERROR",
                    "message": message,
                }
            }
        ).encode("utf-8")

        # Include CORS headers to allow browser to read the error response
        headers: list[tuple[bytes, bytes]] = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
            (b"access-control-allow-credentials", b"true"),
        ]

        # Get origin from request headers
        if scope:
            request_headers = dict(scope.get("headers", []))
            origin = request_headers.get(b"origin", b"").decode("utf-8")
            if origin:
                headers.append((b"access-control-allow-origin", origin.encode()))

        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": headers,
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": body,
            }
        )


class TenantMiddleware:
    """ASGI middleware for tenant context management.

    Sets the tenant context from JWT claims for RLS enforcement.
    The tenant ID is stored in a context variable that can be
    used by the database session to set PostgreSQL session variables.

    Attributes:
        app: Next ASGI application in chain.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Initialize the middleware.

        Args:
            app: Next ASGI application.
        """
        self.app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        """Process the request.

        Args:
            scope: ASGI scope.
            receive: ASGI receive callable.
            send: ASGI send callable.
        """
        # Only process HTTP requests
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Get user claims from previous middleware
        user: ClerkTokenPayload | None = scope.get("state", {}).get("user")

        # Set tenant context if available
        if user and user.tenant_id:
            TenantContext.set_current_tenant_id(user.tenant_id)
            TenantContext.set_current_user_id(user.sub)

        try:
            await self.app(scope, receive, send)
        finally:
            # Always clear context after request
            TenantContext.clear()

    def _is_tenant_optional_path(self, path: str) -> bool:
        """Check if path allows missing tenant context.

        Args:
            path: Request path.

        Returns:
            True if tenant context is optional.
        """
        for optional in TENANT_OPTIONAL_PATHS:
            if path == optional or path.startswith(optional + "/"):
                return True
        return False


def get_current_user_dependency():
    """FastAPI dependency for getting current user from request state.

    This is a factory function that returns a dependency callable.

    Returns:
        Dependency function.
    """
    from fastapi import HTTPException, Request, status

    async def get_current_user(request: Request) -> ClerkTokenPayload:
        """Get current user from request state.

        Args:
            request: FastAPI request object.

        Returns:
            Validated token payload.

        Raises:
            HTTPException: If user is not authenticated.
        """
        user = getattr(request.state, "user", None)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )
        return user

    return get_current_user


def get_current_tenant_dependency():
    """FastAPI dependency for getting current tenant ID.

    Returns:
        Dependency function.
    """
    import uuid

    from fastapi import HTTPException, Request, status

    async def get_current_tenant(request: Request) -> uuid.UUID:
        """Get current tenant ID from request state.

        Args:
            request: FastAPI request object.

        Returns:
            Tenant UUID.

        Raises:
            HTTPException: If tenant context is not set.
        """
        user = getattr(request.state, "user", None)
        if user is None or user.tenant_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant context required",
            )
        return user.tenant_id

    return get_current_tenant


# Create dependency instances for convenience
get_current_user = get_current_user_dependency()
get_current_tenant = get_current_tenant_dependency()
