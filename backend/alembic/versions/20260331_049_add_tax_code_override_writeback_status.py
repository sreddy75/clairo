"""Add writeback_status to tax_code_overrides.

Spec 049: Xero Tax Code Write-Back.
Adds writeback_status VARCHAR(20) NOT NULL DEFAULT 'pending_sync' to tax_code_overrides.

Revision ID: 049_tco_writeback_status
Revises: 049_add_xero_writeback_tables
Create Date: 2026-03-31
"""

import sqlalchemy as sa
from alembic import op

revision = "049_tco_writeback_status"
down_revision = "049_add_xero_writeback_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tax_code_overrides",
        sa.Column(
            "writeback_status",
            sa.String(20),
            nullable=False,
            server_default="pending_sync",
        ),
    )


def downgrade() -> None:
    op.drop_column("tax_code_overrides", "writeback_status")
