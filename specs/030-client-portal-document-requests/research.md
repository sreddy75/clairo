# Research: Client Portal Foundation + Document Requests

**Spec**: 030-client-portal-document-requests
**Date**: 2026-01-01

---

## 1. Magic Link Authentication

### Decision: JWT-Based Magic Links

**Rationale**: Passwordless authentication reduces friction for clients who may only log in occasionally.

**Alternatives Considered**:
- **Password auth**: Too much friction, password reset support burden
- **OAuth (Google/Microsoft)**: Not all business owners have these, adds complexity
- **SMS OTP**: Expensive at scale, phone number collection needed

**Security Considerations**:

```python
# Token structure
MAGIC_LINK_PAYLOAD = {
    "client_id": str,     # Client UUID
    "email": str,         # Email address (for verification)
    "tenant_id": str,     # Tenant scope
    "exp": datetime,      # Expiry (7 days)
    "jti": str,           # Unique token ID (for single-use)
    "iat": datetime,      # Issued at
}

# Security measures
SECURITY_MEASURES = [
    "7-day token expiry",
    "Single-use tokens (optional, configurable)",
    "Rate limit: 3 requests per email per hour",
    "IP logging for audit",
    "Token invalidation on password change (if ever added)",
]
```

**Token Generation**:

```python
import jwt
from datetime import datetime, timedelta
from uuid import uuid4

class MagicLinkService:
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        self.algorithm = "HS256"
        self.expiry_days = 7

    def generate_token(
        self,
        client_id: UUID,
        email: str,
        tenant_id: UUID,
    ) -> str:
        payload = {
            "client_id": str(client_id),
            "email": email,
            "tenant_id": str(tenant_id),
            "exp": datetime.utcnow() + timedelta(days=self.expiry_days),
            "jti": str(uuid4()),
            "iat": datetime.utcnow(),
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_token(self, token: str) -> dict | None:
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise TokenExpiredError("Magic link has expired")
        except jwt.InvalidTokenError:
            raise InvalidTokenError("Invalid magic link")
```

**Session Management**:

```python
# After magic link verification, create session tokens
SESSION_CONFIG = {
    "access_token_expiry": timedelta(hours=1),
    "refresh_token_expiry": timedelta(days=30),
    "refresh_token_rotation": True,  # New refresh token on each use
}
```

---

## 2. Document Request Templates

### Decision: Tenant-Customizable Templates with System Defaults

**Rationale**: Pre-built templates save time, but accountants need to customize.

**System Templates**:

```python
SYSTEM_TEMPLATES = [
    {
        "name": "Bank Statements",
        "description_template": "Please upload bank statements for all business accounts for the period {start_date} to {end_date}.",
        "expected_document_types": ["bank_statement"],
        "default_priority": "NORMAL",
        "default_due_days": 7,
        "icon": "bank",
    },
    {
        "name": "BAS Source Documents",
        "description_template": "Please provide supporting documents for your BAS for {period}. This includes sales invoices, purchase invoices, and expense receipts.",
        "expected_document_types": ["invoice", "receipt"],
        "default_priority": "HIGH",
        "default_due_days": 5,
        "icon": "file-text",
    },
    {
        "name": "End of Financial Year Documents",
        "description_template": "Please upload all documents for the financial year ending {end_date}. This includes bank statements, invoices, asset purchases, and any other relevant records.",
        "expected_document_types": ["bank_statement", "invoice", "receipt", "asset"],
        "default_priority": "HIGH",
        "default_due_days": 14,
        "icon": "calendar",
    },
    {
        "name": "Superannuation Records",
        "description_template": "Please upload superannuation contribution records for {period}.",
        "expected_document_types": ["superannuation"],
        "default_priority": "NORMAL",
        "default_due_days": 7,
        "icon": "shield",
    },
    {
        "name": "Motor Vehicle Logbook",
        "description_template": "Please upload your motor vehicle logbook for the period {start_date} to {end_date}.",
        "expected_document_types": ["logbook"],
        "default_priority": "NORMAL",
        "default_due_days": 7,
        "icon": "car",
    },
    {
        "name": "Custom Request",
        "description_template": "",
        "expected_document_types": [],
        "default_priority": "NORMAL",
        "default_due_days": 7,
        "icon": "file-plus",
    },
]
```

**Template Variables**:

```python
TEMPLATE_VARIABLES = {
    "{period}": "BAS period string (e.g., 'Q1 2026')",
    "{start_date}": "Period start date (formatted)",
    "{end_date}": "Period end date (formatted)",
    "{client_name}": "Client business name",
    "{accountant_name}": "Accountant name",
    "{firm_name}": "Accounting firm name",
}
```

