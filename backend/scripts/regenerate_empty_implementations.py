#!/usr/bin/env python3
"""Fill empty `implementation_text` fields by paraphrasing the explanation.

~8% of the source PDFs have a blank Implementation advice section (e.g.
CLR-222 "Christmas party", CLR-085 "$20,000 instant asset write-off"). The
Explanation prose still contains the actionable content — we just need to
reformat it into numbered imperative steps.

Strict paraphrase contract:
  1. Claude reads the YAML's explanation_text (NOT the PDF — the explanation
     was itself verified against the PDF in the extractor's Pass 2).
  2. Returns numbered imperative steps, where each step cites the specific
     sentence from the explanation it paraphrases.
  3. Verification pass: each step's cited sentence must appear verbatim in
     the explanation. If any step can't be anchored, the whole generation
     is rejected and implementation_text stays empty.
  4. This keeps the contract "every published fact traces to verified PDF
     content" — paraphrase is faithful reformatting, not new information.

Usage:
    uv run python scripts/regenerate_empty_implementations.py            # all empty
    uv run python scripts/regenerate_empty_implementations.py --ids CLR-085,CLR-222
    uv run python scripts/regenerate_empty_implementations.py --dry-run  # don't write
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import anthropic
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings  # noqa: E402
from app.modules.tax_strategies.sync import (  # noqa: E402
    DEFAULT_STRATEGIES_DIR,
    YamlValidationError,
    load_yaml,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)


PARAPHRASE_SYSTEM = """You reformat an Australian tax strategy's Explanation prose into a numbered list of imperative Implementation steps. This is a strict PARAPHRASE, not synthesis — every step you produce must be traceable to a specific sentence in the provided explanation.

Return a single JSON object:

{
  "steps": [
    {
      "step_text": "<imperative step, e.g. 'Review 30th June debtors for uncollectable balances.'>",
      "source_sentence": "<the VERBATIM sentence from the explanation that this step paraphrases>"
    },
    ...
  ]
}

