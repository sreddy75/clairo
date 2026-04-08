"""Test factories for tax planning module models."""

import uuid

import factory
from factory import LazyFunction

from app.modules.tax_planning.models import TaxPlan, TaxPlanMessage, TaxScenario


class TaxPlanFactory(factory.Factory):
    """Factory for tax plans."""

    class Meta:
        model = TaxPlan

    id = LazyFunction(uuid.uuid4)
    tenant_id = LazyFunction(uuid.uuid4)
    xero_connection_id = LazyFunction(uuid.uuid4)
    financial_year = "2026"
    entity_type = "individual"
    status = "draft"
    data_source = "xero"
    financials_data = LazyFunction(
        lambda: {
            "total_income": 120000,
            "total_deductions": 15000,
            "taxable_income": 105000,
        }
    )
    tax_position = LazyFunction(
        lambda: {
            "estimated_tax": 26092,
            "tax_rate": 0.325,
        }
    )


class TaxScenarioFactory(factory.Factory):
    """Factory for tax plan scenarios."""

    class Meta:
        model = TaxScenario

    id = LazyFunction(uuid.uuid4)
    tenant_id = LazyFunction(uuid.uuid4)
    tax_plan_id = LazyFunction(uuid.uuid4)
    title = "Salary Sacrifice to Super"
    description = "Redirect $10,000 pre-tax income to superannuation"
    assumptions = LazyFunction(lambda: {"salary_sacrifice_amount": 10000})
    impact_data = LazyFunction(lambda: {"tax_saving": 3250, "net_benefit": 2500})
    risk_rating = "low"
    sort_order = 0


class TaxPlanMessageFactory(factory.Factory):
    """Factory for tax plan chat messages."""

    class Meta:
        model = TaxPlanMessage

    id = LazyFunction(uuid.uuid4)
    tenant_id = LazyFunction(uuid.uuid4)
    tax_plan_id = LazyFunction(uuid.uuid4)
    role = "user"
    content = "What are the best tax strategies for this client?"


def create_plan_with_scenarios(
    tenant_id: uuid.UUID,
    connection_id: uuid.UUID,
    entity_type: str = "individual",
    scenario_count: int = 2,
) -> tuple:
    """Create a tax plan with scenarios for testing.

    Returns (TaxPlan, list[TaxScenario]).
    Objects are detached — caller must add to session and flush.
    """
    plan = TaxPlanFactory(
        tenant_id=tenant_id,
        xero_connection_id=connection_id,
        entity_type=entity_type,
    )
    scenarios = [
        TaxScenarioFactory(
            tenant_id=tenant_id,
            tax_plan_id=plan.id,
            sort_order=i,
        )
        for i in range(scenario_count)
    ]
    return plan, scenarios
