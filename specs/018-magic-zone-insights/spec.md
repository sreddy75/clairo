# Spec 018: Magic Zone Insights

**Status**: NOT_STARTED
**Phase**: C (Proactive Intelligence)
**Dependencies**: Spec 014 (Multi-Agent Framework) ✅, Spec 016 (Insight Engine) ✅, Spec 017 (Trigger System) ✅

---

## Executive Summary

This spec enhances the Insight Engine (Spec 016) to leverage the Multi-Agent Framework (Spec 014) for high-value insights. Currently, the AI Analyzer uses a single Claude API call to generate insights. For complex scenarios where all three pillars intersect (Data + Compliance + Strategy), we should instead invoke the Multi-Agent Orchestrator to get richer, multi-perspective analysis with actionable OPTIONS.

### The Gap

```
CURRENT STATE (Spec 016 AI Analyzer)        ENHANCED STATE (Spec 018)
────────────────────────────────────        ─────────────────────────────────
Single Claude call                          Multi-Agent Orchestrator call
Generic system prompt                       4 specialist agents collaborate
One perspective                             Cross-pillar synthesis
Single recommendation                       2-4 OPTIONS with trade-offs
No RAG knowledge access                     RAG-powered compliance context
~$0.05/insight                              ~$0.15/insight (high-value only)
```

### Key Insight

The Multi-Agent Framework already exists and does cross-pillar analysis for interactive chat. But proactive insight generation bypasses it entirely. This spec connects them.

---

## Goals

1. **Enhanced Insight Quality** - Use Multi-Agent system for complex, high-value insights
2. **OPTIONS Format** - Present accountants with choices and trade-offs, not just recommendations
3. **RAG Integration** - Leverage compliance knowledge base in proactive insights
4. **Minimal UX Change** - Same screens, same flow, richer content in insight detail

---

## Scope

### In Scope

1. **Magic Zone Analyzer** - New analyzer that routes to Multi-Agent Orchestrator
2. **Strategy Agent Prompt Update** - OPTIONS format for strategic recommendations
3. **Insight Detail Enhancement** - Display OPTIONS in insight detail modal

### Out of Scope

- New UI pages or navigation
- Changes to action items workflow
- Business owner portal (Phase D)
- Automated option selection

---

## Enhancement 1: Magic Zone Analyzer

### Concept

For certain high-value triggers, instead of calling the single-prompt AI Analyzer, call the Multi-Agent Orchestrator. This leverages:
- **Compliance Agent** → ATO rules from RAG knowledge base
- **Quality Agent** → Data quality context
- **Strategy Agent** → Business optimization options
- **Insight Agent** → Pattern synthesis

### Trigger Conditions

The Magic Zone Analyzer activates for these scenarios:

| Trigger | Why Multi-Agent? |
|---------|------------------|
| GST threshold approaching | Compliance (registration rules) + Strategy (timing options) |
| EOFY approaching (May-June) | Compliance (deadlines) + Strategy (deductions, super) |
| Significant revenue change (>30%) | Insight (trend analysis) + Strategy (structure review) |
| First employee hired | Compliance (PAYG, super) + Strategy (award compliance) |
| Business structure question | Compliance (tax implications) + Strategy (protection, growth) |
| Large capital purchase | Compliance (depreciation) + Strategy (timing, financing) |

### Implementation Approach

```python
class MagicZoneAnalyzer(BaseAnalyzer):
    """
    Routes complex scenarios to Multi-Agent Orchestrator
    instead of single Claude call.
    """

    category = InsightCategory.STRATEGIC

    async def analyze_client(
        self,
        db: AsyncSession,
        connection: XeroConnection,
    ) -> list[Insight]:
        insights = []

        # Check each Magic Zone trigger
        triggers = await self._detect_magic_zone_triggers(db, connection)

        for trigger in triggers:
            # Call Multi-Agent Orchestrator (not single Claude call)
            orchestrator_response = await self._call_orchestrator(
                connection=connection,
                trigger=trigger,
                require_options=True,  # Force OPTIONS format
            )

            insight = self._build_insight_from_orchestrator(
                response=orchestrator_response,
                trigger=trigger,
                connection=connection,
            )
            insights.append(insight)

        return insights
```

### Orchestrator Integration

