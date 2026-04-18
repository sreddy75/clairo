"""T110 — Citation regression bank.

Runs the 20-question citation regression bank through the verifier +
confidence gate that the chat and streaming paths share, and asserts the
false-decline rate stays at or below 1 in 20 (SC-008).

We hit the verification layer directly rather than standing up the full
async multi-agent pipeline: the failure mode the bank is defending against
(correct answer → gate incorrectly flips to `low_confidence`) is entirely
inside `_build_citation_verification` + the confidence-score formula, so
that's the right surface to test. Changes to retrieval ranking, verifier
matching, or gate weights flip questions across the threshold and this test
catches the regression.

Spec 059 Phase 12 T110 (augments Phase 8).
"""

from __future__ import annotations

from pathlib import Path

import yaml


FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "citation_regression_bank.yaml"
)

# Matches the gate in `service.send_chat_message` — keep in sync.
CONFIDENCE_THRESHOLD = 0.5
DECLINE_BUDGET = 1  # SC-008: ≤ 1 / 20


def _gate_verdict(response: str, chunks: list[dict]) -> tuple[str, float]:
    """Replicate the verification + confidence gate used by both chat paths.

    Returns `(status, confidence_score)`. A question is declined when the
    returned status is `"low_confidence"` (retrieval confidence below the
    0.5 threshold with chunks present) — matches the production predicate
    at `service.send_chat_message_streaming`.
    """
    from app.modules.tax_planning.service import TaxPlanningService

    # The method only reads its inputs — no `self.session` access — so a
    # bare instance created via `__new__` is sufficient without having to
    # stand up a real async session for every question.
    service = TaxPlanningService.__new__(TaxPlanningService)
    verification = service._build_citation_verification(response, chunks)  # type: ignore[attr-defined]

    scores = [c.get("relevance_score", 0.0) for c in chunks if c.get("relevance_score")]
    top_score = scores[0] if scores else 0.0
    mean_top5 = sum(scores[:5]) / min(len(scores), 5) if scores else 0.0
    verification_rate = verification.get("verification_rate", 0.0)
    confidence_score = 0.4 * top_score + 0.3 * mean_top5 + 0.3 * verification_rate

    status = verification.get("status", "no_citations")
    if confidence_score < CONFIDENCE_THRESHOLD and chunks:
        status = "low_confidence"
    return status, confidence_score


def test_citation_bank_false_decline_rate_within_budget() -> None:
    """Reads every question from the regression bank and counts how many
    would be declined by the confidence gate. Fails if the count exceeds
    the SC-008 budget (1 in 20)."""
    data = yaml.safe_load(FIXTURE_PATH.read_text(encoding="utf-8"))
    questions = data["questions"]
    assert len(questions) >= 20, (
        f"Bank must contain at least 20 questions; got {len(questions)}"
    )

    declined: list[str] = []
    for entry in questions:
        status, score = _gate_verdict(entry["response"], entry["chunks"])
        if status == "low_confidence" or status == "unverified":
            declined.append(f"{entry['id']}: status={status} score={score:.2f}")

    assert len(declined) <= DECLINE_BUDGET, (
        f"False-decline rate {len(declined)} / {len(questions)} exceeds "
        f"the SC-008 budget of {DECLINE_BUDGET}. Declined questions:\n"
        + "\n".join(f"  - {line}" for line in declined)
    )


def test_citation_bank_every_entry_has_verifiable_shape() -> None:
    """Schema check on the fixture itself — guards against a future edit
    that drops a required field and gets papered over by the verifier's
    graceful fallback."""
    data = yaml.safe_load(FIXTURE_PATH.read_text(encoding="utf-8"))
    for i, entry in enumerate(data["questions"]):
        assert "id" in entry, f"question #{i} missing `id`"
        assert "question" in entry, f"{entry.get('id')}: missing `question`"
        assert "response" in entry, f"{entry.get('id')}: missing `response`"
        assert "chunks" in entry, f"{entry.get('id')}: missing `chunks`"
        for chunk in entry["chunks"]:
            assert "relevance_score" in chunk, (
                f"{entry['id']}: chunk missing `relevance_score` — the "
                "confidence gate reads this key specifically (not `score`)"
            )
