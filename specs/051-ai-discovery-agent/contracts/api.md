# API Contracts: AI Discovery Agent

**Branch**: `051-ai-discovery-agent` | **Date**: 2026-04-04

## Route Prefix: `/api/v1/discovery`

### Auth Routes (Public — no auth required)

#### POST /api/v1/discovery/auth/request-code
Request a login code via email (for returning contacts).

**Request**:
```json
{ "email": "john@smithco.com.au" }
```

**Response 200**:
```json
{ "message": "Verification code sent", "expires_in_seconds": 600 }
```

**Response 404**: Contact not found (not yet invited)

---

#### POST /api/v1/discovery/auth/verify
Verify email code or magic link token. Returns JWT session.

**Request**:
```json
{ "token": "abc123..." }
```

**Response 200**:
```json
{
  "access_token": "eyJ...",
  "refresh_token": "xyz...",
  "access_expires_at": "2026-04-04T15:30:00Z",
  "refresh_expires_at": "2026-05-04T15:15:00Z",
  "contact": {
    "id": "uuid",
    "email": "john@smithco.com.au",
    "name": "John Smith",
    "practice_name": "Smith & Co"
  }
}
```

---

#### POST /api/v1/discovery/auth/refresh
Refresh access token.

**Request**:
```json
{ "refresh_token": "xyz..." }
```

**Response 200**: Same shape as verify response (new access_token).

---

### Contact-Facing Routes (Requires `CurrentDiscoveryContact` auth)

#### GET /api/v1/discovery/sessions
List all sessions for the authenticated contact.

**Response 200**:
```json
{
  "items": [
    {
      "id": "uuid",
      "started_at": "2026-04-04T10:00:00Z",
      "ended_at": "2026-04-04T10:45:00Z",
      "message_count": 23,
      "session_summary": "Discussed Uber driver workflow..."
    }
  ]
}
```

---

#### POST /api/v1/discovery/sessions
Start a new chat session.

**Response 201**:
```json
{
  "id": "uuid",
  "started_at": "2026-04-04T10:00:00Z",
  "greeting": "Welcome back, John! Last time we were discussing..."
}
```

---

#### GET /api/v1/discovery/sessions/{session_id}/messages
List messages for a session.

**Query params**: `limit` (default 50), `before` (cursor)

**Response 200**:
```json
{
  "items": [
    {
      "id": "uuid",
      "role": "assistant",
      "content": "Can you tell me about...",
      "a2ui_message": null,
      "created_at": "2026-04-04T10:01:00Z"
    }
  ]
}
```

---

#### POST /api/v1/discovery/sessions/{session_id}/chat/stream
Send a message and stream the agent's response. SSE endpoint.

**Request**: `multipart/form-data`
- `message` (string, required) — User's message
- `file` (file, optional) — Attachment (max 25MB)

**Response**: `text/event-stream`

**SSE Event Types**:
```
data: {"type": "thinking", "content": "Analysing your workflow..."}
data: {"type": "content", "content": "That's really helpful..."}
data: {"type": "extraction", "extraction": {"type": "workflow_step", "content": {...}, "id": "uuid"}}
data: {"type": "a2ui", "a2ui_message": {...}}
data: {"type": "done", "session_id": "uuid"}
data: {"type": "error", "error": "Something went wrong"}
```

**New event types for discovery**:
- `extraction` — Agent extracted structured data, frontend renders accept/modify/reject UI
- `a2ui` — Agent wants to render a dynamic component (file upload, workflow builder, etc.)

---

#### POST /api/v1/discovery/sessions/{session_id}/extractions/{extraction_id}/feedback
Submit feedback on an extraction.

**Request**:
```json
{
  "feedback": "accepted",
  "modified_content": null
}
```

Or:
```json
{
  "feedback": "modified",
  "modified_content": { "step_name": "Download bank CSV", "time_minutes": 5 }
}
```

**Response 200**: Updated extraction.

---

#### POST /api/v1/discovery/sessions/{session_id}/artifacts/upload
Upload an artifact outside of chat stream (e.g., from A2UI file upload component).

**Request**: `multipart/form-data`
- `file` (file, required)
- `workflow_id` (string, optional)

**Response 201**:
```json
{
  "id": "uuid",
  "filename": "bank_statement_template.csv",
  "media_type": "text/csv",
  "size_bytes": 2048,
  "analysis_result": {
    "columns": ["Date", "Description", "Debit", "Credit", "Balance"],
    "row_count": 150,
    "preview_rows": [...]
  }
}
```

---

#### POST /api/v1/discovery/sessions/{session_id}/end
End a session. Triggers state update and summary generation.

**Response 200**:
```json
{
  "session_summary": "In this session, we covered...",
  "workflows_updated": ["Uber Driver BAS Preparation"],
  "completeness_delta": { "uber-driver-bas": 0.15 }
}
```

---

### Admin Routes (Requires Clerk auth + tenant permission)

Prefix: `/api/v1/admin/discovery`

#### POST /api/v1/admin/discovery/contacts/invite
Invite an accountant.

**Request**:
```json
{
  "email": "john@smithco.com.au",
  "name": "John Smith",
  "practice_name": "Smith & Co"
}
```

**Response 201**: Created contact with invitation sent status.

---

#### GET /api/v1/admin/discovery/contacts
List all discovery contacts invited by the current tenant.

**Response 200**:
```json
{
  "items": [
    {
      "id": "uuid",
      "email": "john@smithco.com.au",
      "name": "John Smith",
      "practice_name": "Smith & Co",
      "session_count": 4,
      "last_active_at": "2026-04-03T14:00:00Z",
      "overall_completeness": 0.65,
      "workflows": ["Uber Driver BAS", "Cash Business Reconciliation"]
    }
  ]
}
```

---

#### GET /api/v1/admin/discovery/contacts/{contact_id}
Detailed contact view with sessions, workflows, artifacts.

---

#### GET /api/v1/admin/discovery/workflows
List all discovered workflow types with aggregation data.

**Response 200**:
```json
{
  "items": [
    {
      "id": "uuid",
      "name": "Uber Driver BAS Preparation",
      "contributor_count": 3,
      "completeness_score": 0.85,
      "data_inputs": { "items": [...], "confirmed_by": 3 },
      "pain_points": { "items": [...], "top_pain": "Manual categorisation" },
      "total_client_volume": 85,
      "artifact_count": 5
    }
  ]
}
```

---

#### GET /api/v1/admin/discovery/workflows/{workflow_id}
Full workflow detail with cross-accountant aggregation.

---

#### POST /api/v1/admin/discovery/workflows/{workflow_id}/link
Link a contact's workflow contribution to an existing workflow type.

**Request**:
```json
{ "contact_id": "uuid", "source_workflow_id": "uuid" }
```

---

#### GET /api/v1/admin/discovery/coverage-matrix
Coverage matrix: topics vs contacts.

**Response 200**:
```json
{
  "topics": ["data_inputs", "process_steps", "outputs", "pain_points", "volume", "edge_cases"],
  "contacts": [
    { "id": "uuid", "name": "John Smith" },
    { "id": "uuid", "name": "Sarah Lee" }
  ],
  "matrix": {
    "data_inputs": { "uuid1": "complete", "uuid2": "partial" },
    "process_steps": { "uuid1": "complete", "uuid2": "not_started" }
  }
}
```

---

#### GET /api/v1/admin/discovery/sessions/{session_id}/transcript
Full transcript for a session.
