# Research: Xero Tax Code Write-Back

**Branch**: `049-xero-taxcode-sync` | **Phase**: 0 — Research Output

---

## 1. Xero Write API Mechanics

### Decision
Use `POST /{DocumentType}/{ID}` (same verb as create) to update existing documents, sending the full `LineItems` array with only the target `TaxType` fields modified.

### Rationale
Xero's REST API uses POST for both create and update. The document ID in the path selects the existing record. Partial payloads are NOT supported — omitting a line item removes it from Xero. The full `line_items` JSONB stored on the local Xero entity models is used as the reconstruction base.

### Endpoints
| Document Type | Read | Write |
|--------------|------|-------|
| Invoice | `GET /Invoices/{InvoiceID}` | `POST /Invoices/{InvoiceID}` |
| Bank Transaction | `GET /BankTransactions/{BankTransactionID}` | `POST /BankTransactions/{BankTransactionID}` |
| Credit Note | `GET /CreditNotes/{CreditNoteID}` | `POST /CreditNotes/{CreditNoteID}` |

### Xero Request Header
All write calls require `Xero-Tenant-Id: {xero_tenant_id}` header, derived from `XeroConnection.xero_tenant_id`.

### Alternatives Considered
- **PATCH**: Not available for these Xero endpoints — Xero uses POST for idempotent updates.
- **Bulk POST**: Xero supports `POST /Invoices` with an array, but mixing update-by-ID semantics requires individual calls per document. Per-document approach is clearer and matches our one-call-per-document model.

---

## 2. Pre-Flight Editability Detection

### Decision
Two-phase approach:
1. **Deterministic pre-flight** (before attempting write): Check document status from the GET response — VOIDED, DELETED. Check `UpdatedDateUTC` against local `xero_updated_at` to detect conflict. Bank transactions check `IsReconciled`.
2. **Error-based detection** (during write): Period-locked invoices return Xero HTTP 400 with error code — catch and classify as `period_locked`.

### Rationale
Xero does not expose a universal `isLocked` boolean for all document types. Invoices in a locked period only reveal this on write attempt (HTTP 400 `The accounting period is locked`). Detecting VOIDED/DELETED pre-flight saves an unnecessary write call. For period-locked, the attempt + catch approach is the only reliable path.

### Conflict Detection Logic
```
GET Xero document → compare UpdatedDateUTC with local xero_updated_at
If Xero.UpdatedDateUTC > local.xero_updated_at → skip: conflict_changed
If status in (VOIDED, DELETED) → skip: voided / deleted
If BankTransaction.IsReconciled == True → skip: reconciled
If Invoice.Status == AUTHORISED and has allocated payments/credit notes → skip: authorised_locked
Attempt POST → catch HTTP 400 "period" error → skip: period_locked
Attempt POST → catch HTTP 400 "credit_note_applied" → skip: credit_note_applied
```

**Note**: The correct Xero field for reconciled bank transactions is `IsReconciled` (boolean), not `IsLocked`. `IsLocked` does not exist on bank transactions.

### AUTHORISED Invoice Restriction
Invoices in AUTHORISED status with payments or credit notes allocated against them cannot have line items modified. Xero returns HTTP 400 in this case. Detection strategy: attempt write, catch the specific 400 error message (`"Cannot modify line items on an invoice that has payments"`) and classify as `skip: authorised_locked`.

### Alternatives Considered
- **Skip pre-flight entirely, catch all errors**: Simpler but wastes API calls on known-bad documents, burning rate limit quota.
- **Xero's locked period endpoint**: Xero doesn't expose a dedicated period-lock query endpoint.
- **Pre-flight via `GET /Organisation`**: The org settings endpoint exposes `PeriodLockDate` and `EndOfYearLockDate`. This could allow deterministic period-lock detection before the write attempt. Rejected: adds 1 extra API call per writeback initiation (not per document), and the error-based detection (catch HTTP 400) is reliable and already implemented for the period-lock path. The `GET /Organisation` approach would only help if we wanted to batch-reject all items in a locked period upfront — not worth the complexity for typical BAS session sizes.

