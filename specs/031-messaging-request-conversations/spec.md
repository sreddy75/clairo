# Feature Specification: Messaging & Request Conversations

**Feature Branch**: `031-messaging-request-conversations`
**Created**: 2026-01-01
**Status**: Draft
**Phase**: F (Business Owner Engagement)

## Overview

Add contextual messaging and conversation capabilities to the client portal, enabling back-and-forth communication between accountants and clients. This includes request-specific conversations, BAS approval workflows, and clarification flows that reduce misunderstandings and improve response quality.

**Why This Matters**:
- Reduces back-and-forth emails: Conversations in context of specific requests
- Improves clarity: Clients can ask "What exactly do you need?" before responding
- BAS approval: Digital sign-off with audit trail replaces email confirmations
- Faster resolution: Real-time messaging vs email delays
- Complete audit trail: All communications logged for compliance

**The Conversation Value**:
```
BEFORE: "Can you clarify what bank statements you need?"
        → Email back and forth → 3-day delay → Wrong documents uploaded

AFTER: Client asks in-context → Accountant clarifies in minutes
       → Right documents first time → Everyone happy
```

**Disruption Level**: Low (enhances existing portal, no new user types)

---

## User Scenarios & Testing

### User Story 1 - Request Conversations (Priority: P1)

As a business owner, I want to ask clarifying questions about a document request so that I upload the right documents the first time.

**Why this priority**: Core value - reduces rework and frustration.

**Independent Test**: View request → ask question → accountant sees and responds → client sees reply.

**Acceptance Scenarios**:

1. **Given** I'm viewing a document request, **When** I click "Ask a question", **Then** I can type and send a message to my accountant.

2. **Given** I've sent a question, **When** my accountant replies, **Then** I see the reply in the request conversation and get notified.

3. **Given** there's a conversation on a request, **When** I view the request, **Then** I see the full conversation history.

---

### User Story 2 - Accountant Request Chat (Priority: P1)

As an accountant, I want to see and respond to client questions on requests so that I can clarify what's needed.

**Why this priority**: Accountant side of the core conversation flow.

**Independent Test**: See new message notification → open request → respond → client notified.

**Acceptance Scenarios**:

1. **Given** a client asks a question on a request, **When** I view my request tracking, **Then** I see an indicator that there's a new message.

2. **Given** I open a request with messages, **When** I view the conversation, **Then** I see the client's question and can reply.

3. **Given** I want to proactively clarify, **When** I send a message on a request, **Then** the client is notified.

---

### User Story 3 - Request Amendments (Priority: P1)

As an accountant, I want to update a request after a client question so that the requirements are clear.

**Why this priority**: Enables iterative refinement based on conversation.

**Independent Test**: Client asks question → accountant edits request → client sees updated request.

**Acceptance Scenarios**:

1. **Given** a client asks for clarification, **When** I edit the request description, **Then** the request is updated and client is notified.

2. **Given** I amend a request, **When** the client views it, **Then** they see the updated requirements clearly marked.

3. **Given** a request has been amended, **When** I view the request history, **Then** I see what changed and when.

---

### User Story 4 - BAS Review & Approval (Priority: P1)

As a business owner, I want to review and approve my BAS before lodgement so that I confirm the amounts are correct.

**Why this priority**: Compliance requirement - client sign-off before ATO lodgement.

**Independent Test**: BAS ready → client reviews summary → client approves → approval logged.

**Acceptance Scenarios**:

1. **Given** my BAS is ready for review, **When** I view it in the portal, **Then** I see a clear summary of GST collected, GST paid, and net amount.

2. **Given** I'm reviewing my BAS, **When** I have questions, **Then** I can message my accountant before approving.

3. **Given** I'm satisfied with the BAS, **When** I click "Approve", **Then** my approval is recorded with timestamp and IP address.

---

### User Story 5 - Accountant Approval Dashboard (Priority: P1)

As an accountant, I want to see which BAS returns are pending client approval so that I can follow up before deadlines.

**Why this priority**: Visibility into approval status across portfolio.

**Independent Test**: Multiple BAS ready → see approval dashboard → filter by pending → send reminders.

