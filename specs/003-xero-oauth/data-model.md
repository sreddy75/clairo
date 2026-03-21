# Data Model: Xero OAuth & Connection Management

**Spec**: 003-xero-oauth | **Date**: 2025-12-28

---

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                           TENANT                                     │
│                     (from Spec 002)                                  │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                │ 1:N
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      XERO_CONNECTIONS                                │
├─────────────────────────────────────────────────────────────────────┤
│ id                    UUID (PK)                                      │
│ tenant_id             UUID (FK -> tenants.id) [RLS]                 │
│ xero_tenant_id        VARCHAR(50) - Xero's organization ID          │
│ organization_name     VARCHAR(255)                                   │
│ status                ENUM (active, needs_reauth, disconnected)     │
│ ─────────────────────────────────────────────────────────────────── │
│ access_token          TEXT (encrypted)                               │
│ refresh_token         TEXT (encrypted)                               │
│ token_expires_at      TIMESTAMPTZ                                    │
│ scopes                TEXT[] - granted scopes                        │
│ ─────────────────────────────────────────────────────────────────── │
│ rate_limit_daily_remaining    INTEGER                                │
│ rate_limit_minute_remaining   INTEGER                                │
│ rate_limit_reset_at           TIMESTAMPTZ                            │
│ ─────────────────────────────────────────────────────────────────── │
│ connected_by          UUID (FK -> practice_users.id)                │
│ connected_at          TIMESTAMPTZ                                    │
│ last_used_at          TIMESTAMPTZ                                    │
│ created_at            TIMESTAMPTZ                                    │
│ updated_at            TIMESTAMPTZ                                    │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                │ 1:N
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   XERO_OAUTH_STATES                                  │
│              (Temporary - cleaned up after use)                      │
├─────────────────────────────────────────────────────────────────────┤
│ id                    UUID (PK)                                      │
│ tenant_id             UUID (FK -> tenants.id)                       │
│ user_id               UUID (FK -> practice_users.id)                │
│ state                 VARCHAR(64) UNIQUE - CSRF token               │
│ code_verifier         VARCHAR(128) - PKCE verifier                  │
│ redirect_uri          TEXT                                           │
│ expires_at            TIMESTAMPTZ                                    │
│ created_at            TIMESTAMPTZ                                    │
│ used_at               TIMESTAMPTZ NULL                               │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Enum Definitions

### XeroConnectionStatus

```python
class XeroConnectionStatus(str, Enum):
    ACTIVE = "active"              # Connection healthy, tokens valid
    NEEDS_REAUTH = "needs_reauth"  # Refresh failed, user must re-authorize
    DISCONNECTED = "disconnected"  # User disconnected, tokens revoked
```

---

## Table Definitions

### xero_connections

Primary table storing Xero organization connections per tenant.

```sql
CREATE TYPE xero_connection_status AS ENUM ('active', 'needs_reauth', 'disconnected');

CREATE TABLE xero_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    -- Xero Organization Identity
    xero_tenant_id VARCHAR(50) NOT NULL,
    organization_name VARCHAR(255) NOT NULL,
    status xero_connection_status NOT NULL DEFAULT 'active',

    -- OAuth Tokens (encrypted at application level)
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    token_expires_at TIMESTAMPTZ NOT NULL,
    scopes TEXT[] NOT NULL,

    -- Rate Limiting
    rate_limit_daily_remaining INTEGER DEFAULT 5000,
    rate_limit_minute_remaining INTEGER DEFAULT 60,
    rate_limit_reset_at TIMESTAMPTZ,

    -- Audit
    connected_by UUID REFERENCES practice_users(id),
    connected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    UNIQUE(tenant_id, xero_tenant_id)
);

-- Indexes
CREATE INDEX idx_xero_connections_tenant_id ON xero_connections(tenant_id);
CREATE INDEX idx_xero_connections_xero_tenant_id ON xero_connections(xero_tenant_id);
CREATE INDEX idx_xero_connections_status ON xero_connections(status) WHERE status = 'active';
CREATE INDEX idx_xero_connections_token_expires ON xero_connections(token_expires_at)
    WHERE status = 'active';

-- Row Level Security
ALTER TABLE xero_connections ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_xero_connections ON xero_connections
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

-- Updated at trigger
CREATE TRIGGER xero_connections_updated_at
    BEFORE UPDATE ON xero_connections
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

### xero_oauth_states

Temporary storage for OAuth state during authorization flow. Records are cleaned up after use or expiry.

```sql
CREATE TABLE xero_oauth_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES practice_users(id) ON DELETE CASCADE,

    -- OAuth State
    state VARCHAR(64) NOT NULL UNIQUE,
    code_verifier VARCHAR(128) NOT NULL,
    redirect_uri TEXT NOT NULL,

    -- Lifecycle
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    used_at TIMESTAMPTZ  -- Set when state is consumed
);

