# Quickstart Guide: Client Portal Foundation + Document Requests

**Spec**: 030-client-portal-document-requests
**Branch**: `030-client-portal-document-requests`
**Module**: `backend/app/modules/portal/`

## Overview

This guide covers implementing the client portal with magic link authentication and the ClientChase document request workflow.

## Prerequisites

Before implementing this spec:

1. **Clients Module** - Client records exist
2. **Documents Module** - Document storage configured
3. **Notifications Module** - Resend email integration
4. **S3/MinIO** - Object storage for uploads
5. **BAS Module** - BAS status for dashboard

## Quick Verification

```bash
# Verify prerequisites
cd /Users/suren/KR8IT/projects/Personal/BAS
SPECIFY_FEATURE="030-client-portal-document-requests" .specify/scripts/bash/check-prerequisites.sh

# Run tests after implementation
uv run pytest tests/unit/modules/portal/ -v
uv run pytest tests/integration/api/test_portal*.py -v
```

---

## 1. Magic Link Authentication

### Token Generation

```python
# backend/app/modules/portal/auth/magic_link.py
from datetime import datetime, timedelta, UTC
from uuid import UUID, uuid4
import jwt
from app.config import settings

class MagicLinkService:
    """Generate and verify magic link tokens for portal authentication."""

    TOKEN_EXPIRY_DAYS = 7
    SESSION_ACCESS_EXPIRY_HOURS = 1
    SESSION_REFRESH_EXPIRY_DAYS = 30

    def __init__(self):
        self.secret_key = settings.SECRET_KEY
        self.algorithm = "HS256"

    def generate_magic_link_token(
        self,
        client_id: UUID,
        email: str,
        tenant_id: UUID,
    ) -> str:
        """Generate a magic link JWT token (7-day expiry)."""
        now = datetime.now(UTC)
        payload = {
            "type": "magic_link",
            "client_id": str(client_id),
            "tenant_id": str(tenant_id),
            "email": email,
            "jti": str(uuid4()),  # Unique token ID for revocation
            "iat": now,
            "exp": now + timedelta(days=self.TOKEN_EXPIRY_DAYS),
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_magic_link_token(self, token: str) -> dict | None:
        """Verify magic link token and return payload."""
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
            )
            if payload.get("type") != "magic_link":
                return None
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def create_session_tokens(
        self,
        client_id: UUID,
        tenant_id: UUID,
        session_id: UUID,
    ) -> tuple[str, str]:
        """Create access and refresh tokens for portal session."""
        now = datetime.now(UTC)

        # Access token (1 hour)
        access_payload = {
            "type": "portal_access",
            "client_id": str(client_id),
            "tenant_id": str(tenant_id),
            "session_id": str(session_id),
            "exp": now + timedelta(hours=self.SESSION_ACCESS_EXPIRY_HOURS),
        }
        access_token = jwt.encode(
            access_payload, self.secret_key, algorithm=self.algorithm
        )

        # Refresh token (30 days)
        refresh_payload = {
            "type": "portal_refresh",
            "session_id": str(session_id),
            "jti": str(uuid4()),
            "exp": now + timedelta(days=self.SESSION_REFRESH_EXPIRY_DAYS),
        }
        refresh_token = jwt.encode(
            refresh_payload, self.secret_key, algorithm=self.algorithm
        )

        return access_token, refresh_token

    def verify_access_token(self, token: str) -> dict | None:
        """Verify portal access token."""
        try:
            payload = jwt.decode(
                token, self.secret_key, algorithms=[self.algorithm]
            )
            if payload.get("type") != "portal_access":
                return None
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
```

### Portal Authentication Dependency

```python
# backend/app/modules/portal/auth/dependencies.py
from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.modules.portal.auth.magic_link import MagicLinkService
from app.modules.portal.repository import PortalSessionRepository
from app.modules.portal.schemas import PortalClient

security = HTTPBearer()
magic_link_service = MagicLinkService()


async def get_current_portal_client(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_async_session),
) -> PortalClient:
    """
    Dependency to get the currently authenticated portal client.
    Validates the portal access token and returns client details.
    """
    token = credentials.credentials
    payload = magic_link_service.verify_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    # Verify session is still valid
    session_repo = PortalSessionRepository(session)
    portal_session = await session_repo.get_active_session(
        UUID(payload["session_id"])
    )

    if not portal_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or revoked",
        )

    return PortalClient(
        id=UUID(payload["client_id"]),
        tenant_id=UUID(payload["tenant_id"]),
        session_id=UUID(payload["session_id"]),
    )
```

### Auth Router

