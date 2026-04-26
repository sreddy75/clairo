"""Unit tests for tax_strategies LLM prompt builders and response parsers.

The real Anthropic call is skipped — we test the deterministic pieces
(prompt assembly + response parsing) so the Celery tasks stay thin glue.
"""

from __future__ import annotations

import pytest

from app.modules.tax_strategies.llm import (
    DraftParseError,
    build_draft_user_prompt,
    build_enrich_user_prompt,
    parse_draft_response,
    parse_enrich_response,
)

# ----------------------------------------------------------------------
# Prompt builders
# ----------------------------------------------------------------------


def test_build_draft_user_prompt_includes_all_inputs() -> None:
    prompt = build_draft_user_prompt(
        name="Concessional super contributions",
        categories=["SMSF", "Employees"],
        ato_sources=["ITAA 1997 s 290-25", "TR 2010/1"],
    )
    assert "Concessional super contributions" in prompt
    assert "SMSF, Employees" in prompt
    assert "- ITAA 1997 s 290-25" in prompt
    assert "- TR 2010/1" in prompt


def test_build_draft_user_prompt_handles_no_sources() -> None:
    prompt = build_draft_user_prompt(name="Something", categories=["Business"], ato_sources=[])
    # Don't assert on exact wording — just that the builder doesn't crash
    # and marks the absence clearly.
    assert "Something" in prompt
    assert "none" in prompt.lower()


def test_build_enrich_user_prompt_embeds_drafted_content() -> None:
    prompt = build_enrich_user_prompt(
        name="Change PSI to PSB",
        categories=["Business_structures"],
        implementation_text="1. Review contracts.\n2. Apply results test.",
        explanation_text="Under s 87-15, a PSB is...",
    )
    assert "Change PSI to PSB" in prompt
    assert "Business_structures" in prompt
    assert "Review contracts" in prompt
    assert "Under s 87-15" in prompt


# ----------------------------------------------------------------------
# Draft parser
# ----------------------------------------------------------------------


def test_parse_draft_response_happy_path() -> None:
    text = """## Implementation
1. Review the client's concessional cap for the year.
2. Confirm timing of contribution before 30 June.
3. Lodge a valid notice of intent.

## Explanation
Concessional contributions are capped at $27,500 per person (ITAA 1997 Div 292). A member can claim a personal deduction where a timely notice of intent is lodged (s 290-170)."""
    out = parse_draft_response(text)
    assert out.implementation_text.startswith("1. Review")
    assert "notice of intent" in out.implementation_text
    assert "Concessional contributions are capped" in out.explanation_text
    assert "s 290-170" in out.explanation_text


def test_parse_draft_response_tolerates_trailing_heading_words() -> None:
    # Claude often appends "advice" / "advice:" to the heading.
    text = """## Implementation advice
1. Step one.
2. Step two.

## Strategy explanation
Prose goes here in some detail about the thresholds that apply."""
    out = parse_draft_response(text)
    assert "Step one" in out.implementation_text
    assert "Prose goes here" in out.explanation_text


def test_parse_draft_response_strips_code_fences() -> None:
    text = """```markdown
## Implementation
1. Do the thing.

## Explanation
Some prose.
```"""
    out = parse_draft_response(text)
    assert "Do the thing" in out.implementation_text
    assert "Some prose" in out.explanation_text


def test_parse_draft_response_raises_when_section_missing() -> None:
    text = "## Implementation\n1. One step.\n\n(no explanation)"
    with pytest.raises(DraftParseError):
        parse_draft_response(text)


def test_parse_draft_response_raises_on_empty() -> None:
    with pytest.raises(DraftParseError):
        parse_draft_response("")


# ----------------------------------------------------------------------
# Enrich parser
# ----------------------------------------------------------------------


def test_parse_enrich_response_clean_json() -> None:
    text = """{
  "entity_types": ["sole_trader", "individual"],
  "income_band_min": 100000,
  "income_band_max": 250000,
  "turnover_band_min": null,
  "turnover_band_max": null,
  "age_min": null,
  "age_max": 74,
  "industry_triggers": ["professional_services"],
  "financial_impact_type": ["deduction", "timing"],
  "keywords": ["super", "concessional", "cap"]
}"""
    out = parse_enrich_response(text)
    assert out["entity_types"] == ["sole_trader", "individual"]
    assert out["income_band_min"] == 100000
    assert out["income_band_max"] == 250000
    assert out["age_max"] == 74
    assert out["age_min"] is None
    assert out["financial_impact_type"] == ["deduction", "timing"]
    assert out["keywords"] == ["super", "concessional", "cap"]


def test_parse_enrich_response_strips_code_fences() -> None:
    text = '```json\n{"entity_types": ["company"], "keywords": ["x"]}\n```'
    out = parse_enrich_response(text)
    assert out["entity_types"] == ["company"]
    assert out["keywords"] == ["x"]


def test_parse_enrich_response_filters_unknown_entity_types() -> None:
    text = '{"entity_types": ["sole_trader", "unicorn", "smsf"], "keywords": []}'
    out = parse_enrich_response(text)
    assert out["entity_types"] == ["sole_trader", "smsf"]


def test_parse_enrich_response_filters_unknown_impact_types() -> None:
    text = '{"financial_impact_type": ["deduction", "magic", "offset"], "keywords": []}'
    out = parse_enrich_response(text)
    assert out["financial_impact_type"] == ["deduction", "offset"]


def test_parse_enrich_response_coerces_float_integers() -> None:
    text = '{"income_band_min": 100000.0, "age_max": 74.5}'
    out = parse_enrich_response(text)
    assert out["income_band_min"] == 100000
    # Non-integer floats discarded (architecture §16 — default null on uncertainty).
    assert out["age_max"] is None


def test_parse_enrich_response_defaults_on_malformed_json() -> None:
    out = parse_enrich_response("not json at all")
    assert out["entity_types"] == []
    assert out["keywords"] == []
    assert out["income_band_min"] is None
    assert out["age_max"] is None


def test_parse_enrich_response_defaults_when_top_level_is_list() -> None:
    out = parse_enrich_response("[1, 2, 3]")
    assert out["entity_types"] == []
    assert out["keywords"] == []


def test_parse_enrich_response_dedupes_and_lowercases() -> None:
    text = '{"keywords": ["Super", "SUPER", " concessional ", "concessional"]}'
    out = parse_enrich_response(text)
    assert out["keywords"] == ["super", "concessional"]


def test_parse_enrich_response_ignores_booleans_as_ints() -> None:
    # Pydantic/JSON treats bool as int; guard against a true value sneaking
    # into a numeric field.
    text = '{"income_band_min": true, "age_max": false}'
    out = parse_enrich_response(text)
    assert out["income_band_min"] is None
    assert out["age_max"] is None
