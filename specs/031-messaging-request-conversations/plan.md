# Implementation Plan: Messaging & Request Conversations

**Branch**: `031-messaging-request-conversations` | **Date**: 2026-01-01 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/031-messaging-request-conversations/spec.md`

## Summary

Add contextual messaging capabilities to the client portal with request-specific conversations, BAS approval workflow, and real-time notifications via WebSocket.

**Technical Approach**:
- Extend portal module with messaging submodule
- WebSocket server for real-time delivery
- Conversation context linking (requests, BAS periods)
- Digital approval workflow with audit trail

---

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: FastAPI, SQLAlchemy 2.x, Pydantic v2, WebSocket
**Real-time**: FastAPI WebSocket with Redis pub/sub for scaling
**Storage**: PostgreSQL 16 (encrypted content), S3/MinIO (attachments)
**Email**: Resend (notifications)
**Testing**: pytest, pytest-asyncio
**Target Platform**: AWS ECS/Fargate (Sydney region)
**Project Type**: Web application (backend + frontend)
**Performance Goals**: Message delivery <2s, 10,000 concurrent connections
**Constraints**: Messages encrypted at rest, audit trail for approvals

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Compliance | Notes |
|-----------|------------|-------|
| **Modular Monolith** | ✅ PASS | Extends portal module with messaging submodule |
| **Repository Pattern** | ✅ PASS | ConversationRepository, MessageRepository |
| **Multi-tenancy (RLS)** | ✅ PASS | All messages scoped to tenant |
| **Audit-First** | ✅ PASS | All approvals and messages audited |
| **Type Hints** | ✅ PASS | Pydantic schemas throughout |
| **Test-First** | ✅ PASS | Test WebSocket, messaging, approvals |
| **API Conventions** | ✅ PASS | RESTful + WebSocket endpoints |
| **Privacy** | ✅ PASS | Message content encrypted at rest |

**No violations requiring justification.**

---

## Project Structure

### Documentation (this feature)

```text
specs/031-messaging-request-conversations/
├── plan.md              # This file
├── research.md          # WebSocket, real-time research
├── data-model.md        # Entity definitions
├── quickstart.md        # Developer guide
├── contracts/           # OpenAPI specs
│   ├── messaging-api.yaml    # REST endpoints
│   └── websocket-api.md      # WebSocket protocol
└── tasks.md             # Implementation tasks
```

### Source Code (repository root)

```text
backend/
├── app/
│   └── modules/
│       └── portal/
│           └── messaging/                  # NEW SUBMODULE
│               ├── __init__.py
│               ├── models.py               # Conversation, Message entities
│               ├── schemas.py              # Request/response schemas
│               ├── repository.py           # Database operations
│               ├── service.py              # Business logic
│               ├── router.py               # REST endpoints
│               ├── websocket.py            # WebSocket handler
│               └── encryption.py           # Message encryption
│           │
│           └── approvals/                  # NEW SUBMODULE
│               ├── __init__.py
│               ├── models.py               # BASApproval entity
│               ├── schemas.py              # Approval schemas
│               ├── service.py              # Approval workflow
│               └── router.py               # Approval endpoints
│
├── core/
│   └── websocket/                          # NEW CORE MODULE
│       ├── __init__.py
│       ├── manager.py                      # Connection manager
│       ├── pubsub.py                       # Redis pub/sub for scaling
│       └── auth.py                         # WebSocket authentication
│
└── tests/
    ├── unit/
    │   └── modules/
    │       └── portal/
    │           ├── test_messaging_service.py
    │           └── test_approval_service.py
    └── integration/
        └── api/
            ├── test_messaging.py
            ├── test_websocket.py
            └── test_approvals.py

frontend/
└── src/
    ├── app/
    │   ├── portal/
    │   │   ├── messages/
    │   │   │   └── page.tsx                # General messaging
    │   │   ├── requests/
    │   │   │   └── [id]/
    │   │   │       └── chat/page.tsx       # Request conversation
    │   │   └── bas/
    │   │       └── [period]/
    │   │           └── review/page.tsx     # BAS review & approve
    │   │
    │   └── (protected)/
    │       ├── inbox/
    │       │   └── page.tsx                # Accountant inbox
    │       └── approvals/
    │           └── page.tsx                # Approval dashboard
    │
    ├── components/
    │   ├── messaging/
    │   │   ├── ConversationList.tsx
    │   │   ├── MessageThread.tsx
    │   │   ├── MessageInput.tsx
    │   │   ├── MessageBubble.tsx
    │   │   └── AttachmentPicker.tsx
    │   │
    │   ├── approvals/
    │   │   ├── BASReviewCard.tsx
    │   │   ├── ApprovalButton.tsx
    │   │   └── ApprovalDashboard.tsx
    │   │
    │   └── notifications/
    │       ├── NotificationBell.tsx
    │       └── NotificationToast.tsx
    │
    ├── hooks/
    │   ├── useWebSocket.ts                 # WebSocket connection
    │   ├── useConversation.ts              # Conversation state
    │   └── useNotifications.ts             # Real-time notifications
    │
    └── lib/
        └── api/
            ├── messaging.ts                # Messaging API client
            └── approvals.ts                # Approvals API client
