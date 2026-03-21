# Implementation Tasks: Messaging & Request Conversations

**Feature**: 031-messaging-request-conversations
**Branch**: `031-messaging-request-conversations`
**Total Tasks**: 84
**Estimated Phases**: 12

---

## Overview

This task list implements real-time messaging, request conversations, and BAS approval workflows.

### User Stories (from spec.md)

| Story | Priority | Description |
|-------|----------|-------------|
| US1 | P1 | Request Conversations |
| US2 | P1 | Accountant Request Chat |
| US3 | P1 | Request Amendments |
| US4 | P1 | BAS Review & Approval |
| US5 | P1 | Accountant Approval Dashboard |
| US6 | P2 | General Messaging |
| US7 | P2 | Accountant Inbox |
| US8 | P1 | Completion Confirmation |
| US9 | P1 | Real-time Notifications |
| US10 | P2 | Message Attachments |

### Dependencies

```
US1 (Request Chat) + US2 (Accountant Chat) ──► US3 (Amendments)
                                                    │
US9 (Real-time) ─────────────────────────────────┤
                                                    │
US4 (BAS Approval) ──► US5 (Approval Dashboard) ──┤
                                                    │
US6 (General Messaging) ──► US7 (Inbox) ──────────┤
                                                    │
US10 (Attachments) ───────────────────────────────┘
                                                    │
US8 (Completion) ─────────────────────────────────┘
```

---

## Phase 1: Setup (6 tasks)

**Goal**: Create messaging submodule structure and database tables

- [ ] T001 Create messaging submodule directory in backend/app/modules/portal/messaging/
- [ ] T002 Create approvals submodule directory in backend/app/modules/portal/approvals/
- [ ] T003 Create core websocket module in backend/app/core/websocket/
- [ ] T004 Create models.py with all 6 entity models in backend/app/modules/portal/messaging/models.py
- [ ] T005 [P] Create Alembic migration for messaging tables in backend/alembic/versions/
- [ ] T006 Create test directories in backend/tests/unit/modules/portal/messaging/ and integration

---

## Phase 2: Foundational - WebSocket Infrastructure (10 tasks)

**Goal**: Build WebSocket connection manager with Redis pub/sub

### Connection Manager

- [ ] T007 Create ConnectionManager class in backend/app/core/websocket/manager.py
- [ ] T008 Implement connect() and disconnect() methods in backend/app/core/websocket/manager.py
- [ ] T009 Implement send_to_user() for local delivery in backend/app/core/websocket/manager.py
- [ ] T010 Implement broadcast_message() with Redis pub/sub in backend/app/core/websocket/manager.py
- [ ] T011 Implement _listen_pubsub() for multi-instance in backend/app/core/websocket/manager.py

### WebSocket Authentication

- [ ] T012 Create WebSocket auth handler in backend/app/core/websocket/auth.py
- [ ] T013 Create main websocket_handler in backend/app/modules/portal/messaging/websocket.py
- [ ] T014 Implement message routing in websocket handler in backend/app/modules/portal/messaging/websocket.py
- [ ] T015 Register WebSocket endpoint in FastAPI app in backend/app/main.py
- [ ] T016 [P] Write integration tests for WebSocket auth in backend/tests/integration/api/test_websocket.py

---

## Phase 3: Foundational - Message Encryption (4 tasks)

**Goal**: Message content encryption with per-tenant keys

- [ ] T017 Create MessageEncryption class in backend/app/modules/portal/messaging/encryption.py
- [ ] T018 Implement local encryption for development in backend/app/modules/portal/messaging/encryption.py
- [ ] T019 [P] Implement KMS-based encryption for production in backend/app/modules/portal/messaging/encryption.py
- [ ] T020 [P] Write unit tests for encryption in backend/tests/unit/modules/portal/messaging/test_encryption.py

---

## Phase 4: User Story 1 & 2 - Request Conversations (10 tasks)

**Goal**: Clients and accountants can chat on document requests
**Independent Test**: View request → ask question → accountant responds