**Acceptance Scenarios**:

1. **Given** I have BAS returns ready for client approval, **When** I view my approval dashboard, **Then** I see a list of pending approvals with due dates.

2. **Given** a client hasn't approved, **When** I click "Send Reminder", **Then** they receive a reminder email.

3. **Given** a client approves their BAS, **When** I view the dashboard, **Then** the status updates to "Approved" with timestamp.

---

### User Story 6 - General Messaging (Priority: P2)

As a business owner, I want to send general messages to my accountant so that I can ask questions not related to a specific request.

**Why this priority**: Convenience feature beyond request-specific chat.

**Independent Test**: Open messaging → send message → accountant receives → responds.

**Acceptance Scenarios**:

1. **Given** I want to contact my accountant, **When** I open the messaging section, **Then** I can compose and send a general message.

2. **Given** I've sent a message, **When** my accountant replies, **Then** I see the reply and get notified.

3. **Given** there's a conversation history, **When** I view messages, **Then** I see all past messages organized by date.

---

### User Story 7 - Accountant Inbox (Priority: P2)

As an accountant, I want a unified inbox for all client messages so that I don't miss important communications.

**Why this priority**: Efficiency for managing multiple client conversations.

**Independent Test**: Multiple clients message → see unified inbox → reply from inbox.

**Acceptance Scenarios**:

1. **Given** multiple clients have sent messages, **When** I view my inbox, **Then** I see all messages sorted by recency.

2. **Given** I have unread messages, **When** I log in, **Then** I see a count of unread messages.

3. **Given** I'm in the inbox, **When** I click a message, **Then** I can view the full conversation and reply inline.

---

### User Story 8 - Completion Confirmation (Priority: P1)

As an accountant, I want to confirm receipt of documents and close a request so that the client knows we have what we need.

**Why this priority**: Closes the loop on document requests.

**Independent Test**: Client responds → accountant reviews → marks complete with note → client notified.

**Acceptance Scenarios**:

1. **Given** a client has responded to a request, **When** I review the documents, **Then** I can mark the request as complete.

2. **Given** I'm completing a request, **When** I add a thank-you note, **Then** the client receives it.

3. **Given** documents are incomplete, **When** I need more, **Then** I can re-open the request with additional requirements.

---

### User Story 9 - Real-time Notifications (Priority: P1)

As a user, I want real-time notifications for new messages so that I can respond quickly.

**Why this priority**: Essential for timely communication.

**Independent Test**: Message sent → recipient sees notification within seconds.

**Acceptance Scenarios**:

1. **Given** I'm in the portal, **When** a new message arrives, **Then** I see an in-app notification immediately.

2. **Given** I'm not in the portal, **When** a message arrives, **Then** I receive an email notification.

3. **Given** I have notification preferences, **When** a message arrives, **Then** notifications respect my preferences.

---

### User Story 10 - Message Attachments (Priority: P2)

As a user, I want to attach files to messages so that I can share documents in context.

**Why this priority**: Useful for sharing supporting information.

**Independent Test**: Compose message → attach file → send → recipient sees attachment.

**Acceptance Scenarios**:

1. **Given** I'm composing a message, **When** I click "Attach file", **Then** I can upload a document.

2. **Given** I receive a message with attachment, **When** I view it, **Then** I can download the attachment.

3. **Given** an attachment is a document, **When** uploaded, **Then** it's stored with the conversation for audit purposes.

---

### Edge Cases

- What if client sends many questions without response?
  → Show queue of pending questions, rate limit if excessive

- What if accountant is unavailable for days?
  → Auto-reply option, escalation to other team members

- What if message contains sensitive information?
  → All messages encrypted at rest, no sensitive data in notifications

- What if client wants to retract approval?
  → Allow retraction within 24 hours if BAS not yet lodged

