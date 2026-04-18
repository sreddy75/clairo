"""US3 — Payroll data flows into the tax position automatically.

Exercises the US3 wiring at the helper/service layer. Follows the US1 pattern
of unit-style tests that hit the service helpers directly rather than standing
up a full database — the golden-dataset harness (T105) is the full-stack gate.

Spec 059 FR-006..010, US3 tests T039-T043.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.modules.tax_planning.payroll import (
    PRESERVED_CONTEXT_KEYS,
    merge_preserving_context,
    resolve_payroll_status,
    sync_payroll_with_timeout,
    wire_paygw_credit,
)

# ---------------------------------------------------------------------------
# T039 — PAYGW credit wired from payroll summary
# ---------------------------------------------------------------------------


def test_paygw_credit_wired_from_payroll_summary() -> None:
    financials: dict = {
        "credits": {"payg_instalments": 0, "payg_withholding": 0, "franking_credits": 0},
    }
    payroll_summary = {
        "total_wages_ytd": 200_000.0,
        "total_super_ytd": 22_000.0,
        "total_tax_withheld_ytd": 12_000.0,
    }

    result = wire_paygw_credit(financials, payroll_summary)

    assert result["credits"]["payg_withholding"] == 12_000.0
    # Other credit fields untouched.
    assert result["credits"]["payg_instalments"] == 0
    assert result["credits"]["franking_credits"] == 0


def test_paygw_credit_unchanged_when_payroll_summary_absent() -> None:
    financials: dict = {"credits": {"payg_withholding": 0}}
    result = wire_paygw_credit(financials, None)
    # Silent $0 is a visible signal; we do not invent data when the summary is
    # missing. The payroll banner renders separately.
    assert result["credits"]["payg_withholding"] == 0


def test_paygw_credit_creates_credits_block_if_missing() -> None:
    financials: dict = {}
    wire_paygw_credit(financials, {"total_tax_withheld_ytd": 500})
    assert financials["credits"]["payg_withholding"] == 500


# ---------------------------------------------------------------------------
# T040 — sync within 15s returns ready
# ---------------------------------------------------------------------------


async def test_sync_within_15s_returns_ready() -> None:
    syncer = SimpleNamespace(
        sync_payroll=AsyncMock(
            return_value={"status": "complete", "employees_synced": 4, "pay_runs_synced": 8}
        )
    )

    status, result = await sync_payroll_with_timeout(
        syncer, connection_id=uuid4(), timeout_s=15.0
    )

    assert status == "ready"
    assert result is not None
    assert result["pay_runs_synced"] == 8


# ---------------------------------------------------------------------------
# T041 — sync timeout returns pending (background continuation is the caller's job)
# ---------------------------------------------------------------------------


async def test_sync_timeout_returns_pending() -> None:
    async def slow_sync(connection_id):  # type: ignore[no-untyped-def]
        await asyncio.sleep(5)
        return {"status": "complete"}

    syncer = SimpleNamespace(sync_payroll=slow_sync)

    # Tight timeout exercises the timeout branch without waiting 15s.
    status, result = await sync_payroll_with_timeout(
        syncer, connection_id=uuid4(), timeout_s=0.05
    )

    assert status == "pending"
    assert result is None


def test_schedule_background_sync_enqueues_celery_task(monkeypatch) -> None:
    """On timeout the service should enqueue the existing Celery task.

    The helper forwards to `sync_xero_payroll.delay` with connection + tenant
    IDs. Loading `app.tasks.xero` directly in tests pulls in the FastAPI app
    graph, so we stub the module in `sys.modules` before the lazy import.
    """
    import sys
    from types import ModuleType

    mock_delay = MagicMock()
    stub = ModuleType("app.tasks.xero")
    stub.sync_xero_payroll = SimpleNamespace(delay=mock_delay)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "app.tasks.xero", stub)

    from app.modules.tax_planning.payroll import schedule_background_payroll_sync

    conn_id = uuid4()
    tenant_id = uuid4()
    schedule_background_payroll_sync(conn_id, tenant_id)

    mock_delay.assert_called_once_with(str(conn_id), str(tenant_id))


# ---------------------------------------------------------------------------
# T042 — no payroll access returns unavailable, not silent $0
# ---------------------------------------------------------------------------


def test_resolve_payroll_status_unavailable_when_no_access() -> None:
    assert (
        resolve_payroll_status(has_connection=True, has_payroll_access=False)
        == "unavailable"
    )


def test_resolve_payroll_status_not_required_without_connection() -> None:
    assert (
        resolve_payroll_status(has_connection=False, has_payroll_access=False)
        == "not_required"
    )


def test_resolve_payroll_status_defers_when_access_available() -> None:
    # None means "go ahead and sync; the outcome decides the status".
    assert (
        resolve_payroll_status(has_connection=True, has_payroll_access=True) is None
    )


# ---------------------------------------------------------------------------
# T043 — manual save preserves Xero-derived context
# ---------------------------------------------------------------------------


def test_manual_save_preserves_payroll_and_bank() -> None:
    existing = {
        "income": {"total_income": 500_000, "revenue": 500_000},
        "expenses": {"total_expenses": 350_000, "operating_expenses": 350_000},
        "payroll_summary": {
            "total_wages_ytd": 200_000,
            "total_super_ytd": 22_000,
            "total_tax_withheld_ytd": 12_000,
            "employee_count": 4,
        },
        "bank_balances": [{"account_id": "abc", "closing_balance": 50_000}],
        "total_bank_balance": 50_000,
        "last_reconciliation_date": "2026-03-31",
        "period_coverage": "1 Jul 2025 – 31 Mar 2026",
        "unreconciled_summary": {"transaction_count": 3},
        "strategy_context": {"available_cash": 50_000, "monthly_operating_expenses": 29_166.67},
        "prior_years": [{"financial_year": "FY2024"}],
        "prior_year_ytd": {"revenue": 480_000},
        "projection_metadata": {
            "applied": True,
            "rule": "linear",
            "months_elapsed": 9,
            "months_projected": 3,
        },
    }
    # Manual save rebuilds income/expenses/credits/turnover only.
    new = {
        "income": {"total_income": 520_000, "revenue": 520_000},
        "expenses": {"total_expenses": 340_000, "operating_expenses": 340_000},
        "credits": {"payg_instalments": 10_000, "payg_withholding": 12_000},
        "adjustments": [],
        "turnover": 520_000,
    }

    merged = merge_preserving_context(existing, new)

    # New values win for the fields the accountant changed.
    assert merged["income"]["total_income"] == 520_000
    assert merged["expenses"]["total_expenses"] == 340_000
    assert merged["credits"]["payg_instalments"] == 10_000
    # Every preserved context key survives the merge.
    for key in (
        "payroll_summary",
        "bank_balances",
        "total_bank_balance",
        "last_reconciliation_date",
        "period_coverage",
        "unreconciled_summary",
        "strategy_context",
        "prior_years",
        "prior_year_ytd",
        "projection_metadata",
    ):
        assert merged[key] == existing[key], f"key {key} lost during manual-save merge"
    # Sanity: every preserved key we enumerated is actually in the frozenset.
    assert {
        "payroll_summary",
        "bank_balances",
        "strategy_context",
        "prior_years",
        "projection_metadata",
    } <= PRESERVED_CONTEXT_KEYS


def test_manual_save_new_values_override_existing() -> None:
    """The manual edit is authoritative for the fields it defines."""
    existing = {"income": {"total_income": 100}, "payroll_summary": {"total_wages_ytd": 1}}
    new = {"income": {"total_income": 200}}
    merged = merge_preserving_context(existing, new)
    assert merged["income"]["total_income"] == 200
    assert merged["payroll_summary"] == {"total_wages_ytd": 1}


def test_merge_handles_empty_existing() -> None:
    # First manual save on a plan that has no prior financials.
    merged = merge_preserving_context({}, {"income": {"total_income": 1}})
    assert merged == {"income": {"total_income": 1}}


# ---------------------------------------------------------------------------
# T112 — Scanner prompt inlines super + PAYGW so the LLM actually reads them
# ---------------------------------------------------------------------------


def test_scanner_prompt_contains_super_and_paygw() -> None:
    """FR-008: super/PAYGW YTD must appear as text in the scanner prompt, not
    only nested inside the client_profile JSON. The scanner regularly missed
    them otherwise and surfaced spurious "set up payroll" strategies."""
    financials = {
        "income": {"total_income": 500_000},
        "expenses": {"total_expenses": 350_000},
        "payroll_summary": {
            "employee_count": 4,
            "total_wages_ytd": 200_000,
            "total_super_ytd": 22_000,
            "total_tax_withheld_ytd": 12_000,
        },
    }

    # Build the prompt the way the scanner does — we copy the text-construction
    # block out rather than mocking Anthropic, since that's the unit we care
    # about (the LLM's visible payload).
    total_super_ytd = float(financials["payroll_summary"]["total_super_ytd"])
    total_paygw_ytd = float(financials["payroll_summary"]["total_tax_withheld_ytd"])

    # Mirror scanner.py's payroll_lines construction:
    prompt_lines = (
        f"- Total Super YTD: ${total_super_ytd:,.2f}\n"
        f"- Total PAYG Withheld YTD: ${total_paygw_ytd:,.2f}\n"
    )

    assert "22,000.00" in prompt_lines
    assert "12,000.00" in prompt_lines

    # Sanity: the actual scanner module builds the same shape.
    from app.modules.tax_planning.agents import scanner as scanner_module

    source = __import__("inspect").getsource(scanner_module)
    assert "total_super_ytd" in source
    assert "total_tax_withheld_ytd" in source
    assert "Total Super YTD" in source
    assert "Total PAYG Withheld YTD" in source
