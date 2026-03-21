"""Pydantic schemas for dashboard endpoints.

CRITICAL: In Clairo, "client" = XeroConnection = one business = one BAS to lodge.
Each ClientPortfolioItem represents one Xero organization (business), NOT a contact.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BASStatus(str, Enum):
    """BAS readiness status for a client business (XeroConnection).

    Status Logic:
    - READY: Has activity (invoices OR transactions) AND data synced within 24 hours
    - NEEDS_REVIEW: Has activity BUT sync is stale (>24 hours since last sync)
    - NO_ACTIVITY: No invoices AND no transactions for the quarter
    - MISSING_DATA: Has invoices but no transactions, or vice versa (incomplete data)
    """

    READY = "ready"
    NEEDS_REVIEW = "needs_review"
    NO_ACTIVITY = "no_activity"
    MISSING_DATA = "missing_data"


class StatusCounts(BaseModel):
    """Count of client businesses by BAS status."""

    ready: int = 0
    needs_review: int = 0
    no_activity: int = 0
    missing_data: int = 0


class QualitySummary(BaseModel):
    """Quality summary across all client businesses."""

    avg_score: Decimal = Field(default=Decimal("0.00"), description="Average quality score")
    good_count: int = Field(default=0, description="Clients with score > 80%")
    fair_count: int = Field(default=0, description="Clients with score 50-80%")
    poor_count: int = Field(default=0, description="Clients with score < 50%")
    total_critical_issues: int = Field(default=0, description="Total critical issues")


class DashboardSummaryResponse(BaseModel):
    """Aggregated dashboard summary metrics across all client businesses."""

    total_clients: int  # Count of XeroConnections (businesses)
    active_clients: int  # Connections with activity this quarter
    total_sales: Decimal = Field(default=Decimal("0.00"))
    total_purchases: Decimal = Field(default=Decimal("0.00"))
    gst_collected: Decimal = Field(default=Decimal("0.00"))
    gst_paid: Decimal = Field(default=Decimal("0.00"))
    net_gst: Decimal = Field(default=Decimal("0.00"))
    status_counts: StatusCounts
    quality: QualitySummary = Field(default_factory=QualitySummary)
    quarter_label: str
    quarter: int
    fy_year: int
    quarter_start: date
    quarter_end: date
    last_sync_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ClientPortfolioItem(BaseModel):
    """Single client business (XeroConnection) with financial summary.

    Each item represents one Xero organization = one business = one BAS to lodge.
    NOT a contact within an organization.
    """

    id: UUID  # XeroConnection ID
    organization_name: str  # The business name from Xero
    total_sales: Decimal = Field(default=Decimal("0.00"))
    total_purchases: Decimal = Field(default=Decimal("0.00"))
    gst_collected: Decimal = Field(default=Decimal("0.00"))
    gst_paid: Decimal = Field(default=Decimal("0.00"))
    net_gst: Decimal = Field(default=Decimal("0.00"))
    invoice_count: int = 0
    transaction_count: int = 0
    activity_count: int = 0
    bas_status: BASStatus
    quality_score: Decimal | None = Field(default=None, description="Overall quality score %")
    critical_issues: int = Field(default=0, description="Count of critical quality issues")
    last_synced_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ClientPortfolioResponse(BaseModel):
    """Paginated list of client businesses with financial summaries."""

    clients: list[ClientPortfolioItem]
    total: int
    page: int
    limit: int
