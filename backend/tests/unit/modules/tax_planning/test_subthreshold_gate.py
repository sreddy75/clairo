"""Spec 061 FR-010 — streaming / non-streaming sub-threshold-gate parity.

The `_apply_subthreshold_gate` helper is a pure function; these tests fix
its behaviour so both chat call sites share a single, testable rule.
"""

from __future__ import annotations

from app.modules.tax_planning.service import _apply_subthreshold_gate


def _chunk(score: float = 0.8) -> dict:
    return {"relevance_score": score, "text": "any"}


def test_above_threshold_passes_through() -> None:
    """Confidence ≥ 0.5 returns (content, scenarios, "ok") unchanged."""
    content = "answer"
    scenarios = [{"id": 1}, {"id": 2}]
    chunks = [_chunk()]

    out_content, out_scenarios, label = _apply_subthreshold_gate(
        response_content=content,
        scenarios=scenarios,
        confidence_score=0.75,
        retrieved_chunks=chunks,
    )

    assert out_content == content
    assert out_scenarios == scenarios
    assert label == "ok"


def test_below_threshold_with_chunks_preserves_content_clears_scenarios() -> None:
    """Q2=C hybrid rule: content preserved, scenarios empty, label low_confidence."""
    content = "partial answer"
    scenarios = [{"id": 1}]
    chunks = [_chunk(0.4)]

    out_content, out_scenarios, label = _apply_subthreshold_gate(
        response_content=content,
        scenarios=scenarios,
        confidence_score=0.3,
        retrieved_chunks=chunks,
    )

    assert out_content == content, "content must be preserved verbatim"
    assert out_scenarios == [], "scenarios must be cleared"
    assert label == "low_confidence"


def test_below_threshold_with_no_chunks_passes_through() -> None:
    """If no chunks retrieved, the gate doesn't fire (handled upstream)."""
    content = "answer from general knowledge"
    scenarios = [{"id": 1}]

    out_content, out_scenarios, label = _apply_subthreshold_gate(
        response_content=content,
        scenarios=scenarios,
        confidence_score=0.1,
        retrieved_chunks=[],
    )

    assert out_content == content
    assert out_scenarios == scenarios
    assert label == "ok"


def test_idempotent() -> None:
    """Calling twice with the same inputs yields the same outputs both times."""
    content = "answer"
    scenarios = [{"id": 1}]
    chunks = [_chunk(0.4)]

    first = _apply_subthreshold_gate(
        response_content=content,
        scenarios=scenarios,
        confidence_score=0.3,
        retrieved_chunks=chunks,
    )
    # Calling again on the FIRST output of course returns (content, [], "low_confidence")
    # again — scenarios are already empty. Idempotence here means "same predicate →
    # same classification," not "same output as a complex reducer."
    second = _apply_subthreshold_gate(
        response_content=first[0],
        scenarios=first[1],
        confidence_score=0.3,
        retrieved_chunks=chunks,
    )

    assert first == second


def test_boundary_at_exactly_0_5_passes_through() -> None:
    """The threshold uses strict `<` — confidence == 0.5 is not sub-threshold."""
    content = "answer"
    scenarios = [{"id": 1}]
    chunks = [_chunk(0.5)]

    out_content, out_scenarios, label = _apply_subthreshold_gate(
        response_content=content,
        scenarios=scenarios,
        confidence_score=0.5,
        retrieved_chunks=chunks,
    )

    assert out_content == content
    assert out_scenarios == scenarios
    assert label == "ok"
