"""Anthropic LLM helpers for the tax strategies authoring pipeline (Spec 060 T028).

Two stages call out here: `draft_strategy` and `enrich_strategy`. Each has a
prompt builder (deterministic string assembly) + a response parser (tolerant
of the common variations Claude produces). Both are pure, so the Celery
tasks remain thin glue and the interesting logic stays unit-testable.

The actual Anthropic call is behind `_acall_anthropic` which reads from
`settings.anthropic`. Tests monkeypatch that entry point with a fake that
returns fixture text — no network in unit tests.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

import anthropic

from app.config import get_settings

logger = logging.getLogger(__name__)


# Architecture §10.3 — the "quality floor" drafting prompt. Output format is
# made explicit with section headings so the parser is deterministic.
DRAFT_SYSTEM_PROMPT = """You are writing a single-page tax planning strategy for Australian accountants. The strategy must be factually correct against the provided ATO primary sources, practically actionable, and legally precise on thresholds and tests. Do not invent content not supported by the sources.

Output format — exactly two sections, with these exact headings and nothing else:

## Implementation
1. <imperative step>
2. <imperative step>
...

## Explanation
<250-500 words of prose. Preserve every threshold, percentage, test, date verbatim from the sources. Where you rely on a specific ATO source, cite it inline in parentheses, e.g. "(ITAA 1997 s 290-25)".>

Constraints:
- Implementation: 4 to 8 numbered, imperative steps.
- Do not include an indicative dollar figure, marketing language, or brand names.
- Do not include a preamble, disclaimer, or signoff outside the two sections."""


# Eligibility extraction — strict JSON, nullable fields for anything
# ambiguous. Defaults to null/empty on uncertainty per architecture §16
# mitigations.
ENRICH_SYSTEM_PROMPT = """You extract structured eligibility metadata from Australian tax planning strategy drafts. Read the strategy carefully and return a single JSON object with exactly these fields:

{
  "entity_types": [],                  // subset of ["sole_trader","partnership","company","trust","smsf","individual"]
  "income_band_min": null,             // integer AUD or null
  "income_band_max": null,             // integer AUD or null
  "turnover_band_min": null,           // integer AUD or null
  "turnover_band_max": null,           // integer AUD or null
  "age_min": null,                     // integer years or null
  "age_max": null,                     // integer years or null
  "industry_triggers": [],             // short lowercase tags (e.g. ["professional_services","construction"])
  "financial_impact_type": [],         // subset of ["deduction","concession","offset","timing","structure","rebate","exemption"]
  "keywords": []                       // 5-15 lowercase keywords an accountant might search
}

Rules:
- If a field is ambiguous, unstated, or you are not confident, use null (for scalars) or [] (for arrays). Do NOT guess.
- entity_types, financial_impact_type must only contain values from the enumerated sets above. Drop anything that does not match.
- Output ONLY the JSON object. No markdown code fences, no preamble, no commentary."""


@dataclass(frozen=True)
class DraftOutput:
    """Parsed draft LLM response."""

    implementation_text: str
    explanation_text: str


class DraftParseError(ValueError):
    """Raised when the draft response doesn't contain both required sections."""


# ----------------------------------------------------------------------
# Prompt builders
# ----------------------------------------------------------------------


def build_draft_user_prompt(
    *, name: str, categories: list[str], ato_sources: list[str]
) -> str:
    """Assemble the user message for the drafting call."""
    categories_line = ", ".join(categories) if categories else "(uncategorised)"
    if ato_sources:
        sources_block = "\n".join(f"- {s}" for s in ato_sources)
    else:
        sources_block = "(none — rely on widely-accepted ATO guidance; flag uncertainty)"
    return (
        f"Strategy: {name}\n"
        f"Categories: {categories_line}\n"
        f"ATO primary sources:\n{sources_block}\n\n"
        "Write the Implementation and Explanation sections now."
    )


