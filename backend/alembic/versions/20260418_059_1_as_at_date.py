"""Tax plan as-at date override.

Spec 059.1 (follow-on from 059): adds a nullable `as_at_date` column to
`tax_plans` so accountants can anchor projections to a BAS quarter end
(e.g. 31 Mar) rather than the latest Xero reconciliation date.

Revision ID: 059_1_as_at_date
Revises: 059_tax_planning_correctness
Create Date: 2026-04-18
"""

import sqlalchemy as sa
from alembic import op

revision: str = "059_1_as_at_date"
down_revision: str | None = "059_tax_planning_correctness"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable — null preserves the pre-059.1 behaviour (effective_date falls
    # back to the last reconciliation date). Existing alpha plans get NULL
    # and keep rendering the same numbers until the accountant sets a BAS
    # quarter anchor from the UI.
    op.add_column(
        "tax_plans",
        sa.Column("as_at_date", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tax_plans", "as_at_date")
