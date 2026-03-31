"""Xero integration business logic.

Provides services for:
- XeroOAuthService: OAuth flow handling
- XeroConnectionService: Connection lifecycle management
- XeroDataService: Data sync operations (contacts, invoices, etc.)
- XeroSyncService: Sync orchestration and job management
- XeroClientService: Client viewing and financial summary operations
- XpmClientService: XPM (Xero Practice Manager) client operations
- XeroReportService: Xero Reports API - P&L, Balance Sheet, Aged AR/AP, etc.
"""

import asyncio
import contextlib
import logging
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.modules.auth.models import Tenant
from app.modules.billing.service import BillingService
from app.modules.integrations.xero.client import XeroClient
from app.modules.integrations.xero.encryption import TokenEncryption
from app.modules.integrations.xero.exceptions import (
    XeroConnectionInactiveError,
    XeroConnectionNotFoundError as XeroConnectionNotFoundExc,
    XeroRateLimitExceededError,
    XeroSyncInProgressError,
    XeroSyncJobNotFoundError,
)
from app.modules.integrations.xero.models import (
    XeroConnection,
    XeroConnectionStatus,
    XeroConnectionType,
    XeroSyncJob,
    XeroSyncStatus,
    XeroSyncType,
    XpmClientConnectionStatus,
)
from app.modules.integrations.xero.oauth import (
    build_authorization_url,
    generate_code_challenge,
    generate_code_verifier,
    generate_state,
)
from app.modules.integrations.xero.rate_limiter import RateLimitState, XeroRateLimiter
from app.modules.integrations.xero.repository import (
    XeroAccountRepository,
    XeroAssetRepository,
    XeroAssetTypeRepository,
    XeroBankTransactionRepository,
    XeroClientRepository,
    XeroConnectionRepository,
    XeroCreditNoteAllocationRepository,
    XeroCreditNoteRepository,
    XeroInvoiceRepository,
    XeroJournalRepository,
    XeroManualJournalRepository,
    XeroOAuthStateRepository,
    XeroOverpaymentRepository,
    XeroPaymentRepository,
    XeroPrepaymentRepository,
    XeroSyncJobRepository,
    XpmClientRepository,
)
from app.modules.integrations.xero.schemas import (
    AvailableQuartersResponse,
    ClientFinancialSummaryResponse,
    MultiClientQueuedConnection,
    MultiClientSkippedConnection,
    MultiClientSyncResponse,
    QuarterInfo,
    SyncResult,
    XeroAuthUrlResponse,
    XeroBankTransactionListResponse,
    XeroBankTransactionResponse,
    XeroClientDetailResponse,
    XeroClientListResponse,
    XeroClientResponse,
    XeroConnectionCreate,
    XeroConnectionListResponse,
    XeroConnectionResponse,
    XeroConnectionSummary,
    XeroConnectionUpdate,
    XeroInvoiceListResponse,
    XeroInvoiceResponse,
    XeroOrganization,
    XeroSyncHistoryResponse,
    XeroSyncJobResponse,
    XpmClientConnectionProgress,
    XpmClientListResponse,
    XpmClientResponse,
    XpmClientStatusCounts,
)
from app.modules.integrations.xero.transformers import (
    AccountTransformer,
    AgedPayablesTransformer,
    AgedReceivablesTransformer,
    AssetTransformer,
    AssetTypeTransformer,
    BalanceSheetTransformer,
    BankSummaryTransformer,
    BankTransactionTransformer,
    ContactTransformer,
    CreditNoteAllocationTransformer,
    CreditNoteTransformer,
    InvoiceTransformer,
    JournalTransformer,
    ManualJournalTransformer,
    OverpaymentTransformer,
    PaymentTransformer,
    PrepaymentTransformer,
    ProfitAndLossTransformer,
    TrialBalanceTransformer,
    XeroReportTransformer,
)
from app.modules.integrations.xero.utils import (
    format_quarter,
    get_available_quarters,
    get_current_quarter,
    get_quarter_dates,
)

if TYPE_CHECKING:
    from celery import Celery

logger = logging.getLogger(__name__)


class XeroOAuthError(Exception):
    """Error during Xero OAuth flow."""

    pass


class XeroConnectionNotFoundError(Exception):
    """Xero connection not found."""

    pass


class XeroClientNotFoundError(Exception):
    """Xero client not found."""

    def __init__(self, client_id: UUID) -> None:
        self.client_id = client_id
        super().__init__(f"Xero client {client_id} not found")