### Backend Service

- [ ] T021 [US1] Create MessagingService class in backend/app/modules/portal/messaging/service.py
- [ ] T022 [US1] Implement get_or_create_request_conversation() in backend/app/modules/portal/messaging/service.py
- [ ] T023 [US1] Implement send_message() with encryption in backend/app/modules/portal/messaging/service.py
- [ ] T024 [US1] Implement get_messages() with decryption in backend/app/modules/portal/messaging/service.py
- [ ] T025 [US2] Implement mark_read() in backend/app/modules/portal/messaging/service.py

### Backend Endpoints

- [ ] T026 [US1] Create GET/POST /requests/{id}/conversation endpoints in backend/app/modules/portal/messaging/router.py
- [ ] T027 [US2] Create GET /conversations endpoint (accountant inbox) in backend/app/modules/portal/messaging/router.py
- [ ] T028 [US1] Create portal messaging endpoints in backend/app/modules/portal/messaging/client_router.py
- [ ] T029 [P] [US1] Write integration tests for request conversations in backend/tests/integration/api/test_messaging.py

### WebSocket Handlers

- [ ] T030 [US1] Implement _handle_send_message in websocket handler in backend/app/modules/portal/messaging/websocket.py

---

## Phase 5: User Story 9 - Real-time Notifications (8 tasks)

**Goal**: Real-time message delivery and notifications
**Independent Test**: Send message → recipient sees notification within 2 seconds

### Backend Real-time

- [ ] T031 [US9] Implement real-time broadcast in send_message() in backend/app/modules/portal/messaging/service.py
- [ ] T032 [US9] Implement typing indicators in websocket handler in backend/app/modules/portal/messaging/websocket.py
- [ ] T033 [US9] Create offline notification queueing in backend/app/modules/portal/messaging/service.py
- [ ] T034 [P] [US9] Write integration tests for real-time delivery in backend/tests/integration/api/test_websocket.py

### Frontend WebSocket

- [ ] T035 [US9] Create useWebSocket hook in frontend/src/hooks/useWebSocket.ts
- [ ] T036 [US9] Create NotificationToast component in frontend/src/components/notifications/NotificationToast.tsx
- [ ] T037 [US9] Create NotificationBell component in frontend/src/components/notifications/NotificationBell.tsx
- [ ] T038 [US9] Integrate WebSocket in portal layout in frontend/src/app/portal/layout.tsx

---

## Phase 6: User Story 1 & 2 - Conversation UI (8 tasks)

**Goal**: Message thread UI for clients and accountants

### Portal (Client) UI

- [ ] T039 [US1] Create MessageThread component in frontend/src/components/messaging/MessageThread.tsx
- [ ] T040 [US1] Create MessageBubble component in frontend/src/components/messaging/MessageBubble.tsx
- [ ] T041 [US1] Create MessageInput component in frontend/src/components/messaging/MessageInput.tsx
- [ ] T042 [US1] Add conversation section to request detail page in frontend/src/app/portal/requests/[id]/page.tsx

### Accountant UI

- [ ] T043 [US2] Create request conversation view in frontend/src/app/(protected)/clients/[id]/requests/[requestId]/chat/page.tsx
- [ ] T044 [US2] Add message indicator to RequestTrackingTable in frontend/src/components/requests/RequestTrackingTable.tsx
- [ ] T045 [US2] Create ConversationList component in frontend/src/components/messaging/ConversationList.tsx
- [ ] T046 [US2] Create useConversation hook in frontend/src/hooks/useConversation.ts

---

## Phase 7: User Story 3 - Request Amendments (6 tasks)

**Goal**: Track request changes after client questions
**Independent Test**: Client asks question → accountant edits request → client sees update

