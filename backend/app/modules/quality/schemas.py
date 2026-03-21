"""Pydantic schemas for quality scoring API."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

# =============================================================================
# Quality Dimension Schemas
# =============================================================================


class QualityDimensionResponse(BaseModel):
    """Individual quality dimension score."""

    name: str = Field(..., description="Dimension name")
    score: Decimal = Field(..., ge=0, le=100, description="Score 0-100")
    weight: Decimal = Field(..., ge=0, le=1, description="Weight 0-1")
    details: str = Field(..., description="Human-readable details")
    applicable: bool = Field(default=True, description="Whether dimension applies")


class QualityDimensionsResponse(BaseModel):
    """All quality dimension scores."""

    freshness: QualityDimensionResponse
    reconciliation: QualityDimensionResponse
    categorization: QualityDimensionResponse
    completeness: QualityDimensionResponse
    payg_readiness: QualityDimensionResponse


# =============================================================================
# Quality Issue Schemas
# =============================================================================


class IssueCounts(BaseModel):
    """Issue counts by severity."""

    critical: int = Field(default=0)
    error: int = Field(default=0)
    warning: int = Field(default=0)
    info: int = Field(default=0)

    @property
    def total(self) -> int:
        """Total number of issues."""
        return self.critical + self.error + self.warning + self.info


class QualityIssueResponse(BaseModel):
    """A quality issue."""

    id: UUID
    code: str = Field(..., description="Issue code (e.g., STALE_DATA)")
    severity: str = Field(..., description="Severity level")
    title: str = Field(..., description="Issue title")
    description: str | None = Field(None, description="Detailed description")
    affected_entity_type: str | None = Field(None, description="Type of affected entity")
    affected_count: int = Field(default=0, description="Number of affected items")
    affected_ids: list[str] = Field(default_factory=list, description="IDs of affected items")
    suggested_action: str | None = Field(None, description="Suggested resolution")
    first_detected_at: datetime = Field(..., description="When issue was first detected")
    dismissed: bool = Field(default=False, description="Whether issue is dismissed")
    dismissed_by: UUID | None = Field(None, description="User who dismissed")
    dismissed_at: datetime | None = Field(None, description="When dismissed")
    dismissed_reason: str | None = Field(None, description="Reason for dismissal")


class QualityIssuesListResponse(BaseModel):
    """List of quality issues."""

    issues: list[QualityIssueResponse] = Field(default_factory=list)
    total: int = Field(default=0)


# =============================================================================
# Quality Score Schemas
# =============================================================================


class QualityScoreResponse(BaseModel):
    """Quality score summary for a connection."""

    overall_score: Decimal = Field(..., ge=0, le=100, description="Overall quality score")
    dimensions: QualityDimensionsResponse = Field(..., description="Score breakdown by dimension")
    issue_counts: IssueCounts = Field(default_factory=IssueCounts, description="Issues by severity")
    last_checked_at: datetime | None = Field(None, description="When quality was last calculated")
    trend: str | None = Field(None, description="Score trend: improving, stable, declining")
    has_score: bool = Field(default=False, description="Whether a score has been calculated")


class QualityRecalculateResponse(BaseModel):
    """Response from quality recalculation."""

    overall_score: Decimal = Field(..., description="New overall score")
    issues_found: int = Field(default=0, description="Number of issues detected")
    calculated_at: datetime = Field(..., description="When calculation was performed")


# =============================================================================
# Quality Actions Schemas
# =============================================================================


class DismissIssueRequest(BaseModel):
    """Request to dismiss an issue."""

    reason: str = Field(..., min_length=1, max_length=500, description="Reason for dismissal")


class DismissIssueResponse(BaseModel):
    """Response from dismissing an issue."""

    success: bool = Field(default=True)
    issue_id: UUID
    dismissed_at: datetime


# =============================================================================
# Dashboard Quality Schemas
# =============================================================================


class DashboardQualitySummary(BaseModel):
    """Quality summary for dashboard."""

    avg_score: Decimal = Field(..., description="Average quality score across clients")
    good_count: int = Field(default=0, description="Clients with score > 80%")
    fair_count: int = Field(default=0, description="Clients with score 50-80%")
    poor_count: int = Field(default=0, description="Clients with score < 50%")
    total_critical_issues: int = Field(
        default=0, description="Total critical issues across clients"
    )
