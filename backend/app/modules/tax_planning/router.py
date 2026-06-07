"""API router for Tax Planning module.

All endpoints require authentication and extract tenant_id from current user.
Domain exceptions are caught and converted to HTTPException responses.
"""

import logging
import uuid

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.config import Settings, get_settings
from app.core.exceptions import DomainError
from app.database import get_db
from app.modules.auth.models import PracticeUser
from app.modules.auth.permissions import Permission, require_permission
from app.modules.billing.middleware import require_active_subscription
from app.modules.tax_planning.models import TaxPlan
from app.modules.tax_planning.schemas import (
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
    _sub: None = Depends(require_active_subscription),
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
        connection_status = await service.get_connection_status(plan.xero_connection_id)

        # Check if data is stale (read-only check, no Xero API calls)
        import contextlib

        data_stale = False
        with contextlib.suppress(Exception):
            data_stale = await service.is_plan_data_stale(plan)

        return _plan_to_response(plan, client_name, connection_status, data_stale)
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
    """Pull the latest P&L from Xero and populate the plan's financials.

    Spec 059.1 — when `as_at_date` is provided, persists it on the plan
    before the pull so refresh + anchor change happen in one call.
    """
    try:
        result = await service.pull_xero_financials(
            plan_id,
            current_user.tenant_id,
            data.force_refresh,
            as_at_date=data.as_at_date,
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
    message: str = Form(..., min_length=1, max_length=2000),
    file: UploadFile | None = File(None),
    current_user: PracticeUser = Depends(require_permission(Permission.CLIENT_WRITE)),
    service: TaxPlanningService = Depends(_get_service),
):
    """Send a message to the tax planning AI with optional file attachment."""
    try:
        result = await service.send_chat_message(
            plan_id,
            current_user.tenant_id,
            message,
            file=file,
        )
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
    message: str = Form(..., min_length=1, max_length=2000),
    file: UploadFile | None = File(None),
    current_user: PracticeUser = Depends(require_permission(Permission.CLIENT_WRITE)),
    service: TaxPlanningService = Depends(_get_service),
):
    """Send a message with streaming SSE response, with optional file attachment."""
    import json as json_lib

    from starlette.responses import StreamingResponse

    # Process file before entering the generator (UploadFile may close)
    attachment_data = None
    if file and file.filename:
        try:
            from app.modules.tax_planning.file_processor import process_chat_attachment

            attachment_data = await process_chat_attachment(
                file,
                current_user.tenant_id,
                "tax-planning",
                plan_id,
                f"msg-{uuid.uuid4().hex[:12]}",
            )
        except ValueError as e:
            return StreamingResponse(
                iter([f"data: {json_lib.dumps({'type': 'error', 'error': str(e)})}\n\n"]),
                media_type="text/event-stream",
            )

    async def generate_events():
        try:
            async for event in service.send_chat_message_streaming(
                plan_id,
                current_user.tenant_id,
                message,
                attachment=attachment_data,
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


@router.patch(
    "/{plan_id}/scenarios/{scenario_id}/assumptions/{field_path:path}",
)
async def confirm_scenario_field(
    plan_id: uuid.UUID,
    scenario_id: uuid.UUID,
    field_path: str,
    body: dict = Body(...),
    current_user: PracticeUser = Depends(require_permission(Permission.CLIENT_WRITE)),
    service: TaxPlanningService = Depends(_get_service),
):
    """Spec 059 FR-015 — confirm (or replace) an AI-estimated figure.

    Accepts a URL-encoded JSON Pointer (dotted or canonical) and a `value` in
    the request body. Flips the scenario's provenance tag at `field_path`
    from `estimated` to `confirmed` and updates the stored value.
    """
    try:
        value = body.get("value")
        return await service.confirm_scenario_field(
            plan_id=plan_id,
            tenant_id=current_user.tenant_id,
            scenario_id=scenario_id,
            field_path=field_path,
            new_value=value,
        )
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
# Analysis Pipeline (Spec 041)
# ------------------------------------------------------------------


@router.post("/{plan_id}/analysis/generate", status_code=202)
async def generate_analysis(
    plan_id: uuid.UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.CLIENT_WRITE)),
    service: TaxPlanningService = Depends(_get_service),
):
    """Trigger the multi-agent analysis pipeline. Returns immediately with a task ID."""
    from app.modules.tax_planning.exceptions import AnalysisInProgressError, NoFinancialsError
    from app.modules.tax_planning.models import AnalysisStatus
    from app.modules.tax_planning.repository import AnalysisRepository

    try:
        plan = await service.get_plan(plan_id, current_user.tenant_id)

        if not plan.financials_data:
            raise NoFinancialsError()

        # Check for existing in-progress analysis
        analysis_repo = AnalysisRepository(service.session)
        current = await analysis_repo.get_current_for_plan(plan_id, current_user.tenant_id)
        if current and current.status == AnalysisStatus.GENERATING.value:
            raise AnalysisInProgressError(plan_id)

        # Determine version number
        versions = await analysis_repo.list_versions(plan_id, current_user.tenant_id)
        next_version = max((v.version for v in versions), default=0) + 1

        # Unmark previous current
        if current:
            current.is_current = False
            await service.session.flush()

        # Create analysis record
        analysis = await analysis_repo.create(
            {
                "tenant_id": current_user.tenant_id,
                "tax_plan_id": plan_id,
                "version": next_version,
                "is_current": True,
                "status": AnalysisStatus.GENERATING.value,
                "generated_by": current_user.id,
            }
        )
        await service.session.commit()

        # Dispatch Celery task
        from app.tasks.tax_planning import run_analysis_pipeline

        task_result = run_analysis_pipeline.delay(
            plan_id=str(plan_id),
            tenant_id=str(current_user.tenant_id),
            user_id=str(current_user.id),
            analysis_id=str(analysis.id),
        )

        return {
            "task_id": task_result.id,
            "analysis_id": str(analysis.id),
            "version": next_version,
            "status": "generating",
            "message": "Tax plan analysis started",
        }
    except DomainError as e:
        raise _handle_domain_error(e)


