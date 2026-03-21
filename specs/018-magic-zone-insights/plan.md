# Implementation Plan: Magic Zone Insights (Spec 018)

**Spec**: `/specs/018-magic-zone-insights/spec.md`
**Branch**: `feature/018-magic-zone-insights`

---

## Overview

This plan implements two focused enhancements:

1. **Magic Zone Analyzer** - Routes high-value scenarios to Multi-Agent Orchestrator
2. **OPTIONS Format** - Strategy Agent outputs structured choices with trade-offs

The implementation leverages existing infrastructure (Multi-Agent Framework from Spec 014) with minimal new code.

---

## Architecture

### Current Flow (Spec 016)

```
Trigger → AI Analyzer → Single Claude Call → Insight
                              ↓
                        Generic prompt
                        ~3-5 seconds
                        ~$0.05/insight
```

### Enhanced Flow (Spec 018)

```
Trigger → Magic Zone Analyzer → Multi-Agent Orchestrator → Insight
                                        ↓
                              ┌─────────┼─────────┐
                              ↓         ↓         ↓
                         Compliance  Strategy  Insight
                           Agent      Agent     Agent
                              ↓         ↓         ↓
                              └─────────┼─────────┘
                                        ↓
                                   Synthesis
                                   ~10-15 sec
                                   ~$0.15/insight
```

---

## Component Design

### 1. Magic Zone Trigger Detection

**Location**: `backend/app/modules/insights/analyzers/magic_zone.py`

