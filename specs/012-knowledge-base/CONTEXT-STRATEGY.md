# Context Injection Strategy: Raw vs Aggregated Data

**The Challenge**: More context = better AI responses, but LLM context windows have limits (and costs).

---

## The Problem with Raw Data

### Scale Reality Check

A typical SMB client in Xero might have:

| Data Type | Volume/Year | Tokens (est.) | Context Cost |
|-----------|-------------|---------------|--------------|
| Transactions | 2,000-10,000 | 400K-2M tokens | $0.60-3.00 per query |
| Invoices | 200-1,000 | 100K-500K tokens | $0.15-0.75 |
| Contacts | 50-500 | 25K-250K tokens | $0.04-0.38 |
| Bank Lines | 1,000-5,000 | 200K-1M tokens | $0.30-1.50 |

**Total raw data**: 725K - 3.75M tokens per client

**Problems:**
1. **Cost**: At $3/1M tokens (Claude), that's $2-11 per query just for context
2. **Context Limit**: Claude's context is 200K tokens - we'd exceed it
3. **Noise**: Most transactions are irrelevant to the specific question
4. **Latency**: Fetching and serializing all that data takes time

### What the AI Actually Needs

For "What deductions am I missing?", the AI needs:
- ✅ Expense categories and totals (not every transaction)
- ✅ Business type, industry, entity structure
- ✅ What's been claimed vs typical for industry
- ❌ Individual $45 fuel receipts
- ❌ Every invoice line item

---

## The Solution: Tiered Context Strategy

