# Data Model: BAS Compliance Fixes & Data Accuracy

**Branch**: `062-bas-compliance-fixes` | **Date**: 2026-04-24

---

## Schema Changes (Migrations Required)

### 1. `practice_clients` — Add GST Reporting Basis

```sql
ALTER TABLE practice_clients
  ADD COLUMN gst_reporting_basis VARCHAR(10) NULL
    CHECK (gst_reporting_basis IN ('cash', 'accrual'));

ALTER TABLE practice_clients
  ADD COLUMN gst_basis_updated_at TIMESTAMPTZ NULL;

ALTER TABLE practice_clients
  ADD COLUMN gst_basis_updated_by UUID NULL REFERENCES practice_users(id);
```

**Model update** (`backend/app/modules/clients/models.py` — `PracticeClient`):
```python
gst_reporting_basis: Mapped[str | None] = mapped_column(String(10), nullable=True)
gst_basis_updated_at: Mapped[datetime | None] = mapped_column(nullable=True)
gst_basis_updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("practice_users.id"), nullable=True)
```

**Semantics**: `NULL` = not yet set → system MUST prompt accountant before loading BAS figures. `"cash"` or `"accrual"` = saved preference.

---

### 2. `bas_sessions` — Snapshot Basis Used

```sql
ALTER TABLE bas_sessions
  ADD COLUMN gst_basis_used VARCHAR(10) NULL
    CHECK (gst_basis_used IN ('cash', 'accrual'));
```

**Model update** (`backend/app/modules/bas/models.py` — `BASSession`):
```python
gst_basis_used: Mapped[str | None] = mapped_column(String(10), nullable=True)
```

**Semantics**: Snapshotted at the time of calculation. Immutable after lodgement (enforced in service layer). Provides ATO audit trail of which basis was used for each BAS period.

---

### 3. `bas_calculations` — Add PAYG Instalment Fields

```sql
ALTER TABLE bas_calculations
  ADD COLUMN t1_instalment_income NUMERIC(15, 2) NULL,
  ADD COLUMN t2_instalment_rate   NUMERIC(8, 5)  NULL;
```

**Model update** (`backend/app/modules/bas/models.py` — `BASCalculation`):
```python
# PAYG Instalment (T1/T2) — manual entry for quarterly BAS filers
t1_instalment_income: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
t2_instalment_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 5), nullable=True)
```

**Derived field** (not stored — computed in service):
- `t_instalment_payable = t1_instalment_income * t2_instalment_rate` (if both present)

---

## No New Tables Required

All changes are additive columns on existing tables. No new tables, no new join tables, no schema restructuring.

---

## Entity Reference

### PracticeClient (updated)

| Field | Type | Nullable | Notes |
|-------|------|----------|-------|
| `id` | UUID | No | PK |
| `name` | String | No | Business name |
| `abn` | String(11) | Yes | Australian Business Number |
| `gst_reporting_basis` | String(10) | Yes | `'cash'` \| `'accrual'` \| NULL (not set) |
| `gst_basis_updated_at` | Timestamptz | Yes | When basis was last changed |
| `gst_basis_updated_by` | UUID FK | Yes | Which accountant changed it |
| *(existing fields)* | | | |

### BASSession (updated)

| Field | Type | Nullable | Notes |
|-------|------|----------|-------|
| `id` | UUID | No | PK |
| `gst_basis_used` | String(10) | Yes | Snapshot of basis at calculation time |
| *(existing fields)* | | | |

### BASCalculation (updated)

| Field | Type | Nullable | Notes |
|-------|------|----------|-------|
| `id` | UUID | No | PK |
| `w1_total_wages` | Numeric(15,2) | No | Existing — total wages |
| `w2_amount_withheld` | Numeric(15,2) | No | Existing — PAYG withheld |
| `t1_instalment_income` | Numeric(15,2) | Yes | New — manual entry |
| `t2_instalment_rate` | Numeric(8,5) | Yes | New — manual entry (e.g. 0.04 = 4%) |
| *(existing fields)* | | | |

---

## State Transitions

### GST Basis Preference

```
NULL (not set)
  → [accountant selects basis on BAS open] → 'cash' | 'accrual'
  → [accountant changes basis] → 'cash' | 'accrual'  (with double-confirm if session lodged)
```

### BAS Session Basis (immutable after lodge)

```
NULL
  → [calculation triggered] → 'cash' | 'accrual'  (copied from client preference)
  → [lodged] → LOCKED (service enforces; basis_used is read-only post-lodgement)
  → [post-lodgement change allowed with double-confirm] → updates client preference only;
                                                          session snapshot remains unchanged
```

---

## Frontend State

### New Zustand Store Slice: `useClientPeriodStore`

```typescript
interface ClientPeriodState {
  selectedQuarter: number       // 1-4
  selectedFyYear: number        // e.g. 2025
  setQuarter: (q: number, fy: number) => void
}
```

Consumed by: `BASTab`, Insights tab, Dashboard tab — all on the client detail page. Replaces the local `useState` in `BASTab` for quarter selection. Persists for the duration of the browser session (no localStorage — resets on page refresh, which is acceptable).

---

## Audit Events (new)

| Event | Table | Trigger |
|-------|-------|---------|
| `bas.gst_basis.set` | `audit_logs` | `PracticeClient.gst_reporting_basis` saved for first time |
| `bas.gst_basis.changed` | `audit_logs` | `PractageClient.gst_reporting_basis` changed from one value to another |
| `bas.gst_basis.changed_post_lodgement` | `audit_logs` | Basis changed after a session for this client has been lodged |
| `bas.instalment.entered` | `audit_logs` | T1 or T2 value saved to `BASCalculation` |
