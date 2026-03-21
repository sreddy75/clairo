# Implementation Tasks: Client Portal Foundation + Document Requests

**Feature**: 030-client-portal-document-requests
**Branch**: `030-client-portal-document-requests`
**Total Tasks**: 96
**Estimated Phases**: 14

---

## Overview

This task list implements the client portal with magic link authentication and the ClientChase document request workflow.

### User Stories (from spec.md)

| Story | Priority | Description |
|-------|----------|-------------|
| US1 | P1 | Client Invitation |
| US2 | P1 | Client Dashboard |
| US3 | P1 | Document Request Templates |
| US4 | P1 | Send Document Request |
| US5 | P1 | Bulk Document Requests |
| US6 | P1 | Respond to Request |
| US7 | P1 | Request Tracking Dashboard |
| US8 | P2 | Auto-Reminders |
| US9 | P1 | Document Upload |
| US10 | P2 | Auto-Filing |

### Dependencies

```
US1 (Invitation) ──► US2 (Dashboard) ──► US6 (Respond)
                                              │
US3 (Templates) ──► US4 (Send) ──────────────┤
                        │                     │
                        └──► US5 (Bulk) ──────┤
                                              ▼
                                         US7 (Tracking)
                                              │
US9 (Upload) ────────────────────────────────┘
                                              │
US8 (Auto-Reminders) ─────────────────────────┤
US10 (Auto-Filing) ───────────────────────────┘
```

---

## Phase 1: Setup (6 tasks) ✓ COMPLETE

**Goal**: Create portal module structure and database tables

- [X] T001 Create portal module directory in backend/app/modules/portal/
- [X] T002 Create portal __init__.py with module exports in backend/app/modules/portal/__init__.py
- [X] T003 Create models.py with all 8 entity models in backend/app/modules/portal/models.py
- [X] T004 [P] Create Alembic migration for portal tables in backend/alembic/versions/
- [X] T005 Create test directories in backend/tests/unit/modules/portal/ and backend/tests/integration/api/
- [X] T006 Register portal router in main.py in backend/app/main.py

---

## Phase 2: Foundational - Shared Components (8 tasks) ✓ COMPLETE

**Goal**: Build shared infrastructure for portal and requests

- [X] T007 Create enums.py with RequestStatus, RequestPriority, InvitationStatus, EventType in backend/app/modules/portal/enums.py
- [X] T008 Create exceptions.py with PortalError, InvitationExpiredError, RequestNotFoundError in backend/app/modules/portal/exceptions.py
- [X] T009 Create base schemas.py for request/response schemas in backend/app/modules/portal/schemas.py
- [X] T010 Create repository.py with base PortalRepository in backend/app/modules/portal/repository.py
- [X] T011 [P] Create PortalInvitationRepository in backend/app/modules/portal/repository.py
- [X] T012 [P] Create PortalSessionRepository in backend/app/modules/portal/repository.py
- [X] T013 [P] Create DocumentRequestRepository in backend/app/modules/portal/repository.py
- [X] T014 [P] Create PortalDocumentRepository in backend/app/modules/portal/repository.py

---

## Phase 3: User Story 1 - Client Invitation (10 tasks) ✓ COMPLETE

**Goal**: Accountants can invite clients to portal via magic link
**Independent Test**: Invite client → client receives email → clicks magic link → sees dashboard

### Magic Link Service

- [X] T015 [US1] Create MagicLinkService class in backend/app/modules/portal/auth/magic_link.py
- [X] T016 [US1] Implement generate_magic_link_token() in backend/app/modules/portal/auth/magic_link.py
- [X] T017 [US1] Implement verify_magic_link_token() in backend/app/modules/portal/auth/magic_link.py
- [X] T018 [US1] Implement create_session_tokens() for access/refresh in backend/app/modules/portal/auth/magic_link.py
- [X] T019 [P] [US1] Write unit tests for MagicLinkService in backend/tests/unit/modules/portal/test_magic_link.py

### Invitation Endpoints

- [X] T020 [US1] Create POST /clients/{id}/invite endpoint in backend/app/modules/portal/router.py
- [X] T021 [US1] Create GET /clients/{id}/invitations endpoint in backend/app/modules/portal/router.py
- [X] T022 [US1] Create GET /clients/{id}/portal-access endpoint in backend/app/modules/portal/router.py
- [X] T023 [US1] Create DELETE /clients/{id}/portal-access endpoint in backend/app/modules/portal/router.py
- [X] T024 [US1] Write integration tests for invitation API in backend/tests/integration/api/test_portal_endpoints.py

---

## Phase 4: User Story 1 - Portal Authentication (8 tasks) ✓ COMPLETE

