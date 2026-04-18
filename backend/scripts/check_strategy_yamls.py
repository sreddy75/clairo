#!/usr/bin/env python3
"""Sanity-check the committed strategy YAMLs for data-quality gaps.

Reports per-strategy issues + a summary. Doesn't mutate anything.
Runs in seconds — no API calls.

Flags the following issues (severity → exit code):
  ERROR  (exit 1)  invalid YAML, missing required keys, wrong types
  WARN             empty implementation_text, empty explanation_text,
                    name unusually short, keywords empty
  INFO             all-null eligibility bands (common + expected)

Usage:
    uv run python scripts/check_strategy_yamls.py
    uv run python scripts/check_strategy_yamls.py --strict   # WARN becomes ERROR
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.modules.tax_strategies.sync import (  # noqa: E402
    DEFAULT_STRATEGIES_DIR,
    YamlValidationError,
    load_yaml,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


# Minimum reasonable lengths. Tuned to catch "just a period" placeholders
# and near-empty prose, not to penalise brief but legitimate content.
_MIN_IMPL_CHARS = 30
_MIN_EXPL_CHARS = 150
_MIN_NAME_CHARS = 4


def check_one(path: Path) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for a single YAML. Info-level passes."""
    errors: list[str] = []
    warnings: list[str] = []
    try:
        payload = load_yaml(path)
    except YamlValidationError as e:
        return [f"validation: {e}"], []

    name = payload.get("name", "")
    impl = (payload.get("implementation_text") or "").strip()
    expl = (payload.get("explanation_text") or "").strip()
    keywords = payload.get("keywords") or []

    if len(name) < _MIN_NAME_CHARS:
        errors.append(f"name too short ({len(name)} chars): {name!r}")

    if not impl:
        warnings.append(
            "implementation_text is EMPTY — source PDF had a blank/placeholder "
            "Implementation advice section. Admin detail view will show '(empty)'."
        )
    elif len(impl) < _MIN_IMPL_CHARS:
        warnings.append(
            f"implementation_text is very short ({len(impl)} chars): {impl[:60]!r}"
        )

    if not expl:
        errors.append("explanation_text is EMPTY — chunk would be zero-length")
    elif len(expl) < _MIN_EXPL_CHARS:
        warnings.append(
            f"explanation_text is short ({len(expl)} chars) — retrieval may be weak"
        )

    if not keywords:
        warnings.append("keywords list is empty — retrieval will miss keyword queries")
    elif len(keywords) < 3:
        warnings.append(f"only {len(keywords)} keywords — consider more")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategies-dir", type=Path, default=DEFAULT_STRATEGIES_DIR)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors (exits non-zero on any issue).",
    )
    parser.add_argument(
        "--show-ok",
        action="store_true",
        help="Also list files with no issues.",
    )
    args = parser.parse_args()

    paths = sorted(args.strategies_dir.glob("*.yaml"))
    paths = [p for p in paths if not p.name.endswith(".audit.yaml")]
    if not paths:
        logger.error("no YAML files in %s", args.strategies_dir)
        return 1

    total = len(paths)
    files_with_errors = 0
    files_with_warnings = 0
    clean = 0
    issue_counts: dict[str, int] = {}

    for path in paths:
        errors, warnings = check_one(path)
        if errors:
            files_with_errors += 1
            for e in errors:
                logger.info("ERROR %s: %s", path.stem, e)
                key = e.split(":")[0].strip()
                issue_counts[key] = issue_counts.get(key, 0) + 1
        if warnings:
            files_with_warnings += 1
            for w in warnings:
                logger.info("WARN  %s: %s", path.stem, w)
                key = w.split(" ")[0].lower()
                issue_counts[key] = issue_counts.get(key, 0) + 1
        if not errors and not warnings:
            clean += 1
            if args.show_ok:
                logger.info("OK    %s", path.stem)

    logger.info("")
    logger.info("=" * 60)
    logger.info(
        "SUMMARY: %d total · %d clean · %d with warnings · %d with errors",
        total,
        clean,
        files_with_warnings,
        files_with_errors,
    )
    if issue_counts:
        logger.info("")
        logger.info("Issue breakdown:")
        for key, count in sorted(issue_counts.items(), key=lambda x: -x[1]):
            logger.info("  %s: %d", key, count)

    if files_with_errors:
        return 1
    if args.strict and files_with_warnings:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
