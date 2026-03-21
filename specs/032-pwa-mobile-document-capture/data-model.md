# Data Model: PWA & Mobile + Document Capture

**Feature**: 032-pwa-mobile-document-capture
**Version**: 1.0.0

---

## Overview

This spec introduces both backend (PostgreSQL) and frontend (IndexedDB) data models for PWA functionality.

---

## Backend Models (PostgreSQL)

### Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         clients                                  │
│                    (from Spec 030)                               │
├─────────────────────────────────────────────────────────────────┤
│ id: UUID (PK)                                                   │
│ tenant_id: UUID (FK)                                            │
│ email: str                                                      │
│ ...                                                             │
└────────────────────┬───────────────────┬────────────────────────┘
                     │                   │
                     │ 1                 │ 1
                     │                   │
                     ▼ *                 ▼ *
┌─────────────────────────────┐  ┌─────────────────────────────┐
│     push_subscriptions      │  │   webauthn_credentials      │
├─────────────────────────────┤  ├─────────────────────────────┤
│ id: UUID (PK)               │  │ id: UUID (PK)               │
│ client_id: UUID (FK)        │  │ client_id: UUID (FK)        │
│ tenant_id: UUID (FK)        │  │ tenant_id: UUID (FK)        │
│ endpoint: str               │  │ credential_id: bytes        │
│ p256dh_key: str             │  │ public_key: bytes           │
│ auth_key: str               │  │ sign_count: int             │
│ user_agent: str             │  │ device_name: str            │
│ is_active: bool             │  │ is_active: bool             │
│ created_at: datetime        │  │ created_at: datetime        │
│ last_used_at: datetime      │  │ last_used_at: datetime      │
└─────────────────────────────┘  └─────────────────────────────┘
                     │
                     │ 1
                     │
                     ▼ *
┌─────────────────────────────┐
│    push_notification_logs   │
├─────────────────────────────┤
│ id: UUID (PK)               │
│ subscription_id: UUID (FK)  │
│ notification_type: str      │
│ title: str                  │
│ body: str                   │
│ data: JSONB                 │
│ sent_at: datetime           │
│ delivered_at: datetime?     │
│ clicked_at: datetime?       │
│ error_message: str?         │
└─────────────────────────────┘

┌─────────────────────────────┐
│   pwa_installation_events   │
├─────────────────────────────┤
│ id: UUID (PK)               │
│ client_id: UUID (FK)?       │
│ tenant_id: UUID (FK)        │
│ event_type: str             │
│ user_agent: str             │
│ platform: str               │
│ metadata: JSONB             │
│ created_at: datetime        │
└─────────────────────────────┘
```

---

## Entity Definitions

### PushSubscription

Stores Web Push API subscription data for each client device.

```python
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid

class PushSubscription(Base):
    """Web Push subscription for a client device."""

    __tablename__ = "push_subscriptions"

    id: UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: UUID = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    tenant_id: UUID = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)

    # Web Push subscription data
    endpoint: str = Column(Text, nullable=False)
    p256dh_key: str = Column(String(255), nullable=False)  # Base64 encoded
    auth_key: str = Column(String(255), nullable=False)    # Base64 encoded

    # Device info
    user_agent: str = Column(Text, nullable=True)
    device_name: str = Column(String(255), nullable=True)  # e.g., "iPhone 14"

    # Status
    is_active: bool = Column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at: datetime = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at: datetime = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    client = relationship("Client", back_populates="push_subscriptions")
    notification_logs = relationship("PushNotificationLog", back_populates="subscription")

    __table_args__ = (
        # Unique constraint on endpoint (one subscription per device)
        UniqueConstraint("endpoint", name="uq_push_subscriptions_endpoint"),
        # Multi-tenant index
        Index("ix_push_subscriptions_tenant_client", "tenant_id", "client_id"),
    )
