# Implementation Tasks: PWA & Mobile + Document Capture

**Feature**: 032-pwa-mobile-document-capture
**Branch**: `032-pwa-mobile-document-capture`
**Total Tasks**: 72
**Estimated Phases**: 10

---

## Overview

This task list implements PWA functionality, push notifications, offline support, and camera-first document capture.

### User Stories (from spec.md)

| Story | Priority | Description |
|-------|----------|-------------|
| US1 | P1 | PWA Installation |
| US2 | P1 | Push Notifications |
| US3 | P1 | Offline Request Viewing |
| US4 | P1 | Camera-First Upload |
| US5 | P1 | Multi-Page Scanning |
| US6 | P1 | Offline Upload Queue |
| US7 | P2 | Document Quality Check |
| US8 | P2 | App Settings |
| US9 | P2 | Biometric Quick Access |
| US10 | P2 | Installation Analytics |

### Dependencies

```
US1 (PWA Install) ──────────────────────────────────────┐
                                                         │
US2 (Push Notifications) ───────────────────────────────┤
                                                         │
US3 (Offline Viewing) + US6 (Upload Queue) ─────────────┤
                                                         │
US4 (Camera Capture) ──► US5 (Multi-Page) ──► US7 (Quality)
                                                         │
US9 (Biometric) ─────────────────────────────────────────┤
                                                         │
US10 (Analytics) ────────────────────────────────────────┘
                                                         │
US8 (Settings) ──────────────────────────────────────────┘
```

---

## Phase 1: Setup (6 tasks) ✓ COMPLETE

**Goal**: Create PWA infrastructure and database tables

- [X] T001 Install PWA dependencies (next-pwa, workbox, idb, jspdf) in frontend/package.json
- [X] T002 Create push notification submodule in backend/app/modules/notifications/push/
- [X] T003 Create PWA models in backend/app/modules/notifications/push/models.py
- [X] T004 [P] Create Alembic migration for push_subscriptions, webauthn_credentials, pwa_events in backend/alembic/versions/
- [X] T005 Create manifest.json in frontend/public/manifest.json
- [X] T006 Create PWA icon set (72, 192, 512px) in frontend/public/icons/

---

## Phase 2: User Story 1 - PWA Installation (8 tasks) ✓ COMPLETE

**Goal**: Installable PWA with service worker
**Independent Test**: Visit portal twice → see install prompt → install → app opens standalone

### PWA Configuration

- [X] T007 [US1] Configure next-pwa in frontend/next.config.js
- [X] T008 [US1] Add manifest and meta tags to portal layout in frontend/src/app/portal/layout.tsx
- [X] T009 [US1] Create service worker entry in frontend/src/workers/portal-sw.ts

### Frontend Hooks & Components

- [X] T010 [US1] Create useServiceWorker hook in frontend/src/hooks/useServiceWorker.ts
- [X] T011 [US1] Create InstallPrompt component in frontend/src/components/pwa/InstallPrompt.tsx
- [X] T012 [US1] Create OfflineIndicator component in frontend/src/components/pwa/OfflineIndicator.tsx
- [X] T013 [US1] Create useNetworkStatus hook in frontend/src/hooks/useNetworkStatus.ts
- [X] T014 [US1] Integrate InstallPrompt in portal layout in frontend/src/app/portal/layout.tsx

---

## Phase 3: User Story 2 - Push Notifications (12 tasks)

**Goal**: Push notifications for document requests
**Independent Test**: Enable notifications → accountant creates request → receive push within 2 seconds

### Backend Push Service

- [X] T015 [US2] Create PushSubscriptionRepository in backend/app/modules/notifications/push/repository.py
- [X] T016 [US2] Create PushSubscriptionService in backend/app/modules/notifications/push/service.py
- [X] T017 [US2] Create push schemas in backend/app/modules/notifications/push/schemas.py
- [X] T018 [US2] Create push router with VAPID key endpoint in backend/app/modules/notifications/push/router.py
- [X] T019 [US2] Create subscribe/unsubscribe endpoints in backend/app/modules/notifications/push/router.py
- [X] T020 [P] [US2] Web Push API integration via pywebpush (no Firebase needed)
- [X] T021 [US2] Add push notification triggers to DocumentRequestService in backend/app/modules/portal/requests/service.py

