# Spec 010: Review & Approval - Gap Analysis

**Status**: DEFERRED to Phase E
**Priority**: After AI Core (Phase B-D)
**Reason**: Review workflow doesn't create competitive moat; AI does

---

## Context

Spec 010 was implemented on branch `feature/010-review-approval` but diverged significantly from main. The branches cannot be safely merged due to conflicting changes in:
- `backend/app/modules/bas/models.py`
- `backend/app/modules/bas/router.py`
- `backend/app/modules/bas/schemas.py`
- `backend/app/modules/bas/service.py`
- `frontend/src/components/bas/BASTab.tsx`
- `backend/app/modules/notifications/` (completely different implementation)

**Decision**: Rebuild Spec 010 from scratch after Phase D, using the original requirements as reference.

---

## Features to Rebuild

### P1 - Must Have (Core Workflow)

#### 1. Submit for Review
- Preparer clicks "Submit for Review" on completed BAS session
- Status changes from "In Progress" to "Ready for Review"
- Notification sent to eligible reviewers
- Optional: Preparer can add notes for reviewer
- Block submission if critical issues unresolved

#### 2. Review Queue
- New page: `/review`
- Shows all "Ready for Review" sessions for tenant
- Sorted by: due date (nearest first), then submission date (oldest first)
- Columns: Client name, ABN, Period, Preparer, Submitted date, Due date, Days until due, Total payable, Quality score
- Highlight sessions in review >48 hours as "Overdue for review"

#### 3. Review BAS Details
- Reviewer opens session and sees:
  - Complete GST calculation summary (G-fields, 1A, 1B)
  - PAYG withholding summary (W1, W2)
  - Total payable/refundable
  - Variance analysis vs prior periods
  - List of adjustments with reasons
  - Preparer notes
- Drill-down to underlying transactions
- Preview working papers (PDF/Excel) without downloading

#### 4. Approve BAS
- Reviewer clicks "Approve" with confirmation dialog
- Status changes to "Approved"
- Records: approval timestamp, approver ID
- Audit log entry created
- **Self-approval blocked**: "Cannot approve your own work"
- Approved sessions are locked from editing

#### 5. Audit Trail
- Every action logged:
  - Action type (submitted, approved, changes_requested, commented)
  - Actor (user ID, name)
  - Timestamp
  - Before/after values where applicable
- Viewable in session detail page
- Exportable for compliance

### P2 - Should Have (Quality Control)

#### 6. Request Changes
- Reviewer clicks "Request Changes"
- Modal to enter detailed feedback
- Status changes to "Changes Requested"
- Preparer receives notification
- Feedback visible to preparer prominently

#### 7. Review Comments
- Field-level comments (e.g., comment on G1 Total Sales)
- Comment icon on each BAS field
- "View All Comments" consolidated list
- Preparer can mark comments as "Resolved" with response

#### 8. Re-submit Flow
- Preparer makes corrections
- Re-submits with response notes
- Review history shows all cycles (feedback → response → feedback...)

### P3 - Nice to Have

#### 9. Multi-level Approval
- Configurable approval chain: Junior → Senior → Partner
- Each level has own approval step
- Settings per tenant

#### 10. Solo Practitioner Mode
- Self-approval allowed for solo practitioners
- Enabled in practice settings
- Still creates audit trail

#### 11. Reviewer Assignment
- When submitting, preparer can select specific reviewer
- Dropdown of users with review permissions
- Notification only to assigned reviewer

---

## Database Changes Required

```python
# New fields on BASSession model
submitted_at: datetime | None
submitted_by_id: UUID | None
reviewer_id: UUID | None  # Assigned reviewer
approved_at: datetime | None
approved_by_id: UUID | None

# New model: ReviewComment
class ReviewComment(Base):
    id: UUID
    session_id: UUID  # FK to BASSession
    user_id: UUID
    field_name: str | None  # e.g., "g1_total_sales" for field-level
    content: str
    is_resolved: bool
    resolved_by_id: UUID | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime

# New model: ReviewAuditLog
class ReviewAuditLog(Base):
    id: UUID
    session_id: UUID
    action: str  # submitted, approved, changes_requested, comment_added, etc.
    actor_id: UUID
    details: dict  # JSON with action-specific data
    created_at: datetime
```

---

## API Endpoints Required

```
POST   /api/v1/bas/sessions/{session_id}/submit-for-review
POST   /api/v1/bas/sessions/{session_id}/approve
POST   /api/v1/bas/sessions/{session_id}/request-changes
GET    /api/v1/bas/review-queue
GET    /api/v1/bas/sessions/{session_id}/comments
POST   /api/v1/bas/sessions/{session_id}/comments
PATCH  /api/v1/bas/comments/{comment_id}/resolve
GET    /api/v1/bas/sessions/{session_id}/audit-log
```

---

## Frontend Components Required

1. **Review Queue Page** (`/review`)
   - Table with filtering, sorting
   - Click row to open review

2. **Review Panel in BASTab**
   - Approve/Request Changes buttons
   - Comments sidebar
   - Audit trail accordion

3. **Submit for Review Modal**
   - Notes field
   - Reviewer selection (optional)
   - Validation warnings

4. **Comments Component**
   - Inline comments on fields
   - Consolidated comment list
   - Resolve/reply functionality

---

## Reference

The original implementation exists on branch `feature/010-review-approval`. Key files:
- `specs/010-review-approval/spec.md` - Full requirements
- `specs/010-review-approval/plan.md` - Architecture decisions
- `specs/010-review-approval/tasks.md` - Implementation tasks

These can be referenced but code should be rebuilt fresh on current main.

---

## When to Implement

**Phase E (Week 11+)** - After:
- Phase B: AI Core (Knowledge Base, RAG, Multi-Agent, AI Assistant)
- Phase C: Proactive Intelligence (Insight Engine, Triggers, Cross-Pillar)
- Phase D: Business Owner Experience (Portal, AI, Documents, Mobile)

Estimated effort: 1-2 weeks to rebuild from scratch.
