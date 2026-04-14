"""Xero integration database operations.

Provides repositories for:
- XeroConnectionRepository: CRUD for XeroConnection
- XeroOAuthStateRepository: CRUD for XeroOAuthState
- XeroSyncJobRepository: CRUD for XeroSyncJob
- XeroClientRepository: CRUD for XeroClient (contacts from Xero Accounting)
- XeroInvoiceRepository: CRUD for XeroInvoice
- XeroBankTransactionRepository: CRUD for XeroBankTransaction
- XeroAccountRepository: CRUD for XeroAccount
- XpmClientRepository: CRUD for XpmClient (clients from Xero Practice Manager)
- XeroReportRepository: CRUD for XeroReport (cached financial reports)
- XeroReportSyncJobRepository: CRUD for XeroReportSyncJob (report sync audit trail)
- XeroSyncEntityProgressRepository: CRUD for XeroSyncEntityProgress (per-entity sync tracking)
- PostSyncTaskRepository: CRUD for PostSyncTask (post-sync preparation tasks)
- XeroWebhookEventRepository: CRUD for XeroWebhookEvent (webhook event processing)
"""

import contextlib
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.integrations.xero.models import (
    PostSyncTask,
    PostSyncTaskStatus,
    XeroAccount,
    XeroAsset,
    XeroAssetStatus,
    XeroAssetType,
    XeroBankTransaction,
    XeroClient,
    XeroConnection,
    XeroConnectionStatus,
    XeroConnectionType,
    XeroCreditNote,
    XeroCreditNoteAllocation,
    XeroCreditNoteStatus,
    XeroCreditNoteType,
    XeroInvoice,
    XeroJournal,
    XeroJournalSourceType,
    XeroManualJournal,
    XeroManualJournalStatus,
    XeroOAuthState,
    XeroOverpayment,
    XeroPayment,
    XeroPaymentStatus,
    XeroPrepayment,
    XeroPurchaseOrder,
    XeroPurchaseOrderStatus,
    XeroQuote,
    XeroQuoteStatus,
    XeroRepeatingInvoice,
    XeroRepeatingInvoiceStatus,
    XeroReport,
    XeroReportSyncJob,
    XeroReportSyncStatus,
    XeroReportType,
    XeroSyncEntityProgress,
    XeroSyncEntityProgressStatus,
    XeroSyncJob,
    XeroSyncStatus,
    XeroSyncType,
    XeroTrackingCategory,
    XeroTrackingOption,
    XeroWebhookEvent,
    XeroWebhookEventStatus,
    XpmClient,
    XpmClientConnectionStatus,
)
from app.modules.integrations.xero.schemas import XeroConnectionCreate, XeroConnectionUpdate


class XeroOAuthStateRepository:
    """Repository for XeroOAuthState CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session.
        """
        self.session = session

    async def create(
        self,
        tenant_id: UUID,
        user_id: UUID,
        state: str,
        code_verifier: str,
        redirect_uri: str,
        expires_at: datetime,
        xpm_client_id: UUID | None = None,
        connection_type: XeroConnectionType = XeroConnectionType.PRACTICE,
        is_bulk_import: bool = False,
    ) -> XeroOAuthState:
        """Create a new OAuth state record.

        Args:
            tenant_id: The tenant initiating OAuth.
            user_id: The user initiating OAuth.
            state: CSRF protection token.
            code_verifier: PKCE code verifier.
            redirect_uri: Frontend redirect URI.
            expires_at: When the state expires.
            xpm_client_id: XPM client ID if this is client-specific OAuth.
            connection_type: Whether this is for practice or client Xero org.
            is_bulk_import: True for bulk import OAuth flows.

        Returns:
            The created XeroOAuthState.
        """
        oauth_state = XeroOAuthState(
            tenant_id=tenant_id,
            user_id=user_id,
            state=state,
            code_verifier=code_verifier,
            redirect_uri=redirect_uri,
            expires_at=expires_at,
            xpm_client_id=xpm_client_id,
            connection_type=connection_type,
            is_bulk_import=is_bulk_import,
        )
        self.session.add(oauth_state)
        await self.session.flush()
        return oauth_state

    async def get_by_state(self, state: str) -> XeroOAuthState | None:
        """Get OAuth state by state token.

        Note: This lookup is not tenant-scoped as the state is used
        for lookup before tenant context is established.

        Args:
            state: The state token to look up.

        Returns:
            XeroOAuthState if found, None otherwise.
        """
        result = await self.session.execute(
            select(XeroOAuthState).where(XeroOAuthState.state == state)
        )
        return result.scalar_one_or_none()

    async def mark_as_used(self, state_id: UUID) -> None:
        """Mark a state as used (consumed).

        Args:
            state_id: ID of the state to mark.
        """
        await self.session.execute(
            update(XeroOAuthState)
            .where(XeroOAuthState.id == state_id)
            .values(used_at=datetime.now(UTC))
        )

    async def cleanup_expired(self) -> int:
        """Delete expired and used states.

        Returns:
            Number of records deleted.
        """
        result = await self.session.execute(
            delete(XeroOAuthState).where(
                (XeroOAuthState.expires_at < datetime.now(UTC))
                | (XeroOAuthState.used_at.is_not(None))
            )
        )
        return result.rowcount


