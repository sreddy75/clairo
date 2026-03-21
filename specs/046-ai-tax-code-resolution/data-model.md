# Data Model: AI Tax Code Resolution

**Branch**: `046-ai-tax-code-resolution` | **Date**: 2026-03-14

## New Entities

### TaxCodeSuggestion

Stores AI-generated tax code suggestions for excluded transaction line items within a BAS session.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | UUID | PK, default uuid4 | |
| `tenant_id` | UUID | FK tenants.id, NOT NULL, indexed | RLS |
| `session_id` | UUID | FK bas_sessions.id, NOT NULL, indexed | Scoped to BAS session |
| `source_type` | Enum | NOT NULL | `invoice`, `bank_transaction`, `credit_note` |
| `source_id` | UUID | NOT NULL, indexed | ID of XeroInvoice/XeroBankTransaction/XeroCreditNote |
| `line_item_index` | Integer | NOT NULL | Index into `line_items` JSONB array |
| `line_item_id` | String(50) | nullable | Xero LineItemID (for reference) |
| `original_tax_type` | String(50) | NOT NULL | Tax type from Xero (e.g., "NONE", "BASEXCLUDED") |
| `suggested_tax_type` | String(50) | nullable | AI-suggested tax type (null if no suggestion) |
| `applied_tax_type` | String(50) | nullable | Actually applied tax type (may differ from suggestion) |
| `confidence_score` | Decimal(3,2) | nullable | 0.00-1.00 |
| `confidence_tier` | Enum | nullable | `account_default`, `client_history`, `tenant_history`, `llm_classification`, `manual` |
| `suggestion_basis` | Text | nullable | Human-readable explanation of why this was suggested |
| `status` | Enum | NOT NULL, default 'pending' | `pending`, `approved`, `rejected`, `overridden`, `dismissed` |
| `resolved_by` | UUID | FK practice_users.id, nullable | User who resolved |
| `resolved_at` | DateTime(tz) | nullable | When resolved |
| `dismissal_reason` | Text | nullable | Reason if dismissed |
| `account_code` | String(10) | nullable | Account code from line item (denormalized for display) |
| `account_name` | String(255) | nullable | Account name (denormalized for display) |
| `description` | Text | nullable | Line item description (denormalized for display) |
| `line_amount` | Decimal(15,2) | nullable | Line item amount (denormalized for display) |
| `tax_amount` | Decimal(15,2) | nullable | Line item tax amount |
| `contact_name` | String(255) | nullable | Counterparty name (denormalized for display) |
| `transaction_date` | Date | nullable | Invoice issue_date or transaction_date |
| `created_at` | DateTime(tz) | NOT NULL, server_default now() | |
| `updated_at` | DateTime(tz) | NOT NULL, server_default now(), onupdate | |

**Indexes**:
- `ix_tax_code_suggestions_tenant_id` on `tenant_id`
- `ix_tax_code_suggestions_session_id` on `session_id`
- `ix_tax_code_suggestions_source` on `(source_type, source_id)`
- `uq_tax_code_suggestion_session_source_line` on `(session_id, source_type, source_id, line_item_index)` — idempotency constraint

**Enums**:
- `TaxCodeSuggestionSourceType`: `invoice`, `bank_transaction`, `credit_note`
- `TaxCodeSuggestionStatus`: `pending`, `approved`, `rejected`, `overridden`, `dismissed`
- `ConfidenceTier`: `account_default`, `client_history`, `tenant_history`, `llm_classification`, `manual`

### TaxCodeOverride

