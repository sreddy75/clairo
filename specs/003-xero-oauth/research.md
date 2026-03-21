# Research: Xero OAuth 2.0 Integration

**Spec**: 003-xero-oauth | **Date**: 2025-12-28

---

## Xero OAuth 2.0 Overview

### Authentication Flow Options

Xero supports two OAuth 2.0 flows:

1. **Standard Authorization Code Flow** - For server-side applications with secure client secret storage
2. **PKCE (Proof Key for Code Exchange) Flow** - For applications that cannot securely store client secrets

**Recommendation**: Use PKCE flow for enhanced security, even though we're server-side. PKCE provides additional protection against authorization code interception attacks.

### Key URLs

| Purpose | URL |
|---------|-----|
| Authorization | `https://login.xero.com/identity/connect/authorize` |
| Token Exchange | `https://identity.xero.com/connect/token` |
| Connections | `https://api.xero.com/connections` |
| Revoke Token | `https://identity.xero.com/connect/revocation` |

---

## Token Lifecycle

### Access Tokens

- **Lifetime**: 30 minutes
- **Type**: JWT
- **Usage**: Bearer token in Authorization header
- **Refresh**: Required before expiry for uninterrupted access

### Refresh Tokens

- **Lifetime**: 60 days maximum
- **Inactivity Expiry**: 30 days without use
- **Single Use**: Yes (rotating tokens - each use returns new refresh token)
- **Retry Window**: Can retry with same token for 30 minutes if no response received

### Token Storage Requirements

```
Access Token:  Encrypted, indexed by tenant_id + xero_tenant_id
Refresh Token: Encrypted, indexed by tenant_id + xero_tenant_id
Expires At:    Timestamp (UTC), used for proactive refresh
```

---

## Required Scopes

Based on Clairo requirements for BAS preparation:

| Scope | Purpose | Required |
|-------|---------|----------|
| `offline_access` | Enables refresh tokens | Yes |
| `openid` | OpenID Connect identity | Yes |
| `profile` | User profile information | Yes |
| `email` | User email address | Yes |
| `accounting.settings` | Organization settings, chart of accounts | Yes |
| `accounting.transactions` | Invoices, bills, bank transactions | Yes |
| `accounting.transactions.read` | Read-only transaction access | Optional (subset) |
| `accounting.contacts` | Customer and supplier contacts | Yes |
| `accounting.contacts.read` | Read-only contact access | Optional (subset) |
| `accounting.reports.read` | Financial reports including GST | Yes |

**Full Scope String**:
```
offline_access openid profile email accounting.settings accounting.transactions accounting.contacts accounting.reports.read
```

---

## Rate Limits

### Per-Tenant Limits

| Limit Type | Value | Reset |
|------------|-------|-------|
| Daily | 5,000 calls | Rolling 24 hours |
| Minute | 60 calls | Rolling 60 seconds |

### App-Wide Limits

| Limit Type | Value | Reset |
|------------|-------|-------|
| App Minute | 10,000 calls | Rolling 60 seconds |

### Response Headers

```http
X-DayLimit-Remaining: 4950
X-MinLimit-Remaining: 55
X-AppMinLimit-Remaining: 9900
Retry-After: 30  # Only present on 429 response
```

### Rate Limit Strategy

1. **Proactive Tracking**: Store remaining limits after each request
2. **Pre-check**: Before making request, check if limits allow
3. **Backoff**: On 429, wait for Retry-After seconds
4. **Exponential Backoff**: For repeated failures, increase wait time
5. **Queue**: Low-priority requests can be queued when approaching limits

---

## Multi-Tenant Considerations

### Xero Organization Selection

When a user authorizes, they may have access to multiple Xero organizations. After OAuth:

