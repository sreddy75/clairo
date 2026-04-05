# Data Model: Beta Legal & Compliance

**Branch**: `052-beta-legal-compliance` | **Date**: 2026-04-05

## Entity Relationship Diagram

```
User 1──N ToS Acceptance (new column on existing User model)
AuditLog (existing) ← extended with new AI event types (no schema change)
```

## Model Changes

### User (existing — add columns)

Add ToS tracking fields to the existing `User` model at `backend/app/modules/auth/models.py:415`.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| tos_accepted_at | TIMESTAMPTZ | NULLABLE | When the user accepted ToS |
| tos_version_accepted | VARCHAR(20) | NULLABLE | Version string (e.g., "1.0", "1.1") |
| tos_accepted_ip | INET | NULLABLE | IP address at time of acceptance |

**Migration**: Single Alembic migration adding 3 columns to `users` table. Existing users will have `NULL` values, triggering the ToS acceptance flow on next login.

**No new tables required** — the existing `audit_logs` table handles all new event types via its flexible JSONB `metadata` column.

## New Audit Event Types

These are logical event types logged to the existing `audit_logs` table. No schema changes needed.

### ToS Events

| Event Type | Category | Action | Data in `metadata` |
|---|---|---|---|
| `user.tos.accepted` | auth | create | `{version, ip_address}` |
| `user.tos.prompted` | auth | access | `{current_version, last_accepted_version}` |

### AI Suggestion Events

| Event Type | Category | Action | Data in `metadata` |
|---|---|---|---|
| `ai.tax_planning.chat` | data | create | `{model, input_tokens, output_tokens, plan_id, scenarios_count}` |
| `ai.tax_planning.analysis` | data | create | `{model, agent_role, input_tokens, output_tokens, plan_id}` |
| `ai.bas.classification` | data | create | `{model, transaction_id, suggested_code, confidence, tier}` |
| `ai.bas.client_classification` | data | create | `{model, transaction_id, classification_result}` |
| `ai.insights.analysis` | data | create | `{model, insight_type, input_tokens, output_tokens}` |
| `ai.insights.summary` | data | create | `{model, summary_length, input_tokens, output_tokens}` |

### Human Override Events

| Event Type | Category | Action | Data in `old_values` / `new_values` |
|---|---|---|---|
| `ai.suggestion.approved` | data | update | `old: {ai_value}`, `new: {approved_value}` |
| `ai.suggestion.modified` | data | update | `old: {ai_value}`, `new: {modified_value, reason}` |
| `ai.suggestion.rejected` | data | update | `old: {ai_value}`, `new: {replacement_value, reason}` |

## State Transitions

### ToS Acceptance
```
User.tos_accepted_at = NULL → User logs in → Redirected to /accept-terms
User accepts → tos_accepted_at = NOW(), tos_version_accepted = "1.0"
ToS version bumps to "1.1" → User logs in → tos_version_accepted != current → Redirected again
User re-accepts → tos_accepted_at = NOW(), tos_version_accepted = "1.1"
```

### Cookie Consent (client-side only)
```
localStorage.clairo_cookie_consent = null → Banner shown, no analytics
User clicks Accept → localStorage = {status: "accepted", timestamp, version}
User clicks Decline → localStorage = {status: "declined", timestamp, version}
```

## Notes

- **No new tables**: This feature adds 3 columns to an existing table and new event types to the existing audit log. The audit log's JSONB `metadata` column accommodates all new data without schema changes.
- **Cookie consent is client-side only**: No server-side storage needed. The consent state lives in localStorage and controls which scripts load in the browser.
- **Legal page content**: Stored as static files in the repository (MDX or TSX). No database storage needed.
