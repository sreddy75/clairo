# Quickstart: Spec 047 — Client Transaction Classification

## What This Feature Does

Accountants can send clients a magic link to classify their unresolved BAS transactions in plain English. The AI maps client descriptions to tax codes. The accountant reviews and approves. Full audit trail recorded.

## Architecture Summary

This feature bridges two existing modules:
- **`bas/`** module: owns the data models, accountant-facing service, AI mapping logic
- **`portal/`** module: owns client-facing endpoints, magic link auth, email delivery

## Key Files

### Backend (new)
| File | Purpose |
|------|---------|
| `backend/app/modules/bas/classification_models.py` | `ClassificationRequest` + `ClientClassification` SQLAlchemy models |
| `backend/app/modules/bas/classification_service.py` | Business logic: create request, AI mapping, review/approve |
| `backend/app/modules/bas/classification_schemas.py` | Pydantic request/response schemas |
| `backend/app/modules/bas/classification_constants.py` | Category taxonomy (plain English → tax code groups) |
| `backend/app/modules/portal/classification_router.py` | Client-facing API endpoints (portal auth) |
| `backend/app/modules/portal/notifications/templates.py` | New `transaction_classification_request` template (extend existing) |
| `backend/alembic/versions/047_*.py` | Migration: `classification_requests` + `client_classifications` tables |

### Backend (modified)
| File | Change |
|------|--------|
| `backend/app/modules/bas/router.py` | Add accountant-facing classification endpoints |
| `backend/app/modules/bas/models.py` | New audit event type constants |
| `backend/app/modules/portal/service.py` | Wire up email sending in `InvitationService` |
| `backend/app/main.py` | Mount new portal classification router |

### Frontend (new)
| File | Purpose |
|------|---------|
| `frontend/src/app/portal/classify/[requestId]/page.tsx` | Client classification page |
| `frontend/src/components/portal/TransactionClassifier.tsx` | Category picker + free text per transaction |
| `frontend/src/components/bas/ClassificationRequestButton.tsx` | "Request Client Input" button for BAS prep |
| `frontend/src/components/bas/ClassificationReview.tsx` | Accountant review screen |
| `frontend/src/lib/constants/classification-categories.ts` | Category taxonomy (mirrors backend) |
| `frontend/src/lib/api/portal.ts` | Add `classify.*` methods to `portalApi` |

### Frontend (modified)
| File | Change |
|------|--------|
| BAS prep page | Add `ClassificationRequestButton` + status indicator |

## Development Order

1. **Migration + Models** — Create tables, define SQLAlchemy models
2. **Category Constants** — Define taxonomy (backend + frontend)
3. **Classification Service** — Create request, save classification, submit, AI mapping, review/approve
4. **Wire Email Sending** — Fix the existing portal invitation email gap
5. **Email Template** — New "classify transactions" template
6. **Accountant API** — Create request, get status, review, approve endpoints
7. **Client API** — Get transactions, save classification, submit endpoints
8. **Client Frontend** — `/portal/classify/[requestId]` page
9. **Accountant Frontend** — Request button + review screen
10. **Tests** — Unit (service), integration (API), E2E (full flow)

## Key Decisions

| Decision | Choice | Reference |
|----------|--------|-----------|
| Model location | `bas/` module | research.md R1 |
| Magic link strategy | Reuse `PortalInvitation` via existing `MagicLinkService` | research.md R2 |
| AI mapping trigger | Lazy on accountant review, not on client submit | research.md R3 |
| Category storage | Hardcoded constants (backend + frontend) | research.md R4 |
| Save progress | Server-side auto-save per classification | research.md R6 |
| Review flow | Creates `TaxCodeSuggestion` records with tier `client_classified` | research.md R7 |

## Testing Strategy

| Test Type | Scope |
|-----------|-------|
| Unit | `ClassificationService` — create request, save, submit, AI mapping, approve |
| Unit | Category taxonomy validation |
| Integration | All 11 API endpoints |
| Integration | Email sending (mock Resend) |
| Integration | Magic link → classify → submit → review → approve flow |
| E2E | Accountant creates request → client classifies → accountant reviews |
