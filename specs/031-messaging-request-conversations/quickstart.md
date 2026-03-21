# Quickstart Guide: Messaging & Request Conversations

**Spec**: 031-messaging-request-conversations
**Branch**: `031-messaging-request-conversations`
**Module**: `backend/app/modules/portal/messaging/`

## Overview

This guide covers implementing the messaging system with WebSocket real-time delivery, request conversations, and BAS approval workflow.

## Prerequisites

Before implementing this spec:

1. **Spec 030**: Client Portal Foundation - portal infrastructure and authentication
2. **Redis**: Required for WebSocket pub/sub scaling
3. **Notifications Module**: Email delivery
4. **BAS Module**: BAS periods and status

## Quick Verification

```bash
# Verify prerequisites
cd /Users/suren/KR8IT/projects/Personal/BAS
SPECIFY_FEATURE="031-messaging-request-conversations" .specify/scripts/bash/check-prerequisites.sh

# Run tests after implementation
uv run pytest tests/unit/modules/portal/messaging/ -v
uv run pytest tests/integration/api/test_messaging.py -v
uv run pytest tests/integration/api/test_websocket.py -v
```

---

## 1. WebSocket Connection Manager

### Core Connection Manager

```python
# backend/app/core/websocket/manager.py
from typing import Dict, Set
from uuid import UUID
from dataclasses import dataclass
from datetime import datetime, UTC
from fastapi import WebSocket
import redis.asyncio as redis
import json
import asyncio

from app.config import settings


@dataclass
class Connection:
    """Represents an active WebSocket connection."""
    websocket: WebSocket
    user_id: UUID
    user_type: str  # "client" or "accountant"
    tenant_id: UUID
    connected_at: datetime
    last_ping: datetime
    client_id: UUID | None = None


class ConnectionManager:
    """
    Manages WebSocket connections with Redis pub/sub for multi-instance scaling.
    """

    def __init__(self):
        self.connections: Dict[UUID, Set[Connection]] = {}  # user_id -> connections
        self.redis: redis.Redis | None = None
        self.channel = "ws:messages"
        self._pubsub_task: asyncio.Task | None = None

    async def initialize(self):
        """Initialize Redis connection and start pub/sub listener."""
        self.redis = await redis.from_url(settings.REDIS_URL)
        self._pubsub_task = asyncio.create_task(self._listen_pubsub())

    async def shutdown(self):
        """Clean shutdown of connections and Redis."""
        if self._pubsub_task:
            self._pubsub_task.cancel()
        if self.redis:
            await self.redis.close()

    async def connect(
        self,
        websocket: WebSocket,
        user_id: UUID,
        user_type: str,
        tenant_id: UUID,
        client_id: UUID | None = None,
    ) -> Connection:
        """Accept and track a new WebSocket connection."""
        await websocket.accept()

        connection = Connection(
            websocket=websocket,
            user_id=user_id,
            user_type=user_type,
            tenant_id=tenant_id,
            client_id=client_id,
            connected_at=datetime.now(UTC),
            last_ping=datetime.now(UTC),
        )

        if user_id not in self.connections:
            self.connections[user_id] = set()
        self.connections[user_id].add(connection)

        return connection

    def disconnect(self, connection: Connection):
        """Remove connection from tracking."""
        user_id = connection.user_id
        if user_id in self.connections:
            self.connections[user_id].discard(connection)
            if not self.connections[user_id]:
                del self.connections[user_id]

    async def send_to_user(self, user_id: UUID, message: dict):
        """Send message to all connections for a user (local instance only)."""
        if user_id in self.connections:
            dead_connections = set()
            for conn in self.connections[user_id]:
                try:
                    await conn.websocket.send_json(message)
                except Exception:
                    dead_connections.add(conn)

            # Clean up dead connections
            for conn in dead_connections:
                self.disconnect(conn)

    async def broadcast_message(
        self,
        recipient_id: UUID,
        message: dict,
    ):
        """Broadcast message via Redis for multi-instance delivery."""
        payload = {
            "recipient_id": str(recipient_id),
            "payload": message,
        }
        await self.redis.publish(self.channel, json.dumps(payload))

    async def _listen_pubsub(self):
        """Listen to Redis pub/sub and deliver to local connections."""
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(self.channel)

        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    recipient_id = UUID(data["recipient_id"])
                    await self.send_to_user(recipient_id, data["payload"])
        except asyncio.CancelledError:
            await pubsub.unsubscribe(self.channel)
            raise

    def is_online(self, user_id: UUID) -> bool:
        """Check if user has any active connections."""
        return user_id in self.connections and len(self.connections[user_id]) > 0


# Global instance
connection_manager = ConnectionManager()
```

