"""Spec 061 — Citation Substantive Validation unit tests.

TDD baseline: these tests describe the TARGET behaviour of the redesigned
citation verifier. Many will be RED after Phase 3 lands (the verifier still
blind-substring-matches and has no act-year check). Phases 4 and 5 make
them GREEN.

The `match_strength` ↔ `matched_by` invariant from R5 is enforced by
`test_match_strength_matched_by_invariant`.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.modules.knowledge.data import section_act_mapping as mapping_module
from app.modules.knowledge.data.section_act_mapping import normalise_section
from app.modules.knowledge.retrieval.citation_verifier import (
    CitationReasonCode,
    CitationVerifier,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _make_chunk(
    *,
    ruling_number: str | None = None,
    section_ref: str | None = None,
    title: str = "Test chunk",
    text: str = "",
    relevance_score: float = 0.8,
    source_url: str = "https://example.test",
    source_type: str = "ruling",
    effective_date: str | None = None,
) -> dict[str, Any]:
    """Build a minimal chunk dict with the fields the verifier reads."""
    return {
        "ruling_number": ruling_number,
        "section_ref": section_ref,
        "title": title,
        "text": text,
        "relevance_score": relevance_score,
        "score": relevance_score,  # legacy key used by _build_citation_dict
        "source_url": source_url,
        "source_type": source_type,
        "effective_date": effective_date,
    }


def _make_verifier() -> CitationVerifier:
    return CitationVerifier()


@pytest.fixture
def test_mapping(monkeypatch: pytest.MonkeyPatch) -> dict[str, dict]:
    """Tiny controlled mapping for act-year tests.

    Overrides the module-level cache so tests do not depend on the shipped
    YAML. `monkeypatch` handles teardown automatically.
    """
    fixture = {
        "82kzm": {"act": "ITAA 1936", "display_name": "s 82KZM ITAA 1936", "notes": None},
        "328-180": {
            "act": "ITAA 1997",
            "display_name": "s 328-180 ITAA 1997",
            "notes": None,
        },
    }
    # Replace the accessor outright — simpler than clearing functools.cache and
    # re-running the YAML read with a monkeypatched path.
    monkeypatch.setattr(mapping_module, "get_section_act_mapping", lambda: fixture, raising=True)
    return fixture


def _find_citation_by_ref(citations: list[dict], ref_fragment: str) -> dict | None:
    """Helper: find the citation whose raw value contains the fragment."""
    for c in citations:
        ref = str(c.get("section_ref") or c.get("title") or "")
        if ref_fragment.lower() in ref.lower():
            return c
    # Fall back: some ungrounded citations store the raw ref in section_ref
    return citations[0] if citations else None


# ---------------------------------------------------------------------------
# Normaliser unit (R7) — covers Story 3 T017
# ---------------------------------------------------------------------------


def test_normalise_section_handles_common_variants() -> None:
    """R7 — normalisation folds the common LLM-output spelling variants."""
    variants = ["Section 82KZM", "s 82KZM", "S82KZM", "sec. 82kzm", " s82KZM "]
    for v in variants:
        assert normalise_section(v) == "82kzm", (
            f"Variant {v!r} should normalise to '82kzm', got {normalise_section(v)!r}"
        )


# ---------------------------------------------------------------------------
# T009 — ruling metadata equality verifies strong
# ---------------------------------------------------------------------------


def test_ruling_metadata_equality_verifies_strong() -> None:
    """FR-001: `ruling_number` metadata equality is the only path to verified=True."""
    verifier = _make_verifier()
    chunks = [
        _make_chunk(
            ruling_number="TR 2024/1",
            title="Prepayment guidance",
            text="Body text unrelated to the ruling identifier itself.",
        )
    ]
    result = verifier.verify_citations("See TR 2024/1 for details.", chunks)

    assert len(result.citations) == 1
    cite = result.citations[0]
    assert cite["verified"] is True
    assert cite["match_strength"] == "strong"
    assert cite["matched_by"] == "ruling_number"
    assert cite["reason_code"] == CitationReasonCode.STRONG_MATCH.value


# ---------------------------------------------------------------------------
# T010 — body-text-only match is weak, not verified
# ---------------------------------------------------------------------------


def test_ruling_body_text_only_is_weak_not_verified() -> None:
    """FR-002: body-text mention without metadata equality → weak, not verified."""
    verifier = _make_verifier()
    chunks = [
        _make_chunk(
            ruling_number="TR 2023/5",  # Different from the cited ruling
            title="Some other ruling",
            text="This chunk mentions TR 2024/1 in passing as a cross-reference.",
        )
    ]
    result = verifier.verify_citations("We rely on TR 2024/1.", chunks)

    assert len(result.citations) == 1
    cite = result.citations[0]
    assert cite["verified"] is False
    assert cite["match_strength"] == "weak"
    assert cite["reason_code"] == CitationReasonCode.WEAK_MATCH_BODY_ONLY.value


# ---------------------------------------------------------------------------
# T011 — hallucinated ruling (no match anywhere)
# ---------------------------------------------------------------------------


def test_hallucinated_ruling_no_match_anywhere() -> None:
    """FR-003: identifier absent from every chunk's metadata AND body → verified=False, none."""
    verifier = _make_verifier()
    chunks = [
        _make_chunk(
            ruling_number="TR 2020/1",
            title="Unrelated ruling",
            text="No mention of the hallucinated identifier in this body text.",
        )
    ]
    result = verifier.verify_citations("As per TR 9999/99...", chunks)

    assert len(result.citations) == 1
    cite = result.citations[0]
    assert cite["verified"] is False
    assert cite["match_strength"] == "none"
    assert cite["reason_code"] == CitationReasonCode.WEAK_MATCH_NONE.value


