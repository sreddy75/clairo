"""Unit tests for XeroConnectionService token refresh robustness.

Feature 059: Xero Authentication Robustness & Reconnection UX.

Tests cover:
- T004: Concurrent refresh — lock winner re-reads DB; if sibling already
        refreshed (tokens fresh), skip Xero call and return immediately.
- T005: Redis-unavailable — _refresh_with_lock falls back to refresh_tokens
        when Redis.from_url raises ConnectionError or lock.acquire raises RedisError.
- T006: Retry-before-reauth — in refresh_tokens, invalid_grant from Xero triggers
        a DB re-read; if sibling propagated fresh tokens, return without needs_reauth.
- T007: Sibling propagation — after successful refresh, all siblings sharing the
        same auth_event_id receive the new tokens (including needs_reauth siblings).
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.integrations.xero.connection_service import (
    XeroConnectionNotFoundError,
    XeroConnectionService,
)
from app.modules.integrations.xero.exceptions import XeroAuthRequiredError
from app.modules.integrations.xero.models import XeroConnectionStatus
from app.modules.integrations.xero.schemas import XeroConnectionUpdate

# ===========================================================================
# Helpers
# ===========================================================================

EXPIRED_AT = datetime.now(UTC) - timedelta(minutes=1)
FRESH_AT = datetime.now(UTC) + timedelta(minutes=60)
AUTH_EVENT_ID = "evt_abc123"


def _make_connection(
    *,
    connection_id=None,
    tenant_id=None,
    auth_event_id=AUTH_EVENT_ID,
    status=XeroConnectionStatus.ACTIVE,
    token_expires_at=None,
    access_token="enc_access",
    refresh_token="enc_refresh",
    organization_name="ACME Pty Ltd",
    needs_refresh=None,
):
    conn = MagicMock()
    conn.id = connection_id or uuid4()
    conn.tenant_id = tenant_id or uuid4()
    conn.auth_event_id = auth_event_id
    conn.status = status
    conn.access_token = access_token
    conn.refresh_token = refresh_token
    conn.organization_name = organization_name
    expires = token_expires_at or EXPIRED_AT
    conn.token_expires_at = expires
    # Derive needs_refresh from expires if not explicit
    if needs_refresh is None:
        conn.needs_refresh = expires <= datetime.now(UTC) + timedelta(minutes=5)
    else:
        conn.needs_refresh = needs_refresh
    return conn


def _make_service():
    """XeroConnectionService with mocked repo, encryption, and settings."""
    settings = MagicMock()
    settings.redis.url = "redis://localhost:6379"

    with patch("app.modules.integrations.xero.connection_service.TokenEncryption") as mock_enc_cls:
        mock_enc_cls.return_value = MagicMock()
        svc = XeroConnectionService(AsyncMock(), settings)

    svc.connection_repo = AsyncMock()
    svc.encryption = MagicMock()
    svc.encryption.decrypt.return_value = "decrypted_access_token"
    svc.encryption.encrypt.return_value = "enc_new_token"
    return svc


AIOREDIS_PATCH = "app.modules.integrations.xero.connection_service.aioredis"


def _make_redis_mock(
    *, from_url_side_effect=None, lock_acquire_side_effect=None, lock_acquire_return=True
):
    """Build a fake aioredis module to patch connection_service.aioredis."""
    mock_redis_module = MagicMock()

    mock_lock = MagicMock()
    mock_lock.acquire = AsyncMock(return_value=lock_acquire_return)
    mock_lock.release = AsyncMock()
    if lock_acquire_side_effect:
        mock_lock.acquire.side_effect = lock_acquire_side_effect

    mock_redis_client = MagicMock()
    mock_redis_client.lock.return_value = mock_lock
    mock_redis_client.aclose = AsyncMock()

    if from_url_side_effect:
        mock_redis_module.from_url.side_effect = from_url_side_effect
    else:
        mock_redis_module.from_url.return_value = mock_redis_client

    return mock_redis_module, mock_lock, mock_redis_client


def _make_xero_client_patch(*, token_response=None, refresh_side_effect=None):
    """Patch XeroClient with a mock that returns a token response or raises."""
    mock_client_cls = MagicMock()
    mock_xero = MagicMock()
    mock_xero.__aenter__ = AsyncMock(return_value=mock_xero)
    mock_xero.__aexit__ = AsyncMock(return_value=False)

    if refresh_side_effect:
        mock_xero.refresh_token = AsyncMock(side_effect=refresh_side_effect)
    else:
        tr = token_response or MagicMock(access_token="new_access", refresh_token="new_refresh")
        mock_xero.refresh_token = AsyncMock(return_value=(tr, FRESH_AT))

    mock_client_cls.return_value = mock_xero
    return mock_client_cls, mock_xero


# ===========================================================================
# T004 — Concurrent refresh: lock winner skips Xero when tokens already fresh
# ===========================================================================


class TestConcurrentRefreshLockBehavior:
    """After acquiring the grant lock, re-read DB.

    If a sibling already refreshed (tokens no longer stale), skip the Xero
    call and return the connection immediately — exactly 0 Xero API calls
    for the second task.
    """

    @pytest.mark.asyncio
    async def test_no_xero_call_when_tokens_fresh_after_lock_acquired(self) -> None:
        """Lock acquired, re-read shows fresh tokens → return without calling Xero.

        Call sequence:
          1. ensure_valid_token reads conn (expired → needs_refresh)
          2. _refresh_with_lock reads conn at start (to get lock key)
          3. _refresh_with_lock re-reads conn after lock acquired → fresh (sibling won)
          → should return immediately, no Xero call
        """
        conn_id = uuid4()
        conn_expired = _make_connection(connection_id=conn_id, token_expires_at=EXPIRED_AT)
        conn_fresh = _make_connection(
            connection_id=conn_id, token_expires_at=FRESH_AT, needs_refresh=False
        )

        svc = _make_service()
        # 3 get_by_id calls: initial, lock-key lookup, post-lock re-read
        svc.connection_repo.get_by_id.side_effect = [conn_expired, conn_expired, conn_fresh]

        mock_redis_module, _, _ = _make_redis_mock(lock_acquire_return=True)
        mock_client_cls, mock_xero = _make_xero_client_patch()

        with patch(AIOREDIS_PATCH, mock_redis_module):
            with patch(
                "app.modules.integrations.xero.connection_service.XeroClient", mock_client_cls
            ):
                result = await svc.ensure_valid_token(conn_id)

        # Token was fresh after lock — Xero refresh must NOT have been called
        mock_xero.refresh_token.assert_not_called()
        assert result == "decrypted_access_token"

    @pytest.mark.asyncio
    async def test_xero_called_once_when_tokens_still_stale_after_lock(self) -> None:
        """Lock acquired, re-read still stale → delegates to refresh_tokens (1 Xero call).

        Call sequence:
          1. ensure_valid_token reads conn (expired)
          2. _refresh_with_lock reads conn at start (lock key)
          3. _refresh_with_lock re-reads after lock → still expired → calls refresh_tokens
          4. refresh_tokens reads conn (to decrypt refresh token)
          → exactly 1 Xero API call
        """
        conn_id = uuid4()
        tenant_id = uuid4()
        conn_expired = _make_connection(
            connection_id=conn_id, tenant_id=tenant_id, token_expires_at=EXPIRED_AT
        )
        conn_refreshed = _make_connection(
            connection_id=conn_id,
            tenant_id=tenant_id,
            token_expires_at=FRESH_AT,
            needs_refresh=False,
        )

        svc = _make_service()
        # 4 get_by_id calls: initial, lock-key lookup, post-lock re-read, refresh_tokens read
        svc.connection_repo.get_by_id.side_effect = [
            conn_expired,
            conn_expired,
            conn_expired,
            conn_expired,
        ]
        svc.connection_repo.list_by_tenant.return_value = [conn_expired]
        svc.connection_repo.update.return_value = conn_refreshed

        mock_redis_module, _, _ = _make_redis_mock(lock_acquire_return=True)
        mock_client_cls, mock_xero = _make_xero_client_patch()

        with patch(AIOREDIS_PATCH, mock_redis_module):
            with patch(
                "app.modules.integrations.xero.connection_service.XeroClient", mock_client_cls
            ):
                await svc.ensure_valid_token(conn_id)

        mock_xero.refresh_token.assert_awaited_once()


# ===========================================================================
# T005 — Redis unavailable: best-effort refresh without lock
# ===========================================================================


class TestRedisUnavailable:
    """When Redis is unavailable, refresh must still succeed without the lock."""

    @pytest.mark.asyncio
    async def test_refresh_succeeds_when_from_url_raises_connection_error(self) -> None:
        conn_id = uuid4()
        tenant_id = uuid4()
        conn_expired = _make_connection(connection_id=conn_id, tenant_id=tenant_id)
        conn_refreshed = _make_connection(
            connection_id=conn_id,
            tenant_id=tenant_id,
            token_expires_at=FRESH_AT,
            needs_refresh=False,
        )

        svc = _make_service()
        # from_url raises → fallback to refresh_tokens
        # get_by_id calls: initial, _refresh_with_lock start, refresh_tokens read
        svc.connection_repo.get_by_id.side_effect = [conn_expired, conn_expired, conn_expired]
        svc.connection_repo.list_by_tenant.return_value = [conn_expired]
        svc.connection_repo.update.return_value = conn_refreshed

        mock_redis_module, _, _ = _make_redis_mock(
            from_url_side_effect=ConnectionError("Redis unreachable")
        )
        mock_client_cls, mock_xero = _make_xero_client_patch()

        with patch(AIOREDIS_PATCH, mock_redis_module):
            with patch(
                "app.modules.integrations.xero.connection_service.XeroClient", mock_client_cls
            ):
                result = await svc.ensure_valid_token(conn_id)

        # Must have called Xero despite Redis being unavailable
        mock_xero.refresh_token.assert_awaited_once()
        assert result == "decrypted_access_token"

    @pytest.mark.asyncio
    async def test_refresh_succeeds_when_lock_acquire_raises_redis_error(self) -> None:
        conn_id = uuid4()
        tenant_id = uuid4()
        conn_expired = _make_connection(connection_id=conn_id, tenant_id=tenant_id)
        conn_refreshed = _make_connection(
            connection_id=conn_id,
            tenant_id=tenant_id,
            token_expires_at=FRESH_AT,
            needs_refresh=False,
        )

        svc = _make_service()
        # lock.acquire raises → fallback to refresh_tokens
        # get_by_id calls: initial, _refresh_with_lock start, refresh_tokens read
        svc.connection_repo.get_by_id.side_effect = [conn_expired, conn_expired, conn_expired]
        svc.connection_repo.list_by_tenant.return_value = [conn_expired]
        svc.connection_repo.update.return_value = conn_refreshed

        # lock.acquire itself raises — simulates Redis connection drop mid-operation
        mock_redis_module, _, _ = _make_redis_mock(
            lock_acquire_side_effect=ConnectionError("Connection lost during acquire")
        )
        mock_client_cls, mock_xero = _make_xero_client_patch()

        with patch(AIOREDIS_PATCH, mock_redis_module):
            with patch(
                "app.modules.integrations.xero.connection_service.XeroClient", mock_client_cls
            ):
                result = await svc.ensure_valid_token(conn_id)

        mock_xero.refresh_token.assert_awaited_once()
        assert result == "decrypted_access_token"


# ===========================================================================
# T006 — Retry-before-reauth: sibling propagated tokens before us
# ===========================================================================


class TestRetryBeforeReauth:
    """In refresh_tokens, on Xero exception, re-read DB before marking needs_reauth.

    If sibling already propagated fresh tokens, do not mark needs_reauth.
    """

    @pytest.mark.asyncio
    async def test_no_needs_reauth_when_sibling_propagated_fresh_tokens(self) -> None:
        conn_id = uuid4()
        tenant_id = uuid4()
        conn_expired = _make_connection(connection_id=conn_id, tenant_id=tenant_id)
        # Sibling propagated: same connection now has fresh tokens
        conn_fresh = _make_connection(
            connection_id=conn_id,
            tenant_id=tenant_id,
            token_expires_at=FRESH_AT,
            needs_refresh=False,
        )

        svc = _make_service()
        # First get (initial call to refresh_tokens) → expired
        # Second get (retry after Xero exception) → fresh (sibling propagated)
        svc.connection_repo.get_by_id.side_effect = [conn_expired, conn_fresh]
        svc.connection_repo.list_by_tenant.return_value = [conn_expired]

        mock_client_cls, mock_xero = _make_xero_client_patch(
            refresh_side_effect=Exception("invalid_grant")
        )

        with patch("app.modules.integrations.xero.connection_service.XeroClient", mock_client_cls):
            # refresh_tokens is called directly (not via lock — tested separately)
            result = await svc.refresh_tokens(conn_id)

        # Should return the fresh connection without marking needs_reauth
        assert result is conn_fresh

        # Must NOT have written needs_reauth
        for call in svc.connection_repo.update.call_args_list:
            update_data = call.args[1] if len(call.args) > 1 else call.kwargs.get("data")
            if isinstance(update_data, XeroConnectionUpdate) and update_data.status:
                assert update_data.status != XeroConnectionStatus.NEEDS_REAUTH, (
                    "Should not mark needs_reauth when sibling already propagated fresh tokens"
                )

    @pytest.mark.asyncio
    async def test_marks_needs_reauth_on_genuine_invalid_grant(self) -> None:
        """DB re-read still shows expired tokens → mark needs_reauth and raise."""
        conn_id = uuid4()
        conn_expired = _make_connection(connection_id=conn_id)

        svc = _make_service()
        # Both reads return expired (no sibling propagated anything)
        svc.connection_repo.get_by_id.return_value = conn_expired
        svc.connection_repo.update.return_value = conn_expired

        mock_client_cls, _ = _make_xero_client_patch(refresh_side_effect=Exception("invalid_grant"))

        with patch("app.modules.integrations.xero.connection_service.XeroClient", mock_client_cls):
            with pytest.raises(Exception, match="invalid_grant"):
                await svc.refresh_tokens(conn_id)

        # Must have marked needs_reauth
        needs_reauth_writes = [
            call
            for call in svc.connection_repo.update.call_args_list
            if (
                len(call.args) > 1
                and isinstance(call.args[1], XeroConnectionUpdate)
                and call.args[1].status == XeroConnectionStatus.NEEDS_REAUTH
            )
        ]
        assert needs_reauth_writes, "Should have marked connection as needs_reauth"


# ===========================================================================
# T007 — Sibling propagation: all grant siblings receive updated tokens
# ===========================================================================


class TestSiblingPropagation:
    """After refresh_tokens succeeds, all connections sharing auth_event_id are updated."""

    @pytest.mark.asyncio
    async def test_all_active_siblings_receive_updated_tokens(self) -> None:
        tenant_id = uuid4()
        conn_main_id = uuid4()
        sibling1_id = uuid4()
        sibling2_id = uuid4()

        conn_main = _make_connection(connection_id=conn_main_id, tenant_id=tenant_id)
        sibling1 = _make_connection(
            connection_id=sibling1_id, tenant_id=tenant_id, organization_name="Sibling One"
        )
        sibling2 = _make_connection(
            connection_id=sibling2_id, tenant_id=tenant_id, organization_name="Sibling Two"
        )
        conn_refreshed = _make_connection(
            connection_id=conn_main_id,
            tenant_id=tenant_id,
            token_expires_at=FRESH_AT,
            needs_refresh=False,
        )

        svc = _make_service()
        svc.connection_repo.get_by_id.return_value = conn_main
        svc.connection_repo.list_by_tenant.return_value = [conn_main, sibling1, sibling2]
        svc.connection_repo.update.return_value = conn_refreshed

        mock_client_cls, _ = _make_xero_client_patch()

        with patch("app.modules.integrations.xero.connection_service.XeroClient", mock_client_cls):
            await svc.refresh_tokens(conn_main_id)

        updated_ids = {call.args[0] for call in svc.connection_repo.update.call_args_list}
        assert sibling1_id in updated_ids, "Sibling 1 must receive updated tokens"
        assert sibling2_id in updated_ids, "Sibling 2 must receive updated tokens"

    @pytest.mark.asyncio
    async def test_needs_reauth_sibling_receives_tokens_and_set_to_active(self) -> None:
        """A sibling already in needs_reauth must be healed back to active."""
        tenant_id = uuid4()
        conn_main_id = uuid4()
        sibling_reauth_id = uuid4()

        conn_main = _make_connection(connection_id=conn_main_id, tenant_id=tenant_id)
        sibling_reauth = _make_connection(
            connection_id=sibling_reauth_id,
            tenant_id=tenant_id,
            status=XeroConnectionStatus.NEEDS_REAUTH,
            organization_name="Reauth Sibling",
        )
        conn_refreshed = _make_connection(
            connection_id=conn_main_id,
            tenant_id=tenant_id,
            token_expires_at=FRESH_AT,
            needs_refresh=False,
        )

        svc = _make_service()
        svc.connection_repo.get_by_id.return_value = conn_main
        svc.connection_repo.list_by_tenant.return_value = [conn_main, sibling_reauth]
        svc.connection_repo.update.return_value = conn_refreshed

        mock_client_cls, _ = _make_xero_client_patch()

        with patch("app.modules.integrations.xero.connection_service.XeroClient", mock_client_cls):
            await svc.refresh_tokens(conn_main_id)

        # Find the update call for the needs_reauth sibling
        sibling_calls = [
            call
            for call in svc.connection_repo.update.call_args_list
            if call.args[0] == sibling_reauth_id
        ]
        assert sibling_calls, "needs_reauth sibling must receive a token update"

        update_data = sibling_calls[0].args[1]
        assert isinstance(update_data, XeroConnectionUpdate)
        assert update_data.status == XeroConnectionStatus.ACTIVE, (
            "Sibling must be set back to ACTIVE after token propagation"
        )

    @pytest.mark.asyncio
    async def test_different_auth_event_id_not_propagated(self) -> None:
        """Connections with a different auth_event_id must not receive propagated tokens."""
        tenant_id = uuid4()
        conn_main_id = uuid4()
        unrelated_id = uuid4()

        conn_main = _make_connection(
            connection_id=conn_main_id, tenant_id=tenant_id, auth_event_id="evt_A"
        )
        conn_unrelated = _make_connection(
            connection_id=unrelated_id,
            tenant_id=tenant_id,
            auth_event_id="evt_B",  # Different grant
        )
        conn_refreshed = _make_connection(
            connection_id=conn_main_id,
            tenant_id=tenant_id,
            token_expires_at=FRESH_AT,
            needs_refresh=False,
        )

        svc = _make_service()
        svc.connection_repo.get_by_id.return_value = conn_main
        svc.connection_repo.list_by_tenant.return_value = [conn_main, conn_unrelated]
        svc.connection_repo.update.return_value = conn_refreshed

        mock_client_cls, _ = _make_xero_client_patch()

        with patch("app.modules.integrations.xero.connection_service.XeroClient", mock_client_cls):
            await svc.refresh_tokens(conn_main_id)

        updated_ids = {call.args[0] for call in svc.connection_repo.update.call_args_list}
        assert unrelated_id not in updated_ids, (
            "Connection with different auth_event_id must not receive propagated tokens"
        )

    @pytest.mark.asyncio
    async def test_no_propagation_when_connection_has_no_auth_event_id(self) -> None:
        """Connection without auth_event_id: refresh works but no sibling update attempted."""
        conn_id = uuid4()
        conn = _make_connection(connection_id=conn_id, auth_event_id=None)
        conn_refreshed = _make_connection(
            connection_id=conn_id, token_expires_at=FRESH_AT, needs_refresh=False
        )

        svc = _make_service()
        svc.connection_repo.get_by_id.return_value = conn
        svc.connection_repo.update.return_value = conn_refreshed

        mock_client_cls, mock_xero = _make_xero_client_patch()

        with patch("app.modules.integrations.xero.connection_service.XeroClient", mock_client_cls):
            result = await svc.refresh_tokens(conn_id)

        # No sibling query should be made
        svc.connection_repo.list_by_tenant.assert_not_called()
        assert result is conn_refreshed


# ===========================================================================
# Additional: ensure_valid_token fast-path and guard conditions
# ===========================================================================


class TestEnsureValidTokenGuards:
    """ensure_valid_token fast-path and pre-condition checks."""

    @pytest.mark.asyncio
    async def test_returns_decrypted_token_when_still_valid(self) -> None:
        conn_id = uuid4()
        conn = _make_connection(
            connection_id=conn_id, token_expires_at=FRESH_AT, needs_refresh=False
        )

        svc = _make_service()
        svc.connection_repo.get_by_id.return_value = conn

        with patch("app.modules.integrations.xero.connection_service.XeroClient") as mock_cls:
            result = await svc.ensure_valid_token(conn_id)
            mock_cls.assert_not_called()

        assert result == "decrypted_access_token"

    @pytest.mark.asyncio
    async def test_raises_auth_required_for_needs_reauth_connection(self) -> None:
        conn_id = uuid4()
        conn = _make_connection(connection_id=conn_id, status=XeroConnectionStatus.NEEDS_REAUTH)

        svc = _make_service()
        svc.connection_repo.get_by_id.return_value = conn

        with pytest.raises(XeroAuthRequiredError) as exc_info:
            await svc.ensure_valid_token(conn_id)

        assert exc_info.value.connection_id == conn_id

    @pytest.mark.asyncio
    async def test_raises_not_found_for_missing_connection(self) -> None:
        svc = _make_service()
        svc.connection_repo.get_by_id.return_value = None

        with pytest.raises(XeroConnectionNotFoundError):
            await svc.ensure_valid_token(uuid4())