### WebSocket Handler

```python
# backend/app/modules/portal/messaging/websocket.py
from fastapi import WebSocket, WebSocketDisconnect, Depends
from uuid import UUID
import asyncio

from app.core.websocket.manager import connection_manager, Connection
from app.modules.portal.auth.magic_link import MagicLinkService
from app.modules.portal.messaging.service import MessagingService
from app.database import get_async_session


magic_link_service = MagicLinkService()


async def websocket_handler(websocket: WebSocket):
    """Main WebSocket handler for messaging."""
    connection: Connection | None = None

    try:
        # Authenticate
        token = websocket.query_params.get("token")
        if not token:
            await websocket.close(code=4001, reason="Token required")
            return

        # Verify token (works for both portal and accountant tokens)
        payload = magic_link_service.verify_access_token(token)
        if not payload:
            await websocket.close(code=4002, reason="Invalid token")
            return

        # Determine user type and IDs
        user_type = payload.get("type", "accountant")
        if user_type == "portal_access":
            user_type = "client"
            user_id = UUID(payload["client_id"])
            client_id = user_id
        else:
            user_id = UUID(payload["user_id"])
            client_id = None

        tenant_id = UUID(payload["tenant_id"])

        # Connect
        connection = await connection_manager.connect(
            websocket=websocket,
            user_id=user_id,
            user_type=user_type,
            tenant_id=tenant_id,
            client_id=client_id,
        )

        # Send auth success
        await websocket.send_json({
            "type": "auth.success",
            "user_id": str(user_id),
            "user_type": user_type,
        })

        # Start heartbeat task
        heartbeat_task = asyncio.create_task(
            _heartbeat(websocket, connection)
        )

        # Message loop
        try:
            while True:
                data = await websocket.receive_json()
                await _handle_message(data, connection)
        finally:
            heartbeat_task.cancel()

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({
                "type": "error",
                "code": "internal_error",
                "message": str(e),
            })
        except:
            pass
    finally:
        if connection:
            connection_manager.disconnect(connection)


async def _heartbeat(websocket: WebSocket, connection: Connection):
    """Send periodic pings to keep connection alive."""
    while True:
        await asyncio.sleep(30)
        try:
            await websocket.send_json({"type": "ping"})
        except:
            break


async def _handle_message(data: dict, connection: Connection):
    """Route incoming WebSocket messages to handlers."""
    msg_type = data.get("type")

    if msg_type == "pong":
        connection.last_ping = datetime.now(UTC)

    elif msg_type == "message.send":
        await _handle_send_message(data, connection)

    elif msg_type == "message.read":
        await _handle_read_message(data, connection)

    elif msg_type == "typing.start":
        await _handle_typing(data, connection, True)

    elif msg_type == "typing.stop":
        await _handle_typing(data, connection, False)


async def _handle_send_message(data: dict, connection: Connection):
    """Handle sending a new message."""
    async with get_async_session() as session:
        service = MessagingService(session)

        message = await service.send_message(
            conversation_id=UUID(data["conversation_id"]),
            sender_id=connection.user_id,
            sender_type=connection.user_type,
            content=data["content"],
            attachment_ids=data.get("attachment_ids"),
        )

        # Send confirmation to sender
        await connection.websocket.send_json({
            "type": "message.sent",
            "message": message.to_dict(),
        })

        # Get conversation to find recipient
        conversation = await service.get_conversation(message.conversation_id)
        recipient_id = (
            conversation.client_id
            if connection.user_type == "accountant"
            else conversation.accountant_id
        )

        # Broadcast to recipient via Redis
        await connection_manager.broadcast_message(
            recipient_id=recipient_id,
            message={
                "type": "message.new",
                "message": message.to_dict(),
            },
        )


async def _handle_typing(data: dict, connection: Connection, is_typing: bool):
    """Handle typing indicator."""
    conversation_id = UUID(data["conversation_id"])

    # Get recipient from conversation
    async with get_async_session() as session:
        service = MessagingService(session)
        conversation = await service.get_conversation(conversation_id)

        recipient_id = (
            conversation.client_id
            if connection.user_type == "accountant"
            else conversation.accountant_id
        )

    # Broadcast typing indicator
    await connection_manager.broadcast_message(
        recipient_id=recipient_id,
        message={
            "type": "typing",
            "conversation_id": str(conversation_id),
            "user_id": str(connection.user_id),
            "is_typing": is_typing,
        },
    )
```