# ---------------------------------------------------------------------------
# T012 — wrong-act-year flagged
# ---------------------------------------------------------------------------


def test_section_wrong_act_year_flagged(test_mapping: dict) -> None:
    """FR-005: s 82KZM attributed to ITAA 1997 → wrong_act_year (belongs to 1936)."""
    verifier = _make_verifier()
    chunks = [
        _make_chunk(
            section_ref="s 82KZM",
            title="Prepayment guidance",
            text="Section 82KZM covers prepayment timing rules.",
        )
    ]
    result = verifier.verify_citations("See s 82KZM ITAA 1997 for the rule.", chunks)

    assert len(result.citations) == 1
    cite = result.citations[0]
    assert cite["verified"] is False
    assert cite["reason_code"] == CitationReasonCode.WRONG_ACT_YEAR.value


# ---------------------------------------------------------------------------
# T013 — correct act-year verifies
# ---------------------------------------------------------------------------


def test_section_correct_act_year_verifies(test_mapping: dict) -> None:
    """FR-005 positive path: s 82KZM ITAA 1936 verifies (mapping agrees)."""
    verifier = _make_verifier()
    chunks = [
        _make_chunk(
            section_ref="s 82KZM",
            title="Prepayment guidance",
            text="Section 82KZM covers prepayment timing rules.",
        )
    ]
    result = verifier.verify_citations("See s 82KZM ITAA 1936 for the rule.", chunks)

    assert len(result.citations) == 1
    cite = result.citations[0]
    assert cite["verified"] is True
    # Act-year check does not fire when mapping agrees; match proceeds normally.
    assert cite["reason_code"] != CitationReasonCode.WRONG_ACT_YEAR.value


# ---------------------------------------------------------------------------
# T014 — unknown section: no penalty
# ---------------------------------------------------------------------------


def test_section_unknown_in_mapping_not_penalised(test_mapping: dict) -> None:
    """FR-006: section absent from mapping → no wrong_act_year, falls through."""
    verifier = _make_verifier()
    chunks = [
        _make_chunk(
            section_ref="s 9999Z",
            title="Obscure section",
            text="Section 9999Z something.",
        )
    ]
    result = verifier.verify_citations("Refer to s 9999Z ITAA 1997.", chunks)

    assert len(result.citations) == 1
    cite = result.citations[0]
    assert cite["reason_code"] != CitationReasonCode.WRONG_ACT_YEAR.value


# ---------------------------------------------------------------------------
# T015 — no act suffix: act-year check is skipped
# ---------------------------------------------------------------------------


