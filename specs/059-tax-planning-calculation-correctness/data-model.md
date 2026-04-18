# Phase 1 Data Model — Tax Planning Calculation Correctness

**Feature**: `059-tax-planning-calculation-correctness`
**Date**: 2026-04-18

This document captures the schema and domain-object changes needed to deliver the spec. Minimal churn: 3 new columns on one existing table, 1 new partial unique index, and a documented `projection_metadata` key inside an existing JSONB field.

---

## Summary of changes

| Entity | Change type | Detail |
|--------|------------|--------|
| `TaxScenario` | New column | `strategy_category` (Enum, NOT NULL, default `other`) |
| `TaxScenario` | New column | `requires_group_model` (Boolean, NOT NULL, default `false`) |
| `TaxScenario` | New column | `source_tags` (JSONB, NOT NULL, default `{}`) |
| `TaxScenario` | New index | `ix_tax_scenarios_plan_normalized_title` — partial unique on `(tax_plan_id, lower(trim(title)))` |
| `TaxPlan.financials_data` | New JSON key | `projection_metadata` — structured sub-document (no migration — JSONB shape) |
| `TaxPlanMessage.citation_verification` | Extended enum | `status` may now take `"low_confidence"` (no migration — JSONB enum) |
| `CitationVerificationStatus` frontend enum | Synced | add `"low_confidence"` in `frontend/src/types/tax-planning.ts` |

No new tables. No changes to `TaxPlan`, `TaxPlanAnalysis`, `XeroPayRun`, `XeroConnection`, or any other entity.

---

## Entity: `TaxScenario` (modified)

**Module**: `backend/app/modules/tax_planning/models.py`

### Before (current relevant shape)

```python
class TaxScenario(Base):
    __tablename__ = "tax_scenarios"
    __table_args__ = (Index("ix_tax_scenarios_tax_plan_id", "tax_plan_id"),)

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tax_plan_id: Mapped[UUID] = mapped_column(ForeignKey("tax_plans.id"), nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text)
    impact_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    assumptions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # … timestamps, relationships …
```

### After (new fields appended; existing fields unchanged)

```python
class TaxScenario(Base):
    # … existing columns …

    # NEW
    strategy_category: Mapped[StrategyCategory] = mapped_column(
        SQLEnum(StrategyCategory, name="strategy_category_enum"),
        nullable=False,
        default=StrategyCategory.OTHER,
        server_default=StrategyCategory.OTHER.value,
    )
    requires_group_model: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )
    source_tags: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}",
    )

    __table_args__ = (
        Index("ix_tax_scenarios_tax_plan_id", "tax_plan_id"),
        # NEW: enforce dedup per plan, case-insensitive, whitespace-trimmed
        Index(
            "ix_tax_scenarios_plan_normalized_title",
            "tax_plan_id",
            func.lower(func.trim(column("title"))),
            unique=True,
        ),
    )
```

### Validation & invariants

- **Uniqueness**: two scenarios within the same `tax_plan_id` cannot share a normalised title (case-insensitive + whitespace-trimmed). Enforced at DB level, backed up by `repository.upsert_by_normalized_title`.
- **`strategy_category`**: one of the closed enum values — see `StrategyCategory` below.
- **`requires_group_model`**: derived from `strategy_category` via `strategy_category.requires_group_model(category)` at persist time. Never set directly from LLM output — the LLM emits `strategy_category`, the service computes the boolean.
- **`source_tags`**: keys are JSON Pointer strings (RFC 6901) addressing into `impact_data` and `assumptions`. Values are one of `{"confirmed", "derived", "estimated"}`. Tag coverage is validated at serialise time — every numeric leaf in `impact_data.modified_*` and `assumptions[*].amount` MUST have a corresponding tag.

### State transitions

Provenance transitions per-field (tracked in `source_tags`):

```
estimated ──(accountant confirms via PATCH endpoint)──▶ confirmed
  │
  └──(modeller regenerates scenario wholesale)──▶ estimated  (reset)

derived ──(accountant overrides value in UI)──▶ confirmed

confirmed ── (terminal: no automatic transitions away)
```

---

## New supporting types

### Enum: `StrategyCategory`

**Module**: `backend/app/modules/tax_planning/strategy_category.py`

```python
from enum import Enum

class StrategyCategory(str, Enum):
    PREPAYMENT = "prepayment"
    CAPEX_DEDUCTION = "capex_deduction"
    SUPER_CONTRIBUTION = "super_contribution"
    DIRECTOR_SALARY = "director_salary"
    TRUST_DISTRIBUTION = "trust_distribution"
    DIVIDEND_TIMING = "dividend_timing"
    SPOUSE_CONTRIBUTION = "spouse_contribution"
    MULTI_ENTITY_RESTRUCTURE = "multi_entity_restructure"
    OTHER = "other"

REQUIRES_GROUP_MODEL: frozenset[StrategyCategory] = frozenset({
    StrategyCategory.DIRECTOR_SALARY,
    StrategyCategory.TRUST_DISTRIBUTION,
    StrategyCategory.DIVIDEND_TIMING,
    StrategyCategory.SPOUSE_CONTRIBUTION,
    StrategyCategory.MULTI_ENTITY_RESTRUCTURE,
})

def requires_group_model(category: StrategyCategory) -> bool:
    return category in REQUIRES_GROUP_MODEL
```

