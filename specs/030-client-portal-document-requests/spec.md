# Feature Specification: Client Portal Foundation + Document Requests

**Feature Branch**: `030-client-portal-document-requests`
**Created**: 2026-01-01
**Status**: Draft
**Phase**: F (Business Owner Engagement + ClientChase)

## Overview

Build the client portal foundation that enables business owners to interact with their accountant through Clairo, and implement the ClientChase document request workflow. This creates a B2B2C distribution channel where accountants invite clients, and provides automated document collection that reduces chase time from hours to minutes.

**Why This Matters**:
- B2B2C distribution: Each accountant brings 50-200 clients
- Reduces document chase time: 4 hours/week → 15 minutes
- Professional experience: Clients see BAS status, not spreadsheets
- Audit trail: All requests and responses tracked
- Auto-reminders: No more manual follow-up emails

**The ClientChase Value**:
```
BEFORE: "Can you send me your bank statements?" → 3 emails, 2 phone calls, 1 week
AFTER: Click template → Client gets push notification → Upload from phone → Done
```

**Disruption Level**: Medium (new portal surface, new user type)

---

## User Scenarios & Testing

### User Story 1 - Client Invitation (Priority: P1)

As an accountant, I want to invite clients to the portal so that they can view their BAS status and respond to requests.

**Why this priority**: Foundation for all portal functionality.

**Independent Test**: Invite client → client receives email → clicks magic link → sees dashboard.

**Acceptance Scenarios**:

1. **Given** I have a client record, **When** I click "Invite to Portal", **Then** an invitation email is sent with a magic link.

2. **Given** a client receives the invitation, **When** they click the magic link, **Then** they're authenticated and see their dashboard without password creation.

3. **Given** a client has portal access, **When** they return later, **Then** they can request a new magic link via email.

---

### User Story 2 - Client Dashboard (Priority: P1)

As a business owner, I want to see my BAS status and key metrics so that I understand where things stand.

**Why this priority**: Core value proposition for client engagement.

**Independent Test**: Client logs in → sees current BAS status, pending items, key metrics.

**Acceptance Scenarios**:

1. **Given** I log into the portal, **When** the dashboard loads, **Then** I see my current BAS period status (Draft, Ready, Lodged).

2. **Given** I have pending action items, **When** I view the dashboard, **Then** I see a count of items needing my attention.

3. **Given** my BAS is ready for review, **When** I view the dashboard, **Then** I see a prominent "Review BAS" call-to-action.

---

### User Story 3 - Document Request Templates (Priority: P1)

As an accountant, I want to use pre-built document request templates so that I can quickly ask for common documents.

**Why this priority**: Templates are the core time-saver for ClientChase.

**Independent Test**: Select "Bank Statements" template → customize dates → send to client.

**Acceptance Scenarios**:

1. **Given** I want to request bank statements, **When** I select the template, **Then** it pre-fills title, description, and expected document type.

2. **Given** I'm using a template, **When** I customize the period, **Then** the description updates to include the specific dates.

3. **Given** I need a custom request, **When** I create from scratch, **Then** I can save it as a template for future use.

---

### User Story 4 - Send Document Request (Priority: P1)

As an accountant, I want to send document requests to clients so that they know what I need.

**Why this priority**: Core workflow for document collection.

**Independent Test**: Send request → client sees it in portal → gets email notification.

**Acceptance Scenarios**:

1. **Given** I've composed a request, **When** I click "Send", **Then** the client receives an email with a link to respond.

2. **Given** the client has the app, **When** a request is sent, **Then** they receive a push notification.

3. **Given** I set a due date, **When** the request is sent, **Then** the due date is prominently displayed to the client.

---

### User Story 5 - Bulk Document Requests (Priority: P1)

As an accountant, I want to send the same request to multiple clients so that I can efficiently collect end-of-year documents.

**Why this priority**: Huge time-saver for common requests across portfolio.

**Independent Test**: Select 20 clients → apply template → send to all.

**Acceptance Scenarios**:

1. **Given** I want to request bank statements from all clients, **When** I select multiple clients and apply a template, **Then** individual requests are created for each.

2. **Given** I'm sending bulk requests, **When** I preview before sending, **Then** I see each client's personalized request.

