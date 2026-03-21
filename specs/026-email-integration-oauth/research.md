# Research: Email Integration & OAuth

**Feature**: 026-email-integration-oauth
**Date**: 2026-01-01
**Status**: Complete

---

## Research Tasks

### 1. Gmail API OAuth 2.0

**Decision**: Use Gmail API with OAuth 2.0 and minimal scopes

**OAuth Configuration**:

| Setting | Value |
|---------|-------|
| Authorization URL | `https://accounts.google.com/o/oauth2/v2/auth` |
| Token URL | `https://oauth2.googleapis.com/token` |
| Scopes | `https://www.googleapis.com/auth/gmail.readonly` |
| Response Type | `code` |
| Access Type | `offline` (for refresh tokens) |
| Prompt | `consent` (always show consent screen) |

**Required Scopes**:
```
https://www.googleapis.com/auth/gmail.readonly
```

**Gmail API Endpoints**:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/gmail/v1/users/me/messages` | GET | List messages |
| `/gmail/v1/users/me/messages/{id}` | GET | Get single message |
| `/gmail/v1/users/me/history` | GET | Get changes since historyId |
| `/gmail/v1/users/me/profile` | GET | Get user email address |

**Query Syntax for ATO Emails**:
```
from:(@ato.gov.au OR @notifications.ato.gov.au) newer_than:365d
```

**Rate Limits**:
- 250 quota units per user per second
- `messages.list` = 5 units
- `messages.get` = 5 units
- Daily limit: 1,000,000,000 quota units

**Token Refresh**:
- Access tokens expire in 1 hour
- Refresh tokens valid until revoked (for "Testing" apps: 7 days)
- Use `grant_type=refresh_token` to get new access token

**Rationale**: Gmail API provides comprehensive email access with well-documented OAuth flow. The `gmail.readonly` scope is the minimum required for reading emails.

---

### 2. Microsoft Graph API OAuth 2.0

**Decision**: Use Microsoft Graph API with delegated permissions

**OAuth Configuration**:

| Setting | Value |
|---------|-------|
| Authorization URL | `https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize` |
| Token URL | `https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token` |
| Tenant | `common` (for multi-tenant apps) |
| Response Type | `code` |

**Required Scopes**:
```
Mail.Read
Mail.ReadBasic
User.Read
offline_access
```

**Scope Descriptions**:
- `Mail.Read`: Read user's mail (full message)
- `Mail.ReadBasic`: Read basic mail properties (faster, no body)
- `User.Read`: Get user profile (email address)
- `offline_access`: Obtain refresh tokens

**Microsoft Graph Endpoints**:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/me/messages` | GET | List messages |
| `/me/messages/{id}` | GET | Get single message |
| `/me/mailFolders/inbox/messages/delta` | GET | Get changes (delta query) |
| `/me` | GET | Get user profile |

**Filter Syntax for ATO Emails**:
```
$filter=from/emailAddress/address contains 'ato.gov.au'
```

**Rate Limits**:
- 10,000 requests per 10 minutes per app
- Per-mailbox: 10,000 requests per 10 minutes
- Throttling: HTTP 429 with Retry-After header

**Token Refresh**:
- Access tokens expire in ~1 hour
- Refresh tokens valid for 90 days (sliding window)
- `offline_access` scope required for refresh tokens

**Rationale**: Microsoft Graph is the modern API for Outlook/365. Delegated permissions respect user consent model.

---

### 3. Token Encryption

**Decision**: AES-256-GCM with encryption key from environment

**Implementation**:
```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os
import base64

class TokenEncryption:
    def __init__(self):
        key = os.environ.get("EMAIL_TOKEN_ENCRYPTION_KEY")
        self.key = base64.b64decode(key)  # 32-byte key for AES-256

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a token using AES-256-GCM."""
        aesgcm = AESGCM(self.key)
        nonce = os.urandom(12)  # 96-bit nonce
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
        return base64.b64encode(nonce + ciphertext).decode()

    def decrypt(self, encrypted: str) -> str:
        """Decrypt a token."""
        data = base64.b64decode(encrypted)
        nonce = data[:12]
        ciphertext = data[12:]
        aesgcm = AESGCM(self.key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode()
```

