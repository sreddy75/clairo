# Clairo Edge Case Library

Edge cases organized by category. Each entry describes the problem, affected modules, and the standard mitigation pattern used (or required) in Clairo.

---

## 1. Tenant Isolation

### 1.1 Missing tenant_id in Queries
- **Problem**: A query runs without setting the RLS session variable `app.current_tenant_id`, returning data from all tenants or zero rows.
- **Affected Modules**: All modules with tenant-scoped tables
- **Mitigation**: All database sessions MUST set `app.current_tenant_id` via `SET LOCAL` before executing queries. The `get_tenant_db_session()` dependency handles this. Never use raw sessions for tenant-scoped data.

### 1.2 Cross-Tenant Data Leak via Foreign Keys
- **Problem**: An entity references another entity by UUID, but the referenced entity belongs to a different tenant. Example: creating an ActionItem with a `client_id` from a different tenant.
- **Affected Modules**: insights, action_items, bas, triggers
- **Mitigation**: Service layer MUST validate that referenced entities share the same `tenant_id` before creating relationships. RLS provides a safety net but service-layer checks are the primary defense.

### 1.3 Global Tables Mistakenly Filtered by RLS
- **Problem**: Tables like `users`, `xero_oauth_states`, `knowledge_sources` are NOT tenant-scoped but queries fail if RLS is applied.
- **Affected Modules**: auth, integrations (OAuth), knowledge
- **Mitigation**: These tables have explicit RLS policies allowing access without tenant context. The `users` table uses global email uniqueness for cross-tenant lookup. Knowledge sources are shared across all tenants.

### 1.4 Tenant Context Lost in Background Tasks
- **Problem**: Celery tasks run outside request context, losing the tenant_id that was set during the HTTP request.
- **Affected Modules**: All Celery tasks (sync, ingestion, triggers, insights)
- **Mitigation**: Always pass `tenant_id` as an explicit task argument. The task MUST set `app.current_tenant_id` at the start of execution.

---

## 2. Xero OAuth Token Races

### 2.1 Concurrent Token Refresh
- **Problem**: Two simultaneous API calls detect an expired token and both attempt to refresh. One succeeds, the other gets a "refresh token already used" error from Xero (refresh tokens are single-use).
- **Affected Modules**: integrations/xero
- **Mitigation**: Use a Redis-based distributed lock keyed by `xero_refresh:{connection_id}`. The first caller refreshes and updates the stored tokens; subsequent callers wait for the lock, then read the new token. Lock timeout: 30 seconds.

### 2.2 Token Expiry Mid-Sync
- **Problem**: A long-running sync job's access token expires partway through. Next API call returns 401.
- **Affected Modules**: integrations/xero (sync jobs)
- **Mitigation**: Before each API call batch, check `token_expires_at`. If < 5 minutes remaining, proactively refresh. If a 401 is received mid-sync, auto-refresh and retry the failed call without restarting the entire sync. Spec 043 FR-020 codifies this.

### 2.3 Multi-Org Shared Tokens (Bulk Import)
- **Problem**: A single OAuth flow authorizes multiple Xero organizations. All connections share one access/refresh token pair. Refreshing for one connection must update all connections from the same auth event.
- **Affected Modules**: integrations/xero, onboarding (bulk import)
- **Mitigation**: Store `authorization_event_id` on `xero_oauth_states`. When refreshing, update tokens for ALL connections with the same `authorization_event_id`. Spec 035 FR-003.

### 2.4 Xero Revokes Access Without Notification
- **Problem**: A Xero admin disconnects the app from their org. Next API call returns 403. No webhook notification.
- **Affected Modules**: integrations/xero
- **Mitigation**: On receiving 403, set connection status to `needs_reauth`. Show banner in UI prompting reconnection. Do not retry.

---

## 3. Xero Rate Limiting