```python
# backend/app/modules/portal/auth/router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.database import get_async_session
from app.modules.portal.auth.magic_link import MagicLinkService
from app.modules.portal.auth.dependencies import get_current_portal_client
from app.modules.portal.repository import (
    PortalInvitationRepository,
    PortalSessionRepository,
)
from app.modules.portal.schemas import (
    MagicLinkRequest,
    MagicLinkResponse,
    VerifyTokenRequest,
    AuthResponse,
    RefreshTokenRequest,
)
from app.modules.clients.repository import ClientRepository
from app.modules.notifications.service import NotificationService

router = APIRouter(prefix="/portal/auth", tags=["Portal Auth"])
magic_link_service = MagicLinkService()


@router.post("/request-link", response_model=MagicLinkResponse)
async def request_magic_link(
    request: MagicLinkRequest,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Request a magic link for portal login.
    Always returns 200 to prevent email enumeration.
    """
    client_repo = ClientRepository(session)
    notification_service = NotificationService(session)

    # Find client by email
    client = await client_repo.get_by_email(request.email)

    if client and client.portal_enabled:
        # Generate magic link
        token = magic_link_service.generate_magic_link_token(
            client_id=client.id,
            email=request.email,
            tenant_id=client.tenant_id,
        )

        # Send magic link email
        await notification_service.send_portal_magic_link(
            client=client,
            token=token,
        )

    # Always return success to prevent enumeration
    return MagicLinkResponse(
        message="If this email is registered, you'll receive a login link shortly"
    )


@router.post("/verify", response_model=AuthResponse)
async def verify_magic_link(
    request: VerifyTokenRequest,
    session: AsyncSession = Depends(get_async_session),
):
    """Verify magic link token and create portal session."""
    # Verify token
    payload = magic_link_service.verify_magic_link_token(request.token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired magic link",
        )

    # Create session
    session_repo = PortalSessionRepository(session)
    portal_session = await session_repo.create_session(
        client_id=UUID(payload["client_id"]),
        tenant_id=UUID(payload["tenant_id"]),
    )

    # Generate tokens
    access_token, refresh_token = magic_link_service.create_session_tokens(
        client_id=portal_session.client_id,
        tenant_id=portal_session.tenant_id,
        session_id=portal_session.id,
    )

    # Get client details
    client_repo = ClientRepository(session)
    client = await client_repo.get(portal_session.client_id)

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=3600,
        client={
            "id": client.id,
            "business_name": client.business_name,
            "abn": client.abn,
        },
    )


@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    session: AsyncSession = Depends(get_async_session),
):
    """Refresh access token using refresh token."""
    payload = magic_link_service.verify_refresh_token(request.refresh_token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    session_repo = PortalSessionRepository(session)
    portal_session = await session_repo.get_active_session(
        UUID(payload["session_id"])
    )

    if not portal_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or revoked",
        )

    # Generate new tokens
    access_token, refresh_token = magic_link_service.create_session_tokens(
        client_id=portal_session.client_id,
        tenant_id=portal_session.tenant_id,
        session_id=portal_session.id,
    )

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=3600,
    )


@router.post("/logout", status_code=204)
async def logout(
    client: PortalClient = Depends(get_current_portal_client),
    session: AsyncSession = Depends(get_async_session),
):
    """Logout and invalidate current session."""
    session_repo = PortalSessionRepository(session)
    await session_repo.revoke_session(client.session_id)
```

---

## 2. Document Request Templates

### Built-in Templates

```python
# backend/app/modules/portal/requests/templates.py
from enum import Enum
from uuid import UUID
from dataclasses import dataclass

class TemplateCategory(str, Enum):
    BAS_PREPARATION = "bas_preparation"
    YEAR_END = "year_end"
    COMPLIANCE = "compliance"
    GENERAL = "general"


@dataclass
class SystemTemplate:
    id: str  # Stable ID for system templates
    name: str
    description_template: str
    expected_document_types: list[str]
    default_priority: str
    default_due_days: int
    category: TemplateCategory


SYSTEM_TEMPLATES = [
    SystemTemplate(
        id="bank-statements-quarterly",
        name="Bank Statements - Quarterly",
        description_template=(
            "Please upload all bank statements for {period}.\n\n"
            "We need statements for all business bank accounts including:\n"
            "- Primary business account\n"
            "- Savings accounts\n"
            "- Credit card statements\n\n"
            "These are required to complete your BAS preparation."
        ),
        expected_document_types=["bank_statement", "pdf"],
        default_priority="normal",
        default_due_days=7,
        category=TemplateCategory.BAS_PREPARATION,
    ),
    SystemTemplate(
        id="receipts-expenses",
        name="Expense Receipts",
        description_template=(
            "Please upload receipts for business expenses in {period}.\n\n"
            "Include receipts for:\n"
            "- Office supplies\n"
            "- Travel expenses\n"
            "- Client entertainment\n"
            "- Any other deductible expenses\n\n"
            "Photo of receipts is fine - just ensure the details are legible."
        ),
        expected_document_types=["receipt", "invoice", "pdf"],
        default_priority="normal",
        default_due_days=7,
        category=TemplateCategory.BAS_PREPARATION,
    ),
    SystemTemplate(
        id="sales-invoices",
        name="Sales Invoices",
        description_template=(
            "Please upload all sales invoices issued in {period}.\n\n"
            "These are needed to verify GST collected and ensure "
            "your BAS accurately reflects all sales."
        ),
        expected_document_types=["invoice", "pdf"],
        default_priority="normal",
        default_due_days=7,
        category=TemplateCategory.BAS_PREPARATION,
    ),
    SystemTemplate(
        id="payroll-summary",
        name="Payroll Summary",
        description_template=(
            "Please upload your payroll summary for {period}.\n\n"
            "This should include:\n"
            "- Gross wages paid\n"
            "- PAYG withholding amounts\n"
            "- Superannuation contributions\n\n"
            "If you use a payroll system, export the period summary report."
        ),
        expected_document_types=["payroll", "pdf"],
        default_priority="high",
        default_due_days=5,
        category=TemplateCategory.BAS_PREPARATION,
    ),
    SystemTemplate(
        id="eofy-bank-statements",
        name="End of Year Bank Statements",
        description_template=(
            "Please upload bank statements for the full financial year "
            "(1 July to 30 June).\n\n"
            "These are required for your end of financial year processing."
        ),
        expected_document_types=["bank_statement", "pdf"],
        default_priority="high",
        default_due_days=14,
        category=TemplateCategory.YEAR_END,
    ),
    SystemTemplate(
        id="motor-vehicle-logbook",
        name="Motor Vehicle Logbook",
        description_template=(
            "Please upload your motor vehicle logbook for the financial year.\n\n"
            "Include:\n"
            "- Odometer readings (start and end of year)\n"
            "- Trip log or logbook app export\n"
            "- Fuel receipts (if claiming actuals)"
        ),
        expected_document_types=["pdf", "other"],
        default_priority="normal",
        default_due_days=14,
        category=TemplateCategory.YEAR_END,
    ),
]


def get_system_template(template_id: str) -> SystemTemplate | None:
    """Get a system template by ID."""
    for template in SYSTEM_TEMPLATES:
        if template.id == template_id:
            return template
    return None


def personalize_description(
    template: str,
    client_name: str,
    period: str | None = None,
) -> str:
    """Replace template variables with actual values."""
    result = template.replace("{client_name}", client_name)
    if period:
        result = result.replace("{period}", period)
    return result
```