Tracks locally applied tax codes that differ from Xero, enabling conflict detection on re-sync.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | UUID | PK, default uuid4 | |
| `tenant_id` | UUID | FK tenants.id, NOT NULL, indexed | RLS |
| `connection_id` | UUID | FK xero_connections.id, NOT NULL, indexed | Xero connection |
| `source_type` | Enum | NOT NULL | `invoice`, `bank_transaction`, `credit_note` |
| `source_id` | UUID | NOT NULL | ID of the Xero entity |
| `line_item_index` | Integer | NOT NULL | Index into line_items array |
| `original_tax_type` | String(50) | NOT NULL | Tax type from Xero at time of override |
| `override_tax_type` | String(50) | NOT NULL | Tax type applied by accountant |
| `applied_by` | UUID | FK practice_users.id, NOT NULL | Who applied |
| `applied_at` | DateTime(tz) | NOT NULL | When applied |
| `suggestion_id` | UUID | FK tax_code_suggestions.id, nullable | Link to originating suggestion |
| `is_active` | Boolean | NOT NULL, default true | False when override is superseded |
| `conflict_detected` | Boolean | NOT NULL, default false | True when re-sync found different data |
| `xero_new_tax_type` | String(50) | nullable | Xero's new value when conflict detected |
| `conflict_resolved_at` | DateTime(tz) | nullable | |
| `created_at` | DateTime(tz) | NOT NULL, server_default now() | |
| `updated_at` | DateTime(tz) | NOT NULL, server_default now(), onupdate | |

**Indexes**:
- `ix_tax_code_overrides_tenant_id` on `tenant_id`
- `ix_tax_code_overrides_connection_id` on `connection_id`
- `uq_tax_code_override_active` on `(connection_id, source_type, source_id, line_item_index)` WHERE `is_active = true` — only one active override per line item

## Modified Entities

### GSTResult (in-memory, calculator.py)

Add field:
- `excluded_items: list[dict]` — collects line items excluded during calculation with their context (source_type, source_id, line_item_index, tax_type, amount, account_code, description)

### BASAuditEventType (enum, models.py)

Add values:
- `TAX_CODE_SUGGESTIONS_GENERATED` — suggestion engine completed
- `TAX_CODE_SUGGESTION_APPROVED` — single suggestion approved
- `TAX_CODE_SUGGESTION_REJECTED` — single suggestion rejected
- `TAX_CODE_SUGGESTION_OVERRIDDEN` — suggestion overridden with different code
- `TAX_CODE_TRANSACTION_DISMISSED` — transaction confirmed as excluded
- `TAX_CODE_BULK_APPROVED` — batch approval of high-confidence suggestions
- `TAX_CODE_CONFLICT_DETECTED` — re-sync conflict found
- `BAS_RECALCULATED_AFTER_RESOLUTION` — BAS recalculated post-resolution

## State Transitions

### TaxCodeSuggestion Status

```
pending ──→ approved     (accountant accepts AI suggestion)
       ──→ rejected      (accountant rejects, no alternative given)
       ──→ overridden    (accountant selects different tax code)
       ──→ dismissed     (accountant confirms exclusion is correct)
```

All transitions are terminal within a session. If re-generated (idempotent re-run), existing resolved suggestions are preserved; only new/changed items get new `pending` records.

### TaxCodeOverride Lifecycle

```
Created (is_active=true) ──→ Conflict detected (conflict_detected=true)
                         ──→ Superseded (is_active=false) [when Xero matches override]
                         ──→ Superseded (is_active=false) [when accountant resolves conflict]
```

## Entity Relationships

```
BASSession 1──* TaxCodeSuggestion   (session_id FK)
TaxCodeSuggestion 1──0..1 TaxCodeOverride   (suggestion_id FK)
XeroConnection 1──* TaxCodeOverride   (connection_id FK)
PracticeUser 1──* TaxCodeSuggestion   (resolved_by FK)
PracticeUser 1──* TaxCodeOverride   (applied_by FK)
```

## Denormalization Decisions

`TaxCodeSuggestion` denormalizes `account_code`, `account_name`, `description`, `line_amount`, `tax_amount`, `contact_name`, and `transaction_date` from the source transaction/invoice. This avoids expensive joins when listing suggestions in the UI (which needs to show all these fields). The denormalized data is populated once at suggestion creation time and is not updated on re-sync (the suggestion is a snapshot of what was excluded).
