#!/usr/bin/env python3
"""One-off: extract tax strategy content from Tax Fitness PDFs into YAML.

Reads every PDF under `--source-dir` (default: the Tax Fitness Strategy
folder on Suren's disk), sends each PDF to Claude for structured extraction,
and writes one YAML file per strategy under `--output-dir` (default:
backend/app/modules/tax_strategies/data/strategies/).

The YAMLs are the source of truth committed to git. `seed_from_strategies_dir`
reads them at runtime to create TaxStrategy rows in both local and prod
databases — that's how prod Postgres gets the same content as local without
a DB dump.

Idempotent: skips PDFs whose target YAML already exists unless `--force` is
passed. Safe to re-run while iterating on a subset.

Usage:
    # Extract a pilot set of 5 strategies:
    uv run python scripts/import_tax_strategies_from_pdfs.py --pilot

    # Extract every PDF (~$12 in Anthropic API charges):
    uv run python scripts/import_tax_strategies_from_pdfs.py

    # Re-extract specific IDs:
    uv run python scripts/import_tax_strategies_from_pdfs.py --ids CLR-012,CLR-241 --force
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import anthropic
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings  # noqa: E402
from app.modules.tax_strategies.schemas import ALLOWED_CATEGORIES  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


DEFAULT_SOURCE_DIR = Path("/Users/suren/KR8IT/projects/Personal/Clairo docs/Tax Fitness Strategy")
DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent / "app/modules/tax_strategies/data/strategies"

# 5 pilot strategies — mix of categories so we can eyeball quality across
# the breadth of the catalogue before widening.
PILOT_IDS: frozenset[str] = frozenset({"CLR-012", "CLR-241", "CLR-085", "CLR-222", "CLR-149"})

# Map "N. Category Name (done ...)" folder → ALLOWED_CATEGORIES value.
# The PDFs list their own category inside the document but this map is the
# authoritative fallback when the PDF text is ambiguous.
FOLDER_CATEGORY_MAP: dict[str, str] = {
    "1. Business": "Business",
    "2. Recommendations": "Recommendations",
    "3. Employees": "Employees",
    "4. ATO obligations": "ATO_obligations",
    "5. Rental properties": "Rental_properties",
    "6. Investors and retirees": "Investors_retirees",
    "7. Business structures": "Business_structures",
    "8. SMSF": "SMSF",
}


@dataclass(frozen=True)
class PdfSource:
    """A single PDF on disk ready to be extracted."""

    strategy_id: str  # "CLR-012" (3+ digit, zero-padded)
    source_number: int  # 12 — raw number from filename
    fallback_category: str  # from folder name
    pdf_path: Path

    @property
    def output_filename(self) -> str:
        return f"{self.strategy_id}.yaml"


# Filename example: "Concessional superannuation contributions - 12.pdf"
# Variants: `"Bona fide travel allowance -15.pdf"`, double-space, etc.
_FILENAME_RE = re.compile(r"^(?P<name>.+?)\s*-\s*(?P<num>\d+)\.pdf$")


def _folder_to_category(folder_name: str) -> str | None:
    """Map the category folder stem to an ALLOWED_CATEGORIES string."""
    for prefix, cat in FOLDER_CATEGORY_MAP.items():
        if folder_name.startswith(prefix):
            return cat
    return None


def discover_pdfs(source_dir: Path) -> list[PdfSource]:
    """Walk the source directory and yield one PdfSource per PDF found."""
    found: list[PdfSource] = []
    seen_ids: dict[str, Path] = {}
    for category_dir in sorted(source_dir.iterdir()):
        if not category_dir.is_dir():
            continue
        category = _folder_to_category(category_dir.name)
        if category is None:
            logger.warning("skipping folder %r — no matching category", category_dir.name)
            continue
        for pdf_path in sorted(category_dir.glob("*.pdf")):
            m = _FILENAME_RE.match(pdf_path.name)
            if not m:
                logger.warning(
                    "skipping %s — filename doesn't match '<name> - <num>.pdf'",
                    pdf_path.name,
                )
                continue
            num = int(m.group("num"))
            strategy_id = f"CLR-{num:03d}"
            if strategy_id in seen_ids:
                logger.warning(
                    "duplicate strategy id %s at %s (already seen at %s) — keeping first",
                    strategy_id,
                    pdf_path,
                    seen_ids[strategy_id],
                )
                continue
            seen_ids[strategy_id] = pdf_path
            found.append(
                PdfSource(
                    strategy_id=strategy_id,
                    source_number=num,
                    fallback_category=category,
                    pdf_path=pdf_path,
                )
            )
    return found


# ----------------------------------------------------------------------
# Claude extraction
# ----------------------------------------------------------------------


EXTRACTION_SYSTEM = """You extract structured data from an Australian tax planning strategy one-pager PDF. The PDF follows a fixed template with sections: Strategy (name), Category (comma-separated), Implementation advice (numbered steps), Strategy explanation (prose), and optionally Deductions / Tax payable / Tax savings figures.

