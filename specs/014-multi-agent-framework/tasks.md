# Tasks: Multi-Agent Framework (Spec 014)

**Input**: Design documents from `/specs/014-multi-agent-framework/`
**Prerequisites**: plan.md (required), spec.md (required)
**Branch**: `feature/014-multi-agent-framework`

---

## 📊 Implementation Status

| Phase | Status | Tasks |
|-------|--------|-------|
| Phase 0: Git Setup | ✅ Complete | T000 |
| Phase 1: Setup & Foundation | ✅ Complete | T001-T004 |
| Phase 2: Perspective Detection | ✅ Complete | T005-T007 |
| Phase 3: Orchestrator MVP | ✅ Complete | T008-T013 |
| Phase 4: Escalation & Audit | ✅ Complete | T014-T016 |
| Phase 5: Frontend Integration | ✅ Complete | T017-T021 |
| Phase 6: Polish & Testing | ✅ Complete | T022-T025 |
| Phase FINAL: PR & Merge | ✅ Complete | TFINAL-1 to TFINAL-4 |

**Last Updated**: 2024-12-31

### Additional Enhancements Implemented
- SSE streaming endpoint (`/api/v1/agents/chat/stream`) with thinking status messages
- `ThinkingIndicator` component with animated progress and perspective detection display
- Real-time status updates during processing ("Analyzing...", "Loading client data...", etc.)

## Implementation Strategy: Simplified First

> **Note**: The spec.md and plan.md document the full multi-agent vision with separate
> agent classes and parallel LLM calls. This tasks.md implements a **simplified approach**
> that delivers the same user value with better performance and lower cost:
>
> - **Single LLM call** with multi-perspective prompt (not 4 separate calls)
> - **Perspective detection** determines which lenses to apply
> - **Attributed responses** parsed from structured output
> - **Same user experience** - accountant sees [Compliance], [Insight], etc.
>
> This approach can be expanded to true multi-agent architecture later if needed.

### Why Simplified?

| Aspect | Full Spec (4 agents) | Simplified (1 call) |
|--------|---------------------|---------------------|
| LLM Calls | 4-5 per query | 1 per query |
| Cost | $0.50-1.00 | $0.10-0.15 |
| Latency | 10-15 seconds | 3-5 seconds |
| User Value | ✓ Same | ✓ Same |

---

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- Include exact file paths in descriptions

---

## Phase 0: Git Setup (REQUIRED)

**Purpose**: Create feature branch before any implementation

- [x] T000 Create feature branch from main ✅
  - Run: `git checkout main && git pull origin main`
  - Run: `git checkout -b feature/014-multi-agent-framework`
  - Verify: You are now on the feature branch

---

## Phase 1: Setup & Foundation

**Purpose**: Module structure and core components

- [x] T001 [P] Create agents module directory structure ✅
  - Create: `backend/app/modules/agents/__init__.py`
  - Create: `backend/app/modules/agents/models.py`
  - Create: `backend/app/modules/agents/schemas.py`
  - Create: `backend/app/modules/agents/router.py`
  - Create: `backend/app/modules/agents/exceptions.py`

- [x] T002 [P] Create agent settings configuration ✅
  - Create: `backend/app/modules/agents/settings.py`
  - Add `AgentSettings` class with confidence thresholds, perspective configs
  - Add to `backend/app/config.py` settings loading

- [x] T003 [P] Create database migration for agent audit ✅
  - Create migration for `agent_queries` table (simplified)
  - Fields: id, correlation_id, tenant_id, user_id, client_id, perspectives_used, confidence, escalation_required, created_at
  - Add RLS policies for tenant isolation
  - Run: `alembic revision --autogenerate -m "add_agent_queries_table"`

- [x] T004 Implement agent schemas ✅
  - Add to `backend/app/modules/agents/schemas.py`:
    - `Perspective` enum (COMPLIANCE, QUALITY, STRATEGY, INSIGHT)
    - `PerspectiveResult` dataclass
    - `OrchestratorRequest` Pydantic model
    - `OrchestratorResponse` Pydantic model
    - `AgentChatRequest` Pydantic model

**Checkpoint**: Module structure ready ✅

---

## Phase 2: Perspective Detection & Context Building

**Purpose**: Determine which perspectives apply and build unified context

- [x] T005 Implement PerspectiveDetector ✅
  - Create: `backend/app/modules/agents/perspective_detector.py`
  - Implement `PerspectiveDetector` class with:
    - `PERSPECTIVE_PATTERNS` keyword dictionaries per perspective
    - `MULTI_PERSPECTIVE_PATTERNS` for complex queries
    - `detect(query, client_context) -> list[Perspective]`
  - Map query patterns to perspectives:
    - GST/BAS/tax/deduct → COMPLIANCE
    - error/issue/reconcile/duplicate → QUALITY
    - optimize/structure/strategy/should I → STRATEGY
    - trend/pattern/why/unusual → INSIGHT