```
TIERED CONTEXT ARCHITECTURE
═══════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────┐
│                    TIER 1: ALWAYS INCLUDED                       │
│                    (~500-1,000 tokens)                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  CLIENT PROFILE (pre-computed, cached)                          │
│  ├── Business name, ABN                                         │
│  ├── Entity type (sole trader, company, trust)                  │
│  ├── Industry (ANZSIC code + description)                       │
│  ├── GST registered (yes/no)                                    │
│  ├── Employee count                                             │
│  ├── Years in business                                          │
│  └── Revenue bracket (under $75K, $75K-500K, etc.)              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    TIER 2: QUERY-RELEVANT SUMMARIES              │
│                    (~1,000-3,000 tokens)                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Selected based on query type:                                   │
│                                                                  │
│  For TAX/DEDUCTION queries:                                      │
│  ├── Expense summary by category (last 12 months)               │
│  ├── Income summary by source                                    │
│  ├── Asset register summary                                      │
│  └── Prior year comparison                                       │
│                                                                  │
│  For CASH FLOW queries:                                          │
│  ├── Accounts receivable aging summary                           │
│  ├── Accounts payable aging summary                              │
│  ├── Monthly cash flow trend                                     │
│  └── Outstanding invoices by customer                            │
│                                                                  │
│  For GST/BAS queries:                                            │
│  ├── GST collected (1A) this period                              │
│  ├── GST paid (1B) this period                                   │
│  ├── Adjustment items                                            │
│  └── Comparison to prior quarters                                │
│                                                                  │
│  For COMPLIANCE queries:                                         │
│  ├── Contractor payments summary                                 │
│  ├── Payroll summary                                             │
│  ├── Super guarantee summary                                     │
│  └── BAS lodgement history                                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    TIER 3: ON-DEMAND DETAIL                      │
│                    (~500-5,000 tokens when requested)            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  AI can REQUEST specific detail in multi-turn:                   │
│                                                                  │
│  "I need more detail on vehicle expenses"                        │
│  → Fetch vehicle-related transactions                            │
│                                                                  │
│  "Show me the overdue invoices"                                  │
│  → Fetch invoices > 30 days with customer names                  │
│                                                                  │
│  "What's the breakdown of that $45K materials expense?"          │
│  → Fetch transactions in 'Materials' category                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## What We Should Pre-Compute and Store

### Aggregation Tables (PostgreSQL)

```sql
-- ============================================================
-- CLIENT PROFILE SUMMARY
-- Updated: On every Xero sync
-- ============================================================
CREATE TABLE client_ai_profile (
    connection_id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,

    -- Basic Info
    organization_name VARCHAR(255),
    abn VARCHAR(11),
    entity_type VARCHAR(50),  -- sole_trader, company, trust, partnership
    industry_code VARCHAR(10),  -- ANZSIC
    industry_description VARCHAR(255),

    -- Status
    gst_registered BOOLEAN,
    gst_registration_date DATE,
    bas_frequency VARCHAR(20),  -- monthly, quarterly

    -- Scale Indicators
    annual_revenue DECIMAL(15,2),
    annual_expenses DECIMAL(15,2),
    revenue_bracket VARCHAR(20),  -- under_75k, 75k_to_500k, etc.
    employee_count INTEGER,
    contractor_count INTEGER,
    years_in_business INTEGER,

    -- Computed at sync
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- EXPENSE SUMMARY BY CATEGORY
-- Updated: On every Xero sync
-- ============================================================
CREATE TABLE expense_category_summary (
    id UUID PRIMARY KEY,
    connection_id UUID NOT NULL,

    -- Time Period
    period_type VARCHAR(20),  -- 'month', 'quarter', 'year'
    period_start DATE,
    period_end DATE,

    -- Category
    account_code VARCHAR(20),
    account_name VARCHAR(255),
    category_group VARCHAR(100),  -- 'vehicle', 'office', 'materials', etc.

    -- Aggregates
    transaction_count INTEGER,
    total_amount DECIMAL(15,2),
    gst_amount DECIMAL(15,2),

    -- For comparison
    prior_period_amount DECIMAL(15,2),
    variance_pct DECIMAL(5,2),

    UNIQUE(connection_id, period_type, period_start, account_code)
);

-- ============================================================
-- INCOME SUMMARY BY SOURCE
-- Updated: On every Xero sync
-- ============================================================
CREATE TABLE income_source_summary (
    id UUID PRIMARY KEY,
    connection_id UUID NOT NULL,

    period_type VARCHAR(20),
    period_start DATE,
    period_end DATE,

    -- Source
    income_type VARCHAR(100),  -- 'sales', 'services', 'interest', etc.
    account_code VARCHAR(20),

    -- Aggregates
    invoice_count INTEGER,
    total_amount DECIMAL(15,2),
    gst_amount DECIMAL(15,2),

    -- Comparison
    prior_period_amount DECIMAL(15,2),
    variance_pct DECIMAL(5,2)
);

-- ============================================================
-- ACCOUNTS RECEIVABLE AGING
-- Updated: Daily or on sync
-- ============================================================
CREATE TABLE ar_aging_summary (
    id UUID PRIMARY KEY,
    connection_id UUID NOT NULL,
    as_of_date DATE,

    -- Aging Buckets
    current_amount DECIMAL(15,2),  -- 0-30 days
    days_31_60 DECIMAL(15,2),
    days_61_90 DECIMAL(15,2),
    days_over_90 DECIMAL(15,2),
    total_outstanding DECIMAL(15,2),

    -- Metrics
    invoice_count INTEGER,
    average_days_outstanding DECIMAL(5,1),
    largest_debtor_name VARCHAR(255),
    largest_debtor_amount DECIMAL(15,2),

    -- Top 5 Debtors (JSON for flexibility)
    top_debtors JSONB  -- [{name, amount, days_overdue}, ...]
);

-- ============================================================
-- GST/BAS PERIOD SUMMARY
-- Updated: On Xero sync, used for BAS preparation
-- ============================================================
CREATE TABLE gst_period_summary (
    id UUID PRIMARY KEY,
    connection_id UUID NOT NULL,

    period_start DATE,
    period_end DATE,

    -- GST Figures
    gst_on_sales DECIMAL(15,2),      -- 1A
    gst_on_purchases DECIMAL(15,2),  -- 1B
    net_gst DECIMAL(15,2),

    -- Sales Breakdown
    total_sales DECIMAL(15,2),
    gst_free_sales DECIMAL(15,2),
    input_taxed_sales DECIMAL(15,2),
    export_sales DECIMAL(15,2),

    -- Purchase Breakdown
    capital_purchases DECIMAL(15,2),
    non_capital_purchases DECIMAL(15,2),

    -- PAYG
    payg_withholding DECIMAL(15,2),
    payg_instalments DECIMAL(15,2),

    -- Comparison
    prior_quarter_gst DECIMAL(15,2),
    variance_pct DECIMAL(5,2),
    variance_explained TEXT  -- AI can populate this
);

-- ============================================================
-- CONTRACTOR PAYMENT SUMMARY
-- Critical for compliance (TPAR, super obligations)
-- ============================================================
CREATE TABLE contractor_summary (
    id UUID PRIMARY KEY,
    connection_id UUID NOT NULL,

    financial_year INTEGER,

    -- Contractor
    contact_id UUID,
    contact_name VARCHAR(255),
    abn VARCHAR(11),

    -- Payments
    total_paid DECIMAL(15,2),
    payment_count INTEGER,
    first_payment_date DATE,
    last_payment_date DATE,
    payment_frequency VARCHAR(20),  -- weekly, monthly, irregular

    -- Risk Indicators
    regular_payment_flag BOOLEAN,  -- Potential employee?
    super_obligation_likely BOOLEAN,
    tpar_reportable BOOLEAN
);

-- ============================================================
-- DEDUCTION ANALYSIS (AI-Enhanced)
-- Pre-computed analysis of claimed vs typical
-- ============================================================
CREATE TABLE deduction_analysis (
    id UUID PRIMARY KEY,
    connection_id UUID NOT NULL,
    analysis_date DATE,

    -- By Category
    category VARCHAR(100),
    amount_claimed DECIMAL(15,2),
    industry_benchmark DECIMAL(15,2),
    variance_from_benchmark DECIMAL(5,2),

    -- AI Insights
    potentially_missing BOOLEAN,
    missing_estimate_low DECIMAL(15,2),
    missing_estimate_high DECIMAL(15,2),
    recommendation TEXT,
    confidence VARCHAR(20),  -- high, medium, low

    -- Source
    benchmark_source VARCHAR(255)  -- 'ATO Industry Benchmarks 2024'
);

-- ============================================================
-- MONTHLY TREND DATA
-- For visualizations and trend analysis
-- ============================================================
CREATE TABLE monthly_trends (
    id UUID PRIMARY KEY,
    connection_id UUID NOT NULL,
    month DATE,  -- First of month

    -- P&L
    revenue DECIMAL(15,2),
    expenses DECIMAL(15,2),
    gross_profit DECIMAL(15,2),
    net_profit DECIMAL(15,2),

    -- Cash Flow
    cash_in DECIMAL(15,2),
    cash_out DECIMAL(15,2),
    net_cash_flow DECIMAL(15,2),
    closing_cash DECIMAL(15,2),

    -- Activity
    invoices_issued INTEGER,
    invoices_paid INTEGER,
    bills_received INTEGER,
    bills_paid INTEGER,

    -- Ratios
    gross_margin_pct DECIMAL(5,2),
    expense_ratio_pct DECIMAL(5,2)
);
```

---

## Context Builder Service

```python
# backend/app/modules/ai/context_builder.py

from enum import Enum
from typing import Any
from uuid import UUID

class QueryIntent(Enum):
    """Detected query intent determines which summaries to include."""
    TAX_DEDUCTIONS = "tax_deductions"
    CASH_FLOW = "cash_flow"
    GST_BAS = "gst_bas"
    COMPLIANCE = "compliance"
    PRICING = "pricing"
    GROWTH = "growth"
    GENERAL = "general"


class ContextBuilder:
    """
    Builds optimized context for AI queries.

    Principle: Include enough context for a great answer,
    but not so much that we waste tokens or hit limits.
    """

    # Token budgets (approximate)
    TIER1_BUDGET = 1000   # Always included
    TIER2_BUDGET = 3000   # Query-relevant summaries
    TIER3_BUDGET = 5000   # On-demand detail
    TOTAL_BUDGET = 9000   # Max context for client data

    async def build_context(
        self,
        connection_id: UUID,
        query: str,
        intent: QueryIntent | None = None
    ) -> ClientContext:
        """Build tiered context for AI query."""

        # Detect intent if not provided
        if intent is None:
            intent = await self._detect_intent(query)

        # TIER 1: Always include profile
        profile = await self._get_profile(connection_id)

        # TIER 2: Select relevant summaries based on intent
        summaries = await self._get_relevant_summaries(
            connection_id,
            intent
        )

        return ClientContext(
            profile=profile,
            summaries=summaries,
            intent=intent,
            token_estimate=self._estimate_tokens(profile, summaries)
        )

    async def _get_relevant_summaries(
        self,
        connection_id: UUID,
        intent: QueryIntent
    ) -> dict[str, Any]:
        """Fetch summaries relevant to the query intent."""

        summaries = {}

        if intent == QueryIntent.TAX_DEDUCTIONS:
            summaries["expense_by_category"] = await self._get_expense_summary(
                connection_id,
                period="last_12_months"
            )
            summaries["deduction_analysis"] = await self._get_deduction_analysis(
                connection_id
            )
            summaries["asset_summary"] = await self._get_asset_summary(
                connection_id
            )
            summaries["prior_year_comparison"] = await self._get_yoy_comparison(
                connection_id,
                categories=["expenses"]
            )

        elif intent == QueryIntent.CASH_FLOW:
            summaries["ar_aging"] = await self._get_ar_aging(connection_id)
            summaries["ap_aging"] = await self._get_ap_aging(connection_id)
            summaries["monthly_cash_flow"] = await self._get_monthly_trends(
                connection_id,
                metrics=["cash_in", "cash_out", "net_cash_flow"],
                months=6
            )
            summaries["top_debtors"] = await self._get_top_debtors(
                connection_id,
                limit=5
            )

        elif intent == QueryIntent.GST_BAS:
            summaries["current_period_gst"] = await self._get_gst_summary(
                connection_id,
                period="current_quarter"
            )
            summaries["prior_quarters"] = await self._get_gst_summary(
                connection_id,
                period="last_4_quarters"
            )
            summaries["adjustments"] = await self._get_gst_adjustments(
                connection_id
            )

        elif intent == QueryIntent.COMPLIANCE:
            summaries["contractor_summary"] = await self._get_contractor_summary(
                connection_id
            )
            summaries["payroll_summary"] = await self._get_payroll_summary(
                connection_id
            )
            summaries["super_summary"] = await self._get_super_summary(
                connection_id
            )
            summaries["lodgement_history"] = await self._get_lodgement_history(
                connection_id
            )

        elif intent == QueryIntent.PRICING:
            summaries["revenue_by_service"] = await self._get_revenue_breakdown(
                connection_id
            )
            summaries["monthly_trends"] = await self._get_monthly_trends(
                connection_id,
                metrics=["revenue", "gross_profit", "gross_margin_pct"],
                months=12
            )
            summaries["industry_benchmarks"] = await self._get_industry_benchmarks(
                connection_id
            )

        elif intent == QueryIntent.GROWTH:
            summaries["revenue_trend"] = await self._get_monthly_trends(
                connection_id,
                metrics=["revenue", "net_profit"],
                months=24
            )
            summaries["expense_ratio"] = await self._get_expense_ratio_trend(
                connection_id
            )
            summaries["employee_growth"] = await self._get_employee_trend(
                connection_id
            )

        else:  # GENERAL
            # Include a bit of everything
            summaries["financial_snapshot"] = await self._get_financial_snapshot(
                connection_id
            )
            summaries["recent_activity"] = await self._get_recent_activity(
                connection_id
            )

        return summaries

    def format_for_prompt(self, context: ClientContext) -> str:
        """Format context as string for LLM prompt."""

        lines = ["<client_context>"]

        # Profile
        p = context.profile
        lines.append(f"Business: {p.organization_name}")
        lines.append(f"ABN: {p.abn}")
        lines.append(f"Structure: {p.entity_type}")
        lines.append(f"Industry: {p.industry_description} ({p.industry_code})")
        lines.append(f"GST Registered: {'Yes' if p.gst_registered else 'No'}")
        lines.append(f"Annual Revenue: ${p.annual_revenue:,.0f}")
        lines.append(f"Employees: {p.employee_count}")
        lines.append("")

        # Summaries
        for name, data in context.summaries.items():
            lines.append(f"## {name.replace('_', ' ').title()}")
            lines.append(self._format_summary(data))
            lines.append("")

        lines.append("</client_context>")

        return "\n".join(lines)

    def _format_summary(self, data: Any) -> str:
        """Format a summary dict/list as readable text."""

        if isinstance(data, dict):
            return "\n".join(f"  {k}: {v}" for k, v in data.items())
        elif isinstance(data, list):
            return "\n".join(f"  - {item}" for item in data)
        else:
            return str(data)
```

---

## Example: Context for "What deductions am I missing?"

### Tier 1: Profile (~300 tokens)

```
Business: ABC Electrical Services
ABN: 12 345 678 901
Structure: Sole Trader
Industry: Electrical Services (ANZSIC 32320)
GST Registered: Yes
Annual Revenue: $185,000
Employees: 0 (uses subcontractors)
Years in Business: 4
```

### Tier 2: Deduction-Relevant Summaries (~1,500 tokens)

```
## Expense Summary (Last 12 Months)

Category              Amount      % of Revenue   Industry Avg
───────────────────────────────────────────────────────────────
Materials            $45,000      24.3%          22-28%  ✓
Subcontractors       $32,000      17.3%          15-25%  ✓
Vehicle - Fuel        $8,400       4.5%           3-6%   ✓
Insurance             $3,200       1.7%           1-3%   ✓
Phone/Internet        $1,800       1.0%           0.5-1.5% ✓
Accounting            $2,400       1.3%           1-2%   ✓
───────────────────────────────────────────────────────────────
Total Expenses       $92,800      50.2%

## Deduction Analysis

Category              Claimed    Expected    Gap         Priority
───────────────────────────────────────────────────────────────
Vehicle Depreciation    $0       $3,000-5,000  ⚠️ HIGH   Missing
Tool Depreciation       $0       $4,000-8,000  ⚠️ HIGH   Missing
Home Office             $0       $1,000-1,500  ⚠️ MEDIUM Missing
PPE/Safety Gear         $0       $500-800      ⚠️ LOW    Missing
Training/Licensing      $0       $500-1,000    ⚠️ LOW    Missing

Estimated Missing Deductions: $9,000-16,300
Potential Tax Savings: $2,970-5,380 (at 33% rate)

## Asset Register

No assets currently registered for depreciation.

Note: Electricians typically have $15,000-30,000 in tools
and a work vehicle valued at $30,000-60,000.
```

### What We DON'T Include

❌ Individual transactions (2,000+ rows)
❌ Every invoice line item
❌ Full contact list
❌ Bank statement lines
❌ Historical data beyond relevance

### Result: ~1,800 tokens of highly relevant context

This enables the AI to give a specific, actionable answer:

> "Based on your electrical business, you're likely missing $9,000-16,300 in deductions, primarily vehicle depreciation ($3,000-5,000) and tool depreciation ($4,000-8,000). This could save you $2,970-5,380 in tax..."

---

## When to Use Raw Data (Tier 3)

### Trigger: AI requests more detail

```
User: "What deductions am I missing?"

AI: "I can see you're not claiming vehicle depreciation.
     To give you an accurate estimate, I need to know about
     your work vehicle. Do you own a vehicle used for business?"

User: "Yes, I have a 2021 Toyota HiLux"

→ System fetches asset details or prompts for more info

AI: "A 2021 Toyota HiLux with typical business use would
     generate approximately $4,500/year in depreciation claims
     using the diminishing value method..."
```

### Trigger: Drill-down query

```
User: "Show me my overdue invoices"

→ System fetches AR detail (Tier 3)

AI: "You have $28,000 in overdue invoices:

     Johnson Developments  $12,400  67 days overdue
     Metro Constructions    $8,200  45 days overdue
     Sunrise Properties     $5,800  38 days overdue

     Johnson Developments hasn't responded to 2 emails.
     Would you like me to draft a firmer follow-up?"
```

### Trigger: Anomaly investigation

```
AI: "I notice your GST is 45% higher than last quarter..."

User: "Why?"

→ System fetches transaction detail for GST variance

AI: "The increase is due to a $45,000 Bobcat purchase on
     Oct 15. This is legitimate and will result in a larger
     GST refund this quarter."
```

---

## Aggregation Refresh Strategy

| Data Type | Refresh Trigger | Latency |
|-----------|-----------------|---------|
| Client Profile | Every Xero sync | Real-time |
| Expense Summary | Every Xero sync | Real-time |
| AR/AP Aging | Daily + on sync | Near real-time |
| GST Summary | Every Xero sync | Real-time |
| Deduction Analysis | Weekly batch job | Async |
| Industry Benchmarks | Quarterly update | Background |
| Monthly Trends | End of month + sync | Near real-time |

---

## Token Budget Summary

| Tier | Content | Tokens | When |
|------|---------|--------|------|
| **Tier 1** | Profile | 300-500 | Always |
| **Tier 2** | Relevant summaries | 1,000-3,000 | Based on intent |
| **Tier 3** | Raw detail | 500-5,000 | On demand |
| **Knowledge** | Qdrant chunks | 2,000-4,000 | Per query |
| **Total** | | **4,000-12,500** | Per query |

At ~$3/1M tokens (Claude):
- Average query cost: **$0.012-0.038** for context
- Much better than $2-11 for raw data!

---

## Recommendation Summary

| Question | Answer |
|----------|--------|
| **Store raw data?** | Yes, in PostgreSQL (we already do via Xero sync) |
| **Store aggregations?** | Yes, pre-compute on every sync |
| **What to aggregate?** | Expense categories, AR/AP aging, GST summaries, trends |
| **How to select context?** | Detect query intent → include relevant summaries |
| **When raw data?** | On-demand drill-down, multi-turn conversations |
| **Token budget?** | ~4,000-12,500 total (~$0.01-0.04/query) |

The key insight: **Smart aggregation gives 90% of the value at 5% of the token cost.**