1. Call `/connections` endpoint to list authorized organizations
2. Each organization has a unique `tenantId` (Xero's terminology)
3. User can select which organization(s) to connect
4. Each connection is independent with its own rate limits

### Token Scope

- Tokens are scoped to the **user**, not the organization
- A single token can access multiple organizations the user authorized
- Must specify `xero-tenant-id` header for each API call

### Clairo Multi-Tenancy Mapping

```
Clairo Tenant (Practice)
    └── XeroConnection 1 (Xero Org A)
    └── XeroConnection 2 (Xero Org B)
    └── XeroConnection 3 (Xero Org C)
```

Each XeroConnection stores:
- The Xero tenant ID (organization)
- Tokens (shared if same Xero user authorized multiple orgs)
- Independent rate limit tracking

---

## Security Considerations

### PKCE Implementation

```python
# Generate code_verifier (43-128 characters, URL-safe)
import secrets
code_verifier = secrets.token_urlsafe(32)  # 43 chars

# Generate code_challenge
import hashlib
import base64
code_challenge = base64.urlsafe_b64encode(
    hashlib.sha256(code_verifier.encode()).digest()
).decode().rstrip('=')

# code_challenge_method = 'S256'
```

### State Parameter

- Generate cryptographically random state
- Store state with: tenant_id, user_id, timestamp, redirect_uri
- Validate on callback
- Expire after 10 minutes

### Token Encryption

- Use AES-256-GCM for token encryption
- Encryption key from environment variable
- Unique IV per encryption operation
- Store IV with ciphertext

---

## Error Handling

### OAuth Errors

| Error | Description | Action |
|-------|-------------|--------|
| `access_denied` | User denied authorization | Show friendly message |
| `invalid_grant` | Code expired or already used | Restart flow |
| `invalid_client` | Client credentials wrong | Check configuration |
| `invalid_request` | Missing parameters | Log and restart flow |

### Token Refresh Errors

| Error | Description | Action |
|-------|-------------|--------|
| `invalid_grant` | Refresh token expired/revoked | Mark for re-auth |
| Network error | No response within timeout | Retry with same token (30 min window) |

### API Errors

| HTTP Status | Description | Action |
|-------------|-------------|--------|
| 401 | Unauthorized | Refresh token, retry |
| 403 | Forbidden | Check scopes, may need re-auth with more scopes |
| 404 | Resource not found | Handle gracefully |
| 429 | Rate limited | Wait Retry-After, exponential backoff |
| 500+ | Xero server error | Retry with backoff |

---

## Python Libraries

### Recommended

- **httpx**: Async HTTP client for API calls
- **python-jose**: JWT handling
- **cryptography**: Token encryption (Fernet or AES-GCM)

### Not Recommended

- **xero-python SDK**: Adds complexity, we only need OAuth + few endpoints
- **requests**: Use httpx for async support

---

## Implementation Approach

### Backend Module Structure

```
backend/app/modules/integrations/xero/
├── __init__.py
├── router.py          # API endpoints
├── service.py         # Business logic
├── repository.py      # Database operations
├── models.py          # SQLAlchemy models
├── schemas.py         # Pydantic schemas
├── oauth.py           # OAuth flow handling
├── client.py          # Xero API client
├── rate_limiter.py    # Rate limit tracking
└── encryption.py      # Token encryption
```

### Frontend Components

```
frontend/src/
├── app/(protected)/settings/integrations/
│   ├── page.tsx                    # Integrations list
│   └── xero/
│       ├── page.tsx                # Xero connections
│       └── callback/page.tsx       # OAuth callback
├── components/integrations/
│   ├── XeroConnectionCard.tsx
│   ├── XeroConnectButton.tsx
│   └── ConnectionStatusBadge.tsx
└── lib/
    └── api/integrations.ts         # API client
```

---

## Testing Strategy

### Unit Tests

- PKCE code generation
- Token encryption/decryption
- Rate limit calculations
- State validation

### Integration Tests

- OAuth flow (mocked Xero responses)
- Token refresh flow
- Rate limit handling
- Connection CRUD operations

### Contract Tests

- Mock Xero API responses
- Verify request format matches Xero expectations
- Test error response handling

### E2E Tests

- Full OAuth flow with Xero demo company
- Connect, view, disconnect journey

---

## References

- [Xero OAuth 2.0 Overview](https://developer.xero.com/documentation/guides/oauth2/overview/)
- [Xero PKCE Flow](https://developer.xero.com/documentation/guides/oauth2/pkce-flow)
- [Xero Scopes](https://developer.xero.com/documentation/guides/oauth2/scopes/)
- [Xero Rate Limits](https://developer.xero.com/documentation/guides/oauth2/limits/)
- [Xero API Connections](https://developer.xero.com/documentation/guides/oauth2/tenants/)
