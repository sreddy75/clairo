"""add feedback tables

Revision ID: 5a25648fbac1
Revises: 047_client_classification
Create Date: 2026-03-15 18:31:51.049097+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Revision identifiers
revision: str = '5a25648fbac1'
down_revision: str | None = '047_client_classification'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'feedback_submissions',
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('submitter_id', sa.UUID(), nullable=False),
        sa.Column('submitter_name', sa.String(length=255), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=True),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=True),
        sa.Column('audio_file_key', sa.String(length=500), nullable=True),
        sa.Column('audio_duration_seconds', sa.Integer(), nullable=True),
        sa.Column('transcript', sa.Text(), nullable=True),
        sa.Column('brief_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('brief_markdown', sa.Text(), nullable=True),
        sa.Column('conversation_complete', sa.Boolean(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_feedback_submissions_tenant_id', 'feedback_submissions', ['tenant_id'])
    op.create_index('ix_feedback_submissions_tenant_status', 'feedback_submissions', ['tenant_id', 'status'])
    op.create_index('ix_feedback_submissions_tenant_submitter', 'feedback_submissions', ['tenant_id', 'submitter_id'])
    op.create_index('ix_feedback_submissions_tenant_type', 'feedback_submissions', ['tenant_id', 'type'])

    op.create_table(
        'feedback_messages',
        sa.Column('submission_id', sa.UUID(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_type', sa.String(length=20), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['submission_id'], ['feedback_submissions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_feedback_messages_submission_created', 'feedback_messages', ['submission_id', 'created_at'])

    op.create_table(
        'feedback_comments',
        sa.Column('submission_id', sa.UUID(), nullable=False),
        sa.Column('author_id', sa.UUID(), nullable=False),
        sa.Column('author_name', sa.String(length=255), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['submission_id'], ['feedback_submissions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_feedback_comments_submission', 'feedback_comments', ['submission_id'])


def downgrade() -> None:
    op.drop_table('feedback_comments')
    op.drop_table('feedback_messages')
    op.drop_table('feedback_submissions')
