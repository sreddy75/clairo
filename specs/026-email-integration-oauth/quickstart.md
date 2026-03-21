# Quickstart: Email Integration & OAuth

**Spec**: 026-email-integration-oauth
**Time to Implement**: ~3-4 days
**Prerequisites**: Celery setup, Redis, PostgreSQL

---

## Overview

This guide covers implementing OAuth-based email connections for Gmail and Microsoft 365 to capture ATO correspondence automatically.

---

## Quick Setup

### 1. Install Dependencies

```bash
cd backend
uv add authlib httpx cryptography
```

### 2. Environment Variables

```bash
# Gmail OAuth (Google Cloud Console)
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret

# Microsoft OAuth (Azure Portal)
MICROSOFT_CLIENT_ID=your-azure-client-id
MICROSOFT_CLIENT_SECRET=your-azure-client-secret
MICROSOFT_TENANT_ID=common  # or specific tenant

# Token Encryption (generate with: python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())")
EMAIL_TOKEN_ENCRYPTION_KEY=your-32-byte-base64-encoded-key

# Callback URLs
EMAIL_OAUTH_CALLBACK_URL=https://app.clairo.ai/api/v1/email/oauth
```

### 3. Google Cloud Console Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create project or select existing
3. Enable Gmail API: APIs & Services → Enable APIs → Gmail API
4. Create OAuth credentials:
   - OAuth consent screen → Configure for external users
   - Credentials → Create OAuth Client ID → Web application
   - Add authorized redirect URI: `https://app.clairo.ai/api/v1/email/oauth/gmail/callback`
5. Note the Client ID and Client Secret

### 4. Azure Portal Setup