**Goal**: Clients can authenticate via magic link
**Independent Test**: Click magic link → authenticated → see dashboard

### Auth Endpoints

- [X] T025 [US1] Create POST /portal/auth/request-link endpoint in backend/app/modules/portal/auth/router.py
- [X] T026 [US1] Create POST /portal/auth/verify endpoint in backend/app/modules/portal/auth/router.py
- [X] T027 [US1] Create POST /portal/auth/refresh endpoint in backend/app/modules/portal/auth/router.py
- [X] T028 [US1] Create POST /portal/auth/logout endpoint in backend/app/modules/portal/auth/router.py
- [X] T029 [US1] Create get_current_portal_client dependency in backend/app/modules/portal/auth/dependencies.py
- [X] T030 [P] [US1] Write integration tests for portal auth in backend/tests/integration/api/test_portal_endpoints.py

### Frontend Auth Pages

- [X] T031 [US1] Create portal login page in frontend/src/app/portal/login/page.tsx
- [X] T032 [US1] Create portal verify page in frontend/src/app/portal/verify/page.tsx

---

## Phase 5: User Story 2 - Client Dashboard (8 tasks) ✓ COMPLETE

**Goal**: Clients see BAS status, pending items, and key metrics
**Independent Test**: Login → see current BAS status, pending requests count

### Backend Dashboard

- [X] T033 [US2] Create PortalDashboardService in backend/app/modules/portal/dashboard/service.py
- [X] T034 [US2] Implement get_dashboard() aggregation in backend/app/modules/portal/dashboard/service.py
- [X] T035 [US2] Create GET /portal/dashboard endpoint in backend/app/modules/portal/dashboard/router.py
- [X] T036 [US2] Create GET /portal/dashboard/bas-status endpoint in backend/app/modules/portal/dashboard/router.py
- [X] T037 [US2] Create GET /portal/dashboard/activity endpoint in backend/app/modules/portal/dashboard/router.py
- [X] T038 [P] [US2] Write integration tests for dashboard API in backend/tests/integration/api/test_portal_endpoints.py

### Frontend Dashboard

- [X] T039 [US2] Create portal dashboard page in frontend/src/app/portal/dashboard/page.tsx
- [X] T040 [US2] Create DashboardCards component in frontend/src/components/portal/DashboardCards.tsx

---

## Phase 6: User Story 3 - Document Request Templates (8 tasks) ✓ COMPLETE

**Goal**: Pre-built templates for common document requests
**Independent Test**: Select "Bank Statements" template → pre-fills title, description

### Template System

- [X] T041 [US3] Create SYSTEM_TEMPLATES list in backend/app/modules/portal/requests/templates.py
- [X] T042 [US3] Create DocumentRequestTemplateRepository in backend/app/modules/portal/repository.py (already existed)
- [X] T043 [US3] Create GET /request-templates endpoint in backend/app/modules/portal/requests/router.py
- [X] T044 [US3] Create POST /request-templates endpoint in backend/app/modules/portal/requests/router.py
- [X] T045 [US3] Create PATCH /request-templates/{id} endpoint in backend/app/modules/portal/requests/router.py
- [X] T046 [US3] Create DELETE /request-templates/{id} endpoint in backend/app/modules/portal/requests/router.py
- [X] T047 [P] [US3] Write unit tests for templates in backend/tests/unit/modules/portal/test_templates.py

### Frontend Templates

- [X] T048 [US3] Create RequestTemplateSelector component in frontend/src/components/requests/RequestTemplateSelector.tsx

---

## Phase 7: User Story 4 - Send Document Request (8 tasks) ✓ COMPLETE

**Goal**: Accountants can send document requests to clients
**Independent Test**: Send request → client receives email → sees request in portal

### Request Service

- [X] T049 [US4] Create DocumentRequestService in backend/app/modules/portal/requests/service.py
- [X] T050 [US4] Implement create_request() in backend/app/modules/portal/requests/service.py
- [X] T051 [US4] Implement send_request() in backend/app/modules/portal/requests/service.py
- [X] T052 [US4] Create POST /clients/{id}/requests endpoint in backend/app/modules/portal/requests/router.py
- [X] T053 [US4] Create POST /requests/{id}/send endpoint in backend/app/modules/portal/requests/router.py
- [X] T054 [P] [US4] Write integration tests for request creation in backend/tests/integration/api/test_document_requests.py

### Frontend Request Creation

- [X] T055 [US4] Create new request page in frontend/src/app/(protected)/clients/[id]/requests/new/page.tsx
- [X] T056 [US4] Create RequestForm component in frontend/src/components/requests/RequestForm.tsx