---

## 3. Document Request Service

```python
# backend/app/modules/portal/requests/service.py
from uuid import UUID
from datetime import date, datetime, UTC
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.portal.requests.models import (
    DocumentRequest,
    RequestStatus,
    RequestPriority,
    RequestResponse,
    RequestEvent,
    EventType,
)
from app.modules.portal.repository import (
    DocumentRequestRepository,
    RequestResponseRepository,
    RequestEventRepository,
)
from app.modules.clients.repository import ClientRepository
from app.modules.notifications.service import NotificationService
from app.core.audit import audit_log


class DocumentRequestService:
    """Service for managing document requests (ClientChase)."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.request_repo = DocumentRequestRepository(session)
        self.response_repo = RequestResponseRepository(session)
        self.event_repo = RequestEventRepository(session)
        self.client_repo = ClientRepository(session)
        self.notification_service = NotificationService(session)

    async def create_request(
        self,
        tenant_id: UUID,
        client_id: UUID,
        created_by: UUID,
        title: str,
        description: str,
        due_date: date | None = None,
        priority: RequestPriority = RequestPriority.NORMAL,
        expected_document_types: list[str] | None = None,
        template_id: UUID | None = None,
        auto_remind: bool = True,
        send_immediately: bool = False,
    ) -> DocumentRequest:
        """Create a new document request."""
        # Create request
        request = await self.request_repo.create(
            tenant_id=tenant_id,
            client_id=client_id,
            created_by=created_by,
            template_id=template_id,
            title=title,
            description=description,
            due_date=due_date,
            priority=priority,
            expected_document_types=expected_document_types or [],
            auto_remind=auto_remind,
            status=RequestStatus.DRAFT if not send_immediately else RequestStatus.PENDING,
        )

        # Log event
        await self._log_event(
            request_id=request.id,
            event_type=EventType.CREATED,
            actor_type="accountant",
            actor_id=created_by,
        )

        # Send if requested
        if send_immediately:
            await self._send_request(request, created_by)

        # Audit
        await audit_log(
            self.session,
            action="request.created",
            resource_type="document_request",
            resource_id=request.id,
            user_id=created_by,
            tenant_id=tenant_id,
        )

        return request

    async def send_request(
        self,
        request_id: UUID,
        sent_by: UUID,
    ) -> DocumentRequest:
        """Send a draft request to the client."""
        request = await self.request_repo.get(request_id)

        if request.status != RequestStatus.DRAFT:
            raise ValueError("Can only send draft requests")

        await self._send_request(request, sent_by)

        return await self.request_repo.get(request_id)

    async def _send_request(
        self,
        request: DocumentRequest,
        sent_by: UUID,
    ) -> None:
        """Internal: Send request and notify client."""
        # Update status
        request.status = RequestStatus.PENDING
        request.sent_at = datetime.now(UTC)
        await self.session.commit()

        # Get client
        client = await self.client_repo.get(request.client_id)

        # Send notification
        await self.notification_service.send_document_request(
            client=client,
            request=request,
        )

        # Log event
        await self._log_event(
            request_id=request.id,
            event_type=EventType.SENT,
            actor_type="accountant",
            actor_id=sent_by,
        )

    async def mark_viewed(
        self,
        request_id: UUID,
        client_id: UUID,
    ) -> DocumentRequest:
        """Mark request as viewed by client."""
        request = await self.request_repo.get(request_id)

        if request.client_id != client_id:
            raise PermissionError("Cannot view other client's request")

        if request.status == RequestStatus.PENDING:
            request.status = RequestStatus.VIEWED
            request.viewed_at = datetime.now(UTC)
            await self.session.commit()

            # Log event
            await self._log_event(
                request_id=request.id,
                event_type=EventType.VIEWED,
                actor_type="client",
                actor_id=client_id,
            )

        return request

    async def submit_response(
        self,
        request_id: UUID,
        client_id: UUID,
        document_ids: list[UUID],
        note: str | None = None,
    ) -> RequestResponse:
        """Submit a response to a request."""
        request = await self.request_repo.get(request_id)

        if request.client_id != client_id:
            raise PermissionError("Cannot respond to other client's request")

        if request.status not in [RequestStatus.PENDING, RequestStatus.VIEWED]:
            raise ValueError("Cannot respond to completed or cancelled request")

        if not document_ids:
            raise ValueError("At least one document is required")

        # Create response
        response = await self.response_repo.create(
            request_id=request_id,
            document_ids=document_ids,
            note=note,
        )

        # Update request status
        request.status = RequestStatus.RESPONDED
        request.responded_at = datetime.now(UTC)
        await self.session.commit()

        # Log event
        await self._log_event(
            request_id=request.id,
            event_type=EventType.RESPONDED,
            actor_type="client",
            actor_id=client_id,
            metadata={"document_count": len(document_ids)},
        )

        # Notify accountant
        await self.notification_service.notify_request_response(
            request=request,
            response=response,
        )

        return response

    async def complete_request(
        self,
        request_id: UUID,
        completed_by: UUID,
        note: str | None = None,
    ) -> DocumentRequest:
        """Mark a responded request as complete."""
        request = await self.request_repo.get(request_id)

        if request.status != RequestStatus.RESPONDED:
            raise ValueError("Can only complete responded requests")

        request.status = RequestStatus.COMPLETE
        request.completed_at = datetime.now(UTC)
        await self.session.commit()

        # Log event
        await self._log_event(
            request_id=request.id,
            event_type=EventType.COMPLETED,
            actor_type="accountant",
            actor_id=completed_by,
            metadata={"note": note} if note else None,
        )

        return request

    async def send_reminder(
        self,
        request_id: UUID,
        sent_by: UUID | None = None,
        is_auto: bool = False,
        custom_message: str | None = None,
    ) -> bool:
        """Send a reminder for a pending request."""
        request = await self.request_repo.get(request_id)

        if request.status not in [RequestStatus.PENDING, RequestStatus.VIEWED]:
            return False

        client = await self.client_repo.get(request.client_id)

        # Send reminder
        await self.notification_service.send_request_reminder(
            client=client,
            request=request,
            is_overdue=request.is_overdue,
            custom_message=custom_message,
        )

        # Update reminder count
        request.reminder_count += 1
        request.last_reminder_at = datetime.now(UTC)
        await self.session.commit()

        # Log event
        await self._log_event(
            request_id=request.id,
            event_type=EventType.REMINDER_SENT,
            actor_type="system" if is_auto else "accountant",
            actor_id=sent_by,
            metadata={"is_auto": is_auto, "reminder_count": request.reminder_count},
        )

        return True

    async def _log_event(
        self,
        request_id: UUID,
        event_type: EventType,
        actor_type: str,
        actor_id: UUID | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Log a request event."""
        await self.event_repo.create(
            request_id=request_id,
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            metadata=metadata,
        )
```

