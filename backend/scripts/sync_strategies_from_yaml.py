#!/usr/bin/env python3
"""Sync committed strategy YAMLs into the database + publish them (Spec 060).

This is the single script that runs in BOTH environments to reconcile
`data/strategies/*.yaml` with the DB and Pinecone:

Local (one-off bootstrap):
    TAX_STRATEGIES_VECTOR_WRITE_ENABLED=true \\
      uv run python scripts/sync_strategies_from_yaml.py

    Creates TaxStrategy rows, embeds chunks, upserts Pinecone vectors
    into the shared `tax_strategies` namespace.

Prod (after code deploy):
    TAX_STRATEGIES_VECTOR_WRITE_ENABLED=false \\
      uv run python scripts/sync_strategies_from_yaml.py

    Creates TaxStrategy rows. The publish task's idempotency check
    finds the vectors already in Pinecone (from the local run) and
    skips embed+upsert — so prod doesn't need write credentials or pay
    embedding cost. Content hash match = skip.

Versioning:
    A YAML with `version: N` where N > the live row's version triggers
    a supersede + new-version row. Default (no `version` key) is update
    in place at v1.

Flags:
    --dry-run        Don't write to DB; print what would happen.
    --ids CLR-012,CLR-241   Restrict to specific ids (pilot testing).
    --no-publish     Sync DB only; don't trigger the publish task.
    --sync-publish   Run publish inline synchronously (slower but
                     immediate feedback). Default is to dispatch via
                     Celery `apply_async`.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.modules.tax_strategies.env_gate import vector_writes_enabled  # noqa: E402
from app.modules.tax_strategies.sync import (  # noqa: E402
    DEFAULT_STRATEGIES_DIR,
    SyncSummary,
    sync_all,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger("sync_strategies_from_yaml")


def _make_session_factory() -> async_sessionmaker[AsyncSession]:
    settings = get_settings()
    engine = create_async_engine(
        settings.database.url, echo=False, poolclass=NullPool
    )
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _publish_sync(
    session: AsyncSession, strategy_id: str, actor: str
) -> dict[str, Any]:
    """Inline synchronous publish — imports the celery task's async body."""
    from app.tasks.tax_strategy_authoring import _run_publish

    return await _run_publish(strategy_id, actor)


def _dispatch_async(strategy_id: str, actor: str) -> None:
    """Enqueue a Celery publish task (default behaviour for large batches)."""
    from app.tasks.tax_strategy_authoring import publish_strategy

    publish_strategy.apply_async(args=[strategy_id, actor])


async def run(args: argparse.Namespace) -> int:
    strategies_dir: Path = args.strategies_dir
    if not strategies_dir.exists():
        logger.error("strategies dir %s does not exist", strategies_dir)
        return 1

    wanted: set[str] | None = None
    if args.ids:
        wanted = {s.strip() for s in args.ids.split(",") if s.strip()}

    if args.dry_run:
        logger.info("DRY RUN — no DB writes")

    factory = _make_session_factory()
    async with factory() as session:
        summary: SyncSummary = await sync_all(
            session,
            strategies_dir=strategies_dir,
            strategy_ids=wanted,
            actor=f"system:sync:{'dry' if args.dry_run else 'run'}",
        )
        if args.dry_run:
            await session.rollback()
        else:
            await session.commit()

    logger.info(
        "sync done: created=%d updated=%d unchanged=%d version_bumps=%d invalid=%d",
        summary.created,
        summary.updated,
        summary.unchanged,
        summary.version_bumps,
        summary.invalid,
    )

    for d in summary.decisions:
        level = logging.WARNING if d.action == "invalid" else logging.INFO
        logger.log(level, "%s: %s %s", d.strategy_id, d.action, d.reason)

    # Publish dispatch
    if args.dry_run or args.no_publish:
        logger.info("publish step skipped")
        return 0

    publish_ids = summary.needs_publish_ids
    if not publish_ids:
        logger.info("no strategies need publish (no drift, no new rows)")
        return 0

    vec_enabled = vector_writes_enabled()
    logger.info(
        "publishing %d strategies (vector_writes_enabled=%s — embeds will %s)",
        len(publish_ids),
        vec_enabled,
        "run" if vec_enabled else "skip (must have vectors already in Pinecone)",
    )

    if args.sync_publish:
        # Inline publish — one at a time. Each call opens its own session
        # (via `_make_session_factory` inside the task). Progress visible.
        factory = _make_session_factory()
        errors = 0
        for i, strategy_id in enumerate(publish_ids, 1):
            async with factory() as session:  # noqa: F841 — task manages its own
                try:
                    result = await _publish_sync(
                        session,
                        strategy_id,
                        "system:sync:inline",
                    )
                    logger.info(
                        "[%d/%d] %s published (reused=%s)",
                        i,
                        len(publish_ids),
                        strategy_id,
                        result.get("vectors_reused"),
                    )
                except Exception:
                    errors += 1
                    logger.exception("[%d/%d] %s FAILED", i, len(publish_ids), strategy_id)
        logger.info(
            "inline publish finished: %d/%d ok, %d failed",
            len(publish_ids) - errors,
            len(publish_ids),
            errors,
        )
        return 1 if errors else 0

    # Default: dispatch via Celery. Worker processes them in parallel.
    for strategy_id in publish_ids:
        _dispatch_async(strategy_id, "system:sync:dispatch")
    logger.info(
        "dispatched %d publish jobs to Celery queue 'tax_strategies' — "
        "watch the worker logs for completion",
        len(publish_ids),
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strategies-dir",
        type=Path,
        default=DEFAULT_STRATEGIES_DIR,
        help="Directory containing strategy YAML files.",
    )
    parser.add_argument(
        "--ids",
        default="",
        help="Comma-separated CLR-XXX ids to sync (default: all).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse YAMLs and report what would happen; no DB writes.",
    )
    parser.add_argument(
        "--no-publish",
        action="store_true",
        help="Sync DB but skip the publish dispatch.",
    )
    parser.add_argument(
        "--sync-publish",
        action="store_true",
        help="Run publish inline (slower, immediate feedback, no Celery).",
    )
    args = parser.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