- [x] T006 Extend ContextBuilder for multi-perspective ✅
  - Update: `backend/app/modules/knowledge/context_builder.py`
  - Add `build_multi_perspective_context()` method:
    - COMPLIANCE: Fetch from compliance_knowledge namespace
    - QUALITY: Fetch quality scores, uncoded txns, reconciliation status
    - STRATEGY: Fetch from strategic_advisory namespace
    - INSIGHT: Fetch trends, anomalies, threshold alerts
  - Return unified context dict keyed by perspective

- [x] T007 Add quality data to context builder ✅
  - Update: `backend/app/modules/knowledge/context_builder.py`
  - Add `_get_quality_context()` method:
    - Integrate with existing quality scores (Spec 008)
    - Fetch uncoded transactions count
    - Fetch reconciliation status
    - Identify GST coding warnings

**Checkpoint**: Can detect perspectives and build context for each ✅

---

## Phase 3: Multi-Perspective Orchestrator (MVP) 🎯

**Purpose**: Single LLM call with structured multi-perspective output

- [x] T008 Implement MultiPerspectiveOrchestrator ✅
  - Create: `backend/app/modules/agents/orchestrator.py`
  - Implement `MultiPerspectiveOrchestrator` class:
    ```python
    async def process_query(
        query: str,
        tenant_id: UUID,
        client_context: ClientContext | None,
    ) -> OrchestratorResponse
    ```
  - Flow:
    1. Detect perspectives needed
    2. Build unified context for all perspectives
    3. Construct multi-perspective prompt
    4. Single Claude call
    5. Parse attributed response
    6. Calculate confidence
    7. Check escalation thresholds

- [x] T009 Create multi-perspective prompt template ✅
  - Create: `backend/app/modules/agents/prompts.py`
  - System prompt explaining multi-perspective analysis
  - Dynamic prompt builder based on detected perspectives
  - Clear output format instructions:
    ```
    [Compliance] Your compliance analysis here...
    [Insight] Your trend analysis here...
    [Strategy] Your strategic recommendations here...
    ```
  - Include client context and RAG results

- [x] T010 Implement response parser ✅
  - Add to `backend/app/modules/agents/orchestrator.py`:
  - `_parse_response()` method to extract perspective sections
  - Handle cases where Claude doesn't follow format exactly
  - Extract confidence indicators from response

- [x] T011 Implement confidence scoring ✅
  - Add to `backend/app/modules/agents/orchestrator.py`:
  - `_calculate_confidence()` method:
    - Base score from RAG citation quality
    - Bonus for complete client data
    - Penalty for missing perspectives
    - Threshold checks (0.4 escalation, 0.6 review)

- [x] T012 Create agent API router ✅
  - Add to `backend/app/modules/agents/router.py`:
    - `POST /api/v1/agents/chat` endpoint (non-streaming first)
    - `POST /api/v1/agents/chat/stream` endpoint (SSE with thinking status)
  - Request: query, client_id (optional)
  - Response: content, perspectives_used, confidence, citations
  - Register router in `backend/app/main.py`

- [x] T013 Create agent dependencies ✅
  - Create: `backend/app/modules/agents/dependencies.py`
  - `get_orchestrator()` dependency
  - Wire up context builder, perspective detector, Claude client

**Checkpoint**: Multi-perspective queries working end-to-end via API ✅

---

## Phase 4: Escalation & Audit

**Purpose**: Flag low confidence and log decisions

- [x] T014 Implement escalation logic ✅
  - Update `backend/app/modules/agents/orchestrator.py`:
  - Add `_check_escalation()` method:
    - Confidence < 0.4 → mandatory escalation
    - Confidence 0.4-0.6 → flag for review
    - Complex keywords (trust, international, penalty) → escalate
  - Return escalation_required and escalation_reason

- [x] T015 Implement audit logging ✅
  - Create: `backend/app/modules/agents/audit.py`
  - `AgentAuditService` class:
    - `log_query()` - save to agent_queries table
    - Log: correlation_id, perspectives_used, confidence, escalation
    - Do NOT log query content (privacy) - uses hash instead
  - Integrate with orchestrator

- [x] T016 Add escalation endpoints ✅
  - Update `backend/app/modules/agents/router.py`:
  - `GET /api/v1/agents/escalations` - list pending
  - `GET /api/v1/agents/escalations/stats` - escalation statistics
  - `GET /api/v1/agents/escalations/{id}` - get single escalation
  - `POST /api/v1/agents/escalations/{id}/resolve` - mark resolved
  - `POST /api/v1/agents/escalations/{id}/dismiss` - dismiss escalation

**Checkpoint**: Escalations tracked and queryable ✅

---

## Phase 5: Frontend Integration

**Purpose**: Display multi-perspective responses in chat UI

- [x] T017 [P] Create agent types for frontend ✅
  - Create: `frontend/src/types/agents.ts`
  - `Perspective` enum
  - `PerspectiveResult` interface
  - `AgentResponse` interface with perspectives array
  - Helper functions: `parsePerspectiveSections()`, `getConfidenceLevel()`

