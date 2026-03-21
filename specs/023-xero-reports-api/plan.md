# Implementation Plan: Xero Reports API Integration

**Branch**: `023-xero-reports-api` | **Date**: 2026-01-01 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/023-xero-reports-api/spec.md`

## Summary

Integrate Xero Reports API to fetch pre-calculated financial reports (P&L, Balance Sheet, Aged Receivables/Payables, Trial Balance, Bank Summary, Budget Summary). Following the established Xero integration patterns (client.py, repository.py, service.py), we add new models for report storage, API client methods for each report type, and expose reports through the existing router for AI agent consumption and UI display.

**Technical Approach**:
- Extend `XeroClient` with report-fetching methods
- Add `XeroReport`, `XeroReportRow` models with JSONB for flexible storage
- Create `XeroReportRepository` and `XeroReportService` following existing patterns
- Background Celery task for nightly report sync
- REST endpoints for report retrieval and on-demand refresh
- Integration with AI agents via enhanced context

---

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: FastAPI, SQLAlchemy 2.x, Pydantic v2, httpx, Celery
**Storage**: PostgreSQL 16 with JSONB for flexible report data
**Testing**: pytest, pytest-asyncio, httpx for API testing
**Target Platform**: AWS ECS/Fargate (Sydney region)
**Project Type**: Web application (backend + frontend)
**Performance Goals**: Report sync for 100 clients < 30 minutes, API response < 500ms
**Constraints**: Xero rate limit 60 req/min, ATO 7-year data retention
**Scale/Scope**: Up to 1,000 clients per tenant, ~7 report types per client

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Compliance | Notes |
|-----------|------------|-------|
| **Modular Monolith** | ✅ PASS | Reports added to existing `integrations/xero/` module |
| **Repository Pattern** | ✅ PASS | `XeroReportRepository` follows established pattern |
| **Multi-tenancy (RLS)** | ✅ PASS | All report tables include `tenant_id` |
| **Audit-First** | ✅ PASS | Audit events for sync operations and report access |
| **Type Hints** | ✅ PASS | Pydantic schemas, typed functions throughout |
| **Test-First** | ✅ PASS | Contract tests for Xero API, integration tests for sync |
| **API Conventions** | ✅ PASS | RESTful endpoints under `/api/v1/clients/{id}/reports/` |
| **External Integration Pattern** | ✅ PASS | Rate limiting, token refresh, error handling per constitution |

**No violations requiring justification.**

---

## Project Structure

### Documentation (this feature)

```text
specs/023-xero-reports-api/
├── plan.md              # This file
├── research.md          # Phase 0: Xero Reports API research
├── data-model.md        # Phase 1: XeroReport models
├── quickstart.md        # Phase 1: Developer guide
├── contracts/           # Phase 1: OpenAPI specs
│   └── reports-api.yaml
└── tasks.md             # Phase 2: Implementation tasks
```

### Source Code (repository root)

```text
backend/
├── app/
│   └── modules/
│       └── integrations/
│           └── xero/
│               ├── client.py           # + Report API methods
│               ├── models.py           # + XeroReport, XeroReportRow
│               ├── repository.py       # + XeroReportRepository
│               ├── service.py          # + XeroReportService
│               ├── schemas.py          # + Report schemas
│               ├── router.py           # + Report endpoints
│               └── transformers.py     # + Report data transformers
│
└── tests/
    ├── unit/
    │   └── modules/
    │       └── integrations/
    │           └── xero/
    │               └── test_report_service.py
    ├── integration/
    │   └── api/
    │       └── test_xero_reports.py
    └── contract/
        └── adapters/
            └── test_xero_reports_api.py

frontend/
└── src/
    ├── app/
    │   └── (protected)/
    │       └── clients/
    │           └── [id]/
    │               └── reports/
    │                   └── page.tsx       # Reports tab
    ├── components/
    │   └── reports/
    │       ├── ProfitLossReport.tsx
    │       ├── BalanceSheetReport.tsx
    │       ├── AgedReceivablesReport.tsx
    │       ├── AgedPayablesReport.tsx
    │       └── ReportSelector.tsx
    └── lib/
        └── api/
            └── reports.ts             # API client methods