### Frontend Push Integration

- [X] T022 [US2] Create usePushNotifications hook in frontend/src/hooks/usePushNotifications.ts
- [X] T023 [US2] Create NotificationPermission component in frontend/src/components/pwa/NotificationPermission.tsx
- [X] T024 [US2] Add push message handler to service worker in frontend/src/workers/portal-sw.ts
- [X] T025 [US2] Add notification prompt after first request view in frontend/src/app/portal/requests/[id]/page.tsx
- [X] T026 [P] [US2] Write integration tests for push endpoints in backend/tests/integration/api/test_push.py

---

## Phase 4: User Story 3 - Offline Request Viewing (8 tasks) ✓ COMPLETE

**Goal**: View requests and dashboard when offline
**Independent Test**: Load dashboard → go offline → refresh → dashboard still shows

### IndexedDB Setup

- [X] T027 [US3] Create IndexedDB database setup in frontend/src/lib/pwa/db.ts
- [X] T028 [US3] Create cached-requests store operations in frontend/src/lib/pwa/cached-requests.ts
- [X] T029 [US3] Create cached-dashboard store operations in frontend/src/lib/pwa/cached-dashboard.ts

### Service Worker Caching

- [X] T030 [US3] Configure API caching strategies in frontend/src/workers/portal-sw.ts
- [X] T031 [US3] Implement stale-while-revalidate for dashboard API in frontend/src/workers/portal-sw.ts
- [X] T032 [US3] Cache request list on view in frontend/src/app/portal/dashboard/page.tsx

### Offline UI

- [X] T033 [US3] Add offline fallback data loading in frontend/src/app/portal/dashboard/page.tsx
- [X] T034 [US3] Add last sync timestamp display in frontend/src/components/pwa/OfflineIndicator.tsx

---

## Phase 5: User Story 4 - Camera-First Upload (10 tasks) ✓ COMPLETE

**Goal**: Open camera directly from request and upload photo
**Independent Test**: View request → tap Take Photo → capture → photo uploads

### Camera Capture

- [X] T035 [US4] Create useCamera hook in frontend/src/hooks/useCamera.ts
- [X] T036 [US4] Create CameraCapture component in frontend/src/components/pwa/CameraCapture.tsx
- [X] T037 [US4] Create CameraPreview component in frontend/src/components/pwa/CameraPreview.tsx

### Image Processing

- [X] T038 [US4] Create image compression utility in frontend/src/lib/pwa/image-processor.ts
- [X] T039 [US4] Create EXIF orientation handler in frontend/src/lib/pwa/image-processor.ts
- [X] T040 [US4] Create image resize utility in frontend/src/lib/pwa/image-processor.ts

### Integration

- [X] T041 [US4] Add "Take Photo" button to request detail (via CameraUploadFlow component)
- [X] T042 [US4] Create CameraUploadFlow component in frontend/src/components/pwa/CameraUploadFlow.tsx
- [X] T043 [US4] Add camera permission error handling in frontend/src/components/pwa/CameraCapture.tsx
- [X] T044 [US4] Add upload progress indicator in frontend/src/components/pwa/CameraUploadFlow.tsx

---

## Phase 6: User Story 5 - Multi-Page Scanning (8 tasks) ✓ COMPLETE

**Goal**: Capture multiple pages as single PDF
**Independent Test**: Capture 3 pages → reorder → generate PDF → upload

### Multi-Page Capture

- [X] T045 [US5] Create captured-pages IndexedDB store in frontend/src/lib/pwa/db.ts
- [X] T046 [US5] Create MultiPageScanner component in frontend/src/components/pwa/MultiPageScanner.tsx
- [X] T047 [US5] Create PageThumbnailStrip component in frontend/src/components/pwa/PageThumbnailStrip.tsx
- [X] T048 [US5] Add page reorder with drag-and-drop in frontend/src/components/pwa/PageThumbnailStrip.tsx

### PDF Generation

