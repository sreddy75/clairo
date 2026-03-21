# Requirements Document: Xero Data Sync

## Introduction

This document defines the requirements for synchronizing data from connected Xero organizations to Clairo. Building upon the completed Xero OAuth integration (Spec 003), this feature enables accountants to pull client contacts, invoices, bank transactions, and BAS-relevant financial data from Xero into Clairo for processing and analysis.

The Xero Data Sync feature is a core component of Layer 1 (Core BAS Platform) and directly supports Milestone M1 (Single Client View). It establishes the foundation for Pillar 1 (Client Data) of the Clairo three-pillar architecture by ingesting real-time and historical financial data from Xero.

**Key Context:**
- Xero OAuth connections are already established (Spec 003 complete)
- XeroConnection model exists with encrypted OAuth tokens and rate limit tracking
- Rate limits: 60 calls/minute, 5000 calls/day per tenant
- Multi-tenant architecture with RLS (Row-Level Security) enforced
- Background task processing via Celery + Redis

---

## Requirements

### Requirement 1: Contact Synchronization

**User Story:** As an accountant, I want to sync Xero contacts to Clairo as clients, so that I can manage all my clients in one place without manual data entry.

#### Acceptance Criteria

1. WHEN a user initiates a contact sync for a Xero connection THEN the system SHALL retrieve all contacts from the connected Xero organization via the Xero Contacts API.

2. WHEN a Xero contact is retrieved THEN the system SHALL map the following Xero fields to Clairo client fields:
   - ContactID -> xero_contact_id (reference identifier)
   - Name -> name
   - EmailAddress -> email
   - ContactNumber -> contact_number
   - ABN (from TaxNumber) -> abn
   - Addresses -> addresses (structured)
   - Phones -> phones (structured)
   - ContactStatus -> is_active (ACTIVE = true, ARCHIVED = false)
   - IsCustomer/IsSupplier -> contact_type (enum: CUSTOMER, SUPPLIER, BOTH)
   - UpdatedDateUTC -> xero_updated_at

3. IF a contact with the same xero_contact_id already exists for the tenant THEN the system SHALL update the existing client record with the latest Xero data.

4. IF a contact is new (no matching xero_contact_id) THEN the system SHALL create a new client record linked to the Xero connection.

5. WHEN syncing contacts IF the contact status in Xero is ARCHIVED THEN the system SHALL soft-delete the corresponding client record in Clairo (set is_active = false).

6. WHEN contact sync completes THEN the system SHALL record audit events for all created, updated, and archived client records.

7. WHEN syncing contacts THEN the system SHALL validate ABN format (11 digits) and store only valid ABNs, logging warnings for invalid formats.

---

### Requirement 2: Invoice Synchronization

**User Story:** As an accountant, I want to sync invoices from Xero, so that I can review my clients' financial activity and prepare accurate BAS statements.

#### Acceptance Criteria

1. WHEN a user initiates an invoice sync for a Xero connection THEN the system SHALL retrieve invoices from the Xero Invoices API.

2. WHEN an invoice is retrieved THEN the system SHALL map the following Xero fields to Clairo invoice fields:
   - InvoiceID -> xero_invoice_id
   - InvoiceNumber -> invoice_number
   - Type -> invoice_type (ACCREC = sales, ACCPAY = purchase)
   - Contact.ContactID -> client_id (via xero_contact_id lookup)
   - Status -> status
   - Date -> issue_date
   - DueDate -> due_date
   - SubTotal -> subtotal
   - TotalTax -> tax_amount
   - Total -> total_amount
   - CurrencyCode -> currency (default AUD)
   - LineItems -> line_items (structured JSON)
   - UpdatedDateUTC -> xero_updated_at

3. WHEN syncing invoice line items THEN the system SHALL capture the following BAS-relevant data for each line:
   - AccountCode -> account_code
   - TaxType -> tax_type (GST classification)
   - TaxAmount -> line_tax_amount
   - LineAmount -> line_amount

4. IF an invoice with the same xero_invoice_id already exists THEN the system SHALL update the existing record with the latest Xero data.

5. IF an invoice references a contact not yet synced to Clairo THEN the system SHALL queue the contact for sync before completing the invoice sync.

