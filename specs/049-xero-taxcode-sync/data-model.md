# Data Model: Xero Tax Code Write-Back

**Branch**: `049-xero-taxcode-sync` | **Phase**: 1 — Data Model

---

## Overview

This feature introduces 4 new tables and modifies 2 existing tables. The line item / split management update (2026-04-07) adds 4 further nullable columns to `tax_code_overrides` and extends the write-back pipeline to support agent-defined splits. Changes span two modules: `integrations/xero` (writeback job tracking) and `bas` (classification workflow extensions).

---

## New Tables

### `xero_writeback_jobs`

Represents one "Sync to Xero" invocation triggered by a tax agent.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `tenant_id` | UUID NOT NULL | RLS enforced |
| `connection_id` | UUID NOT NULL | FK → `xero_connections` |
| `session_id` | UUID NOT NULL | FK → `bas_sessions` |
| `triggered_by` | UUID NOT NULL | FK → `practice_users` |
| `status` | VARCHAR(20) NOT NULL | `pending \| in_progress \| completed \| failed \| partial` |
| `total_count` | INTEGER DEFAULT 0 | Total items queued |
| `succeeded_count` | INTEGER DEFAULT 0 | Written to Xero |
| `skipped_count` | INTEGER DEFAULT 0 | Not editable |
| `failed_count` | INTEGER DEFAULT 0 | Unexpected errors |
| `started_at` | TIMESTAMPTZ | Set when task begins |
| `completed_at` | TIMESTAMPTZ | Set when all items processed |
| `duration_seconds` | INTEGER | Computed on completion |
| `error_detail` | TEXT | Top-level error (e.g. auth failure) |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | |

**Indexes**: `(tenant_id, session_id)`, `(tenant_id, status)` where status != 'completed'

**Enums** (stored as VARCHAR):
```python
class XeroWritebackJobStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"  # some succeeded, some failed
```

---

### `xero_writeback_items`

One item per Xero document updated within a writeback job.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `tenant_id` | UUID NOT NULL | RLS enforced |
| `job_id` | UUID NOT NULL | FK → `xero_writeback_jobs` |
| `source_type` | VARCHAR(30) NOT NULL | `invoice \| bank_transaction \| credit_note` |
| `xero_document_id` | VARCHAR(255) NOT NULL | Xero's document UUID |
| `local_document_id` | UUID NOT NULL | FK to XeroInvoice / XeroBankTransaction / XeroCreditNote |
| `override_ids` | UUID[] NOT NULL | Array of TaxCodeOverride IDs included |
| `line_item_indexes` | INTEGER[] NOT NULL | Which line items changed |
| `before_tax_types` | JSONB NOT NULL | `{index: original_tax_type}` per changed line item |
| `after_tax_types` | JSONB NOT NULL | `{index: new_tax_type}` per changed line item |
| `status` | VARCHAR(20) NOT NULL DEFAULT 'pending' | `pending \| in_progress \| success \| skipped \| failed` |
| `skip_reason` | VARCHAR(50) | `voided \| deleted \| period_locked \| reconciled \| conflict_changed \| credit_note_applied` |
| `error_detail` | TEXT | Xero error message on failure |
| `xero_http_status` | INTEGER | HTTP status from Xero response |
| `processed_at` | TIMESTAMPTZ | When this item was attempted |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | |

**Unique constraint**: `(job_id, source_type, xero_document_id)`

**Indexes**: `(tenant_id, job_id)`, `(tenant_id, status)` where status = 'failed'

**Enums**:
```python
class XeroWritebackItemStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"

class XeroWritebackSkipReason(str, Enum):
    VOIDED = "voided"
    DELETED = "deleted"
    PERIOD_LOCKED = "period_locked"
    RECONCILED = "reconciled"
    CONFLICT_CHANGED = "conflict_changed"
    CREDIT_NOTE_APPLIED = "credit_note_applied"
```

---

### `agent_transaction_notes`

Per-transaction notes added by the tax agent when sending or reviewing a classification request.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `tenant_id` | UUID NOT NULL | RLS enforced |
| `request_id` | UUID NOT NULL | FK → `classification_requests` |
| `source_type` | VARCHAR(30) NOT NULL | `invoice \| bank_transaction \| credit_note` |
| `source_id` | UUID NOT NULL | Local doc ID |
| `line_item_index` | INTEGER NOT NULL | Which line item |
| `note_text` | TEXT NOT NULL | Agent's note |
| `is_send_back_comment` | BOOLEAN NOT NULL DEFAULT FALSE | False = context note on initial send; True = guidance on send-back |
| `created_by` | UUID NOT NULL | FK → `practice_users` |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | |

**Indexes**: `(tenant_id, request_id)`, `(request_id, source_type, source_id, line_item_index)`

---

### `client_classification_rounds`