### 3.1 Per-Org Minute Limit (60 calls/min)
- **Problem**: Exceeding 60 API calls per minute per Xero organization triggers 429 responses and potential temporary ban.
- **Affected Modules**: integrations/xero
- **Mitigation**: Token bucket rate limiter tracks per-connection minute usage. Warn at 80% (48 calls), block new requests at 95% (57 calls). Wait for minute window reset. Use `X-Rate-Limit-Problem` and `Retry-After` response headers.

### 3.2 Per-Org Daily Limit (5000 calls/day)
- **Problem**: Large initial syncs or frequent re-syncs consume the daily budget. Can only check via headers.
- **Affected Modules**: integrations/xero
- **Mitigation**: Track `rate_limit_daily_remaining` from response headers. Warn at 80%, hard-block at 95%. Schedule heavy syncs for off-peak hours. Daily limit resets at midnight UTC.

### 3.3 App-Wide Limit During Bulk Sync (10,000 calls/min)
- **Problem**: When syncing 50+ clients in parallel, the aggregate call rate across all orgs can hit the app-wide Xero limit.
- **Affected Modules**: integrations/xero, onboarding (bulk import)
- **Mitigation**: Global concurrency limiter: max 10 concurrent org syncs (Spec 035 FR-009). Stagger sync starts. Monitor aggregate call rate.

### 3.4 Missing Rate Limit Headers
- **Problem**: Xero occasionally omits rate limit headers from responses, making remaining quota unknown.
- **Affected Modules**: integrations/xero
- **Mitigation**: Fall back to conservative defaults: assume 50% of limits consumed. Spec 043 edge case.

---

## 4. Background Task Failures

### 4.1 Celery Task Crash with Partial Progress
- **Problem**: A long-running sync or ingestion task crashes mid-way. Some records are committed, others are not.
- **Affected Modules**: integrations/xero, knowledge
- **Mitigation**: Track per-entity progress (XeroSyncEntityProgress for syncs, completed_items/failed_items for ingestion). On restart/retry, resume from last checkpoint rather than restarting from scratch. Spec 043 FR-019, Spec 045 checkpoint/resume.

### 4.2 Retry Storms
- **Problem**: A permanently failing external service causes exponential retry growth, overwhelming the task queue.
- **Affected Modules**: All Celery tasks
- **Mitigation**: Exponential backoff with jitter. Max 3 retries. Circuit breaker pattern for external services (ScraperCircuitBreakerState for knowledge, implicit for Xero). After max retries, mark as failed and notify user.

### 4.3 Task Idempotency
- **Problem**: Celery may deliver the same task twice (at-least-once delivery). Double-processing creates duplicates.
- **Affected Modules**: integrations (sync), knowledge (ingestion), billing (webhooks)
- **Mitigation**: Use idempotency keys. Xero sync: upsert by `xero_*_id`. Knowledge ingestion: `content_hash` + `natural_key`. Billing: `stripe_event_id` unique constraint. Always upsert, never blind insert.

### 4.4 Dead Letter Queue Handling
- **Problem**: Tasks that fail all retries sit in DLQ with no visibility.
- **Affected Modules**: All Celery tasks
- **Mitigation**: Log failed tasks with full context. Update job/sync status to "failed". Create user-visible notification with retry action.

---

## 5. Subscription Limit Enforcement

### 5.1 Client Limit Reached During Bulk Import
- **Problem**: Accountant bulk-imports 30 orgs but plan only allows 5 more. Must not silently exceed limit.
- **Affected Modules**: onboarding, billing
- **Mitigation**: Check remaining capacity BEFORE starting import. If total > capacity, show warning and let user select which orgs to import. If limit reached mid-import, stop importing new connections and mark remaining as "skipped (plan limit reached)". Spec 035 FR-006.

### 5.2 Tier Downgrade with Over-Limit Clients
- **Problem**: Tenant downgrades from Professional (100 clients) to Starter (25 clients) but has 80 active clients.
- **Affected Modules**: billing, auth
- **Mitigation**: Block new client creation but allow existing clients to continue functioning. Display upgrade prompt on new client creation. Do NOT automatically disconnect existing clients.

