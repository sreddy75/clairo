"""XPM Client and Connection Authorization fields.

Revision ID: 027_xpm_client_auth
Revises: 026_onboarding
Create Date: 2026-01-01

Phase 6b: Client Organization Authorization
- Add connection_type and auth_event_id to xero_connections
- Create xpm_clients table for practice management clients
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Revision identifiers
revision: str = "027_xpm_client_auth"
down_revision: str | None = "026_onboarding"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade database to this revision."""
    # Create new enum types
    xero_connection_type = postgresql.ENUM(
        "practice",
        "client",
        name="xero_connection_type",
        create_type=False,
    )
    xero_connection_type.create(op.get_bind(), checkfirst=True)

    xpm_client_connection_status = postgresql.ENUM(
        "not_connected",
        "connected",
        "disconnected",
        "no_access",
        name="xpm_client_connection_status",
        create_type=False,
    )
    xpm_client_connection_status.create(op.get_bind(), checkfirst=True)

    # Add new columns to xero_connections
    op.add_column(
        "xero_connections",
        sa.Column(
            "connection_type",
            postgresql.ENUM(
                "practice",
                "client",
                name="xero_connection_type",
                create_type=False,
            ),
            nullable=False,
            server_default="practice",
            comment="Whether this is the practice's own Xero or a client's Xero",
        ),
    )
    op.add_column(
        "xero_connections",
        sa.Column(
            "auth_event_id",
            sa.String(50),
            nullable=True,
            comment="Groups connections from the same bulk authorization flow",
        ),
    )

    # Create indexes for new columns
    op.create_index(
        "ix_xero_connections_connection_type",
        "xero_connections",
        ["connection_type"],
    )
    op.create_index(
        "ix_xero_connections_auth_event_id",
        "xero_connections",
        ["auth_event_id"],
    )

    # Create xpm_clients table
    op.create_table(
        "xpm_clients",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column(
            "tenant_id",
            sa.UUID(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            comment="Foreign key to Clairo tenant (the accounting practice)",
        ),
        sa.Column(
            "xpm_client_id",
            sa.String(50),
            nullable=False,
            comment="XPM's unique client identifier",
        ),
        sa.Column(
            "xero_connection_id",
            sa.UUID(),
            sa.ForeignKey("xero_connections.id", ondelete="SET NULL"),
            nullable=True,
            comment="FK to XeroConnection when client's Xero org is authorized",
        ),
        sa.Column(
            "name",
            sa.String(500),
            nullable=False,
            comment="Client business name",
        ),
        sa.Column(
            "abn",
            sa.String(11),
            nullable=True,
            comment="Australian Business Number (11 digits)",
        ),
        sa.Column(
            "email",
            sa.String(255),
            nullable=True,
            comment="Primary contact email",
        ),
        sa.Column(
            "phone",
            sa.String(50),
            nullable=True,
            comment="Primary contact phone",
        ),
        sa.Column(
            "address",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Business address",
        ),
        sa.Column(
            "contact_person",
            sa.String(255),
            nullable=True,
            comment="Primary contact name",
        ),
        sa.Column(
            "xero_org_name",
            sa.String(255),
            nullable=True,
            comment="Cached Xero organization name (for matching)",
        ),
        sa.Column(
            "connection_status",
            postgresql.ENUM(
                "not_connected",
                "connected",
                "disconnected",
                "no_access",
                name="xpm_client_connection_status",
                create_type=False,
            ),
            nullable=False,
            server_default="not_connected",
            comment="Status of Xero organization connection",
        ),
        sa.Column(
            "xero_connected_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When client's Xero org was authorized",
        ),
        sa.Column(
            "xpm_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last update timestamp from XPM",
        ),
        sa.Column(
            "extra_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Additional XPM metadata",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("tenant_id", "xpm_client_id", name="uq_xpm_client_tenant_xpm_id"),
    )

    # Create indexes for xpm_clients
    op.create_index("ix_xpm_clients_tenant_id", "xpm_clients", ["tenant_id"])
    op.create_index("ix_xpm_clients_xpm_client_id", "xpm_clients", ["xpm_client_id"])
    op.create_index("ix_xpm_clients_xero_connection_id", "xpm_clients", ["xero_connection_id"])
    op.create_index("ix_xpm_clients_name", "xpm_clients", ["name"])
    op.create_index("ix_xpm_clients_abn", "xpm_clients", ["abn"])
    op.create_index("ix_xpm_clients_connection_status", "xpm_clients", ["connection_status"])
    op.create_index("ix_xpm_clients_tenant_name", "xpm_clients", ["tenant_id", "name"])
    op.create_index("ix_xpm_clients_tenant_abn", "xpm_clients", ["tenant_id", "abn"])
    op.create_index(
        "ix_xpm_clients_tenant_status", "xpm_clients", ["tenant_id", "connection_status"]
    )

    # Enable RLS on xpm_clients
    op.execute("ALTER TABLE xpm_clients ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY xpm_clients_tenant_isolation ON xpm_clients
        FOR ALL
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    """)


def downgrade() -> None:
    """Downgrade database from this revision."""
    # Drop RLS policy
    op.execute("DROP POLICY IF EXISTS xpm_clients_tenant_isolation ON xpm_clients")

    # Drop xpm_clients table
    op.drop_index("ix_xpm_clients_tenant_status", table_name="xpm_clients")
    op.drop_index("ix_xpm_clients_tenant_abn", table_name="xpm_clients")
    op.drop_index("ix_xpm_clients_tenant_name", table_name="xpm_clients")
    op.drop_index("ix_xpm_clients_connection_status", table_name="xpm_clients")
    op.drop_index("ix_xpm_clients_abn", table_name="xpm_clients")
    op.drop_index("ix_xpm_clients_name", table_name="xpm_clients")
    op.drop_index("ix_xpm_clients_xero_connection_id", table_name="xpm_clients")
    op.drop_index("ix_xpm_clients_xpm_client_id", table_name="xpm_clients")
    op.drop_index("ix_xpm_clients_tenant_id", table_name="xpm_clients")
    op.drop_table("xpm_clients")

    # Drop columns from xero_connections
    op.drop_index("ix_xero_connections_auth_event_id", table_name="xero_connections")
    op.drop_index("ix_xero_connections_connection_type", table_name="xero_connections")
    op.drop_column("xero_connections", "auth_event_id")
    op.drop_column("xero_connections", "connection_type")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS xpm_client_connection_status")
    op.execute("DROP TYPE IF EXISTS xero_connection_type")
