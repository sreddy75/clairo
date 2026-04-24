# Research: BAS Compliance Fixes & Data Accuracy

**Branch**: `062-bas-compliance-fixes` | **Date**: 2026-04-24

---

## Decision 1: GST Basis Storage Location

**Decision**: Add `gst_reporting_basis: Mapped[str | None]` to `PracticeClient` model.

**Rationale**: The basis is a property of the client's ATO registration, not of a specific Xero connection or BAS session. `PracticeClient` is the right home — it already holds other ATO-level facts (`abn`, `accounting_software`). Nullable = not yet set = system must prompt on next BAS open.

**Alternatives considered**:
- `XeroConnection`: Rejected — a client could theoretically switch accounting software; the basis should survive a reconnection.
- `BASSession`: Rejected — would require re-entering on every new session. The basis is a durable client attribute.
- Separate `ClientGSTSettings` table: Rejected — unnecessary complexity for a single field at this stage.

**Basis change audit**: Also add `gst_basis_used: Mapped[str]` to `BASSession` so the basis that was active at calculation time is snapshotted for each session — required for ATO audit trail.

---

## Decision 2: Cash Basis Implementation in GSTCalculator

**Decision**: When `gst_reporting_basis == 'cash'`, filter invoices via `XeroPayment.payment_date` (join invoices to payments) rather than `XeroInvoice.issue_date`.

**Rationale**: The `XeroPayment` model (at `integrations/xero/models.py:2813`) already exists with a `payment_date` field and links to invoices. Bank transactions are inherently cash-basis (they represent actual movements), so `XeroBankTransaction.transaction_date` filtering is already correct for both bases.

**Current behaviour**: `GSTCalculator` mixes accrual invoices (`issue_date`) with cash bank transactions (`transaction_date`) indiscriminately. Switching the invoice filter to payment date for cash-basis clients is the targeted fix.

**Implementation approach**:
1. `GSTCalculator.calculate()` accepts a new `gst_basis: Literal["cash", "accrual"]` parameter.
2. `_get_invoices()` branches: accrual → filter by `XeroInvoice.issue_date`; cash → join to `XeroPayment` and filter by `XeroPayment.payment_date`.
3. Credit notes follow the same branching logic (filter by `credit_note_date` for accrual, payment date for cash).

**Risk**: `XeroPayment` records must be synced for this to work. Verify `data_service.sync_payments()` exists and is called in the Xero sync pipeline. If not, a payments sync must be added. Flag as implementation task.

---

## Decision 3: PAYG Instalment T1/T2 Storage

**Decision**: Add `t1_instalment_income: Mapped[Decimal | None]` and `t2_instalment_rate: Mapped[Decimal | None]` directly to `BASCalculation` model, alongside existing W1/W2 fields.

**Rationale**: `BASCalculation` already holds all ATO form fields (`w1_total_wages`, `w2_amount_withheld`, `g1_total_sales`, etc.). T1/T2 are standard BAS fields and belong in the same model. Both are nullable — zero means not applicable, null means not yet entered.

**Label clarification**: For quarterly BAS filers (confirmed in clarifications), the correct ATO field labels are:
- **T1**: PAYG instalment income (the income figure the instalment is based on)
- **T2**: PAYG instalment rate (percentage applied to T1 to calculate the instalment amount)

The instalment amount payable = T1 × T2. Both are manual entry only — no ATO portal connection exists.

---

## Decision 4: Quarter State — Lifting to Parent

**Decision**: Lift quarter selection state from `BASTab.tsx` local state to the client detail page parent (`/clients/[id]/page.tsx`) using a shared Zustand store slice or by extending the existing prop-passing pattern.

**Rationale**: The parent already passes `selectedQuarter` and `selectedFyYear` to `BASTab`. The Insights tab is a sibling component that currently receives no quarter context. The simplest fix is to pass the same props to the Insights tab. The Dashboard tab also needs to consume this state (per spec).

**Approach**: Create a `useClientPeriodStore` Zustand slice that holds `{ selectedQuarter, selectedFyYear, setQuarter }`. Both BAS and Insights tabs subscribe to this store. This avoids deep prop-drilling and works cleanly with the existing Zustand pattern in the codebase.

---

## Decision 5: Unreconciled Transaction Detection

**Decision**: Query the count of `XeroBankTransaction` records with `is_reconciled = false` (or equivalent status field) for the selected period. If count > 0, show the blocking warning.

