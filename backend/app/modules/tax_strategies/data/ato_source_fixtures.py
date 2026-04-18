"""Pre-populated ATO primary source references per strategy (Spec 060 T028).

Phase 1 implementation of the research task reads this map instead of
scraping live ATO content. Phase 2 replaces with real scraping per
architecture §10.2. Entries here are the ATO primary sources a qualified
Australian tax practitioner would consult when drafting the strategy —
preserved verbatim from ATO publications (these references are law, not
content).

Shape: strategy_id → list of reference strings. Each string is an
unambiguous citation an accountant would recognise (act+section or
ruling number). URLs are omitted here because they move; the citation
is authoritative.

When a strategy_id has no fixture entry, the research task returns an
empty ato_sources list and still completes successfully — the downstream
reviewer will then add sources manually during Phase 2 authoring.
"""

from __future__ import annotations

# Primary-source references, one entry per strategy. Keys match
# TaxStrategy.strategy_id values (CLR-XXX format).
ATO_SOURCE_FIXTURES: dict[str, list[str]] = {
    # CLR-012 — Concessional super contributions.
    # Vertical-slice candidate per architecture §18.
    "CLR-012": [
        "ITAA 1997 Div 292",  # Excess concessional contributions charge
        "ITAA 1997 s 290-25",  # Deduction for personal contributions
        "ITAA 1997 s 290-170",  # Notice of intent to claim a deduction
        "ITAA 1997 Subdiv 291-C",  # Excess concessional contributions
        "TR 2010/1",  # Superannuation contributions ruling
    ],
    # CLR-241 — Change PSI to PSB.
    # Included alongside CLR-012 as the documented worked example
    # (architecture §17, §9.5).
    "CLR-241": [
        "ITAA 1997 Div 87",  # Personal services income
        "ITAA 1997 s 87-15",  # When an entity conducts a PSB
        "ITAA 1997 s 87-18",  # Results test
        "ITAA 1997 s 87-20",  # The 80% rule
        "ITAA 1997 s 87-25",  # Unrelated clients test
        "TR 2001/8",  # PSI — meaning of personal services business
        "TR 2022/3",  # PSI — current ATO view
    ],
}


def get_fixture_sources(strategy_id: str) -> list[str]:
    """Return the fixture-loaded ATO sources for a strategy.

    Returns an empty list when no fixture is configured — research task
    still completes, just with no sources to record.
    """
    return list(ATO_SOURCE_FIXTURES.get(strategy_id, []))