```python
from enum import Enum
from dataclasses import dataclass
from typing import Optional
from datetime import date

class MagicZoneTriggerType(str, Enum):
    GST_THRESHOLD = "gst_threshold_approaching"
    EOFY_PLANNING = "eofy_planning_window"
    REVENUE_CHANGE = "significant_revenue_change"
    FIRST_EMPLOYEE = "first_employee_hired"
    STRUCTURE_REVIEW = "business_structure_review"
    CAPITAL_PURCHASE = "large_capital_purchase"


@dataclass
class MagicZoneTrigger:
    trigger_type: MagicZoneTriggerType
    title: str
    context: dict  # Trigger-specific data
    query: str  # Question to send to Orchestrator
    priority: str  # HIGH, MEDIUM


class MagicZoneTriggerDetector:
    """Detects scenarios that warrant Multi-Agent analysis."""

    async def detect_triggers(
        self,
        db: AsyncSession,
        connection: XeroConnection,
    ) -> list[MagicZoneTrigger]:
        triggers = []

        # GST Threshold Check
        gst_trigger = await self._check_gst_threshold(db, connection)
        if gst_trigger:
            triggers.append(gst_trigger)

        # EOFY Window Check (May-June)
        eofy_trigger = await self._check_eofy_window(db, connection)
        if eofy_trigger:
            triggers.append(eofy_trigger)

        # Revenue Change Check
        revenue_trigger = await self._check_revenue_change(db, connection)
        if revenue_trigger:
            triggers.append(revenue_trigger)

        return triggers

    async def _check_gst_threshold(
        self,
        db: AsyncSession,
        connection: XeroConnection,
    ) -> Optional[MagicZoneTrigger]:
        """
        Trigger if:
        - Not GST registered
        - Revenue > $60K (approaching $75K threshold)
        - Trending upward
        """
        profile = await self._get_client_profile(db, connection)

        if profile.is_gst_registered:
            return None

        if profile.annual_revenue < 60000:
            return None

        # Check upward trend
        trend = await self._get_revenue_trend(db, connection)
        if trend.direction != "increasing":
            return None

        return MagicZoneTrigger(
            trigger_type=MagicZoneTriggerType.GST_THRESHOLD,
            title="GST Registration Decision",
            context={
                "current_revenue": profile.annual_revenue,
                "projected_revenue": trend.projected_annual,
                "months_to_threshold": trend.months_to_threshold,
            },
            query=f"""
            This client has annual revenue of ${profile.annual_revenue:,.0f}
            and is projected to reach ${trend.projected_annual:,.0f} within
            {trend.months_to_threshold} months.

            They are NOT currently registered for GST. The $75,000 threshold
            requires registration within 21 days of being exceeded.

            What are their OPTIONS? Consider:
            1. Register now vs wait
            2. Input credit opportunities
            3. Impact on client pricing
            4. Business structure alternatives
            """,
            priority="HIGH",
        )

    async def _check_eofy_window(
        self,
        db: AsyncSession,
        connection: XeroConnection,
    ) -> Optional[MagicZoneTrigger]:
        """
        Trigger if:
        - Current month is May or June
        - Haven't generated EOFY insight in last 30 days
        """
        today = date.today()
        if today.month not in [5, 6]:
            return None

        # Check for recent EOFY insight
        recent = await self._has_recent_insight(
            db, connection, "eofy_planning_window", days=30
        )
        if recent:
            return None

        profile = await self._get_client_profile(db, connection)

        return MagicZoneTrigger(
            trigger_type=MagicZoneTriggerType.EOFY_PLANNING,
            title="End of Financial Year Planning",
            context={
                "days_to_eofy": (date(today.year, 6, 30) - today).days,
                "entity_type": profile.entity_type,
                "annual_revenue": profile.annual_revenue,
            },
            query=f"""
            The financial year ends in {(date(today.year, 6, 30) - today).days} days.

            This client is a {profile.entity_type} with annual revenue
            of ${profile.annual_revenue:,.0f}.

            What EOFY planning OPTIONS should they consider?
            Include:
            1. Deduction timing (prepay expenses, asset purchases)
            2. Super contributions (concessional cap)
            3. Income deferral opportunities
            4. Trust distribution considerations (if applicable)
            5. Any compliance deadlines
            """,
            priority="HIGH",
        )

    async def _check_revenue_change(
        self,
        db: AsyncSession,
        connection: XeroConnection,
    ) -> Optional[MagicZoneTrigger]:
        """
        Trigger if:
        - Revenue changed >30% compared to prior period
        - Either direction (growth or decline)
        """
        trend = await self._get_revenue_trend(db, connection)

        if abs(trend.change_percent) < 30:
            return None

        direction = "increased" if trend.change_percent > 0 else "decreased"

        return MagicZoneTrigger(
            trigger_type=MagicZoneTriggerType.REVENUE_CHANGE,
            title=f"Significant Revenue {'Growth' if trend.change_percent > 0 else 'Decline'}",
            context={
                "change_percent": trend.change_percent,
                "prior_revenue": trend.prior_period,
                "current_revenue": trend.current_period,
            },
            query=f"""
            This client's revenue has {direction} by {abs(trend.change_percent):.0f}%
            compared to the prior period.

            Prior period: ${trend.prior_period:,.0f}
            Current period: ${trend.current_period:,.0f}

            What are the strategic OPTIONS given this change?
            Consider:
            1. Tax implications of {'higher' if trend.change_percent > 0 else 'lower'} income
            2. Cash flow management
            3. Business structure review (if significant growth)
            4. Cost optimization (if decline)
            5. Any compliance changes triggered
            """,
            priority="HIGH",
        )
```

### 2. Magic Zone Analyzer

**Location**: `backend/app/modules/insights/analyzers/magic_zone.py`