---

## Phase 8: User Story 5 - Bulk Document Requests (8 tasks) ✓ COMPLETE

**Goal**: Send same request to multiple clients at once
**Independent Test**: Select 20 clients → apply template → send to all

### Bulk Service

- [X] T057 [US5] Create BulkRequestService in backend/app/modules/portal/requests/bulk.py
- [X] T058 [US5] Implement create_bulk_request() in backend/app/modules/portal/requests/bulk.py
- [X] T059 [US5] Implement process_bulk_request() for Celery in backend/app/modules/portal/requests/bulk.py
- [X] T060 [US5] Create POST /bulk-requests endpoint in backend/app/modules/portal/requests/router.py
- [X] T061 [US5] Create POST /bulk-requests/preview endpoint in backend/app/modules/portal/requests/router.py
- [X] T062 [US5] Create Celery task for bulk processing in backend/app/tasks/portal/send_bulk_requests.py
- [X] T063 [P] [US5] Write integration tests for bulk requests in backend/tests/integration/api/test_bulk_requests.py

### Frontend Bulk UI

- [X] T064 [US5] Create BulkRequestWizard component in frontend/src/components/requests/BulkRequestWizard.tsx

---

## Phase 9: User Story 6 - Respond to Request (8 tasks) ✓ COMPLETE

**Goal**: Clients can respond with document uploads and notes
**Independent Test**: Open request → upload document → submit → accountant notified

### Response Service

- [X] T065 [US6] Implement mark_viewed() in backend/app/modules/portal/requests/service.py
- [X] T066 [US6] Implement submit_response() in backend/app/modules/portal/requests/service.py
- [X] T067 [US6] Create GET /portal/requests endpoint in backend/app/modules/portal/requests/client_router.py
- [X] T068 [US6] Create GET /portal/requests/{id} endpoint in backend/app/modules/portal/requests/client_router.py
- [X] T069 [US6] Create POST /portal/requests/{id}/respond endpoint in backend/app/modules/portal/requests/client_router.py
- [X] T070 [P] [US6] Write integration tests for client response in backend/tests/integration/api/test_portal_requests.py

### Frontend Response UI

- [X] T071 [US6] Create request detail page in frontend/src/app/portal/requests/[id]/page.tsx
- [X] T072 [US6] Create RespondForm component in frontend/src/components/portal/RespondForm.tsx

---

## Phase 10: User Story 9 - Document Upload (8 tasks) ✓ COMPLETE

**Goal**: Drag-drop and mobile-friendly document upload
**Independent Test**: Drag file → upload with progress → attach to response

### Upload Service

- [X] T073 [US9] Create PortalUploadService in backend/app/modules/portal/documents/upload.py
- [X] T074 [US9] Implement upload_document() with S3 in backend/app/modules/portal/documents/upload.py
- [X] T075 [US9] Implement get_presigned_upload_url() in backend/app/modules/portal/documents/upload.py
- [X] T076 [US9] Create POST /portal/documents/upload endpoint in backend/app/modules/portal/documents/router.py
- [X] T077 [US9] Create POST /portal/documents/upload-url endpoint in backend/app/modules/portal/documents/router.py
- [X] T078 [P] [US9] Write integration tests for document upload in backend/tests/integration/api/test_portal_documents.py

### Frontend Uploader

- [X] T079 [US9] Create DocumentUploader component in frontend/src/components/portal/DocumentUploader.tsx
- [X] T080 [US9] Implement drag-drop with react-dropzone in frontend/src/components/portal/DocumentUploader.tsx

---

## Phase 11: User Story 7 - Request Tracking Dashboard (6 tasks) ✓ COMPLETE

**Goal**: Accountants can track request status across all clients
**Independent Test**: Open tracking dashboard → see requests grouped by status

### Tracking API

- [X] T081 [US7] Create GET /requests/tracking endpoint in backend/app/modules/portal/requests/router.py
- [X] T082 [US7] Create GET /requests/tracking/summary endpoint in backend/app/modules/portal/requests/router.py
- [X] T083 [P] [US7] Write integration tests for tracking API in backend/tests/integration/api/test_request_tracking.py

### Frontend Tracking

- [X] T084 [US7] Create request tracking page in frontend/src/app/(protected)/requests/page.tsx
- [X] T085 [US7] Create RequestTrackingTable component in frontend/src/components/requests/RequestTrackingTable.tsx
- [X] T086 [US7] Create RequestStatusBadge component in frontend/src/components/requests/RequestStatusBadge.tsx

---

## Phase 12: User Story 8 - Auto-Reminders (6 tasks) ✓ COMPLETE