1. Go to [Azure Portal](https://portal.azure.com/)
2. Azure Active Directory → App registrations → New registration
3. Redirect URI: `https://app.clairo.ai/api/v1/email/oauth/outlook/callback`
4. API Permissions → Add:
   - `Mail.Read`
   - `Mail.ReadBasic`
   - `User.Read`
   - `offline_access`
5. Certificates & secrets → New client secret
6. Note the Application (client) ID and Secret

---

## Core Implementation

### Token Encryption

```python
# backend/app/modules/email/crypto.py
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os
import base64

class TokenEncryption:
    """AES-256-GCM encryption for OAuth tokens."""

    def __init__(self, key: str | None = None):
        key = key or os.environ.get("EMAIL_TOKEN_ENCRYPTION_KEY")
        if not key:
            raise ValueError("EMAIL_TOKEN_ENCRYPTION_KEY not set")
        self.key = base64.b64decode(key)

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

### OAuth Base Interface

```python
# backend/app/modules/email/oauth/base.py
from abc import ABC, abstractmethod
from typing import TypedDict

class TokenData(TypedDict):
    access_token: str
    refresh_token: str | None
    expires_in: int
    token_type: str

class EmailOAuthProvider(ABC):
    """Base class for email OAuth providers."""

    @abstractmethod
    async def get_authorization_url(
        self,
        redirect_uri: str,
        state: str
    ) -> str:
        """Generate OAuth authorization URL."""
        pass

    @abstractmethod
    async def exchange_code(
        self,
        code: str,
        redirect_uri: str
    ) -> TokenData:
        """Exchange authorization code for tokens."""
        pass

    @abstractmethod
    async def refresh_token(
        self,
        refresh_token: str
    ) -> TokenData:
        """Refresh an expired access token."""
        pass

    @abstractmethod
    async def get_user_email(
        self,
        access_token: str
    ) -> str:
        """Get the authenticated user's email address."""
        pass
```

### Gmail OAuth Client

```python
# backend/app/modules/email/oauth/gmail.py
from authlib.integrations.httpx_client import AsyncOAuth2Client
import httpx

from app.config import settings
from .base import EmailOAuthProvider, TokenData

class GmailOAuthClient(EmailOAuthProvider):
    """Gmail OAuth 2.0 client."""

    AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
    SCOPE = "https://www.googleapis.com/auth/gmail.readonly"

    def __init__(self):
        self.client_id = settings.GOOGLE_CLIENT_ID
        self.client_secret = settings.GOOGLE_CLIENT_SECRET

    async def get_authorization_url(
        self,
        redirect_uri: str,
        state: str
    ) -> str:
        """Generate Gmail OAuth authorization URL."""
        client = AsyncOAuth2Client(
            client_id=self.client_id,
            client_secret=self.client_secret,
        )
        url, _ = client.create_authorization_url(
            self.AUTHORIZATION_URL,
            redirect_uri=redirect_uri,
            state=state,
            scope=self.SCOPE,
            access_type="offline",  # For refresh tokens
            prompt="consent",  # Always show consent screen
        )
        return url

    async def exchange_code(
        self,
        code: str,
        redirect_uri: str
    ) -> TokenData:
        """Exchange authorization code for tokens."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            response.raise_for_status()
            return response.json()

    async def refresh_token(
        self,
        refresh_token: str
    ) -> TokenData:
        """Refresh an expired access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
            return response.json()

    async def get_user_email(
        self,
        access_token: str
    ) -> str:
        """Get the authenticated user's email address."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            data = response.json()
            return data["email"]
```

### Microsoft Graph OAuth Client

```python
# backend/app/modules/email/oauth/microsoft.py
from authlib.integrations.httpx_client import AsyncOAuth2Client
import httpx

from app.config import settings
from .base import EmailOAuthProvider, TokenData

class MicrosoftOAuthClient(EmailOAuthProvider):
    """Microsoft Graph OAuth 2.0 client."""

    TENANT = "common"  # Multi-tenant
    AUTHORIZATION_URL = f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/authorize"
    TOKEN_URL = f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/token"
    USERINFO_URL = "https://graph.microsoft.com/v1.0/me"
    SCOPES = ["Mail.Read", "Mail.ReadBasic", "User.Read", "offline_access"]

    def __init__(self):
        self.client_id = settings.MICROSOFT_CLIENT_ID
        self.client_secret = settings.MICROSOFT_CLIENT_SECRET

    async def get_authorization_url(
        self,
        redirect_uri: str,
        state: str
    ) -> str:
        """Generate Microsoft OAuth authorization URL."""
        client = AsyncOAuth2Client(
            client_id=self.client_id,
            client_secret=self.client_secret,
        )
        url, _ = client.create_authorization_url(
            self.AUTHORIZATION_URL,
            redirect_uri=redirect_uri,
            state=state,
            scope=" ".join(self.SCOPES),
        )
        return url

    async def exchange_code(
        self,
        code: str,
        redirect_uri: str
    ) -> TokenData:
        """Exchange authorization code for tokens."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                    "scope": " ".join(self.SCOPES),
                },
            )
            response.raise_for_status()
            return response.json()

    async def refresh_token(
        self,
        refresh_token: str
    ) -> TokenData:
        """Refresh an expired access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                    "scope": " ".join(self.SCOPES),
                },
            )
            response.raise_for_status()
            return response.json()

    async def get_user_email(
        self,
        access_token: str
    ) -> str:
        """Get the authenticated user's email address."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            data = response.json()
            return data.get("mail") or data.get("userPrincipalName")
```

### Gmail Sync Service

```python
# backend/app/modules/email/sync/gmail_sync.py
import httpx
from datetime import datetime, timedelta

from app.modules.email.models import EmailConnection, RawEmail
from app.modules.email.repository import EmailRepository

# ATO email domains to filter
ATO_DOMAINS = [
    "@ato.gov.au",
    "@notifications.ato.gov.au",
    "@email.ato.gov.au",
    "@online.ato.gov.au",
]