def build_enrich_user_prompt(
    *,
    name: str,
    categories: list[str],
    implementation_text: str,
    explanation_text: str,
) -> str:
    """Assemble the user message for the enrichment call."""
    categories_line = ", ".join(categories) if categories else "(uncategorised)"
    return (
        f"Strategy name: {name}\n"
        f"Categories: {categories_line}\n\n"
        f"Implementation:\n{implementation_text}\n\n"
        f"Explanation:\n{explanation_text}\n\n"
        "Return the JSON object now."
    )


# ----------------------------------------------------------------------
# Response parsers
# ----------------------------------------------------------------------


# A markdown heading line: one-or-more '#' followed by space(s) and
# heading text. Matched line-by-line rather than across the whole body so
# we don't accidentally swallow a newline into the heading.
_HEADING_RE = re.compile(r"^\s*#{1,6}[ \t]+(?P<heading>.+?)\s*$")


def parse_draft_response(text: str) -> DraftOutput:
    """Split a draft LLM response into implementation + explanation.

    Tolerant of heading level (`##`, `###`) and trailing heading text
    ("## Implementation advice", "## Strategy explanation"). Requires both
    sections to be present — otherwise raises DraftParseError so the
    Celery task fails loudly and Celery's retry-with-backoff kicks in.
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z]*\n?", "", stripped)
        stripped = re.sub(r"\n?```\s*$", "", stripped)

    lines = stripped.split("\n")
    # Walk the lines, tracking which section we're in and collecting body
    # lines into buckets keyed by section name.
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines:
        m = _HEADING_RE.match(line)
        if m:
            heading = m.group("heading").lower()
            if "implementation" in heading:
                current = "implementation"
                sections.setdefault(current, [])
                continue
            if "explanation" in heading:
                current = "explanation"
                sections.setdefault(current, [])
                continue
            # Some other heading — leave current section open so prose
            # containing sub-headings (rare, but tolerable) still lands
            # in the right bucket.
        if current is not None:
            sections[current].append(line)

    implementation = "\n".join(sections.get("implementation", [])).strip()
    explanation = "\n".join(sections.get("explanation", [])).strip()
    if not implementation or not explanation:
        raise DraftParseError(
            "Draft response missing required sections "
            f"(implementation={bool(implementation)}, "
            f"explanation={bool(explanation)}): {text[:300]!r}"
        )
    return DraftOutput(
        implementation_text=implementation, explanation_text=explanation
    )


_ALLOWED_ENTITY_TYPES: frozenset[str] = frozenset(
    {"sole_trader", "partnership", "company", "trust", "smsf", "individual"}
)

_ALLOWED_IMPACT_TYPES: frozenset[str] = frozenset(
    {"deduction", "concession", "offset", "timing", "structure", "rebate", "exemption"}
)

# Default eligibility shape — all nullable/empty. The enrichment parser
# falls back to this on any failure, so the task still records the drafted
# content and transitions forward instead of getting wedged.
_DEFAULT_ELIGIBILITY: dict[str, Any] = {
    "entity_types": [],
    "income_band_min": None,
    "income_band_max": None,
    "turnover_band_min": None,
    "turnover_band_max": None,
    "age_min": None,
    "age_max": None,
    "industry_triggers": [],
    "financial_impact_type": [],
    "keywords": [],
}


def parse_enrich_response(text: str) -> dict[str, Any]:
    """Parse the enrichment JSON response, safely defaulting on malformed output.

    Returns a dict with every field in _DEFAULT_ELIGIBILITY. Unknown fields
    in the LLM output are dropped silently. Enum-valued list fields are
    filtered to the allowed vocabulary. Numeric scalars that aren't
    integers are coerced to None.
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z]*\n?", "", stripped)
        stripped = re.sub(r"\n?```\s*$", "", stripped)

    try:
        raw = json.loads(stripped)
    except json.JSONDecodeError:
        logger.warning("parse_enrich_response: JSON decode failed; using defaults")
        return dict(_DEFAULT_ELIGIBILITY)

    if not isinstance(raw, dict):
        logger.warning(
            "parse_enrich_response: top-level value is %s, expected dict", type(raw)
        )
        return dict(_DEFAULT_ELIGIBILITY)

    result = dict(_DEFAULT_ELIGIBILITY)

    result["entity_types"] = _filter_string_list(
        raw.get("entity_types"), allowed=_ALLOWED_ENTITY_TYPES
    )
    result["financial_impact_type"] = _filter_string_list(
        raw.get("financial_impact_type"), allowed=_ALLOWED_IMPACT_TYPES
    )
    result["industry_triggers"] = _filter_string_list(raw.get("industry_triggers"))
    result["keywords"] = _filter_string_list(raw.get("keywords"))

    for field_name in (
        "income_band_min",
        "income_band_max",
        "turnover_band_min",
        "turnover_band_max",
        "age_min",
        "age_max",
    ):
        result[field_name] = _coerce_int_or_none(raw.get(field_name))

    return result


