# Plan: Action Items (Spec 016b)

**Spec**: 016b-action-items
**Phase**: C (Proactive Intelligence)
**Dependencies**: Spec 016 (Insight Engine) ✅
**Estimated Effort**: 2-3 days

---

## Overview

Convert AI-generated insights into curated, actionable work items. This creates a human-in-the-loop workflow where AI suggests issues and accountants decide what becomes prioritized work.

---

## Architecture

### Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DATA FLOW                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐        │
│  │   Insight    │     │  ActionItem  │     │    User      │        │
│  │   (Spec 016) │────▶│   (New)      │────▶│   Actions    │        │
│  └──────────────┘     └──────────────┘     └──────────────┘        │
│         │                    │                    │                 │
│         │                    │                    │                 │
│    AI-generated         Human-curated        Work completed         │
│    (automatic)          (intentional)        (accountable)          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Model Relationships

```
┌─────────────────────┐
│      Insight        │
│  (from Spec 016)    │
├─────────────────────┤
│ id                  │
│ title               │
│ priority            │
│ client_id           │
│ status              │◀───────┐
└─────────────────────┘        │ source_insight_id (optional)
                               │
┌─────────────────────┐        │
│    ActionItem       │────────┘
│      (NEW)          │
├─────────────────────┤
│ id                  │
│ tenant_id           │
│ title               │
│ description         │
│ source_insight_id   │ ← Links back to source insight
│ client_id           │
│ client_name         │
│ assigned_to_user_id │
│ assigned_to_name    │
│ assigned_by_user_id │
│ due_date            │
│ priority            │
│ status              │
│ created_at          │
│ completed_at        │
│ resolution_notes    │
└─────────────────────┘
```

---

## Implementation Phases

### Phase 1: Backend Foundation
- Database migration for action_items table
- ActionItem SQLAlchemy model
- Pydantic schemas (Create, Update, Response)
- Basic ActionItemService with CRUD

### Phase 2: API Endpoints
- REST endpoints for action items
- Convert insight to action endpoint
- List with filters (status, priority, assignee, client)
- Status transitions (start, complete)

### Phase 3: Frontend - Action Items Page
- New route `/action-items`
- List view with grouping (overdue, this week, upcoming)
- Filter controls
- Action item cards with status actions

### Phase 4: Frontend - Integration
- "Convert to Action" on insight cards/detail
- Modal for creating action item from insight
- Update insight status when converted
- Dashboard widget

### Phase 5: Polish
- Navigation link
- Empty states
- Loading states
- Error handling

---

## Technical Decisions

### 1. Separate Model (Option B)

**Decision**: Create separate ActionItem model, not extend Insight

**Rationale**:
- Clean separation of concerns (AI-generated vs human-curated)
- ActionItems can exist without insights (standalone tasks)
- Different lifecycle and status states
- Easier to add features (recurring, templates) later

### 2. Denormalized Fields

**Decision**: Store `client_name` and `assigned_to_name` on ActionItem

**Rationale**:
- Avoids joins for list queries
- Client/user names rarely change
- Performance for dashboard widget

### 3. Soft Reference to Insight

**Decision**: `source_insight_id` is nullable FK

**Rationale**:
- Action items can be standalone (custom tasks)
- Maintains traceability when created from insight
- Insight can be deleted without breaking action item

### 4. User Assignment via Clerk ID

**Decision**: Store Clerk user_id for assignment

**Rationale**:
- Consistent with existing auth
- Can fetch user details from Clerk when needed
- Denormalize name for display

---

## API Design

### Endpoints

```
# Core CRUD
POST   /api/v1/action-items              Create action item
GET    /api/v1/action-items              List with filters
GET    /api/v1/action-items/:id          Get single item
PATCH  /api/v1/action-items/:id          Update item
DELETE /api/v1/action-items/:id          Delete item

# Status transitions
POST   /api/v1/action-items/:id/start    Mark in_progress
POST   /api/v1/action-items/:id/complete Mark completed

# Convenience
POST   /api/v1/insights/:id/convert      Create action from insight
```

### Query Parameters for List

```
GET /api/v1/action-items?
    status=pending,in_progress     # Filter by status
    priority=urgent,high           # Filter by priority
    assigned_to=user_id            # Filter by assignee
    assigned_to=me                 # Shortcut for current user
    client_id=uuid                 # Filter by client
    due_before=2026-01-15          # Due date filter
    due_after=2026-01-01
    include_completed=false        # Exclude completed by default
    limit=50
    offset=0
```

---

## Frontend Components

### New Components

