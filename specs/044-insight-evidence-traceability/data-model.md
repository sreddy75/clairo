# Data Model: Platform-Wide Evidence & Traceability

**Feature**: 044-insight-evidence-traceability
**Date**: 2026-02-24

---

## Entities

### 1. Evidence Item (new value object — embedded in Data Snapshot)

An individual data point extracted from the financial context, structured for frontend rendering.

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `source` | string | Data source name | "Profit & Loss" |
| `period` | string | Reporting period or as-of date | "FY2025", "Feb 2026" |
| `metric` | string | Metric label | "Total Revenue" |
| `value` | string | Formatted value | "$185,000" |
| `category` | string (enum) | Evidence category | "financial", "aging", "gst", "quality", "trend" |

**Not a database table** — embedded as a JSON array within `data_snapshot.evidence_items`.

**Validation Rules**:
- `source` required, max 100 chars
- `period` required, max 50 chars
- `metric` required, max 100 chars
- `value` required, max 100 chars
- `category` required, one of: `financial`, `aging`, `gst`, `quality`, `trend`

---

### 2. Data Snapshot (existing JSONB column — expanded structure)

The `data_snapshot` JSONB column on `Insight` model (already exists, `models.py:89`). Currently stores `{"ai_analysis": True}` for AI insights. Expanded to store structured financial context.

| Field | Type | Description | Stored For |
|-------|------|-------------|------------|
| `version` | string | Schema version for forward compat | All snapshots |
| `captured_at` | ISO datetime | When snapshot was taken | All snapshots |
| `data_freshness` | ISO datetime | Last Xero sync timestamp | All AI snapshots |
| `evidence_items` | EvidenceItem[] | Extracted evidence array | AI-expanded insights |
| `profile` | object | Client profile summary | AI-expanded insights |
| `profile.name` | string | Organization name | — |
| `profile.entity_type` | string | Entity type | — |
| `profile.industry` | string | Industry code | — |
| `profile.gst_registered` | boolean | GST registration status | — |
| `profile.revenue_bracket` | string | Revenue bracket | — |
| `financial_summary` | object | Key P&L/BS figures | AI-expanded insights |
| `financial_summary.revenue` | number | Total revenue | — |
| `financial_summary.expenses` | number | Total expenses | — |
| `financial_summary.net_profit` | number | Net profit | — |
| `financial_summary.current_ratio` | number | Current ratio | — |
| `financial_summary.debt_to_equity` | number | Debt-to-equity ratio | — |
| `aging_summary` | object | AR/AP aging buckets | AI-expanded insights |
| `aging_summary.ar_total` | number | Total receivables | — |
| `aging_summary.ar_overdue` | number | Overdue receivables | — |
| `aging_summary.ar_overdue_pct` | number | Overdue percentage | — |
| `aging_summary.ap_total` | number | Total payables | — |
| `aging_summary.ap_overdue` | number | Overdue payables | — |
| `gst_summary` | object | GST position summary | AI-expanded insights |
| `gst_summary.collected` | number | GST collected | — |
| `gst_summary.paid` | number | GST paid | — |
| `gst_summary.net_position` | number | Net GST position | — |
| `monthly_trends` | object[] | Last 6 months trend data | AI-expanded insights |
| `quality_scores` | object | Quality score + dimensions | AI-expanded insights |
| `perspectives_used` | string[] | Agent perspectives used | AI-expanded insights |
| `ai_analysis` | boolean | Legacy flag (kept for compat) | All AI snapshots |
| `generated_at` | ISO datetime | Legacy field (kept for compat) | All AI snapshots |

**Size Constraint**: 50KB maximum. Trim priority:
1. Remove `extended_data` (fixed assets, POs, journals)
2. Truncate `monthly_trends` to last 3 months
3. Remove `raw_data`
4. Core summaries (profile, financial_summary, aging_summary, gst_summary, quality_scores) always preserved

**No migration required** — column already exists as `JSONB nullable`. Only the stored structure changes.

---

### 3. Threshold Rule (new — configuration registry, not a database table)

Defines the classification rules behind scores, severity labels, and risk indicators.

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `metric_key` | string | Unique metric identifier | "bas_variance_severity" |
| `display_name` | string | Human-readable name | "BAS Variance Severity" |
| `rules` | ThresholdBand[] | Ordered threshold bands | See below |
| `description` | string | Plain-English methodology | "Based on percentage change and absolute dollar change" |

**ThresholdBand**:
| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `label` | string | Classification label | "Critical" |
| `color` | string | Display color | "red" |
| `condition` | string | Human-readable rule | ">50% change OR >$10,000 absolute change" |

**Storage**: Python dict/dataclass in a dedicated module (not database). Exposed via API endpoint for frontend consumption.

---

### 4. Confidence Breakdown (P3 — future, embedded value object)

| Field | Type | Description |
|-------|------|-------------|
| `overall` | float (0-1) | Computed confidence score |
| `data_completeness` | float (0-1) | How complete the financial data is |
| `data_freshness` | float (0-1) | How recent the data is |
| `knowledge_match` | float (0-1) | RAG retrieval relevance |
| `perspective_coverage` | float (0-1) | How many perspectives contributed |

**P3 scope** — not implemented in P1/P2. Confidence scores hidden until this is ready.

---

## Entity Relationships

```
Insight (existing)
  └── data_snapshot (JSONB column, already exists)
       ├── evidence_items[] (EvidenceItem value objects)
       ├── profile (client profile summary)
       ├── financial_summary (P&L/BS key figures)
       ├── aging_summary (AR/AP aging)
       ├── gst_summary (GST position)
       ├── monthly_trends[] (trend data)
       ├── quality_scores (score + dimensions)
       └── [future P3] confidence_breakdown

ThresholdRegistry (in-memory configuration)
  └── threshold_rules[] (ThresholdRule objects)
       └── rules[] (ThresholdBand objects)
```

## State Transitions

**Data Snapshot Lifecycle**:
1. **Empty** → Insight created (rule-based: may have partial snapshot with triggering metrics)
2. **Stub** → AI Analyzer creates insight with `{"ai_analysis": True}` (current behavior, replaced in P1)
3. **Populated** → Insight expanded or AI Analyzer generates with full context capture
4. **Immutable** → Once written, snapshot is never modified (point-in-time record)

**No delete/archive transitions** — snapshots are append-only audit records, retained per ATO 7-year requirement.
