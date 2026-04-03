# Data Model: Multi-Agent Tax Planning Pipeline

**Date**: 2026-04-03  
**Feature**: 041-multi-agent-tax-planning

## Entity Relationship

```
TaxPlan (existing)
  │
  ├── 1:N ── TaxPlanAnalysis (NEW)
  │            │
  │            └── 1:N ── ImplementationItem (NEW)
  │
  ├── 1:N ── TaxScenario (existing)
  ├── 1:N ── TaxPlanMessage (existing)
  └── N:1 ── XeroConnection (existing)
```

## New Tables

### tax_plan_analyses

Stores the complete output of the multi-agent pipeline. One analysis per generation run, versioned for re-generation support.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | UUID | No | Primary key |
| `tenant_id` | UUID (FK tenants) | No | Multi-tenancy (RLS) |
| `tax_plan_id` | UUID (FK tax_plans) | No | Parent tax plan |
| `version` | Integer | No | Auto-incrementing per plan (1, 2, 3...) |
| `is_current` | Boolean | No | True for the latest version |
| `status` | String(20) | No | generating, draft, reviewed, approved, shared |
| **Agent outputs** | | | |
| `client_profile` | JSONB | Yes | Profiler agent output: entity classification, eligibility flags, thresholds |
| `strategies_evaluated` | JSONB | Yes | Scanner agent output: array of all strategies with applicability |
| `recommended_scenarios` | JSONB | Yes | Modeller agent output: top strategies with calculator numbers |
| `combined_strategy` | JSONB | Yes | Modeller agent output: optimal combination analysis |
| **Documents** | | | |
| `accountant_brief` | Text | Yes | Advisor agent output: technical markdown document |
| `client_summary` | Text | Yes | Advisor agent output: plain-language markdown document |
| **Quality** | | | |
| `review_result` | JSONB | Yes | Reviewer agent output: verification results |
| `review_passed` | Boolean | Yes | True if all quality checks passed |
| **Phase 2 extension fields** | | | |
| `entities` | JSONB | Yes | Array of entity profiles (Phase 1: single item) |
| `group_structure` | JSONB | Yes | Trust → beneficiary relationships (Phase 2) |
| `distribution_plan` | JSONB | Yes | Optimal allocation (Phase 2) |
| `entity_summaries` | JSONB | Yes | Per-beneficiary summaries (Phase 2) |
| **Metadata** | | | |
| `generation_time_ms` | Integer | Yes | Pipeline execution time |
| `token_usage` | JSONB | Yes | Per-agent token consumption |
| `generated_by` | UUID | Yes | User who triggered generation |
| `reviewed_by` | UUID | Yes | User who approved |
| `shared_at` | DateTime(tz) | Yes | When shared to client portal |
| `created_at` | DateTime(tz) | No | Record creation time |
| `updated_at` | DateTime(tz) | No | Last modification time |

**Indexes:**
- `ix_tax_plan_analyses_plan_id` on `(tax_plan_id)`
- `ix_tax_plan_analyses_tenant_status` on `(tenant_id, status)`
- Unique constraint on `(tax_plan_id, version)`

**Constraints:**
- Only one row per `tax_plan_id` can have `is_current = true`
- `status` transitions: generating → draft → reviewed → approved → shared

### implementation_items

Individual action items within a tax plan analysis. Tracks progress across accountant and client portal views.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | UUID | No | Primary key |
| `tenant_id` | UUID (FK tenants) | No | Multi-tenancy (RLS) |
| `analysis_id` | UUID (FK tax_plan_analyses) | No | Parent analysis |
| `sort_order` | Integer | No | Display order |
| `title` | String(255) | No | Action title (plain language) |
| `description` | Text | Yes | Detailed description |
| `strategy_ref` | String(100) | Yes | Links to strategy in `strategies_evaluated` |
| `deadline` | Date | Yes | Implementation deadline |
| `estimated_saving` | Decimal | Yes | Projected tax saving from this action |
| `entity_id` | UUID | Yes | Which entity this applies to (Phase 2: specific beneficiary) |
| `risk_rating` | String(20) | Yes | conservative, moderate, aggressive |
| `compliance_notes` | Text | Yes | ATO provisions, documentation requirements |
| `client_visible` | Boolean | No | Whether to show in client portal (default true) |
| `status` | String(20) | No | pending, in_progress, completed, skipped |
| `completed_at` | DateTime(tz) | Yes | When marked complete |
| `completed_by` | String(20) | Yes | 'accountant' or 'client' |
| `created_at` | DateTime(tz) | No | Record creation time |
| `updated_at` | DateTime(tz) | No | Last modification time |