---

## 2. Messaging Service

```python
# backend/app/modules/portal/messaging/service.py
from uuid import UUID
from datetime import datetime, UTC
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.portal.messaging.models import (
    Conversation,
    Message,
    ConversationContextType,
    ConversationStatus,
    SenderType,
)
from app.modules.portal.messaging.repository import (
    ConversationRepository,
    MessageRepository,
)
from app.modules.portal.messaging.encryption import MessageEncryption
from app.modules.notifications.service import NotificationService
from app.core.audit import audit_log


class MessagingService:
    """Business logic for messaging and conversations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.conv_repo = ConversationRepository(session)
        self.msg_repo = MessageRepository(session)
        self.encryption = MessageEncryption()
        self.notifications = NotificationService(session)

    async def get_or_create_request_conversation(
        self,
        request_id: UUID,
        client_id: UUID,
        tenant_id: UUID,
    ) -> Conversation:
        """Get or create a conversation for a document request."""
        # Try to find existing
        conversation = await self.conv_repo.get_by_context(
            context_type=ConversationContextType.REQUEST,
            context_id=request_id,
        )

        if not conversation:
            conversation = await self.conv_repo.create(
                tenant_id=tenant_id,
                client_id=client_id,
                context_type=ConversationContextType.REQUEST,
                context_id=request_id,
            )

        return conversation

    async def create_general_conversation(
        self,
        tenant_id: UUID,
        client_id: UUID,
        subject: str,
        initial_message: str | None = None,
        sender_id: UUID | None = None,
        sender_type: str = "client",
    ) -> Conversation:
        """Create a new general conversation."""
        conversation = await self.conv_repo.create(
            tenant_id=tenant_id,
            client_id=client_id,
            context_type=ConversationContextType.GENERAL,
            subject=subject,
        )

        if initial_message:
            await self.send_message(
                conversation_id=conversation.id,
                sender_id=sender_id,
                sender_type=sender_type,
                content=initial_message,
            )

        return conversation

    async def send_message(
        self,
        conversation_id: UUID,
        sender_id: UUID,
        sender_type: str,
        content: str,
        attachment_ids: list[UUID] | None = None,
    ) -> Message:
        """Send a message in a conversation."""
        conversation = await self.conv_repo.get(conversation_id)

        if not conversation:
            raise ValueError("Conversation not found")

        # Encrypt content
        encrypted_content = self.encryption.encrypt(
            content=content,
            tenant_id=conversation.tenant_id,
        )

        # Create preview (truncated, unencrypted)
        preview = content[:100] + "..." if len(content) > 100 else content

        # Get sender name
        sender_name = await self._get_sender_name(sender_id, sender_type)

        # Create message
        message = await self.msg_repo.create(
            conversation_id=conversation_id,
            sender_type=SenderType(sender_type),
            sender_id=sender_id,
            sender_name=sender_name,
            content_encrypted=encrypted_content,
            content_preview=preview,
        )

        # Handle attachments
        if attachment_ids:
            await self.msg_repo.attach_files(message.id, attachment_ids)

        # Update conversation
        conversation.last_message_at = datetime.now(UTC)
        if sender_type == "client":
            conversation.unread_count_accountant += 1
        else:
            conversation.unread_count_client += 1
        await self.session.commit()

        # Notify recipient if offline
        await self._notify_if_offline(conversation, message, sender_type)

        # Audit log
        await audit_log(
            self.session,
            action="message.sent",
            resource_type="message",
            resource_id=message.id,
            user_id=sender_id,
            tenant_id=conversation.tenant_id,
        )

        # Decrypt for return
        message.content = content  # Add decrypted content
        return message

    async def get_messages(
        self,
        conversation_id: UUID,
        before: UUID | None = None,
        limit: int = 50,
        tenant_id: UUID | None = None,
    ) -> list[Message]:
        """Get messages for a conversation with decryption."""
        messages = await self.msg_repo.list_by_conversation(
            conversation_id=conversation_id,
            before=before,
            limit=limit,
        )

        # Get tenant_id for decryption
        if not tenant_id:
            conversation = await self.conv_repo.get(conversation_id)
            tenant_id = conversation.tenant_id

        # Decrypt content
        for msg in messages:
            msg.content = self.encryption.decrypt(
                encrypted=msg.content_encrypted,
                tenant_id=tenant_id,
            )

        return messages

    async def mark_read(
        self,
        message_id: UUID,
        reader_id: UUID,
    ) -> Message:
        """Mark a message as read."""
        message = await self.msg_repo.get(message_id)

        if message.read_at is None:
            message.read_at = datetime.now(UTC)
            message.read_by_id = reader_id
            await self.session.commit()

            # Update conversation unread count
            conversation = await self.conv_repo.get(message.conversation_id)
            if message.sender_type == SenderType.CLIENT:
                conversation.unread_count_accountant = max(
                    0, conversation.unread_count_accountant - 1
                )
            else:
                conversation.unread_count_client = max(
                    0, conversation.unread_count_client - 1
                )
            await self.session.commit()

        return message

    async def resolve_conversation(
        self,
        conversation_id: UUID,
        resolved_by: UUID,
    ) -> Conversation:
        """Mark conversation as resolved."""
        conversation = await self.conv_repo.get(conversation_id)
        conversation.status = ConversationStatus.RESOLVED
        conversation.resolved_at = datetime.now(UTC)
        await self.session.commit()

        # Add system message
        await self.msg_repo.create_system_message(
            conversation_id=conversation_id,
            content="Conversation marked as resolved",
        )

        return conversation

    async def _get_sender_name(self, sender_id: UUID, sender_type: str) -> str:
        """Get display name for sender."""
        if sender_type == "client":
            from app.modules.clients.repository import ClientRepository
            repo = ClientRepository(self.session)
            client = await repo.get(sender_id)
            return client.contact_name or client.business_name
        else:
            from app.modules.auth.repository import UserRepository
            repo = UserRepository(self.session)
            user = await repo.get(sender_id)
            return user.name

    async def _notify_if_offline(
        self,
        conversation: Conversation,
        message: Message,
        sender_type: str,
    ):
        """Send email notification if recipient is offline."""
        from app.core.websocket.manager import connection_manager

        recipient_id = (
            conversation.client_id
            if sender_type == "accountant"
            else conversation.accountant_id
        )

        if not connection_manager.is_online(recipient_id):
            await self.notifications.queue_message_notification(
                conversation=conversation,
                message=message,
                recipient_type="client" if sender_type == "accountant" else "accountant",
            )
```