---

## 4. Bulk Request Processing

```python
# backend/app/modules/portal/requests/bulk.py
from uuid import UUID
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.portal.requests.service import DocumentRequestService
from app.modules.portal.requests.templates import personalize_description
from app.modules.portal.requests.models import (
    BulkRequest,
    BulkRequestItem,
    BulkStatus,
    RequestPriority,
)
from app.modules.portal.repository import BulkRequestRepository
from app.modules.clients.repository import ClientRepository


class BulkRequestService:
    """Service for processing bulk document requests."""

    MAX_CLIENTS_PER_BATCH = 500

    def __init__(self, session: AsyncSession):
        self.session = session
        self.bulk_repo = BulkRequestRepository(session)
        self.client_repo = ClientRepository(session)
        self.request_service = DocumentRequestService(session)

    async def create_bulk_request(
        self,
        tenant_id: UUID,
        created_by: UUID,
        client_ids: list[UUID],
        title_template: str,
        description_template: str,
        due_date: date | None = None,
        priority: RequestPriority = RequestPriority.NORMAL,
        expected_document_types: list[str] | None = None,
        auto_remind: bool = True,
    ) -> BulkRequest:
        """Create a bulk request for multiple clients."""
        if len(client_ids) > self.MAX_CLIENTS_PER_BATCH:
            raise ValueError(f"Maximum {self.MAX_CLIENTS_PER_BATCH} clients per batch")

        # Create bulk request record
        bulk = await self.bulk_repo.create(
            tenant_id=tenant_id,
            created_by=created_by,
            title_template=title_template,
            description_template=description_template,
            client_count=len(client_ids),
        )

        # Create individual items (pending)
        for client_id in client_ids:
            await self.bulk_repo.create_item(
                bulk_id=bulk.id,
                client_id=client_id,
                status=BulkStatus.PENDING,
            )

        await self.session.commit()
        return bulk

    async def process_bulk_request(self, bulk_id: UUID) -> BulkRequest:
        """Process all items in a bulk request (called by Celery task)."""
        bulk = await self.bulk_repo.get(bulk_id)
        bulk.status = BulkStatus.PROCESSING
        await self.session.commit()

        items = await self.bulk_repo.get_items(bulk_id)
        success_count = 0
        failed_count = 0

        for item in items:
            try:
                # Get client for personalization
                client = await self.client_repo.get(item.client_id)

                # Personalize templates
                title = personalize_description(
                    bulk.title_template,
                    client_name=client.business_name,
                )
                description = personalize_description(
                    bulk.description_template,
                    client_name=client.business_name,
                    period=bulk.period,
                )

                # Create and send request
                request = await self.request_service.create_request(
                    tenant_id=bulk.tenant_id,
                    client_id=item.client_id,
                    created_by=bulk.created_by,
                    title=title,
                    description=description,
                    due_date=bulk.due_date,
                    priority=bulk.priority,
                    expected_document_types=bulk.expected_document_types,
                    auto_remind=bulk.auto_remind,
                    send_immediately=True,
                )

                # Update item
                item.request_id = request.id
                item.status = BulkStatus.SENT
                success_count += 1

            except Exception as e:
                item.status = BulkStatus.FAILED
                item.error = str(e)
                failed_count += 1

        # Update bulk status
        bulk.success_count = success_count
        bulk.failed_count = failed_count
        bulk.status = BulkStatus.COMPLETED
        await self.session.commit()

        return bulk

    async def preview_bulk_request(
        self,
        tenant_id: UUID,
        client_ids: list[UUID],
        title_template: str,
        description_template: str,
        period: str | None = None,
    ) -> list[dict]:
        """Preview personalized requests without sending."""
        previews = []

        for client_id in client_ids:
            try:
                client = await self.client_repo.get(client_id)

                title = personalize_description(
                    title_template,
                    client_name=client.business_name,
                )
                description = personalize_description(
                    description_template,
                    client_name=client.business_name,
                    period=period,
                )

                previews.append({
                    "client": {
                        "id": client.id,
                        "business_name": client.business_name,
                        "contact_email": client.email,
                    },
                    "title": title,
                    "description": description,
                    "valid": True,
                    "validation_error": None,
                })

            except Exception as e:
                previews.append({
                    "client": {"id": client_id},
                    "valid": False,
                    "validation_error": str(e),
                })

        return previews
```

