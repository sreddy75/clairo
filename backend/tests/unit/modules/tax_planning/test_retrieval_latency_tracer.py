"""Unit tests for the retrieval latency tracer (Spec 060 T063)."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock

import pytest


class _FakeService:
    """Minimal stand-in exposing just the tracer wrapper.

    We don't instantiate a full TaxPlanningService because it requires
    a live session + settings; the tracer is purely wrapper logic around
    the _impl method.
    """

    def __init__(self, impl_return: tuple) -> None:
        self._retrieve_tax_knowledge_impl = AsyncMock(return_value=impl_return)

    # Copy the tracer wrapper verbatim from TaxPlanningService so we can
    # test it in isolation.
    async def _retrieve_tax_knowledge(
        self,
        query: str,
        entity_type: str,
        financials_data: dict | None = None,
    ):
        import time

        from app.modules.tax_planning.service import logger

        start = time.perf_counter()
        outcome = "success"
        compliance_count = 0
        strategy_count = 0
        try:
            result = await self._retrieve_tax_knowledge_impl(
                query, entity_type, financials_data
            )
            _, _, retrieved_strategies = result
            strategy_count = len(retrieved_strategies)
            compliance_count = sum(
                1
                for c in result[0]
                if not c.get("chunk_id", "").startswith("strategy:")
            )
            return result
        except BaseException:
            outcome = "error"
            raise
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            logger.info(
                "tax_planning.retrieve.ms=%.1f query_len=%d entity=%s "
                "compliance=%d strategies=%d outcome=%s",
                elapsed_ms,
                len(query),
                entity_type,
                compliance_count,
                strategy_count,
                outcome,
            )


@pytest.fixture(autouse=True)
def _caplog_info_level(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="app.modules.tax_planning.service")


async def test_emits_latency_log_on_success(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # 2 compliance chunks + 1 strategy entry; strategy_count should be 1
    # (entries with chunk_id starting `strategy:` are strategies).
    svc = _FakeService(
        impl_return=(
            [
                {"chunk_id": "abc"},
                {"chunk_id": "def"},
                {"chunk_id": "strategy:CLR-012"},
            ],
            "rendered reference material",
            [{"strategy_id": "CLR-012", "name": "Concessional super contributions"}],
        )
    )
    result = await svc._retrieve_tax_knowledge(
        "should my employee salary-sacrifice to super?",
        "individual",
        None,
    )
    assert len(result[2]) == 1
    # Exactly one tracer line emitted.
    tracer_lines = [r for r in caplog.records if "tax_planning.retrieve.ms" in r.message]
    assert len(tracer_lines) == 1
    msg = tracer_lines[0].getMessage()
    assert "compliance=2" in msg
    assert "strategies=1" in msg
    assert "entity=individual" in msg
    assert "outcome=success" in msg


async def test_emits_latency_log_on_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    svc = _FakeService(impl_return=([], "", []))
    svc._retrieve_tax_knowledge_impl = AsyncMock(side_effect=RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        await svc._retrieve_tax_knowledge("test query", "company", None)
    tracer_lines = [r for r in caplog.records if "tax_planning.retrieve.ms" in r.message]
    assert len(tracer_lines) == 1
    msg = tracer_lines[0].getMessage()
    assert "outcome=error" in msg


async def test_zero_results_logs_zeros(
    caplog: pytest.LogCaptureFixture,
) -> None:
    svc = _FakeService(impl_return=([], "", []))
    await svc._retrieve_tax_knowledge("q", "trust", None)
    tracer_lines = [r for r in caplog.records if "tax_planning.retrieve.ms" in r.message]
    assert len(tracer_lines) == 1
    msg = tracer_lines[0].getMessage()
    assert "compliance=0" in msg
    assert "strategies=0" in msg


async def test_elapsed_ms_is_non_negative(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Sanity: the elapsed value in the log is non-negative (guards against
    monotonic-clock bugs)."""
    svc = _FakeService(impl_return=([], "", []))
    await svc._retrieve_tax_knowledge("q", "individual", None)
    tracer_lines = [r for r in caplog.records if "tax_planning.retrieve.ms" in r.message]
    msg = tracer_lines[0].getMessage()
    # Extract the float after "ms="
    import re

    m = re.search(r"tax_planning\.retrieve\.ms=([\d.]+)", msg)
    assert m is not None
    elapsed = float(m.group(1))
    assert elapsed >= 0.0
