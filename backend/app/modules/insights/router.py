"""API routes for insights."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.a2ui import A2UIMessage, get_device_context_from_request
from app.core.audit import AuditService
from app.core.dependencies import PineconeDep, VoyageDep, get_current_tenant_id
from app.database import get_db
from app.modules.action_items.models import ActionItemPriority
from app.modules.action_items.schemas import (
    ActionItemCreate,
    ActionItemResponse,
    ConvertInsightRequest,
)
from app.modules.action_items.service import ActionItemService
from app.modules.insights.a2ui_generator import generate_insight_ui
from app.modules.insights.models import InsightPriority, InsightStatus
from app.modules.insights.schemas import (
    InsightDashboardResponse,
    InsightGenerationResponse,
    InsightListResponse,
    InsightResponse,
    MarkInsightRequest,
    MultiClientQueryRequest,
    MultiClientQueryResponse,
)
from app.modules.insights.service import InsightService
from app.modules.insights.thresholds import THRESHOLD_REGISTRY, ThresholdRegistryResponse

router = APIRouter(prefix="/api/v1/insights", tags=["insights"])
platform_router = APIRouter(prefix="/api/v1/platform", tags=["platform"])


# Type aliases
DbSession = Annotated[AsyncSession, Depends(get_db)]
TenantIdDep = Annotated[UUID, Depends(get_current_tenant_id)]


async def get_current_user_id(request: Request) -> str:
    """Get current user ID from Clerk JWT claims."""
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user.sub


UserIdDep = Annotated[str, Depends(get_current_user_id)]


async def get_insight_service(db: DbSession) -> InsightService:
    """Dependency to get insight service."""
    return InsightService(db)


InsightServiceDep = Annotated[InsightService, Depends(get_insight_service)]


async def get_audit_service(db: DbSession) -> AuditService:
    """Dependency to get audit service."""
    return AuditService(session=db)


AuditServiceDep = Annotated[AuditService, Depends(get_audit_service)]


@router.get("", response_model=InsightListResponse)
async def list_insights(
    service: InsightServiceDep,
    tenant_id: TenantIdDep,
    status: list[str] | None = Query(None, description="Filter by status"),
    priority: list[str] | None = Query(None, description="Filter by priority"),
    category: list[str] | None = Query(None, description="Filter by category"),
    client_id: UUID | None = Query(None, description="Filter by client"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> InsightListResponse:
    """List insights with filtering.

    By default excludes dismissed and expired insights.
    """
    return await service.list(
        tenant_id=tenant_id,
        status=status,
        priority=priority,
        category=category,
        client_id=client_id,
        limit=limit,
        offset=offset,
    )


@router.get("/dashboard", response_model=InsightDashboardResponse)
async def get_dashboard(
    service: InsightServiceDep,
    tenant_id: TenantIdDep,
    top_count: int = Query(5, ge=1, le=20),
) -> InsightDashboardResponse:
    """Get dashboard summary with top insights and stats."""
    return await service.get_dashboard(tenant_id, top_count)


@router.get("/{insight_id}", response_model=InsightResponse)
async def get_insight(
    insight_id: UUID,
    service: InsightServiceDep,
    tenant_id: TenantIdDep,
) -> InsightResponse:
    """Get a single insight by ID."""
    insight = await service.get_by_id(insight_id, tenant_id)
    if not insight:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insight not found",
        )
    return service._to_response(insight)


@router.get("/{insight_id}/ui", response_model=A2UIMessage, tags=["A2UI"])
async def get_insight_ui(
    insight_id: UUID,
    service: InsightServiceDep,
    tenant_id: TenantIdDep,
    db: DbSession,
    user_agent: str | None = Header(None, alias="user-agent"),
    x_device_type: str | None = Header(None, alias="X-Device-Type"),
) -> A2UIMessage:
    """Get A2UI for an insight.

    Returns a dynamic UI message that adapts based on:
    - Insight severity and priority
    - Device type (mobile/tablet/desktop)
    - Insight content and data
    """
    insight = await service.get_by_id(insight_id, tenant_id)
    if not insight:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insight not found",
        )

    device_context = get_device_context_from_request(user_agent, x_device_type)
    return await generate_insight_ui(db, insight, device_context)


@router.post("/{insight_id}/view", response_model=InsightResponse)
async def mark_viewed(
    insight_id: UUID,
    service: InsightServiceDep,
    tenant_id: TenantIdDep,
    db: DbSession,
) -> InsightResponse:
    """Mark an insight as viewed."""
    insight = await service.mark_viewed(insight_id, tenant_id)
    if not insight:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insight not found",
        )
    await db.commit()
    return service._to_response(insight)


@router.post("/{insight_id}/action", response_model=InsightResponse)
async def mark_actioned(
    insight_id: UUID,
    service: InsightServiceDep,
    tenant_id: TenantIdDep,
    db: DbSession,
    pinecone: PineconeDep,
    voyage: VoyageDep,
    request: MarkInsightRequest | None = None,
) -> InsightResponse:
    """Mark an insight as actioned."""
    notes = request.notes if request else None
    insight = await service.mark_actioned(insight_id, tenant_id, notes)
    if not insight:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insight not found",
        )
    await db.commit()

    # Remove dedup vector so the topic can be re-created if it resurfaces
    from app.modules.insights.dedup import InsightDedupService

    dedup = InsightDedupService(pinecone, voyage, db)
    await dedup.remove_insight(insight_id)

    return service._to_response(insight)


@router.post("/{insight_id}/dismiss", response_model=InsightResponse)
async def dismiss_insight(
    insight_id: UUID,
    service: InsightServiceDep,
    tenant_id: TenantIdDep,
    db: DbSession,
    pinecone: PineconeDep,
    voyage: VoyageDep,
    request: MarkInsightRequest | None = None,
) -> InsightResponse:
    """Dismiss an insight."""
    notes = request.notes if request else None
    insight = await service.dismiss(insight_id, tenant_id, notes)
    if not insight:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insight not found",
        )
    await db.commit()

    # Remove dedup vector so the topic can be re-created if it resurfaces
    from app.modules.insights.dedup import InsightDedupService

    dedup = InsightDedupService(pinecone, voyage, db)
    await dedup.remove_insight(insight_id)

    return service._to_response(insight)


@router.post("/{insight_id}/expand", response_model=InsightResponse)
async def expand_insight(
    insight_id: UUID,
    service: InsightServiceDep,
    tenant_id: TenantIdDep,
    db: DbSession,
    audit_service: AuditServiceDep,
    pinecone: PineconeDep,
    voyage: VoyageDep,
) -> InsightResponse:
    """Expand an insight with multi-agent OPTIONS analysis.

    Takes any insight and routes it through the Multi-Agent Orchestrator
    to generate strategic OPTIONS with trade-offs and recommendations.
    """
    # Import here to avoid circular imports
    from app.modules.agents.orchestrator import MultiPerspectiveOrchestrator

    # Get the insight
    insight = await service.get_by_id(insight_id, tenant_id)
    if not insight:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insight not found",
        )

    # Skip if already expanded
    if insight.generation_type == "magic_zone":
        return service._to_response(insight)

    # Build query for orchestrator based on insight content
    query = f"""Analyze this issue and provide strategic OPTIONS with trade-offs:

