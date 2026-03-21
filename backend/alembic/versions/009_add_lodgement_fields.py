"""Add lodgement tracking fields to BAS sessions

Revision ID: 009_add_lodgement_fields
Revises: 008_bas_audit_log
Create Date: 2025-01-01

Spec 011: Interim Lodgement
- Adds lodgement tracking fields to bas_sessions table
- Adds version column for optimistic locking
- Adds partial index on lodged_at for efficient filtering
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = "009_add_lodgement_fields"
down_revision = "008_bas_audit_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add lodgement fields to bas_sessions
    op.add_column(
        "bas_sessions",
        sa.Column(
            "lodged_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp when BAS was marked as lodged",
        ),
    )
    op.add_column(
        "bas_sessions",
        sa.Column(
            "lodged_by",
            UUID(as_uuid=True),
            nullable=True,
            comment="User who recorded the lodgement",
        ),
    )
    op.add_column(
        "bas_sessions",
        sa.Column(
            "lodgement_method",
            sa.String(20),
            nullable=True,
            comment="Lodgement method: ATO_PORTAL, XERO, OTHER",
        ),
    )
    op.add_column(
        "bas_sessions",
        sa.Column(
            "lodgement_method_description",
            sa.String(255),
            nullable=True,
            comment="Description for OTHER lodgement method",
        ),
    )
    op.add_column(
        "bas_sessions",
        sa.Column(
            "ato_reference_number",
            sa.String(50),
            nullable=True,
            comment="ATO lodgement reference number",
        ),
    )
    op.add_column(
        "bas_sessions",
        sa.Column(
            "lodgement_notes",
            sa.Text(),
            nullable=True,
            comment="Additional notes about the lodgement",
        ),
    )

    # Add version column for optimistic locking
    op.add_column(
        "bas_sessions",
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default="1",
            comment="Version for optimistic locking",
        ),
    )

    # Add foreign key constraint for lodged_by
    op.create_foreign_key(
        "fk_bas_sessions_lodged_by_practice_users",
        "bas_sessions",
        "practice_users",
        ["lodged_by"],
        ["id"],
        ondelete="SET NULL",
    )

    # Add partial index for efficient lodgement status filtering
    op.create_index(
        "ix_bas_sessions_lodged_at",
        "bas_sessions",
        ["lodged_at"],
        postgresql_where=sa.text("lodged_at IS NOT NULL"),
    )

    # Add index for due date queries (for deadline notifications)
    op.create_index(
        "ix_bas_periods_due_date",
        "bas_periods",
        ["due_date"],
    )


def downgrade() -> None:
    # Remove indexes
    op.drop_index("ix_bas_periods_due_date", "bas_periods")
    op.drop_index("ix_bas_sessions_lodged_at", "bas_sessions")

    # Remove foreign key
    op.drop_constraint(
        "fk_bas_sessions_lodged_by_practice_users", "bas_sessions", type_="foreignkey"
    )

    # Remove columns
    op.drop_column("bas_sessions", "version")
    op.drop_column("bas_sessions", "lodgement_notes")
    op.drop_column("bas_sessions", "ato_reference_number")
    op.drop_column("bas_sessions", "lodgement_method_description")
    op.drop_column("bas_sessions", "lodgement_method")
    op.drop_column("bas_sessions", "lodged_by")
    op.drop_column("bas_sessions", "lodged_at")