class GmailSyncService:
    """Sync emails from Gmail API."""

    BASE_URL = "https://gmail.googleapis.com/gmail/v1"

    def __init__(self, repository: EmailRepository):
        self.repository = repository

    async def initial_backfill(
        self,
        connection: EmailConnection,
        access_token: str
    ) -> int:
        """Sync emails from the last 12 months."""
        query = "from:(@ato.gov.au OR @notifications.ato.gov.au) newer_than:365d"

        async with httpx.AsyncClient() as client:
            # Get message IDs
            response = await client.get(
                f"{self.BASE_URL}/users/me/messages",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"q": query, "maxResults": 500},
            )
            response.raise_for_status()
            data = response.json()

            messages = data.get("messages", [])
            synced_count = 0

            for msg_info in messages:
                # Get full message
                msg_response = await client.get(
                    f"{self.BASE_URL}/users/me/messages/{msg_info['id']}",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params={"format": "full"},
                )
                msg_response.raise_for_status()
                message = msg_response.json()

                # Store email
                await self._store_email(connection, message)
                synced_count += 1

            # Store history ID for incremental sync
            if "historyId" in data:
                await self.repository.update_sync_cursor(
                    connection.id,
                    cursor=data["historyId"]
                )

            return synced_count

    async def incremental_sync(
        self,
        connection: EmailConnection,
        access_token: str
    ) -> int:
        """Sync new emails since last sync."""
        if not connection.sync_cursor:
            return await self.initial_backfill(connection, access_token)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/users/me/history",
                headers={"Authorization": f"Bearer {access_token}"},
                params={
                    "startHistoryId": connection.sync_cursor,
                    "historyTypes": "messageAdded",
                },
            )
            response.raise_for_status()
            data = response.json()

            synced_count = 0
            history = data.get("history", [])

            for record in history:
                for msg_added in record.get("messagesAdded", []):
                    message_id = msg_added["message"]["id"]

                    # Get full message
                    msg_response = await client.get(
                        f"{self.BASE_URL}/users/me/messages/{message_id}",
                        headers={"Authorization": f"Bearer {access_token}"},
                        params={"format": "full"},
                    )
                    msg_response.raise_for_status()
                    message = msg_response.json()

                    # Check if from ATO
                    if self._is_ato_email(message):
                        await self._store_email(connection, message)
                        synced_count += 1

            # Update cursor
            if "historyId" in data:
                await self.repository.update_sync_cursor(
                    connection.id,
                    cursor=data["historyId"]
                )

            return synced_count

    def _is_ato_email(self, message: dict) -> bool:
        """Check if email is from an ATO domain."""
        headers = {h["name"]: h["value"] for h in message.get("payload", {}).get("headers", [])}
        from_addr = headers.get("From", "").lower()
        return any(domain in from_addr for domain in ATO_DOMAINS)

    async def _store_email(
        self,
        connection: EmailConnection,
        message: dict
    ) -> RawEmail:
        """Extract and store email from Gmail API response."""
        headers = {h["name"]: h["value"] for h in message.get("payload", {}).get("headers", [])}

        email = RawEmail(
            tenant_id=connection.tenant_id,
            connection_id=connection.id,
            provider_message_id=message["id"],
            from_address=headers.get("From", ""),
            to_addresses=[headers.get("To", "")],
            subject=headers.get("Subject", ""),
            received_at=datetime.fromtimestamp(int(message["internalDate"]) / 1000),
            body_text=self._extract_body(message, "text/plain"),
            body_html=self._extract_body(message, "text/html"),
            raw_headers=headers,
        )

        return await self.repository.create_email(email)

    def _extract_body(self, message: dict, mime_type: str) -> str | None:
        """Extract body content by MIME type."""
        payload = message.get("payload", {})

        # Simple message
        if payload.get("mimeType") == mime_type:
            import base64
            data = payload.get("body", {}).get("data", "")
            return base64.urlsafe_b64decode(data).decode() if data else None

        # Multipart message
        for part in payload.get("parts", []):
            if part.get("mimeType") == mime_type:
                import base64
                data = part.get("body", {}).get("data", "")
                return base64.urlsafe_b64decode(data).decode() if data else None

        return None
```

### Celery Tasks for Sync

```python
# backend/app/modules/email/sync/scheduler.py
from datetime import datetime, timedelta
from celery import shared_task