def _filter_string_list(
    value: Any, *, allowed: frozenset[str] | None = None
) -> list[str]:
    """Normalise to a list[str]; optionally restrict to an allowed vocabulary."""
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        clean = item.strip().lower()
        if not clean:
            continue
        if allowed is not None and clean not in allowed:
            continue
        if clean in out:
            continue  # dedupe while preserving order
        out.append(clean)
    return out


def _coerce_int_or_none(value: Any) -> int | None:
    """Accept int or integer-valued float; otherwise None."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None  # bool is an int subclass; exclude explicitly
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


# ----------------------------------------------------------------------
# Anthropic call wrappers
# ----------------------------------------------------------------------


async def run_draft_llm(
    *,
    name: str,
    categories: list[str],
    ato_sources: list[str],
    client: anthropic.AsyncAnthropic | None = None,
    model: str | None = None,
    max_tokens: int = 4096,
) -> DraftOutput:
    """Call Claude and return parsed draft output.

    `client` + `model` are injectable for testing. Production callers leave
    both None to resolve from settings.
    """
    text = await _acall_anthropic(
        system=DRAFT_SYSTEM_PROMPT,
        user=build_draft_user_prompt(
            name=name, categories=categories, ato_sources=ato_sources
        ),
        client=client,
        model=model,
        max_tokens=max_tokens,
    )
    return parse_draft_response(text)


async def run_enrich_llm(
    *,
    name: str,
    categories: list[str],
    implementation_text: str,
    explanation_text: str,
    client: anthropic.AsyncAnthropic | None = None,
    model: str | None = None,
    max_tokens: int = 2048,
) -> dict[str, Any]:
    """Call Claude and return structured eligibility dict."""
    text = await _acall_anthropic(
        system=ENRICH_SYSTEM_PROMPT,
        user=build_enrich_user_prompt(
            name=name,
            categories=categories,
            implementation_text=implementation_text,
            explanation_text=explanation_text,
        ),
        client=client,
        model=model,
        max_tokens=max_tokens,
    )
    return parse_enrich_response(text)


async def _acall_anthropic(
    *,
    system: str,
    user: str,
    client: anthropic.AsyncAnthropic | None,
    model: str | None,
    max_tokens: int,
) -> str:
    """Actual API call. Extracted so tests monkeypatch a single symbol."""
    resolved_client = client or _default_client()
    resolved_model = model or get_settings().anthropic.model
    response = await resolved_client.messages.create(
        model=resolved_model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    if not response.content:
        return ""
    # Anthropic SDK returns a list of content blocks; the first text block
    # is what we want. This mirrors tax_planning/agents/scanner.py.
    first = response.content[0]
    return getattr(first, "text", "") or ""


def _default_client() -> anthropic.AsyncAnthropic:
    """Construct an AsyncAnthropic from settings.

    Raises RuntimeError if the API key is empty so the Celery task error
    message is specific rather than a cryptic auth failure from the SDK.
    """
    settings = get_settings()
    api_key = settings.anthropic.api_key.get_secret_value()
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not configured; cannot run tax_strategies LLM tasks"
        )
    return anthropic.AsyncAnthropic(api_key=api_key)