```python
from app.modules.insights.analyzers.base import BaseAnalyzer
from app.modules.insights.models import Insight, InsightCategory, InsightPriority
from app.modules.agents.orchestrator import OrchestratorService


class MagicZoneAnalyzer(BaseAnalyzer):
    """
    Routes complex scenarios to Multi-Agent Orchestrator
    for cross-pillar analysis with OPTIONS format.
    """

    category = InsightCategory.STRATEGIC

    def __init__(self):
        self.trigger_detector = MagicZoneTriggerDetector()
        self.orchestrator = OrchestratorService()

    async def analyze_client(
        self,
        db: AsyncSession,
        connection: XeroConnection,
    ) -> list[Insight]:
        insights = []

        # Detect Magic Zone triggers
        triggers = await self.trigger_detector.detect_triggers(db, connection)

        for trigger in triggers:
            try:
                # Call Multi-Agent Orchestrator
                response = await self._call_orchestrator(
                    db=db,
                    connection=connection,
                    trigger=trigger,
                )

                # Build insight from orchestrator response
                insight = self._build_insight(
                    trigger=trigger,
                    response=response,
                    connection=connection,
                )
                insights.append(insight)

            except Exception as e:
                # Log error but continue with other triggers
                logger.error(
                    "magic_zone_orchestrator_error",
                    trigger=trigger.trigger_type,
                    connection_id=str(connection.id),
                    error=str(e),
                )

        return insights

    async def _call_orchestrator(
        self,
        db: AsyncSession,
        connection: XeroConnection,
        trigger: MagicZoneTrigger,
    ) -> OrchestratorResponse:
        """
        Invoke Multi-Agent Orchestrator for cross-pillar analysis.
        """
        response = await self.orchestrator.process_query(
            query=trigger.query,
            connection_id=connection.id,
            tenant_id=connection.tenant_id,
            options_format=True,  # Force OPTIONS output
            db=db,
        )

        return response

    def _build_insight(
        self,
        trigger: MagicZoneTrigger,
        response: OrchestratorResponse,
        connection: XeroConnection,
    ) -> Insight:
        """
        Convert orchestrator response to Insight model.
        """
        # Count options in response
        options_count = self._count_options(response.content)

        return Insight(
            tenant_id=connection.tenant_id,
            client_id=connection.id,
            category=InsightCategory.STRATEGIC,
            insight_type=trigger.trigger_type.value,
            priority=InsightPriority.HIGH,
            title=trigger.title,
            summary=self._extract_summary(response.content),
            detail=response.content,  # Full OPTIONS markdown
            suggested_actions=self._extract_actions(response.content),
            related_url=f"/clients/{connection.id}",
            generation_source="magic_zone",
            confidence=response.confidence,
            data_snapshot=trigger.context,
            # New fields
            generation_type="magic_zone",
            agents_used=response.agents_used,
            options_count=options_count,
        )

    def _count_options(self, content: str) -> int:
        """Count 'Option N:' occurrences in content."""
        import re
        return len(re.findall(r'### Option \d+:', content))

    def _extract_summary(self, content: str) -> str:
        """Extract first paragraph or generate summary."""
        lines = content.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('---'):
                return line[:200]
        return "Strategic analysis with multiple options available."

    def _extract_actions(self, content: str) -> list[dict]:
        """Extract Action items from OPTIONS format."""
        import re
        actions = []
        pattern = r'\*\*Action:\*\* (.+?)(?:\n|$)'
        matches = re.findall(pattern, content)
        for i, action in enumerate(matches):
            actions.append({
                "action": action.strip(),
                "option_number": i + 1,
            })
        return actions
```

### 3. Strategy Agent Prompt Update

**Location**: `backend/app/modules/agents/prompts/strategy.py`

```python
STRATEGY_AGENT_SYSTEM_PROMPT = """
You are a strategic business advisor for Australian SMBs, working alongside
accountants in a BAS preparation and advisory platform called Clairo.

## Your Role

Provide strategic tax optimization and business advice tailored to each
client's specific situation. You have access to their financial data,
entity type, industry, and revenue profile.

## OUTPUT FORMAT: OPTIONS

When providing strategic advice, ALWAYS present 2-4 OPTIONS with trade-offs.
This empowers accountants to discuss choices with their clients.

### Required Format

```markdown
## Options

### Option 1: [Short Name] (Recommended)
**Best if:** [One-line condition when this is the best choice]