CRITICAL RULE — NO HALLUCINATIONS: Every value you include MUST be directly supported by text that literally appears in this PDF. If a field is not explicitly stated, use null (for scalars) or [] (for arrays). Do NOT use your training knowledge of Australian tax law to fill gaps. This file will be committed to a knowledge base used in production — inventing a threshold, a ruling number, or an eligibility band corrupts the index.

Return a single JSON object with exactly these keys — nothing else, no preamble, no markdown fences.

{
  "name": "<strategy name, verbatim from the Strategy header>",
  "categories": ["<subset of the 8 allowed categories — must appear on the PDF's Category line>"],
  "implementation_text": "<the Implementation advice section, verbatim numbered list. EMPTY STRING if the PDF's Implementation advice is blank, missing, or only a placeholder. DO NOT synthesise steps.>",
  "explanation_text": "<the Strategy explanation section, prose verbatim — preserve every dollar figure, percentage, date, and threshold>",
  "ato_sources": ["<ATO primary source references that literally appear in the PDF text — e.g. 'ITAA 1997 s 290-25', 'TR 2010/1', 'Div 87'. Do NOT include references you only know from your training.>"],
  "case_refs": ["<case citations that literally appear in the PDF — e.g. 'Smith v FCT (2019)'. Empty if none appear.>"],
  "entity_types": ["<subset of sole_trader, partnership, company, trust, smsf, individual — ONLY types literally named or unambiguously required by the PDF text (e.g. an SMSF-titled strategy implies smsf). Empty if not specified.>"],
  "income_band_min": <integer AUD, ONLY if the PDF literally states a minimum taxpayer income threshold for eligibility; null otherwise>,
  "income_band_max": <integer AUD, ONLY if the PDF literally states a maximum taxpayer income threshold for eligibility; null otherwise>,
  "turnover_band_min": <integer AUD, ONLY if the PDF literally states a minimum business turnover threshold; null otherwise>,
  "turnover_band_max": <integer AUD, ONLY if the PDF literally states a maximum business turnover threshold; null otherwise>,
  "age_min": <integer years, ONLY if the PDF literally states a minimum age for eligibility; null otherwise>,
  "age_max": <integer years, ONLY if the PDF literally states a maximum age for eligibility; null otherwise>,
  "industry_triggers": ["<short lowercase tags ONLY for industries literally named in the PDF (e.g. 'farmers', 'professional_services'). Empty if broadly applicable or unspecified.>"],
  "financial_impact_type": ["<subset of deduction, concession, offset, timing, structure, rebate, exemption — only types directly supported by explicit PDF language (e.g. 'tax-deductible' → deduction).>"],
  "keywords": ["<5-15 lowercase keywords an accountant might search. Keywords are generated by you (not asserted facts) — they're search hints, not claims.>"]
}

Allowed categories (use EXACTLY these spellings): Business, Recommendations, Employees, ATO_obligations, Rental_properties, Investors_retirees, Business_structures, SMSF.

