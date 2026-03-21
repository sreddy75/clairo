"""Pydantic schemas for the agents module."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.a2ui import A2UIMessage


class Perspective(str, Enum):
    """Available analysis perspectives."""

    COMPLIANCE = "compliance"
    QUALITY = "quality"
    STRATEGY = "strategy"
    INSIGHT = "insight"

    @property
    def display_name(self) -> str:
        """Human-readable name for the perspective."""
        return self.value.title()

    @property
    def description(self) -> str:
        """Description of what this perspective covers."""
        descriptions = {
            "compliance": "ATO rules, GST, BAS requirements, tax obligations",
            "quality": "Data issues, reconciliation, coding errors, duplicates",
            "strategy": "Tax optimization, business structure, growth advice",
            "insight": "Trends, patterns, anomalies, projections",
        }
        return descriptions.get(self.value, "")

    @property
    def color(self) -> str:
        """Color code for UI display."""
        colors = {
            "compliance": "blue",
            "quality": "orange",
            "strategy": "green",
            "insight": "purple",
        }
        return colors.get(self.value, "gray")


@dataclass
class PerspectiveResult:
    """Result from a single perspective analysis."""

    perspective: Perspective
    content: str
    citations: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.7


@dataclass
class PerspectiveContext:
    """Context gathered for a specific perspective."""

    perspective: Perspective
    knowledge_chunks: list[dict[str, Any]] = field(default_factory=list)
    client_data: dict[str, Any] | None = None
    quality_data: dict[str, Any] | None = None
    trend_data: dict[str, Any] | None = None


@dataclass
class OrchestratorResponse:
    """Response from the multi-perspective orchestrator."""

    correlation_id: UUID
    content: str  # Full response with [Perspective] markers
    perspectives_used: list[Perspective]
    perspective_results: list[PerspectiveResult]
    confidence: float
    escalation_required: bool
    escalation_reason: str | None
    citations: list[dict[str, Any]]
    processing_time_ms: int
    token_usage: int | None = None
    a2ui_message: A2UIMessage | None = None  # Rich UI components
    # Evidence traceability: raw structured context for snapshot building
    raw_client_context: Any | None = None
    raw_perspective_contexts: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "correlation_id": str(self.correlation_id),
            "content": self.content,
            "perspectives_used": [p.value for p in self.perspectives_used],
            "perspective_results": [
                {
                    "perspective": r.perspective.value,
                    "content": r.content,
                    "citations": r.citations,
                    "confidence": r.confidence,
                }
                for r in self.perspective_results
            ],
            "confidence": self.confidence,
            "escalation_required": self.escalation_required,
            "escalation_reason": self.escalation_reason,
            "citations": self.citations,
            "processing_time_ms": self.processing_time_ms,
            "token_usage": self.token_usage,
            "a2ui_message": self.a2ui_message.model_dump(by_alias=True)
            if self.a2ui_message
            else None,
        }


# API Request/Response Models


class AgentChatRequest(BaseModel):
    """Request for multi-perspective agent chat."""

    query: str = Field(..., min_length=1, max_length=2000)
    connection_id: UUID | None = Field(
        None, description="Client connection ID for client-specific queries"
    )
    conversation_id: UUID | None = Field(
        None, description="Conversation ID for follow-up questions"
    )


class PerspectiveResultResponse(BaseModel):
    """Individual perspective result in API response."""

    perspective: str
    content: str
    citations: list[dict[str, Any]] = []
    confidence: float


class AgentChatResponse(BaseModel):
    """Response from multi-perspective agent chat."""

    correlation_id: str
    content: str
    perspectives_used: list[str]
    perspective_results: list[PerspectiveResultResponse]
    confidence: float
    escalation_required: bool
    escalation_reason: str | None = None
    citations: list[dict[str, Any]] = []
    processing_time_ms: int
    a2ui_message: dict[str, Any] | None = None  # Rich UI components
    data_freshness: str | None = None  # ISO datetime of last data sync


class AgentChatMetadata(BaseModel):
    """Metadata sent at end of streaming response."""

    correlation_id: str
    perspectives_used: list[str]
    confidence: float
    escalation_required: bool
    escalation_reason: str | None = None
    citations: list[dict[str, Any]] = []
    processing_time_ms: int
    a2ui_message: dict[str, Any] | None = None  # Rich UI components
    data_freshness: str | None = None  # ISO datetime of last data sync


# Escalation Models


class EscalationStatus(str, Enum):
    """Status of an escalation."""

    PENDING = "pending"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class EscalationResponse(BaseModel):
    """Escalation record in API response."""

    id: UUID
    query_id: UUID
    reason: str
    confidence: float
    status: EscalationStatus
    query_preview: str  # First 200 chars of query
    perspectives_used: list[str]
    connection_id: UUID | None = None
    created_at: datetime
    resolved_at: datetime | None = None
    resolved_by_name: str | None = None


class ResolveEscalationRequest(BaseModel):
    """Request to resolve an escalation."""

    resolution_notes: str = Field(..., min_length=1, max_length=2000)
    accountant_response: str | None = Field(None, description="Accountant's answer to the query")
    feedback_useful: bool | None = Field(
        None, description="Was the agent's partial analysis useful?"
    )


class EscalationStatsResponse(BaseModel):
    """Statistics about escalations."""

    pending_count: int
    resolved_today: int
    average_confidence: float
    top_reasons: list[dict[str, Any]]
