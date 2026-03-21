# Feature Specification: ATOtrack Workflow Integration

**Feature Branch**: `028-atotrack-workflow-integration`
**Created**: 2026-01-01
**Status**: Draft
**Phase**: E.5 (ATOtrack)

## Overview

Integrate parsed ATO correspondence into the Clairo workflow system - automatically creating tasks, generating insights, sending notifications, and providing a dedicated ATOtrack dashboard. This completes the ATOtrack feature set, transforming raw email capture into proactive practice intelligence.

**Why This Matters**:
- Parsed emails are data; workflow integration makes them actionable
- Accountants need tasks with deadlines, not just a list of notices
- Proactive notifications prevent missed deadlines
- AI-drafted responses save hours on audit and remission requests
- ATOtrack dashboard = single view for all ATO matters across clients

**Disruption Level**: Low (extends existing task/insight systems)

---

## User Scenarios & Testing

### User Story 1 - Automatic Task Creation (Priority: P1)

As an accountant, I want tasks automatically created from ATO correspondence so that I don't have to manually track each notice.

**Why this priority**: Tasks with deadlines are the core value - ensuring nothing is missed.

**Independent Test**: ATO audit notice parsed → task created with 28-day deadline.

**Acceptance Scenarios**:

1. **Given** an audit notice is parsed, **When** workflow runs, **Then** a task is created with "Respond to ATO audit" and due date.

2. **Given** a penalty notice is parsed, **When** workflow runs, **Then** a task is created with "Review penalty - request remission or pay".

3. **Given** the correspondence is linked to a client, **When** task is created, **Then** the task is associated with that client.

---

### User Story 2 - Automatic Insight Generation (Priority: P1)

As an accountant, I want insights generated from ATO correspondence so that urgent matters surface in my dashboard.

**Why this priority**: Insights provide visibility in the main dashboard, not just ATO inbox.

**Independent Test**: Penalty notice parsed → insight appears in client dashboard and portfolio view.

**Acceptance Scenarios**:

1. **Given** a penalty notice is parsed, **When** insight is generated, **Then** it shows "ATO Penalty: $1,100 for [Client]" with high severity.

2. **Given** an audit notice is parsed, **When** insight is generated, **Then** it shows "ATO Audit Notice - Response Required" with critical severity.

3. **Given** I view my portfolio dashboard, **When** I check insights, **Then** I see all pending ATO matters across clients.

---

### User Story 3 - Deadline Notifications (Priority: P1)

As an accountant, I want notifications when ATO deadlines approach so that I never miss a response date.

**Why this priority**: Notifications are the proactive layer that prevents costly oversights.

**Independent Test**: Task due in 3 days → email notification sent.

**Acceptance Scenarios**:

1. **Given** a task due date is 7 days away, **When** notification check runs, **Then** I receive an email reminder.

2. **Given** a task due date is 3 days away, **When** notification check runs, **Then** I receive an urgent reminder.

3. **Given** a task is overdue, **When** notification check runs, **Then** I receive an overdue alert.

---

### User Story 4 - ATOtrack Dashboard (Priority: P1)

As an accountant, I want a dedicated ATOtrack dashboard so that I can see all ATO matters in one place.

**Why this priority**: Unified view across all clients is the core ATOtrack experience.

**Independent Test**: Open ATOtrack → see counts for overdue, due soon, handled, triage.

**Acceptance Scenarios**:

1. **Given** I open ATOtrack, **When** dashboard loads, **Then** I see summary cards: Overdue, Due Soon, Handled, Triage.

2. **Given** there are overdue items, **When** I view "Requires Attention", **Then** items are sorted by urgency.

3. **Given** I click on an item, **When** detail opens, **Then** I see the full correspondence with action buttons.

---

### User Story 5 - AI Response Drafting (Priority: P2)

As an accountant, I want AI to draft responses to ATO notices so that I can save time on common correspondence.

**Why this priority**: AI drafting accelerates the response process but requires human review.

**Independent Test**: Click "Draft Response" on audit notice → AI-generated response appears.

**Acceptance Scenarios**:

1. **Given** an audit notice is selected, **When** I click "Draft Response", **Then** AI generates a professional response template.

2. **Given** a penalty notice is selected, **When** I click "Draft Remission Request", **Then** AI drafts a remission request with relevant details.

3. **Given** a draft is generated, **When** I review it, **Then** I can edit and save for later or copy to email.

---

### User Story 6 - Mark as Resolved (Priority: P1)

As an accountant, I want to mark correspondence as resolved so that I can track what's been handled.

**Why this priority**: Completion tracking is essential for workflow closure.

**Independent Test**: Click "Mark Resolved" → item moves to Handled, task completed.

**Acceptance Scenarios**:

1. **Given** I'm viewing a correspondence item, **When** I click "Mark Resolved", **Then** status changes to RESOLVED.

2. **Given** the correspondence has a linked task, **When** I resolve it, **Then** the task is also marked complete.

3. **Given** the correspondence has a linked insight, **When** I resolve it, **Then** the insight is dismissed.

---

### User Story 7 - Practice Management Integration (Priority: P3)

As an accountant using Karbon or XPM, I want ATO tasks pushed to my practice management system so that I have one task list.

**Why this priority**: Nice-to-have integration; most value is in Clairo native workflow.

**Independent Test**: Configure Karbon → ATO task created in Clairo → appears in Karbon.

