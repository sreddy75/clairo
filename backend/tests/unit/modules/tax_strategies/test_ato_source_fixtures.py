"""Unit tests for the ATO source fixture loader (Spec 060 T028 research)."""

from __future__ import annotations

from app.modules.tax_strategies.data.ato_source_fixtures import (
    ATO_SOURCE_FIXTURES,
    get_fixture_sources,
)


def test_clr_012_has_sources() -> None:
    """Vertical-slice candidate (architecture §18) must have sources seeded."""
    sources = get_fixture_sources("CLR-012")
    assert len(sources) > 0
    # Must reference the concessional super regime — ITAA Division 292 is
    # the canonical anchor for this strategy.
    assert any("Div 292" in s for s in sources)


def test_clr_241_has_psi_psb_sources() -> None:
    """Worked example from architecture §17 has the full PSI/PSB reference set."""
    sources = get_fixture_sources("CLR-241")
    assert any("Div 87" in s for s in sources)
    assert any("TR 2001/8" in s for s in sources)


def test_unknown_strategy_returns_empty_list() -> None:
    """Strategies without a fixture entry are not an error — research still
    completes, just with no sources to record."""
    assert get_fixture_sources("CLR-999") == []
    assert get_fixture_sources("CLR-001") == []


def test_get_fixture_sources_returns_a_copy_not_the_shared_list() -> None:
    """Callers must not be able to mutate the module-level fixture by
    appending to the returned list."""
    first = get_fixture_sources("CLR-012")
    first.append("MUTATED")
    second = get_fixture_sources("CLR-012")
    assert "MUTATED" not in second


def test_all_fixture_keys_follow_clr_format() -> None:
    """Sanity: every key in the fixture is a valid CLR-XXX identifier."""
    import re

    pattern = re.compile(r"^CLR-\d{3,5}$")
    for key in ATO_SOURCE_FIXTURES:
        assert pattern.match(key), f"Invalid fixture key: {key!r}"


def test_all_fixture_entries_are_non_empty_string_lists() -> None:
    for key, sources in ATO_SOURCE_FIXTURES.items():
        assert isinstance(sources, list), f"{key} fixture is not a list"
        assert len(sources) > 0, f"{key} fixture is empty"
        for s in sources:
            assert isinstance(s, str) and s.strip(), (
                f"{key} fixture has empty/non-string entry: {s!r}"
            )
