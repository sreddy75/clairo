"""add practice_clients, exclusions, note_history tables

Revision ID: 9ea16a7e81fb
Revises: 057_reconciliation_fields
Create Date: 2026-04-15 12:40:35.083969+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Revision identifiers
revision: str = '9ea16a7e81fb'
down_revision: str | None = '057_reconciliation_fields'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade database to this revision."""
    # --- practice_clients table ---
    op.create_table('practice_clients',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False, comment='Client business name'),
        sa.Column('abn', sa.String(length=11), nullable=True, comment='Australian Business Number (11 digits)'),
        sa.Column('accounting_software', sa.String(length=20), server_default='unknown', nullable=False, comment='Accounting software: xero, quickbooks, myob, email, other, unknown'),
        sa.Column('xero_connection_id', sa.UUID(), nullable=True, comment='FK to xero_connections (NULL for non-Xero clients)'),
        sa.Column('assigned_user_id', sa.UUID(), nullable=True, comment='Team member responsible for this client'),
        sa.Column('notes', sa.Text(), nullable=True, comment='Persistent client notes (carries across quarters)'),
        sa.Column('notes_updated_at', sa.DateTime(timezone=True), nullable=True, comment='When notes were last edited'),
        sa.Column('notes_updated_by', sa.UUID(), nullable=True, comment='Who last edited notes'),
        sa.Column('manual_status', sa.String(length=20), nullable=True, comment='BAS status for non-Xero clients'),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("accounting_software IN ('xero', 'quickbooks', 'myob', 'email', 'other', 'unknown')", name='ck_practice_clients_software'),
        sa.CheckConstraint("manual_status IS NULL OR manual_status IN ('not_started', 'in_progress', 'completed', 'lodged')", name='ck_practice_clients_manual_status'),
        sa.ForeignKeyConstraint(['assigned_user_id'], ['practice_users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['notes_updated_by'], ['practice_users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['xero_connection_id'], ['xero_connections.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('xero_connection_id'),
    )
    op.create_index('ix_practice_clients_assigned_user_id', 'practice_clients', ['assigned_user_id'])
    op.create_index('ix_practice_clients_tenant_id', 'practice_clients', ['tenant_id'])
    op.create_index('ix_practice_clients_tenant_name', 'practice_clients', ['tenant_id', 'name'])
    op.create_index('ix_practice_clients_tenant_software', 'practice_clients', ['tenant_id', 'accounting_software'])

    # --- client_note_history table ---
    op.create_table('client_note_history',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('client_id', sa.UUID(), nullable=False),
        sa.Column('note_text', sa.Text(), nullable=False, comment='Snapshot of note content at time of change'),
        sa.Column('edited_by', sa.UUID(), nullable=False),
        sa.Column('edited_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['practice_clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['edited_by'], ['practice_users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_client_note_history_tenant_id', 'client_note_history', ['tenant_id'])
    op.create_index('ix_note_history_client_date', 'client_note_history', ['client_id', sa.text('edited_at DESC')])

    # --- client_quarter_exclusions table ---
    op.create_table('client_quarter_exclusions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('client_id', sa.UUID(), nullable=False),
        sa.Column('quarter', sa.SmallInteger(), nullable=False, comment='Quarter number (1-4)'),
        sa.Column('fy_year', sa.String(length=7), nullable=False, comment="Financial year (e.g., '2025-26')"),
        sa.Column('reason', sa.String(length=30), nullable=True, comment='Exclusion reason'),
        sa.Column('reason_detail', sa.Text(), nullable=True, comment="Free text detail (when reason = 'other')"),
        sa.Column('excluded_by', sa.UUID(), nullable=False),
        sa.Column('excluded_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reversed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reversed_by', sa.UUID(), nullable=True),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.CheckConstraint('quarter >= 1 AND quarter <= 4', name='ck_exclusion_quarter_range'),
        sa.ForeignKeyConstraint(['client_id'], ['practice_clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['excluded_by'], ['practice_users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['reversed_by'], ['practice_users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_client_quarter_exclusions_tenant_id', 'client_quarter_exclusions', ['tenant_id'])
    op.create_index('ix_exclusions_tenant_quarter', 'client_quarter_exclusions', ['tenant_id', 'quarter', 'fy_year'])
    op.create_index('uix_client_quarter_exclusion_active', 'client_quarter_exclusions', ['client_id', 'quarter', 'fy_year'], unique=True, postgresql_where=sa.text('reversed_at IS NULL'))

    # --- Add display_name to practice_users ---
    op.add_column('practice_users', sa.Column('display_name', sa.String(length=100), nullable=True, comment='Cached display name from Clerk'))


def downgrade() -> None:
    """Downgrade database from this revision."""
    op.drop_column('practice_users', 'display_name')
    op.drop_table('client_quarter_exclusions')
    op.drop_table('client_note_history')
    op.drop_table('practice_clients')
