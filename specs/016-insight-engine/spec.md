# Spec 016: Insight Engine

**Status**: NOT_STARTED
**Phase**: C (Proactive Intelligence)
**Dependencies**: Spec 014 (Multi-Agent Framework) ✅
**Merged Scope**: Includes remaining Spec 015 features (multi-client queries, workflow integration)

---

## Executive Summary

The Insight Engine transforms Clairo from a **reactive** tool (user asks questions) to a **proactive** advisor (system surfaces issues). This is the key differentiator - accountants don't have time to ask the right questions for every client. The system should tell them what needs attention.

### The Shift

```
BEFORE (Reactive - Specs 012-014)          AFTER (Proactive - Spec 016)
─────────────────────────────────          ────────────────────────────────
Accountant asks: "What's wrong             System alerts: "3 clients need
with this client's GST?"                   attention this week"

Accountant asks: "Who has                  Dashboard shows: Priority-ranked
overdue BAS?"                              insights with actions

Accountant manually checks                 Notification: "ACME Corp GST
each client for issues                     threshold in 2 months"
```

---

## Goals

1. **Proactive Insight Generation** - System analyzes all clients and surfaces issues
2. **Multi-Client Intelligence** - Cross-portfolio queries and comparisons
3. **Workflow Integration** - AI assistance embedded in BAS prep, quality review
4. **Actionable Notifications** - Priority-ranked alerts with clear next steps

---

## Feature 1: Proactive Insight Generation

### Insight Types

| Category | Insight | Trigger Condition | Priority |
|----------|---------|-------------------|----------|
| **Compliance** | GST threshold approaching | Revenue > $65K, trending up | HIGH |
| **Compliance** | BAS deadline approaching | Due date < 7 days, not lodged | HIGH |
| **Compliance** | Super guarantee due | Quarter end approaching | MEDIUM |
| **Quality** | Unreconciled transactions | Count > 10, age > 7 days | HIGH |
| **Quality** | Uncoded transactions | GST code missing | MEDIUM |
| **Quality** | Bank reconciliation gap | Last rec > 14 days | MEDIUM |
| **Cash Flow** | Overdue receivables spike | AR aging > 30 days increase | HIGH |
| **Cash Flow** | Cash flow warning | Projected negative in 30 days | HIGH |
| **Tax** | Missing deductions | Industry benchmark comparison | LOW |
| **Tax** | Super optimization window | Pre-30 June, headroom exists | MEDIUM |

### Insight Data Model

```python
class Insight:
    id: UUID
    tenant_id: UUID
    client_id: UUID | None  # None for multi-client insights

    # Classification
    category: InsightCategory  # COMPLIANCE, QUALITY, CASH_FLOW, TAX, STRATEGIC
    insight_type: str          # "gst_threshold_approaching", "unreconciled_txns", etc.
    priority: Priority         # HIGH, MEDIUM, LOW

    # Content
    title: str                 # "GST Threshold Approaching"
    summary: str               # "ACME Corp will hit $75K in ~2 months"
    detail: str | None         # Markdown with full analysis

    # Actions
    suggested_actions: list[Action]  # What to do about it
    related_url: str | None          # Link to relevant page

    # Lifecycle
    status: InsightStatus      # NEW, VIEWED, ACTIONED, DISMISSED, RESOLVED
    generated_at: datetime
    expires_at: datetime | None
    viewed_at: datetime | None
    actioned_at: datetime | None

    # Audit
    generation_source: str     # "scheduled_analysis", "data_sync", "manual_trigger"
    confidence: float          # 0.0-1.0
    data_snapshot: dict        # Key metrics at generation time
```

### Generation Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                     INSIGHT GENERATION PIPELINE                      │
└─────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐         ┌───────────────┐         ┌───────────────┐
│  DATA SYNC    │         │  SCHEDULED    │         │   MANUAL      │
│  TRIGGER      │         │  (Daily/Weekly)│        │   TRIGGER     │
│               │         │               │         │               │
│ After Xero    │         │ 6am daily     │         │ User clicks   │
│ sync completes│         │ analysis      │         │ "Analyze"     │
└───────────────┘         └───────────────┘         └───────────────┘
        │                           │                           │
        └───────────────────────────┼───────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────┐
                    │    INSIGHT ANALYZERS      │
                    │                           │
                    │  • ComplianceAnalyzer     │
                    │  • QualityAnalyzer        │
                    │  • CashFlowAnalyzer       │
                    │  • TaxOptimizationAnalyzer│
                    └───────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────┐
                    │   DEDUPLICATION &         │
                    │   PRIORITY RANKING        │
                    │                           │
                    │  • Don't repeat recent    │
                    │  • Merge similar          │
                    │  • Rank by urgency        │
                    └───────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────┐
                    │   NOTIFICATION DISPATCH   │
                    │                           │
                    │  • In-app notifications   │
                    │  • Dashboard widget       │
                    │  • Email digest (optional)│
                    └───────────────────────────┘
