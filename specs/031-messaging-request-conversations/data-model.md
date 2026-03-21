# Data Model: Messaging & Request Conversations

**Spec**: 031-messaging-request-conversations
**Date**: 2026-01-01

## Overview

This document defines the data models for the messaging system, including conversations, messages, BAS approvals, and notification preferences.

---

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    MESSAGING DATA MODEL                                  │
│                                                                         │
│  ┌─────────────────┐         ┌─────────────────┐                       │
│  │     Client      │◄───────►│   Conversation  │                       │
│  │  (from clients) │  1   N  │                 │                       │
│  └─────────────────┘         └────────┬────────┘                       │
│                                       │                                 │
│                                       │ 1                               │
│                                       │                                 │
│                                       ▼ N                               │
│                              ┌─────────────────┐                       │
│                              │     Message     │                       │
│                              │                 │                       │
│                              └────────┬────────┘                       │
│                                       │                                 │
│                                       │ 1                               │
│                                       │                                 │
│                                       ▼ N                               │
│                              ┌─────────────────┐                       │
│                              │ MessageAttach   │                       │
│                              │     ment        │                       │
│                              └─────────────────┘                       │
│                                                                         │
│  ┌─────────────────┐         ┌─────────────────┐                       │
│  │   BASPeriod     │◄───────►│   BASApproval   │                       │
│  │  (from bas)     │  1   1  │                 │                       │
│  └─────────────────┘         └─────────────────┘                       │
│                                                                         │
│  ┌─────────────────┐         ┌─────────────────┐                       │
│  │ DocumentRequest │◄───────►│ RequestAmend    │                       │
│  │  (from portal)  │  1   N  │     ment        │                       │
│  └─────────────────┘         └─────────────────┘                       │
│                                                                         │
│  ┌─────────────────┐                                                   │
│  │ Notification    │                                                   │
│  │  Preference     │                                                   │
│  └─────────────────┘                                                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Entities

### 1. Conversation

**Purpose**: Thread container for messages between accountant and client.

```python
# backend/app/modules/portal/messaging/models.py
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime
import enum

class ConversationContextType(str, enum.Enum):
    REQUEST = "request"       # Linked to DocumentRequest
    BAS_PERIOD = "bas_period" # Linked to BASPeriod
    GENERAL = "general"       # No specific context

class ConversationStatus(str, enum.Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    ARCHIVED = "archived"

class Conversation(Base):
    """
    A conversation thread between an accountant and client.
    Can be linked to a specific request, BAS period, or be general.
    """
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)

    # Context linking (polymorphic)
    context_type = Column(
        Enum(ConversationContextType),
        default=ConversationContextType.GENERAL,
        nullable=False
    )
    context_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    # Status
    status = Column(
        Enum(ConversationStatus),
        default=ConversationStatus.ACTIVE,
        nullable=False
    )

    # Subject (for general conversations)
    subject = Column(String(200), nullable=True)

    # Tracking
    last_message_at = Column(DateTime(timezone=True), nullable=True)
    unread_count_client = Column(Integer, default=0)
    unread_count_accountant = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    messages = relationship("Message", back_populates="conversation", order_by="Message.created_at")
    client = relationship("Client", back_populates="conversations")

    # Indexes
    __table_args__ = (
        Index("ix_conversations_context", "context_type", "context_id"),
        Index("ix_conversations_client_status", "client_id", "status"),
    )
```

**Fields**:

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| id | UUID | No | Primary key |
| tenant_id | UUID | No | Tenant reference (RLS) |
| client_id | UUID | No | Client this conversation belongs to |
| context_type | Enum | No | Type of context (request, bas_period, general) |
| context_id | UUID | Yes | ID of linked request or BAS period |
| status | Enum | No | Conversation status |
| subject | String(200) | Yes | Subject for general conversations |
| last_message_at | DateTime | Yes | Timestamp of most recent message |
| unread_count_client | Integer | No | Unread count for client |
| unread_count_accountant | Integer | No | Unread count for accountant |
| created_at | DateTime | No | Creation timestamp |
| updated_at | DateTime | No | Last update timestamp |
| resolved_at | DateTime | Yes | When conversation was resolved |

