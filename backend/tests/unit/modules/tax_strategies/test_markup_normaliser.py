"""Unit tests for citation markup normalisation (Spec 060 T064b)."""

from __future__ import annotations

from app.modules.tax_strategies.markup import normalise_strategy_citations


_RETRIEVED = [
    {
        "strategy_id": "CLR-012",
        "name": "Concessional super contributions",
    },
    {
        "strategy_id": "CLR-241",
        "name": "Change PSI to PSB",
    },
]


def test_canonical_form_is_preserved_verbatim() -> None:
    """Canonical [CLR-XXX: Name] must not be rewritten."""
    text = "Apply [CLR-012: Concessional super contributions] here."
    assert normalise_strategy_citations(text, _RETRIEVED) == text


def test_bracketed_identifier_without_name_is_normalised() -> None:
    text = "Apply [CLR-012] here."
    out = normalise_strategy_citations(text, _RETRIEVED)
    assert out == "Apply [CLR-012: Concessional super contributions] here."


def test_bracketed_identifier_with_empty_name_is_normalised() -> None:
    text = "Apply [CLR-012: ] here."
    out = normalise_strategy_citations(text, _RETRIEVED)
    assert out == "Apply [CLR-012: Concessional super contributions] here."


def test_parenthesised_form_is_normalised() -> None:
    """(CLR-241) should become [CLR-241: Change PSI to PSB]."""
    text = "Consider (CLR-241) for contracting income."
    out = normalise_strategy_citations(text, _RETRIEVED)
    assert out == "Consider [CLR-241: Change PSI to PSB] for contracting income."


def test_bare_identifier_is_normalised() -> None:
    """Bare CLR-241 outside any bracketing → canonical form."""
    text = "CLR-241 applies here."
    out = normalise_strategy_citations(text, _RETRIEVED)
    assert out == "[CLR-241: Change PSI to PSB] applies here."


def test_unknown_identifier_is_left_untouched() -> None:
    """A hallucinated CLR-999 (not in retrieved set) must NOT be rewritten —
    the verifier needs to classify it as unverified (red chip)."""
    text = "Apply [CLR-999] for this case."
    out = normalise_strategy_citations(text, _RETRIEVED)
    assert out == text


def test_mixed_canonical_and_near_miss_in_one_response() -> None:
    text = (
        "First consider [CLR-012: Concessional super contributions] — "
        "then look at (CLR-241) and finally CLR-012 once more."
    )
    out = normalise_strategy_citations(text, _RETRIEVED)
    # Canonical preserved; parenthesised and bare both normalised.
    assert "[CLR-012: Concessional super contributions]" in out
    assert "[CLR-241: Change PSI to PSB]" in out
    assert "(CLR-241)" not in out
    # Bare "CLR-012 once" rewrites to canonical too.
    assert "[CLR-012: Concessional super contributions] once more" in out


def test_empty_retrieved_set_returns_text_unchanged() -> None:
    text = "Apply [CLR-012] here."
    assert normalise_strategy_citations(text, []) == text


def test_empty_text_returns_empty() -> None:
    assert normalise_strategy_citations("", _RETRIEVED) == ""


def test_does_not_rewrite_inside_source_citation_like_form() -> None:
    """The ATO-source style [Source: ...] is distinct and unaffected."""
    text = "[Source: ITAA 1997 s 87-15] and [CLR-241]."
    out = normalise_strategy_citations(text, _RETRIEVED)
    assert "[Source: ITAA 1997 s 87-15]" in out
    assert "[CLR-241: Change PSI to PSB]" in out


def test_identifier_in_canonical_form_near_near_miss_form() -> None:
    """A canonical form followed by a bare form on the same line — the
    canonical stays, the bare gets rewritten. The bare-match regex uses
    negative lookbehind for `:` to avoid confusing with the canonical
    form's `[CLR-NNN: Name]` context.
    """
    text = "[CLR-012: Concessional super contributions]; also CLR-241."
    out = normalise_strategy_citations(text, _RETRIEVED)
    assert out == (
        "[CLR-012: Concessional super contributions]; also "
        "[CLR-241: Change PSI to PSB]."
    )