---

## 5. Auto-Reminder Celery Task

```python
# backend/app/tasks/portal/auto_reminders.py
from datetime import datetime, date, timedelta, UTC
from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.modules.portal.requests.models import RequestStatus
from app.modules.portal.repository import DocumentRequestRepository
from app.modules.portal.requests.service import DocumentRequestService


# Reminder schedule: days relative to due date
REMINDER_SCHEDULE = [
    {"days_before_due": 3, "template": "reminder_3_days"},
    {"days_before_due": 1, "template": "reminder_1_day"},
    {"days_after_due": 1, "template": "overdue_1_day"},
    {"days_after_due": 3, "template": "overdue_3_days"},
    {"days_after_due": 7, "template": "overdue_7_days"},
]


@shared_task(name="portal.auto_reminders")
async def process_auto_reminders():
    """
    Daily task to send auto-reminders for pending requests.
    Runs at configured time (default 9 AM tenant timezone).
    """
    async with async_session_factory() as session:
        request_repo = DocumentRequestRepository(session)
        request_service = DocumentRequestService(session)

        today = date.today()

        # Get all pending/viewed requests with auto_remind enabled
        pending_requests = await request_repo.get_pending_with_auto_remind()

        for request in pending_requests:
            if not request.due_date:
                continue

            days_until_due = (request.due_date - today).days

            # Check if we should send a reminder today
            should_remind = False
            is_overdue = days_until_due < 0

            for schedule in REMINDER_SCHEDULE:
                if schedule.get("days_before_due"):
                    if days_until_due == schedule["days_before_due"]:
                        should_remind = True
                        break
                elif schedule.get("days_after_due"):
                    if days_until_due == -schedule["days_after_due"]:
                        should_remind = True
                        break

            if should_remind:
                await request_service.send_reminder(
                    request_id=request.id,
                    is_auto=True,
                )


@shared_task(name="portal.send_bulk_requests")
async def process_bulk_request(bulk_id: str):
    """Process a bulk request asynchronously."""
    from uuid import UUID
    from app.modules.portal.requests.bulk import BulkRequestService

    async with async_session_factory() as session:
        bulk_service = BulkRequestService(session)
        await bulk_service.process_bulk_request(UUID(bulk_id))
```

---

## 6. Document Upload Service

```python
# backend/app/modules/portal/documents/upload.py
from uuid import UUID, uuid4
from datetime import datetime, UTC
import mimetypes
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.documents.storage import StorageService
from app.modules.portal.models import PortalDocument
from app.modules.portal.repository import PortalDocumentRepository


class PortalUploadService:
    """Service for handling document uploads from the portal."""

    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    ALLOWED_TYPES = [
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/heic",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/csv",
    ]

    def __init__(self, session: AsyncSession):
        self.session = session
        self.doc_repo = PortalDocumentRepository(session)
        self.storage = StorageService()

    async def upload_document(
        self,
        tenant_id: UUID,
        client_id: UUID,
        file_content: bytes,
        original_filename: str,
        document_type: str = "other",
        period: str | None = None,
        request_id: UUID | None = None,
    ) -> PortalDocument:
        """Upload a document from the portal."""
        # Validate file size
        if len(file_content) > self.MAX_FILE_SIZE:
            raise ValueError(f"File too large. Maximum size is {self.MAX_FILE_SIZE // 1024 // 1024}MB")

        # Detect MIME type
        mime_type, _ = mimetypes.guess_type(original_filename)
        if mime_type not in self.ALLOWED_TYPES:
            raise ValueError(f"File type not allowed: {mime_type}")

        # Generate storage key
        file_id = uuid4()
        extension = original_filename.rsplit(".", 1)[-1] if "." in original_filename else ""
        storage_key = f"portal/{tenant_id}/{client_id}/{file_id}.{extension}"

        # Upload to S3
        await self.storage.upload(
            key=storage_key,
            content=file_content,
            content_type=mime_type,
        )

        # Create document record
        document = await self.doc_repo.create(
            id=file_id,
            tenant_id=tenant_id,
            client_id=client_id,
            request_id=request_id,
            original_filename=original_filename,
            storage_key=storage_key,
            mime_type=mime_type,
            size_bytes=len(file_content),
            document_type=document_type,
            period=period,
        )

        return document

    async def get_presigned_upload_url(
        self,
        tenant_id: UUID,
        client_id: UUID,
        filename: str,
        content_type: str,
    ) -> tuple[str, UUID]:
        """Get a presigned URL for direct upload."""
        if content_type not in self.ALLOWED_TYPES:
            raise ValueError(f"File type not allowed: {content_type}")

        file_id = uuid4()
        extension = filename.rsplit(".", 1)[-1] if "." in filename else ""
        storage_key = f"portal/{tenant_id}/{client_id}/{file_id}.{extension}"

        upload_url = await self.storage.get_presigned_upload_url(
            key=storage_key,
            content_type=content_type,
            expires_in=900,  # 15 minutes
        )

        return upload_url, file_id

    async def get_download_url(
        self,
        document_id: UUID,
        client_id: UUID,
    ) -> str:
        """Get a presigned download URL for a document."""
        document = await self.doc_repo.get(document_id)

        if document.client_id != client_id:
            raise PermissionError("Cannot download other client's document")

        return await self.storage.get_presigned_download_url(
            key=document.storage_key,
            expires_in=900,  # 15 minutes
        )
```

---