---

## 3. Rate Limiting Strategy

### Decision
Reuse existing `XeroRateLimiter` from `rate_limiter.py`. Process writeback items sequentially (not concurrently), sleeping between calls when needed. Store `rate_limit_minute_remaining` and `rate_limit_daily_remaining` on `XeroConnection` (already exists). Update from Xero response headers after each call.

### Rationale
`XeroRateLimiter` already implements: `can_make_request()`, `get_wait_time()`, `calculate_backoff()`, `update_from_headers()`, and `should_retry()`. The infrastructure is battle-tested from the sync pipeline. Sequential processing is appropriate since the rate limit is per-org, not per-connection — concurrent writes would collide on the same limit.

### Batch-per-Document Logic
Multiple overrides on the same Xero document are grouped into one API call (one `XeroWritebackItem`, multiple line item indexes). This minimises API call count.

### Alternatives Considered
- **Concurrent with semaphore**: More complex, risk of 429 storms. Not justified for typical BAS session sizes (≤50 documents).

---

## 4. Progress Reporting

### Decision
Use polling via `GET /writeback/jobs/{job_id}`. Frontend polls every 2 seconds while job is `in_progress`. `XeroWritebackJob.succeeded_count`, `skipped_count`, `failed_count`, and `total_count` are updated atomically after each item.

### Rationale
SSE (Server-Sent Events) would require a persistent HTTP connection. Polling at 2-second intervals is adequate for this use case (sync typically completes in < 2 minutes, 30 items = ~30 seconds). Consistent with existing sync progress patterns in `sync_progress.py`.

### Alternatives Considered
- **SSE**: More responsive but adds infra complexity and requires long-lived connections.
- **WebSocket**: Overkill for a one-way status stream.

---

## 5. Celery vs. Synchronous Execution

### Decision
Execute writeback as a **Celery task** (`tasks/xero_writeback.py`). The API endpoint creates the job record and enqueues the task, returning immediately with the job ID. Frontend polls for progress.

### Rationale
Writeback can take 30-60+ seconds. A synchronous endpoint would time out at the API gateway (30s typical). Celery is already used for long-running operations (Xero sync). The task must be idempotent: it checks each `XeroWritebackItem.status` before processing, so a retry does not double-write.

### Token Refresh During Task
The Celery task checks token expiry before each write. If `XeroConnection.token_expires_at` is within 5 minutes, the task refreshes the token using `XeroClient.refresh_token()` and saves the new tokens before continuing. If refresh fails, remaining items are marked `failed` with reason `auth_error` and the job transitions to `failed`.

---

## 6. Where New Models Live

### Decision
- `XeroWritebackJob` and `XeroWritebackItem` → `backend/app/modules/integrations/xero/writeback_models.py` (new file in Xero module)
- `AgentTransactionNote` and `ClientClassificationRound` → `backend/app/modules/bas/classification_models.py` (append to existing file)
- `TaxCodeOverride.writeback_status` → alter existing model in `backend/app/modules/bas/models.py`
- `ClassificationRequest.parent_request_id` + `.round_number` → alter existing model in `backend/app/modules/bas/classification_models.py`

### Rationale
Writeback models belong to the Xero integration domain — they reference Xero document IDs and connection credentials. Classification models belong to the BAS domain. Keeping them separate maintains module boundary integrity.

---

## 7. Send-Back Flow Architecture

### Decision
`POST /bas/sessions/{session_id}/classification-requests/{request_id}/send-back` creates a **new** `ClassificationRequest` linked to the original via `parent_request_id`, scoped to only the returned items. A new magic link is generated and emailed.