### Dataclass: `GroundTruth`

**Module**: `backend/app/modules/tax_planning/tax_calculator.py`

```python
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class GroundTruth:
    taxable_income: Decimal
    gross_tax: Decimal
    total_tax_payable: Decimal
    credits_total: Decimal
    net_position: Decimal
    source: str = "independent_re_derivation"  # for audit
```

Used by the reviewer (Phase 4) to compare against modeller-emitted scenario `before` numbers with a $1 tolerance.

### Dataclass: `ProjectionMetadata`

**Module**: `backend/app/modules/tax_planning/projection.py`

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class ProjectionMetadata:
    applied: bool
    rule: str  # "linear" for v1
    months_elapsed: int
    months_projected: int
    ytd_snapshot: dict  # {income: ..., expenses: ..., per-line-item}
    applied_at: datetime
    reason: str | None = None  # e.g. "manual_full_year" when applied=False
```

Serialised into `TaxPlan.financials_data["projection_metadata"]`. Not a DB column — it lives inside the existing JSONB.

---

## Structured JSONB contract: `TaxPlan.financials_data`

This is an existing JSONB field. This spec formalises its shape with one new sub-key.

```json
{
  "income": { "total_income": 500000.00, "...": "line items" },
  "expenses": { "total_expenses": 350000.00, "...": "line items" },
  "credits": {
    "payg_instalments": 25000.00,
    "payg_withholding": 12000.00,    // NEW: wired from payroll_summary.total_tax_withheld_ytd (FR-007)
    "franking_credits": 0.00
  },
  "adjustments": [],
  "turnover": 500000.00,
  "has_help_debt": false,

  "payroll_summary": {
    "total_wages_ytd": 200000.00,
    "total_super_ytd": 22000.00,
    "total_tax_withheld_ytd": 12000.00,
    "pay_run_count": 8
  },
  "bank_balances": { "...": "..." },
  "strategy_context": { "...": "..." },
  "prior_years": [ { "...": "..." } ],

  "projection_metadata": {                  // NEW (FR-001..FR-004)
    "applied": true,
    "rule": "linear",
    "months_elapsed": 6,
    "months_projected": 6,
    "ytd_snapshot": {
      "income": { "total_income": 250000.00 },
      "expenses": { "total_expenses": 175000.00 }
    },
    "applied_at": "2026-04-18T12:34:56Z",
    "reason": null
  }
}
```

### Invariants

- When `projection_metadata.applied=true`, the top-level `income.total_income` and `expenses.total_expenses` are the **projected** values, and `ytd_snapshot` holds the originals.
- When `projection_metadata.applied=false`, `projection_metadata.reason` is set (one of: `"months_elapsed>=12"`, `"manual_full_year"`).
- `credits.payg_withholding` is populated automatically from `payroll_summary.total_tax_withheld_ytd` during the Xero transform, unless manually overridden (then a provenance flag in a sibling `credits_source_tags` key — deferred; not needed for v1 as manual override is already a confirmed figure).
- `payroll_summary` is always present when `has_payroll_access=True`; otherwise absent, with a top-level `payroll_status: "unavailable" | "pending" | "ready"` flag added when relevant (new key, no migration needed as this is JSONB).

---

## Structured JSONB contract: `TaxPlanMessage.citation_verification`

Existing JSONB field; this spec extends the `status` enum.

```json
{
  "status": "verified" | "partially_verified" | "unverified" | "no_citations" | "low_confidence",
  "verified_count": 3,
  "total_citations": 3,
  "confidence_score": 0.82,
  "citations": [
    {
      "identifier": "TR 98/1",
      "verified": true,
      "matched_by": "ruling_number" | "section_ref" | "title" | "body_text"
    }
  ]
}
```

### Invariants

- `status="low_confidence"` NEW: emitted when the confidence gate (`< 0.5`) fires AND at least one chunk was retrieved. Renders in UI with amber badge and "AI declined — low source confidence" copy.
- `confidence_score` is now computed against `relevance_score` (not `score`) — the key fix.
- `matched_by` is a new field recording how the verifier passed the citation; useful for auditing and for the contract test (FR-023).

---

## Frontend type contract: `frontend/src/types/tax-planning.ts`

Extension, not a rewrite.

```typescript
// Added
export type Provenance = "confirmed" | "derived" | "estimated";

export type StrategyCategory =
  | "prepayment" | "capex_deduction" | "super_contribution"
  | "director_salary" | "trust_distribution" | "dividend_timing"
  | "spouse_contribution" | "multi_entity_restructure" | "other";

export interface SourceTags {
  [jsonPointer: string]: Provenance;
}

// Modified
export interface TaxScenarioResponse {
  // … existing fields …
  strategy_category: StrategyCategory;          // NEW
  requires_group_model: boolean;                // NEW
  source_tags: SourceTags;                      // NEW
}

