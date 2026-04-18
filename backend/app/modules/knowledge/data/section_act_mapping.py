"""Authoritative section → Act mapping for Australian tax-law citation validation.

Loads `section_act_mapping.yaml` (co-located) once at import and caches the
normalised result. The mapping is used by the citation verifier to detect
wrong-act-year attributions (e.g., "s 82KZM ITAA 1997" when the section
belongs to ITAA 1936). See spec 061-citation-validation for the design.

Public interface:
  - `get_section_act_mapping()` — returns the cached mapping, reloadable via
    `get_section_act_mapping.cache_clear()` in tests.
  - `normalise_section(raw)` — canonicalises a section identifier.
  - `RECOGNISED_ACTS` — closed set of Acts the loader knows about (unknown
    acts are preserved but trigger a warning).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from functools import cache
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

# Closed set of Australian tax-law Acts the loader recognises. Entries whose
# `act` value is outside this set are kept (for future extensibility) but log
# a warning at load time so an obvious typo surfaces in CI output.
RECOGNISED_ACTS: frozenset[str] = frozenset(
    {
        "ITAA 1997",
        "ITAA 1936",
        "TAA 1953",
        "GST Act 1999",
        "FBTAA 1986",
        "SGAA 1992",
        "SISA 1993",
    }
)

_YAML_PATH: Path = Path(__file__).with_name("section_act_mapping.yaml")


_PREFIX_RE = re.compile(r"^\s*(section|sec\.?|s)\s+", flags=re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")


def normalise_section(raw: str) -> str:
    """Canonical form for section identifiers used as mapping keys.

    Rules (R7 in research.md):
    - Lowercase
    - Strip outer whitespace
    - Drop leading `section `, `sec. `, `sec `, or bare `s` (each with any
      following whitespace)
    - Take only the first whitespace-separated token after the prefix.
      This drops any trailing Act suffix or prose (e.g. "s82KZM ITAA 1997"
      normalises to the same "82kzm" as "s82KZM"), which is what makes
      the mapping key comparable to both citation values and chunk
      `section_ref` fields.

    Examples:
      "Section 82KZM"        → "82kzm"
      "s 82KZM"              → "82kzm"
      "S82KZM"               → "82kzm"
      "sec. 82kzm"           → "82kzm"
      " s82KZM "             → "82kzm"
      "s328-180 ITAA 1997"   → "328-180"
      "s 82KZM ITAA 1936"    → "82kzm"
    """
    if not raw:
        return ""
    stripped = raw.strip()
    # Try prefix + whitespace first (e.g. "s 82KZM", "section 82KZM")
    after_prefix = _PREFIX_RE.sub("", stripped)
    if after_prefix == stripped and stripped and stripped[0].lower() == "s":
        # Bare "s" glued to identifier, e.g. "s82KZM" or "S82KZM"
        after_prefix = stripped[1:]
    tokens = after_prefix.split()
    section_token = tokens[0] if tokens else ""
    return section_token.lower()


@cache
def get_section_act_mapping() -> Mapping[str, dict]:
    """Return the authoritative mapping, loaded once and cached.

    Keys are normalised section identifiers (see `normalise_section`).
    Values are dicts with `act`, `display_name`, and optional `notes`.

    Raises:
        RuntimeError: on YAML parse failure, missing required fields,
            duplicate normalised keys, or missing mapping file.

    Test override:
        Call `get_section_act_mapping.cache_clear()` then monkeypatch the
        module-level `_YAML_PATH` or wrap with a fixture that replaces the
        function directly.
    """
    if not _YAML_PATH.exists():
        raise RuntimeError(
            f"Section-Act mapping YAML not found at {_YAML_PATH}. "
            "Spec 061 requires this file to exist."
        )

    try:
        raw = yaml.safe_load(_YAML_PATH.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise RuntimeError(f"Section-Act mapping YAML is malformed: {exc}") from exc

    if not isinstance(raw, dict):
        raise RuntimeError(
            f"Section-Act mapping must be a top-level object; got {type(raw).__name__}."
        )

    mapping: dict[str, dict] = {}
    for raw_key, entry in raw.items():
        if not isinstance(entry, dict):
            raise RuntimeError(
                f"Section-Act mapping entry for {raw_key!r} must be an object; "
                f"got {type(entry).__name__}."
            )
        for required in ("act", "display_name"):
            if required not in entry or not entry[required]:
                raise RuntimeError(
                    f"Section-Act mapping entry for {raw_key!r} is missing required "
                    f"field {required!r}."
                )

        normalised = normalise_section(str(raw_key))
        if not normalised:
            raise RuntimeError(f"Section-Act mapping key {raw_key!r} normalised to empty string.")
        if normalised in mapping:
            raise RuntimeError(
                f"Duplicate normalised section key {normalised!r} in mapping "
                f"(original keys collide after normalisation)."
            )

        if entry["act"] not in RECOGNISED_ACTS:
            logger.warning(
                "Section-Act mapping: entry %r has act=%r which is outside the "
                "recognised set %s — entry kept but please verify.",
                raw_key,
                entry["act"],
                sorted(RECOGNISED_ACTS),
            )

        mapping[normalised] = {
            "act": entry["act"],
            "display_name": entry["display_name"],
            "notes": entry.get("notes"),
        }

    logger.info("Section-Act mapping: loaded %d entries from %s", len(mapping), _YAML_PATH)
    return mapping
