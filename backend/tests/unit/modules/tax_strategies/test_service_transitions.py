"""Unit tests for TaxStrategyService._transition_status (Spec 060 T018).

These tests cover the state-machine edges defined in data-model §1.2.
The audit event emission path requires a live session + audit infrastructure
and is exercised in the integration tests (T022).
"""

from __future__ import annotations

import pytest

from app.modules.tax_strategies.service import _ALLOWED_TRANSITIONS


@pytest.mark.parametrize(
    "edge",
    [
        ("stub", "researching"),
        ("researching", "drafted"),
        ("drafted", "enriched"),
        ("enriched", "in_review"),
        ("in_review", "approved"),
        ("approved", "published"),
        ("in_review", "drafted"),  # reject
        ("published", "superseded"),
    ],
)
def test_happy_path_edges_are_allowed(edge: tuple[str, str]) -> None:
    assert edge in _ALLOWED_TRANSITIONS


@pytest.mark.parametrize(
    "edge",
    [
        ("stub", "published"),  # FR-011 cannot skip pipeline
        ("stub", "in_review"),
        ("stub", "approved"),
        ("published", "drafted"),  # cannot rewind past approval
        ("superseded", "published"),
        ("archived", "published"),
    ],
)
def test_illegal_edges_are_denied(edge: tuple[str, str]) -> None:
    assert edge not in _ALLOWED_TRANSITIONS


def test_archive_is_allowed_from_any_active_status() -> None:
    """A manual kill-switch — archive from any non-terminal status."""
    active_statuses = [
        "stub",
        "researching",
        "drafted",
        "enriched",
        "in_review",
        "approved",
        "published",
    ]
    for status in active_statuses:
        assert (status, "archived") in _ALLOWED_TRANSITIONS, (
            f"Expected archive allowed from {status}"
        )


def test_supersede_requires_published_source() -> None:
    """Only a published strategy can transition to superseded."""
    assert ("published", "superseded") in _ALLOWED_TRANSITIONS
    for not_published in ("stub", "drafted", "approved"):
        assert (not_published, "superseded") not in _ALLOWED_TRANSITIONS
