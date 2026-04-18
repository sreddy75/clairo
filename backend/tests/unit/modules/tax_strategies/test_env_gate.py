"""Unit tests for tax_strategies env gate (Spec 060 T012)."""

from __future__ import annotations

import pytest

from app.config import get_settings
from app.modules.tax_strategies import env_gate


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    """The get_settings() result is lru_cached; reset before each test so the
    monkeypatched env var is read fresh.
    """
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_vector_writes_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TAX_STRATEGIES_VECTOR_WRITE_ENABLED", raising=False)
    assert env_gate.vector_writes_enabled() is False


@pytest.mark.parametrize("value", ["true", "True", "1", "yes"])
def test_vector_writes_enabled_when_flag_true(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("TAX_STRATEGIES_VECTOR_WRITE_ENABLED", value)
    assert env_gate.vector_writes_enabled() is True


@pytest.mark.parametrize("value", ["false", "False", "0", "no"])
def test_vector_writes_disabled_when_flag_false_like(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("TAX_STRATEGIES_VECTOR_WRITE_ENABLED", value)
    assert env_gate.vector_writes_enabled() is False
