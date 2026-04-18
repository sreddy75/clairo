# Quickstart: Verifying the Modeller Redesign

**Feature**: Tax Planning Modeller — Architectural Redesign
**Audience**: Engineers landing or reviewing the implementation

---

## Prerequisites

- Docker Compose stack running (`docker-compose up -d`)
- `uv` installed (backend Python tooling)
- A tax plan exists in the local DB with applicable strategies (use the golden-dataset fixture or any existing KR8 IT test plan)

---

## 1. Unit tests (no Docker required)

Fast, deterministic, mocked Anthropic client.

```sh
cd backend && uv run pytest tests/modules/tax_planning/agents/test_modeller.py -v
```

**Expect**: 5 tests pass.

| Test | What it proves |
|------|----------------|
| `test_drops_unknown_strategy_id` | An LLM-invented `strategy_id` is dropped at validation. FR-001. |
| `test_dedupes_duplicate_strategy_ids` | Duplicate `strategy_id` entries collapse to the first. FR-002. |
| `test_truncates_to_input_count` | Returned scenarios never exceed input strategy count. FR-003. |
| `test_combined_total_equals_sum_of_scenarios` | `combined.total_tax_saving == sum(scenarios.tax_saving)`. FR-004. |
| `test_group_model_scenario_excluded_from_combined` | Spec 059 group-model behaviour preserved. NFR-001. |

Previously-existing tests for the three removed filter layers are expected to be deleted.

---

## 2. Static check — legacy filters are gone

```sh
grep -nE "_META_KEYWORDS|max_tool_calls|1\.1 \*" backend/app/modules/tax_planning/agents/modeller.py
```

**Expect**: no matches; grep exits 1. Satisfies SC-004.

---

## 3. End-to-end: live Anthropic call via Celery

The modeller runs inside the Celery worker, not the FastAPI process. You must restart celery after changing modeller code because Python caches imports at process start (this burned us during investigation — see HANDOFF.md).

```sh
docker restart clairo-celery-worker
# Wait for health
until docker ps --format "{{.Names}}\t{{.Status}}" | grep -q "clairo-celery-worker.*healthy"; do sleep 2; done
```

Open the app → any client's tax planning tab → click **Re-generate Analysis**. In another terminal:

```sh
docker logs -f clairo-celery-worker 2>&1 | grep -iE "modeller|tax_saving|streaming"
```

### Expected logs (happy path)

```
Modeller: produced N scenarios (from N validated modifications), combined saving=$X,XXX
```

where `N ≤ number of applicable strategies` and `$X,XXX` equals the sum of per-strategy savings shown in the UI.

### Expected NOT to appear

- `Streaming is required for operations that may take longer than 10 minutes` (FR-007)
- `Modeller: rejecting tool call` (deleted Layer 1)
- `Modeller: name-filter stripped` (deleted Layer 2)
- `Modeller: structural-filter stripped` (deleted Layer 3)

### May appear (informational only)

- `Modeller: dropping unknown strategy_id=<value>` — benign; the LLM attempted to invent a strategy and we dropped it.
- `Modeller: dropping duplicate strategy_id=<value>` — benign; dedupe fired.
- `Modeller: no valid modifications returned; producing empty scenario list` — analysis succeeds with an empty list.

---

## 4. UI verification

On the Analysis tab:

- **Total Tax Saving** headline at top must equal the arithmetic sum of the individual strategy savings shown below. Satisfies Story 1.
- Analysis status must NOT be "Needs Review" for reasons attributable to combined-total inconsistency. Satisfies Story 4. (Other quality issues may still flag — reviewer continues to run on substance.)
- Strategies Recommended count must equal the number of per-strategy cards shown. No phantom combined/meta entry.

Run this 3 times across 3 distinct clients to confirm stability.

---

## 5. Smoke: no regression in sibling agents

```sh
cd backend && uv run pytest tests/modules/tax_planning/ -v
```

All existing tests for advisor, reviewer, scanner, profiler, orchestrator should remain green. This spec does not touch them.

---

## Rollback

If a regression surfaces post-merge:

```sh
git revert <commit-sha-of-this-feature>
docker restart clairo-celery-worker
```

The previous code path (the failing three-layer-filter code) will be restored. That code does not produce correct results either, but it is the known-prior state. The analysis will either fail with "Streaming required" or produce doubled totals — same as before this feature, no worse.

Preferred recovery: roll forward with a fix. This spec is load-bearing for UAT sessions.

---

## Definition of done

- [ ] All 5 unit tests pass
- [ ] Grep for legacy filter markers returns zero matches
- [ ] Live run produces a headline figure equal to the per-strategy sum on 3 consecutive runs
- [ ] No "Streaming is required" errors in worker logs over the verification window
- [ ] Reviewer no longer flags combined-total inconsistency
- [ ] `modeller.run()` return signature `(list[dict], dict)` unchanged (verified by orchestrator test remaining green)
- [ ] HANDOFF.md section "Active Problem: Meta-Scenario Double-Counting" updated to reference this spec as the resolution