---

### 2. Message

**Purpose**: Individual message within a conversation.

```python
class MessageType(str, enum.Enum):
    TEXT = "text"
    SYSTEM = "system"  # System-generated notifications

class SenderType(str, enum.Enum):
    CLIENT = "client"
    ACCOUNTANT = "accountant"
    SYSTEM = "system"

class Message(Base):
    """
    A single message in a conversation.
    Content is encrypted at rest.
    """
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False, index=True)

    # Sender
    sender_type = Column(Enum(SenderType), nullable=False)
    sender_id = Column(UUID(as_uuid=True), nullable=True)  # Null for system messages
    sender_name = Column(String(100), nullable=True)  # Display name at time of sending

    # Content
    message_type = Column(Enum(MessageType), default=MessageType.TEXT, nullable=False)
    content_encrypted = Column(String, nullable=False)  # Fernet encrypted content
    content_preview = Column(String(100), nullable=True)  # Unencrypted preview for notifications

    # Read tracking
    read_at = Column(DateTime(timezone=True), nullable=True)
    read_by_id = Column(UUID(as_uuid=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    edited_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    attachments = relationship("MessageAttachment", back_populates="message")

    # Indexes
    __table_args__ = (
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
    )
```

**Fields**:

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| id | UUID | No | Primary key |
| conversation_id | UUID | No | Parent conversation |
| sender_type | Enum | No | Who sent (client, accountant, system) |
| sender_id | UUID | Yes | ID of sender (null for system) |
| sender_name | String(100) | Yes | Display name at send time |
| message_type | Enum | No | Message type (text, system) |
| content_encrypted | String | No | Fernet encrypted content |
| content_preview | String(100) | Yes | Preview for notifications (unencrypted) |
| read_at | DateTime | Yes | When recipient read the message |
| read_by_id | UUID | Yes | Who read the message |
| created_at | DateTime | No | Creation timestamp |
| edited_at | DateTime | Yes | Edit timestamp |
| deleted_at | DateTime | Yes | Soft delete timestamp |

---

### 3. MessageAttachment

**Purpose**: File attached to a message.

```python
class MessageAttachment(Base):
    """
    File attachment on a message.
    Stored in S3, linked to message.
    """
    __tablename__ = "message_attachments"

    id = Column(UUID(as_uuid=True), primary_key=True)
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id"), nullable=False, index=True)

    # File info
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    storage_key = Column(String(500), nullable=False)  # S3 key
    mime_type = Column(String(100), nullable=False)
    size_bytes = Column(Integer, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    message = relationship("Message", back_populates="attachments")
```

**Fields**:

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| id | UUID | No | Primary key |
| message_id | UUID | No | Parent message |
| filename | String(255) | No | Stored filename |
| original_filename | String(255) | No | Original upload name |
| storage_key | String(500) | No | S3 storage key |
| mime_type | String(100) | No | MIME type |
| size_bytes | Integer | No | File size |
| created_at | DateTime | No | Upload timestamp |

---

### 4. BASApproval

**Purpose**: Records client approval of BAS with full audit trail.

