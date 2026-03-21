# Implementation Plan: Data Quality Scoring

**Branch**: `feature/008-data-quality-scoring` | **Date**: 2025-12-29 | **Spec**: [spec.md](./spec.md)

## Summary

Implement a data quality scoring system that analyzes synced Xero data to produce a 0-100% quality score across five dimensions (Freshness, Reconciliation, Categorization, Completeness, PAYG Readiness). The system detects specific issues, integrates with the existing dashboard, and provides a detailed quality tab in the client detail view.

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Pydantic v2, Celery
**Storage**: PostgreSQL 16 with RLS
**Testing**: pytest, pytest-asyncio, httpx
**Target Platform**: Docker Compose (local), AWS ECS (production)
**Project Type**: Web application (backend + frontend)
**Performance Goals**: Quality calculation <5s for typical client
**Constraints**: Must not block sync completion, tenant isolation via RLS

## Constitution Check

| Requirement | Compliant | Notes |
|-------------|-----------|-------|
| Modular Monolith | ✅ | New `quality` module under `app/modules/` |
| Repository Pattern | ✅ | QualityRepository for DB access |
| Multi-tenancy (RLS) | ✅ | All tables have tenant_id, RLS policies |
| Test-First | ✅ | Unit tests for scoring logic, integration tests for API |
| Pydantic Schemas | ✅ | All API I/O uses Pydantic models |
| Audit Logging | ✅ | Score calculations and dismissals logged |

## Project Structure

### Documentation (this feature)

```text
specs/008-data-quality-scoring/
├── spec.md              # Requirements document
├── plan.md              # This file
└── tasks.md             # Task list (generated next)
```

### Source Code Changes

```text
backend/
├── alembic/versions/
│   └── 005_quality_scoring.py      # NEW: Migration for quality tables
├── app/
│   └── modules/
│       ├── quality/                 # NEW: Quality scoring module
│       │   ├── __init__.py
│       │   ├── router.py           # API endpoints
│       │   ├── service.py          # Quality calculation logic
│       │   ├── repository.py       # Database access
│       │   ├── schemas.py          # Pydantic models
│       │   ├── models.py           # SQLAlchemy models
│       │   ├── calculator.py       # Score calculation algorithms
│       │   └── issue_detector.py   # Issue detection logic
│       ├── clients/
│       │   ├── service.py          # UPDATE: Include quality in client detail
│       │   └── schemas.py          # UPDATE: Add quality fields
│       └── dashboard/
│           ├── service.py          # UPDATE: Include quality aggregates
│           └── schemas.py          # UPDATE: Add quality fields
├── tasks/
│   └── quality.py                  # NEW: Celery tasks for quality calculation

frontend/
├── src/
│   ├── app/(protected)/clients/[id]/
│   │   └── page.tsx               # UPDATE: Add Quality tab
│   └── components/
│       └── quality/               # NEW: Quality components
│           ├── QualityScoreCard.tsx
│           ├── QualityDimensionBreakdown.tsx
│           ├── QualityIssuesList.tsx
│           └── QualityBadge.tsx
```

## Architecture Design

### Quality Calculation Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    QUALITY CALCULATION FLOW                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  [Xero Sync Completes]                                          │
│         │                                                        │
│         ▼                                                        │
│  [Celery Task: calculate_quality]                               │
│         │                                                        │
│         ├──► DataFreshnessCalculator.calculate()                │
│         │         └── Check last_full_sync_at timestamp          │
│         │                                                        │
│         ├──► ReconciliationCalculator.calculate()               │
│         │         └── Query bank transactions, count reconciled  │
│         │                                                        │
│         ├──► CategorizationCalculator.calculate()               │
│         │         └── Query invoices + txns, check tax_type      │
│         │                                                        │
│         ├──► CompletenessCalculator.calculate()                 │
│         │         └── Check presence of accounts, contacts, etc  │
│         │                                                        │
│         ├──► PaygReadinessCalculator.calculate()                │
│         │         └── Check has_payroll_access, pay_runs exist   │
│         │                                                        │
│         ▼                                                        │
│  [Aggregate Weighted Score]                                     │
│         │                                                        │
│         ├──► IssueDetector.detect_issues()                      │
│         │         └── Generate QualityIssue records              │
│         │                                                        │
│         ▼                                                        │
│  [Save QualityScore + QualityIssues to DB]                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Database Schema