```

**Field Notes**:
- `endpoint`: FCM/browser push endpoint URL
- `p256dh_key`: Public key for encrypting push payloads
- `auth_key`: Authentication secret
- `is_active`: Set to false when subscription fails delivery

---

### WebAuthnCredential

Stores passkey/biometric credentials for quick authentication.

```python
class WebAuthnCredential(Base):
    """WebAuthn credential for biometric authentication."""

    __tablename__ = "webauthn_credentials"

    id: UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: UUID = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    tenant_id: UUID = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)

    # WebAuthn credential data
    credential_id: bytes = Column(LargeBinary, nullable=False, unique=True)
    public_key: bytes = Column(LargeBinary, nullable=False)
    sign_count: int = Column(Integer, default=0, nullable=False)

    # Credential metadata
    device_name: str = Column(String(255), nullable=True)  # e.g., "Face ID"
    aaguid: bytes = Column(LargeBinary, nullable=True)     # Authenticator identifier

    # Status
    is_active: bool = Column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at: datetime = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at: datetime = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    client = relationship("Client", back_populates="webauthn_credentials")

    __table_args__ = (
        Index("ix_webauthn_credentials_credential_id", "credential_id"),
        Index("ix_webauthn_credentials_tenant_client", "tenant_id", "client_id"),
    )
```

**Field Notes**:
- `credential_id`: Unique identifier for the credential (from authenticator)
- `public_key`: COSE-encoded public key for signature verification
- `sign_count`: Counter to detect cloned authenticators
- `aaguid`: Identifies the authenticator type (e.g., Touch ID vs hardware key)

---

### PushNotificationLog

Tracks push notification delivery and engagement.

```python
class NotificationType(str, Enum):
    NEW_REQUEST = "new_request"
    URGENT_REQUEST = "urgent_request"
    REQUEST_REMINDER = "request_reminder"
    REQUEST_OVERDUE = "request_overdue"
    NEW_MESSAGE = "new_message"
    BAS_READY = "bas_ready"

class PushNotificationLog(Base):
    """Log of push notifications sent."""

    __tablename__ = "push_notification_logs"

    id: UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscription_id: UUID = Column(UUID(as_uuid=True), ForeignKey("push_subscriptions.id"), nullable=False, index=True)

    # Notification content
    notification_type: str = Column(String(50), nullable=False)
    title: str = Column(String(255), nullable=False)
    body: str = Column(Text, nullable=False)
    data: dict = Column(JSONB, default={})  # Click action, deep link, etc.

    # Delivery tracking
    sent_at: datetime = Column(DateTime(timezone=True), server_default=func.now())
    delivered_at: datetime = Column(DateTime(timezone=True), nullable=True)
    clicked_at: datetime = Column(DateTime(timezone=True), nullable=True)

    # Error tracking
    fcm_message_id: str = Column(String(255), nullable=True)
    error_message: str = Column(Text, nullable=True)

    # Relationships
    subscription = relationship("PushSubscription", back_populates="notification_logs")

    __table_args__ = (
        Index("ix_push_notification_logs_sent_at", "sent_at"),
        Index("ix_push_notification_logs_type_sent", "notification_type", "sent_at"),
    )
```

**Field Notes**:
- `data`: Contains deep link URL and any action-specific data
- `fcm_message_id`: Firebase message ID for delivery tracking
- Click/delivery tracking enables analytics on notification effectiveness

---

### PWAInstallationEvent

Tracks PWA installation and permission events for analytics.

```python
class PWAEventType(str, Enum):
    INSTALL_PROMPT_SHOWN = "install_prompt_shown"
    INSTALL_PROMPT_ACCEPTED = "install_prompt_accepted"
    INSTALL_PROMPT_DISMISSED = "install_prompt_dismissed"
    APP_INSTALLED = "app_installed"
    PUSH_PERMISSION_GRANTED = "push_permission_granted"
    PUSH_PERMISSION_DENIED = "push_permission_denied"
    BIOMETRIC_REGISTERED = "biometric_registered"

