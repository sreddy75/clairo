"""API router for Tax Planning module.

All endpoints require authentication and extract tenant_id from current user.
Domain exceptions are caught and converted to HTTPException responses.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.exceptions import DomainError
from app.database import get_db
from app.modules.auth.models import PracticeUser
from app.modules.auth.permissions import Permission, require_permission
from app.modules.tax_planning.models import TaxPlan
from app.modules.tax_planning.schemas import (
    ChatMessageRequest,
    ChatResponse,
    FinancialsInput,
    FinancialsPullResponse,
    MessageListResponse,
    TaxPlanCreate,
    TaxPlanListItem,
    TaxPlanListResponse,
    TaxPlanMessageResponse,
    TaxPlanResponse,
    TaxPlanUpdate,
    TaxRateConfigResponse,
    TaxRatesResponse,
    TaxScenarioListResponse,
    TaxScenarioResponse,
    XeroPullRequest,
)
from app.modules.tax_planning.service import TaxPlanningService

router = APIRouter(prefix="/tax-plans", tags=["Tax Planning"])


def _get_service(
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TaxPlanningService:
    return TaxPlanningService(session, settings)


def _handle_domain_error(e: DomainError) -> HTTPException:
    return HTTPException(
        status_code=e.status_code,
        detail={"error": e.message, "code": e.code, "details": e.details},
    )


# ------------------------------------------------------------------
# Plan CRUD
# ------------------------------------------------------------------


@router.post("", status_code=201, response_model=TaxPlanResponse)
async def create_tax_plan(
    data: TaxPlanCreate,
    current_user: PracticeUser = Depends(require_permission(Permission.CLIENT_WRITE)),
    service: TaxPlanningService = Depends(_get_service),
):
    """Create a new tax plan for a client."""
    try:
        plan = await service.create_plan(current_user.tenant_id, data)
        client_name = await service.get_client_name(data.xero_connection_id, current_user.tenant_id)
        return _plan_to_response(plan, client_name)
    except DomainError as e:
        raise _handle_domain_error(e)


@router.get("", response_model=TaxPlanListResponse)
async def list_tax_plans(
    status: str | None = Query(None),
    financial_year: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: PracticeUser = Depends(require_permission(Permission.CLIENT_READ)),
    service: TaxPlanningService = Depends(_get_service),
):
    """List all tax plans for the current tenant."""
    try:
        plans, total = await service.list_plans(
            current_user.tenant_id, status, financial_year, search, page, page_size
        )
        items = []
        for plan in plans:
            client_name = await service.get_client_name(
                plan.xero_connection_id, current_user.tenant_id
            )
            net_position = None
            if plan.tax_position:
                net_position = plan.tax_position.get("net_position")
            items.append(
                TaxPlanListItem(
                    id=plan.id,
                    xero_connection_id=plan.xero_connection_id,
                    client_name=client_name,
                    financial_year=plan.financial_year,
                    entity_type=plan.entity_type,
                    status=plan.status,
                    data_source=plan.data_source,
                    scenario_count=len(plan.scenarios) if plan.scenarios else 0,
                    net_position=net_position,
                    updated_at=plan.updated_at,
                )
            )
        return TaxPlanListResponse(items=items, total=total, page=page, page_size=page_size)
    except DomainError as e:
        raise _handle_domain_error(e)


@router.get("/{plan_id}", response_model=TaxPlanResponse)
async def get_tax_plan(
    plan_id: uuid.UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.CLIENT_READ)),
    service: TaxPlanningService = Depends(_get_service),
):
    """Get a single tax plan with full details."""
    try:
        plan = await service.get_plan(plan_id, current_user.tenant_id)
        client_name = await service.get_client_name(plan.xero_connection_id, current_user.tenant_id)
        return _plan_to_response(plan, client_name)
    except DomainError as e:
        raise _handle_domain_error(e)


@router.patch("/{plan_id}", response_model=TaxPlanResponse)
async def update_tax_plan(
    plan_id: uuid.UUID,
    data: TaxPlanUpdate,
    current_user: PracticeUser = Depends(require_permission(Permission.CLIENT_WRITE)),
    service: TaxPlanningService = Depends(_get_service),
):
    """Update tax plan fields (status, notes, entity type)."""
    try:
        plan = await service.update_plan(plan_id, current_user.tenant_id, data)
        client_name = await service.get_client_name(plan.xero_connection_id, current_user.tenant_id)
        return _plan_to_response(plan, client_name)
    except DomainError as e:
        raise _handle_domain_error(e)


@router.delete("/{plan_id}", status_code=204)
async def delete_tax_plan(
    plan_id: uuid.UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.CLIENT_WRITE)),
    service: TaxPlanningService = Depends(_get_service),
):
    """Delete a tax plan and all associated scenarios and messages."""
    try:
        await service.delete_plan(plan_id, current_user.tenant_id)
    except DomainError as e:
        raise _handle_domain_error(e)


# ------------------------------------------------------------------
# Financials
# ------------------------------------------------------------------


@router.post(
    "/{plan_id}/financials/pull-xero",
    response_model=FinancialsPullResponse,
)
async def pull_xero_financials(
    plan_id: uuid.UUID,
    data: XeroPullRequest,
    current_user: PracticeUser = Depends(require_permission(Permission.CLIENT_WRITE)),
    service: TaxPlanningService = Depends(_get_service),
):
    """Pull the latest P&L from Xero and populate the plan's financials."""
    try:
        result = await service.pull_xero_financials(
            plan_id, current_user.tenant_id, data.force_refresh
        )
        return FinancialsPullResponse(**result)
    except DomainError as e:
        raise _handle_domain_error(e)


