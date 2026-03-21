"""Pydantic schemas for Client Portal API.

Request and response models for portal endpoints.

Spec: 030-client-portal-document-requests
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl

from app.modules.portal.enums import (
    BulkRequestStatus,
    InvitationStatus,
    RequestPriority,
    RequestStatus,
    ScanStatus,
)

# =============================================================================
# Base Schemas
# =============================================================================


class PortalBaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Invitation Schemas
# =============================================================================


class InvitationCreateRequest(BaseModel):
    """Request to create a portal invitation."""

    email: EmailStr = Field(..., description="Email address to send invitation")
    message: str | None = Field(
        None,
        max_length=500,
        description="Optional personalized message to include",
    )


class InvitationResponse(PortalBaseSchema):
    """Response for a portal invitation."""

    id: UUID
    connection_id: UUID
    email: str
    status: InvitationStatus
    sent_at: datetime | None = None
    accepted_at: datetime | None = None
    expires_at: datetime
    email_delivered: bool = False
    email_bounced: bool = False
    bounce_reason: str | None = None
    created_at: datetime


class InvitationListResponse(BaseModel):
    """Response for list of invitations."""

    invitations: list[InvitationResponse]
    total: int


class InvitationCreateResponse(BaseModel):
    """Response after creating a portal invitation."""

    invitation: InvitationResponse
    magic_link_url: str = Field(..., description="Magic link URL to send to client")


class PortalAccessStatusResponse(BaseModel):
    """Response for portal access status."""

    has_access: bool = Field(..., description="Whether client has active portal access")
    active_sessions: int = Field(..., description="Number of active sessions")
    latest_invitation: InvitationResponse | None = None
    invitation_status: InvitationStatus | None = None


class MagicLinkVerifyRequest(BaseModel):
    """Request to verify a magic link token."""

    token: str = Field(..., min_length=32, max_length=128)
    device_fingerprint: str | None = Field(
        None,
        max_length=128,
        description="Client device fingerprint for security tracking",
    )
    user_agent: str | None = Field(
        None,
        max_length=512,
        description="Client user agent string",
    )
    ip_address: str | None = Field(
        None,
        max_length=45,
        description="Client IP address",
    )


class MagicLinkVerifyResponse(BaseModel):
    """Response after successful magic link verification."""

    access_token: str = Field(..., description="JWT access token for API calls")
    refresh_token: str = Field(..., description="Long-lived refresh token")
    token_type: str = "bearer"
    expires_at: datetime = Field(..., description="When access token expires")
    connection_id: UUID = Field(..., description="XeroConnection ID for the client")
    tenant_id: UUID = Field(..., description="Tenant ID for the accounting practice")


class PortalTokenRefreshRequest(BaseModel):
    """Request to refresh a portal access token."""

    refresh_token: str = Field(..., description="The refresh token from login")
    ip_address: str | None = Field(
        None,
        max_length=45,
        description="Current client IP address",
    )


class PortalTokenRefreshResponse(BaseModel):
    """Response with new access token."""

    access_token: str = Field(..., description="New JWT access token")
    token_type: str = "bearer"
    expires_at: datetime = Field(..., description="When access token expires")


# =============================================================================
# Session Schemas
# =============================================================================


class SessionRefreshRequest(BaseModel):
    """Request to refresh a portal session."""

    refresh_token: str


class SessionRefreshResponse(BaseModel):
    """Response with new access token."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class SessionRevokeRequest(BaseModel):
    """Request to revoke a portal session."""

    reason: str | None = Field(None, max_length=255)


class ActiveSessionResponse(PortalBaseSchema):
    """Response for an active portal session."""

    id: UUID
    connection_id: UUID
    device_fingerprint: str | None = None
    user_agent: str | None = None
    ip_address: str | None = None
    last_active_at: datetime
    expires_at: datetime
    created_at: datetime


# =============================================================================
# Template Schemas
# =============================================================================


class TemplateCreateRequest(BaseModel):
    """Request to create a document request template."""

    name: str = Field(..., min_length=1, max_length=100)
    description_template: str = Field(..., min_length=1)
    expected_document_types: list[str] = Field(default_factory=list)
    icon: str | None = Field(None, max_length=50)
    default_priority: RequestPriority = RequestPriority.NORMAL
    default_due_days: int = Field(default=7, ge=1, le=365)