- [ ] T047 [US3] Create RequestAmendmentRepository in backend/app/modules/portal/messaging/repository.py
- [ ] T048 [US3] Implement track_amendment() in DocumentRequestService in backend/app/modules/portal/requests/service.py
- [ ] T049 [US3] Create GET /requests/{id}/amendments endpoint in backend/app/modules/portal/requests/router.py
- [ ] T050 [US3] Show amendment history in request detail in frontend/src/app/portal/requests/[id]/page.tsx
- [ ] T051 [US3] Add "Request Updated" system message on amendment in backend/app/modules/portal/requests/service.py
- [ ] T052 [P] [US3] Write integration tests for amendments in backend/tests/integration/api/test_amendments.py

---

## Phase 8: User Story 4 - BAS Review & Approval (10 tasks)

**Goal**: Client reviews and approves BAS before lodgement
**Independent Test**: BAS ready → client reviews → approves → approval recorded

### Backend Approval Service

- [ ] T053 [US4] Create ApprovalService class in backend/app/modules/portal/approvals/service.py
- [ ] T054 [US4] Implement mark_ready_for_review() in backend/app/modules/portal/approvals/service.py
- [ ] T055 [US4] Implement approve() with audit capture in backend/app/modules/portal/approvals/service.py
- [ ] T056 [US4] Implement retract() with time window in backend/app/modules/portal/approvals/service.py
- [ ] T057 [US4] Create approval endpoints in backend/app/modules/portal/approvals/router.py
- [ ] T058 [P] [US4] Write integration tests for approvals in backend/tests/integration/api/test_approvals.py

### Portal Approval UI

- [ ] T059 [US4] Create BAS review page in frontend/src/app/portal/bas/[period]/review/page.tsx
- [ ] T060 [US4] Create BASReviewCard component in frontend/src/components/approvals/BASReviewCard.tsx
- [ ] T061 [US4] Create ApprovalButton component in frontend/src/components/approvals/ApprovalButton.tsx
- [ ] T062 [US4] Add approval conversation support in backend/app/modules/portal/messaging/service.py

---

## Phase 9: User Story 5 - Approval Dashboard (6 tasks)

**Goal**: Accountant dashboard for tracking approvals
**Independent Test**: Multiple BAS ready → see approval dashboard → send reminders

- [ ] T063 [US5] Create GET /approvals endpoint in backend/app/modules/portal/approvals/router.py
- [ ] T064 [US5] Create GET /approvals/summary endpoint in backend/app/modules/portal/approvals/router.py
- [ ] T065 [US5] Create POST /bas/{id}/remind endpoint in backend/app/modules/portal/approvals/router.py
- [ ] T066 [US5] Create approvals dashboard page in frontend/src/app/(protected)/approvals/page.tsx
- [ ] T067 [US5] Create ApprovalDashboard component in frontend/src/components/approvals/ApprovalDashboard.tsx
- [ ] T068 [P] [US5] Write integration tests for approval dashboard in backend/tests/integration/api/test_approvals.py

---

## Phase 10: User Story 6 & 7 - General Messaging (8 tasks)

**Goal**: Non-request messaging and unified inbox
**Independent Test**: Client sends general message → accountant sees in inbox

### Backend

- [ ] T069 [US6] Implement create_general_conversation() in backend/app/modules/portal/messaging/service.py
- [ ] T070 [US6] Create portal general messaging endpoints in backend/app/modules/portal/messaging/client_router.py
- [ ] T071 [US7] Implement inbox aggregation in backend/app/modules/portal/messaging/service.py
- [ ] T072 [P] [US6] Write integration tests for general messaging in backend/tests/integration/api/test_messaging.py

### Frontend

- [ ] T073 [US6] Create portal messages page in frontend/src/app/portal/messages/page.tsx
- [ ] T074 [US7] Create accountant inbox page in frontend/src/app/(protected)/inbox/page.tsx
- [ ] T075 [US7] Create InboxList component in frontend/src/components/messaging/InboxList.tsx
- [ ] T076 [US7] Add unread count to header in frontend/src/components/layout/Header.tsx

---

## Phase 11: User Story 8 & 10 - Completion & Attachments (8 tasks)

**Goal**: Request completion confirmation and message attachments
**Independent Test**: Complete request with note → client notified

