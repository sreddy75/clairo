"""Pydantic schemas for the queries module."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Request for ad-hoc query visualization."""

    query: str = Field(..., min_length=1, max_length=1000, description="Natural language query")
    connection_id: UUID | None = Field(
        None, description="Client connection ID for client-specific queries"
    )


class QueryResponse(BaseModel):
    """Response from query visualization endpoint."""

    correlation_id: str
    text_response: str
    a2ui_message: dict[str, Any] | None = None
    query_type: str
    confidence: float
    time_period: dict[str, Any] | None = None
    metric_focus: list[str] = []


class QueryHistoryItem(BaseModel):
    """Single item in query history."""

    id: UUID
    query: str
    query_type: str
    timestamp: str
    connection_id: UUID | None = None
    client_name: str | None = None


class QueryHistoryResponse(BaseModel):
    """Response with query history."""

    queries: list[QueryHistoryItem]
    total: int