**Risk / Uncertainty**: The research agents did not confirm whether `XeroBankTransaction` has an `is_reconciled` boolean field. This must be verified during implementation:
- If `XeroBankTransaction.is_reconciled` exists → use it directly.
- If not → check whether Xero's bank transaction status (`"AUTHORISED"` vs `"DELETED"`) serves as a proxy, or whether a separate `XeroBankStatement` model tracks reconciliation.
- Fallback: expose a new Xero API call to `GET /BankTransactions?where=IsReconciled=false` for the period and count results.

**New API endpoint needed**: `GET /api/v1/bas/clients/{client_id}/reconciliation-status?start=&end=` → returns `{ unreconciled_count: int, as_of: datetime }`.

---

## Decision 6: "Manual Required" Label Origin

**Decision**: The "Manual Required" text originates in the frontend — `TaxCodeSuggestion.status = "pending"` is rendered as "Manual Required" in the UI. Fix is a frontend-only label change.

**Also fix**: The backend `router.py` line 1277 uses "Manual Required" in an API summary string — update to "Uncoded" for consistency. The frontend component rendering the count badge (likely in `BASTab.tsx` or a sub-component) must be identified during implementation and updated to "Uncoded" / "Needs tax code".

**Two-status display**: Add a reconciliation status indicator alongside the coding status indicator in the BAS header. These must be visually distinct — reconciliation status (from Xero sync) and coding status (from `TaxCodeSuggestion` count) are different signals.

---

## Decision 7: Insight Confidence Routing

**Decision**: Add a `URGENT_CONFIDENCE_THRESHOLD = 0.70` constant to the insight routing layer. Any insight with `confidence_score < 0.70` must be routed to `InsightPriority.MEDIUM` (For Review) regardless of the analyzer's urgency signal.

**Current behaviour**: `magic_zone.py` assigns `InsightPriority.HIGH` based on `trigger.urgency == "high"` without checking confidence. Analyzers report fixed confidence ranges (0.75–0.95 for most) but the magic zone can receive lower-confidence signals.

**Implementation**: In `InsightGenerator.generate()` (or the routing step after each analyzer), apply: `if insight.confidence_score < URGENT_CONFIDENCE_THRESHOLD: insight.priority = InsightPriority.MEDIUM`.

---

## Decision 8: Insight Deduplication

**Decision**: Add a deduplication step in `InsightGenerator` before persisting insights. Dedup key: `(insight_type, period)`. Keep the highest-confidence instance; discard the rest.

**Rationale**: The brief observed "unusually high voided invoices" and "low expense ratio" appearing twice with slightly different wording — same root cause as the Tax Planning scenario dedup bug (per CLAUDE.md). The fix is the same pattern: normalise on a stable key, not on text content.

---

## Decision 9: Overdue Receivables vs Overdue Lodgements

**Decision**: These are two distinct data sources and must not be conflated:

- **Overdue AR** (accounts receivable): Query `XeroInvoice` records where `due_date < today` and `status != "PAID"` and `status != "VOIDED"`. Sum/count these. **Do not** divide total outstanding by total AR — show the actual overdue balance.
- **Overdue lodgements**: Query `BASSession` records where `due_date < today` and `lodged_at IS NULL` for the tenant.

The current insight likely uses total outstanding AR divided by something — the fix is to switch to the correct query.

---

## Decision 10: Insights Report in BAS Lodgement Email

**Decision**: Add an optional `include_insights: bool` parameter to the `record_lodgement()` service method and the `send_lodgement_confirmation()` email method. The accountant chooses format (inline / PDF / magic link) at the point of lodgement confirmation.

**Phase 1 scope (this spec)**: Implement inline email section only — a summary of the top 3–5 insights for the quarter, in professional advisory language, added as a section to the existing `lodgement_confirmation` email template. PDF and magic link formats are deferred to a follow-up spec.

**Rationale**: Inline is lowest effort and validates the concept fastest. The accountant can see the content before sending. PDF generation requires WeasyPrint and a new template — that's a separate spec.

---

## Decision 11: Request Client Input Label Fixes

**Decision**: The `transaction_classification_request` email template in `portal/notifications/templates.py` must be updated to use plain-language labels ("Needs tax code", not "Manual Required") and transactions must be passed in date-descending order.

**Implementation**: In `classification_service.py`, sort the `unresolved_suggestions` list by `transaction_date DESC` before building the email payload. Update the template string.

---

## Risk Register

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| `XeroPayment` sync not in pipeline | Medium | Verify `data_service.sync_payments()` exists; add if missing |
| `XeroBankTransaction.is_reconciled` field absent | Medium | Check model during implementation; fallback to Xero API call |
| Cash basis changes affect existing BAS sessions | High | Only apply new basis logic to new sessions; existing sessions use `gst_basis_used` snapshot |
| Xero payroll OAuth scope missing | Low | Already confirmed as an assumption; verify during implementation |