**Key Generation**:
```bash
# Generate 256-bit key
python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
```

**Key Rotation Strategy**:
1. Generate new key, add to env as `EMAIL_TOKEN_ENCRYPTION_KEY_NEW`
2. Re-encrypt all tokens with new key
3. Remove old key, rename new key

**Rationale**: AES-256-GCM provides authenticated encryption with good performance. Key stored in environment, not in code.

---

### 4. Email Sync Strategy

**Decision**: Polling-based sync with delta queries

**Initial Backfill**:
1. Query all emails from last 12 months matching ATO filter
2. Process in batches of 100
3. Store full email content and metadata
4. Record initial historyId (Gmail) or deltaToken (Microsoft)

**Incremental Sync**:
```
Every 15 minutes via Celery beat:
1. Get changes since last sync cursor
2. Filter to ATO emails only
3. Store new/modified emails
4. Update sync cursor
```

**Gmail History API**:
```python
# Get changes since historyId
response = service.users().history().list(
    userId='me',
    startHistoryId=last_history_id,
    historyTypes=['messageAdded']
).execute()
```

**Microsoft Delta Query**:
```python
# Initial: Get first page with deltaLink
response = client.get('/me/mailFolders/inbox/messages/delta')

# Incremental: Use deltaToken
response = client.get(f'/me/mailFolders/inbox/messages/delta?$deltatoken={token}')
```

**Sync Frequency Trade-offs**:
| Interval | Pros | Cons |
|----------|------|------|
| 5 min | Near real-time | High API usage |
| 15 min | Good balance | Acceptable delay |
| 30 min | Low API usage | May miss urgent notices |

**Decision**: 15-minute polling provides acceptable latency while staying well within rate limits.

**Rationale**: Polling is simpler than webhooks and provides acceptable latency for ATO correspondence. Delta queries minimize data transfer.

---

### 5. Email Forwarding Fallback

**Decision**: Inbound email processing via SES or Postmark

**Architecture**:
```
User sets mail rule:
  From: @ato.gov.au
  Forward to: {tenant_slug}@ingest.clairo.ai

AWS SES receives email:
  1. Store in S3
  2. Trigger Lambda
  3. Lambda posts to Clairo API

Clairo processes:
  1. Validate sender domain (@ato.gov.au)
  2. Extract original sender from headers
  3. Store as RawEmail
```

**Forwarding Address Format**:
```
{tenant_slug}@ingest.clairo.ai
```

**Original Sender Extraction**:
When email is forwarded, the original sender is in headers:
- `X-Original-Sender`
- `X-Forwarded-From`
- Parse from body: "From: <original@ato.gov.au>"

**Security Considerations**:
- Validate `From` header contains @ato.gov.au
- Rate limit per tenant (max 100 emails/hour)
- Reject attachments over 25MB
- SPF/DKIM validation where possible

**Rationale**: Some organizations prohibit OAuth connections. Forwarding provides fallback access to ATO correspondence.

---

### 6. OAuth Provider Libraries

**Decision**: Use `authlib` for OAuth implementation

**Library Comparison**:

| Library | Gmail | Microsoft | Maintenance | Notes |
|---------|-------|-----------|-------------|-------|
| authlib | ✅ | ✅ | Active | Well-documented, async support |
| oauthlib | ✅ | ✅ | Active | Lower level, more manual work |
| google-auth | ✅ | ❌ | Google | Gmail only |
| msal | ❌ | ✅ | Microsoft | Microsoft only |

