"""Three-state classification for CLR citations (Spec 060 T046, SC-007).

Covers every branch of `CitationVerifier.verify_strategy_citations`:
    - exact id + in-threshold name    → verified
    - exact id + drifted name          → partially_verified
    - no matching id                   → unverified

Each case is asserted against a retrieved_strategies set so the fixture
shape stays faithful to what the tax_planning service actually passes at
runtime.
"""

from __future__ import annotations

import pytest

from app.modules.knowledge.retrieval.citation_verifier import CitationVerifier

_RETRIEVED = [
    {
        "strategy_id": "CLR-012",
        "name": "Concessional super contributions",
        "categories": ["SMSF", "Employees"],
    },
    {
        "strategy_id": "CLR-241",
        "name": "Change PSI to PSB",
        "categories": ["Business_structures"],
    },
]


@pytest.mark.parametrize(
    "response_text,expected_status,expected_strategy_id",
    [
        # Exact-name match → verified.
        (
            "Consider [CLR-012: Concessional super contributions] here.",
            "verified",
            "CLR-012",
        ),
        # Id matches but the cited name has drifted past the 0.30 threshold.
        # "Maximum super contributions" vs stored "Concessional super
        # contributions" — roughly half the tokens differ.
        (
            "Try [CLR-012: Maximum super contributions totally different].",
            "partially_verified",
            "CLR-012",
        ),
        # No retrieved strategy with this id → unverified (e.g., hallucinated
        # or a strategy that was superseded since retrieval).
        (
            "And also [CLR-999: Imaginary strategy].",
            "unverified",
            "CLR-999",
        ),
    ],
)
def test_strategy_citation_state_classification(
    response_text: str,
    expected_status: str,
    expected_strategy_id: str,
) -> None:
    results = CitationVerifier().verify_strategy_citations(response_text, _RETRIEVED)
    assert len(results) == 1
    assert results[0]["strategy_id"] == expected_strategy_id
    assert results[0]["status"] == expected_status


def test_mixed_response_returns_all_three_states_in_source_order() -> None:
    text = (
        "Start with [CLR-012: Concessional super contributions], then "
        "consider [CLR-012: A completely different title that has drifted], "
        "and finally [CLR-999: Fake fake fake]."
    )
    results = CitationVerifier().verify_strategy_citations(text, _RETRIEVED)
    statuses = [r["status"] for r in results]
    assert statuses == ["verified", "partially_verified", "unverified"]
    # name_drift is present on the id-match cases and None on the miss.
    assert results[0]["name_drift"] is not None and results[0]["name_drift"] < 0.30
    assert results[1]["name_drift"] is not None and results[1]["name_drift"] >= 0.30
    assert results[2]["name_drift"] is None


def test_empty_response_returns_empty_list() -> None:
    assert CitationVerifier().verify_strategy_citations("", _RETRIEVED) == []


def test_response_without_citations_returns_empty_list() -> None:
    text = "This message has prose but no strategy references."
    assert CitationVerifier().verify_strategy_citations(text, _RETRIEVED) == []
