# API Contract: Suggestion Notes

Base path: `/api/v1/clients/{connection_id}/bas/sessions/{session_id}/tax-code-suggestions/{suggestion_id}`

## PUT /note

Save or update a note on a suggestion. Upsert semantics — creates if no note exists, replaces if one does.

**Request**:
```json
{
  "note_text": "Client confirmed this is a personal expense, not business-related.",
  "sync_to_xero": false
}
```

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `note_text` | string | Yes | 1–2,000 characters |
| `sync_to_xero` | boolean | No | Default: false. Only honored when Xero connection is active and source type supports History & Notes. |

**Response** (200):
```json
{
  "suggestion_id": "uuid",
  "note_text": "Client confirmed this is a personal expense, not business-related.",
  "note_updated_by": "uuid",
  "note_updated_by_name": "Jane Smith",
  "note_updated_at": "2026-04-10T12:00:00Z"
}
```

**Errors**:
- 404: Suggestion not found or not in this tenant
- 422: `note_text` exceeds 2,000 characters or is empty

## DELETE /note

Remove a note from a suggestion.

**Response** (204): No content

**Errors**:
- 404: Suggestion not found or has no note

