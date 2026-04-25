"""Post-generation citation verification.

Checks that every section/ruling reference in an LLM response actually
exists in the retrieved context, preventing hallucinated citations.

Spec 061 (`specs/061-citation-validation/`) extended the verifier with:
- Topical relevance: ruling citations require `ruling_number` metadata
  equality on a chunk to earn `match_strength=strong`. Body-text mentions
  are downgraded to `match_strength=weak` and `verified=False`.
- Act-year validation: section citations that carry an explicit Act suffix
  (e.g. "ITAA 1997") are cross-checked against an authoritative section→Act
  mapping. Mis-attributions flag as ``reason_code=WRONG_ACT_YEAR``.
- `reason_code` StrEnum + `match_strength` field on every result.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import StrEnum

from app.modules.knowledge.chunkers.base import (
    RULING_REF_PATTERN,
    SECTION_REF_PATTERN,
)
from app.modules.knowledge.data.section_act_mapping import (
    get_section_act_mapping,
    normalise_section,
)

logger = logging.getLogger(__name__)

# Pattern for numbered citations like [1], [2], etc.
NUMBERED_CITATION_PATTERN = re.compile(r"\[(\d+)\]")

# Pattern matching a section followed by an Act suffix within a short window.
# Used to associate an act-year attribution with the section citation the
# extractor saw. Captures: (section_token, act_display).
_SECTION_WITH_ACT_PATTERN = re.compile(
    r"""
    (?:[Ss](?:ection|ec\.?|)|[Dd]iv(?:ision)?|[Pp]art)\s*
    (?P<section>\d+[\w\-]*)
    \s+
    (?P<act>
        ITAA\s+(?:1997|1936)
      | TAA\s+1953
      | GST\s+Act\s+1999
      | FBTAA\s+1986
      | SGAA\s+1992
      | SISA\s+1993
    )
    """,
    re.VERBOSE,
)

_ACT_CANONICAL = {
    "ITAA 1997": "ITAA 1997",
    "ITAA 1936": "ITAA 1936",
    "TAA 1953": "TAA 1953",
    "GST Act 1999": "GST Act 1999",
    "FBTAA 1986": "FBTAA 1986",
    "SGAA 1992": "SGAA 1992",
    "SISA 1993": "SISA 1993",
}


def _canonical_act(raw: str | None) -> str | None:
    """Normalise whitespace in a captured act string, then map to canonical form."""
    if not raw:
        return None
    collapsed = re.sub(r"\s+", " ", raw.strip())
    return _ACT_CANONICAL.get(collapsed, collapsed)


class CitationReasonCode(StrEnum):
    """Machine-readable reason attached to each citation verification result.

    Spec 061 FR-012 — extensible taxonomy readable in audit logs, DB JSONB,
    and downstream UI badges without further parsing.
    """

    STRONG_MATCH = "strong_match"
    """Metadata equality on the chunk's ruling_number / section_ref field,
    or positional match for numbered citations. Only reason_code compatible
    with ``verified=True``."""

    WEAK_MATCH_BODY_ONLY = "weak_match_body_only"
    """Citation identifier appears in a chunk's body text but not in its
    authoritative metadata. Reported as ``verified=False`` — body mentions
    are evidence of relationship, not authority."""

    WEAK_MATCH_NONE = "weak_match_none"
    """Citation identifier appears nowhere in retrieved chunks — neither
    metadata nor body. Classic hallucination signal."""

    WRONG_ACT_YEAR = "wrong_act_year"
    """Section citation attributed to an Act that the authoritative
    section→Act mapping records as incorrect (e.g., ``s 82KZM ITAA 1997``
    when the section belongs to ITAA 1936)."""

    UNKNOWN_SECTION = "unknown_section"
    """Section citation that is not present in the authoritative mapping.
    Act-year check is skipped (FR-006); downstream match logic still runs."""

    NO_CITATIONS = "no_citations"
    """Response contained nothing the extractor recognised. Emitted at the
    verification-result aggregate level, not per citation."""


__all__ = ["CitationReasonCode", "CitationVerificationResult", "CitationVerifier"]


@dataclass
class CitationVerificationResult:
    """Result of verifying citations in an LLM response against retrieved chunks.

    Attributes:
        citations: List of citation dicts, each with verification metadata.
        ungrounded_count: Number of citations not found in retrieved context.
        verification_rate: Fraction of citations that are grounded (0.0 to 1.0).
    """

    citations: list[dict] = field(default_factory=list)
    ungrounded_count: int = 0
    verification_rate: float = 1.0


class CitationVerifier:
    """Verifies that citations in an LLM response are grounded in retrieved context.

    Extracts section references, ruling references, and numbered citations
    from the response text, then checks each against the retrieved chunks
    to determine whether the citation is grounded or hallucinated.

    Spec 061 strengthens the match logic: rulings require metadata equality
    for ``verified=True``; sections with explicit Act suffixes are cross-
    checked against an authoritative mapping to catch wrong-act-year
    attributions.
    """

    def verify_citations(
        self,
        response_text: str,
        retrieved_chunks: list[dict],
    ) -> CitationVerificationResult:
        """Verify all citations in the LLM response against retrieved chunks.

        Returns:
            CitationVerificationResult with per-citation verification status,
            where each citation dict carries the Spec 061 fields
            ``match_strength``, ``matched_by``, ``reason_code`` alongside the
            existing ``verified`` / ``section_ref`` / etc.
        """
        extracted = self._extract_citations_from_response(response_text)

        if not extracted:
            return CitationVerificationResult(
                citations=[],
                ungrounded_count=0,
                verification_rate=1.0,
            )

        verified_citations: list[dict] = []
        verified_count = 0

        for ref_info in extracted:
            ref_type = ref_info["type"]
            ref_value = ref_info["value"]

            if ref_type == "numbered":
                # Numbered citations [1], [2] map to chunk indices (1-based)
                chunk_index = ref_info.get("index", 0) - 1
                if 0 <= chunk_index < len(retrieved_chunks):
                    chunk = retrieved_chunks[chunk_index]
                    verified_citations.append(
                        self._build_citation_dict(
                            number=ref_info["index"],
                            ref_value=ref_value,
                            chunk=chunk,
                            verified=True,
                            match_strength="strong",
                            matched_by="numbered_index",
                            reason_code=CitationReasonCode.STRONG_MATCH,
                        )
                    )
                    verified_count += 1
                else:
                    verified_citations.append(
                        self._build_citation_dict(
                            number=ref_info.get("index", 0),
                            ref_value=ref_value,
                            chunk=None,
                            verified=False,
                            match_strength="none",
                            matched_by="unverified",
                            reason_code=CitationReasonCode.WEAK_MATCH_NONE,
                        )
                    )
                continue

            # Section or ruling reference
            match = self._find_chunk_for_reference(
                ref_type=ref_type,
                ref=ref_value,
                act_year=ref_info.get("act_year"),
                chunks=retrieved_chunks,
            )
            citation_number = len(verified_citations) + 1

            verified_citations.append(
                self._build_citation_dict(
                    number=citation_number,
                    ref_value=ref_value,
                    chunk=match.chunk,
                    verified=match.verified,
                    match_strength=match.match_strength,
                    matched_by=match.matched_by,
                    reason_code=match.reason_code,
                )
            )
            if match.verified:
                verified_count += 1

        total = len(verified_citations)
        ungrounded = total - verified_count
        rate = verified_count / total if total > 0 else 1.0

        return CitationVerificationResult(
            citations=verified_citations,
            ungrounded_count=ungrounded,
            verification_rate=rate,
        )

    def _extract_citations_from_response(self, text: str) -> list[dict]:
        """Extract all citation references from the LLM response text.

        Finds:
        - Numbered citations: [1], [2], etc.
        - Section references: s109D, section 104-10, Division 7A, Part 3-1
          (with optional act-year suffix captured separately per FR-004)
        - Ruling references: TR 2024/1, GSTR 2000/1, TD 2024/D1, PCG 2024/1

        Returns:
            Deduplicated list of extracted citation dicts, each with
            ``type`` (``"numbered"``, ``"section"``, ``"ruling"``),
            ``value`` (the matched text), ``act_year`` (captured suffix
            for section citations, else None), and optionally ``index``
            for numbered.
        """
        seen: set[str] = set()
        results: list[dict] = []

        # 1. Numbered citations [N]
        for match in NUMBERED_CITATION_PATTERN.finditer(text):
            num = int(match.group(1))
            key = f"numbered:{num}"
            if key not in seen:
                seen.add(key)
                results.append(
                    {
                        "type": "numbered",
                        "value": match.group(0),
                        "index": num,
                        "act_year": None,
                    }
                )

        # 2a. Sections with an Act suffix — capture act_year for these.
        section_to_act: dict[str, str] = {}
        for sw_match in _SECTION_WITH_ACT_PATTERN.finditer(text):
            section_token = sw_match.group("section").lower()
            act = _canonical_act(sw_match.group("act"))
            if act:
                section_to_act[section_token] = act

        # 2b. All section references (with or without act suffix).
        for match in SECTION_REF_PATTERN.finditer(text):
            ref = match.group(0).strip()
            key = f"section:{ref.lower()}"
            if key in seen:
                continue
            seen.add(key)
            # Pick up any act-year captured for this section token.
            normalised = normalise_section(ref)
            act_year = section_to_act.get(normalised)
            results.append(
                {
                    "type": "section",
                    "value": ref,
                    "act_year": act_year,
                }
            )

        # 3. Ruling references
        for match in RULING_REF_PATTERN.finditer(text):
            ref = match.group(0).strip()
            key = f"ruling:{ref.lower()}"
            if key not in seen:
                seen.add(key)
                results.append(
                    {
                        "type": "ruling",
                        "value": ref,
                        "act_year": None,
                    }
                )

        return results

    def _find_chunk_for_reference(
        self,
        *,
        ref_type: str,
        ref: str,
        act_year: str | None,
        chunks: list[dict],
    ) -> _MatchResult:
        """Locate a chunk matching the given citation and classify the match.

        Decision order:
        1. For ruling citations, require `chunk.ruling_number` metadata equality
           (case-insensitive, whitespace-collapsed) for `match_strength=strong`.
           Body-text mentions fall to `match_strength=weak` with `verified=False`.
        2. For section citations, first run the act-year check (if applicable).
           Then try metadata equality on `section_ref`, then body-text fallback.
        3. If nothing matches anywhere → `match_strength=none`,
           `reason_code=WEAK_MATCH_NONE`, `verified=False`.
        """
        if ref_type == "ruling":
            return self._match_ruling(ref, chunks)
        if ref_type == "section":
            return self._match_section(ref, act_year, chunks)
        # Defensive — shouldn't reach here for known types.
        return _MatchResult(
            chunk=None,
            verified=False,
            match_strength="none",
            matched_by="unverified",
            reason_code=CitationReasonCode.WEAK_MATCH_NONE,
        )

    def _match_ruling(self, ref: str, chunks: list[dict]) -> _MatchResult:
        """Ruling-specific match: metadata equality required for strong."""
        ref_norm = _normalise_ruling(ref)

        # Strong: ruling_number metadata equality
        for chunk in chunks:
            chunk_ruling = _normalise_ruling(chunk.get("ruling_number") or "")
            if chunk_ruling and chunk_ruling == ref_norm:
                return _MatchResult(
                    chunk=chunk,
                    verified=True,
                    match_strength="strong",
                    matched_by="ruling_number",
                    reason_code=CitationReasonCode.STRONG_MATCH,
                )

        # Weak: body-text mention
        ref_lower = ref.lower()
        for chunk in chunks:
            body = (chunk.get("text") or "").lower()
            if ref_lower in body or ref_norm in _normalise_ruling(body):
                return _MatchResult(
                    chunk=chunk,
                    verified=False,
                    match_strength="weak",
                    matched_by="body_text",
                    reason_code=CitationReasonCode.WEAK_MATCH_BODY_ONLY,
                )

        # None: nowhere
        return _MatchResult(
            chunk=None,
            verified=False,
            match_strength="none",
            matched_by="unverified",
            reason_code=CitationReasonCode.WEAK_MATCH_NONE,
        )

    def _match_section(self, ref: str, act_year: str | None, chunks: list[dict]) -> _MatchResult:
        """Section-specific match: act-year gate first, then metadata/body."""
        normalised_section = normalise_section(ref)
        mapping = get_section_act_mapping()

        # Act-year gate: when the citation carries an Act attribution AND the
        # section is in our authoritative mapping, we require them to agree.
        if act_year and normalised_section in mapping:
            expected_act = mapping[normalised_section]["act"]
            if act_year != expected_act:
                # Wrong-act-year — short-circuit to failure. Surface the chunk
                # if we can find one (for debugging), but the result is
                # verified=False regardless.
                chunk = self._first_section_match(normalised_section, chunks)
                return _MatchResult(
                    chunk=chunk,
                    verified=False,
                    match_strength="none",
                    matched_by="unverified",
                    reason_code=CitationReasonCode.WRONG_ACT_YEAR,
                )

        # Strong: section_ref metadata equality (normalised both sides)
        for chunk in chunks:
            chunk_section = normalise_section(chunk.get("section_ref") or "")
            if chunk_section and chunk_section == normalised_section:
                return _MatchResult(
                    chunk=chunk,
                    verified=True,
                    match_strength="strong",
                    matched_by="section_ref",
                    reason_code=CitationReasonCode.STRONG_MATCH,
                )

        # Weak: body-text mention of the section token.
        # NOTE: For sections (unlike rulings — see FR-001..FR-003 which are
        # ruling-scoped), body-text matches still count as verified=True.
        # A chunk that discusses s 82KZM in prose is a valid authoritative
        # source for that section, even if the chunk's section_ref metadata
        # is a different adjacent section. We surface the weak distinction
        # via match_strength / reason_code for observability.
        ref_lower = ref.lower()
        for chunk in chunks:
            body = (chunk.get("text") or "").lower()
            if ref_lower in body or normalised_section in body:
                return _MatchResult(
                    chunk=chunk,
                    verified=True,
                    match_strength="weak",
                    matched_by="body_text",
                    reason_code=CitationReasonCode.WEAK_MATCH_BODY_ONLY,
                )

        # None: nowhere
        return _MatchResult(
            chunk=None,
            verified=False,
            match_strength="none",
            matched_by="unverified",
            reason_code=CitationReasonCode.WEAK_MATCH_NONE,
        )

    @staticmethod
    def _first_section_match(normalised_section: str, chunks: list[dict]) -> dict | None:
        """Best-effort chunk pick for a section, used only for debugging context
        on wrong-act-year failures."""
        for chunk in chunks:
            chunk_section = normalise_section(chunk.get("section_ref") or "")
            if chunk_section == normalised_section:
                return chunk
        return None

    @staticmethod
    def _build_citation_dict(
        *,
        number: int,
        ref_value: str,
        chunk: dict | None,
        verified: bool,
        match_strength: str,
        matched_by: str,
        reason_code: CitationReasonCode,
    ) -> dict:
        """Build a citation dict from a reference and optional matching chunk.

        Spec 061 FR-012: additive fields ``match_strength``, ``matched_by``,
        ``reason_code`` appear on every returned citation.
        """
        if chunk is not None:
            text = chunk.get("text", "")
            text_preview = text[:200] + "..." if len(text) > 200 else text
            base = {
                "number": number,
                "title": chunk.get("title"),
                "url": chunk.get("source_url", ""),
                "source_type": chunk.get("source_type", "unknown"),
                "section_ref": chunk.get("section_ref"),
                "effective_date": chunk.get("effective_date"),
                "text_preview": text_preview,
                "score": chunk.get("score", 0.0),
                "verified": verified,
            }
        else:
            base = {
                "number": number,
                "title": None,
                "url": "",
                "source_type": "unknown",
                "section_ref": ref_value,
                "effective_date": None,
                "text_preview": "",
                "score": 0.0,
                "verified": verified,
            }
        base["match_strength"] = match_strength
        base["matched_by"] = matched_by
        base["reason_code"] = reason_code.value
        return base

    # -----------------------------------------------------------------
    # Spec 060 — Tax strategy citations [CLR-XXX: Name]
    # -----------------------------------------------------------------

    # Single canonical citation form per spec 060 FR-020 clarification.
    _CLR_PATTERN: re.Pattern[str] = re.compile(r"\[CLR-(?P<num>\d{3,5}):\s*(?P<name>[^\]]+)\]")

    # Name drift threshold per spec 060 clarification. Normalised Levenshtein
    # distance (length-adjusted) ≥ this value flips a citation from verified
    # to partially_verified when the identifier matches.
    _NAME_DRIFT_THRESHOLD: float = 0.30

    def extract_strategy_citations(self, text: str) -> list[dict]:
        """Parse every ``[CLR-XXX: Name]`` occurrence in the text.

        Does NOT resolve against retrieved strategies — that's what
        verify_strategy_citations() does. This returns raw parse hits so
        callers can also count / inspect them.

        Returns:
            List of dicts ``{strategy_id, name, span}`` in source order.
        """
        results: list[dict] = []
        for match in self._CLR_PATTERN.finditer(text):
            results.append(
                {
                    "strategy_id": f"CLR-{match.group('num')}",
                    "name": match.group("name").strip(),
                    "span": match.span(),
                }
            )
        return results

    def verify_strategy_citations(
        self,
        response_text: str,
        retrieved_strategies: list[dict],
    ) -> list[dict]:
        """Classify each ``[CLR-XXX]`` citation against the retrieved set.

        Classification (FR-020):
        - verified: exact ``strategy_id`` match AND name drift < 0.30
        - partially_verified: ``strategy_id`` match but name drift ≥ 0.30
        - unverified: no ``strategy_id`` match

        Args:
            response_text: The LLM assistant message text.
            retrieved_strategies: The set of strategies served to the LLM for
                this response. Each item is a dict with at least
                ``strategy_id`` and ``name``. Additional fields are preserved
                in the output for UI hydration.

        Returns:
            One result dict per citation found in source order, each carrying
            ``strategy_id``, ``cited_name``, ``status`` ∈
            {verified, partially_verified, unverified}, ``name_drift`` (float,
            None when no id match), and a reference to the matched strategy
            dict (or None) under ``strategy``.
        """
        citations = self.extract_strategy_citations(response_text)
        if not citations:
            return []

        by_id: dict[str, dict] = {
            s["strategy_id"]: s for s in retrieved_strategies if s.get("strategy_id")
        }

        results: list[dict] = []
        for citation in citations:
            strategy_id = citation["strategy_id"]
            cited_name = citation["name"]
            match = by_id.get(strategy_id)

            if match is None:
                results.append(
                    {
                        "strategy_id": strategy_id,
                        "cited_name": cited_name,
                        "status": "unverified",
                        "name_drift": None,
                        "strategy": None,
                        "span": citation["span"],
                    }
                )
                continue

            stored_name = (match.get("name") or "").strip()
            drift = _normalised_levenshtein(cited_name, stored_name)
            if drift < self._NAME_DRIFT_THRESHOLD:
                status = "verified"
            else:
                status = "partially_verified"

            results.append(
                {
                    "strategy_id": strategy_id,
                    "cited_name": cited_name,
                    "status": status,
                    "name_drift": drift,
                    "strategy": match,
                    "span": citation["span"],
                }
            )

        return results


def _normalised_levenshtein(a: str, b: str) -> float:
    """Length-normalised Levenshtein distance on lower-cased, whitespace-
    collapsed strings. Returns a value in [0.0, 1.0].

    0.0 means identical. 1.0 means completely different. Used for the
    Spec-060 name-drift threshold.
    """
    norm_a = re.sub(r"\s+", " ", a.strip().lower())
    norm_b = re.sub(r"\s+", " ", b.strip().lower())
    if norm_a == norm_b:
        return 0.0
    if not norm_a or not norm_b:
        return 1.0

    # Classic dynamic-programming Levenshtein. Corpus is short (strategy
    # names < 200 chars by FR-001), so an O(n*m) loop is fine.
    len_a, len_b = len(norm_a), len(norm_b)
    prev = list(range(len_b + 1))
    curr = [0] * (len_b + 1)
    for i in range(1, len_a + 1):
        curr[0] = i
        for j in range(1, len_b + 1):
            cost = 0 if norm_a[i - 1] == norm_b[j - 1] else 1
            curr[j] = min(
                prev[j] + 1,  # deletion
                curr[j - 1] + 1,  # insertion
                prev[j - 1] + cost,  # substitution
            )
        prev, curr = curr, prev
    distance = prev[len_b]
    max_len = max(len_a, len_b)
    return distance / max_len if max_len else 0.0


@dataclass
class _MatchResult:
    """Internal return shape of the match helpers."""

    chunk: dict | None
    verified: bool
    match_strength: str
    matched_by: str
    reason_code: CitationReasonCode


def _normalise_ruling(raw: str) -> str:
    """Normalise a ruling identifier for equality comparison.

    Collapses whitespace, lowercases. Preserves the slash and year.
    """
    if not raw:
        return ""
    return re.sub(r"\s+", " ", raw.strip().lower())
