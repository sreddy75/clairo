# API Contracts: BAS Compliance Fixes & Data Accuracy

**Branch**: `062-bas-compliance-fixes` | **Date**: 2026-04-24

All endpoints are under `/api/v1/`. All require valid Clerk JWT (accountant). All are tenant-scoped.

---

## Modified Endpoints

### PATCH /clients/{client_id}

Add `gst_reporting_basis` to the existing client update endpoint.

**Request body addition**:
```json
{
  "gst_reporting_basis": "cash" | "accrual" | null
}
```

**Response addition** (in `PracticeClientResponse`):
```json
{
  "gst_reporting_basis": "cash" | "accrual" | null,
  "gst_basis_updated_at": "2026-04-24T10:00:00Z" | null,
  "gst_basis_updated_by": "uuid" | null
}
```

**Side effects**: Creates `bas.gst_basis.set` or `bas.gst_basis.changed` audit event. If an already-lodged BAS session exists for this client, creates `bas.gst_basis.changed_post_lodgement` audit event.

---

### GET /clients/{client_id}

Add `gst_reporting_basis` to the existing client read response (same fields as above).

---

### POST /bas/sessions (or existing session creation endpoint)

When `PracticeClient.gst_reporting_basis IS NULL`, the frontend blocks session calculation and prompts the accountant. Once the accountant selects a basis, it is saved via `PATCH /clients/{client_id}` before triggering calculation. No change to the session creation endpoint itself — the basis is read from the client record at calculation time.

---

### GET /bas/sessions/{session_id}

Add `gst_basis_used` to the session response:
```json
{
  "gst_basis_used": "cash" | "accrual" | null
}
```

---

### PATCH /bas/calculations/{calculation_id}

Extend the existing calculation adjustment endpoint to accept T1/T2 instalment fields:

**Request body addition**:
```json
{
  "t1_instalment_income": 125000.00 | null,
  "t2_instalment_rate": 0.04 | null
}
```

**Response** includes updated totals:
```json
{
  "t1_instalment_income": 125000.00,
  "t2_instalment_rate": 0.04,
  "t_instalment_payable": 5000.00
}
```

**Side effects**: Creates `bas.instalment.entered` audit event with old/new values.

---

## New Endpoints

### GET /bas/clients/{client_id}/reconciliation-status

Returns the unreconciled transaction count for a given date range (used before showing BAS figures).

**Query params**: `start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`

**Response**:
```json
{
  "unreconciled_count": 3,
  "total_transactions": 71,
  "as_of": "2026-04-24T09:30:00Z"
}
```

**Used by**: Frontend — called when accountant opens BAS preparation, before fetching BAS figures. If `unreconciled_count > 0`, show blocking warning.

---

### POST /bas/sessions/{session_id}/lodge (modified)

Extend the lodge endpoint to support optional Insights inclusion:

**Request body addition**:
```json
{
  "include_insights": true,
  "insights_format": "inline"
}
```

For Phase 1, only `"inline"` is supported. The lodgement confirmation email will include a "This Quarter in Numbers" section with the top insights.

**Response**: unchanged (existing lodgement response).

---

## Frontend-Only Changes (no new endpoints)

The following bugs are fixed purely in the frontend with no API contract changes:

| Bug | Fix Location |
|-----|--------------|
| "Manual Required" label | `BASTab.tsx` and sub-components — text replacement |
| Transaction sort order | Already `ORDER BY issue_date DESC` in backend — frontend was overriding; remove override |
| Quarter state across tabs | New `useClientPeriodStore` Zustand slice — no API change |
| Retry button non-functional | Fix event handler in error state component |
| Insight language | Backend — `AIAnalyzer` prompt and post-processing |
| Insight deduplication | Backend — `InsightGenerator` dedup step |
| Insight confidence routing | Backend — threshold check in routing layer |
| Overdue AR figure | Backend — fix query in `ComplianceAnalyzer` |
