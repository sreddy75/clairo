# Clairo Entity Taxonomy

Full entity reference grouped by architectural layer. Each entry includes the module location, table name, key fields, and foreign key relationships.

---

## 1. Auth & Multi-Tenancy Layer

Module: `backend/app/modules/auth/models.py`

### Tenant
- **Table**: `tenants`
- **Purpose**: Accounting practice (the paying subscriber). All tenant-scoped data isolated via PostgreSQL RLS.
- **Key Fields**:
  - `id` (UUID, PK)
  - `name` (String 255) - Practice display name
  - `slug` (String 50, unique) - URL-friendly identifier
  - `settings` (JSONB) - Tenant-specific configuration
  - `tier` (Enum: starter/professional/growth/enterprise) - Subscription tier
  - `subscription_status` (Enum: trial/active/past_due/suspended/cancelled/grandfathered)
  - `stripe_customer_id` (String, unique, nullable) - Stripe customer reference
  - `stripe_subscription_id` (String, nullable)
  - `current_period_end` (DateTime, nullable) - Billing period end
  - `client_count` (Integer) - Denormalized count for limit checks
  - `ai_queries_month` (Integer) - Monthly usage counter
  - `documents_month` (Integer) - Monthly usage counter
  - `usage_month_reset` (Date, nullable) - Last reset date
  - `owner_email` (String, nullable) - Primary billing contact
  - `mfa_required` (Boolean) - Whether MFA is mandatory
  - `is_active` (Boolean)
- **Relationships**: Has many PracticeUsers, Invitations, BillingEvents, UsageSnapshots, UsageAlerts, OnboardingProgress (1:1), BulkImportJobs, EmailDrips, FeatureFlagOverrides
- **Access Logic**: `can_access` property checks is_active AND status in (trial, active, past_due, grandfathered)

### User
- **Table**: `users`
- **Purpose**: Single source of identity for ALL user types. NOT tenant-scoped (global email uniqueness).
- **Key Fields**:
  - `id` (UUID, PK)
  - `email` (String 255, unique) - Global unique email
  - `user_type` (Enum: practice_user/business_owner) - Discriminator for profile lookup
  - `is_active` (Boolean)
- **Relationships**: Has one PracticeUser profile (1:1) or ClientUser profile (future)
- **Design**: Shared Identity + Separate Profiles pattern

### PracticeUser
- **Table**: `practice_users`
- **Purpose**: Tenant-scoped profile for accountants/staff. RLS enforced.
- **Key Fields**:
  - `id` (UUID, PK)
  - `user_id` (UUID, FK -> users.id, unique) - 1:1 with User
  - `tenant_id` (UUID, FK -> tenants.id) - RLS enforced
  - `clerk_id` (String 100, unique) - Clerk auth identifier
  - `role` (Enum: admin/accountant/staff)
  - `mfa_enabled` (Boolean)
  - `last_login_at` (DateTime, nullable)
- **Relationships**: Belongs to User, Tenant. Has many Invitations, Notifications
- **Permissions**: admin = full access; accountant = client/BAS write; staff = read-only

### Invitation
- **Table**: `invitations`
- **Purpose**: Pending team invitations. Tenant-scoped with special public token lookup policy.
- **Key Fields**:
  - `id` (UUID, PK)
  - `tenant_id` (UUID, FK -> tenants.id)
  - `invited_by` (UUID, FK -> practice_users.id)
  - `email` (String 255)
  - `role` (Enum: admin/accountant/staff)
  - `token` (String 64, unique) - URL-safe invitation token
  - `expires_at` (DateTime) - Default 7 days
  - `accepted_at`, `accepted_by`, `revoked_at` (nullable timestamps)
- **Status**: Computed property from timestamps (pending/accepted/revoked/expired)

---

## 2. Data Layer (Xero Integration)

Module: `backend/app/modules/integrations/xero/models.py`

