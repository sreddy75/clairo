# Feature Specification: ATO Correspondence Parsing

**Feature Branch**: `027-ato-correspondence-parsing`
**Created**: 2026-01-01
**Status**: Draft
**Phase**: E.5 (ATOtrack)

## Overview

Parse synced ATO emails using AI (Claude) to extract structured data: notice type, due dates, amounts, reference numbers, and required actions. Automatically match correspondence to clients and surface items requiring attention.

**Why This Matters**:
- Raw emails are unstructured - accountants need structured, actionable data
- ATO notices contain critical deadlines that must not be missed
- Manual reading of 100+ ATO emails/month is time-consuming
- AI parsing enables proactive alerts and automated task creation
- This is the "intelligence" layer that transforms email capture into ATOtrack

**Disruption Level**: Low (additive to Spec 026)

---

## User Scenarios & Testing

### User Story 1 - Automatic Email Parsing (Priority: P1)

As an accountant, I want synced ATO emails to be automatically parsed so that I can see structured information without reading each email.

**Why this priority**: Core value proposition - transforming raw emails into actionable intelligence.

**Independent Test**: New ATO email syncs → parsed data appears with notice type, due date, and summary.

**Acceptance Scenarios**:

1. **Given** an ATO email is synced, **When** parsing completes, **Then** I see the notice type (e.g., "Activity Statement Reminder").

2. **Given** an email contains a due date, **When** parsing completes, **Then** the due date is extracted and displayed.

3. **Given** an email contains an amount (penalty/debt), **When** parsing completes, **Then** the amount is extracted and displayed.

---

### User Story 2 - Notice Type Classification (Priority: P1)

As an accountant, I want emails classified by notice type so that I can prioritize and filter correspondence.

**Why this priority**: Different notice types require different urgency levels and responses.

**Independent Test**: View ATO inbox → emails are grouped/filterable by notice type.

**Acceptance Scenarios**:

1. **Given** I view ATO correspondence, **When** I filter by "Audit Notice", **Then** I see only audit-related emails.

2. **Given** an Activity Statement reminder arrives, **When** parsed, **Then** it's classified as "Activity Statement" type.

3. **Given** a penalty notice arrives, **When** parsed, **Then** it's classified as "Penalty" type with amount extracted.

---

### User Story 3 - Client Matching (Priority: P1)

As an accountant, I want ATO correspondence automatically matched to clients so that I can see all correspondence for a specific client.

**Why this priority**: Linking correspondence to clients enables the client-centric view accountants need.

**Independent Test**: Email with ABN → automatically matched to correct client.

**Acceptance Scenarios**:

1. **Given** an ATO email contains an ABN, **When** parsed, **Then** it's matched to the client with that ABN.

2. **Given** an email contains only a business name, **When** parsed, **Then** fuzzy matching suggests the likely client.

3. **Given** matching confidence is below 80%, **When** parsed, **Then** the item appears in the triage queue for manual review.

---

### User Story 4 - Triage Queue (Priority: P1)

As an accountant, I want to review and assign unmatched correspondence so that nothing falls through the cracks.

**Why this priority**: Not all emails can be auto-matched; manual triage ensures completeness.

**Independent Test**: View triage queue → assign unmatched email to correct client.

**Acceptance Scenarios**:

1. **Given** an email couldn't be matched, **When** I view the triage queue, **Then** I see the unmatched items.

2. **Given** I'm in triage, **When** I select a client for an item, **Then** it's linked and removed from triage.

3. **Given** an email is not relevant (spam/unrelated), **When** I mark as "Ignore", **Then** it's excluded from ATO tracking.

---

### User Story 5 - Confidence Scores (Priority: P2)

As an accountant, I want to see parsing confidence scores so that I can prioritize review of uncertain items.

**Why this priority**: AI isn't perfect - confidence scores help focus human review.

**Independent Test**: View parsed email → see confidence percentage for extracted fields.

**Acceptance Scenarios**:

1. **Given** a clearly structured ATO notice, **When** parsed, **Then** confidence score is 90%+.

2. **Given** an ambiguous email, **When** parsed, **Then** confidence score is lower and item is flagged.

3. **Given** I filter by "Low Confidence", **When** I view results, **Then** I see items needing review.

---

### User Story 6 - Semantic Search (Priority: P2)

As an accountant, I want to search ATO correspondence by meaning, not just keywords, so that I can find relevant items quickly.

**Why this priority**: Vector search enables "find all audit-related notices" queries.

**Independent Test**: Search "penalty notices last quarter" → relevant results appear.

**Acceptance Scenarios**:

1. **Given** I search "audit notices for Smith", **When** results load, **Then** I see audit-related correspondence for Smith clients.

2. **Given** I search "overdue activity statements", **When** results load, **Then** I see relevant matches even if exact phrase isn't in email.

3. **Given** correspondence is stored with embeddings, **When** I search, **Then** results are ranked by semantic relevance.

---

### User Story 7 - Attachment Extraction (Priority: P2)

As an accountant, I want PDF attachments parsed so that I can access structured data from formal ATO notices.

**Why this priority**: Many ATO notices are PDF attachments, not inline email content.

**Independent Test**: Email with PDF notice → PDF content is parsed and structured.

**Acceptance Scenarios**:

1. **Given** an email has a PDF attachment, **When** parsed, **Then** the PDF content is extracted.

