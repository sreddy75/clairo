"""Pydantic schemas for onboarding API.

Request and response models for onboarding endpoints.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.integrations.xero.models import XpmClientConnectionStatus
from app.modules.onboarding.models import BulkImportJobStatus, OnboardingStatus

# =============================================================================
# Checklist Schemas
# =============================================================================


class ChecklistItem(BaseModel):
    """Single checklist item."""

    id: str
    label: str
    completed: bool
    completed_at: datetime | None = None


class OnboardingChecklist(BaseModel):
    """Onboarding checklist with all items."""

    items: list[ChecklistItem]
    completed_count: int
    total_count: int
    dismissed: bool


# =============================================================================
# Progress Schemas
# =============================================================================


class OnboardingProgressResponse(BaseModel):
    """Response for onboarding progress."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: OnboardingStatus
    current_step: str
    started_at: datetime
    tier_selected_at: datetime | None = None
    payment_setup_at: datetime | None = None
    xero_connected_at: datetime | None = None
    clients_imported_at: datetime | None = None
    tour_completed_at: datetime | None = None
    completed_at: datetime | None = None
    xero_skipped: bool = False
    tour_skipped: bool = False
    checklist: OnboardingChecklist


# =============================================================================
# Tier Selection Schemas
# =============================================================================


class TierSelectionRequest(BaseModel):
    """Request to select subscription tier and start free trial."""

    tier: str = Field(
        ...,
        pattern="^(starter|professional|growth|enterprise)$",
        description="Subscription tier",
    )
    with_trial: bool = Field(
        default=True,
        description="Whether to include 14-day free trial",
    )


# =============================================================================
# Payment Schemas
# =============================================================================


class PaymentCompleteRequest(BaseModel):
    """Request to mark payment setup complete."""

    session_id: str = Field(..., description="Stripe Checkout session ID")


# =============================================================================
# Xero Schemas
# =============================================================================


class XeroConnectResponse(BaseModel):
    """Response with Xero OAuth authorization URL."""

    authorization_url: str = Field(..., description="Xero OAuth authorization URL")


# =============================================================================
# Client Import Schemas
# =============================================================================


class AvailableClient(BaseModel):
    """Client available for import from Xero/XPM."""

    id: str = Field(..., description="XPM/Xero client ID")
    name: str
    email: str | None = None
    abn: str | None = None
    status: str = "active"
    already_imported: bool = Field(
        default=False,
        description="Whether this client is already in Clairo",
    )
    xero_org_status: XpmClientConnectionStatus = Field(
        default=XpmClientConnectionStatus.NOT_CONNECTED,
        description="Connection status to client's own Xero organization",
    )
    xero_connection_id: UUID | None = Field(
        default=None,
        description="ID of the linked Xero connection (if connected)",
    )


class AvailableClientsResponse(BaseModel):
    """Response with list of clients available for import."""

    clients: list[AvailableClient]
    total: int = Field(..., description="Total available clients")
    source_type: str = Field(..., pattern="^(xpm|xero_accounting)$")
    tier_limit: int = Field(..., description="Client limit for current tier")
    current_count: int = Field(..., description="Current imported client count")
    page: int = 1
    page_size: int = 50


class BulkImportRequest(BaseModel):
    """Request to start bulk client import."""

    client_ids: list[str] = Field(
        ...,
        min_length=1,
        max_length=250,
        description="List of XPM/Xero client IDs to import",
    )


class ImportedClient(BaseModel):
    """Details of successfully imported client."""

    xero_id: str
    client_id: UUID
    name: str
    transactions_synced: int = 0


class FailedClient(BaseModel):
    """Details of failed client import."""

    xero_id: str
    name: str
    error: str


class BulkImportJobResponse(BaseModel):
    """Response with bulk import job status."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: BulkImportJobStatus
    source_type: str | None = None
    total_clients: int
    imported_count: int
    failed_count: int
    progress_percent: int = Field(..., ge=0, le=100)
    started_at: datetime
    completed_at: datetime | None = None
    imported_clients: list[ImportedClient] = []
    failed_clients: list[FailedClient] = []


# =============================================================================
# Error Schemas
# =============================================================================


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str = Field(..., description="Error message")
    code: str = Field(..., description="Error code")
    details: dict | None = None