**Authlib Implementation**:
```python
from authlib.integrations.httpx_client import AsyncOAuth2Client

class GmailOAuthClient:
    def __init__(self, client_id: str, client_secret: str):
        self.client = AsyncOAuth2Client(
            client_id=client_id,
            client_secret=client_secret,
            authorization_endpoint='https://accounts.google.com/o/oauth2/v2/auth',
            token_endpoint='https://oauth2.googleapis.com/token',
            scope='https://www.googleapis.com/auth/gmail.readonly',
        )

    async def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        url, _ = self.client.create_authorization_url(
            'https://accounts.google.com/o/oauth2/v2/auth',
            redirect_uri=redirect_uri,
            state=state,
            access_type='offline',
            prompt='consent',
        )
        return url

    async def fetch_token(self, code: str, redirect_uri: str) -> dict:
        token = await self.client.fetch_token(
            'https://oauth2.googleapis.com/token',
            code=code,
            redirect_uri=redirect_uri,
        )
        return token
```

**Rationale**: Authlib provides a unified interface for both Gmail and Microsoft OAuth, with good async support and active maintenance.

---

### 7. Token Refresh Strategy

**Decision**: Proactive refresh before expiry

**Refresh Schedule**:
```python
# Celery beat task: every 30 minutes
@celery.task
async def refresh_expiring_tokens():
    """Refresh tokens expiring in the next hour."""
    expiring_soon = await connection_repo.get_expiring_tokens(
        expires_before=datetime.utcnow() + timedelta(hours=1)
    )

    for connection in expiring_soon:
        try:
            new_token = await oauth_client.refresh_token(
                connection.refresh_token_decrypted
            )
            await connection_repo.update_tokens(
                connection.id,
                access_token=new_token['access_token'],
                expires_at=calculate_expiry(new_token),
            )
        except TokenRefreshError:
            await connection_repo.mark_expired(connection.id)
            await notify_user(connection.tenant_id, 'email_connection_expired')
```

**Handling Refresh Failures**:
1. Log the failure with reason
2. Mark connection status as `EXPIRED`
3. Create notification for user
4. Skip this connection in sync jobs

**Rationale**: Proactive refresh prevents sync failures due to expired tokens. User notification enables manual re-authorization.

---

### 8. ATO Email Domains

**Decision**: Filter to known ATO sender domains

**Valid ATO Domains**:
```python
ATO_DOMAINS = [
    '@ato.gov.au',
    '@notifications.ato.gov.au',
    '@email.ato.gov.au',
    '@online.ato.gov.au',
]
```

**Email Types from ATO**:
- Activity Statement notices
- BAS lodgement confirmations
- Payment reminders
- Audit notifications
- Debt notifications
- Penalty notices
- Running balance updates
- Tax return assessments

**Rationale**: Limiting to ATO domains ensures we only capture relevant correspondence and respect user privacy.

---

## Summary of Decisions

| Area | Decision |
|------|----------|
| Gmail OAuth | Use Gmail API v1 with `gmail.readonly` scope |
| Microsoft OAuth | Use Graph API with `Mail.Read` scope |
| Token Encryption | AES-256-GCM with env-based key |
| Sync Strategy | 15-minute polling with delta queries |
| Fallback | Email forwarding via SES/Postmark |
| OAuth Library | authlib for unified Gmail/Microsoft support |
| Token Refresh | Proactive refresh 1 hour before expiry |
| Email Filter | Only @ato.gov.au domains |

---

## Sources

- [Gmail API OAuth Scopes](https://developers.google.com/workspace/gmail/api/auth/scopes)
- [Gmail API Python Quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python)
- [Gmail History API](https://developers.google.com/gmail/api/guides/sync)
- [Microsoft Graph Mail API](https://learn.microsoft.com/en-us/graph/api/user-list-messages)
- [Microsoft Graph Delta Query](https://learn.microsoft.com/en-us/graph/delta-query-messages)
- [Microsoft Graph Permissions](https://learn.microsoft.com/en-us/graph/permissions-reference)
- [Authlib Documentation](https://docs.authlib.org/en/latest/)
- [Python Cryptography - AESGCM](https://cryptography.io/en/latest/hazmat/primitives/aead/)