```sql
-- Migration: 005_quality_scoring.py

CREATE TABLE quality_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    connection_id UUID NOT NULL REFERENCES xero_connections(id),
    quarter INTEGER NOT NULL CHECK (quarter >= 1 AND quarter <= 4),
    fy_year INTEGER NOT NULL CHECK (fy_year >= 2020),

    -- Overall weighted score
    overall_score DECIMAL(5,2) NOT NULL CHECK (overall_score >= 0 AND overall_score <= 100),

    -- Individual dimension scores (0-100)
    freshness_score DECIMAL(5,2) NOT NULL,
    reconciliation_score DECIMAL(5,2) NOT NULL,
    categorization_score DECIMAL(5,2) NOT NULL,
    completeness_score DECIMAL(5,2) NOT NULL,
    payg_score DECIMAL(5,2),  -- NULL if has_payroll_access = false

    -- Calculation metadata
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    calculation_duration_ms INTEGER,
    trigger_reason VARCHAR(50),  -- 'sync', 'manual', 'scheduled'

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Unique per connection per quarter
    UNIQUE(connection_id, quarter, fy_year)
);

CREATE TABLE quality_issues (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    connection_id UUID NOT NULL REFERENCES xero_connections(id),
    quarter INTEGER NOT NULL,
    fy_year INTEGER NOT NULL,

    -- Issue identification
    code VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('critical', 'error', 'warning', 'info')),
    title VARCHAR(255) NOT NULL,
    description TEXT,

    -- Affected entities
    affected_entity_type VARCHAR(50),
    affected_count INTEGER DEFAULT 0,
    affected_ids JSONB DEFAULT '[]'::jsonb,
    suggested_action TEXT,

    -- Lifecycle
    first_detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,

    -- Dismissal
    dismissed BOOLEAN NOT NULL DEFAULT FALSE,
    dismissed_by UUID REFERENCES users(id),
    dismissed_at TIMESTAMPTZ,
    dismissed_reason TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_quality_scores_connection ON quality_scores(connection_id);
CREATE INDEX idx_quality_scores_quarter ON quality_scores(quarter, fy_year);
CREATE INDEX idx_quality_scores_tenant ON quality_scores(tenant_id);

CREATE INDEX idx_quality_issues_connection ON quality_issues(connection_id);
CREATE INDEX idx_quality_issues_quarter ON quality_issues(quarter, fy_year);
CREATE INDEX idx_quality_issues_severity ON quality_issues(severity);
CREATE INDEX idx_quality_issues_dismissed ON quality_issues(dismissed);

-- RLS Policies
ALTER TABLE quality_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE quality_issues ENABLE ROW LEVEL SECURITY;

CREATE POLICY quality_scores_tenant_isolation ON quality_scores
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY quality_issues_tenant_isolation ON quality_issues
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid);
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/clients/{id}/quality` | Get quality score summary |
| GET | `/api/v1/clients/{id}/quality/issues` | List quality issues |
| POST | `/api/v1/clients/{id}/quality/recalculate` | Trigger recalculation |
| POST | `/api/v1/clients/{id}/quality/issues/{issue_id}/dismiss` | Dismiss an issue |

### Quality Score Weights

```python
DIMENSION_WEIGHTS = {
    "freshness": 0.20,      # 20%
    "reconciliation": 0.30, # 30%
    "categorization": 0.20, # 20%
    "completeness": 0.15,   # 15%
    "payg_readiness": 0.15, # 15%
}
```

### Issue Codes

```python
class IssueCode(str, Enum):
    STALE_DATA = "STALE_DATA"
    STALE_DATA_CRITICAL = "STALE_DATA_CRITICAL"
    UNRECONCILED_TXN = "UNRECONCILED_TXN"
    MISSING_GST_CODE = "MISSING_GST_CODE"
    INVALID_GST_CODE = "INVALID_GST_CODE"
    NO_INVOICES = "NO_INVOICES"
    NO_TRANSACTIONS = "NO_TRANSACTIONS"
    MISSING_PAYROLL = "MISSING_PAYROLL"
    INCOMPLETE_PAYROLL = "INCOMPLETE_PAYROLL"
```

## Integration Points

### 1. Post-Sync Quality Calculation

After `sync_all_data()` completes in `tasks/xero.py`:

