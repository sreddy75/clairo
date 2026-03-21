# Data Model: Voice Feedback Portal

**Feature**: 048-voice-feedback-portal
**Date**: 2026-03-16

## Entities

### 1. FeedbackSubmission

The primary entity. Represents a single feedback submission from a user.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, auto-generated | Unique identifier |
| tenant_id | UUID | FK → tenants.id, NOT NULL, indexed | Tenant isolation |
| submitter_id | UUID | NOT NULL, indexed | Clerk user ID of submitter |
| submitter_name | VARCHAR(255) | NOT NULL | Display name (denormalised for card display) |
| title | VARCHAR(500) | NULL | Brief title — set when brief is confirmed |
| type | VARCHAR(20) | NOT NULL | `feature_request` or `bug_enhancement` |
| status | VARCHAR(20) | NOT NULL, default `draft` | `draft`, `new`, `in_review`, `planned`, `in_progress`, `done` |
| severity | VARCHAR(20) | NULL | `low`, `medium`, `high`, `critical` — set from brief |
| audio_file_key | VARCHAR(500) | NULL | MinIO object key for uploaded audio |
| audio_duration_seconds | INTEGER | NULL | Duration of audio recording |
| transcript | TEXT | NULL | Full transcription of audio |
| brief_data | JSONB | NULL | Structured brief as JSON (mode-specific schema) |
| brief_markdown | TEXT | NULL | Pre-rendered markdown of the brief |
| conversation_complete | BOOLEAN | NOT NULL, default FALSE | Whether AI conversation is finished |
| created_at | TIMESTAMPTZ | NOT NULL, auto | Creation timestamp |
| updated_at | TIMESTAMPTZ | NOT NULL, auto | Last update timestamp |

**Indexes**:
- `ix_feedback_submissions_tenant_status` — (tenant_id, status) for kanban queries
- `ix_feedback_submissions_tenant_submitter` — (tenant_id, submitter_id) for "my submissions" queries
- `ix_feedback_submissions_tenant_type` — (tenant_id, type) for type filtering

**State transitions**:
```
draft → new (user confirms brief)
new → in_review (team picks up)
in_review → planned (team decides to build)
in_review → done (team closes — duplicate, won't fix)
planned → in_progress (work starts)
in_progress → done (work complete)
Any → done (can close from any state)
```

---

### 2. FeedbackMessage

Individual messages in the AI clarification conversation. One-to-many with FeedbackSubmission.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, auto-generated | Unique identifier |
| submission_id | UUID | FK → feedback_submissions.id, NOT NULL, indexed | Parent submission |
| role | VARCHAR(20) | NOT NULL | `system`, `user`, `assistant` |
| content | TEXT | NOT NULL | Message text content |
| content_type | VARCHAR(20) | NOT NULL, default `text` | `text`, `transcript` (for transcribed voice messages) |
| created_at | TIMESTAMPTZ | NOT NULL, auto | Message timestamp |

**Indexes**:
- `ix_feedback_messages_submission_created` — (submission_id, created_at) for ordered conversation retrieval

**Notes**:
- No `tenant_id` needed — tenant isolation is enforced at the submission level via JOIN
- `system` role messages store the initial system prompt (PM hat or Engineer hat) — included for auditability
- `transcript` content_type distinguishes voice-transcribed responses from typed text

---

### 3. FeedbackComment

Internal team notes on a submission. One-to-many with FeedbackSubmission.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, auto-generated | Unique identifier |
| submission_id | UUID | FK → feedback_submissions.id, NOT NULL, indexed | Parent submission |
| author_id | UUID | NOT NULL | Clerk user ID of commenter |
| author_name | VARCHAR(255) | NOT NULL | Display name (denormalised) |
| content | TEXT | NOT NULL | Comment text |
| created_at | TIMESTAMPTZ | NOT NULL, auto | Comment timestamp |

**Indexes**:
- `ix_feedback_comments_submission` — (submission_id) for loading comments on a submission

**Notes**:
- No `tenant_id` needed — tenant isolation enforced via submission JOIN
- Comments are team-only — access controlled at the API level (admin role required)

---

## Enums

```python
class SubmissionType(str, Enum):
    FEATURE_REQUEST = "feature_request"
    BUG_ENHANCEMENT = "bug_enhancement"

class SubmissionStatus(str, Enum):
    DRAFT = "draft"
    NEW = "new"
    IN_REVIEW = "in_review"
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    DONE = "done"

class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"

class ContentType(str, Enum):
    TEXT = "text"
    TRANSCRIPT = "transcript"

class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
```

---

## Entity Relationship Diagram

```
┌─────────────────────────┐
│   FeedbackSubmission    │
├─────────────────────────┤
│ id (PK)                 │
│ tenant_id (FK)          │───── tenants
│ submitter_id            │
│ submitter_name          │
│ title                   │
│ type                    │
│ status                  │
│ severity                │
│ audio_file_key          │
│ audio_duration_seconds  │
│ transcript              │
│ brief_data (JSONB)      │
│ brief_markdown          │
│ conversation_complete   │
│ created_at              │
│ updated_at              │
├─────────────────────────┤
│                         │
│  1 ───── * messages     │──┐
│  1 ───── * comments     │──┼──┐
│                         │  │  │
└─────────────────────────┘  │  │
                             │  │
┌─────────────────────────┐  │  │
│    FeedbackMessage      │◄─┘  │
├─────────────────────────┤     │
│ id (PK)                 │     │
│ submission_id (FK)      │     │
│ role                    │     │
│ content                 │     │
│ content_type            │     │
│ created_at              │     │
└─────────────────────────┘     │
                                │
┌─────────────────────────┐     │
│    FeedbackComment      │◄────┘
├─────────────────────────┤
│ id (PK)                 │
│ submission_id (FK)      │
│ author_id               │
│ author_name             │
│ content                 │
│ created_at              │
└─────────────────────────┘
```

---

## Migration Notes

- All three tables are new — no migration conflicts expected
- FeedbackSubmission.tenant_id references the existing `tenants` table
- No foreign keys to `users` table — user IDs are stored as UUIDs referencing Clerk (consistent with other modules)
- JSONB `brief_data` has no database-level schema validation — validated at the application layer via Pydantic
- Cascade delete: deleting a submission should cascade to its messages and comments
