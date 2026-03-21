# Research: Bulk Client Import via Multi-Org Xero OAuth

**Feature**: 035-bulk-client-import
**Date**: 2026-02-08

## Research Findings

### R1: Multi-Org Token Sharing Strategy

**Decision**: Store the same encrypted access/refresh token on every XeroConnection created from a single OAuth callback. Use `auth_event_id` to group connections from the same authorization event.

**Rationale**: Xero's OAuth 2.0 model issues a single token pair per user session, not per organization. The `Xero-Tenant-Id` header selects which org an API call targets. The token pair is valid for all authorized orgs. Storing it per-connection (rather than in a shared table) follows the existing pattern and keeps the `XeroConnection` self-contained for sync operations.

**Alternatives Considered**:
- **Shared token table**: Normalizes storage but breaks the existing pattern where `XeroConnection` is the unit of sync — all sync code reads tokens from the connection record.
- **Reference first connection's tokens**: Would create coupling between connections and fail if the first connection is disconnected.

### R2: Callback Handler Refactoring Approach

**Decision**: Create a new `handle_bulk_callback()` method alongside the existing `handle_callback()`, rather than modifying the existing method. The existing single-org flow remains unchanged (FR-013 backward compatibility). A new `bulk=true` parameter in the OAuth state determines which handler runs.

**Rationale**: The existing `handle_callback()` is tightly coupled to single-org logic (XPM client linking, connection type from OAuth state). Modifying it risks breaking the established flow. A separate method for bulk import can iterate all organizations, create connections with shared tokens, and return the full list for the configuration screen.

**Alternatives Considered**:
- **Modify existing callback**: Simpler but higher risk to established flow. Would need conditional logic throughout.
- **New endpoint entirely**: Unnecessary — the OAuth redirect URL can remain the same; the state record differentiates.

### R3: Bulk Sync Orchestration Pattern

**Decision**: Use the existing `BulkImportJob` model from the onboarding module (with `source_type="xero_bulk_oauth"`) to track the overall import job. Create a new Celery task `run_bulk_xero_import` that orchestrates individual `run_sync` tasks with concurrency control.

**Rationale**: The `BulkImportJob` model already has the right fields (total_clients, imported_count, failed_count, progress_percent, imported_clients JSONB, failed_clients JSONB). The portal bulk requests pattern (create job → queue Celery → poll status) is proven. Individual org syncs should use the existing `run_sync` task to avoid duplicating sync logic.

**Alternatives Considered**:
- **New model for bulk import tracking**: Duplication of existing `BulkImportJob`.
- **Celery Group/Chord**: Too rigid for staggered execution with rate limit pauses. A loop-based orchestrator task with sleep intervals provides better control.
- **Per-org Celery tasks with Celery rate limit**: Celery's built-in rate limiting is per-worker, not app-wide. Doesn't solve the cross-org app-level limit coordination.

### R4: App-Wide Rate Limit Coordination

**Decision**: Use Redis as a shared counter for the app-wide 10,000 calls/minute Xero limit. The orchestrator task checks this counter before dispatching each org sync. Individual sync tasks update the counter from Xero's `X-AppMinLimit-Remaining` response header.

**Rationale**: The current `XeroRateLimiter` is stateless (per-connection `RateLimitState` dataclass). For bulk operations hitting 10+ orgs concurrently, the app-wide minute limit (10,000 calls) is the binding constraint. Redis provides a fast shared counter that Celery workers can read/write atomically.

**Alternatives Considered**:
- **In-memory counter**: Not shared across Celery workers.
- **Database counter**: Too slow for per-request checking.
- **Conservative fixed delay between orgs**: Simple but wastes throughput — if one org has few records, the slot is wasted.

### R5: Frontend Flow Architecture

**Decision**: Implement the bulk import as a multi-step wizard flow on a new page (`/clients/import`):
1. Step 1: Initiate OAuth → redirect to Xero
2. Step 2: Callback → redirect to `/clients/import?auth_event_id=X` → show configuration screen
3. Step 3: Submit selected orgs → redirect to `/clients/import/progress/{job_id}`
4. Step 4: Progress dashboard with real-time polling

**Rationale**: A dedicated page keeps the complexity isolated from the existing clients page. The wizard pattern matches user expectations for a multi-step import process. Polling (not WebSockets) for progress follows the existing pattern used for sync status updates throughout the app.

**Alternatives Considered**:
- **Modal/drawer on clients page**: Too much UI complexity to embed in the existing page.
- **WebSocket for real-time updates**: Over-engineered for this use case — 2-second polling is sufficient.
- **Server-Sent Events (SSE)**: Not widely used in the codebase; polling is simpler and proven.

### R6: Auto-Matching Strategy

**Decision**: Two-pass matching approach:
1. **Exact match**: Normalize both names (lowercase, strip "pty ltd", "pty", "ltd", leading/trailing whitespace) and compare.
2. **Fuzzy match**: Use simple token-set similarity (Jaccard similarity on word tokens) with a threshold of 0.8. Present fuzzy matches as "suggested" for user confirmation.

**Rationale**: Exact matching handles the majority case (80%+ per SC-004). Simple fuzzy matching catches common variations (e.g., "KR8 IT Pty Ltd" vs "KR8 IT") without requiring external dependencies. More sophisticated NLP matching is out of scope per the spec assumptions.

**Alternatives Considered**:
- **python-Levenshtein or fuzzywuzzy**: External dependency for marginal improvement.
- **ABN matching**: Would be definitive but XeroConnection doesn't always have ABN readily available from the `/connections` response.
- **AI-powered matching**: Over-engineered for this use case.

### R7: Subscription Limit Enforcement

**Decision**: Check the tenant's available client slots (tier limit - current client count) before the configuration screen. If the number of new orgs exceeds available slots, show the limit on the configuration screen and disable excess checkboxes. Allow the user to select which orgs to import within their limit.

**Rationale**: Checking before import (not during) provides a better user experience — the accountant sees the constraint upfront and chooses which clients to prioritize. The existing `BillingService.check_client_limit()` (called by `XeroSyncService.initiate_sync()`) provides the foundation.

**Alternatives Considered**:
- **Hard block at callback**: Too disruptive — the OAuth flow already completed, blocking wastes the authorization.
- **Import all, disable excess**: Creates connections that can't sync — confusing UX.
