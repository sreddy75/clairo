# Clairo — Technical Debt Review

**Date:** 2026-02-08
**Scope:** Full codebase (backend, frontend, tests, database/config, architecture)
**Method:** 5 parallel automated code analysis agents

---

## Executive Summary

This review identified **101+ findings** across the Clairo codebase, including critical security gaps in tenant isolation, massive test coverage shortfalls, and deep architectural coupling that will impede future development velocity.

| Severity | Count | Description |
|----------|-------|-------------|
| **Critical** | 11 | Security vulnerabilities, data isolation failures, broken core flows |
| **High** | 26 | Missing tests, architectural debt, hardcoded secrets, broken patterns |
| **Medium** | 38 | Inconsistent patterns, missing features, code quality issues |
| **Low** | 26+ | Minor style issues, documentation drift, cleanup items |

The top 3 priorities are:
1. **Fix tenant isolation in knowledge base** — unauthenticated, unscoped access to all tenant data
2. **Add RLS policies to 25+ tables** — database-level tenant isolation is missing for majority of newer tables
3. **Guard production secrets** — JWT key, encryption key, and MinIO credentials have exploitable defaults

---

## Table of Contents

1. [Critical Findings](#1-critical-findings)
2. [Backend Code Quality](#2-backend-code-quality)
3. [Frontend Code Quality](#3-frontend-code-quality)
4. [Test Coverage](#4-test-coverage)
5. [Database & Configuration](#5-database--configuration)
6. [Architecture](#6-architecture)
7. [Recommended Quick Wins](#7-recommended-quick-wins)
8. [Prioritised Action Plan](#8-prioritised-action-plan)

---

## 1. Critical Findings

These items represent active security risks or broken core functionality.

### 1.1 Knowledge Base Has Zero Tenant Isolation

**Files:** `backend/app/modules/knowledge/models.py`, `knowledge/router.py`, `auth/middleware.py:41`

All 5 knowledge models (`KnowledgeSource`, `ContentChunk`, `IngestionJob`, `ChatConversation`, `ChatMessage`) lack a `tenant_id` column entirely. The knowledge router has zero authentication dependencies — it is explicitly excluded from auth middleware:

```python
# auth/middleware.py:41
"/api/v1/admin/knowledge",  # Knowledge base admin endpoints (dev only - add auth later)
```

**Impact:** Any unauthenticated user can access, modify, or delete any tenant's knowledge base, chat history, and ingested content. This endpoint allows initialising/resetting vector collections, CRUD on knowledge sources, content ingestion, search, and chat.

### 1.2 25+ Tenant-Scoped Tables Missing RLS Policies

**Tables WITH RLS (~15):** `practice_users`, `invitations`, `xero_connections`, `xero_sync_jobs`, `xero_clients`, `xero_invoices`, `xero_bank_transactions`, `xero_accounts`, `xero_employees`, `xero_pay_runs`, `quality_scores`, `quality_issues`, `bas_periods`, `bas_sessions`, `bas_calculations`, `bas_adjustments`, `bas_audit_log`, `client_data_aggregations`, `agent_queries`, `agent_escalations`, `insights`, `xpm_clients`

**Tables WITHOUT RLS (25+):**

| Table | Migration |
|-------|-----------|
| `action_items` | `019_action_items.py` |
| `triggers`, `trigger_executions` | `021_triggers.py` |
| `billing_events` | `023_billing_subscription.py` |
| `usage_snapshots`, `usage_alerts` | `025_usage_tracking.py` |
| `onboarding_progress`, `bulk_import_jobs`, `email_drips` | `026_onboarding.py` |
| `feature_flag_overrides` | `029_feature_flag_overrides.py` |
| `xero_reports` | `030_xero_reports.py` |
| `xero_transactions` | `031_xero_transactions.py` |
| `xero_fixed_assets`, `xero_purchase_orders`, etc. | `032_spec_025*.py` |
| `portal_invitations`, `portal_sessions`, `document_requests`, etc. (8 tables) | `033_spec_030*.py` |
| `push_subscriptions`, `webauthn_credentials`, etc. (4 tables) | `034_spec_032*.py` |
| `notifications` | `035_notifications.py` |
| `bulk_import_organizations` | `20260208_*.py` |

### 1.3 JWT Secret Has Exploitable Default

**File:** `backend/app/config.py:189-191`

```python
secret_key: SecretStr = Field(
    default=SecretStr("change-me-in-production-use-openssl-rand-hex-32"),
)
```

No runtime validation rejects this default in production. If `JWT_SECRET_KEY` is unset, all JWTs are forgeable.

### 1.4 Onboarding OAuth Flow Is a Complete Stub

| File | Line(s) | Issue |
|------|---------|-------|
| `onboarding/router.py` | 295-308 | Xero callback returns hardcoded `{"status": "ok"}`, ignores `code` and `state` |
| `onboarding/tasks.py` | 63-78 | Bulk import task simulates success with `time.sleep()`, never calls Xero |
| `onboarding/service.py` | 313-314 | `complete_xero_connect()` never exchanges OAuth code for tokens |

### 1.5 Frontend API Calls With No Auth / Broken URLs

| File | Line | Issue | Severity |
|------|------|-------|----------|
| `queries/page.tsx` | 187 | API call with **no Authorization header** in a `(protected)` route | Critical |
| `lib/api/agents.ts` | 102 | `process.env.NEXT_PUBLIC_API_URL` without fallback — produces `undefined/api/v1/...` | Critical |
| `clients/[id]/reports/page.tsx` | 91 | Same missing fallback | Critical |
| `clients/[id]/assets/page.tsx` | 79 | Same missing fallback | Critical |
| `clients/[id]/purchase-orders/page.tsx` | 46 | Same missing fallback | Critical |

---

## 2. Backend Code Quality

### 2.1 Module Pattern Violations

The documented pattern requires `models.py`, `schemas.py`, `repository.py`, `service.py`, `router.py` per module. Several modules deviate:

| Module | models | schemas | repository | service | router | Severity |
|--------|--------|---------|------------|---------|--------|----------|
| `queries` | - | present | - | - | present | High |
| `productivity` | - | - | - | - | present | High |
| `clients` | - | present | present | present | present | Medium |
| `action_items` | present | present | - | present | present | Medium |
| `triggers` | present | present | - | present | present | Medium |
| `agents` | present | present | - | - | present | Medium |
| `knowledge` | present | present | present | - | present | Medium |
| `notifications` | present | present | - | present | present | Medium |
| `dashboard` | - | present | present | present | present | Low |

### 2.2 Error Handling

No `HTTPException` found in any `service.py` — this is clean and follows the project standard. Domain exceptions are properly used in services with HTTP translation happening at the router layer.

`HTTPException` in non-router files is limited to middleware/dependency layers (`auth/webhooks.py`, `auth/permissions.py`, `portal/auth/dependencies.py`) — acceptable.

### 2.3 TODO/FIXME/HACK Comments (32 total)

#### Critical — Incomplete Core Features

| File | Line(s) | Comment |
|------|---------|---------|
| `onboarding/tasks.py` | 65-67 | `# TODO: Fetch client from XPM/Xero` / `Create client record` / `Sync transactions` |
| `onboarding/router.py` | 305-308 | `# TODO: Parse tenant_id from state` / `Complete OAuth flow` |
| `onboarding/service.py` | 313-314 | `# TODO: Exchange code for tokens` / `Detect XPM vs Xero Accounting` |
| `integrations/xero/router.py` | 4162 | `# TODO: Queue Celery task for retry (T020)` — retry endpoint is a no-op |

#### High — Missing Integration Points

| File | Line(s) | Comment |
|------|---------|---------|
| `onboarding/tasks.py` | 190, 200, 248, 258 | `# TODO: Send email via NotificationService` — 4 locations that log but never send |
| `onboarding/service.py` | 77-78 | `# TODO: Emit OnboardingStartedEvent` / `Send welcome email` |
| `onboarding/service.py` | 424, 593 | `# TODO: Queue Celery task` / `Send email via NotificationService` |
| `portal/auth/router.py` | 121 | `# TODO: Implement email lookup and sending in Phase 8` — magic link is a no-op |
| `portal/requests/router.py` | 1197, 1222 | `# TODO: Load/Save from tenant settings table` — reminder settings hardcoded |
| `portal/dashboard/service.py` | 167 | `# TODO: Integrate with BAS module` — returns hardcoded BAS status |

#### Medium — Tracking/Analytics Stubs

| File | Line(s) | Comment |
|------|---------|---------|
| `admin/service.py` | 309-310, 843, 923-929, 958 | Multiple `# TODO: Track ...` / `Integrate with usage tracking` — all return 0 |

### 2.4 Hardcoded Values

#### Production URLs That Should Be Config

| File | Line | Value | Severity |
|------|------|-------|----------|
| `auth/service.py` | 1132 | `https://app.clairo.com.au/invitation?token={token}` | High |
| `onboarding/router.py` | 278 | `http://localhost:3000` as fallback origin | High |
| `notifications/email_service.py` | 133, 321, 366 | `https://app.clairo.com.au/dashboard`, `/settings/billing` | Medium |
| `auth/clerk.py` | 427, 487 | `https://api.clerk.com/v1/users/{clerk_id}` | Medium |
| `notifications/push/webauthn_service.py` | 100 | `os.getenv()` bypassing Pydantic Settings | Low |

#### Magic Numbers

| File | Line(s) | Value | Severity |
|------|---------|-------|----------|
| `integrations/xero/service.py` | 1245, 1350, 1430, 1510, 1600, 1676 | `100` — Xero page size hardcoded in 6 pagination checks | Medium |
| `integrations/xero/service.py` | 4194-4200, 4357-4363 | Aging bucket boundaries (`30/60/90` days) duplicated | Medium |
| `billing/service.py` | 284, 353-378 | Usage alert thresholds (`80/90/100%`) | Low |

### 2.5 Async Issues

#### Deprecated `asyncio.get_event_loop()` (High)

| File | Line(s) |
|------|---------|
| `onboarding/tasks.py` | 36, 154, 219 |
| `tasks/portal/send_bulk_requests.py` | 59 |
| `tasks/portal/auto_reminders.py` | 59, 227 |
| `knowledge/scrapers/base.py` | 301, 305 |

Deprecated since Python 3.10. Unreliable in Celery worker context. Replace with `asyncio.run()`.

#### `os.getenv()` Bypassing Settings (Medium)

| File | Line(s) | Variables |
|------|---------|-----------|
| `notifications/push/service.py` | 55-56, 71 | `VAPID_PRIVATE_KEY`, `VAPID_PUBLIC_KEY`, `VAPID_CONTACT_EMAIL` |
| `notifications/push/webauthn_service.py` | 90, 95, 100 | `WEBAUTHN_RP_ID`, `WEBAUTHN_RP_NAME`, `WEBAUTHN_RP_ORIGIN` |

### 2.6 Other Backend Issues

| Issue | File(s) | Severity |
|-------|---------|----------|
| `if False:` instead of `TYPE_CHECKING` | `auth/service.py:66`, `core/dependencies.py:430` | Low |
| Silent exception swallowing (`except: pass`) | `notifications/push/webauthn_service.py:228-232`, `xero/service.py:523-525`, `core/audit.py:548-550` | Medium |
| Duplicated `get_quarter_dates()` | `clients/service.py:32` vs `quality/service.py:40` | Medium |
| Duplicated email template constants | `notifications/templates.py:32-33` vs `portal/notifications/templates.py:42-43` | Low |

---

## 3. Frontend Code Quality

### 3.1 TypeScript Strictness

#### Unsafe `{} as T` in API Client (High)

**File:** `frontend/src/lib/api-client.ts`
- Line 140: `return {} as T` for 204 No Content responses
- Line 148: `return {} as T` for non-JSON content types

Returns empty object cast to generic type — callers accessing properties will get `undefined` at runtime.

#### Unsafe Type Assertions (Medium)

| File | Line(s) | Issue |
|------|---------|-------|
| `hooks/useNetworkStatus.ts` | 45-47, 83-85 | `(navigator as any).connection` — non-standard API |
| `components/pwa/InstallPrompt.tsx` | 57, 75 | `(window.navigator as any).standalone`, `!(window as any).MSStream` |
| `clients/[id]/requests/page.tsx` | 187-188 | `.toLowerCase() as RequestStatus` — unvalidated cast |
| `lib/api/agents.ts` | 140 | `JSON.parse(data) as AgentStreamEvent` — no runtime validation |
| `lib/xero-reports.ts` | 236 | `(responseData.detail || responseData) as RateLimitError` |

#### Placeholder Types File (Medium)

**File:** `frontend/src/types/api.ts:10-11`

Comment says "Placeholder types until generated from backend" and "npm run generate-api-types". Contains only 3 minimal route definitions. Auto-gen has never been run.

### 3.2 Duplicated API Base URL (High)

`process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'` is independently defined in **10+ files**:

| File | Variable Name |
|------|--------------|
| `lib/api-client.ts:8` | `API_BASE_URL` |
| `lib/api.ts:15` | inline `baseUrl` |
| `lib/api/billing.ts:27` | `API_BASE` |
| `lib/api/portal.ts:8` | `API_BASE_URL` |
| `lib/api/onboarding.ts:7` | `API_BASE` |
| `lib/api/admin.ts:33` | `API_BASE` |
| `lib/api/requests.ts:11` | `API_BASE_URL` |
| `lib/api/knowledge.ts` | 5 inline references |
| `lib/bas.ts:733` | `API_BASE_URL` |
| `app/onboarding/xero/callback/page.tsx:7` | `API_BASE` |

### 3.3 Large Components

20+ components exceed 300 lines. The worst offenders:

| File | Lines | Description |
|------|-------|-------------|
| `clients/[id]/page.tsx` | **2,349** | 8 fetch functions, 15+ state vars, 8 tab renders |
| `components/bas/BASTab.tsx` | **1,872** | Entire BAS workflow UI |
| `app/(protected)/assistant/page.tsx` | **1,571** | Chat UI, client selection, action items |
| `app/page.tsx` | **1,128** | Landing/marketing page |
| `lib/bas.ts` | **1,043** | BAS utility/API library |
| `lib/api/knowledge.ts` | **930** | Knowledge base API client |
| `lib/api/portal.ts` | **914** | Portal API client |
| `lib/api/requests.ts` | **889** | Document requests API |
| `app/(protected)/lodgements/page.tsx` | **860** | Lodgements workboard |
| `app/onboarding/import-clients/page.tsx` | **859** | Client import onboarding |
| `app/(protected)/notifications/page.tsx` | **842** | Notifications page |
| `app/(protected)/dashboard/page.tsx` | **788** | Dashboard page |

### 3.4 Missing Error Handling

#### Silent `console.error` With No User Feedback (Medium)

8 fetch functions in `clients/[id]/page.tsx` catch errors but only call `console.error` — no error state is set for the UI:

- Line 391: `fetchContacts`
- Line 419: `fetchInvoices`
- Line 447: `fetchTransactions`
- Line 476: `fetchEmployees`
- Line 504: `fetchPayRuns`
- Line 525: `fetchCreditNotes`

Also in `hooks/useClientXeroConnection.ts` (lines 120-121, 140-141).

#### Silent Error Swallowing in Agent Stream (High)

`lib/api/agents.ts:149-156` — JSON parse errors are silently skipped with comment `// Skip non-JSON lines silently`. Actual parse errors or unexpected data is lost.

### 3.5 Incomplete Implementations

| File | Line(s) | Issue | Severity |
|------|---------|-------|----------|
| `components/productivity/DaySummaryModal.tsx` | 134-143 | `export`, `createTask`, `custom` handlers are `console.log` stubs | High |
| `app/onboarding/page.tsx` | 10-27 | Always redirects to tier-selection, never fetches progress | Medium |
| `clients/[id]/reports/page.tsx` | 385-394 | "Report viewer coming soon" with raw `JSON.stringify` | Medium |
| `settings/integrations/page.tsx` | 309-327 | MYOB integration is "Coming Soon" placeholder | Medium |
| `stores/example.store.ts` | 1-56 | Boilerplate Zustand store, not imported anywhere | Low |

### 3.6 Excessive Console Logging

151 `console.log/warn/error` calls found across 54 files. Many appear to be development-time debug aids that should be removed or replaced with a logging framework.

---

## 4. Test Coverage

### 4.1 Backend Module Coverage

| Module | Has Router | Unit Tests | Integration Tests | Verdict |
|--------|-----------|------------|-------------------|---------|
| `auth` | Yes | 6 files | 1 file (3+ tests) | Covered |
| `integrations/xero` | Yes | 7 files | 3 files | Covered |
| `billing` | Yes | 3 files | 1 file | Covered |
| `dashboard` | Yes | 1 file | 1 file | Covered |
| `onboarding` | Yes | 1 file | 1 file | Covered |
| `portal` | Yes (5 sub-routers) | 3 files | 5 files | Covered |
| `bas` | Yes | 1 file | 1 file | Partial |
| `knowledge` | Yes | 1 file | 0 files | **Gaps** |
| `admin` | Yes | 0 files | 1 file | **Gaps** |
| **`insights`** | Yes | **0 files** | **0 files** | **NO TESTS** |
| **`triggers`** | Yes | **0 files** | **0 files** | **NO TESTS** |
| **`quality`** | Yes | **0 files** | **0 files** | **NO TESTS** |
| **`agents`** | Yes | **0 files** | **0 files** | **NO TESTS** |
| **`clients`** | Yes | **0 files** | 1 file | **Unit gap** |
| **`notifications`** | Yes (2 routers) | **0 files** | **0 files** | **NO TESTS** |
| **`action_items`** | Yes | **0 files** | **0 files** | **NO TESTS** |
| **`queries`** | Yes | **0 files** | **0 files** | **NO TESTS** |
| **`productivity`** | Yes | **0 files** | **0 files** | **NO TESTS** |

**9 modules with routers have zero unit tests.** The project target is 80% unit coverage.

### 4.2 Integration Test Gaps

**10 routers with zero integration tests** (target is 100%):

- `insights/router.py`
- `triggers/router.py`
- `quality/router.py`
- `agents/router.py`
- `notifications/router.py`
- `notifications/push/router.py`
- `action_items/router.py`
- `queries/router.py`
- `productivity/router.py`
- `knowledge/router.py` + `knowledge/client_chat_router.py`

### 4.3 Contract Test Gaps

Only 1 contract test file exists: `tests/contract/adapters/test_xero_bulk_connections.py`

Covers: `GET /connections` response, token exchange response, rate limit headers.

**Missing contract tests for:** Xero Contacts, Invoices, Bank Transactions, Accounts, Credit Notes, Reports (6 report types), Clerk webhooks, Stripe webhooks.

### 4.4 Frontend Tests

**2 test files for 90+ components, 20 hooks, all pages, all API clients, all stores.**

Only tested:
- `UpgradePrompt.test.tsx` — 11 test cases
- `useTier.test.ts` — 10 test cases

Vitest + jsdom + React Testing Library is configured and working. Zero E2E tests (no Playwright/Cypress).

### 4.5 Celery Task Tests

**15 task files with zero dedicated tests.** Tasks cover aggregation, triggers, BAS, reports, scheduler, insights, quality, knowledge, usage, portal auto-reminders, portal bulk requests, and xero sync.

### 4.6 Test Quality Issues

#### Skipped Tests (High)

`tests/unit/modules/integrations/xero/test_service.py` — 7 skipped tests with `pass` bodies. All were placeholders from early development; the functionality was implemented but tests were never written.

#### E2E Tests That Aren't E2E (High)

`tests/e2e/test_xero_sync_e2e.py` — Tests in the `e2e/` directory never make HTTP requests. They test in-memory data structures, dict key existence, and enum value assertions. Should be recategorised as unit tests.

#### Tautological Tests (Medium)

Several tests verify local Python arithmetic or hardcoded values rather than production code:
- `test_bulk_import_service.py:815-885` — Tests `isinstance(s, str)` on string literals, arithmetic on local variables
- `test_xero_sync_e2e.py:341-363` — Tests `hasattr` on model class (only fails if model definition deleted)

### 4.7 Test Configuration

- pytest markers properly defined: `unit`, `integration`, `e2e`, `slow`
- `asyncio_mode = "auto"` configured
- Coverage target: `fail_under = 80` — almost certainly not being met
- `conftest.py` missing portal and admin model imports (lines 39-51) — may cause relationship resolution failures

---

## 5. Database & Configuration

### 5.1 Model Consistency

#### Inconsistent Base Class Usage

Many models bypass `BaseModel` (which provides `id` + timestamps via `TimestampMixin`) and use `Base` directly:

| Module | Models Using `Base` Only |
|--------|--------------------------|
| quality | `QualityScore`, `QualityIssue` |
| knowledge | All 5 models |
| insights | `Insight` |
| triggers | `Trigger`, `TriggerExecution` |
| action_items | `ActionItem` |
| billing | `BillingEvent`, `UsageSnapshot`, `UsageAlert` |
| notifications | `Notification` |
| notifications/push | All 4 models |
| portal | `RequestEvent` |
| auth | `Invitation` |

#### Quality Model Timestamps Will Fail on Insert (High)

`backend/app/modules/quality/models.py` — `created_at` and `updated_at` are `nullable=False` but have no `server_default=func.now()`. Will fail on insert if not explicitly set in application code. Also uses string `server_default="gen_random_uuid()"` instead of `sa.text(...)` for UUID primary keys.

#### Push Models Use Legacy Column() Style (Medium)

`notifications/push/models.py` — All 4 models use legacy `Column()` syntax instead of modern `Mapped[type] = mapped_column()` used throughout the rest of the codebase.

### 5.2 Migration Health

#### Inconsistent Naming (High)

Three naming schemes coexist:
1. Sequential numeric: `001_auth_multitenancy` ... `035_notifications` (35 files)
2. Auto-generated hash: `20260103_095059_54ae5071be1b_add_...` (2 files)
3. Hybrid date-prefix: `20260208_035_add_bulk_import_organizations.py` (1 file)

#### Branch and Merge in Chain (High)

Chain diverges after `034_pwa_tables` into two branches, merged by `688ec7c374ee`. While Alembic supports this, it adds complexity.

#### Alembic env.py Missing Model Imports (High)

`alembic/env.py:20-25` only imports models from `auth` and `onboarding`. Running `alembic revision --autogenerate` will not detect drift in 15+ other modules.

### 5.3 Configuration Security

| Issue | File:Line | Severity |
|-------|-----------|----------|
| JWT secret has known default | `config.py:189` | Critical |
| MinIO credentials hardcoded | `config.py:150-151` | High |
| Token encryption key allows empty | `config.py:408-409` | Medium |
| Redis has no password in Docker | `docker-compose.yml:39` | Medium |
| MinIO uses `:latest` tag | `docker-compose.yml:57` | Medium |

### 5.4 Dependencies

- **Duplicate anthropic dependency**: `>=0.75.0` in main deps, `>=0.40.0` in `[ai]` extra (`pyproject.toml`)
- **No upper bounds**: All deps use `>=` specifiers. `uv.lock` mitigates for deterministic builds.
- **.gitignore**: Well-configured — covers `.env*`, `*.pem`, `*.key`, `secrets/`

### 5.5 Database Connection

**Positive:** Connection pooling is well-configured (`pool_size=5`, `max_overflow=10`, `pool_pre_ping=True`, `pool_recycle=1800s`). Celery session handling properly creates/disposes engines per task.

**Minor:** `database.py:270-272` uses raw SQL string `"SELECT 1"` instead of `text("SELECT 1")` for SQLAlchemy 2.x compliance.

---

## 6. Architecture

### 6.1 Module Boundary Violations (High)

Nearly every module imports other modules' internals directly. Key violations:

| Source Module | Imports From | File |
|---------------|-------------|------|
| `onboarding` | `xero.service`, `xero.repository`, `billing.service`, `auth.repository` | `onboarding/service.py`, `onboarding/router.py` |
| `billing` | `notifications.email_service`, `notifications.templates` | `billing/webhooks.py`, `billing/usage_alerts.py` |
| `admin` | `auth.models`, `billing.models`, `xero.models`, `billing.stripe_client` | `admin/repository.py`, `admin/service.py` |
| `bas` | `quality.service`, `xero.repository`, `notifications.service` | `bas/service.py`, `bas/deadline_notification_service.py` |
| `clients` | `xero.payroll_repository`, `quality.repository`, `dashboard.schemas/service` | `clients/service.py`, `clients/router.py` |
| `dashboard` | `quality.repository`, `xero.utils` | `dashboard/service.py` |
| `agents` | `knowledge.repository`, `knowledge.context_builder` | `agents/router.py`, `agents/orchestrator.py` |
| `insights` | `action_items.service`, `agents.orchestrator` | `insights/router.py` |
| `triggers` | `insights.models`, `insights.generator` | `triggers/executor.py` |
| `knowledge` | `xero.models` (XeroClient) | `knowledge/repository.py` |
| `portal.requests` | `notifications.push.service` | `portal/requests/service.py` |
| `queries` | `agents.query_agent` | `queries/router.py` |
| `productivity` | `agents.summary_agent` | `productivity/router.py` |

### 6.2 Event Bus: Built but Unused (High)

`backend/app/core/events.py` is a complete in-process pub/sub system (lines 67-183) with async/sync handlers, concurrent execution, and error isolation. **It is used in zero production modules.** The only consumer is the `_template` module, which is a scaffold.

Every inter-module interaction uses direct imports instead:
- Billing sends emails by importing `notifications.email_service`
- BAS triggers quality calculations by calling `quality.service` directly
- Xero sync dispatches downstream tasks via direct Celery calls
- Triggers create insights by calling `InsightGenerator` directly

The event bus also uses `print()` for errors instead of proper logging (lines 161, 171).

### 6.3 Audit Logging: Partial Coverage (Medium)

The audit infrastructure at `core/audit.py` is well-engineered (checksum chaining, IP/email masking, decorator pattern). But adoption is incomplete:

**WITH audit logging:** `auth`, `integrations/xero`, `bas`, `agents` (custom `AgentAuditService`), `tasks/xero` (bulk import)

**WITHOUT audit logging:** `billing`, `clients`, `notifications`, `insights`, `triggers`, `quality`, `admin`, `portal`, `dashboard`, `onboarding`

The `@audited` decorator (line 459) is never actually used anywhere in the codebase.

### 6.4 Security Issues

| Issue | File:Line | Severity |
|-------|-----------|----------|
| Knowledge endpoints unauthenticated | `auth/middleware.py:41` | Critical |
| Triggers router has no role-based auth (only `get_current_tenant_id`) | `triggers/router.py:27` | Medium |
| Action items + insights use custom auth (bypasses standard patterns) | `action_items/router.py:33-44`, `insights/router.py:40-48` | Medium |
| CORS: wildcard methods + headers by default | `config.py:596-603` | Medium |
| OpenAPI schema always exposed (no auth) | `main.py:141` | Low |
| JWT middleware reflects Origin header in 401 responses (CORS bypass) | `auth/middleware.py:232-236` | Medium |
| `user_id` as plain parameter (impersonation risk) | `knowledge/client_chat_router.py:285` | High |

### 6.5 API Consistency

- **No standard pagination** — Only `triggers/router.py` implements `limit`/`offset`. All other list endpoints return unbounded results.
- **Inconsistent response typing** — Most routers use Pydantic `response_model`, but `productivity/router.py` returns raw `dict[str, Any]`.
- **Mock data in production** — `productivity/router.py:142-154,179-201` returns hardcoded mock data for `/stats` and `/activity` endpoints.

### 6.6 Celery Tasks

#### Duplicated Infrastructure (High)

`_get_async_session()` is copy-pasted identically into **8 task files** (`xero.py`, `insights.py`, `triggers.py`, `reports.py`, `bas.py`, `scheduler.py`, `usage.py`, `aggregation.py`). Each creates a new SQLAlchemy engine per call (never disposed). Similarly, `_set_tenant_context()` is duplicated in 6 files.

#### Other Task Issues

| Issue | File | Severity |
|-------|------|----------|
| Engine never disposed — connection pool leaks | All 8 task files | Medium |
| `time.sleep(2)` in async context | `xero.py:1441` | Low |
| Quality task uses different session pattern | `quality.py:76-77` | Medium |
| Usage tasks configure `max_retries=3` but no `autoretry_for` | `usage.py:37-42` | Medium |
| Knowledge task has custom event loop handling | `knowledge.py:27-39` | Low |

### 6.7 Missing Middleware

| Missing | Impact | Severity |
|---------|--------|----------|
| Global API rate limiting | Only in-memory rate limit for login/invitations; no protection for AI/LLM endpoints, bulk operations | Medium |
| Request logging middleware | No per-request method/path/duration/status logging | Low |
| Request ID middleware | No correlation ID for request tracing | Low |

### 6.8 Dead/Incomplete Modules

| Module | Issue | Severity |
|--------|-------|----------|
| `_template` | Scaffold with `items` table — could confuse autogenerate | Low |
| `documents` | Listed in CLAUDE.md but doesn't exist — doc drift | Low |
| `productivity` | Returns hardcoded mock data in production endpoints | Low |

---

## 7. Recommended Quick Wins

These items are low effort but high impact — consider tackling first:

| # | Action | Effort | Impact |
|---|--------|--------|--------|
| 1 | Add auth to knowledge endpoints — remove exclusion at `auth/middleware.py:41` | 5 min | Critical security fix |
| 2 | Guard JWT secret in production — add validator in `config.py` rejecting default value | 15 min | Critical security fix |
| 3 | Guard token encryption key — reject empty string in production | 15 min | Security fix |
| 4 | Add env var fallback to 4 frontend files missing it | 10 min | Prevents broken URLs |
| 5 | Add Authorization header to `queries/page.tsx:187` | 5 min | Auth fix |
| 6 | Centralise `API_BASE_URL` — extract to single const, import in 10+ files | 30 min | Reduces duplication |
| 7 | Fix Alembic `env.py` — import all module models | 15 min | Fixes autogenerate |
| 8 | Extract `_get_async_session()` to `app/tasks/utils.py` | 30 min | Removes 8x duplication |
| 9 | Replace `asyncio.get_event_loop()` with `asyncio.run()` in 5 task files | 20 min | Removes deprecation |
| 10 | Add `server_default=func.now()` to quality model timestamps | 10 min | Prevents insert failures |

---

## 8. Prioritised Action Plan

### P0 — Security (This Sprint)

1. Authenticate knowledge base endpoints
2. Add `tenant_id` to all knowledge models + migration
3. Guard JWT secret and encryption key in production
4. Create migration adding RLS policies to all 25+ missing tables
5. Fix frontend auth header and URL fallbacks
6. Remove `user_id` plain parameter from `client_chat_router.py`

### P1 — Data Integrity (Next Sprint)

7. Fix Alembic `env.py` to import all models
8. Fix quality model timestamps (`server_default`)
9. Standardise migration naming convention
10. Add `server_default` to insight model timestamps
11. Consolidate `_get_async_session()` in Celery tasks

### P2 — Test Coverage (Next 2-4 Sprints)

12. Add integration tests for 10 untested routers
13. Add unit tests for 9 untested modules (prioritise `insights`, `triggers`, `quality`, `notifications`)
14. Add contract tests for Xero Contacts/Invoices/Transactions APIs
15. Add contract tests for Clerk + Stripe webhooks
16. Set up Playwright for critical E2E paths
17. Recategorise misplaced E2E tests as unit tests
18. Write tests for 15 Celery task files

### P3 — Architecture (Ongoing)

19. Introduce module interfaces / anti-corruption layers for top cross-module imports
20. Adopt the event bus for billing->notifications, xero->quality/insights/aggregation flows
21. Expand audit logging to billing, portal, admin, triggers, insights modules
22. Add API pagination standard (shared schema + middleware)
23. Add global rate limiting middleware
24. Add request logging + request ID middleware

### P4 — Frontend Quality (Ongoing)

25. Break up `clients/[id]/page.tsx` (2,349 lines) into sub-components
26. Break up `BASTab.tsx` (1,872 lines) and `assistant/page.tsx` (1,571 lines)
27. Centralise API base URL
28. Fix `{} as T` returns in API client
29. Replace `console.error`-only error handling with user-facing error states
30. Generate proper types from backend OpenAPI spec
31. Remove example store and 151 debug console.log calls

---

*Generated by automated tech debt review — 2026-02-08*
*Review performed by 5 parallel analysis agents covering backend, frontend, tests, database/config, and architecture*