**Acceptance Scenarios**:

1. **Given** Karbon is connected, **When** an ATO task is created, **Then** a corresponding task is created in Karbon.

2. **Given** XPM is connected, **When** an ATO task is created, **Then** a job is created in XPM with deadline.

3. **Given** the external task is completed, **When** sync runs, **Then** Clairo task is also marked complete.

---

### Edge Cases

- What if correspondence has no due date?
  → Create task with default deadline (14 days) and flag for review

- What if the client is not yet matched?
  → Create task without client link, add to triage, update when matched

- What if AI drafting fails?
  → Show error message, provide manual template options

- What if Karbon/XPM sync fails?
  → Log error, retry with backoff, notify user of sync issues

- What if a notice is a duplicate?
  → Detect by reference number, link to existing correspondence

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST create tasks from parsed ATO correspondence
- **FR-002**: System MUST set task due dates based on notice type defaults
- **FR-003**: System MUST generate insights for high-priority correspondence
- **FR-004**: System MUST send notifications for approaching deadlines
- **FR-005**: System MUST provide ATOtrack dashboard with summary statistics
- **FR-006**: System MUST allow marking correspondence as resolved
- **FR-007**: System SHOULD provide AI-drafted responses for audit and penalty notices
- **FR-008**: System MAY integrate with Karbon and XPM for task sync
- **FR-009**: System MUST link tasks and insights to correspondence
- **FR-010**: System MUST update task/insight when correspondence is resolved

### Key Entities

- **ATOCorrespondence** (from Spec 027): Extended with task_id, insight_id
- **Task** (existing): Linked to correspondence
- **Insight** (existing): Generated from correspondence
- **Notification** (existing): Triggered by deadlines
- **ResponseDraft**: AI-generated response drafts

### Non-Functional Requirements

- **NFR-001**: Task creation MUST complete within 5 seconds of parsing
- **NFR-002**: Dashboard MUST load within 2 seconds
- **NFR-003**: AI drafting MUST complete within 30 seconds
- **NFR-004**: Notifications MUST be sent within 15 minutes of trigger
- **NFR-005**: Practice management sync MUST not block core workflow

---

## Auditing & Compliance Checklist

### Audit Events Required

- [x] **Workflow Events**: Yes - task/insight creation, resolution
- [x] **Notification Events**: Yes - deadline reminders sent
- [x] **AI Events**: Yes - response drafting requests
- [x] **Integration Events**: Yes - practice management sync

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|------------|---------|---------------|-----------|----------------|
| `atotrack.task.created` | Task auto-created | correspondence_id, task_id, due_date | 7 years | None |
| `atotrack.insight.created` | Insight generated | correspondence_id, insight_id, severity | 7 years | None |
| `atotrack.resolved` | Correspondence resolved | correspondence_id, user_id, method | 7 years | None |
| `atotrack.response.drafted` | AI draft generated | correspondence_id, draft_type | 7 years | None |
| `atotrack.notification.sent` | Deadline notification | correspondence_id, notification_type | 7 years | None |

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% of parsed correspondence with due dates creates tasks
- **SC-002**: Notification delivery rate >99%
- **SC-003**: AI response drafts used in >50% of applicable cases
- **SC-004**: Dashboard load time <2 seconds
- **SC-005**: Zero ATO deadlines missed by users with ATOtrack enabled

---

## Technical Notes (for Plan phase)

### Task Creation Rules

```python
TASK_RULES = {
    ATONoticeType.AUDIT_NOTICE: {
        "title_template": "Respond to ATO audit - {client_name}",
        "default_days": 28,
        "priority": "high",
    },
    ATONoticeType.PENALTY_NOTICE: {
        "title_template": "Review ATO penalty ${amount} - {client_name}",
        "default_days": 21,
        "priority": "high",
    },
    ATONoticeType.ACTIVITY_STATEMENT_REMINDER: {
        "title_template": "Lodge Activity Statement - {client_name}",
        "default_days": 14,
        "priority": "medium",
    },
    ATONoticeType.DEBT_NOTICE: {
        "title_template": "Address ATO debt ${amount} - {client_name}",
        "default_days": 14,
        "priority": "high",
    },
    # ... more rules
}
```

### Insight Generation

```python
class ATOInsight:
    correspondence_id: UUID
    client_id: UUID
    title: str  # "ATO Audit Notice - Response Required"
    description: str  # Summary from parsing
    severity: InsightSeverity  # CRITICAL, HIGH, MEDIUM, LOW
    action_url: str  # Link to correspondence detail
    due_date: date | None
```

### Notification Schedule

| Trigger | Channel | Template |
|---------|---------|----------|
| 7 days before due | Email | "ATO matter due in 7 days: {title}" |
| 3 days before due | Email + Push | "URGENT: ATO matter due in 3 days" |
| 1 day before due | Email + Push | "FINAL REMINDER: ATO matter due tomorrow" |
| Overdue | Email + Push | "OVERDUE: ATO matter past due date" |

---

## Dependencies

- **Spec 026 (Email Integration)**: Required - email connection
- **Spec 027 (ATO Parsing)**: Required - parsed correspondence
- **Existing Tasks module**: Required - task creation
- **Existing Insights module**: Required - insight generation
- **Existing Notifications module**: Required - email/push delivery
- **Karbon/XPM APIs**: Optional - practice management integration