```

**Structure Decision**: Extends existing `integrations/xero/` module rather than creating a separate reports module. This maintains cohesion with existing Xero sync infrastructure and shares connection management, rate limiting, and token refresh logic.

---

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND                                       │
│                                                                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │ ReportSelector  │  │ ProfitLoss      │  │ BalanceSheet    │  ...    │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘         │
│           │                    │                    │                   │
│           └────────────────────┼────────────────────┘                   │
│                                ▼                                        │
│                    ┌─────────────────────┐                              │
│                    │ reports.ts (API)    │                              │
│                    └─────────┬───────────┘                              │
└──────────────────────────────┼──────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           BACKEND                                        │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                        router.py                                 │   │
│  │  GET /clients/{id}/reports/{type}                               │   │
│  │  POST /clients/{id}/reports/{type}/refresh                      │   │
│  └────────────────────────────┬────────────────────────────────────┘   │
│                               │                                         │
│                               ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    XeroReportService                             │   │
│  │  get_report() → Check cache → Fetch if stale → Transform        │   │
│  │  sync_all_reports() → Batch sync for client                     │   │
│  └────────────────────────────┬────────────────────────────────────┘   │
│                               │                                         │
│                ┌──────────────┼──────────────┐                         │
│                ▼              ▼              ▼                         │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐          │
│  │ XeroReport      │ │ XeroClient      │ │ AI Agents       │          │
│  │ Repository      │ │ (API calls)     │ │ (Context)       │          │
│  └────────┬────────┘ └────────┬────────┘ └─────────────────┘          │
│           │                   │                                        │
│           ▼                   ▼                                        │
│  ┌─────────────────┐ ┌─────────────────┐                              │
│  │   PostgreSQL    │ │   Xero API      │                              │
│  │   (JSONB)       │ │   Reports       │                              │
│  └─────────────────┘ └─────────────────┘                              │
└─────────────────────────────────────────────────────────────────────────┘
```

### Sync Strategy

```
REPORT SYNC FLOW
═══════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────┐
│                     NIGHTLY BATCH SYNC (Celery)                          │
│                                                                         │
│  For each active XeroConnection:                                        │
│    1. Fetch P&L (current FY + prior FY)                                │
│    2. Fetch Balance Sheet (as of today)                                │
│    3. Fetch Aged Receivables                                           │
│    4. Fetch Aged Payables                                              │
│    5. Fetch Trial Balance (current FY)                                 │
│    6. Fetch Bank Summary (current period)                              │
│    7. Fetch Budget Summary (if budget exists)                          │
│                                                                         │
│  Rate limiting: 60 req/min → batch timing                              │
│  Error handling: Skip failed, log, continue                            │
│  Retry: Failed syncs queued for retry with backoff                     │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                     ON-DEMAND REFRESH                                    │
│                                                                         │
│  User triggers: POST /clients/{id}/reports/{type}/refresh              │
│    1. Check rate limit budget                                          │
│    2. Fetch specific report from Xero                                  │
│    3. Update cache                                                     │
│    4. Return fresh data                                                │
│                                                                         │
│  Throttle: Max 1 refresh per report type per 5 minutes                 │
└─────────────────────────────────────────────────────────────────────────┘
```

### Caching Strategy

