# Data Model: Spec 047 — Client Transaction Classification

## New Entities

### ClassificationRequest

Represents an accountant's request for a client to classify unresolved transactions. Links a BAS session to a portal invitation.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | `UUID` | PK | Auto-generated |
| `tenant_id` | `UUID` | NOT NULL | FK `tenants.id`, indexed |
| `connection_id` | `UUID` | NOT NULL | FK `xero_connections.id`, indexed |
| `session_id` | `UUID` | NOT NULL | FK `bas_sessions.id` |
| `invitation_id` | `UUID` | NULL | FK `portal_invitations.id` — set when magic link is created |
| `requested_by` | `UUID` | NOT NULL | FK `practice_users.id` — the accountant |
| `client_email` | `String(255)` | NOT NULL | Email sent to (from XeroClient or manually entered) |
| `message` | `Text` | NULL | Optional message from accountant to client |
| `status` | `String(20)` | NOT NULL | See state transitions below |
| `transaction_count` | `Integer` | NOT NULL | Number of transactions included |
| `classified_count` | `Integer` | NOT NULL | Default 0 — how many client has classified |
| `submitted_at` | `DateTime(tz)` | NULL | When client submitted their classifications |
| `reviewed_at` | `DateTime(tz)` | NULL | When accountant finished reviewing |
| `reviewed_by` | `UUID` | NULL | FK `practice_users.id` |
| `expires_at` | `DateTime(tz)` | NOT NULL | Magic link expiry (default: 7 days) |
| `created_at` | `DateTime(tz)` | NOT NULL | From TimestampMixin |
| `updated_at` | `DateTime(tz)` | NOT NULL | From TimestampMixin |

**Indexes**:
- `ix_classification_request_tenant` on `(tenant_id)`
- `ix_classification_request_session` on `(session_id)`
- `ix_classification_request_connection_status` on `(connection_id, status)`

**Unique constraint**: `uq_classification_request_session` on `(session_id)` — one active request per BAS session.

#### Status State Transitions

```
DRAFT → SENT → VIEWED → IN_PROGRESS → SUBMITTED → REVIEWING → COMPLETED
  │                                                                │
  └──────────────────── CANCELLED ←────────────────────────────────┘
  └──────────────────── EXPIRED (automatic if link expires)
```

| Status | Meaning |
|--------|---------|
| `DRAFT` | Request created but magic link not yet sent |
| `SENT` | Magic link emailed to client |
| `VIEWED` | Client clicked the link (session created) |
| `IN_PROGRESS` | Client has saved at least one classification |
| `SUBMITTED` | Client clicked "Submit" |
| `REVIEWING` | Accountant is reviewing client classifications |
| `COMPLETED` | Accountant approved/resolved all classifications |
| `CANCELLED` | Accountant cancelled the request |
| `EXPIRED` | Magic link expired without submission |

### ClientClassification

Per-transaction classification from the client. One record per transaction per request.

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | `UUID` | PK | Auto-generated |
| `tenant_id` | `UUID` | NOT NULL | FK `tenants.id`, indexed |
| `request_id` | `UUID` | NOT NULL | FK `classification_requests.id`, CASCADE |
| `source_type` | `String(20)` | NOT NULL | "invoice" / "bank_transaction" / "credit_note" |
| `source_id` | `UUID` | NOT NULL | Reference to source entity |
| `line_item_index` | `Integer` | NOT NULL | Position in JSONB line_items array |
| `transaction_date` | `Date` | NOT NULL | Denormalized snapshot |
| `line_amount` | `Numeric(15,2)` | NOT NULL | Denormalized snapshot |
| `description` | `Text` | NULL | Bank/payee description (denormalized snapshot) |
| `contact_name` | `String(255)` | NULL | Denormalized snapshot |
| `account_code` | `String(10)` | NULL | Denormalized snapshot |
| `client_category` | `String(50)` | NULL | Category ID from taxonomy (e.g. "office_supplies") |
| `client_description` | `Text` | NULL | Free-text description from client |
| `client_is_personal` | `Boolean` | NOT NULL | Default false — true if client marked "not business" |
| `client_needs_help` | `Boolean` | NOT NULL | Default false — true if client marked "I don't know" |
| `classified_at` | `DateTime(tz)` | NULL | When client provided their classification |
| `classified_by_session` | `UUID` | NULL | FK `portal_sessions.id` — which portal session |
| `ai_suggested_tax_type` | `String(50)` | NULL | AI's mapping after client input |
| `ai_confidence` | `Numeric(3,2)` | NULL | AI confidence score |
| `ai_mapped_at` | `DateTime(tz)` | NULL | When AI mapping was performed |
| `suggestion_id` | `UUID` | NULL | FK `tax_code_suggestions.id` — links to 046 suggestion |
| `accountant_action` | `String(20)` | NULL | approved / overridden / rejected |
| `accountant_user_id` | `UUID` | NULL | FK `practice_users.id` |
| `accountant_tax_type` | `String(50)` | NULL | Final tax type if overridden |
| `accountant_reason` | `Text` | NULL | Reason for override |
| `accountant_acted_at` | `DateTime(tz)` | NULL | Timestamp of accountant action |
| `receipt_required` | `Boolean` | NOT NULL | Default false — true if receipt/invoice is needed |
| `receipt_flag_source` | `String(20)` | NULL | "auto" (rule-based) or "manual" (accountant-flagged) |
| `receipt_flag_reason` | `String(255)` | NULL | Human-readable reason (e.g., "GST credit > $82.50") |
| `receipt_document_id` | `UUID` | NULL | FK `portal_documents.id` — attached receipt/invoice |
| `created_at` | `DateTime(tz)` | NOT NULL | From TimestampMixin |
| `updated_at` | `DateTime(tz)` | NOT NULL | From TimestampMixin |

**Indexes**:
- `ix_client_classification_request` on `(request_id)`
- `ix_client_classification_tenant` on `(tenant_id)`

**Unique constraint**: `uq_client_classification_request_source_line` on `(request_id, source_type, source_id, line_item_index)` — one classification per line item per request.

## Modified Entities

### TaxCodeSuggestion (Spec 046) — No Schema Change

The existing `confidence_tier` field (`String(20)`) gains a new value: `"client_classified"`. No migration needed — it's a string column, not an enum.

### BASAuditEventType (Spec 046) — New Values

Add to the existing string constants in `bas/models.py`:

```python
CLASSIFICATION_REQUEST_CREATED = "classification_request_created"
CLASSIFICATION_REQUEST_SENT = "classification_request_sent"
CLASSIFICATION_REQUEST_SUBMITTED = "classification_request_submitted"
CLASSIFICATION_REVIEWED = "classification_reviewed"
CLASSIFICATION_AI_MAPPED = "classification_ai_mapped"
```

## Entity Relationships

```
BASSession (1) ──── (0..1) ClassificationRequest
                              │
ClassificationRequest (1) ──── (N) ClientClassification
                              │
ClassificationRequest (0..1) ── (1) PortalInvitation
                              │
ClientClassification (0..1) ── (1) TaxCodeSuggestion
ClientClassification (0..1) ── (1) PortalDocument
ClientClassification (0..1) ── (1) PortalSession
```

## Migration

Single migration: `047_spec_047_client_transaction_classification.py`

Creates:
- `classification_requests` table
- `client_classifications` table
- All indexes and constraints listed above
