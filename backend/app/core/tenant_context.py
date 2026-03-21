"""Tenant context management for multi-tenancy.

This module provides utilities for managing tenant context in a request-scoped
manner. It uses Python's contextvars for request isolation and integrates
with PostgreSQL session variables for RLS enforcement.

Usage:
    # Set tenant context for current request
    TenantContext.set_current_tenant_id(tenant_id)

    # Get current tenant ID
    tenant_id = TenantContext.get_current_tenant_id()

    # Use async context manager
    async with tenant_scope(session, tenant_id):
        # All queries in this block are scoped to tenant_id
        result = await session.execute(select(User))

The tenant context integrates with PostgreSQL RLS policies by setting
the session variable `app.current_tenant_id` which is used in RLS
policy conditions.
"""

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from contextvars import ContextVar

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Context variable for storing the current tenant ID
# This provides request-level isolation for concurrent requests
_current_tenant_id: ContextVar[uuid.UUID | None] = ContextVar("current_tenant_id", default=None)

# Context variable for storing the current user ID (Clerk ID)
_current_user_id: ContextVar[str | None] = ContextVar("current_user_id", default=None)

# Context variable for storing the current request ID (for correlation)
_current_request_id: ContextVar[uuid.UUID | None] = ContextVar("current_request_id", default=None)


class TenantContext:
    """Manages tenant context for multi-tenancy.

    This class provides static methods for getting and setting the
    current tenant context. The context is stored in a ContextVar
    which ensures isolation between concurrent requests.

    The tenant context should be set early in the request lifecycle
    (typically in middleware) and cleared at the end of the request.
    """

    @staticmethod
    def get_current_tenant_id() -> uuid.UUID | None:
        """Get the current tenant ID from context.

        Returns:
            The current tenant ID if set, None otherwise.
        """
        return _current_tenant_id.get()

    @staticmethod
    def set_current_tenant_id(tenant_id: uuid.UUID) -> None:
        """Set the current tenant ID in context.

        Args:
            tenant_id: The tenant ID to set as current.
        """
        _current_tenant_id.set(tenant_id)

    @staticmethod
    def clear() -> None:
        """Clear the current tenant context.

        Should be called at the end of each request to ensure
        proper cleanup and prevent context leakage.
        """
        _current_tenant_id.set(None)
        _current_user_id.set(None)
        _current_request_id.set(None)

    @staticmethod
    def get_current_user_id() -> str | None:
        """Get the current user ID (Clerk ID) from context.

        Returns:
            The current user ID if set, None otherwise.
        """
        return _current_user_id.get()

    @staticmethod
    def set_current_user_id(user_id: str) -> None:
        """Set the current user ID (Clerk ID) in context.

        Args:
            user_id: The Clerk user ID to set as current.
        """
        _current_user_id.set(user_id)

    @staticmethod
    def get_current_request_id() -> uuid.UUID | None:
        """Get the current request ID from context.

        Returns:
            The current request ID if set, None otherwise.
        """
        return _current_request_id.get()

    @staticmethod
    def set_current_request_id(request_id: uuid.UUID) -> None:
        """Set the current request ID in context.

        Args:
            request_id: The request ID for correlation.
        """
        _current_request_id.set(request_id)

    @staticmethod
    async def set_db_context(
        session: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> None:
        """Set the PostgreSQL session variable for RLS.

        This method sets the `app.current_tenant_id` session variable
        which is used by RLS policies to filter data by tenant.

        Args:
            session: The async database session.
            tenant_id: The tenant ID to set in the session.

        Note:
            This must be called at the start of each request before
            any queries that should be tenant-scoped.
        """
        await session.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))

    @staticmethod
    async def clear_db_context(session: AsyncSession) -> None:
        """Clear the PostgreSQL session variable.

        This method clears the `app.current_tenant_id` session variable.
        Should be called at the end of each request.

        Args:
            session: The async database session.
        """
        await session.execute(text("SET app.current_tenant_id = ''"))

    @staticmethod
    def is_set() -> bool:
        """Check if tenant context is currently set.

        Returns:
            True if a tenant ID is set, False otherwise.
        """
        return _current_tenant_id.get() is not None


@asynccontextmanager
async def tenant_scope(
    session: AsyncSession,
    tenant_id: uuid.UUID,
) -> AsyncGenerator[None, None]:
    """Async context manager for scoped tenant context.

    This context manager:
    1. Sets the tenant ID in the Python context
    2. Sets the PostgreSQL session variable for RLS
    3. Yields control for the scoped operations
    4. Clears both contexts on exit (success or failure)

    Usage:
        async with tenant_scope(session, tenant_id):
            # All queries here are scoped to tenant_id
            users = await session.execute(select(PracticeUser))

    Args:
        session: The async database session.
        tenant_id: The tenant ID to scope to.

    Yields:
        None - the context is set via side effects.

    Example:
        async with get_db_context() as session:
            async with tenant_scope(session, tenant_id):
                result = await session.execute(select(PracticeUser))
                users = result.scalars().all()
                # users contains only records from tenant_id
    """
    # Store previous context for restoration (supports nesting)
    previous_tenant_id = TenantContext.get_current_tenant_id()

    try:
        # Set the Python context
        TenantContext.set_current_tenant_id(tenant_id)

        # Set the PostgreSQL session variable
        await TenantContext.set_db_context(session, tenant_id)

        yield
    finally:
        # Restore previous context or clear
        if previous_tenant_id is not None:
            TenantContext.set_current_tenant_id(previous_tenant_id)
            await TenantContext.set_db_context(session, previous_tenant_id)
        else:
            TenantContext.clear()
            await TenantContext.clear_db_context(session)


def require_tenant_context() -> uuid.UUID:
    """Get current tenant ID or raise an error.

    This is a helper function for services that require a tenant context.
    It raises an error if no tenant context is set, ensuring fail-closed
    behavior.

    Returns:
        The current tenant ID.

    Raises:
        RuntimeError: If no tenant context is set.
    """
    tenant_id = TenantContext.get_current_tenant_id()
    if tenant_id is None:
        raise RuntimeError("Tenant context is required but not set")
    return tenant_id
