# Research: Messaging & Request Conversations

**Spec**: 031-messaging-request-conversations
**Date**: 2026-01-01

## Overview

This document covers research on WebSocket implementation, message encryption, real-time scaling, and approval workflow patterns for the messaging feature.

---

## 1. WebSocket Implementation

### FastAPI WebSocket Support

**Decision**: Use FastAPI's native WebSocket support with Redis pub/sub for scaling.

**Rationale**:
- Native FastAPI integration
- Async support aligns with our stack
- Well-documented patterns for authentication
- Starlette WebSocket foundation is battle-tested

**Alternatives Considered**:
- Socket.IO: More features but additional dependency, Python support less mature
- Server-Sent Events: One-directional, not suitable for chat
- Long polling: Higher latency, more server load

### Connection Manager Pattern

```python
# backend/app/core/websocket/manager.py
from typing import Dict, Set
from uuid import UUID
from fastapi import WebSocket
import redis.asyncio as redis

class ConnectionManager:
    """
    Manages WebSocket connections with Redis pub/sub for multi-instance scaling.
    """

    def __init__(self, redis_client: redis.Redis):
        self.active_connections: Dict[UUID, Set[WebSocket]] = {}  # user_id -> connections
        self.redis = redis_client
        self.channel = "websocket_messages"

    async def connect(self, websocket: WebSocket, user_id: UUID):
        """Accept connection and track by user ID."""
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)

    def disconnect(self, websocket: WebSocket, user_id: UUID):
        """Remove connection from tracking."""
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def send_to_user(self, user_id: UUID, message: dict):
        """Send message to specific user (all their connections)."""
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    # Connection may be stale
                    self.disconnect(connection, user_id)

    async def broadcast_via_redis(self, message: dict):
        """Publish message to Redis for multi-instance delivery."""
        await self.redis.publish(self.channel, json.dumps(message))

    async def listen_redis(self):
        """Subscribe to Redis and deliver to local connections."""
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(self.channel)

        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                user_id = UUID(data.get("recipient_id"))
                await self.send_to_user(user_id, data["payload"])
```

### WebSocket Authentication

```python
# backend/app/core/websocket/auth.py
from fastapi import WebSocket, HTTPException
from app.modules.portal.auth.magic_link import MagicLinkService

async def authenticate_websocket(websocket: WebSocket) -> dict:
    """
    Authenticate WebSocket connection using token from query params or first message.
    """
    # Option 1: Token in query params (less secure but simpler)
    token = websocket.query_params.get("token")

    if not token:
        # Option 2: Wait for auth message
        await websocket.accept()
        try:
            auth_message = await asyncio.wait_for(
                websocket.receive_json(),
                timeout=10.0
            )
            token = auth_message.get("token")
        except asyncio.TimeoutError:
            await websocket.close(code=4001, reason="Auth timeout")
            raise HTTPException(401, "Authentication timeout")

    # Verify token
    magic_link_service = MagicLinkService()
    payload = magic_link_service.verify_access_token(token)

    if not payload:
        await websocket.close(code=4002, reason="Invalid token")
        raise HTTPException(401, "Invalid token")

    return payload
```

### WebSocket Protocol

```python
# Message Types (Client → Server)
CLIENT_MESSAGES = {
    "auth": {"token": "jwt_token"},  # Authenticate connection
    "message.send": {
        "conversation_id": "uuid",
        "content": "message text",
        "attachments": ["uuid"]  # Optional attachment IDs
    },
    "message.read": {
        "message_id": "uuid"
    },
    "typing.start": {"conversation_id": "uuid"},
    "typing.stop": {"conversation_id": "uuid"},
    "ping": {}  # Keepalive
}

# Message Types (Server → Client)
SERVER_MESSAGES = {
    "auth.success": {"user_id": "uuid"},
    "auth.error": {"message": "reason"},
    "message.new": {
        "id": "uuid",
        "conversation_id": "uuid",
        "sender_type": "client|accountant",
        "content": "message text",
        "created_at": "iso_datetime"
    },
    "message.read": {
        "message_id": "uuid",
        "read_by": "uuid",
        "read_at": "iso_datetime"
    },
    "typing": {
        "conversation_id": "uuid",
        "user_id": "uuid",
        "is_typing": True
    },
    "notification": {
        "type": "bas_ready|request_new|approval_received",
        "title": "notification title",
        "body": "notification body",
        "link": "/portal/path"
    },
    "pong": {}
}
```

