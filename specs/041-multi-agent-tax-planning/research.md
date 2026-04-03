# Research: Multi-Agent Tax Planning Pipeline

**Date**: 2026-04-03  
**Feature**: 041-multi-agent-tax-planning

## Decision 1: Agent Execution Model

**Decision**: Sequential Celery task with SSE progress via Redis pub/sub

**Rationale**: The 5 agents must run sequentially (each depends on the previous output). Running as a Celery task gives us: async execution (30-60s), retry on failure, progress tracking via `task.update_state()`, and existing infrastructure (Redis broker, worker pool). SSE progress is delivered by polling the Celery task state from a streaming endpoint, matching the existing pattern in `reports.py` and `knowledge.py`.

**Alternatives considered**:
- Direct async in request handler → too slow (30-60s blocks the request)
- Separate Celery task per agent → over-engineering, adds coordination complexity
- WebSocket → no existing pattern, SSE already proven in the codebase

## Decision 2: Agent Implementation Pattern

**Decision**: Each agent is a stateless async function that takes inputs and returns outputs. Agents call Claude via the Anthropic SDK. Agents that need tax calculations use the existing `calculate_tax_position` function via Claude's tool-use mechanism (same pattern as `TaxPlanningAgent._execute_tool()`).

**Rationale**: The existing `TaxPlanningAgent` proves this pattern works. Stateless functions are testable, composable, and replaceable. Tool-use ensures numbers come from the real calculator, never hallucinated.

**Alternatives considered**:
- LangChain/LangGraph agent framework → adds dependency, existing pattern is simpler and proven
- Custom agent loop with reflection → over-engineering for Phase 1
- Direct function calls without LLM → loses the intelligence of strategy evaluation

## Decision 3: Data Storage

**Decision**: New `tax_plan_analyses` table with JSONB columns for structured agent outputs. Linked to `tax_plans` via FK. Versioned for re-generation support.

**Rationale**: JSONB gives flexibility for each agent's output schema to evolve without migrations. The `entities[]` array for Phase 2 multi-entity support is just a JSONB field with a single-item array in Phase 1. Versioning via `version` integer + `is_current` flag supports re-generation with history.

**Alternatives considered**:
- Separate tables per agent output → too many tables for data that's always accessed together
- Document store (MongoDB) → not in our stack, PostgreSQL JSONB is sufficient
- Storing in the existing `tax_plans` table → too much data, mixes concerns

## Decision 4: Client Portal Sharing

**Decision**: The `tax_plan_analyses` table has `shared_at` and `client_summary` fields. The portal module queries this table by `connection_id` (same pattern as `portal/classification_router.py`). Implementation items are a separate `implementation_items` table for checklist tracking.

**Rationale**: Follows the existing portal pattern — no data duplication, the portal is a read-only scoped view into tenant data. Magic link auth + `connection_id` filtering provides isolation.

**Alternatives considered**:
- Copying data to a portal-specific table → violates DRY, creates sync issues
- Embedding checklist in the analysis JSONB → harder to track individual item completion timestamps

## Decision 5: Progress Reporting

**Decision**: Celery `update_state(state="PROGRESS", meta={...})` with a polling SSE endpoint. The meta includes `stage` (string), `stage_number` (int), `total_stages` (int), `message` (string), and `detail` (optional dict).

**Rationale**: Celery's built-in state tracking is simple and proven. The existing `knowledge.py` tasks use this pattern. A thin SSE endpoint polls the Celery task result and streams events.

**Alternatives considered**:
- Redis pub/sub for real-time progress → more complex, Celery state is sufficient for 5 stages
- WebSocket → no existing pattern
- Long polling → more complex client code

## Decision 6: Reuse of Existing Components

**Decision**: Reuse these existing components directly:

| Component | Source | How |
|-----------|--------|-----|
| Tax calculator | `tax_calculator.py:calculate_tax_position()` | Called by Modeller agent via tool-use |
| CALCULATE_TAX_TOOL | `prompts.py:52-115` | Shared tool definition for Claude |
| `_execute_tool()` | `agent.py:268-367` | Extracted to shared utility for Modeller agent |
| RAG retrieval | `service.py:_retrieve_tax_knowledge()` | Called by Scanner agent for compliance citations |
| Rate config loading | `service.py:_load_rate_configs()` | Shared across all agents that need tax rates |
| Portal auth | `portal/auth/dependencies.py` | Reused for client summary access |

**Rationale**: These are battle-tested, working components. No need to rewrite.

## Decision 7: Phase 2 Extension Points

**Decision**: Design these nullable JSONB fields into the data model now:

- `entities` (JSONB array) — Phase 1: `[{single_entity}]`, Phase 2: multiple
- `group_structure` (JSONB) — Phase 1: null, Phase 2: trust → beneficiaries
- `distribution_plan` (JSONB) — Phase 1: null, Phase 2: allocation optimization
- `entity_summaries` (JSONB array) — Phase 1: null, Phase 2: per-beneficiary

**Rationale**: Adding nullable JSONB columns costs nothing in Phase 1 but avoids schema migrations in Phase 2. The agent interfaces accept optional parameters that Phase 2 will populate.