@router.put("/{plan_id}/financials", response_model=FinancialsPullResponse)
async def save_manual_financials(
    plan_id: uuid.UUID,
    data: FinancialsInput,
    current_user: PracticeUser = Depends(require_permission(Permission.CLIENT_WRITE)),
    service: TaxPlanningService = Depends(_get_service),
):
    """Save manually entered or adjusted financials. Recalculates tax position."""
    try:
        result = await service.save_manual_financials(plan_id, current_user.tenant_id, data)
        return FinancialsPullResponse(**result)
    except DomainError as e:
        raise _handle_domain_error(e)


# ------------------------------------------------------------------
# AI Chat
# ------------------------------------------------------------------


@router.post("/{plan_id}/chat", response_model=ChatResponse)
async def send_chat_message(
    plan_id: uuid.UUID,
    data: ChatMessageRequest,
    current_user: PracticeUser = Depends(require_permission(Permission.CLIENT_WRITE)),
    service: TaxPlanningService = Depends(_get_service),
):
    """Send a message to the tax planning AI."""
    try:
        result = await service.send_chat_message(plan_id, current_user.tenant_id, data.message)
        return ChatResponse(
            message=TaxPlanMessageResponse.model_validate(result["message"]),
            scenarios_created=[
                TaxScenarioResponse.model_validate(s) for s in result["scenarios_created"]
            ],
            updated_tax_position=result.get("updated_tax_position"),
        )
    except DomainError as e:
        raise _handle_domain_error(e)


@router.post("/{plan_id}/chat/stream")
async def send_chat_message_stream(
    plan_id: uuid.UUID,
    data: ChatMessageRequest,
    current_user: PracticeUser = Depends(require_permission(Permission.CLIENT_WRITE)),
    service: TaxPlanningService = Depends(_get_service),
):
    """Send a message with streaming SSE response."""
    import json as json_lib

    from starlette.responses import StreamingResponse

    async def generate_events():
        try:
            async for event in service.send_chat_message_streaming(
                plan_id, current_user.tenant_id, data.message
            ):
                yield f"data: {json_lib.dumps(event, default=str)}\n\n"
        except DomainError as e:
            yield f"data: {json_lib.dumps({'type': 'error', 'error': e.message})}\n\n"
        except Exception as e:
            yield f"data: {json_lib.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(generate_events(), media_type="text/event-stream")


# ------------------------------------------------------------------
# Scenarios
# ------------------------------------------------------------------


@router.get("/{plan_id}/scenarios", response_model=TaxScenarioListResponse)
async def list_scenarios(
    plan_id: uuid.UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.CLIENT_READ)),
    service: TaxPlanningService = Depends(_get_service),
):
    """List all scenarios for a tax plan."""
    try:
        scenarios = await service.list_scenarios(plan_id, current_user.tenant_id)
        return TaxScenarioListResponse(
            items=[TaxScenarioResponse.model_validate(s) for s in scenarios],
            total=len(scenarios),
        )
    except DomainError as e:
        raise _handle_domain_error(e)


