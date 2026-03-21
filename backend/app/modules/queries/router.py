"""API endpoints for ad-hoc queries with visualization."""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.a2ui import DeviceContext
from app.core.dependencies import get_current_practice_user, get_db
from app.modules.agents.query_agent import process_query_with_visualization
from app.modules.auth.models import PracticeUser
from app.modules.integrations.xero.repository import XeroConnectionRepository

from .schemas import QueryRequest, QueryResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/queries", tags=["queries"])


async def get_client_data_for_query(
    connection_id: UUID,
    session: AsyncSession,
    tenant_id: UUID,
) -> dict | None:
    """Fetch client financial data for query context."""
    repo = XeroConnectionRepository(session)
    connection = await repo.get_by_id(connection_id)

    if not connection or connection.tenant_id != tenant_id:
        return None

    # In production, fetch actual financial data from Xero sync
    # For now, return the organization name for context
    return {
        "client_name": connection.organization_name,
        "connection_id": str(connection_id),
    }


@router.post(
    "/ui",
    response_model=QueryResponse,
    summary="Process query with A2UI visualization",
    description="Process a natural language query and return visual answer components.",
)
async def process_query_ui(
    request: QueryRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
    is_mobile: bool = False,
    is_tablet: bool = False,
) -> QueryResponse:
    """
    Process a natural language query and generate visualization.

    The endpoint analyzes the query, classifies it (summary, trend, comparison, etc.),
    and returns appropriate A2UI components for visualization.

    ## Query Types Supported

    - **Summary**: Overview requests ("What's my GST position?")
    - **Trend**: Time-based analysis ("How has revenue changed?")
    - **Comparison**: Period comparisons ("Compare Q1 vs Q2")
    - **Breakdown**: Category analysis ("Where are my expenses going?")
    - **List**: Item listings ("Show overdue invoices")
    - **Anomaly**: Issue detection ("Any unusual patterns?")

    ## Examples

    - "What's my GST liability for this quarter?"
    - "Show me the expense breakdown by category"
    - "Who owes me money?"
    - "Compare this quarter to last quarter"
    - "What are the trends in my revenue?"
    """
    client_data = None

    # If client-specific query, fetch client data
    if request.connection_id:
        client_data = await get_client_data_for_query(
            request.connection_id,
            session,
            user.tenant_id,
        )
        if client_data is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client connection not found",
            )

    # Create device context
    device_context = DeviceContext(
        isMobile=is_mobile,
        isTablet=is_tablet,
    )

    try:
        result = await process_query_with_visualization(
            query=request.query,
            client_data=client_data,
            connection_id=request.connection_id,
            device_context=device_context,
        )

        return QueryResponse(
            correlation_id=result["correlation_id"],
            text_response=result["text_response"],
            a2ui_message=result["a2ui_message"].model_dump(by_alias=True)
            if result.get("a2ui_message")
            else None,
            query_type=result["query_type"],
            confidence=result["confidence"],
            time_period=result.get("time_period"),
            metric_focus=result.get("metric_focus", []),
        )

    except Exception as e:
        logger.exception(f"Error processing query: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process query",
        ) from e


@router.get(
    "/suggestions",
    summary="Get query suggestions",
    description="Get suggested queries based on user context and recent activity.",
)
async def get_query_suggestions(
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
    connection_id: UUID | None = None,
) -> dict:
    """
    Get suggested queries based on context.

    Returns a list of suggested queries that the user might find useful
    based on their recent activity and the current time period.
    """
    # Base suggestions applicable to all users
    general_suggestions = [
        {
            "query": "What's my GST position for this quarter?",
            "category": "GST",
            "icon": "dollar-sign",
        },
        {
            "query": "Show expense breakdown by category",
            "category": "Expenses",
            "icon": "pie-chart",
        },
        {
            "query": "Compare this quarter to last quarter",
            "category": "Comparison",
            "icon": "bar-chart-2",
        },
        {
            "query": "What are my revenue trends?",
            "category": "Trends",
            "icon": "trending-up",
        },
        {
            "query": "Who owes me money?",
            "category": "Receivables",
            "icon": "users",
        },
        {
            "query": "Any unusual patterns in my data?",
            "category": "Anomalies",
            "icon": "alert-triangle",
        },
    ]

    # Add client-specific suggestions if connection provided
    if connection_id:
        client_suggestions = [
            {
                "query": "What's this client's BAS status?",
                "category": "BAS",
                "icon": "file-text",
            },
            {
                "query": "Show overdue invoices for this client",
                "category": "Receivables",
                "icon": "clock",
            },
        ]
        return {
            "suggestions": client_suggestions + general_suggestions[:4],
            "connection_id": str(connection_id),
        }

    return {"suggestions": general_suggestions}