```

---

## Feature 2: Multi-Client Queries (from Spec 015)

Enable accountants to query across their entire portfolio:

### Query Types

| Query | Response |
|-------|----------|
| "Which clients have issues this quarter?" | List of clients with active HIGH priority insights |
| "Show me clients approaching GST threshold" | Filtered list with revenue projections |
| "Who has overdue BAS?" | Clients with BAS due date passed, not lodged |
| "Compare Q1 across all clients" | Aggregated comparison table |
| "Which clients need attention this week?" | Priority-ranked list based on insights |

### Implementation

```python
# New endpoint for multi-client queries
POST /api/v1/agents/multi-client/chat

{
    "query": "Which clients have issues this quarter?",
    "filters": {
        "include_inactive": false,
        "date_range": "current_quarter"
    }
}

# Response includes aggregated data across all tenant clients
{
    "response": "You have 3 clients that need attention...",
    "clients_referenced": [
        {"id": "...", "name": "ACME Corp", "issues": ["GST threshold"]},
        {"id": "...", "name": "Beta LLC", "issues": ["Unreconciled txns"]}
    ],
    "perspectives_used": ["compliance", "quality"],
    "confidence": 0.85
}
```

### Context Building for Multi-Client

```python
class MultiClientContextBuilder:
    """Build context across all tenant clients for portfolio queries."""

    async def build_portfolio_context(
        self,
        tenant_id: UUID,
        query_intent: str,
    ) -> PortfolioContext:
        """
        Returns aggregated view:
        - Summary stats (total clients, GST registered, etc.)
        - Active insights by client
        - Clients grouped by status/urgency
        - Relevant metrics for query intent
        """
```

---

## Feature 3: Workflow Integration (from Spec 015)

### BAS Preparation Integration

Add AI assistance buttons to the BAS prep workflow:

```
┌─────────────────────────────────────────────────────────────────────┐
│  BAS Preparation: ACME Corp - Q2 2025                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  GST on Sales:     $12,450.00                                       │
│  GST on Purchases: $8,230.00        [🤖 Explain variance]           │
│  ─────────────────────────────                                      │
│  Net GST Payable:  $4,220.00                                        │
│                                                                     │
│  ⚠️ Variance from Q1: +$1,850 (78%)  [🤖 Analyze]                   │
│                                                                     │
│  PAYG Withholding: $5,400.00                                        │
│  PAYG Instalment:  $2,100.00                                        │
│                                                                     │
│  [🤖 Pre-lodgement checklist]    [Submit for Review]                │
└─────────────────────────────────────────────────────────────────────┘
```

### Integration Points

| Location | AI Feature | Trigger |
|----------|------------|---------|
| BAS Prep | "Explain variance" | Button click, opens AI panel with context |
| BAS Prep | "Pre-lodgement checklist" | AI-generated checklist of things to verify |
| Quality Review | "Explain issues" | Expand on quality score issues |
| Client Detail | "Insights panel" | Show active insights for this client |
| Dashboard | "Insights widget" | Summary of portfolio insights |

### AI Panel Component

```typescript
// Reusable AI panel that can be embedded anywhere
interface AIPanelProps {
    context: {
        type: 'bas_variance' | 'quality_issue' | 'client_insight' | 'general';
        clientId?: string;
        basSessionId?: string;
        prefilledQuery?: string;
    };
    onClose: () => void;
}
```

---

## Feature 4: Insights Dashboard & Notifications

### Dashboard Widget

```
┌─────────────────────────────────────────────────────────────────────┐
│  🔔 Insights (5 new)                                    [View All →]│
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  🔴 HIGH  ACME Corp - GST threshold in 2 months         [Action →] │
│           Revenue $68K, trending to $90K                            │
│                                                                     │
│  🔴 HIGH  Beta LLC - 15 unreconciled transactions       [Review →] │
│           Last sync: 2 hours ago                                    │
│                                                                     │
│  🟡 MED   Delta Inc - BAS due in 5 days                 [Prepare →]│
│           Q2 2025 not started                                       │
│                                                                     │
│  🟡 MED   3 clients - Super guarantee due June 28       [View →]   │
│                                                                     │
│  🟢 LOW   Gamma Corp - Potential deductions identified  [View →]   │
│           Home office, vehicle expenses                             │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Notification System Integration

