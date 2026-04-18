"""US7 — No pre-Stage-3 rate language leaks to the LLM.

CI gate. Scans every prompt module under `app/modules/tax_planning/` and
`app/modules/agents/` for superseded tax-rate strings. The scan catches
comments and docstrings too — humans copy those into Slack answers and PR
descriptions, so drift risk is not limited to code.

Also asserts positive grounding: the tax planning system prompt contains the
four current Stage-3 thresholds verbatim, so the LLM never has to improvise.

Spec 059 FR-028..FR-030, US7 tests T090-T091 and T113.
"""

from __future__ import annotations

import re
from pathlib import Path

# Repo-relative paths the scan walks. Order matters only for test readability.
PROMPT_MODULE_ROOTS = [
    "app/modules/tax_planning",
    "app/modules/agents",
]

# Forbidden substrings — each catches one family of superseded references:
#   "32.5" — old middle-band marginal rate
#   "19%"  — pre-Stage-3 19% bracket (word-boundary match to avoid false hits)
#   "$120,000" / "$120k" — pre-Stage-3 bracket boundary
FORBIDDEN_LITERAL = ("32.5", "$120,000", "$120k")
FORBIDDEN_REGEX = (re.compile(r"\b19%\B"), re.compile(r"\b19%\b"))

# Current Stage-3 thresholds that must appear in TAX_PLANNING_SYSTEM_PROMPT.
REQUIRED_THRESHOLDS = ("18,200", "45,000", "135,000", "190,000")

BACKEND_ROOT = Path(__file__).resolve().parents[4]


def _iter_prompt_files():
    this_file = Path(__file__).resolve()
    for rel in PROMPT_MODULE_ROOTS:
        root = BACKEND_ROOT / rel
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if path.resolve() == this_file:
                continue  # self-reference
            if "__pycache__" in path.parts:
                continue
            yield path


def test_no_pre_stage3_strings_in_prompt_modules() -> None:
    """Fails CI if a superseded tax rate or bracket boundary is reintroduced
    anywhere under the tax planning or agents prompt trees."""
    offenders: list[str] = []
    for path in _iter_prompt_files():
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_LITERAL:
            if token in text:
                offenders.append(f"{path.relative_to(BACKEND_ROOT)}: contains {token!r}")
        for pattern in FORBIDDEN_REGEX:
            if pattern.search(text):
                offenders.append(f"{path.relative_to(BACKEND_ROOT)}: matches {pattern.pattern!r}")
    assert not offenders, (
        "Pre-Stage-3 tax-rate language must not appear in prompt modules.\n"
        + "\n".join(offenders)
    )


def test_tax_planning_system_prompt_grounds_stage3() -> None:
    """Positive grounding: the system prompt lists the four current Stage-3
    thresholds verbatim so the LLM doesn't hallucinate fresh ones."""
    from app.modules.tax_planning.prompts import TAX_PLANNING_SYSTEM_PROMPT

    for threshold in REQUIRED_THRESHOLDS:
        assert threshold in TAX_PLANNING_SYSTEM_PROMPT, (
            f"TAX_PLANNING_SYSTEM_PROMPT missing Stage-3 threshold {threshold!r}"
        )


# ---------------------------------------------------------------------------
# T113 — Factory coverage (Phase 12 remediation, augments Phase 9)
# ---------------------------------------------------------------------------


def test_factory_uses_stage3_rates() -> None:
    """Test factories feed reality — they must not carry pre-Stage-3 rates."""
    factory_path = BACKEND_ROOT / "tests" / "factories" / "tax_planning.py"
    assert factory_path.exists(), "expected backend/tests/factories/tax_planning.py"
    text = factory_path.read_text(encoding="utf-8")
    assert "0.325" not in text, (
        "tests/factories/tax_planning.py contains pre-Stage-3 rate 0.325 — "
        "update to a Stage-3-correct value (0.30 is the middle-band equivalent)."
    )