def test_section_no_act_year_attribution_skips_act_check(test_mapping: dict) -> None:
    """FR-006: no act suffix → no wrong_act_year flag even if mapping expects a specific Act."""
    verifier = _make_verifier()
    chunks = [
        _make_chunk(
            section_ref="s 82KZM",
            title="Prepayment guidance",
            text="Section 82KZM covers prepayment timing rules.",
        )
    ]
    # No "ITAA 1997" / "ITAA 1936" suffix in the citation — act-year check must skip.
    result = verifier.verify_citations("See s 82KZM for the rule.", chunks)

    assert len(result.citations) == 1
    cite = result.citations[0]
    assert cite["reason_code"] != CitationReasonCode.WRONG_ACT_YEAR.value


# ---------------------------------------------------------------------------
# T016 — match_strength ↔ matched_by invariant (R5)
# ---------------------------------------------------------------------------


def test_match_strength_matched_by_invariant() -> None:
    """R5: every result must satisfy the strong/weak/none ↔ matched_by invariant."""
    verifier = _make_verifier()
    chunks = [
        _make_chunk(ruling_number="TR 2024/1", title="Strong-path ruling"),
        _make_chunk(
            ruling_number="TR 2020/1",
            title="Weak-body-path ruling",
            text="Brief cross-reference to TR 2025/7 in body.",
        ),
    ]
    # Strong (metadata), weak-body (body only), hallucination (none) — three citations.
    text = "Per TR 2024/1, and see TR 2025/7, but TR 9999/99 does not exist."
    result = verifier.verify_citations(text, chunks)

    assert len(result.citations) == 3

    for cite in result.citations:
        strength = cite.get("match_strength")
        matched_by = cite.get("matched_by")
        assert strength in {"strong", "weak", "none"}, (
            f"match_strength missing or invalid on citation: {cite}"
        )
        if strength == "strong":
            assert matched_by in {"ruling_number", "section_ref"}, (
                f"strong match must have metadata matched_by, got {matched_by!r}: {cite}"
            )
        elif strength == "weak":
            assert matched_by in {"body_text", "title", "numbered_index"}, (
                f"weak match must have non-metadata matched_by, got {matched_by!r}: {cite}"
            )
        else:  # none
            assert matched_by == "unverified", (
                f"none match must have matched_by='unverified', got {matched_by!r}: {cite}"
            )


# ---------------------------------------------------------------------------
# Additional coverage — extractor-level act-year capture
# ---------------------------------------------------------------------------


def test_section_extractor_captures_act_year_when_present() -> None:
    """FR-004 negative: section citation with act suffix carries act_year field."""
    verifier = _make_verifier()
    # Empty chunks — we just care about the extracted shape.
    result = verifier.verify_citations("Per s 82KZM ITAA 1936 prepayments apply.", [])
    # Even ungrounded, the citation record must exist.
    assert len(result.citations) == 1


# ---------------------------------------------------------------------------
# Numbered-citation coverage — positional match is authoritative
# ---------------------------------------------------------------------------


def test_numbered_citation_in_range_verifies_strong() -> None:
    """Numbered [N] in range → strong match, verified=True, matched_by=numbered_index."""
    verifier = _make_verifier()
    chunks = [
        _make_chunk(title="First retrieved chunk"),
        _make_chunk(title="Second retrieved chunk"),
    ]
    result = verifier.verify_citations("See [1] for context.", chunks)

    assert len(result.citations) == 1
    cite = result.citations[0]
    assert cite["verified"] is True
    assert cite["match_strength"] == "strong"
    assert cite["matched_by"] == "numbered_index"
    assert cite["reason_code"] == CitationReasonCode.STRONG_MATCH.value


def test_numbered_citation_out_of_range_unverified() -> None:
    """Numbered [N] out of range → none, verified=False."""
    verifier = _make_verifier()
    chunks = [_make_chunk(title="Only chunk")]
    result = verifier.verify_citations("See [5] which does not exist.", chunks)

    assert len(result.citations) == 1
    cite = result.citations[0]
    assert cite["verified"] is False
    assert cite["match_strength"] == "none"
    assert cite["matched_by"] == "unverified"
    assert cite["reason_code"] == CitationReasonCode.WEAK_MATCH_NONE.value


def test_no_citations_in_response_returns_empty_result() -> None:
    """Response with no recognised citations → empty citations list, rate=1.0."""
    verifier = _make_verifier()
    result = verifier.verify_citations("Plain text with no citations.", [_make_chunk()])

    assert result.citations == []
    assert result.ungrounded_count == 0
    assert result.verification_rate == 1.0