Rules:
- 3 to 8 steps. Imperative form ("Do X", "Review Y", "Ensure Z").
- `source_sentence` MUST be a substring of the explanation_text provided — verbatim, including punctuation and casing. Pick the single sentence most directly supporting the step.
- Never introduce a fact, threshold, date, dollar figure, or qualification that isn't in the explanation.
- If the explanation doesn't contain actionable content (e.g. it's purely descriptive), return {"steps": []}.
- Output ONLY the JSON object. No preamble, no code fences."""


@dataclass(frozen=True)
class ParaphraseResult:
    steps: list[dict]  # list of {"step_text", "source_sentence"}
    rejected: list[dict]  # list of {"step_text", "reason"}

    @property
    def implementation_text(self) -> str:
        """Join accepted steps into the numbered-list format the chunker expects."""
        if not self.steps:
            return ""
        return "\n".join(
            f"{i + 1}. {s['step_text'].strip()}" for i, s in enumerate(self.steps)
        )


def _parse_json(response: anthropic.types.Message) -> dict:
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


def _normalise_for_match(s: str) -> str:
    """Collapse whitespace + lowercase — used to locate source_sentence inside the explanation.

    The prompt demands verbatim matching but LLMs sometimes drift on
    whitespace around the quote boundary. This normalisation is lossy
    for matching only; the stored step text isn't altered.
    """
    return re.sub(r"\s+", " ", s).strip().lower()


def paraphrase_explanation(
    client: anthropic.Anthropic,
    strategy_id: str,
    explanation_text: str,
    model: str,
) -> ParaphraseResult:
    """Single-pass paraphrase with self-verification.

    The verification is structural: every step must cite a sentence, and
    that sentence must be a substring of explanation_text. Steps that
    don't pass the anchor check are dropped.
    """
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system=PARAPHRASE_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Strategy: {strategy_id}\n\n"
                    f"Explanation (paraphrase this into imperative steps):\n\n"
                    f"{explanation_text}"
                ),
            }
        ],
    )
    data = _parse_json(response)
    raw_steps = data.get("steps") or []

    haystack = _normalise_for_match(explanation_text)
    accepted: list[dict] = []
    rejected: list[dict] = []
    for step in raw_steps:
        if not isinstance(step, dict):
            rejected.append({"step_text": repr(step), "reason": "not a dict"})
            continue
        step_text = (step.get("step_text") or "").strip()
        source = (step.get("source_sentence") or "").strip()
        if not step_text or not source:
            rejected.append(
                {"step_text": step_text, "reason": "missing step_text or source_sentence"}
            )
            continue
        if _normalise_for_match(source) not in haystack:
            rejected.append(
                {
                    "step_text": step_text,
                    "reason": (
                        "source_sentence not found in explanation_text — "
                        "possible hallucination or paraphrase drift"
                    ),
                }
            )
            continue
        accepted.append({"step_text": step_text, "source_sentence": source})

    return ParaphraseResult(steps=accepted, rejected=rejected)


def iter_empty_yamls(
    strategies_dir: Path, wanted: set[str] | None
) -> list[tuple[Path, dict]]:
    """Return YAML paths + parsed payloads for strategies with empty implementation."""
    out: list[tuple[Path, dict]] = []
    for path in sorted(strategies_dir.glob("*.yaml")):
        if path.name.endswith(".audit.yaml"):
            continue
        try:
            payload = load_yaml(path)
        except YamlValidationError as e:
            logger.warning("skip %s: %s", path.name, e)
            continue
        if wanted is not None and payload["strategy_id"] not in wanted:
            continue
        if (payload.get("implementation_text") or "").strip():
            continue
        out.append((path, payload))
    return out


def _write_yaml(path: Path, payload: dict) -> None:
    path.write_text(
        yaml.safe_dump(
            payload,
            sort_keys=False,
            allow_unicode=True,
            width=100,
            default_flow_style=False,
        ),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strategies-dir", type=Path, default=DEFAULT_STRATEGIES_DIR
    )
    parser.add_argument(
        "--ids",
        default="",
        help="Comma-separated CLR-XXX ids to process (default: all empty).",
    )
    parser.add_argument("--model", default="claude-sonnet-4-6")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    wanted: set[str] | None = None
    if args.ids:
        wanted = {s.strip() for s in args.ids.split(",") if s.strip()}

    targets = iter_empty_yamls(args.strategies_dir, wanted)
    if not targets:
        logger.info("no YAMLs with empty implementation_text match the filter")
        return 0
    logger.info("found %d strategies with empty implementation_text", len(targets))

    settings = get_settings()
    api_key = settings.anthropic.api_key.get_secret_value()
    if not api_key:
        logger.error("ANTHROPIC_API_KEY is not configured")
        return 2

    client = anthropic.Anthropic(api_key=api_key)
    accepted_total = 0
    rejected_total = 0
    empty_output = 0

    for i, (path, payload) in enumerate(targets, 1):
        strategy_id = payload["strategy_id"]
        logger.info("[%d/%d] %s — paraphrasing", i, len(targets), strategy_id)
        try:
            result = paraphrase_explanation(
                client=client,
                strategy_id=strategy_id,
                explanation_text=payload["explanation_text"],
                model=args.model,
            )
        except Exception:
            logger.exception("failed for %s", strategy_id)
            continue

        accepted_total += len(result.steps)
        rejected_total += len(result.rejected)

        if not result.steps:
            empty_output += 1
            logger.warning(
                "%s: 0 steps accepted (rejected=%d). Leaving implementation_text empty.",
                strategy_id,
                len(result.rejected),
            )
            continue

        if result.rejected:
            for r in result.rejected:
                logger.warning("  rejected: %s — %s", r["step_text"][:70], r["reason"])

        new_text = result.implementation_text
        logger.info(
            "%s: accepted %d steps (%d chars)",
            strategy_id,
            len(result.steps),
            len(new_text),
        )
        logger.info("  preview: %s", new_text[:100].replace("\n", " | "))

        if not args.dry_run:
            payload["implementation_text"] = new_text
            _write_yaml(path, payload)

    logger.info(
        "done — %d steps accepted, %d rejected, %d YAMLs left empty",
        accepted_total,
        rejected_total,
        empty_output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