from app.database import get_session
from app.modules.email.repository import EmailConnectionRepository, EmailRepository
from app.modules.email.oauth.gmail import GmailOAuthClient
from app.modules.email.oauth.microsoft import MicrosoftOAuthClient
from app.modules.email.sync.gmail_sync import GmailSyncService
from app.modules.email.sync.microsoft_sync import MicrosoftSyncService
from app.modules.email.crypto import TokenEncryption
from app.modules.email.models import ConnectionStatus, EmailProvider

crypto = TokenEncryption()

@shared_task
def sync_all_email_connections():
    """Celery beat task: sync all active connections (every 15 min)."""
    import asyncio
    asyncio.run(_sync_all_connections())

async def _sync_all_connections():
    """Sync all active email connections."""
    async with get_session() as session:
        conn_repo = EmailConnectionRepository(session)
        email_repo = EmailRepository(session)

        connections = await conn_repo.get_active_connections()

        for connection in connections:
            try:
                # Decrypt access token
                access_token = crypto.decrypt(connection.access_token_encrypted)

                # Sync based on provider
                if connection.provider == EmailProvider.GMAIL:
                    sync_service = GmailSyncService(email_repo)
                    count = await sync_service.incremental_sync(connection, access_token)
                elif connection.provider == EmailProvider.OUTLOOK:
                    sync_service = MicrosoftSyncService(email_repo)
                    count = await sync_service.incremental_sync(connection, access_token)

                # Update last sync time
                await conn_repo.update_last_sync(connection.id, count)

            except Exception as e:
                await conn_repo.mark_sync_failed(connection.id, str(e))

@shared_task
def refresh_expiring_tokens():
    """Celery beat task: refresh tokens expiring soon (every 30 min)."""
    import asyncio
    asyncio.run(_refresh_expiring_tokens())

async def _refresh_expiring_tokens():
    """Refresh tokens that expire within the next hour."""
    async with get_session() as session:
        conn_repo = EmailConnectionRepository(session)

        expiring_soon = await conn_repo.get_expiring_connections(
            expires_before=datetime.utcnow() + timedelta(hours=1)
        )

        gmail_client = GmailOAuthClient()
        microsoft_client = MicrosoftOAuthClient()

        for connection in expiring_soon:
            try:
                # Decrypt refresh token
                refresh_token = crypto.decrypt(connection.refresh_token_encrypted)

                # Get new tokens
                if connection.provider == EmailProvider.GMAIL:
                    token_data = await gmail_client.refresh_token(refresh_token)
                elif connection.provider == EmailProvider.OUTLOOK:
                    token_data = await microsoft_client.refresh_token(refresh_token)

                # Encrypt and store new tokens
                await conn_repo.update_tokens(
                    connection.id,
                    access_token_encrypted=crypto.encrypt(token_data["access_token"]),
                    refresh_token_encrypted=crypto.encrypt(
                        token_data.get("refresh_token", refresh_token)
                    ),
                    token_expires_at=datetime.utcnow() + timedelta(
                        seconds=token_data["expires_in"]
                    ),
                )

            except Exception as e:
                # Mark connection as expired, notify user
                await conn_repo.mark_expired(connection.id, str(e))
```

### API Router

```python
# backend/app/modules/email/router.py
from fastapi import APIRouter, Depends, HTTPException, Query
from uuid import UUID
import secrets

from app.core.auth import get_current_tenant
from app.core.redis import redis_client
from app.modules.email.service import EmailService
from app.modules.email.schemas import (
    OAuthAuthorizeResponse,
    ConnectionListResponse,
    ConnectionDetailResponse,
    EmailListResponse,
)

router = APIRouter(prefix="/email", tags=["email"])

@router.get("/oauth/{provider}/authorize")
async def initiate_oauth(
    provider: str,
    redirect_uri: str = Query(None),
    tenant = Depends(get_current_tenant),
    service: EmailService = Depends(),
) -> OAuthAuthorizeResponse:
    """Initiate OAuth flow for Gmail or Outlook."""
    if provider not in ("gmail", "outlook"):
        raise HTTPException(status_code=400, detail="Invalid provider")

    # Generate state token
    state = secrets.token_urlsafe(32)

    # Store state in Redis (expires in 10 minutes)
    await redis_client.setex(
        f"email_oauth_state:{state}",
        600,
        f"{tenant.id}:{provider}:{redirect_uri or ''}",
    )

    # Get authorization URL
    auth_url = await service.get_authorization_url(provider, state)

    return OAuthAuthorizeResponse(
        authorization_url=auth_url,
        state=state,
    )