@router.get("/{plan_id}/analysis/progress/{task_id}")
async def get_analysis_progress(
    plan_id: uuid.UUID,
    task_id: str,
    current_user: PracticeUser = Depends(require_permission(Permission.CLIENT_READ)),
):
    """Stream real-time progress of the pipeline via SSE."""
    import asyncio
    import json as json_lib

    from celery.result import AsyncResult
    from starlette.responses import StreamingResponse

    async def generate_events():
        result = AsyncResult(task_id)
        while True:
            if result.state == "PROGRESS":
                meta = result.info or {}
                yield f"data: {json_lib.dumps({'type': 'progress', **meta})}\n\n"
            elif result.state == "SUCCESS":
                data = result.result or {}
                yield f"data: {json_lib.dumps({'type': 'complete', 'analysis_id': data.get('analysis_id'), 'status': data.get('status')})}\n\n"
                return
            elif result.state == "FAILURE":
                yield f"data: {json_lib.dumps({'type': 'error', 'message': str(result.info), 'retryable': True})}\n\n"
                return
            elif result.state == "PENDING":
                yield f"data: {json_lib.dumps({'type': 'progress', 'stage': 'queued', 'stage_number': 0, 'total_stages': 5, 'message': 'Waiting to start...'})}\n\n"

            await asyncio.sleep(1)

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/{plan_id}/analysis")
async def get_analysis(
    plan_id: uuid.UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.CLIENT_READ)),
    service: TaxPlanningService = Depends(_get_service),
):
    """Get the current analysis for a plan."""
    from app.modules.tax_planning.exceptions import AnalysisNotFoundError
    from app.modules.tax_planning.repository import AnalysisRepository, ImplementationItemRepository

    try:
        analysis_repo = AnalysisRepository(service.session)
        analysis = await analysis_repo.get_current_for_plan(plan_id, current_user.tenant_id)
        if not analysis:
            raise AnalysisNotFoundError(plan_id)

        item_repo = ImplementationItemRepository(service.session)
        items = await item_repo.list_by_analysis(analysis.id, current_user.tenant_id)

        # Get previous versions for comparison
        versions = await analysis_repo.list_versions(plan_id, current_user.tenant_id)
        previous_versions = [
            {"version": v.version, "generated_at": str(v.created_at), "status": v.status}
            for v in versions
            if v.id != analysis.id
        ]

        # Spec 059 FR-013 — the analysis response now includes source-of-truth
        # financials alongside the AI-derived output so the UI can render
        # accountant-visible figures next to AI narrative without a second
        # API call.
        plan_for_financials = await service.get_plan(plan_id, current_user.tenant_id)
        financials_data_payload = plan_for_financials.financials_data or None
        projection_metadata = (
            financials_data_payload.get("projection_metadata") if financials_data_payload else None
        )

        return {
            "id": str(analysis.id),
            "version": analysis.version,
            "status": analysis.status,
            "client_profile": analysis.client_profile,
            "strategies_evaluated": analysis.strategies_evaluated,
            "recommended_scenarios": analysis.recommended_scenarios,
            "combined_strategy": analysis.combined_strategy,
            "accountant_brief": analysis.accountant_brief,
            "client_summary": analysis.client_summary,
            "review_result": analysis.review_result,
            "review_passed": analysis.review_passed,
            "financials_data": financials_data_payload,
            "projection_metadata": projection_metadata,
            "implementation_items": [
                {
                    "id": str(item.id),
                    "title": item.title,
                    "description": item.description,
                    "deadline": str(item.deadline) if item.deadline else None,
                    "estimated_saving": float(item.estimated_saving)
                    if item.estimated_saving
                    else None,
                    "risk_rating": item.risk_rating,
                    "status": item.status,
                    "client_visible": item.client_visible,
                    "completed_at": str(item.completed_at) if item.completed_at else None,
                }
                for item in items
            ],
            "generation_time_ms": analysis.generation_time_ms,
            "generated_at": str(analysis.created_at),
            "previous_versions": previous_versions,
        }
    except DomainError as e:
        raise _handle_domain_error(e)


