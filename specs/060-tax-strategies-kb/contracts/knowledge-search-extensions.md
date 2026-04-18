# Knowledge Search Extensions — Contract

Two additive, backwards-compatible changes to the existing `KnowledgeSearchRequest` / `KnowledgeSearchFilters` schemas in `backend/app/modules/knowledge/schemas.py`. Existing callers that don't set the new fields continue to behave exactly as before (SC-004).

---

## 1. `KnowledgeSearchRequest` — new field

```python
class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    domain: str | None = Field(None)
    filters: KnowledgeSearchFilters | None = None
    limit: int = Field(default=10, ge=1, le=50)

    # NEW — opt-in. When None, the service resolves to the default namespace list
    # (backwards-compatible with current behaviour: compliance_knowledge only).
    namespaces: list[str] | None = Field(
        default=None,
        description=(
            "Explicit list of knowledge namespaces to search. "
            "Tax planning passes ['compliance_knowledge', 'tax_strategies']. "
            "When None, default is ['compliance_knowledge']."
        ),
    )
```

## 2. `KnowledgeSearchFilters` — new structured-eligibility fields

```python
class KnowledgeSearchFilters(BaseModel):
    # Existing fields — unchanged.
    entity_types: list[str] | None = None
    source_types: list[str] | None = None
    fy_applicable: str | None = None
    exclude_superseded: bool = True

    # NEW — structured eligibility pre-filter (applied at Pinecone metadata layer).
    # All optional. Absent = unconstrained on that axis.
    income_band: int | None = Field(
        None, description="Client income in AUD; strategy included when income_band_min <= v <= income_band_max (NULL bounds = unbounded)."
    )
    turnover_band: int | None = Field(
        None, description="Client turnover in AUD; same inclusion logic as income_band."
    )
    age: int | None = Field(None, description="Client age; strategy included when age_min <= v <= age_max.")
    industry_codes: list[str] | None = Field(
        None, description="Client industry codes; matched against strategy industry_triggers via $in."
    )
    tenant_id: str | None = Field(
        None, description="Tenant context; used to union {\"platform\", tenant_id} on the filter."
    )
```

### 2.1 Filter-over-restriction fallback (FR-017)

If the structured pre-filter would return zero candidates, `HybridSearchEngine` MUST re-run the semantic search **without** the structured eligibility clauses (but keeping `tenant_id`, `exclude_superseded`, and `_collection`). This prevents empty-result dead-ends on sparsely-tagged strategies.

Behavior is emitted as a log line with level `INFO` and tag `retrieval.fallback.unfiltered` so Phase 2 tuning can measure how often it trips.

---

## 3. Response shape — additive metadata on `KnowledgeSearchResultSchema`

```python
class KnowledgeSearchResultSchema(BaseModel):
    chunk_id: str
    title: str | None = None
    text: str
    source_url: str | None = None
    source_type: str
    section_ref: str | None = None
    ruling_number: str | None = None
    effective_date: str | None = None
    is_superseded: bool = False
    relevance_score: float
    content_type: str | None = None

    # NEW — populated only when result is a tax strategy chunk; otherwise None.
    tax_strategy_id: str | None = None         # e.g. "CLR-241"
    strategy_name: str | None = None           # e.g. "Change PSI to PSB"
    categories: list[str] | None = None
    chunk_section: str | None = None           # "implementation" | "explanation"
```

Non-strategy results leave these fields as `None` — backwards-compatible with existing consumers.

---

## 4. LLM retrieval envelope (tax planning)

When `tax_planning` receives a retrieval result with `content_type == "tax_strategy"`, the service wraps it in the `<strategy>` XML envelope before passing to the LLM:

```xml
<strategy id="CLR-241" name="Change PSI to PSB"
          categories="Business"
          ato_sources="ITAA 1997 Div 87, TR 2001/8"
          case_refs="">
  <implementation>
    1. Advertise the business to the general public ...
  </implementation>
  <explanation>
    Personal services income (PSI) is mainly from ...
  </explanation>
</strategy>
```

The envelope is built from the parent `TaxStrategy` row (fetched once per query after chunk-level dedupe), not from the chunk text — the LLM always sees the full, current prose.

System prompt addition:

> When drawing on a `<strategy>` element, cite inline as `[CLR-XXX: Name]`
> using the exact strategy identifier and name from the element's attributes.
> Include ATO source references in parentheses for any threshold or test.
> Never assert a figure, threshold, or test that is not present in the
> provided strategies or compliance sources.
