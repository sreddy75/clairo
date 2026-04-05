"""Test factories for BAS module models."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import factory
from factory import Faker, LazyFunction

from app.modules.bas.models import (
    BASPeriod,
    BASSession,
    TaxCodeSuggestion,
)


class BASPeriodFactory(factory.Factory):
    """Factory for BAS periods."""

    class Meta:
        model = BASPeriod

    id = LazyFunction(uuid.uuid4)
    tenant_id = LazyFunction(uuid.uuid4)
    xero_connection_id = LazyFunction(uuid.uuid4)
    period_start = LazyFunction(lambda: datetime(2025, 7, 1, tzinfo=UTC))
    period_end = LazyFunction(lambda: datetime(2025, 9, 30, tzinfo=UTC))
    period_type = "quarterly"
    financial_year = "2026"


class BASSessionFactory(factory.Factory):
    """Factory for BAS sessions."""

    class Meta:
        model = BASSession

    id = LazyFunction(uuid.uuid4)
    tenant_id = LazyFunction(uuid.uuid4)
    bas_period_id = LazyFunction(uuid.uuid4)
    xero_connection_id = LazyFunction(uuid.uuid4)
    status = "draft"
    created_by = LazyFunction(uuid.uuid4)


class TaxCodeSuggestionFactory(factory.Factory):
    """Factory for AI tax code suggestions."""

    class Meta:
        model = TaxCodeSuggestion

    id = LazyFunction(uuid.uuid4)
    tenant_id = LazyFunction(uuid.uuid4)
    session_id = LazyFunction(uuid.uuid4)
    xero_connection_id = LazyFunction(uuid.uuid4)
    line_item_id = Faker("uuid4")
    original_tax_type = "OUTPUT"
    suggested_tax_type = "INPUT"
    confidence_score = Decimal("0.85")
    confidence_tier = "rule_based"
    suggestion_basis = "AI classification"
    status = "pending"


def create_bas_session_with_suggestions(
    tenant_id: uuid.UUID,
    connection_id: uuid.UUID,
    suggestion_count: int = 3,
) -> tuple:
    """Create a BAS session with suggestions for testing.

    Returns (BASPeriod, BASSession, list[TaxCodeSuggestion]).
    Objects are detached — caller must add to session and flush.
    """
    period = BASPeriodFactory(
        tenant_id=tenant_id,
        xero_connection_id=connection_id,
    )
    session = BASSessionFactory(
        tenant_id=tenant_id,
        bas_period_id=period.id,
        xero_connection_id=connection_id,
    )
    suggestions = [
        TaxCodeSuggestionFactory(
            tenant_id=tenant_id,
            session_id=session.id,
            xero_connection_id=connection_id,
        )
        for _ in range(suggestion_count)
    ]
    return period, session, suggestions
