"""Smoke tests for the tax_strategies routers (Spec 060 T034/T035).

These tests verify the router surface — route registration, auth gating
shape, and FR-008 (source_ref stripping) at the schema level. Full
behaviour tests that require a database and Celery are deferred to the
integration suite (T024).
"""

from __future__ import annotations

from app.modules.tax_strategies.router import (
    _to_public,
    _visible_to_caller,
    public_router,
    router,
)
from app.modules.tax_strategies.schemas import PublicTaxStrategy


class _FakeStrategy:
    """Minimal duck-typed stand-in for TaxStrategy in projection tests."""

    def __init__(self, **kwargs: object) -> None:
        self.strategy_id = kwargs.get("strategy_id", "CLR-012")
        self.name = kwargs.get("name", "Concessional super contributions")
        self.categories = kwargs.get("categories", ["Recommendations"])
        self.implementation_text = kwargs.get("implementation_text", "impl body")
        self.explanation_text = kwargs.get("explanation_text", "expl body")
        self.ato_sources = kwargs.get("ato_sources", ["ITAA 1997 s 290-25"])
        self.case_refs = kwargs.get("case_refs", [])
        self.fy_applicable_from = kwargs.get("fy_applicable_from")
        self.fy_applicable_to = kwargs.get("fy_applicable_to")
        self.version = kwargs.get("version", 1)
        self.tenant_id = kwargs.get("tenant_id", "platform")
        self.status = kwargs.get("status", "published")
        self.superseded_by_strategy_id = kwargs.get("superseded_by_strategy_id")
        self.source_ref = kwargs.get("source_ref", "STP-012")


def test_admin_router_registers_expected_routes() -> None:
    paths = {r.path for r in router.routes}
    assert "/api/v1/admin/tax-strategies" in paths
    assert "/api/v1/admin/tax-strategies/pipeline-stats" in paths
    assert "/api/v1/admin/tax-strategies/{strategy_id}" in paths
    assert "/api/v1/admin/tax-strategies/{strategy_id}/research" in paths
    assert "/api/v1/admin/tax-strategies/{strategy_id}/draft" in paths
    assert "/api/v1/admin/tax-strategies/{strategy_id}/enrich" in paths
    assert "/api/v1/admin/tax-strategies/{strategy_id}/submit" in paths
    assert "/api/v1/admin/tax-strategies/{strategy_id}/approve" in paths
    assert "/api/v1/admin/tax-strategies/{strategy_id}/reject" in paths


def test_public_router_registers_expected_routes() -> None:
    paths = {r.path for r in public_router.routes}
    assert "/api/v1/tax-strategies/public" in paths
    assert "/api/v1/tax-strategies/{strategy_id}/public" in paths


def test_to_public_omits_source_ref() -> None:
    """FR-008: source_ref MUST NEVER appear in the public projection."""
    strategy = _FakeStrategy(source_ref="STP-012")
    projected = _to_public(strategy)
    assert isinstance(projected, PublicTaxStrategy)
    # Ensure the Pydantic model has no source_ref field at all.
    assert "source_ref" not in projected.model_dump()
    assert "source_ref" not in PublicTaxStrategy.model_fields


def test_to_public_tags_platform_flag_correctly() -> None:
    platform = _FakeStrategy(tenant_id="platform")
    overlay = _FakeStrategy(tenant_id="tenant-uuid-abc")
    assert _to_public(platform).is_platform is True
    assert _to_public(overlay).is_platform is False


def test_visible_to_caller_requires_published_and_live() -> None:
    live = _FakeStrategy(status="published", superseded_by_strategy_id=None)
    superseded = _FakeStrategy(status="published", superseded_by_strategy_id="CLR-999")
    draft = _FakeStrategy(status="drafted")
    in_review = _FakeStrategy(status="in_review")
    archived = _FakeStrategy(status="archived")

    assert _visible_to_caller(live) is True
    assert _visible_to_caller(superseded) is False
    assert _visible_to_caller(draft) is False
    assert _visible_to_caller(in_review) is False
    assert _visible_to_caller(archived) is False
