# Quickstart: Xero Tax Code Write-Back (049)

**Branch**: `049-xero-taxcode-sync`

---

## Prerequisites

- Branches 046 and 047 implemented and merged to `main`
- Local dev environment running (`docker-compose up -d`)
- Xero sandbox credentials configured in `.env`

---

## Environment Variables

Add to `.env` (no new vars required — writeback reuses existing Xero OAuth):

```bash
# Already required from Xero integration setup
XERO_CLIENT_ID=...
XERO_CLIENT_SECRET=...
XERO_REDIRECT_URI=...

# Ensure Celery is configured (used for writeback task)
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

---

## Database Migrations

Run all migrations in order:

```bash
cd backend
uv run alembic upgrade head
```

This applies 5 new migrations:
1. `xero_writeback_tables` — `xero_writeback_jobs`, `xero_writeback_items`
2. `tax_code_override_writeback_status` — adds `writeback_status` column
3. `classification_request_send_back` — adds `parent_request_id`, `round_number`; replaces unique constraint
4. `agent_transaction_notes` — new table
5. `client_classification_rounds` — new table

---

## Running the Feature Locally

### 1. Start all services

```bash
docker-compose up -d          # PostgreSQL, Redis, MinIO
cd backend && uv run uvicorn app.main:app --reload
cd backend && uv run celery -A app.tasks.celery_app worker -Q xero_writeback -l info
```

### 2. Create test data (seed)

```bash
cd backend && uv run python -m scripts.seed_049
```

This seeds:
- 1 tenant + Xero connection (sandbox)
- 1 BAS session with 5 approved TaxCodeOverride records
- 1 ClassificationRequest with 3 items (2 answered, 1 "I don't know")

### 3. Test writeback flow

```bash
# Via API (with auth token):
curl -X POST http://localhost:8000/api/v1/bas/sessions/{session_id}/writeback \
  -H "Authorization: Bearer $TOKEN"

# Poll for progress:
curl http://localhost:8000/api/v1/bas/sessions/{session_id}/writeback/jobs/{job_id} \
  -H "Authorization: Bearer $TOKEN"
```

### 4. Test classification send-back

```bash
# Send "I don't know" item back with agent comment:
curl -X POST http://localhost:8000/api/v1/bas/sessions/{session_id}/classification-requests/{request_id}/send-back \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {
        "classification_id": "{classification_id}",
        "agent_comment": "This was your business card — do you recall what it was for?"
      }
    ]
  }'
```

---

## Running Tests

```bash
cd backend

# All 049 tests:
uv run pytest tests/ -k "049 or writeback or send_back" -v

# Specific test groups:
uv run pytest tests/unit/modules/integrations/xero/test_writeback_service.py -v
uv run pytest tests/integration/api/test_writeback.py -v
uv run pytest tests/contract/adapters/test_xero_writeback_adapter.py -v
```

---

## Key Files

| File | Purpose |
|------|---------|
| `backend/app/modules/integrations/xero/writeback_models.py` | `XeroWritebackJob`, `XeroWritebackItem` SQLAlchemy models |
| `backend/app/modules/integrations/xero/writeback_service.py` | Initiate/retry logic, document grouping, pre-flight checks |
| `backend/app/modules/integrations/xero/writeback_repository.py` | DB access for writeback entities |
| `backend/app/modules/integrations/xero/writeback_schemas.py` | Pydantic request/response schemas |
| `backend/app/modules/integrations/xero/client.py` | Xero HTTP client — new `update_*` and `get_*` methods added |
| `backend/app/tasks/xero_writeback.py` | Celery task — processes writeback items sequentially |
| `backend/app/modules/bas/classification_models.py` | Extended with `AgentTransactionNote`, `ClientClassificationRound` |
| `backend/app/modules/bas/classification_service.py` | Extended with `send_items_back()`, send-back round logic |
| `frontend/src/app/bas/[sessionId]/_components/SyncToXeroButton.tsx` | Trigger writeback action |
| `frontend/src/app/bas/[sessionId]/_components/WritebackProgressPanel.tsx` | Live progress during sync |
| `frontend/src/app/bas/[sessionId]/_components/WritebackResultsSummary.tsx` | Post-sync results |
| `frontend/src/app/portal/classify/[token]/_components/ClassificationItem.tsx` | Updated for mandatory description + all-questions gate |

---

## Architecture Diagram

```
Tax Agent (browser)
  │
  │ POST /writeback ──────────────────────────────────────────────
  │                                                                │
  v                                                               v
BAS Router                                           Celery Worker
  │                                                    (xero_writeback queue)
  ├── validates session status                           │
  ├── calls XeroWritebackService.initiate_writeback()   │
  │     → creates XeroWritebackJob (pending)            │
  │     → enqueues process_writeback_job task ──────────┘
  │                                                       │
  └── returns {job_id, status: "pending"}                │
                                                          v
Tax Agent polls GET /writeback/jobs/{job_id}     process_writeback_job:
  ↑                                                │
  │ (every 2s)                                     ├─ Groups TaxCodeOverrides by Xero doc
  │                                                ├─ For each doc group:
  │                                                │   ├─ GET doc from Xero (pre-flight)
  │                                                │   ├─ Check editability
  │                                                │   ├─ Reconstruct line_items payload
  │                                                │   ├─ POST to Xero API
  │                                                │   ├─ Update XeroWritebackItem
  │                                                │   ├─ Update TaxCodeOverride.writeback_status
  │                                                │   ├─ Update local Xero entity line_items
  │                                                │   └─ Emit audit event
  │                                                ├─ Refresh OAuth token if needed
  │                                                └─ Update XeroWritebackJob (counts, status)
  │
  └── receives updated counts + item statuses
```

---

## Xero Sandbox Testing

Use the Xero Demo Company for integration tests:
1. Connect to Xero Demo Company in local dev
2. Create test invoices with known tax types
3. Run the writeback flow
4. Verify in Xero UI that tax types were updated

**Note**: Xero Demo Company has some pre-locked periods. Use invoices dated within the current financial year for write tests.