- [X] T049 [US5] Create PDF generator utility in frontend/src/lib/pwa/pdf-generator.ts
- [X] T050 [US5] Create PDFPreview component in frontend/src/components/pwa/PDFPreview.tsx
- [X] T051 [US5] Add PDF filename generation in frontend/src/lib/pwa/pdf-generator.ts
- [X] T052 [US5] Integrate multi-page scanner in request detail in frontend/src/app/portal/requests/[id]/page.tsx

---

## Phase 7: User Story 6 - Offline Upload Queue (8 tasks) ✓ COMPLETE

**Goal**: Queue uploads when offline, sync when back online
**Independent Test**: Go offline → capture photo → queue shows pending → go online → auto-uploads

### Upload Queue

- [X] T053 [US6] Create upload-queue IndexedDB store in frontend/src/lib/pwa/db.ts
- [X] T054 [US6] Create upload queue operations in frontend/src/lib/pwa/upload-queue.ts
- [X] T055 [US6] Create useOfflineQueue hook in frontend/src/hooks/useOfflineQueue.ts
- [X] T056 [US6] Create QueueStatus component in frontend/src/components/pwa/QueueStatus.tsx

### Background Sync

- [X] T057 [US6] Implement background sync in service worker in frontend/src/workers/portal-sw.ts
- [X] T058 [US6] Add retry logic with exponential backoff in frontend/src/lib/pwa/upload-queue.ts
- [X] T059 [US6] Add queue processing on online event in frontend/src/hooks/useOfflineQueue.ts
- [X] T060 [US6] Add queue status notification in frontend/src/components/pwa/QueueStatus.tsx

---

## Phase 8: User Story 7 - Document Quality Check (4 tasks) ✓ COMPLETE

**Goal**: Warn user about blurry/dark photos before upload
**Independent Test**: Take blurry photo → see warning → retake → quality passes

- [X] T061 [US7] Create quality check utilities in frontend/src/lib/pwa/quality-check.ts
- [X] T062 [US7] Create QualityFeedback component in frontend/src/components/pwa/QualityFeedback.tsx
- [X] T063 [US7] Integrate quality check in CameraCapture in frontend/src/components/pwa/CameraCapture.tsx
- [X] T064 [US7] Add "Send Anyway" override option in frontend/src/components/pwa/QualityFeedback.tsx

---

## Phase 9: User Story 9 - Biometric Quick Access (8 tasks) ✓ COMPLETE

**Goal**: Use Face ID/fingerprint to authenticate
**Independent Test**: Register biometric → close app → reopen → authenticate with face/finger

### Backend WebAuthn

- [X] T065 [US9] Create WebAuthnRepository in backend/app/modules/notifications/push/repository.py (already exists)
- [X] T066 [US9] Create WebAuthnService in backend/app/modules/notifications/push/webauthn_service.py
- [X] T067 [US9] Create WebAuthn endpoints in backend/app/modules/notifications/push/router.py
- [X] T068 [P] [US9] Write integration tests for WebAuthn in backend/tests/integration/api/test_webauthn.py

### Frontend WebAuthn

- [X] T069 [US9] Create useBiometricAuth hook in frontend/src/hooks/useBiometricAuth.ts
- [X] T070 [US9] Create BiometricSetup component in frontend/src/components/pwa/BiometricSetup.tsx
- [X] T071 [US9] Add biometric prompt on app reopen in frontend/src/app/portal/layout.tsx (via login page)
- [X] T072 [US9] Add biometric option to login flow in frontend/src/app/portal/login/page.tsx

---

## Phase 10: User Story 8 & 10 - Settings & Analytics (8 tasks) ✓ COMPLETE

**Goal**: App settings and installation tracking
**Independent Test**: View settings → toggle notifications → change persists

### Settings

- [X] T073 [US8] Create settings IndexedDB store in frontend/src/lib/pwa/db.ts
- [X] T074 [US8] Create SettingsPage in frontend/src/app/portal/settings/page.tsx
- [X] T075 [US8] Create NotificationSettings component in frontend/src/components/pwa/NotificationSettings.tsx
- [X] T076 [US8] Create StorageSettings component in frontend/src/components/pwa/StorageSettings.tsx

### Analytics