```
CACHE TTL BY REPORT TYPE
═══════════════════════════════════════════════════════════════════════════

Report Type         │ Historical Period  │ Current Period
────────────────────┼───────────────────┼───────────────────
Profit & Loss       │ Indefinite         │ 1 hour (stale OK)
Balance Sheet       │ Indefinite         │ 1 hour
Aged Receivables    │ N/A (point-in-time)│ 4 hours
Aged Payables       │ N/A (point-in-time)│ 4 hours
Trial Balance       │ Indefinite         │ 1 hour
Bank Summary        │ Indefinite         │ 4 hours
Budget Summary      │ Indefinite         │ 24 hours

Storage:
- Report metadata in PostgreSQL (xero_reports table)
- Report row data as JSONB (flexible structure per report type)
- Historical versions kept for 7 years (ATO compliance)
```

---

## Data Flow

### Report Request Flow

```
1. User clicks "View P&L Report" for client
   │
   ▼
2. Frontend: GET /api/v1/clients/{id}/reports/profit-and-loss?period=2025-FY
   │
   ▼
3. Backend: XeroReportService.get_report(client_id, "profit_and_loss", period)
   │
   ├─► Cache hit (fresh) → Return cached report
   │
   └─► Cache miss or stale
       │
       ▼
4. XeroClient.get_profit_and_loss(access_token, tenant_id, from_date, to_date)
   │
   ▼
5. Xero API returns report JSON
   │
   ▼
6. Transform to internal format, save to DB
   │
   ▼
7. Return XeroReportResponse to frontend
```

### AI Agent Integration

```
AGENT CONTEXT ENHANCEMENT
═══════════════════════════════════════════════════════════════════════════

Before (current state):
  Agent receives: invoices, transactions, contacts, accounts
  Limitation: Must calculate P&L, ratios manually (error-prone)

After (with reports):
  Agent receives: + P&L summary, Balance Sheet, Aged Reports

  Financial Health Agent context now includes:
  {
    "profit_and_loss": {
      "revenue": 245000,
      "cost_of_sales": 98000,
      "gross_profit": 147000,
      "expenses": 112000,
      "net_profit": 35000
    },
    "balance_sheet": {
      "current_assets": 180000,
      "current_liabilities": 85000,
      "current_ratio": 2.12
    },
    "aged_receivables": {
      "current": 45000,
      "30_days": 12000,
      "60_days": 3000,
      "90_plus": 8500
    }
  }

  Enables: Accurate ratio analysis, trend detection, collection risk alerts
```

---

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Storage format | JSONB in PostgreSQL | Reports have varying structures; JSONB provides flexibility while maintaining queryability |
| Report versioning | Keep historical snapshots | ATO compliance requires 7-year retention; enables trend analysis |
| Cache invalidation | TTL-based + on-demand | Balance between freshness and API quota usage |
| Sync scheduling | Nightly batch + on-demand | Minimize API calls while ensuring data availability |
| Module location | Extend `xero/` module | Shares infrastructure (tokens, rate limiting, connections) |

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Xero rate limits exceeded | Staggered sync, priority queue, backoff retries |
| Large report sizes | Pagination for aged reports, streaming for large datasets |
| Report format changes | JSONB storage handles schema evolution; version tracking |
| Connection token expiry during sync | Token refresh before each batch, graceful failure handling |
| Missing data for some clients | Handle empty reports gracefully, clear UI indication |

---

## Dependencies

### Internal Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| Spec 003: Xero OAuth | ✅ Complete | Connection management exists |
| Spec 004: Xero Data Sync | ✅ Complete | Sync patterns established |
| Spec 014: Multi-Agent Framework | ✅ Complete | Agent context enhancement target |
| Phase D: Monetization | ✅ Complete | Feature gating in place |

### External Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| Xero Reports API | v2 | Data source |
| PostgreSQL | 16+ | Storage (JSONB) |
| Celery | 5.x | Background sync |
| httpx | 0.27+ | Async HTTP client |

---

## Phase References

- **Phase 0**: See [research.md](./research.md) for Xero API research
- **Phase 1**: See [data-model.md](./data-model.md) for entity definitions
- **Phase 1**: See [contracts/reports-api.yaml](./contracts/reports-api.yaml) for API specs
- **Phase 1**: See [quickstart.md](./quickstart.md) for developer guide