### XeroConnection
- **Table**: `xero_connections`
- **Purpose**: Central "client" entity. Links Clairo tenant to a Xero organization. Stores encrypted OAuth tokens.
- **Key Fields**:
  - `id` (UUID, PK)
  - `tenant_id` (UUID, FK -> tenants.id) - RLS enforced
  - `xero_tenant_id` (String, unique per tenant) - Xero org identifier
  - `organization_name` (String) - Display name
  - `connection_type` (Enum: practice/client)
  - `status` (Enum: active/needs_reauth/disconnected)
  - `access_token`, `refresh_token` (encrypted strings)
  - `token_expires_at` (DateTime)
  - `scopes` (Array of String) - Granted OAuth scopes
  - `rate_limit_daily_remaining`, `rate_limit_minute_remaining` (Integer)
  - `connected_by` (UUID, FK -> practice_users.id)
  - `last_*_sync_at` timestamps per entity type
  - `sync_in_progress` (Boolean)
- **Relationships**: Has many XeroClients, XeroInvoices, XeroBankTransactions, XeroAccounts, XeroEmployees, XeroPayRuns, QualityScores, QualityIssues, Insights, BASPeriods, XeroReports, XeroCreditNotes, XeroPayments, XeroJournals, XeroAssets
- **Critical Note**: This is what Clairo calls a "client" - NOT XeroClient (which is a Xero contact)

### XeroOAuthState
- **Table**: `xero_oauth_states`
- **Purpose**: CSRF protection for OAuth flow. NOT tenant-scoped (lookup by state token).
- **Key Fields**: `state`, `code_verifier`, `tenant_id`, `initiated_by`, `expires_at`, `is_used`, `authorization_event_id` (for bulk import)

### XeroSyncJob
- **Table**: `xero_sync_jobs`
- **Purpose**: Tracks individual sync operations per connection.
- **Key Fields**: `connection_id`, `sync_type` (contacts/invoices/bank_transactions/accounts/employees/pay_runs/payroll/full), `status`, `records_processed/created/updated/failed`, timing fields, `error_message`

### XeroClient (Contact)
- **Table**: `xero_clients`
- **Purpose**: Xero contacts (customers, suppliers, or both).
- **Key Fields**: `connection_id` (FK -> xero_connections.id), `xero_contact_id`, `name`, `contact_type` (customer/supplier/both), `abn`, `email`, `is_active`
- **Warning**: "XeroClient" = Xero contact. NOT the same as "client" in Clairo domain language.

### XeroInvoice
- **Table**: `xero_invoices`
- **Key Fields**: `connection_id`, `xero_invoice_id`, `invoice_type` (accrec/accpay), `status`, `total`, `total_tax`, `tax_type`, `line_items` (JSONB)

### XeroBankTransaction
- **Table**: `xero_bank_transactions`
- **Key Fields**: `connection_id`, `xero_transaction_id`, `transaction_type` (receive/spend/...), `total`, `total_tax`, `is_reconciled`, `line_items` (JSONB)

### XeroAccount
- **Table**: `xero_accounts`
- **Key Fields**: `connection_id`, `xero_account_id`, `code`, `name`, `account_class` (asset/equity/expense/liability/revenue), `tax_type`

### XeroEmployee
- **Table**: `xero_employees`
- **Key Fields**: `connection_id`, `xero_employee_id`, `first_name`, `last_name`, `status` (active/terminated), `date_of_birth`, `start_date`, `tax_file_number_masked`

### XeroPayRun
- **Table**: `xero_pay_runs`
- **Key Fields**: `connection_id`, `xero_pay_run_id`, `status` (draft/posted), `period_start/end_date`, `total_pay`, `total_tax`, `total_super`, `employee_count`, `pay_items` (JSONB)

### XeroCreditNote (Spec 024)
- **Table**: `xero_credit_notes`
- **Key Fields**: `connection_id`, `xero_credit_note_id`, `type` (accpaycredit/accreccredit), `status`, `total`, `total_tax`, `remaining_credit`
- **GST Impact**: Credit notes reduce GST collected/paid. Formula: GST Collected = Sum(Invoice GST) - Sum(Credit Note GST)

### XeroPayment (Spec 024)
- **Table**: `xero_payments`
- **Key Fields**: `connection_id`, `xero_payment_id`, `payment_type`, `amount`, `invoice_id` (FK), `payment_date`
- **Cash Flow Impact**: Actual payment dates vs invoice dates for real cash flow analysis

