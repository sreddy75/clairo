"""Add split columns to tax_code_overrides.

Spec 049 (line items & splits): Adds line_amount, line_description,
line_account_code, and is_new_split to support bank transaction split
management in the Clairo UI.

Revision ID: 049_tco_split_cols
Revises: 049_cls_rounds
Create Date: 2026-04-07
"""

import sqlalchemy as sa
from alembic import op

revision = "049_tco_split_cols"
down_revision = "049_cls_rounds"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tax_code_overrides",
        sa.Column("line_amount", sa.Numeric(15, 2), nullable=True),
    )
    op.add_column(
        "tax_code_overrides",
        sa.Column("line_description", sa.Text, nullable=True),
    )
    op.add_column(
        "tax_code_overrides",
        sa.Column("line_account_code", sa.String(50), nullable=True),
    )
    op.add_column(
        "tax_code_overrides",
        sa.Column(
            "is_new_split",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("tax_code_overrides", "is_new_split")
    op.drop_column("tax_code_overrides", "line_account_code")
    op.drop_column("tax_code_overrides", "line_description")
    op.drop_column("tax_code_overrides", "line_amount")