### 5.3 Trial Expiry with Active Data
- **Problem**: 14-day trial ends. Tenant has not entered payment. They have active clients and BAS sessions.
- **Affected Modules**: auth, billing
- **Mitigation**: Transition to `suspended` status. Read-only access for 30 days (grace period). Then full lock. Data retained for 90 days. Resume on payment.

---

## 6. Stale Data

### 6.1 Xero Data Not Recently Synced
- **Problem**: AI insights or BAS calculations use data that hasn't been synced for days/weeks. Results are misleading.
- **Affected Modules**: insights, bas, quality, agents
- **Mitigation**: Display "Data as of [last_sync_at]" on all AI responses and insights. Show prominent stale data warning when data > 7 days old (Spec 044 FR-017). Quality scoring dimension: freshness_score.

### 6.2 Cached Reports Expired
- **Problem**: Xero reports (P&L, Balance Sheet) cached in `xero_reports` are stale but still displayed.
- **Affected Modules**: integrations/xero (reports)
- **Mitigation**: Daily refresh schedule for active clients. On-demand refresh for current period when user opens report. Show report generation timestamp.

### 6.3 Quality Scores from Previous Quarter
- **Problem**: Quality scores are per-quarter. At the start of a new quarter, the previous quarter's score is displayed until new data is available.
- **Affected Modules**: quality
- **Mitigation**: Trigger quality recalculation after sync completion (post-sync pipeline, Spec 043 FR-021). Display which quarter the score applies to.

---

## 7. Concurrent Operations

### 7.1 Duplicate Sync Triggers
- **Problem**: User clicks "Sync" while a sync is already running. Or scheduler triggers a sync that overlaps with a user-triggered one.
- **Affected Modules**: integrations/xero
- **Mitigation**: Check `sync_in_progress` flag on XeroConnection before starting. If already syncing, reject with clear error message. Spec 043 edge case.

### 7.2 Simultaneous BAS Session Edits
- **Problem**: Two accountants edit the same BAS session concurrently. Last write wins, silently overwriting changes.
- **Affected Modules**: bas
- **Mitigation**: Optimistic locking via `version` column on BASSession. SQLAlchemy `version_id_col` mapper config. On conflict, return 409 with instructions to reload.

### 7.3 Concurrent Bulk Imports for Same Tenant
- **Problem**: Accountant initiates two bulk import flows simultaneously, creating duplicate connections.
- **Affected Modules**: onboarding
- **Mitigation**: Prevent concurrent bulk import jobs per tenant (Spec 035 FR-017). Check for in-progress job before starting new one. Duplicate connection prevention via XeroConnection unique constraint on `(tenant_id, xero_tenant_id)`.

---

## 8. External Service Unavailability

### 8.1 Xero API 503 (Service Unavailable)
- **Problem**: Xero is temporarily down. Syncs fail, OAuth flows fail.
- **Affected Modules**: integrations/xero
- **Mitigation**: Retry with exponential backoff (1s, 2s, 4s) up to 3 times. Mark entity as "partially synced" if retries exhausted. User notification with retry action.

### 8.2 Pinecone Outage
- **Problem**: Vector database is down. Knowledge base queries fail, ingestion fails.
- **Affected Modules**: knowledge
- **Mitigation**: Graceful degradation: knowledge chatbot returns "Knowledge base temporarily unavailable" instead of crashing. Ingestion jobs pause and resume when service recovers (circuit breaker). BM25 search can serve as partial fallback.

### 8.3 Stripe Webhook Delays
- **Problem**: Stripe webhook arrives late (hours). Subscription status in Clairo is stale.
- **Affected Modules**: billing
- **Mitigation**: Idempotent webhook processing via `stripe_event_id` unique constraint. Periodic polling of Stripe subscription status as safety net. Grace period on payment failures (past_due status).

### 8.4 Clerk Auth Service Downtime
- **Problem**: Clerk is down. Users cannot authenticate. JWT validation fails.
- **Affected Modules**: auth
- **Mitigation**: Cache JWT public keys locally (JWKS cache). Short-lived tokens still work during outage. No new logins possible during Clerk downtime - accept this risk.