```

---

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    MESSAGING ARCHITECTURE                                │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                    FRONTEND (Next.js)                              │ │
│  │                                                                    │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │ │
│  │  │  Message    │  │  Approval   │  │ Notification│               │ │
│  │  │  Thread     │  │  Review     │  │  Toast      │               │ │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘               │ │
│  │         │                │                │                        │ │
│  │         └────────────────┼────────────────┘                       │ │
│  │                          │                                         │ │
│  │                  ┌───────┴───────┐                                │ │
│  │                  │  WebSocket    │                                │ │
│  │                  │  Connection   │                                │ │
│  │                  └───────────────┘                                │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                             ▲│                                         │
│                             ││  WebSocket                              │
│                             │▼                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                    BACKEND (FastAPI)                               │ │
│  │                                                                    │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │ │
│  │  │  WebSocket  │  │    REST     │  │  Approval   │               │ │
│  │  │  Handler    │  │   Router    │  │   Router    │               │ │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘               │ │
│  │         │                │                │                        │ │
│  │         └────────────────┼────────────────┘                       │ │
│  │                          │                                         │ │
│  │  ┌───────────────────────┴───────────────────────────────────┐    │ │
│  │  │              MESSAGING SERVICE                             │    │ │
│  │  │  - Create conversations                                    │    │ │
│  │  │  - Send/receive messages                                   │    │ │
│  │  │  - Track read status                                       │    │ │
│  │  │  - Encrypt/decrypt content                                 │    │ │
│  │  └───────────────────────────────────────────────────────────┘    │ │
│  │                          │                                         │ │
│  │  ┌───────────────────────┴───────────────────────────────────┐    │ │
│  │  │              CONNECTION MANAGER                            │    │ │
│  │  │  - Track active connections                                │    │ │
│  │  │  - Redis pub/sub for multi-instance                       │    │ │
│  │  │  - Broadcast to subscribers                                │    │ │
│  │  └───────────────────────────────────────────────────────────┘    │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                    INFRASTRUCTURE                                  │ │
│  │   PostgreSQL (Messages)     Redis (Pub/Sub)     S3 (Attachments) │ │
│  └───────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### Message Flow

```
MESSAGE FLOW
═══════════════════════════════════════════════════════════════════════════

1. CLIENT SENDS MESSAGE
   ├── Client types message in thread
   ├── WebSocket: message.send event
   └── Server receives
           │
           ▼
2. SERVER PROCESSES
   ├── Validate sender permission
   ├── Encrypt message content
   ├── Save to database
   ├── Log audit event
   └── Broadcast via Redis pub/sub
           │
           ▼
3. RECIPIENT RECEIVES
   ├── If online: WebSocket message.new event
   ├── If offline: Queue email notification
   └── Update unread count
           │
           ▼
4. RECIPIENT READS
   ├── Mark message as read
   ├── Update conversation unread count
   └── Broadcast read receipt (optional)
```

### BAS Approval Flow

```
BAS APPROVAL WORKFLOW
═══════════════════════════════════════════════════════════════════════════

1. ACCOUNTANT MARKS BAS READY
   POST /api/v1/bas/{period}/ready
   └── Status: READY_FOR_REVIEW
           │
           ▼
2. CLIENT NOTIFIED
   ├── Email: "Your BAS is ready for review"
   ├── Portal: Dashboard shows "Review BAS"
   └── WebSocket: bas.ready event
           │
           ▼
3. CLIENT REVIEWS
   GET /portal/bas/{period}/review
   ├── See summary: GST collected, paid, net
   ├── View breakdown by category
   └── Option to ask questions
           │
           ├── If questions → Start conversation
           │   └── Return to review after resolved
           │
           ▼
4. CLIENT APPROVES
   POST /api/v1/portal/bas/{period}/approve
   ├── Capture: timestamp, IP, user agent
   ├── Create BASApproval record
   ├── Status: APPROVED
   └── Notify accountant
           │
           ▼
5. ACCOUNTANT LODGES
   (After approval, can proceed with ATO lodgement)

RETRACTION (if needed)
─────────────────────────────────────────
If within 24 hours and not yet lodged:
   POST /api/v1/portal/bas/{period}/retract
   ├── Record retraction reason
   ├── Status: PENDING_REVIEW
   └── Notify accountant
```

---

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Real-time Protocol | WebSocket | Bidirectional, lower latency than polling |
| Scaling | Redis pub/sub | Multi-instance message broadcasting |
| Encryption | Fernet (symmetric) | Fast, AES-128, suitable for message content |
| Conversation Context | Polymorphic | Links to requests, BAS, or standalone |
| Read Receipts | Optional | Configurable per user preference |
| Approval Retraction | 24-hour window | Balance flexibility with process integrity |

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| WebSocket connection drops | Auto-reconnect with exponential backoff |
| Message delivery failure | Retry queue, fallback to email |
| High connection count | Redis pub/sub, connection pooling |
| Encryption key management | AWS KMS for key storage/rotation |
| Spam/abuse | Rate limiting per user, content moderation |
| Approval disputes | Full audit trail, IP capture, retraction window |

---

## Dependencies

### Internal Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| Portal module (Spec 030) | Required | Authentication, portal infrastructure |
| Documents module | Required | For message attachments |
| Notifications module | Required | Email notifications |
| BAS module | Required | BAS status and data |

### External Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| Redis | 7+ | Pub/sub for WebSocket scaling |
| cryptography | 41+ | Fernet encryption for messages |
| websockets | 12+ | WebSocket protocol support |

---

## Phase References

- **Phase 0**: See [research.md](./research.md) for WebSocket and encryption research
- **Phase 1**: See [data-model.md](./data-model.md) for entity definitions
- **Phase 1**: See [contracts/messaging-api.yaml](./contracts/messaging-api.yaml) for REST API
- **Phase 1**: See [contracts/websocket-api.md](./contracts/websocket-api.md) for WebSocket protocol
- **Phase 1**: See [quickstart.md](./quickstart.md) for developer guide