@router.patch("/{plan_id}/analysis")
async def update_analysis(
    plan_id: uuid.UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.CLIENT_WRITE)),
    service: TaxPlanningService = Depends(_get_service),
    accountant_brief: str | None = None,
    client_summary: str | None = None,
    status: str | None = None,
):
    """Update the accountant brief, client summary, or status."""
    from app.modules.tax_planning.exceptions import AnalysisNotFoundError
    from app.modules.tax_planning.repository import AnalysisRepository

    try:
        analysis_repo = AnalysisRepository(service.session)
        analysis = await analysis_repo.get_current_for_plan(plan_id, current_user.tenant_id)
        if not analysis:
            raise AnalysisNotFoundError(plan_id)

        update_data: dict = {}
        if accountant_brief is not None:
            update_data["accountant_brief"] = accountant_brief
        if client_summary is not None:
            update_data["client_summary"] = client_summary
        if status is not None:
            update_data["status"] = status
            if status == "reviewed":
                update_data["reviewed_by"] = current_user.id

        if update_data:
            await analysis_repo.update(analysis, update_data)
            await service.session.commit()

        return {"status": analysis.status, "message": "Analysis updated"}
    except DomainError as e:
        raise _handle_domain_error(e)


@router.post("/{plan_id}/analysis/approve")
async def approve_analysis(
    plan_id: uuid.UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.CLIENT_WRITE)),
    service: TaxPlanningService = Depends(_get_service),
):
    """Approve the analysis for client sharing."""
    from app.modules.tax_planning.exceptions import AnalysisNotFoundError
    from app.modules.tax_planning.repository import AnalysisRepository

    try:
        analysis_repo = AnalysisRepository(service.session)
        analysis = await analysis_repo.get_current_for_plan(plan_id, current_user.tenant_id)
        if not analysis:
            raise AnalysisNotFoundError(plan_id)

        await analysis_repo.update(
            analysis,
            {
                "status": "approved",
                "reviewed_by": current_user.id,
            },
        )
        await service.session.commit()

        logger.info(
            "analysis.approved plan=%s user=%s tenant=%s",
            plan_id,
            current_user.id,
            current_user.tenant_id,
        )
        return {"status": "approved", "message": "Analysis approved. Ready to share with client."}
    except DomainError as e:
        raise _handle_domain_error(e)


@router.post("/{plan_id}/analysis/share")
async def share_analysis(
    plan_id: uuid.UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.CLIENT_WRITE)),
    service: TaxPlanningService = Depends(_get_service),
):
    """Share the approved analysis to the client portal."""
    from datetime import UTC, datetime

    from app.modules.tax_planning.exceptions import AnalysisNotApprovedError, AnalysisNotFoundError
    from app.modules.tax_planning.repository import AnalysisRepository

    try:
        analysis_repo = AnalysisRepository(service.session)
        analysis = await analysis_repo.get_current_for_plan(plan_id, current_user.tenant_id)
        if not analysis:
            raise AnalysisNotFoundError(plan_id)
        if analysis.status != "approved":
            raise AnalysisNotApprovedError()

        await analysis_repo.update(
            analysis,
            {
                "status": "shared",
                "shared_at": datetime.now(UTC),
            },
        )
        await service.session.commit()

        logger.info(
            "analysis.shared plan=%s user=%s tenant=%s",
            plan_id,
            current_user.id,
            current_user.tenant_id,
        )
        return {
            "status": "shared",
            "shared_at": str(analysis.shared_at),
            "message": "Analysis shared to client portal",
        }
    except DomainError as e:
        raise _handle_domain_error(e)