## 7. Portal Dashboard Service

```python
# backend/app/modules/portal/dashboard/service.py
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.clients.repository import ClientRepository
from app.modules.bas.repository import BASRepository
from app.modules.portal.repository import (
    DocumentRequestRepository,
    PortalDocumentRepository,
)
from app.modules.portal.requests.models import RequestStatus


class PortalDashboardService:
    """Aggregates dashboard data for the client portal."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.client_repo = ClientRepository(session)
        self.bas_repo = BASRepository(session)
        self.request_repo = DocumentRequestRepository(session)
        self.doc_repo = PortalDocumentRepository(session)

    async def get_dashboard(self, client_id: UUID) -> dict:
        """Get aggregated dashboard data for a client."""
        client = await self.client_repo.get(client_id)

        # Get BAS status
        current_bas = await self.bas_repo.get_current_period(client_id)
        bas_status = None
        if current_bas:
            bas_status = {
                "current_period": current_bas.period,
                "status": current_bas.status,
                "due_date": current_bas.due_date,
                "days_until_due": (current_bas.due_date - date.today()).days
                if current_bas.due_date else None,
            }

        # Get pending requests
        pending_requests = await self.request_repo.count_by_status(
            client_id=client_id,
            statuses=[RequestStatus.PENDING, RequestStatus.VIEWED],
        )
        overdue_requests = await self.request_repo.count_overdue(client_id)

        # Get recent activity
        recent_activity = await self._get_recent_activity(client_id)

        # Get metrics
        metrics = await self._get_client_metrics(client_id)

        return {
            "client": {
                "id": client.id,
                "business_name": client.business_name,
                "abn": client.abn,
                "accountant": {
                    "name": client.accountant_name,
                    "firm_name": client.tenant.name,
                },
            },
            "bas_status": bas_status,
            "action_items": {
                "pending_requests": pending_requests,
                "overdue_requests": overdue_requests,
                "total": pending_requests,
            },
            "recent_activity": recent_activity[:5],
            "metrics": metrics,
        }

    async def _get_recent_activity(self, client_id: UUID) -> list[dict]:
        """Get recent activity for the client."""
        # Combine request events and BAS status changes
        activities = []

        # Recent requests
        requests = await self.request_repo.get_recent(client_id, limit=10)
        for req in requests:
            activities.append({
                "id": req.id,
                "type": "request_received",
                "title": f"Document request: {req.title}",
                "description": f"Due {req.due_date}" if req.due_date else "No due date",
                "timestamp": req.created_at,
                "link": f"/portal/requests/{req.id}",
            })

        # Sort by timestamp
        activities.sort(key=lambda x: x["timestamp"], reverse=True)
        return activities

    async def _get_client_metrics(self, client_id: UUID) -> dict:
        """Calculate client response metrics."""
        stats = await self.request_repo.get_response_stats(client_id)

        return {
            "response_rate": stats.get("response_rate", 0),
            "avg_response_days": stats.get("avg_response_days", 0),
            "documents_uploaded": await self.doc_repo.count_by_client(client_id),
        }
```

---

## 8. Frontend Portal Components

### Portal Layout

```typescript
// frontend/src/app/portal/layout.tsx
import { PortalHeader } from "@/components/portal/PortalHeader";
import { PortalAuthProvider } from "@/components/portal/PortalAuthProvider";

export default function PortalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <PortalAuthProvider>
      <div className="min-h-screen bg-slate-50">
        <PortalHeader />
        <main className="container mx-auto px-4 py-6">
          {children}
        </main>
      </div>
    </PortalAuthProvider>
  );
}
```

### Request Response Form

```typescript
// frontend/src/components/portal/RespondForm.tsx
"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { DocumentUploader } from "./DocumentUploader";
import { usePortalApi } from "@/lib/api/portal";

const responseSchema = z.object({
  documentIds: z.array(z.string().uuid()).min(1, "At least one document required"),
  note: z.string().max(2000).optional(),
});

type ResponseFormData = z.infer<typeof responseSchema>;

interface RespondFormProps {
  requestId: string;
  expectedTypes: string[];
  onSuccess: () => void;
}

export function RespondForm({ requestId, expectedTypes, onSuccess }: RespondFormProps) {
  const [uploadedDocIds, setUploadedDocIds] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { submitResponse } = usePortalApi();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ResponseFormData>({
    resolver: zodResolver(responseSchema),
    defaultValues: {
      documentIds: [],
      note: "",
    },
  });

  const onSubmit = async (data: ResponseFormData) => {
    setIsSubmitting(true);
    try {
      await submitResponse(requestId, {
        document_ids: uploadedDocIds,
        note: data.note || undefined,
      });
      onSuccess();
    } catch (error) {
      console.error("Failed to submit response:", error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUploadComplete = (docId: string) => {
    setUploadedDocIds((prev) => [...prev, docId]);
  };

  const handleRemoveDocument = (docId: string) => {
    setUploadedDocIds((prev) => prev.filter((id) => id !== docId));
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
      <div>
        <label className="block text-sm font-medium mb-2">
          Upload Documents
        </label>
        <DocumentUploader
          requestId={requestId}
          expectedTypes={expectedTypes}
          uploadedIds={uploadedDocIds}
          onUploadComplete={handleUploadComplete}
          onRemove={handleRemoveDocument}
        />
        {errors.documentIds && (
          <p className="text-red-500 text-sm mt-1">
            {errors.documentIds.message}
          </p>
        )}
      </div>

      <div>
        <label className="block text-sm font-medium mb-2">
          Note (optional)
        </label>
        <Textarea
          {...register("note")}
          placeholder="Add any notes for your accountant..."
          rows={3}
        />
      </div>

      <Button
        type="submit"
        disabled={isSubmitting || uploadedDocIds.length === 0}
        className="w-full"
      >
        {isSubmitting ? "Submitting..." : "Submit Response"}
      </Button>
    </form>
  );
}
```