3. **Given** I've sent bulk requests, **When** I view tracking, **Then** I see aggregate status (15 pending, 3 responded, 2 complete).

---

### User Story 6 - Respond to Request (Priority: P1)

As a business owner, I want to respond to document requests so that my accountant has what they need.

**Why this priority**: Client side of the core workflow.

**Independent Test**: Open request → upload document → add note → submit.

**Acceptance Scenarios**:

1. **Given** I have a pending request, **When** I view it, **Then** I see what's being asked for and the due date.

2. **Given** I'm responding to a request, **When** I drag-drop files, **Then** they upload and attach to my response.

3. **Given** I've uploaded documents, **When** I click "Submit", **Then** my accountant is notified and the request moves to "Responded".

---

### User Story 7 - Request Tracking Dashboard (Priority: P1)

As an accountant, I want to track request status across all clients so that I know who hasn't responded.

**Why this priority**: Visibility is essential for follow-up.

**Independent Test**: Open tracking dashboard → see all pending requests sorted by urgency.

**Acceptance Scenarios**:

1. **Given** I have multiple pending requests, **When** I view tracking, **Then** I see them grouped by status (Pending, Viewed, Responded, Complete).

2. **Given** some requests are overdue, **When** I filter by "Overdue", **Then** I see only those clients.

3. **Given** a client viewed but didn't respond, **When** I see their request, **Then** the status shows "Viewed" with timestamp.

---

### User Story 8 - Auto-Reminders (Priority: P2)

As an accountant, I want automatic reminders sent to clients so that I don't have to chase manually.

**Why this priority**: Automation that saves significant time.

**Independent Test**: Request due in 2 days → auto-reminder sent → client receives email.

**Acceptance Scenarios**:

1. **Given** a request is pending and due in 3 days, **When** the reminder job runs, **Then** the client receives a reminder email.

2. **Given** a request is overdue, **When** the reminder job runs daily, **Then** the client receives an overdue reminder.

3. **Given** I want to disable auto-reminders for a request, **When** I toggle the setting, **Then** no automatic reminders are sent.

---

### User Story 9 - Document Upload (Priority: P1)

As a business owner, I want to upload documents easily so that responding is quick.

**Why this priority**: Frictionless upload increases response rates.

**Independent Test**: Drag-drop file → see preview → confirm upload.

**Acceptance Scenarios**:

1. **Given** I'm responding to a request, **When** I drag files onto the upload area, **Then** they upload with progress indicator.

2. **Given** I'm on mobile, **When** I tap "Upload", **Then** I can choose from camera, photos, or files.

3. **Given** I've uploaded a document, **When** I view the preview, **Then** I can remove it before submitting.

---

### User Story 10 - Auto-Filing (Priority: P2)

As an accountant, I want uploaded documents automatically organized so that I can find them easily.

**Why this priority**: Reduces manual filing work.

**Independent Test**: Client uploads bank statement → appears in client's Documents > Bank Statements folder.

**Acceptance Scenarios**:

1. **Given** a client uploads a document, **When** it's received, **Then** it's automatically filed under the client and period.

2. **Given** the request specifies document type, **When** the client uploads, **Then** the document is tagged with that type.

3. **Given** I'm viewing a client's documents, **When** I look at the folder structure, **Then** I see organized by type and period.

---

### Edge Cases

- What if client's email bounces?
  → Mark invitation as failed, notify accountant

- What if magic link expires?
  → Client can request a new link via email entry

- What if client uploads wrong document?
  → Accountant can reject and re-request

- What if bulk request fails for some clients?
  → Show partial success, allow retry for failed

- What if document is too large?
  → Compress if possible, otherwise reject with size limit

- What if client has no email?
  → Cannot use portal, accountant notes this in client record

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST allow accountants to invite clients via email
- **FR-002**: System MUST authenticate clients via magic link (no password)
- **FR-003**: System MUST show client dashboard with BAS status
- **FR-004**: System MUST provide document request templates
- **FR-005**: System MUST support bulk document requests to multiple clients
- **FR-006**: System MUST allow clients to respond with document uploads
- **FR-007**: System MUST track request status (Pending, Viewed, Responded, Complete)
- **FR-008**: System MUST send auto-reminders for pending requests
- **FR-009**: System MUST support drag-drop and mobile upload
- **FR-010**: System SHOULD auto-file documents by type and period
- **FR-011**: System MUST notify accountants when clients respond
- **FR-012**: System MUST provide request tracking dashboard