class PWAInstallationEvent(Base):
    """PWA installation and permission events for analytics."""

    __tablename__ = "pwa_installation_events"

    id: UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: UUID = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=True, index=True)
    tenant_id: UUID = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)

    # Event details
    event_type: str = Column(String(50), nullable=False)
    user_agent: str = Column(Text, nullable=True)
    platform: str = Column(String(50), nullable=True)  # ios, android, desktop

    # Additional metadata
    metadata: dict = Column(JSONB, default={})

    # Timestamp
    created_at: datetime = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_pwa_events_tenant_type", "tenant_id", "event_type"),
        Index("ix_pwa_events_created_at", "created_at"),
    )
```

---

## Frontend Models (IndexedDB)

### Database Schema

```typescript
// Database name: clairo-portal
// Version: 1

interface ClairoPortalDB extends DBSchema {
  'upload-queue': {
    key: string;
    value: UploadQueueItem;
    indexes: {
      'by-status': string;
      'by-request': string;
      'by-created': number;
    };
  };

  'cached-requests': {
    key: string;
    value: CachedRequest;
    indexes: {
      'by-cached-at': number;
      'by-status': string;
    };
  };

  'cached-dashboard': {
    key: 'dashboard';
    value: CachedDashboard;
  };

  'captured-pages': {
    key: string;
    value: CapturedPage;
    indexes: {
      'by-session': string;
      'by-order': number;
    };
  };

  'settings': {
    key: string;
    value: unknown;
  };
}
```

---

### UploadQueueItem

Stores documents waiting to be uploaded when offline.

```typescript
interface UploadQueueItem {
  // Identifiers
  id: string;                    // UUID
  requestId: string;             // Document request ID
  clientId: string;              // Client ID

  // File data
  fileName: string;              // Original or generated filename
  mimeType: string;              // image/jpeg, application/pdf
  fileData: ArrayBuffer;         // Binary file content
  fileSize: number;              // Size in bytes

  // Status tracking
  status: 'queued' | 'uploading' | 'failed' | 'completed';
  retryCount: number;            // Max 3 retries
  errorMessage: string | null;   // Last error message

  // Timestamps
  createdAt: number;             // Date.now()
  lastAttempt: number | null;    // Last upload attempt time
  completedAt: number | null;    // When upload succeeded
}
```

**Usage**:
```typescript
// Add to queue
async function queueUpload(
  requestId: string,
  file: Blob,
  fileName: string
): Promise<string> {
  const db = await openDB<ClairoPortalDB>('clairo-portal', 1);

  const item: UploadQueueItem = {
    id: crypto.randomUUID(),
    requestId,
    clientId: getCurrentClientId(),
    fileName,
    mimeType: file.type,
    fileData: await file.arrayBuffer(),
    fileSize: file.size,
    status: 'queued',
    retryCount: 0,
    errorMessage: null,
    createdAt: Date.now(),
    lastAttempt: null,
    completedAt: null,
  };

  await db.put('upload-queue', item);
  return item.id;
}
```

---

### CachedRequest

Stores document requests for offline viewing.

```typescript
interface CachedRequest {
  // Request data (from API)
  id: string;
  title: string;
  description: string;
  status: 'pending' | 'responded' | 'reviewed' | 'completed';
  priority: 'normal' | 'high' | 'urgent';
  dueDate: string | null;        // ISO date string
  createdAt: string;
  accountantName: string;
  attachmentsCount: number;

  // Cache metadata
  cachedAt: number;              // When cached
  version: number;               // For cache invalidation
}
```

---

### CachedDashboard

Stores dashboard summary for offline viewing.

```typescript
interface CachedDashboard {
  // Summary counts
  pendingCount: number;
  urgentCount: number;
  overdueCount: number;
  completedCount: number;

  // Recent requests (minimal data)
  recentRequests: Array<{
    id: string;
    title: string;
    status: string;
    priority: string;
    dueDate: string | null;
  }>;

  // Accountant info
  accountant: {
    name: string;
    email: string;
    phone: string | null;
  };

