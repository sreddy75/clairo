"""Celery tasks for the tax_strategies authoring pipeline (Spec 060).

Four stages — research, draft, enrich, publish — one task per stage. Each
task writes a TaxStrategyAuthoringJob row and advances the TaxStrategy's
status via TaxStrategyService._transition_status.

Phase 1 scaffolding: stubs raise NotImplementedError. Real implementations
land in T027 (publish — env-gated) and T028 (research/draft/enrich).
"""

from __future__ import annotations

import logging
from typing import Any

from celery import Task

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(  # type: ignore[misc]
    bind=True,
    name="tax_strategies.research",
    max_retries=3,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def research_strategy(self: Task, strategy_id: str, triggered_by: str) -> dict[str, Any]:
    """Phase 1: load pre-populated ATO sources from fixture map (T028).

    Phase 2 replaces this with real scraping.
    """
    raise NotImplementedError("research_strategy implementation lands in T028")


@celery_app.task(  # type: ignore[misc]
    bind=True,
    name="tax_strategies.draft",
    max_retries=3,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def draft_strategy(self: Task, strategy_id: str, triggered_by: str) -> dict[str, Any]:
    """Phase 1: real Anthropic SDK call per architecture §10.3 (T028)."""
    raise NotImplementedError("draft_strategy implementation lands in T028")


@celery_app.task(  # type: ignore[misc]
    bind=True,
    name="tax_strategies.enrich",
    max_retries=3,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def enrich_strategy(self: Task, strategy_id: str, triggered_by: str) -> dict[str, Any]:
    """Phase 1: second LLM pass extracting structured eligibility (T028)."""
    raise NotImplementedError("enrich_strategy implementation lands in T028")


@celery_app.task(  # type: ignore[misc]
    bind=True,
    name="tax_strategies.publish",
    max_retries=3,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def publish_strategy(self: Task, strategy_id: str, triggered_by: str) -> dict[str, Any]:
    """Phase 1: env-gated chunk → embed → upsert (T027).

    Calls env_gate.vector_writes_enabled(); on false the job fails with
    `vector_write_disabled_in_this_environment` and the strategy stays
    in `approved` status per FR-011.
    """
    raise NotImplementedError("publish_strategy implementation lands in T027")
