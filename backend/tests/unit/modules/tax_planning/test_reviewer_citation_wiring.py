"""Spec 061 follow-up — reviewer consumes structural citation verification.

These tests cover the small helper extensions in reviewer.py that feed
CitationVerificationResult objects into the reviewer's prompt. The full
reviewer.run() path hits Anthropic so it is not exercised here; we test
the deterministic formatting helper directly.
"""

from __future__ import annotations

from app.modules.knowledge.retrieval.citation_verifier import (
    CitationVerificationResult,
)
from app.modules.tax_planning.agents.reviewer import (
    _format_citation_findings,
    _summarise_verification,
)


def _result(citations: list[dict], rate: float = 1.0) -> CitationVerificationResult:
    return CitationVerificationResult(
        citations=citations,
        ungrounded_count=sum(1 for c in citations if not c.get("verified")),
        verification_rate=rate,
    )


def test_format_with_no_verifications_emits_legacy_disclaimer() -> None:
    """Both None → short disclaimer, prompt remains well-formed."""
    text = _format_citation_findings(None, None)
    assert "No structural citation verification" in text


def test_format_with_all_strong_matches_shows_clean_state() -> None:
    """All citations verified → reviewer is told nothing was flagged."""
    brief = _result(
        [
            {
                "section_ref": "s 82KZM ITAA 1936",
                "verified": True,
                "reason_code": "strong_match",
            }
        ],
        rate=1.0,
    )
    text = _format_citation_findings(brief, None)
    assert "all 1 citation(s) verified" in text
    # No per-citation problem line (the "→ reason=…" marker) should appear.
    assert "→ reason=" not in text


def test_format_surfaces_wrong_act_year_finding_verbatim() -> None:
    """Problem citations appear in the prompt with their reason_code."""
    brief = _result(
        [
            {
                "section_ref": "s 82KZM ITAA 1997",
                "verified": False,
                "reason_code": "wrong_act_year",
            },
            {
                "section_ref": "s 328-180 ITAA 1997",
                "verified": True,
                "reason_code": "strong_match",
            },
        ],
        rate=0.5,
    )
    text = _format_citation_findings(brief, None)
    assert "wrong_act_year" in text
    assert "s 82KZM ITAA 1997" in text
    # Strong-match entries should NOT be reported as problems.
    assert text.count("→ reason=") == 1
    # Authority instruction must reach the prompt so Claude doesn't override
    # the structural verifier with its own legal training.
    assert "structural verifier is authoritative" in text


def test_format_emits_separate_sections_per_document() -> None:
    """Brief and summary are labelled distinctly so the reviewer can cite
    the right document in its finding."""
    brief = _result(
        [
            {
                "section_ref": "s 82KZM ITAA 1997",
                "verified": False,
                "reason_code": "wrong_act_year",
            }
        ],
        rate=0.0,
    )
    summary = _result(
        [
            {
                "section_ref": "s 328-180 ITAA 1997",
                "verified": True,
                "reason_code": "strong_match",
            }
        ],
        rate=1.0,
    )
    text = _format_citation_findings(brief, summary)
    assert "Accountant Brief" in text
    assert "Client Summary" in text
    # The brief section flags wrong_act_year; the summary section is clean.
    brief_idx = text.index("Accountant Brief")
    summary_idx = text.index("Client Summary")
    assert brief_idx < summary_idx
    wrong_act_idx = text.index("wrong_act_year")
    assert brief_idx < wrong_act_idx < summary_idx, (
        "wrong_act_year must appear under the brief section, not the summary"
    )


def test_summarise_with_weak_match_none_reports_hallucination() -> None:
    """Hallucinated identifiers are flagged with their reason code."""
    result = _result(
        [
            {
                "section_ref": "TR 9999/99",
                "verified": False,
                "reason_code": "weak_match_none",
            }
        ],
        rate=0.0,
    )
    summary = _summarise_verification(result, "Accountant Brief")
    assert summary is not None
    assert "weak_match_none" in summary
    assert "TR 9999/99" in summary


def test_summarise_empty_returns_none() -> None:
    """Empty verification result → nothing to say, returns None so the
    formatter can omit the sub-section cleanly."""
    result = _result([], rate=1.0)
    assert _summarise_verification(result, "Accountant Brief") is None
    assert _summarise_verification(None, "Accountant Brief") is None