  // Cache metadata
  cachedAt: number;
  clientId: string;
}
```

---

### CapturedPage

Stores pages during multi-page document capture.

```typescript
interface CapturedPage {
  id: string;                    // UUID
  sessionId: string;             // Capture session ID
  pageNumber: number;            // Order in document
  imageData: ArrayBuffer;        // Processed image
  thumbnail: ArrayBuffer;        // Small preview (200px width)
  width: number;
  height: number;
  capturedAt: number;

  // Quality metrics
  qualityScore: number;          // 0-100
  warnings: string[];            // e.g., ["blurry", "dark"]
}
```

**Usage**:
```typescript
// Multi-page capture session
interface CaptureSession {
  id: string;
  requestId: string;
  startedAt: number;
  pages: CapturedPage[];
}

async function addPageToSession(
  sessionId: string,
  imageBlob: Blob,
  quality: QualityResult
): Promise<void> {
  const db = await openDB<ClairoPortalDB>('clairo-portal', 1);

  const existingPages = await db.getAllFromIndex('captured-pages', 'by-session', sessionId);
  const pageNumber = existingPages.length + 1;

  // Generate thumbnail
  const thumbnail = await createThumbnail(imageBlob, 200);

  const page: CapturedPage = {
    id: crypto.randomUUID(),
    sessionId,
    pageNumber,
    imageData: await imageBlob.arrayBuffer(),
    thumbnail: await thumbnail.arrayBuffer(),
    width: quality.resolution.width,
    height: quality.resolution.height,
    capturedAt: Date.now(),
    qualityScore: calculateQualityScore(quality),
    warnings: quality.suggestions,
  };

  await db.put('captured-pages', page);
}
```

---

## Pydantic Schemas

### Push Subscription Schemas

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID

class PushSubscriptionCreate(BaseModel):
    """Request to register a push subscription."""
    endpoint: str = Field(..., description="Web Push endpoint URL")
    keys: dict = Field(..., description="p256dh and auth keys")
    user_agent: Optional[str] = None
    device_name: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "endpoint": "https://fcm.googleapis.com/fcm/send/...",
                "keys": {
                    "p256dh": "BEl62iUYgU...",
                    "auth": "7L7VLd..."
                },
                "device_name": "iPhone 14 Pro"
            }
        }

class PushSubscriptionResponse(BaseModel):
    """Push subscription details."""
    id: UUID
    device_name: Optional[str]
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime]

class PushSubscriptionList(BaseModel):
    """List of push subscriptions for a client."""
    subscriptions: list[PushSubscriptionResponse]
    total: int
```

---

### WebAuthn Schemas

```python
class WebAuthnRegistrationChallenge(BaseModel):
    """Challenge for WebAuthn registration."""
    challenge: str = Field(..., description="Base64-encoded challenge")
    rp: dict = Field(..., description="Relying party info")
    user: dict = Field(..., description="User info")
    timeout: int = 60000

class WebAuthnRegistrationResponse(BaseModel):
    """Response from WebAuthn registration."""
    id: str = Field(..., description="Credential ID")
    response: dict = Field(..., description="Attestation response")

class WebAuthnAuthChallenge(BaseModel):
    """Challenge for WebAuthn authentication."""
    challenge: str
    timeout: int = 60000
    rp_id: str

class WebAuthnAuthResponse(BaseModel):
    """Response from WebAuthn authentication."""
    id: str
    response: dict

class WebAuthnCredentialResponse(BaseModel):
    """WebAuthn credential details."""
    id: UUID
    device_name: Optional[str]
    created_at: datetime
    last_used_at: Optional[datetime]
```

---

### PWA Analytics Schemas