class XeroConnectionRepository:
    """Repository for XeroConnection CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session.
        """
        self.session = session

    async def create(self, data: XeroConnectionCreate) -> XeroConnection:
        """Create a new Xero connection.

        Args:
            data: Connection data including encrypted tokens.

        Returns:
            The created XeroConnection.
        """
        connection = XeroConnection(
            tenant_id=data.tenant_id,
            xero_tenant_id=data.xero_tenant_id,
            organization_name=data.organization_name,
            access_token=data.access_token,
            refresh_token=data.refresh_token,
            token_expires_at=data.token_expires_at,
            scopes=data.scopes,
            connected_by=data.connected_by,
            connected_at=datetime.now(UTC),
        )
        # Set auth_event_id if provided (bulk import flow)
        if data.auth_event_id:
            connection.auth_event_id = data.auth_event_id
        # Set connection_type (defaults to 'practice' if not specified)
        if data.connection_type and data.connection_type != "practice":
            from app.modules.integrations.xero.models import XeroConnectionType
            with contextlib.suppress(ValueError):
                connection.connection_type = XeroConnectionType(data.connection_type)
        self.session.add(connection)
        await self.session.flush()
        return connection

    async def get_by_id(
        self, connection_id: UUID, tenant_id: UUID | None = None
    ) -> XeroConnection | None:
        """Get connection by ID.

        Note: RLS provides database-level isolation. The optional tenant_id
        parameter adds application-level defense-in-depth.
        """
        query = select(XeroConnection).where(XeroConnection.id == connection_id)
        if tenant_id is not None:
            query = query.where(XeroConnection.tenant_id == tenant_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_xero_tenant_id(
        self, tenant_id: UUID, xero_tenant_id: str
    ) -> XeroConnection | None:
        """Get connection by Xero organization ID.

        Args:
            tenant_id: The Clairo tenant ID.
            xero_tenant_id: The Xero organization ID.

        Returns:
            XeroConnection if found, None otherwise.
        """
        result = await self.session.execute(
            select(XeroConnection).where(
                XeroConnection.tenant_id == tenant_id,
                XeroConnection.xero_tenant_id == xero_tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def find_by_xero_tenant_id(self, xero_tenant_id: str) -> list[XeroConnection]:
        """Find all active connections matching a Xero organization ID.

        Used by webhook processing where the Clairo tenant_id is unknown.
        Returns all connections across tenants that match the given Xero
        organization ID, allowing the webhook handler to resolve which
        tenant(s) the event belongs to.

        Note: This query bypasses tenant-scoped filtering intentionally
        because webhooks arrive without Clairo tenant context. The caller
        must set appropriate tenant context before further processing.

        Args:
            xero_tenant_id: The Xero organization ID from the webhook event.

        Returns:
            List of matching XeroConnection objects.
        """
        result = await self.session.execute(
            select(XeroConnection).where(
                XeroConnection.xero_tenant_id == xero_tenant_id,
                XeroConnection.status.in_([
                    XeroConnectionStatus.ACTIVE,
                    XeroConnectionStatus.NEEDS_REAUTH,
                ]),
            )
        )
        return list(result.scalars().all())

    async def list_by_tenant(
        self,
        tenant_id: UUID,
        include_disconnected: bool = False,
    ) -> list[XeroConnection]:
        """List all connections for a tenant.

        Note: RLS provides additional tenant isolation.

        Args:
            tenant_id: The tenant ID.
            include_disconnected: Whether to include disconnected connections.

        Returns:
            List of XeroConnection objects.
        """
        query = select(XeroConnection).where(XeroConnection.tenant_id == tenant_id)

        if not include_disconnected:
            query = query.where(XeroConnection.status != XeroConnectionStatus.DISCONNECTED)

        query = query.order_by(XeroConnection.organization_name)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update(
        self,
        connection_id: UUID,
        data: XeroConnectionUpdate,
        tenant_id: UUID | None = None,
    ) -> XeroConnection | None:
        """Update a connection.

        Args:
            connection_id: The connection ID.
            data: Fields to update.
            tenant_id: Optional tenant filter for defense-in-depth.

        Returns:
            Updated XeroConnection, or None if not found.
        """
        # Build update values from non-None fields
        update_values: dict = {}
        if data.access_token is not None:
            update_values["access_token"] = data.access_token
        if data.refresh_token is not None:
            update_values["refresh_token"] = data.refresh_token
        if data.token_expires_at is not None:
            update_values["token_expires_at"] = data.token_expires_at
        if data.status is not None:
            update_values["status"] = data.status
        if data.rate_limit_daily_remaining is not None:
            update_values["rate_limit_daily_remaining"] = data.rate_limit_daily_remaining
        if data.rate_limit_minute_remaining is not None:
            update_values["rate_limit_minute_remaining"] = data.rate_limit_minute_remaining
        if data.rate_limit_reset_at is not None:
            update_values["rate_limit_reset_at"] = data.rate_limit_reset_at
        if data.last_used_at is not None:
            update_values["last_used_at"] = data.last_used_at
        # Sync timestamps
        if data.last_contacts_sync_at is not None:
            update_values["last_contacts_sync_at"] = data.last_contacts_sync_at
        if data.last_invoices_sync_at is not None:
            update_values["last_invoices_sync_at"] = data.last_invoices_sync_at
        if data.last_transactions_sync_at is not None:
            update_values["last_transactions_sync_at"] = data.last_transactions_sync_at
        if data.last_accounts_sync_at is not None:
            update_values["last_accounts_sync_at"] = data.last_accounts_sync_at
        if data.last_full_sync_at is not None:
            update_values["last_full_sync_at"] = data.last_full_sync_at
        if data.sync_in_progress is not None:
            update_values["sync_in_progress"] = data.sync_in_progress
        # Payroll timestamps
        if data.has_payroll_access is not None:
            update_values["has_payroll_access"] = data.has_payroll_access
        if data.last_payroll_sync_at is not None:
            update_values["last_payroll_sync_at"] = data.last_payroll_sync_at
        if data.last_employees_sync_at is not None:
            update_values["last_employees_sync_at"] = data.last_employees_sync_at

        if not update_values:
            return await self.get_by_id(connection_id, tenant_id=tenant_id)

        stmt = (
            update(XeroConnection).where(XeroConnection.id == connection_id).values(**update_values)
        )
        if tenant_id is not None:
            stmt = stmt.where(XeroConnection.tenant_id == tenant_id)
        await self.session.execute(stmt)

        return await self.get_by_id(connection_id, tenant_id=tenant_id)

    async def disconnect(self, connection_id: UUID, tenant_id: UUID | None = None) -> None:
        """Mark a connection as disconnected.

        Args:
            connection_id: The connection ID.
            tenant_id: Optional tenant filter for defense-in-depth.
        """
        stmt = (
            update(XeroConnection)
            .where(XeroConnection.id == connection_id)
            .values(
                status=XeroConnectionStatus.DISCONNECTED,
                access_token="[REVOKED]",
                refresh_token="[REVOKED]",
            )
        )
        if tenant_id is not None:
            stmt = stmt.where(XeroConnection.tenant_id == tenant_id)
        await self.session.execute(stmt)

    async def count_active_by_tenant(self, tenant_id: UUID) -> int:
        """Count active connections for a tenant.

        Args:
            tenant_id: The tenant ID.

        Returns:
            Number of active connections.
        """
        result = await self.session.execute(
            select(XeroConnection).where(
                XeroConnection.tenant_id == tenant_id,
                XeroConnection.status.in_([
                    XeroConnectionStatus.ACTIVE,
                    XeroConnectionStatus.NEEDS_REAUTH,
                ]),
            )
        )
        return len(result.scalars().all())

    async def update_sync_timestamps(
        self,
        connection_id: UUID,
        sync_type: XeroSyncType,
        timestamp: datetime | None = None,
    ) -> None:
        """Update sync timestamp for a specific sync type.

        Args:
            connection_id: The connection ID.
            sync_type: Type of sync that completed.
            timestamp: Timestamp to set (defaults to now).
        """
        ts = timestamp or datetime.now(UTC)
        field_map = {
            XeroSyncType.CONTACTS: "last_contacts_sync_at",
            XeroSyncType.INVOICES: "last_invoices_sync_at",
            XeroSyncType.BANK_TRANSACTIONS: "last_transactions_sync_at",
            XeroSyncType.ACCOUNTS: "last_accounts_sync_at",
            XeroSyncType.FULL: "last_full_sync_at",
        }
        field = field_map.get(sync_type)
        if field:
            await self.session.execute(
                update(XeroConnection)
                .where(XeroConnection.id == connection_id)
                .values(**{field: ts})
            )

    async def set_sync_in_progress(self, connection_id: UUID, in_progress: bool) -> None:
        """Set the sync_in_progress flag.

        Args:
            connection_id: The connection ID.
            in_progress: Whether sync is in progress.
        """
        await self.session.execute(
            update(XeroConnection)
            .where(XeroConnection.id == connection_id)
            .values(sync_in_progress=in_progress)
        )

    async def get_all_active(self, tenant_id: UUID) -> list[XeroConnection]:
        """Get all active connections for a tenant.

        Args:
            tenant_id: The tenant ID.

        Returns:
            List of active XeroConnection objects.
        """
        result = await self.session.execute(
            select(XeroConnection).where(
                XeroConnection.tenant_id == tenant_id,
                XeroConnection.status.in_([
                    XeroConnectionStatus.ACTIVE,
                    XeroConnectionStatus.NEEDS_REAUTH,
                ]),
            )
        )
        return list(result.scalars().all())


class XeroSyncJobRepository:
    """Repository for XeroSyncJob CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        sync_type: XeroSyncType,
    ) -> XeroSyncJob:
        """Create a new sync job with pending status.

        Args:
            tenant_id: The tenant ID.
            connection_id: The connection ID.
            sync_type: Type of sync.

        Returns:
            The created XeroSyncJob.
        """
        job = XeroSyncJob(
            tenant_id=tenant_id,
            connection_id=connection_id,
            sync_type=sync_type,
            status=XeroSyncStatus.PENDING,
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_by_id(self, job_id: UUID) -> XeroSyncJob | None:
        """Get sync job by ID.

        Args:
            job_id: The job ID.

        Returns:
            XeroSyncJob if found, None otherwise.
        """
        result = await self.session.execute(select(XeroSyncJob).where(XeroSyncJob.id == job_id))
        return result.scalar_one_or_none()

    async def get_active_for_connection(self, connection_id: UUID) -> XeroSyncJob | None:
        """Get any active (pending or in_progress) job for connection.

        Args:
            connection_id: The connection ID.

        Returns:
            Active XeroSyncJob if exists, None otherwise.
        """
        result = await self.session.execute(
            select(XeroSyncJob).where(
                XeroSyncJob.connection_id == connection_id,
                XeroSyncJob.status.in_(
                    [
                        XeroSyncStatus.PENDING,
                        XeroSyncStatus.IN_PROGRESS,
                    ]
                ),
            )
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        job_id: UUID,
        status: XeroSyncStatus,
        error_message: str | None = None,
    ) -> None:
        """Update job status.

        Args:
            job_id: The job ID.
            status: New status.
            error_message: Optional error message.
        """
        values: dict[str, Any] = {"status": status}

        if status == XeroSyncStatus.IN_PROGRESS:
            values["started_at"] = datetime.now(UTC)
        elif status in (
            XeroSyncStatus.COMPLETED,
            XeroSyncStatus.FAILED,
            XeroSyncStatus.CANCELLED,
        ):
            values["completed_at"] = datetime.now(UTC)

        if error_message:
            values["error_message"] = error_message

        await self.session.execute(
            update(XeroSyncJob).where(XeroSyncJob.id == job_id).values(**values)
        )

    async def update_progress(
        self,
        job_id: UUID,
        records_processed: int,
        records_created: int,
        records_updated: int,
        records_failed: int,
        progress_details: dict[str, Any] | None = None,
    ) -> None:
        """Update job progress metrics.

        Args:
            job_id: The job ID.
            records_processed: Total records processed.
            records_created: Records created.
            records_updated: Records updated.
            records_failed: Records failed.
            progress_details: Optional progress details.
        """
        values: dict[str, Any] = {
            "records_processed": records_processed,
            "records_created": records_created,
            "records_updated": records_updated,
            "records_failed": records_failed,
            # Explicitly bump updated_at so the staleness checker sees activity.
            # (SQLAlchemy's onupdate may not fire on Core update() statements.)
            "updated_at": datetime.now(UTC),
        }
        if progress_details is not None:
            values["progress_details"] = progress_details

        await self.session.execute(
            update(XeroSyncJob).where(XeroSyncJob.id == job_id).values(**values)
        )

    async def list_by_connection(
        self,
        connection_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[XeroSyncJob], int]:
        """List sync jobs for a connection with pagination.

        Args:
            connection_id: The connection ID.
            limit: Max records to return.
            offset: Records to skip.

        Returns:
            Tuple of (jobs list, total count).
        """
        # Get total count
        count_result = await self.session.execute(
            select(func.count())
            .select_from(XeroSyncJob)
            .where(XeroSyncJob.connection_id == connection_id)
        )
        total = count_result.scalar() or 0

        # Get paginated results
        result = await self.session.execute(
            select(XeroSyncJob)
            .where(XeroSyncJob.connection_id == connection_id)
            .order_by(XeroSyncJob.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        jobs = list(result.scalars().all())

        return jobs, total

    async def get_latest_for_connection(self, connection_id: UUID) -> XeroSyncJob | None:
        """Get the most recent sync job for a connection.

        Args:
            connection_id: The connection ID.

        Returns:
            Most recent XeroSyncJob if exists, None otherwise.
        """
        result = await self.session.execute(
            select(XeroSyncJob)
            .where(XeroSyncJob.connection_id == connection_id)
            .order_by(XeroSyncJob.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


class XeroClientRepository:
    """Repository for XeroClient CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: dict[str, Any]) -> XeroClient:
        """Create a new client.

        Args:
            data: Client data.

        Returns:
            The created XeroClient.
        """
        client = XeroClient(**data)
        self.session.add(client)
        await self.session.flush()
        return client

    async def get_by_id(self, client_id: UUID) -> XeroClient | None:
        """Get client by ID."""
        result = await self.session.execute(select(XeroClient).where(XeroClient.id == client_id))
        return result.scalar_one_or_none()

    async def get_by_xero_contact_id(
        self, connection_id: UUID, xero_contact_id: str
    ) -> XeroClient | None:
        """Get client by Xero contact ID."""
        result = await self.session.execute(
            select(XeroClient).where(
                XeroClient.connection_id == connection_id,
                XeroClient.xero_contact_id == xero_contact_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_from_xero(self, data: dict[str, Any]) -> tuple[XeroClient, bool]:
        """Upsert client from Xero data.

        Uses PostgreSQL ON CONFLICT for atomic upsert.

        Args:
            data: Client data including connection_id and xero_contact_id.

        Returns:
            Tuple of (client, created) where created is True if new record.
        """
        stmt = insert(XeroClient).values(**data)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_xero_client_connection_contact",
            set_={
                k: v
                for k, v in data.items()
                if k not in ("id", "tenant_id", "connection_id", "xero_contact_id", "created_at")
            },
        ).returning(XeroClient)

        result = await self.session.execute(stmt)
        client = result.scalar_one()
        # Check if it was created (created_at == updated_at roughly)
        created = client.created_at >= client.updated_at
        return client, created

    async def bulk_upsert(self, records: list[dict[str, Any]]) -> tuple[int, int]:
        """Bulk upsert clients.

        Args:
            records: List of client data dicts.

        Returns:
            Tuple of (created_count, updated_count).
        """
        created = 0
        updated = 0
        for data in records:
            _, was_created = await self.upsert_from_xero(data)
            if was_created:
                created += 1
            else:
                updated += 1
        return created, updated

    async def list_by_connection(
        self,
        connection_id: UUID,
        is_active: bool | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[XeroClient], int]:
        """List clients for a connection with filtering and pagination.

        Args:
            connection_id: The connection ID.
            is_active: Filter by active status.
            search: Search by name.
            limit: Max records to return.
            offset: Records to skip.

        Returns:
            Tuple of (clients list, total count).
        """
        query = select(XeroClient).where(XeroClient.connection_id == connection_id)

        if is_active is not None:
            query = query.where(XeroClient.is_active == is_active)

        if search:
            query = query.where(XeroClient.name.ilike(f"%{search}%"))

        # Get total count
        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        # Get paginated results
        result = await self.session.execute(
            query.order_by(XeroClient.name).limit(limit).offset(offset)
        )
        clients = list(result.scalars().all())

        return clients, total

    async def soft_delete(self, client_id: UUID, tenant_id: UUID | None = None) -> None:
        """Soft delete by setting is_active=False."""
        stmt = update(XeroClient).where(XeroClient.id == client_id).values(is_active=False)
        if tenant_id is not None:
            stmt = stmt.where(XeroClient.tenant_id == tenant_id)
        await self.session.execute(stmt)

    async def list_all_for_tenant(
        self,
        search: str | None = None,
        contact_type: str | None = None,
        is_active: bool | None = None,
        sort_by: Literal["name", "contact_type", "created_at"] = "name",
        sort_order: Literal["asc", "desc"] = "asc",
        limit: int = 25,
        offset: int = 0,
        tenant_id: UUID | None = None,
    ) -> tuple[list[XeroClient], int]:
        """List all clients for the current tenant across all connections.

        RLS provides database-level isolation. The optional tenant_id adds
        application-level defense-in-depth.

        Args:
            search: Search by name (case-insensitive partial match).
            contact_type: Filter by contact type (customer, supplier, both).
            is_active: Filter by active status.
            sort_by: Field to sort by.
            sort_order: Sort direction.
            limit: Max records to return.
            offset: Records to skip.

        Returns:
            Tuple of (clients list, total count).
        """
        query = select(XeroClient)

        if tenant_id is not None:
            query = query.where(XeroClient.tenant_id == tenant_id)

        if is_active is not None:
            query = query.where(XeroClient.is_active == is_active)

        if contact_type is not None:
            query = query.where(XeroClient.contact_type == contact_type)

        if search:
            query = query.where(XeroClient.name.ilike(f"%{search}%"))

        # Get total count
        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        # Apply sorting
        sort_column = {
            "name": XeroClient.name,
            "contact_type": XeroClient.contact_type,
            "created_at": XeroClient.created_at,
        }.get(sort_by, XeroClient.name)

        if sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # Get paginated results
        result = await self.session.execute(query.limit(limit).offset(offset))
        clients = list(result.scalars().all())

        return clients, total


class XeroInvoiceRepository:
    """Repository for XeroInvoice CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: dict[str, Any]) -> XeroInvoice:
        """Create a new invoice."""
        invoice = XeroInvoice(**data)
        self.session.add(invoice)
        await self.session.flush()
        return invoice

    async def get_by_id(self, invoice_id: UUID) -> XeroInvoice | None:
        """Get invoice by ID."""
        result = await self.session.execute(select(XeroInvoice).where(XeroInvoice.id == invoice_id))
        return result.scalar_one_or_none()

    async def get_by_xero_invoice_id(
        self, connection_id: UUID, xero_invoice_id: str
    ) -> XeroInvoice | None:
        """Get invoice by Xero invoice ID."""
        result = await self.session.execute(
            select(XeroInvoice).where(
                XeroInvoice.connection_id == connection_id,
                XeroInvoice.xero_invoice_id == xero_invoice_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_from_xero(self, data: dict[str, Any]) -> tuple[XeroInvoice, bool]:
        """Upsert invoice from Xero data."""
        stmt = insert(XeroInvoice).values(**data)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_xero_invoice_connection_invoice",
            set_={
                k: v
                for k, v in data.items()
                if k not in ("id", "tenant_id", "connection_id", "xero_invoice_id", "created_at")
            },
        ).returning(XeroInvoice)

        result = await self.session.execute(stmt)
        invoice = result.scalar_one()
        created = invoice.created_at >= invoice.updated_at
        return invoice, created

    async def bulk_upsert(self, records: list[dict[str, Any]]) -> tuple[int, int]:
        """Bulk upsert invoices."""
        created = 0
        updated = 0
        for data in records:
            _, was_created = await self.upsert_from_xero(data)
            if was_created:
                created += 1
            else:
                updated += 1
        return created, updated

    async def list_by_connection(
        self,
        connection_id: UUID,
        client_id: UUID | None = None,
        invoice_type: str | None = None,
        status: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[XeroInvoice], int]:
        """List invoices for a connection with filtering and pagination."""
        query = select(XeroInvoice).where(XeroInvoice.connection_id == connection_id)

        if client_id is not None:
            query = query.where(XeroInvoice.client_id == client_id)
        if invoice_type is not None:
            query = query.where(XeroInvoice.invoice_type == invoice_type)
        if status is not None:
            query = query.where(XeroInvoice.status == status)
        if date_from is not None:
            query = query.where(XeroInvoice.issue_date >= date_from)
        if date_to is not None:
            query = query.where(XeroInvoice.issue_date <= date_to)

        # Get total count
        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        # Get paginated results
        result = await self.session.execute(
            query.order_by(XeroInvoice.issue_date.desc()).limit(limit).offset(offset)
        )
        invoices = list(result.scalars().all())

        return invoices, total

    async def link_to_client(self, invoice_id: UUID, client_id: UUID) -> None:
        """Link invoice to a synced client."""
        await self.session.execute(
            update(XeroInvoice).where(XeroInvoice.id == invoice_id).values(client_id=client_id)
        )

    async def list_by_client(
        self,
        client_id: UUID,
        invoice_type: str | None = None,
        status: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[XeroInvoice], int]:
        """List invoices for a specific client with filtering and pagination.

        Args:
            client_id: The client ID.
            invoice_type: Filter by type (accrec, accpay).
            status: Filter by status.
            from_date: Filter by issue_date >= from_date.
            to_date: Filter by issue_date <= to_date.
            limit: Max records to return.
            offset: Records to skip.

        Returns:
            Tuple of (invoices list, total count).
        """
        query = select(XeroInvoice).where(XeroInvoice.client_id == client_id)

        if invoice_type is not None:
            query = query.where(XeroInvoice.invoice_type == invoice_type)
        if status is not None:
            query = query.where(XeroInvoice.status == status)
        if from_date is not None:
            query = query.where(XeroInvoice.issue_date >= from_date)
        if to_date is not None:
            query = query.where(XeroInvoice.issue_date <= to_date)

        # Get total count
        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        # Get paginated results
        result = await self.session.execute(
            query.order_by(XeroInvoice.issue_date.desc()).limit(limit).offset(offset)
        )
        invoices = list(result.scalars().all())

        return invoices, total

    async def calculate_summary(
        self,
        client_id: UUID,
        from_date: date,
        to_date: date,
    ) -> dict[str, Any]:
        """Calculate invoice totals for a client within a date range.

        Only includes invoices with status AUTHORISED or PAID.

        Args:
            client_id: The client ID.
            from_date: Start date (inclusive).
            to_date: End date (inclusive).

        Returns:
            Dictionary with summary values:
            - total_sales: Sum of ACCREC invoice totals
            - sales_invoice_count: Count of ACCREC invoices
            - total_purchases: Sum of ACCPAY invoice totals
            - purchase_invoice_count: Count of ACCPAY invoices
            - gst_collected: Sum of tax_amount from ACCREC invoices
            - gst_paid: Sum of tax_amount from ACCPAY invoices
        """
        # Use aggregate query with conditional sums
        result = await self.session.execute(
            select(
                # Sales (ACCREC)
                func.count().filter(XeroInvoice.invoice_type == "accrec").label("sales_count"),
                func.coalesce(
                    func.sum(XeroInvoice.total_amount).filter(XeroInvoice.invoice_type == "accrec"),
                    Decimal("0.00"),
                ).label("total_sales"),
                func.coalesce(
                    func.sum(XeroInvoice.tax_amount).filter(XeroInvoice.invoice_type == "accrec"),
                    Decimal("0.00"),
                ).label("gst_collected"),
                # Purchases (ACCPAY)
                func.count().filter(XeroInvoice.invoice_type == "accpay").label("purchase_count"),
                func.coalesce(
                    func.sum(XeroInvoice.total_amount).filter(XeroInvoice.invoice_type == "accpay"),
                    Decimal("0.00"),
                ).label("total_purchases"),
                func.coalesce(
                    func.sum(XeroInvoice.tax_amount).filter(XeroInvoice.invoice_type == "accpay"),
                    Decimal("0.00"),
                ).label("gst_paid"),
            ).where(
                and_(
                    XeroInvoice.client_id == client_id,
                    XeroInvoice.issue_date >= from_date,
                    XeroInvoice.issue_date <= to_date,
                    XeroInvoice.status.in_(["authorised", "paid"]),
                )
            )
        )

        row = result.one()

        return {
            "total_sales": row.total_sales,
            "sales_invoice_count": row.sales_count,
            "total_purchases": row.total_purchases,
            "purchase_invoice_count": row.purchase_count,
            "gst_collected": row.gst_collected,
            "gst_paid": row.gst_paid,
        }


class XeroBankTransactionRepository:
    """Repository for XeroBankTransaction CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: dict[str, Any]) -> XeroBankTransaction:
        """Create a new bank transaction."""
        transaction = XeroBankTransaction(**data)
        self.session.add(transaction)
        await self.session.flush()
        return transaction

    async def get_by_id(self, transaction_id: UUID) -> XeroBankTransaction | None:
        """Get transaction by ID."""
        result = await self.session.execute(
            select(XeroBankTransaction).where(XeroBankTransaction.id == transaction_id)
        )
        return result.scalar_one_or_none()

    async def get_by_xero_transaction_id(
        self, connection_id: UUID, xero_transaction_id: str
    ) -> XeroBankTransaction | None:
        """Get transaction by Xero transaction ID."""
        result = await self.session.execute(
            select(XeroBankTransaction).where(
                XeroBankTransaction.connection_id == connection_id,
                XeroBankTransaction.xero_transaction_id == xero_transaction_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_from_xero(self, data: dict[str, Any]) -> tuple[XeroBankTransaction, bool]:
        """Upsert transaction from Xero data."""
        stmt = insert(XeroBankTransaction).values(**data)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_xero_transaction_connection_txn",
            set_={
                k: v
                for k, v in data.items()
                if k
                not in ("id", "tenant_id", "connection_id", "xero_transaction_id", "created_at")
            },
        ).returning(XeroBankTransaction)

        result = await self.session.execute(stmt)
        transaction = result.scalar_one()
        created = transaction.created_at >= transaction.updated_at
        return transaction, created

    async def bulk_upsert(self, records: list[dict[str, Any]]) -> tuple[int, int]:
        """Bulk upsert transactions."""
        created = 0
        updated = 0
        for data in records:
            _, was_created = await self.upsert_from_xero(data)
            if was_created:
                created += 1
            else:
                updated += 1
        return created, updated

    async def list_by_connection(
        self,
        connection_id: UUID,
        client_id: UUID | None = None,
        transaction_type: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[XeroBankTransaction], int]:
        """List transactions for a connection with filtering and pagination."""
        query = select(XeroBankTransaction).where(
            XeroBankTransaction.connection_id == connection_id
        )

        if client_id is not None:
            query = query.where(XeroBankTransaction.client_id == client_id)
        if transaction_type is not None:
            query = query.where(XeroBankTransaction.transaction_type == transaction_type)
        if date_from is not None:
            query = query.where(XeroBankTransaction.transaction_date >= date_from)
        if date_to is not None:
            query = query.where(XeroBankTransaction.transaction_date <= date_to)

        # Get total count
        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        # Get paginated results
        result = await self.session.execute(
            query.order_by(XeroBankTransaction.transaction_date.desc()).limit(limit).offset(offset)
        )
        transactions = list(result.scalars().all())

        return transactions, total

    async def list_by_client(
        self,
        client_id: UUID,
        transaction_type: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[XeroBankTransaction], int]:
        """List transactions for a specific client with filtering and pagination.

        Args:
            client_id: The client ID.
            transaction_type: Filter by type (receive, spend, etc.).
            from_date: Filter by transaction_date >= from_date.
            to_date: Filter by transaction_date <= to_date.
            limit: Max records to return.
            offset: Records to skip.

        Returns:
            Tuple of (transactions list, total count).
        """
        query = select(XeroBankTransaction).where(XeroBankTransaction.client_id == client_id)

        if transaction_type is not None:
            query = query.where(XeroBankTransaction.transaction_type == transaction_type)
        if from_date is not None:
            query = query.where(XeroBankTransaction.transaction_date >= from_date)
        if to_date is not None:
            query = query.where(XeroBankTransaction.transaction_date <= to_date)

        # Get total count
        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        # Get paginated results
        result = await self.session.execute(
            query.order_by(XeroBankTransaction.transaction_date.desc()).limit(limit).offset(offset)
        )
        transactions = list(result.scalars().all())

        return transactions, total

    async def count_by_client_and_date_range(
        self,
        client_id: UUID,
        from_date: date,
        to_date: date,
    ) -> int:
        """Count transactions for a client within a date range.

        Args:
            client_id: The client ID.
            from_date: Start date (inclusive).
            to_date: End date (inclusive).

        Returns:
            Number of transactions.
        """
        result = await self.session.execute(
            select(func.count()).where(
                and_(
                    XeroBankTransaction.client_id == client_id,
                    XeroBankTransaction.transaction_date >= from_date,
                    XeroBankTransaction.transaction_date <= to_date,
                )
            )
        )
        return result.scalar() or 0


class XeroAccountRepository:
    """Repository for XeroAccount CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: dict[str, Any]) -> XeroAccount:
        """Create a new account."""
        account = XeroAccount(**data)
        self.session.add(account)
        await self.session.flush()
        return account

    async def get_by_id(self, account_id: UUID) -> XeroAccount | None:
        """Get account by ID."""
        result = await self.session.execute(select(XeroAccount).where(XeroAccount.id == account_id))
        return result.scalar_one_or_none()

    async def get_by_xero_account_id(
        self, connection_id: UUID, xero_account_id: str
    ) -> XeroAccount | None:
        """Get account by Xero account ID."""
        result = await self.session.execute(
            select(XeroAccount).where(
                XeroAccount.connection_id == connection_id,
                XeroAccount.xero_account_id == xero_account_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_from_xero(self, data: dict[str, Any]) -> tuple[XeroAccount, bool]:
        """Upsert account from Xero data."""
        stmt = insert(XeroAccount).values(**data)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_xero_account_connection_account",
            set_={
                k: v
                for k, v in data.items()
                if k not in ("id", "tenant_id", "connection_id", "xero_account_id", "created_at")
            },
        ).returning(XeroAccount)

        result = await self.session.execute(stmt)
        account = result.scalar_one()
        created = account.created_at >= account.updated_at
        return account, created

    async def bulk_upsert(self, records: list[dict[str, Any]]) -> tuple[int, int]:
        """Bulk upsert accounts."""
        created = 0
        updated = 0
        for data in records:
            _, was_created = await self.upsert_from_xero(data)
            if was_created:
                created += 1
            else:
                updated += 1
        return created, updated

    async def list_by_connection(
        self,
        connection_id: UUID,
        is_active: bool | None = None,
        is_bas_relevant: bool | None = None,
    ) -> list[XeroAccount]:
        """List accounts for a connection (no pagination needed for chart of accounts)."""
        query = select(XeroAccount).where(XeroAccount.connection_id == connection_id)

        if is_active is not None:
            query = query.where(XeroAccount.is_active == is_active)
        if is_bas_relevant is not None:
            query = query.where(XeroAccount.is_bas_relevant == is_bas_relevant)

        result = await self.session.execute(query.order_by(XeroAccount.account_code))
        return list(result.scalars().all())


class XpmClientRepository:
    """Repository for XpmClient CRUD operations.

    XpmClient represents clients from Xero Practice Manager (XPM) - the businesses
    that an accounting practice manages BAS for. Each XPM client may have their own
    Xero organization that needs to be authorized separately.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session.
        """
        self.session = session

    async def create(self, data: dict[str, Any]) -> XpmClient:
        """Create a new XPM client.

        Args:
            data: Client data including tenant_id and xpm_client_id.

        Returns:
            The created XpmClient.
        """
        client = XpmClient(**data)
        self.session.add(client)
        await self.session.flush()
        return client

    async def get_by_id(self, client_id: UUID) -> XpmClient | None:
        """Get XPM client by ID.

        Note: RLS ensures only clients for the current tenant are returned.

        Args:
            client_id: The client ID.

        Returns:
            XpmClient if found, None otherwise.
        """
        result = await self.session.execute(select(XpmClient).where(XpmClient.id == client_id))
        return result.scalar_one_or_none()

    async def get_by_xpm_client_id(self, tenant_id: UUID, xpm_client_id: str) -> XpmClient | None:
        """Get XPM client by XPM's unique identifier.

        Args:
            tenant_id: The Clairo tenant ID.
            xpm_client_id: The XPM client ID.

        Returns:
            XpmClient if found, None otherwise.
        """
        result = await self.session.execute(
            select(XpmClient).where(
                XpmClient.tenant_id == tenant_id,
                XpmClient.xpm_client_id == xpm_client_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_xero_connection_id(self, xero_connection_id: UUID) -> XpmClient | None:
        """Get XPM client linked to a specific Xero connection.

        Args:
            xero_connection_id: The XeroConnection ID.

        Returns:
            XpmClient if found, None otherwise.
        """
        result = await self.session.execute(
            select(XpmClient).where(XpmClient.xero_connection_id == xero_connection_id)
        )
        return result.scalar_one_or_none()

    async def list_by_tenant(
        self,
        tenant_id: UUID,
        connection_status: XpmClientConnectionStatus | None = None,
        search: str | None = None,
        sort_by: Literal["name", "connection_status", "created_at"] = "name",
        sort_order: Literal["asc", "desc"] = "asc",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[XpmClient], int]:
        """List XPM clients for a tenant with filtering and pagination.

        Args:
            tenant_id: The tenant ID.
            connection_status: Filter by connection status.
            search: Search by client name (case-insensitive partial match).
            sort_by: Field to sort by.
            sort_order: Sort direction.
            limit: Max records to return.
            offset: Records to skip.

        Returns:
            Tuple of (clients list, total count).
        """
        query = select(XpmClient).where(XpmClient.tenant_id == tenant_id)

        if connection_status is not None:
            query = query.where(XpmClient.connection_status == connection_status)

        if search:
            query = query.where(XpmClient.name.ilike(f"%{search}%"))

        # Get total count
        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        # Apply sorting
        sort_column = {
            "name": XpmClient.name,
            "connection_status": XpmClient.connection_status,
            "created_at": XpmClient.created_at,
        }.get(sort_by, XpmClient.name)

        if sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # Get paginated results
        result = await self.session.execute(query.limit(limit).offset(offset))
        clients = list(result.scalars().all())

        return clients, total

    async def get_unconnected_clients(
        self,
        tenant_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[XpmClient], int]:
        """Get XPM clients that don't have Xero organizations connected yet.

        Args:
            tenant_id: The tenant ID.
            limit: Max records to return.
            offset: Records to skip.

        Returns:
            Tuple of (clients list, total count).
        """
        return await self.list_by_tenant(
            tenant_id=tenant_id,
            connection_status=XpmClientConnectionStatus.NOT_CONNECTED,
            limit=limit,
            offset=offset,
        )

    async def get_connected_clients(
        self,
        tenant_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[XpmClient], int]:
        """Get XPM clients that have Xero organizations connected.

        Args:
            tenant_id: The tenant ID.
            limit: Max records to return.
            offset: Records to skip.

        Returns:
            Tuple of (clients list, total count).
        """
        return await self.list_by_tenant(
            tenant_id=tenant_id,
            connection_status=XpmClientConnectionStatus.CONNECTED,
            limit=limit,
            offset=offset,
        )

    async def update_connection_status(
        self,
        client_id: UUID,
        status: XpmClientConnectionStatus,
        xero_connection_id: UUID | None = None,
        xero_org_name: str | None = None,
    ) -> XpmClient | None:
        """Update the Xero connection status for an XPM client.

        Args:
            client_id: The XPM client ID.
            status: New connection status.
            xero_connection_id: The XeroConnection ID (set when connecting).
            xero_org_name: The Xero organization name (cached for display).

        Returns:
            Updated XpmClient, or None if not found.
        """
        values: dict[str, Any] = {"connection_status": status}

        if status == XpmClientConnectionStatus.CONNECTED:
            values["xero_connection_id"] = xero_connection_id
            values["xero_connected_at"] = datetime.now(UTC)
            if xero_org_name:
                values["xero_org_name"] = xero_org_name
        elif status in (
            XpmClientConnectionStatus.DISCONNECTED,
            XpmClientConnectionStatus.NOT_CONNECTED,
        ):
            # Clear the connection when disconnected
            values["xero_connection_id"] = None

        await self.session.execute(
            update(XpmClient).where(XpmClient.id == client_id).values(**values)
        )

        return await self.get_by_id(client_id)

    async def link_xero_connection(
        self,
        client_id: UUID,
        xero_connection_id: UUID,
        xero_org_name: str | None = None,
    ) -> XpmClient | None:
        """Link an XPM client to a Xero connection.

        Convenience method that sets status to CONNECTED and links the connection.

        Args:
            client_id: The XPM client ID.
            xero_connection_id: The XeroConnection ID to link.
            xero_org_name: The Xero organization name.

        Returns:
            Updated XpmClient, or None if not found.
        """
        return await self.update_connection_status(
            client_id=client_id,
            status=XpmClientConnectionStatus.CONNECTED,
            xero_connection_id=xero_connection_id,
            xero_org_name=xero_org_name,
        )

    async def unlink_xero_connection(
        self, client_id: UUID, mark_as_disconnected: bool = True
    ) -> XpmClient | None:
        """Unlink an XPM client from its Xero connection.

        Args:
            client_id: The XPM client ID.
            mark_as_disconnected: If True, set status to DISCONNECTED (revoked).
                                  If False, set status to NOT_CONNECTED (never linked).

        Returns:
            Updated XpmClient, or None if not found.
        """
        status = (
            XpmClientConnectionStatus.DISCONNECTED
            if mark_as_disconnected
            else XpmClientConnectionStatus.NOT_CONNECTED
        )
        return await self.update_connection_status(
            client_id=client_id,
            status=status,
        )

    async def upsert_from_xpm(self, data: dict[str, Any]) -> tuple[XpmClient, bool]:
        """Upsert XPM client from XPM sync data.

        Uses PostgreSQL ON CONFLICT for atomic upsert on (tenant_id, xpm_client_id).

        Args:
            data: Client data including tenant_id and xpm_client_id.

        Returns:
            Tuple of (client, created) where created is True if new record.
        """
        stmt = insert(XpmClient).values(**data)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_xpm_client_tenant_xpm_id",
            set_={
                k: v
                for k, v in data.items()
                if k
                not in (
                    "id",
                    "tenant_id",
                    "xpm_client_id",
                    "created_at",
                    # Don't overwrite connection fields during XPM sync
                    "xero_connection_id",
                    "connection_status",
                    "xero_connected_at",
                )
            },
        ).returning(XpmClient)

        result = await self.session.execute(stmt)
        client = result.scalar_one()
        # Check if it was created (created_at == updated_at roughly)
        created = client.created_at >= client.updated_at
        return client, created

    async def bulk_upsert_from_xpm(self, records: list[dict[str, Any]]) -> tuple[int, int]:
        """Bulk upsert XPM clients from XPM sync.

        Args:
            records: List of client data dicts.

        Returns:
            Tuple of (created_count, updated_count).
        """
        created = 0
        updated = 0
        for data in records:
            _, was_created = await self.upsert_from_xpm(data)
            if was_created:
                created += 1
            else:
                updated += 1
        return created, updated

    async def count_by_tenant(self, tenant_id: UUID) -> int:
        """Count total XPM clients for a tenant.

        Args:
            tenant_id: The tenant ID.

        Returns:
            Number of clients.
        """
        result = await self.session.execute(
            select(func.count()).select_from(XpmClient).where(XpmClient.tenant_id == tenant_id)
        )
        return result.scalar() or 0

    async def count_by_connection_status(self, tenant_id: UUID) -> dict[str, int]:
        """Count XPM clients by connection status for a tenant.

        Args:
            tenant_id: The tenant ID.

        Returns:
            Dictionary mapping status to count.
        """
        result = await self.session.execute(
            select(
                XpmClient.connection_status,
                func.count().label("count"),
            )
            .where(XpmClient.tenant_id == tenant_id)
            .group_by(XpmClient.connection_status)
        )

        counts = {status.value: 0 for status in XpmClientConnectionStatus}
        for row in result:
            counts[row.connection_status.value] = row.count

        return counts

    async def search_by_name_or_abn(
        self,
        tenant_id: UUID,
        query: str,
        limit: int = 10,
    ) -> list[XpmClient]:
        """Search XPM clients by name or ABN.

        Useful for autocomplete/suggestion features.

        Args:
            tenant_id: The tenant ID.
            query: Search query (partial match on name, exact match on ABN).
            limit: Max results to return.

        Returns:
            List of matching XpmClient records.
        """
        # Try exact ABN match first (if query looks like ABN)
        clean_query = query.replace(" ", "")
        if clean_query.isdigit() and len(clean_query) <= 11:
            # Search by ABN prefix
            stmt = (
                select(XpmClient)
                .where(
                    XpmClient.tenant_id == tenant_id,
                    XpmClient.abn.like(f"{clean_query}%"),
                )
                .limit(limit)
            )
        else:
            # Search by name (case-insensitive)
            stmt = (
                select(XpmClient)
                .where(
                    XpmClient.tenant_id == tenant_id,
                    XpmClient.name.ilike(f"%{query}%"),
                )
                .order_by(XpmClient.name)
                .limit(limit)
            )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class XeroReportRepository:
    """Repository for XeroReport CRUD operations.

    Handles cached Xero financial reports (P&L, Balance Sheet, Aged AR/AP, etc.)
    with cache expiry checking and period key validation.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session.
        """
        self.session = session

    async def get_by_id(self, report_id: UUID) -> XeroReport | None:
        """Get report by ID.

        Note: RLS ensures only reports for the current tenant are returned.

        Args:
            report_id: The report ID.

        Returns:
            XeroReport if found, None otherwise.
        """
        result = await self.session.execute(select(XeroReport).where(XeroReport.id == report_id))
        return result.scalar_one_or_none()

    async def get_cached_report(
        self,
        connection_id: UUID,
        report_type: XeroReportType,
        period_key: str,
        include_expired: bool = False,
    ) -> XeroReport | None:
        """Get a cached report by connection, type, and period.

        The unique constraint on (connection_id, report_type, period_key) ensures
        at most one report exists for each combination.

        Args:
            connection_id: The XeroConnection ID.
            report_type: Type of report (P&L, Balance Sheet, etc.).
            period_key: Period identifier (e.g., '2025-FY', '2025-Q4', '2025-12').
            include_expired: If True, return even if cache has expired.

        Returns:
            XeroReport if found (and not expired unless include_expired=True).
        """
        query = select(XeroReport).where(
            XeroReport.connection_id == connection_id,
            XeroReport.report_type == report_type,
            XeroReport.period_key == period_key,
        )

        if not include_expired:
            query = query.where(XeroReport.cache_expires_at > datetime.now(UTC))

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_reports_by_connection(
        self,
        connection_id: UUID,
        report_type: XeroReportType | None = None,
        include_expired: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[XeroReport], int]:
        """List reports for a connection with filtering and pagination.

        Args:
            connection_id: The XeroConnection ID.
            report_type: Optional filter by report type.
            include_expired: If True, include expired cache entries.
            limit: Max records to return.
            offset: Records to skip.

        Returns:
            Tuple of (reports list, total count).
        """
        query = select(XeroReport).where(XeroReport.connection_id == connection_id)

        if report_type is not None:
            query = query.where(XeroReport.report_type == report_type)

        if not include_expired:
            query = query.where(XeroReport.cache_expires_at > datetime.now(UTC))

        # Get total count
        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        # Get paginated results
        result = await self.session.execute(
            query.order_by(XeroReport.period_key.desc()).limit(limit).offset(offset)
        )
        reports = list(result.scalars().all())

        return reports, total

    async def list_by_tenant(
        self,
        tenant_id: UUID,
        report_type: XeroReportType | None = None,
        include_expired: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[XeroReport], int]:
        """List reports for a tenant across all connections.

        RLS ensures only reports for the current tenant are returned.

        Args:
            tenant_id: The tenant ID.
            report_type: Optional filter by report type.
            include_expired: If True, include expired cache entries.
            limit: Max records to return.
            offset: Records to skip.

        Returns:
            Tuple of (reports list, total count).
        """
        query = select(XeroReport).where(XeroReport.tenant_id == tenant_id)

        if report_type is not None:
            query = query.where(XeroReport.report_type == report_type)

        if not include_expired:
            query = query.where(XeroReport.cache_expires_at > datetime.now(UTC))

        # Get total count
        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        # Get paginated results
        result = await self.session.execute(
            query.order_by(XeroReport.fetched_at.desc()).limit(limit).offset(offset)
        )
        reports = list(result.scalars().all())

        return reports, total

    async def upsert_report(self, data: dict[str, Any]) -> tuple[XeroReport, bool]:
        """Upsert a report record.

        Uses PostgreSQL ON CONFLICT on the unique constraint
        (connection_id, report_type, period_key) for atomic upsert.

        Args:
            data: Report data dict containing all required fields.

        Returns:
            Tuple of (report, created) where created is True if new record.
        """
        stmt = insert(XeroReport).values(**data)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_xero_reports_connection_type_period",
            set_={
                k: v
                for k, v in data.items()
                if k
                not in (
                    "id",
                    "tenant_id",
                    "connection_id",
                    "report_type",
                    "period_key",
                    "created_at",
                )
            },
        ).returning(XeroReport)

        result = await self.session.execute(stmt)
        report = result.scalar_one()
        # Check if it was created (created_at == updated_at roughly)
        created = report.created_at >= report.updated_at
        return report, created

    async def delete_expired(
        self,
        connection_id: UUID | None = None,
        before: datetime | None = None,
    ) -> int:
        """Delete expired cache entries.

        Args:
            connection_id: Optional connection to limit deletion to.
            before: Delete entries that expired before this time (default: now).

        Returns:
            Number of records deleted.
        """
        cutoff = before or datetime.now(UTC)
        query = delete(XeroReport).where(XeroReport.cache_expires_at < cutoff)

        if connection_id is not None:
            query = query.where(XeroReport.connection_id == connection_id)

        result = await self.session.execute(query)
        return result.rowcount

    async def invalidate_by_connection(self, connection_id: UUID) -> int:
        """Expire all cached reports for a connection by setting cache_expires_at to now.

        This forces subsequent reads to bypass cache and fetch fresh data
        from Xero, without deleting the rows (preserving audit history).

        Args:
            connection_id: The XeroConnection ID.

        Returns:
            Number of records invalidated.
        """
        now = datetime.now(UTC)
        stmt = (
            update(XeroReport)
            .where(
                XeroReport.connection_id == connection_id,
                XeroReport.cache_expires_at > now,
            )
            .values(cache_expires_at=now)
        )
        result = await self.session.execute(stmt)
        return result.rowcount

    async def get_stale_reports(
        self,
        connection_id: UUID,
        report_types: list[XeroReportType] | None = None,
    ) -> list[XeroReport]:
        """Get reports that have expired and need refresh.

        Args:
            connection_id: The XeroConnection ID.
            report_types: Optional list of types to check.

        Returns:
            List of expired XeroReport records.
        """
        query = select(XeroReport).where(
            XeroReport.connection_id == connection_id,
            XeroReport.cache_expires_at <= datetime.now(UTC),
        )

        if report_types:
            query = query.where(XeroReport.report_type.in_(report_types))

        result = await self.session.execute(query)
        return list(result.scalars().all())


class XeroReportSyncJobRepository:
    """Repository for XeroReportSyncJob CRUD operations.

    Tracks sync operations for Xero reports with audit trail.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session.
        """
        self.session = session

    async def create(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        report_type: XeroReportType,
        triggered_by: str = "scheduled",
        user_id: UUID | None = None,
    ) -> XeroReportSyncJob:
        """Create a new report sync job with pending status.

        Args:
            tenant_id: The tenant ID.
            connection_id: The XeroConnection ID.
            report_type: Type of report to sync.
            triggered_by: How the sync was triggered ('scheduled', 'on_demand', 'retry').
            user_id: User who triggered on-demand sync.

        Returns:
            The created XeroReportSyncJob.
        """
        job = XeroReportSyncJob(
            tenant_id=tenant_id,
            connection_id=connection_id,
            report_type=report_type,
            status=XeroReportSyncStatus.PENDING,
            triggered_by=triggered_by,
            user_id=user_id,
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_by_id(self, job_id: UUID) -> XeroReportSyncJob | None:
        """Get sync job by ID.

        Args:
            job_id: The job ID.

        Returns:
            XeroReportSyncJob if found, None otherwise.
        """
        result = await self.session.execute(
            select(XeroReportSyncJob).where(XeroReportSyncJob.id == job_id)
        )
        return result.scalar_one_or_none()

    async def get_active_for_connection(
        self,
        connection_id: UUID,
        report_type: XeroReportType | None = None,
    ) -> XeroReportSyncJob | None:
        """Get any active (pending or in_progress) job for connection.

        Args:
            connection_id: The XeroConnection ID.
            report_type: Optional report type filter.

        Returns:
            Active XeroReportSyncJob if exists, None otherwise.
        """
        query = select(XeroReportSyncJob).where(
            XeroReportSyncJob.connection_id == connection_id,
            XeroReportSyncJob.status.in_(
                [
                    XeroReportSyncStatus.PENDING,
                    XeroReportSyncStatus.IN_PROGRESS,
                ]
            ),
        )

        if report_type is not None:
            query = query.where(XeroReportSyncJob.report_type == report_type)

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def update_status(
        self,
        job_id: UUID,
        status: XeroReportSyncStatus,
        report_id: UUID | None = None,
        rows_fetched: int | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """Update job status and related fields.

        Args:
            job_id: The job ID.
            status: New status.
            report_id: The resulting report ID (if successful).
            rows_fetched: Number of rows in the fetched report.
            error_code: Error code (if failed).
            error_message: Error message (if failed).
        """
        values: dict[str, Any] = {"status": status}
        now = datetime.now(UTC)

        if status == XeroReportSyncStatus.IN_PROGRESS:
            values["started_at"] = now
        elif status in (
            XeroReportSyncStatus.COMPLETED,
            XeroReportSyncStatus.FAILED,
            XeroReportSyncStatus.SKIPPED,
        ):
            values["completed_at"] = now
            # Calculate duration if started_at exists
            job = await self.get_by_id(job_id)
            if job and job.started_at:
                duration = now - job.started_at
                values["duration_ms"] = int(duration.total_seconds() * 1000)

        if report_id is not None:
            values["report_id"] = report_id
        if rows_fetched is not None:
            values["rows_fetched"] = rows_fetched
        if error_code is not None:
            values["error_code"] = error_code
        if error_message is not None:
            values["error_message"] = error_message

        await self.session.execute(
            update(XeroReportSyncJob).where(XeroReportSyncJob.id == job_id).values(**values)
        )

    async def mark_for_retry(
        self,
        job_id: UUID,
        next_retry_at: datetime,
    ) -> None:
        """Mark a failed job for retry.

        Args:
            job_id: The job ID.
            next_retry_at: When to retry the job.
        """
        await self.session.execute(
            update(XeroReportSyncJob)
            .where(XeroReportSyncJob.id == job_id)
            .values(
                status=XeroReportSyncStatus.PENDING,
                next_retry_at=next_retry_at,
                retry_count=XeroReportSyncJob.retry_count + 1,
            )
        )

    async def list_by_connection(
        self,
        connection_id: UUID,
        report_type: XeroReportType | None = None,
        status: XeroReportSyncStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[XeroReportSyncJob], int]:
        """List sync jobs for a connection with filtering and pagination.

        Args:
            connection_id: The XeroConnection ID.
            report_type: Optional filter by report type.
            status: Optional filter by status.
            limit: Max records to return.
            offset: Records to skip.

        Returns:
            Tuple of (jobs list, total count).
        """
        query = select(XeroReportSyncJob).where(XeroReportSyncJob.connection_id == connection_id)

        if report_type is not None:
            query = query.where(XeroReportSyncJob.report_type == report_type)
        if status is not None:
            query = query.where(XeroReportSyncJob.status == status)

        # Get total count
        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        # Get paginated results
        result = await self.session.execute(
            query.order_by(XeroReportSyncJob.created_at.desc()).limit(limit).offset(offset)
        )
        jobs = list(result.scalars().all())

        return jobs, total

    async def get_pending_retries(
        self,
        before: datetime | None = None,
        limit: int = 100,
    ) -> list[XeroReportSyncJob]:
        """Get jobs that are pending retry.

        Args:
            before: Only jobs with next_retry_at before this time.
            limit: Max jobs to return.

        Returns:
            List of XeroReportSyncJob records ready for retry.
        """
        cutoff = before or datetime.now(UTC)
        result = await self.session.execute(
            select(XeroReportSyncJob)
            .where(
                XeroReportSyncJob.status == XeroReportSyncStatus.PENDING,
                XeroReportSyncJob.next_retry_at.is_not(None),
                XeroReportSyncJob.next_retry_at <= cutoff,
            )
            .order_by(XeroReportSyncJob.next_retry_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_recent_by_report_type(
        self,
        connection_id: UUID,
        report_type: XeroReportType,
        minutes: int = 5,
    ) -> XeroReportSyncJob | None:
        """Get most recent sync job for throttling check.

        Used to enforce refresh throttling (e.g., max 1 refresh per 5 minutes).

        Args:
            connection_id: The XeroConnection ID.
            report_type: Type of report.
            minutes: Look back window in minutes.

        Returns:
            Most recent XeroReportSyncJob if exists within window.
        """
        cutoff = datetime.now(UTC) - timedelta(minutes=minutes)
        result = await self.session.execute(
            select(XeroReportSyncJob)
            .where(
                XeroReportSyncJob.connection_id == connection_id,
                XeroReportSyncJob.report_type == report_type,
                XeroReportSyncJob.created_at >= cutoff,
            )
            .order_by(XeroReportSyncJob.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


# =============================================================================
# Credit Notes, Payments, Journals Repositories (Spec 024)
# =============================================================================


class XeroCreditNoteRepository:
    """Repository for XeroCreditNote CRUD operations.

    Handles synced credit notes from Xero (both AR and AP credit notes).
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    async def get_by_id(self, credit_note_id: UUID) -> XeroCreditNote | None:
        """Get credit note by ID."""
        result = await self.session.execute(
            select(XeroCreditNote).where(XeroCreditNote.id == credit_note_id)
        )
        return result.scalar_one_or_none()

    async def get_by_xero_credit_note_id(
        self, connection_id: UUID, xero_credit_note_id: str
    ) -> XeroCreditNote | None:
        """Get credit note by Xero credit note ID."""
        result = await self.session.execute(
            select(XeroCreditNote).where(
                XeroCreditNote.connection_id == connection_id,
                XeroCreditNote.xero_credit_note_id == xero_credit_note_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_from_xero(self, data: dict[str, Any]) -> tuple[XeroCreditNote, bool]:
        """Upsert credit note from Xero data."""
        stmt = insert(XeroCreditNote).values(**data)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_xero_credit_note_connection_cn",
            set_={
                k: v
                for k, v in data.items()
                if k
                not in ("id", "tenant_id", "connection_id", "xero_credit_note_id", "created_at")
            },
        ).returning(XeroCreditNote)

        result = await self.session.execute(stmt)
        credit_note = result.scalar_one()
        created = credit_note.created_at >= credit_note.updated_at
        return credit_note, created

    async def bulk_upsert(self, records: list[dict[str, Any]]) -> tuple[int, int]:
        """Bulk upsert credit notes."""
        created = 0
        updated = 0
        for data in records:
            _, was_created = await self.upsert_from_xero(data)
            if was_created:
                created += 1
            else:
                updated += 1
        return created, updated

    async def list_by_connection(
        self,
        connection_id: UUID,
        credit_note_type: XeroCreditNoteType | None = None,
        status: XeroCreditNoteStatus | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[XeroCreditNote], int]:
        """List credit notes for a connection with filtering and pagination."""
        query = select(XeroCreditNote).where(XeroCreditNote.connection_id == connection_id)

        if credit_note_type is not None:
            query = query.where(XeroCreditNote.credit_note_type == credit_note_type)
        if status is not None:
            query = query.where(XeroCreditNote.status == status)
        if date_from is not None:
            query = query.where(XeroCreditNote.issue_date >= date_from)
        if date_to is not None:
            query = query.where(XeroCreditNote.issue_date <= date_to)

        # Get total count
        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        # Get paginated results
        result = await self.session.execute(
            query.order_by(XeroCreditNote.issue_date.desc()).limit(limit).offset(offset)
        )
        credit_notes = list(result.scalars().all())

        return credit_notes, total

    async def get_for_period(
        self,
        connection_id: UUID,
        from_date: date,
        to_date: date,
        credit_note_type: XeroCreditNoteType | None = None,
    ) -> list[XeroCreditNote]:
        """Get credit notes for a BAS period.

        Args:
            connection_id: The XeroConnection ID.
            from_date: Period start date.
            to_date: Period end date.
            credit_note_type: Optional filter by type.

        Returns:
            List of credit notes in the period.
        """
        query = select(XeroCreditNote).where(
            XeroCreditNote.connection_id == connection_id,
            XeroCreditNote.issue_date >= from_date,
            XeroCreditNote.issue_date <= to_date,
            XeroCreditNote.status.in_(
                [
                    XeroCreditNoteStatus.AUTHORISED,
                    XeroCreditNoteStatus.PAID,
                ]
            ),
        )

        if credit_note_type is not None:
            query = query.where(XeroCreditNote.credit_note_type == credit_note_type)

        result = await self.session.execute(query.order_by(XeroCreditNote.issue_date))
        return list(result.scalars().all())

    async def calculate_summary(
        self,
        connection_id: UUID,
        from_date: date,
        to_date: date,
    ) -> dict[str, Any]:
        """Calculate credit note totals for GST calculations.

        Returns summary of credit notes by type with tax amounts.
        """
        result = await self.session.execute(
            select(
                # Sales credits (ACCRECCREDIT)
                func.count()
                .filter(XeroCreditNote.credit_note_type == XeroCreditNoteType.ACCRECCREDIT)
                .label("sales_credit_count"),
                func.coalesce(
                    func.sum(XeroCreditNote.total_amount).filter(
                        XeroCreditNote.credit_note_type == XeroCreditNoteType.ACCRECCREDIT
                    ),
                    Decimal("0.00"),
                ).label("total_sales_credits"),
                func.coalesce(
                    func.sum(XeroCreditNote.tax_amount).filter(
                        XeroCreditNote.credit_note_type == XeroCreditNoteType.ACCRECCREDIT
                    ),
                    Decimal("0.00"),
                ).label("gst_on_sales_credits"),
                # Purchase credits (ACCPAYCREDIT)
                func.count()
                .filter(XeroCreditNote.credit_note_type == XeroCreditNoteType.ACCPAYCREDIT)
                .label("purchase_credit_count"),
                func.coalesce(
                    func.sum(XeroCreditNote.total_amount).filter(
                        XeroCreditNote.credit_note_type == XeroCreditNoteType.ACCPAYCREDIT
                    ),
                    Decimal("0.00"),
                ).label("total_purchase_credits"),
                func.coalesce(
                    func.sum(XeroCreditNote.tax_amount).filter(
                        XeroCreditNote.credit_note_type == XeroCreditNoteType.ACCPAYCREDIT
                    ),
                    Decimal("0.00"),
                ).label("gst_on_purchase_credits"),
            ).where(
                and_(
                    XeroCreditNote.connection_id == connection_id,
                    XeroCreditNote.issue_date >= from_date,
                    XeroCreditNote.issue_date <= to_date,
                    XeroCreditNote.status.in_(
                        [
                            XeroCreditNoteStatus.AUTHORISED,
                            XeroCreditNoteStatus.PAID,
                        ]
                    ),
                )
            )
        )

        row = result.one()

        return {
            "sales_credit_count": row.sales_credit_count,
            "total_sales_credits": row.total_sales_credits,
            "gst_on_sales_credits": row.gst_on_sales_credits,
            "purchase_credit_count": row.purchase_credit_count,
            "total_purchase_credits": row.total_purchase_credits,
            "gst_on_purchase_credits": row.gst_on_purchase_credits,
        }


class XeroCreditNoteAllocationRepository:
    """Repository for XeroCreditNoteAllocation CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    async def get_by_credit_note(self, credit_note_id: UUID) -> list[XeroCreditNoteAllocation]:
        """Get all allocations for a credit note."""
        result = await self.session.execute(
            select(XeroCreditNoteAllocation)
            .where(XeroCreditNoteAllocation.credit_note_id == credit_note_id)
            .order_by(XeroCreditNoteAllocation.allocation_date)
        )
        return list(result.scalars().all())

    async def create_allocation(self, data: dict[str, Any]) -> XeroCreditNoteAllocation:
        """Create a credit note allocation."""
        allocation = XeroCreditNoteAllocation(**data)
        self.session.add(allocation)
        await self.session.flush()
        return allocation

    async def delete_for_credit_note(self, credit_note_id: UUID) -> int:
        """Delete all allocations for a credit note (for re-sync)."""
        result = await self.session.execute(
            delete(XeroCreditNoteAllocation).where(
                XeroCreditNoteAllocation.credit_note_id == credit_note_id
            )
        )
        return result.rowcount

    async def bulk_create(self, records: list[dict[str, Any]]) -> int:
        """Bulk create allocations."""
        for data in records:
            self.session.add(XeroCreditNoteAllocation(**data))
        await self.session.flush()
        return len(records)


class XeroPaymentRepository:
    """Repository for XeroPayment CRUD operations.

    Handles synced payments from Xero.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    async def get_by_id(self, payment_id: UUID) -> XeroPayment | None:
        """Get payment by ID."""
        result = await self.session.execute(select(XeroPayment).where(XeroPayment.id == payment_id))
        return result.scalar_one_or_none()

    async def get_by_xero_payment_id(
        self, connection_id: UUID, xero_payment_id: str
    ) -> XeroPayment | None:
        """Get payment by Xero payment ID."""
        result = await self.session.execute(
            select(XeroPayment).where(
                XeroPayment.connection_id == connection_id,
                XeroPayment.xero_payment_id == xero_payment_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_from_xero(self, data: dict[str, Any]) -> tuple[XeroPayment, bool]:
        """Upsert payment from Xero data."""
        stmt = insert(XeroPayment).values(**data)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_xero_payment_connection_payment",
            set_={
                k: v
                for k, v in data.items()
                if k not in ("id", "tenant_id", "connection_id", "xero_payment_id", "created_at")
            },
        ).returning(XeroPayment)

        result = await self.session.execute(stmt)
        payment = result.scalar_one()
        created = payment.created_at >= payment.updated_at
        return payment, created

    async def bulk_upsert(self, records: list[dict[str, Any]]) -> tuple[int, int]:
        """Bulk upsert payments."""
        created = 0
        updated = 0
        for data in records:
            _, was_created = await self.upsert_from_xero(data)
            if was_created:
                created += 1
            else:
                updated += 1
        return created, updated

    async def list_by_connection(
        self,
        connection_id: UUID,
        status: XeroPaymentStatus | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[XeroPayment], int]:
        """List payments for a connection with filtering and pagination."""
        query = select(XeroPayment).where(XeroPayment.connection_id == connection_id)

        if status is not None:
            query = query.where(XeroPayment.status == status)
        if date_from is not None:
            query = query.where(XeroPayment.payment_date >= date_from)
        if date_to is not None:
            query = query.where(XeroPayment.payment_date <= date_to)

        # Get total count
        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        # Get paginated results
        result = await self.session.execute(
            query.order_by(XeroPayment.payment_date.desc()).limit(limit).offset(offset)
        )
        payments = list(result.scalars().all())

        return payments, total

    async def get_payments_for_invoice(self, xero_invoice_id: str) -> list[XeroPayment]:
        """Get all payments for a specific invoice."""
        result = await self.session.execute(
            select(XeroPayment)
            .where(
                XeroPayment.xero_invoice_id == xero_invoice_id,
                XeroPayment.status == XeroPaymentStatus.AUTHORISED,
            )
            .order_by(XeroPayment.payment_date)
        )
        return list(result.scalars().all())

    async def get_payments_by_contact(
        self,
        connection_id: UUID,
        xero_contact_id: str,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 100,
    ) -> list[XeroPayment]:
        """Get payments for a specific contact.

        Joins with invoices to find payments for a contact.
        Used for cash flow analysis (Spec 024, User Story 4).

        Args:
            connection_id: The Xero connection ID.
            xero_contact_id: The Xero contact ID.
            date_from: Optional start date filter.
            date_to: Optional end date filter.
            limit: Maximum number of payments to return.

        Returns:
            List of payments for the contact, ordered by payment date.
        """
        query = (
            select(XeroPayment)
            .join(XeroInvoice, XeroPayment.xero_invoice_id == XeroInvoice.xero_invoice_id)
            .where(
                XeroPayment.connection_id == connection_id,
                XeroInvoice.xero_contact_id == xero_contact_id,
                XeroPayment.status == XeroPaymentStatus.AUTHORISED,
            )
        )

        if date_from is not None:
            query = query.where(XeroPayment.payment_date >= date_from)
        if date_to is not None:
            query = query.where(XeroPayment.payment_date <= date_to)

        result = await self.session.execute(
            query.order_by(XeroPayment.payment_date.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def get_payment_stats_by_connection(
        self,
        connection_id: UUID,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict[str, Any]:
        """Get payment statistics for a connection.

        Calculates aggregate statistics for cash flow analysis.

        Args:
            connection_id: The Xero connection ID.
            date_from: Optional start date filter.
            date_to: Optional end date filter.

        Returns:
            Dictionary with payment statistics.
        """
        query = select(
            func.count(XeroPayment.id).label("payment_count"),
            func.sum(XeroPayment.amount).label("total_amount"),
            func.avg(XeroPayment.amount).label("average_amount"),
            func.min(XeroPayment.payment_date).label("earliest_payment"),
            func.max(XeroPayment.payment_date).label("latest_payment"),
        ).where(
            XeroPayment.connection_id == connection_id,
            XeroPayment.status == XeroPaymentStatus.AUTHORISED,
        )

        if date_from is not None:
            query = query.where(XeroPayment.payment_date >= date_from)
        if date_to is not None:
            query = query.where(XeroPayment.payment_date <= date_to)

        result = await self.session.execute(query)
        row = result.one()

        return {
            "payment_count": row.payment_count or 0,
            "total_amount": row.total_amount or Decimal("0.00"),
            "average_amount": row.average_amount or Decimal("0.00"),
            "earliest_payment": row.earliest_payment,
            "latest_payment": row.latest_payment,
        }


class XeroOverpaymentRepository:
    """Repository for XeroOverpayment CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    async def get_by_id(self, overpayment_id: UUID) -> XeroOverpayment | None:
        """Get overpayment by ID."""
        result = await self.session.execute(
            select(XeroOverpayment).where(XeroOverpayment.id == overpayment_id)
        )
        return result.scalar_one_or_none()

    async def upsert_from_xero(self, data: dict[str, Any]) -> tuple[XeroOverpayment, bool]:
        """Upsert overpayment from Xero data."""
        stmt = insert(XeroOverpayment).values(**data)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_xero_overpayment_connection_op",
            set_={
                k: v
                for k, v in data.items()
                if k
                not in ("id", "tenant_id", "connection_id", "xero_overpayment_id", "created_at")
            },
        ).returning(XeroOverpayment)

        result = await self.session.execute(stmt)
        overpayment = result.scalar_one()
        created = overpayment.created_at >= overpayment.updated_at
        return overpayment, created

    async def bulk_upsert(self, records: list[dict[str, Any]]) -> tuple[int, int]:
        """Bulk upsert overpayments."""
        created = 0
        updated = 0
        for data in records:
            _, was_created = await self.upsert_from_xero(data)
            if was_created:
                created += 1
            else:
                updated += 1
        return created, updated

    async def list_by_connection(
        self,
        connection_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[XeroOverpayment], int]:
        """List overpayments for a connection."""
        query = select(XeroOverpayment).where(XeroOverpayment.connection_id == connection_id)

        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        result = await self.session.execute(
            query.order_by(XeroOverpayment.overpayment_date.desc()).limit(limit).offset(offset)
        )
        overpayments = list(result.scalars().all())

        return overpayments, total


class XeroPrepaymentRepository:
    """Repository for XeroPrepayment CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    async def get_by_id(self, prepayment_id: UUID) -> XeroPrepayment | None:
        """Get prepayment by ID."""
        result = await self.session.execute(
            select(XeroPrepayment).where(XeroPrepayment.id == prepayment_id)
        )
        return result.scalar_one_or_none()

    async def upsert_from_xero(self, data: dict[str, Any]) -> tuple[XeroPrepayment, bool]:
        """Upsert prepayment from Xero data."""
        stmt = insert(XeroPrepayment).values(**data)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_xero_prepayment_connection_pp",
            set_={
                k: v
                for k, v in data.items()
                if k not in ("id", "tenant_id", "connection_id", "xero_prepayment_id", "created_at")
            },
        ).returning(XeroPrepayment)

        result = await self.session.execute(stmt)
        prepayment = result.scalar_one()
        created = prepayment.created_at >= prepayment.updated_at
        return prepayment, created

    async def bulk_upsert(self, records: list[dict[str, Any]]) -> tuple[int, int]:
        """Bulk upsert prepayments."""
        created = 0
        updated = 0
        for data in records:
            _, was_created = await self.upsert_from_xero(data)
            if was_created:
                created += 1
            else:
                updated += 1
        return created, updated

    async def list_by_connection(
        self,
        connection_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[XeroPrepayment], int]:
        """List prepayments for a connection."""
        query = select(XeroPrepayment).where(XeroPrepayment.connection_id == connection_id)

        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        result = await self.session.execute(
            query.order_by(XeroPrepayment.prepayment_date.desc()).limit(limit).offset(offset)
        )
        prepayments = list(result.scalars().all())

        return prepayments, total


class XeroJournalRepository:
    """Repository for XeroJournal CRUD operations.

    Handles system-generated journals from Xero (read-only, created by transactions).
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    async def get_by_id(self, journal_id: UUID) -> XeroJournal | None:
        """Get journal by ID."""
        result = await self.session.execute(select(XeroJournal).where(XeroJournal.id == journal_id))
        return result.scalar_one_or_none()

    async def get_by_xero_journal_id(
        self, connection_id: UUID, xero_journal_id: str
    ) -> XeroJournal | None:
        """Get journal by Xero journal ID."""
        result = await self.session.execute(
            select(XeroJournal).where(
                XeroJournal.connection_id == connection_id,
                XeroJournal.xero_journal_id == xero_journal_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_from_xero(self, data: dict[str, Any]) -> tuple[XeroJournal, bool]:
        """Upsert journal from Xero data."""
        stmt = insert(XeroJournal).values(**data)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_xero_journal_connection_journal",
            set_={
                k: v
                for k, v in data.items()
                if k not in ("id", "tenant_id", "connection_id", "xero_journal_id", "created_at")
            },
        ).returning(XeroJournal)

        result = await self.session.execute(stmt)
        journal = result.scalar_one()
        created = journal.created_at >= journal.updated_at
        return journal, created

    async def bulk_upsert(self, records: list[dict[str, Any]]) -> tuple[int, int]:
        """Bulk upsert journals."""
        created = 0
        updated = 0
        for data in records:
            _, was_created = await self.upsert_from_xero(data)
            if was_created:
                created += 1
            else:
                updated += 1
        return created, updated

    async def list_by_connection(
        self,
        connection_id: UUID,
        source_type: XeroJournalSourceType | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[XeroJournal], int]:
        """List journals for a connection with filtering and pagination."""
        query = select(XeroJournal).where(XeroJournal.connection_id == connection_id)

        if source_type is not None:
            query = query.where(XeroJournal.source_type == source_type)
        if date_from is not None:
            query = query.where(XeroJournal.journal_date >= date_from)
        if date_to is not None:
            query = query.where(XeroJournal.journal_date <= date_to)

        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        result = await self.session.execute(
            query.order_by(XeroJournal.journal_number.desc()).limit(limit).offset(offset)
        )
        journals = list(result.scalars().all())

        return journals, total

    async def get_by_source(
        self,
        connection_id: UUID,
        source_id: str,
        source_type: XeroJournalSourceType,
    ) -> list[XeroJournal]:
        """Get journals by source transaction."""
        result = await self.session.execute(
            select(XeroJournal)
            .where(
                XeroJournal.connection_id == connection_id,
                XeroJournal.source_id == source_id,
                XeroJournal.source_type == source_type,
            )
            .order_by(XeroJournal.journal_number)
        )
        return list(result.scalars().all())

    async def get_latest_journal_number(self, connection_id: UUID) -> int | None:
        """Get the highest journal number for incremental sync."""
        result = await self.session.execute(
            select(func.max(XeroJournal.journal_number)).where(
                XeroJournal.connection_id == connection_id
            )
        )
        return result.scalar()


class XeroManualJournalRepository:
    """Repository for XeroManualJournal CRUD operations.

    Handles manual (adjusting) journals from Xero.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    async def get_by_id(self, manual_journal_id: UUID) -> XeroManualJournal | None:
        """Get manual journal by ID."""
        result = await self.session.execute(
            select(XeroManualJournal).where(XeroManualJournal.id == manual_journal_id)
        )
        return result.scalar_one_or_none()

    async def get_by_xero_manual_journal_id(
        self, connection_id: UUID, xero_manual_journal_id: str
    ) -> XeroManualJournal | None:
        """Get manual journal by Xero manual journal ID."""
        result = await self.session.execute(
            select(XeroManualJournal).where(
                XeroManualJournal.connection_id == connection_id,
                XeroManualJournal.xero_manual_journal_id == xero_manual_journal_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_from_xero(self, data: dict[str, Any]) -> tuple[XeroManualJournal, bool]:
        """Upsert manual journal from Xero data."""
        stmt = insert(XeroManualJournal).values(**data)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_xero_manual_journal_connection_mj",
            set_={
                k: v
                for k, v in data.items()
                if k
                not in ("id", "tenant_id", "connection_id", "xero_manual_journal_id", "created_at")
            },
        ).returning(XeroManualJournal)

        result = await self.session.execute(stmt)
        manual_journal = result.scalar_one()
        created = manual_journal.created_at >= manual_journal.updated_at
        return manual_journal, created

    async def bulk_upsert(self, records: list[dict[str, Any]]) -> tuple[int, int]:
        """Bulk upsert manual journals."""
        created = 0
        updated = 0
        for data in records:
            _, was_created = await self.upsert_from_xero(data)
            if was_created:
                created += 1
            else:
                updated += 1
        return created, updated

    async def list_by_connection(
        self,
        connection_id: UUID,
        status: XeroManualJournalStatus | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[XeroManualJournal], int]:
        """List manual journals for a connection with filtering and pagination."""
        query = select(XeroManualJournal).where(XeroManualJournal.connection_id == connection_id)

        if status is not None:
            query = query.where(XeroManualJournal.status == status)
        if date_from is not None:
            query = query.where(XeroManualJournal.journal_date >= date_from)
        if date_to is not None:
            query = query.where(XeroManualJournal.journal_date <= date_to)

        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        result = await self.session.execute(
            query.order_by(XeroManualJournal.journal_date.desc()).limit(limit).offset(offset)
        )
        manual_journals = list(result.scalars().all())

        return manual_journals, total

    async def get_for_period(
        self,
        connection_id: UUID,
        from_date: date,
        to_date: date,
    ) -> list[XeroManualJournal]:
        """Get manual journals for a BAS period (posted only)."""
        result = await self.session.execute(
            select(XeroManualJournal)
            .where(
                XeroManualJournal.connection_id == connection_id,
                XeroManualJournal.journal_date >= from_date,
                XeroManualJournal.journal_date <= to_date,
                XeroManualJournal.status == XeroManualJournalStatus.POSTED,
            )
            .order_by(XeroManualJournal.journal_date)
        )
        return list(result.scalars().all())

    async def get_gst_adjustments(
        self,
        connection_id: UUID,
        from_date: date,
        to_date: date,
    ) -> list[XeroManualJournal]:
        """Get manual journals that affect GST accounts for audit purposes.

        Identifies manual journals with lines that have GST tax types.
        """
        # This requires filtering by JSONB content - get all and filter in Python
        # A more efficient approach would use a GIN index on the JSONB column
        journals = await self.get_for_period(connection_id, from_date, to_date)

        gst_journals = []
        gst_tax_types = {"OUTPUT", "INPUT", "OUTPUT2", "INPUT2", "GSTONIMPORTS"}

        for journal in journals:
            for line in journal.journal_lines or []:
                tax_type = line.get("tax_type", "").upper()
                if tax_type in gst_tax_types:
                    gst_journals.append(journal)
                    break

        return gst_journals


class XeroAssetTypeRepository:
    """Repository for XeroAssetType CRUD operations.

    Handles asset types (depreciation categories) from Xero Assets API.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    async def get_by_id(self, asset_type_id: UUID) -> XeroAssetType | None:
        """Get asset type by ID."""
        result = await self.session.execute(
            select(XeroAssetType).where(XeroAssetType.id == asset_type_id)
        )
        return result.scalar_one_or_none()

    async def get_by_xero_asset_type_id(
        self, connection_id: UUID, xero_asset_type_id: str
    ) -> XeroAssetType | None:
        """Get asset type by Xero asset type ID."""
        result = await self.session.execute(
            select(XeroAssetType).where(
                XeroAssetType.connection_id == connection_id,
                XeroAssetType.xero_asset_type_id == xero_asset_type_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_from_xero(self, data: dict[str, Any]) -> tuple[XeroAssetType, bool]:
        """Upsert asset type from Xero data."""
        stmt = insert(XeroAssetType).values(**data)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_xero_asset_types_connection_xero_id",
            set_={
                k: v
                for k, v in data.items()
                if k not in ("id", "tenant_id", "connection_id", "xero_asset_type_id", "created_at")
            },
        ).returning(XeroAssetType)

        result = await self.session.execute(stmt)
        asset_type = result.scalar_one()
        created = asset_type.created_at >= asset_type.updated_at
        return asset_type, created

    async def bulk_upsert(self, records: list[dict[str, Any]]) -> tuple[int, int]:
        """Bulk upsert asset types."""
        created = 0
        updated = 0
        for data in records:
            _, was_created = await self.upsert_from_xero(data)
            if was_created:
                created += 1
            else:
                updated += 1
        return created, updated

    async def list_by_connection(
        self,
        connection_id: UUID,
    ) -> list[XeroAssetType]:
        """List all asset types for a connection (no pagination needed)."""
        result = await self.session.execute(
            select(XeroAssetType)
            .where(XeroAssetType.connection_id == connection_id)
            .order_by(XeroAssetType.asset_type_name)
        )
        return list(result.scalars().all())

    async def count_by_connection(self, connection_id: UUID, tenant_id: UUID) -> int:
        """Count asset types for a connection."""
        result = await self.session.execute(
            select(func.count(XeroAssetType.id)).where(
                XeroAssetType.connection_id == connection_id,
                XeroAssetType.tenant_id == tenant_id,
            )
        )
        return result.scalar() or 0


class XeroAssetRepository:
    """Repository for XeroAsset CRUD operations.

    Handles fixed assets from Xero Assets API including depreciation details.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    async def get_by_id(self, asset_id: UUID) -> XeroAsset | None:
        """Get asset by ID."""
        result = await self.session.execute(select(XeroAsset).where(XeroAsset.id == asset_id))
        return result.scalar_one_or_none()

    async def get_by_xero_asset_id(
        self, connection_id: UUID, xero_asset_id: str
    ) -> XeroAsset | None:
        """Get asset by Xero asset ID."""
        result = await self.session.execute(
            select(XeroAsset).where(
                XeroAsset.connection_id == connection_id,
                XeroAsset.xero_asset_id == xero_asset_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_from_xero(self, data: dict[str, Any]) -> tuple[XeroAsset, bool]:
        """Upsert asset from Xero data."""
        stmt = insert(XeroAsset).values(**data)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_xero_assets_connection_xero_id",
            set_={
                k: v
                for k, v in data.items()
                if k not in ("id", "tenant_id", "connection_id", "xero_asset_id", "created_at")
            },
        ).returning(XeroAsset)

        result = await self.session.execute(stmt)
        asset = result.scalar_one()
        created = asset.created_at >= asset.updated_at
        return asset, created

    async def bulk_upsert(self, records: list[dict[str, Any]]) -> tuple[int, int]:
        """Bulk upsert assets."""
        created = 0
        updated = 0
        for data in records:
            _, was_created = await self.upsert_from_xero(data)
            if was_created:
                created += 1
            else:
                updated += 1
        return created, updated

    async def list_by_connection(
        self,
        connection_id: UUID,
        status: XeroAssetStatus | None = None,
        asset_type_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[XeroAsset], int]:
        """List assets for a connection with filtering and pagination."""
        query = select(XeroAsset).where(XeroAsset.connection_id == connection_id)

        if status is not None:
            query = query.where(XeroAsset.status == status.value)
        if asset_type_id is not None:
            query = query.where(XeroAsset.asset_type_id == asset_type_id)

        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        result = await self.session.execute(
            query.order_by(XeroAsset.purchase_date.desc()).limit(limit).offset(offset)
        )
        assets = list(result.scalars().all())

        return assets, total

    async def get_assets_by_status(
        self,
        connection_id: UUID,
        status: XeroAssetStatus,
    ) -> list[XeroAsset]:
        """Get assets by status."""
        result = await self.session.execute(
            select(XeroAsset)
            .where(
                XeroAsset.connection_id == connection_id,
                XeroAsset.status == status.value,
            )
            .order_by(XeroAsset.purchase_date.desc())
        )
        return list(result.scalars().all())

    async def get_assets_by_purchase_date_range(
        self,
        connection_id: UUID,
        from_date: date,
        to_date: date,
    ) -> list[XeroAsset]:
        """Get assets purchased within a date range.

        Useful for instant asset write-off detection and capital expenditure analysis.
        """
        result = await self.session.execute(
            select(XeroAsset)
            .where(
                XeroAsset.connection_id == connection_id,
                XeroAsset.purchase_date >= from_date,
                XeroAsset.purchase_date <= to_date,
            )
            .order_by(XeroAsset.purchase_date.desc())
        )
        return list(result.scalars().all())

    async def get_eligible_for_instant_write_off(
        self,
        connection_id: UUID,
        threshold: Decimal,
        from_date: date,
        to_date: date,
    ) -> list[XeroAsset]:
        """Get assets eligible for instant asset write-off.

        Returns registered/draft assets purchased within the period
        with purchase price below the threshold.

        Args:
            connection_id: Xero connection ID.
            threshold: Maximum purchase price for eligibility (e.g., $20,000).
            from_date: Start of eligible period.
            to_date: End of eligible period.

        Returns:
            List of eligible assets.
        """
        result = await self.session.execute(
            select(XeroAsset)
            .where(
                XeroAsset.connection_id == connection_id,
                XeroAsset.purchase_date >= from_date,
                XeroAsset.purchase_date <= to_date,
                XeroAsset.purchase_price < threshold,
                XeroAsset.status.in_(["Registered", "Draft"]),
            )
            .order_by(XeroAsset.purchase_date.desc())
        )
        return list(result.scalars().all())

    async def get_fully_depreciated_assets(
        self,
        connection_id: UUID,
    ) -> list[XeroAsset]:
        """Get assets that are fully depreciated (book value = 0).

        Useful for replacement planning and capex analysis.
        """
        result = await self.session.execute(
            select(XeroAsset)
            .where(
                XeroAsset.connection_id == connection_id,
                XeroAsset.status == XeroAssetStatus.REGISTERED.value,
                XeroAsset.book_value == 0,
            )
            .order_by(XeroAsset.purchase_date)
        )
        return list(result.scalars().all())

    async def get_depreciation_summary(
        self,
        connection_id: UUID,
    ) -> dict[str, Any]:
        """Get depreciation summary for all registered assets.

        Returns:
            Dictionary with:
            - total_cost: Sum of all purchase prices
            - total_book_value: Sum of all current book values
            - total_accumulated_depreciation: Difference between cost and book value
            - asset_count: Number of registered assets
        """
        result = await self.session.execute(
            select(
                func.sum(XeroAsset.purchase_price).label("total_cost"),
                func.sum(XeroAsset.book_value).label("total_book_value"),
                func.count(XeroAsset.id).label("asset_count"),
            ).where(
                XeroAsset.connection_id == connection_id,
                XeroAsset.status == XeroAssetStatus.REGISTERED.value,
            )
        )
        row = result.one()
        total_cost = row.total_cost or Decimal("0")
        total_book_value = row.total_book_value or Decimal("0")

        return {
            "total_cost": total_cost,
            "total_book_value": total_book_value,
            "total_accumulated_depreciation": total_cost - total_book_value,
            "asset_count": row.asset_count or 0,
        }

    async def count_by_connection(self, connection_id: UUID, tenant_id: UUID) -> int:
        """Count assets for a connection."""
        result = await self.session.execute(
            select(func.count(XeroAsset.id)).where(
                XeroAsset.connection_id == connection_id,
                XeroAsset.tenant_id == tenant_id,
            )
        )
        return result.scalar() or 0


# =============================================================================
# Spec 025: Purchase Orders, Repeating Invoices, Tracking, Quotes
# =============================================================================


class XeroPurchaseOrderRepository:
    """Repository for XeroPurchaseOrder CRUD operations.

    Handles purchase orders from Xero for cash flow forecasting.
    Spec 025: Fixed Assets & Enhanced Analysis
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    async def get_by_id(self, po_id: UUID) -> XeroPurchaseOrder | None:
        """Get purchase order by ID."""
        result = await self.session.execute(
            select(XeroPurchaseOrder).where(XeroPurchaseOrder.id == po_id)
        )
        return result.scalar_one_or_none()

    async def get_by_xero_id(
        self, connection_id: UUID, xero_po_id: str
    ) -> XeroPurchaseOrder | None:
        """Get purchase order by Xero PO ID."""
        result = await self.session.execute(
            select(XeroPurchaseOrder).where(
                XeroPurchaseOrder.connection_id == connection_id,
                XeroPurchaseOrder.xero_purchase_order_id == xero_po_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_from_xero(self, data: dict[str, Any]) -> tuple[XeroPurchaseOrder, bool]:
        """Upsert purchase order from Xero data."""
        stmt = insert(XeroPurchaseOrder).values(**data)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_xero_purchase_order_connection_po",
            set_={
                k: v
                for k, v in data.items()
                if k
                not in ("id", "tenant_id", "connection_id", "xero_purchase_order_id", "created_at")
            },
        ).returning(XeroPurchaseOrder)

        result = await self.session.execute(stmt)
        po = result.scalar_one()
        created = po.created_at >= po.updated_at
        return po, created

    async def bulk_upsert(self, records: list[dict[str, Any]]) -> tuple[int, int]:
        """Bulk upsert purchase orders."""
        created = 0
        updated = 0
        for data in records:
            _, was_created = await self.upsert_from_xero(data)
            if was_created:
                created += 1
            else:
                updated += 1
        return created, updated

    async def list_by_connection(
        self,
        connection_id: UUID,
        status: str | XeroPurchaseOrderStatus | None = None,
        limit: int = 50,
        offset: int = 0,
        tenant_id: UUID | None = None,  # For API consistency (connection already scopes to tenant)
    ) -> tuple[list[XeroPurchaseOrder], int]:
        """List purchase orders for a connection with filtering and pagination.

        Args:
            connection_id: The connection ID to filter by.
            status: Optional status filter (string or enum).
            limit: Max records to return.
            offset: Records to skip.
            tenant_id: For API consistency (not used, connection already scopes to tenant).

        Returns:
            Tuple of (purchase orders list, total count).
        """
        query = select(XeroPurchaseOrder).where(XeroPurchaseOrder.connection_id == connection_id)

        if status is not None:
            # Handle both string and enum status
            status_value = status.value if isinstance(status, XeroPurchaseOrderStatus) else status
            query = query.where(XeroPurchaseOrder.status == status_value)

        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        result = await self.session.execute(
            query.order_by(XeroPurchaseOrder.date.desc()).limit(limit).offset(offset)
        )
        orders = list(result.scalars().all())

        return orders, total

    async def get_outstanding_orders(self, connection_id: UUID) -> list[XeroPurchaseOrder]:
        """Get outstanding purchase orders (not billed or deleted)."""
        result = await self.session.execute(
            select(XeroPurchaseOrder)
            .where(
                XeroPurchaseOrder.connection_id == connection_id,
                XeroPurchaseOrder.status.in_(
                    [
                        XeroPurchaseOrderStatus.DRAFT.value,
                        XeroPurchaseOrderStatus.SUBMITTED.value,
                        XeroPurchaseOrderStatus.AUTHORISED.value,
                    ]
                ),
            )
            .order_by(XeroPurchaseOrder.delivery_date.asc().nulls_last())
        )
        return list(result.scalars().all())

    async def get_cash_flow_summary(self, connection_id: UUID) -> dict[str, Any]:
        """Get summary of outstanding POs for cash flow forecasting."""
        result = await self.session.execute(
            select(
                func.count(XeroPurchaseOrder.id).label("order_count"),
                func.sum(XeroPurchaseOrder.total).label("total_value"),
            ).where(
                XeroPurchaseOrder.connection_id == connection_id,
                XeroPurchaseOrder.status.in_(
                    [
                        XeroPurchaseOrderStatus.DRAFT.value,
                        XeroPurchaseOrderStatus.SUBMITTED.value,
                        XeroPurchaseOrderStatus.AUTHORISED.value,
                    ]
                ),
            )
        )
        row = result.one()
        return {
            "order_count": row.order_count or 0,
            "total_value": row.total_value or Decimal("0"),
        }

    async def count_by_connection(self, connection_id: UUID, tenant_id: UUID) -> int:
        """Count purchase orders for a connection."""
        result = await self.session.execute(
            select(func.count(XeroPurchaseOrder.id)).where(
                XeroPurchaseOrder.connection_id == connection_id,
                XeroPurchaseOrder.tenant_id == tenant_id,
            )
        )
        return result.scalar() or 0

    async def get_outstanding_summary(
        self, connection_id: UUID, tenant_id: UUID
    ) -> tuple[int, Decimal]:
        """Get count and value of outstanding purchase orders.

        Returns:
            Tuple of (count, total_value).
        """
        result = await self.session.execute(
            select(
                func.count(XeroPurchaseOrder.id).label("count"),
                func.coalesce(func.sum(XeroPurchaseOrder.total), 0).label("total"),
            ).where(
                XeroPurchaseOrder.connection_id == connection_id,
                XeroPurchaseOrder.tenant_id == tenant_id,
                XeroPurchaseOrder.status.in_(
                    [
                        XeroPurchaseOrderStatus.DRAFT.value,
                        XeroPurchaseOrderStatus.SUBMITTED.value,
                        XeroPurchaseOrderStatus.AUTHORISED.value,
                    ]
                ),
            )
        )
        row = result.one()
        return row.count or 0, Decimal(str(row.total or 0))


class XeroRepeatingInvoiceRepository:
    """Repository for XeroRepeatingInvoice CRUD operations.

    Handles repeating invoice templates for recurring revenue/expense forecasting.
    Spec 025: Fixed Assets & Enhanced Analysis
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    async def get_by_id(self, ri_id: UUID) -> XeroRepeatingInvoice | None:
        """Get repeating invoice by ID."""
        result = await self.session.execute(
            select(XeroRepeatingInvoice).where(XeroRepeatingInvoice.id == ri_id)
        )
        return result.scalar_one_or_none()

    async def get_by_xero_id(
        self, connection_id: UUID, xero_ri_id: str
    ) -> XeroRepeatingInvoice | None:
        """Get repeating invoice by Xero ID."""
        result = await self.session.execute(
            select(XeroRepeatingInvoice).where(
                XeroRepeatingInvoice.connection_id == connection_id,
                XeroRepeatingInvoice.xero_repeating_invoice_id == xero_ri_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_from_xero(self, data: dict[str, Any]) -> tuple[XeroRepeatingInvoice, bool]:
        """Upsert repeating invoice from Xero data."""
        stmt = insert(XeroRepeatingInvoice).values(**data)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_xero_repeating_invoice_connection_ri",
            set_={
                k: v
                for k, v in data.items()
                if k
                not in (
                    "id",
                    "tenant_id",
                    "connection_id",
                    "xero_repeating_invoice_id",
                    "created_at",
                )
            },
        ).returning(XeroRepeatingInvoice)

        result = await self.session.execute(stmt)
        ri = result.scalar_one()
        created = ri.created_at >= ri.updated_at
        return ri, created

    async def bulk_upsert(self, records: list[dict[str, Any]]) -> tuple[int, int]:
        """Bulk upsert repeating invoices."""
        created = 0
        updated = 0
        for data in records:
            _, was_created = await self.upsert_from_xero(data)
            if was_created:
                created += 1
            else:
                updated += 1
        return created, updated

    async def list_by_connection(
        self,
        connection_id: UUID,
        status: XeroRepeatingInvoiceStatus | None = None,
        invoice_type: str | None = None,  # "ACCPAY" or "ACCREC"
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[XeroRepeatingInvoice], int]:
        """List repeating invoices for a connection with filtering and pagination."""
        query = select(XeroRepeatingInvoice).where(
            XeroRepeatingInvoice.connection_id == connection_id
        )

        if status is not None:
            query = query.where(XeroRepeatingInvoice.status == status.value)
        if invoice_type is not None:
            query = query.where(XeroRepeatingInvoice.invoice_type == invoice_type)

        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        result = await self.session.execute(
            query.order_by(XeroRepeatingInvoice.schedule_next_scheduled_date.asc().nulls_last())
            .limit(limit)
            .offset(offset)
        )
        invoices = list(result.scalars().all())

        return invoices, total

    async def get_active_invoices(self, connection_id: UUID) -> list[XeroRepeatingInvoice]:
        """Get active (authorised) repeating invoices."""
        result = await self.session.execute(
            select(XeroRepeatingInvoice)
            .where(
                XeroRepeatingInvoice.connection_id == connection_id,
                XeroRepeatingInvoice.status == XeroRepeatingInvoiceStatus.AUTHORISED.value,
            )
            .order_by(XeroRepeatingInvoice.schedule_next_scheduled_date.asc().nulls_last())
        )
        return list(result.scalars().all())

    async def count_by_connection(self, connection_id: UUID, tenant_id: UUID) -> int:
        """Count repeating invoices for a connection."""
        result = await self.session.execute(
            select(func.count(XeroRepeatingInvoice.id)).where(
                XeroRepeatingInvoice.connection_id == connection_id,
                XeroRepeatingInvoice.tenant_id == tenant_id,
            )
        )
        return result.scalar() or 0

    async def count_active(self, connection_id: UUID, tenant_id: UUID) -> int:
        """Count active repeating invoices for a connection."""
        result = await self.session.execute(
            select(func.count(XeroRepeatingInvoice.id)).where(
                XeroRepeatingInvoice.connection_id == connection_id,
                XeroRepeatingInvoice.tenant_id == tenant_id,
                XeroRepeatingInvoice.status == XeroRepeatingInvoiceStatus.AUTHORISED.value,
            )
        )
        return result.scalar() or 0

    async def get_monthly_recurring_summary(
        self, connection_id: UUID, tenant_id: UUID
    ) -> tuple[Decimal, Decimal]:
        """Get monthly recurring revenue and expense summary.

        Returns:
            Tuple of (monthly_revenue, monthly_expense).
        """
        # Get revenue (ACCREC - sales invoices)
        revenue_result = await self.session.execute(
            select(func.coalesce(func.sum(XeroRepeatingInvoice.total), 0).label("total")).where(
                XeroRepeatingInvoice.connection_id == connection_id,
                XeroRepeatingInvoice.tenant_id == tenant_id,
                XeroRepeatingInvoice.status == XeroRepeatingInvoiceStatus.AUTHORISED.value,
                XeroRepeatingInvoice.invoice_type == "ACCREC",
            )
        )
        revenue = Decimal(str(revenue_result.scalar() or 0))

        # Get expense (ACCPAY - bills)
        expense_result = await self.session.execute(
            select(func.coalesce(func.sum(XeroRepeatingInvoice.total), 0).label("total")).where(
                XeroRepeatingInvoice.connection_id == connection_id,
                XeroRepeatingInvoice.tenant_id == tenant_id,
                XeroRepeatingInvoice.status == XeroRepeatingInvoiceStatus.AUTHORISED.value,
                XeroRepeatingInvoice.invoice_type == "ACCPAY",
            )
        )
        expense = Decimal(str(expense_result.scalar() or 0))

        return revenue, expense


class XeroTrackingCategoryRepository:
    """Repository for XeroTrackingCategory CRUD operations.

    Handles tracking categories for profitability analysis.
    Spec 025: Fixed Assets & Enhanced Analysis
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    async def get_by_id(self, tc_id: UUID) -> XeroTrackingCategory | None:
        """Get tracking category by ID."""
        result = await self.session.execute(
            select(XeroTrackingCategory).where(XeroTrackingCategory.id == tc_id)
        )
        return result.scalar_one_or_none()

    async def get_by_xero_id(
        self, connection_id: UUID, xero_tc_id: str
    ) -> XeroTrackingCategory | None:
        """Get tracking category by Xero ID."""
        result = await self.session.execute(
            select(XeroTrackingCategory).where(
                XeroTrackingCategory.connection_id == connection_id,
                XeroTrackingCategory.xero_tracking_category_id == xero_tc_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_from_xero(self, data: dict[str, Any]) -> tuple[XeroTrackingCategory, bool]:
        """Upsert tracking category from Xero data."""
        stmt = insert(XeroTrackingCategory).values(**data)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_xero_tracking_categories_connection_xero_id",
            set_={
                k: v
                for k, v in data.items()
                if k
                not in (
                    "id",
                    "tenant_id",
                    "connection_id",
                    "xero_tracking_category_id",
                    "created_at",
                )
            },
        ).returning(XeroTrackingCategory)

        result = await self.session.execute(stmt)
        tc = result.scalar_one()
        created = tc.created_at >= tc.updated_at
        return tc, created

    async def list_by_connection(
        self, connection_id: UUID, include_archived: bool = False
    ) -> list[XeroTrackingCategory]:
        """List all tracking categories for a connection."""
        query = select(XeroTrackingCategory).where(
            XeroTrackingCategory.connection_id == connection_id
        )
        if not include_archived:
            query = query.where(XeroTrackingCategory.status == "ACTIVE")

        result = await self.session.execute(query.order_by(XeroTrackingCategory.name))
        return list(result.scalars().all())

    async def count_by_connection(self, connection_id: UUID, tenant_id: UUID) -> int:
        """Count tracking categories for a connection."""
        result = await self.session.execute(
            select(func.count(XeroTrackingCategory.id)).where(
                XeroTrackingCategory.connection_id == connection_id,
                XeroTrackingCategory.tenant_id == tenant_id,
            )
        )
        return result.scalar() or 0


class XeroTrackingOptionRepository:
    """Repository for XeroTrackingOption CRUD operations.

    Handles tracking options (values within a category).
    Spec 025: Fixed Assets & Enhanced Analysis
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    async def upsert_from_xero(self, data: dict[str, Any]) -> tuple[XeroTrackingOption, bool]:
        """Upsert tracking option from Xero data."""
        stmt = insert(XeroTrackingOption).values(**data)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_xero_tracking_options_category_xero_id",
            set_={
                k: v
                for k, v in data.items()
                if k not in ("id", "tracking_category_id", "xero_tracking_option_id", "created_at")
            },
        ).returning(XeroTrackingOption)

        result = await self.session.execute(stmt)
        to = result.scalar_one()
        created = to.created_at >= to.updated_at
        return to, created

    async def list_by_category(
        self, category_id: UUID, include_deleted: bool = False
    ) -> list[XeroTrackingOption]:
        """List all options for a tracking category."""
        query = select(XeroTrackingOption).where(
            XeroTrackingOption.tracking_category_id == category_id
        )
        if not include_deleted:
            query = query.where(XeroTrackingOption.is_deleted == False)  # noqa: E712

        result = await self.session.execute(query.order_by(XeroTrackingOption.name))
        return list(result.scalars().all())

    async def count_active_by_connection(self, connection_id: UUID, tenant_id: UUID) -> int:
        """Count active tracking options for a connection.

        Joins through categories to count non-deleted options.
        """
        result = await self.session.execute(
            select(func.count(XeroTrackingOption.id))
            .join(
                XeroTrackingCategory,
                XeroTrackingOption.tracking_category_id == XeroTrackingCategory.id,
            )
            .where(
                XeroTrackingCategory.connection_id == connection_id,
                XeroTrackingCategory.tenant_id == tenant_id,
                XeroTrackingOption.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar() or 0


class XeroQuoteRepository:
    """Repository for XeroQuote CRUD operations.

    Handles quotes for pipeline analysis.
    Spec 025: Fixed Assets & Enhanced Analysis
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    async def get_by_id(self, quote_id: UUID) -> XeroQuote | None:
        """Get quote by ID."""
        result = await self.session.execute(select(XeroQuote).where(XeroQuote.id == quote_id))
        return result.scalar_one_or_none()

    async def get_by_xero_id(self, connection_id: UUID, xero_quote_id: str) -> XeroQuote | None:
        """Get quote by Xero quote ID."""
        result = await self.session.execute(
            select(XeroQuote).where(
                XeroQuote.connection_id == connection_id,
                XeroQuote.xero_quote_id == xero_quote_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_from_xero(self, data: dict[str, Any]) -> tuple[XeroQuote, bool]:
        """Upsert quote from Xero data."""
        stmt = insert(XeroQuote).values(**data)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_xero_quotes_connection_xero_id",
            set_={
                k: v
                for k, v in data.items()
                if k not in ("id", "tenant_id", "connection_id", "xero_quote_id", "created_at")
            },
        ).returning(XeroQuote)

        result = await self.session.execute(stmt)
        quote = result.scalar_one()
        created = quote.created_at >= quote.updated_at
        return quote, created

    async def bulk_upsert(self, records: list[dict[str, Any]]) -> tuple[int, int]:
        """Bulk upsert quotes."""
        created = 0
        updated = 0
        for data in records:
            _, was_created = await self.upsert_from_xero(data)
            if was_created:
                created += 1
            else:
                updated += 1
        return created, updated

    async def list_by_connection(
        self,
        connection_id: UUID,
        status: XeroQuoteStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[XeroQuote], int]:
        """List quotes for a connection with filtering and pagination."""
        query = select(XeroQuote).where(XeroQuote.connection_id == connection_id)

        if status is not None:
            query = query.where(XeroQuote.status == status.value)

        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        result = await self.session.execute(
            query.order_by(XeroQuote.date.desc()).limit(limit).offset(offset)
        )
        quotes = list(result.scalars().all())

        return quotes, total

    async def get_pipeline_summary(self, connection_id: UUID) -> dict[str, Any]:
        """Get summary of quote pipeline for sales forecasting."""
        result = await self.session.execute(
            select(
                XeroQuote.status,
                func.count(XeroQuote.id).label("count"),
                func.sum(XeroQuote.total).label("total_value"),
            )
            .where(
                XeroQuote.connection_id == connection_id,
            )
            .group_by(XeroQuote.status)
        )
        rows = result.all()

        pipeline = {}
        for row in rows:
            pipeline[row.status] = {
                "count": row.count or 0,
                "total_value": row.total_value or Decimal("0"),
            }

        return pipeline

    async def count_by_connection(self, connection_id: UUID, tenant_id: UUID) -> int:
        """Count quotes for a connection."""
        result = await self.session.execute(
            select(func.count(XeroQuote.id)).where(
                XeroQuote.connection_id == connection_id,
                XeroQuote.tenant_id == tenant_id,
            )
        )
        return result.scalar() or 0

    async def get_open_quotes_summary(
        self, connection_id: UUID, tenant_id: UUID
    ) -> tuple[int, Decimal]:
        """Get count and value of open quotes.

        Open quotes are those with DRAFT or SENT status.

        Returns:
            Tuple of (count, total_value).
        """
        result = await self.session.execute(
            select(
                func.count(XeroQuote.id).label("count"),
                func.coalesce(func.sum(XeroQuote.total), 0).label("total"),
            ).where(
                XeroQuote.connection_id == connection_id,
                XeroQuote.tenant_id == tenant_id,
                XeroQuote.status.in_(
                    [
                        XeroQuoteStatus.DRAFT.value,
                        XeroQuoteStatus.SENT.value,
                    ]
                ),
            )
        )
        row = result.one()
        return row.count or 0, Decimal(str(row.total or 0))


class XeroSyncEntityProgressRepository:
    """Repository for XeroSyncEntityProgress CRUD operations.

    Tracks per-entity sync progress within a parent sync job.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session.
        """
        self.session = session

    async def create(self, **kwargs: Any) -> XeroSyncEntityProgress:
        """Create a single entity progress record.

        Args:
            **kwargs: Field values for the entity progress record.

        Returns:
            The created XeroSyncEntityProgress.
        """
        progress = XeroSyncEntityProgress(**kwargs)
        self.session.add(progress)
        await self.session.flush()
        return progress

    async def bulk_create_for_job(
        self,
        job_id: UUID,
        tenant_id: UUID,
        entity_types: list[str],
    ) -> list[XeroSyncEntityProgress]:
        """Create entity progress records for all entity types in a job.

        All records are created with status=pending.

        Args:
            job_id: The parent sync job ID.
            tenant_id: The tenant ID.
            entity_types: List of entity type names to create progress for.

        Returns:
            List of created XeroSyncEntityProgress records.
        """
        records: list[XeroSyncEntityProgress] = []
        for entity_type in entity_types:
            progress = XeroSyncEntityProgress(
                job_id=job_id,
                tenant_id=tenant_id,
                entity_type=entity_type,
                status=XeroSyncEntityProgressStatus.PENDING,
            )
            self.session.add(progress)
            records.append(progress)
        await self.session.flush()
        return records

    async def update_status(
        self,
        progress_id: UUID,
        status: XeroSyncEntityProgressStatus,
        **kwargs: Any,
    ) -> XeroSyncEntityProgress | None:
        """Update entity progress status and optional fields.

        Supports updating: records_processed, records_created,
        records_updated, records_failed, error_message, started_at,
        completed_at, duration_ms.

        Args:
            progress_id: The entity progress record ID.
            status: New status value.
            **kwargs: Optional fields to update alongside status.

        Returns:
            Updated XeroSyncEntityProgress, or None if not found.
        """
        allowed_fields = {
            "records_processed",
            "records_created",
            "records_updated",
            "records_failed",
            "error_message",
            "started_at",
            "completed_at",
            "duration_ms",
        }
        values: dict[str, Any] = {"status": status}
        for key, value in kwargs.items():
            if key in allowed_fields:
                values[key] = value

        await self.session.execute(
            update(XeroSyncEntityProgress)
            .where(XeroSyncEntityProgress.id == progress_id)
            .values(**values)
        )

        # Fetch and return the updated record
        result = await self.session.execute(
            select(XeroSyncEntityProgress).where(XeroSyncEntityProgress.id == progress_id)
        )
        return result.scalar_one_or_none()

    async def get_by_job_id(self, job_id: UUID) -> list[XeroSyncEntityProgress]:
        """Get all entity progress records for a job.

        Args:
            job_id: The parent sync job ID.

        Returns:
            List of XeroSyncEntityProgress records for the job.
        """
        result = await self.session.execute(
            select(XeroSyncEntityProgress)
            .where(XeroSyncEntityProgress.job_id == job_id)
            .order_by(XeroSyncEntityProgress.created_at)
        )
        return list(result.scalars().all())

    async def get_by_job_and_entity(
        self, job_id: UUID, entity_type: str
    ) -> XeroSyncEntityProgress | None:
        """Get a specific entity progress record by job and entity type.

        Args:
            job_id: The parent sync job ID.
            entity_type: The entity type name (e.g., 'contacts', 'invoices').

        Returns:
            XeroSyncEntityProgress if found, None otherwise.
        """
        result = await self.session.execute(
            select(XeroSyncEntityProgress).where(
                XeroSyncEntityProgress.job_id == job_id,
                XeroSyncEntityProgress.entity_type == entity_type,
            )
        )
        return result.scalar_one_or_none()


class PostSyncTaskRepository:
    """Repository for PostSyncTask CRUD operations.

    Tracks execution of post-sync data preparation tasks
    (quality scoring, BAS calculation, aggregation, insights, triggers).
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session.
        """
        self.session = session

    async def create(self, **kwargs: Any) -> PostSyncTask:
        """Create a post-sync task record.

        Args:
            **kwargs: Field values for the post-sync task.

        Returns:
            The created PostSyncTask.
        """
        task = PostSyncTask(**kwargs)
        self.session.add(task)
        await self.session.flush()
        return task

    async def update_status(
        self,
        task_id: UUID,
        status: PostSyncTaskStatus,
        **kwargs: Any,
    ) -> PostSyncTask | None:
        """Update post-sync task status and optional fields.

        Supports updating: started_at, completed_at, error_message,
        result_summary.

        Args:
            task_id: The post-sync task ID.
            status: New status value.
            **kwargs: Optional fields to update alongside status.

        Returns:
            Updated PostSyncTask, or None if not found.
        """
        allowed_fields = {
            "started_at",
            "completed_at",
            "error_message",
            "result_summary",
        }
        values: dict[str, Any] = {"status": status}
        for key, value in kwargs.items():
            if key in allowed_fields:
                values[key] = value

        await self.session.execute(
            update(PostSyncTask).where(PostSyncTask.id == task_id).values(**values)
        )

        # Fetch and return the updated record
        result = await self.session.execute(select(PostSyncTask).where(PostSyncTask.id == task_id))
        return result.scalar_one_or_none()

    async def get_by_job_id(self, job_id: UUID) -> list[PostSyncTask]:
        """Get all post-sync tasks for a job.

        Args:
            job_id: The parent sync job ID.

        Returns:
            List of PostSyncTask records for the job.
        """
        result = await self.session.execute(
            select(PostSyncTask)
            .where(PostSyncTask.job_id == job_id)
            .order_by(PostSyncTask.created_at)
        )
        return list(result.scalars().all())

    async def get_by_connection(self, connection_id: UUID) -> list[PostSyncTask]:
        """Get recent post-sync tasks for a connection.

        Returns the most recent tasks ordered by creation time descending.

        Args:
            connection_id: The Xero connection ID.

        Returns:
            List of recent PostSyncTask records for the connection.
        """
        result = await self.session.execute(
            select(PostSyncTask)
            .where(PostSyncTask.connection_id == connection_id)
            .order_by(PostSyncTask.created_at.desc())
            .limit(50)
        )
        return list(result.scalars().all())


class XeroWebhookEventRepository:
    """Repository for XeroWebhookEvent CRUD operations.

    Manages incoming Xero webhook events for deduplication,
    batching, and processing.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session.
        """
        self.session = session

    async def create(self, **kwargs: Any) -> XeroWebhookEvent:
        """Create a webhook event record.

        Args:
            **kwargs: Field values for the webhook event.

        Returns:
            The created XeroWebhookEvent.
        """
        event = XeroWebhookEvent(**kwargs)
        self.session.add(event)
        await self.session.flush()
        return event

    async def get_by_webhook_key(self, webhook_key: str) -> XeroWebhookEvent | None:
        """Get a webhook event by its deduplication key.

        Args:
            webhook_key: The Xero event key used for deduplication.

        Returns:
            XeroWebhookEvent if found, None otherwise.
        """
        result = await self.session.execute(
            select(XeroWebhookEvent).where(XeroWebhookEvent.webhook_key == webhook_key)
        )
        return result.scalar_one_or_none()

    async def get_pending_by_connection(self, connection_id: UUID) -> list[XeroWebhookEvent]:
        """Get pending webhook events for a connection.

        Args:
            connection_id: The Xero connection ID.

        Returns:
            List of pending XeroWebhookEvent records.
        """
        result = await self.session.execute(
            select(XeroWebhookEvent)
            .where(
                XeroWebhookEvent.connection_id == connection_id,
                XeroWebhookEvent.status == XeroWebhookEventStatus.PENDING,
            )
            .order_by(XeroWebhookEvent.created_at)
        )
        return list(result.scalars().all())

    async def mark_processed(
        self,
        event_id: UUID,
        batch_id: UUID | None = None,
    ) -> None:
        """Mark a webhook event as completed.

        Sets the status to COMPLETED and records the processing timestamp.
        Optionally assigns a batch ID for batch-processed events.

        Args:
            event_id: The webhook event ID.
            batch_id: Optional batch ID grouping events processed together.
        """
        values: dict[str, Any] = {
            "status": XeroWebhookEventStatus.COMPLETED,
            "processed_at": datetime.now(UTC),
        }
        if batch_id is not None:
            values["batch_id"] = batch_id

        await self.session.execute(
            update(XeroWebhookEvent).where(XeroWebhookEvent.id == event_id).values(**values)
        )

    async def mark_failed(
        self,
        event_id: UUID,
        error_message: str,
        batch_id: UUID | None = None,
    ) -> None:
        """Mark a webhook event as failed.

        Sets the status to FAILED and records the error message.
        Optionally assigns a batch ID for batch-processed events.

        Args:
            event_id: The webhook event ID.
            error_message: Description of what went wrong.
            batch_id: Optional batch ID grouping events processed together.
        """
        values: dict[str, Any] = {
            "status": XeroWebhookEventStatus.FAILED,
            "processed_at": datetime.now(UTC),
            "error_message": error_message,
        }
        if batch_id is not None:
            values["batch_id"] = batch_id

        await self.session.execute(
            update(XeroWebhookEvent).where(XeroWebhookEvent.id == event_id).values(**values)
        )

    async def get_all_pending(self) -> list[XeroWebhookEvent]:
        """Get all pending webhook events across all connections.

        Used by the process_webhook_events Celery task to find
        unprocessed events for batching and dispatch.

        Returns:
            List of pending XeroWebhookEvent records ordered by creation time.
        """
        result = await self.session.execute(
            select(XeroWebhookEvent)
            .where(
                XeroWebhookEvent.status == XeroWebhookEventStatus.PENDING,
            )
            .order_by(XeroWebhookEvent.created_at)
        )
        return list(result.scalars().all())

    async def get_pending_batch(self, batch_id: UUID) -> list[XeroWebhookEvent]:
        """Get all webhook events in a batch.

        Args:
            batch_id: The batch ID grouping related events.

        Returns:
            List of XeroWebhookEvent records in the batch.
        """
        result = await self.session.execute(
            select(XeroWebhookEvent)
            .where(
                XeroWebhookEvent.batch_id == batch_id,
            )
            .order_by(XeroWebhookEvent.created_at)
        )
        return list(result.scalars().all())