2. **Given** the PDF is an official ATO notice, **When** parsed, **Then** reference number and dates are extracted.

3. **Given** I view correspondence detail, **When** I click attachment, **Then** I can download the original PDF.

---

### Edge Cases

- What if the email is not actually from ATO (spoofed)?
  → Validate sender domain strictly, flag suspicious emails

- What if parsing extracts incorrect data?
  → Show confidence scores, allow manual correction, learn from corrections

- What if the same email is processed twice?
  → Idempotent processing using provider_message_id

- What if client ABN has changed?
  → Match on historical ABNs as well as current

- What if an email relates to multiple clients?
  → Support multiple client links per correspondence

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST parse all synced ATO emails using AI
- **FR-002**: System MUST classify emails into notice types (Activity Statement, Audit, Penalty, Debt, General)
- **FR-003**: System MUST extract: notice type, due date, amount, reference number, required action
- **FR-004**: System MUST match correspondence to clients by ABN (exact) or name (fuzzy)
- **FR-005**: System MUST surface low-confidence matches in triage queue
- **FR-006**: System MUST store email content in vector database for semantic search
- **FR-007**: System SHOULD extract content from PDF attachments
- **FR-008**: System MUST provide confidence scores for all extracted fields
- **FR-009**: System MUST allow manual correction of parsed data
- **FR-010**: System MUST be idempotent (same email processed once)

### Key Entities

- **ATOCorrespondence**: Parsed email with structured fields
- **ATONoticeType**: Enum of notice categories
- **CorrespondenceStatus**: NEW, REVIEWED, ACTIONED, RESOLVED
- **TriageItem**: Unmatched/low-confidence items for manual review

### Non-Functional Requirements

- **NFR-001**: Parsing MUST complete within 30 seconds per email
- **NFR-002**: Client matching MUST achieve >90% accuracy for ABN matches
- **NFR-003**: Vector embeddings MUST be stored per-tenant (data isolation)
- **NFR-004**: Parsing costs MUST be tracked per tenant for billing
- **NFR-005**: System MUST handle 1,000 emails/day per tenant

---

## Auditing & Compliance Checklist

### Audit Events Required

- [x] **Data Access Events**: Yes - accessing parsed correspondence
- [x] **Data Modification Events**: Yes - manual corrections
- [x] **AI Processing Events**: Yes - track parsing and confidence
- [x] **Compliance Events**: Yes - 7-year retention

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|------------|---------|---------------|-----------|----------------|
| `correspondence.parsed` | AI parsing complete | tenant_id, email_id, notice_type, confidence | 7 years | None |
| `correspondence.matched` | Client matched | correspondence_id, client_id, match_type | 7 years | None |
| `correspondence.triaged` | Manual triage action | correspondence_id, action, user_id | 7 years | None |
| `correspondence.corrected` | Manual correction | correspondence_id, field, old_value, new_value | 7 years | None |

### Compliance Considerations

- **AI Transparency**: Store parsing prompts and model version for auditability
- **Data Isolation**: Vector store collections scoped by tenant_id
- **Retention**: 7-year retention per ATO requirements
- **Accuracy**: Track and report parsing accuracy over time

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: >95% of emails parsed within 30 seconds
- **SC-002**: >90% accuracy for ABN-based client matching
- **SC-003**: >80% accuracy for name-based fuzzy matching
- **SC-004**: <5% of emails require manual triage
- **SC-005**: Semantic search returns relevant results in <2 seconds

---

## Technical Notes (for Plan phase)

### Notice Type Taxonomy

```python
class ATONoticeType(str, Enum):
    ACTIVITY_STATEMENT = "activity_statement"  # BAS/IAS reminders
    ACTIVITY_STATEMENT_CONFIRMATION = "activity_statement_confirmation"
    AUDIT_NOTICE = "audit_notice"
    PENALTY_NOTICE = "penalty_notice"
    DEBT_NOTICE = "debt_notice"
    RUNNING_BALANCE = "running_balance"
    TAX_RETURN = "tax_return"
    SUPERANNUATION = "superannuation"
    PAYG_WITHHOLDING = "payg_withholding"
    FBT = "fringe_benefits_tax"
    GENERAL = "general"
```

### Claude Parsing Prompt

```
Extract structured information from this ATO email:

<email>
{email_content}
</email>

Return JSON with:
- notice_type: one of [activity_statement, audit_notice, penalty_notice, ...]
- reference_number: ATO reference if present
- due_date: in YYYY-MM-DD format if present
- amount: numeric amount if present (penalties, debts)
- client_identifier: ABN, TFN, or business name mentioned
- required_action: brief summary of what action is needed
- confidence: 0-100 score for overall extraction confidence
```

### Vector Storage

```python
# Qdrant collection per tenant
collection_name = f"ato_correspondence_{tenant_id}"

# Embedding model
model = "text-embedding-3-small"  # OpenAI or Claude embeddings

# Metadata stored with vector
metadata = {
    "correspondence_id": str,
    "notice_type": str,
    "client_id": str,
    "received_at": datetime,
}
```

---

## Dependencies

- **Spec 026 (Email Integration)**: Required - provides RawEmail entities to parse
- **Spec 028 (ATOtrack Workflow)**: Dependent - consumes parsed correspondence
- **Existing Client Module**: Required - for ABN/name matching
- **Existing Qdrant Setup**: Required - for vector storage
