# Implementation Plan: Xero OAuth & Connection Management

**Branch**: `feature/003-xero-oauth` | **Date**: 2025-12-28 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-xero-oauth/spec.md`

---

## Summary

Implement Xero OAuth 2.0 with PKCE flow to enable Clairo users to connect their Xero organizations. This includes secure token management, automatic refresh, rate limiting, multi-tenant isolation, and a frontend UI for connection management.

---

## Technical Context

**Language/Version**: Python 3.12+ (Backend), TypeScript/React (Frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.x, httpx, cryptography, Next.js 14
**Storage**: PostgreSQL 16 with RLS
**Testing**: pytest, pytest-asyncio, httpx (mocked), Playwright
**Target Platform**: Linux server (backend), Vercel (frontend)
**Project Type**: Web application (frontend + backend)
**Performance Goals**: Token refresh < 2s, OAuth callback < 5s
**Constraints**: Xero rate limits (60/min, 5000/day per tenant)
**Scale/Scope**: 100+ practices, multiple Xero orgs per practice

---

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| Modular Monolith | PASS | New module: `modules/integrations/xero/` |
| Repository Pattern | PASS | `XeroConnectionRepository` |
| Multi-tenancy (RLS) | PASS | RLS on `xero_connections` table |
| Type Hints | PASS | All functions typed |
| Pydantic Schemas | PASS | Request/response schemas defined |
| Audit Logging | PASS | All connection events audited |
| Test Coverage (80%) | PASS | Unit + integration tests planned |

---

## Project Structure

### Documentation (this feature)

```text
specs/003-xero-oauth/
├── spec.md              # User-centric specification
├── plan.md              # This file
├── research.md          # Xero OAuth research
├── data-model.md        # Database schema
└── tasks.md             # Task list (generated next)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── config.py                          # Add XeroSettings
│   ├── modules/
│   │   └── integrations/
│   │       └── xero/
│   │           ├── __init__.py
│   │           ├── router.py              # API endpoints
│   │           ├── service.py             # Business logic
│   │           ├── repository.py          # Database operations
│   │           ├── models.py              # SQLAlchemy models
│   │           ├── schemas.py             # Pydantic schemas
│   │           ├── oauth.py               # OAuth flow handling
│   │           ├── client.py              # Xero API client
│   │           ├── rate_limiter.py        # Rate limit tracking
│   │           ├── encryption.py          # Token encryption
│   │           └── audit_events.py        # Audit event definitions
│   └── core/
│       └── encryption.py                  # Shared encryption utilities
├── alembic/
│   └── versions/
│       └── 003_xero_oauth.py              # Migration
└── tests/
    ├── unit/
    │   └── modules/
    │       └── integrations/
    │           └── xero/
    │               ├── test_oauth.py
    │               ├── test_encryption.py
    │               ├── test_rate_limiter.py
    │               └── test_service.py
    ├── integration/
    │   └── api/
    │       └── test_xero_endpoints.py
    └── factories/
        └── xero.py                        # Test factories

frontend/
├── src/
│   ├── app/
│   │   └── (protected)/
│   │       └── settings/
│   │           └── integrations/
│   │               ├── page.tsx           # Integrations list
│   │               └── xero/
│   │                   ├── page.tsx       # Xero connections
│   │                   └── callback/
│   │                       └── page.tsx   # OAuth callback
│   ├── components/
│   │   └── integrations/
│   │       ├── XeroConnectionCard.tsx
│   │       ├── XeroConnectButton.tsx
│   │       └── ConnectionStatusBadge.tsx
│   └── lib/
│       └── api/
│           └── integrations.ts            # API client
└── tests/
    └── e2e/
        └── xero-oauth.spec.ts
```

**Structure Decision**: Web application structure following existing patterns from Spec 002.

---

## Component Design

### Backend Components

#### 1. XeroOAuthService

Handles OAuth flow initiation and callback processing.

```python
class XeroOAuthService:
    def __init__(
        self,
        settings: XeroSettings,
        state_repo: XeroOAuthStateRepository,
        connection_repo: XeroConnectionRepository,
        encryption: TokenEncryption,
        audit: AuditService,
    ):
        pass

    async def generate_auth_url(
        self,
        tenant_id: UUID,
        user_id: UUID,
        redirect_uri: str,
    ) -> XeroAuthUrlResponse:
        """Generate OAuth URL with PKCE."""
        pass

    async def handle_callback(
        self,
        code: str,
        state: str,
    ) -> XeroConnection:
        """Exchange code for tokens and create connection."""
        pass
```

#### 2. XeroConnectionService

Manages connection lifecycle.

```python
class XeroConnectionService:
    async def list_connections(self, tenant_id: UUID) -> list[XeroConnectionSummary]:
        pass

    async def get_connection(self, connection_id: UUID) -> XeroConnection:
        pass

    async def disconnect(
        self,
        connection_id: UUID,
        user_id: UUID,
        reason: str | None = None,
    ) -> None:
        pass

    async def refresh_tokens(self, connection_id: UUID) -> XeroConnection:
        pass
```

#### 3. XeroClient

HTTP client for Xero API calls.

```python
class XeroClient:
    async def exchange_code(
        self,
        code: str,
        code_verifier: str,
        redirect_uri: str,
    ) -> TokenResponse:
        pass

    async def refresh_token(self, refresh_token: str) -> TokenResponse:
        pass

    async def get_connections(self, access_token: str) -> list[XeroOrganization]:
        pass

    async def revoke_token(self, token: str) -> None:
        pass
