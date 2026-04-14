"""Xero connection lifecycle service — list, get, disconnect, delete, token refresh."""

from __future__ import annotations

import contextlib
import logging
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.modules.integrations.xero.client import XeroClient
from app.modules.integrations.xero.encryption import TokenEncryption
from app.modules.integrations.xero.exceptions import XeroOAuthError
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
        from ..bas.models import BASPeriod
        from ..quality.models import QualityScore
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
            # Mark connection as needing re-auth
            await self.connection_repo.update(
                connection_id,
                XeroConnectionUpdate(status=XeroConnectionStatus.NEEDS_REAUTH),
            )
            raise XeroOAuthError(f"Token refresh failed: {e}") from e

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

        # Propagate refreshed token to sibling connections (same tenant) that share
        # the same Xero OAuth grant. Bulk-imported connections share a single token,
        # and Xero rotates refresh tokens — so siblings go stale after first refresh.
        try:
            siblings = await self.connection_repo.list_by_tenant(
                connection.tenant_id, include_disconnected=False
            )
            for sibling in siblings:
                if sibling.id != connection_id and sibling.status == XeroConnectionStatus.NEEDS_REAUTH:
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
                        "Restored sibling connection with refreshed token",
                        connection_id=str(sibling.id),
                        organization=sibling.organization_name,
                    )
        except Exception as e:
            logger.warning("Failed to propagate token to siblings", error=str(e))

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

        # Check if token needs refresh
        if connection.needs_refresh:
            connection = await self._refresh_with_lock(connection_id)

        return self.encryption.decrypt(connection.access_token)

    async def _refresh_with_lock(
        self,
        connection_id: UUID,
    ) -> XeroConnection:
        """Refresh tokens with a distributed Redis lock.

        If another task is already refreshing, waits for it to complete
        then re-reads the connection (which should now have fresh tokens).
        """
        import redis.asyncio as aioredis

        lock_key = f"xero_token_refresh:{connection_id}"
        redis_client = aioredis.from_url(self.settings.redis.url)

        try:
            lock = redis_client.lock(lock_key, timeout=30, blocking_timeout=15)
            acquired = await lock.acquire(blocking=True)

            if acquired:
                try:
                    # Re-check if token still needs refresh (another task
                    # may have refreshed while we were waiting for the lock)
                    connection = await self.connection_repo.get_by_id(connection_id)
                    if connection and connection.needs_refresh:
                        return await self.refresh_tokens(connection_id)
                    if connection is None:
                        raise XeroConnectionNotFoundError(f"Connection {connection_id} not found")
                    return connection
                finally:
                    with contextlib.suppress(Exception):
                        await lock.release()  # Lock may have expired
            else:
                # Could not acquire lock — another task is refreshing.
                # Re-read the connection which should have fresh tokens.
                connection = await self.connection_repo.get_by_id(connection_id)
                if connection is None:
                    raise XeroConnectionNotFoundError(f"Connection {connection_id} not found")
                return connection
        finally:
            await redis_client.aclose()

