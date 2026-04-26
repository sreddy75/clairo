"""Phase 12 T111 — Export warns loudly when estimated figures remain.

Spec 059 FR-016: when at least one scenario still has a `source_tags.* ==
"estimated"` entry at export time, the PDF/HTML pack renders a prominent
warning banner at the top and marks affected figures with an asterisk so the
accountant can't accidentally send unconfirmed AI numbers to the client.

We render the Jinja template directly (no weasyprint) — faster, and it's the
template content that carries the contract, not the PDF binary.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from jinja2 import Environment, FileSystemLoader


@pytest.fixture
def template_env() -> Environment:
    template_dir = (
        Path(__file__).resolve().parents[4] / "app" / "modules" / "tax_planning" / "templates"
    )
    return Environment(loader=FileSystemLoader(str(template_dir)), autoescape=True)


def _render(
    env: Environment,
    *,
    has_estimated_figures: bool,
    scenarios: list | None = None,
) -> str:
    template = env.get_template("tax_plan_export.html")

    # DotDict pattern used by the export path so Jinja can dot-access.
    class DotDict(dict):
        __getattr__ = dict.get

    tax_position = DotDict(
        {
            "net_position": 5000.0,
            "total_tax_payable": 30000.0,
            "taxable_income": 100000.0,
            "gross_tax": 30000.0,
            "medicare_levy": 0,
            "help_repayment": 0,
            "effective_rate_pct": 30.0,
            "calculation_method": "company_small_business",
            "credits_applied": DotDict(
                {
                    "payg_instalments": 25000.0,
                    "payg_withholding": 0,
                    "franking_credits": 0,
                    "total": 25000.0,
                }
            ),
            "offsets": DotDict({}),
        }
    )

    return template.render(
        practice_name="Test Practice",
        client_name="Test Client",
        financial_year="2025-26",
        entity_type_label="Company",
        tax_position=tax_position,
        scenarios=scenarios or [],
        include_scenarios=True,
        messages=[],
        include_conversation=False,
        generated_date="18 April 2026",
        ai_disclaimer="This is an AI-generated estimate.",
        has_estimated_figures=has_estimated_figures,
    )


def _scenario(estimated: bool) -> SimpleNamespace:
    # Full impact_data shape so the scenarios section renders without errors.
    return SimpleNamespace(
        title="Prepay rent",
        description="Prepay 12 months",
        impact_data={
            "before": {"taxable_income": 100000.0, "tax_payable": 30000.0},
            "after": {"taxable_income": 75000.0, "tax_payable": 22500.0},
            "change": {
                "taxable_income_change": -25000.0,
                "tax_saving": 7500.0,
            },
        },
        assumptions={"items": ["25k prepayment"]},
        risk_rating="conservative",
        compliance_notes="s82KZM",
        cash_flow_impact=-19000.0,
        source_tags={"impact_data.after.tax_payable": "estimated" if estimated else "confirmed"},
    )


def test_export_warns_when_estimated_figures_remain(template_env: Environment) -> None:
    html = _render(template_env, has_estimated_figures=True, scenarios=[_scenario(estimated=True)])
    assert "AI-estimated" in html, "warning banner copy missing"
    assert "Review before sharing" in html, "banner header missing"


def test_export_no_warning_when_all_confirmed(template_env: Environment) -> None:
    html = _render(
        template_env, has_estimated_figures=False, scenarios=[_scenario(estimated=False)]
    )
    assert "AI-estimated" not in html
    assert "Review before sharing" not in html
