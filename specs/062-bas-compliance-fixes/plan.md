# Implementation Plan: BAS Compliance Fixes & Data Accuracy

**Branch**: `062-bas-compliance-fixes` | **Date**: 2026-04-24 | **Spec**: [spec.md](spec.md)

## Summary

Fix 11 confirmed bugs and gaps in the BAS preparation workflow, surfaced during a live trial by Unni Ashok (Ashok Business Consulting Group). The most critical issue — Clairo loading the wrong GST basis — requires a calculator refactor and a new client-level preference field. The remaining issues span backend data accuracy, frontend label/state bugs, Insights tab quality, and email delivery of Insights alongside BAS lodgement.

**Approach**: Additive schema changes only (3 new nullable columns across 2 tables). No new tables. Backend calculator refactor for cash/accrual branching. Frontend label fixes, state lifting, and Insights routing corrections.

---

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript 5.x / Next.js 14 (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 async, Pydantic v2, Alembic, Celery + Redis, Anthropic SDK (Claude Sonnet — Insights AI), React 18 + shadcn/ui, TanStack Query, Zustand
**Storage**: PostgreSQL 16 — 3 new nullable columns across 2 existing tables (`practice_clients`, `bas_sessions`, `bas_calculations`). No new tables.
**Testing**: pytest + pytest-asyncio (backend), TypeScript tsc + ESLint (frontend)
**Target Platform**: Linux server (backend), Vercel (frontend)
**Performance Goals**: BAS basis prompt adds ≤1 round trip before data load. Reconciliation status check must complete in ≤500ms.
**Constraints**: Existing BAS sessions must not be affected by new cash/accrual logic — `gst_basis_used` snapshot isolates historical sessions. All changes must preserve multi-tenancy isolation.
**Scale/Scope**: ~50–200 clients per tenant; BAS prepared quarterly. Insight generation is async (Celery) — no real-time constraint.

---

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| Modular monolith boundaries | ✅ PASS | Changes stay within `bas`, `clients`, `insights`, `notifications` modules |
| Repository pattern | ✅ PASS | All DB access via existing repositories; new fields follow same pattern |
| Multi-tenancy (`tenant_id` on all queries) | ✅ PASS | All modified models already have `tenant_id`; new queries must include it |
| Audit-first | ✅ PASS | 4 new audit event types defined in `data-model.md` |
| Domain exceptions (not HTTPException in services) | ✅ PASS | Plan uses existing `exceptions.py` pattern |
| `flush()` not `commit()` in repositories | ✅ PASS | Session lifecycle managed by caller |
| Frontend: shadcn/ui components only | ✅ PASS | All new UI uses existing shadcn components (Dialog, Badge, Alert) |
| Frontend: CSS variable tokens only | ✅ PASS | No hardcoded colours |
| Frontend: Next.js App Router | ✅ PASS | All frontend changes in `app/` |
| Celery tasks idempotent | ✅ PASS | Insight dedup fix does not change task idempotency |

---

## Project Structure

### Documentation (this feature)

```text
specs/062-bas-compliance-fixes/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── contracts/
│   └── api.md           # API contracts
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code

```text
backend/app/
├── modules/
│   ├── clients/
│   │   ├── models.py           # + gst_reporting_basis, gst_basis_updated_at/by
│   │   ├── schemas.py          # + GSTBasisUpdate, gst_reporting_basis in response
│   │   ├── repository.py       # + update_gst_basis()
│   │   └── service.py          # + set_gst_basis() with audit
│   ├── bas/
│   │   ├── models.py           # + gst_basis_used on BASSession; t1/t2 on BASCalculation
│   │   ├── schemas.py          # + InstalmentUpdate, gst_basis_used in responses
│   │   ├── calculator.py       # REFACTOR: cash/accrual branching in GSTCalculator
│   │   ├── service.py          # + reconciliation_status(); + instalment update
│   │   ├── repository.py       # + get_reconciliation_status()
│   │   ├── router.py           # + GET reconciliation-status; PATCH instalments; POST lodge update
│   │   ├── audit_events.py     # + 4 new audit event types
│   │   └── lodgement_service.py # + include_insights param in record_lodgement()
│   ├── insights/
│   │   ├── generator.py        # + dedup step; + confidence routing threshold
│   │   └── analyzers/
│   │       ├── compliance.py   # FIX: overdue AR query (due_date < today, not paid)
│   │       └── magic_zone.py   # FIX: confidence threshold gate before Urgent assignment
│   └── notifications/
│       ├── templates.py        # + insights_section param in lodgement_confirmation()
│       └── email_service.py    # + include_insights in send_lodgement_confirmation()
├── alembic/versions/
│   └── [hash]_bas_gst_basis_and_instalments.py   # Migration

frontend/src/
├── stores/
│   └── clientPeriodStore.ts    # NEW: useClientPeriodStore (quarter + FY state)
├── app/(protected)/clients/[id]/
│   └── page.tsx                # REFACTOR: use clientPeriodStore; pass to Insights + Dashboard tabs
├── components/
│   ├── bas/
│   │   ├── BASTab.tsx          # + basis prompt modal; fix retry; use clientPeriodStore
│   │   ├── GSTBasisModal.tsx   # NEW: modal to select cash/accrual before data loads
│   │   ├── UnreconciledWarning.tsx  # NEW: blocking dialog with Proceed/Go Back
│   │   ├── InstalmentSection.tsx    # NEW: T1/T2 entry within PAYG tab
│   │   └── TransactionList.tsx # FIX: label "Uncoded", two-status header display
│   └── insights/
│       └── InsightsTab.tsx     # FIX: consume clientPeriodStore for quarter context
```

---

## Implementation Phases

### Phase A — Database & Backend Core (P1–P3: Compliance-critical)

**Goal**: The three compliance-critical fixes: GST basis, PAYGW population, PAYG Instalment.

#### A1. Schema Migration
- Add `gst_reporting_basis`, `gst_basis_updated_at`, `gst_basis_updated_by` to `practice_clients`
- Add `gst_basis_used` to `bas_sessions`
- Add `t1_instalment_income`, `t2_instalment_rate` to `bas_calculations`
- Alembic auto-generate + manual review

#### A2. Client GST Basis — Backend
- `PracticeClient` model update
- `ClientRepository.update_gst_basis()` method
- `ClientService.set_gst_basis()` — saves preference, writes audit event
  - Detects if any `BASSession` for this client is lodged → emits `bas.gst_basis.changed_post_lodgement`
- Extend `PATCH /clients/{id}` schema to accept and return `gst_reporting_basis`
- Extend `GET /clients/{id}` response with basis fields

#### A3. GSTCalculator Cash/Accrual Branching
- `GSTCalculator.calculate()` — accept `gst_basis: Literal["cash", "accrual"]` parameter
- `_get_invoices()` — branch:
  - `accrual`: existing `WHERE issue_date BETWEEN start AND end`
  - `cash`: `JOIN xero_payments ON invoice_id WHERE payment_date BETWEEN start AND end`
- `_get_credit_notes()` — same branching
- `BASService` — read `client.gst_reporting_basis` and pass to calculator
- `BASSession.gst_basis_used` — set at calculation time from client preference
- Verify `XeroPayment` sync exists in `data_service.py`; add if missing

#### A4. PAYG Instalment T1/T2
- `BASCalculation` model update
- `BASRepository` — extend update method to accept T1/T2
- `BASService.update_instalment()` — saves T1/T2, computes payable, writes audit event
- New `PATCH /bas/calculations/{id}/instalments` endpoint (or extend existing adjustment endpoint)
- Extend `BASCalculation` schema to include T1/T2 in response

#### A5. Verify PAYGW Auto-Population
- Trace why W1/W2 fields (which exist in `BASCalculation`) are not being populated
- The `PAYGCalculator` class reads from `XeroPayRun` — check if pay runs are synced for the client and whether `PAYGCalculator.calculate()` is being called correctly in `BASService`
- Fix the call chain if broken; no model change needed (fields already exist)

---

### Phase B — Data Accuracy Fixes (P4–P6: Labels, Sort, Precision)

**Goal**: Fix the three data accuracy issues that erode accountant trust.

#### B1. "Manual Required" → "Uncoded" Label
- Find all instances of "Manual Required" text in frontend components (BASTab.tsx and sub-components)
- Replace with "Uncoded" or "Needs tax code" (context-dependent)
- Update `router.py` line 1277 API summary string
- Add two-status header display: reconciliation badge (from Xero sync status) + coding badge (from `TaxCodeSuggestion` pending count) — separate, visually distinct

#### B2. Transaction Sort Order
- Verify backend already returns `ORDER BY issue_date DESC` (confirmed in research — backend is correct)
- Identify any frontend override sorting the list in a different order; remove it
- Ensure the `TransactionList` component respects backend ordering

#### B3. Cent Precision
- Find all instances of transaction amount formatting in the frontend (search for `toFixed(0)`, `Math.round`, `parseInt` on currency values)
- Replace with a `formatCurrency` call that preserves 2 decimal places
- Verify `formatCurrency` in `@/lib/formatters` already supports cents; update if not

---

### Phase C — Navigation & State Fixes (P7: Quarter context)

**Goal**: Quarter selection persists across all tabs.

#### C1. Create `useClientPeriodStore`
- New Zustand slice at `frontend/src/stores/clientPeriodStore.ts`
- State: `{ selectedQuarter: number, selectedFyYear: number, setQuarter: (q, fy) => void }`
- No localStorage persistence — resets on page load (acceptable)

#### C2. Wire Client Detail Page
- `/clients/[id]/page.tsx` — replace local `selectedQuarter`/`selectedFyYear` state with `useClientPeriodStore`
- Pass store to BAS tab, Insights tab, Dashboard tab (all consume same source)
- Remove prop-drilling of quarter from parent to child where Zustand replaces it

#### C3. Insights Tab Consumes Store
- `InsightsTab.tsx` — replace hardcoded or absent quarter state with `useClientPeriodStore`
- Ensure all Insights API calls include `?period=Q{quarter}&fy={fyYear}` query params
- Display selected quarter label prominently on Insights tab header

---

### Phase D — Insights Quality Fixes (P8: Accuracy & relevance)

**Goal**: Fix 6 sub-issues in the Insights tab.

#### D1. Overdue AR Fix
- `compliance.py` (`ComplianceAnalyzer`) — fix the overdue receivables query
- Correct query: `XeroInvoice WHERE due_date < today AND status NOT IN ('PAID', 'VOIDED')`
- Do not divide total AR outstanding by a ratio — sum the actual overdue invoice amounts

#### D2. GST Registration Suppression
- `compliance.py` — before generating the GST registration insight, check `PracticeClient.gst_reporting_basis IS NOT NULL` (i.e., client is already GST-registered in Clairo) or check ABN/GST registration from client profile
- If client is already registered, skip the insight entirely

#### D3. AI Language Fix (Distinct Generation Paths)
- `AIAnalyzer` — audit the prompt used for insight card generation vs the chat prompt
- Add explicit instruction: insight cards must use third-person declarative language ("Revenue declined X%") not first-person chat language ("I notice...")
- Add post-processing assertion: strip any response beginning with "I " or "It appears"

#### D4. Confidence Threshold Routing
- `InsightGenerator` or routing layer — add `URGENT_CONFIDENCE_THRESHOLD = 0.70`
- After each analyzer runs: `if insight.confidence_score < 0.70: insight.priority = InsightPriority.MEDIUM`
- This gates all insights — not just MagicZone ones

#### D5. Deduplication
- `InsightGenerator.generate()` — after collecting all insights from all analyzers, dedup on `(insight_type, period)`
- Keep highest-confidence duplicate; discard the rest

#### D6. Calculation Breakdown
- Each insight with a numeric figure must store its source data points in `metadata` JSONB (if not already)
- Frontend `InsightCard` — add "How was this calculated?" expandable section
- Render the stored data points and formula from `metadata`

---

### Phase E — Reliability Fixes (P9–P10: Error handling, unreconciled warning)

**Goal**: Fix blocking UX defect (retry button) and compliance risk (unreconciled warning).

#### E1. Fix Retry Button
- Identify the error state component in `BASTab.tsx`
- The retry button's `onClick` handler is likely missing or calling a no-op function
- Wire it to re-trigger the BAS data fetch (existing `refetch()` from React Query or re-call `triggerBASCalculation`)
- Ensure error message is descriptive (shows what failed and a suggested next step)

#### E2. Unreconciled Warning
- Backend: `BASService.get_reconciliation_status(client_id, start_date, end_date)` — query `XeroBankTransaction` for unreconciled records in the period
  - First: verify `XeroBankTransaction.is_reconciled` field exists; if not, investigate alternative (see research.md risk register)
- New endpoint: `GET /bas/clients/{client_id}/reconciliation-status?start=&end=`
- Frontend: before showing BAS figures, call this endpoint
  - If `unreconciled_count > 0`: show `UnreconciledWarning` dialog (shadcn `Dialog` or `AlertDialog`) with "Proceed anyway" and "Go back" buttons
  - "Proceed anyway" → load BAS figures + show persistent `Alert` banner
  - "Go back" → navigate to client overview

---

### Phase F — Client-Facing Fixes (P9 Request Client Input, FR-022)

**Goal**: Apply label and sort fixes to the client-facing transaction classification request.

#### F1. Classification Email Template
- `portal/notifications/templates.py` — `transaction_classification_request()` template
- Update transaction label from "Manual Required" to "Needs tax code" (plain language for non-accountants)

#### F2. Classification Service Sort
- `classification_service.py` — `create_request()` method
- Sort `unresolved_suggestions` by `transaction_date DESC` before building the email payload

---

### Phase G — Insights in BAS Lodgement Email (FR-021)

**Goal**: Allow accountant to optionally include Insights summary in BAS lodgement confirmation email.

#### G1. Backend
- `lodgement_service.py` — `record_lodgement()` accepts optional `include_insights: bool` and `insights_format: str = "inline"`
- If `include_insights`, fetch top 5 insights for the period (ordered by priority DESC, confidence DESC)
- Format as a plain-text/HTML "This Quarter in Numbers" section
- `notifications/templates.py` — `lodgement_confirmation()` accepts optional `insights_section: str | None`
- If provided, render the section in the email body

#### G2. Frontend
- `LodgementModal.tsx` — add a toggle "Include Insights summary in client email" (default off)
- If toggled on, show a preview of the insights that will be included
- Pass `include_insights: true` to the lodge API call

---

## Complexity Tracking

No constitution violations. All changes are within existing modules.

---

## Testing Strategy

### Backend Unit Tests
- `test_gst_calculator.py` — cash basis: assert invoices filtered by payment_date not issue_date; accrual: assert existing behaviour unchanged
- `test_client_service.py` — set_gst_basis(): audit event created; post-lodgement audit event created correctly
- `test_bas_service.py` — instalment update: T1/T2 saved; payable computed correctly
- `test_insight_generator.py` — dedup: duplicate insights removed; confidence routing: <0.70 → MEDIUM priority
- `test_compliance_analyzer.py` — overdue AR: only invoices past due_date and not paid are counted

### Backend Integration Tests
- `test_bas_router.py` — reconciliation-status endpoint returns correct count
- `test_clients_router.py` — PATCH client with gst_reporting_basis persists correctly

### Frontend
- Manual testing: basis prompt appears on first BAS open; disappears on second open (saved preference)
- Manual testing: quarter context preserved BAS → Insights → Dashboard → BAS
- Manual testing: retry button re-triggers fetch
- TypeScript typecheck (`npx tsc --noEmit`) must pass

---

## Migration

Single Alembic migration file: `[hash]_bas_gst_basis_and_instalments.py`

- Adds 3 columns to `practice_clients` (nullable — zero downtime)
- Adds 1 column to `bas_sessions` (nullable — zero downtime)
- Adds 2 columns to `bas_calculations` (nullable — zero downtime)

Rollback: all columns are `DROP COLUMN` (no data loss if rolled back).