- [x] T018 [P] Create agent API client ✅
  - Create: `frontend/src/lib/api/agents.ts`
  - `agentChat()` function
  - `agentChatStream()` function with SSE (yields structured events)
  - `listEscalations()`, `resolveEscalation()`, `dismissEscalation()` functions

- [x] T019 Update AssistantPage for multi-perspective ✅
  - Update: `frontend/src/app/(protected)/assistant/page.tsx`
  - Always use agent chat (replaced old knowledge chat)
  - Display perspective badges on response
  - Show confidence indicator
  - Added ThinkingIndicator with animated progress during processing

- [x] T020 Create PerspectiveBadges component ✅
  - Create: `frontend/src/components/assistant/PerspectiveBadges.tsx`
  - Display which perspectives contributed
  - Color-coded badges:
    - Compliance: Blue
    - Quality: Orange
    - Strategy: Green
    - Insight: Purple
  - ConfidenceIndicator component with progress bar
  - EscalationBanner component for review recommendations

- [x] T021 Style perspective sections in response ✅
  - Update: `frontend/src/app/(protected)/assistant/page.tsx` MessageBubble
  - Parse [Perspective] markers in response
  - Apply colored headers to each section
  - Expandable/collapsible perspective sections

**Checkpoint**: Frontend displays attributed responses ✅

---

## Phase 6: Polish & Testing

**Purpose**: Refinements and validation

- [x] T022 Prompt tuning ✅
  - Test with real accountant queries
  - Adjust perspective detection patterns
  - Tune output format instructions
  - Optimize for clarity and attribution

- [x] T023 Add confidence display ✅
  - Update: `frontend/src/app/(protected)/assistant/page.tsx`
  - Show confidence score (e.g., "High confidence" / "Review recommended")
  - Visual indicator (color bar) with percentage

- [x] T024 Handle edge cases ✅
  - No client selected → general knowledge mode (works)
  - Claude doesn't follow format → fallback parsing (handled)
  - Low confidence → show escalation banner
  - Error handling throughout

- [x] T025 Performance validation ✅
  - Added SSE streaming with thinking status messages for better UX
  - ThinkingIndicator shows progress during ~20s processing time
  - Token usage logged in audit table

---

## Phase FINAL: PR & Merge (REQUIRED)

- [x] TFINAL-1 Run all tests and linting ✅
  - Run: `cd backend && uv run pytest && uv run ruff check .`
  - Run: `cd frontend && npm run lint && npm run build`

- [x] TFINAL-2 Push and create PR ✅
  - Run: `git push -u origin feature/014-multi-agent-framework`
  - Create PR with summary of multi-perspective approach
  - PR #3: https://github.com/sreddy75/Clairo/pull/3

- [x] TFINAL-3 Merge to main ✅
  - Squash merge after approval
  - Delete feature branch

- [x] TFINAL-4 Update ROADMAP.md ✅
  - Mark Spec 014 as COMPLETE
  - Update current focus to Spec 015

---

## Dependencies

```
Phase 0 (Git) → Phase 1 (Setup) → Phase 2 (Detection) → Phase 3 (Orchestrator MVP)
                                                                    ↓
                                          Phase 4 (Escalation) ← Phase 3
                                                                    ↓
                                          Phase 5 (Frontend) ← Phase 3
                                                                    ↓
                                          Phase 6 (Polish) ← Phase 4 + 5
```

---

## Example: How It Works

**User asks**: "Should ACME Corp register for GST?"

1. **Perspective Detection** → [COMPLIANCE, INSIGHT, STRATEGY]

2. **Context Building**:
   - COMPLIANCE: GST threshold rules from Pinecone
   - INSIGHT: ACME revenue trend ($52K → $68K), projections
   - STRATEGY: Early registration pros/cons from Pinecone

3. **Single Prompt to Claude**:
   ```
   Analyze from these perspectives: Compliance, Insight, Strategy

   CLIENT: ACME Corp, not GST registered, $68K revenue
   TREND: Revenue growing 15% quarter-over-quarter

   KNOWLEDGE:
   [Compliance KB chunks...]
   [Strategy KB chunks...]

   Question: Should ACME Corp register for GST?

   Format your response with [Perspective] prefixes.
   ```

4. **Claude Response**:
   ```
   [Compliance] GST registration is required at $75K turnover...

   [Insight] ACME's revenue trajectory ($52K → $58K → $68K) projects
   reaching $75K threshold in approximately 2-3 months...

   [Strategy] Given the growth trajectory, early registration allows
   claiming input credits on current purchases ($4,200 GST paid)...
   ```

5. **Parsed Result**:
   - perspectives_used: ["compliance", "insight", "strategy"]
   - confidence: 0.82
   - escalation_required: false

---

## Notes

- Single LLM call = faster + cheaper than multiple agents
- Same user value (attributed perspectives)
- Can expand to true multi-agent if single call proves limiting
- Focus on prompt engineering for quality output
