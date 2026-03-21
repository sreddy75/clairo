# Implementation Plan: Email Integration & OAuth

**Branch**: `026-email-integration-oauth` | **Date**: 2026-01-01 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/026-email-integration-oauth/spec.md`

## Summary

Enable OAuth-based email connection to Gmail and Microsoft 365 for automatic capture of ATO correspondence. This is the foundation for ATOtrack - ensuring accounting practices never miss an ATO deadline or notice.

**Technical Approach**:
- Add new module: `modules/email/` for email integration
- Implement OAuth 2.0 flows for Gmail and Microsoft Graph APIs
- Store encrypted tokens with automatic refresh
- Background sync via Celery for email polling
- Email forwarding fallback via inbound email processing
- Filter to only capture @ato.gov.au emails

---

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: FastAPI, SQLAlchemy 2.x, Pydantic v2, httpx, cryptography
**Storage**: PostgreSQL 16 with encrypted token columns
**Testing**: pytest, pytest-asyncio, respx for mocking HTTP
**Target Platform**: AWS ECS/Fargate (Sydney region)
**Project Type**: Web application (backend + frontend)
**Performance Goals**: Initial sync <10 min, incremental sync <15 min latency
**Constraints**: Token security (AES-256), email privacy, 7-year retention
**Scale/Scope**: Up to 1,000 emails/day per tenant

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Compliance | Notes |
|-----------|------------|-------|
| **Modular Monolith** | ✅ PASS | New `modules/email/` module |
| **Repository Pattern** | ✅ PASS | Repositories for connections, emails |
| **Multi-tenancy (RLS)** | ✅ PASS | All tables include `tenant_id` |
| **Audit-First** | ✅ PASS | Audit events for connections and syncs |
| **Type Hints** | ✅ PASS | Pydantic schemas, typed functions |
| **Test-First** | ✅ PASS | Mock OAuth providers, test token refresh |
| **API Conventions** | ✅ PASS | RESTful endpoints for connection management |
| **External Integration Pattern** | ✅ PASS | Token encryption, error handling, retry |

**No violations requiring justification.**

---

## Project Structure

### Documentation (this feature)

```text
specs/026-email-integration-oauth/
├── plan.md              # This file
├── research.md          # OAuth API research
├── data-model.md        # Entity definitions
├── quickstart.md        # Developer guide
├── contracts/           # OpenAPI specs
│   └── email-api.yaml
└── tasks.md             # Implementation tasks
```

### Source Code (repository root)

```text
backend/
├── app/
│   └── modules/
│       └── email/                    # NEW MODULE
│           ├── __init__.py
│           ├── models.py             # EmailConnection, RawEmail, etc.
│           ├── schemas.py            # Pydantic schemas
│           ├── repository.py         # Connection and email repositories
│           ├── service.py            # Email sync service
│           ├── router.py             # API endpoints
│           ├── oauth/
│           │   ├── __init__.py
│           │   ├── gmail.py          # Gmail OAuth client
│           │   ├── microsoft.py      # Microsoft Graph OAuth client
│           │   └── base.py           # OAuth provider interface
│           ├── sync/
│           │   ├── __init__.py
│           │   ├── gmail_sync.py     # Gmail sync implementation
│           │   ├── microsoft_sync.py # Microsoft sync implementation
│           │   └── scheduler.py      # Celery tasks for sync
│           ├── ingest/
│           │   ├── __init__.py
│           │   └── forwarding.py     # Inbound email processing
│           └── crypto.py             # Token encryption utilities
│
└── tests/
    ├── unit/
    │   └── modules/
    │       └── email/
    │           ├── test_oauth_gmail.py
    │           ├── test_oauth_microsoft.py
    │           ├── test_sync_service.py
    │           └── test_token_refresh.py
    └── integration/
        └── api/
            └── test_email_connections.py