```python
class ApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    RETRACTED = "retracted"

class BASApproval(Base):
    """
    Client approval of a BAS return before lodgement.
    Captures full audit trail for compliance.
    """
    __tablename__ = "bas_approvals"

    id = Column(UUID(as_uuid=True), primary_key=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    bas_period_id = Column(UUID(as_uuid=True), ForeignKey("bas_periods.id"), nullable=False, unique=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)

    # Status
    status = Column(Enum(ApprovalStatus), default=ApprovalStatus.PENDING, nullable=False)

    # Approval details
    approved_at = Column(DateTime(timezone=True), nullable=True)
    approved_by_name = Column(String(100), nullable=True)  # Name at approval time

    # Retraction details
    retracted_at = Column(DateTime(timezone=True), nullable=True)
    retraction_reason = Column(String(500), nullable=True)

    # Audit capture
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent = Column(String(500), nullable=True)
    portal_session_id = Column(UUID(as_uuid=True), nullable=True)

    # BAS snapshot at approval time
    bas_summary = Column(JSONB, nullable=True)
    # Structure: {
    #   "period": "2025-Q4",
    #   "gst_collected": 5000.00,
    #   "gst_paid": 2000.00,
    #   "net_gst": 3000.00,
    #   "lodgement_due": "2026-02-28"
    # }

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    bas_period = relationship("BASPeriod", back_populates="approval")
    client = relationship("Client", back_populates="bas_approvals")
```

**Fields**:

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| id | UUID | No | Primary key |
| tenant_id | UUID | No | Tenant reference (RLS) |
| bas_period_id | UUID | No | BAS period being approved (unique) |
| client_id | UUID | No | Client doing the approval |
| status | Enum | No | Approval status |
| approved_at | DateTime | Yes | Approval timestamp |
| approved_by_name | String(100) | Yes | Approver's name at time |
| retracted_at | DateTime | Yes | Retraction timestamp |
| retraction_reason | String(500) | Yes | Why approval was retracted |
| ip_address | String(45) | Yes | Client IP at approval |
| user_agent | String(500) | Yes | Browser at approval |
| portal_session_id | UUID | Yes | Portal session reference |
| bas_summary | JSONB | Yes | BAS data snapshot |
| created_at | DateTime | No | Creation timestamp |
| updated_at | DateTime | No | Last update timestamp |

---

### 5. RequestAmendment

**Purpose**: Tracks changes to document requests after client questions.

```python
class RequestAmendment(Base):
    """
    Audit trail for request modifications after conversations.
    """
    __tablename__ = "request_amendments"

    id = Column(UUID(as_uuid=True), primary_key=True)
    request_id = Column(UUID(as_uuid=True), ForeignKey("document_requests.id"), nullable=False, index=True)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True)

    # What changed
    field_changed = Column(String(50), nullable=False)  # "title", "description", "due_date"
    old_value = Column(String, nullable=True)
    new_value = Column(String, nullable=True)
    reason = Column(String(500), nullable=True)  # Why the change was made

    # Who changed
    changed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    changed_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    request = relationship("DocumentRequest", back_populates="amendments")
    conversation = relationship("Conversation")

    # Indexes
    __table_args__ = (
        Index("ix_request_amendments_request_created", "request_id", "changed_at"),
    )
```

**Fields**:

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| id | UUID | No | Primary key |
| request_id | UUID | No | Request that was amended |
| conversation_id | UUID | Yes | Conversation that prompted change |
| field_changed | String(50) | No | Which field changed |
| old_value | String | Yes | Previous value |
| new_value | String | Yes | New value |
| reason | String(500) | Yes | Reason for change |
| changed_by | UUID | No | User who made change |
| changed_at | DateTime | No | Change timestamp |

---

### 6. NotificationPreference

**Purpose**: User preferences for notification delivery.