```python
async def _call_orchestrator(
    self,
    connection: XeroConnection,
    trigger: MagicZoneTrigger,
    require_options: bool = True,
) -> OrchestratorResponse:
    """
    Invoke the Multi-Agent Orchestrator for cross-pillar analysis.
    """
    # Build query from trigger
    query = self._build_orchestrator_query(trigger)

    # Call existing orchestrator (from Spec 014)
    response = await orchestrator_service.process_query(
        query=query,
        connection_id=connection.id,
        tenant_id=connection.tenant_id,
        options_format=require_options,  # New parameter
    )

    return response
```

---

## Enhancement 2: OPTIONS Format for Strategy Agent

### Current Behavior

Strategy Agent returns a single recommendation:

```
"This client should register for GST now to claim input credits
on recent purchases. The registration process takes 2-3 days
and backdating is possible for up to 4 years."
```

### Enhanced Behavior

Strategy Agent returns 2-4 OPTIONS with trade-offs:

```markdown
## Options

### Option 1: Register for GST Now (Recommended)
**Best if:** You want to claim input credits immediately

**Pros:**
- Claim $890 in input credits from recent equipment purchase
- Avoid penalties if threshold crossed unexpectedly
- Simplified pricing (all prices GST-inclusive)

**Cons:**
- Must charge GST to clients (10% price increase perception)
- Quarterly BAS lodgement requirement
- Cash flow timing (collect GST, remit later)

**Action:** Register via ATO Business Portal or accountant lodgement

---

### Option 2: Wait Until Threshold Crossed
**Best if:** Revenue growth is uncertain, want to delay compliance burden

**Pros:**
- No BAS lodgement until required
- Simpler invoicing for now
- Delay cash flow complexity

**Cons:**
- Cannot claim input credits on current purchases
- Must register within 21 days of crossing $75K
- May need to backdate if threshold crossed unknowingly

**Action:** Monitor monthly revenue, set reminder at $65K

---

### Option 3: Consider Company Structure
**Best if:** Asset protection and tax planning are priorities

**Pros:**
- Asset protection from business liabilities
- Potential tax rate benefits (30% company vs marginal rate)
- Professional image for clients

**Cons:**
- Setup costs ($1,500-3,000)
- Annual compliance (ASIC fees, company tax return)
- More complex to extract profits

**Action:** Discuss with accountant, compare 5-year projections
```

### Prompt Engineering

Update Strategy Agent system prompt to enforce OPTIONS format:

```python
STRATEGY_AGENT_PROMPT = """
You are a strategic business advisor for Australian SMBs.
When providing advice, ALWAYS present 2-4 OPTIONS with trade-offs.

FORMAT YOUR RESPONSE AS:

## Options

### Option 1: [Name] (Recommended if applicable)
**Best if:** [One-line condition when this is the best choice]

**Pros:**
- [Benefit 1]
- [Benefit 2]
- [Benefit 3]

**Cons:**
- [Drawback 1]
- [Drawback 2]

**Action:** [Specific next step]

---

### Option 2: [Name]
[Same format...]

---

RULES:
1. Always provide at least 2 options, maximum 4
2. Mark one as "(Recommended)" only if clearly superior
3. Each option must have at least 2 pros and 1 con
4. "Action" must be a specific, concrete next step
5. Consider the client's specific situation (entity type, revenue, industry)
6. Include relevant numbers/estimates where possible
"""
```

---

## Enhancement 3: Insight Detail Display

### Current UI

The insight detail modal shows:
- Title
- Summary
- Detail (markdown)
- Suggested actions (list)
- Action buttons

### Enhanced UI

For Magic Zone insights, the detail section renders the OPTIONS format:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ⚡ Magic Zone Insight                                        [Close X] │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  GST Registration Decision                                              │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━│
│                                                                         │
│  📊 Analysis from: Compliance Agent, Strategy Agent, Insight Agent      │
│  🎯 Confidence: 0.89                                                    │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │ Option 1: Register Now ⭐ Recommended                               ││
│  │                                                                     ││
│  │ Best if: You want to claim input credits immediately                ││
│  │                                                                     ││
│  │ ✓ Claim $890 in input credits                                       ││
│  │ ✓ Avoid penalties if threshold crossed                              ││
│  │ ✗ Must charge GST to clients                                        ││
│  │ ✗ Quarterly BAS requirement                                         ││
│  │                                                                     ││
│  │ Action: Register via ATO Business Portal                            ││
│  └─────────────────────────────────────────────────────────────────────┘│
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │ Option 2: Wait Until Threshold                                      ││
│  │                                                                     ││
│  │ Best if: Revenue growth uncertain                                   ││
│  │                                                                     ││
│  │ ✓ No BAS lodgement until required                                   ││
│  │ ✓ Simpler invoicing                                                 ││
│  │ ✗ Cannot claim current input credits                                ││
│  │                                                                     ││
│  │ Action: Monitor revenue, set $65K reminder                          ││
│  └─────────────────────────────────────────────────────────────────────┘│
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │ Option 3: Consider Company Structure                                ││
│  │                                                                     ││
│  │ Best if: Asset protection is priority                               ││
│  │                                                                     ││
│  │ ✓ Asset protection                                                  ││
│  │ ✓ Potential tax benefits                                            ││
│  │ ✗ Setup costs $1,500-3,000                                          ││
│  │                                                                     ││
│  │ Action: Discuss with accountant                                     ││
│  └─────────────────────────────────────────────────────────────────────┘│
│                                                                         │
│  [Mark Viewed]  [Convert to Action Item]  [Dismiss]                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Implementation Notes

