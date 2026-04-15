# Research: 058-bas-workflow-tracker

**Date**: 2026-04-15  
**Branch**: `058-bas-workflow-tracker`

---

## Decision 1: Universal Client Entity Strategy

**Question**: Where should `assigned_user_id`, `notes`, and `accounting_software` live? The spec says "Client (extended)" but the codebase has two existing client-adjacent entities: `XeroConnection` (central to dashboard queries) and `XpmClient` (XPM-specific, not universal).

**Decision**: Create a new `PracticeClient` model as the universal practice management entity.

**Rationale**:
- `XeroConnection` is an integration record (OAuth tokens, sync state, rate limits). Adding practice management fields pollutes it.
- `XpmClient` is XPM-specific (has `xpm_client_id`, `xpm_updated_at`, `connection_status` for org matching). It doesn't exist for non-XPM Xero connections and would be a misleading home for non-Xero clients.
- A new `PracticeClient` creates a clean layer: one record per client the practice manages, with an optional FK to `XeroConnection` for Xero-connected clients. Non-Xero clients simply have `xero_connection_id = NULL`.
- Migration backfills: for every active `XeroConnection`, create a corresponding `PracticeClient` with `xero_connection_id` set and `accounting_software = 'xero'`.

**Alternatives considered**:
- *Add fields to XeroConnection*: Rejected — mixes integration and management concerns; doesn't work for non-Xero clients without ugly UNION queries.
- *Repurpose XpmClient*: Rejected — XpmClient has XPM-specific semantics and doesn't exist for all Xero connections; would require backfill AND removal of XPM coupling.
- *Separate ManualClient model + fields on XeroConnection*: Rejected — two client entity types means the dashboard needs UNION queries and all filters need to handle both.

---

## Decision 2: Dashboard Query Refactoring

**Question**: The dashboard currently queries `xero_connections` directly with LEFT JOINs to invoice/transaction subqueries. How do we integrate `PracticeClient` without breaking the existing data flow?

**Decision**: Refactor `DashboardRepository.list_connections_with_financials` to query from `practice_clients` LEFT JOIN `xero_connections`, then conditionally LEFT JOIN invoice/transaction subqueries (only when `xero_connection_id` is present).

**Rationale**:
- `PracticeClient` becomes the driving table. For Xero clients, the join to `xero_connections` provides the connection data needed for financial subqueries.
- For non-Xero clients, the `xero_connections` join returns NULL, and the financial subqueries return NULLs — these clients show zero financial data and manual BAS status.
- The `assigned_user_id` and exclusion filters can be applied directly on `practice_clients` in SQL, avoiding the current problem of Python-side post-filtering.
- Also refactors `get_status_counts` from the current approach (fetching 1000 rows then counting in Python) to a proper SQL COUNT/GROUP BY.

**Alternatives considered**:
- *Keep xero_connections as driving table, JOIN practice_clients*: Rejected — non-Xero clients (no XeroConnection) would be excluded.
- *Separate endpoints for Xero vs non-Xero clients*: Rejected — forces the frontend to merge two data sources; defeats the "single view" purpose.

---

## Decision 3: Exclusion Data Model

**Question**: Should exclusion be a flag on the client record or a separate junction table?

**Decision**: Separate `client_quarter_exclusions` table (client_id + quarter + fy_year).

**Rationale**:
- Per-quarter exclusion is a temporal relationship, not a client attribute. A flag on the client record would require quarterly cleanup.
- A junction table naturally supports: "excluded for Q3 but active for Q4", reversible exclusions, audit trail per exclusion, and reason tracking.
- Query pattern: LEFT JOIN `client_quarter_exclusions` for the selected quarter; WHERE exclusion IS NULL for the default view; WHERE exclusion IS NOT NULL for the "Excluded" filter.

**Alternatives considered**:
- *Boolean flag on PracticeClient*: Rejected — no per-quarter semantics; would need resetting every quarter.
- *Status field on BASSession*: Rejected — exclusion is a practice management decision about the client, not a BAS workflow state.

---