6. WHEN invoice sync completes THEN the system SHALL record audit events for all created and updated invoice records.

---

### Requirement 3: Bank Transaction Synchronization

**User Story:** As an accountant, I want to sync bank transactions from Xero, so that I can reconcile client accounts and identify BAS-relevant transactions.

#### Acceptance Criteria

1. WHEN a user initiates a bank transaction sync THEN the system SHALL retrieve transactions from the Xero Bank Transactions API.

2. WHEN a bank transaction is retrieved THEN the system SHALL map the following fields:
   - BankTransactionID -> xero_transaction_id
   - Type -> transaction_type (RECEIVE, SPEND, etc.)
   - Contact.ContactID -> client_id (if applicable)
   - BankAccount.AccountID -> bank_account_id
   - Date -> transaction_date
   - Reference -> reference
   - Status -> status
   - SubTotal -> subtotal
   - TotalTax -> tax_amount
   - Total -> total_amount
   - LineItems -> line_items (structured JSON with tax details)
   - UpdatedDateUTC -> xero_updated_at

3. WHEN syncing bank transaction line items THEN the system SHALL capture GST-relevant data:
   - AccountCode -> account_code
   - TaxType -> tax_type
   - TaxAmount -> line_tax_amount

4. IF a bank transaction with the same xero_transaction_id already exists THEN the system SHALL update the existing record.

5. WHEN bank transaction sync completes THEN the system SHALL record audit events for all synced transactions.

---

### Requirement 4: Account Balance Synchronization

**User Story:** As an accountant, I want to sync account balances from Xero, so that I can view current financial positions for my clients.

#### Acceptance Criteria

1. WHEN a user initiates an account sync THEN the system SHALL retrieve the chart of accounts from the Xero Accounts API.

2. WHEN an account is retrieved THEN the system SHALL map the following fields:
   - AccountID -> xero_account_id
   - Code -> account_code
   - Name -> account_name
   - Type -> account_type
   - Class -> account_class (ASSET, LIABILITY, EQUITY, REVENUE, EXPENSE)
   - TaxType -> default_tax_type
   - Status -> is_active
   - ReportingCode -> reporting_code (for BAS mapping)

3. WHEN syncing accounts THEN the system SHALL identify BAS-relevant accounts based on:
   - GST-related tax types (OUTPUT, INPUT, GSTONIMPORTS, etc.)
   - PAYG Withholding accounts
   - Superannuation liability accounts

4. IF an account with the same xero_account_id already exists THEN the system SHALL update the existing record.

5. WHEN account sync completes THEN the system SHALL record audit events for all account changes.

---

### Requirement 5: Background Sync Jobs (Celery)

**User Story:** As an accountant, I want data synchronization to happen in the background, so that I can continue working while large datasets are being synced.

#### Acceptance Criteria

1. WHEN a user initiates a sync operation THEN the system SHALL create a Celery background task and return immediately with a job ID.

2. WHEN a sync task is created THEN the system SHALL track the following job metadata:
   - job_id (UUID)
   - connection_id (Xero connection)
   - sync_type (contacts, invoices, transactions, accounts, full)
   - status (pending, in_progress, completed, failed)
   - started_at
   - completed_at
   - records_processed
   - records_created
   - records_updated
   - records_failed
   - error_message (if failed)

3. WHILE a sync job is in progress THEN the system SHALL update the job record with progress information at regular intervals.

4. IF a sync job fails THEN the system SHALL:
   - Record the error details in the job record
   - Emit an audit event for the failure
   - NOT retry automatically (user must manually retry)

5. WHEN a sync job completes successfully THEN the system SHALL:
   - Update the job status to completed
   - Record the completion timestamp
   - Emit an audit event for successful completion
   - Update the last_sync_at timestamp on the Xero connection

6. WHEN querying sync job status THEN the system SHALL return the current job state including progress metrics.

7. IF multiple sync jobs are requested for the same connection THEN the system SHALL queue them sequentially to prevent conflicts.

---

### Requirement 6: Incremental Sync

**User Story:** As an accountant, I want subsequent syncs to only fetch changed data, so that sync operations are fast and efficient.

#### Acceptance Criteria

