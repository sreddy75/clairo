# API Contracts: AI Tax Planning & Advisory

**Branch**: `049-ai-tax-planning` | **Date**: 2026-03-31

Base URL: `/api/v1/tax-plans`

---

## Tax Plan CRUD

### POST /api/v1/tax-plans

Create a new tax plan for a client. If a plan already exists for the same client+FY, returns 409 Conflict (frontend handles replacement confirmation).

**Request Body**:
```json
{
  "xpm_client_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "financial_year": "2025-26",
  "entity_type": "company",
  "data_source": "xero",
  "replace_existing": false
}
```

**Validation**: `entity_type` must be one of: `company`, `individual`, `trust`, `partnership`. `financial_year` must match pattern `YYYY-YY`. If `data_source` is `xero`, the client must have a connected Xero organisation.

**Response 201**:
```json
{
  "id": "f8a9b0c1-d2e3-4567-8901-abcdef123456",
  "tenant_id": "11111111-2222-3333-4444-555555555555",
  "xpm_client_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "client_name": "Smith Trading Pty Ltd",
  "financial_year": "2025-26",
  "entity_type": "company",
  "status": "draft",
  "data_source": "xero",
  "financials_data": null,
  "tax_position": null,
  "xero_report_fetched_at": null,
  "created_at": "2026-03-31T10:00:00+11:00",
  "updated_at": "2026-03-31T10:00:00+11:00",
  "scenario_count": 0,
  "message_count": 0
}
```

**Error 409** (existing plan): `{"error": "Tax plan already exists for this client and financial year", "code": "PLAN_EXISTS", "details": {"existing_plan_id": "..."}}`

**Error 400** (no Xero connection): `{"error": "Client has no connected Xero organisation", "code": "NO_XERO_CONNECTION"}`

---

### GET /api/v1/tax-plans

List all tax plans for the current tenant.

**Query Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | string | all | Filter by status: `draft`, `in_progress`, `finalised` |
| `financial_year` | string | all | Filter by FY, e.g. `2025-26` |
| `search` | string | none | Search by client name |
| `page` | int | 1 | Page number |
| `page_size` | int | 25 | Items per page (max 100) |

**Response 200**:
```json
{
  "items": [
    {
      "id": "f8a9b0c1-d2e3-4567-8901-abcdef123456",
      "xpm_client_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "client_name": "Smith Trading Pty Ltd",
      "financial_year": "2025-26",
      "entity_type": "company",
      "status": "in_progress",
      "data_source": "xero",
      "scenario_count": 3,
      "net_position": 15500.00,
      "updated_at": "2026-03-31T14:30:00+11:00"
    }
  ],
  "total": 12,
  "page": 1,
  "page_size": 25
}
```

---

### GET /api/v1/tax-plans/{plan_id}

Get a single tax plan with full details.

**Response 200**:
```json
{
  "id": "f8a9b0c1-d2e3-4567-8901-abcdef123456",
  "tenant_id": "11111111-2222-3333-4444-555555555555",
  "xpm_client_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "client_name": "Smith Trading Pty Ltd",
  "financial_year": "2025-26",
  "entity_type": "company",
  "status": "in_progress",
  "data_source": "xero",
  "financials_data": {
    "income": {
      "revenue": 500000.00,
      "other_income": 12000.00,
      "total_income": 512000.00,
      "breakdown": [
        {"category": "Trading Income", "amount": 500000.00},
        {"category": "Interest Received", "amount": 8000.00},
        {"category": "Dividends", "amount": 4000.00}
      ]
    },
    "expenses": {
      "cost_of_sales": 200000.00,
      "operating_expenses": 150000.00,
      "total_expenses": 350000.00,
      "breakdown": [
        {"category": "Wages & Salaries", "amount": 120000.00},
        {"category": "Rent", "amount": 36000.00}
      ]
    },
    "credits": {
      "payg_instalments": 25000.00,
      "payg_withholding": 0.00,
      "franking_credits": 0.00
    },
    "adjustments": [],
    "turnover": 512000.00,
    "months_data_available": 9,
    "is_annualised": false
  },
  "tax_position": {
    "taxable_income": 162000.00,
    "gross_tax": 40500.00,
    "offsets": {"lito": 0.00, "other": 0.00},
    "medicare_levy": 0.00,
    "help_repayment": 0.00,
    "total_tax_payable": 40500.00,
    "credits_applied": {
      "payg_instalments": 25000.00,
      "payg_withholding": 0.00,
      "franking_credits": 0.00,
      "total": 25000.00
    },
    "net_position": 15500.00,
    "effective_rate_pct": 25.0,
    "calculation_method": "company_small_business",
    "rate_config_year": "2025-26"
  },
  "notes": null,
  "xero_report_fetched_at": "2026-03-31T10:01:00+11:00",
  "created_at": "2026-03-31T10:00:00+11:00",
  "updated_at": "2026-03-31T14:30:00+11:00",
  "scenarios": [
    {
      "id": "...",
      "title": "Prepay 6 months rent ($30K)",
      "risk_rating": "conservative",
      "impact_data": {"change": {"tax_saving": 7500.00}},
      "created_at": "2026-03-31T14:00:00+11:00"
    }
  ],
  "scenario_count": 3,
  "message_count": 8
}
```

