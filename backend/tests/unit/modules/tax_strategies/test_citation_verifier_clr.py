"""Unit tests for CitationVerifier CLR-XXX extensions (Spec 060 T020)."""

from __future__ import annotations

from app.modules.knowledge.retrieval.citation_verifier import (
    CitationVerifier,
    _normalised_levenshtein,
)


def _verifier() -> CitationVerifier:
    return CitationVerifier()


# ----------------------------------------------------------------------
# extract_strategy_citations
# ----------------------------------------------------------------------


def test_extract_single_citation_basic() -> None:
    text = "Consider [CLR-241: Change PSI to PSB] for this profile."
    hits = _verifier().extract_strategy_citations(text)
    assert len(hits) == 1
    assert hits[0]["strategy_id"] == "CLR-241"
    assert hits[0]["name"] == "Change PSI to PSB"


def test_extract_multiple_citations_preserves_order() -> None:
    text = (
        "First apply [CLR-012: Concessional super contributions], then "
        "consider [CLR-241: Change PSI to PSB] and finally "
        "[CLR-089: Income splitting via partnership]."
    )
    hits = _verifier().extract_strategy_citations(text)
    assert [h["strategy_id"] for h in hits] == ["CLR-012", "CLR-241", "CLR-089"]


def test_extract_handles_whitespace_variations() -> None:
    text = "See [CLR-241:   Change PSI to PSB   ] — note the padding."
    hits = _verifier().extract_strategy_citations(text)
    assert len(hits) == 1
    assert hits[0]["name"] == "Change PSI to PSB"


def test_extract_handles_multi_line_response() -> None:
    text = (
        "Line one mentions [CLR-012: Concessional super contributions].\n"
        "Line two has another: [CLR-241: Change PSI to PSB].\n"
        "Line three has none."
    )
    hits = _verifier().extract_strategy_citations(text)
    assert len(hits) == 2


def test_extract_rejects_malformed_markers() -> None:
    # Missing brackets, wrong prefix, stray identifier-only forms.
    text = (
        "Near-miss forms like (CLR-241) and CLR-241 should NOT match. "
        "Nor should [LTR-241: wrong prefix] or [CLR-12: short digits]. "
        "[CLR-241: valid] is the only real hit."
    )
    hits = _verifier().extract_strategy_citations(text)
    assert len(hits) == 1
    assert hits[0]["strategy_id"] == "CLR-241"


def test_extract_returns_empty_on_empty_text() -> None:
    assert _verifier().extract_strategy_citations("") == []


# ----------------------------------------------------------------------
# verify_strategy_citations — classification
# ----------------------------------------------------------------------


_RETRIEVED = [
    {
        "strategy_id": "CLR-241",
        "name": "Change PSI to PSB",
        "categories": ["Business"],
    },
    {
        "strategy_id": "CLR-012",
        "name": "Concessional super contributions",
        "categories": ["Recommendations"],
    },
]


def test_exact_match_classifies_verified() -> None:
    text = "[CLR-241: Change PSI to PSB]"
    results = _verifier().verify_strategy_citations(text, _RETRIEVED)
    assert len(results) == 1
    assert results[0]["status"] == "verified"
    assert results[0]["name_drift"] == 0.0
    assert results[0]["strategy"]["strategy_id"] == "CLR-241"


def test_minor_drift_still_verified() -> None:
    """A trivial difference (case/whitespace) should be normalised away and
    classify as verified, not partially."""
    text = "[CLR-241: change psi to PSB]"  # case variation only
    results = _verifier().verify_strategy_citations(text, _RETRIEVED)
    assert len(results) == 1
    assert results[0]["status"] == "verified"


def test_significant_name_drift_classifies_partially_verified() -> None:
    # "Super contributions strategy" differs from "Concessional super
    # contributions" by >30% normalised edit distance.
    text = "[CLR-012: Super contributions strategy]"
    results = _verifier().verify_strategy_citations(text, _RETRIEVED)
    assert len(results) == 1
    assert results[0]["status"] == "partially_verified"
    assert results[0]["name_drift"] >= 0.30
    # Strategy reference is still populated so UI can hydrate.
    assert results[0]["strategy"]["strategy_id"] == "CLR-012"


def test_hallucinated_identifier_classifies_unverified() -> None:
    text = "[CLR-999: Totally fake strategy]"
    results = _verifier().verify_strategy_citations(text, _RETRIEVED)
    assert len(results) == 1
    assert results[0]["status"] == "unverified"
    assert results[0]["name_drift"] is None
    assert results[0]["strategy"] is None


def test_mixed_trio_classifies_each_separately() -> None:
    """Spec SC-007 path: one of each verification state in one response."""
    text = (
        "First [CLR-241: Change PSI to PSB], "
        "then [CLR-012: Something else entirely], "
        "plus [CLR-999: Fake]."
    )
    results = _verifier().verify_strategy_citations(text, _RETRIEVED)
    assert [r["status"] for r in results] == [
        "verified",
        "partially_verified",
        "unverified",
    ]


def test_empty_response_returns_empty() -> None:
    assert _verifier().verify_strategy_citations("", _RETRIEVED) == []


def test_response_with_no_clr_citations_returns_empty() -> None:
    text = "This response only cites ITAA 1997 s 87-15 — no strategies."
    assert _verifier().verify_strategy_citations(text, _RETRIEVED) == []


# ----------------------------------------------------------------------
# _normalised_levenshtein sanity checks
# ----------------------------------------------------------------------


def test_levenshtein_identical_is_zero() -> None:
    assert _normalised_levenshtein("Change PSI to PSB", "Change PSI to PSB") == 0.0


def test_levenshtein_completely_different_is_one() -> None:
    # Different lengths, no shared characters → normalised distance = 1.0.
    assert _normalised_levenshtein("abc", "xyz") == 1.0


def test_levenshtein_handles_whitespace_and_case() -> None:
    # Normalisation strips whitespace and lowercases before comparing.
    assert _normalised_levenshtein("  CHANGE psi to PSB  ", "change psi to psb") == 0.0