@router.get("/oauth/{provider}/callback")
async def handle_oauth_callback(
    provider: str,
    code: str = Query(...),
    state: str = Query(...),
    error: str = Query(None),
    service: EmailService = Depends(),
):
    """Handle OAuth callback from Gmail or Outlook."""
    if error:
        raise HTTPException(status_code=400, detail=f"OAuth error: {error}")

    # Validate state
    stored_state = await redis_client.get(f"email_oauth_state:{state}")
    if not stored_state:
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    tenant_id, stored_provider, redirect_uri = stored_state.decode().split(":", 2)

    if provider != stored_provider:
        raise HTTPException(status_code=400, detail="Provider mismatch")

    # Exchange code for tokens and create connection
    connection = await service.complete_oauth_flow(
        provider=provider,
        code=code,
        tenant_id=UUID(tenant_id),
    )

    # Clean up state
    await redis_client.delete(f"email_oauth_state:{state}")

    # Redirect to frontend
    if redirect_uri:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"{redirect_uri}?connection_id={connection.id}")

    return {"connection_id": str(connection.id), "status": "connected"}

@router.get("/connections")
async def list_connections(
    tenant = Depends(get_current_tenant),
    service: EmailService = Depends(),
) -> ConnectionListResponse:
    """List all email connections for the tenant."""
    connections = await service.list_connections(tenant.id)
    return ConnectionListResponse(items=connections)

@router.delete("/connections/{connection_id}")
async def disconnect_email(
    connection_id: UUID,
    tenant = Depends(get_current_tenant),
    service: EmailService = Depends(),
):
    """Disconnect an email account."""
    await service.disconnect(connection_id, tenant.id)
    return {"status": "disconnected"}

@router.get("/inbox")
async def list_emails(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    is_read: bool = Query(None),
    tenant = Depends(get_current_tenant),
    service: EmailService = Depends(),
) -> EmailListResponse:
    """List synced ATO emails."""
    return await service.list_emails(
        tenant_id=tenant.id,
        page=page,
        page_size=page_size,
        is_read=is_read,
    )
```

---

## Testing

### Unit Test: Token Encryption

```python
# backend/tests/unit/modules/email/test_crypto.py
import pytest
from app.modules.email.crypto import TokenEncryption
import base64
import secrets

@pytest.fixture
def crypto():
    key = base64.b64encode(secrets.token_bytes(32)).decode()
    return TokenEncryption(key)

def test_encrypt_decrypt_roundtrip(crypto):
    """Test that encrypt/decrypt preserves the original value."""
    original = "test_access_token_12345"
    encrypted = crypto.encrypt(original)
    decrypted = crypto.decrypt(encrypted)
    assert decrypted == original

def test_encrypted_value_is_different(crypto):
    """Test that encrypted value is different from original."""
    original = "test_token"
    encrypted = crypto.encrypt(original)
    assert encrypted != original
    assert len(encrypted) > len(original)

def test_different_encryptions_produce_different_output(crypto):
    """Test that encrypting same value twice produces different output (due to nonce)."""
    original = "test_token"
    encrypted1 = crypto.encrypt(original)
    encrypted2 = crypto.encrypt(original)
    assert encrypted1 != encrypted2  # Different nonces
