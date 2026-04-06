# API Contract Changes: Tax Planning Intelligence

**Date**: 2026-04-06

## No New Endpoints

All improvements enrich the data returned by existing endpoints. No new API routes needed.

## Enriched Response: POST /api/v1/tax-plans/{id}/pull-financials

The `financials_data` field in the response gains new optional keys:

| New Field | Type | When Present |
|-----------|------|-------------|
| `projection` | object | When ≥3 months of YTD data available |
| `prior_year_ytd` | object | When prior year Xero data exists |
| `prior_years` | array | When any prior FY data exists in Xero |
| `strategy_context` | object | Always (derived from existing financials + bank) |
| `payroll_summary` | object | When Xero connection has payroll access and data |

### Breaking Changes: None

- `total_bank_balance` changes from `0` to `null` when no bank data — frontend already handles null
- `months_data_available` changes from hardcoded `12` to actual months — no consumers depend on exact value
- `is_annualised` changes from hardcoded `false` to `true` when projection is used — informational only

All new fields are optional (nullable). Existing clients that don't read them are unaffected.