### Completion Confirmation

- [ ] T077 [US8] Add completion note support in backend/app/modules/portal/requests/service.py
- [ ] T078 [US8] Add re-open request functionality in backend/app/modules/portal/requests/service.py
- [ ] T079 [US8] Create completion confirmation UI in frontend/src/components/requests/CompleteRequestModal.tsx

### Attachments

- [ ] T080 [US10] Create MessageAttachment repository in backend/app/modules/portal/messaging/repository.py
- [ ] T081 [US10] Implement file upload for messages in backend/app/modules/portal/messaging/service.py
- [ ] T082 [US10] Create AttachmentPicker component in frontend/src/components/messaging/AttachmentPicker.tsx
- [ ] T083 [US10] Add attachment display to MessageBubble in frontend/src/components/messaging/MessageBubble.tsx
- [ ] T084 [P] [US10] Write integration tests for attachments in backend/tests/integration/api/test_messaging.py

---

## Phase 12: Notification Preferences (4 tasks)

**Goal**: User notification settings

- [ ] T085 Create NotificationPreferenceRepository in backend/app/modules/portal/messaging/repository.py
- [ ] T086 Create GET/PATCH /settings/notifications endpoints in backend/app/modules/portal/messaging/router.py
- [ ] T087 Create notification preferences UI in frontend/src/app/(protected)/settings/notifications/page.tsx
- [ ] T088 Add DND (Do Not Disturb) logic to notification service in backend/app/modules/notifications/service.py

---

## Parallel Execution Guide

### Maximum Parallelism by Phase

| Phase | Parallel Groups |
|-------|-----------------|
| Phase 1 | T001+T002+T003, T004 → T005, T006 |
| Phase 2 | T007-T11 → T12-T15 → T16 |
| Phase 3 | T017-T18, T19+T20 |
| Phase 4 | T021-T25, T26-T28 → T29, T30 |
| Phase 5 | T031-T34, T35-T38 |
| Phase 6 | T039-T42, T43-T46 |
| Phase 7 | T047-T51 → T52 |
| Phase 8 | T053-T57 → T58, T59-T62 |
| Phase 9 | T063-T65, T66-T67 → T68 |
| Phase 10 | T069-T72, T73-T76 |
| Phase 11 | T077-T79, T080-T83 → T84 |
| Phase 12 | T085-T88 |

### Independent Work Streams

```
Stream A (WebSocket): Phase 2 → Phase 5
Stream B (Conversations): Phase 3 → Phase 4 → Phase 6 → Phase 7
Stream C (Approvals): Phase 8 → Phase 9
Stream D (General Messaging): Phase 10 (after Stream B)
Stream E (Completion/Attachments): Phase 11 (after Stream B)
Stream F (Preferences): Phase 12 (after Phase 5)
```

---

## MVP Scope

**Minimum Viable Product**: User Stories 1, 2, 4, 9 (Phases 1-6, 8)

| Phase | Tasks | Description |
|-------|-------|-------------|
| 1 | T001-T006 | Setup |
| 2 | T007-T016 | WebSocket Infrastructure |
| 3 | T017-T020 | Message Encryption |
| 4 | T021-T030 | Request Conversations |
| 5 | T031-T038 | Real-time Notifications |
| 6 | T039-T046 | Conversation UI |
| 8 | T053-T062 | BAS Approval |

**MVP Task Count**: 56 tasks

**Post-MVP**:
- Phase 7: Request Amendments (T047-T052)
- Phase 9: Approval Dashboard (T063-T068)
- Phase 10: General Messaging (T069-T076)
- Phase 11: Completion & Attachments (T077-T084)
- Phase 12: Notification Preferences (T085-T088)

---

## Validation Checklist

- [x] All 88 tasks follow checklist format
- [x] Each user story phase is independently testable
- [x] Dependencies are correctly sequenced
- [x] Parallel opportunities identified
- [x] MVP scope defined (56 tasks)
- [x] File paths specified for all implementation tasks