**Pros:**
- [Specific benefit with numbers if possible]
- [Another benefit]
- [Third benefit if applicable]

**Cons:**
- [Specific drawback]
- [Another drawback]

**Action:** [Concrete next step the accountant/client can take]

---

### Option 2: [Short Name]
**Best if:** [Condition]

**Pros:**
- [Benefits]

**Cons:**
- [Drawbacks]

**Action:** [Next step]

---

[Add Option 3 and 4 if genuinely different approaches exist]
```

## Rules

1. **Always provide 2-4 options** - Never just one recommendation
2. **Mark "(Recommended)" sparingly** - Only when one option is clearly superior
3. **Be specific** - Include dollar amounts, percentages, timeframes
4. **Pros must outnumber cons** - At least 2 pros per option
5. **Actions must be concrete** - "Register via ATO Portal" not "Consider registering"
6. **Consider client context** - Entity type, revenue, industry matter
7. **Include compliance angles** - Partner with Compliance Agent context
8. **Acknowledge uncertainty** - If advice depends on factors you don't know

## Australian Context

- GST threshold: $75,000 annual turnover
- Company tax rate: 25% (base rate entity) or 30%
- Super guarantee: 11.5% (increasing to 12% July 2025)
- Financial year: July 1 - June 30
- BAS lodgement: Monthly (>$20M) or Quarterly (most SMBs)

## Example Response

```markdown
## Options

### Option 1: Register for GST Now (Recommended)
**Best if:** You want to claim input credits on recent purchases

**Pros:**
- Claim $1,250 in input credits from last quarter's equipment
- Avoid penalties if $75K threshold crossed unexpectedly
- Professional credibility with larger clients who expect GST invoices

**Cons:**
- Must charge GST on all taxable supplies (effective 10% price increase)
- Quarterly BAS lodgement requirement begins

**Action:** Complete GST registration via ATO Business Portal - takes 2-3 business days

---

### Option 2: Wait Until Threshold is Certain
**Best if:** Revenue growth is inconsistent or seasonal

**Pros:**
- No BAS compliance burden until legally required
- Simpler invoicing and bookkeeping for now
- Can reassess in 3 months with more data

**Cons:**
- Cannot claim input credits on current purchases ($800 unclaimed YTD)
- Must register within 21 days if threshold crossed - tight timeline

**Action:** Set revenue monitoring alert at $65,000 to give 21-day buffer

---

### Option 3: Restructure as Company
**Best if:** Asset protection and long-term tax planning are priorities

**Pros:**
- Limited liability protects personal assets
- Company tax rate (25%) vs personal marginal rate (potentially 32.5%+)
- Easier to bring in partners or sell the business later

**Cons:**
- Setup costs: $1,500-3,000 (company registration, accountant fees)
- Ongoing compliance: $800-1,500/year (ASIC fees, company tax return)
- More complex profit extraction (dividends, salary)

**Action:** Book strategy session with accountant to model 5-year comparison
```
"""


def get_strategy_agent_prompt(options_format: bool = False) -> str:
    """
    Get Strategy Agent prompt, optionally enforcing OPTIONS format.
    """
    if options_format:
        return STRATEGY_AGENT_SYSTEM_PROMPT
    else:
        # Fallback to simpler prompt for quick queries
        return STRATEGY_AGENT_SIMPLE_PROMPT
```

### 4. Orchestrator Service Update

**Location**: `backend/app/modules/agents/orchestrator.py`

Add `options_format` parameter to existing orchestrator:

```python
class OrchestratorService:
    """
    Routes queries to specialist agents and synthesizes responses.
    """

    async def process_query(
        self,
        query: str,
        connection_id: UUID,
        tenant_id: UUID,
        db: AsyncSession,
        options_format: bool = False,  # NEW PARAMETER
    ) -> OrchestratorResponse:
        """
        Process a query through the multi-agent system.

        Args:
            query: The user's question
            connection_id: Client connection ID
            tenant_id: Tenant ID for data access
            db: Database session
            options_format: If True, force Strategy Agent to output OPTIONS
        """
        # Existing routing logic...

        # When calling Strategy Agent, pass options_format
        if "strategy" in agents_to_call:
            strategy_response = await self.strategy_agent.process(
                query=query,
                context=context,
                options_format=options_format,  # Pass through
            )

        # Rest of existing synthesis logic...
```

### 5. Frontend OPTIONS Display

**Location**: `frontend/src/app/(protected)/clients/[id]/page.tsx`

Enhance the insight detail modal to render OPTIONS nicely:

```typescript
// Add to existing InsightDetailModal component

const OptionsDisplay = ({ content }: { content: string }) => {
  // Parse OPTIONS from markdown
  const optionRegex = /### Option (\d+): (.+?)(?:\n|$)/g;
  const options: Array<{
    number: number;
    name: string;
    isRecommended: boolean;
  }> = [];

  let match;
  while ((match = optionRegex.exec(content)) !== null) {
    options.push({
      number: parseInt(match[1]),
      name: match[2].replace(' (Recommended)', ''),
      isRecommended: match[2].includes('(Recommended)'),
    });
  }

  if (options.length === 0) {
    // Not an OPTIONS-format insight, render normally
    return (
      <div className="prose prose-sm max-w-none">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {content}
        </ReactMarkdown>
      </div>
    );
  }

  // Render OPTIONS with enhanced styling
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Sparkles className="h-4 w-4" />
        <span>{options.length} options to consider</span>
      </div>

      <div className="prose prose-sm max-w-none">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            h3: ({ children, ...props }) => {
              const text = String(children);
              const isOption = text.startsWith('Option');
              const isRecommended = text.includes('(Recommended)');

              if (isOption) {
                return (
                  <div
                    className={cn(
                      'rounded-lg border p-4 mb-4',
                      isRecommended
                        ? 'border-green-500 bg-green-50 dark:bg-green-950'
                        : 'border-border bg-muted/30'
                    )}
                  >
                    <h3
                      className={cn(
                        'text-base font-semibold flex items-center gap-2',
                        isRecommended && 'text-green-700 dark:text-green-400'
                      )}
                      {...props}
                    >
                      {isRecommended && <Star className="h-4 w-4" />}
                      {children}
                    </h3>
                  </div>
                );
              }
              return <h3 {...props}>{children}</h3>;
            },
            // Style Pros/Cons
            li: ({ children, ...props }) => {
              const text = String(children);
              // Check if parent is in Pros or Cons section
              return (
                <li className="flex items-start gap-2" {...props}>
                  {children}
                </li>
              );
            },
          }}
        >
          {content}
        </ReactMarkdown>
      </div>
    </div>
  );
};
```

### 6. Database Migration

**Location**: `backend/alembic/versions/021_magic_zone_insights.py`

```python
"""Add Magic Zone insight fields

Revision ID: 021
Revises: 020
Create Date: 2025-01-XX
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '021'
down_revision = '020'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'insights',
        sa.Column('generation_type', sa.String(50), default='rule_based')
    )
    op.add_column(
        'insights',
        sa.Column('agents_used', JSONB, nullable=True)
    )
    op.add_column(
        'insights',
        sa.Column('options_count', sa.Integer, nullable=True)
    )

    # Index for filtering Magic Zone insights
    op.create_index(
        'idx_insights_generation_type',
        'insights',
        ['generation_type']
    )


def downgrade():
    op.drop_index('idx_insights_generation_type')
    op.drop_column('insights', 'options_count')
    op.drop_column('insights', 'agents_used')
    op.drop_column('insights', 'generation_type')
```

---

## Integration Points

### Insight Generator Registration

**File**: `backend/app/modules/insights/generator.py`

