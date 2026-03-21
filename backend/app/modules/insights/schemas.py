"""Pydantic schemas for insights."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.insights.models import InsightCategory, InsightPriority


class SuggestedAction(BaseModel):
    """A suggested action for an insight."""

    model_config = {"extra": "ignore"}

    label: str = Field(..., description="Button label for the action")
    url: str | None = Field(None, description="URL to navigate to")
    action: str | None = Field(None, description="Action type (e.g., 'schedule_meeting')")


class InsightCreate(BaseModel):
    """Schema for creating a new insight."""

    category: InsightCategory
    insight_type: str = Field(..., max_length=100)
    priority: InsightPriority = InsightPriority.MEDIUM

    title: str = Field(..., max_length=255)
    summary: str
    detail: str | None = None

    suggested_actions: list[SuggestedAction] = Field(default_factory=list)
    related_url: str | None = Field(None, max_length=500)

    expires_at: datetime | None = None
    action_deadline: datetime | None = Field(
        None, description="Date by which action should be taken (e.g., BAS due date)"
    )
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    data_snapshot: dict[str, Any] | None = None

    # Magic Zone fields
    generation_type: str = Field(
        default="rule_based",
        description="How insight was generated: rule_based, ai_single, or magic_zone",
    )
    agents_used: list[str] | None = Field(
        default=None,
        description="List of agent names that contributed to this insight",
    )
    options_count: int | None = Field(
        default=None,
        description="Number of OPTIONS presented in the insight detail",
    )


class InsightResponse(BaseModel):
    """Schema for insight response."""

    id: UUID
    tenant_id: UUID
    client_id: UUID | None

    category: str
    insight_type: str
    priority: str

    title: str
    summary: str
    detail: str | None

    suggested_actions: list[SuggestedAction]
    related_url: str | None

    status: str
    generated_at: datetime
    expires_at: datetime | None
    action_deadline: datetime | None = None
    viewed_at: datetime | None
    actioned_at: datetime | None

    generation_source: str
    confidence: float | None
    data_snapshot: dict[str, Any] | None = None

    # Magic Zone fields
    generation_type: str = "rule_based"
    agents_used: list[str] | None = None
    options_count: int | None = None

    # Client info for navigation
    client_name: str | None = None
    client_url: str | None = None  # Direct link to client page

    model_config = {"from_attributes": True}


class InsightListResponse(BaseModel):
    """Response for listing insights with pagination."""

    insights: list[InsightResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class InsightStats(BaseModel):
    """Statistics about insights."""

    total: int
    by_priority: dict[str, int]  # {"high": 5, "medium": 10, "low": 3}
    by_category: dict[str, int]  # {"compliance": 8, "quality": 10}
    by_status: dict[str, int]  # {"new": 12, "viewed": 5}
    new_this_week: int


class InsightDashboardResponse(BaseModel):
    """Dashboard widget response with top insights and stats."""

    top_insights: list[InsightResponse]
    stats: InsightStats
    new_count: int  # Unviewed insights


class InsightGenerationResponse(BaseModel):
    """Response from manual insight generation."""

    generated_count: int
    insights: list[InsightResponse]
    client_id: UUID | None = None


class MarkInsightRequest(BaseModel):
    """Request to mark an insight (viewed, actioned, dismissed)."""

    notes: str | None = Field(None, description="Optional notes about the action")


# Multi-client query schemas


class ClientReference(BaseModel):
    """Reference to a client mentioned in multi-client query response."""

    id: UUID
    name: str
    issues: list[str] = Field(default_factory=list)


class MultiClientQueryRequest(BaseModel):
    """Request for multi-client query."""

    query: str = Field(..., min_length=1, max_length=1000)
    include_inactive: bool = False


class MultiClientQueryResponse(BaseModel):
    """Response from multi-client query."""

    response: str
    clients_referenced: list[ClientReference]
    perspectives_used: list[str]
    confidence: float
    insights_included: int  # Number of insights used in context