Disambiguation guidance:
- "Thresholds in the strategy content" (e.g. "$30,000 annual cap on contributions") are part of the strategy prose — they belong in implementation_text/explanation_text, NOT in the eligibility band fields. The band fields are ONLY for who is eligible for the strategy itself (e.g. "turnover < $10m" → turnover_band_max: 10000000).
- "Tips when writing off bad debts" style lists in explanation_text are fine as prose; do not split into implementation steps unless the PDF literally has them in the Implementation advice section.
- NEVER include the "Deductions $X", "Tax payable before/after", marketing language, or the STP / Success Tax Professionals branding.

Output ONLY the JSON object."""


# Verification pass — re-reads the PDF with the Pass 1 output and nulls any
# value it can't justify with a literal quote.
VERIFICATION_SYSTEM = """You are verifying a structured extraction of an Australian tax strategy PDF. The extraction was produced by an earlier LLM pass. Your job is to detect hallucinations by requiring a literal quote from the PDF for every non-empty value — and null any value you can't justify.

Return a single JSON object with exactly these keys — nothing else:

{
  "verified": {
    "<field_name>": {"quote": "<verbatim PDF text span supporting the value>", "ok": true}
  },
  "rejected": {
    "<field_name>": {"reason": "<why this value is not supported by the PDF>"}
  },
  "cleaned": <the extraction with every rejected value replaced: scalars → null, lists → empty array>
}

Rules:
- For every non-null scalar and non-empty list IN THE EXTRACTION, you must EITHER supply a supporting quote from the PDF under `verified`, OR move the field into `rejected` and null/empty it in `cleaned`.
- Fields that are already null / [] in the extraction don't need verification — echo them as-is in `cleaned`.
- A quote is verbatim text from the PDF. Paraphrases do not count.
- For `keywords`, no quote is required — they're generated search hints, not asserted facts. Always echo them in `cleaned`.
- For `categories`, the supporting quote must be the PDF's Category line.
- For scalar bands (income_band_*, turnover_band_*, age_*), the quote must include an explicit threshold statement (e.g. "businesses with turnover less than $10 million"). Thresholds inside the strategy prose do NOT count — only eligibility thresholds for the strategy.
- For entity_types, a literal mention ("company", "SMSF", "trust") or unambiguous implication (strategy title says "SMSF") counts.
- Conservative principle: when in doubt, reject. We prefer a null over a hallucination.