- What if conversation gets too long?
  → Paginate older messages, keep recent ones visible

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST allow clients to ask questions on document requests
- **FR-002**: System MUST allow accountants to respond to request questions
- **FR-003**: System MUST support request amendments with change tracking
- **FR-004**: System MUST provide BAS review and approval workflow
- **FR-005**: System MUST record approvals with timestamp and IP for audit
- **FR-006**: System SHOULD support general messaging (not request-specific)
- **FR-007**: System MUST provide unified inbox for accountants
- **FR-008**: System MUST support completion confirmation with notes
- **FR-009**: System MUST send real-time notifications for new messages
- **FR-010**: System SHOULD support file attachments in messages
- **FR-011**: System MUST maintain full conversation history
- **FR-012**: System MUST support notification preferences

### Key Entities

- **Conversation**: Thread of messages (can be request-specific or general)
- **Message**: Individual message within a conversation
- **MessageAttachment**: File attached to a message
- **BASApproval**: Client approval of BAS with audit data
- **NotificationPreference**: User notification settings

### Non-Functional Requirements

- **NFR-001**: New messages MUST appear within 2 seconds (WebSocket)
- **NFR-002**: Message history MUST load within 1 second
- **NFR-003**: Conversations MUST be encrypted at rest
- **NFR-004**: Email notifications MUST send within 1 minute
- **NFR-005**: System MUST support 10,000 concurrent WebSocket connections
- **NFR-006**: Message search MUST return results within 500ms

---

## Auditing & Compliance Checklist

### Audit Events Required

- [x] **Message Events**: Yes - sent, read, deleted
- [x] **Approval Events**: Yes - BAS reviewed, approved, retracted
- [x] **Amendment Events**: Yes - request modified after questions
- [x] **Notification Events**: Yes - sent, delivered, opened

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|------------|---------|---------------|-----------|----------------|
| `message.sent` | Message created | conversation_id, sender, type | 7 years | Content (encrypted) |
| `message.read` | Message viewed | message_id, reader, timestamp | 7 years | None |
| `approval.created` | BAS approved | bas_id, client_id, IP | 7 years | IP address |
| `approval.retracted` | Approval retracted | approval_id, reason | 7 years | None |
| `request.amended` | Request updated | request_id, changes | 7 years | None |

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: >90% of request questions answered within 4 hours
- **SC-002**: >50% reduction in "wrong documents" submissions
- **SC-003**: >95% BAS approvals obtained within 48 hours of ready
- **SC-004**: <5 minutes average time from BAS ready to client viewing
- **SC-005**: Real-time message delivery <2 seconds

---

## Technical Notes (for Plan phase)

### Conversation Model

```python
class Conversation(Base):
    id: UUID
    tenant_id: UUID
    client_id: UUID

    # Context (optional - null for general conversations)
    context_type: str | None  # "request", "bas_period", null
    context_id: UUID | None   # Reference to request or BAS

    status: str  # ACTIVE, RESOLVED, ARCHIVED

    created_at: datetime
    last_message_at: datetime
    unread_count_client: int
    unread_count_accountant: int
```

### Message Model

```python
class Message(Base):
    id: UUID
    conversation_id: UUID

    sender_type: str  # "client", "accountant", "system"
    sender_id: UUID | None

    content: str  # Encrypted
    content_type: str  # "text", "system_notification"

    read_at: datetime | None
    created_at: datetime
```

### BAS Approval Model

```python
class BASApproval(Base):
    id: UUID
    bas_period_id: UUID
    client_id: UUID

    status: str  # PENDING, APPROVED, RETRACTED
    approved_at: datetime | None
    retracted_at: datetime | None
    retraction_reason: str | None

    # Audit data
    ip_address: str
    user_agent: str

    created_at: datetime
```

### WebSocket Events

```python
# Client → Server
{
    "type": "message.send",
    "conversation_id": "uuid",
    "content": "What bank accounts do you need?"
}

# Server → Client
{
    "type": "message.new",
    "message": {
        "id": "uuid",
        "conversation_id": "uuid",
        "sender_type": "accountant",
        "content": "All business accounts from July-September",
        "created_at": "2026-01-01T10:30:00Z"
    }
}
```

---

## Dependencies

- **Spec 030**: Client Portal Foundation - portal infrastructure and authentication
- **Documents module**: Existing - for message attachments
- **Notifications module**: Existing - for email notifications
- **WebSocket support**: New - for real-time messaging
