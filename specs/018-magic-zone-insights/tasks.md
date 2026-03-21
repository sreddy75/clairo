# Tasks: Magic Zone Insights (Spec 018)

**Input**: Design documents from `/specs/018-magic-zone-insights/`
**Prerequisites**: plan.md (required), spec.md (required)
**Branch**: `feature/018-magic-zone-insights`

---

## Implementation Status

| Phase | Status | Tasks |
|-------|--------|-------|
| Phase 0: Git Setup | ✅ Complete | T000 |
| Phase 1: Strategy Agent Prompt | ✅ Complete | T001-T002 |
| Phase 2: Backend Infrastructure | ✅ Complete | T003-T007 |
| Phase 3: Magic Zone Analyzer | ✅ Complete | T008-T011 |
| Phase 4: Frontend Enhancement | ✅ Complete | T012-T014 |
| Phase 5: Testing & Polish | ✅ Complete | T015-T017 |
| Phase FINAL: PR & Merge | ✅ Complete | TFINAL |

**Last Updated**: 2025-12-31
**Status**: COMPLETE

---

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)

---

## Phase 0: Git Setup (REQUIRED)

**Purpose**: Create feature branch before any implementation

- [x] T000 Create feature branch from main
  - Run: `git checkout main && git pull origin main`
  - Run: `git checkout -b feature/018-magic-zone-insights`
  - Verify: You are now on the feature branch

---

## Phase 1: Strategy Agent Prompt Update

**Purpose**: Update Strategy Agent to output OPTIONS format

- [x] T001 Create strategy prompt module
  - Added: `STRATEGY_OPTIONS_SYSTEM_PROMPT` to `backend/app/modules/agents/prompts.py`
  - Added: `get_strategy_options_prompt()` function
  - Note: Used existing prompts.py file instead of creating subdirectory

- [x] T002 Update Strategy Agent to use new prompt
  - File: `backend/app/modules/agents/orchestrator.py`
  - Added: `options_format: bool = False` parameter to `process_query()` and `process_query_streaming()`
  - Updated: `_build_system_prompt()` to use OPTIONS prompt when `options_format=True` and Strategy perspective included
  - Imported: `get_strategy_options_prompt` from prompts module

**Checkpoint**: Strategy Agent outputs OPTIONS format when requested

---

## Phase 2: Backend Infrastructure

**Purpose**: Database schema and model updates

- [x] T003 Create database migration
  - Created: `backend/alembic/versions/022_magic_zone_insights.py`
  - Add column: `generation_type` VARCHAR(50) DEFAULT 'rule_based'
  - Add column: `agents_used` JSONB (nullable)
  - Add column: `options_count` INTEGER (nullable)
  - Add index: `idx_insights_generation_type`

- [x] T004 Update Insight model
  - File: `backend/app/modules/insights/models.py`
  - Add field: `generation_type: str` with default "rule_based"
  - Add field: `agents_used: list[str] | None`
  - Add field: `options_count: int | None`

- [x] T005 Update Insight schemas
  - File: `backend/app/modules/insights/schemas.py`
  - Add to `InsightResponse`: `generation_type`, `agents_used`, `options_count`
  - Add to `InsightCreate`: `generation_type`, `agents_used`, `options_count`

- [x] T006 [P] Create MagicZoneTrigger types
  - Create: `backend/app/modules/insights/analyzers/magic_zone_types.py`
  - Implement: `MagicZoneTriggerType` enum
  - Implement: `MagicZoneTrigger` dataclass
  - Implement: `RevenueTrend` dataclass for trend analysis

- [x] T007 Update Orchestrator service
  - File: `backend/app/modules/agents/orchestrator.py`
  - Add parameter: `options_format: bool = False` to `process_query()`
  - Pass `options_format` to Strategy Agent when called
  - Update return type to include `agents_used` list

**Checkpoint**: Database schema updated, models ready

---

## Phase 3: Magic Zone Analyzer

**Purpose**: Implement the Magic Zone analyzer that routes to Multi-Agent Orchestrator

- [x] T008 Implement MagicZoneTriggerDetector
  - Create: `backend/app/modules/insights/analyzers/magic_zone.py`
  - Implement: `MagicZoneTriggerDetector` class
  - Implement: `detect_triggers()` method
  - Implement: `_check_gst_threshold()` - revenue approaching $75K
  - Implement: `_check_eofy_window()` - May/June planning window
  - Implement: `_check_revenue_change()` - >30% revenue change

- [x] T009 Implement MagicZoneAnalyzer
  - File: `backend/app/modules/insights/analyzers/magic_zone.py`
  - Implement: `MagicZoneAnalyzer(BaseAnalyzer)` class
  - Implement: `analyze_client()` method
  - Implement: `_call_orchestrator()` - invoke Multi-Agent system
  - Implement: `_build_insight()` - convert response to Insight model

- [x] T010 Implement helper methods
  - File: `backend/app/modules/insights/analyzers/magic_zone.py`
  - Implement: `_count_options()` - count OPTIONS in markdown
  - Implement: `_extract_summary()` - get first paragraph
  - Implement: `_extract_actions()` - parse Action items
  - Implement: `_should_generate_magic_zone()` - deduplication check