-- Indexes
CREATE INDEX idx_xero_oauth_states_state ON xero_oauth_states(state);
CREATE INDEX idx_xero_oauth_states_expires ON xero_oauth_states(expires_at);

-- No RLS needed - state lookup is by state value, not tenant
-- Validation happens after lookup by checking tenant/user match

-- Cleanup job: DELETE FROM xero_oauth_states WHERE expires_at < NOW() OR used_at IS NOT NULL;
```

---

## SQLAlchemy Models

### XeroConnection

```python
from sqlalchemy import Column, String, Text, DateTime, Enum, ForeignKey, ARRAY, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

class XeroConnectionStatus(str, enum.Enum):
    ACTIVE = "active"
    NEEDS_REAUTH = "needs_reauth"
    DISCONNECTED = "disconnected"


class XeroConnection(Base):
    __tablename__ = "xero_connections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)

    # Xero Organization
    xero_tenant_id = Column(String(50), nullable=False)
    organization_name = Column(String(255), nullable=False)
    status = Column(
        Enum(XeroConnectionStatus, name="xero_connection_status"),
        nullable=False,
        default=XeroConnectionStatus.ACTIVE
    )

    # Tokens (encrypted)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=False)
    token_expires_at = Column(DateTime(timezone=True), nullable=False)
    scopes = Column(ARRAY(Text), nullable=False)

    # Rate Limiting
    rate_limit_daily_remaining = Column(Integer, default=5000)
    rate_limit_minute_remaining = Column(Integer, default=60)
    rate_limit_reset_at = Column(DateTime(timezone=True))

    # Audit
    connected_by = Column(UUID(as_uuid=True), ForeignKey("practice_users.id"))
    connected_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    last_used_at = Column(DateTime(timezone=True))

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant", back_populates="xero_connections")
    connected_by_user = relationship("PracticeUser", foreign_keys=[connected_by])

    __table_args__ = (
        UniqueConstraint("tenant_id", "xero_tenant_id", name="uq_xero_connection_tenant_org"),
    )

    # Computed Properties
    @property
    def is_active(self) -> bool:
        return self.status == XeroConnectionStatus.ACTIVE

    @property
    def needs_refresh(self) -> bool:
        """Token needs refresh if expiring within 5 minutes."""
        if not self.token_expires_at:
            return True
        return datetime.utcnow() + timedelta(minutes=5) >= self.token_expires_at

    @property
    def is_rate_limited(self) -> bool:
        """Check if currently rate limited."""
        return (self.rate_limit_minute_remaining or 0) <= 0
```

### XeroOAuthState

```python
class XeroOAuthState(Base):
    __tablename__ = "xero_oauth_states"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("practice_users.id"), nullable=False)

    state = Column(String(64), nullable=False, unique=True)
    code_verifier = Column(String(128), nullable=False)
    redirect_uri = Column(Text, nullable=False)

    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    used_at = Column(DateTime(timezone=True))

    # Relationships
    tenant = relationship("Tenant")
    user = relationship("PracticeUser")

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() >= self.expires_at

    @property
    def is_used(self) -> bool:
        return self.used_at is not None

    @property
    def is_valid(self) -> bool:
        return not self.is_expired and not self.is_used
```

---

## Pydantic Schemas

### Request Schemas

```python
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID

class XeroConnectRequest(BaseModel):
    """Request to initiate Xero OAuth flow."""
    redirect_uri: str = Field(..., description="Where to redirect after OAuth")

class XeroCallbackRequest(BaseModel):
    """OAuth callback parameters."""
    code: str = Field(..., description="Authorization code from Xero")
    state: str = Field(..., description="State parameter for CSRF validation")

class XeroDisconnectRequest(BaseModel):
    """Request to disconnect a Xero organization."""
    reason: str | None = Field(None, description="Optional reason for audit")
```

### Response Schemas

```python
class XeroConnectionResponse(BaseModel):
    """Xero connection details."""
    id: UUID
    xero_tenant_id: str
    organization_name: str
    status: XeroConnectionStatus
    scopes: list[str]
    connected_at: datetime
    last_used_at: datetime | None

    # Rate limit info (for admins)
    rate_limit_daily_remaining: int | None = None
    rate_limit_minute_remaining: int | None = None

    model_config = ConfigDict(from_attributes=True)

class XeroConnectionSummary(BaseModel):
    """Summary for list views."""
    id: UUID
    organization_name: str
    status: XeroConnectionStatus
    connected_at: datetime

    model_config = ConfigDict(from_attributes=True)

class XeroAuthUrlResponse(BaseModel):
    """OAuth authorization URL."""
    auth_url: str
    state: str  # For client-side state management if needed

class XeroConnectionListResponse(BaseModel):
    """List of connections."""
    connections: list[XeroConnectionSummary]
    total: int