---

## 3. Message Encryption

```python
# backend/app/modules/portal/messaging/encryption.py
from uuid import UUID
from cryptography.fernet import Fernet
import os

from app.config import settings


class MessageEncryption:
    """
    Encrypts/decrypts message content.

    In production: Uses AWS KMS for per-tenant key management.
    In development: Uses a static key from environment.
    """

    def __init__(self):
        if settings.ENVIRONMENT == "production":
            self._init_kms()
        else:
            self._init_local()

    def _init_local(self):
        """Initialize with local static key for development."""
        key = os.getenv("MESSAGE_ENCRYPTION_KEY")
        if not key:
            key = Fernet.generate_key().decode()
            print(f"Generated encryption key: {key}")
            print("Set MESSAGE_ENCRYPTION_KEY env var for persistence")

        self.fernet = Fernet(key.encode() if isinstance(key, str) else key)
        self.use_kms = False

    def _init_kms(self):
        """Initialize AWS KMS for production."""
        import boto3
        self.kms_client = boto3.client('kms')
        self.key_cache: dict[UUID, bytes] = {}
        self.use_kms = True

    def encrypt(self, content: str, tenant_id: UUID) -> str:
        """Encrypt message content."""
        if self.use_kms:
            key = self._get_tenant_key(tenant_id)
            f = Fernet(key)
            return f.encrypt(content.encode()).decode()
        else:
            return self.fernet.encrypt(content.encode()).decode()

    def decrypt(self, encrypted: str, tenant_id: UUID) -> str:
        """Decrypt message content."""
        if self.use_kms:
            key = self._get_tenant_key(tenant_id)
            f = Fernet(key)
            return f.decrypt(encrypted.encode()).decode()
        else:
            return self.fernet.decrypt(encrypted.encode()).decode()

    def _get_tenant_key(self, tenant_id: UUID) -> bytes:
        """Get or create encryption key for tenant from KMS."""
        if tenant_id in self.key_cache:
            return self.key_cache[tenant_id]

        key_alias = f"alias/clairo-messaging-{tenant_id}"

        try:
            response = self.kms_client.describe_key(KeyId=key_alias)
            key_id = response['KeyMetadata']['KeyId']
        except self.kms_client.exceptions.NotFoundException:
            response = self.kms_client.create_key(
                Description=f"Message encryption for tenant {tenant_id}",
                KeyUsage='ENCRYPT_DECRYPT',
            )
            key_id = response['KeyMetadata']['KeyId']
            self.kms_client.create_alias(
                AliasName=key_alias,
                TargetKeyId=key_id,
            )

        data_key = self.kms_client.generate_data_key(
            KeyId=key_id,
            KeySpec='AES_256',
        )

        import base64
        key = base64.urlsafe_b64encode(data_key['Plaintext'][:32])
        self.key_cache[tenant_id] = key
        return key
```