- [X] T077 [US10] Create analytics tracking endpoints in backend/app/modules/notifications/push/router.py
- [X] T078 [US10] Create ClientPWAStatus query endpoint in backend/app/modules/notifications/push/router.py
- [X] T079 [US10] Create PWASummary dashboard endpoint in backend/app/modules/notifications/push/router.py
- [X] T080 [P] [US10] Add PWA status to client profile in frontend/src/app/(protected)/clients/[id]/page.tsx

---

## Parallel Execution Guide

### Maximum Parallelism by Phase

| Phase | Parallel Groups |
|-------|-----------------|
| Phase 1 | T001+T002, T003 → T004, T005+T006 |
| Phase 2 | T007-T09, T010-T13 → T014 |
| Phase 3 | T015-T21, T022-T25 → T026 |
| Phase 4 | T027-T29, T030-T32 → T033-T34 |
| Phase 5 | T035-T40, T041-T44 |
| Phase 6 | T045-T48, T049-T51 → T052 |
| Phase 7 | T053-T56, T057-T60 |
| Phase 8 | T061-T64 |
| Phase 9 | T065-T68, T069-T72 |
| Phase 10 | T073-T76, T077-T80 |

### Independent Work Streams

```
Stream A (PWA Core): Phase 1 → Phase 2 → Phase 3
Stream B (Offline): Phase 4 → Phase 7
Stream C (Camera): Phase 5 → Phase 6 → Phase 8
Stream D (Auth): Phase 9 (after Phase 2)
Stream E (Settings): Phase 10 (after all others)
```

---

## MVP Scope

**Minimum Viable Product**: User Stories 1, 2, 4, 6 (Phases 1-5, 7)

| Phase | Tasks | Description |
|-------|-------|-------------|
| 1 | T001-T006 | Setup |
| 2 | T007-T014 | PWA Installation |
| 3 | T015-T026 | Push Notifications |
| 4 | T027-T034 | Offline Viewing |
| 5 | T035-T044 | Camera Capture |
| 7 | T053-T060 | Offline Queue |

**MVP Task Count**: 52 tasks

**Post-MVP**:
- Phase 6: Multi-Page Scanning (T045-T052)
- Phase 8: Quality Check (T061-T064)
- Phase 9: Biometric Auth (T065-T072)
- Phase 10: Settings & Analytics (T073-T080)

---

## Validation Checklist

- [x] All 80 tasks follow checklist format
- [x] Each user story phase is independently testable
- [x] Dependencies are correctly sequenced
- [x] Parallel opportunities identified
- [x] MVP scope defined (52 tasks)
- [x] File paths specified for all implementation tasks

---

## Completion Summary

**Status**: ✅ COMPLETE
**Completed**: 2026-01-03
**Branch**: `032-pwa-mobile-document-capture`

### Implemented Features

| Feature | Status | Notes |
|---------|--------|-------|
| PWA Installation | ✅ | Service worker, manifest, install prompt |
| Push Notifications | ✅ | VAPID keys, web push, notification permission |
| Offline Request Viewing | ✅ | IndexedDB caching, stale-while-revalidate |
| Camera-First Upload | ✅ | Camera capture, image compression, EXIF handling |
| Multi-Page Scanning | ✅ | Page capture, reordering, PDF generation |
| Offline Upload Queue | ✅ | Background sync, retry with backoff |
| Document Quality Check | ✅ | Blur/brightness detection, user feedback |
| Biometric Quick Access | ✅ | WebAuthn, Face ID/Touch ID support |
| Settings & Analytics | ✅ | Notification settings, storage management |

### Key Files Created

**Backend**:
- `backend/app/modules/notifications/push/` - Push notification service
- `backend/app/modules/notifications/push/webauthn_service.py` - WebAuthn biometric auth

**Frontend**:
- `frontend/src/components/pwa/` - All PWA components
- `frontend/src/hooks/useBiometricAuth.ts` - Biometric authentication hook
- `frontend/src/hooks/useNetworkStatus.ts` - Network status tracking
- `frontend/src/lib/pwa/` - IndexedDB, image processing, PDF generation

### Testing Notes

- Portal accessible at `/portal/login`
- PWA installable after 2 visits
- Magic link authentication required for full portal access
- Biometric available after initial magic link login