**Error 404**: `{"error": "Tax plan not found", "code": "NOT_FOUND"}`

---

### PATCH /api/v1/tax-plans/{plan_id}

Update tax plan fields (status, notes, financials adjustments).

**Request Body** (all fields optional):
```json
{
  "status": "in_progress",
  "notes": "Discussed with client on 31 March. Leaning towards rent prepayment strategy.",
  "entity_type": "company"
}
```

**Response 200**: Updated tax plan (same schema as GET).

---

### DELETE /api/v1/tax-plans/{plan_id}

Delete a tax plan and all associated scenarios and messages.

**Response 204**: No content.

---

## Financials

### POST /api/v1/tax-plans/{plan_id}/financials/pull-xero

Pull the latest P&L from Xero and populate the plan's financials. Triggers a fresh Xero sync if data is stale.

**Request Body**:
```json
{
  "force_refresh": false
}
```

**Response 200**:
```json
{
  "financials_data": { "...same as above..." },
  "tax_position": { "...recalculated..." },
  "data_freshness": {
    "fetched_at": "2026-03-31T10:01:00+11:00",
    "is_fresh": true,
    "cache_age_minutes": 15
  }
}
```

**Error 400** (no Xero connection): `{"error": "Client has no connected Xero organisation", "code": "NO_XERO_CONNECTION"}`
**Error 502** (Xero API failure): `{"error": "Failed to fetch data from Xero", "code": "XERO_API_ERROR"}`

---

### PUT /api/v1/tax-plans/{plan_id}/financials

Save manually entered or adjusted financials. Recalculates the tax position.

**Request Body**:
```json
{
  "income": {
    "revenue": 500000.00,
    "other_income": 12000.00,
    "breakdown": [
      {"category": "Trading Income", "amount": 500000.00},
      {"category": "Interest Received", "amount": 12000.00}
    ]
  },
  "expenses": {
    "cost_of_sales": 200000.00,
    "operating_expenses": 150000.00,
    "breakdown": [
      {"category": "Wages & Salaries", "amount": 120000.00},
      {"category": "Rent", "amount": 36000.00}
    ]
  },
  "credits": {
    "payg_instalments": 25000.00,
    "payg_withholding": 0.00,
    "franking_credits": 0.00
  },
  "adjustments": [
    {"description": "Non-deductible entertainment", "amount": 5000.00, "type": "add_back"}
  ],
  "turnover": 512000.00,
  "has_help_debt": false
}
```

**Response 200**:
```json
{
  "financials_data": { "...saved financials..." },
  "tax_position": { "...recalculated..." }
}
```

---

## Scenarios

### GET /api/v1/tax-plans/{plan_id}/scenarios

List all scenarios for a tax plan.

**Response 200**:
```json
{
  "items": [
    {
      "id": "b1c2d3e4-f5a6-7890-bcde-f12345678901",
      "tax_plan_id": "f8a9b0c1-d2e3-4567-8901-abcdef123456",
      "title": "Prepay 6 months rent ($30K)",
      "description": "Prepay rent of $30,000 covering July to December 2026 before 30 June 2026. This qualifies as an immediate deduction under the 12-month prepayment rule (s82KZM ITAA 1997) for small business entities.",
      "assumptions": {
        "items": [
          "Rent prepayment covers 6 months (July-December 2026)",
          "Prepayment made before 30 June 2026",
          "Qualifies under 12-month prepayment rule (s82KZM ITAA 1997)"
        ]
      },
      "impact_data": {
        "before": {
          "taxable_income": 162000.00,
          "tax_payable": 40500.00,
          "net_position": 15500.00
        },
        "after": {
          "taxable_income": 132000.00,
          "tax_payable": 33000.00,
          "net_position": -8000.00
        },
        "change": {
          "taxable_income_change": -30000.00,
          "tax_saving": 7500.00,
          "net_benefit": 7500.00
        }
      },
      "risk_rating": "conservative",
      "compliance_notes": "Deduction available under s82KZM ITAA 1997 (prepaid expenses — 12-month rule). Must be paid before EOFY. ATO scrutinises large prepayments near year-end — ensure commercial rationale beyond tax benefit.",
      "cash_flow_impact": -22500.00,
      "sort_order": 1,
      "created_at": "2026-03-31T14:00:00+11:00"
    }
  ],
  "total": 3
}
```

---