Leverage existing notification infrastructure (Spec 011):

```python
# New notification types for insights
class InsightNotificationType(str, Enum):
    INSIGHT_HIGH_PRIORITY = "insight_high_priority"
    INSIGHT_BATCH_DAILY = "insight_batch_daily"
    INSIGHT_WEEKLY_SUMMARY = "insight_weekly_summary"
```

---

## API Endpoints

### Insights API

```
# Insight management
GET    /api/v1/insights                    # List insights (filterable)
GET    /api/v1/insights/{id}               # Get single insight
POST   /api/v1/insights/{id}/view          # Mark as viewed
POST   /api/v1/insights/{id}/action        # Mark as actioned
POST   /api/v1/insights/{id}/dismiss       # Dismiss insight
POST   /api/v1/insights/generate           # Trigger manual generation

# Multi-client queries
POST   /api/v1/agents/multi-client/chat    # Cross-portfolio AI query
POST   /api/v1/agents/multi-client/stream  # Streaming version

# Dashboard
GET    /api/v1/insights/dashboard          # Dashboard summary
GET    /api/v1/insights/stats              # Insight statistics
```

### Query Parameters

```
GET /api/v1/insights?
    status=new,viewed              # Filter by status
    priority=high,medium           # Filter by priority
    category=compliance,quality    # Filter by category
    client_id=uuid                 # Filter by client
    limit=20                       # Pagination
    offset=0
```

---

## Database Schema

```sql
-- Insights table
CREATE TABLE insights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    client_id UUID REFERENCES xero_connections(id),  -- NULL for multi-client

    -- Classification
    category VARCHAR(50) NOT NULL,
    insight_type VARCHAR(100) NOT NULL,
    priority VARCHAR(20) NOT NULL DEFAULT 'medium',

    -- Content
    title VARCHAR(255) NOT NULL,
    summary TEXT NOT NULL,
    detail TEXT,

    -- Actions
    suggested_actions JSONB DEFAULT '[]',
    related_url VARCHAR(500),

    -- Lifecycle
    status VARCHAR(50) NOT NULL DEFAULT 'new',
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    viewed_at TIMESTAMPTZ,
    actioned_at TIMESTAMPTZ,
    dismissed_at TIMESTAMPTZ,

    -- Audit
    generation_source VARCHAR(50) NOT NULL,
    confidence DECIMAL(3,2),
    data_snapshot JSONB,

    -- Constraints
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_insights_tenant_status ON insights(tenant_id, status);
CREATE INDEX idx_insights_tenant_priority ON insights(tenant_id, priority);
CREATE INDEX idx_insights_client ON insights(client_id) WHERE client_id IS NOT NULL;
CREATE INDEX idx_insights_generated ON insights(generated_at DESC);

-- RLS
ALTER TABLE insights ENABLE ROW LEVEL SECURITY;
CREATE POLICY insights_tenant_isolation ON insights
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid);
```

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Insights generated per client per week | > 2 |
| False positive rate | < 15% |
| Insights actioned within 48h | > 60% |
| Accountant satisfaction (useful rating) | > 80% |
| Multi-client query accuracy | > 85% |

---

## Out of Scope (Future Specs)

- Email notifications (Spec 017 - Trigger System)
- Automated actions (Spec 017)
- Cross-pillar "Magic Zone" analysis (Spec 018)
- Business owner notifications (Spec 020)

---

## Technical Notes

### Celery Tasks

```python
# Daily insight generation
@celery.task
def generate_daily_insights():
    """Run all analyzers for all active tenants."""

# Post-sync insight generation
@celery.task
def generate_post_sync_insights(connection_id: UUID):
    """Run analyzers for specific client after Xero sync."""
```

### Analyzer Interface

```python
class InsightAnalyzer(ABC):
    """Base class for insight analyzers."""

    @abstractmethod
    async def analyze(
        self,
        tenant_id: UUID,
        client_id: UUID | None,
    ) -> list[Insight]:
        """Generate insights for tenant/client."""
```

---

## References

- Spec 012: Knowledge Base (RAG foundation)
- Spec 013: Client-Context Chat (client data access)
- Spec 014: Multi-Agent Framework (perspective analysis)
- Spec 011: Notifications (notification infrastructure)