```

### Integration Test: OAuth Flow

```python
# backend/tests/integration/api/test_email_oauth.py
import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_initiate_gmail_oauth(client: AsyncClient, auth_headers: dict):
    """Test initiating Gmail OAuth flow."""
    response = await client.get(
        "/api/v1/email/oauth/gmail/authorize",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert "authorization_url" in data
    assert "accounts.google.com" in data["authorization_url"]
    assert "state" in data

@pytest.mark.asyncio
async def test_initiate_outlook_oauth(client: AsyncClient, auth_headers: dict):
    """Test initiating Outlook OAuth flow."""
    response = await client.get(
        "/api/v1/email/oauth/outlook/authorize",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert "authorization_url" in data
    assert "login.microsoftonline.com" in data["authorization_url"]

@pytest.mark.asyncio
async def test_oauth_callback_invalid_state(client: AsyncClient):
    """Test OAuth callback with invalid state."""
    response = await client.get(
        "/api/v1/email/oauth/gmail/callback",
        params={"code": "test_code", "state": "invalid_state"},
    )

    assert response.status_code == 400
    assert "Invalid or expired state" in response.json()["detail"]

@pytest.mark.asyncio
async def test_list_connections_empty(client: AsyncClient, auth_headers: dict):
    """Test listing connections when none exist."""
    response = await client.get(
        "/api/v1/email/connections",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["items"] == []
```

### Mocking Gmail API

```python
# backend/tests/unit/modules/email/test_gmail_sync.py
import pytest
from unittest.mock import AsyncMock, patch
import respx
import httpx

from app.modules.email.sync.gmail_sync import GmailSyncService

@pytest.fixture
def gmail_messages_response():
    return {
        "messages": [
            {"id": "msg1", "threadId": "thread1"},
            {"id": "msg2", "threadId": "thread2"},
        ],
        "historyId": "12345",
    }

@pytest.fixture
def gmail_message_detail():
    return {
        "id": "msg1",
        "internalDate": "1704067200000",  # 2024-01-01
        "payload": {
            "headers": [
                {"name": "From", "value": "notices@ato.gov.au"},
                {"name": "To", "value": "accountant@example.com"},
                {"name": "Subject", "value": "Activity Statement Notice"},
            ],
            "mimeType": "text/plain",
            "body": {"data": "SGVsbG8gV29ybGQ="},  # "Hello World" base64
        },
    }

@pytest.mark.asyncio
@respx.mock
async def test_initial_backfill(gmail_messages_response, gmail_message_detail):
    """Test initial email backfill from Gmail."""
    # Mock Gmail API
    respx.get("https://gmail.googleapis.com/gmail/v1/users/me/messages").mock(
        return_value=httpx.Response(200, json=gmail_messages_response)
    )
    respx.get("https://gmail.googleapis.com/gmail/v1/users/me/messages/msg1").mock(
        return_value=httpx.Response(200, json=gmail_message_detail)
    )
    respx.get("https://gmail.googleapis.com/gmail/v1/users/me/messages/msg2").mock(
        return_value=httpx.Response(200, json=gmail_message_detail)
    )

    # Create mock repository
    mock_repo = AsyncMock()
    mock_repo.create_email = AsyncMock()
    mock_repo.update_sync_cursor = AsyncMock()

    # Create mock connection
    mock_connection = AsyncMock()
    mock_connection.tenant_id = "tenant-123"
    mock_connection.id = "conn-123"

    service = GmailSyncService(mock_repo)
    count = await service.initial_backfill(mock_connection, "fake_access_token")

    assert count == 2
    assert mock_repo.create_email.call_count == 2
    mock_repo.update_sync_cursor.assert_called_once()
```

---

## Celery Beat Configuration

```python
# backend/app/celery_config.py
from celery.schedules import crontab

beat_schedule = {
    "sync-email-connections": {
        "task": "app.modules.email.sync.scheduler.sync_all_email_connections",
        "schedule": crontab(minute="*/15"),  # Every 15 minutes
    },
    "refresh-expiring-tokens": {
        "task": "app.modules.email.sync.scheduler.refresh_expiring_tokens",
        "schedule": crontab(minute="*/30"),  # Every 30 minutes
    },
}
```

---

## Frontend Components

### Connection Card

```tsx
// frontend/src/components/email/ConnectionCard.tsx
'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Mail, RefreshCw, Unlink } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

interface ConnectionCardProps {
  connection: {
    id: string;
    provider: 'GMAIL' | 'OUTLOOK';
    email_address: string;
    status: 'ACTIVE' | 'EXPIRED' | 'REVOKED';
    last_sync_at: string | null;
  };
  onDisconnect: (id: string) => void;
  onReconnect: (id: string) => void;
}

export function ConnectionCard({ connection, onDisconnect, onReconnect }: ConnectionCardProps) {
  const statusColors = {
    ACTIVE: 'bg-green-100 text-green-800',
    EXPIRED: 'bg-yellow-100 text-yellow-800',
    REVOKED: 'bg-red-100 text-red-800',
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div className="flex items-center gap-3">
          <Mail className="h-5 w-5" />
          <div>
            <CardTitle className="text-sm font-medium">
              {connection.email_address}
            </CardTitle>
            <p className="text-xs text-muted-foreground">
              {connection.provider === 'GMAIL' ? 'Gmail' : 'Outlook'}
            </p>
          </div>
        </div>
        <Badge className={statusColors[connection.status]}>
          {connection.status}
        </Badge>
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            {connection.last_sync_at
              ? `Last synced ${formatDistanceToNow(new Date(connection.last_sync_at))} ago`
              : 'Never synced'}
          </p>
          <div className="flex gap-2">
            {connection.status === 'EXPIRED' && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => onReconnect(connection.id)}
              >
                <RefreshCw className="h-4 w-4 mr-1" />
                Reconnect
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onDisconnect(connection.id)}
            >
              <Unlink className="h-4 w-4 mr-1" />
              Disconnect
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
```

### Connect Buttons

```tsx
// frontend/src/components/email/ConnectEmailButtons.tsx
'use client';

import { Button } from '@/components/ui/button';
import { useEmailApi } from '@/lib/api/email';
import { useState } from 'react';

export function ConnectGmailButton() {
  const [isLoading, setIsLoading] = useState(false);
  const { initiateOAuth } = useEmailApi();

  const handleConnect = async () => {
    setIsLoading(true);
    try {
      const { authorization_url } = await initiateOAuth('gmail');
      window.location.href = authorization_url;
    } catch (error) {
      console.error('Failed to initiate OAuth:', error);
      setIsLoading(false);
    }
  };

  return (
    <Button onClick={handleConnect} disabled={isLoading}>
      {isLoading ? 'Connecting...' : 'Connect Gmail'}
    </Button>
  );
}

export function ConnectOutlookButton() {
  const [isLoading, setIsLoading] = useState(false);
  const { initiateOAuth } = useEmailApi();

  const handleConnect = async () => {
    setIsLoading(true);
    try {
      const { authorization_url } = await initiateOAuth('outlook');
      window.location.href = authorization_url;
    } catch (error) {
      console.error('Failed to initiate OAuth:', error);
      setIsLoading(false);
    }
  };

  return (
    <Button variant="outline" onClick={handleConnect} disabled={isLoading}>
      {isLoading ? 'Connecting...' : 'Connect Outlook'}
    </Button>
  );
}
```

---

## Verification Checklist

- [ ] OAuth credentials configured in Google Cloud Console
- [ ] OAuth credentials configured in Azure Portal
- [ ] `EMAIL_TOKEN_ENCRYPTION_KEY` generated and set
- [ ] Redis available for OAuth state storage
- [ ] Celery beat running for scheduled sync
- [ ] Gmail connection flow works end-to-end
- [ ] Microsoft connection flow works end-to-end
- [ ] Token refresh happens before expiry
- [ ] Only @ato.gov.au emails are synced
- [ ] Emails visible in inbox after sync

---

## Common Issues

| Issue | Solution |
|-------|----------|
| "Invalid redirect URI" | Ensure callback URL in console matches exactly |
| "State mismatch" | Check Redis connection, state may have expired |
| "Token refresh failed" | User may have revoked access, prompt reconnection |
| "Rate limit exceeded" | Implement exponential backoff, reduce sync frequency |
| "No emails syncing" | Verify ATO domain filter, check query syntax |