---

## 3. Bulk Request Processing

### Decision: Background Processing with Batch Operations

**Rationale**: 100+ clients should complete in <30 seconds.

**Implementation**:

```python
from celery import group

class BulkRequestService:
    MAX_BATCH_SIZE = 100
    PARALLEL_WORKERS = 10

    async def create_bulk_requests(
        self,
        tenant_id: UUID,
        client_ids: list[UUID],
        template_id: UUID,
        due_date: date,
        custom_message: str | None,
        user_id: UUID,
    ) -> BulkRequestResult:
        """Create requests for multiple clients."""
        # Validate all clients exist and belong to tenant
        clients = await self.client_repo.get_by_ids(client_ids, tenant_id)
        if len(clients) != len(client_ids):
            raise ClientNotFoundError("Some clients not found")

        # Get template
        template = await self.template_repo.get(template_id)

        # Create requests in batches
        requests = []
        for client in clients:
            request = DocumentRequest(
                tenant_id=tenant_id,
                client_id=client.id,
                template_id=template_id,
                title=template.name,
                description=self._render_description(
                    template.description_template,
                    client=client,
                ),
                due_date=due_date,
                priority=template.default_priority,
                status=RequestStatus.PENDING,
                created_by=user_id,
            )
            requests.append(request)

        # Bulk insert
        await self.request_repo.create_bulk(requests)

        # Queue notification emails (parallel)
        notification_tasks = group(
            send_request_notification.s(str(r.id))
            for r in requests
        )
        notification_tasks.apply_async()

        return BulkRequestResult(
            total=len(requests),
            created=len(requests),
            failed=0,
        )
```

**Performance Optimizations**:

```python
BULK_OPTIMIZATIONS = [
    "Bulk INSERT with COPY for large batches",
    "Parallel email sending via Celery group",
    "Batch client validation query",
    "Connection pooling for DB operations",
    "Progress updates via WebSocket for UI",
]
```

---

## 4. Auto-Reminder System

### Decision: Daily Celery Job with Timezone Awareness

**Rationale**: Reminders should arrive at 9 AM in client's timezone.

**Reminder Schedule**:

```python
REMINDER_SCHEDULE = [
    {
        "trigger": "3_days_before_due",
        "template": "reminder_upcoming",
        "subject": "Reminder: Document request due in 3 days",
        "urgency": "normal",
    },
    {
        "trigger": "1_day_before_due",
        "template": "reminder_urgent",
        "subject": "Urgent: Document request due tomorrow",
        "urgency": "high",
    },
    {
        "trigger": "due_date",
        "template": "reminder_due_today",
        "subject": "Due Today: Document request",
        "urgency": "high",
    },
    {
        "trigger": "1_day_overdue",
        "template": "reminder_overdue",
        "subject": "Overdue: Document request past due date",
        "urgency": "critical",
    },
    {
        "trigger": "3_days_overdue",
        "template": "reminder_overdue",
        "subject": "Overdue: Document request - please respond",
        "urgency": "critical",
    },
    {
        "trigger": "7_days_overdue",
        "template": "reminder_final",
        "subject": "Final Notice: Document request overdue",
        "urgency": "critical",
        "is_final": True,
    },
]
```

**Celery Task**:

```python
from celery import shared_task
from datetime import date, timedelta

@shared_task
def run_auto_reminders():
    """Daily job to send auto-reminders for pending requests."""
    today = date.today()

    # Query requests needing reminders
    requests = DocumentRequest.query.filter(
        DocumentRequest.status.in_([RequestStatus.PENDING, RequestStatus.VIEWED]),
        DocumentRequest.auto_remind == True,
    ).all()

    for request in requests:
        # Calculate days relative to due date
        days_until_due = (request.due_date - today).days if request.due_date else None

        # Determine which reminder (if any) to send
        reminder = get_applicable_reminder(days_until_due, request.reminder_count)

        if reminder and should_send_reminder(request, reminder):
            send_reminder_email.delay(str(request.id), reminder["template"])

            # Update reminder tracking
            request.reminder_count += 1
            request.last_reminder_at = datetime.utcnow()


def get_applicable_reminder(days_until_due: int | None, reminder_count: int) -> dict | None:
    """Determine which reminder template applies."""
    if days_until_due is None:
        return None

    if days_until_due == 3:
        return REMINDER_SCHEDULE[0]
    elif days_until_due == 1:
        return REMINDER_SCHEDULE[1]
    elif days_until_due == 0:
        return REMINDER_SCHEDULE[2]
    elif days_until_due == -1:
        return REMINDER_SCHEDULE[3]
    elif days_until_due == -3:
        return REMINDER_SCHEDULE[4]
    elif days_until_due == -7:
        return REMINDER_SCHEDULE[5]

    return None
```