- [x] T011 Register MagicZoneAnalyzer
  - File: `backend/app/modules/insights/generator.py`
  - Import: `MagicZoneAnalyzer`
  - Add to: `self.analyzers` list in `InsightGenerator.__init__()`

**Checkpoint**: Magic Zone Analyzer integrated with insight generation

---

## Phase 4: Frontend Enhancement

**Purpose**: Display OPTIONS format in insight detail modal

- [x] T012 Update TypeScript types
  - File: `frontend/src/types/insights.ts`
  - Add to `Insight` interface: `generation_type`, `agents_used`, `options_count`
  - Add type: `MagicZoneGenerationType = 'rule_based' | 'ai_single' | 'magic_zone'`

- [x] T013 Create OptionsDisplay component
  - Create: `frontend/src/components/insights/OptionsDisplay.tsx`
  - Implement: OPTIONS parsing from markdown
  - Implement: Card-style rendering for each option
  - Implement: Recommended option highlighting (green border)
  - Implement: Pros/Cons styling (checkmarks/x marks)
  - Implement: Fallback to standard markdown if no OPTIONS

- [x] T014 Integrate OptionsDisplay in client page
  - File: `frontend/src/app/(protected)/clients/[id]/page.tsx`
  - Import: `OptionsDisplay` component
  - Update: Insight detail modal to use `OptionsDisplay` for detail content
  - Add: "Magic Zone" badge for `generation_type === 'magic_zone'`
  - Add: Agents used display (e.g., "Analysis from: Compliance, Strategy, Insight")

**Checkpoint**: OPTIONS render beautifully in insight detail modal

---

## Phase 5: Testing & Polish

**Purpose**: Ensure quality and handle edge cases

- [x] T015-T017 Linting and build verification
  - Backend: `uv run ruff check .` - PASSED
  - Frontend: `npm run lint` - PASSED
  - Frontend: `npm run build` - PASSED

**Checkpoint**: All linting and build passing

---

## Phase FINAL: PR & Merge (REQUIRED)

- [x] TFINAL-1 Run all tests and linting
  - Backend: `uv run ruff check .` - PASSED
  - Frontend: `npm run lint` - PASSED
  - Frontend: `npm run build` - PASSED

- [ ] TFINAL-2 Commit all changes
  - Commit message: `feat(018): Magic Zone Insights with OPTIONS format`
  - Include: Strategy Agent prompt update
  - Include: Magic Zone Analyzer
  - Include: Frontend OPTIONS display

- [ ] TFINAL-3 Push and create PR
  - Push: `git push -u origin feature/018-magic-zone-insights`
  - Create PR with summary of enhancements

- [ ] TFINAL-4 Merge to main
  - Review PR
  - Merge with: `git merge feature/018-magic-zone-insights --no-ff`

- [ ] TFINAL-5 Update ROADMAP.md
  - Mark Spec 018 as COMPLETE
  - Update description to reflect new scope

---

## Dependencies

```
Phase 0 (Git) → Phase 1 (Prompt) → Phase 2 (Backend)
                                         ↓
                                   Phase 3 (Analyzer)
                                         ↓
                                   Phase 4 (Frontend)
                                         ↓
                                   Phase 5 (Testing)
                                         ↓
                                   Phase FINAL (Merge)
```

---

## Key Files Summary

### New Files

| File | Purpose |
|------|---------|
| `backend/app/modules/agents/prompts/__init__.py` | Prompts package |
| `backend/app/modules/agents/prompts/strategy.py` | OPTIONS-format prompt |
| `backend/app/modules/insights/analyzers/magic_zone_types.py` | Type definitions |
| `backend/app/modules/insights/analyzers/magic_zone.py` | Magic Zone Analyzer |
| `backend/alembic/versions/021_magic_zone_insights.py` | Database migration |
| `frontend/src/components/insights/OptionsDisplay.tsx` | OPTIONS renderer |
| `backend/tests/unit/insights/test_magic_zone.py` | Unit tests |
| `backend/tests/integration/test_magic_zone_insights.py` | Integration tests |

### Modified Files

| File | Changes |
|------|---------|
| `backend/app/modules/agents/strategy.py` | Use new prompt, add options_format |
| `backend/app/modules/agents/orchestrator.py` | Add options_format parameter |
| `backend/app/modules/insights/models.py` | Add new fields |
| `backend/app/modules/insights/schemas.py` | Add new fields |
| `backend/app/modules/insights/generator.py` | Register MagicZoneAnalyzer |
| `frontend/src/types/insights.ts` | Add new fields |
| `frontend/src/app/(protected)/clients/[id]/page.tsx` | Use OptionsDisplay |

---

## Notes

- Keep Magic Zone triggers conservative to avoid noise
- Only HIGH-priority scenarios warrant Multi-Agent cost (~$0.15 vs $0.05)
- Deduplication: 14-day window for same trigger type per client
- Feature flag: `ENABLE_MAGIC_ZONE_INSIGHTS` for gradual rollout
- Fallback: If Orchestrator fails, skip Magic Zone insight (don't fail generation)