@router.delete("/{plan_id}/scenarios/{scenario_id}", status_code=204)
async def delete_scenario(
    plan_id: uuid.UUID,
    scenario_id: uuid.UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.CLIENT_WRITE)),
    service: TaxPlanningService = Depends(_get_service),
):
    """Delete a specific scenario."""
    try:
        await service.delete_scenario(plan_id, current_user.tenant_id, scenario_id)
    except DomainError as e:
        raise _handle_domain_error(e)


# ------------------------------------------------------------------
# Export
# ------------------------------------------------------------------


@router.get("/{plan_id}/export")
async def export_tax_plan(
    plan_id: uuid.UUID,
    include_scenarios: bool = Query(True),
    include_conversation: bool = Query(False),
    current_user: PracticeUser = Depends(require_permission(Permission.CLIENT_READ)),
    service: TaxPlanningService = Depends(_get_service),
):
    """Export the tax plan as a formatted PDF."""
    from starlette.responses import Response as StarletteResponse

    try:
        pdf_bytes = await service.export_plan_pdf(
            plan_id, current_user.tenant_id, include_scenarios, include_conversation
        )
        return StarletteResponse(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="tax-plan-{plan_id}.pdf"'},
        )
    except DomainError as e:
        raise _handle_domain_error(e)


# ------------------------------------------------------------------
# Messages
# ------------------------------------------------------------------


@router.get("/{plan_id}/messages", response_model=MessageListResponse)
async def list_messages(
    plan_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: PracticeUser = Depends(require_permission(Permission.CLIENT_READ)),
    service: TaxPlanningService = Depends(_get_service),
):
    """Get conversation history for a tax plan."""
    try:
        messages, total = await service.list_messages(
            plan_id, current_user.tenant_id, page, page_size
        )
        return MessageListResponse(
            items=[TaxPlanMessageResponse.model_validate(m) for m in messages],
            total=total,
            page=page,
            page_size=page_size,
        )
    except DomainError as e:
        raise _handle_domain_error(e)


# ------------------------------------------------------------------
# Xero change detection
# ------------------------------------------------------------------


@router.get("/{plan_id}/xero-changes")
async def check_xero_changes(
    plan_id: uuid.UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.CLIENT_READ)),
    service: TaxPlanningService = Depends(_get_service),
):
    """Check if Xero data has changed since the plan was last updated."""
    try:
        changes = await service.check_xero_changes(plan_id, current_user.tenant_id)
        return {"changes": changes}
    except DomainError as e:
        raise _handle_domain_error(e)


# ------------------------------------------------------------------
# Tax rates (admin/read-only)
# ------------------------------------------------------------------


@router.get(
    "/rates/{financial_year}",
    response_model=TaxRatesResponse,
    tags=["Tax Rates"],
)
async def get_tax_rates(
    financial_year: str,
    current_user: PracticeUser = Depends(require_permission(Permission.CLIENT_READ)),
    service: TaxPlanningService = Depends(_get_service),
):
    """Get all tax rate configurations for a financial year."""
    configs = await service.rate_repo.get_rates_for_year(financial_year)
    return TaxRatesResponse(
        financial_year=financial_year,
        rates=[TaxRateConfigResponse.model_validate(c) for c in configs],
    )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _plan_to_response(plan: TaxPlan, client_name: str) -> TaxPlanResponse:
    """Convert TaxPlan model to response schema."""
    scenarios = plan.scenarios or []
    return TaxPlanResponse(
        id=plan.id,
        tenant_id=plan.tenant_id,
        xero_connection_id=plan.xero_connection_id,
        client_name=client_name,
        financial_year=plan.financial_year,
        entity_type=plan.entity_type,
        status=plan.status,
        data_source=plan.data_source,
        financials_data=plan.financials_data,
        tax_position=plan.tax_position,
        notes=plan.notes,
        xero_report_fetched_at=plan.xero_report_fetched_at,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        scenarios=[TaxScenarioResponse.model_validate(s) for s in scenarios],
        scenario_count=len(scenarios),
        message_count=0,  # Messages loaded separately
    )