export interface CitationVerification {
  status: "verified" | "partially_verified" | "unverified" | "no_citations" | "low_confidence";
  // … existing fields …
}

// NEW: Analysis response now includes financials alongside AI output (FR-013)
export interface TaxPlanAnalysisResponse {
  // … existing AI-derived fields …
  financials_data: FinancialsData;              // NEW
  projection_metadata: ProjectionMetadata;      // NEW
}

export interface ProjectionMetadata {
  applied: boolean;
  rule: "linear";
  months_elapsed: number;
  months_projected: number;
  ytd_snapshot: Record<string, unknown>;
  applied_at: string;
  reason: string | null;
}
```

---

## Audit event payload shapes

From spec §Audit Implementation Requirements. Consistent shape for each:

```json
{
  "event_type": "tax_planning.<subject>.<verb>",
  "tenant_id": "uuid",
  "actor_id": "uuid or null",
  "resource_type": "tax_plan" | "tax_scenario" | "tax_plan_message",
  "resource_id": "uuid",
  "metadata": { "event-specific fields" },
  "occurred_at": "iso8601"
}
```

Event-specific metadata:

| Event | Metadata keys |
|-------|--------------|
| `tax_planning.financials.annualised` | `months_elapsed, months_projected, rule, ytd_totals, projected_totals` |
| `tax_planning.payroll.sync_triggered` | `connection_id, sync_outcome, pay_run_count, totals_summary, duration_ms, timeout_hit: bool` |
| `tax_planning.payroll.unavailable` | `reason_code, connection_id` |
| `tax_planning.scenario.provenance_confirmed` | `scenario_id, field_path, old_value, new_value, old_provenance, new_provenance` |
| `tax_planning.scenario.requires_group_model_flag` | `scenario_id, strategy_category, title` |
| `tax_planning.review.verification_failed` | `plan_id, scenario_id, field_path, expected, got, delta` |
| `tax_planning.citation.verification_outcome` | `message_id, total_citations, verified_count, confidence_score, status, matched_by_breakdown` |
| `tax_planning.manual_financials.saved` | `plan_id, fields_changed, preserved_context_keys` |

Retention: 7 years for all (per constitution §X default). Sensitive-data masking: none required (no TFN/bank on any of these events).

---

## Migration

**File**: `backend/alembic/versions/20260418_059_tax_planning_correctness.py`

Pseudocode (upgrade):

```python
def upgrade() -> None:
    # 1. Enum type
    strategy_category_enum = sa.Enum(
        "prepayment", "capex_deduction", "super_contribution",
        "director_salary", "trust_distribution", "dividend_timing",
        "spouse_contribution", "multi_entity_restructure", "other",
        name="strategy_category_enum",
    )
    strategy_category_enum.create(op.get_bind(), checkfirst=True)

    # 2. Columns
    op.add_column("tax_scenarios", sa.Column(
        "strategy_category", strategy_category_enum,
        nullable=False, server_default="other",
    ))
    op.add_column("tax_scenarios", sa.Column(
        "requires_group_model", sa.Boolean(),
        nullable=False, server_default=sa.text("false"),
    ))
    op.add_column("tax_scenarios", sa.Column(
        "source_tags", postgresql.JSONB(astext_type=sa.Text()),
        nullable=False, server_default=sa.text("'{}'::jsonb"),
    ))

    # 3. Dedup pre-existing duplicate titles before creating unique index
    op.execute("""
        UPDATE tax_scenarios
        SET title = title || ' (duplicate ' || id || ')'
        WHERE id IN (
          SELECT id FROM (
            SELECT id, row_number() OVER (
              PARTITION BY tax_plan_id, lower(trim(title)) ORDER BY created_at
            ) AS rn
            FROM tax_scenarios
          ) t WHERE rn > 1
        )
    """)

    # 4. Partial unique index (case-insensitive + trimmed)
    op.create_index(
        "ix_tax_scenarios_plan_normalized_title",
        "tax_scenarios",
        ["tax_plan_id", sa.text("lower(trim(title))")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_tax_scenarios_plan_normalized_title", "tax_scenarios")
    op.drop_column("tax_scenarios", "source_tags")
    op.drop_column("tax_scenarios", "requires_group_model")
    op.drop_column("tax_scenarios", "strategy_category")
    sa.Enum(name="strategy_category_enum").drop(op.get_bind(), checkfirst=True)
```

**Back-compat**: existing rows survive — defaults populate new columns; duplicate titles are disambiguated before the index is created. No data loss.

---

## Out of this data model (noted only)

- **Group tax model** (`TaxPlanGroup`, `TaxPlanEntity`, `TaxPlanFlow`) — next spec.
- **Normalised provenance table** — deferred per R4; JSONB is enough for v1.
- **Confirmed-assumption history table** — current design overwrites on confirm; audit log captures before/after. A dedicated history table is future work if the accountant ever asks to undo a confirmation.

---

**Status**: Data model complete. See `contracts/api-changes.md` for endpoint and schema surface changes.
