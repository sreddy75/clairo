# Implementation Plan: Client Transaction Classification

**Branch**: `047-client-transaction-classification` | **Date**: 2026-03-15 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/047-client-transaction-classification/spec.md`

## Summary

Extend the BAS preparation workflow so accountants can send clients a magic link to classify their unresolved transactions in plain English. The AI maps client descriptions to BAS tax codes. The accountant reviews and approves. Every step is recorded as an ATO-ready audit trail. Built on top of Spec 046 (tax code suggestions) and Spec 030 (portal infrastructure).

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.x / Next.js 14 (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Pydantic v2, anthropic SDK, Resend, Clerk (accountant auth), portal magic link (client auth)
**Storage**: PostgreSQL 16 (2 new tables: `classification_requests`, `client_classifications`)
**Testing**: pytest with pytest-asyncio (backend), Jest (frontend)
**Target Platform**: Web (responsive — client page optimized for mobile)
**Project Type**: Web application (full-stack)
**Performance Goals**: Client classification page loads <3s on mobile; AI mapping <15s for batch of 50 transactions
**Constraints**: 200 transaction limit per request (UX); 7-day magic link expiry; portal auth (no Clerk for clients)
**Scale/Scope**: 2 new DB tables, ~11 API endpoints, 2 new frontend pages/screens, 1 email template

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Module boundaries respected | PASS | `bas/` owns models + accountant service. `portal/` owns client endpoints. Cross-module via service layer. |
| Repository pattern | PASS | New `ClassificationRepository` follows existing pattern |
| Multi-tenancy (`tenant_id` on all tables) | PASS | Both new tables have `tenant_id` FK + index |
| Layer order (L1 before L2) | PASS | L1 (BAS, Phases A-E) complete. L2 (Portal) infrastructure complete. This connects them. |
| Audit trail | PASS | 5 new audit event types. Immutable `ClientClassification` records. Full chain recorded. |
| Human-in-the-loop | PASS | Client classifies → AI maps → accountant approves. AI never auto-applies. |
| Pydantic schemas for all inputs | PASS | All endpoints use Pydantic v2 request/response models |
| Domain exceptions (not HTTPException in services) | PASS | New exceptions in `bas/exceptions.py` |
| UUID primary keys | PASS | Both tables use UUID PKs |
| Testing strategy | PASS | Unit + integration + E2E planned |

### Post-Design Re-check

| Gate | Status | Notes |
|------|--------|-------|
| No new module created | PASS | Extends `bas/` and `portal/` — no new top-level module |
| Cross-module communication via service layer | PASS | Portal classification router imports `ClassificationService` from `bas/` |
| No circular dependencies | PASS | `portal/` → `bas/` (one-way). `bas/` does not import from `portal/`. |
| Existing patterns reused | PASS | Reuses `MagicLinkService`, `TaxCodeSuggestion`, `PortalEmailTemplates`, `portalApi` |

## Project Structure

### Documentation (this feature)

```text
specs/047-client-transaction-classification/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 research (8 decisions)
├── data-model.md        # 2 new entities, state transitions
├── quickstart.md        # Developer orientation
├── contracts/
│   └── api.md           # 11 API endpoints
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── modules/
│   │   ├── bas/
│   │   │   ├── classification_models.py      # NEW: ClassificationRequest, ClientClassification
│   │   │   ├── classification_service.py     # NEW: ClassificationService
│   │   │   ├── classification_schemas.py     # NEW: Pydantic schemas
│   │   │   ├── classification_constants.py   # NEW: Category taxonomy
│   │   │   ├── router.py                     # MODIFIED: add accountant classification endpoints
│   │   │   ├── models.py                     # MODIFIED: new audit event constants
│   │   │   └── exceptions.py                 # MODIFIED: new domain exceptions
│   │   └── portal/
│   │       ├── classification_router.py      # NEW: client-facing classification endpoints
│   │       ├── service.py                    # MODIFIED: wire email sending
│   │       └── notifications/
│   │           └── templates.py              # MODIFIED: new email template
│   └── main.py                               # MODIFIED: mount classification router
├── alembic/
│   └── versions/
│       └── 047_spec_047_client_classification.py  # NEW: migration
└── tests/
    ├── unit/
    │   └── modules/bas/
    │       └── test_classification_service.py     # NEW
    └── integration/
        └── api/
            └── test_classification.py             # NEW

frontend/
├── src/
│   ├── app/
│   │   └── portal/
│   │       └── classify/
│   │           └── [requestId]/
│   │               └── page.tsx              # NEW: client classification page
│   ├── components/
│   │   ├── portal/
│   │   │   └── TransactionClassifier.tsx     # NEW: category picker component
│   │   └── bas/
│   │       ├── ClassificationRequestButton.tsx  # NEW: trigger button
│   │       └── ClassificationReview.tsx         # NEW: review screen
│   └── lib/
│       ├── api/
│       │   └── portal.ts                     # MODIFIED: add classify.* methods
│       └── constants/
│           └── classification-categories.ts  # NEW: category taxonomy
```

**Structure Decision**: Extends existing `bas/` and `portal/` modules. No new top-level module. New files use `classification_` prefix to namespace within the module.

## Complexity Tracking

No constitution violations. Feature reuses existing infrastructure heavily:
- Portal magic link auth (Spec 030)
- Tax code suggestion/override flow (Spec 046)
- Email templates + Resend (Spec 030)
- Portal frontend layout + API client (Spec 030)