**Celery Beat Schedule**:

```python
CELERY_BEAT_SCHEDULE = {
    "auto-reminders": {
        "task": "app.tasks.portal.auto_reminders.run_auto_reminders",
        "schedule": crontab(hour=9, minute=0),  # 9 AM daily
    },
}
```

---

## 5. Document Upload & Auto-Filing

### Decision: S3 Direct Upload with Metadata Tagging

**Rationale**: Direct upload reduces server load, metadata enables auto-filing.

**Upload Flow**:

```python
class PortalUploadService:
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
    ALLOWED_TYPES = ["pdf", "jpg", "jpeg", "png", "heic", "doc", "docx", "xls", "xlsx"]

    async def get_upload_url(
        self,
        client_id: UUID,
        request_id: UUID,
        filename: str,
        content_type: str,
    ) -> PresignedUpload:
        """Generate presigned URL for direct S3 upload."""
        # Validate file type
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext not in self.ALLOWED_TYPES:
            raise InvalidFileTypeError(f"File type {ext} not allowed")

        # Generate S3 key with auto-filing structure
        s3_key = self._generate_s3_key(client_id, request_id, filename)

        # Create presigned URL
        url = self.s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.DOCUMENTS_BUCKET,
                "Key": s3_key,
                "ContentType": content_type,
            },
            ExpiresIn=3600,  # 1 hour
        )

        return PresignedUpload(
            upload_url=url,
            s3_key=s3_key,
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )

    def _generate_s3_key(
        self,
        client_id: UUID,
        request_id: UUID,
        filename: str,
    ) -> str:
        """Generate S3 key with auto-filing structure."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_filename = self._sanitize_filename(filename)

        return f"clients/{client_id}/requests/{request_id}/{timestamp}_{safe_filename}"
```

**Auto-Filing Logic**:

```python
class AutoFilingService:
    async def file_document(
        self,
        document_id: UUID,
        request: DocumentRequest,
    ) -> None:
        """Auto-file document based on request context."""
        document = await self.document_repo.get(document_id)

        # Determine document type from request template
        if request.template_id:
            template = await self.template_repo.get(request.template_id)
            document.document_type = template.expected_document_types[0]

        # Set period from request
        if request.period_start and request.period_end:
            document.period_start = request.period_start
            document.period_end = request.period_end

        # Tag with request context
        document.tags = [
            f"request:{request.id}",
            f"template:{request.template_id}" if request.template_id else None,
        ]

        await self.document_repo.update(document)
```

---

## 6. Email Templates

### Decision: Resend with React Email Templates

**Rationale**: Professional, responsive emails increase engagement.

**Template Structure**:

```python
EMAIL_TEMPLATES = {
    "invitation": {
        "subject": "{firm_name} has invited you to Clairo",
        "template": "portal/invitation",
    },
    "request_new": {
        "subject": "Document request from {firm_name}: {title}",
        "template": "portal/request_new",
    },
    "reminder_upcoming": {
        "subject": "Reminder: {title} due in {days} days",
        "template": "portal/reminder",
    },
    "reminder_overdue": {
        "subject": "Overdue: {title}",
        "template": "portal/reminder_overdue",
    },
    "response_received": {
        "subject": "{client_name} responded to: {title}",
        "template": "portal/response_received",
    },
}
```

**React Email Component Example**:

```tsx
// emails/portal/request-new.tsx
import { Button, Container, Heading, Text } from "@react-email/components";

interface RequestNewEmailProps {
  clientName: string;
  firmName: string;
  requestTitle: string;
  requestDescription: string;
  dueDate: string;
  portalUrl: string;
}

export function RequestNewEmail({
  clientName,
  firmName,
  requestTitle,
  requestDescription,
  dueDate,
  portalUrl,
}: RequestNewEmailProps) {
  return (
    <Container>
      <Heading>Hi {clientName},</Heading>

      <Text>
        {firmName} has requested documents from you:
      </Text>

      <Text style={{ fontWeight: "bold" }}>{requestTitle}</Text>
      <Text>{requestDescription}</Text>

      <Text>Due by: {dueDate}</Text>

      <Button href={portalUrl}>
        Respond Now
      </Button>

      <Text style={{ fontSize: "12px", color: "#666" }}>
        This email was sent via Clairo on behalf of {firmName}.
      </Text>
    </Container>
  );
}
```