```python
class NotificationPreference(Base):
    """
    User notification preferences for messaging.
    """
    __tablename__ = "notification_preferences"

    id = Column(UUID(as_uuid=True), primary_key=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)

    # User reference (could be accountant or client)
    user_type = Column(String(20), nullable=False)  # "accountant" or "client"
    user_id = Column(UUID(as_uuid=True), nullable=False)

    # Email preferences
    email_new_message = Column(Boolean, default=True)
    email_request_question = Column(Boolean, default=True)
    email_approval_reminder = Column(Boolean, default=True)

    # Digest preferences
    email_digest_enabled = Column(Boolean, default=False)
    email_digest_frequency = Column(String(20), default="daily")  # "daily", "weekly"

    # Do not disturb
    dnd_enabled = Column(Boolean, default=False)
    dnd_start_time = Column(String(5), nullable=True)  # "22:00"
    dnd_end_time = Column(String(5), nullable=True)    # "08:00"

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Indexes
    __table_args__ = (
        UniqueConstraint("user_type", "user_id", name="uq_notification_prefs_user"),
        Index("ix_notification_prefs_user", "user_type", "user_id"),
    )
```

**Fields**:

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| id | UUID | No | Primary key |
| tenant_id | UUID | No | Tenant reference |
| user_type | String(20) | No | Type of user |
| user_id | UUID | No | User ID |
| email_new_message | Boolean | No | Email on new messages |
| email_request_question | Boolean | No | Email on request questions |
| email_approval_reminder | Boolean | No | Email approval reminders |
| email_digest_enabled | Boolean | No | Enable digest emails |
| email_digest_frequency | String(20) | No | Digest frequency |
| dnd_enabled | Boolean | No | Do not disturb enabled |
| dnd_start_time | String(5) | Yes | DND start (HH:MM) |
| dnd_end_time | String(5) | Yes | DND end (HH:MM) |
| created_at | DateTime | No | Creation timestamp |
| updated_at | DateTime | No | Last update timestamp |

---

### 7. WebSocketConnection (Runtime only, not persisted)

**Purpose**: Tracks active WebSocket connections in memory.

```python
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from fastapi import WebSocket

@dataclass
class WebSocketConnection:
    """
    In-memory representation of an active WebSocket connection.
    Not persisted to database.
    """
    websocket: WebSocket
    user_id: UUID
    user_type: str  # "client" or "accountant"
    tenant_id: UUID
    connected_at: datetime
    last_ping: datetime

    # Optional client context
    client_id: UUID | None = None  # For client connections
```

---

## Database Indexes

```sql
-- Conversation indexes
CREATE INDEX ix_conversations_tenant_client ON conversations(tenant_id, client_id);
CREATE INDEX ix_conversations_context ON conversations(context_type, context_id);
CREATE INDEX ix_conversations_client_status ON conversations(client_id, status);
CREATE INDEX ix_conversations_last_message ON conversations(last_message_at DESC);

-- Message indexes
CREATE INDEX ix_messages_conversation_created ON messages(conversation_id, created_at);
CREATE INDEX ix_messages_sender ON messages(sender_type, sender_id);
CREATE INDEX ix_messages_unread ON messages(conversation_id) WHERE read_at IS NULL;

-- BAS Approval indexes
CREATE UNIQUE INDEX ix_bas_approvals_period ON bas_approvals(bas_period_id);
CREATE INDEX ix_bas_approvals_client ON bas_approvals(client_id);
CREATE INDEX ix_bas_approvals_status ON bas_approvals(status) WHERE status = 'pending';

-- Request Amendment indexes
CREATE INDEX ix_request_amendments_request ON request_amendments(request_id, changed_at DESC);

-- Notification Preference indexes
CREATE UNIQUE INDEX uq_notification_prefs_user ON notification_preferences(user_type, user_id);
```

---

## Migrations

