# API Contract: Reject Endpoint Deprecation

## POST /{connection_id}/bas/sessions/{session_id}/tax-code-suggestions/{suggestion_id}/reject

**Status**: Deprecated (backward-compatible)

**Behavior change**: Internally maps to the dismiss action. Sets `status = "dismissed"` instead of `status = "rejected"`. The optional `reason` field is written to `note_text` (the unified notes field).

**Request** (unchanged):
```json
{
  "reason": "Optional reason text"
}
```

**Response** (unchanged schema — 200):
```json
{
  "id": "uuid",
  "status": "dismissed",
  "resolved_by": "uuid",
  "resolved_at": "2026-04-10T12:00:00Z"
}
```

**Note**: The response now returns `"status": "dismissed"` instead of `"status": "rejected"`. This is the only observable change for API consumers.

## Frontend Changes

- `rejectSuggestion()` function in `lib/bas.ts`: Removed (no longer called from UI)
- `handleReject()` in `TaxCodeResolutionPanel.tsx`: Removed
- `onReject` prop on `TaxCodeSuggestionCard`, `TransactionLineItemGroup`, `SuggestionTable`: Removed
- Status display: Both `rejected` and `dismissed` render as "Dismissed" with the same styling
