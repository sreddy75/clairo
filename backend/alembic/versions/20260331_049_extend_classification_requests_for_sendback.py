"""Extend classification_requests for multi-round send-back.

Spec 049: Xero Tax Code Write-Back.
Adds parent_request_id (self-ref FK) and round_number to classification_requests.
Removes old UNIQUE(session_id) constraint, adds partial unique index for root requests.

Revision ID: 049_cls_multiround
Revises: 049_tco_writeback_status
Create Date: 2026-03-31
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "049_cls_multiround"
down_revision = "049_tco_writeback_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add parent_request_id — nullable self-referential FK
    op.add_column(
        "classification_requests",
        sa.Column(
            "parent_request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("classification_requests.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # Add round_number — default 1 for all existing records
    op.add_column(
        "classification_requests",
        sa.Column(
            "round_number",
            sa.Integer,
            nullable=False,
            server_default="1",
        ),
    )

    # Drop the old unique constraint on session_id alone (one request per session)
    op.drop_constraint(
        "uq_classification_request_session",
        "classification_requests",
        type_="unique",
    )

    # Add partial unique index: only one root request (no parent) per session
    op.create_index(
        "uq_classification_request_root_session",
        "classification_requests",
        ["session_id"],
        unique=True,
        postgresql_where=sa.text("parent_request_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_classification_request_root_session",
        table_name="classification_requests",
    )
    op.create_unique_constraint(
        "uq_classification_request_session",
        "classification_requests",
        ["session_id"],
    )
    op.drop_column("classification_requests", "round_number")
    op.drop_column("classification_requests", "parent_request_id")
