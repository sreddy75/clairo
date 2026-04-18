"""Xero connection lifecycle service — list, get, disconnect, delete, token refresh."""

from __future__ import annotations

import contextlib
import logging
from uuid import UUID

import redis.asyncio as aioredis
from redis.exceptions import RedisError
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.modules.integrations.xero.client import XeroClient
from app.modules.integrations.xero.encryption import TokenEncryption
from app.modules.integrations.xero.exceptions import XeroAuthRequiredError, XeroOAuthError
from app.modules.integrations.xero.models import XeroConnection, XeroConnectionStatus
from app.modules.integrations.xero.repository import XeroConnectionRepository
from app.modules.integrations.xero.schemas import (
    XeroConnectionListResponse,
    XeroConnectionResponse,
    XeroConnectionSummary,
    XeroConnectionUpdate,
)

logger = logging.getLogger(__name__)


class XeroConnectionNotFoundError(Exception):
    """Xero connection not found."""

    pass


class XeroConnectionService:
    """Service for managing Xero connections."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
    ) -> None:
        """Initialize connection service.

        Args:
            session: Database session.
            settings: Application settings.
        """
        self.session = session
        self.settings = settings
        self.connection_repo = XeroConnectionRepository(session)
        self.encryption = TokenEncryption(settings.token_encryption.key.get_secret_value())

    async def list_connections(
        self,
        tenant_id: UUID,
    ) -> XeroConnectionListResponse:
        """List all Xero connections for a tenant.

        Args:
            tenant_id: The tenant ID.

        Returns:
            XeroConnectionListResponse with connection summaries.
        """
        connections = await self.connection_repo.list_by_tenant(tenant_id)

        summaries = [
            XeroConnectionSummary(
                id=conn.id,
                organization_name=conn.organization_name,
                status=conn.status,
                connected_at=conn.connected_at,
                last_full_sync_at=conn.last_full_sync_at,
            )
            for conn in connections
        ]

        return XeroConnectionListResponse(
            connections=summaries,
            total=len(summaries),
        )

    async def get_connection(
        self,
        connection_id: UUID,
    ) -> XeroConnectionResponse:
        """Get connection details.

        Args:
            connection_id: The connection ID.

        Returns:
            XeroConnectionResponse with full details.

        Raises:
            XeroConnectionNotFoundError: If connection not found.
        """
        connection = await self.connection_repo.get_by_id(connection_id)
        if connection is None:
            raise XeroConnectionNotFoundError(f"Connection {connection_id} not found")

        return XeroConnectionResponse(
            id=connection.id,
            xero_tenant_id=connection.xero_tenant_id,
            organization_name=connection.organization_name,
            status=connection.status,
            scopes=connection.scopes,
            connected_at=connection.connected_at,
            last_used_at=connection.last_used_at,
            rate_limit_daily_remaining=connection.rate_limit_daily_remaining,
            rate_limit_minute_remaining=connection.rate_limit_minute_remaining,
        )

    async def disconnect(
        self,
        connection_id: UUID,
        user_id: UUID,
        reason: str | None = None,
    ) -> None:
        """Disconnect a Xero organization.

        Revokes tokens at Xero and marks connection as disconnected.

        Args:
            connection_id: The connection ID.
            user_id: The user performing the disconnect.
            reason: Optional reason for audit.

        Raises:
            XeroConnectionNotFoundError: If connection not found.
        """
        connection = await self.connection_repo.get_by_id(connection_id)
        if connection is None:
            raise XeroConnectionNotFoundError(f"Connection {connection_id} not found")

        # Try to revoke token at Xero (best effort)
        if connection.status == XeroConnectionStatus.ACTIVE:
            try:
                refresh_token = self.encryption.decrypt(connection.refresh_token)
                async with XeroClient(self.settings.xero) as client:
                    await client.revoke_token(refresh_token)
            except Exception:
                # Don't fail disconnect if revocation fails
                pass

        # Mark as disconnected (clears tokens)
        await self.connection_repo.disconnect(connection_id)

    async def get_connection_data_counts(
        self,
        connection_id: UUID,
    ) -> dict[str, int]:
        """Get counts of all data associated with a connection.

        Args:
            connection_id: The connection ID.

        Returns:
            Dictionary of entity type -> record count.

        Raises:
            XeroConnectionNotFoundError: If connection not found.
        """
        from app.modules.bas.models import BASPeriod
        from app.modules.quality.models import QualityScore

        from .models import (
            XeroAccount,
            XeroBankTransaction,
            XeroClient,
            XeroCreditNote,
            XeroEmployee,
            XeroInvoice,
            XeroJournal,
            XeroPayment,
            XeroSyncJob,
        )

        connection = await self.connection_repo.get_by_id(connection_id)
        if connection is None:
            raise XeroConnectionNotFoundError(f"Connection {connection_id} not found")

        counts = {}
        tables = [
            ("clients", XeroClient),
            ("invoices", XeroInvoice),
            ("bank_transactions", XeroBankTransaction),
            ("payments", XeroPayment),
            ("credit_notes", XeroCreditNote),
            ("journals", XeroJournal),
            ("accounts", XeroAccount),
            ("employees", XeroEmployee),
            ("sync_jobs", XeroSyncJob),
        ]

        for name, model in tables:
            result = await self.session.execute(
                select(func.count()).select_from(model).where(model.connection_id == connection_id)
            )
            counts[name] = result.scalar() or 0

        # BAS periods and quality scores link via connection_id
        for name, model in [("bas_periods", BASPeriod), ("quality_scores", QualityScore)]:
            result = await self.session.execute(
                select(func.count()).select_from(model).where(model.connection_id == connection_id)
            )
            counts[name] = result.scalar() or 0

        return counts

    async def delete_connection(
        self,
        connection_id: UUID,
        user_id: UUID,
    ) -> None:
        """Permanently delete a connection and all associated data.

        Revokes tokens at Xero, then deletes the connection row.
        CASCADE foreign keys handle deletion of all dependent data.

        Args:
            connection_id: The connection ID.
            user_id: The user performing the deletion.

        Raises:
            XeroConnectionNotFoundError: If connection not found.
        """
        connection = await self.connection_repo.get_by_id(connection_id)
        if connection is None:
            raise XeroConnectionNotFoundError(f"Connection {connection_id} not found")

        # Try to revoke token at Xero (best effort)
        if connection.status == XeroConnectionStatus.ACTIVE:
            try:
                refresh_token = self.encryption.decrypt(connection.refresh_token)
                async with XeroClient(self.settings.xero) as client:
                    await client.revoke_token(refresh_token)
            except Exception:
                pass

        # Delete the connection row — CASCADE handles all dependent data
        await self.session.execute(delete(XeroConnection).where(XeroConnection.id == connection_id))
        await self.session.flush()

    async def refresh_tokens(
        self,
        connection_id: UUID,
    ) -> XeroConnection:
        """Refresh tokens for a connection.

        Args:
            connection_id: The connection ID.

        Returns:
            Updated XeroConnection.

        Raises:
            XeroConnectionNotFoundError: If connection not found.
            XeroOAuthError: If refresh fails.
        """
        connection = await self.connection_repo.get_by_id(connection_id)
        if connection is None:
            raise XeroConnectionNotFoundError(f"Connection {connection_id} not found")

        if connection.status != XeroConnectionStatus.ACTIVE:
            raise XeroOAuthError("Connection is not active, cannot refresh")

        # Decrypt current refresh token
        refresh_token = self.encryption.decrypt(connection.refresh_token)

        try:
            async with XeroClient(self.settings.xero) as client:
                token_response, token_expires_at = await client.refresh_token(refresh_token)
        except Exception as e:
            # Before marking needs_reauth, re-read DB — a sibling connection sharing the
            # same OAuth grant may have already refreshed and propagated fresh tokens.
            # Xero rotating refresh tokens mean only one winner per rotation window.
            fresh = await self.connection_repo.get_by_id(connection_id)
            if fresh and not fresh.needs_refresh:
                logger.info(
                    "Token refresh conflict resolved: sibling already refreshed, "
                    "using propagated tokens (connection_id=%s)",
                    connection_id,
                )
                return fresh

            # Genuine failure — mark as needs_reauth
            await self.connection_repo.update(
                connection_id,
                XeroConnectionUpdate(status=XeroConnectionStatus.NEEDS_REAUTH),
            )
            raise XeroOAuthError(str(e)) from e

        # Update with new tokens
        encrypted_access = self.encryption.encrypt(token_response.access_token)
        encrypted_refresh = self.encryption.encrypt(token_response.refresh_token)

        updated = await self.connection_repo.update(
            connection_id,
            XeroConnectionUpdate(
                access_token=encrypted_access,
                refresh_token=encrypted_refresh,
                token_expires_at=token_expires_at,
            ),
        )

        if updated is None:
            raise XeroConnectionNotFoundError(f"Connection {connection_id} not found")

        # Propagate refreshed tokens to ALL sibling connections that share the same
        # OAuth grant (identified by auth_event_id). Xero rotates refresh tokens on
        # every use — siblings holding the old token will get invalid_grant without this.
        # Fix: propagate to ALL siblings regardless of status (previously only NEEDS_REAUTH).
        if connection.auth_event_id:
            try:
                siblings = await self.connection_repo.list_by_tenant(
                    connection.tenant_id, include_disconnected=False
                )
                for sibling in siblings:
                    if (
                        sibling.id != connection_id
                        and sibling.auth_event_id == connection.auth_event_id
                    ):
                        await self.connection_repo.update(
                            sibling.id,
                            XeroConnectionUpdate(
                                access_token=encrypted_access,
                                refresh_token=encrypted_refresh,
                                token_expires_at=token_expires_at,
                                status=XeroConnectionStatus.ACTIVE,
                            ),
                        )
                        logger.info(
                            "Propagated refreshed token to sibling connection %s (%s)",
                            sibling.id,
                            sibling.organization_name,
                        )
            except Exception as e:
                logger.warning("Failed to propagate token to siblings: %s", e)

        return updated

    async def ensure_valid_token(
        self,
        connection_id: UUID,
    ) -> str:
        """Ensure connection has valid access token, refreshing if needed.

        Uses a Redis distributed lock to prevent concurrent token refreshes
        for the same connection. Xero uses rotating refresh tokens — if two
        tasks refresh simultaneously, one will invalidate the other's token,
        causing the connection to be marked as NEEDS_REAUTH.

        Args:
            connection_id: The connection ID.

        Returns:
            Decrypted access token.

        Raises:
            XeroConnectionNotFoundError: If connection not found.
            XeroOAuthError: If refresh fails.
        """
        connection = await self.connection_repo.get_by_id(connection_id)
        if connection is None:
            raise XeroConnectionNotFoundError(f"Connection {connection_id} not found")

        # Connections in needs_reauth require a new OAuth flow — cannot auto-refresh.
        if connection.status == XeroConnectionStatus.NEEDS_REAUTH:
            raise XeroAuthRequiredError(
                connection_id, org_name=connection.organization_name or ""
            )

        # Check if token needs refresh
        if connection.needs_refresh:
            connection = await self._refresh_with_lock(connection_id)

        return self.encryption.decrypt(connection.access_token)

    async def _refresh_with_lock(
        self,
        connection_id: UUID,
    ) -> XeroConnection:
        """Refresh tokens with a distributed Redis lock scoped to the OAuth grant.

        The lock is keyed by auth_event_id (shared across all connections from the
        same OAuth flow), preventing sibling connections from simultaneously rotating
        the same Xero refresh token. Xero invalidates the old token on each rotation —
        concurrent rotations cause invalid_grant errors for all but the first caller.

        If Redis is unavailable, falls back to a best-effort refresh without the lock.
        """
        connection = await self.connection_repo.get_by_id(connection_id)
        if connection is None:
            raise XeroConnectionNotFoundError(f"Connection {connection_id} not found")

        # Scope lock to OAuth grant (auth_event_id groups siblings from same callback).
        # Fall back to per-connection key for connections without an auth_event_id.
        lock_scope = connection.auth_event_id or str(connection_id)
        lock_key = f"xero_token_refresh:event:{lock_scope}"

        try:
            redis_client = aioredis.from_url(self.settings.redis.url)
        except (RedisError, ConnectionError, OSError) as e:
            logger.warning(
                "Redis unavailable for token refresh lock, attempting without lock "
                "(connection_id=%s, error=%s)",
                connection_id,
                e,
            )
            return await self.refresh_tokens(connection_id)

        try:
            lock = redis_client.lock(lock_key, timeout=30, blocking_timeout=15)

            try:
                acquired = await lock.acquire(blocking=True)
            except (RedisError, ConnectionError, OSError) as e:
                logger.warning(
                    "Redis lock acquisition failed, attempting without lock "
                    "(connection_id=%s, error=%s)",
                    connection_id,
                    e,
                )
                return await self.refresh_tokens(connection_id)

            if acquired:
                try:
                    # Re-check after acquiring the lock: another task holding the
                    # same grant lock may have already refreshed and propagated tokens.
                    connection = await self.connection_repo.get_by_id(connection_id)
                    if connection is None:
                        raise XeroConnectionNotFoundError(
                            f"Connection {connection_id} not found"
                        )
                    if connection.needs_refresh:
                        return await self.refresh_tokens(connection_id)
                    return connection
                finally:
                    with contextlib.suppress(Exception):
                        await lock.release()
            else:
                # Could not acquire within 15s — another task holds the grant lock.
                # Re-read from DB; the holder should have written fresh tokens by now.
                connection = await self.connection_repo.get_by_id(connection_id)
                if connection is None:
                    raise XeroConnectionNotFoundError(f"Connection {connection_id} not found")
                return connection
        finally:
            with contextlib.suppress(Exception):
                await redis_client.aclose()