**Indexes:**
- `ix_implementation_items_analysis_id` on `(analysis_id)`
- `ix_implementation_items_tenant_status` on `(tenant_id, status)`

## JSONB Schema Details

### client_profile (Profiler output)

```json
{
  "entity_type": "company",
  "entity_classification": "Small Business Entity",
  "sbe_eligible": true,
  "aggregated_turnover": 401933,
  "applicable_tax_rate": 0.25,
  "has_help_debt": false,
  "financial_year": "2025-26",
  "key_thresholds": {
    "sbe_turnover_limit": 10000000,
    "base_rate_entity_limit": 50000000,
    "instant_asset_writeoff_limit": 20000
  },
  "financials_summary": {
    "total_income": 401933,
    "total_expenses": 141211,
    "net_profit": 260721,
    "taxable_income": 260721
  }
}
```

### strategies_evaluated (Scanner output)

```json
[
  {
    "strategy_id": "timing-prepaid-expenses",
    "category": "timing",
    "name": "Prepaid Operating Expenses",
    "applicable": true,
    "applicability_reason": "SBE eligible, 12-month rule applies",
    "estimated_impact_range": { "min": 3000, "max": 8000 },
    "risk_rating": "conservative",
    "compliance_refs": ["s8-1 ITAA 1997", "TR 98/7"],
    "eofy_deadline": "2026-06-30",
    "requires_cash_outlay": true
  },
  {
    "strategy_id": "depreciation-instant-writeoff",
    "category": "depreciation",
    "name": "Instant Asset Write-Off",
    "applicable": true,
    "applicability_reason": "SBE eligible, assets < $20K threshold",
    "estimated_impact_range": { "min": 2500, "max": 5000 },
    "risk_rating": "conservative",
    "compliance_refs": ["s328-180 ITAA 1997"],
    "eofy_deadline": "2026-06-30",
    "requires_cash_outlay": true
  }
]
```

### recommended_scenarios (Modeller output)

```json
[
  {
    "strategy_id": "timing-prepaid-expenses",
    "scenario_title": "Prepaid Expenses Strategy",
    "description": "Prepay 6 months of office rent ($25,000) before EOFY",
    "assumptions": ["$25,000 prepayment", "12-month rule applies", "Paid before 30 June"],
    "impact": {
      "before": { "taxable_income": 260721, "tax_payable": 65180 },
      "after": { "taxable_income": 235721, "tax_payable": 58930 },
      "change": { "taxable_income_change": -25000, "tax_saving": 6250 }
    },
    "cash_flow_impact": -18750,
    "risk_rating": "conservative",
    "compliance_notes": "Must meet 12-month rule under TR 98/7"
  }
]
```

### combined_strategy (Modeller output)

```json
{
  "recommended_combination": ["timing-prepaid-expenses", "depreciation-instant-writeoff", "super-additional-contributions"],
  "total_tax_saving": 20000,
  "total_cash_outlay": 60000,
  "net_cash_benefit": -40000,
  "new_taxable_income": 180721,
  "new_tax_payable": 45180,
  "notes": "All three strategies are complementary with no conflicts"
}
```

## Existing Tables Modified

### tax_plans (minor addition)

| Column | Change |
|--------|--------|
| `current_analysis_id` | New nullable UUID FK to `tax_plan_analyses.id` — quick access to the current analysis |

## State Machine

### TaxPlanAnalysis.status

```
generating → draft → reviewed → approved → shared
                ↑                    │
                └────────────────────┘  (re-generate creates new version)
```

- `generating`: Pipeline is running (Celery task in progress)
- `draft`: Pipeline complete, awaiting accountant review
- `reviewed`: Accountant has reviewed (possibly edited)
- `approved`: Accountant has approved for sharing
- `shared`: Client summary visible in portal