Title: {insight.title}
Summary: {insight.summary}
Category: {insight.category}
Priority: {insight.priority}

{insight.detail or ""}

Please provide 2-4 strategic OPTIONS for addressing this issue,
including pros, cons, and recommended actions for each option."""

    # Call orchestrator with OPTIONS format
    orchestrator = MultiPerspectiveOrchestrator(db)
    response = await orchestrator.process_query(
        query=query,
        tenant_id=tenant_id,
        user_id=tenant_id,  # Use tenant as user for expansion
        connection_id=insight.client_id,
        options_format=True,
    )

    # Count OPTIONS in response
    import re

    options_pattern = r"###\s*Option\s+\d+"
    options_count = len(re.findall(options_pattern, response.content, re.IGNORECASE))

    # Build evidence snapshot from structured context (before it was flattened to prompt)
    from app.modules.insights.evidence import build_evidence_snapshot, trim_snapshot_to_size

    snapshot = build_evidence_snapshot(
        client_context=response.raw_client_context,
        perspective_contexts=response.raw_perspective_contexts,
    )
    snapshot.perspectives_used = [p.value for p in response.perspectives_used]
    trimmed_snapshot = trim_snapshot_to_size(snapshot)

    # Update the insight
    insight.detail = response.content
    insight.generation_type = "magic_zone"
    insight.agents_used = [p.value for p in response.perspectives_used]
    insight.options_count = options_count
    insight.data_snapshot = trimmed_snapshot

    # Audit: insight expanded
    evidence_count = 0
    if trimmed_snapshot and isinstance(trimmed_snapshot, dict):
        evidence_count = len(trimmed_snapshot.get("evidence_items", []) or [])
    await audit_service.log_event(
        event_type="insight.expanded",
        event_category="data",
        actor_type="user",
        tenant_id=tenant_id,
        resource_type="insight",
        resource_id=insight_id,
        action="update",
        outcome="success",
        metadata={
            "client_id": str(insight.client_id) if insight.client_id else None,
            "perspectives_used": [p.value for p in response.perspectives_used],
            "evidence_count": evidence_count,
            "options_count": options_count,
        },
    )

    await db.commit()
    await db.refresh(insight)

    # Refresh dedup vector to reflect updated title/summary
    from app.modules.insights.dedup import InsightDedupService

    dedup = InsightDedupService(pinecone, voyage, db)
    await dedup.update_insight_vector(insight)

    return service._to_response(insight)


@router.post("/generate", response_model=InsightGenerationResponse)
async def generate_insights(
    service: InsightServiceDep,
    tenant_id: TenantIdDep,
    db: DbSession,
    pinecone: PineconeDep,
    voyage: VoyageDep,
    client_id: UUID | None = Query(None, description="Generate for specific client only"),
) -> InsightGenerationResponse:
    """Manually trigger insight generation.

    If client_id is provided, only generates for that client.
    Otherwise generates for all clients in the tenant.
    """
    # Import here to avoid circular imports
    from app.modules.insights.generator import InsightGenerator

    try:
        generator = InsightGenerator(db, pinecone=pinecone, voyage=voyage)

        if client_id:
            insights = await generator.generate_for_client(
                tenant_id=tenant_id,
                client_id=client_id,
                source="manual",
            )
        else:
            insights = await generator.generate_for_tenant(
                tenant_id=tenant_id,
                source="manual",
            )

        await db.commit()

        # Refresh insights to load relationships after commit
        # This prevents greenlet_spawn errors from lazy loading
        insight_ids = [i.id for i in insights]
        response_insights = []
        for insight_id in insight_ids:
            refreshed = await service.get_by_id(insight_id, tenant_id)
            if refreshed:
                response_insights.append(service._to_response(refreshed))

        return InsightGenerationResponse(
            generated_count=len(insights),
            insights=response_insights,
            client_id=client_id,
        )
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error("Insight generation failed: %s", e, exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Insight generation failed: {e}",
        )


@router.post("/query", response_model=MultiClientQueryResponse)
async def multi_client_query(
    request: MultiClientQueryRequest,
    service: InsightServiceDep,
    tenant_id: TenantIdDep,
) -> MultiClientQueryResponse:
    """Query insights across all clients.

    Uses AI to analyze insights and answer questions like:
    - "Which clients have GST issues?"
    - "What are the top compliance concerns?"
    - "Which clients need attention this week?"

    Returns an AI-generated response with references to specific clients.
    """
    return await service.query_multi_client(
        tenant_id=tenant_id,
        query=request.query,
        include_inactive=request.include_inactive,
    )


def _map_insight_priority_to_action(priority: InsightPriority) -> ActionItemPriority:
    """Map insight priority to action item priority."""
    mapping = {
        InsightPriority.HIGH: ActionItemPriority.HIGH,
        InsightPriority.MEDIUM: ActionItemPriority.MEDIUM,
        InsightPriority.LOW: ActionItemPriority.LOW,
    }
    return mapping.get(priority, ActionItemPriority.MEDIUM)


@router.post("/{insight_id}/convert-to-action", response_model=ActionItemResponse)
async def convert_insight_to_action(
    insight_id: UUID,
    request: ConvertInsightRequest,
    service: InsightServiceDep,
    tenant_id: TenantIdDep,
    user_id: UserIdDep,
    db: DbSession,
) -> ActionItemResponse:
    """Convert an insight into an action item.

    Creates an action item linked to the insight, using the insight's
    title, client, and priority as defaults. These can be overridden
    via the request body.

    The insight will be marked as ACTIONED after conversion.
    """

    # Get the insight
    insight = await service.get_by_id(insight_id, tenant_id)
    if not insight:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insight not found",
        )

    # Check if insight is already actioned
    if insight.status == InsightStatus.ACTIONED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insight has already been actioned",
        )

    # Get client name from relationship if available
    client_name = insight.client.organization_name if insight.client else None

    # Create action item data
    action_data = ActionItemCreate(
        title=request.title or insight.title,
        description=request.description or insight.summary,
        notes=request.notes,
        source_insight_id=insight.id,
        client_id=insight.client_id,
        client_name=client_name,
        assigned_to_user_id=request.assigned_to_user_id,
        assigned_to_name=request.assigned_to_name,
        due_date=request.due_date or insight.action_deadline,
        priority=request.priority or _map_insight_priority_to_action(insight.priority),
    )

    # Create action item (user_id is the creator/assigned_by)
    action_service = ActionItemService(db)
    action_item = await action_service.create(tenant_id, user_id, action_data)

    # Mark insight as actioned
    await service.mark_actioned(insight_id, tenant_id, notes="Converted to action item")
    await db.commit()

    # Refresh action item to get latest state
    action_item = await action_service.get_by_id(tenant_id, action_item.id)

    return ActionItemResponse.from_model(action_item)


# =============================================================================
# Platform endpoints (threshold transparency)
# =============================================================================


@platform_router.get("/thresholds", response_model=ThresholdRegistryResponse)
async def get_thresholds(
    _tenant_id: TenantIdDep,
) -> ThresholdRegistryResponse:
    """Get all platform threshold rules.

    Returns the threshold registry used for all computed scores,
    severity classifications, and trigger conditions. Used by the
    frontend to render tooltip explanations.
    """
    return ThresholdRegistryResponse(thresholds=THRESHOLD_REGISTRY)