class XeroOAuthService:
    """Service for handling Xero OAuth 2.0 flow."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
    ) -> None:
        """Initialize OAuth service.

        Args:
            session: Database session.
            settings: Application settings.
        """
        self.session = session
        self.settings = settings
        self.state_repo = XeroOAuthStateRepository(session)
        self.connection_repo = XeroConnectionRepository(session)
        self.encryption = TokenEncryption(settings.token_encryption.key.get_secret_value())

    async def generate_auth_url(
        self,
        tenant_id: UUID,
        user_id: UUID,
        frontend_redirect_uri: str,
    ) -> XeroAuthUrlResponse:
        """Generate Xero OAuth authorization URL.

        Creates PKCE parameters and stores state for callback validation.

        Args:
            tenant_id: The tenant initiating OAuth.
            user_id: The user initiating OAuth.
            frontend_redirect_uri: Where to redirect after OAuth.

        Returns:
            XeroAuthUrlResponse with authorization URL and state.
        """
        # Generate PKCE parameters
        code_verifier = generate_code_verifier()
        code_challenge = generate_code_challenge(code_verifier)
        state = generate_state()

        # Store state for callback validation
        expires_at = datetime.now(UTC) + timedelta(minutes=10)
        await self.state_repo.create(
            tenant_id=tenant_id,
            user_id=user_id,
            state=state,
            code_verifier=code_verifier,
            redirect_uri=frontend_redirect_uri,
            expires_at=expires_at,
        )

        # Build authorization URL
        auth_url = build_authorization_url(
            settings=self.settings.xero,
            state=state,
            code_challenge=code_challenge,
            redirect_uri=self.settings.xero.redirect_uri,
        )

        return XeroAuthUrlResponse(auth_url=auth_url, state=state)

    async def generate_client_auth_url(
        self,
        tenant_id: UUID,
        user_id: UUID,
        xpm_client_id: UUID,
        frontend_redirect_uri: str,
    ) -> XeroAuthUrlResponse:
        """Generate Xero OAuth authorization URL for a specific client's org.

        Creates PKCE parameters and stores state with client context for callback.
        The OAuth flow will be for authorizing access to the client's Xero organization.

        Args:
            tenant_id: The tenant (accounting practice) ID.
            user_id: The user initiating OAuth.
            xpm_client_id: The XPM client whose Xero org we're authorizing.
            frontend_redirect_uri: Where to redirect after OAuth.

        Returns:
            XeroAuthUrlResponse with authorization URL and state.
        """
        # Generate PKCE parameters
        code_verifier = generate_code_verifier()
        code_challenge = generate_code_challenge(code_verifier)
        state = generate_state()

        # Store state for callback validation (with client context)
        expires_at = datetime.now(UTC) + timedelta(minutes=10)
        await self.state_repo.create(
            tenant_id=tenant_id,
            user_id=user_id,
            state=state,
            code_verifier=code_verifier,
            redirect_uri=frontend_redirect_uri,
            expires_at=expires_at,
            xpm_client_id=xpm_client_id,
            connection_type=XeroConnectionType.CLIENT,
        )

        # Build authorization URL
        # Note: For individual client auth, we could add acr_values=bulk_connect:false
        # to force single-org selection, but Xero may not support this
        auth_url = build_authorization_url(
            settings=self.settings.xero,
            state=state,
            code_challenge=code_challenge,
            redirect_uri=self.settings.xero.redirect_uri,
        )

        return XeroAuthUrlResponse(auth_url=auth_url, state=state)

    async def handle_callback(
        self,
        code: str,
        state: str,
    ) -> tuple[XeroConnection, UUID | None]:
        """Handle OAuth callback from Xero.

        Validates state, exchanges code for tokens, and creates connection.
        If this was a client-specific OAuth, also links the connection to the XPM client.

        Args:
            code: Authorization code from Xero.
            state: State parameter for CSRF validation.

        Returns:
            Tuple of (XeroConnection, xpm_client_id or None).

        Raises:
            XeroOAuthError: If state is invalid or token exchange fails.
        """
        # Validate state
        oauth_state = await self.state_repo.get_by_state(state)
        if oauth_state is None:
            raise XeroOAuthError("Invalid or unknown state parameter")

        if not oauth_state.is_valid:
            if oauth_state.is_expired:
                raise XeroOAuthError("Authorization expired, please try again")
            if oauth_state.is_used:
                raise XeroOAuthError("Authorization already completed")
            raise XeroOAuthError("Invalid state")

        # Mark state as used
        await self.state_repo.mark_as_used(oauth_state.id)

        # Exchange code for tokens
        async with XeroClient(self.settings.xero) as client:
            token_response, token_expires_at = await client.exchange_code(
                code=code,
                code_verifier=oauth_state.code_verifier,
                redirect_uri=self.settings.xero.redirect_uri,
            )

            # Get connected organizations
            organizations = await client.get_connections(token_response.access_token)

        if not organizations:
            raise XeroOAuthError("No organizations authorized")

        # Create connection for the first organization
        # (In a real app, you might want to let user choose which org to connect)
        org = organizations[0]

        # Check if connection already exists for this org
        existing = await self.connection_repo.get_by_xero_tenant_id(
            tenant_id=oauth_state.tenant_id,
            xero_tenant_id=org.id,
        )

        # Check if payroll scopes were granted
        payroll_scopes = ["payroll.employees", "payroll.payruns"]
        has_payroll = all(scope in token_response.scopes_list for scope in payroll_scopes)

        # Determine connection type from OAuth state
        connection_type = oauth_state.connection_type
        xpm_client_id = oauth_state.xpm_client_id

        if existing:
            # Update existing connection (reconnection scenario)
            updated = await self.connection_repo.update(
                connection_id=existing.id,
                data=XeroConnectionUpdate(
                    access_token=self.encryption.encrypt(token_response.access_token),
                    refresh_token=self.encryption.encrypt(token_response.refresh_token),
                    token_expires_at=token_expires_at,
                    status=XeroConnectionStatus.ACTIVE,
                    has_payroll_access=has_payroll,
                ),
            )
            if updated:
                # Update connection_type if this is client OAuth
                if connection_type == XeroConnectionType.CLIENT:
                    from sqlalchemy import text

                    await self.session.execute(
                        text("""
                        UPDATE xero_connections
                        SET connection_type = :connection_type
                        WHERE id = :connection_id
                        """),
                        {
                            "connection_type": connection_type.value,
                            "connection_id": updated.id,
                        },
                    )
                    # Link to XPM client if specified
                    if xpm_client_id:
                        xpm_repo = XpmClientRepository(self.session)
                        await xpm_repo.link_xero_connection(
                            client_id=xpm_client_id,
                            xero_connection_id=updated.id,
                            xero_org_name=org.display_name,
                        )
                return updated, xpm_client_id
            raise XeroOAuthError("Failed to update existing connection")

        # Create new connection
        connection = await self.connection_repo.create(
            XeroConnectionCreate(
                tenant_id=oauth_state.tenant_id,
                xero_tenant_id=org.id,
                organization_name=org.display_name,
                access_token=self.encryption.encrypt(token_response.access_token),
                refresh_token=self.encryption.encrypt(token_response.refresh_token),
                token_expires_at=token_expires_at,
                scopes=token_response.scopes_list,
                connected_by=oauth_state.user_id,
                has_payroll_access=has_payroll,
            )
        )

        # Set connection_type for new connection
        if connection_type == XeroConnectionType.CLIENT:
            from sqlalchemy import text

            await self.session.execute(
                text("""
                UPDATE xero_connections
                SET connection_type = :connection_type
                WHERE id = :connection_id
                """),
                {
                    "connection_type": connection_type.value,
                    "connection_id": connection.id,
                },
            )
            # Link to XPM client if specified
            if xpm_client_id:
                xpm_repo = XpmClientRepository(self.session)
                await xpm_repo.link_xero_connection(
                    client_id=xpm_client_id,
                    xero_connection_id=connection.id,
                    xero_org_name=org.display_name,
                )

        return connection, xpm_client_id


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
        updated = await self.connection_repo.update(
            connection_id,
            XeroConnectionUpdate(
                access_token=self.encryption.encrypt(token_response.access_token),
                refresh_token=self.encryption.encrypt(token_response.refresh_token),
                token_expires_at=token_expires_at,
            ),
        )

        if updated is None:
            raise XeroConnectionNotFoundError(f"Connection {connection_id} not found")

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


# =============================================================================
# Data Sync Services
# =============================================================================


class XeroDataService:
    """Service for syncing data from Xero API.

    Handles the actual data retrieval and storage for:
    - Contacts -> XeroClient
    - Invoices -> XeroInvoice
    - Bank Transactions -> XeroBankTransaction
    - Accounts -> XeroAccount
    """

    # Rate limit safety margins
    MIN_MINUTE_REMAINING = 5
    MIN_DAILY_REMAINING = 100

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
    ) -> None:
        """Initialize data service.

        Args:
            session: Database session.
            settings: Application settings.
        """
        self.session = session
        self.settings = settings
        self.connection_repo = XeroConnectionRepository(session)
        self.client_repo = XeroClientRepository(session)
        self.invoice_repo = XeroInvoiceRepository(session)
        self.transaction_repo = XeroBankTransactionRepository(session)
        self.account_repo = XeroAccountRepository(session)
        # Spec 024: Credit Notes, Payments, Journals repositories
        self.credit_note_repo = XeroCreditNoteRepository(session)
        self.credit_note_allocation_repo = XeroCreditNoteAllocationRepository(session)
        self.payment_repo = XeroPaymentRepository(session)
        self.overpayment_repo = XeroOverpaymentRepository(session)
        self.prepayment_repo = XeroPrepaymentRepository(session)
        self.journal_repo = XeroJournalRepository(session)
        self.manual_journal_repo = XeroManualJournalRepository(session)
        # Spec 025: Fixed Assets repositories
        self.asset_type_repo = XeroAssetTypeRepository(session)
        self.asset_repo = XeroAssetRepository(session)
        self.encryption = TokenEncryption(settings.token_encryption.key.get_secret_value())
        self.rate_limiter = XeroRateLimiter()

    async def _get_connection_with_token(
        self,
        connection_id: UUID,
    ) -> tuple[XeroConnection, str]:
        """Get connection and ensure valid access token.

        Args:
            connection_id: The connection ID.

        Returns:
            Tuple of (connection, decrypted_access_token).

        Raises:
            XeroConnectionNotFoundExc: If connection not found.
            XeroConnectionInactiveError: If connection not active.
        """
        connection = await self.connection_repo.get_by_id(connection_id)
        if connection is None:
            raise XeroConnectionNotFoundExc(connection_id)

        if connection.status != XeroConnectionStatus.ACTIVE:
            raise XeroConnectionInactiveError(connection_id)

        # Refresh if needed
        if connection.needs_refresh:
            conn_service = XeroConnectionService(self.session, self.settings)
            connection = await conn_service.refresh_tokens(connection_id)

        access_token = self.encryption.decrypt(connection.access_token)
        return connection, access_token

    async def _ensure_valid_token(self, connection_id: UUID) -> str:
        """Ensure the Xero access token is still valid, refreshing if needed.

        Call this inside pagination loops to prevent token expiry during
        long-running syncs (Xero tokens expire after 30 minutes).

        Args:
            connection_id: The connection ID.

        Returns:
            Decrypted access token.
        """
        conn_service = XeroConnectionService(self.session, self.settings)
        return await conn_service.ensure_valid_token(connection_id)

    async def _check_rate_limits(self, connection: XeroConnection) -> None:
        """Check if rate limits allow proceeding.

        Args:
            connection: The connection to check.

        Raises:
            XeroRateLimitExceededError: If limits exceeded.
        """
        state = RateLimitState(
            daily_remaining=connection.rate_limit_daily_remaining or 5000,
            minute_remaining=connection.rate_limit_minute_remaining or 60,
            # Note: rate_limit_reset_at tracks when the minute bucket resets,
            # NOT when we're rate limited until. We're only rate limited if
            # we've actually hit a 429. So we don't set rate_limited_until here.
        )
        if not self.rate_limiter.can_make_request(state):
            wait_seconds = self.rate_limiter.get_wait_time(state)
            raise XeroRateLimitExceededError(wait_seconds)

    async def _update_rate_limits(
        self,
        connection_id: UUID,
        minute_remaining: int,
        daily_remaining: int,
    ) -> None:
        """Update connection with latest rate limit values.

        Args:
            connection_id: The connection ID.
            minute_remaining: Remaining minute limit.
            daily_remaining: Remaining daily limit.
        """
        reset_at = datetime.now(UTC) + timedelta(seconds=60)
        await self.connection_repo.update(
            connection_id,
            XeroConnectionUpdate(
                rate_limit_minute_remaining=minute_remaining,
                rate_limit_daily_remaining=daily_remaining,
                rate_limit_reset_at=reset_at,
                last_used_at=datetime.now(UTC),
            ),
        )

    async def sync_contacts(
        self,
        connection_id: UUID,
        modified_since: datetime | None = None,
        progress_callback: Callable[..., None] | None = None,
        max_new_clients: int | None = None,
    ) -> SyncResult:
        """Sync contacts from Xero to local storage.

        Args:
            connection_id: The connection ID.
            modified_since: Only sync contacts modified after this time.
            progress_callback: Optional callback(processed, created, updated).
            max_new_clients: Maximum number of new clients to create. If None,
                no limit is applied. Used for client limit enforcement (Spec 020).

        Returns:
            SyncResult with counts and any error message.
        """
        result = SyncResult()
        connection, access_token = await self._get_connection_with_token(connection_id)

        page = 1
        has_more = True
        limit_reached = False

        async with XeroClient(self.settings.xero) as client:
            while has_more:
                await self._check_rate_limits(connection)
                access_token = await self._ensure_valid_token(connection_id)

                try:
                    contacts, has_more, rate_limit = await client.get_contacts(
                        access_token=access_token,
                        tenant_id=connection.xero_tenant_id,
                        page=page,
                        modified_since=modified_since,
                    )
                except Exception as e:
                    result.error_message = str(e)
                    logger.error(f"Failed to fetch contacts page {page}: {e}")
                    break

                # Update rate limits
                await self._update_rate_limits(
                    connection_id,
                    rate_limit.minute_remaining,
                    rate_limit.daily_remaining,
                )

                # Transform and upsert contacts
                for contact in contacts:
                    try:
                        transformed = ContactTransformer.transform(contact)
                        transformed["tenant_id"] = connection.tenant_id
                        transformed["connection_id"] = connection_id

                        # Check if this would create a new client
                        existing = await self.client_repo.get_by_xero_contact_id(
                            connection.tenant_id, contact.get("ContactID")
                        )

                        if existing:
                            # Update existing client
                            _, created = await self.client_repo.upsert_from_xero(transformed)
                            result.records_processed += 1
                            result.records_updated += 1
                        else:
                            # Would create new client - check limit
                            if (
                                max_new_clients is not None
                                and result.records_created >= max_new_clients
                            ):
                                # Skip creating new clients when limit reached
                                limit_reached = True
                                result.records_failed += 1
                                continue

                            _, created = await self.client_repo.upsert_from_xero(transformed)
                            result.records_processed += 1
                            if created:
                                result.records_created += 1
                            else:
                                result.records_updated += 1

                    except Exception as e:
                        result.records_failed += 1
                        logger.warning(
                            f"Failed to transform contact {contact.get('ContactID')}: {e}"
                        )

                if progress_callback:
                    progress_callback(
                        result.records_processed,
                        result.records_created,
                        result.records_updated,
                    )

                page += 1

                # Brief pause between pages to be nice to the API
                if has_more:
                    await asyncio.sleep(0.1)

        # Update last sync timestamp
        await self.connection_repo.update(
            connection_id,
            XeroConnectionUpdate(last_used_at=datetime.now(UTC)),
        )

        # Add warning if limit was reached
        if limit_reached:
            result.error_message = (
                f"Client limit reached. {result.records_created} new clients added, "
                f"{result.records_failed} skipped. Upgrade for more clients."
            )

        return result

    async def sync_invoices(
        self,
        connection_id: UUID,
        modified_since: datetime | None = None,
        progress_callback: Callable[..., None] | None = None,
    ) -> SyncResult:
        """Sync invoices from Xero to local storage.

        Args:
            connection_id: The connection ID.
            modified_since: Only sync invoices modified after this time.
            progress_callback: Optional callback(processed, created, updated).

        Returns:
            SyncResult with counts and any error message.
        """
        result = SyncResult()
        connection, access_token = await self._get_connection_with_token(connection_id)

        page = 1
        has_more = True

        async with XeroClient(self.settings.xero) as client:
            while has_more:
                await self._check_rate_limits(connection)
                access_token = await self._ensure_valid_token(connection_id)

                try:
                    invoices, has_more, rate_limit = await client.get_invoices(
                        access_token=access_token,
                        tenant_id=connection.xero_tenant_id,
                        page=page,
                        modified_since=modified_since,
                    )
                except Exception as e:
                    result.error_message = str(e)
                    logger.error(f"Failed to fetch invoices page {page}: {e}")
                    break

                # Update rate limits
                await self._update_rate_limits(
                    connection_id,
                    rate_limit.minute_remaining,
                    rate_limit.daily_remaining,
                )

                # Transform and upsert invoices
                for invoice in invoices:
                    try:
                        transformed = InvoiceTransformer.transform(invoice)
                        transformed["tenant_id"] = connection.tenant_id
                        transformed["connection_id"] = connection_id

                        # Try to link to existing client
                        xero_contact_id = transformed.get("xero_contact_id")
                        if xero_contact_id:
                            xero_client = await self.client_repo.get_by_xero_contact_id(
                                connection_id, xero_contact_id
                            )
                            if xero_client:
                                transformed["client_id"] = xero_client.id

                        _, created = await self.invoice_repo.upsert_from_xero(transformed)

                        result.records_processed += 1
                        if created:
                            result.records_created += 1
                        else:
                            result.records_updated += 1

                    except Exception as e:
                        result.records_failed += 1
                        logger.warning(
                            f"Failed to transform invoice {invoice.get('InvoiceID')}: {e}"
                        )

                if progress_callback:
                    progress_callback(
                        result.records_processed,
                        result.records_created,
                        result.records_updated,
                    )

                page += 1

                if has_more:
                    await asyncio.sleep(0.1)

        return result

    async def sync_bank_transactions(
        self,
        connection_id: UUID,
        modified_since: datetime | None = None,
        progress_callback: Callable[..., None] | None = None,
    ) -> SyncResult:
        """Sync bank transactions from Xero to local storage.

        Args:
            connection_id: The connection ID.
            modified_since: Only sync transactions modified after this time.
            progress_callback: Optional callback(processed, created, updated).

        Returns:
            SyncResult with counts and any error message.
        """
        result = SyncResult()
        connection, access_token = await self._get_connection_with_token(connection_id)

        page = 1
        has_more = True

        async with XeroClient(self.settings.xero) as client:
            while has_more:
                await self._check_rate_limits(connection)
                access_token = await self._ensure_valid_token(connection_id)

                try:
                    transactions, has_more, rate_limit = await client.get_bank_transactions(
                        access_token=access_token,
                        tenant_id=connection.xero_tenant_id,
                        page=page,
                        modified_since=modified_since,
                    )
                except Exception as e:
                    result.error_message = str(e)
                    logger.error(f"Failed to fetch transactions page {page}: {e}")
                    break

                # Update rate limits
                await self._update_rate_limits(
                    connection_id,
                    rate_limit.minute_remaining,
                    rate_limit.daily_remaining,
                )

                # Transform and upsert transactions
                for txn in transactions:
                    try:
                        transformed = BankTransactionTransformer.transform(txn)
                        transformed["tenant_id"] = connection.tenant_id
                        transformed["connection_id"] = connection_id

                        # Try to link to existing client
                        xero_contact_id = transformed.get("xero_contact_id")
                        if xero_contact_id:
                            xero_client = await self.client_repo.get_by_xero_contact_id(
                                connection_id, xero_contact_id
                            )
                            if xero_client:
                                transformed["client_id"] = xero_client.id

                        _, created = await self.transaction_repo.upsert_from_xero(transformed)

                        result.records_processed += 1
                        if created:
                            result.records_created += 1
                        else:
                            result.records_updated += 1

                    except Exception as e:
                        result.records_failed += 1
                        logger.warning(
                            f"Failed to transform transaction {txn.get('BankTransactionID')}: {e}"
                        )

                if progress_callback:
                    progress_callback(
                        result.records_processed,
                        result.records_created,
                        result.records_updated,
                    )

                page += 1

                if has_more:
                    await asyncio.sleep(0.1)

        return result

    async def sync_accounts(
        self,
        connection_id: UUID,
        progress_callback: Callable[..., None] | None = None,
    ) -> SyncResult:
        """Sync chart of accounts from Xero to local storage.

        Note: Accounts don't support incremental sync (no modified_since).

        Args:
            connection_id: The connection ID.
            progress_callback: Optional callback(processed, created, updated).

        Returns:
            SyncResult with counts and any error message.
        """
        result = SyncResult()
        connection, access_token = await self._get_connection_with_token(connection_id)

        await self._check_rate_limits(connection)

        async with XeroClient(self.settings.xero) as client:
            try:
                accounts, rate_limit = await client.get_accounts(
                    access_token=access_token,
                    tenant_id=connection.xero_tenant_id,
                )
            except Exception as e:
                result.error_message = str(e)
                logger.error(f"Failed to fetch accounts: {e}")
                return result

            # Update rate limits
            await self._update_rate_limits(
                connection_id,
                rate_limit.minute_remaining,
                rate_limit.daily_remaining,
            )

            # Transform and upsert accounts
            for account in accounts:
                try:
                    transformed = AccountTransformer.transform(account)
                    transformed["tenant_id"] = connection.tenant_id
                    transformed["connection_id"] = connection_id

                    _, created = await self.account_repo.upsert_from_xero(transformed)

                    result.records_processed += 1
                    if created:
                        result.records_created += 1
                    else:
                        result.records_updated += 1

                except Exception as e:
                    result.records_failed += 1
                    logger.warning(f"Failed to transform account {account.get('AccountID')}: {e}")

            if progress_callback:
                progress_callback(
                    result.records_processed,
                    result.records_created,
                    result.records_updated,
                )

        return result

    async def sync_organisation_profile(
        self,
        connection_id: UUID,
    ) -> dict[str, Any] | None:
        """Fetch organisation details from Xero and create/update ClientAIProfile.

        This populates the ClientAIProfile with entity type, ABN, GST status
        and other organisation-level information from Xero.

        Args:
            connection_id: The connection ID.

        Returns:
            The organisation details dict if successful, None otherwise.
        """
        from app.modules.knowledge.aggregation_repository import AggregationRepository

        connection, access_token = await self._get_connection_with_token(connection_id)
        agg_repo = AggregationRepository(self.session)

        try:
            async with XeroClient(self.settings.xero) as client:
                await self._check_rate_limits(connection)

                org_data, rate_limit = await client.get_organisation(
                    access_token=access_token,
                    tenant_id=connection.xero_tenant_id,
                )

                await self._update_rate_limits(
                    connection_id,
                    rate_limit.minute_remaining,
                    rate_limit.daily_remaining,
                )

                if not org_data:
                    logger.warning(f"No organisation data returned for connection {connection_id}")
                    return None

                # Map Xero org type to our entity type
                xero_org_type = org_data.get("OrganisationType")
                entity_type_map = {
                    "COMPANY": "company",
                    "SOLETRADER": "sole_trader",
                    "PARTNERSHIP": "partnership",
                    "TRUST": "trust",
                    "CHARITY": "charity",
                    "CLUBSOCIETY": "club",
                    "PRACTICE": "practice",
                    "PERSON": "individual",
                }
                entity_type = entity_type_map.get(xero_org_type, xero_org_type)

                # Determine GST registration status
                tax_number = org_data.get("TaxNumber")  # ABN for AU
                sales_tax_basis = org_data.get("SalesTaxBasis")
                gst_registered = bool(tax_number and sales_tax_basis)

                # Create/update profile
                await agg_repo.upsert_client_profile(
                    tenant_id=connection.tenant_id,
                    connection_id=connection_id,
                    client_id=None,  # Organization-level profile, not contact-specific
                    entity_type=entity_type,
                    industry_code=None,  # Not available from Xero
                    gst_registered=gst_registered,
                    revenue_bracket=None,  # Not available from Xero
                    employee_count=0,  # Would need payroll data
                )

                await self.session.commit()

                logger.info(
                    f"Synced organisation profile for connection {connection_id}: "
                    f"entity_type={entity_type}, gst_registered={gst_registered}"
                )

                return org_data

        except Exception as e:
            logger.error(f"Failed to sync organisation profile for {connection_id}: {e}")
            return None

    # =========================================================================
    # Credit Notes, Payments, Journals Sync Methods (Spec 024)
    # =========================================================================

    async def sync_credit_notes(
        self,
        connection_id: UUID,
        modified_since: datetime | None = None,
        progress_callback: Callable[..., None] | None = None,
    ) -> SyncResult:
        """Sync credit notes from Xero to local storage.

        Args:
            connection_id: The connection ID.
            modified_since: Only sync credit notes modified after this time.
            progress_callback: Optional callback(processed, created, updated).

        Returns:
            SyncResult with counts and any error message.
        """
        result = SyncResult()
        connection, access_token = await self._get_connection_with_token(connection_id)

        page = 1
        has_more = True

        async with XeroClient(self.settings.xero) as client:
            while has_more:
                await self._check_rate_limits(connection)
                access_token = await self._ensure_valid_token(connection_id)

                try:
                    credit_notes, rate_limit = await client.get_credit_notes(
                        access_token=access_token,
                        tenant_id=connection.xero_tenant_id,
                        page=page,
                        modified_since=modified_since,
                    )
                except Exception as e:
                    result.error_message = str(e)
                    logger.error(f"Failed to fetch credit notes page {page}: {e}")
                    break

                # Update rate limits
                await self._update_rate_limits(
                    connection_id,
                    rate_limit.minute_remaining,
                    rate_limit.daily_remaining,
                )

                # Check if more pages
                has_more = len(credit_notes) == 100

                # Transform and upsert credit notes
                for credit_note in credit_notes:
                    try:
                        transformed = CreditNoteTransformer.transform(credit_note)
                        transformed["tenant_id"] = connection.tenant_id
                        transformed["connection_id"] = connection_id

                        # Link to client if contact exists
                        if transformed.get("xero_contact_id"):
                            xero_client = await self.client_repo.get_by_xero_contact_id(
                                connection.tenant_id, transformed["xero_contact_id"]
                            )
                            if xero_client:
                                transformed["client_id"] = xero_client.id

                        _, created = await self.credit_note_repo.upsert_from_xero(transformed)

                        # Sync allocations if present
                        allocations = credit_note.get("Allocations", [])
                        for alloc in allocations:
                            alloc_data = CreditNoteAllocationTransformer.transform(
                                alloc, credit_note["CreditNoteID"]
                            )
                            alloc_data["tenant_id"] = connection.tenant_id
                            alloc_data["connection_id"] = connection_id
                            await self.credit_note_allocation_repo.upsert_from_xero(alloc_data)

                        result.records_processed += 1
                        if created:
                            result.records_created += 1
                        else:
                            result.records_updated += 1

                    except Exception as e:
                        result.records_failed += 1
                        logger.warning(
                            f"Failed to transform credit note "
                            f"{credit_note.get('CreditNoteID')}: {e}"
                        )

                if progress_callback:
                    progress_callback(
                        result.records_processed,
                        result.records_created,
                        result.records_updated,
                    )

                page += 1

                # Brief pause between pages
                if has_more:
                    await asyncio.sleep(0.1)

        return result

    async def sync_payments(
        self,
        connection_id: UUID,
        modified_since: datetime | None = None,
        progress_callback: Callable[..., None] | None = None,
    ) -> SyncResult:
        """Sync payments from Xero to local storage.

        Args:
            connection_id: The connection ID.
            modified_since: Only sync payments modified after this time.
            progress_callback: Optional callback(processed, created, updated).

        Returns:
            SyncResult with counts and any error message.
        """
        result = SyncResult()
        connection, access_token = await self._get_connection_with_token(connection_id)

        page = 1
        has_more = True

        async with XeroClient(self.settings.xero) as client:
            while has_more:
                await self._check_rate_limits(connection)
                access_token = await self._ensure_valid_token(connection_id)

                try:
                    payments, rate_limit = await client.get_payments(
                        access_token=access_token,
                        tenant_id=connection.xero_tenant_id,
                        page=page,
                        modified_since=modified_since,
                    )
                except Exception as e:
                    result.error_message = str(e)
                    logger.error(f"Failed to fetch payments page {page}: {e}")
                    break

                await self._update_rate_limits(
                    connection_id,
                    rate_limit.minute_remaining,
                    rate_limit.daily_remaining,
                )

                has_more = len(payments) == 100

                for payment in payments:
                    try:
                        transformed = PaymentTransformer.transform(payment)
                        transformed["tenant_id"] = connection.tenant_id
                        transformed["connection_id"] = connection_id

                        # Link to client if contact exists
                        if transformed.get("xero_contact_id"):
                            xero_client = await self.client_repo.get_by_xero_contact_id(
                                connection.tenant_id, transformed["xero_contact_id"]
                            )
                            if xero_client:
                                transformed["client_id"] = xero_client.id

                        _, created = await self.payment_repo.upsert_from_xero(transformed)

                        result.records_processed += 1
                        if created:
                            result.records_created += 1
                        else:
                            result.records_updated += 1

                    except Exception as e:
                        result.records_failed += 1
                        logger.warning(
                            f"Failed to transform payment {payment.get('PaymentID')}: {e}"
                        )

                if progress_callback:
                    progress_callback(
                        result.records_processed,
                        result.records_created,
                        result.records_updated,
                    )

                page += 1
                if has_more:
                    await asyncio.sleep(0.1)

        return result

    async def sync_overpayments(
        self,
        connection_id: UUID,
        modified_since: datetime | None = None,
        progress_callback: Callable[..., None] | None = None,
    ) -> SyncResult:
        """Sync overpayments from Xero to local storage."""
        result = SyncResult()
        connection, access_token = await self._get_connection_with_token(connection_id)

        page = 1
        has_more = True

        async with XeroClient(self.settings.xero) as client:
            while has_more:
                await self._check_rate_limits(connection)
                access_token = await self._ensure_valid_token(connection_id)

                try:
                    overpayments, rate_limit = await client.get_overpayments(
                        access_token=access_token,
                        tenant_id=connection.xero_tenant_id,
                        page=page,
                        modified_since=modified_since,
                    )
                except Exception as e:
                    result.error_message = str(e)
                    logger.error(f"Failed to fetch overpayments page {page}: {e}")
                    break

                await self._update_rate_limits(
                    connection_id,
                    rate_limit.minute_remaining,
                    rate_limit.daily_remaining,
                )

                has_more = len(overpayments) == 100

                for overpayment in overpayments:
                    try:
                        transformed = OverpaymentTransformer.transform(overpayment)
                        transformed["tenant_id"] = connection.tenant_id
                        transformed["connection_id"] = connection_id

                        if transformed.get("xero_contact_id"):
                            xero_client = await self.client_repo.get_by_xero_contact_id(
                                connection.tenant_id, transformed["xero_contact_id"]
                            )
                            if xero_client:
                                transformed["client_id"] = xero_client.id

                        _, created = await self.overpayment_repo.upsert_from_xero(transformed)

                        result.records_processed += 1
                        if created:
                            result.records_created += 1
                        else:
                            result.records_updated += 1

                    except Exception as e:
                        result.records_failed += 1
                        logger.warning(
                            f"Failed to transform overpayment "
                            f"{overpayment.get('OverpaymentID')}: {e}"
                        )

                if progress_callback:
                    progress_callback(
                        result.records_processed,
                        result.records_created,
                        result.records_updated,
                    )

                page += 1
                if has_more:
                    await asyncio.sleep(0.1)

        return result

    async def sync_prepayments(
        self,
        connection_id: UUID,
        modified_since: datetime | None = None,
        progress_callback: Callable[..., None] | None = None,
    ) -> SyncResult:
        """Sync prepayments from Xero to local storage."""
        result = SyncResult()
        connection, access_token = await self._get_connection_with_token(connection_id)

        page = 1
        has_more = True

        async with XeroClient(self.settings.xero) as client:
            while has_more:
                await self._check_rate_limits(connection)
                access_token = await self._ensure_valid_token(connection_id)

                try:
                    prepayments, rate_limit = await client.get_prepayments(
                        access_token=access_token,
                        tenant_id=connection.xero_tenant_id,
                        page=page,
                        modified_since=modified_since,
                    )
                except Exception as e:
                    result.error_message = str(e)
                    logger.error(f"Failed to fetch prepayments page {page}: {e}")
                    break

                await self._update_rate_limits(
                    connection_id,
                    rate_limit.minute_remaining,
                    rate_limit.daily_remaining,
                )

                has_more = len(prepayments) == 100

                for prepayment in prepayments:
                    try:
                        transformed = PrepaymentTransformer.transform(prepayment)
                        transformed["tenant_id"] = connection.tenant_id
                        transformed["connection_id"] = connection_id

                        if transformed.get("xero_contact_id"):
                            xero_client = await self.client_repo.get_by_xero_contact_id(
                                connection.tenant_id, transformed["xero_contact_id"]
                            )
                            if xero_client:
                                transformed["client_id"] = xero_client.id

                        _, created = await self.prepayment_repo.upsert_from_xero(transformed)

                        result.records_processed += 1
                        if created:
                            result.records_created += 1
                        else:
                            result.records_updated += 1

                    except Exception as e:
                        result.records_failed += 1
                        logger.warning(
                            f"Failed to transform prepayment {prepayment.get('PrepaymentID')}: {e}"
                        )

                if progress_callback:
                    progress_callback(
                        result.records_processed,
                        result.records_created,
                        result.records_updated,
                    )

                page += 1
                if has_more:
                    await asyncio.sleep(0.1)

        return result

    async def sync_journals(
        self,
        connection_id: UUID,
        modified_since: datetime | None = None,
        progress_callback: Callable[..., None] | None = None,
    ) -> SyncResult:
        """Sync journals from Xero to local storage.

        Note: Journals use offset-based pagination (journal number),
        not page numbers.
        """
        result = SyncResult()
        connection, access_token = await self._get_connection_with_token(connection_id)

        # Get the latest journal number to start from for incremental sync
        offset = 0
        if modified_since:
            latest = await self.journal_repo.get_latest_journal_number(connection_id)
            if latest:
                offset = latest

        has_more = True

        async with XeroClient(self.settings.xero) as client:
            while has_more:
                await self._check_rate_limits(connection)
                access_token = await self._ensure_valid_token(connection_id)

                try:
                    journals, rate_limit = await client.get_journals(
                        access_token=access_token,
                        tenant_id=connection.xero_tenant_id,
                        offset=offset,
                        modified_since=modified_since,
                    )
                except Exception as e:
                    result.error_message = str(e)
                    logger.error(f"Failed to fetch journals at offset {offset}: {e}")
                    break

                await self._update_rate_limits(
                    connection_id,
                    rate_limit.minute_remaining,
                    rate_limit.daily_remaining,
                )

                has_more = len(journals) == 100

                for journal in journals:
                    try:
                        transformed = JournalTransformer.transform(journal)
                        transformed["tenant_id"] = connection.tenant_id
                        transformed["connection_id"] = connection_id

                        _, created = await self.journal_repo.upsert_from_xero(transformed)

                        result.records_processed += 1
                        if created:
                            result.records_created += 1
                        else:
                            result.records_updated += 1

                        # Update offset to latest journal number
                        journal_num = journal.get("JournalNumber", 0)
                        if journal_num > offset:
                            offset = journal_num

                    except Exception as e:
                        result.records_failed += 1
                        logger.warning(
                            f"Failed to transform journal {journal.get('JournalID')}: {e}"
                        )

                if progress_callback:
                    progress_callback(
                        result.records_processed,
                        result.records_created,
                        result.records_updated,
                    )

                if has_more:
                    await asyncio.sleep(0.1)

        return result

    async def sync_manual_journals(
        self,
        connection_id: UUID,
        modified_since: datetime | None = None,
        progress_callback: Callable[..., None] | None = None,
    ) -> SyncResult:
        """Sync manual journals from Xero to local storage."""
        result = SyncResult()
        connection, access_token = await self._get_connection_with_token(connection_id)

        page = 1
        has_more = True

        async with XeroClient(self.settings.xero) as client:
            while has_more:
                await self._check_rate_limits(connection)
                access_token = await self._ensure_valid_token(connection_id)

                try:
                    manual_journals, rate_limit = await client.get_manual_journals(
                        access_token=access_token,
                        tenant_id=connection.xero_tenant_id,
                        page=page,
                        modified_since=modified_since,
                    )
                except Exception as e:
                    result.error_message = str(e)
                    logger.error(f"Failed to fetch manual journals page {page}: {e}")
                    break

                await self._update_rate_limits(
                    connection_id,
                    rate_limit.minute_remaining,
                    rate_limit.daily_remaining,
                )

                has_more = len(manual_journals) == 100

                for manual_journal in manual_journals:
                    try:
                        transformed = ManualJournalTransformer.transform(manual_journal)
                        transformed["tenant_id"] = connection.tenant_id
                        transformed["connection_id"] = connection_id

                        _, created = await self.manual_journal_repo.upsert_from_xero(transformed)

                        result.records_processed += 1
                        if created:
                            result.records_created += 1
                        else:
                            result.records_updated += 1

                    except Exception as e:
                        result.records_failed += 1
                        logger.warning(
                            f"Failed to transform manual journal "
                            f"{manual_journal.get('ManualJournalID')}: {e}"
                        )

                if progress_callback:
                    progress_callback(
                        result.records_processed,
                        result.records_created,
                        result.records_updated,
                    )

                page += 1
                if has_more:
                    await asyncio.sleep(0.1)

        return result

    # -------------------------------------------------------------------------
    # Spec 025: Fixed Assets Sync Methods
    # -------------------------------------------------------------------------

    async def sync_asset_types(
        self,
        connection_id: UUID,
        progress_callback: Callable[..., None] | None = None,
    ) -> SyncResult:
        """Sync asset types from Xero Assets API to local storage.

        Asset types define depreciation categories with book and tax settings.
        Requires 'assets' or 'assets.read' OAuth scope.

        Args:
            connection_id: The Xero connection ID.
            progress_callback: Optional callback for progress updates.

        Returns:
            SyncResult with sync statistics.
        """
        result = SyncResult()
        connection, access_token = await self._get_connection_with_token(connection_id)

        async with XeroClient(self.settings.xero) as client:
            await self._check_rate_limits(connection)

            try:
                asset_types, rate_limit = await client.get_asset_types(
                    access_token=access_token,
                    tenant_id=connection.xero_tenant_id,
                )
            except Exception as e:
                result.error_message = str(e)
                logger.error(f"Failed to fetch asset types: {e}")
                return result

            await self._update_rate_limits(
                connection_id,
                rate_limit.minute_remaining,
                rate_limit.daily_remaining,
            )

            for asset_type in asset_types:
                try:
                    # Handle unexpected data formats
                    if not isinstance(asset_type, dict):
                        logger.warning(
                            f"Unexpected asset_type format: {type(asset_type)}, "
                            f"expected dict. Skipping."
                        )
                        result.records_failed += 1
                        continue

                    transformed = AssetTypeTransformer.transform(asset_type)
                    transformed["tenant_id"] = connection.tenant_id
                    transformed["connection_id"] = connection_id

                    _, created = await self.asset_type_repo.upsert_from_xero(transformed)

                    result.records_processed += 1
                    if created:
                        result.records_created += 1
                    else:
                        result.records_updated += 1

                except Exception as e:
                    result.records_failed += 1
                    asset_type_id = (
                        asset_type.get("assetTypeId", "unknown")
                        if isinstance(asset_type, dict)
                        else "unknown"
                    )
                    logger.warning(f"Failed to transform asset type {asset_type_id}: {e}")

            if progress_callback:
                progress_callback(
                    result.records_processed,
                    result.records_created,
                    result.records_updated,
                )

        return result

    async def sync_assets(
        self,
        connection_id: UUID,
        status: str | None = None,
        progress_callback: Callable[..., None] | None = None,
    ) -> SyncResult:
        """Sync fixed assets from Xero Assets API to local storage.

        Syncs assets with their depreciation schedules, book values, and
        disposal information. Requires 'assets' or 'assets.read' OAuth scope.

        Args:
            connection_id: The Xero connection ID.
            status: Optional filter by asset status (Draft, Registered, Disposed).
            progress_callback: Optional callback for progress updates.

        Returns:
            SyncResult with sync statistics.
        """
        result = SyncResult()
        connection, access_token = await self._get_connection_with_token(connection_id)

        page = 1
        has_more = True

        async with XeroClient(self.settings.xero) as client:
            while has_more:
                await self._check_rate_limits(connection)
                access_token = await self._ensure_valid_token(connection_id)

                try:
                    assets, pagination, rate_limit = await client.get_assets(
                        access_token=access_token,
                        tenant_id=connection.xero_tenant_id,
                        status=status,
                        page=page,
                        page_size=100,
                    )
                except Exception as e:
                    result.error_message = str(e)
                    logger.error(f"Failed to fetch assets page {page}: {e}")
                    break

                await self._update_rate_limits(
                    connection_id,
                    rate_limit.minute_remaining,
                    rate_limit.daily_remaining,
                )

                # Check pagination for more pages
                total_pages = pagination.get("pageCount", 1)
                has_more = page < total_pages

                for asset in assets:
                    try:
                        transformed = AssetTransformer.transform(asset)
                        transformed["tenant_id"] = connection.tenant_id
                        transformed["connection_id"] = connection_id

                        _, created = await self.asset_repo.upsert_from_xero(transformed)

                        result.records_processed += 1
                        if created:
                            result.records_created += 1
                        else:
                            result.records_updated += 1

                    except Exception as e:
                        result.records_failed += 1
                        logger.warning(f"Failed to transform asset {asset.get('assetId')}: {e}")

                if progress_callback:
                    progress_callback(
                        result.records_processed,
                        result.records_created,
                        result.records_updated,
                    )

                page += 1
                if has_more:
                    await asyncio.sleep(0.1)

        return result

    # =========================================================================
    # Spec 025: Purchase Orders, Repeating Invoices, Tracking, Quotes
    # =========================================================================

    async def sync_purchase_orders(
        self,
        connection_id: UUID,
        status: str | None = None,
        progress_callback: Callable[[int, int, int], None] | None = None,
    ) -> SyncResult:
        """Sync purchase orders from Xero.

        Args:
            connection_id: Connection UUID.
            status: Filter by status (DRAFT, SUBMITTED, AUTHORISED, BILLED).
            progress_callback: Optional callback for progress updates.

        Returns:
            SyncResult with counts.
        """
        from .repository import XeroPurchaseOrderRepository
        from .transformers import PurchaseOrderTransformer

        result = SyncResult(
            sync_type=XeroSyncType.FULL.value,
            started_at=datetime.now(UTC),
        )

        connection, access_token = await self._get_connection_with_token(connection_id)

        po_repo = XeroPurchaseOrderRepository(self.session)
        page = 1

        async with XeroClient(self.settings.xero) as client:
            while True:
                access_token = await self._ensure_valid_token(connection_id)
                try:
                    orders, rate_limit = await client.get_purchase_orders(
                        access_token=access_token,
                        tenant_id=connection.xero_tenant_id,
                        status=status,
                        page=page,
                    )
                except Exception as e:
                    logger.error(f"Failed to fetch purchase orders: {e}")
                    result.records_failed += 1
                    break

                if not orders:
                    break

                for order in orders:
                    try:
                        data = PurchaseOrderTransformer.transform(
                            order,
                            tenant_id=connection.tenant_id,
                            connection_id=connection_id,
                        )
                        _, created = await po_repo.upsert_from_xero(data)
                        result.records_processed += 1
                        if created:
                            result.records_created += 1
                        else:
                            result.records_updated += 1
                    except Exception as e:
                        result.records_failed += 1
                        logger.warning(
                            f"Failed to transform PO {order.get('PurchaseOrderID')}: {e}"
                        )

                if progress_callback:
                    progress_callback(
                        result.records_processed, result.records_created, result.records_updated
                    )

                page += 1
                if len(orders) < 100:
                    break
                await asyncio.sleep(0.1)

        result.completed_at = datetime.now(UTC)
        return result

    async def sync_repeating_invoices(
        self,
        connection_id: UUID,
        status: str | None = None,
        progress_callback: Callable[[int, int, int], None] | None = None,
    ) -> SyncResult:
        """Sync repeating invoices from Xero.

        Args:
            connection_id: Connection UUID.
            status: Filter by status (DRAFT, AUTHORISED).
            progress_callback: Optional callback for progress updates.

        Returns:
            SyncResult with counts.
        """
        from .repository import XeroRepeatingInvoiceRepository
        from .transformers import RepeatingInvoiceTransformer

        result = SyncResult(
            sync_type=XeroSyncType.FULL.value,
            started_at=datetime.now(UTC),
        )

        connection, access_token = await self._get_connection_with_token(connection_id)

        ri_repo = XeroRepeatingInvoiceRepository(self.session)

        async with XeroClient(self.settings.xero) as client:
            try:
                invoices, rate_limit = await client.get_repeating_invoices(
                    access_token=access_token,
                    tenant_id=connection.xero_tenant_id,
                    status=status,
                )
            except Exception as e:
                logger.error(f"Failed to fetch repeating invoices: {e}")
                result.records_failed += 1
                result.completed_at = datetime.now(UTC)
                return result

        for invoice in invoices:
            try:
                data = RepeatingInvoiceTransformer.transform(
                    invoice,
                    tenant_id=connection.tenant_id,
                    connection_id=connection_id,
                )
                _, created = await ri_repo.upsert_from_xero(data)
                result.records_processed += 1
                if created:
                    result.records_created += 1
                else:
                    result.records_updated += 1
            except Exception as e:
                result.records_failed += 1
                logger.warning(
                    f"Failed to transform repeating invoice {invoice.get('RepeatingInvoiceID')}: {e}"
                )

        if progress_callback:
            progress_callback(
                result.records_processed, result.records_created, result.records_updated
            )

        result.completed_at = datetime.now(UTC)
        return result

    async def sync_tracking_categories(
        self,
        connection_id: UUID,
        include_archived: bool = False,
        progress_callback: Callable[[int, int, int], None] | None = None,
    ) -> SyncResult:
        """Sync tracking categories from Xero.

        Args:
            connection_id: Connection UUID.
            include_archived: Include archived categories.
            progress_callback: Optional callback for progress updates.

        Returns:
            SyncResult with counts.
        """
        from .repository import XeroTrackingCategoryRepository, XeroTrackingOptionRepository
        from .transformers import TrackingCategoryTransformer, TrackingOptionTransformer

        result = SyncResult(
            sync_type=XeroSyncType.FULL.value,
            started_at=datetime.now(UTC),
        )

        connection, access_token = await self._get_connection_with_token(connection_id)

        tc_repo = XeroTrackingCategoryRepository(self.session)
        to_repo = XeroTrackingOptionRepository(self.session)

        async with XeroClient(self.settings.xero) as client:
            try:
                categories, rate_limit = await client.get_tracking_categories(
                    access_token=access_token,
                    tenant_id=connection.xero_tenant_id,
                    include_archived=include_archived,
                )
            except Exception as e:
                logger.error(f"Failed to fetch tracking categories: {e}")
                result.records_failed += 1
                result.completed_at = datetime.now(UTC)
                return result

        for category in categories:
            try:
                cat_data = TrackingCategoryTransformer.transform(
                    category,
                    tenant_id=connection.tenant_id,
                    connection_id=connection_id,
                )
                saved_category, created = await tc_repo.upsert_from_xero(cat_data)
                result.records_processed += 1
                if created:
                    result.records_created += 1
                else:
                    result.records_updated += 1

                # Sync options for this category
                options = category.get("Options", [])
                for option in options:
                    try:
                        opt_data = TrackingOptionTransformer.transform(
                            option,
                            tracking_category_id=saved_category.id,
                        )
                        await to_repo.upsert_from_xero(opt_data)
                    except Exception as e:
                        logger.warning(f"Failed to transform tracking option: {e}")

            except Exception as e:
                result.records_failed += 1
                logger.warning(
                    f"Failed to transform tracking category {category.get('TrackingCategoryID')}: {e}"
                )

        if progress_callback:
            progress_callback(
                result.records_processed, result.records_created, result.records_updated
            )

        result.completed_at = datetime.now(UTC)
        return result

    async def sync_quotes(
        self,
        connection_id: UUID,
        status: str | None = None,
        progress_callback: Callable[[int, int, int], None] | None = None,
    ) -> SyncResult:
        """Sync quotes from Xero.

        Args:
            connection_id: Connection UUID.
            status: Filter by status (DRAFT, SENT, ACCEPTED, etc).
            progress_callback: Optional callback for progress updates.

        Returns:
            SyncResult with counts.
        """
        from .repository import XeroQuoteRepository
        from .transformers import QuoteTransformer

        result = SyncResult(
            sync_type=XeroSyncType.FULL.value,
            started_at=datetime.now(UTC),
        )

        connection, access_token = await self._get_connection_with_token(connection_id)

        quote_repo = XeroQuoteRepository(self.session)
        page = 1

        async with XeroClient(self.settings.xero) as client:
            while True:
                access_token = await self._ensure_valid_token(connection_id)
                try:
                    quotes, rate_limit = await client.get_quotes(
                        access_token=access_token,
                        tenant_id=connection.xero_tenant_id,
                        status=status,
                        page=page,
                    )
                except Exception as e:
                    logger.error(f"Failed to fetch quotes: {e}")
                    result.records_failed += 1
                    break

                if not quotes:
                    break

                for quote in quotes:
                    try:
                        data = QuoteTransformer.transform(
                            quote,
                            tenant_id=connection.tenant_id,
                            connection_id=connection_id,
                        )
                        _, created = await quote_repo.upsert_from_xero(data)
                        result.records_processed += 1
                        if created:
                            result.records_created += 1
                        else:
                            result.records_updated += 1
                    except Exception as e:
                        result.records_failed += 1
                        logger.warning(f"Failed to transform quote {quote.get('QuoteID')}: {e}")

                if progress_callback:
                    progress_callback(
                        result.records_processed, result.records_created, result.records_updated
                    )

                page += 1
                if len(quotes) < 100:
                    break
                await asyncio.sleep(0.1)

        result.completed_at = datetime.now(UTC)
        return result


class XeroSyncService:
    """Service for orchestrating Xero sync operations.

    Manages sync jobs, validates preconditions, and coordinates
    the sync workflow.
    """

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        celery_app: "Celery | None" = None,
    ) -> None:
        """Initialize sync service.

        Args:
            session: Database session.
            settings: Application settings.
            celery_app: Optional Celery app for queuing tasks.
        """
        self.session = session
        self.settings = settings
        self.celery_app = celery_app
        self.connection_repo = XeroConnectionRepository(session)
        self.job_repo = XeroSyncJobRepository(session)
        self.rate_limiter = XeroRateLimiter()

    async def initiate_sync(
        self,
        connection_id: UUID,
        sync_type: XeroSyncType = XeroSyncType.FULL,
        force_full: bool = False,
        check_client_limit: bool = True,
    ) -> XeroSyncJobResponse:
        """Initiate a new sync operation.

        Creates a sync job and queues a Celery task.

        Args:
            connection_id: The connection ID.
            sync_type: Type of sync to perform.
            force_full: Force full sync even if incremental available.
            check_client_limit: Whether to check client limit before sync (Spec 020).

        Returns:
            XeroSyncJobResponse with job details.

        Raises:
            XeroConnectionNotFoundExc: If connection not found.
            XeroConnectionInactiveError: If connection not active.
            XeroSyncInProgressError: If sync already in progress.
            XeroRateLimitExceededError: If rate limits exceeded.
            ClientLimitExceededError: If tenant is at client limit (Spec 020).
        """
        # Validate connection exists and is active
        connection = await self.connection_repo.get_by_id(connection_id)
        if connection is None:
            raise XeroConnectionNotFoundExc(connection_id)

        if connection.status != XeroConnectionStatus.ACTIVE:
            raise XeroConnectionInactiveError(connection_id)

        # Check client limit before starting sync (Spec 020)
        if check_client_limit:
            from sqlalchemy import select

            tenant = await self.session.scalar(
                select(Tenant).where(Tenant.id == connection.tenant_id)
            )
            if tenant:
                billing_service = BillingService(self.session)
                # This raises ClientLimitExceededError if at limit
                billing_service.check_client_limit(tenant)

        # Check for existing sync in progress
        existing_job = await self.job_repo.get_active_for_connection(connection_id)
        if existing_job:
            # Auto-expire stale jobs stuck as in_progress for over 30 minutes
            stale_threshold = datetime.now(UTC) - timedelta(minutes=30)
            if existing_job.updated_at.replace(tzinfo=UTC) < stale_threshold:
                await self.job_repo.update_status(
                    existing_job.id,
                    XeroSyncStatus.FAILED,
                    error_message="Auto-expired: job stale for over 30 minutes",
                )
                await self.session.flush()
            else:
                raise XeroSyncInProgressError(connection_id, existing_job.id)

        # Check rate limits
        state = RateLimitState(
            daily_remaining=connection.rate_limit_daily_remaining or 5000,
            minute_remaining=connection.rate_limit_minute_remaining or 60,
            # Note: rate_limit_reset_at tracks when the minute bucket resets,
            # NOT when we're rate limited until. We're only rate limited if
            # we've actually hit a 429. So we don't set rate_limited_until here.
        )
        if not self.rate_limiter.can_make_request(state):
            wait_seconds = self.rate_limiter.get_wait_time(state)
            raise XeroRateLimitExceededError(wait_seconds)

        # Delegate to start_phased_sync for the actual job creation and dispatch
        return await self.start_phased_sync(
            connection=connection,
            sync_type=sync_type,
            force_full=force_full,
            triggered_by="user",
        )

    async def start_phased_sync(
        self,
        connection: XeroConnection,
        sync_type: XeroSyncType = XeroSyncType.FULL,
        force_full: bool = False,
        triggered_by: str = "user",
    ) -> XeroSyncJobResponse:
        """Create a sync job and dispatch the phased sync Celery task.

        This method creates a XeroSyncJob with the triggered_by field and
        dispatches the run_phased_sync Celery task (not the legacy run_sync).

        Args:
            connection: The validated, active XeroConnection.
            sync_type: Type of sync to perform.
            force_full: Force full sync even if incremental is available.
            triggered_by: What triggered this sync (user, schedule, webhook, system).

        Returns:
            XeroSyncJobResponse with the created job details.
        """
        # Create sync job with phased sync fields
        job = await self.job_repo.create(
            tenant_id=connection.tenant_id,
            connection_id=connection.id,
            sync_type=sync_type,
        )
        # Set the triggered_by field on the job
        job.triggered_by = triggered_by
        await self.session.flush()

        # Mark connection as sync in progress
        await self.connection_repo.update(
            connection.id,
            XeroConnectionUpdate(last_used_at=datetime.now(UTC)),
        )

        # Queue phased sync Celery task if available
        if self.celery_app:
            self.celery_app.send_task(
                "app.tasks.xero.run_phased_sync",
                kwargs={
                    "job_id": str(job.id),
                    "connection_id": str(connection.id),
                    "tenant_id": str(connection.tenant_id),
                    "sync_type": sync_type.value,
                    "force_full": force_full,
                },
            )

        logger.info(
            "Phased sync job created and dispatched",
            extra={
                "job_id": str(job.id),
                "connection_id": str(connection.id),
                "tenant_id": str(connection.tenant_id),
                "sync_type": sync_type.value,
                "force_full": force_full,
                "triggered_by": triggered_by,
            },
        )

        return XeroSyncJobResponse(
            id=job.id,
            connection_id=job.connection_id,
            sync_type=job.sync_type,
            status=job.status,
            started_at=job.started_at,
            completed_at=job.completed_at,
            records_processed=job.records_processed,
            records_created=job.records_created,
            records_updated=job.records_updated,
            records_failed=job.records_failed,
            error_message=job.error_message,
            progress_details=job.progress_details,
            created_at=job.created_at,
            sync_phase=job.sync_phase,
            triggered_by=job.triggered_by,
        )

    async def get_sync_status(self, job_id: UUID) -> XeroSyncJobResponse:
        """Get status of a sync job.

        Args:
            job_id: The job ID.

        Returns:
            XeroSyncJobResponse with current status.

        Raises:
            XeroSyncJobNotFoundError: If job not found.
        """
        job = await self.job_repo.get_by_id(job_id)
        if job is None:
            raise XeroSyncJobNotFoundError(job_id)

        return XeroSyncJobResponse(
            id=job.id,
            connection_id=job.connection_id,
            sync_type=job.sync_type,
            status=job.status,
            started_at=job.started_at,
            completed_at=job.completed_at,
            records_processed=job.records_processed,
            records_created=job.records_created,
            records_updated=job.records_updated,
            records_failed=job.records_failed,
            error_message=job.error_message,
            progress_details=job.progress_details,
            created_at=job.created_at,
            sync_phase=job.sync_phase,
            triggered_by=job.triggered_by,
        )

    async def get_sync_history(
        self,
        connection_id: UUID,
        limit: int = 10,
        offset: int = 0,
    ) -> XeroSyncHistoryResponse:
        """Get sync job history for a connection.

        Args:
            connection_id: The connection ID.
            limit: Max jobs to return.
            offset: Number of jobs to skip.

        Returns:
            XeroSyncHistoryResponse with paginated jobs.
        """
        jobs, total = await self.job_repo.list_by_connection(
            connection_id,
            limit=limit,
            offset=offset,
        )

        return XeroSyncHistoryResponse(
            jobs=[
                XeroSyncJobResponse(
                    id=job.id,
                    connection_id=job.connection_id,
                    sync_type=job.sync_type,
                    status=job.status,
                    started_at=job.started_at,
                    completed_at=job.completed_at,
                    records_processed=job.records_processed,
                    records_created=job.records_created,
                    records_updated=job.records_updated,
                    records_failed=job.records_failed,
                    error_message=job.error_message,
                    progress_details=job.progress_details,
                    created_at=job.created_at,
                    sync_phase=job.sync_phase,
                    triggered_by=job.triggered_by,
                )
                for job in jobs
            ],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def cancel_sync(self, job_id: UUID) -> XeroSyncJobResponse:
        """Cancel a sync job.

        Args:
            job_id: The job ID.

        Returns:
            XeroSyncJobResponse with updated status.

        Raises:
            XeroSyncJobNotFoundError: If job not found.
        """
        job = await self.job_repo.get_by_id(job_id)
        if job is None:
            raise XeroSyncJobNotFoundError(job_id)

        # Only cancel if pending or in_progress
        if job.status in (XeroSyncStatus.PENDING, XeroSyncStatus.IN_PROGRESS):
            await self.job_repo.update_status(
                job_id,
                XeroSyncStatus.CANCELLED,
                error_message="Cancelled by user",
            )

        # Refresh job
        job = await self.job_repo.get_by_id(job_id)

        return XeroSyncJobResponse(
            id=job.id,
            connection_id=job.connection_id,
            sync_type=job.sync_type,
            status=job.status,
            started_at=job.started_at,
            completed_at=job.completed_at,
            records_processed=job.records_processed,
            records_created=job.records_created,
            records_updated=job.records_updated,
            records_failed=job.records_failed,
            error_message=job.error_message,
            progress_details=job.progress_details,
            created_at=job.created_at,
            sync_phase=job.sync_phase,
            triggered_by=job.triggered_by,
        )

    async def start_multi_client_sync(
        self,
        tenant_id: UUID,
        force_full: bool = False,
    ) -> MultiClientSyncResponse:
        """Start phased sync for all active connections in a tenant.

        Fetches all active Xero connections for the given tenant, skips any
        that already have an active sync job, creates a new sync job for each
        eligible connection, and dispatches phased sync tasks with staggered
        delays to avoid Xero API rate limit spikes.

        Args:
            tenant_id: The tenant ID to sync all connections for.
            force_full: Force full sync even if incremental is available.

        Returns:
            MultiClientSyncResponse with batch_id, totals, and per-connection details.
        """
        import uuid

        batch_id = uuid.uuid4()

        # Get all active connections for this tenant
        connections = await self.connection_repo.get_all_active(tenant_id)

        jobs_queued: list[MultiClientQueuedConnection] = []
        jobs_skipped: list[MultiClientSkippedConnection] = []

        for i, connection in enumerate(connections):
            # Check for existing active sync (pending or in_progress)
            active_job = await self.job_repo.get_active_for_connection(connection.id)
            if active_job:
                jobs_skipped.append(
                    MultiClientSkippedConnection(
                        connection_id=connection.id,
                        organization_name=connection.organization_name or "Unknown",
                        reason="sync_in_progress",
                    )
                )
                continue

            # Create sync job for this connection
            job = XeroSyncJob(
                tenant_id=tenant_id,
                connection_id=connection.id,
                sync_type=XeroSyncType.FULL,
                status=XeroSyncStatus.PENDING,
                triggered_by="system",
            )
            self.session.add(job)
            await self.session.flush()

            # Dispatch phased sync with staggered countdown to avoid rate limit spikes.
            # Each connection is delayed by 2 seconds relative to the previous one.
            if self.celery_app:
                self.celery_app.send_task(
                    "app.tasks.xero.run_phased_sync",
                    kwargs={
                        "job_id": str(job.id),
                        "connection_id": str(connection.id),
                        "tenant_id": str(tenant_id),
                        "sync_type": "full",
                        "force_full": force_full,
                    },
                    countdown=i * 2,
                )

            jobs_queued.append(
                MultiClientQueuedConnection(
                    connection_id=connection.id,
                    organization_name=connection.organization_name or "Unknown",
                    job_id=job.id,
                )
            )

        await self.session.commit()

        logger.info(
            "Multi-client sync batch dispatched",
            extra={
                "batch_id": str(batch_id),
                "tenant_id": str(tenant_id),
                "total_connections": len(connections),
                "jobs_queued": len(jobs_queued),
                "jobs_skipped": len(jobs_skipped),
                "force_full": force_full,
            },
        )

        return MultiClientSyncResponse(
            batch_id=batch_id,
            total_connections=len(connections),
            jobs_queued=len(jobs_queued),
            jobs_skipped=len(jobs_skipped),
            queued=jobs_queued,
            skipped=jobs_skipped,
        )


class XeroClientService:
    """Service for viewing client data and financial summaries.

    Provides read-only operations for:
    - Listing clients with filtering and pagination
    - Getting client details with connection metadata
    - Retrieving client invoices and transactions
    - Calculating BAS quarter financial summaries
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize client service.

        Args:
            session: Database session.
        """
        self.session = session
        self.client_repo = XeroClientRepository(session)
        self.invoice_repo = XeroInvoiceRepository(session)
        self.transaction_repo = XeroBankTransactionRepository(session)
        self.connection_repo = XeroConnectionRepository(session)

    async def list_clients(
        self,
        search: str | None = None,
        contact_type: str | None = None,
        is_active: bool | None = None,
        sort_by: Literal["name", "contact_type", "created_at"] = "name",
        sort_order: Literal["asc", "desc"] = "asc",
        limit: int = 25,
        offset: int = 0,
    ) -> XeroClientListResponse:
        """List all clients for the current tenant.

        Args:
            search: Optional search term for name/email.
            contact_type: Filter by contact type (CUSTOMER, SUPPLIER, etc.).
            is_active: Filter by active status.
            sort_by: Field to sort by.
            sort_order: Sort direction.
            limit: Maximum results to return.
            offset: Number of results to skip.

        Returns:
            XeroClientListResponse with clients and pagination info.
        """
        clients, total = await self.client_repo.list_all_for_tenant(
            search=search,
            contact_type=contact_type,
            is_active=is_active,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset,
        )

        return XeroClientListResponse(
            clients=[XeroClientResponse.model_validate(c) for c in clients],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get_client_detail(self, client_id: UUID) -> XeroClientDetailResponse:
        """Get detailed client information with connection metadata.

        Args:
            client_id: The client ID.

        Returns:
            XeroClientDetailResponse with full client details.

        Raises:
            XeroClientNotFoundError: If client not found.
        """
        client = await self.client_repo.get_by_id(client_id)
        if client is None:
            raise XeroClientNotFoundError(client_id)

        # Get connection for metadata
        connection = await self.connection_repo.get_by_id(client.connection_id)

        return XeroClientDetailResponse(
            id=client.id,
            connection_id=client.connection_id,
            xero_contact_id=client.xero_contact_id,
            name=client.name,
            email=client.email,
            contact_number=client.contact_number,
            abn=client.abn,
            contact_type=client.contact_type,
            is_active=client.is_active,
            addresses=client.addresses,
            phones=client.phones,
            xero_updated_at=client.xero_updated_at,
            created_at=client.created_at,
            updated_at=client.updated_at,
            organization_name=connection.organization_name if connection else "Unknown",
            connection_status=connection.status if connection else None,
            last_synced_at=connection.last_contacts_sync_at if connection else None,
        )

    async def get_client_invoices(
        self,
        client_id: UUID,
        from_date: date | None = None,
        to_date: date | None = None,
        status: str | None = None,
        invoice_type: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> XeroInvoiceListResponse:
        """Get invoices for a specific client.

        Args:
            client_id: The client ID.
            from_date: Filter invoices from this date.
            to_date: Filter invoices to this date.
            status: Filter by invoice status.
            invoice_type: Filter by invoice type (ACCREC, ACCPAY).
            limit: Maximum results to return.
            offset: Number of results to skip.

        Returns:
            XeroInvoiceListResponse with invoices and pagination info.

        Raises:
            XeroClientNotFoundError: If client not found.
        """
        # Verify client exists
        client = await self.client_repo.get_by_id(client_id)
        if client is None:
            raise XeroClientNotFoundError(client_id)

        invoices, total = await self.invoice_repo.list_by_client(
            client_id=client_id,
            from_date=from_date,
            to_date=to_date,
            status=status,
            invoice_type=invoice_type,
            limit=limit,
            offset=offset,
        )

        return XeroInvoiceListResponse(
            invoices=[XeroInvoiceResponse.model_validate(inv) for inv in invoices],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get_client_transactions(
        self,
        client_id: UUID,
        from_date: date | None = None,
        to_date: date | None = None,
        transaction_type: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> XeroBankTransactionListResponse:
        """Get bank transactions for a specific client.

        Args:
            client_id: The client ID.
            from_date: Filter transactions from this date.
            to_date: Filter transactions to this date.
            transaction_type: Filter by transaction type.
            limit: Maximum results to return.
            offset: Number of results to skip.

        Returns:
            XeroBankTransactionListResponse with transactions and pagination info.

        Raises:
            XeroClientNotFoundError: If client not found.
        """
        # Verify client exists
        client = await self.client_repo.get_by_id(client_id)
        if client is None:
            raise XeroClientNotFoundError(client_id)

        transactions, total = await self.transaction_repo.list_by_client(
            client_id=client_id,
            from_date=from_date,
            to_date=to_date,
            transaction_type=transaction_type,
            limit=limit,
            offset=offset,
        )

        return XeroBankTransactionListResponse(
            transactions=[XeroBankTransactionResponse.model_validate(tx) for tx in transactions],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get_client_financial_summary(
        self,
        client_id: UUID,
        quarter: int,
        fy_year: int,
    ) -> ClientFinancialSummaryResponse:
        """Calculate financial summary for a client in a specific quarter.

        Args:
            client_id: The client ID.
            quarter: Quarter number (1-4).
            fy_year: Financial year (e.g., 2025 for FY25).

        Returns:
            ClientFinancialSummaryResponse with BAS-relevant totals.

        Raises:
            XeroClientNotFoundError: If client not found.
            ValueError: If quarter is invalid.
        """
        # Verify client exists
        client = await self.client_repo.get_by_id(client_id)
        if client is None:
            raise XeroClientNotFoundError(client_id)

        # Get quarter date range
        start_date, end_date = get_quarter_dates(quarter, fy_year)

        # Calculate invoice summary
        invoice_summary = await self.invoice_repo.calculate_summary(
            client_id=client_id,
            from_date=start_date,
            to_date=end_date,
        )

        # Get transaction count for the period
        transaction_count = await self.transaction_repo.count_by_client_and_date_range(
            client_id=client_id,
            from_date=start_date,
            to_date=end_date,
        )

        # Calculate total invoice count from sales + purchases
        invoice_count = (
            invoice_summary["sales_invoice_count"] + invoice_summary["purchase_invoice_count"]
        )

        return ClientFinancialSummaryResponse(
            client_id=client_id,
            quarter=quarter,
            fy_year=fy_year,
            quarter_label=format_quarter(quarter, fy_year),
            total_sales=invoice_summary["total_sales"],
            gst_collected=invoice_summary["gst_collected"],
            total_purchases=invoice_summary["total_purchases"],
            gst_paid=invoice_summary["gst_paid"],
            invoice_count=invoice_count,
            transaction_count=transaction_count,
            net_gst=invoice_summary["gst_collected"] - invoice_summary["gst_paid"],
        )

    def get_available_quarters(
        self,
        num_previous: int = 4,
        include_next: bool = True,
    ) -> AvailableQuartersResponse:
        """Get list of available quarters for selection.

        Args:
            num_previous: Number of previous quarters to include.
            include_next: Whether to include next quarter if near end of current.

        Returns:
            AvailableQuartersResponse with quarters list and current quarter.
        """
        quarters = get_available_quarters(
            num_previous=num_previous,
            include_next=include_next,
        )
        current_q, current_fy = get_current_quarter()

        quarter_infos = []
        for q, fy in quarters:
            start, end = get_quarter_dates(q, fy)
            quarter_infos.append(
                QuarterInfo(
                    quarter=q,
                    fy_year=fy,
                    label=format_quarter(q, fy),
                    start_date=datetime.combine(start, datetime.min.time()),
                    end_date=datetime.combine(end, datetime.max.time()),
                )
            )

        # Build current quarter info
        current_start, current_end = get_quarter_dates(current_q, current_fy)
        current_info = QuarterInfo(
            quarter=current_q,
            fy_year=current_fy,
            label=format_quarter(current_q, current_fy),
            start_date=datetime.combine(current_start, datetime.min.time()),
            end_date=datetime.combine(current_end, datetime.max.time()),
        )

        return AvailableQuartersResponse(
            quarters=quarter_infos,
            current=current_info,
        )


class XpmClientNotFoundError(Exception):
    """XPM client not found."""

    def __init__(self, client_id: UUID) -> None:
        self.client_id = client_id
        super().__init__(f"XPM client {client_id} not found")


class XpmClientService:
    """Service for XPM client and Xero organization connection management.

    Handles:
    - Fetching all Xero connections from Xero API
    - Syncing connections to database
    - Matching Xero organizations to XPM clients
    - Managing XPM client connection status
    """

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
    ) -> None:
        """Initialize XPM client service.

        Args:
            session: Database session.
            settings: Application settings.
        """
        self.session = session
        self.settings = settings
        self.xpm_client_repo = XpmClientRepository(session)
        self.connection_repo = XeroConnectionRepository(session)
        self.encryption = TokenEncryption(settings.token_encryption.key.get_secret_value())

    async def fetch_xero_connections(
        self,
        connection_id: UUID,
    ) -> list[XeroOrganization]:
        """Fetch all authorized Xero organizations from Xero API.

        Uses an existing connection's access token to call the Xero /connections
        endpoint and retrieve all organizations the user has access to.

        Args:
            connection_id: ID of an existing active XeroConnection to use for auth.

        Returns:
            List of XeroOrganization objects from Xero API.

        Raises:
            XeroConnectionNotFoundError: If connection not found.
            XeroConnectionInactiveError: If connection is not active.
        """
        # Get the connection for auth
        connection = await self.connection_repo.get_by_id(connection_id)
        if not connection:
            raise XeroConnectionNotFoundExc(connection_id)

        if connection.status != XeroConnectionStatus.ACTIVE:
            raise XeroConnectionInactiveError(
                f"Connection {connection_id} is not active (status: {connection.status})"
            )

        # Decrypt access token
        access_token = self.encryption.decrypt(connection.access_token)

        # Fetch connections from Xero API
        async with XeroClient(self.settings.xero) as client:
            organizations = await client.get_connections(access_token)

        logger.info(
            "Fetched %d Xero connections for tenant %s",
            len(organizations),
            connection.tenant_id,
        )

        return organizations

    async def sync_xero_connections(
        self,
        tenant_id: UUID,
        organizations: list[XeroOrganization],
        connected_by: UUID | None = None,
    ) -> dict[str, Any]:
        """Sync Xero organizations to database as XeroConnection records.

        Creates or updates XeroConnection records for each organization.
        Groups connections by authEventId to identify bulk authorization batches.

        Args:
            tenant_id: The Clairo tenant ID.
            organizations: List of XeroOrganization from Xero API.
            connected_by: User ID who authorized the connections.

        Returns:
            Dictionary with sync results:
            - created: Number of new connections created
            - updated: Number of existing connections updated
            - total: Total organizations processed
            - connections: List of connection IDs
        """
        created = 0
        updated = 0
        connection_ids: list[UUID] = []

        for org in organizations:
            # Check if connection already exists
            existing = await self.connection_repo.get_by_xero_tenant_id(
                tenant_id=tenant_id,
                xero_tenant_id=org.id,
            )

            if existing:
                # Update existing connection (re-authorization or refresh)
                await self.connection_repo.update(
                    connection_id=existing.id,
                    data=XeroConnectionUpdate(
                        status=XeroConnectionStatus.ACTIVE,
                    ),
                )
                # Update auth_event_id if provided (for bulk connections)
                if org.auth_event_id:
                    from sqlalchemy import text

                    await self.session.execute(
                        text("""
                        UPDATE xero_connections
                        SET auth_event_id = :auth_event_id
                        WHERE id = :connection_id
                        """),
                        {
                            "auth_event_id": org.auth_event_id,
                            "connection_id": existing.id,
                        },
                    )
                connection_ids.append(existing.id)
                updated += 1
                logger.debug(
                    "Updated existing connection %s for org %s",
                    existing.id,
                    org.display_name,
                )
            else:
                # This is a new organization - we need tokens to create a connection
                # In practice, this sync method is called after OAuth callback
                # where we already have the tokens. For now, log a warning.
                logger.warning(
                    "Organization %s (%s) not in database - needs OAuth authorization",
                    org.display_name,
                    org.id,
                )
                # We'll track it but can't create without tokens
                # The OAuth callback handler should create these

        logger.info(
            "Synced Xero connections for tenant %s: %d created, %d updated",
            tenant_id,
            created,
            updated,
        )

        return {
            "created": created,
            "updated": updated,
            "total": len(organizations),
            "connections": connection_ids,
        }

    async def match_connections_to_xpm_clients(
        self,
        tenant_id: UUID,
    ) -> dict[str, Any]:
        """Match Xero connections to XPM clients.

        Attempts to match XeroConnection records to XpmClient records based on:
        1. Exact organization name match
        2. ABN match (if available in organization details)
        3. Fuzzy name match (TODO: implement later)

        Args:
            tenant_id: The Clairo tenant ID.

        Returns:
            Dictionary with matching results:
            - matched: List of {client_id, connection_id, org_name}
            - unmatched_connections: List of connections without matching clients
            - unmatched_clients: List of clients without connections
        """
        matched: list[dict[str, Any]] = []
        unmatched_connections: list[dict[str, Any]] = []

        # Get all client-type connections for this tenant
        all_connections = await self.connection_repo.list_by_tenant(
            tenant_id=tenant_id,
            include_disconnected=False,
        )

        # Filter to client connections only (not practice connections)
        client_connections = [
            c for c in all_connections if c.connection_type == XeroConnectionType.CLIENT
        ]

        # Get all XPM clients that are not yet connected
        unconnected_clients, _ = await self.xpm_client_repo.get_unconnected_clients(
            tenant_id=tenant_id,
            limit=1000,  # Get all for matching
        )

        # Create a lookup by name (normalized)
        client_by_name: dict[str, Any] = {}
        for client in unconnected_clients:
            normalized_name = client.name.lower().strip()
            client_by_name[normalized_name] = client

        # Try to match each connection
        for connection in client_connections:
            # Skip if this connection is already linked to a client
            existing_link = await self.xpm_client_repo.get_by_xero_connection_id(connection.id)
            if existing_link:
                matched.append(
                    {
                        "client_id": str(existing_link.id),
                        "client_name": existing_link.name,
                        "connection_id": str(connection.id),
                        "org_name": connection.organization_name,
                        "match_type": "existing",
                    }
                )
                continue

            # Try exact name match
            normalized_org_name = connection.organization_name.lower().strip()
            if normalized_org_name in client_by_name:
                client = client_by_name[normalized_org_name]
                # Link the connection to the client
                await self.xpm_client_repo.link_xero_connection(
                    client_id=client.id,
                    xero_connection_id=connection.id,
                    xero_org_name=connection.organization_name,
                )
                matched.append(
                    {
                        "client_id": str(client.id),
                        "client_name": client.name,
                        "connection_id": str(connection.id),
                        "org_name": connection.organization_name,
                        "match_type": "exact_name",
                    }
                )
                # Remove from unconnected pool
                del client_by_name[normalized_org_name]
                continue

            # No match found
            unmatched_connections.append(
                {
                    "connection_id": str(connection.id),
                    "org_name": connection.organization_name,
                    "xero_tenant_id": connection.xero_tenant_id,
                }
            )

        # Remaining clients are unmatched
        unmatched_clients = [
            {
                "client_id": str(client.id),
                "client_name": client.name,
                "xpm_client_id": client.xpm_client_id,
            }
            for client in client_by_name.values()
        ]

        logger.info(
            "Matched Xero connections to XPM clients for tenant %s: "
            "%d matched, %d unmatched connections, %d unmatched clients",
            tenant_id,
            len(matched),
            len(unmatched_connections),
            len(unmatched_clients),
        )

        return {
            "matched": matched,
            "unmatched_connections": unmatched_connections,
            "unmatched_clients": unmatched_clients,
        }

    async def link_client_to_connection(
        self,
        client_id: UUID,
        connection_id: UUID,
    ) -> XpmClientResponse:
        """Manually link an XPM client to a Xero connection.

        Used when automatic matching fails and user manually selects which
        Xero organization belongs to which client.

        Args:
            client_id: The XPM client ID.
            connection_id: The XeroConnection ID to link.

        Returns:
            Updated XpmClientResponse.

        Raises:
            XpmClientNotFoundError: If client not found.
            XeroConnectionNotFoundError: If connection not found.
        """
        # Verify client exists
        client = await self.xpm_client_repo.get_by_id(client_id)
        if not client:
            raise XpmClientNotFoundError(client_id)

        # Verify connection exists
        connection = await self.connection_repo.get_by_id(connection_id)
        if not connection:
            raise XeroConnectionNotFoundExc(connection_id)

        # Link them
        updated_client = await self.xpm_client_repo.link_xero_connection(
            client_id=client_id,
            xero_connection_id=connection_id,
            xero_org_name=connection.organization_name,
        )

        logger.info(
            "Linked XPM client %s to Xero connection %s (%s)",
            client_id,
            connection_id,
            connection.organization_name,
        )

        return XpmClientResponse.model_validate(updated_client)

    async def unlink_client_from_connection(
        self,
        client_id: UUID,
        reason: str | None = None,
    ) -> XpmClientResponse:
        """Unlink an XPM client from its Xero connection.

        Args:
            client_id: The XPM client ID.
            reason: Optional reason for unlinking (for audit).

        Returns:
            Updated XpmClientResponse.

        Raises:
            XpmClientNotFoundError: If client not found.
        """
        client = await self.xpm_client_repo.get_by_id(client_id)
        if not client:
            raise XpmClientNotFoundError(client_id)

        updated_client = await self.xpm_client_repo.unlink_xero_connection(
            client_id=client_id,
            mark_as_disconnected=True,
        )

        logger.info(
            "Unlinked XPM client %s from Xero connection. Reason: %s",
            client_id,
            reason or "Not specified",
        )

        return XpmClientResponse.model_validate(updated_client)

    async def list_xpm_clients(
        self,
        tenant_id: UUID,
        connection_status: XpmClientConnectionStatus | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> XpmClientListResponse:
        """List XPM clients for a tenant with filtering.

        Args:
            tenant_id: The tenant ID.
            connection_status: Filter by connection status.
            search: Search by name.
            limit: Max results.
            offset: Pagination offset.

        Returns:
            XpmClientListResponse with clients and pagination info.
        """
        clients, total = await self.xpm_client_repo.list_by_tenant(
            tenant_id=tenant_id,
            connection_status=connection_status,
            search=search,
            limit=limit,
            offset=offset,
        )

        return XpmClientListResponse(
            clients=[XpmClientResponse.model_validate(c) for c in clients],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get_connection_progress(
        self,
        tenant_id: UUID,
    ) -> XpmClientConnectionProgress:
        """Get connection progress summary for a tenant.

        Shows how many XPM clients have their Xero organizations connected.

        Args:
            tenant_id: The tenant ID.

        Returns:
            XpmClientConnectionProgress with status counts and rates.
        """
        counts = await self.xpm_client_repo.count_by_connection_status(tenant_id)
        total = sum(counts.values())

        connected = counts.get("connected", 0)
        connection_rate = connected / total if total > 0 else 0.0

        return XpmClientConnectionProgress(
            status_counts=XpmClientStatusCounts(
                not_connected=counts.get("not_connected", 0),
                connected=connected,
                disconnected=counts.get("disconnected", 0),
                no_access=counts.get("no_access", 0),
                total=total,
            ),
            connection_rate=connection_rate,
            all_connected=(connected == total and total > 0),
        )

    async def link_client_by_tenant_id(
        self,
        client_id: UUID,
        xero_tenant_id: str,
        tenant_id: UUID,
    ) -> XpmClientResponse:
        """Link an XPM client to a Xero connection by Xero tenant ID.

        Alternative to link_client_to_connection that uses Xero's tenant ID
        instead of our internal connection UUID.

        Args:
            client_id: The XPM client ID.
            xero_tenant_id: The Xero organization's tenant ID.
            tenant_id: The tenant ID for scoping.

        Returns:
            Updated XpmClientResponse.

        Raises:
            XpmClientNotFoundError: If client not found.
            XeroConnectionNotFoundError: If no connection with that tenant ID.
        """
        # Verify client exists
        client = await self.xpm_client_repo.get_by_id(client_id)
        if not client:
            raise XpmClientNotFoundError(client_id)

        # Find connection by Xero tenant ID
        connection = await self.connection_repo.get_by_xero_tenant_id(
            xero_tenant_id=xero_tenant_id,
            tenant_id=tenant_id,
        )
        if not connection:
            raise XeroConnectionNotFoundExc(
                f"No Xero connection found with tenant ID: {xero_tenant_id}"
            )

        # Link them
        updated_client = await self.xpm_client_repo.link_xero_connection(
            client_id=client_id,
            xero_connection_id=connection.id,
            xero_org_name=connection.organization_name,
        )

        logger.info(
            "Linked XPM client %s to Xero org %s (tenant_id: %s)",
            client_id,
            connection.organization_name,
            xero_tenant_id,
        )

        return XpmClientResponse.model_validate(updated_client)

    async def get_unmatched_connections(
        self,
        tenant_id: UUID,
    ) -> list[XeroConnectionResponse]:
        """Get Xero connections that aren't linked to any XPM client.

        These are organizations the accountant has authorized but couldn't be
        automatically matched to an XPM client (by name or email).

        Args:
            tenant_id: The tenant ID.

        Returns:
            List of XeroConnectionResponse for unmatched connections.
        """
        # Get all XPM clients with their connection IDs
        clients, _ = await self.xpm_client_repo.list_by_tenant(
            tenant_id=tenant_id,
            limit=10000,  # Get all clients
            offset=0,
        )
        linked_connection_ids = {c.xero_connection_id for c in clients if c.xero_connection_id}

        # Get all active Xero connections for tenant
        all_connections = await self.connection_repo.list_by_tenant(tenant_id)

        # Filter to only unmatched (not linked to any client)
        unmatched = [
            conn
            for conn in all_connections
            if conn.id not in linked_connection_ids and conn.status == XeroConnectionStatus.ACTIVE
        ]

        return [XeroConnectionResponse.model_validate(conn) for conn in unmatched]


# =============================================================================
# Xero Report Service (Spec 023)
# =============================================================================


class XeroReportService:
    """Service for managing Xero financial reports.

    Handles fetching, caching, and transforming reports from Xero's
    Reports API including Profit & Loss, Balance Sheet, Aged Receivables,
    Aged Payables, Trial Balance, Bank Summary, and Budget Summary.
    """

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
    ) -> None:
        """Initialize XeroReportService.

        Args:
            session: Database session.
            settings: Application settings.
        """
        from app.core.audit import AuditService
        from app.modules.integrations.xero.repository import (
            XeroReportRepository,
            XeroReportSyncJobRepository,
        )

        self.session = session
        self.settings = settings
        self.report_repo = XeroReportRepository(session)
        self.sync_job_repo = XeroReportSyncJobRepository(session)
        self.connection_repo = XeroConnectionRepository(session)
        self.encryption = TokenEncryption(settings.token_encryption.key.get_secret_value())
        self.audit_service = AuditService(session)
        self.logger = logging.getLogger(__name__)

    async def _get_connection_and_token(self, connection_id: UUID) -> tuple[XeroConnection, str]:
        """Get connection and ensure valid access token.

        Args:
            connection_id: The connection ID.

        Returns:
            Tuple of (connection, decrypted_access_token).

        Raises:
            XeroConnectionNotFoundExc: If connection not found.
            XeroConnectionInactiveError: If connection not active.
        """
        connection = await self.connection_repo.get_by_id(connection_id)
        if connection is None:
            raise XeroConnectionNotFoundExc(connection_id)

        if connection.status != XeroConnectionStatus.ACTIVE:
            raise XeroConnectionInactiveError(str(connection_id))

        # Refresh if needed
        if connection.needs_refresh:
            self.logger.info(
                f"Token needs refresh for connection {connection_id}, "
                f"expires_at={connection.token_expires_at}"
            )
            conn_service = XeroConnectionService(self.session, self.settings)
            connection = await conn_service.refresh_tokens(connection_id)
            self.logger.info(f"Token refreshed successfully for connection {connection_id}")

        access_token = self.encryption.decrypt(connection.access_token)
        return connection, access_token

    async def get_report(
        self,
        connection_id: UUID,
        report_type: str,
        period_key: str,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Get a report, from cache if available or fetch from Xero.

        Args:
            connection_id: The Xero connection ID.
            report_type: Type of report (e.g., 'profit_and_loss').
            period_key: Period identifier (e.g., '2025-FY', '2025-12').
            force_refresh: If True, bypass cache and fetch fresh data.

        Returns:
            Report data dict with summary and rows.

        Raises:
            XeroConnectionNotFoundError: If connection not found.
            XeroConnectionInactiveError: If connection is inactive.
        """
        from app.modules.integrations.xero.models import XeroReportType

        # Convert string to enum
        try:
            report_type_enum = XeroReportType(report_type)
        except ValueError as e:
            raise ValueError(f"Invalid report type: {report_type}") from e

        # Handle aged reports specially - compute from synced invoice data
        # Xero's aged report APIs require contactId which isn't practical
        if report_type_enum == XeroReportType.AGED_RECEIVABLES:
            self.logger.info(
                "Computing aged receivables from synced invoices",
                extra={
                    "connection_id": str(connection_id),
                    "report_type": report_type,
                    "period_key": period_key,
                },
            )
            await self._log_report_access(
                connection_id=connection_id,
                report_type=report_type,
                period_key=period_key,
                source="computed",
            )
            return await self._compute_aged_receivables(connection_id)

        if report_type_enum == XeroReportType.AGED_PAYABLES:
            self.logger.info(
                "Computing aged payables from synced bills",
                extra={
                    "connection_id": str(connection_id),
                    "report_type": report_type,
                    "period_key": period_key,
                },
            )
            await self._log_report_access(
                connection_id=connection_id,
                report_type=report_type,
                period_key=period_key,
                source="computed",
            )
            return await self._compute_aged_payables(connection_id)

        # Check cache first (unless forcing refresh)
        if not force_refresh:
            cached = await self.report_repo.get_cached_report(
                connection_id=connection_id,
                report_type=report_type_enum,
                period_key=period_key,
                include_expired=False,
            )
            if cached:
                self.logger.info(
                    "Returning cached report",
                    extra={
                        "connection_id": str(connection_id),
                        "report_type": report_type,
                        "period_key": period_key,
                    },
                )
                # Log audit event for report access
                await self._log_report_access(
                    connection_id=connection_id,
                    report_type=report_type,
                    period_key=period_key,
                    source="cache",
                )
                return self._report_to_dict(cached)

        # Fetch from Xero
        return await self._fetch_and_cache_report(
            connection_id=connection_id,
            report_type=report_type_enum,
            period_key=period_key,
        )

    async def list_report_statuses(
        self,
        connection_id: UUID,
    ) -> list[dict[str, Any]]:
        """List available report types with their sync status.

        Args:
            connection_id: The Xero connection ID.

        Returns:
            List of report status dicts.
        """
        from app.modules.integrations.xero.models import XeroReportType

        # Get connection to verify it exists and is active
        connection = await self.connection_repo.get_by_id(connection_id)
        if not connection:
            raise XeroConnectionNotFoundExc(connection_id)

        statuses = []

        for report_type in XeroReportType:
            # Get any active sync job for this report type
            active_job = await self.sync_job_repo.get_active_for_connection(
                connection_id=connection_id,
                report_type=report_type,
            )

            # Get cached reports for this type
            reports, _ = await self.report_repo.get_reports_by_connection(
                connection_id=connection_id,
                report_type=report_type,
                include_expired=True,
                limit=10,
            )

            # Find most recent valid cached report
            last_synced_at = None
            is_stale = True
            periods_available = []

            for report in reports:
                periods_available.append(report.period_key)
                if report.fetched_at:
                    if last_synced_at is None or report.fetched_at > last_synced_at:
                        last_synced_at = report.fetched_at
                if report.cache_expires_at and report.cache_expires_at > datetime.now(UTC):
                    is_stale = False

            statuses.append(
                {
                    "report_type": report_type.value,
                    "display_name": XeroReportTransformer.get_display_name(report_type.value),
                    "is_available": True,
                    "last_synced_at": last_synced_at,
                    "is_stale": is_stale and len(reports) > 0,
                    "sync_status": active_job.status.value if active_job else None,
                    "periods_available": periods_available,
                }
            )

        return statuses

    async def refresh_report(
        self,
        connection_id: UUID,
        report_type: str,
        period_key: str,
        user_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Request a refresh of a specific report.

        Enforces throttling (max 1 refresh per 5 minutes per report type).

        Args:
            connection_id: The Xero connection ID.
            report_type: Type of report to refresh.
            period_key: Period to refresh.
            user_id: User requesting the refresh.

        Returns:
            Report data if immediately available, or pending status.

        Raises:
            XeroRateLimitExceededError: If refresh throttle exceeded.
        """
        from app.modules.integrations.xero.models import XeroReportType

        try:
            report_type_enum = XeroReportType(report_type)
        except ValueError as e:
            raise ValueError(f"Invalid report type: {report_type}") from e

        # Handle aged reports specially - compute from synced invoice data
        # Xero's aged report APIs require contactId which isn't practical
        if report_type_enum == XeroReportType.AGED_RECEIVABLES:
            self.logger.info(
                "Computing aged receivables from synced invoices (refresh)",
                extra={
                    "connection_id": str(connection_id),
                    "report_type": report_type,
                },
            )
            return await self._compute_aged_receivables(connection_id)

        if report_type_enum == XeroReportType.AGED_PAYABLES:
            self.logger.info(
                "Computing aged payables from synced bills (refresh)",
                extra={
                    "connection_id": str(connection_id),
                    "report_type": report_type,
                },
            )
            return await self._compute_aged_payables(connection_id)

        # Check throttle (1 minute between refresh requests)
        recent_job = await self.sync_job_repo.get_recent_by_report_type(
            connection_id=connection_id,
            report_type=report_type_enum,
            minutes=1,
        )

        if recent_job:
            seconds_remaining = 60 - int(
                (datetime.now(UTC) - recent_job.created_at).total_seconds()
            )
            if seconds_remaining > 0:
                raise XeroRateLimitExceededError(
                    wait_seconds=seconds_remaining,
                    limit_type="refresh",
                )

        # Fetch fresh data
        return await self._fetch_and_cache_report(
            connection_id=connection_id,
            report_type=report_type_enum,
            period_key=period_key,
            triggered_by="on_demand",
            user_id=user_id,
        )

    async def sync_all_reports(
        self,
        connection_id: UUID,
        report_types: list[str] | None = None,
    ) -> dict[str, Any]:
        """Sync all (or specified) report types for a connection.

        Used for scheduled batch sync operations.

        Args:
            connection_id: The Xero connection ID.
            report_types: Optional list of report types to sync.

        Returns:
            Summary of sync results.
        """
        from app.modules.integrations.xero.models import XeroReportType

        # Get connection
        connection = await self.connection_repo.get_by_id(connection_id)
        if not connection:
            raise XeroConnectionNotFoundExc(connection_id)

        # Determine report types to sync
        # Exclude aged reports - they are computed from synced invoices, not fetched from API
        excluded_types = {XeroReportType.AGED_RECEIVABLES, XeroReportType.AGED_PAYABLES}
        types_to_sync = []
        if report_types:
            for rt in report_types:
                try:
                    report_type_enum = XeroReportType(rt)
                    if report_type_enum not in excluded_types:
                        types_to_sync.append(report_type_enum)
                    else:
                        self.logger.info(f"Skipping {rt} - computed from synced invoices")
                except ValueError:
                    self.logger.warning(f"Ignoring invalid report type: {rt}")
        else:
            types_to_sync = [rt for rt in XeroReportType if rt not in excluded_types]

        results = {
            "connection_id": str(connection_id),
            "reports_synced": 0,
            "reports_failed": 0,
            "errors": [],
        }

        # Generate current period key
        now = datetime.now(UTC)
        current_period = f"{now.year}-{now.month:02d}"

        for report_type in types_to_sync:
            try:
                await self._fetch_and_cache_report(
                    connection_id=connection_id,
                    report_type=report_type,
                    period_key=current_period,
                    triggered_by="scheduled",
                )
                results["reports_synced"] += 1
            except Exception as e:
                self.logger.error(
                    f"Failed to sync {report_type.value}: {e}",
                    exc_info=True,
                )
                results["reports_failed"] += 1
                results["errors"].append(
                    {
                        "report_type": report_type.value,
                        "error": str(e),
                    }
                )

        return results

    async def _fetch_and_cache_report(
        self,
        connection_id: UUID,
        report_type: "XeroReportType",
        period_key: str,
        triggered_by: str = "on_demand",
        user_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Fetch a report from Xero and cache it.

        Args:
            connection_id: The Xero connection ID.
            report_type: Type of report to fetch.
            period_key: Period identifier.
            triggered_by: How the sync was triggered.
            user_id: User who triggered the sync.

        Returns:
            Report data dict.
        """
        from app.modules.integrations.xero.models import (
            XeroReportSyncStatus,
        )

        # Get connection with valid token (refreshes if needed)
        connection, access_token = await self._get_connection_and_token(connection_id)

        # Create sync job
        job = await self.sync_job_repo.create(
            tenant_id=connection.tenant_id,
            connection_id=connection_id,
            report_type=report_type,
            triggered_by=triggered_by,
            user_id=user_id,
        )

        try:
            # Update job status to in_progress
            await self.sync_job_repo.update_status(
                job_id=job.id,
                status=XeroReportSyncStatus.IN_PROGRESS,
            )

            # Parse period key to get date range
            from_date, to_date = self._parse_period_key(period_key)

            # Fetch report from Xero based on type
            async with XeroClient(self.settings.xero) as client:
                xero_response, rate_limit = await self._call_xero_report_api(
                    client=client,
                    access_token=access_token,
                    tenant_id=connection.xero_tenant_id,
                    report_type=report_type,
                    from_date=from_date,
                    to_date=to_date,
                )

            # Update rate limits on connection
            await self.connection_repo.update(
                connection_id,
                XeroConnectionUpdate(
                    rate_limit_minute_remaining=rate_limit.minute_remaining,
                    rate_limit_daily_remaining=rate_limit.daily_remaining,
                    last_used_at=datetime.now(UTC),
                ),
            )

            # Extract metadata and rows
            metadata = XeroReportTransformer.extract_report_metadata(xero_response)
            rows = XeroReportTransformer.extract_rows(xero_response)
            rows_count = XeroReportTransformer.count_data_rows(rows)

            # Extract summary using appropriate transformer
            summary_data = self._extract_summary(report_type, rows)

            # Calculate cache expiry
            cache_ttl = self._get_cache_ttl(report_type, period_key)
            cache_expires_at = datetime.now(UTC) + cache_ttl

            # Determine if current period
            is_current = self._is_current_period(period_key)

            # Upsert report
            report_data = {
                "id": job.id,  # Use job ID as report ID for now
                "tenant_id": connection.tenant_id,
                "connection_id": connection_id,
                "report_type": report_type,
                "period_key": period_key,
                "xero_report_id": metadata.get("xero_report_id"),
                "report_name": metadata.get("report_name", report_type.value),
                "report_titles": metadata.get("report_titles", []),
                "xero_updated_at": metadata.get("xero_updated_at"),
                "rows_data": {"rows": rows},
                "summary_data": summary_data,
                "fetched_at": datetime.now(UTC),
                "cache_expires_at": cache_expires_at,
                "is_current_period": is_current,
                "parameters": {},
            }

            report, _ = await self.report_repo.upsert_report(report_data)

            # Update job as completed
            await self.sync_job_repo.update_status(
                job_id=job.id,
                status=XeroReportSyncStatus.COMPLETED,
                report_id=report.id,
                rows_fetched=rows_count,
            )

            # Log audit event for report fetch from Xero
            await self._log_report_access(
                connection_id=connection_id,
                report_type=report_type.value,
                period_key=period_key,
                source="xero_api",
            )

            return self._report_to_dict(report)

        except Exception as e:
            # Update job as failed
            await self.sync_job_repo.update_status(
                job_id=job.id,
                status=XeroReportSyncStatus.FAILED,
                error_code="FETCH_ERROR",
                error_message=str(e)[:500],
            )
            raise

    def _get_cache_ttl(self, report_type: "XeroReportType", period_key: str) -> timedelta:
        """Get cache TTL for a report type and period.

        Args:
            report_type: Type of report.
            period_key: Period identifier.

        Returns:
            Cache TTL as timedelta.
        """
        from app.modules.integrations.xero.models import XeroReportType

        is_current = self._is_current_period(period_key)

        # Historical periods have indefinite cache (1 year)
        if not is_current:
            return timedelta(days=365)

        # Current period TTLs by report type
        ttls = {
            XeroReportType.PROFIT_AND_LOSS: timedelta(hours=1),
            XeroReportType.BALANCE_SHEET: timedelta(hours=1),
            XeroReportType.AGED_RECEIVABLES: timedelta(hours=4),
            XeroReportType.AGED_PAYABLES: timedelta(hours=4),
            XeroReportType.TRIAL_BALANCE: timedelta(hours=1),
            XeroReportType.BANK_SUMMARY: timedelta(hours=4),
            XeroReportType.BUDGET_SUMMARY: timedelta(hours=24),
        }

        return ttls.get(report_type, timedelta(hours=1))

    def _is_current_period(self, period_key: str) -> bool:
        """Check if a period key represents the current period.

        Args:
            period_key: Period identifier.

        Returns:
            True if current period, False otherwise.
        """
        now = datetime.now(UTC)

        # Handle financial year (YYYY-FY)
        if period_key.endswith("-FY"):
            year = int(period_key.split("-")[0])
            # Australian FY runs July to June
            if now.month >= 7:
                return year == now.year
            return year == now.year - 1

        # Handle quarter (YYYY-QN)
        if "-Q" in period_key:
            parts = period_key.split("-Q")
            year = int(parts[0])
            quarter = int(parts[1])
            current_quarter = (now.month - 1) // 3 + 1
            return year == now.year and quarter == current_quarter

        # Handle month (YYYY-MM)
        if len(period_key) == 7:  # YYYY-MM
            year_month = f"{now.year}-{now.month:02d}"
            return period_key == year_month

        # Handle date (YYYY-MM-DD) - current if today or future
        if len(period_key) == 10:  # YYYY-MM-DD
            try:
                period_date = datetime.strptime(period_key, "%Y-%m-%d")
                return period_date.date() >= now.date()
            except ValueError:
                return True

        return True  # Default to current

    def _report_to_dict(self, report: "XeroReport") -> dict[str, Any]:
        """Convert a XeroReport model to a response dict.

        Args:
            report: XeroReport model instance.

        Returns:
            Response dict.
        """
        return {
            "id": str(report.id),
            "report_type": report.report_type.value,
            "report_name": report.report_name,
            "report_titles": report.report_titles,
            "period_key": report.period_key,
            "period_start": report.period_start,
            "period_end": report.period_end,
            "as_of_date": report.as_of_date,
            "summary": report.summary_data,
            "rows": report.rows_data.get("rows", []),
            "fetched_at": report.fetched_at,
            "cache_expires_at": report.cache_expires_at,
            "is_current_period": report.is_current_period,
            "is_stale": report.cache_expires_at < datetime.now(UTC),
        }

    def _parse_period_key(self, period_key: str) -> tuple[str | None, str | None]:
        """Parse a period key into from_date and to_date strings.

        Args:
            period_key: Period identifier (e.g., '2025-FY', '2025-12', '2025-Q1').

        Returns:
            Tuple of (from_date, to_date) in YYYY-MM-DD format.
        """
        now = datetime.now(UTC)

        # Handle "current" keyword
        if period_key == "current":
            # Current month
            first_day = date(now.year, now.month, 1)
            if now.month == 12:
                last_day = date(now.year + 1, 1, 1) - timedelta(days=1)
            else:
                last_day = date(now.year, now.month + 1, 1) - timedelta(days=1)
            return first_day.isoformat(), last_day.isoformat()

        # Handle financial year (YYYY-FY) - Australian FY runs July to June
        if period_key.endswith("-FY"):
            fy_year = int(period_key.split("-")[0])
            from_date = date(fy_year, 7, 1)  # July 1
            to_date = date(fy_year + 1, 6, 30)  # June 30
            return from_date.isoformat(), to_date.isoformat()

        # Handle quarter (YYYY-QN)
        if "-Q" in period_key:
            parts = period_key.split("-Q")
            year = int(parts[0])
            quarter = int(parts[1])
            # Q1 = Jan-Mar, Q2 = Apr-Jun, Q3 = Jul-Sep, Q4 = Oct-Dec
            quarter_months = {1: (1, 3), 2: (4, 6), 3: (7, 9), 4: (10, 12)}
            start_month, end_month = quarter_months[quarter]
            from_date = date(year, start_month, 1)
            if end_month == 12:
                to_date = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                to_date = date(year, end_month + 1, 1) - timedelta(days=1)
            return from_date.isoformat(), to_date.isoformat()

        # Handle month (YYYY-MM)
        if len(period_key) == 7:
            year, month = period_key.split("-")
            year_int = int(year)
            month_int = int(month)
            from_date = date(year_int, month_int, 1)
            if month_int == 12:
                to_date = date(year_int + 1, 1, 1) - timedelta(days=1)
            else:
                to_date = date(year_int, month_int + 1, 1) - timedelta(days=1)
            return from_date.isoformat(), to_date.isoformat()

        # Handle specific date (YYYY-MM-DD) - use as both from and to
        if len(period_key) == 10:
            return period_key, period_key

        # Default: return None to let API use defaults
        return None, None

    # =========================================================================
    # Bank Data Methods (Spec 049 — FR-015 to FR-018)
    # =========================================================================

    async def get_bank_balances(
        self,
        connection_id: UUID,
    ) -> list[dict[str, Any]]:
        """Get per-account bank balances from the Bank Summary report.

        Uses the existing report cache pipeline. Returns per-account
        opening/closing balances from the most recent Bank Summary.

        Args:
            connection_id: The Xero connection ID.

        Returns:
            List of per-account balance dicts.
        """
        from app.modules.integrations.xero.transformers import BankSummaryTransformer

        report_data = await self.get_report(
            connection_id=connection_id,
            report_type="bank_summary",
            period_key="current",
        )
        rows_data = report_data.get("rows_data", [])
        if not rows_data:
            return []
        return BankSummaryTransformer.extract_per_account_summary(rows_data)

    async def get_last_reconciliation_date(
        self,
        connection_id: UUID,
    ) -> "date | None":
        """Derive the last bank reconciliation date from synced transactions.

        Queries the most recent reconciled bank transaction date across
        all bank accounts for the given connection.

        Args:
            connection_id: The Xero connection ID.

        Returns:
            The date of the most recent reconciled transaction, or None.
        """
        from sqlalchemy import func, select

        from app.modules.integrations.xero.models import XeroBankTransaction

        result = await self.session.execute(
            select(func.max(XeroBankTransaction.transaction_date)).where(
                XeroBankTransaction.connection_id == connection_id,
                XeroBankTransaction.is_reconciled.is_(True),
            )
        )
        max_date = result.scalar_one_or_none()
        if max_date is None:
            return None
        return max_date.date() if hasattr(max_date, "date") else max_date

    async def _call_xero_report_api(
        self,
        client: XeroClient,
        access_token: str,
        tenant_id: str,
        report_type: "XeroReportType",
        from_date: str | None,
        to_date: str | None,
    ) -> tuple[dict[str, Any], RateLimitState]:
        """Call the appropriate Xero Reports API based on report type.

        Args:
            client: XeroClient instance.
            access_token: Valid Xero access token.
            tenant_id: Xero tenant/organization ID.
            report_type: Type of report to fetch.
            from_date: Start date for the report period.
            to_date: End date for the report period.

        Returns:
            Tuple of (Xero API response dict, rate limit state).
        """
        from app.modules.integrations.xero.models import XeroReportType

        if report_type == XeroReportType.PROFIT_AND_LOSS:
            return await client.get_profit_and_loss(
                access_token=access_token,
                tenant_id=tenant_id,
                from_date=from_date,
                to_date=to_date,
            )
        elif report_type == XeroReportType.BALANCE_SHEET:
            return await client.get_balance_sheet(
                access_token=access_token,
                tenant_id=tenant_id,
                as_of_date=to_date,  # Balance sheet is point-in-time
            )
        elif report_type == XeroReportType.AGED_RECEIVABLES:
            return await client.get_aged_receivables(
                access_token=access_token,
                tenant_id=tenant_id,
                as_of_date=to_date,
            )
        elif report_type == XeroReportType.AGED_PAYABLES:
            return await client.get_aged_payables(
                access_token=access_token,
                tenant_id=tenant_id,
                as_of_date=to_date,
            )
        elif report_type == XeroReportType.TRIAL_BALANCE:
            return await client.get_trial_balance(
                access_token=access_token,
                tenant_id=tenant_id,
                as_of_date=to_date,
            )
        elif report_type == XeroReportType.BANK_SUMMARY:
            return await client.get_bank_summary(
                access_token=access_token,
                tenant_id=tenant_id,
                from_date=from_date,
                to_date=to_date,
            )
        elif report_type == XeroReportType.BUDGET_SUMMARY:
            return await client.get_budget_summary(
                access_token=access_token,
                tenant_id=tenant_id,
            )
        else:
            raise ValueError(f"Unsupported report type: {report_type}")

    def _extract_summary(
        self,
        report_type: "XeroReportType",
        rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Extract summary data from report rows using appropriate transformer.

        Args:
            report_type: Type of report.
            rows: Report rows from Xero API.

        Returns:
            Summary dict with extracted metrics.
        """
        from app.modules.integrations.xero.models import XeroReportType

        if report_type == XeroReportType.PROFIT_AND_LOSS:
            return ProfitAndLossTransformer.extract_profit_and_loss_summary(rows)
        elif report_type == XeroReportType.BALANCE_SHEET:
            return BalanceSheetTransformer.extract_balance_sheet_summary(rows)
        elif report_type == XeroReportType.AGED_RECEIVABLES:
            return AgedReceivablesTransformer.extract_aged_receivables_summary(rows)
        elif report_type == XeroReportType.AGED_PAYABLES:
            return AgedPayablesTransformer.extract_aged_payables_summary(rows)
        elif report_type == XeroReportType.TRIAL_BALANCE:
            return TrialBalanceTransformer.extract_trial_balance_summary(rows)
        elif report_type == XeroReportType.BANK_SUMMARY:
            return BankSummaryTransformer.extract_bank_summary_summary(rows)
        else:
            # For Budget Summary or unknown types, return empty summary
            return {}

    async def _log_report_access(
        self,
        connection_id: UUID,
        report_type: str,
        period_key: str,
        source: str = "api",
        outcome: str = "success",
    ) -> None:
        """Log an audit event for report access.

        Args:
            connection_id: The Xero connection ID.
            report_type: Type of report accessed.
            period_key: Period of the report.
            source: Where the report came from (cache, api).
            outcome: Whether access was successful.
        """
        from app.core.tenant_context import TenantContext

        try:
            # Get tenant context
            tenant_id = TenantContext.get_current_tenant_id()

            await self.audit_service.log_event(
                event_type=f"xero.report.{report_type}.accessed",
                event_category="integration",
                resource_type="xero_report",
                resource_id=connection_id,
                action="read",
                outcome=outcome,
                tenant_id=tenant_id,
                new_values={
                    "report_type": report_type,
                    "period_key": period_key,
                    "source": source,
                },
            )
        except Exception as e:
            # Don't fail the main request if audit logging fails
            self.logger.warning(
                f"Failed to log audit event: {e}",
                extra={
                    "connection_id": str(connection_id),
                    "report_type": report_type,
                },
            )

    # =========================================================================
    # Computed Aged Reports (from synced invoices)
    # =========================================================================

    async def _compute_aged_receivables(
        self,
        connection_id: UUID,
        as_of_date: date | None = None,
    ) -> dict[str, Any]:
        """Compute aged receivables from synced ACCREC invoices.

        Args:
            connection_id: The Xero connection ID.
            as_of_date: Date to calculate aging from. Defaults to today.

        Returns:
            Report data dict with summary and rows.
        """
        from sqlalchemy import and_, select

        from app.modules.integrations.xero.models import (
            XeroClient,
            XeroInvoice,
            XeroInvoiceStatus,
            XeroInvoiceType,
        )

        if as_of_date is None:
            as_of_date = date.today()

        # Query unpaid receivables (ACCREC + AUTHORISED status)
        query = select(XeroInvoice).where(
            and_(
                XeroInvoice.connection_id == connection_id,
                XeroInvoice.invoice_type == XeroInvoiceType.ACCREC,
                XeroInvoice.status == XeroInvoiceStatus.AUTHORISED,
            )
        )
        result = await self.session.execute(query)
        invoices = result.scalars().all()

        # Get contact names for display
        contact_ids = list({inv.xero_contact_id for inv in invoices if inv.xero_contact_id})
        contact_names: dict[str, str] = {}
        if contact_ids:
            contact_query = select(XeroClient.xero_contact_id, XeroClient.name).where(
                and_(
                    XeroClient.connection_id == connection_id,
                    XeroClient.xero_contact_id.in_(contact_ids),
                )
            )
            contact_result = await self.session.execute(contact_query)
            contact_names = {row[0]: row[1] for row in contact_result.fetchall()}

        # Calculate aging buckets
        current = Decimal("0.00")
        overdue_30 = Decimal("0.00")
        overdue_60 = Decimal("0.00")
        overdue_90 = Decimal("0.00")
        overdue_90_plus = Decimal("0.00")

        # Track high-risk contacts (contacts with most overdue)
        contact_totals: dict[str, dict] = {}

        rows = []
        for inv in invoices:
            amount = inv.total_amount or Decimal("0.00")
            due_date = inv.due_date.date() if inv.due_date else inv.issue_date.date()
            days_overdue = (as_of_date - due_date).days

            # Assign to bucket
            if days_overdue <= 0:
                current += amount
                bucket = "Current"
            elif days_overdue <= 30:
                overdue_30 += amount
                bucket = "1-30 Days"
            elif days_overdue <= 60:
                overdue_60 += amount
                bucket = "31-60 Days"
            elif days_overdue <= 90:
                overdue_90 += amount
                bucket = "61-90 Days"
            else:
                overdue_90_plus += amount
                bucket = "90+ Days"

            # Track by contact for high-risk list
            contact_id = inv.xero_contact_id or "Unknown"
            contact_name = contact_names.get(contact_id, contact_id)
            if contact_id not in contact_totals:
                contact_totals[contact_id] = {
                    "name": contact_name,
                    "total": Decimal("0.00"),
                    "overdue": Decimal("0.00"),
                }
            contact_totals[contact_id]["total"] += amount
            if days_overdue > 0:
                contact_totals[contact_id]["overdue"] += amount

            # Add row for display
            rows.append(
                {
                    "row_type": "Row",
                    "cells": [
                        {"value": inv.invoice_number or inv.xero_invoice_id, "attributes": []},
                        {"value": contact_name, "attributes": []},
                        {"value": str(due_date), "attributes": []},
                        {"value": f"${float(amount):,.2f}", "attributes": []},
                        {"value": bucket, "attributes": []},
                    ],
                }
            )

        total = current + overdue_30 + overdue_60 + overdue_90 + overdue_90_plus
        overdue_total = overdue_30 + overdue_60 + overdue_90 + overdue_90_plus
        overdue_pct = float(overdue_total / total * 100) if total > 0 else 0.0

        # Get top 5 high-risk contacts (most overdue)
        high_risk = sorted(
            [
                {"name": c["name"], "amount": float(c["overdue"])}
                for c in contact_totals.values()
                if c["overdue"] > 0
            ],
            key=lambda x: x["amount"],
            reverse=True,
        )[:5]

        summary = {
            "total": float(total),
            "current": float(current),
            "overdue_30": float(overdue_30),
            "overdue_60": float(overdue_60),
            "overdue_90": float(overdue_90),
            "overdue_90_plus": float(overdue_90_plus),
            "overdue_total": float(overdue_total),
            "overdue_pct": round(overdue_pct, 1),
            "high_risk_contacts": high_risk,
        }

        # Add header row
        header_row = {
            "row_type": "Header",
            "cells": [
                {"value": "Invoice", "attributes": []},
                {"value": "Contact", "attributes": []},
                {"value": "Due Date", "attributes": []},
                {"value": "Amount", "attributes": []},
                {"value": "Aging", "attributes": []},
            ],
        }

        import uuid as uuid_module

        return {
            "id": str(uuid_module.uuid4()),
            "report_type": "aged_receivables_by_contact",
            "report_name": "Aged Receivables",
            "report_titles": [f"As of {as_of_date}"],
            "period_key": str(as_of_date),
            "period_start": None,
            "period_end": str(as_of_date),
            "as_of_date": str(as_of_date),
            "summary": summary,
            "rows": [header_row] + rows,
            "fetched_at": datetime.now(UTC).isoformat(),
            "cache_expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            "is_current_period": True,
            "is_stale": False,
        }

    async def _compute_aged_payables(
        self,
        connection_id: UUID,
        as_of_date: date | None = None,
    ) -> dict[str, Any]:
        """Compute aged payables from synced ACCPAY invoices.

        Args:
            connection_id: The Xero connection ID.
            as_of_date: Date to calculate aging from. Defaults to today.

        Returns:
            Report data dict with summary and rows.
        """
        from sqlalchemy import and_, select

        from app.modules.integrations.xero.models import (
            XeroClient,
            XeroInvoice,
            XeroInvoiceStatus,
            XeroInvoiceType,
        )

        if as_of_date is None:
            as_of_date = date.today()

        # Query unpaid payables (ACCPAY + AUTHORISED status)
        query = select(XeroInvoice).where(
            and_(
                XeroInvoice.connection_id == connection_id,
                XeroInvoice.invoice_type == XeroInvoiceType.ACCPAY,
                XeroInvoice.status == XeroInvoiceStatus.AUTHORISED,
            )
        )
        result = await self.session.execute(query)
        invoices = result.scalars().all()

        # Get contact names for display
        contact_ids = list({inv.xero_contact_id for inv in invoices if inv.xero_contact_id})
        contact_names: dict[str, str] = {}
        if contact_ids:
            contact_query = select(XeroClient.xero_contact_id, XeroClient.name).where(
                and_(
                    XeroClient.connection_id == connection_id,
                    XeroClient.xero_contact_id.in_(contact_ids),
                )
            )
            contact_result = await self.session.execute(contact_query)
            contact_names = {row[0]: row[1] for row in contact_result.fetchall()}

        # Calculate aging buckets
        current = Decimal("0.00")
        overdue_30 = Decimal("0.00")
        overdue_60 = Decimal("0.00")
        overdue_90 = Decimal("0.00")
        overdue_90_plus = Decimal("0.00")

        rows = []
        for inv in invoices:
            amount = inv.total_amount or Decimal("0.00")
            due_date = inv.due_date.date() if inv.due_date else inv.issue_date.date()
            days_overdue = (as_of_date - due_date).days

            # Assign to bucket
            if days_overdue <= 0:
                current += amount
                bucket = "Current"
            elif days_overdue <= 30:
                overdue_30 += amount
                bucket = "1-30 Days"
            elif days_overdue <= 60:
                overdue_60 += amount
                bucket = "31-60 Days"
            elif days_overdue <= 90:
                overdue_90 += amount
                bucket = "61-90 Days"
            else:
                overdue_90_plus += amount
                bucket = "90+ Days"

            # Add row for display
            contact_name = contact_names.get(inv.xero_contact_id, inv.xero_contact_id or "Unknown")
            rows.append(
                {
                    "row_type": "Row",
                    "cells": [
                        {"value": inv.invoice_number or inv.xero_invoice_id, "attributes": []},
                        {"value": contact_name, "attributes": []},
                        {"value": str(due_date), "attributes": []},
                        {"value": f"${float(amount):,.2f}", "attributes": []},
                        {"value": bucket, "attributes": []},
                    ],
                }
            )

        total = current + overdue_30 + overdue_60 + overdue_90 + overdue_90_plus
        overdue_total = overdue_30 + overdue_60 + overdue_90 + overdue_90_plus

        summary = {
            "total": float(total),
            "current": float(current),
            "overdue_30": float(overdue_30),
            "overdue_60": float(overdue_60),
            "overdue_90": float(overdue_90),
            "overdue_90_plus": float(overdue_90_plus),
            "overdue_total": float(overdue_total),
        }

        # Add header row
        header_row = {
            "row_type": "Header",
            "cells": [
                {"value": "Invoice", "attributes": []},
                {"value": "Supplier", "attributes": []},
                {"value": "Due Date", "attributes": []},
                {"value": "Amount", "attributes": []},
                {"value": "Aging", "attributes": []},
            ],
        }

        import uuid as uuid_module

        return {
            "id": str(uuid_module.uuid4()),
            "report_type": "aged_payables_by_contact",
            "report_name": "Aged Payables",
            "report_titles": [f"As of {as_of_date}"],
            "period_key": str(as_of_date),
            "period_start": None,
            "period_end": str(as_of_date),
            "as_of_date": str(as_of_date),
            "summary": summary,
            "rows": [header_row] + rows,
            "fetched_at": datetime.now(UTC).isoformat(),
            "cache_expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            "is_current_period": True,
            "is_stale": False,
        }


# =============================================================================
# Payment Analysis Service (Spec 024 - User Story 4)
# =============================================================================


class PaymentAnalysisService:
    """Service for payment analysis and cash flow insights.

    Spec 024: Credit Notes, Payments & Journals - User Story 4
    Provides payment analytics for AI agent context.

    Attributes:
        session: SQLAlchemy async session.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the payment analysis service.

        Args:
            session: SQLAlchemy async session.
        """
        self.session = session
        self.payment_repo = XeroPaymentRepository(session)
        self.invoice_repo = XeroInvoiceRepository(session)

    async def calculate_average_days_to_pay(
        self,
        connection_id: UUID,
        xero_contact_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict[str, Any]:
        """Calculate average days to pay for invoices.

        For each paid invoice, calculates the number of days between
        invoice issue date and payment date. Returns aggregate statistics.

        Args:
            connection_id: The Xero connection ID.
            xero_contact_id: Optional contact to filter by.
            date_from: Optional start date filter.
            date_to: Optional end date filter.

        Returns:
            Dictionary with:
            - average_days: Average days to pay
            - median_days: Median days to pay
            - min_days: Minimum days to pay
            - max_days: Maximum days to pay
            - sample_size: Number of invoices analyzed
            - payment_patterns: List of (invoice_date, payment_date, days) tuples
        """
        # Get paid invoices with payments
        invoices, _ = await self.invoice_repo.list_by_connection(
            connection_id=connection_id,
            xero_contact_id=xero_contact_id,
            status="PAID",
            date_from=date_from.date() if date_from else None,
            date_to=date_to.date() if date_to else None,
            limit=500,  # Reasonable limit for analysis
        )

        if not invoices:
            return {
                "average_days": None,
                "median_days": None,
                "min_days": None,
                "max_days": None,
                "sample_size": 0,
                "payment_patterns": [],
            }

        # Calculate days to pay for each invoice
        days_list: list[int] = []
        payment_patterns: list[dict[str, Any]] = []

        for invoice in invoices:
            if invoice.fully_paid_on_date and invoice.issue_date:
                days = (invoice.fully_paid_on_date - invoice.issue_date).days
                if days >= 0:  # Only include valid positive values
                    days_list.append(days)
                    payment_patterns.append(
                        {
                            "invoice_date": invoice.issue_date.isoformat(),
                            "payment_date": invoice.fully_paid_on_date.isoformat(),
                            "days_to_pay": days,
                            "amount": float(invoice.total_amount),
                        }
                    )

        if not days_list:
            return {
                "average_days": None,
                "median_days": None,
                "min_days": None,
                "max_days": None,
                "sample_size": 0,
                "payment_patterns": [],
            }

        # Calculate statistics
        sorted_days = sorted(days_list)
        average_days = sum(days_list) / len(days_list)
        median_days = sorted_days[len(sorted_days) // 2]

        return {
            "average_days": round(average_days, 1),
            "median_days": median_days,
            "min_days": min(days_list),
            "max_days": max(days_list),
            "sample_size": len(days_list),
            "payment_patterns": payment_patterns[:20],  # Return top 20 for context
        }

    async def get_cash_flow_summary(
        self,
        connection_id: UUID,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict[str, Any]:
        """Get cash flow summary for a connection.

        Analyzes incoming and outgoing payments to provide
        cash flow insights for AI agents.

        Args:
            connection_id: The Xero connection ID.
            date_from: Optional start date filter.
            date_to: Optional end date filter.

        Returns:
            Dictionary with cash flow summary data.
        """
        # Get payment statistics
        payment_stats = await self.payment_repo.get_payment_stats_by_connection(
            connection_id=connection_id,
            date_from=date_from,
            date_to=date_to,
        )

        # Get average days to pay for receivables
        receivables_analysis = await self.calculate_average_days_to_pay(
            connection_id=connection_id,
            date_from=date_from,
            date_to=date_to,
        )

        return {
            "period": {
                "from": date_from.isoformat() if date_from else None,
                "to": date_to.isoformat() if date_to else None,
            },
            "payments": {
                "total_count": payment_stats["payment_count"],
                "total_amount": float(payment_stats["total_amount"]),
                "average_amount": float(payment_stats["average_amount"]),
                "earliest": payment_stats["earliest_payment"].isoformat()
                if payment_stats["earliest_payment"]
                else None,
                "latest": payment_stats["latest_payment"].isoformat()
                if payment_stats["latest_payment"]
                else None,
            },
            "receivables": {
                "average_days_to_collect": receivables_analysis["average_days"],
                "median_days_to_collect": receivables_analysis["median_days"],
                "sample_size": receivables_analysis["sample_size"],
            },
        }

    async def identify_payment_patterns(
        self,
        connection_id: UUID,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict[str, Any]:
        """Identify recurring payment patterns.

        Analyzes payment history to identify:
        - Regular payment schedules
        - Common payment amounts
        - Seasonal patterns

        Args:
            connection_id: The Xero connection ID.
            date_from: Optional start date filter.
            date_to: Optional end date filter.

        Returns:
            Dictionary with identified payment patterns.
        """
        payments, _ = await self.payment_repo.list_by_connection(
            connection_id=connection_id,
            date_from=date_from,
            date_to=date_to,
            limit=200,
        )

        if not payments:
            return {
                "recurring_amounts": [],
                "payment_frequency": None,
                "common_days_of_month": [],
            }

        # Analyze payment amounts for recurring patterns
        amount_counts: dict[Decimal, int] = {}
        day_of_month_counts: dict[int, int] = {}

        for payment in payments:
            # Round amount to nearest dollar for pattern matching
            rounded_amount = round(payment.amount)
            amount_counts[rounded_amount] = amount_counts.get(rounded_amount, 0) + 1

            # Track day of month
            day = payment.payment_date.day
            day_of_month_counts[day] = day_of_month_counts.get(day, 0) + 1

        # Find recurring amounts (appear 3+ times)
        recurring_amounts = [
            {"amount": float(amount), "occurrences": count}
            for amount, count in sorted(amount_counts.items(), key=lambda x: x[1], reverse=True)
            if count >= 3
        ][:10]  # Top 10

        # Find common days of month
        common_days = [
            {"day": day, "occurrences": count}
            for day, count in sorted(day_of_month_counts.items(), key=lambda x: x[1], reverse=True)
        ][:5]  # Top 5

        # Calculate average payment frequency
        if len(payments) >= 2:
            dates = sorted([p.payment_date for p in payments])
            intervals = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
            avg_interval = sum(intervals) / len(intervals) if intervals else None
        else:
            avg_interval = None

        return {
            "recurring_amounts": recurring_amounts,
            "average_days_between_payments": round(avg_interval, 1) if avg_interval else None,
            "common_days_of_month": common_days,
            "total_payments_analyzed": len(payments),
        }


# =============================================================================
# Bulk Import Exceptions
# =============================================================================


class BulkImportInProgressError(Exception):
    """Raised when a bulk import is already in progress for the tenant."""

    def __init__(self, tenant_id: UUID, job_id: UUID):
        self.tenant_id = tenant_id
        self.job_id = job_id
        super().__init__(
            f"A bulk import is already in progress for tenant {tenant_id} (job {job_id})"
        )


class BulkImportValidationError(Exception):
    """Raised when bulk import validation fails."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


# =============================================================================
# Bulk Import Service (Phase 035)
# =============================================================================


class BulkImportService:
    """Service for bulk importing multiple Xero client organizations.

    Handles the multi-org OAuth flow:
    1. initiate_bulk_import() - Generate auth URL with is_bulk_import=True
    2. handle_bulk_callback() - Process callback, return all authorized orgs
    3. confirm_bulk_import() - Create connections, BulkImportJob, queue sync
    """

    # Uncertified Xero app limit
    XERO_ORG_LIMIT = 25

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
    ) -> None:
        """Initialize bulk import service.

        Args:
            session: Database session.
            settings: Application settings.
        """
        from app.core.audit import AuditService
        from app.modules.onboarding.repository import (
            BulkImportJobRepository,
            BulkImportOrganizationRepository,
        )

        self.session = session
        self.settings = settings
        self.state_repo = XeroOAuthStateRepository(session)
        self.connection_repo = XeroConnectionRepository(session)
        self.encryption = TokenEncryption(settings.token_encryption.key.get_secret_value())
        self.job_repo = BulkImportJobRepository(session)
        self.org_repo = BulkImportOrganizationRepository(session)
        self.audit_service = AuditService(session)
        self.logger = logging.getLogger(__name__)

    async def initiate_bulk_import(
        self,
        tenant_id: UUID,
        user_id: UUID,
        redirect_uri: str,
    ) -> dict[str, str]:
        """Initiate a bulk import OAuth flow.

        Checks for concurrent imports, creates OAuth state with is_bulk_import=True,
        and generates the Xero authorization URL.

        Args:
            tenant_id: The tenant (accounting practice) ID.
            user_id: The user initiating the import.
            redirect_uri: Frontend URL to redirect back to after OAuth.

        Returns:
            Dict with auth_url and state token.

        Raises:
            BulkImportInProgressError: If a bulk import is already in progress.
        """
        from app.modules.onboarding.models import BulkImportJobStatus

        # Check for concurrent bulk import (FR-017)
        active_jobs = await self.job_repo.list_by_tenant(
            tenant_id, status=BulkImportJobStatus.IN_PROGRESS
        )
        if active_jobs:
            raise BulkImportInProgressError(tenant_id, active_jobs[0].id)

        # Also check PENDING jobs (queued but not yet started)
        pending_jobs = await self.job_repo.list_by_tenant(
            tenant_id, status=BulkImportJobStatus.PENDING
        )
        # Only block on pending jobs that are xero_bulk_oauth source type
        pending_bulk = [j for j in pending_jobs if j.source_type == "xero_bulk_oauth"]
        if pending_bulk:
            raise BulkImportInProgressError(tenant_id, pending_bulk[0].id)

        # Generate PKCE parameters
        code_verifier = generate_code_verifier()
        code_challenge = generate_code_challenge(code_verifier)
        state = generate_state()

        # Store state for callback validation with bulk import flag
        expires_at = datetime.now(UTC) + timedelta(minutes=10)
        await self.state_repo.create(
            tenant_id=tenant_id,
            user_id=user_id,
            state=state,
            code_verifier=code_verifier,
            redirect_uri=redirect_uri,
            expires_at=expires_at,
            is_bulk_import=True,
        )

        # Build authorization URL
        auth_url = build_authorization_url(
            settings=self.settings.xero,
            state=state,
            code_challenge=code_challenge,
            redirect_uri=self.settings.xero.redirect_uri,
        )

        # Audit event
        await self.audit_service.log_event(
            event_type="integration.xero.bulk_import.start",
            event_category="integration",
            resource_type="bulk_import",
            resource_id=tenant_id,
            action="create",
            outcome="success",
            tenant_id=tenant_id,
            new_values={"user_id": str(user_id), "redirect_uri": redirect_uri},
        )

        self.logger.info(
            "Bulk import OAuth initiated",
            extra={"tenant_id": str(tenant_id), "user_id": str(user_id)},
        )

        return {"auth_url": auth_url, "state": state}

    async def handle_bulk_callback(
        self,
        code: str,
        state: str,
    ) -> dict[str, Any]:
        """Handle OAuth callback for bulk import.

        Validates state, exchanges code for tokens, fetches all authorized orgs,
        identifies new vs already-connected, and returns the list for configuration.
        Does NOT create connections yet - that happens on confirm.

        Args:
            code: Authorization code from Xero.
            state: State parameter for CSRF validation.

        Returns:
            Dict with auth_event_id, organizations, counts, and plan limits.

        Raises:
            XeroOAuthError: If state is invalid or token exchange fails.
        """
        from app.core.feature_flags import get_client_limit
        from app.modules.integrations.xero.schemas import ImportOrganization

        # Validate state
        oauth_state = await self.state_repo.get_by_state(state)
        if oauth_state is None:
            raise XeroOAuthError("Invalid or unknown state parameter")

        if not oauth_state.is_valid:
            if oauth_state.is_expired:
                raise XeroOAuthError("Authorization expired, please try again")
            if oauth_state.is_used:
                raise XeroOAuthError("Authorization already completed")
            raise XeroOAuthError("Invalid state")

        # Verify this is a bulk import flow
        if not oauth_state.is_bulk_import:
            raise XeroOAuthError("State is not for bulk import flow")

        # Mark state as used
        await self.state_repo.mark_as_used(oauth_state.id)

        # Exchange code for tokens
        async with XeroClient(self.settings.xero) as client:
            token_response, token_expires_at = await client.exchange_code(
                code=code,
                code_verifier=oauth_state.code_verifier,
                redirect_uri=self.settings.xero.redirect_uri,
            )

            # Get ALL connected organizations
            all_orgs = await client.get_connections(token_response.access_token)

        if not all_orgs:
            raise XeroOAuthError("No organizations authorized")

        # Store tokens temporarily for use during confirm step
        # We encrypt and store on the OAuth state record for retrieval
        encrypted_access = self.encryption.encrypt(token_response.access_token)
        encrypted_refresh = self.encryption.encrypt(token_response.refresh_token)

        # Filter to orgs from this auth event (FR-002)
        # If auth_event_id is available, use it; otherwise include all
        auth_event_id = None
        if all_orgs[0].auth_event_id:
            auth_event_id = all_orgs[0].auth_event_id

        # Get existing connections for this tenant
        existing_connections = await self.connection_repo.list_by_tenant(
            tenant_id=oauth_state.tenant_id,
            include_disconnected=False,
        )
        existing_xero_ids = {conn.xero_tenant_id: conn for conn in existing_connections}

        # Build organization list with already_connected status
        organizations: list[ImportOrganization] = []
        already_connected_count = 0
        new_count = 0

        for org in all_orgs:
            existing_conn = existing_xero_ids.get(org.id)
            is_connected = existing_conn is not None
            if is_connected:
                already_connected_count += 1
            else:
                new_count += 1

            organizations.append(
                ImportOrganization(
                    xero_tenant_id=org.id,
                    organization_name=org.display_name,
                    already_connected=is_connected,
                    existing_connection_id=existing_conn.id if existing_conn else None,
                )
            )

        # Check subscription tier limit (FR-006)
        from sqlalchemy import select as sa_select

        tenant = await self.session.scalar(
            sa_select(Tenant).where(Tenant.id == oauth_state.tenant_id)
        )

        plan_limit = 0
        current_client_count = 0
        available_slots = 0
        if tenant:
            tier_value: str = tenant.tier.value  # type: ignore[assignment]
            limit = get_client_limit(tier_value)
            plan_limit = limit if limit is not None else 999999
            current_client_count = tenant.client_count
            available_slots = (
                max(0, plan_limit - current_client_count) if limit is not None else 999999
            )

        # Check uncertified app limit (FR-007)
        total_orgs = len(all_orgs)
        if total_orgs > self.XERO_ORG_LIMIT:
            self.logger.warning(
                "Bulk import: org count exceeds uncertified app limit",
                extra={
                    "tenant_id": str(oauth_state.tenant_id),
                    "org_count": total_orgs,
                    "limit": self.XERO_ORG_LIMIT,
                },
            )

        # Store encrypted tokens on the state for retrieval during confirm
        # Using the state record's redirect_uri field is insufficient,
        # so we store tokens in a temporary approach via session state
        # We'll store the tokens keyed by auth_event_id for confirm step
        from app.modules.integrations.xero.models import XeroOAuthState

        oauth_state_record = await self.session.get(XeroOAuthState, oauth_state.id)
        if oauth_state_record:
            # Store encrypted tokens in the redirect_uri field as JSON
            # (This field is no longer needed after callback)
            import json

            token_data = json.dumps(
                {
                    "access_token": encrypted_access,
                    "refresh_token": encrypted_refresh,
                    "token_expires_at": token_expires_at.isoformat(),
                    "scopes": token_response.scopes_list,
                }
            )
            oauth_state_record.redirect_uri = token_data

        # Audit event
        await self.audit_service.log_event(
            event_type="integration.xero.oauth.multi_org",
            event_category="integration",
            resource_type="bulk_import",
            resource_id=oauth_state.tenant_id,
            action="read",
            outcome="success",
            tenant_id=oauth_state.tenant_id,
            new_values={
                "auth_event_id": auth_event_id,
                "total_orgs": total_orgs,
                "new_count": new_count,
                "already_connected_count": already_connected_count,
            },
        )

        self.logger.info(
            "Bulk import callback processed",
            extra={
                "tenant_id": str(oauth_state.tenant_id),
                "auth_event_id": auth_event_id,
                "total_orgs": total_orgs,
                "new_orgs": new_count,
                "already_connected": already_connected_count,
            },
        )

        # Auto-match organizations to existing clients (T025 - US4)
        org_dicts = [org.model_dump() for org in organizations]
        org_dicts = await self.match_orgs_to_clients(
            tenant_id=oauth_state.tenant_id,
            organizations=org_dicts,
        )

        return {
            "auth_event_id": auth_event_id or "",
            "organizations": org_dicts,
            "already_connected_count": already_connected_count,
            "new_count": new_count,
            "plan_limit": plan_limit,
            "current_client_count": current_client_count,
            "available_slots": available_slots,
            "state": state,  # Needed by confirm to retrieve tokens
        }

    async def confirm_bulk_import(
        self,
        tenant_id: UUID,
        user_id: UUID,
        state: str,
        auth_event_id: str,
        organizations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Confirm selected organizations and start bulk import.

        Creates XeroConnection records for selected orgs, creates a BulkImportJob,
        creates BulkImportOrganization records, and queues Celery sync tasks.

        Args:
            tenant_id: The tenant ID.
            user_id: The user confirming the import.
            state: OAuth state token (used to retrieve stored tokens).
            auth_event_id: Authorization event ID grouping the orgs.
            organizations: List of org selections with configuration.

        Returns:
            Dict with job details.

        Raises:
            BulkImportInProgressError: If import already in progress.
            BulkImportValidationError: If validation fails.
            XeroOAuthError: If tokens cannot be retrieved.
        """
        from app.core.feature_flags import get_client_limit
        from app.modules.onboarding.models import (
            BulkImportJob,
            BulkImportJobStatus,
        )

        # Check for concurrent bulk import (FR-017)
        active_jobs = await self.job_repo.list_by_tenant(
            tenant_id, status=BulkImportJobStatus.IN_PROGRESS
        )
        if active_jobs:
            raise BulkImportInProgressError(tenant_id, active_jobs[0].id)

        # Retrieve stored tokens from the OAuth state
        import json

        oauth_state = await self.state_repo.get_by_state(state)
        if oauth_state is None:
            raise XeroOAuthError("OAuth state not found - session may have expired")

        try:
            token_data = json.loads(oauth_state.redirect_uri)
            encrypted_access = token_data["access_token"]
            encrypted_refresh = token_data["refresh_token"]
            token_expires_at = datetime.fromisoformat(token_data["token_expires_at"])
            scopes = token_data.get("scopes", [])
        except (json.JSONDecodeError, KeyError) as e:
            raise XeroOAuthError(f"Failed to retrieve stored tokens: {e}") from e

        # Separate selected vs deselected orgs
        selected_orgs = [o for o in organizations if o.get("selected", False)]
        deselected_orgs = [o for o in organizations if not o.get("selected", False)]

        if not selected_orgs:
            raise BulkImportValidationError("No organizations selected for import")

        # Check subscription tier limit (FR-006)
        from sqlalchemy import select as sa_select

        tenant = await self.session.scalar(sa_select(Tenant).where(Tenant.id == tenant_id))

        if tenant:
            tier_value: str = tenant.tier.value  # type: ignore[assignment]
            limit = get_client_limit(tier_value)
            if limit is not None:
                available = max(0, limit - tenant.client_count)
                # Count only genuinely new orgs (not already connected)
                new_selected = [o for o in selected_orgs if not o.get("already_connected", False)]
                if len(new_selected) > available:
                    raise BulkImportValidationError(
                        f"Selection exceeds plan limit. "
                        f"Available slots: {available}, selected: {len(new_selected)}. "
                        f"Please deselect some organizations or upgrade your plan."
                    )

        # Check payroll scopes
        payroll_scopes = ["payroll.employees", "payroll.payruns"]
        has_payroll = all(scope in scopes for scope in payroll_scopes)

        # Create XeroConnections for each selected NEW org
        created_connections: dict[str, XeroConnection] = {}
        for org_selection in selected_orgs:
            xero_tenant_id = org_selection["xero_tenant_id"]

            # Skip already-connected orgs
            if org_selection.get("already_connected", False):
                continue

            connection_type = org_selection.get("connection_type", "client")

            # Create XeroConnection with shared tokens
            connection = await self.connection_repo.create(
                XeroConnectionCreate(
                    tenant_id=tenant_id,
                    xero_tenant_id=xero_tenant_id,
                    organization_name=org_selection.get(
                        "organization_name", f"Org {xero_tenant_id[:8]}"
                    ),
                    access_token=encrypted_access,
                    refresh_token=encrypted_refresh,
                    token_expires_at=token_expires_at,
                    scopes=scopes,
                    connected_by=user_id,
                    has_payroll_access=has_payroll,
                    auth_event_id=auth_event_id,
                )
            )

            # Set connection_type if not the default
            if connection_type != "client":
                from sqlalchemy import text

                await self.session.execute(
                    text("""
                    UPDATE xero_connections
                    SET connection_type = :connection_type
                    WHERE id = :connection_id
                    """),
                    {
                        "connection_type": connection_type,
                        "connection_id": connection.id,
                    },
                )

            created_connections[xero_tenant_id] = connection

            # Audit per-connection creation
            await self.audit_service.log_event(
                event_type="integration.xero.connection.created",
                event_category="integration",
                resource_type="xero_connection",
                resource_id=connection.id,
                action="create",
                outcome="success",
                tenant_id=tenant_id,
                new_values={
                    "xero_tenant_id": xero_tenant_id,
                    "organization_name": org_selection.get("organization_name", ""),
                    "connection_type": connection_type,
                    "auth_event_id": auth_event_id,
                    "bulk_import": True,
                },
            )

        # Create BulkImportJob
        all_client_ids = [o["xero_tenant_id"] for o in selected_orgs]
        job = BulkImportJob(
            tenant_id=tenant_id,
            status=BulkImportJobStatus.PENDING,
            source_type="xero_bulk_oauth",
            total_clients=len(selected_orgs),
            client_ids=all_client_ids,
        )
        job = await self.job_repo.create(job)

        # Create BulkImportOrganization records for ALL orgs (selected + deselected)
        org_records: list[dict[str, Any]] = []

        for org_selection in selected_orgs:
            xero_tenant_id = org_selection["xero_tenant_id"]
            is_already_connected = org_selection.get("already_connected", False)
            conn = created_connections.get(xero_tenant_id)

            status = "pending"
            if is_already_connected:
                status = "skipped"

            org_records.append(
                {
                    "tenant_id": tenant_id,
                    "bulk_import_job_id": job.id,
                    "xero_tenant_id": xero_tenant_id,
                    "organization_name": org_selection.get(
                        "organization_name", f"Org {xero_tenant_id[:8]}"
                    ),
                    "status": status,
                    "connection_id": conn.id if conn else None,
                    "connection_type": org_selection.get("connection_type", "client"),
                    "assigned_user_id": (
                        UUID(org_selection["assigned_user_id"])
                        if org_selection.get("assigned_user_id")
                        else None
                    ),
                    "already_connected": is_already_connected,
                    "selected_for_import": True,
                }
            )

        for org_selection in deselected_orgs:
            org_records.append(
                {
                    "tenant_id": tenant_id,
                    "bulk_import_job_id": job.id,
                    "xero_tenant_id": org_selection["xero_tenant_id"],
                    "organization_name": org_selection.get(
                        "organization_name", f"Org {org_selection['xero_tenant_id'][:8]}"
                    ),
                    "status": "skipped",
                    "connection_type": org_selection.get("connection_type", "client"),
                    "already_connected": org_selection.get("already_connected", False),
                    "selected_for_import": False,
                }
            )

        if org_records:
            await self.org_repo.bulk_create(org_records)

        # Calculate counts
        skipped = len([o for o in org_records if o["status"] == "skipped"])

        self.logger.info(
            "Bulk import confirmed",
            extra={
                "tenant_id": str(tenant_id),
                "job_id": str(job.id),
                "selected_count": len(selected_orgs),
                "deselected_count": len(deselected_orgs),
                "connections_created": len(created_connections),
            },
        )

        # Queue Celery task for bulk sync (T020)
        from app.tasks.celery_app import celery_app

        celery_app.send_task(
            "app.tasks.xero.run_bulk_xero_import",
            kwargs={
                "job_id": str(job.id),
                "tenant_id": str(tenant_id),
            },
        )

        return {
            "job_id": job.id,
            "status": job.status.value,
            "total_organizations": job.total_clients,
            "imported_count": 0,
            "failed_count": 0,
            "skipped_count": skipped,
            "progress_percent": 0,
            "created_at": job.created_at,
        }

    # =========================================================================
    # App-Wide Rate Limit (T021)
    # =========================================================================

    @staticmethod
    async def check_app_rate_limit() -> bool:
        """Check if app-wide Xero rate limit allows more requests.

        Uses Redis counter for the current minute window.

        Returns:
            True if requests can proceed, False if rate limited.
        """
        try:
            import redis.asyncio as aioredis

            from app.config import get_settings

            settings = get_settings()
            client = aioredis.from_url(settings.redis.url)

            minute_key = f"xero:app_rate_limit:{int(datetime.now(UTC).timestamp()) // 60}"
            remaining = await client.get(minute_key)
            await client.aclose()

            if remaining is not None and int(remaining) < 500:
                return False
            return True
        except Exception:
            # If Redis is unavailable, allow requests (fail open)
            return True

    @staticmethod
    async def update_app_rate_limit(remaining: int) -> None:
        """Update the app-wide rate limit counter from Xero response header.

        Args:
            remaining: Value from X-AppMinLimit-Remaining header.
        """
        try:
            import redis.asyncio as aioredis

            from app.config import get_settings

            settings = get_settings()
            client = aioredis.from_url(settings.redis.url)

            minute_key = f"xero:app_rate_limit:{int(datetime.now(UTC).timestamp()) // 60}"
            await client.set(minute_key, remaining, ex=60)
            await client.aclose()
        except Exception:
            pass  # Best-effort

    # =========================================================================
    # Auto-Matching (T025 - US4)
    # =========================================================================

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Normalize organization name for matching.

        Strips common suffixes like "Pty Ltd", "Pty", "Ltd" and normalizes
        whitespace and case.
        """
        import re

        normalized = name.lower().strip()
        # Remove common Australian business suffixes
        for suffix in ["pty ltd", "pty. ltd.", "pty. ltd", "pty ltd.", "limited", "pty", "ltd"]:
            if normalized.endswith(suffix):
                normalized = normalized[: -len(suffix)].strip()
        # Remove extra whitespace
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    @staticmethod
    def _jaccard_similarity(name_a: str, name_b: str) -> float:
        """Calculate Jaccard similarity between two names based on word tokens."""
        tokens_a = set(name_a.lower().split())
        tokens_b = set(name_b.lower().split())
        if not tokens_a or not tokens_b:
            return 0.0
        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        return len(intersection) / len(union) if union else 0.0

    async def match_orgs_to_clients(
        self,
        tenant_id: UUID,
        organizations: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Match imported Xero organizations against existing client records.

        Two-pass matching (R6):
        1. Exact match on normalized names
        2. Fuzzy match with Jaccard similarity > 0.8

        Args:
            tenant_id: The tenant ID.
            organizations: List of org dicts with xero_tenant_id and organization_name.

        Returns:
            Updated list with match_status and matched_client_name fields set.
        """
        # Get existing connections (which represent connected client businesses)
        existing_connections = await self.connection_repo.list_by_tenant(
            tenant_id=tenant_id,
            include_disconnected=False,
        )

        # Build normalized name lookup
        existing_names: dict[str, str] = {}  # normalized_name -> original_name
        for conn in existing_connections:
            if conn.organization_name:
                norm = self._normalize_name(conn.organization_name)
                existing_names[norm] = conn.organization_name

        for org in organizations:
            org_name = org.get("organization_name", "")
            norm_org = self._normalize_name(org_name)

            # Pass 1: Exact match
            if norm_org in existing_names:
                org["match_status"] = "matched"
                org["matched_client_name"] = existing_names[norm_org]
                continue

            # Pass 2: Fuzzy match
            best_score = 0.0
            best_match = None
            for norm_existing, original_name in existing_names.items():
                score = self._jaccard_similarity(norm_org, norm_existing)
                if score > best_score:
                    best_score = score
                    best_match = original_name

            if best_score >= 0.8 and best_match:
                org["match_status"] = "suggested"
                org["matched_client_name"] = best_match
            else:
                org["match_status"] = "unmatched"
                org["matched_client_name"] = None

        return organizations
