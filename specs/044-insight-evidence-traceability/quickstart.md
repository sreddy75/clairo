# Quickstart: Platform-Wide Evidence & Traceability

**Feature**: 044-insight-evidence-traceability
**Date**: 2026-02-24

---

## Overview

This feature adds evidence traceability to AI-generated content across the Clairo platform. It is delivered in 3 phases:

- **P1**: Evidence in Insight OPTIONS + Data Snapshot Preservation + Hide Confidence Scores
- **P2**: Agent Chat Citations + Data Freshness Indicators + Threshold Transparency
- **P3**: Confidence Score Reform + Safe AI Content Export + Mock Data Safety

## Prerequisites

- Backend running (`uv run uvicorn app.main:app --reload`)
- Frontend running (`npm run dev`)
- PostgreSQL with existing `insights` table (has `data_snapshot` JSONB column)
- At least one Xero-connected client with synced financial data
- Redis running (for Celery background tasks)

## P1 Quick Verification

### 1. Backend Changes

**Files modified** (P1):
- `backend/app/modules/insights/schemas.py` — Add `data_snapshot` to `InsightResponse`
- `backend/app/modules/insights/service.py` — Include `data_snapshot` in `_to_response()`
- `backend/app/modules/insights/router.py` — Capture context in expand endpoint
- `backend/app/modules/agents/prompts.py` — Add `**Evidence:**` to OPTIONS template
- `backend/app/modules/agents/orchestrator.py` — Return structured context alongside response
- `backend/app/modules/insights/analyzers/ai_analyzer.py` — Store real context in data_snapshot
- `backend/app/modules/insights/evidence.py` — New: evidence extraction + snapshot builder

**No database migration required** — `data_snapshot` column already exists.

### 2. Test Evidence Flow

```bash
# Run backend tests
cd backend && uv run pytest tests/ -k "evidence or snapshot" -v

# Verify InsightResponse includes data_snapshot
curl -s http://localhost:8000/api/v1/insights/{insight_id} \
  -H "Authorization: Bearer $TOKEN" | jq '.data_snapshot'

# Expand an insight and verify evidence
curl -s -X POST http://localhost:8000/api/v1/insights/{insight_id}/expand \
  -H "Authorization: Bearer $TOKEN" | jq '.data_snapshot.evidence_items'
```

### 3. Frontend Changes

**Files modified** (P1):
- `frontend/src/types/insights.ts` — Add `data_snapshot` to `Insight` interface
- `frontend/src/components/insights/OptionsDisplay.tsx` — Add evidence section to OptionCard
- `frontend/src/components/insights/EvidenceSection.tsx` — New: collapsible evidence display
- `frontend/src/components/insights/InsightDetailPanel.tsx` — Hide confidence display

### 4. Verify Frontend

1. Navigate to a client → Insights tab
2. Click "Expand Analysis" on any insight
3. Each option card should show "X data points" indicator (collapsed)
4. Click the indicator to expand evidence items
5. Each evidence item shows: source, period, metric, value
6. Confidence score should NOT be visible

## P2 Quick Verification

### Additional Backend Changes
- `backend/app/modules/agents/prompts.py` — Add citation instructions to orchestrator prompt
- `backend/app/modules/insights/thresholds.py` — New: threshold registry
- `backend/app/modules/insights/router.py` — New: `GET /api/v1/platform/thresholds` endpoint

### Additional Frontend Changes
- `frontend/src/components/insights/DataFreshnessIndicator.tsx` — New: "Data as of" badge
- `frontend/src/components/insights/ThresholdTooltip.tsx` — New: threshold explanation tooltips
- Quality score cards, variance badges, risk labels — Add tooltip triggers

### Verify
1. Ask the AI assistant a client question → response should include inline citations
2. Select a client with stale data → AI response should show "Stale data" warning
3. Hover over a quality score badge → tooltip shows dimension weights
4. Hover over a variance severity badge → tooltip shows threshold rules

## Architecture Notes

### Evidence Extraction Flow (P1)
```
1. User clicks "Expand Analysis"
2. router.py calls orchestrator.process_query()
3. orchestrator builds client_context (structured data)
4. orchestrator builds perspective_contexts (structured data)
5. orchestrator flattens to text prompt → sends to Claude
6. Claude returns OPTIONS text with inline evidence
7. router.py calls build_evidence_snapshot(client_context, perspective_contexts)
   → Returns structured EvidenceItem[] + trimmed context (≤50KB)
8. router.py stores snapshot in insight.data_snapshot
9. InsightResponse returns data_snapshot to frontend
10. OptionsDisplay renders evidence from data_snapshot.evidence_items
```

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Evidence source | Backend-extracted, not AI-parsed | Reliability — structured data guaranteed |
| Display | Collapsible, collapsed by default | Non-intrusive UX |
| Snapshot size | 50KB cap with trim strategy | Storage efficiency |
| Confidence scores | Hidden until P3 | Meaningless scores worse than no scores |
| Staleness threshold | Fixed 7 days | Aligned with weekly review cycles |
| Threshold info | Tooltips on existing badges | Minimal UI disruption |