Tracks the per-transaction conversation thread across multiple rounds of send-back.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `tenant_id` | UUID NOT NULL | RLS enforced |
| `session_id` | UUID NOT NULL | FK → `bas_sessions` |
| `source_type` | VARCHAR(30) NOT NULL | |
| `source_id` | UUID NOT NULL | |
| `line_item_index` | INTEGER NOT NULL | |
| `round_number` | INTEGER NOT NULL | 1 = initial, 2+ = send-back |
| `request_id` | UUID NOT NULL | FK → `classification_requests` (the round's request) |
| `agent_comment` | TEXT | Agent's comment for this round (null for round 1) |
| `client_response_category` | VARCHAR(100) | What client selected |
| `client_response_description` | TEXT | Client's description |
| `client_needs_help` | BOOLEAN DEFAULT FALSE | "I don't know" selected |
| `responded_at` | TIMESTAMPTZ | When client submitted |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | |

**Indexes**: `(tenant_id, session_id, source_type, source_id, line_item_index)`, `(tenant_id, request_id)`

---

## Modified Tables

### `tax_code_overrides` — Add `writeback_status` + Split Columns

```sql
ALTER TABLE tax_code_overrides
ADD COLUMN writeback_status VARCHAR(20) NOT NULL DEFAULT 'pending_sync',
ADD COLUMN line_amount NUMERIC(15,2),
ADD COLUMN line_description TEXT,
ADD COLUMN line_account_code VARCHAR(50),
ADD COLUMN is_new_split BOOLEAN NOT NULL DEFAULT FALSE;
```

| New Column | Type | Notes |
|------------|------|-------|
| `writeback_status` | VARCHAR(20) DEFAULT `pending_sync` | `pending_sync \| synced \| skipped \| failed` |
| `line_amount` | NUMERIC(15,2) nullable | When set: the `LineAmount` to write for this line item. Null = keep existing Xero amount. Required for all `is_new_split=True` records. |
| `line_description` | TEXT nullable | Optional description override. Null = keep existing. |
| `line_account_code` | VARCHAR(50) nullable | Optional account code override. Null = keep existing. |
| `is_new_split` | BOOLEAN NOT NULL DEFAULT FALSE | `true` → insert a new line item at `line_item_index`; `false` → patch existing line item at that index. |

**Enum**:
```python
class TaxCodeOverrideWritebackStatus(str, Enum):
    PENDING_SYNC = "pending_sync"
    SYNCED = "synced"
    SKIPPED = "skipped"
    FAILED = "failed"
```

**Behaviour on successful write**:
- `writeback_status` → `synced`
- `is_active` → `false` (Xero is now source of truth; no local divergence remains)

**Balance constraint** (server-side, enforced on split create/update/delete):
```python
# Sum of line_amount for all active overrides on the same source_id
# where line_amount IS NOT NULL must equal the transaction's total_amount.
SELECT SUM(line_amount) FROM tax_code_overrides
WHERE source_id = :source_id AND is_active = true AND line_amount IS NOT NULL;
```
Returns 422 `{"detail": "split_amount_mismatch"}` if unbalanced.

**Unique partial index** (existing, unchanged):
```sql
UNIQUE (connection_id, source_type, source_id, line_item_index) WHERE is_active = true
```
This still works correctly for splits: each new split occupies a distinct `line_item_index`.

---

### `classification_requests` — Add `parent_request_id` and `round_number`

```sql
ALTER TABLE classification_requests
ADD COLUMN parent_request_id UUID REFERENCES classification_requests(id) ON DELETE SET NULL,
ADD COLUMN round_number INTEGER NOT NULL DEFAULT 1;
```

| New Column | Type | Notes |
|------------|------|-------|
| `parent_request_id` | UUID nullable | FK → `classification_requests.id` (self-referential, SET NULL on delete) |
| `round_number` | INTEGER NOT NULL DEFAULT 1 | 1 = initial, 2+ = each send-back |

**Constraint**: `(session_id)` unique constraint from 047 must be relaxed — a session can now have multiple requests (one per round). **Remove** the existing `UNIQUE (session_id)` constraint and replace with: `UNIQUE (session_id, round_number)` where `parent_request_id IS NULL` (only one root per session) or use a partial unique index.

**Migration note**: Existing records from spec 047 all have `round_number = 1` and `parent_request_id = NULL`. The unique constraint change must be applied as a migration step.

---

## Entity Relationships (ERD Summary)

```
BASSession ──────────────────────────────┐
  │                                       │
  ├── TaxCodeSuggestion[]                 │
  ├── TaxCodeOverride[] ──(writeback_status) │
  │       │                              │
  │       └── XeroWritebackItem[] ────── XeroWritebackJob
  │                                       │
  └── ClassificationRequest ─────────────┘
        │ (parent_request_id self-ref)
        ├── ClassificationRequest (round 2+)
        ├── ClientClassification[]
        ├── AgentTransactionNote[]
        └── ClientClassificationRound[]

XeroConnection ── XeroWritebackJob
  ├── XeroInvoice ── (source for writeback)
  ├── XeroBankTransaction
  └── XeroCreditNote
```

---

## New Service Interfaces

### `XeroWritebackService` (new file: `writeback_service.py`)

```python
async def initiate_writeback(
    session_id: UUID, triggered_by: UUID, tenant_id: UUID, db: AsyncSession
) -> XeroWritebackJob
# Creates job record, enqueues Celery task

async def get_job(
    job_id: UUID, tenant_id: UUID, db: AsyncSession
) -> XeroWritebackJob

async def get_latest_job_for_session(
    session_id: UUID, tenant_id: UUID, db: AsyncSession
) -> XeroWritebackJob | None

async def retry_failed_items(
    job_id: UUID, triggered_by: UUID, tenant_id: UUID, db: AsyncSession
) -> XeroWritebackJob
# Creates new job with only failed items from previous job
```

### `ClassificationSendBackService` (extends `classification_service.py`)

```python
async def send_items_back(
    request_id: UUID,
    item_ids: list[UUID],
    agent_comments: dict[UUID, str],  # item_id → comment
    triggered_by: UUID,
    tenant_id: UUID,
    db: AsyncSession,
) -> ClassificationRequest
# Creates new round request, issues new magic link, sends email

async def get_classification_thread(
    session_id: UUID,
    source_type: str,
    source_id: UUID,
    line_item_index: int,
    tenant_id: UUID,
    db: AsyncSession,
) -> list[ClientClassificationRound]
# Returns full conversation history for a transaction
```

---

## Celery Task Interface

### `tasks/xero_writeback.py`

```python
@celery_app.task(bind=True, max_retries=0, name="xero.writeback.process_job")
async def process_writeback_job(self, job_id: str, tenant_id: str) -> None:
    """
    Processes all pending XeroWritebackItems in a job sequentially.

    Steps per item:
    1. Check TaxCodeOverride records for this document group
    2. GET document from Xero (pre-flight check)
    3. Detect editability (VOIDED, DELETED, conflict_changed, IsReconciled, authorised_locked)
    4. Reconstruct full line_items payload with tax type changes applied
    5. POST to Xero, handle rate limiting, catch period_locked errors
    6. Update XeroWritebackItem.status + XeroWritebackJob counts
    7. If success: update TaxCodeOverride.writeback_status = synced, is_active = false
    8. If success: update local XeroInvoice/BankTransaction/CreditNote.line_items
    9. Emit audit event
    10. Refresh OAuth token if needed before next item
    """
```

---

## Migration Files Required

```
backend/app/migrations/versions/
├── xxxx_add_xero_writeback_tables.py
│   - Creates: xero_writeback_jobs, xero_writeback_items
├── xxxx_add_tax_code_override_writeback_status.py
│   - ALTER: tax_code_overrides ADD COLUMN writeback_status
├── xxxx_extend_classification_requests_for_sendback.py
│   - ALTER: classification_requests ADD COLUMN parent_request_id, round_number
│   - DROP UNIQUE (session_id), ADD UNIQUE (session_id, round_number) partial
├── xxxx_add_agent_transaction_notes.py
│   - Creates: agent_transaction_notes
├── xxxx_add_client_classification_rounds.py
│   - Creates: client_classification_rounds
└── xxxx_add_tax_code_override_split_columns.py
    - ALTER: tax_code_overrides ADD COLUMN line_amount, line_description,
             line_account_code, is_new_split
    (Can be combined with writeback_status migration if not yet run)
```

---

## Split Management Service Interface

### `SplitService` (new methods on `TaxCodeService` or a standalone helper)

```python
async def create_split_override(
    session_id: UUID,
    source_id: UUID,       # XeroBankTransaction local PK
    line_item_index: int,
    override_tax_type: str,
    line_amount: Decimal,
    line_description: str | None,
    line_account_code: str | None,
    applied_by: UUID,
    tenant_id: UUID,
    db: AsyncSession,
) -> TaxCodeOverride
# Creates override with is_new_split=True, validates balance after insert.

async def update_split_override(
    override_id: UUID,
    line_amount: Decimal | None,
    override_tax_type: str | None,
    line_description: str | None,
    line_account_code: str | None,
    tenant_id: UUID,
    db: AsyncSession,
) -> TaxCodeOverride
# Updates fields, re-validates balance.

async def delete_split_override(
    override_id: UUID,
    tenant_id: UUID,
    db: AsyncSession,
) -> None
# Sets is_active=False, re-validates balance for remaining splits.

async def get_splits_for_transaction(
    source_id: UUID,
    tenant_id: UUID,
    db: AsyncSession,
) -> list[TaxCodeOverride]
# Returns all active overrides (both is_new_split=True and False) for a source_id,
# ordered by line_item_index.
```

### `apply_overrides_to_line_items` — Updated Signature

```python
def apply_overrides_to_line_items(
    line_items: list[dict[str, Any]],
    overrides: list[TaxCodeOverride],
    validate_balance: bool = False,
    expected_total: Decimal | None = None,
) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, str]]:
    """
    Two modes per override:
    - is_new_split=False: patch TaxType (+ optional LineAmount/Description/AccountCode)
      on existing item at line_item_index
    - is_new_split=True: insert new entry at line_item_index in the reconstructed array

    If validate_balance=True and expected_total is provided:
    - After reconstruction, asserts sum(LineAmount) == expected_total
    - Raises ValueError("split_amount_mismatch") if not balanced
    """
```
