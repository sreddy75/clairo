"""Fix BAS table foreign keys to reference practice_users instead of users.

Revision ID: 007_fix_bas_user_fks
Revises: 006_bas_workflow
Create Date: 2025-12-29

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "007_fix_bas_user_fks"
down_revision: str | None = "006_bas_workflow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop incorrect foreign key constraints on bas_sessions
    op.drop_constraint("fk_bas_sessions_created_by_users", "bas_sessions", type_="foreignkey")
    op.drop_constraint("fk_bas_sessions_last_modified_by_users", "bas_sessions", type_="foreignkey")
    op.drop_constraint("fk_bas_sessions_approved_by_users", "bas_sessions", type_="foreignkey")

    # Drop incorrect foreign key constraint on bas_adjustments
    op.drop_constraint("fk_bas_adjustments_created_by_users", "bas_adjustments", type_="foreignkey")

    # Add correct foreign key constraints referencing practice_users
    op.create_foreign_key(
        "fk_bas_sessions_created_by_practice_users",
        "bas_sessions",
        "practice_users",
        ["created_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_bas_sessions_last_modified_by_practice_users",
        "bas_sessions",
        "practice_users",
        ["last_modified_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_bas_sessions_approved_by_practice_users",
        "bas_sessions",
        "practice_users",
        ["approved_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_bas_adjustments_created_by_practice_users",
        "bas_adjustments",
        "practice_users",
        ["created_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Drop correct foreign key constraints
    op.drop_constraint(
        "fk_bas_adjustments_created_by_practice_users", "bas_adjustments", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_bas_sessions_approved_by_practice_users", "bas_sessions", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_bas_sessions_last_modified_by_practice_users", "bas_sessions", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_bas_sessions_created_by_practice_users", "bas_sessions", type_="foreignkey"
    )

    # Restore incorrect foreign key constraints referencing users
    op.create_foreign_key(
        "fk_bas_sessions_created_by_users",
        "bas_sessions",
        "users",
        ["created_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_bas_sessions_last_modified_by_users",
        "bas_sessions",
        "users",
        ["last_modified_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_bas_sessions_approved_by_users",
        "bas_sessions",
        "users",
        ["approved_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_bas_adjustments_created_by_users",
        "bas_adjustments",
        "users",
        ["created_by"],
        ["id"],
        ondelete="SET NULL",
    )