---

## 2. Message Encryption

### Encryption Strategy

**Decision**: Fernet symmetric encryption with per-tenant keys stored in AWS KMS.

**Rationale**:
- AES-128-CBC with HMAC-SHA256 (authenticated encryption)
- Fast for high-volume messaging
- Per-tenant keys for data isolation
- AWS KMS for secure key management

**Alternatives Considered**:
- End-to-end encryption: More secure but complicates server-side search and moderation
- No encryption: Not acceptable for compliance
- Per-message keys: Overhead too high for chat volume

### Encryption Implementation

```python
# backend/app/modules/portal/messaging/encryption.py
from cryptography.fernet import Fernet
from functools import lru_cache
import boto3

class MessageEncryption:
    """
    Handles message content encryption/decryption with per-tenant keys.
    """

    def __init__(self):
        self.kms_client = boto3.client('kms')
        self.key_cache: Dict[UUID, bytes] = {}

    @lru_cache(maxsize=100)
    def _get_tenant_key(self, tenant_id: UUID) -> bytes:
        """
        Get or create encryption key for tenant.
        Keys are stored in KMS and cached locally.
        """
        key_alias = f"alias/clairo-messaging-{tenant_id}"

        try:
            # Try to get existing key
            response = self.kms_client.describe_key(KeyId=key_alias)
            key_id = response['KeyMetadata']['KeyId']
        except self.kms_client.exceptions.NotFoundException:
            # Create new key for tenant
            response = self.kms_client.create_key(
                Description=f"Message encryption key for tenant {tenant_id}",
                KeyUsage='ENCRYPT_DECRYPT',
                Origin='AWS_KMS',
            )
            key_id = response['KeyMetadata']['KeyId']
            self.kms_client.create_alias(
                AliasName=key_alias,
                TargetKeyId=key_id
            )

        # Generate data key for Fernet
        data_key = self.kms_client.generate_data_key(
            KeyId=key_id,
            KeySpec='AES_256'
        )
        return base64.urlsafe_b64encode(data_key['Plaintext'][:32])

    def encrypt(self, content: str, tenant_id: UUID) -> str:
        """Encrypt message content."""
        key = self._get_tenant_key(tenant_id)
        f = Fernet(key)
        return f.encrypt(content.encode()).decode()

    def decrypt(self, encrypted: str, tenant_id: UUID) -> str:
        """Decrypt message content."""
        key = self._get_tenant_key(tenant_id)
        f = Fernet(key)
        return f.decrypt(encrypted.encode()).decode()
```

### Development Environment

```python
# For local development without KMS
class LocalMessageEncryption:
    """Local encryption for development (uses static key)."""

    def __init__(self):
        # Use env variable for local dev key
        self.key = os.getenv(
            "MESSAGE_ENCRYPTION_KEY",
            Fernet.generate_key()
        )
        self.fernet = Fernet(self.key)

    def encrypt(self, content: str, tenant_id: UUID) -> str:
        return self.fernet.encrypt(content.encode()).decode()

    def decrypt(self, encrypted: str, tenant_id: UUID) -> str:
        return self.fernet.decrypt(encrypted.encode()).decode()
```

---

## 3. Scaling WebSocket Connections

### Redis Pub/Sub Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    MULTI-INSTANCE WEBSOCKET                      │
│                                                                  │
│    ┌──────────┐    ┌──────────┐    ┌──────────┐                │
│    │ Instance │    │ Instance │    │ Instance │                │
│    │    A     │    │    B     │    │    C     │                │
│    │ (users   │    │ (users   │    │ (users   │                │
│    │  1-100)  │    │  101-200)│    │  201-300)│                │
│    └────┬─────┘    └────┬─────┘    └────┬─────┘                │
│         │               │               │                        │
│         └───────────────┼───────────────┘                       │
│                         │                                        │
│                    ┌────┴────┐                                  │
│                    │  Redis  │                                  │
│                    │ Pub/Sub │                                  │
│                    └─────────┘                                  │
│                                                                  │
│    Message to User 150:                                         │
│    1. Instance A publishes to Redis                             │
│    2. All instances receive                                     │
│    3. Instance B has User 150 connected                        │
│    4. Instance B delivers to WebSocket                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Connection Limits