Output ONLY the JSON object."""


def _build_user_message(pdf_bytes: bytes, fallback_category: str) -> list[dict]:
    """Construct the multi-modal content blocks for the Anthropic call.

    The PDF is passed as a base64 document block — Claude reads layout,
    so we don't need pypdf-level text extraction. `fallback_category` is
    attached as a hint but the model is instructed to trust the PDF's own
    Category line first.
    """
    b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")
    return [
        {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": b64,
            },
        },
        {
            "type": "text",
            "text": (
                "Extract the strategy from this PDF according to the system "
                "prompt's schema.\n\n"
                f"Fallback category (from the parent folder, use only if the "
                f"PDF's Category line is unclear): {fallback_category}\n\n"
                "Return the JSON object only."
            ),
        },
    ]


def _call_anthropic(
    client: anthropic.Anthropic,
    pdf_bytes: bytes,
    fallback_category: str,
    model: str,
) -> dict[str, Any]:
    """Pass 1: literal extraction. Returns parsed JSON dict."""
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=EXTRACTION_SYSTEM,
        messages=[{"role": "user", "content": _build_user_message(pdf_bytes, fallback_category)}],
    )
    return _parse_json_response(response)


def _call_verification(
    client: anthropic.Anthropic,
    pdf_bytes: bytes,
    pass1_json: dict[str, Any],
    model: str,
) -> dict[str, Any]:
    """Pass 2: verification. Re-reads the PDF alongside the Pass 1 output
    and returns {verified, rejected, cleaned}. Values that can't be quoted
    from the PDF are moved into `rejected` and nulled in `cleaned`.
    """
    b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")
    user_content = [
        {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": b64,
            },
        },
        {
            "type": "text",
            "text": (
                "Verify this extraction against the PDF. Return the JSON "
                "object defined in the system prompt.\n\n"
                f"Extraction to verify:\n{json.dumps(pass1_json, indent=2)}"
            ),
        },
    ]
    response = client.messages.create(
        model=model,
        max_tokens=6144,
        system=VERIFICATION_SYSTEM,
        messages=[{"role": "user", "content": user_content}],
    )
    return _parse_json_response(response)


def _parse_json_response(response: Any) -> dict[str, Any]:
    """Extract JSON from an Anthropic messages response, tolerating fences."""
    text = ""
    for block in response.content:
        t = getattr(block, "text", None)
        if t:
            text += t
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z]*\n?", "", stripped)
        stripped = re.sub(r"\n?```\s*$", "", stripped)
    return json.loads(stripped)


# ----------------------------------------------------------------------
# Extraction pipeline
# ----------------------------------------------------------------------


def _sanitize_categories(raw: list[str] | None, fallback: str) -> list[str]:
    """Filter to ALLOWED_CATEGORIES, always including the folder fallback."""
    out: list[str] = []
    for c in raw or []:
        if c in ALLOWED_CATEGORIES and c not in out:
            out.append(c)
    if fallback not in out:
        out.append(fallback)
    return out


def _build_yaml_payload(source: PdfSource, extracted: dict[str, Any]) -> dict[str, Any]:
    """Produce the final YAML-ready dict for one strategy.

    Applies light cleanup on top of the LLM output so downstream seeders
    can trust the shape (categories filtered, source_ref synthesised from
    the filename number).
    """
    categories = _sanitize_categories(extracted.get("categories"), source.fallback_category)
    return {
        "strategy_id": source.strategy_id,
        "source_ref": f"STP-{source.source_number:03d}",
        "name": extracted.get("name", "").strip(),
        "categories": categories,
        "implementation_text": extracted.get("implementation_text", "").strip(),
        "explanation_text": extracted.get("explanation_text", "").strip(),
        "ato_sources": list(extracted.get("ato_sources") or []),
        "case_refs": list(extracted.get("case_refs") or []),
        "entity_types": list(extracted.get("entity_types") or []),
        "income_band_min": extracted.get("income_band_min"),
        "income_band_max": extracted.get("income_band_max"),
        "turnover_band_min": extracted.get("turnover_band_min"),
        "turnover_band_max": extracted.get("turnover_band_max"),
        "age_min": extracted.get("age_min"),
        "age_max": extracted.get("age_max"),
        "industry_triggers": list(extracted.get("industry_triggers") or []),
        "financial_impact_type": list(extracted.get("financial_impact_type") or []),
        "keywords": list(extracted.get("keywords") or []),
    }


def extract_one(
    source: PdfSource,
    client: anthropic.Anthropic,
    model: str,
    output_dir: Path,
    force: bool,
    skip_verification: bool = False,
) -> bool:
    """Extract a single PDF into YAML. Two passes by default:
      1. Literal extraction (strict prompt, no hallucinations).
      2. Verification — Claude re-reads the PDF with the Pass 1 output and
         rejects any value it can't quote from the PDF. Rejected values are
         nulled/emptied in the final YAML.

    Also writes a sibling `CLR-XXX.audit.yaml` with the supporting quotes
    for every retained value plus the list of rejected values + reasons.
    The audit file is listed in .gitignore — local-only by design.

    Returns True if a YAML was written.
    """
    out_path = output_dir / source.output_filename
    audit_path = output_dir / f"{source.strategy_id}.audit.yaml"
    if out_path.exists() and not force:
        logger.info("skip %s (exists — pass --force to re-extract)", source.strategy_id)
        return False

    logger.info("extracting %s from %s (pass 1)", source.strategy_id, source.pdf_path.name)
    pdf_bytes = source.pdf_path.read_bytes()
    try:
        pass1 = _call_anthropic(client, pdf_bytes, source.fallback_category, model=model)
    except Exception:
        logger.exception("pass 1 failed for %s", source.strategy_id)
        return False

    cleaned = pass1
    audit: dict[str, Any] | None = None
    if not skip_verification:
        logger.info("verifying %s (pass 2)", source.strategy_id)
        try:
            verification = _call_verification(client, pdf_bytes, pass1, model=model)
            cleaned = verification.get("cleaned", pass1)
            audit = {
                "strategy_id": source.strategy_id,
                "pdf_path": str(source.pdf_path),
                "verified": verification.get("verified", {}),
                "rejected": verification.get("rejected", {}),
                "pass1_raw": pass1,
            }
            if audit["rejected"]:
                logger.warning(
                    "%s: %d field(s) rejected by verifier — see %s",
                    source.strategy_id,
                    len(audit["rejected"]),
                    audit_path.name,
                )
        except Exception:
            logger.exception(
                "verification failed for %s — keeping pass 1 output "
                "(set --skip-verification to avoid this)",
                source.strategy_id,
            )

    payload = _build_yaml_payload(source, cleaned)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        yaml.safe_dump(
            payload,
            sort_keys=False,
            allow_unicode=True,
            width=100,
            default_flow_style=False,
        ),
        encoding="utf-8",
    )
    if audit is not None:
        audit_path.write_text(
            yaml.safe_dump(audit, sort_keys=False, allow_unicode=True, width=100),
            encoding="utf-8",
        )
    logger.info("wrote %s", out_path)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--pilot",
        action="store_true",
        help=f"Only extract the pilot set: {sorted(PILOT_IDS)}",
    )
    parser.add_argument(
        "--ids",
        default="",
        help="Comma-separated strategy ids (e.g. CLR-012,CLR-241). Overrides --pilot.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of PDFs to process (after filtering). Handy for smoke tests.",
    )
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-6",
        help="Anthropic model id (default: claude-sonnet-4-6).",
    )
    parser.add_argument("--force", action="store_true", help="Re-extract even if YAML exists.")
    parser.add_argument("--dry-run", action="store_true", help="List PDFs but don't call the API.")
    parser.add_argument(
        "--skip-verification",
        action="store_true",
        help=(
            "Skip the Pass 2 verification call. Saves ~50%% cost but any "
            "hallucination from Pass 1 will land in the YAML unchecked. "
            "Default behaviour is to verify."
        ),
    )
    args = parser.parse_args()

    if not args.source_dir.exists():
        logger.error("source dir %s does not exist", args.source_dir)
        return 1

    all_sources = discover_pdfs(args.source_dir)
    logger.info("discovered %d PDFs", len(all_sources))

    if args.ids:
        wanted = {s.strip().upper() for s in args.ids.split(",") if s.strip()}
        sources = [s for s in all_sources if s.strategy_id in wanted]
        missing = wanted - {s.strategy_id for s in sources}
        if missing:
            logger.warning("requested ids not found: %s", sorted(missing))
    elif args.pilot:
        sources = [s for s in all_sources if s.strategy_id in PILOT_IDS]
        missing = PILOT_IDS - {s.strategy_id for s in sources}
        if missing:
            logger.warning("pilot ids not found: %s", sorted(missing))
    else:
        sources = all_sources

    if args.limit is not None:
        sources = sources[: args.limit]

    if args.dry_run:
        for s in sources:
            logger.info("would extract %s from %s", s.strategy_id, s.pdf_path)
        logger.info("dry-run: %d PDFs would be processed", len(sources))
        return 0

    settings = get_settings()
    api_key = settings.anthropic.api_key.get_secret_value()
    if not api_key:
        logger.error("ANTHROPIC_API_KEY is not configured (.env / .env.local)")
        return 2

    client = anthropic.Anthropic(api_key=api_key)
    written = 0
    for i, source in enumerate(sources, start=1):
        logger.info("[%d/%d] %s", i, len(sources), source.strategy_id)
        if extract_one(
            source,
            client,
            args.model,
            args.output_dir,
            args.force,
            skip_verification=args.skip_verification,
        ):
            written += 1

    logger.info("done — %d/%d PDFs extracted to %s", written, len(sources), args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
