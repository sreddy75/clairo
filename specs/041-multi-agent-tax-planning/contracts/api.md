# API Contracts: Multi-Agent Tax Planning Pipeline

**Date**: 2026-04-03  
**Feature**: 041-multi-agent-tax-planning  
**Base Path**: `/api/v1/tax-plans/{plan_id}/analysis`

## Endpoints

### POST /api/v1/tax-plans/{plan_id}/analysis/generate

Trigger the multi-agent analysis pipeline. Returns immediately with a task ID.

**Auth**: Accountant (CLIENT_WRITE permission)

**Request**: Empty body (financials come from the plan)

**Response** (202 Accepted):
```json
{
  "task_id": "celery-task-uuid",
  "analysis_id": "uuid",
  "status": "generating",
  "message": "Tax plan analysis started"
}
```

**Errors**:
- 404: Plan not found
- 409: Analysis already in progress for this plan
- 422: Plan has no financials data (must load Xero or manual first)

---

### GET /api/v1/tax-plans/{plan_id}/analysis/progress/{task_id}

Stream real-time progress of the pipeline via SSE.

**Auth**: Accountant (CLIENT_READ permission)

**Response** (SSE stream):
```
data: {"type": "progress", "stage": "profiling", "stage_number": 1, "total_stages": 5, "message": "Analysing client profile..."}

data: {"type": "progress", "stage": "scanning", "stage_number": 2, "total_stages": 5, "message": "Evaluating strategy 8 of 22..."}

data: {"type": "progress", "stage": "modelling", "stage_number": 3, "total_stages": 5, "message": "Modelling top 5 strategies..."}

data: {"type": "progress", "stage": "writing", "stage_number": 4, "total_stages": 5, "message": "Writing accountant brief..."}

data: {"type": "progress", "stage": "reviewing", "stage_number": 5, "total_stages": 5, "message": "Verifying calculations and citations..."}

data: {"type": "complete", "analysis_id": "uuid", "review_passed": true}

data: {"type": "error", "stage": "modelling", "message": "Xero token expired", "retryable": true}
```

---

### GET /api/v1/tax-plans/{plan_id}/analysis

Get the current analysis for a plan.

**Auth**: Accountant (CLIENT_READ permission)

**Response** (200):
```json
{
  "id": "uuid",
  "version": 1,
  "status": "draft",
  "client_profile": { "...profiler output..." },
  "strategies_evaluated": [ "...scanner output..." ],
  "recommended_scenarios": [ "...modeller output..." ],
  "combined_strategy": { "...optimal combination..." },
  "accountant_brief": "# Executive Summary\n...",
  "client_summary": "# Your Tax Plan\n...",
  "review_result": { "numbers_verified": true, "citations_valid": true },
  "review_passed": true,
  "implementation_items": [
    {
      "id": "uuid",
      "title": "Purchase IT equipment ($40K)",
      "deadline": "2026-06-30",
      "estimated_saving": 10000,
      "risk_rating": "conservative",
      "status": "pending",
      "client_visible": true
    }
  ],
  "generation_time_ms": 45000,
  "generated_at": "2026-04-03T10:00:00Z",
  "previous_versions": [
    { "version": 1, "generated_at": "2026-03-15T10:00:00Z", "status": "approved" }
  ]
}
```

**Errors**:
- 404: No analysis exists for this plan

---

### PATCH /api/v1/tax-plans/{plan_id}/analysis

Update the accountant brief or client summary (accountant edits).

**Auth**: Accountant (CLIENT_WRITE permission)

**Request**:
```json
{
  "accountant_brief": "# Updated Executive Summary\n...",
  "client_summary": "# Your Updated Tax Plan\n...",
  "status": "reviewed"
}
```

**Response** (200): Updated analysis object.

---

### POST /api/v1/tax-plans/{plan_id}/analysis/approve

Approve the analysis for client sharing.

**Auth**: Accountant (CLIENT_WRITE permission)

**Response** (200):
```json
{
  "status": "approved",
  "reviewed_by": "user-uuid",
  "message": "Analysis approved. Ready to share with client."
}
```

---

### POST /api/v1/tax-plans/{plan_id}/analysis/share

Share the approved analysis to the client portal.

**Auth**: Accountant (CLIENT_WRITE permission)

**Response** (200):
```json
{
  "status": "shared",
  "shared_at": "2026-04-03T12:00:00Z",
  "portal_url": "/portal/tax-plan/uuid"
}
```

**Errors**:
- 422: Analysis not yet approved

---

### POST /api/v1/tax-plans/{plan_id}/analysis/regenerate

Re-run the pipeline with current financials. Creates a new version.

**Auth**: Accountant (CLIENT_WRITE permission)

**Response** (202 Accepted): Same as generate response.

---

### PATCH /api/v1/tax-plans/{plan_id}/analysis/items/{item_id}

Update an implementation item (mark complete, update status).

**Auth**: Accountant (CLIENT_WRITE) OR Portal Client (via magic link)

**Request**:
```json
{
  "status": "completed"
}
```

**Response** (200): Updated item object.

---

## Portal Endpoints

### GET /api/v1/client-portal/tax-plan

Get the shared tax plan for the authenticated portal client.

**Auth**: Portal Client (magic link)

**Response** (200):
```json
{
  "plan_id": "uuid",
  "client_name": "KR8 IT",
  "financial_year": "2025-26",
  "client_summary": "# Your Tax Plan\n...",
  "total_estimated_saving": 20000,
  "implementation_items": [
    {
      "id": "uuid",
      "title": "Purchase IT equipment ($40K) before 30 June",
      "estimated_saving": 10000,
      "deadline": "2026-06-30",
      "status": "pending"
    }
  ],
  "shared_at": "2026-04-03T12:00:00Z",
  "practice_name": "KR8 IT Accounting"
}
```

### POST /api/v1/client-portal/tax-plan/question

Client asks a question about the tax plan.

**Auth**: Portal Client (magic link)

**Request**:
```json
{
  "question": "Do I need to purchase the equipment before or after June 30?"
}
```

**Response** (201):
```json
{
  "message": "Your question has been sent to your accountant. They'll get back to you shortly.",
  "question_id": "uuid"
}
```