### XeroJournal / XeroManualJournal (Spec 024)
- **Tables**: `xero_journals`, `xero_manual_journals`
- **Purpose**: System-generated and user-created journals for complete audit trail

### XeroReport (Spec 023)
- **Table**: `xero_reports`
- **Key Fields**: `connection_id`, `report_type` (profit_and_loss/balance_sheet/aged_receivables/aged_payables/trial_balance/bank_summary/budget_summary), `report_data` (JSONB), `report_date`, `period_start/end`

### XeroAsset (Spec 025)
- **Table**: `xero_assets`
- **Key Fields**: `connection_id`, `xero_asset_id`, `asset_name`, `asset_status` (Draft/Registered/Disposed), `purchase_date`, `purchase_price`, `book_depreciation_*`, `tax_depreciation_*`, `book_value`, `disposal_*`

### XeroSyncEntityProgress (Spec 043)
- **Table**: `xero_sync_entity_progress`
- **Purpose**: Per-entity-type sync progress within a sync job. Enables incremental sync and checkpoint/resume.
- **Key Fields**: `sync_job_id` (FK), `entity_type`, `status`, `records_processed/created/updated/failed`, `last_modified_since`

### XeroWebhookEvent (Spec 043)
- **Table**: `xero_webhook_events`
- **Purpose**: Incoming Xero webhook events for idempotent processing.
- **Key Fields**: `webhook_key` (unique dedup key), `event_type`, `connection_id`, `processing_status`

---

## 3. Compliance Layer (BAS Workflow)

Module: `backend/app/modules/bas/models.py`

### BASPeriod
- **Table**: `bas_periods`
- **Purpose**: A reporting period for a client. Quarters (Q1-Q4) or months (1-12).
- **Key Fields**: `tenant_id`, `connection_id` (FK -> xero_connections.id), `period_type` (quarterly/monthly), `quarter` (1-4, nullable), `month` (1-12, nullable), `fy_year`, `start_date`, `end_date`, `due_date`
- **Constraints**: Quarter XOR Month (not both). Unique per connection+fy_year+quarter.

### BASSession
- **Table**: `bas_sessions`
- **Purpose**: Preparation workflow for one BAS period. Tracks status, approvals, lodgement.
- **Key Fields**: `tenant_id`, `period_id` (FK, unique - 1:1 with BASPeriod), `status` (draft/in_progress/ready_for_review/approved/lodged), `created_by`, `approved_by/at`, `reviewed_by/at`, `lodged_at/by`, `lodgement_method` (ATO_PORTAL/XERO/OTHER), `ato_reference_number`, `version` (optimistic locking)
- **Workflow**: DRAFT -> IN_PROGRESS -> READY_FOR_REVIEW -> APPROVED -> LODGED

### BASCalculation
- **Table**: `bas_calculations`
- **Purpose**: Cached GST and PAYG calculation results. 1:1 with BASSession.
- **GST G-Fields**:
  - `g1_total_sales` - Total sales including GST
  - `g2_export_sales` - Export sales (GST-free)
  - `g3_gst_free_sales` - Other GST-free sales
  - `g10_capital_purchases` - Capital purchases
  - `g11_non_capital_purchases` - Non-capital purchases
  - `field_1a_gst_on_sales` - GST collected
  - `field_1b_gst_on_purchases` - GST paid
- **PAYG W-Fields**:
  - `w1_total_wages` - Total salary/wages (gross)
  - `w2_amount_withheld` - PAYG tax withheld
- **Summary**:
  - `gst_payable` = 1A - 1B (negative = refund)
  - `total_payable` = GST + PAYG

### BASAdjustment
- **Table**: `bas_adjustments`
- **Purpose**: Manual adjustments with mandatory reason (audit requirement).
- **Valid Fields**: g1, g2, g3, g10, g11, 1a, 1b, w1, w2

### BASAuditLog
- **Table**: `bas_audit_log`
- **Purpose**: Immutable compliance audit trail. Event types include session lifecycle, calculations, lodgement, exports, notifications.