```

---

## Alembic Migration

```python
"""003_xero_oauth

Revision ID: 003_xero_oauth
Revises: 002_auth_multitenancy
Create Date: 2025-12-28

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '003_xero_oauth'
down_revision = '002_auth_multitenancy'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum
    xero_connection_status = postgresql.ENUM(
        'active', 'needs_reauth', 'disconnected',
        name='xero_connection_status'
    )
    xero_connection_status.create(op.get_bind())

    # Create xero_connections table
    op.create_table(
        'xero_connections',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),

        sa.Column('xero_tenant_id', sa.String(50), nullable=False),
        sa.Column('organization_name', sa.String(255), nullable=False),
        sa.Column('status', xero_connection_status, nullable=False,
                  server_default='active'),

        sa.Column('access_token', sa.Text, nullable=False),
        sa.Column('refresh_token', sa.Text, nullable=False),
        sa.Column('token_expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('scopes', postgresql.ARRAY(sa.Text), nullable=False),

        sa.Column('rate_limit_daily_remaining', sa.Integer, server_default='5000'),
        sa.Column('rate_limit_minute_remaining', sa.Integer, server_default='60'),
        sa.Column('rate_limit_reset_at', sa.DateTime(timezone=True)),

        sa.Column('connected_by', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('practice_users.id')),
        sa.Column('connected_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('last_used_at', sa.DateTime(timezone=True)),

        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),

        sa.UniqueConstraint('tenant_id', 'xero_tenant_id',
                           name='uq_xero_connection_tenant_org'),
    )

    # Create indexes
    op.create_index('idx_xero_connections_tenant_id', 'xero_connections', ['tenant_id'])
    op.create_index('idx_xero_connections_xero_tenant_id', 'xero_connections',
                    ['xero_tenant_id'])
    op.create_index('idx_xero_connections_status', 'xero_connections', ['status'],
                    postgresql_where=sa.text("status = 'active'"))
    op.create_index('idx_xero_connections_token_expires', 'xero_connections',
                    ['token_expires_at'],
                    postgresql_where=sa.text("status = 'active'"))

    # Enable RLS
    op.execute('ALTER TABLE xero_connections ENABLE ROW LEVEL SECURITY')
    op.execute("""
        CREATE POLICY tenant_isolation_xero_connections ON xero_connections
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    """)

    # Create xero_oauth_states table
    op.create_table(
        'xero_oauth_states',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('practice_users.id', ondelete='CASCADE'), nullable=False),

        sa.Column('state', sa.String(64), nullable=False, unique=True),
        sa.Column('code_verifier', sa.String(128), nullable=False),
        sa.Column('redirect_uri', sa.Text, nullable=False),

        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('used_at', sa.DateTime(timezone=True)),
    )

    op.create_index('idx_xero_oauth_states_state', 'xero_oauth_states', ['state'])
    op.create_index('idx_xero_oauth_states_expires', 'xero_oauth_states', ['expires_at'])

    # Add relationship to Tenant model (update tenants table if needed)
    # This is handled in the model, not migration


def downgrade() -> None:
    op.drop_table('xero_oauth_states')
    op.drop_table('xero_connections')
    op.execute('DROP TYPE xero_connection_status')
```

---

## Token Encryption

Tokens are encrypted at application level using AES-256-GCM:

```python
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os
import base64

class TokenEncryption:
    """Encrypt/decrypt OAuth tokens using AES-256-GCM."""

    def __init__(self, key: str):
        # Key should be 32 bytes, base64 encoded in config
        self.key = base64.b64decode(key)
        if len(self.key) != 32:
            raise ValueError("Encryption key must be 32 bytes")
        self.aesgcm = AESGCM(self.key)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt token, return base64(nonce + ciphertext)."""
        nonce = os.urandom(12)  # 96-bit nonce for GCM
        ciphertext = self.aesgcm.encrypt(nonce, plaintext.encode(), None)
        return base64.b64encode(nonce + ciphertext).decode()

    def decrypt(self, encrypted: str) -> str:
        """Decrypt token from base64(nonce + ciphertext)."""
        data = base64.b64decode(encrypted)
        nonce = data[:12]
        ciphertext = data[12:]
        plaintext = self.aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode()
```

---

## Audit Events

The following audit events are logged to the existing `audit_logs` table:

| Event Type | Description |
|------------|-------------|
| `integration.xero.oauth_started` | User initiated OAuth flow |
| `integration.xero.connected` | Successfully connected organization |
| `integration.xero.disconnected` | User disconnected organization |
| `integration.xero.token_refreshed` | Automatic token refresh |
| `integration.xero.token_refresh_failed` | Token refresh failed |
| `integration.xero.rate_limited` | Hit rate limit |
| `integration.xero.authorization_required` | Connection needs re-auth |
