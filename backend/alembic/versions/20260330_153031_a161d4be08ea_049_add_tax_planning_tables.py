"""049: add tax planning tables

Revision ID: a161d4be08ea
Revises: 5a25648fbac1
Create Date: 2026-03-30 15:30:31.921942+00:00

Creates: tax_rate_configs, tax_plans, tax_scenarios, tax_plan_messages
Seeds: 2025-26 Australian tax rate configurations
"""

import uuid
from collections.abc import Sequence
from datetime import date

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# Revision identifiers
revision: str = "a161d4be08ea"
down_revision: str | None = "5a25648fbac1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create tax planning tables and seed 2025-26 rate data."""

    # 1. tax_rate_configs
    op.create_table(
        "tax_rate_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("financial_year", sa.String(10), nullable=False),
        sa.Column("rate_type", sa.String(50), nullable=False),
        sa.Column("rates_data", postgresql.JSONB, nullable=False),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("financial_year", "rate_type", name="uq_tax_rate_config_year_type"),
    )
    op.create_index("ix_tax_rate_configs_financial_year", "tax_rate_configs", ["financial_year"])

    # 2. tax_plans
    op.create_table(
        "tax_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "xero_connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("xero_connections.id"),
            nullable=False,
        ),
        sa.Column("financial_year", sa.String(10), nullable=False),
        sa.Column("entity_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("data_source", sa.String(30), nullable=False),
        sa.Column("financials_data", postgresql.JSONB, nullable=True),
        sa.Column("tax_position", postgresql.JSONB, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("xero_report_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("xero_connection_id", "financial_year", name="uq_tax_plan_connection_fy"),
    )
    op.create_index("ix_tax_plans_tenant_status", "tax_plans", ["tenant_id", "status"])
    op.create_index("ix_tax_plans_xero_connection_id", "tax_plans", ["xero_connection_id"])

    # 3. tax_scenarios
    op.create_table(
        "tax_scenarios",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "tax_plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tax_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("assumptions", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("impact_data", postgresql.JSONB, nullable=False),
        sa.Column("risk_rating", sa.String(20), nullable=False),
        sa.Column("compliance_notes", sa.Text, nullable=True),
        sa.Column("cash_flow_impact", sa.Numeric(15, 2), nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_tax_scenarios_tax_plan_id", "tax_scenarios", ["tax_plan_id"])

    # 4. tax_plan_messages
    op.create_table(
        "tax_plan_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "tax_plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tax_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column(
            "scenario_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("token_count", sa.Integer, nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_tax_plan_messages_plan_id_created", "tax_plan_messages", ["tax_plan_id", "created_at"]
    )

    # 5. Seed 2025-26 tax rate configurations
    effective = date(2025, 7, 1)
    fy = "2025-26"

    tax_rate_configs = sa.table(
        "tax_rate_configs",
        sa.column("id", postgresql.UUID),
        sa.column("financial_year", sa.String),
        sa.column("rate_type", sa.String),
        sa.column("rates_data", postgresql.JSONB),
        sa.column("effective_from", sa.Date),
        sa.column("notes", sa.Text),
    )

    seed_data = [
        {
            "id": str(uuid.uuid4()),
            "financial_year": fy,
            "rate_type": "individual",
            "rates_data": {
                "brackets": [
                    {"min": 0, "max": 18200, "rate": 0.00},
                    {"min": 18201, "max": 45000, "rate": 0.16},
                    {"min": 45001, "max": 135000, "rate": 0.30},
                    {"min": 135001, "max": 190000, "rate": 0.37},
                    {"min": 190001, "max": None, "rate": 0.45},
                ]
            },
            "effective_from": effective,
            "notes": "2025-26 individual tax rates per Stage 3 tax cuts",
        },
        {
            "id": str(uuid.uuid4()),
            "financial_year": fy,
            "rate_type": "company",
            "rates_data": {
                "small_business_rate": 0.25,
                "standard_rate": 0.30,
                "small_business_turnover_threshold": 50000000,
            },
            "effective_from": effective,
            "notes": "Company tax rates — 25% small business (turnover < $50M), 30% standard",
        },
        {
            "id": str(uuid.uuid4()),
            "financial_year": fy,
            "rate_type": "trust",
            "rates_data": {"undistributed_rate": 0.47},
            "effective_from": effective,
            "notes": "Trust rate on undistributed income",
        },
        {
            "id": str(uuid.uuid4()),
            "financial_year": fy,
            "rate_type": "medicare",
            "rates_data": {
                "rate": 0.02,
                "low_income_threshold_single": 26000,
                "phase_in_threshold_single": 32500,
                "low_income_threshold_family": 43846,
                "shade_in_rate": 0.10,
            },
            "effective_from": effective,
            "notes": "Medicare Levy 2% with low-income thresholds",
        },
        {
            "id": str(uuid.uuid4()),
            "financial_year": fy,
            "rate_type": "lito",
            "rates_data": {
                "max_offset": 700,
                "full_offset_threshold": 37500,
                "first_reduction_rate": 0.05,
                "first_reduction_threshold": 45000,
                "second_reduction_rate": 0.015,
                "second_reduction_threshold": 66667,
            },
            "effective_from": effective,
            "notes": "Low Income Tax Offset — max $700, reducing above $37,500",
        },
        {
            "id": str(uuid.uuid4()),
            "financial_year": fy,
            "rate_type": "help",
            "rates_data": {
                "thresholds": [
                    {"min": 54435, "max": 62850, "rate": 0.01},
                    {"min": 62851, "max": 66620, "rate": 0.02},
                    {"min": 66621, "max": 70618, "rate": 0.025},
                    {"min": 70619, "max": 74855, "rate": 0.03},
                    {"min": 74856, "max": 79346, "rate": 0.035},
                    {"min": 79347, "max": 84107, "rate": 0.04},
                    {"min": 84108, "max": 89154, "rate": 0.045},
                    {"min": 89155, "max": 94503, "rate": 0.05},
                    {"min": 94504, "max": 100174, "rate": 0.055},
                    {"min": 100175, "max": 106185, "rate": 0.06},
                    {"min": 106186, "max": 112556, "rate": 0.065},
                    {"min": 112557, "max": 119310, "rate": 0.07},
                    {"min": 119311, "max": 126467, "rate": 0.075},
                    {"min": 126468, "max": 134056, "rate": 0.08},
                    {"min": 134057, "max": 142100, "rate": 0.085},
                    {"min": 142101, "max": 150626, "rate": 0.09},
                    {"min": 150627, "max": 159663, "rate": 0.095},
                    {"min": 159664, "max": None, "rate": 0.10},
                ]
            },
            "effective_from": effective,
            "notes": "HELP/HECS repayment thresholds 2025-26",
        },
    ]

    op.bulk_insert(tax_rate_configs, seed_data)


def downgrade() -> None:
    """Drop tax planning tables."""
    op.drop_table("tax_plan_messages")
    op.drop_table("tax_scenarios")
    op.drop_table("tax_plans")
    op.drop_table("tax_rate_configs")