1. WHEN a sync operation is initiated THEN the system SHALL check the last successful sync timestamp for the entity type and connection.

2. IF a previous successful sync exists THEN the system SHALL use Xero's "If-Modified-Since" header or "where" parameter with UpdatedDateUTC to fetch only records modified since the last sync.

3. IF no previous sync exists THEN the system SHALL perform a full sync of all records.

4. WHEN storing sync timestamps THEN the system SHALL track the following per connection:
   - last_contacts_sync_at
   - last_invoices_sync_at
   - last_transactions_sync_at
   - last_accounts_sync_at
   - last_full_sync_at

5. WHEN a full sync is requested THEN the system SHALL ignore previous timestamps and fetch all records, then update all sync timestamps.

6. IF an incremental sync fails THEN the system SHALL NOT update the sync timestamp, ensuring the next sync will retry the same time range.

7. WHEN using incremental sync THEN the system SHALL also detect and handle deleted records by comparing Xero's current record set with stored records.

---

### Requirement 7: Rate Limit Management

**User Story:** As an accountant, I want the sync process to respect Xero's rate limits, so that my connection is not throttled or blocked.

#### Acceptance Criteria

1. WHILE making Xero API calls THEN the system SHALL read rate limit headers from each response:
   - X-Rate-Limit-Problem (if 429 received)
   - Retry-After (seconds to wait)
   - X-MinLimit-Remaining (minute limit)
   - X-DayLimit-Remaining (daily limit)

2. WHEN rate limit headers are received THEN the system SHALL update the XeroConnection record with:
   - rate_limit_minute_remaining
   - rate_limit_daily_remaining
   - rate_limit_reset_at

3. IF the minute limit (60/min) is approaching exhaustion (< 5 remaining) THEN the system SHALL pause the sync job until the minute limit resets.

4. IF the daily limit (5000/day) is approaching exhaustion (< 100 remaining) THEN the system SHALL:
   - Pause non-critical sync operations
   - Emit a warning audit event
   - Notify the user that sync is rate-limited

5. IF a 429 (Too Many Requests) response is received THEN the system SHALL:
   - Parse the Retry-After header
   - Wait the specified duration
   - Retry the request (max 3 retries)
   - If retries exhausted, fail the sync job with rate limit error

6. WHEN planning sync operations THEN the system SHALL estimate API calls required and check against remaining limits before starting.

---

### Requirement 8: Sync Status Visibility

**User Story:** As an accountant, I want to see the sync status and last sync time for each Xero connection, so that I know how fresh my data is.

#### Acceptance Criteria

1. WHEN viewing a Xero connection THEN the system SHALL display:
   - Last successful sync timestamp per entity type
   - Current sync status (idle, syncing, error)
   - Records synced in the last sync
   - Next scheduled sync (if applicable)

2. WHEN a sync is in progress THEN the system SHALL display:
   - Progress indicator
   - Records processed / total (estimated)
   - Current entity type being synced

3. IF the last sync failed THEN the system SHALL display:
   - Error message
   - Timestamp of failure
   - Option to retry sync

4. WHEN viewing sync history THEN the system SHALL list recent sync jobs with:
   - Job type (full/incremental)
   - Start and end time
   - Records affected
   - Status (success/failed)

5. WHEN data is stale (last sync > 24 hours ago) THEN the system SHALL display a visual indicator warning the user.

---

### Requirement 9: Multi-Tenant Data Isolation

**User Story:** As an accountant, I want my synced Xero data to be completely isolated from other tenants, so that client confidentiality is maintained.

#### Acceptance Criteria

1. WHEN syncing data THEN the system SHALL associate all synced records with the tenant_id from the Xero connection.

2. WHEN storing synced data THEN the system SHALL enforce tenant_id on all tables containing Xero-sourced data.

3. WHERE RLS (Row-Level Security) is configured THEN the system SHALL ensure sync jobs set the PostgreSQL session variable `app.current_tenant_id` before any database operations.

4. IF a sync job attempts to access data from a different tenant THEN the system SHALL reject the operation and log a security audit event.

5. WHEN a tenant has multiple Xero connections THEN the system SHALL track xero_connection_id on all synced records to distinguish data sources.