@router.get("/{plan_id}/analysis/export-pdf")
async def export_analysis_pdf(
    plan_id: uuid.UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.CLIENT_READ)),
    service: TaxPlanningService = Depends(_get_service),
):
    """Export the accountant brief as a PDF."""
    from starlette.responses import Response

    from app.modules.tax_planning.exceptions import AnalysisNotFoundError
    from app.modules.tax_planning.repository import AnalysisRepository

    try:
        analysis_repo = AnalysisRepository(service.session)
        analysis = await analysis_repo.get_current_for_plan(plan_id, current_user.tenant_id)
        if not analysis or not analysis.accountant_brief:
            raise AnalysisNotFoundError(plan_id)

        # Convert markdown to simple HTML for PDF
        import markdown

        html_content = markdown.markdown(
            analysis.accountant_brief,
            extensions=["tables", "fenced_code"],
        )

        from app.core.constants import AI_DISCLAIMER_TEXT

        # Wrap in basic HTML template
        html = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<style>
body {{ font-family: Arial, sans-serif; font-size: 11pt; line-height: 1.6; margin: 40px; }}
h1 {{ font-size: 18pt; color: #1a1a1a; }}
h2 {{ font-size: 14pt; color: #333; border-bottom: 1px solid #ddd; padding-bottom: 4px; }}
h3 {{ font-size: 12pt; color: #555; }}
table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
th, td {{ border: 1px solid #ddd; padding: 6px 10px; text-align: left; font-size: 10pt; }}
th {{ background-color: #f5f5f5; }}
.disclaimer {{ font-size: 9pt; color: #888; margin-top: 30px; border-top: 1px solid #ddd; padding-top: 10px; }}
</style>
</head><body>
{html_content}
<div class="disclaimer">
{AI_DISCLAIMER_TEXT}
</div>
</body></html>"""

        import weasyprint

        pdf_bytes = weasyprint.HTML(string=html).write_pdf()

        plan = await service.get_plan(plan_id, current_user.tenant_id)
        client_name = await service.get_client_name(plan.xero_connection_id, current_user.tenant_id)
        filename = (
            f"tax-plan-analysis-{client_name.lower().replace(' ', '-')}-{plan.financial_year}.pdf"
        )

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except DomainError as e:
        raise _handle_domain_error(e)


@router.patch("/{plan_id}/analysis/items/{item_id}")
async def update_implementation_item(
    plan_id: uuid.UUID,
    item_id: uuid.UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.CLIENT_WRITE)),
    service: TaxPlanningService = Depends(_get_service),
    status: str = "completed",
):
    """Update an implementation item status."""
    from app.modules.tax_planning.repository import ImplementationItemRepository

    item_repo = ImplementationItemRepository(service.session)
    item = await item_repo.update_status(
        item_id,
        current_user.tenant_id,
        status,
        completed_by="accountant",
    )
    if not item:
        raise HTTPException(status_code=404, detail="Implementation item not found")
    await service.session.commit()

    return {
        "id": str(item.id),
        "status": item.status,
        "completed_at": str(item.completed_at) if item.completed_at else None,
    }


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _plan_to_response(
    plan: TaxPlan,
    client_name: str,
    connection_status: str | None = None,
    data_stale: bool = False,
) -> TaxPlanResponse:
    """Convert TaxPlan model to response schema."""
    scenarios = plan.scenarios or []
    # Derive payroll_sync_status from financials_data.payroll_status (set at
    # ingest time by pull_xero_financials). Manual plans with no connection
    # surface "not_required"; plans without financials yet report None.
    payroll_sync_status: str | None = None
    if plan.financials_data:
        raw = plan.financials_data.get("payroll_status")
        if raw in {"ready", "pending", "unavailable", "not_required"}:
            payroll_sync_status = raw
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
        xero_connection_status=connection_status,
        data_stale=data_stale,
        payroll_sync_status=payroll_sync_status,  # type: ignore[arg-type]
        as_at_date=plan.as_at_date,
    )