### Round Tracking
- `ClassificationRequest.round_number`: starts at 1, incremented on each send-back
- `ClientClassificationRound`: records the conversation thread for each transaction across rounds (original response → agent comment → revised response)

### Per-Transaction Agent Notes
`AgentTransactionNote` is created when the agent adds a note to an item on initial send OR on a send-back. The `is_send_back_comment` flag differentiates context notes (initial) from guidance notes (send-back).

---

## 8. Portal Validation Enforcement

### Decision
- "I don't know" description: enforced **client-side** (disable proceed) AND **server-side** (400 if `client_needs_help=true` and `client_description` is null/empty).
- All-questions gate: enforced **client-side** (disable submit button, show counter) AND **server-side** (400 if any transaction in the request has no `classified_at`).

### Rationale
Defense-in-depth. Client-side UX prevents accidental submission. Server-side validation ensures integrity even if JS is bypassed. Consistent with spec assumption: "enforced client-side for UX and server-side for integrity."

---

## 9. Audit Trail Integration

### Decision
All writeback events use the existing `audit_event()` function from `app.core.audit`. Events are defined as constants in `backend/app/modules/integrations/xero/audit_events.py` (extend existing file). Classification send-back events use the BAS module's audit events file.

### Events Defined
See Auditing Checklist in spec. Eight events required, four for writeback and two for classification workflow.

---

## 10. Idempotency for Writeback

### Decision
`XeroWritebackItem` has a unique constraint on `(job_id, source_type, xero_document_id)`. Before processing an item, check `status != success`. On retry, only items with `status = failed` are reprocessed. Items with `status = success` or `status = skipped` are never reprocessed in subsequent jobs for the same session unless a new override has been approved after the previous sync.

### Re-sync Guard (FR-009)
When initiating a new writeback job for a session, the service queries `TaxCodeOverride` records where `writeback_status = pending_sync` (excludes already-synced). This prevents re-syncing items that were successfully written in a prior job.

---

## 11. Tax Type Validation

### Decision
Before queuing writeback items, call `GET /TaxRates` for the connected organisation and validate each `override_tax_type` against the active tax codes returned. Raise `WritebackError("invalid_tax_type")` for any unrecognised code.

### Rationale
Xero organisations can have custom tax rates beyond the standard Australian codes. Hardcoding a list would silently fail for any org with non-standard rates. The `GET /TaxRates` call costs 1 API call per writeback initiation (not per item) — acceptable overhead. This catches the "TaxType code cannot be used with account code" class of errors before they burn write calls.

### Alternatives Considered
- **Hardcode standard Australian codes**: Fragile for multi-org deployments; explicitly warned against in Xero documentation.
- **Let Xero reject on write**: Possible fallback — the HTTP 400 would be caught by T027 — but wastes one API call per affected document and gives a less clear user-facing error message.

---

## 12. Xero API-Level Idempotency

### Decision
Pass `idempotencyKey: str(XeroWritebackItem.id)` as a request header on every Xero write call.

### Rationale
Celery tasks can be retried (network failure, worker restart). Without an idempotency key, a retry could write the same TaxType change twice — Xero would still return 200 but could produce double audit entries or unexpected state if Xero's behaviour changes. Using the stable `XeroWritebackItem.id` as the key ensures Xero deduplicates at the API level as a second layer of protection beyond the DB-level `status != success` check.

### Alternatives Considered
- **DB-only idempotency (current approach)**: Sufficient for most cases but does not protect against the window between the Xero write call succeeding and the DB status update completing (process kill mid-write).

---

## 13. Line Item Display — Grouping Strategy

### Decision
Group `TaxCodeSuggestion` records by `source_id` in `TaxCodeResolutionPanel` before rendering. Each group becomes a `TransactionGroup`:
- **Single suggestion at index 0, no pending splits** → render existing `TaxCodeSuggestionCard` unchanged (no visual change for single-line transactions).
- **Multiple suggestions OR agent-defined splits exist** → render a collapsible parent row (date, total amount, contact name) with child `TaxCodeSuggestionCard` rows per line item.