```python
class PWAInstallEvent(BaseModel):
    """PWA installation event."""
    event_type: str = Field(..., pattern="^(install_prompt_shown|install_prompt_accepted|install_prompt_dismissed|app_installed)$")
    platform: Optional[str] = None
    metadata: Optional[dict] = None

class PWAPermissionEvent(BaseModel):
    """Permission grant event."""
    permission_type: str = Field(..., pattern="^(push|biometric)$")
    granted: bool
    metadata: Optional[dict] = None

class ClientPWAStatus(BaseModel):
    """PWA status for a client."""
    client_id: UUID
    has_push_subscription: bool
    push_subscription_count: int
    has_webauthn_credential: bool
    last_notification_sent: Optional[datetime]
    last_notification_clicked: Optional[datetime]
```

---

## Migration Script

```python
"""Add PWA tables for push subscriptions and WebAuthn

Revision ID: 032_pwa_tables
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    # Push subscriptions table
    op.create_table(
        'push_subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clients.id'), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('endpoint', sa.Text, nullable=False),
        sa.Column('p256dh_key', sa.String(255), nullable=False),
        sa.Column('auth_key', sa.String(255), nullable=False),
        sa.Column('user_agent', sa.Text, nullable=True),
        sa.Column('device_name', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean, default=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
    )

    op.create_unique_constraint('uq_push_subscriptions_endpoint', 'push_subscriptions', ['endpoint'])
    op.create_index('ix_push_subscriptions_client_id', 'push_subscriptions', ['client_id'])
    op.create_index('ix_push_subscriptions_tenant_client', 'push_subscriptions', ['tenant_id', 'client_id'])

    # WebAuthn credentials table
    op.create_table(
        'webauthn_credentials',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clients.id'), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('credential_id', sa.LargeBinary, nullable=False, unique=True),
        sa.Column('public_key', sa.LargeBinary, nullable=False),
        sa.Column('sign_count', sa.Integer, default=0, nullable=False),
        sa.Column('device_name', sa.String(255), nullable=True),
        sa.Column('aaguid', sa.LargeBinary, nullable=True),
        sa.Column('is_active', sa.Boolean, default=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index('ix_webauthn_credentials_client_id', 'webauthn_credentials', ['client_id'])
    op.create_index('ix_webauthn_credentials_credential_id', 'webauthn_credentials', ['credential_id'])

    # Push notification logs table
    op.create_table(
        'push_notification_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('subscription_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('push_subscriptions.id'), nullable=False),
        sa.Column('notification_type', sa.String(50), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('body', sa.Text, nullable=False),
        sa.Column('data', postgresql.JSONB, default={}),
        sa.Column('sent_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('clicked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('fcm_message_id', sa.String(255), nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
    )

    op.create_index('ix_push_notification_logs_subscription_id', 'push_notification_logs', ['subscription_id'])
    op.create_index('ix_push_notification_logs_sent_at', 'push_notification_logs', ['sent_at'])

    # PWA installation events table
    op.create_table(
        'pwa_installation_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clients.id'), nullable=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('user_agent', sa.Text, nullable=True),
        sa.Column('platform', sa.String(50), nullable=True),
        sa.Column('metadata', postgresql.JSONB, default={}),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index('ix_pwa_events_tenant_type', 'pwa_installation_events', ['tenant_id', 'event_type'])
    op.create_index('ix_pwa_events_created_at', 'pwa_installation_events', ['created_at'])


def downgrade():
    op.drop_table('pwa_installation_events')
    op.drop_table('push_notification_logs')
    op.drop_table('webauthn_credentials')
    op.drop_table('push_subscriptions')
```

---

## Data Retention

| Table | Retention Policy |
|-------|------------------|
| push_subscriptions | Keep active, delete 30 days after inactive |
| webauthn_credentials | Keep while active, delete on client request |
| push_notification_logs | 90 days |
| pwa_installation_events | 365 days |

### IndexedDB Cleanup

| Store | Cleanup Policy |
|-------|----------------|
| upload-queue | Delete completed after 7 days |
| cached-requests | Delete if cachedAt > 7 days |
| cached-dashboard | Replace on each refresh |
| captured-pages | Delete after PDF generated or 24 hours |
