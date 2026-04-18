"""Citation markup normalisation (Spec 060 T064b, Constitution §VIII).

Principle: "Prompts enforce nothing — code enforces everything."

The tax planning system prompt instructs the LLM to cite tax strategies
as ``[CLR-XXX: Name]`` verbatim from the ``<strategy>`` envelope. But
prompt compliance is probabilistic; the LLM drifts. Common drift forms
observed in the wild:

    CLR-241                    (bare identifier, no brackets)
    (CLR-241)                  (parenthesised — matches ATO-source style)
    [CLR-241]                  (bracketed identifier, no name)
    [CLR-241: ]                (bracketed, trailing colon, empty name)

This module rewrites those near-misses into the canonical
``[CLR-XXX: Name]`` form when the identifier is actually in the retrieved
strategies set. Unresolvable near-misses (unknown identifier) are left
untouched so the verifier can classify them as `unverified` and the UI
can render them red.

This guards against markup drift degrading chip coverage — a verified
strategy shouldn't render as unverified just because the LLM dropped the
brackets.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

# Matches near-miss forms that should be rewritten IF the identifier
# resolves to a retrieved strategy. Order matters: longer / more specific
# patterns are tried first so we don't double-rewrite.
#
# The canonical form `[CLR-XXX: NonEmptyName]` is explicitly NOT matched
# here — we only want to rewrite *near-misses*, not canonical hits.
_CLR_NEAR_MISS_PATTERNS: tuple[re.Pattern[str], ...] = (
    # [CLR-241] or [CLR-241: ] or [CLR-241:   ]
    re.compile(r"\[CLR-(?P<num>\d{3,5})(?::\s*)?\]"),
    # (CLR-241)
    re.compile(r"\(CLR-(?P<num>\d{3,5})\)"),
    # Bare CLR-241 not already inside brackets. Uses negative lookbehind
    # for `[` / `(` / `:` (part of canonical) and negative lookahead for
    # `:` / `]` / `)` so we don't eat partial matches of other forms.
    re.compile(r"(?<![\[\(:])\bCLR-(?P<num>\d{3,5})\b(?![:\]\)])"),
)


def normalise_strategy_citations(
    text: str,
    retrieved_strategies: Iterable[dict],
) -> str:
    """Rewrite near-miss CLR citations to canonical form where resolvable.

    Args:
        text: The LLM response text (may contain a mix of canonical and
            near-miss citations).
        retrieved_strategies: The strategies served to the LLM for this
            response. Each dict must carry at least ``strategy_id`` and
            ``name``. Extra fields are ignored.

    Returns:
        Rewritten text. Canonical ``[CLR-XXX: Name]`` occurrences are
        preserved verbatim. Near-miss forms whose identifier matches a
        retrieved strategy are rewritten to canonical form. Unresolvable
        near-misses are left untouched.
    """
    if not text:
        return text

    name_by_id: dict[str, str] = {}
    for s in retrieved_strategies:
        sid = s.get("strategy_id")
        name = s.get("name")
        if sid and name:
            name_by_id[sid] = name
    if not name_by_id:
        return text

    def _replace(match: re.Match[str]) -> str:
        strategy_id = f"CLR-{match.group('num')}"
        name = name_by_id.get(strategy_id)
        if name is None:
            # Unknown identifier — leave untouched; verifier will flag it
            # as unverified and the UI will render it red. The spec calls
            # out that hallucinated ids must NOT break rendering.
            return match.group(0)
        return f"[{strategy_id}: {name}]"

    rewritten = text
    for pattern in _CLR_NEAR_MISS_PATTERNS:
        rewritten = pattern.sub(_replace, rewritten)
    return rewritten