**Target**: 10,000 concurrent WebSocket connections

**Configuration**:
```python
# backend/app/config.py
class WebSocketSettings(BaseSettings):
    max_connections_per_user: int = 3  # Multiple tabs/devices
    heartbeat_interval_seconds: int = 30
    connection_timeout_seconds: int = 60
    max_message_size_bytes: int = 65536  # 64KB

    # Redis settings
    redis_channel_prefix: str = "ws:"
    redis_pool_size: int = 10
```

### Heartbeat and Reconnection

```python
# Client-side reconnection logic (TypeScript)
class WebSocketClient {
    private reconnectAttempts = 0;
    private maxReconnectAttempts = 10;
    private reconnectDelay = 1000; // Start with 1 second

    private async reconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error("Max reconnection attempts reached");
            return;
        }

        this.reconnectAttempts++;
        const delay = Math.min(
            this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
            30000 // Max 30 seconds
        );

        await new Promise(resolve => setTimeout(resolve, delay));
        this.connect();
    }

    private handleMessage(data: any) {
        if (data.type === "ping") {
            this.send({ type: "pong" });
        }
        // ... handle other message types
    }
}
```

---

## 4. Conversation Context Linking

### Polymorphic Conversation Context

**Decision**: Use context_type and context_id fields for flexible linking.

**Rationale**:
- Single conversation table handles all use cases
- Easy to query by context
- Extensible for future context types

```python
# Conversation context types
class ConversationContextType(str, Enum):
    REQUEST = "request"       # DocumentRequest conversation
    BAS_PERIOD = "bas_period" # BAS-related conversation
    GENERAL = "general"       # No specific context

# Example queries
async def get_request_conversation(request_id: UUID) -> Conversation:
    """Get or create conversation for a document request."""
    return await self.repo.get_or_create(
        context_type=ConversationContextType.REQUEST,
        context_id=request_id,
    )

async def get_client_conversations(client_id: UUID) -> List[Conversation]:
    """Get all conversations for a client."""
    return await self.repo.list_by_client(client_id)
```

### Request Amendment Tracking

```python
class RequestAmendment(Base):
    """Track changes to requests after client questions."""

    id: UUID
    request_id: UUID
    conversation_id: UUID  # Link to conversation that prompted change

    field_changed: str  # "title", "description", "due_date"
    old_value: str
    new_value: str
    reason: str | None  # Optional reason for change

    changed_by: UUID
    changed_at: datetime
```

---

## 5. BAS Approval Workflow

### Approval States

```python
class ApprovalStatus(str, Enum):
    PENDING = "pending"     # BAS ready, awaiting client review
    APPROVED = "approved"   # Client approved
    RETRACTED = "retracted" # Client retracted approval
    EXPIRED = "expired"     # Approval window expired without action
```

### Approval Audit Data

```python
class BASApproval(Base):
    """
    Records client approval of BAS with full audit trail.
    """
    id: UUID
    bas_period_id: UUID
    client_id: UUID
    tenant_id: UUID

    status: ApprovalStatus

    # Approval details
    approved_at: datetime | None
    approved_by_name: str | None  # Display name at time of approval

    # Retraction details
    retracted_at: datetime | None
    retraction_reason: str | None

    # Audit capture
    ip_address: str
    user_agent: str
    session_id: UUID  # Portal session that performed action

    # Metadata
    bas_summary: dict  # Snapshot of BAS at approval time
    created_at: datetime
```

### Approval Notifications

```python
APPROVAL_NOTIFICATION_FLOW = {
    "bas_ready": {
        "recipient": "client",
        "channels": ["email", "portal", "websocket"],
        "template": "bas_ready_for_review",
    },
    "approval_received": {
        "recipient": "accountant",
        "channels": ["email", "portal"],
        "template": "client_approved_bas",
    },
    "approval_retracted": {
        "recipient": "accountant",
        "channels": ["email", "portal"],
        "template": "client_retracted_approval",
        "urgency": "high",
    },
    "approval_reminder": {
        "recipient": "client",
        "channels": ["email"],
        "template": "approval_reminder",
        "schedule": "48h_before_due",
    },
}
```

---

## 6. Notification Delivery

### Multi-Channel Strategy