## Decision 4: BAS Status Derivation for Non-Xero Clients

**Question**: How does BAS status work for clients without Xero data?

**Decision**: Non-Xero clients get a `manual_status` field on `PracticeClient` (enum: not_started, in_progress, completed, lodged). This is displayed instead of the auto-derived BAS status.

**Rationale**:
- Auto-derived status requires invoice/transaction data from Xero. Non-Xero clients have no such data.
- A manual status lets accountants track progress for non-Xero clients without pretending the system can derive readiness.
- The dashboard column shows auto-derived status for Xero clients and manual status for non-Xero clients, unified into a single visual indicator.

**Alternatives considered**:
- *Always show "No Activity" for non-Xero clients*: Rejected — misleading; a non-Xero client could be actively worked on outside Clairo.
- *Create BASSession for non-Xero clients*: Rejected — BASSession is tightly coupled to BASPeriod → XeroConnection; too much refactoring for a display-only need.

---

## Decision 5: Reconciliation Signal in BAS Status

**Question**: How to incorporate unreconciled transaction count into the BAS status derivation?

**Decision**: Add an unreconciled transaction count subquery to the dashboard SQL and add a check in the Python BAS status derivation: if `unreconciled_count > 5` and status would otherwise be `READY`, downgrade to `NEEDS_REVIEW`.

**Rationale**:
- The `XeroBankTransaction.is_reconciled` field exists and is already indexed. A COUNT WHERE `is_reconciled = false` per connection for the quarter is efficient.
- The threshold (>5) is hardcoded as a sensible default per spec assumptions.
- Adding it to the existing Python derivation logic keeps the change minimal — one additional condition in the existing decision tree.

**Alternatives considered**:
- *SQL-only status derivation*: Rejected — would require rewriting the entire status derivation; too much risk for this feature.
- *Configurable threshold*: Rejected for this scope — adds UI complexity; can be added later if needed.

---

## Decision 6: Client Note History

**Question**: How to implement note change history for audit purposes?

**Decision**: Append-only `client_note_history` table with (client_id, note_text, edited_by, edited_at). On every note update, insert a new row before overwriting the current note on `PracticeClient`.

**Rationale**:
- Simple append-only pattern is easy to implement and query.
- Aligns with Clairo's audit-first approach — immutable history records.
- The current note lives on `PracticeClient.notes` for fast reads; history is only consulted for audit or recovery.

**Alternatives considered**:
- *JSONB array of versions on PracticeClient*: Rejected — harder to query for audit reports; grows the main record.
- *Reuse audit_logs table*: Could work but audit_logs has a broader schema; dedicated table is simpler to query for "show note history for client X".

---

## Decision 7: Module Placement

**Question**: Should this be a new module or extend the existing `clients` module?

**Decision**: Extend the existing `clients` module with new models, and update the `dashboard` module's repository/service/schemas.

**Rationale**:
- `PracticeClient`, `ClientQuarterExclusion`, and `ClientNoteHistory` are client entities — they belong in the clients module.
- The dashboard module owns the portfolio view — its query/schema changes belong there.
- No new module needed; this follows the modular monolith pattern of extending existing modules.

---

## Decision 8: Team Member Display Names

**Question**: `PracticeUser` has no `display_name` field. How to show team member names?

**Decision**: Fetch display names from Clerk on demand via the existing Clerk SDK integration. Cache on `PracticeUser` as `display_name` (nullable, updated on login or when fetched).

**Rationale**:
- Clerk is the source of truth for user identity. Names are available via the Clerk API.
- Caching on `PracticeUser` avoids repeated Clerk API calls for the dashboard (which shows assignee names for every row).
- The field is nullable — falls back to email when name hasn't been cached yet.
- Updated on login (when Clerk webhook fires) or on first display if null.

**Alternatives considered**:
- *Always show email*: Rejected — poor UX; "pawan@firm.com.au" is less scannable than "Pawan" in a busy triage list.
- *Call Clerk API per request*: Rejected — too slow for a 280-row dashboard; rate limits.
