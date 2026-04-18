"""US8 — Duplicate scenarios do not accumulate.

Unit-style coverage for the upsert-by-normalised-title helper. The integration
contract (partial unique index at the DB level) is validated by the migration
itself; here we confirm the repository uses case- and whitespace-insensitive
matching so a refined-title retry updates the existing row instead of
creating a second one.

Spec 059 FR-024..FR-025, US8 tests T097-T098.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.tax_planning.repository import TaxScenarioRepository


class _StubSession:
    """Minimal AsyncSession stand-in for the lookup branch — we want to assert
    the helper queries with lower(trim(title)) semantics without spinning up
    a real SQLAlchemy engine."""

    def __init__(self, existing=None):
        self.existing = existing
        self.added = []
        self.flush = AsyncMock()
        self.refresh = AsyncMock()
        self.delete = AsyncMock()
        self.captured_query = None

    async def execute(self, stmt):  # noqa: ANN001
        self.captured_query = stmt
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=self.existing)
        return result

    def add(self, obj):  # noqa: ANN001
        self.added.append(obj)


@pytest.fixture
def repo_with_existing():
    """Return (repo, session, existing_scenario) where existing_scenario is
    what the lookup will return, simulating a pre-existing row."""
    existing = MagicMock()
    existing.id = uuid4()
    existing.title = "Prepay rent"
    existing.tax_plan_id = uuid4()
    existing.tenant_id = uuid4()
    existing.created_at = "2026-04-01T00:00:00Z"

    session = _StubSession(existing=existing)
    repo = TaxScenarioRepository(session)  # type: ignore[arg-type]
    return repo, session, existing


# ---------------------------------------------------------------------------
# T097 — same normalised title updates the existing row
# ---------------------------------------------------------------------------


async def test_same_normalized_title_updates_existing_row(repo_with_existing) -> None:
    """Whitespace + case differences must still resolve to the same row."""
    repo, session, existing = repo_with_existing

    scenario = await repo.upsert_by_normalized_title(
        tax_plan_id=existing.tax_plan_id,
        tenant_id=existing.tenant_id,
        title="  PREPAY RENT  ",  # Messy casing + whitespace — must match.
        payload={
            "description": "Refined description",
            "assumptions": {"items": ["$30k prepayment"]},
            "impact_data": {"change": {"tax_saving": 7_500}},
            "risk_rating": "conservative",
            "compliance_notes": "s82KZM",
            "cash_flow_impact": -22_500,
            "sort_order": 0,
        },
    )

    # Same row returned — UUID preserved so React keys / links keep working.
    assert scenario.id == existing.id
    # No new row added to the session.
    assert session.added == []
    # Fields updated in place on the existing row.
    assert existing.description == "Refined description"
    assert existing.impact_data == {"change": {"tax_saving": 7_500}}
    assert existing.title == "  PREPAY RENT  "  # new title wins per payload


async def test_upsert_preserves_immutable_fields(repo_with_existing) -> None:
    """id / tenant_id / tax_plan_id / created_at must not be overwritten by a
    payload dict that happens to contain them."""
    repo, _session, existing = repo_with_existing
    original_id = existing.id
    original_created = existing.created_at

    hostile_payload = {
        "id": uuid4(),  # must be ignored
        "tenant_id": uuid4(),  # must be ignored
        "tax_plan_id": uuid4(),  # must be ignored
        "created_at": "1999-01-01",  # must be ignored
        "description": "updated",
        "assumptions": {},
        "impact_data": {},
        "risk_rating": "moderate",
        "compliance_notes": None,
        "cash_flow_impact": None,
        "sort_order": 0,
    }

    await repo.upsert_by_normalized_title(
        tax_plan_id=existing.tax_plan_id,
        tenant_id=existing.tenant_id,
        title="Prepay rent",
        payload=hostile_payload,
    )

    assert existing.id == original_id
    assert existing.created_at == original_created


# ---------------------------------------------------------------------------
# T098-style — no match creates a new row
# ---------------------------------------------------------------------------


async def test_no_existing_row_creates_new_scenario() -> None:
    session = _StubSession(existing=None)
    repo = TaxScenarioRepository(session)  # type: ignore[arg-type]

    tenant_id = uuid4()
    plan_id = uuid4()

    scenario = await repo.upsert_by_normalized_title(
        tax_plan_id=plan_id,
        tenant_id=tenant_id,
        title="Buy new depreciating asset",
        payload={
            "description": "Purchase",
            "assumptions": {"items": []},
            "impact_data": {},
            "risk_rating": "moderate",
            "compliance_notes": None,
            "cash_flow_impact": None,
            "sort_order": 0,
        },
    )

    assert scenario.title == "Buy new depreciating asset"
    assert len(session.added) == 1
    assert session.added[0].tax_plan_id == plan_id
    assert session.added[0].tenant_id == tenant_id