```python
from app.modules.insights.analyzers.magic_zone import MagicZoneAnalyzer

class InsightGenerator:
    def __init__(self):
        self.analyzers = [
            ComplianceAnalyzer(),
            QualityAnalyzer(),
            CashFlowAnalyzer(),
            MagicZoneAnalyzer(),  # Add Magic Zone
        ]
```

### Deduplication

Magic Zone insights should not duplicate regular insights. Add check:

```python
async def _should_generate_magic_zone(
    self,
    db: AsyncSession,
    connection: XeroConnection,
    trigger_type: str,
) -> bool:
    """
    Check if we should generate a Magic Zone insight.
    Avoid if similar insight generated in last 14 days.
    """
    recent = await db.execute(
        select(Insight)
        .where(Insight.client_id == connection.id)
        .where(Insight.insight_type == trigger_type)
        .where(Insight.generated_at > datetime.utcnow() - timedelta(days=14))
        .where(Insight.status.not_in(['DISMISSED', 'EXPIRED']))
    )
    return recent.scalar_one_or_none() is None
```

---

## Testing Strategy

### Unit Tests

1. **Trigger Detection**
   - Test each trigger condition (GST threshold, EOFY, revenue change)
   - Test edge cases (already registered, wrong month, etc.)

2. **OPTIONS Parsing**
   - Test extraction of options from markdown
   - Test recommended option detection
   - Test action extraction

3. **Strategy Agent Prompt**
   - Test OPTIONS format output
   - Test with various client contexts

### Integration Tests

1. **Orchestrator Integration**
   - Test Magic Zone Analyzer → Orchestrator flow
   - Test options_format parameter propagation
   - Test timeout handling

2. **End-to-End**
   - Create client approaching GST threshold
   - Trigger insight generation
   - Verify Magic Zone insight created with OPTIONS

### Manual Testing

1. Connect test client with revenue ~$65K
2. Run insight generation
3. Verify Magic Zone insight appears
4. Check OPTIONS format in insight detail modal

---

## Rollout Plan

1. **Feature Flag**: `ENABLE_MAGIC_ZONE_INSIGHTS=false` initially
2. **Internal Testing**: Enable for dev/staging
3. **Beta**: Enable for 2-3 trusted accountant practices
4. **GA**: Enable for all after positive feedback

---

## Files to Create/Modify

### New Files

| File | Purpose |
|------|---------|
| `backend/app/modules/insights/analyzers/magic_zone.py` | Magic Zone Analyzer |
| `backend/app/modules/agents/prompts/strategy.py` | OPTIONS-format prompt |
| `backend/alembic/versions/021_magic_zone_insights.py` | Migration |

### Modified Files

| File | Changes |
|------|---------|
| `backend/app/modules/insights/generator.py` | Register MagicZoneAnalyzer |
| `backend/app/modules/insights/models.py` | Add new fields |
| `backend/app/modules/insights/schemas.py` | Add new fields to response |
| `backend/app/modules/agents/orchestrator.py` | Add options_format param |
| `frontend/src/app/(protected)/clients/[id]/page.tsx` | OPTIONS display |
| `frontend/src/types/insights.ts` | Add new fields |

---

## Estimated Effort

| Phase | Tasks | Estimate |
|-------|-------|----------|
| Phase 1: Strategy Agent Prompt | Prompt engineering, testing | 2 hours |
| Phase 2: Magic Zone Analyzer | Trigger detection, orchestrator integration | 4 hours |
| Phase 3: Frontend Enhancement | OPTIONS styling, type updates | 2 hours |
| Phase 4: Testing & Polish | Unit tests, integration tests, manual QA | 2 hours |
| **Total** | | **10 hours** |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Orchestrator latency too high | Set 15-second timeout, degrade gracefully |
| Cost spike from Magic Zone | Limit to 3 Magic Zone insights per client per month |
| OPTIONS format not parseable | Robust regex, fallback to standard markdown rendering |
| Duplicate insights | Deduplication check before generation |
