# API Contracts: Spec 047 — Client Transaction Classification

## Accountant-Facing Endpoints (Clerk auth required)

All under prefix: `/api/v1/{connection_id}/bas/sessions/{session_id}/classification`

### 1. Create Classification Request

**`POST /api/v1/{connection_id}/bas/sessions/{session_id}/classification/request`**

Creates a request and sends the magic link email to the client.

**Request:**
```json
{
  "message": "Hi — please classify these transactions before Friday. Thanks!",
  "transaction_ids": null,
  "email_override": null,
  "manual_receipt_flags": [
    {"source_type": "bank_transaction", "source_id": "uuid", "line_item_index": 0, "reason": "Need invoice for this one"}
  ]
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `message` | `string` | No | Optional message to client (max 500 chars) |
| `transaction_ids` | `array[object]` | No | Subset of transactions to include. Null = all unresolved. Each: `{source_type, source_id, line_item_index}` |
| `email_override` | `string (email)` | No | Override client email if XeroClient.email is null |
| `manual_receipt_flags` | `array[object]` | No | Transactions the accountant wants receipts for. Each: `{source_type, source_id, line_item_index, reason?}`. Added on top of auto-flags. |

**Response (201):**
```json
{
  "id": "uuid",
  "status": "sent",
  "client_email": "owner@business.com.au",
  "transaction_count": 12,
  "magic_link_sent": true,
  "expires_at": "2026-03-22T10:30:00+11:00",
  "created_at": "2026-03-15T10:30:00+11:00"
}
```

**Error (400):** `{"error": "no_unresolved_transactions"}` — No transactions to classify.
**Error (400):** `{"error": "no_client_email"}` — No email on XeroClient and no `email_override` provided.
**Error (409):** `{"error": "request_already_exists"}` — Active request already exists for this session.

### 2. Get Classification Request Status

**`GET /api/v1/{connection_id}/bas/sessions/{session_id}/classification/request`**

**Response (200):**
```json
{
  "id": "uuid",
  "status": "in_progress",
  "client_email": "owner@business.com.au",
  "message": "Please classify these before Friday.",
  "transaction_count": 12,
  "classified_count": 7,
  "submitted_at": null,
  "expires_at": "2026-03-22T10:30:00+11:00",
  "created_at": "2026-03-15T10:30:00+11:00"
}
```

**Error (404):** No classification request exists for this session.

### 3. Cancel Classification Request

**`POST /api/v1/{connection_id}/bas/sessions/{session_id}/classification/request/cancel`**

**Response (200):**
```json
{
  "id": "uuid",
  "status": "cancelled"
}
```

### 4. Get Classifications for Review

**`GET /api/v1/{connection_id}/bas/sessions/{session_id}/classification/review`**

Returns all client classifications with AI mappings. Triggers AI mapping on first access if not yet done.

**Query params:**
- `filter`: `all` | `needs_attention` | `auto_mappable` (default: `all`)

**Response (200):**
```json
{
  "request_id": "uuid",
  "request_status": "submitted",
  "classifications": [
    {
      "id": "uuid",
      "source_type": "bank_transaction",
      "source_id": "uuid",
      "line_item_index": 0,
      "transaction_date": "2026-01-15",
      "line_amount": -245.50,
      "description": "OFFICEWORKS SYDNEY",
      "contact_name": null,
      "account_code": "400",
      "client_category": "office_supplies",
      "client_category_label": "Office supplies & stationery",
      "client_description": null,
      "client_is_personal": false,
      "client_needs_help": false,
      "classified_at": "2026-03-16T14:22:00+11:00",
      "ai_suggested_tax_type": "GST on Expenses",
      "ai_confidence": 0.92,
      "needs_attention": false,
      "receipt_required": true,
      "receipt_reason": "GST credit claim over $82.50",
      "receipt_attached": true,
      "receipt_document_id": "uuid",
      "suggestion_id": "uuid",
      "accountant_action": null
    },
    {
      "id": "uuid",
      "source_type": "bank_transaction",
      "source_id": "uuid",
      "line_item_index": 0,
      "transaction_date": "2026-02-03",
      "line_amount": -89.00,
      "description": "TRANSFER 0412345678",
      "contact_name": null,
      "account_code": "800",
      "client_category": null,
      "client_category_label": null,
      "client_description": "Paid a subcontractor for website work",
      "client_is_personal": false,
      "client_needs_help": false,
      "classified_at": "2026-03-16T14:25:00+11:00",
      "ai_suggested_tax_type": "GST on Expenses",
      "ai_confidence": 0.68,
      "needs_attention": true,
      "receipt_required": true,
      "receipt_reason": "Vague bank description",
      "receipt_attached": false,
      "receipt_document_id": null,
      "suggestion_id": "uuid",
      "accountant_action": null
    }
  ],
  "summary": {
    "total": 12,
    "classified_by_client": 10,
    "marked_personal": 1,
    "needs_help": 1,
    "auto_mappable": 7,
    "needs_attention": 3,
    "already_reviewed": 0,
    "receipts_required": 8,
    "receipts_attached": 5,
    "receipts_missing": 3
  }
}
```

`needs_attention` is true when: `ai_confidence < 0.7`, or `client_needs_help = true`, or `client_is_personal = true`.

### 5. Approve/Override Classification

**`POST /api/v1/{connection_id}/bas/sessions/{session_id}/classification/{classification_id}/resolve`**

**Request:**
```json
{
  "action": "approved",
  "tax_type": null,
  "reason": null
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `action` | `string` | Yes | `approved` / `overridden` / `rejected` |
| `tax_type` | `string` | If overridden | The tax type to apply instead |
| `reason` | `string` | If overridden | Reason for override |

**Response (200):**
```json
{
  "id": "uuid",
  "accountant_action": "approved",
  "final_tax_type": "GST on Expenses",
  "suggestion_id": "uuid"
}
```

### 6. Bulk Approve Classifications

**`POST /api/v1/{connection_id}/bas/sessions/{session_id}/classification/bulk-approve`**

**Request:**
```json
{
  "min_confidence": 0.80,
  "exclude_personal": true,
  "exclude_needs_help": true
}
```

**Response (200):**
```json
{
  "approved_count": 7,
  "skipped_count": 5
}
```

### 7. Export Audit Trail

**`GET /api/v1/{connection_id}/bas/sessions/{session_id}/classification/audit-export`**

**Query params:**
- `format`: `json` | `csv` (default: `json`)

**Response (200):** CSV or JSON with full audit chain per transaction.

---

## Client-Facing Endpoints (Portal magic link auth)

All under prefix: `/api/v1/client-portal/classify`

### 8. Get Classification Request (Client View)

**`GET /api/v1/client-portal/classify/{request_id}`**

Returns transactions the client needs to classify.

**Auth**: `CurrentPortalClient` dependency — validates `connection_id` matches.

**Response (200):**
```json
{
  "request_id": "uuid",
  "practice_name": "Smith & Associates",
  "message": "Please classify these before Friday.",
  "expires_at": "2026-03-22T10:30:00+11:00",
  "transactions": [
    {
      "id": "uuid",
      "transaction_date": "2026-01-15",
      "amount": -245.50,
      "description": "OFFICEWORKS SYDNEY",
      "hint": "This looks like it could be office supplies",
      "current_category": null,
      "current_description": null,
      "is_classified": false,
      "receipt_required": true,
      "receipt_reason": "GST credit claim over $82.50",
      "receipt_attached": false
    }
  ],
  "categories": [
    {
      "id": "office_supplies",
      "label": "Office supplies & stationery",
      "group": "expense"
    },
    {
      "id": "computer_it",
      "label": "Computer & IT equipment",
      "group": "expense"
    }
  ],
  "progress": {
    "total": 12,
    "classified": 0,
    "remaining": 12
  }
}
```

**Note**: Transaction amounts are shown but account codes, tax types, and Xero IDs are NOT exposed to the client.

### 9. Save Classification (Individual)

**`PUT /api/v1/client-portal/classify/{request_id}/transactions/{classification_id}`**

Auto-saves as client works through the list.

**Request:**
```json
{
  "category": "office_supplies",
  "description": null,
  "is_personal": false,
  "needs_help": false
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `category` | `string` | No | Category ID from taxonomy |
| `description` | `string` | No | Free-text description (max 500 chars) |
| `is_personal` | `boolean` | No | Mark as personal/not business |
| `needs_help` | `boolean` | No | Mark as "I don't know" |

At least one of `category`, `description`, `is_personal`, or `needs_help` must be provided.

**Response (200):**
```json
{
  "id": "uuid",
  "is_classified": true,
  "classified_at": "2026-03-16T14:22:00+11:00"
}
```

### 10. Submit Classifications

**`POST /api/v1/client-portal/classify/{request_id}/submit`**

Marks the request as submitted. Partial submissions accepted.

**Request:** (empty body)

**Response (200):**
```json
{
  "request_id": "uuid",
  "status": "submitted",
  "classified_count": 10,
  "total_count": 12,
  "submitted_at": "2026-03-16T14:30:00+11:00"
}
```

### 11. Upload Receipt (per transaction)

**`POST /api/v1/client-portal/classify/{request_id}/transactions/{classification_id}/receipt`**

Uses existing portal document upload infrastructure.

**Request:** `multipart/form-data` with `file` field.

**Response (200):**
```json
{
  "document_id": "uuid",
  "filename": "receipt-officeworks.jpg",
  "size": 245000
}
```