```python
# backend/alembic/versions/xxxx_add_messaging_tables.py
"""Add messaging and approval tables

Revision ID: xxxx
Revises: yyyy
Create Date: 2026-01-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

def upgrade():
    # Conversation table
    op.create_table(
        'conversations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('client_id', UUID(as_uuid=True), sa.ForeignKey('clients.id'), nullable=False),
        sa.Column('context_type', sa.String(20), nullable=False, default='general'),
        sa.Column('context_id', UUID(as_uuid=True), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, default='active'),
        sa.Column('subject', sa.String(200), nullable=True),
        sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('unread_count_client', sa.Integer, default=0),
        sa.Column('unread_count_accountant', sa.Integer, default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Message table
    op.create_table(
        'messages',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('conversation_id', UUID(as_uuid=True), sa.ForeignKey('conversations.id'), nullable=False),
        sa.Column('sender_type', sa.String(20), nullable=False),
        sa.Column('sender_id', UUID(as_uuid=True), nullable=True),
        sa.Column('sender_name', sa.String(100), nullable=True),
        sa.Column('message_type', sa.String(20), nullable=False, default='text'),
        sa.Column('content_encrypted', sa.Text, nullable=False),
        sa.Column('content_preview', sa.String(100), nullable=True),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('read_by_id', UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('edited_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Message attachments table
    op.create_table(
        'message_attachments',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('message_id', UUID(as_uuid=True), sa.ForeignKey('messages.id'), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('original_filename', sa.String(255), nullable=False),
        sa.Column('storage_key', sa.String(500), nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=False),
        sa.Column('size_bytes', sa.Integer, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    # BAS Approvals table
    op.create_table(
        'bas_approvals',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('bas_period_id', UUID(as_uuid=True), sa.ForeignKey('bas_periods.id'), nullable=False, unique=True),
        sa.Column('client_id', UUID(as_uuid=True), sa.ForeignKey('clients.id'), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, default='pending'),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approved_by_name', sa.String(100), nullable=True),
        sa.Column('retracted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('retraction_reason', sa.String(500), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('portal_session_id', UUID(as_uuid=True), nullable=True),
        sa.Column('bas_summary', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # Request Amendments table
    op.create_table(
        'request_amendments',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('request_id', UUID(as_uuid=True), sa.ForeignKey('document_requests.id'), nullable=False),
        sa.Column('conversation_id', UUID(as_uuid=True), sa.ForeignKey('conversations.id'), nullable=True),
        sa.Column('field_changed', sa.String(50), nullable=False),
        sa.Column('old_value', sa.Text, nullable=True),
        sa.Column('new_value', sa.Text, nullable=True),
        sa.Column('reason', sa.String(500), nullable=True),
        sa.Column('changed_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('changed_at', sa.DateTime(timezone=True), nullable=False),
    )

    # Notification Preferences table
    op.create_table(
        'notification_preferences',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('user_type', sa.String(20), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('email_new_message', sa.Boolean, default=True),
        sa.Column('email_request_question', sa.Boolean, default=True),
        sa.Column('email_approval_reminder', sa.Boolean, default=True),
        sa.Column('email_digest_enabled', sa.Boolean, default=False),
        sa.Column('email_digest_frequency', sa.String(20), default='daily'),
        sa.Column('dnd_enabled', sa.Boolean, default=False),
        sa.Column('dnd_start_time', sa.String(5), nullable=True),
        sa.Column('dnd_end_time', sa.String(5), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # Create indexes
    op.create_index('ix_conversations_context', 'conversations', ['context_type', 'context_id'])
    op.create_index('ix_conversations_client_status', 'conversations', ['client_id', 'status'])
    op.create_index('ix_messages_conversation_created', 'messages', ['conversation_id', 'created_at'])

def downgrade():
    op.drop_table('notification_preferences')
    op.drop_table('request_amendments')
    op.drop_table('bas_approvals')
    op.drop_table('message_attachments')
    op.drop_table('messages')
    op.drop_table('conversations')
```

---

## Summary

| Entity | Purpose | Key Fields |
|--------|---------|------------|
| Conversation | Message thread container | context_type, context_id, unread counts |
| Message | Individual message | content_encrypted, sender_type, read_at |
| MessageAttachment | File on message | storage_key, mime_type |
| BASApproval | Client BAS sign-off | status, ip_address, bas_summary |
| RequestAmendment | Request change audit | field_changed, old/new_value |
| NotificationPreference | User notification settings | email preferences, DND |
