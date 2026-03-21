# Quickstart: Bulk Client Import

**Feature**: 035-bulk-client-import

## Prerequisites

- Docker Compose running (`docker-compose up -d`)
- Backend and frontend dev servers running
- At least one Xero account with access to multiple organizations
- A registered tenant (accounting practice) in Clairo

## Development Setup

### Backend

```bash
cd backend
uv sync
uv run alembic upgrade head  # Apply new migration for bulk_import_organizations table
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Testing the Feature

### Manual Testing Flow

1. **Navigate to Clients page** at `http://localhost:3001/clients`
2. **Click "Import Clients from Xero"** button in the page header
3. **Complete Xero OAuth** — select multiple organizations in Xero's consent screen
4. **Review configuration screen** — verify all authorized orgs appear with:
   - Checkboxes (default: selected)
   - Team member dropdown
   - Connection type selector
   - Already-connected orgs greyed out
5. **Select desired orgs and click "Import Selected"**
6. **Monitor progress dashboard** — verify real-time status updates
7. **Navigate to Clients list** — verify imported clients appear

### Key Test Scenarios

| Scenario | Steps | Expected |
|----------|-------|----------|
| Happy path (5 orgs) | Authorize 5, select all, import | 5 connections created, syncs start |
| Mixed new/existing | Authorize 10, 3 already connected | 7 new imported, 3 shown as already connected |
| Plan limit hit | 20 clients, Starter plan (25 limit), import 10 | Warning shown, only 5 selectable |
| Retry failed | Import 5, 1 fails | Click retry on failed org, sync restarts |
| Auto-matching | Have XPM clients, import matching orgs | Matched orgs auto-linked |

## File Locations

### Backend (changes)

```
backend/app/
├── modules/
│   ├── integrations/xero/
│   │   ├── service.py           # New handle_bulk_callback(), BulkImportService
│   │   ├── router.py            # New /bulk-import/* endpoints
│   │   ├── schemas.py           # New bulk import request/response schemas
│   │   └── models.py            # XeroOAuthState.is_bulk_import field
│   └── onboarding/
│       └── models.py            # BulkImportOrganization model (new table)
├── tasks/
│   └── xero.py                  # New run_bulk_xero_import Celery task
└── alembic/versions/
    └── xxx_add_bulk_import.py   # Migration
```

### Frontend (changes)

```
frontend/src/
├── app/(protected)/clients/
│   ├── page.tsx                 # Add "Import Clients from Xero" button
│   └── import/
│       ├── page.tsx             # Configuration screen (post-OAuth)
│       └── progress/
│           └── [jobId]/
│               └── page.tsx     # Progress dashboard
├── lib/api/
│   └── bulk-import.ts           # API client for bulk import endpoints
└── types/
    └── bulk-import.ts           # TypeScript types
```

## Environment Variables

No new environment variables required. Uses existing:
- `XERO_CLIENT_ID` / `XERO_CLIENT_SECRET` — OAuth credentials
- `REDIS_URL` — For app-wide rate limit counter
- `CELERY_BROKER_URL` — For background task dispatch