```python
# In run_sync task, after sync completes:
from app.tasks.quality import calculate_quality_score

# Trigger quality calculation
calculate_quality_score.delay(
    connection_id=str(connection_id),
    trigger_reason="sync"
)
```

### 2. Dashboard Integration

Update `dashboard/service.py` to include quality aggregates:

```python
async def get_dashboard_summary(...) -> DashboardSummaryResponse:
    # Existing code...

    # Add quality aggregates
    quality_summary = await quality_service.get_portfolio_quality_summary(
        tenant_id=tenant_id,
        quarter=quarter,
        fy_year=fy_year
    )

    return DashboardSummaryResponse(
        # ... existing fields
        quality=quality_summary
    )
```

### 3. Client Detail Integration

Update `clients/service.py` to include quality in client detail:

```python
async def get_client_detail(...) -> ClientDetailResponse:
    # Existing code...

    quality = await quality_service.get_quality_summary(
        connection_id=connection_id,
        quarter=quarter,
        fy_year=fy_year
    )

    return ClientDetailResponse(
        # ... existing fields
        quality_score=quality.overall_score,
        quality_issues_count=quality.issue_counts.total
    )
```

## Frontend Components

### QualityBadge

Small badge showing score with color:

```tsx
<QualityBadge score={87} /> // Green badge showing "87%"
<QualityBadge score={65} /> // Yellow badge showing "65%"
<QualityBadge score={35} /> // Red badge showing "35%"
```

### QualityScoreCard

Large card for client detail page:

```tsx
<QualityScoreCard
  score={87}
  lastChecked="2025-12-29T10:30:00Z"
  trend="stable"
/>
```

### QualityDimensionBreakdown

Progress bars for each dimension:

```tsx
<QualityDimensionBreakdown
  dimensions={{
    freshness: { score: 100, weight: 20 },
    reconciliation: { score: 75, weight: 30 },
    categorization: { score: 90, weight: 20 },
    completeness: { score: 100, weight: 15 },
    payg: { score: null, weight: 15, applicable: false }
  }}
/>
```

### QualityIssuesList

List of detected issues with actions:

```tsx
<QualityIssuesList
  issues={issues}
  onDismiss={(issueId, reason) => handleDismiss(issueId, reason)}
  onViewDetails={(issueId) => handleViewDetails(issueId)}
/>
```

## Testing Strategy

### Unit Tests

```
backend/tests/unit/modules/quality/
├── test_calculator.py       # Test dimension calculators
├── test_issue_detector.py   # Test issue detection
├── test_service.py          # Test service methods
└── test_repository.py       # Test database operations
```

### Integration Tests

```
backend/tests/integration/api/
└── test_quality_endpoints.py  # Test all quality API endpoints
```

### Test Cases

1. **Freshness Calculator**
   - Synced within 24h → 100%
   - Synced 48h ago → 75%
   - Never synced → 0%

2. **Reconciliation Calculator**
   - All transactions reconciled → 100%
   - Half reconciled → 50%
   - None reconciled → 0%
   - No transactions → 100% (nothing to reconcile)

3. **Issue Detection**
   - Stale data → STALE_DATA issue created
   - Unreconciled transactions → UNRECONCILED_TXN issue with count

4. **API Endpoints**
   - GET quality returns correct score
   - POST recalculate triggers calculation
   - POST dismiss marks issue as dismissed
   - RLS prevents cross-tenant access

## Performance Considerations

1. **Efficient Queries**: Use aggregate queries, not N+1
2. **Background Processing**: Quality calculation runs in Celery, doesn't block sync
3. **Caching**: Store calculated scores, recalculate only on sync or manual trigger
4. **Index Usage**: Ensure queries use connection_id and quarter indexes

## Error Handling

1. **Missing Data**: If connection has no data, score gracefully (e.g., completeness = 0)
2. **Calculation Errors**: Log and store partial results, don't fail entire calculation
3. **API Errors**: Return appropriate HTTP status codes with error details

## Rollout Plan

1. **Phase 1**: Database migration, models, repository
2. **Phase 2**: Calculator and issue detector implementation
3. **Phase 3**: API endpoints
4. **Phase 4**: Integration with sync (Celery task)
5. **Phase 5**: Dashboard integration
6. **Phase 6**: Client detail Quality tab (frontend)
7. **Phase 7**: Testing and validation
