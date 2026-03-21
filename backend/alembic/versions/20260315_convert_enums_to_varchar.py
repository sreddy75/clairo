"""Convert tax code resolution enum columns to varchar.

SQLAlchemy Enum type sends Python enum names (uppercase) but PostgreSQL
expects lowercase values. Converting to varchar avoids the type mismatch.

Revision ID: 046_enum_to_varchar
Revises: 046_tax_code_resolution
Create Date: 2026-03-15
"""

from alembic import op

revision = "046_enum_to_varchar"
down_revision = "046_tax_code_resolution"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE tax_code_suggestions "
        "ALTER COLUMN status TYPE VARCHAR(20) USING status::text"
    )
    op.execute(
        "ALTER TABLE tax_code_suggestions "
        "ALTER COLUMN source_type TYPE VARCHAR(20) USING source_type::text"
    )
    op.execute(
        "ALTER TABLE tax_code_suggestions "
        "ALTER COLUMN confidence_tier TYPE VARCHAR(20) USING confidence_tier::text"
    )
    op.execute(
        "ALTER TABLE tax_code_overrides "
        "ALTER COLUMN source_type TYPE VARCHAR(20) USING source_type::text"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE tax_code_overrides "
        "ALTER COLUMN source_type TYPE tax_code_suggestion_source_type "
        "USING source_type::tax_code_suggestion_source_type"
    )
    op.execute(
        "ALTER TABLE tax_code_suggestions "
        "ALTER COLUMN confidence_tier TYPE confidence_tier "
        "USING confidence_tier::confidence_tier"
    )
    op.execute(
        "ALTER TABLE tax_code_suggestions "
        "ALTER COLUMN source_type TYPE tax_code_suggestion_source_type "
        "USING source_type::tax_code_suggestion_source_type"
    )
    op.execute(
        "ALTER TABLE tax_code_suggestions "
        "ALTER COLUMN status TYPE tax_code_suggestion_status "
        "USING status::tax_code_suggestion_status"
    )