---

## 4. BAS Approval Service

```python
# backend/app/modules/portal/approvals/service.py
from uuid import UUID
from datetime import datetime, timedelta, UTC
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.portal.approvals.models import BASApproval, ApprovalStatus
from app.modules.portal.approvals.repository import ApprovalRepository
from app.modules.bas.repository import BASRepository
from app.modules.notifications.service import NotificationService
from app.core.audit import audit_log


class ApprovalService:
    """Business logic for BAS approval workflow."""

    RETRACTION_WINDOW_HOURS = 24

    def __init__(self, session: AsyncSession):
        self.session = session
        self.approval_repo = ApprovalRepository(session)
        self.bas_repo = BASRepository(session)
        self.notifications = NotificationService(session)

    async def mark_ready_for_review(
        self,
        bas_period_id: UUID,
        marked_by: UUID,
    ) -> BASApproval:
        """Mark BAS as ready for client review."""
        bas_period = await self.bas_repo.get(bas_period_id)

        # Create or get approval record
        approval = await self.approval_repo.get_by_period(bas_period_id)
        if not approval:
            approval = await self.approval_repo.create(
                tenant_id=bas_period.tenant_id,
                bas_period_id=bas_period_id,
                client_id=bas_period.client_id,
                bas_summary=self._create_summary(bas_period),
            )
        else:
            approval.status = ApprovalStatus.PENDING
            approval.bas_summary = self._create_summary(bas_period)
            await self.session.commit()

        # Notify client
        await self.notifications.send_bas_ready(
            client_id=bas_period.client_id,
            period=bas_period.period,
            summary=approval.bas_summary,
        )

        await audit_log(
            self.session,
            action="bas.ready_for_review",
            resource_type="bas_period",
            resource_id=bas_period_id,
            user_id=marked_by,
            tenant_id=bas_period.tenant_id,
        )

        return approval

    async def approve(
        self,
        bas_period_id: UUID,
        client_id: UUID,
        ip_address: str,
        user_agent: str,
        session_id: UUID,
    ) -> BASApproval:
        """Record client approval of BAS."""
        approval = await self.approval_repo.get_by_period(bas_period_id)

        if not approval:
            raise ValueError("BAS not ready for approval")

        if approval.client_id != client_id:
            raise PermissionError("Cannot approve another client's BAS")

        if approval.status != ApprovalStatus.PENDING:
            raise ValueError("BAS already approved or retracted")

        # Get client name
        from app.modules.clients.repository import ClientRepository
        client_repo = ClientRepository(self.session)
        client = await client_repo.get(client_id)

        # Record approval
        approval.status = ApprovalStatus.APPROVED
        approval.approved_at = datetime.now(UTC)
        approval.approved_by_name = client.contact_name or client.business_name
        approval.ip_address = ip_address
        approval.user_agent = user_agent
        approval.portal_session_id = session_id

        await self.session.commit()

        # Notify accountant
        await self.notifications.send_approval_received(
            approval=approval,
        )

        await audit_log(
            self.session,
            action="approval.created",
            resource_type="bas_approval",
            resource_id=approval.id,
            user_id=client_id,
            tenant_id=approval.tenant_id,
            metadata={"ip_address": ip_address},
        )

        return approval

    async def retract(
        self,
        bas_period_id: UUID,
        client_id: UUID,
        reason: str,
    ) -> BASApproval:
        """Retract a BAS approval (within window)."""
        approval = await self.approval_repo.get_by_period(bas_period_id)

        if not approval:
            raise ValueError("No approval found")

        if approval.client_id != client_id:
            raise PermissionError("Cannot retract another client's approval")

        if approval.status != ApprovalStatus.APPROVED:
            raise ValueError("Cannot retract - not approved")

        # Check retraction window
        window_end = approval.approved_at + timedelta(
            hours=self.RETRACTION_WINDOW_HOURS
        )
        if datetime.now(UTC) > window_end:
            raise ValueError("Retraction window expired (24 hours)")

        # Check if BAS already lodged
        bas_period = await self.bas_repo.get(bas_period_id)
        if bas_period.lodged_at:
            raise ValueError("Cannot retract - BAS already lodged")

        # Record retraction
        approval.status = ApprovalStatus.RETRACTED
        approval.retracted_at = datetime.now(UTC)
        approval.retraction_reason = reason

        await self.session.commit()

        # Notify accountant (urgent)
        await self.notifications.send_approval_retracted(
            approval=approval,
            reason=reason,
        )

        await audit_log(
            self.session,
            action="approval.retracted",
            resource_type="bas_approval",
            resource_id=approval.id,
            user_id=client_id,
            tenant_id=approval.tenant_id,
            metadata={"reason": reason},
        )

        return approval

    def _create_summary(self, bas_period) -> dict:
        """Create BAS summary snapshot for approval record."""
        return {
            "period": bas_period.period,
            "gst_collected": float(bas_period.gst_collected or 0),
            "gst_paid": float(bas_period.gst_paid or 0),
            "net_gst": float(bas_period.net_gst or 0),
            "payg_withheld": float(bas_period.payg_withheld or 0) if bas_period.payg_withheld else None,
            "lodgement_due": bas_period.due_date.isoformat() if bas_period.due_date else None,
        }

    async def can_retract(self, approval: BASApproval) -> bool:
        """Check if approval can still be retracted."""
        if approval.status != ApprovalStatus.APPROVED:
            return False

        window_end = approval.approved_at + timedelta(
            hours=self.RETRACTION_WINDOW_HOURS
        )
        if datetime.now(UTC) > window_end:
            return False

        bas_period = await self.bas_repo.get(approval.bas_period_id)
        if bas_period.lodged_at:
            return False

        return True
```