---

## 4. AI & Intelligence Layer

### Insight
Module: `backend/app/modules/insights/models.py`
- **Table**: `insights`
- **Key Fields**: `tenant_id`, `client_id` (FK -> xero_connections.id), `category` (compliance/quality/cash_flow/tax/strategic), `insight_type`, `priority` (high/medium/low), `title`, `summary`, `detail`, `suggested_actions` (JSONB), `status` (new/viewed/actioned/dismissed/resolved/expired), `confidence`, `data_snapshot` (JSONB - point-in-time financial context), `generation_type` (rule_based/ai_single/magic_zone), `agents_used` (JSONB), `action_deadline`

### ActionItem
Module: `backend/app/modules/action_items/models.py`
- **Table**: `action_items`
- **Key Fields**: `tenant_id`, `title`, `source_insight_id` (FK -> insights.id, nullable), `client_id` (FK -> xero_connections.id, nullable), `assigned_to_user_id`, `due_date`, `priority` (urgent/high/medium/low), `status` (pending/in_progress/completed/cancelled)

### Trigger
Module: `backend/app/modules/triggers/models.py`
- **Table**: `triggers`
- **Key Fields**: `tenant_id`, `name`, `trigger_type` (data_threshold/time_scheduled/event_based), `config` (JSONB), `target_analyzers` (Array), `dedup_window_hours`, `status` (active/disabled/error), `is_system_default`

### TriggerExecution
- **Table**: `trigger_executions`
- **Key Fields**: `trigger_id`, `tenant_id`, `status` (running/success/failed/partial), `clients_evaluated`, `insights_created`, `insights_deduplicated`

### AgentQuery
Module: `backend/app/modules/agents/models.py`
- **Table**: `agent_queries`
- **Purpose**: Audit log for multi-perspective agent queries. Stores metadata ONLY (no query text for privacy).
- **Key Fields**: `correlation_id`, `tenant_id`, `user_id`, `connection_id`, `query_hash` (SHA-256 dedup), `perspectives_used`, `confidence`, `escalation_required`, `processing_time_ms`, `token_usage`

### AgentEscalation
- **Table**: `agent_escalations`
- **Purpose**: Human escalation records. DOES store query text (needed for review).
- **Key Fields**: `query_id`, `reason`, `confidence`, `status` (pending/resolved/dismissed), `query_text`, `partial_response`, `resolved_by/at`

---

## 5. Knowledge Base Layer

Module: `backend/app/modules/knowledge/models.py`

### KnowledgeSource
- **Table**: `knowledge_sources`
- **Purpose**: Content source configuration. NOT tenant-scoped (shared knowledge base).
- **Key Fields**: `name`, `source_type` (ato_rss/ato_web/austlii/business_gov/fair_work), `base_url`, `collection_name` (target Pinecone namespace), `scrape_config` (JSONB), `is_active`, `last_scraped_at`

### ContentChunk
- **Table**: `content_chunks`
- **Purpose**: Metadata for chunks stored in Pinecone. Dual storage: Pinecone has vectors, PostgreSQL has queryable metadata.
- **Key Fields**: `source_id` (FK -> knowledge_sources.id), `qdrant_point_id` (legacy name, actually Pinecone vector ID), `collection_name`, `content_hash` (SHA-256 dedup), `source_url`, `title`, `source_type` (ato_ruling/ato_guide/legislation/business_guide), `effective_date`, `expiry_date`, `entity_types` (Array), `industries` (Array), `ruling_number`
- **Spec 045 Extensions**: `content_type` (operative_provision/definition/example/etc), `section_ref`, `cross_references` (JSONB), `topic_tags` (JSONB), `court` (HCA/FCA/FCAFC/AATA), `case_citation`, `document_hash` (full document change detection), `natural_key` (idempotency key)

### IngestionJob
- **Table**: `ingestion_jobs`
- **Key Fields**: `source_id`, `status` (pending/running/completed/failed/cancelled), `items_processed/added/updated/skipped/failed`, `tokens_used`, `errors` (JSONB), `triggered_by` (manual/scheduled/webhook)
- **Spec 045**: `completed_items`/`failed_items` (JSONB for checkpoint/resume), `is_resumable`, `parent_job_id`

