"""Post-generation citation verification.

Checks that every section/ruling reference in an LLM response actually
exists in the retrieved context, preventing hallucinated citations.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from app.modules.knowledge.chunkers.base import (
    RULING_REF_PATTERN,
    SECTION_REF_PATTERN,
)

logger = logging.getLogger(__name__)

# Pattern for numbered citations like [1], [2], etc.
NUMBERED_CITATION_PATTERN = re.compile(r"\[(\d+)\]")


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
    """

    def verify_citations(
        self,
        response_text: str,
        retrieved_chunks: list[dict],
    ) -> CitationVerificationResult:
        """Verify all citations in the LLM response against retrieved chunks.

        For each extracted reference (section, ruling, or numbered citation):
        - If found in retrieved_chunks: mark verified=True and attach chunk metadata.
        - If NOT found: mark verified=False (ungrounded/hallucinated).

        Args:
            response_text: The full text of the LLM response.
            retrieved_chunks: List of chunk dicts from the retrieval pipeline.
                Each chunk should have keys like ``text``, ``title``, ``source_url``,
                ``source_type``, ``section_ref``, ``ruling_number``, ``score``,
                ``effective_date``.

        Returns:
            CitationVerificationResult with per-citation verification status.
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
                        )
                    )
            else:
                # Section or ruling reference -- search chunks for a match
                matching_chunk = self._find_chunk_for_reference(ref_value, retrieved_chunks)
                citation_number = len(verified_citations) + 1
                if matching_chunk is not None:
                    verified_citations.append(
                        self._build_citation_dict(
                            number=citation_number,
                            ref_value=ref_value,
                            chunk=matching_chunk,
                            verified=True,
                        )
                    )
                    verified_count += 1
                else:
                    verified_citations.append(
                        self._build_citation_dict(
                            number=citation_number,
                            ref_value=ref_value,
                            chunk=None,
                            verified=False,
                        )
                    )

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
        - Ruling references: TR 2024/1, GSTR 2000/1, TD 2024/D1, PCG 2024/1

        Returns:
            Deduplicated list of extracted citation dicts, each with
            ``type`` (``"numbered"``, ``"section"``, ``"ruling"``),
            ``value`` (the matched text), and optionally ``index`` for numbered.
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
                    }
                )

        # 2. Section references
        for match in SECTION_REF_PATTERN.finditer(text):
            ref = match.group(0).strip()
            key = f"section:{ref.lower()}"
            if key not in seen:
                seen.add(key)
                results.append(
                    {
                        "type": "section",
                        "value": ref,
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
                    }
                )

        return results

    def _find_chunk_for_reference(
        self,
        ref: str,
        chunks: list[dict],
    ) -> dict | None:
        """Search retrieved chunks for one that matches the given reference.

        Matches against chunk ``section_ref`` or ``ruling_number`` metadata
        fields, falling back to a case-insensitive substring search in the
        chunk text.

        Args:
            ref: The section or ruling reference string to look up.
            chunks: List of retrieved chunk dicts.

        Returns:
            The matching chunk dict, or ``None`` if no match is found.
        """
        ref_lower = ref.lower().strip()

        # Normalise by stripping common prefixes for flexible matching
        normalised_ref = (
            ref_lower.replace("section ", "")
            .replace("sec. ", "")
            .replace("sec ", "")
            .replace("division ", "div ")
            .replace("part ", "")
        )

        for chunk in chunks:
            # Check section_ref metadata
            section_ref = (chunk.get("section_ref") or "").lower().strip()
            if section_ref and (
                ref_lower in section_ref
                or section_ref in ref_lower
                or normalised_ref in section_ref
            ):
                return chunk

            # Check ruling_number metadata
            ruling_number = (chunk.get("ruling_number") or "").lower().strip()
            if ruling_number and (ref_lower in ruling_number or ruling_number in ref_lower):
                return chunk

        # Fallback: substring search in chunk text
        for chunk in chunks:
            chunk_text = (chunk.get("text") or "").lower()
            if ref_lower in chunk_text:
                return chunk

        return None

    @staticmethod
    def _build_citation_dict(
        number: int,
        ref_value: str,
        chunk: dict | None,
        verified: bool,
    ) -> dict:
        """Build a citation dict from a reference and optional matching chunk.

        Args:
            number: Citation display number.
            ref_value: The raw reference string from the response.
            chunk: Matching chunk dict (None if ungrounded).
            verified: Whether the citation was found in context.

        Returns:
            Dict with citation metadata suitable for API responses.
        """
        if chunk is not None:
            text = chunk.get("text", "")
            text_preview = text[:200] + "..." if len(text) > 200 else text
            return {
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

        # Ungrounded citation -- no matching chunk
        return {
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
