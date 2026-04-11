# API Contract: Xero BAS Cross-Check

Base path: `/api/v1/clients/{connection_id}/bas/sessions/{session_id}`

## GET /xero-crosscheck

Fetch BAS report data from Xero for the session's period and return a comparison with Clairo's calculated figures.

**Query Parameters**: None (period is derived from the session).

**Response** (200):
```json
{
  "xero_report_found": true,
  "xero_figures": {
    "label_1a_gst_on_sales": 12345.67,
    "label_1b_gst_on_purchases": 5678.90,
    "net_gst": 6666.77
  },
  "clairo_figures": {
    "label_1a_gst_on_sales": 12345.67,
    "label_1b_gst_on_purchases": 5680.00,
    "net_gst": 6665.67
  },
  "differences": {
    "label_1b_gst_on_purchases": {
      "xero": 5678.90,
      "clairo": 5680.00,
      "delta": -1.10,
      "material": true
    }
  },
  "period_label": "Q3 2025-26",
  "fetched_at": "2026-04-10T12:00:00Z"
}
```

When no Xero report exists:
```json
{
  "xero_report_found": false,
  "xero_figures": null,
  "clairo_figures": {
    "label_1a_gst_on_sales": 12345.67,
    "label_1b_gst_on_purchases": 5680.00,
    "net_gst": 6665.67
  },
  "differences": null,
  "period_label": "Q3 2025-26",
  "fetched_at": "2026-04-10T12:00:00Z"
}
```

**Errors**:
- 404: Session not found or not in this tenant
- 503: Xero API unavailable (returns partial response with `xero_report_found: null` and error message in `xero_error` field instead of 503 — graceful degradation)

**Graceful degradation response** (200 with error context):
```json
{
  "xero_report_found": null,
  "xero_figures": null,
  "clairo_figures": { "..." },
  "differences": null,
  "xero_error": "Xero connection expired. Please reconnect.",
  "period_label": "Q3 2025-26",
  "fetched_at": "2026-04-10T12:00:00Z"
}
```

**Material difference threshold**: >$1 absolute difference on any compared field.