### DELETE /api/v1/tax-plans/{plan_id}/scenarios/{scenario_id}

Delete a specific scenario.

**Response 204**: No content.

---

## AI Chat

### POST /api/v1/tax-plans/{plan_id}/chat

Send a message to the tax planning AI. Non-streaming — returns the full response.

**Request Body**:
```json
{
  "message": "Client wants to prepay 6 months of rent ($30K) before June 30. What's the tax impact?"
}
```

**Response 200**:
```json
{
  "message": {
    "id": "c2d3e4f5-a6b7-8901-cdef-234567890123",
    "role": "assistant",
    "content": "I've modelled the rent prepayment scenario. Here's the analysis:\n\n**Strategy: Prepay 6 months rent ($30,000)**\n\nThis qualifies as an immediate deduction under the 12-month prepayment rule...",
    "scenario_ids": ["b1c2d3e4-f5a6-7890-bcde-f12345678901"],
    "created_at": "2026-03-31T14:00:05+11:00"
  },
  "scenarios_created": [
    {
      "id": "b1c2d3e4-f5a6-7890-bcde-f12345678901",
      "title": "Prepay 6 months rent ($30K)",
      "impact_data": { "...as above..." },
      "risk_rating": "conservative"
    }
  ],
  "updated_tax_position": null
}
```

---

### POST /api/v1/tax-plans/{plan_id}/chat/stream

Send a message to the tax planning AI with streaming SSE response.

**Request Body**: Same as non-streaming.

**Response**: `text/event-stream`

```
data: {"type": "thinking", "content": "Analysing scenario..."}

data: {"type": "thinking", "content": "Calculating tax impact..."}

data: {"type": "content", "content": "I've modelled the rent prepayment"}

data: {"type": "content", "content": " scenario. Here's the analysis:"}

data: {"type": "scenario", "scenario": {"id": "...", "title": "Prepay 6 months rent ($30K)", "impact_data": {...}, "risk_rating": "conservative"}}

data: {"type": "done", "message_id": "...", "scenarios_created": ["..."]}
```

---

### GET /api/v1/tax-plans/{plan_id}/messages

Get conversation history for a tax plan.

**Query Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | int | 1 | Page number |
| `page_size` | int | 50 | Messages per page |

**Response 200**:
```json
{
  "items": [
    {
      "id": "d3e4f5a6-b7c8-9012-def0-345678901234",
      "role": "user",
      "content": "Client wants to prepay 6 months of rent ($30K) before June 30",
      "scenario_ids": [],
      "created_at": "2026-03-31T14:00:00+11:00"
    },
    {
      "id": "c2d3e4f5-a6b7-8901-cdef-234567890123",
      "role": "assistant",
      "content": "I've modelled the rent prepayment scenario...",
      "scenario_ids": ["b1c2d3e4-f5a6-7890-bcde-f12345678901"],
      "created_at": "2026-03-31T14:00:05+11:00"
    }
  ],
  "total": 8,
  "page": 1,
  "page_size": 50
}
```

---

## Export

### GET /api/v1/tax-plans/{plan_id}/export

Export the tax plan summary as a formatted PDF.

**Query Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `include_scenarios` | bool | true | Include scenario comparison table |
| `include_conversation` | bool | false | Include conversation history |

**Response 200**: `Content-Type: application/pdf`, `Content-Disposition: attachment; filename="tax-plan-smith-trading-2025-26.pdf"`

**Error 400**: `{"error": "Tax plan has no calculated tax position", "code": "NO_TAX_POSITION"}`

---

## Tax Rate Configuration (Admin)

### GET /api/v1/tax-rates/{financial_year}

Get all tax rate configurations for a financial year.

**Response 200**:
```json
{
  "financial_year": "2025-26",
  "rates": [
    {
      "id": "...",
      "rate_type": "individual",
      "rates_data": {
        "brackets": [
          {"min": 0, "max": 18200, "rate": 0.00},
          {"min": 18201, "max": 45000, "rate": 0.16},
          {"min": 45001, "max": 135000, "rate": 0.30},
          {"min": 135001, "max": 190000, "rate": 0.37},
          {"min": 190001, "max": null, "rate": 0.45}
        ]
      },
      "effective_from": "2025-07-01"
    },
    {
      "id": "...",
      "rate_type": "company",
      "rates_data": {
        "small_business_rate": 0.25,
        "standard_rate": 0.30,
        "small_business_turnover_threshold": 50000000
      },
      "effective_from": "2025-07-01"
    }
  ]
}
```

---

## Shared Types

**Valid Entity Types**: `company`, `individual`, `trust`, `partnership`

**Valid Plan Statuses**: `draft`, `in_progress`, `finalised`

**Valid Data Sources**: `xero`, `manual`, `xero_with_adjustments`

**Valid Risk Ratings**: `conservative`, `moderate`, `aggressive`