---

## 5. Frontend WebSocket Hook

```typescript
// frontend/src/hooks/useWebSocket.ts
import { useEffect, useRef, useState, useCallback } from 'react';
import { useAuth } from '@/hooks/useAuth';

interface WebSocketMessage {
  type: string;
  [key: string]: any;
}

interface UseWebSocketOptions {
  onMessage?: (data: WebSocketMessage) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const { token } = useAuth();
  const wsRef = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const reconnectAttempts = useRef(0);
  const maxReconnects = 10;

  const connect = useCallback(() => {
    if (!token) return;

    const wsUrl = `${process.env.NEXT_PUBLIC_WS_URL}/ws?token=${token}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setIsConnected(true);
      setError(null);
      reconnectAttempts.current = 0;
      options.onConnect?.();
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      // Handle pong internally
      if (data.type === 'ping') {
        ws.send(JSON.stringify({ type: 'pong' }));
        return;
      }

      options.onMessage?.(data);
    };

    ws.onclose = () => {
      setIsConnected(false);
      options.onDisconnect?.();

      // Reconnect with exponential backoff
      if (reconnectAttempts.current < maxReconnects) {
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000);
        reconnectAttempts.current++;
        setTimeout(connect, delay);
      }
    };

    ws.onerror = () => {
      setError('WebSocket connection error');
    };

    wsRef.current = ws;
  }, [token, options]);

  const send = useCallback((data: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  const sendMessage = useCallback((conversationId: string, content: string) => {
    send({
      type: 'message.send',
      conversation_id: conversationId,
      content,
    });
  }, [send]);

  const markRead = useCallback((messageId: string) => {
    send({
      type: 'message.read',
      message_id: messageId,
    });
  }, [send]);

  const sendTyping = useCallback((conversationId: string, isTyping: boolean) => {
    send({
      type: isTyping ? 'typing.start' : 'typing.stop',
      conversation_id: conversationId,
    });
  }, [send]);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
    };
  }, [connect]);

  return {
    isConnected,
    error,
    send,
    sendMessage,
    markRead,
    sendTyping,
  };
}
```

---

## 6. Message Thread Component

```typescript
// frontend/src/components/messaging/MessageThread.tsx
"use client";