### Document Uploader

```typescript
// frontend/src/components/portal/DocumentUploader.tsx
"use client";

import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, X, FileText, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { usePortalApi } from "@/lib/api/portal";

interface DocumentUploaderProps {
  requestId: string;
  expectedTypes: string[];
  uploadedIds: string[];
  onUploadComplete: (docId: string) => void;
  onRemove: (docId: string) => void;
}

interface UploadingFile {
  file: File;
  progress: number;
  docId?: string;
  error?: string;
}

export function DocumentUploader({
  requestId,
  expectedTypes,
  uploadedIds,
  onUploadComplete,
  onRemove,
}: DocumentUploaderProps) {
  const [uploadingFiles, setUploadingFiles] = useState<UploadingFile[]>([]);
  const { uploadDocument } = usePortalApi();

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      for (const file of acceptedFiles) {
        // Add to uploading state
        setUploadingFiles((prev) => [...prev, { file, progress: 0 }]);

        try {
          // Upload file
          const result = await uploadDocument(file, {
            request_id: requestId,
            document_type: inferDocumentType(file.name, expectedTypes),
          });

          // Update state
          setUploadingFiles((prev) =>
            prev.map((f) =>
              f.file === file ? { ...f, progress: 100, docId: result.id } : f
            )
          );

          onUploadComplete(result.id);
        } catch (error) {
          setUploadingFiles((prev) =>
            prev.map((f) =>
              f.file === file
                ? { ...f, error: "Upload failed" }
                : f
            )
          );
        }
      }
    },
    [requestId, expectedTypes, uploadDocument, onUploadComplete]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "image/*": [".jpg", ".jpeg", ".png", ".heic"],
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [
        ".xlsx",
      ],
      "text/csv": [".csv"],
    },
    maxSize: 50 * 1024 * 1024, // 50MB
  });

  return (
    <div className="space-y-4">
      <div
        {...getRootProps()}
        className={`
          border-2 border-dashed rounded-lg p-8 text-center cursor-pointer
          transition-colors
          ${isDragActive ? "border-blue-500 bg-blue-50" : "border-gray-300 hover:border-gray-400"}
        `}
      >
        <input {...getInputProps()} />
        <Upload className="mx-auto h-12 w-12 text-gray-400" />
        <p className="mt-2 text-sm text-gray-600">
          {isDragActive
            ? "Drop files here..."
            : "Drag & drop files, or click to select"}
        </p>
        <p className="mt-1 text-xs text-gray-500">
          PDF, images, Excel files up to 50MB
        </p>
      </div>

      {/* Uploading/Uploaded files */}
      {uploadingFiles.length > 0 && (
        <div className="space-y-2">
          {uploadingFiles.map((item, idx) => (
            <div
              key={idx}
              className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg"
            >
              <FileText className="h-5 w-5 text-gray-500" />
              <span className="flex-1 text-sm truncate">{item.file.name}</span>
              {item.progress < 100 && !item.error && (
                <Loader2 className="h-4 w-4 animate-spin" />
              )}
              {item.error && (
                <span className="text-red-500 text-sm">{item.error}</span>
              )}
              {item.docId && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    onRemove(item.docId!);
                    setUploadingFiles((prev) =>
                      prev.filter((f) => f.docId !== item.docId)
                    );
                  }}
                >
                  <X className="h-4 w-4" />
                </Button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function inferDocumentType(filename: string, expected: string[]): string {
  const lower = filename.toLowerCase();
  if (lower.includes("bank") || lower.includes("statement")) {
    return "bank_statement";
  }
  if (lower.includes("invoice")) {
    return "invoice";
  }
  if (lower.includes("receipt")) {
    return "receipt";
  }
  if (lower.includes("payroll") || lower.includes("wage")) {
    return "payroll";
  }
  return expected[0] || "other";
}
```

---

## 9. Email Templates