```
frontend/src/
├── app/(protected)/
│   └── action-items/
│       └── page.tsx              # Action Items list page
├── components/
│   └── action-items/
│       ├── ActionItemCard.tsx    # Single action item display
│       ├── ActionItemList.tsx    # List with grouping
│       ├── ActionItemFilters.tsx # Filter controls
│       ├── CreateActionModal.tsx # Create/convert modal
│       └── ActionItemWidget.tsx  # Dashboard widget
├── lib/api/
│   └── action-items.ts           # API client functions
└── types/
    └── action-items.ts           # TypeScript types
```

### Integration Points

```
# Insight card - add "Convert to Action" button
frontend/src/app/(protected)/clients/[id]/page.tsx

# Dashboard - add ActionItemWidget
frontend/src/app/(protected)/dashboard/page.tsx

# Navigation - add Action Items link
frontend/src/app/(protected)/layout.tsx
```

---

## Database Schema

```sql
CREATE TABLE action_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),

    -- Content
    title VARCHAR(500) NOT NULL,
    description TEXT,

    -- Source
    source_insight_id UUID REFERENCES insights(id) ON DELETE SET NULL,

    -- Client context
    client_id UUID REFERENCES xero_connections(id) ON DELETE SET NULL,
    client_name VARCHAR(255),

    -- Assignment
    assigned_to_user_id VARCHAR(255),  -- Clerk user ID
    assigned_to_name VARCHAR(255),
    assigned_by_user_id VARCHAR(255) NOT NULL,

    -- Scheduling
    due_date DATE,
    priority VARCHAR(20) NOT NULL DEFAULT 'medium',

    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    -- Completion
    resolution_notes TEXT,

    -- Constraints
    CONSTRAINT action_items_priority_check
        CHECK (priority IN ('urgent', 'high', 'medium', 'low')),
    CONSTRAINT action_items_status_check
        CHECK (status IN ('pending', 'in_progress', 'completed', 'cancelled'))
);

-- Indexes
CREATE INDEX idx_action_items_tenant ON action_items(tenant_id);
CREATE INDEX idx_action_items_status ON action_items(tenant_id, status);
CREATE INDEX idx_action_items_assigned ON action_items(tenant_id, assigned_to_user_id);
CREATE INDEX idx_action_items_due_date ON action_items(tenant_id, due_date);
CREATE INDEX idx_action_items_client ON action_items(tenant_id, client_id);
CREATE INDEX idx_action_items_insight ON action_items(source_insight_id);

-- RLS
ALTER TABLE action_items ENABLE ROW LEVEL SECURITY;
```

---

## UI/UX Specifications

### Action Items Page Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  Action Items                                    [+ New Item]       │
├─────────────────────────────────────────────────────────────────────┤
│  [My Items] [All Team]              [Status ▼] [Priority ▼] [🔍]   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  OVERDUE (2)                                                  ── ─  │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 🔴 Follow up ABC Corp receivables           Due: Jan 10 ❗  │   │
│  │    ABC Corp  •  Assigned: You  •  From insight             │   │
│  │                                    [Start] [Complete] [···]│   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  THIS WEEK (3)                                                ── ─  │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 🟡 Review XYZ GST registration              Due: Jan 15     │   │
│  │    XYZ Services  •  Assigned: Sarah  •  From insight       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  LATER                                                        ── ─  │
│  ...                                                                │
└─────────────────────────────────────────────────────────────────────┘
```

### Priority Colors

| Priority | Color | Use Case |
|----------|-------|----------|
| Urgent | Red (`red-500`) | Do today |
| High | Orange (`orange-500`) | This week |
| Medium | Blue (`blue-500`) | This month |
| Low | Gray (`gray-400`) | When possible |

### Status Flow

```
pending → in_progress → completed
    ↓                       ↑
    └───────────────────────┘ (can skip in_progress)

    └──→ cancelled (from any state)
```

---

## Testing Strategy

### Backend Tests

1. **Unit Tests**
   - ActionItemService CRUD operations
   - Status transitions
   - Filter logic

2. **Integration Tests**
   - API endpoints
   - Convert insight to action
   - RLS enforcement

### Frontend Tests

1. **Component Tests**
   - ActionItemCard renders correctly
   - Filter controls work
   - Modal submit/cancel

2. **E2E Tests** (optional)
   - Create action from insight flow
   - Complete action flow

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Scope creep into full project management | Keep features minimal, defer advanced features |
| Team assignment complexity | Start with simple dropdown, no notifications |
| Performance with many items | Pagination, default filters (exclude completed) |

---

## Out of Scope (Future)

- Email notifications
- Recurring action items
- Action item templates
- Bulk operations
- Calendar integration
- Comments/activity log
- Time tracking
