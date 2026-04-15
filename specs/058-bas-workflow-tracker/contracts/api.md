# API Contracts: 058-bas-workflow-tracker

**Branch**: `058-bas-workflow-tracker`  
**Date**: 2026-04-15  
**Base path**: `/api/v1`

---

## Practice Clients

### POST /clients/manual

Create a non-Xero client manually.

**Request**:
```json
{
  "name": "Smith & Co Pty Ltd",
  "abn": "12345678901",
  "accounting_software": "quickbooks",
  "assigned_user_id": "uuid-of-practice-user",
  "notes": "Client does the bookkeeping"
}
```

**Fields**:
- `name` (string, required, 1-255 chars)
- `abn` (string, optional, 11 digits)
- `accounting_software` (enum: quickbooks | myob | email | other, required)
- `assigned_user_id` (UUID, optional)
- `notes` (string, optional, max 5000 chars)

**Response** (201):
```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "name": "Smith & Co Pty Ltd",
  "abn": "12345678901",
  "accounting_software": "quickbooks",
  "xero_connection_id": null,
  "assigned_user_id": "uuid",
  "assigned_user_name": "Pawan",
  "notes": "Client does the bookkeeping",
  "notes_updated_at": "2026-04-15T10:00:00Z",
  "notes_updated_by_name": "Vik",
  "manual_status": "not_started",
  "created_at": "2026-04-15T10:00:00Z"
}
```

---

### PATCH /clients/{client_id}/assign

Assign or reassign a team member to a client.

**Request**:
```json
{
  "assigned_user_id": "uuid-of-practice-user"
}
```

Set `assigned_user_id` to `null` to unassign.

**Response** (200):
```json
{
  "id": "uuid",
  "assigned_user_id": "uuid",
  "assigned_user_name": "Pawan"
}
```

---

### POST /clients/bulk-assign

Bulk reassign multiple clients to a team member.

**Request**:
```json
{
  "client_ids": ["uuid-1", "uuid-2", "uuid-3"],
  "assigned_user_id": "uuid-of-practice-user"
}
```

**Fields**:
- `client_ids` (array of UUIDs, required, 1-100 items)
- `assigned_user_id` (UUID, required; use `null` to unassign all)

**Response** (200):
```json
{
  "updated_count": 3,
  "clients": [
    { "id": "uuid-1", "assigned_user_id": "uuid", "assigned_user_name": "Pawan" },
    { "id": "uuid-2", "assigned_user_id": "uuid", "assigned_user_name": "Pawan" },
    { "id": "uuid-3", "assigned_user_id": "uuid", "assigned_user_name": "Pawan" }
  ]
}
```

---

### PATCH /clients/{client_id}/notes

Update persistent client notes.

**Request**:
```json
{
  "notes": "Client does the bookkeeping, usually sends on the last day"
}
```

**Fields**:
- `notes` (string, required, max 5000 chars; send empty string to clear)

**Response** (200):
```json
{
  "id": "uuid",
  "notes": "Client does the bookkeeping, usually sends on the last day",
  "notes_updated_at": "2026-04-15T10:00:00Z",
  "notes_updated_by_name": "Aarti"
}
```

---

### GET /clients/{client_id}/notes/history

Get note change history for a client.

**Response** (200):
```json
{
  "history": [
    {
      "note_text": "Client does the bookkeeping, usually sends on the last day",
      "edited_by_name": "Aarti",
      "edited_at": "2026-04-15T10:00:00Z"
    },
    {
      "note_text": "Client does the bookkeeping",
      "edited_by_name": "Vik",
      "edited_at": "2026-03-01T09:00:00Z"
    }
  ]
}
```

---

### PATCH /clients/{client_id}/manual-status

Update BAS status for non-Xero clients (manual progression).

**Request**:
```json
{
  "manual_status": "in_progress"
}
```

**Fields**:
- `manual_status` (enum: not_started | in_progress | completed | lodged, required)

**Response** (200):
```json
{
  "id": "uuid",
  "manual_status": "in_progress"
}
```

**Error** (400): If client has a Xero connection (auto-derived status cannot be overridden manually).

---

## Quarter Exclusions

### POST /clients/{client_id}/exclusions

Exclude a client from a quarter.

**Request**:
```json
{
  "quarter": 3,
  "fy_year": "2025-26",
  "reason": "dormant",
  "reason_detail": null
}
```

**Fields**:
- `quarter` (int, 1-4, required)
- `fy_year` (string, required, format "YYYY-YY")
- `reason` (enum: dormant | lodged_externally | gst_cancelled | left_practice | other, optional)
- `reason_detail` (string, optional, max 500 chars; relevant when reason = "other")

**Response** (201):
```json
{
  "id": "uuid",
  "client_id": "uuid",
  "quarter": 3,
  "fy_year": "2025-26",
  "reason": "dormant",
  "excluded_by_name": "Vik",
  "excluded_at": "2026-04-15T10:00:00Z"
}
```

**Error** (409): If client is already excluded for that quarter.

---

### DELETE /clients/{client_id}/exclusions/{exclusion_id}

Reverse (soft-delete) a quarter exclusion.

**Response** (200):
```json
{
  "id": "uuid",
  "reversed_at": "2026-04-15T11:00:00Z",
  "reversed_by_name": "Vik"
}
```

---

## Dashboard (Modified Endpoints)

### GET /dashboard/summary

**New query params**:
- `assigned_user_id` (UUID, optional) — filter summary to a specific team member's clients

**Response changes** — new fields in response:
```json
{
  "total_clients": 280,
  "active_clients": 240,
  "excluded_count": 40,
  "team_members": [
    { "id": "uuid", "name": "Pawan", "client_count": 70 },
    { "id": "uuid", "name": "Aarti", "client_count": 65 },
    { "id": "uuid", "name": "Anil", "client_count": 55 },
    { "id": null, "name": "Unassigned", "client_count": 50 }
  ],
  "status_counts": { "ready": 45, "needs_review": 80, "no_activity": 75, "missing_data": 40 },
  "...existing fields..."
}
```

---

### GET /dashboard/clients

**New query params**:
- `assigned_user_id` (UUID, optional) — filter by team member; "me" as special value for current user
- `show_excluded` (boolean, default false) — when true, show only excluded clients instead of active
- `software` (string, optional) — filter by accounting_software enum value

**Response changes** — `ClientPortfolioItem` gains new fields:
```json
{
  "id": "uuid",
  "organization_name": "OreScope Surveying Pty Ltd",
  "assigned_user_id": "uuid",
  "assigned_user_name": "Pawan",
  "accounting_software": "xero",
  "has_xero_connection": true,
  "notes_preview": "Client does the bookkeeping...",
  "unreconciled_count": 12,
  "exclusion": null,
  "manual_status": null,
  "...existing financial fields...",
  "bas_status": "needs_review"
}
```

When `show_excluded=true`, `exclusion` is populated:
```json
{
  "exclusion": {
    "id": "uuid",
    "reason": "dormant",
    "excluded_by_name": "Vik",
    "excluded_at": "2026-04-15T10:00:00Z"
  }
}
```

---

### GET /auth/users

**Response changes** — add `display_name` to `PracticeUserResponse`:
```json
{
  "id": "uuid",
  "email": "pawan@firm.com.au",
  "display_name": "Pawan",
  "role": "accountant",
  "...existing fields..."
}
```