import { useEffect, useRef, useState } from 'react';
import { format } from 'date-fns';
import { Send } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useConversation } from '@/hooks/useConversation';

interface Message {
  id: string;
  sender_type: 'client' | 'accountant' | 'system';
  sender_name: string | null;
  content: string;
  created_at: string;
  read_at: string | null;
}

interface MessageThreadProps {
  conversationId: string;
  currentUserType: 'client' | 'accountant';
}

export function MessageThread({ conversationId, currentUserType }: MessageThreadProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const typingTimeoutRef = useRef<NodeJS.Timeout>();

  const { messages, isLoading, addMessage } = useConversation(conversationId);
  const { sendMessage, sendTyping, markRead, isConnected } = useWebSocket({
    onMessage: (data) => {
      if (data.type === 'message.new' && data.message.conversation_id === conversationId) {
        addMessage(data.message);
        // Auto-mark as read if thread is open
        markRead(data.message.id);
      }
      if (data.type === 'typing' && data.conversation_id === conversationId) {
        setIsTyping(data.is_typing);
      }
    },
  });

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = () => {
    if (!input.trim()) return;

    sendMessage(conversationId, input.trim());
    setInput('');
    sendTyping(conversationId, false);
  };

  const handleInputChange = (value: string) => {
    setInput(value);

    // Debounced typing indicator
    sendTyping(conversationId, true);
    clearTimeout(typingTimeoutRef.current);
    typingTimeoutRef.current = setTimeout(() => {
      sendTyping(conversationId, false);
    }, 2000);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (isLoading) {
    return <div className="flex items-center justify-center h-full">Loading...</div>;
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message) => (
          <MessageBubble
            key={message.id}
            message={message}
            isOwn={message.sender_type === currentUserType}
          />
        ))}

        {isTyping && (
          <div className="flex items-center gap-2 text-gray-500 text-sm">
            <div className="flex gap-1">
              <span className="animate-bounce">.</span>
              <span className="animate-bounce delay-100">.</span>
              <span className="animate-bounce delay-200">.</span>
            </div>
            <span>Typing...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t p-4 bg-white">
        <div className="flex gap-2">
          <Textarea
            value={input}
            onChange={(e) => handleInputChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a message..."
            rows={2}
            className="flex-1 resize-none"
          />
          <Button
            onClick={handleSend}
            disabled={!input.trim() || !isConnected}
            size="icon"
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>

        {!isConnected && (
          <p className="text-sm text-yellow-600 mt-2">
            Reconnecting...
          </p>
        )}
      </div>
    </div>
  );
}

function MessageBubble({ message, isOwn }: { message: Message; isOwn: boolean }) {
  return (
    <div className={`flex ${isOwn ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[70%] rounded-lg px-4 py-2 ${
          isOwn
            ? 'bg-blue-600 text-white'
            : message.sender_type === 'system'
            ? 'bg-gray-100 text-gray-600 italic'
            : 'bg-gray-200 text-gray-900'
        }`}
      >
        {!isOwn && message.sender_name && (
          <p className="text-xs font-medium mb-1">{message.sender_name}</p>
        )}
        <p className="whitespace-pre-wrap">{message.content}</p>
        <p className={`text-xs mt-1 ${isOwn ? 'text-blue-200' : 'text-gray-500'}`}>
          {format(new Date(message.created_at), 'HH:mm')}
          {message.read_at && isOwn && ' ✓'}
        </p>
      </div>
    </div>
  );
}
```

---

## Testing

### WebSocket Integration Test

```python
# backend/tests/integration/api/test_websocket.py
import pytest
import asyncio
from httpx import AsyncClient
from websockets import connect as ws_connect

from app.main import app


@pytest.mark.asyncio
async def test_websocket_auth(portal_token):
    """Test WebSocket authentication."""
    async with ws_connect(
        f"ws://localhost:8000/ws?token={portal_token}"
    ) as ws:
        # Should receive auth success
        response = await ws.recv()
        data = json.loads(response)

        assert data["type"] == "auth.success"
        assert "user_id" in data


@pytest.mark.asyncio
async def test_send_and_receive_message(
    portal_token,
    accountant_token,
    test_conversation,
):
    """Test sending and receiving messages via WebSocket."""
    async with ws_connect(f"ws://localhost:8000/ws?token={portal_token}") as client_ws:
        async with ws_connect(f"ws://localhost:8000/ws?token={accountant_token}") as acc_ws:
            # Wait for both connections to authenticate
            await client_ws.recv()  # auth.success
            await acc_ws.recv()     # auth.success

            # Client sends message
            await client_ws.send(json.dumps({
                "type": "message.send",
                "conversation_id": str(test_conversation.id),
                "content": "Hello, I have a question",
            }))

            # Client should receive sent confirmation
            client_response = await client_ws.recv()
            client_data = json.loads(client_response)
            assert client_data["type"] == "message.sent"

            # Accountant should receive new message
            acc_response = await acc_ws.recv()
            acc_data = json.loads(acc_response)
            assert acc_data["type"] == "message.new"
            assert acc_data["message"]["content"] == "Hello, I have a question"


@pytest.mark.asyncio
async def test_typing_indicator(
    portal_token,
    accountant_token,
    test_conversation,
):
    """Test typing indicators."""
    async with ws_connect(f"ws://localhost:8000/ws?token={portal_token}") as client_ws:
        async with ws_connect(f"ws://localhost:8000/ws?token={accountant_token}") as acc_ws:
            await client_ws.recv()  # auth.success
            await acc_ws.recv()     # auth.success

            # Client starts typing
            await client_ws.send(json.dumps({
                "type": "typing.start",
                "conversation_id": str(test_conversation.id),
            }))

            # Accountant should receive typing indicator
            acc_response = await acc_ws.recv()
            acc_data = json.loads(acc_response)
            assert acc_data["type"] == "typing"
            assert acc_data["is_typing"] is True
```

---

## Next Steps

After implementing the core functionality:

1. **Phase 2**: Request amendments UI
2. **Phase 3**: BAS approval dashboard
3. **Phase 4**: Notification preferences UI
4. **Phase 5**: Message attachments
5. **Phase 6**: Email digest notifications

See [tasks.md](./tasks.md) for complete implementation checklist.