- OPTIONS are stored in `insight.detail` as markdown
- Existing `react-markdown` + `remark-gfm` renders the format
- Add CSS styling for option cards (border, background)
- "Convert to Action Item" creates separate action for each option if needed

---

## Data Model Changes

### Insight Model Updates

```python
class Insight:
    # ... existing fields ...

    # New fields for Magic Zone insights
    generation_type: str  # "rule_based", "ai_single", "magic_zone"
    agents_used: list[str] | None  # ["compliance", "strategy", "insight"]
    options_count: int | None  # Number of options presented
```

### Migration

```sql
ALTER TABLE insights
ADD COLUMN generation_type VARCHAR(50) DEFAULT 'rule_based',
ADD COLUMN agents_used JSONB,
ADD COLUMN options_count INTEGER;
```

---

## API Changes

### Generate Insights Endpoint

No changes to existing endpoint. The Magic Zone Analyzer is added to the analyzer registry and runs automatically.

### Orchestrator Service Update

Add `options_format` parameter:

```python
async def process_query(
    self,
    query: str,
    connection_id: UUID,
    tenant_id: UUID,
    options_format: bool = False,  # NEW: Force OPTIONS output from Strategy Agent
) -> OrchestratorResponse:
```

---

## Cost Analysis

| Insight Type | Current Cost | Magic Zone Cost | When Used |
|--------------|--------------|-----------------|-----------|
| Rule-based | ~$0 | ~$0 | Simple threshold checks |
| AI Single Call | ~$0.05 | ~$0.05 | Pattern detection |
| Magic Zone | N/A | ~$0.15 | Complex strategic decisions |

**Expected volume**: ~5-10% of insights trigger Magic Zone (high-value scenarios only)

**Cost impact**: Minimal increase in overall insight generation cost

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Magic Zone insights generated per client per month | 1-3 |
| OPTIONS format adoption (insights with 2+ options) | 100% of Magic Zone |
| Accountant "useful" rating for Magic Zone insights | >90% |
| Time saved per strategic decision | 15-20 min → 3-5 min |

---

## Implementation Phases

### Phase 1: Strategy Agent Prompt Update
- Update Strategy Agent prompt for OPTIONS format
- Test with existing chat interface
- Validate output structure

### Phase 2: Magic Zone Analyzer
- Create MagicZoneAnalyzer class
- Implement trigger detection
- Integrate with Orchestrator service

### Phase 3: Frontend Enhancement
- Style OPTIONS cards in insight detail modal
- Add "agents used" display
- Test rendering with various option counts

### Phase 4: Testing & Polish
- End-to-end testing with real client data
- Cost monitoring
- Performance validation

---

## Technical Notes

### Why Not Always Use Multi-Agent?

1. **Cost**: Multi-Agent queries cost ~3x more than single calls
2. **Latency**: Multi-Agent takes 10-15 seconds vs 3-5 seconds
3. **Value**: Simple insights (e.g., "15 unreconciled transactions") don't need strategic analysis

Magic Zone is reserved for scenarios where the extra cost/latency provides proportionally higher value.

### Orchestrator Integration

The Multi-Agent Orchestrator (Spec 014) already handles:
- Parallel agent execution
- Response synthesis
- Confidence scoring
- Audit logging

We're adding a new entry point (proactive insights) rather than rebuilding.

---

## References

- Spec 012: Knowledge Base + RAG Engine
- Spec 013: Client-Context Chat
- Spec 014: Multi-Agent Framework (Orchestrator, Specialist Agents)
- Spec 016: Insight Engine (AI Analyzer, Proactive Insights)
- Spec 016b: Action Items (Convert Insight to Action)
- Spec 017: Trigger System (Automated Insight Generation)