frontend/
└── src/
    ├── app/
    │   └── (protected)/
    │       └── settings/
    │           └── email-connections/
    │               └── page.tsx
    ├── components/
    │   └── email/
    │       ├── ConnectionCard.tsx
    │       ├── ConnectGmailButton.tsx
    │       ├── ConnectOutlookButton.tsx
    │       └── ConnectionStatus.tsx
    └── lib/
        └── api/
            └── email.ts
```

**Structure Decision**: Creates new `modules/email/` module to maintain separation from Xero integration.

---

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      EMAIL INTEGRATION ARCHITECTURE                      │
│                                                                         │
│  External Providers                                                     │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐               │
│  │   Gmail     │     │  Microsoft  │     │  Forwarding │               │
│  │   OAuth     │     │   Graph     │     │   Ingest    │               │
│  └──────┬──────┘     └──────┬──────┘     └──────┬──────┘               │
│         │                   │                   │                       │
│         └───────────────────┴───────────────────┘                       │
│                             │                                           │
│                             ▼                                           │
│                   ┌─────────────────┐                                   │
│                   │  Email Module   │                                   │
│                   │  ┌───────────┐  │                                   │
│                   │  │ OAuth     │  │  ◄── Handles OAuth flows         │
│                   │  │ Clients   │  │                                   │
│                   │  └─────┬─────┘  │                                   │
│                   │        │        │                                   │
│                   │  ┌─────▼─────┐  │                                   │
│                   │  │  Sync     │  │  ◄── Polls for new emails        │
│                   │  │  Service  │  │                                   │
│                   │  └─────┬─────┘  │                                   │
│                   │        │        │                                   │
│                   │  ┌─────▼─────┐  │                                   │
│                   │  │  Crypto   │  │  ◄── Encrypts/decrypts tokens    │
│                   │  │  Service  │  │                                   │
│                   │  └───────────┘  │                                   │
│                   └────────┬────────┘                                   │
│                            │                                            │
│                            ▼                                            │
│                   ┌─────────────────┐                                   │
│                   │   PostgreSQL    │                                   │
│                   │ (encrypted cols)│                                   │
│                   └─────────────────┘                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

### OAuth Flow

```
OAUTH 2.0 AUTHORIZATION CODE FLOW
═══════════════════════════════════════════════════════════════════════════

User                    Clairo                   Google/Microsoft
  │                        │                            │
  │  1. Click "Connect"    │                            │
  ├───────────────────────►│                            │
  │                        │                            │
  │                        │  2. Generate state token   │
  │                        │     Store in session       │
  │                        │                            │
  │  3. Redirect to OAuth  │                            │
  │◄───────────────────────┤                            │
  │                        │                            │
  │  4. Login & Consent    │                            │
  ├────────────────────────┼───────────────────────────►│
  │                        │                            │
  │  5. Redirect with code │                            │
  │◄───────────────────────┼────────────────────────────┤
  │                        │                            │
  │  6. POST code to Clairo                            │
  ├───────────────────────►│                            │
  │                        │                            │
  │                        │  7. Exchange code for tokens
  │                        ├───────────────────────────►│
  │                        │                            │
  │                        │  8. Access + Refresh tokens│
  │                        │◄───────────────────────────┤
  │                        │                            │
  │                        │  9. Encrypt & store tokens │
  │                        │     Create EmailConnection │
  │                        │                            │
  │  10. Show success      │                            │
  │◄───────────────────────┤                            │
  │                        │                            │
  │                        │  11. Trigger initial sync  │
  │                        │      (Celery task)         │
```

### Email Sync Flow

```
EMAIL SYNC STRATEGY
═══════════════════════════════════════════════════════════════════════════

INITIAL BACKFILL
─────────────────
1. Query emails from last 12 months
2. Filter: from @ato.gov.au only
3. Paginate through results (100 per batch)
4. Store raw emails with metadata
5. Mark sync cursor (historyId / deltaToken)

INCREMENTAL SYNC (Every 15 minutes)
───────────────────────────────────
1. Check token expiry, refresh if needed
2. Query changes since cursor
3. Filter new ATO emails
4. Store new emails
5. Update sync cursor

