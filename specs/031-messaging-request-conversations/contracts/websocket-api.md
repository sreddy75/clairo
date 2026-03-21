# WebSocket API Protocol

**Spec**: 031-messaging-request-conversations
**Version**: 1.0.0

## Overview

This document defines the WebSocket protocol for real-time messaging in Clairo.

## Connection

### Endpoint

```
wss://api.clairo.ai/ws
```

### Authentication

Connect with JWT token in query params:

```
wss://api.clairo.ai/ws?token=<jwt_token>
```

Or send auth message after connection:

```json
{
  "type": "auth",
  "token": "<jwt_token>"
}
```

### Connection Response

Success:
```json
{
  "type": "auth.success",
  "user_id": "uuid",
  "user_type": "client|accountant"
}
```

Failure:
```json
{
  "type": "auth.error",
  "message": "Invalid token"
}
```

---

## Message Types

### Client → Server

#### Send Message

```json
{
  "type": "message.send",
  "conversation_id": "uuid",
  "content": "Hello, I have a question about the bank statements.",
  "attachment_ids": ["uuid"]  // Optional
}
```

Response:
```json
{
  "type": "message.sent",
  "message": {
    "id": "uuid",
    "conversation_id": "uuid",
    "sender_type": "client",
    "content": "Hello, I have a question about the bank statements.",
    "created_at": "2026-01-01T10:30:00Z"
  }
}
```

#### Mark Message Read

```json
{
  "type": "message.read",
  "message_id": "uuid"
}
```

#### Typing Indicator

```json
{
  "type": "typing.start",
  "conversation_id": "uuid"
}
```

```json
{
  "type": "typing.stop",
  "conversation_id": "uuid"
}
```

#### Ping (Keepalive)

```json
{
  "type": "ping"
}
```

Response:
```json
{
  "type": "pong"
}
```

---

### Server → Client

#### New Message

Sent when a new message is received in a conversation the user is part of.

```json
{
  "type": "message.new",
  "message": {
    "id": "uuid",
    "conversation_id": "uuid",
    "sender_type": "accountant",
    "sender_name": "Jane Smith",
    "content": "Please upload all statements from July to September.",
    "attachments": [],
    "created_at": "2026-01-01T10:35:00Z"
  }
}
```

#### Message Read Receipt

Sent when the other party reads a message.

```json
{
  "type": "message.read",
  "message_id": "uuid",
  "read_by": "uuid",
  "read_at": "2026-01-01T10:36:00Z"
}
```

#### Typing Indicator

```json
{
  "type": "typing",
  "conversation_id": "uuid",
  "user_id": "uuid",
  "user_name": "John Smith",
  "is_typing": true
}
```

#### Notification

General notifications (new request, BAS ready, etc.)

```json
{
  "type": "notification",
  "notification": {
    "id": "uuid",
    "type": "bas_ready",
    "title": "BAS Ready for Review",
    "body": "Your BAS for Q4 2025 is ready. Please review and approve.",
    "link": "/portal/bas/2025-q4/review",
    "created_at": "2026-01-01T11:00:00Z"
  }
}
```

Notification types:
- `bas_ready` - BAS ready for client review
- `approval_received` - Client approved BAS
- `approval_retracted` - Client retracted approval
- `request_new` - New document request
- `request_response` - Client responded to request
- `message_new` - New message (when not in conversation)

#### Conversation Updated

Sent when a conversation is resolved or archived.

```json
{
  "type": "conversation.updated",
  "conversation_id": "uuid",
  "status": "resolved"
}
```

#### Error

```json
{
  "type": "error",
  "code": "conversation_not_found",
  "message": "Conversation not found or access denied"
}
```

Error codes:
- `auth_required` - Not authenticated
- `auth_failed` - Authentication failed
- `conversation_not_found` - Conversation doesn't exist or no access
- `rate_limited` - Too many messages
- `invalid_message` - Malformed message

---

## Heartbeat

The server sends a `ping` every 30 seconds. Clients should respond with `pong`.

If no `pong` is received within 60 seconds, the connection is closed.

Clients should also implement reconnection logic:
- Initial retry: 1 second
- Exponential backoff: double each attempt
- Maximum retry delay: 30 seconds
- Maximum attempts: 10

---

## Rate Limiting

- Maximum 10 messages per minute per user
- Maximum 1 typing indicator per second
- Exceeding limits results in `rate_limited` error

---

## Example Session

```
# 1. Connect with token
Client connects to: wss://api.clairo.ai/ws?token=eyJ...

# 2. Server confirms auth
→ {"type": "auth.success", "user_id": "abc123", "user_type": "client"}

# 3. Client sends message
← {"type": "message.send", "conversation_id": "conv1", "content": "Hello?"}

# 4. Server confirms and broadcasts
→ {"type": "message.sent", "message": {...}}
→ (to accountant) {"type": "message.new", "message": {...}}

# 5. Accountant typing
→ (to client) {"type": "typing", "conversation_id": "conv1", "is_typing": true}

# 6. Accountant responds
→ {"type": "message.new", "message": {...}}

# 7. Client reads message
← {"type": "message.read", "message_id": "msg2"}
→ (to accountant) {"type": "message.read", "message_id": "msg2", "read_at": "..."}

# 8. Keepalive
→ {"type": "ping"}
← {"type": "pong"}
```

---

## Security Considerations

1. **Token Validation**: All tokens are validated on connection and periodically during the session
2. **Tenant Isolation**: Users can only receive messages for their tenant
3. **Connection Limits**: Maximum 3 connections per user (multiple tabs)
4. **Message Size**: Maximum 64KB per message
5. **TLS Required**: All connections must use WSS (TLS)