```python
# backend/app/modules/portal/notifications/templates.py
from dataclasses import dataclass


@dataclass
class EmailTemplate:
    subject: str
    html_body: str
    text_body: str


def portal_invitation(
    client_name: str,
    firm_name: str,
    magic_link: str,
) -> EmailTemplate:
    """Email template for portal invitation."""
    return EmailTemplate(
        subject=f"{firm_name} has invited you to their client portal",
        html_body=f"""
        <h1>Welcome to the Client Portal</h1>
        <p>Hi {client_name},</p>
        <p>{firm_name} has invited you to access your client portal where you can:</p>
        <ul>
            <li>View your BAS status</li>
            <li>Respond to document requests</li>
            <li>Upload documents securely</li>
        </ul>
        <p><a href="{magic_link}" style="background: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">Access Portal</a></p>
        <p>This link expires in 7 days.</p>
        <p>Best regards,<br>{firm_name}</p>
        """,
        text_body=f"""
Welcome to the Client Portal

Hi {client_name},

{firm_name} has invited you to access your client portal.

Click here to access: {magic_link}

This link expires in 7 days.

Best regards,
{firm_name}
        """,
    )


def document_request(
    client_name: str,
    request_title: str,
    request_description: str,
    due_date: str | None,
    portal_link: str,
    firm_name: str,
) -> EmailTemplate:
    """Email template for document request notification."""
    due_text = f"Due: {due_date}" if due_date else "No due date"

    return EmailTemplate(
        subject=f"Document Request: {request_title}",
        html_body=f"""
        <h1>Document Request</h1>
        <p>Hi {client_name},</p>
        <p>Your accountant has requested documents:</p>
        <div style="background: #f3f4f6; padding: 16px; border-radius: 8px; margin: 16px 0;">
            <h2 style="margin: 0 0 8px 0;">{request_title}</h2>
            <p style="margin: 0; color: #6b7280;">{due_text}</p>
        </div>
        <p>{request_description}</p>
        <p><a href="{portal_link}" style="background: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">Respond Now</a></p>
        <p>Best regards,<br>{firm_name}</p>
        """,
        text_body=f"""
Document Request: {request_title}

Hi {client_name},

Your accountant has requested documents:

{request_title}
{due_text}

{request_description}

Respond here: {portal_link}

Best regards,
{firm_name}
        """,
    )


def request_reminder(
    client_name: str,
    request_title: str,
    due_date: str | None,
    is_overdue: bool,
    portal_link: str,
    firm_name: str,
) -> EmailTemplate:
    """Email template for request reminder."""
    if is_overdue:
        subject = f"Overdue: {request_title}"
        urgency = "This request is now overdue. Please respond as soon as possible."
    else:
        subject = f"Reminder: {request_title}"
        urgency = f"This request is due on {due_date}."

    return EmailTemplate(
        subject=subject,
        html_body=f"""
        <h1>Reminder</h1>
        <p>Hi {client_name},</p>
        <p>{urgency}</p>
        <div style="background: #fef3c7; padding: 16px; border-radius: 8px; margin: 16px 0;">
            <h2 style="margin: 0;">{request_title}</h2>
        </div>
        <p><a href="{portal_link}" style="background: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">Respond Now</a></p>
        <p>Best regards,<br>{firm_name}</p>
        """,
        text_body=f"""
Reminder: {request_title}

Hi {client_name},

{urgency}

Respond here: {portal_link}

Best regards,
{firm_name}
        """,
    )
```

---

## Testing

### Unit Tests

```python
# backend/tests/unit/modules/portal/test_magic_link.py
import pytest
from datetime import datetime, timedelta, UTC
from uuid import uuid4

from app.modules.portal.auth.magic_link import MagicLinkService


class TestMagicLinkService:
    def setup_method(self):
        self.service = MagicLinkService()

    def test_generate_magic_link_token(self):
        client_id = uuid4()
        tenant_id = uuid4()
        email = "test@example.com"

        token = self.service.generate_magic_link_token(
            client_id=client_id,
            email=email,
            tenant_id=tenant_id,
        )

        assert token is not None
        assert len(token) > 0

    def test_verify_valid_token(self):
        client_id = uuid4()
        tenant_id = uuid4()
        email = "test@example.com"

        token = self.service.generate_magic_link_token(
            client_id=client_id,
            email=email,
            tenant_id=tenant_id,
        )

        payload = self.service.verify_magic_link_token(token)

        assert payload is not None
        assert payload["client_id"] == str(client_id)
        assert payload["email"] == email
        assert payload["type"] == "magic_link"

    def test_verify_invalid_token(self):
        payload = self.service.verify_magic_link_token("invalid-token")
        assert payload is None

    def test_create_session_tokens(self):
        client_id = uuid4()
        tenant_id = uuid4()
        session_id = uuid4()

        access_token, refresh_token = self.service.create_session_tokens(
            client_id=client_id,
            tenant_id=tenant_id,
            session_id=session_id,
        )

        assert access_token is not None
        assert refresh_token is not None
        assert access_token != refresh_token

    def test_verify_access_token(self):
        client_id = uuid4()
        tenant_id = uuid4()
        session_id = uuid4()

        access_token, _ = self.service.create_session_tokens(
            client_id=client_id,
            tenant_id=tenant_id,
            session_id=session_id,
        )

        payload = self.service.verify_access_token(access_token)

        assert payload is not None
        assert payload["client_id"] == str(client_id)
        assert payload["type"] == "portal_access"
```

### Integration Tests

```python
# backend/tests/integration/api/test_portal_auth.py
import pytest
from httpx import AsyncClient
from uuid import uuid4

from app.main import app
from tests.fixtures import create_test_client, create_test_tenant


@pytest.mark.asyncio
async def test_request_magic_link(async_client: AsyncClient, test_client_with_portal):
    """Test requesting a magic link."""
    response = await async_client.post(
        "/api/v1/portal/auth/request-link",
        json={"email": test_client_with_portal.email},
    )

    assert response.status_code == 200
    assert "message" in response.json()


@pytest.mark.asyncio
async def test_verify_magic_link(
    async_client: AsyncClient,
    test_client_with_portal,
    magic_link_token,
):
    """Test verifying a magic link."""
    response = await async_client.post(
        "/api/v1/portal/auth/verify",
        json={"token": magic_link_token},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_verify_invalid_token(async_client: AsyncClient):
    """Test verifying an invalid token."""
    response = await async_client.post(
        "/api/v1/portal/auth/verify",
        json={"token": "invalid-token"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_dashboard(
    async_client: AsyncClient,
    portal_auth_headers,
):
    """Test getting the portal dashboard."""
    response = await async_client.get(
        "/api/v1/portal/dashboard",
        headers=portal_auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert "client" in data
    assert "bas_status" in data
    assert "action_items" in data
```

---

## Celery Configuration

```python
# backend/app/tasks/celery_config.py (add to existing)
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    # ... existing schedules ...

    "portal-auto-reminders": {
        "task": "portal.auto_reminders",
        "schedule": crontab(hour=9, minute=0),  # Daily at 9 AM
    },
}
```

---

## Next Steps

After implementing the core functionality:

1. **Phase 2**: Bulk request UI and preview
2. **Phase 3**: Request tracking dashboard
3. **Phase 4**: Auto-filing for uploaded documents
4. **Phase 5**: Push notifications (mobile)

See [tasks.md](./tasks.md) for complete implementation checklist.