TOKEN REFRESH (Before expiry)
─────────────────────────────
1. Celery beat checks tokens expiring in <1 hour
2. Use refresh token to get new access token
3. Update encrypted tokens in database
4. If refresh fails → mark connection as EXPIRED
```

### Entity Relationships

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       ENTITY RELATIONSHIPS                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Tenant                                                                 │
│    │                                                                    │
│    └──► EmailConnection (1:N)                                          │
│              │                                                          │
│              ├──► EmailSyncJob (1:N)                                   │
│              │                                                          │
│              └──► RawEmail (1:N)                                       │
│                       │                                                 │
│                       └──► EmailAttachment (1:N)                       │
│                                                                         │
│  Note: RawEmail will be consumed by Spec 027 (ATO Parsing)             │
│        and linked to ATOCorrespondence and Client                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### Connection Creation Flow

```
1. User clicks "Connect Gmail/Outlook"
   │
   ▼
2. Frontend redirects to:
   GET /api/v1/email/oauth/{provider}/authorize
   │
   ▼
3. Backend generates state token, stores in Redis
   │
   ▼
4. Backend returns redirect URL to OAuth provider
   │
   ▼
5. User completes OAuth consent
   │
   ▼
6. Provider redirects to callback with code
   GET /api/v1/email/oauth/{provider}/callback?code=...&state=...
   │
   ▼
7. Backend validates state, exchanges code for tokens
   │
   ▼
8. Backend encrypts tokens, creates EmailConnection
   │
   ▼
9. Backend triggers initial sync (Celery task)
   │
   ▼
10. Frontend polls for sync status
```

### Email Sync Flow

```
1. Celery beat triggers sync task every 15 minutes
   │
   ▼
2. For each ACTIVE connection:
   │
   ├──► Check token expiry, refresh if needed
   │
   ├──► Query email provider for changes since cursor
   │    Gmail: GET /gmail/v1/users/me/history?startHistoryId=...
   │    Microsoft: GET /me/mailFolders/inbox/messages/delta?$deltatoken=...
   │
   ├──► Filter to @ato.gov.au emails only
   │
   ├──► For each new email:
   │    ├──► Store email metadata
   │    ├──► Store email body (encrypted at rest)
   │    ├──► Store attachment references
   │    └──► Emit email.received event
   │
   └──► Update sync cursor
   │
   ▼
3. Mark sync job complete
```

---

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| OAuth Library | authlib | Well-maintained, supports Gmail + Microsoft |
| Token Encryption | AES-256-GCM | Industry standard, key in env var |
| Sync Method | Polling (15 min) | Simpler than webhooks, acceptable latency |
| Email Storage | Full body stored | Required for parsing by Spec 027 |
| Attachment Handling | Metadata + on-demand | Avoid storage bloat, download when needed |
| Forwarding Fallback | SES/Postmark inbound | Organizations that can't use OAuth |

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Token theft | AES-256 encryption, key rotation capability |
| Rate limiting by providers | Respect rate limits, exponential backoff |
| OAuth consent revocation | Handle 401s gracefully, notify user |
| Large email volumes | Pagination, background processing |
| Provider API changes | Abstract provider-specific code, monitor deprecations |
| Forwarding abuse | Validate sender domain, rate limit inbound |

---

## Dependencies

### Internal Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| Core Auth | ✅ Complete | User authentication for protected endpoints |
| Celery Setup | ✅ Complete | Background task infrastructure |
| Redis | ✅ Complete | OAuth state storage |
| Spec 027 | Dependent | Will consume RawEmail entities |

### External Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| Google Gmail API | v1 | Email access |
| Microsoft Graph API | v1.0 | Email access |
| authlib | 1.x | OAuth 2.0 client |
| cryptography | 41+ | Token encryption |

---

## Phase References

- **Phase 0**: See [research.md](./research.md) for OAuth API research
- **Phase 1**: See [data-model.md](./data-model.md) for entity definitions
- **Phase 1**: See [contracts/email-api.yaml](./contracts/email-api.yaml) for API specs
- **Phase 1**: See [quickstart.md](./quickstart.md) for developer guide