**Goal**: Automatic reminders sent before and after due dates
**Independent Test**: Request due in 3 days → auto-reminder sent

### Reminder System

- [X] T087 [US8] Implement send_reminder() in backend/app/modules/portal/requests/service.py
- [X] T088 [US8] Create auto_reminders Celery task in backend/app/tasks/portal/auto_reminders.py
- [X] T089 [US8] Schedule auto_reminders in Celery beat config in backend/app/tasks/celery_app.py
- [X] T090 [US8] Create GET/PATCH /requests/{id}/auto-remind endpoints in backend/app/modules/portal/requests/router.py
- [X] T091 [US8] Create GET/PATCH /settings/reminders endpoints in backend/app/modules/portal/requests/router.py
- [X] T092 [P] [US8] Write unit tests for reminder scheduling in backend/tests/unit/portal/test_auto_reminders.py

---

## Phase 13: Notifications & Email Templates (4 tasks) ✓ COMPLETE

**Goal**: Professional email templates for all portal notifications

- [X] T093 Create portal invitation email template in backend/app/modules/portal/notifications/templates.py
- [X] T094 Create document request email template in backend/app/modules/portal/notifications/templates.py
- [X] T095 Create reminder email templates (3-day, 1-day, overdue) in backend/app/modules/portal/notifications/templates.py
- [X] T096 Create response notification email template in backend/app/modules/portal/notifications/templates.py

---

## Phase 14: Polish & Cross-Cutting (4 tasks) ✓ COMPLETE

**Goal**: Final validation and documentation

- [X] T097 Implement auto-filing for uploaded documents in backend/app/modules/portal/documents/auto_file.py
- [X] T098 Create PortalHeader component in frontend/src/components/portal/PortalHeader.tsx
- [X] T099 Create portal layout with navigation in frontend/src/app/portal/layout.tsx
- [X] T100 Update API documentation and validate all endpoints in specs/030-client-portal-document-requests/contracts/

---

## Parallel Execution Guide

### Maximum Parallelism by Phase

| Phase | Parallel Groups |
|-------|-----------------|
| Phase 1 | T001 → T002-T06 |
| Phase 2 | T007-T09, (T10+T11+T12+T13+T14) |
| Phase 3 | T015-T18 → T19, T20-T24 |
| Phase 4 | T025-T29 → T30, T31+T32 |
| Phase 5 | T033-T37 → T38, T39+T40 |
| Phase 6 | T041-T46 → T47, T48 |
| Phase 7 | T049-T53 → T54, T55+T56 |
| Phase 8 | T057-T62 → T63, T64 |
| Phase 9 | T065-T69 → T70, T71+T72 |
| Phase 10 | T073-T77 → T78, T79+T80 |
| Phase 11 | T081-T82 → T83, T84-T86 |
| Phase 12 | T087-T91 → T92 |
| Phase 13 | T093+T094+T095+T096 |
| Phase 14 | T097+T098+T099+T100 |

### Independent Work Streams

```
Stream A (Auth): Phase 3 → Phase 4
Stream B (Dashboard): Phase 5 (after Phase 4)
Stream C (Requests): Phase 6 → Phase 7 → Phase 8 → Phase 11 → Phase 12
Stream D (Response): Phase 9 → Phase 10 (after Phase 4)
Stream E (Notifications): Phase 13 (after Phase 7)
Stream F (Polish): Phase 14 (after all)
```

---

## MVP Scope

**Minimum Viable Product**: User Stories 1, 2, 4, 6, 9 (Phases 1-5, 7, 9-10)

| Phase | Tasks | Description |
|-------|-------|-------------|
| 1 | T001-T006 | Setup |
| 2 | T007-T014 | Foundational |
| 3 | T015-T024 | Invitation |
| 4 | T025-T032 | Portal Auth |
| 5 | T033-T040 | Dashboard |
| 7 | T049-T056 | Send Request |
| 9 | T065-T072 | Respond |
| 10 | T073-T080 | Upload |

**MVP Task Count**: 56 tasks

**Post-MVP**:
- Phase 6: Templates (T041-T048)
- Phase 8: Bulk Requests (T057-T064)
- Phase 11: Tracking Dashboard (T081-T086)
- Phase 12: Auto-Reminders (T087-T092)
- Phase 13: Notifications (T093-T096)
- Phase 14: Polish (T097-T100)

---

## Validation Checklist

- [x] All 100 tasks follow checklist format
- [x] Each user story phase is independently testable
- [x] Dependencies are correctly sequenced
- [x] Parallel opportunities identified
- [x] MVP scope defined (56 tasks)
- [x] File paths specified for all implementation tasks