```

#### 4. XeroRateLimiter

Tracks and enforces rate limits.

```python
class XeroRateLimiter:
    def update_from_headers(
        self,
        connection_id: UUID,
        headers: dict[str, str],
    ) -> None:
        pass

    def can_make_request(self, connection_id: UUID) -> bool:
        pass

    def get_wait_time(self, connection_id: UUID) -> int:
        """Seconds to wait before next request."""
        pass
```

### Frontend Components

#### 1. IntegrationsPage

List view of all integrations.

```tsx
export default function IntegrationsPage() {
  // Show Xero integration card
  // Future: MYOB, others
}
```

#### 2. XeroConnectionsPage

Manage Xero connections.

```tsx
export default function XeroConnectionsPage() {
  // List connected organizations
  // Connect button
  // Disconnect functionality
}
```

#### 3. XeroCallbackPage

Handle OAuth redirect.

```tsx
export default function XeroCallbackPage() {
  // Extract code and state from URL
  // Send to backend
  // Redirect on success/failure
}
```

---

## API Endpoints

| Method | Path | Handler | Auth |
|--------|------|---------|------|
| GET | `/api/v1/integrations/xero/auth-url` | `generate_auth_url` | JWT |
| GET | `/api/v1/integrations/xero/callback` | `handle_callback` | State |
| GET | `/api/v1/integrations/xero/connections` | `list_connections` | JWT |
| GET | `/api/v1/integrations/xero/connections/{id}` | `get_connection` | JWT |
| DELETE | `/api/v1/integrations/xero/connections/{id}` | `disconnect` | JWT (Admin) |
| POST | `/api/v1/integrations/xero/connections/{id}/refresh` | `refresh_tokens` | JWT (Admin) |

---

## Security Measures

### PKCE Implementation

1. Generate 43-character `code_verifier` using `secrets.token_urlsafe(32)`
2. Compute `code_challenge` = `BASE64URL(SHA256(code_verifier))`
3. Store `code_verifier` with state, never expose to client
4. Include `code_verifier` in token exchange request

### State Validation

1. Generate 32-byte random state using `secrets.token_urlsafe(32)`
2. Store with tenant_id, user_id, timestamp
3. Expire after 10 minutes
4. Mark as used on successful callback
5. Reject if state doesn't match or is expired/used

### Token Encryption

1. Use AES-256-GCM with unique nonce per encryption
2. Key stored in environment variable
3. Encrypt before storing, decrypt when reading
4. Never log plaintext tokens

---

## Error Handling

### OAuth Errors

| Error | HTTP Status | User Message |
|-------|-------------|--------------|
| `access_denied` | 400 | "You cancelled the authorization. Please try again." |
| `invalid_state` | 400 | "Authorization expired. Please try again." |
| `state_mismatch` | 400 | "Security validation failed. Please try again." |
| `token_exchange_failed` | 500 | "Unable to complete connection. Please try again." |

### Token Refresh Errors

| Error | Action |
|-------|--------|
| `invalid_grant` | Mark connection as `needs_reauth`, notify user |
| Network timeout | Retry up to 3 times with exponential backoff |
| 500 from Xero | Retry with backoff, alert if persistent |

---

## Testing Strategy

### Unit Tests

- PKCE code generation (verifier, challenge)
- Token encryption/decryption
- State validation logic
- Rate limit calculations
- Service method logic with mocked dependencies

### Integration Tests

- Full OAuth flow with mocked Xero responses
- Token refresh flow
- Connection CRUD operations
- Rate limit enforcement
- RLS isolation

### E2E Tests

- Connect Xero flow (with Xero demo company)
- View connections page
- Disconnect flow

---

## Configuration

### Environment Variables

```bash
# Xero OAuth
XERO_CLIENT_ID=your_client_id
XERO_CLIENT_SECRET=your_client_secret  # Optional for PKCE
XERO_REDIRECT_URI=http://localhost:3000/settings/integrations/xero/callback
XERO_SCOPES=offline_access openid profile email accounting.settings accounting.transactions accounting.contacts accounting.reports.read

# Token Encryption
TOKEN_ENCRYPTION_KEY=base64_encoded_32_byte_key
```

### XeroSettings Pydantic

```python
class XeroSettings(BaseSettings):
    client_id: str
    client_secret: str | None = None  # Optional for PKCE
    redirect_uri: str
    scopes: str = "offline_access openid profile email accounting.settings accounting.transactions accounting.contacts accounting.reports.read"
    authorization_url: str = "https://login.xero.com/identity/connect/authorize"
    token_url: str = "https://identity.xero.com/connect/token"
    connections_url: str = "https://api.xero.com/connections"
    revocation_url: str = "https://identity.xero.com/connect/revocation"

    model_config = SettingsConfigDict(env_prefix="XERO_")
```

---

## Dependencies

### Python Packages (add to pyproject.toml)

```toml
[project.dependencies]
httpx = "^0.27"  # Already present
cryptography = "^42"  # For token encryption
```

### Frontend Packages

No new packages required - using existing fetch/API infrastructure.

---

## Rollout Plan

1. **Phase 1**: Backend implementation with mocked Xero
2. **Phase 2**: Frontend UI implementation
3. **Phase 3**: Integration with real Xero (dev credentials)
4. **Phase 4**: E2E testing with Xero demo company
5. **Phase 5**: Production deployment with production credentials

---

## Complexity Tracking

No constitution violations - standard implementation following established patterns.
