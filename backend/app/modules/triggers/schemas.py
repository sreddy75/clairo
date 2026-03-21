"""Pydantic schemas for triggers."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.triggers.models import TriggerStatus, TriggerType

# ============================================================================
# Trigger Schemas
# ============================================================================


class TriggerConfigDataThreshold(BaseModel):
    """Configuration for data threshold triggers."""

    metric: str = Field(..., description="Metric to evaluate (e.g., 'revenue_ytd')")
    operator: str = Field(..., description="Comparison operator: gt, gte, lt, lte, eq")
    threshold: float = Field(..., description="Threshold value to compare against")


class TriggerConfigTimeScheduled(BaseModel):
    """Configuration for time-scheduled triggers."""

    cron: str = Field(..., description="Cron expression (e.g., '0 6 * * *')")
    timezone: str = Field(
        default="Australia/Sydney",
        description="Timezone for schedule",
    )
    days_before_deadline: int | None = Field(
        default=None,
        description="For deadline reminders, days before BAS deadline",
    )


class TriggerConfigEventBased(BaseModel):
    """Configuration for event-based triggers."""

    event: str = Field(
        ...,
        description="Event type to listen for (e.g., 'xero_sync_complete')",
    )
    conditions: dict | None = Field(
        default=None,
        description="Additional conditions to match",
    )


class TriggerCreate(BaseModel):
    """Schema for creating a trigger."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    trigger_type: TriggerType
    config: dict = Field(..., description="Type-specific configuration")
    target_analyzers: list[str] = Field(
        ...,
        min_length=1,
        description="List of analyzer names to run",
    )
    dedup_window_hours: int = Field(
        default=168,
        ge=0,
        description="Hours to wait before creating similar insight",
    )


class TriggerUpdate(BaseModel):
    """Schema for updating a trigger."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    config: dict | None = None
    target_analyzers: list[str] | None = None
    dedup_window_hours: int | None = Field(default=None, ge=0)
    status: TriggerStatus | None = None


class TriggerResponse(BaseModel):
    """Schema for trigger response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    trigger_type: TriggerType
    config: dict
    target_analyzers: list[str]
    dedup_window_hours: int
    status: TriggerStatus
    is_system_default: bool
    last_executed_at: datetime | None
    last_error: str | None
    consecutive_failures: int
    created_at: datetime
    updated_at: datetime

    # Computed fields (added by service)
    executions_24h: int | None = None
    insights_24h: int | None = None


class TriggerListResponse(BaseModel):
    """Paginated list of triggers."""

    items: list[TriggerResponse]
    total: int
    limit: int
    offset: int


# ============================================================================
# Trigger Execution Schemas
# ============================================================================


class TriggerExecutionResponse(BaseModel):
    """Schema for trigger execution response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    trigger_id: UUID
    tenant_id: UUID
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
    status: str
    clients_evaluated: int
    insights_created: int
    insights_deduplicated: int
    error_message: str | None

    # Added by service
    trigger_name: str | None = None


class TriggerExecutionListResponse(BaseModel):
    """Paginated list of trigger executions."""

    items: list[TriggerExecutionResponse]
    total: int
    limit: int
    offset: int


# ============================================================================
# Trigger Test Schemas
# ============================================================================


class TriggerTestRequest(BaseModel):
    """Request to test a trigger (dry run)."""

    client_ids: list[UUID] | None = Field(
        default=None,
        description="Specific clients to test, or None for all",
    )
    dry_run: bool = Field(
        default=True,
        description="If true, don't create insights",
    )


class TriggerTestResponse(BaseModel):
    """Response from trigger test."""

    would_fire: bool
    clients_matched: int
    insights_would_create: int
    insights_would_dedup: int
    details: list[dict] = Field(default_factory=list)