### Rationale
The AI pipeline already generates one `TaxCodeSuggestion` per line item (iterates `line_items` with index in `bas/service.py`). `TaxCodeSuggestion` already carries `line_item_index` and `line_amount` in the frontend type. No backend change is needed to surface this data — only the frontend rendering needs to group by `source_id`.

---

## 14. Split Storage — Extend `TaxCodeOverride`

### Decision
Add four nullable columns to `tax_code_overrides`:
- `line_amount` NUMERIC(15,2) — amount for this line item slot; null = keep existing Xero amount
- `line_description` TEXT — description for this slot; null = keep existing
- `line_account_code` VARCHAR(50) — account code; null = keep existing
- `is_new_split` BOOLEAN DEFAULT FALSE — when true, this override inserts a new line item at `line_item_index` rather than patching an existing one

`suggestion_id` is already nullable on `TaxCodeOverride` — no change needed. Agent-created splits simply omit the FK.

### Rationale
Avoids a new table. All split definition lives on the override record already processed by the write-back pipeline. The unique partial index `(connection_id, source_type, source_id, line_item_index) WHERE is_active` already ensures one active override per slot.

### Balance Constraint
Enforced server-side on split create/update: `SELECT SUM(line_amount) FROM tax_code_overrides WHERE source_id = ? AND is_active = true AND line_amount IS NOT NULL`. If this sum ≠ transaction total, raise a 422. The writeback task re-validates before queuing any document that has `is_new_split=True` overrides.

---

## 15. `apply_overrides_to_line_items` — Two-Mode Extension

### Decision
Extend the function to handle `is_new_split`:

**Override mode** (`is_new_split=False`, existing behaviour): deep-copy existing items, patch `TaxType`, optionally set `LineAmount`/`Description`/`AccountCode` from non-null override fields, pop `TaxAmount`.

**Split mode** (`is_new_split=True`): after applying all override-mode patches, insert new entries into the reconstructed array for each new-split override ordered by `line_item_index`. New entries carry `TaxType`, `LineAmount`, and optionally `Description`/`AccountCode`. `TaxAmount` is omitted.

The function signature gains `validate_balance: bool = False`. When `True`, after reconstruction it checks `sum(item["LineAmount"] for item in result) == expected_total`; raises `ValueError("split_amount_mismatch")` if not balanced.

### Alternatives Considered
- Separate function for split-mode: rejected as unnecessary indirection — the two modes share the same reconstruction loop and return contract.

---

## 16. Split Creation API

### Decision
New endpoint: `POST /api/v1/bas/sessions/{session_id}/bank-transactions/{source_id}/splits`

Body: `{ line_item_index, override_tax_type, line_amount, line_description?, line_account_code? }`

Sets `is_new_split=True`, `suggestion_id=null`. Returns the created `TaxCodeOverride`.

Additional endpoints:
- `PATCH /splits/{override_id}` — update amount, tax type, description, account code
- `DELETE /splits/{override_id}` — deactivate (`is_active=False`); triggers balance re-validation for remaining splits

All three endpoints perform balance validation after write and return 422 with `"split_amount_mismatch"` if unbalanced.

### Scope Constraint
Split creation is bank transactions only (FR-034). Invoices and credit notes are read-only structure in Clairo.

---

## 17. "Pending Split" Visual State

### Decision
Agent-defined splits not yet synced to Xero show an amber "Pending" badge on the line item child row (distinct from the Xero sync status badges: "Xero ✓", "⚠ Skipped", "Xero ✗"). Once synced, the badge is replaced by "Xero ✓".

The parent `TransactionGroup` row shows an aggregate indicator:
- All line items resolved + synced → "Xero ✓"
- Any line item syncing → "Syncing…"
- Any pending splits not yet synced → "Pending split"
- Any failed items → "Xero ✗ (N)"