### LegislationSection (Spec 045)
- **Table**: `legislation_sections`
- **Key Fields**: `act_id`, `act_name`, `act_short_name`, `section_ref`, `part`, `division`, `subdivision`, `heading`, `content_hash`, `compilation_date`, `cross_references` (JSONB), `defined_terms` (JSONB), `topic_tags` (JSONB), `is_current`

### ContentCrossReference (Spec 045)
- **Table**: `content_cross_references`
- **Key Fields**: `source_chunk_id` (FK), `target_section_ref`, `target_chunk_id` (FK, nullable), `reference_type` (cites/defines/supersedes/amends)

### TaxDomain (Spec 045)
- **Table**: `tax_domains`
- **Key Fields**: `slug`, `name`, `description`, `topic_tags` (JSONB), `legislation_refs` (JSONB), `ruling_types` (JSONB)

### BM25IndexEntry (Spec 045)
- **Table**: `bm25_index_entries`
- **Purpose**: Lightweight keyword index for hybrid search (BM25 + vector fusion).
- **Key Fields**: `chunk_id` (FK -> content_chunks.id, unique), `collection_name`, `tokens` (JSONB), `section_refs` (JSONB)

### ScraperCircuitBreakerState (Spec 045)
- **Table**: `scraper_circuit_breakers`
- **Key Fields**: `source_host` (unique), `state` (closed/open/half_open), `failure_count`, `recovery_timeout_seconds`

### ChatConversation
- **Table**: `chat_conversations`
- **Key Fields**: `user_id` (Clerk ID), `client_id` (FK -> xero_connections.id, nullable), `title`

### ChatMessage
- **Table**: `chat_messages`
- **Key Fields**: `conversation_id` (FK), `role` (user/assistant), `content`, `citations` (JSONB: [{number, title, url, source_type, score}]), `message_metadata` (JSONB, DB column named 'metadata')

---

## 6. Quality & Scoring Layer

Module: `backend/app/modules/quality/models.py`

### QualityScore
- **Table**: `quality_scores`
- **Key Fields**: `tenant_id`, `connection_id` (FK -> xero_connections.id), `quarter`, `fy_year`, `overall_score` (0-100), `freshness_score`, `reconciliation_score`, `categorization_score`, `completeness_score`, `payg_score` (nullable if N/A), `trigger_reason`
- **Constraint**: Unique per connection+quarter+fy_year

### QualityIssue
- **Table**: `quality_issues`
- **Key Fields**: `tenant_id`, `connection_id`, `quarter`, `fy_year`, `code` (STALE_DATA/UNRECONCILED_TXN/MISSING_GST_CODE/NO_INVOICES/MISSING_PAYROLL/etc), `severity` (critical/error/warning/info), `title`, `affected_count`, `affected_ids` (JSONB), `suggested_action`, `dismissed/dismissed_by/dismissed_reason`

---

## 7. Billing & Subscription Layer

Module: `backend/app/modules/billing/models.py`

### BillingEvent
- **Table**: `billing_events`
- **Key Fields**: `tenant_id`, `stripe_event_id` (unique), `event_type`, `event_data` (JSONB), `amount_cents`, `currency` (default: aud), `status` (pending/processed/failed)

### UsageSnapshot
- **Table**: `usage_snapshots`
- **Key Fields**: `tenant_id`, `captured_at`, `client_count`, `ai_queries_count`, `documents_count`, `tier`, `client_limit`

### UsageAlert
- **Table**: `usage_alerts`
- **Key Fields**: `tenant_id`, `alert_type` (threshold_80/threshold_90/limit_reached), `billing_period` (YYYY-MM), `threshold_percentage`, `client_count_at_alert`, `client_limit_at_alert`, `recipient_email`
- **Constraint**: Unique per tenant+alert_type+billing_period (prevents duplicate alerts)

---

## 8. Admin Layer

Module: `backend/app/modules/admin/models.py`

