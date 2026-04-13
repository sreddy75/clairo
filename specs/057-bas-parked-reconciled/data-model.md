# Data Model: BAS Transaction Grouping by Xero Reconciliation Status

**Branch**: `057-bas-parked-reconciled` | **Date**: 2026-04-13

---

## Schema Changes

### `tax_code_suggestions` — Two New Columns

```sql
ALTER TABLE tax_code_suggestions
  ADD COLUMN is_reconciled    BOOLEAN     NULL,
  ADD COLUMN auto_park_reason VARCHAR(50) NULL;
```

**`is_reconciled`**
- `NULL` for non-bank-transaction source types (invoices, credit notes)
- `True` / `False` for `source_type = 'bank_transaction'`, mirroring `xero_bank_transactions.is_reconciled` at suggestion-generation time
- Updated by the reconciliation refresh endpoint

**`auto_park_reason`**
- `NULL` for all suggestions that were not auto-parked by the system
- `'unreconciled_in_xero'` when the system auto-parks a suggestion because `is_reconciled = False`
- Cleared to `NULL` when a refresh reclassifies an auto-parked suggestion back to `pending`
- Never set by accountant actions — distinguishes system-initiated parks from manual ones

**No other schema changes.** `XeroBankTransaction.is_reconciled` already exists.

---

## SQLAlchemy Model Additions

```python
# backend/app/modules/bas/models.py — TaxCodeSuggestion additions

is_reconciled: Mapped[bool | None] = mapped_column(
    Boolean, nullable=True, default=None
)
auto_park_reason: Mapped[str | None] = mapped_column(
    String(50), nullable=True, default=None
)
```

---

## Entity State Transitions

### `TaxCodeSuggestion.status` — Updated State Machine

```
                    ┌──────────────────────────────────────────────┐
                    │ generate_suggestions()                        │
                    │ bank_transaction + is_reconciled=False        │
                    │ → status="dismissed"                          │
                    │ → auto_park_reason="unreconciled_in_xero"     │
                    └────────────────────┬─────────────────────────┘
                                         │ auto-park
                                         ▼
[pending] ←───────────────── [dismissed / auto_park_reason set]
    │    unpark (reconciled)         │
    │    (refresh moves it back)     │ unpark (manual)
    │                                ▼
    │                      [dismissed / auto_park_reason=NULL]
    │                          (manually parked — stays put)
    │
    ├──approve──► [approved]
    ├──override─► [overridden]
    └──dismiss──► [dismissed / auto_park_reason=NULL]
```

### Auto-Park vs Manual Park — Distinguishing Rules

| Condition | Meaning |
|-----------|---------|
| `status='dismissed'` AND `auto_park_reason='unreconciled_in_xero'` | Auto-parked by system; eligible for reclassification on refresh |
| `status='dismissed'` AND `auto_park_reason IS NULL` | Manually parked by accountant; refresh never touches this row |
| `status IN ('approved', 'overridden')` | Accountant has acted; refresh never changes this row |

---

## Data Access Patterns

### Suggestion List Query — New `is_reconciled` Filter

```python
# repository.py — list_suggestions() extended filters
async def list_suggestions(
    self,
    session_id: UUID,
    tenant_id: UUID,
    status: list[str] | None = None,
    is_reconciled: bool | None = None,   # NEW
    ...
) -> list[TaxCodeSuggestion]:
    ...
    if is_reconciled is not None:
        q = q.where(TaxCodeSuggestion.is_reconciled == is_reconciled)
```

### Reconciliation Refresh Query

```python
# Two-step: fetch current is_reconciled from XeroBankTransaction, then update

# Step 1 — get all bank_transaction source_ids for this session
source_ids = await repo.get_bank_transaction_source_ids(session_id, tenant_id)
# → SELECT DISTINCT source_id FROM tax_code_suggestions
#   WHERE session_id=? AND tenant_id=? AND source_type='bank_transaction'

# Step 2 — fetch current is_reconciled from XeroBankTransaction
# via XeroIntegrationService or direct cross-module service call
reconciled_map: dict[UUID, bool] = await xero_service.get_reconciliation_status_map(
    connection_id, source_ids
)
# → SELECT xero_transaction_id, is_reconciled FROM xero_bank_transactions
#   WHERE connection_id=? AND xero_transaction_id = ANY(?)

# Step 3 — apply changes (repository method)
await bas_repo.apply_reconciliation_refresh(session_id, tenant_id, reconciled_map)
```

### `apply_reconciliation_refresh` Logic (repository)

```python
async def apply_reconciliation_refresh(
    self,
    session_id: UUID,
    tenant_id: UUID,
    reconciled_map: dict[str, bool],  # xero_transaction_id -> is_reconciled
) -> int:  # returns count of reclassified suggestions
    reclassified = 0
    for xero_id, is_reconciled in reconciled_map.items():
        # Fetch matching suggestions
        suggestions = await self._get_suggestions_by_source(
            session_id, tenant_id, "bank_transaction", xero_id
        )
        for s in suggestions:
            if s.is_reconciled == is_reconciled:
                continue  # no change
            s.is_reconciled = is_reconciled
            if is_reconciled and s.auto_park_reason == "unreconciled_in_xero":
                # Newly reconciled + was auto-parked → move back to pending
                s.status = "pending"
                s.auto_park_reason = None
                reclassified += 1
            elif not is_reconciled and s.status == "pending" and s.auto_park_reason is None:
                # Newly unreconciled + still pending + not manually parked → auto-park
                s.status = "dismissed"
                s.auto_park_reason = "unreconciled_in_xero"
                reclassified += 1
    await self.db.flush()
    return reclassified
```

---

## Migration

```
backend/app/alembic/versions/20260413_add_reconciliation_fields_to_suggestions.py
```

```python
def upgrade():
    op.add_column(
        "tax_code_suggestions",
        sa.Column("is_reconciled", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "tax_code_suggestions",
        sa.Column("auto_park_reason", sa.String(50), nullable=True),
    )
    # Index for the new "Reconciled" accordion section filter
    op.create_index(
        "ix_tax_code_suggestions_session_reconciled",
        "tax_code_suggestions",
        ["session_id", "is_reconciled"],
    )

def downgrade():
    op.drop_index("ix_tax_code_suggestions_session_reconciled")
    op.drop_column("tax_code_suggestions", "auto_park_reason")
    op.drop_column("tax_code_suggestions", "is_reconciled")
```

---

## Existing Data (Migration Safety)

Existing `tax_code_suggestions` rows will have `is_reconciled = NULL` and `auto_park_reason = NULL` after migration. This is safe:
- `NULL` is treated as "unknown" — these suggestions are not auto-parked retroactively.
- The Reconciled section will only show suggestions where `is_reconciled = True`. Existing rows with `NULL` are unaffected and stay in their current bucket.
- When `generate_suggestions` is next run for a session, new rows will get the correct `is_reconciled` value.