6. WHEN a Xero connection is disconnected THEN the system SHALL retain the synced data but mark it as stale (no longer receiving updates).

---

### Requirement 10: Error Handling and Recovery

**User Story:** As an accountant, I want sync errors to be handled gracefully, so that partial failures don't corrupt my data.

#### Acceptance Criteria

1. IF the Xero API returns an error during sync THEN the system SHALL:
   - Log the error with full context (endpoint, parameters, response)
   - Record an audit event for the failure
   - Continue processing remaining records (partial failure mode)

2. IF a record fails to sync THEN the system SHALL:
   - Log the specific record that failed
   - Increment the records_failed counter
   - Continue with the next record

3. WHEN a sync job encounters a critical error (auth failure, connection lost) THEN the system SHALL:
   - Stop the sync immediately
   - Record the failure state
   - Mark the connection status as NEEDS_REAUTH if authentication failed

4. IF a sync job is interrupted (worker restart, timeout) THEN the system SHALL:
   - Mark the job as failed with "interrupted" reason
   - Allow the user to retry the sync

5. WHEN retrying a failed sync THEN the system SHALL start from the beginning of the sync (not resume mid-sync) to ensure data consistency.

6. IF the XeroConnection status is not ACTIVE THEN the system SHALL reject sync requests and prompt the user to re-authorize.

---

## Non-Functional Requirements

### Performance

1. WHEN syncing contacts THEN the system SHALL process at least 100 records per second (excluding API wait time).

2. WHEN syncing large datasets (> 10,000 records) THEN the system SHALL use pagination to avoid memory exhaustion.

3. WHEN making Xero API calls THEN the system SHALL batch requests where supported by the API.

4. WHEN storing synced data THEN the system SHALL use bulk insert/update operations for efficiency.

### Reliability

1. WHEN a sync job fails THEN the system SHALL preserve any successfully synced records (no rollback of partial success).

2. WHEN the Celery worker restarts THEN pending sync jobs SHALL remain in the queue and be processed when the worker recovers.

3. WHEN multiple sync jobs complete concurrently THEN the system SHALL handle database conflicts gracefully using optimistic locking.

### Observability

1. WHEN sync operations occur THEN the system SHALL emit structured logs including:
   - Connection ID
   - Sync type
   - Records processed
   - Duration
   - Errors encountered

2. WHEN errors occur THEN the system SHALL include correlation IDs to trace issues across services.

3. WHEN sync jobs complete THEN the system SHALL record metrics for monitoring dashboards.

### Security

1. WHEN making Xero API calls THEN the system SHALL use encrypted tokens from the XeroConnection (never log tokens).

2. WHEN storing synced data THEN the system SHALL apply the same encryption standards as directly entered data.

3. WHEN audit events are recorded THEN the system SHALL NOT include sensitive financial data in the event payload.

---

## Out of Scope

The following items are explicitly out of scope for this specification:

1. **Webhook-based real-time sync** - Xero Practice Manager does not support webhooks for the data types we need
2. **Bi-directional sync** - Writing data back to Xero
3. **MYOB integration** - Separate spec (future)
4. **Scheduled automatic sync** - Will be addressed in a separate scheduling spec
5. **BAS calculation from synced data** - Separate spec (005-bas-calculation)
6. **Data quality scoring** - Separate spec (006-quality-engine)

---

## Dependencies

| Dependency | Description | Status |
|------------|-------------|--------|
| Spec 003: Xero OAuth | OAuth connections with encrypted tokens | COMPLETE |
| Celery + Redis | Background task infrastructure | Available |
| Client module | Client model for storing synced contacts | Needs extension |
| Audit framework | Audit event recording | Available |

---

## Glossary

| Term | Definition |
|------|------------|
| **Xero Tenant** | A Xero organization connected via OAuth |
| **Clairo Tenant** | An accounting practice using Clairo (multi-tenant) |
| **Full Sync** | Fetching all records regardless of modification date |
| **Incremental Sync** | Fetching only records modified since last sync |
| **RLS** | Row-Level Security - PostgreSQL feature for tenant isolation |
| **ACCREC** | Xero invoice type for Accounts Receivable (sales invoice) |
| **ACCPAY** | Xero invoice type for Accounts Payable (purchase invoice) |
