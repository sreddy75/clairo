# API Contract: GET /clients/{client_id}/reconciliation-status

**Changed in**: 063-bas-compliance-xero-figures  
**Endpoint**: `GET /api/v1/clients/{client_id}/reconciliation-status`

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `start_date` | string (YYYY-MM-DD) | Yes | BAS period start |
| `end_date` | string (YYYY-MM-DD) | Yes | BAS period end |

## Response (updated)

```json
{
  "unreconciled_count": 116,
  "total_transactions": 247,
  "balance_discrepancy": 9100.00,
  "as_of": "2026-04-29T03:45:12.000Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `unreconciled_count` | integer | Number of bank transactions not reconciled in Xero for the period |
| `total_transactions` | integer | Total AUTHORISED bank transactions in the period |
| `balance_discrepancy` | number (decimal) | Sum of sub_total amounts for unreconciled transactions (absolute value). 0 if all reconciled. |
| `as_of` | string (ISO 8601) | Timestamp of the status check |

## Breaking change?

No. `balance_discrepancy` is an additive new field. Existing consumers that ignore unknown fields are unaffected.

## Frontend usage

Trigger conditions for the unreconciled warning:
- `unreconciled_count > 0` → show warning
- `balance_discrepancy > 0` (even if `unreconciled_count === 0`) → show warning
- `balance_discrepancy > 0 && balance_discrepancy < 1` → add "This may be a rounding difference" note
