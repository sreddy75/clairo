"""Add is_deleted to tax_code_overrides.

Spec 049 (line items editor): Supports marking an original Xero line item
for deletion from the write-back payload without removing the override record.

Revision ID: 049_tco_is_deleted
Revises: 049_tco_split_cols
Create Date: 2026-04-08
"""

import sqlalchemy as sa
from alembic import op

revision = "049_tco_is_deleted"
down_revision = "049_tco_split_cols"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tax_code_overrides",
        sa.Column(
            "is_deleted",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("tax_code_overrides", "is_deleted")