class TemplateUpdateRequest(BaseModel):
    """Request to update a document request template."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description_template: str | None = Field(None, min_length=1)
    expected_document_types: list[str] | None = None
    icon: str | None = Field(None, max_length=50)
    default_priority: RequestPriority | None = None
    default_due_days: int | None = Field(None, ge=1, le=365)
    is_active: bool | None = None


class TemplateResponse(PortalBaseSchema):
    """Response for a document request template."""

    id: UUID
    tenant_id: UUID | None = None
    name: str
    description_template: str
    expected_document_types: list[str] = []
    icon: str | None = None
    default_priority: RequestPriority
    default_due_days: int
    is_system: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TemplateListResponse(BaseModel):
    """Response for list of templates."""

    templates: list[TemplateResponse]
    total: int


# =============================================================================
# Document Request Schemas
# =============================================================================


class RequestCreateRequest(BaseModel):
    """Request to create a document request (ClientChase)."""

    connection_id: UUID = Field(..., description="XeroConnection ID (client business)")
    template_id: UUID | None = Field(None, description="Optional template to use")
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    recipient_email: str = Field(..., description="Email address to send the request to")
    due_date: date | None = None
    priority: RequestPriority = RequestPriority.NORMAL
    period_start: date | None = None
    period_end: date | None = None
    auto_remind: bool = True
    send_immediately: bool = Field(
        default=True,
        description="Send notification immediately or save as draft",
    )


class RequestUpdateRequest(BaseModel):
    """Request to update a document request."""

    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, min_length=1)
    due_date: date | None = None
    priority: RequestPriority | None = None
    auto_remind: bool | None = None


class RequestResponse(PortalBaseSchema):
    """Response for a document request."""

    id: UUID
    connection_id: UUID
    template_id: UUID | None = None
    title: str
    description: str
    recipient_email: str
    due_date: date | None = None
    priority: RequestPriority
    period_start: date | None = None
    period_end: date | None = None
    status: RequestStatus
    sent_at: datetime | None = None
    viewed_at: datetime | None = None
    responded_at: datetime | None = None
    completed_at: datetime | None = None
    auto_remind: bool
    reminder_count: int
    last_reminder_at: datetime | None = None
    bulk_request_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    # Computed fields
    is_overdue: bool = False
    days_until_due: int | None = None
    response_count: int = 0
    document_count: int = 0


class RequestDetailResponse(RequestResponse):
    """Detailed response for a document request with related data."""

    organization_name: str
    responses: list["ResponseDetailResponse"] = []
    events: list["EventResponse"] = []


class RequestListResponse(BaseModel):
    """Response for list of document requests."""

    requests: list[RequestResponse]
    total: int
    page: int = 1
    page_size: int = 20


class RequestListFilters(BaseModel):
    """Filters for listing document requests."""

    connection_id: UUID | None = None
    status: RequestStatus | None = None
    priority: RequestPriority | None = None
    is_overdue: bool | None = None
    from_date: date | None = None
    to_date: date | None = None
    search: str | None = Field(None, max_length=100)


# =============================================================================
# Response (Client's Response to Request) Schemas
# =============================================================================


class ResponseSubmitRequest(BaseModel):
    """Request to submit a response to a document request."""

    note: str | None = Field(None, max_length=2000)


class ResponseSummary(PortalBaseSchema):
    """Summary of a client response."""

    id: UUID
    request_id: UUID
    note: str | None = None
    submitted_at: datetime
    document_count: int = 0


class ResponseDetailResponse(ResponseSummary):
    """Detailed response including documents."""

    documents: list["DocumentResponse"] = []


# =============================================================================
# Document Schemas
# =============================================================================


class DocumentUploadRequest(BaseModel):
    """Request to upload a document."""

    response_id: UUID | None = Field(None, description="Link to a response if applicable")
    document_type: str | None = Field(None, max_length=50)
    period_start: date | None = None
    period_end: date | None = None
    tags: list[str] | None = Field(None, max_length=10)


class DocumentResponse(PortalBaseSchema):
    """Response for a portal document."""

    id: UUID
    connection_id: UUID
    response_id: UUID | None = None
    filename: str
    original_filename: str
    content_type: str
    file_size: int
    document_type: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    tags: list[str] | None = None
    uploaded_at: datetime
    uploaded_by_client: bool
    scan_status: ScanStatus | None = None
    scanned_at: datetime | None = None


class DocumentListResponse(BaseModel):
    """Response for list of documents."""

    documents: list[DocumentResponse]
    total: int


class DocumentDownloadResponse(BaseModel):
    """Response with presigned download URL."""

    download_url: HttpUrl
    expires_in: int = Field(..., description="Seconds until URL expires")
    filename: str


# =============================================================================
# Event Schemas
# =============================================================================


class EventResponse(PortalBaseSchema):
    """Response for a request event."""

    id: UUID
    request_id: UUID
    event_type: str
    event_data: dict | None = None
    actor_type: str
    actor_id: UUID | None = None
    created_at: datetime


# =============================================================================
# Bulk Request Schemas
# =============================================================================


class BulkRequestCreateRequest(BaseModel):
    """Request to create a bulk document request."""

    connection_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="List of XeroConnection IDs to send requests to",
    )
    template_id: UUID | None = Field(None, description="Optional template to use")
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    due_date: date | None = None
    priority: RequestPriority = RequestPriority.NORMAL


class BulkRequestResponse(PortalBaseSchema):
    """Response for a bulk document request."""

    id: UUID
    template_id: UUID | None = None
    title: str
    due_date: date | None = None
    total_clients: int
    sent_count: int
    failed_count: int
    status: BulkRequestStatus
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    # Computed
    progress_percent: int = 0


class BulkRequestDetailResponse(BulkRequestResponse):
    """Detailed bulk request response with individual requests."""

    requests: list[RequestResponse] = []
    failed_connections: list[UUID] = []


class BulkRequestListResponse(BaseModel):
    """Response for list of bulk requests."""

    bulk_requests: list[BulkRequestResponse]
    total: int


# =============================================================================
# Client Portal Dashboard Schemas
# =============================================================================


class PortalDashboardResponse(BaseModel):
    """Response for client portal dashboard."""

    connection_id: UUID
    organization_name: str
    pending_requests: int
    unread_requests: int
    total_documents: int
    recent_requests: list[RequestResponse] = []
    last_activity_at: datetime | None = None


# =============================================================================
# Request Tracking Schemas
# =============================================================================


class TrackingRequestItem(PortalBaseSchema):
    """Request item in tracking view with organization context."""

    id: UUID
    connection_id: UUID
    organization_name: str
    title: str
    due_date: date | None = None
    priority: RequestPriority
    status: RequestStatus
    sent_at: datetime | None = None
    viewed_at: datetime | None = None
    responded_at: datetime | None = None
    is_overdue: bool = False
    days_until_due: int | None = None
    response_count: int = 0


class TrackingStatusGroup(BaseModel):
    """Requests grouped by status."""

    status: RequestStatus
    count: int
    requests: list[TrackingRequestItem] = []


class TrackingSummary(BaseModel):
    """Summary statistics for request tracking."""

    total: int
    pending: int
    viewed: int
    in_progress: int
    completed: int
    cancelled: int
    overdue: int
    due_today: int
    due_this_week: int


class TrackingResponse(BaseModel):
    """Response for request tracking dashboard."""

    summary: TrackingSummary
    groups: list[TrackingStatusGroup]
    page: int = 1
    page_size: int = 50


class TrackingSummaryResponse(BaseModel):
    """Response for tracking summary only (quick overview)."""

    summary: TrackingSummary
    recent_activity: list[TrackingRequestItem] = []


# =============================================================================
# Auto-Remind & Settings Schemas
# =============================================================================


class AutoRemindToggleRequest(BaseModel):
    """Request to toggle auto-remind for a request."""

    enabled: bool = Field(..., description="Whether auto-remind is enabled")


class AutoRemindResponse(PortalBaseSchema):
    """Response for auto-remind status."""

    request_id: UUID
    auto_remind: bool
    last_reminder_at: datetime | None = None
    reminder_count: int = 0


class ReminderSettingsRequest(BaseModel):
    """Request to update tenant reminder settings."""

    days_before_due: int = Field(
        default=3, ge=1, le=14, description="Days before due date to send first reminder"
    )
    overdue_reminder_days: list[int] = Field(
        default=[1, 3, 7],
        description="List of days after due date to send reminders",
    )
    min_days_between_reminders: int = Field(
        default=3, ge=1, le=7, description="Minimum days between reminders"
    )
    auto_remind_enabled: bool = Field(
        default=True, description="Whether auto-reminders are enabled for tenant"
    )


class ReminderSettingsResponse(PortalBaseSchema):
    """Response for tenant reminder settings."""

    tenant_id: UUID
    days_before_due: int = 3
    overdue_reminder_days: list[int] = [1, 3, 7]
    min_days_between_reminders: int = 3
    auto_remind_enabled: bool = True


class SendReminderResponse(PortalBaseSchema):
    """Response after sending a reminder."""

    request_id: UUID
    reminder_count: int
    last_reminder_at: datetime


# =============================================================================
# Error Schemas
# =============================================================================


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str = Field(..., description="Error message")
    code: str = Field(..., description="Error code")
    details: dict | None = None


# Update forward references
RequestDetailResponse.model_rebuild()
ResponseDetailResponse.model_rebuild()
