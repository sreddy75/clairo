"""Payroll on-demand sync + manual-save context preservation (Spec 059 US3).

Pure helpers for the three wiring bugs identified in FR-006..010:

- FR-007: `credits.payg_withholding` is wired from the payroll summary rather
  than left at zero.
- FR-006: payroll sync is triggered on demand and bounded by a 15s synchronous
  window. A timeout transitions the plan to `pending` and schedules a
  background Celery sync.
- FR-010: `save_manual_financials` must not wipe out Xero-derived context
  (payroll, bank, prior years, strategy, projection metadata) just because
  the accountant is editing income/expenses.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Literal, Protocol
from uuid import UUID

logger = logging.getLogger(__name__)

PayrollSyncStatus = Literal["ready", "pending", "unavailable", "not_required"]

# Keys that flow from Xero into financials_data and must survive a manual edit.
# New keys added downstream should be added here — a missing key is a silent
# data loss that only surfaces when the AI stops seeing the context.
PRESERVED_CONTEXT_KEYS: frozenset[str] = frozenset(
    {
        "payroll_summary",
        "payroll_status",
        "bank_balances",
        "total_bank_balance",
        "last_reconciliation_date",
        "period_coverage",
        "unreconciled_summary",
        "strategy_context",
        "prior_years",
        "prior_year_ytd",
        "projection_metadata",
    }
)

SYNC_TIMEOUT_SECONDS: float = 15.0


def resolve_payroll_status(
    *,
    has_connection: bool,
    has_payroll_access: bool,
) -> PayrollSyncStatus | None:
    """Decide the payroll status before attempting a sync.

    Returns a terminal status (`not_required` / `unavailable`) when no sync
    should be attempted. Returns None when the caller should proceed to run a
    sync and let the outcome determine the status.
    """
    if not has_connection:
        return "not_required"
    if not has_payroll_access:
        return "unavailable"
    return None


def wire_paygw_credit(
    financials_data: dict[str, Any],
    payroll_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    """Copy `total_tax_withheld_ytd` into `credits.payg_withholding` (FR-007).

    When no payroll summary is available (no payroll access, sync pending), the
    credit is left untouched — a zero there is a visible signal paired with the
    payroll-status banner, not a silent $0 fallback.
    """
    if not payroll_summary:
        return financials_data
    credits = financials_data.setdefault("credits", {})
    credits["payg_withholding"] = float(payroll_summary.get("total_tax_withheld_ytd", 0) or 0)
    return financials_data


def merge_preserving_context(
    existing: dict[str, Any] | None,
    new: dict[str, Any],
) -> dict[str, Any]:
    """Merge a freshly-built `financials_data` over an existing one, preserving
    the Xero-derived context keys listed in `PRESERVED_CONTEXT_KEYS` (FR-010).

    The new dict wins for every key it defines. Context keys absent from `new`
    but present in `existing` are copied across. This is intentionally a
    shallow merge — context values are whole sub-documents (lists, dicts) and
    a per-key replace is the right granularity.
    """
    merged: dict[str, Any] = dict(new)
    if not existing:
        return merged
    for key in PRESERVED_CONTEXT_KEYS:
        if key not in merged and key in existing:
            merged[key] = existing[key]
    return merged


class PayrollSyncer(Protocol):
    """Minimal protocol so `sync_payroll_with_timeout` can be unit-tested
    against a simple stub without importing the Xero service."""

    async def sync_payroll(self, connection_id: UUID) -> dict[str, Any]: ...


async def sync_payroll_with_timeout(
    syncer: PayrollSyncer,
    connection_id: UUID,
    timeout_s: float = SYNC_TIMEOUT_SECONDS,
) -> tuple[PayrollSyncStatus, dict[str, Any] | None]:
    """Run a payroll sync bounded by `timeout_s`.

    Returns `("ready", result)` on success, `("pending", None)` on timeout. The
    caller is responsible for scheduling the background continuation — this
    helper stays unaware of Celery so it can be tested in isolation.
    """
    try:
        result = await asyncio.wait_for(
            syncer.sync_payroll(connection_id), timeout=timeout_s
        )
        return "ready", result
    except TimeoutError:
        logger.info(
            "Payroll sync exceeded %.1fs synchronous window for connection %s; "
            "caller will schedule background continuation.",
            timeout_s,
            connection_id,
        )
        return "pending", None


def schedule_background_payroll_sync(connection_id: UUID, tenant_id: UUID) -> None:
    """Enqueue the existing Celery payroll sync task.

    Broken out so the service can call it without importing celery internals at
    module load time, and so tests can monkeypatch it in place of firing a real
    task.
    """
    from app.tasks.xero import sync_xero_payroll

    sync_xero_payroll.delay(str(connection_id), str(tenant_id))