```python
class NotificationChannel(str, Enum):
    WEBSOCKET = "websocket"  # Real-time in-app
    EMAIL = "email"          # Async email
    PUSH = "push"            # Mobile push (future)

class NotificationService:
    """
    Delivers notifications across multiple channels.
    """

    async def notify(
        self,
        user_id: UUID,
        user_type: str,  # "client" or "accountant"
        notification_type: str,
        payload: dict,
    ):
        # Get user preferences
        prefs = await self.get_preferences(user_id, user_type)

        # Attempt WebSocket first (if user is online)
        if await self.is_online(user_id):
            await self.send_websocket(user_id, notification_type, payload)

        # Queue email if preferred and not muted
        if prefs.email_enabled and not prefs.is_muted(notification_type):
            await self.queue_email(user_id, notification_type, payload)
```

### Email Notification Templates

```python
MESSAGING_EMAIL_TEMPLATES = {
    "new_message_client": {
        "subject": "New message from {accountant_name}",
        "preview": "{message_preview}",
        "cta": "View Message",
        "cta_url": "/portal/messages/{conversation_id}",
    },
    "new_message_accountant": {
        "subject": "{client_name} sent you a message",
        "preview": "{message_preview}",
        "cta": "Reply",
        "cta_url": "/inbox/{conversation_id}",
    },
    "request_question": {
        "subject": "{client_name} has a question about: {request_title}",
        "preview": "{question_preview}",
        "cta": "Respond",
        "cta_url": "/clients/{client_id}/requests/{request_id}",
    },
    "bas_ready_for_review": {
        "subject": "Your BAS for {period} is ready to review",
        "preview": "GST collected: ${gst_collected}, Net GST: ${net_gst}",
        "cta": "Review & Approve",
        "cta_url": "/portal/bas/{period}/review",
    },
}
```

---

## 7. Frontend Integration

### useWebSocket Hook

```typescript
// frontend/src/hooks/useWebSocket.ts
import { useEffect, useRef, useState, useCallback } from 'react';

interface UseWebSocketOptions {
  url: string;
  token: string;
  onMessage?: (data: any) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
}

export function useWebSocket(options: UseWebSocketOptions) {
  const { url, token, onMessage, onConnect, onDisconnect } = options;
  const wsRef = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const connect = useCallback(() => {
    const ws = new WebSocket(`${url}?token=${token}`);

    ws.onopen = () => {
      setIsConnected(true);
      setError(null);
      onConnect?.();
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      onMessage?.(data);
    };

    ws.onclose = () => {
      setIsConnected(false);
      onDisconnect?.();
      // Auto-reconnect after 3 seconds
      setTimeout(connect, 3000);
    };

    ws.onerror = (event) => {
      setError(new Error('WebSocket error'));
    };

    wsRef.current = ws;
  }, [url, token, onMessage, onConnect, onDisconnect]);

  const send = useCallback((data: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
    };
  }, [connect]);

  return { isConnected, error, send };
}
```

### Message Thread Component

```typescript
// frontend/src/components/messaging/MessageThread.tsx
interface MessageThreadProps {
  conversationId: string;
  messages: Message[];
  onSendMessage: (content: string) => void;
  isTyping?: boolean;
}

export function MessageThread({
  conversationId,
  messages,
  onSendMessage,
  isTyping,
}: MessageThreadProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [input, setInput] = useState('');

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = () => {
    if (input.trim()) {
      onSendMessage(input.trim());
      setInput('');
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
        {isTyping && (
          <div className="text-gray-500 text-sm">Typing...</div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="border-t p-4">
        <MessageInput
          value={input}
          onChange={setInput}
          onSend={handleSend}
          placeholder="Type a message..."
        />
      </div>
    </div>
  );
}
```

---

## Summary of Decisions

| Topic | Decision | Key Reason |
|-------|----------|------------|
| Real-time Protocol | FastAPI WebSocket | Native integration, async |
| Scaling | Redis pub/sub | Multi-instance message delivery |
| Encryption | Fernet + KMS | Fast symmetric, secure key management |
| Conversation Model | Polymorphic context | Flexible linking to requests/BAS |
| Approval Audit | Full capture | IP, user agent, session for compliance |
| Notifications | Multi-channel | WebSocket + email for reliability |
| Read Receipts | Optional | User preference |