---

## 7. Portal Session Management

### Decision: Separate Session Store with Short-Lived Tokens

**Rationale**: Portal users need different session handling than accountants.

**Session Configuration**:

```python
PORTAL_SESSION_CONFIG = {
    "access_token_expiry": timedelta(hours=1),
    "refresh_token_expiry": timedelta(days=30),
    "token_refresh_threshold": timedelta(minutes=15),  # Refresh if <15min left
    "max_sessions_per_client": 5,
}
```

**Session Model**:

```python
class PortalSession(Base):
    id: UUID
    client_id: UUID
    tenant_id: UUID

    # Token tracking
    refresh_token_hash: str  # Hashed for security
    device_fingerprint: str | None
    user_agent: str | None
    ip_address: str | None

    # Timestamps
    created_at: datetime
    last_active_at: datetime
    expires_at: datetime

    # Revocation
    revoked: bool = False
    revoked_at: datetime | None
    revoke_reason: str | None
```

---

## 8. Request Status Tracking

### Decision: Event-Sourced Status with Read Tracking

**Rationale**: Detailed tracking enables analytics and audit.

**Status Events**:

```python
class RequestEvent(Base):
    id: UUID
    request_id: UUID

    event_type: str  # CREATED, SENT, VIEWED, RESPONDED, COMPLETED, REMINDER_SENT
    event_data: dict  # Additional context

    actor_type: str  # SYSTEM, ACCOUNTANT, CLIENT
    actor_id: UUID | None

    created_at: datetime
    ip_address: str | None
```

**Tracking Implementation**:

```python
class RequestTrackingService:
    async def mark_viewed(
        self,
        request_id: UUID,
        client_id: UUID,
        ip_address: str | None,
    ) -> None:
        """Mark request as viewed by client."""
        request = await self.request_repo.get(request_id)

        # Only update if first view
        if request.status == RequestStatus.PENDING:
            request.status = RequestStatus.VIEWED
            request.viewed_at = datetime.utcnow()

            await self.event_repo.create(
                RequestEvent(
                    request_id=request_id,
                    event_type="VIEWED",
                    actor_type="CLIENT",
                    actor_id=client_id,
                    ip_address=ip_address,
                )
            )

    async def get_request_timeline(
        self,
        request_id: UUID,
    ) -> list[RequestEvent]:
        """Get full timeline of request events."""
        return await self.event_repo.get_by_request_id(request_id)
```

---

## 9. Mobile Upload Considerations

### Decision: Progressive Enhancement with Camera API

**Rationale**: Mobile clients need easy document capture.

**Mobile Features**:

```tsx
// Camera capture on mobile
const handleUpload = () => {
  if (isMobile) {
    // Show options: Camera, Photo Library, Files
    showUploadOptions([
      { label: "Take Photo", action: openCamera },
      { label: "Photo Library", action: openPhotoLibrary },
      { label: "Browse Files", action: openFilePicker },
    ]);
  } else {
    // Desktop: drag-drop or file picker
    openFilePicker();
  }
};

// Camera capture with image optimization
const captureFromCamera = async () => {
  const stream = await navigator.mediaDevices.getUserMedia({
    video: { facingMode: "environment" },
  });

  // Capture image
  const photo = await capturePhoto(stream);

  // Optimize for upload (compress, resize)
  const optimized = await optimizeImage(photo, {
    maxWidth: 2048,
    maxHeight: 2048,
    quality: 0.8,
  });

  return optimized;
};
```

**Image Optimization**:

```python
IMAGE_OPTIMIZATION = {
    "max_width": 2048,
    "max_height": 2048,
    "jpeg_quality": 85,
    "heic_to_jpeg": True,
    "auto_rotate": True,
}
```

---

## 10. Rate Limiting & Security

### Decision: Per-Client Rate Limits with Abuse Prevention

**Rationale**: Prevent abuse while allowing legitimate use.

**Rate Limits**:

```python
PORTAL_RATE_LIMITS = {
    "magic_link_request": {
        "limit": 3,
        "window": timedelta(hours=1),
        "key": "email",
    },
    "document_upload": {
        "limit": 50,
        "window": timedelta(hours=1),
        "key": "client_id",
    },
    "request_response": {
        "limit": 20,
        "window": timedelta(hours=1),
        "key": "client_id",
    },
}
```

**Security Headers**:

```python
PORTAL_SECURITY_HEADERS = {
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}
```