### 8.5 ATO Website Changes (Knowledge Ingestion)
- **Problem**: ATO changes their website structure, breaking scrapers. Content is stale or ingestion fails repeatedly.
- **Affected Modules**: knowledge
- **Mitigation**: Circuit breaker per source host (ScraperCircuitBreakerState). After consecutive failures, circuit opens and stops attempting. Alerts to admin. Scrapers have configurable CSS selectors in `scrape_config`. Manual ingestion fallback.

---

## 9. Knowledge Ingestion Reliability

### 9.1 Deduplication Failures
- **Problem**: Current dedup checks only the first chunk's content_hash. Multi-chunk documents may create duplicates when content changes.
- **Affected Modules**: knowledge
- **Mitigation (Spec 045)**: Document-level idempotency via `document_hash` (SHA-256 of full source document) + `natural_key` (e.g., "legislation:s109D-ITAA1936"). IngestionManager checks document_hash before re-processing.

### 9.2 Orphaned Vectors
- **Problem**: `delete_by_source()` removes PostgreSQL records but does not clean corresponding Pinecone vectors. Stale vectors remain searchable.
- **Affected Modules**: knowledge
- **Mitigation (Spec 045)**: Deterministic vector IDs: `{source_type}:{natural_key}:{chunk_index}`. When updating a document, delete old vectors by ID prefix before upserting new ones. Periodic reconciliation job to detect orphans.

### 9.3 Checkpoint/Resume for Large Ingestion Jobs
- **Problem**: Ingesting thousands of documents can take hours. A crash at 80% means restarting from scratch.
- **Affected Modules**: knowledge
- **Mitigation (Spec 045)**: `completed_items` and `failed_items` JSONB arrays on IngestionJob. `is_resumable` flag. `parent_job_id` for resume lineage. Resume skips already-completed items.

### 9.4 Single-Vector Upserts in Celery Loop
- **Problem**: Current implementation upserts one vector at a time to Pinecone, causing excessive API calls and slow ingestion.
- **Affected Modules**: knowledge
- **Mitigation**: Batch upserts (100 vectors per Pinecone call). Accumulate in memory, flush when batch is full or job ends.

---

## 10. AI Output Trust

### 10.1 Hardcoded Confidence Scores
- **Problem**: Insights display "85% confidence" that is a meaningless constant (0.75 for AI, 0.85 for Magic Zone). Creates false trust.
- **Affected Modules**: insights, agents
- **Mitigation (Spec 044)**: Compute confidence from data completeness, knowledge base match quality, data freshness, and number of data sources. Display confidence breakdown on hover. FR-022 through FR-024.

### 10.2 Missing Evidence on AI Recommendations
- **Problem**: Magic Zone OPTIONS show strategic recommendations without citing the specific data points that informed them.
- **Affected Modules**: insights
- **Mitigation (Spec 044)**: AI prompt instructs model to include `**Evidence:**` section per option. Backend independently extracts structured evidence from known financial context (not from AI text). Frontend renders from structured data. FR-001 through FR-006.

### 10.3 Data Snapshot Not Preserved
- **Problem**: Financial data sent to Claude during insight generation is discarded. No audit trail of what the AI had access to.
- **Affected Modules**: insights, agents
- **Mitigation (Spec 044)**: Store financial context in `data_snapshot` JSONB field on Insight. Bounded to 50KB (summary data only, no raw transactions). FR-007 through FR-011.

### 10.4 Data Freshness Not Shown on AI Responses
- **Problem**: AI responses reference financial data but don't indicate how current that data is. Stale data warnings only in page header, not alongside AI content.
- **Affected Modules**: insights, agents (chat)
- **Mitigation (Spec 044)**: Every AI response includes "Data as of [date]" indicator. Prominent stale warning (>7 days) alongside content, not just in header. FR-016 through FR-018.
