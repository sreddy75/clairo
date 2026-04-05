# API Contracts: Beta Legal & Compliance

**Branch**: `052-beta-legal-compliance` | **Date**: 2026-04-05

## Modified Endpoints

### GET /api/v1/auth/bootstrap (existing — extend response)

Add `tos_accepted_at` and `tos_version_accepted` to the bootstrap response so the frontend can gate access.

**Response 200** (new fields added):
```json
{
  "user": {
    "id": "uuid",
    "email": "john@smithco.com.au",
    "tos_accepted_at": "2026-04-05T10:00:00Z",
    "tos_version_accepted": "1.0"
  },
  "features": { ... },
  "trial": { ... }
}
```

When `tos_accepted_at` is `null` or `tos_version_accepted` does not match the current version, the frontend redirects to `/accept-terms`.

---

## New Endpoints

### POST /api/v1/auth/accept-terms

Accept the current Terms of Service. Requires Clerk authentication.

**Request**:
```json
{
  "version": "1.0"
}
```

**Response 200**:
```json
{
  "tos_accepted_at": "2026-04-05T10:00:00Z",
  "tos_version_accepted": "1.0"
}
```

**Response 400**: Version mismatch (client sent stale version).

**Side effects**: Creates an audit event `user.tos.accepted`.

---

### GET /api/v1/auth/tos-version

Get the current ToS version. Public endpoint (no auth required).

**Response 200**:
```json
{
  "version": "1.0",
  "effective_date": "2026-04-01"
}
```

---

### GET /api/v1/admin/audit

List audit events for the current tenant. Requires Clerk auth + admin role.

**Query params**:

| Param | Type | Default | Description |
|---|---|---|---|
| `page` | int | 1 | Page number |
| `per_page` | int | 50 | Items per page (max 100) |
| `event_type` | string | — | Filter by event type prefix (e.g., `ai.tax_planning`) |
| `event_category` | string | — | Filter by category (`auth`, `data`, `compliance`, `integration`) |
| `actor_id` | UUID | — | Filter by actor |
| `date_from` | ISO 8601 | — | Start of date range |
| `date_to` | ISO 8601 | — | End of date range |
| `resource_type` | string | — | Filter by resource type |

**Response 200**:
```json
{
  "items": [
    {
      "id": "uuid",
      "occurred_at": "2026-04-05T10:00:00Z",
      "event_type": "ai.tax_planning.chat",
      "event_category": "data",
      "actor_email": "jo***@smithco.com.au",
      "resource_type": "tax_plan",
      "resource_id": "uuid",
      "action": "create",
      "outcome": "success",
      "metadata": {
        "model": "claude-sonnet-4-20250514",
        "input_tokens": 1200,
        "output_tokens": 800
      }
    }
  ],
  "total": 1234,
  "page": 1,
  "per_page": 50,
  "pages": 25
}
```

---

### GET /api/v1/admin/audit/export

Export audit events as CSV. Same query params as the list endpoint (except pagination). Streams the response.

**Query params**: Same as GET /api/v1/admin/audit (minus `page`, `per_page`). Adds:

| Param | Type | Default | Description |
|---|---|---|---|
| `max_rows` | int | 50000 | Maximum rows to export |

**Response 200**: `Content-Type: text/csv`, `Content-Disposition: attachment; filename="audit_log_2026-04-05.csv"`

CSV columns: `occurred_at, event_type, event_category, actor_email, resource_type, resource_id, action, outcome, metadata`

---

### GET /api/v1/admin/audit/summary

Summary statistics for the audit log. Requires Clerk auth + admin role.

**Query params**: `date_from`, `date_to` (defaults to last 30 days)

**Response 200**:
```json
{
  "total_events": 5432,
  "by_category": {
    "auth": 1200,
    "data": 3100,
    "compliance": 800,
    "integration": 332
  },
  "by_event_type": {
    "ai.tax_planning.chat": 450,
    "ai.bas.classification": 1200,
    "ai.suggestion.approved": 890
  },
  "ai_suggestions": {
    "total": 2100,
    "approved": 890,
    "modified": 340,
    "rejected": 120,
    "pending": 750
  }
}
```
