"""Unit tests for TenantContext utility.

Tests cover:
- Context isolation between concurrent contexts
- Proper cleanup on context exit
- DB session variable setting
- Nested context handling
"""

import asyncio
import uuid
from unittest.mock import AsyncMock

import pytest

from app.core.tenant_context import (
    TenantContext,
    require_tenant_context,
    tenant_scope,
)


class TestTenantContext:
    """Tests for TenantContext static methods."""

    def test_get_current_tenant_id_default_none(self) -> None:
        """Default tenant ID should be None."""
        TenantContext.clear()
        assert TenantContext.get_current_tenant_id() is None

    def test_set_and_get_tenant_id(self) -> None:
        """Setting tenant ID should be retrievable."""
        tenant_id = uuid.uuid4()
        TenantContext.set_current_tenant_id(tenant_id)

        assert TenantContext.get_current_tenant_id() == tenant_id

        # Cleanup
        TenantContext.clear()

    def test_clear_removes_tenant_id(self) -> None:
        """Clear should remove the tenant ID."""
        tenant_id = uuid.uuid4()
        TenantContext.set_current_tenant_id(tenant_id)
        TenantContext.clear()

        assert TenantContext.get_current_tenant_id() is None

    def test_is_set_when_tenant_set(self) -> None:
        """is_set should return True when tenant is set."""
        tenant_id = uuid.uuid4()
        TenantContext.set_current_tenant_id(tenant_id)

        assert TenantContext.is_set() is True

        TenantContext.clear()

    def test_is_set_when_cleared(self) -> None:
        """is_set should return False when cleared."""
        TenantContext.clear()
        assert TenantContext.is_set() is False

    def test_request_id_management(self) -> None:
        """Request ID should be settable and retrievable."""
        request_id = uuid.uuid4()
        TenantContext.set_current_request_id(request_id)

        assert TenantContext.get_current_request_id() == request_id

        TenantContext.clear()
        assert TenantContext.get_current_request_id() is None


class TestTenantContextDBOperations:
    """Tests for TenantContext database operations."""

    @pytest.mark.asyncio
    async def test_set_db_context(self) -> None:
        """set_db_context should execute SET statement."""
        session = AsyncMock()
        tenant_id = uuid.uuid4()

        await TenantContext.set_db_context(session, tenant_id)

        session.execute.assert_called_once()
        call_args = session.execute.call_args
        # Check that the SQL contains the tenant ID
        sql_text = str(call_args[0][0])
        assert "SET app.current_tenant_id" in sql_text
        assert str(tenant_id) in sql_text

    @pytest.mark.asyncio
    async def test_clear_db_context(self) -> None:
        """clear_db_context should execute SET statement with empty value."""
        session = AsyncMock()

        await TenantContext.clear_db_context(session)

        session.execute.assert_called_once()
        call_args = session.execute.call_args
        sql_text = str(call_args[0][0])
        assert "SET app.current_tenant_id" in sql_text


class TestTenantScope:
    """Tests for tenant_scope context manager."""

    @pytest.mark.asyncio
    async def test_tenant_scope_sets_context(self) -> None:
        """tenant_scope should set both Python and DB context."""
        session = AsyncMock()
        tenant_id = uuid.uuid4()

        TenantContext.clear()

        async with tenant_scope(session, tenant_id):
            # Inside scope, tenant should be set
            assert TenantContext.get_current_tenant_id() == tenant_id

        # After scope, should be cleared
        assert TenantContext.get_current_tenant_id() is None

    @pytest.mark.asyncio
    async def test_tenant_scope_clears_on_exit(self) -> None:
        """tenant_scope should clear context on normal exit."""
        session = AsyncMock()
        tenant_id = uuid.uuid4()

        TenantContext.clear()

        async with tenant_scope(session, tenant_id):
            pass

        assert TenantContext.get_current_tenant_id() is None
        # Should have called clear_db_context
        assert session.execute.call_count == 2  # set + clear

    @pytest.mark.asyncio
    async def test_tenant_scope_clears_on_exception(self) -> None:
        """tenant_scope should clear context on exception."""
        session = AsyncMock()
        tenant_id = uuid.uuid4()

        TenantContext.clear()

        with pytest.raises(ValueError):
            async with tenant_scope(session, tenant_id):
                raise ValueError("Test error")

        # Context should still be cleared
        assert TenantContext.get_current_tenant_id() is None

    @pytest.mark.asyncio
    async def test_tenant_scope_nested(self) -> None:
        """Nested tenant_scope should restore previous context."""
        session = AsyncMock()
        tenant_1 = uuid.uuid4()
        tenant_2 = uuid.uuid4()

        TenantContext.clear()

        async with tenant_scope(session, tenant_1):
            assert TenantContext.get_current_tenant_id() == tenant_1

            async with tenant_scope(session, tenant_2):
                assert TenantContext.get_current_tenant_id() == tenant_2

            # Should restore tenant_1
            assert TenantContext.get_current_tenant_id() == tenant_1

        # Should be cleared
        assert TenantContext.get_current_tenant_id() is None


class TestContextIsolation:
    """Tests for context isolation between concurrent operations."""

    @pytest.mark.asyncio
    async def test_concurrent_contexts_isolated(self) -> None:
        """Concurrent async operations should have isolated contexts."""
        tenant_1 = uuid.uuid4()
        tenant_2 = uuid.uuid4()
        results: list[tuple[int, uuid.UUID | None]] = []

        async def task(task_id: int, tenant_id: uuid.UUID) -> None:
            TenantContext.set_current_tenant_id(tenant_id)
            # Simulate some async work
            await asyncio.sleep(0.01)
            # Record what we see
            results.append((task_id, TenantContext.get_current_tenant_id()))

        # Clear before test
        TenantContext.clear()

        # Run concurrent tasks
        await asyncio.gather(
            task(1, tenant_1),
            task(2, tenant_2),
        )

        # Each task should see its own tenant
        # Note: Due to contextvars, this test demonstrates isolation
        task_1_result = next(r for r in results if r[0] == 1)
        task_2_result = next(r for r in results if r[0] == 2)

        assert task_1_result[1] == tenant_1
        assert task_2_result[1] == tenant_2


class TestRequireTenantContext:
    """Tests for require_tenant_context helper."""

    def test_require_tenant_context_returns_id_when_set(self) -> None:
        """Should return tenant ID when context is set."""
        tenant_id = uuid.uuid4()
        TenantContext.set_current_tenant_id(tenant_id)

        result = require_tenant_context()

        assert result == tenant_id

        TenantContext.clear()

    def test_require_tenant_context_raises_when_not_set(self) -> None:
        """Should raise RuntimeError when context is not set."""
        TenantContext.clear()

        with pytest.raises(RuntimeError) as exc_info:
            require_tenant_context()

        assert "Tenant context is required" in str(exc_info.value)
