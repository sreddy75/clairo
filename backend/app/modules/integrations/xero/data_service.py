"""Xero data sync service — fetches and upserts all entity types from Xero API."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.modules.integrations.xero.client import XeroClient
from app.modules.integrations.xero.encryption import TokenEncryption
from app.modules.integrations.xero.models import XeroConnection, XeroConnectionStatus
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
    XeroOverpaymentRepository,
    XeroPaymentRepository,
    XeroPrepaymentRepository,
)
from app.modules.integrations.xero.schemas import SyncResult, XeroConnectionUpdate
from app.modules.integrations.xero.transformers import (
    AccountTransformer,
    AssetTransformer,
    AssetTypeTransformer,
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
)

logger = logging.getLogger(__name__)


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