### Key Entities

- **PortalInvitation**: Invitation sent to client with magic link
- **PortalSession**: Authenticated client session
- **DocumentRequestTemplate**: Reusable request templates
- **DocumentRequest**: Request sent to client for documents
- **DocumentRequestResponse**: Client's response with uploaded documents
- **PortalDocument**: Document uploaded through portal

### Non-Functional Requirements

- **NFR-001**: Magic link MUST be valid for 7 days
- **NFR-002**: Document upload MUST support files up to 50MB
- **NFR-003**: Portal MUST load within 2 seconds
- **NFR-004**: Email notifications MUST send within 5 minutes
- **NFR-005**: Auto-reminders MUST run daily at 9 AM client timezone
- **NFR-006**: Bulk requests MUST complete within 30 seconds for 100 clients

---

## Auditing & Compliance Checklist

### Audit Events Required

- [x] **Portal Events**: Yes - invitations, logins, actions
- [x] **Request Events**: Yes - sent, viewed, responded, completed
- [x] **Document Events**: Yes - uploads, downloads
- [x] **Notification Events**: Yes - emails sent, reminders sent

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|------------|---------|---------------|-----------|----------------|
| `portal.invitation.sent` | Invite client | client_id, email | 7 years | Email |
| `portal.login` | Magic link used | client_id, IP | 7 years | IP address |
| `request.sent` | Request created | request_id, client_id | 7 years | None |
| `request.viewed` | Client opens | request_id, timestamp | 7 years | None |
| `request.responded` | Client submits | request_id, doc_count | 7 years | None |
| `request.completed` | Accountant closes | request_id, user_id | 7 years | None |
| `document.uploaded` | File uploaded | doc_id, size, type | 7 years | None |
| `reminder.sent` | Auto-reminder | request_id, reminder_count | 7 years | None |

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: >40% client activation rate (invited → logged in)
- **SC-002**: >70% document request response rate
- **SC-003**: Average response time <3 days
- **SC-004**: <10% requests requiring manual chase
- **SC-005**: Portal load time <2 seconds

---

## Technical Notes (for Plan phase)

### Magic Link Authentication

```python
class MagicLinkService:
    TOKEN_EXPIRY_DAYS = 7

    def generate_token(self, client_id: UUID, email: str) -> str:
        """Generate a secure magic link token."""
        payload = {
            "client_id": str(client_id),
            "email": email,
            "exp": datetime.utcnow() + timedelta(days=self.TOKEN_EXPIRY_DAYS),
            "jti": str(uuid4()),  # Unique token ID
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

    def verify_token(self, token: str) -> dict | None:
        """Verify magic link token."""
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
```

### Document Request Template

```python
class DocumentRequestTemplate(Base):
    id: UUID
    tenant_id: UUID

    name: str  # "Bank Statements"
    description_template: str  # "Please upload bank statements for {period}"
    expected_document_types: list[str]  # ["bank_statement", "pdf"]
    default_priority: RequestPriority
    default_due_days: int  # Days from send date

    is_system: bool  # Built-in vs custom
    created_by: UUID | None
```

### Request Status Flow

```
PENDING → VIEWED → RESPONDED → COMPLETE
    │         │          │
    │         │          └── Accountant marks complete
    │         └── Client submits response
    └── Client opens request
```

### Auto-Reminder Schedule

```python
REMINDER_SCHEDULE = [
    {"days_before_due": 3, "template": "reminder_3_days"},
    {"days_before_due": 1, "template": "reminder_1_day"},
    {"days_after_due": 1, "template": "overdue_1_day"},
    {"days_after_due": 3, "template": "overdue_3_days"},
    {"days_after_due": 7, "template": "overdue_7_days"},
]
```

---

## Dependencies

- **Existing clients module**: Required - client records to invite
- **Existing documents module**: Required - document storage
- **Email service (Resend)**: Required - invitation and notification emails
- **Push notifications**: Required - mobile alerts
- **S3/MinIO**: Required - document upload storage