### FeatureFlagOverride
- **Table**: `feature_flag_overrides`
- **Key Fields**: `tenant_id`, `feature_key` (ai_insights/client_portal/custom_triggers/api_access/knowledge_base/magic_zone), `override_value` (Boolean), `reason`, `set_by` (FK -> practice_users.id)
- **Precedence**: Override > Tier default

---

## 9. Onboarding Layer

Module: `backend/app/modules/onboarding/models.py`

### OnboardingProgress
- **Table**: `onboarding_progress`
- **Purpose**: 1:1 with Tenant. Tracks setup completion state machine.
- **Status Values**: started -> tier_selected -> payment_setup -> xero_connected -> clients_imported -> tour_completed -> completed (also: skipped_xero)

### BulkImportJob
- **Table**: `bulk_import_jobs`
- **Purpose**: Tracks bulk client import operations.
- **Key Fields**: `tenant_id`, `status` (pending/in_progress/completed/partial_failure/failed/cancelled), total/imported/failed/skipped counts, per-org results

### EmailDrip
- **Table**: `email_drips`
- **Purpose**: Prevents duplicate onboarding emails.
- **Types**: welcome, connect_xero, import_clients, trial_midpoint, trial_ending, trial_ended, onboarding_complete

---

## 10. Portal Layer

Module: `backend/app/modules/portal/models.py`

### PortalInvitation
- **Table**: `portal_invitations`
- **Purpose**: Magic-link invitations for business owners to access client portal.
- **Key Fields**: `tenant_id`, `connection_id` (FK -> xero_connections.id), `email`, `token_hash` (SHA-256), `status`, `expires_at`

### DocumentRequest (ClientChase)
- **Table**: `document_requests` (planned)
- **Purpose**: Accountant requests documents from business owners.
- **Key Fields**: `tenant_id`, `client_id`, `title`, `description`, `due_date`, `priority`, `status` (pending/viewed/responded/complete), `auto_remind`

### DocumentRequestTemplate
- **Purpose**: Reusable templates for common requests (bank statements, BAS workpapers, source docs)

---

## 11. Notifications Layer

Module: `backend/app/modules/notifications/models.py`

### Notification
- **Table**: `notifications`
- **Key Fields**: `tenant_id`, `user_id` (FK -> practice_users.id), `notification_type` (deadline_approaching/deadline_tomorrow/deadline_today/deadline_overdue/review_requested/review_overdue/info/warning/success), `title`, `message`, `entity_type/entity_id` (polymorphic link), `is_read/read_at`

---

## Entity Relationship Summary

```
Tenant (1) ----< (N) PracticeUser
Tenant (1) ----< (N) XeroConnection ("client")
Tenant (1) ---- (1) OnboardingProgress

XeroConnection (1) ----< (N) XeroClient (contacts)
XeroConnection (1) ----< (N) XeroInvoice
XeroConnection (1) ----< (N) XeroBankTransaction
XeroConnection (1) ----< (N) XeroAccount
XeroConnection (1) ----< (N) XeroEmployee
XeroConnection (1) ----< (N) XeroPayRun
XeroConnection (1) ----< (N) XeroCreditNote
XeroConnection (1) ----< (N) XeroPayment
XeroConnection (1) ----< (N) XeroJournal
XeroConnection (1) ----< (N) XeroReport
XeroConnection (1) ----< (N) XeroAsset
XeroConnection (1) ----< (N) QualityScore
XeroConnection (1) ----< (N) QualityIssue
XeroConnection (1) ----< (N) BASPeriod
XeroConnection (1) ----< (N) Insight

BASPeriod (1) ---- (1) BASSession
BASSession (1) ---- (1) BASCalculation
BASSession (1) ----< (N) BASAdjustment
BASSession (1) ----< (N) BASAuditLog

Insight (1) ----< (N) ActionItem (optional link)

KnowledgeSource (1) ----< (N) ContentChunk
KnowledgeSource (1) ----< (N) IngestionJob
ContentChunk (1) ----< (N) ContentCrossReference
ContentChunk (1) ---- (1) BM25IndexEntry

Trigger (1) ----< (N) TriggerExecution
AgentQuery (1) ----< (N) AgentEscalation
```
