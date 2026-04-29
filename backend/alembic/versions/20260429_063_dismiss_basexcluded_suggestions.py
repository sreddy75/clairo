"""Dismiss pre-existing BASEXCLUDED tax code suggestions.

Spec 063: One-time cleanup — set status='dismissed' on TaxCodeSuggestion
rows where tax_type='BASEXCLUDED' and status='pending'. These transactions
are not BAS-reportable and should never appear in the uncoded count or
client request queue. New suggestion generation already filters them out
(Spec 046); this migration cleans up rows created before that guard existed.

Revision ID: 063_dismiss_basexcluded
Revises: 062_fix_rls_nullif
Create Date: 2026-04-29
"""

import sqlalchemy as sa
from alembic import op

revision: str = "063_dismiss_basexcluded"
down_revision: str | None = "062_fix_rls_nullif"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE tax_code_suggestions
            SET
                status = 'dismissed',
                resolved_at = NOW(),
                dismissal_reason = 'bas_excluded_auto_cleanup'
            WHERE
                upper(original_tax_type) = 'BASEXCLUDED'
                AND status = 'pending'
            """
        )
    )


def downgrade() -> None:
    # Data-only migration — downgrade is intentionally a no-op.
    # Restoring dismissed BASEXCLUDED suggestions would reintroduce the bug.
    pass
