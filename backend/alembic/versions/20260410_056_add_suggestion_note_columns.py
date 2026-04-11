"""Add note columns to tax_code_suggestions.

Spec 056: BAS UX Polish & Xero Status Sync.
Adds per-suggestion notes with optional Xero sync status.
Migrates existing dismissal_reason values to note_text.

Revision ID: 056_suggestion_notes
Revises: 049_tco_is_deleted
Create Date: 2026-04-10
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "056_suggestion_notes"
down_revision = "049_tco_is_deleted"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tax_code_suggestions",
        sa.Column("note_text", sa.Text, nullable=True),
    )
    op.add_column(
        "tax_code_suggestions",
        sa.Column(
            "note_updated_by",
            UUID(as_uuid=True),
            sa.ForeignKey("practice_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "tax_code_suggestions",
        sa.Column("note_updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Migrate existing dismissal_reason values to note_text
    op.execute(
        """
        UPDATE tax_code_suggestions
        SET note_text = dismissal_reason,
            note_updated_at = resolved_at
        WHERE dismissal_reason IS NOT NULL
          AND note_text IS NULL
        """
    )

    # Partial index for efficient "has note" queries
    op.create_index(
        "ix_tax_code_suggestions_has_note",
        "tax_code_suggestions",
        ["session_id"],
        postgresql_where=sa.text("note_text IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_tax_code_suggestions_has_note", "tax_code_suggestions")
    op.drop_column("tax_code_suggestions", "note_updated_at")
    op.drop_column("tax_code_suggestions", "note_updated_by")
    op.drop_column("tax_code_suggestions", "note_text")
