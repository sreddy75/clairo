"""API endpoints for BAS preparation workflow."""

from __future__ import annotations

import logging
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_practice_user, get_db
from app.modules.auth.models import PracticeUser
from app.modules.bas.classification_schemas import (
    ClassificationBulkApprove,
    ClassificationBulkApproveResponse,
    ClassificationRequestCreate,
    ClassificationRequestResponse,
    ClassificationRequestStatusResponse,
    ClassificationResolve,
    ClassificationResolveResponse,
    ClassificationReviewResponse,
)
from app.modules.bas.classification_service import ClassificationService
from app.modules.bas.exceptions import (
    ConcurrentModificationError,
    ExportNotAllowedError,
    LodgementAlreadyRecordedError,
    LodgementNotAllowedError,
    SessionNotFoundError,
    SplitAmountMismatchError,
    SplitOverrideNotFoundError,
)
from app.modules.bas.lodgement_service import LodgementService
from app.modules.bas.schemas import (
    ApproveSessionRequest,
    ApproveSuggestionRequest,
    BASAdjustmentCreate,
    BASAdjustmentListResponse,
    BASAdjustmentResponse,
    BASCalculateTriggerResponse,
    BASCalculationResponse,
    BASFieldTransactionsResponse,
    BASPeriodListResponse,
    BASPeriodResponse,
    BASSessionCreate,
    BASSessionListResponse,
    BASSessionResponse,
    BASSessionUpdate,
    BASSummaryResponse,
    BulkApproveRequest,
    BulkApproveResponse,
    ConflictListResponse,
    DismissSuggestionRequest,
    GenerateSuggestionsResponse,
    LodgementRecordRequest,
    LodgementSummaryResponse,
    LodgementUpdateRequest,
    LodgementWorkboardResponse,
    LodgementWorkboardSummaryResponse,
    OverrideSuggestionRequest,
    RecalculateResponse,
    RejectSuggestionRequest,
    ReopenSessionRequest,
    RequestChangesRequest,
    ResolveConflictRequest,
    ResolveConflictResponse,
    SplitCreateRequest,
    SplitUpdateRequest,
    SuggestionNoteRequest,
    SuggestionNoteResponse,
    SuggestionResolutionResponse,
    TaxCodeOverrideWithSplitResponse,
    TaxCodeSuggestionListResponse,
    TaxCodeSuggestionSummaryResponse,
    TransactionSplitsResponse,
    VarianceAnalysisResponse,
    XeroBASCrossCheckResponse,
    XeroLineItemView,
)
from app.modules.bas.service import BASService
from app.modules.bas.tax_code_service import TaxCodeService
from app.modules.bas.workboard_service import WorkboardService
from app.modules.billing.middleware import require_active_subscription
from app.modules.integrations.xero.repository import XeroConnectionRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clients", tags=["bas"])


async def verify_connection_access(
    connection_id: UUID,
    session: AsyncSession,
    user: PracticeUser,
) -> None:
    """Verify the user has access to the connection."""
    repo = XeroConnectionRepository(session)
    connection = await repo.get_by_id(connection_id)

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found",
        )

    if connection.tenant_id != user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )


# =============================================================================
# Period Endpoints
# =============================================================================


@router.get(
    "/{connection_id}/bas/periods",
    response_model=BASPeriodListResponse,
    summary="List BAS periods",
    description="List BAS periods for a client connection.",
)
async def list_periods(
    connection_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
    limit: int = Query(12, ge=1, le=24, description="Number of periods to return"),
) -> BASPeriodListResponse:
    """List BAS periods for a connection."""
    await verify_connection_access(connection_id, session, user)

    service = BASService(session)
    return await service.list_periods(connection_id, limit)


@router.post(
    "/{connection_id}/bas/periods",
    response_model=BASPeriodResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Get or create period",
    description="Get an existing period or create a new one.",
)
async def get_or_create_period(
    connection_id: UUID,
    request: BASSessionCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> BASPeriodResponse:
    """Get or create a BAS period."""
    await verify_connection_access(connection_id, session, user)

    service = BASService(session)
    return await service.get_or_create_period(
        connection_id=connection_id,
        quarter=request.quarter,
        fy_year=request.fy_year,
        tenant_id=user.tenant_id,
    )


# =============================================================================
# Session Endpoints
# =============================================================================


@router.post(
    "/{connection_id}/bas/sessions",
    response_model=BASSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create BAS session",
    description="Create a new BAS preparation session for a quarter.",
)
async def create_session(
    connection_id: UUID,
    request: BASSessionCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
    _sub: None = Depends(require_active_subscription),
) -> BASSessionResponse:
    """Create a new BAS session."""
    await verify_connection_access(connection_id, session, user)

    service = BASService(session)

    try:
        return await service.create_session(
            connection_id=connection_id,
            quarter=request.quarter,
            fy_year=request.fy_year,
            user_id=user.id,
            tenant_id=user.tenant_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get(
    "/{connection_id}/bas/sessions",
    response_model=BASSessionListResponse,
    summary="List BAS sessions",
    description="List BAS sessions for a client connection.",
)
async def list_sessions(
    connection_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
    limit: int = Query(20, ge=1, le=50, description="Number of sessions to return"),
    lodgement_status: Literal["all", "lodged", "not_lodged"] = Query(
        "all", description="Filter by lodgement status"
    ),
) -> BASSessionListResponse:
    """List BAS sessions for a connection."""
    await verify_connection_access(connection_id, session, user)

    service = BASService(session)
    return await service.list_sessions(connection_id, limit, lodgement_status)


@router.get(
    "/{connection_id}/bas/sessions/{session_id}",
    response_model=BASSessionResponse,
    summary="Get BAS session",
    description="Get details of a specific BAS session.",
)
async def get_session(
    connection_id: UUID,
    session_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> BASSessionResponse:
    """Get a BAS session by ID."""
    await verify_connection_access(connection_id, session, user)

    service = BASService(session)
    result = await service.get_session(session_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return result


@router.patch(
    "/{connection_id}/bas/sessions/{session_id}",
    response_model=BASSessionResponse,
    summary="Update BAS session",
    description="Update session status or notes.",
)
async def update_session(
    connection_id: UUID,
    session_id: UUID,
    request: BASSessionUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> BASSessionResponse:
    """Update a BAS session."""
    await verify_connection_access(connection_id, session, user)

    service = BASService(session)

    try:
        if request.status:
            return await service.update_session_status(
                session_id=session_id,
                new_status=request.status,
                user_id=user.id,
            )
        else:
            # Handle internal notes update if needed
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No update fields provided",
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post(
    "/{connection_id}/bas/sessions/{session_id}/review",
    response_model=BASSessionResponse,
    summary="Mark session as reviewed",
    description="Mark an auto-created BAS session as reviewed by an accountant.",
)
async def mark_session_reviewed(
    connection_id: UUID,
    session_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> BASSessionResponse:
    """Mark an auto-created BAS session as reviewed."""
    await verify_connection_access(connection_id, session, user)

    service = BASService(session)

    try:
        return await service.mark_session_reviewed(
            session_id=session_id,
            user_id=user.id,
            tenant_id=user.tenant_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


# =============================================================================
# Approval Workflow Endpoints (Spec 010)
# =============================================================================


@router.post(
    "/{connection_id}/bas/sessions/{session_id}/approve",
    response_model=BASSessionResponse,
    summary="Approve BAS session",
    description="Approve a BAS session that is ready for review.",
)
async def approve_session(
    connection_id: UUID,
    session_id: UUID,
    request: ApproveSessionRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> BASSessionResponse:
    """Approve a BAS session.

    The session must be in 'ready_for_review' status. Once approved,
    the session can proceed to lodgement.
    """
    await verify_connection_access(connection_id, session, user)

    service = BASService(session)

    try:
        return await service.update_session_status(
            session_id=session_id,
            new_status="approved",
            user_id=user.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post(
    "/{connection_id}/bas/sessions/{session_id}/request-changes",
    response_model=BASSessionResponse,
    summary="Request changes to BAS session",
    description="Send a BAS session back for changes with feedback.",
)
async def request_session_changes(
    connection_id: UUID,
    session_id: UUID,
    request: RequestChangesRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> BASSessionResponse:
    """Request changes to a BAS session.

    The session must be in 'ready_for_review' status. The feedback
    will be recorded and the session returned to 'in_progress' status.
    """
    await verify_connection_access(connection_id, session, user)

    service = BASService(session)

    try:
        # Update status back to in_progress
        result = await service.update_session_status(
            session_id=session_id,
            new_status="in_progress",
            user_id=user.id,
        )
        # Note: feedback could be stored in internal_notes or a dedicated field
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post(
    "/{connection_id}/bas/sessions/{session_id}/reopen",
    response_model=BASSessionResponse,
    summary="Reopen approved BAS session",
    description="Reopen an approved BAS session for further changes.",
)
async def reopen_session(
    connection_id: UUID,
    session_id: UUID,
    request: ReopenSessionRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> BASSessionResponse:
    """Reopen an approved BAS session.

    The session must be in 'approved' status. This returns it to
    'ready_for_review' status so it can be modified and re-approved.
    """
    await verify_connection_access(connection_id, session, user)

    service = BASService(session)

    try:
        return await service.update_session_status(
            session_id=session_id,
            new_status="ready_for_review",
            user_id=user.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


# =============================================================================
# Calculation Endpoints
# =============================================================================


@router.post(
    "/{connection_id}/bas/sessions/{session_id}/calculate",
    response_model=BASCalculateTriggerResponse,
    summary="Trigger BAS calculation",
    description="Calculate GST and PAYG figures for the session period.",
)
async def trigger_calculation(
    connection_id: UUID,
    session_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> BASCalculateTriggerResponse:
    """Trigger BAS calculation for a session."""
    await verify_connection_access(connection_id, session, user)

    service = BASService(session)

    try:
        return await service.calculate(
            session_id=session_id,
            tenant_id=user.tenant_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get(
    "/{connection_id}/bas/sessions/{session_id}/calculation",
    response_model=BASCalculationResponse,
    summary="Get BAS calculation",
    description="Get the current calculation results for a session.",
)
async def get_calculation(
    connection_id: UUID,
    session_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> BASCalculationResponse:
    """Get calculation for a session."""
    await verify_connection_access(connection_id, session, user)

    service = BASService(session)
    result = await service.get_calculation(session_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No calculation found for this session",
        )

    return result


# =============================================================================
# Adjustment Endpoints
# =============================================================================


@router.post(
    "/{connection_id}/bas/sessions/{session_id}/adjustments",
    response_model=BASAdjustmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add BAS adjustment",
    description="Add a manual adjustment to a BAS field.",
)
async def add_adjustment(
    connection_id: UUID,
    session_id: UUID,
    request: BASAdjustmentCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> BASAdjustmentResponse:
    """Add an adjustment to a session."""
    await verify_connection_access(connection_id, session, user)

    service = BASService(session)

    try:
        return await service.add_adjustment(
            session_id=session_id,
            field_name=request.field_name,
            adjustment_amount=request.adjustment_amount,
            reason=request.reason,
            reference=request.reference,
            user_id=user.id,
            tenant_id=user.tenant_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get(
    "/{connection_id}/bas/sessions/{session_id}/adjustments",
    response_model=BASAdjustmentListResponse,
    summary="List BAS adjustments",
    description="List adjustments for a BAS session.",
)
async def list_adjustments(
    connection_id: UUID,
    session_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> BASAdjustmentListResponse:
    """List adjustments for a session."""
    await verify_connection_access(connection_id, session, user)

    service = BASService(session)
    return await service.list_adjustments(session_id)


@router.delete(
    "/{connection_id}/bas/sessions/{session_id}/adjustments/{adjustment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete BAS adjustment",
    description="Delete an adjustment from a BAS session.",
)
async def delete_adjustment(
    connection_id: UUID,
    session_id: UUID,
    adjustment_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> None:
    """Delete an adjustment."""
    await verify_connection_access(connection_id, session, user)

    service = BASService(session)

    try:
        result = await service.delete_adjustment(adjustment_id, session_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Adjustment not found",
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


# =============================================================================
# Variance Analysis Endpoints
# =============================================================================


@router.get(
    "/{connection_id}/bas/sessions/{session_id}/variance",
    response_model=VarianceAnalysisResponse,
    summary="Get variance analysis",
    description="Get variance analysis comparing to prior periods.",
)
async def get_variance_analysis(
    connection_id: UUID,
    session_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> VarianceAnalysisResponse:
    """Get variance analysis for a session."""
    await verify_connection_access(connection_id, session, user)

    service = BASService(session)

    try:
        return await service.get_variance_analysis(session_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


# =============================================================================
# Summary Endpoints
# =============================================================================


@router.get(
    "/{connection_id}/bas/sessions/{session_id}/summary",
    response_model=BASSummaryResponse,
    summary="Get BAS summary",
    description="Get complete BAS summary for review and approval.",
)
async def get_summary(
    connection_id: UUID,
    session_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> BASSummaryResponse:
    """Get BAS summary for review."""
    await verify_connection_access(connection_id, session, user)

    service = BASService(session)

    try:
        return await service.get_summary(session_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


# =============================================================================
# A2UI Review Endpoints
# =============================================================================


@router.get(
    "/{connection_id}/bas/sessions/{session_id}/review/ui",
    summary="Get BAS review with A2UI",
    description="Get BAS review interface with exception focus using A2UI components.",
)
async def get_review_ui(
    connection_id: UUID,
    session_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
    is_mobile: bool = False,
    is_tablet: bool = False,
) -> dict:
    """
    Get BAS review with A2UI components.

    Returns an A2UI message with:
    - Summary stat cards for key BAS totals
    - Exception alerts (expanded) for fields with significant variances
    - Variance trend chart
    - Field breakdown accordion (normal fields collapsed)
    - Action buttons for review workflow

    This endpoint provides an exception-focused review experience where
    anomalies are prominently displayed while normal fields are minimized.
    """
    from app.core.a2ui import DeviceContext
    from app.modules.bas.a2ui_generator import generate_bas_review_ui

    await verify_connection_access(connection_id, session, user)

    service = BASService(session)

    # Get calculation and variance data
    try:
        calculation_response = await service.get_calculation(session_id)
        if not calculation_response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No calculation found for this session",
            )

        # Convert calculation response to dict
        calculation = {
            "1A": calculation_response.gst_on_sales,
            "1B": calculation_response.gst_on_purchases,
            "8A": calculation_response.total_sales,
            "8B": calculation_response.export_sales,
            "9": calculation_response.net_gst,
            "W1": calculation_response.payg_withheld,
            "W2": calculation_response.payg_amount_withheld,
            "7C": calculation_response.fuel_tax_credits,
            "7D": calculation_response.fuel_tax_adjustments,
        }

        # Try to get variance analysis
        variance_analysis = None
        try:
            variance_response = await service.get_variance_analysis(session_id)
            if variance_response:
                variance_analysis = {
                    "historical_data": [
                        {
                            "period": v.period,
                            "gst_collected": v.gst_collected,
                            "gst_paid": v.gst_paid,
                            "net_gst": v.net_gst,
                        }
                        for v in (variance_response.quarterly_comparison or [])
                    ]
                }
        except ValueError:
            pass  # No variance data available

        # Get prior period data if available
        prior_period = None
        if variance_response and variance_response.prior_period:
            prior_period = {
                "1A": variance_response.prior_period.gst_on_sales,
                "1B": variance_response.prior_period.gst_on_purchases,
                "9": variance_response.prior_period.net_gst,
                "W1": variance_response.prior_period.payg_withheld,
            }

        # Generate A2UI
        device_context = DeviceContext(
            isMobile=is_mobile,
            isTablet=is_tablet,
        )

        a2ui_message = generate_bas_review_ui(
            session_id=session_id,
            calculation=calculation,
            variance_analysis=variance_analysis,
            prior_period=prior_period,
            device_context=device_context,
        )

        return {
            "session_id": str(session_id),
            "a2ui_message": a2ui_message.model_dump(by_alias=True),
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


# =============================================================================
# Export Endpoints
# =============================================================================


@router.get(
    "/{connection_id}/bas/sessions/{session_id}/export",
    summary="Export BAS working papers",
    description="Export BAS working papers as PDF, Excel, or CSV.",
)
async def export_working_papers(
    connection_id: UUID,
    session_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
    format: Literal["pdf", "excel", "csv"] = Query("pdf", description="Export format"),
    include_lodgement_summary: bool = Query(
        True, description="Include ATO-compliant lodgement summary"
    ),
) -> Response:
    """Export BAS working papers.

    Supported formats:
    - pdf: PDF with optional lodgement summary section
    - excel: Excel with optional Lodgement Summary sheet
    - csv: CSV file for data transfer (lodgement summary format only)

    Lodgement exports require the BAS to be in 'approved' or 'lodged' status.
    """
    await verify_connection_access(connection_id, session, user)

    service = BASService(session)

    try:
        file_bytes, filename, content_type = await service.export_working_papers(
            session_id=session_id,
            export_format=format,
            include_lodgement_summary=include_lodgement_summary,
            user_id=user.id,
        )

        return Response(
            content=file_bytes,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    except ExportNotAllowedError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e.message),
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


# =============================================================================
# Lodgement Endpoints (Spec 011)
# =============================================================================


@router.post(
    "/{connection_id}/bas/sessions/{session_id}/lodgement",
    response_model=BASSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record BAS lodgement",
    description="Record that a BAS has been lodged with the ATO.",
)
async def record_lodgement(
    connection_id: UUID,
    session_id: UUID,
    request: LodgementRecordRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> BASSessionResponse:
    """Record lodgement for an approved BAS session.

    The session must be in 'approved' status. Once recorded, the
    lodgement date and method cannot be changed, but the ATO reference
    number and notes can be updated via PATCH.
    """
    await verify_connection_access(connection_id, session, user)

    lodgement_service = LodgementService(session)

    try:
        return await lodgement_service.record_lodgement(
            session_id=session_id,
            lodged_by=user.id,
            tenant_id=user.tenant_id,
            request=request,
        )
    except SessionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
        ) from e
    except LodgementNotAllowedError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        ) from e
    except LodgementAlreadyRecordedError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.message,
        ) from e
    except ConcurrentModificationError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.message,
        ) from e


@router.patch(
    "/{connection_id}/bas/sessions/{session_id}/lodgement",
    response_model=BASSessionResponse,
    summary="Update lodgement details",
    description="Update ATO reference number or notes after lodgement.",
)
async def update_lodgement(
    connection_id: UUID,
    session_id: UUID,
    request: LodgementUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> BASSessionResponse:
    """Update lodgement details.

    Only the ATO reference number and lodgement notes can be updated
    after the initial lodgement is recorded. The lodgement date and
    method cannot be changed.
    """
    await verify_connection_access(connection_id, session, user)

    lodgement_service = LodgementService(session)

    try:
        return await lodgement_service.update_lodgement_details(
            session_id=session_id,
            user_id=user.id,
            tenant_id=user.tenant_id,
            request=request,
        )
    except SessionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
        ) from e
    except LodgementNotAllowedError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        ) from e


@router.get(
    "/{connection_id}/bas/sessions/{session_id}/lodgement",
    response_model=LodgementSummaryResponse,
    summary="Get lodgement summary",
    description="Get lodgement status and details for a BAS session.",
)
async def get_lodgement_summary(
    connection_id: UUID,
    session_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> LodgementSummaryResponse:
    """Get lodgement summary for a session."""
    await verify_connection_access(connection_id, session, user)

    lodgement_service = LodgementService(session)

    try:
        return await lodgement_service.get_lodgement_summary(
            session_id=session_id,
            tenant_id=user.tenant_id,
        )
    except SessionNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
        ) from e


# =============================================================================
# Field Transaction Drilldown Endpoints
# =============================================================================


@router.get(
    "/{connection_id}/bas/sessions/{session_id}/transactions/{field_name}",
    response_model=BASFieldTransactionsResponse,
    summary="Get transactions for BAS field",
    description="Get the invoices and transactions that contribute to a specific BAS field.",
)
async def get_field_transactions(
    connection_id: UUID,
    session_id: UUID,
    field_name: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> BASFieldTransactionsResponse:
    """Get transactions that contribute to a specific BAS field."""
    await verify_connection_access(connection_id, session, user)

    service = BASService(session)

    try:
        return await service.get_field_transactions(
            session_id=session_id,
            field_name=field_name,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


# =============================================================================
# Lodgement Workboard Endpoints (Spec 011 - User Story 8)
# =============================================================================

# Create a separate router for workboard endpoints (no connection_id prefix)
workboard_router = APIRouter(prefix="/bas", tags=["bas-workboard"])


@workboard_router.get(
    "/workboard",
    response_model=LodgementWorkboardResponse,
    summary="Get lodgement workboard",
    description="Get aggregated BAS periods across all clients with deadline information.",
)
async def get_lodgement_workboard(
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
    status_filter: Literal["all", "overdue", "due_this_week", "upcoming", "lodged"] = Query(
        "all", alias="status", description="Filter by deadline status"
    ),
    urgency: Literal["all", "overdue", "critical", "warning", "normal"] = Query(
        "all", description="Filter by urgency level"
    ),
    quarter: Literal["all", "Q1", "Q2", "Q3", "Q4"] = Query("all", description="Filter by quarter"),
    financial_year: str | None = Query(
        None, alias="fy", description="Filter by financial year (e.g., '2024-25')"
    ),
    search: str | None = Query(None, max_length=100, description="Search by client name"),
    sort_by: Literal["due_date", "client_name", "status", "days_remaining"] = Query(
        "due_date", description="Sort field"
    ),
    sort_order: Literal["asc", "desc"] = Query("asc", description="Sort direction"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
) -> LodgementWorkboardResponse:
    """Get lodgement workboard data.

    Returns all BAS periods across all clients with deadline information,
    session status, and lodgement status. Useful for accountants managing
    many clients to see at a glance which BAS lodgements need attention.
    """
    service = WorkboardService(session)

    return await service.get_workboard(
        tenant_id=user.tenant_id,
        status_filter=status_filter,
        urgency_filter=urgency,
        quarter_filter=quarter,
        financial_year=financial_year,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        limit=limit,
    )


@workboard_router.get(
    "/workboard/summary",
    response_model=LodgementWorkboardSummaryResponse,
    summary="Get workboard summary",
    description="Get summary statistics for the lodgement workboard.",
)
async def get_workboard_summary(
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> LodgementWorkboardSummaryResponse:
    """Get workboard summary statistics.

    Returns counts of overdue, due this week, due this month, lodged,
    and not started BAS periods across all clients.
    """
    service = WorkboardService(session)

    return await service.get_workboard_summary(tenant_id=user.tenant_id)


# =============================================================================
# Tax Code Suggestion Endpoints (Spec 046)
# =============================================================================


@router.get(
    "/{connection_id}/bas/sessions/{session_id}/tax-code-suggestions/summary",
    response_model=TaxCodeSuggestionSummaryResponse,
    summary="Get tax code suggestion summary",
)
async def get_suggestion_summary(
    connection_id: UUID,
    session_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> TaxCodeSuggestionSummaryResponse:
    """Get summary of excluded transactions for the BAS exclusion banner."""
    await verify_connection_access(connection_id, session, user)
    service = TaxCodeService(session)
    summary = await service.get_summary(session_id, user.tenant_id)
    return TaxCodeSuggestionSummaryResponse(**summary)


@router.get(
    "/{connection_id}/bas/sessions/{session_id}/tax-code-suggestions",
    response_model=TaxCodeSuggestionListResponse,
    summary="List tax code suggestions",
)
async def list_suggestions(
    connection_id: UUID,
    session_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
    status_filter: str | None = Query(None, alias="status"),
    confidence_tier: str | None = Query(None),
    min_confidence: float | None = Query(None, ge=0, le=1),
) -> TaxCodeSuggestionListResponse:
    """List all tax code suggestions for a BAS session."""
    await verify_connection_access(connection_id, session, user)
    service = TaxCodeService(session)

    from app.modules.bas.repository import BASRepository

    repo = BASRepository(session)

    suggestions = await repo.list_suggestions(
        session_id, user.tenant_id, status_filter, confidence_tier, min_confidence
    )
    summary = await service.get_summary(session_id, user.tenant_id)

    return TaxCodeSuggestionListResponse(
        suggestions=suggestions,
        summary=TaxCodeSuggestionSummaryResponse(**summary),
    )


@router.post(
    "/{connection_id}/bas/sessions/{session_id}/tax-code-suggestions/generate",
    response_model=GenerateSuggestionsResponse,
    summary="Generate tax code suggestions",
)
async def generate_suggestions(
    connection_id: UUID,
    session_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> GenerateSuggestionsResponse:
    """Detect excluded transactions and generate AI tax code suggestions."""
    await verify_connection_access(connection_id, session, user)
    service = TaxCodeService(session)
    result = await service.detect_and_generate(session_id, user.tenant_id)
    return GenerateSuggestionsResponse(**result)


@router.post(
    "/{connection_id}/bas/sessions/{session_id}/tax-code-suggestions/{suggestion_id}/approve",
    response_model=SuggestionResolutionResponse,
    summary="Approve a tax code suggestion",
)
async def approve_suggestion(
    connection_id: UUID,
    session_id: UUID,
    suggestion_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
    body: ApproveSuggestionRequest | None = None,
) -> SuggestionResolutionResponse:
    """Approve a suggestion — apply the suggested tax code."""
    await verify_connection_access(connection_id, session, user)
    service = TaxCodeService(session)
    suggestion = await service.approve_suggestion(
        suggestion_id, user.tenant_id, user.id, body.notes if body else None
    )
    return SuggestionResolutionResponse.model_validate(suggestion)


@router.post(
    "/{connection_id}/bas/sessions/{session_id}/tax-code-suggestions/{suggestion_id}/reject",
    response_model=SuggestionResolutionResponse,
    summary="Reject a tax code suggestion",
)
async def reject_suggestion(
    connection_id: UUID,
    session_id: UUID,
    suggestion_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
    body: RejectSuggestionRequest | None = None,
) -> SuggestionResolutionResponse:
    """Reject a suggestion — transaction remains excluded from BAS."""
    await verify_connection_access(connection_id, session, user)
    service = TaxCodeService(session)
    suggestion = await service.reject_suggestion(
        suggestion_id, user.tenant_id, user.id, body.reason if body else None
    )
    return SuggestionResolutionResponse.model_validate(suggestion)


@router.post(
    "/{connection_id}/bas/sessions/{session_id}/tax-code-suggestions/{suggestion_id}/override",
    response_model=SuggestionResolutionResponse,
    summary="Override a suggestion with different tax code",
)
async def override_suggestion(
    connection_id: UUID,
    session_id: UUID,
    suggestion_id: UUID,
    body: OverrideSuggestionRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> SuggestionResolutionResponse:
    """Override a suggestion — apply a different tax code than suggested."""
    await verify_connection_access(connection_id, session, user)
    service = TaxCodeService(session)
    suggestion = await service.override_suggestion(
        suggestion_id, user.tenant_id, user.id, body.tax_type, body.reason
    )
    return SuggestionResolutionResponse.model_validate(suggestion)


@router.post(
    "/{connection_id}/bas/sessions/{session_id}/tax-code-suggestions/{suggestion_id}/dismiss",
    response_model=SuggestionResolutionResponse,
    summary="Dismiss — confirm exclusion is correct",
)
async def dismiss_suggestion(
    connection_id: UUID,
    session_id: UUID,
    suggestion_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
    body: DismissSuggestionRequest | None = None,
) -> SuggestionResolutionResponse:
    """Dismiss a transaction — confirm it should remain excluded from BAS."""
    await verify_connection_access(connection_id, session, user)
    service = TaxCodeService(session)
    suggestion = await service.dismiss_suggestion(
        suggestion_id, user.tenant_id, user.id, body.reason if body else None
    )
    return SuggestionResolutionResponse.model_validate(suggestion)


@router.post(
    "/{connection_id}/bas/sessions/{session_id}/tax-code-suggestions/{suggestion_id}/unpark",
    response_model=SuggestionResolutionResponse,
    summary="Unpark — return suggestion to Manual Required",
)
async def unpark_suggestion(
    connection_id: UUID,
    session_id: UUID,
    suggestion_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> SuggestionResolutionResponse:
    """Reset a parked (dismissed) suggestion back to pending for manual review."""
    await verify_connection_access(connection_id, session, user)
    service = TaxCodeService(session)
    suggestion = await service.unpark_suggestion(suggestion_id, user.tenant_id, user.id)
    return SuggestionResolutionResponse.model_validate(suggestion)


@router.put(
    "/{connection_id}/bas/sessions/{session_id}/tax-code-suggestions/{suggestion_id}/note",
    response_model=SuggestionNoteResponse,
    summary="Save or update a note on a suggestion",
)
async def save_suggestion_note(
    connection_id: UUID,
    session_id: UUID,
    suggestion_id: UUID,
    body: SuggestionNoteRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> SuggestionNoteResponse:
    """Save or update a free-text note on a tax code suggestion."""
    await verify_connection_access(connection_id, session, user)
    service = TaxCodeService(session)
    suggestion = await service.save_note(
        suggestion_id, user.tenant_id, user.id, body.note_text, body.sync_to_xero,
        connection_id=connection_id,
    )
    return SuggestionNoteResponse(
        suggestion_id=suggestion.id,
        note_text=suggestion.note_text or "",
        note_updated_by=suggestion.note_updated_by,
        note_updated_by_name=(
            suggestion.note_updated_by_user.user.email
            if suggestion.note_updated_by_user
            else None
        ),
        note_updated_at=suggestion.note_updated_at,
    )


@router.delete(
    "/{connection_id}/bas/sessions/{session_id}/tax-code-suggestions/{suggestion_id}/note",
    status_code=204,
    summary="Delete a note from a suggestion",
)
async def delete_suggestion_note(
    connection_id: UUID,
    session_id: UUID,
    suggestion_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> None:
    """Remove a note from a tax code suggestion."""
    await verify_connection_access(connection_id, session, user)
    service = TaxCodeService(session)
    await service.delete_note(suggestion_id, user.tenant_id, user.id)


@router.get(
    "/{connection_id}/bas/sessions/{session_id}/xero-crosscheck",
    response_model=XeroBASCrossCheckResponse,
    summary="Xero BAS cross-check — compare figures",
)
async def xero_bas_crosscheck(
    connection_id: UUID,
    session_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> XeroBASCrossCheckResponse:
    """Fetch BAS report from Xero and compare key figures with Clairo's calculation."""
    await verify_connection_access(connection_id, session, user)
    service = TaxCodeService(session)
    result = await service.get_xero_bas_crosscheck(session_id, connection_id, user.tenant_id)
    return XeroBASCrossCheckResponse(**result)


@router.post(
    "/{connection_id}/bas/sessions/{session_id}/tax-code-suggestions/bulk-approve",
    response_model=BulkApproveResponse,
    summary="Bulk approve high-confidence suggestions",
)
async def bulk_approve_suggestions(
    connection_id: UUID,
    session_id: UUID,
    body: BulkApproveRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> BulkApproveResponse:
    """Approve all pending suggestions matching confidence criteria."""
    await verify_connection_access(connection_id, session, user)
    service = TaxCodeService(session)
    result = await service.bulk_approve(
        session_id,
        user.tenant_id,
        user.id,
        float(body.min_confidence) if body.min_confidence else None,
        body.confidence_tier,
    )
    return BulkApproveResponse(**result)


@router.post(
    "/{connection_id}/bas/sessions/{session_id}/tax-code-suggestions/recalculate",
    response_model=RecalculateResponse,
    summary="Apply resolved suggestions and recalculate BAS",
)
async def recalculate_with_suggestions(
    connection_id: UUID,
    session_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> RecalculateResponse:
    """Apply all approved/overridden tax codes and recalculate BAS figures."""
    await verify_connection_access(connection_id, session, user)
    service = TaxCodeService(session)
    result = await service.apply_and_recalculate(session_id, user.tenant_id, user.id)
    return RecalculateResponse(**result)


@router.get(
    "/{connection_id}/bas/sessions/{session_id}/tax-code-suggestions/conflicts",
    response_model=ConflictListResponse,
    summary="List re-sync conflicts",
)
async def list_conflicts(
    connection_id: UUID,
    session_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> ConflictListResponse:
    """List active conflicts where Xero data changed after local override."""
    await verify_connection_access(connection_id, session, user)
    service = TaxCodeService(session)
    result = await service.get_conflicts(connection_id, user.tenant_id)
    return ConflictListResponse(**result)


@router.post(
    "/{connection_id}/bas/sessions/{session_id}/tax-code-suggestions/conflicts/{override_id}/resolve",
    response_model=ResolveConflictResponse,
    summary="Resolve a re-sync conflict",
)
async def resolve_conflict(
    connection_id: UUID,
    session_id: UUID,
    override_id: UUID,
    body: ResolveConflictRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> ResolveConflictResponse:
    """Resolve a conflict by keeping the override or accepting Xero's new value."""
    await verify_connection_access(connection_id, session, user)
    service = TaxCodeService(session)
    result = await service.resolve_conflict(
        override_id, user.tenant_id, user.id, body.resolution, body.reason
    )
    return ResolveConflictResponse(**result)


# =============================================================================
# Client Classification Endpoints (Spec 047)
# =============================================================================


@router.post(
    "/{connection_id}/bas/sessions/{session_id}/classification/request",
    response_model=ClassificationRequestResponse,
    summary="Create a classification request for client",
    status_code=201,
)
async def create_classification_request(
    connection_id: UUID,
    session_id: UUID,
    body: ClassificationRequestCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
    _sub: None = Depends(require_active_subscription),
) -> ClassificationRequestResponse:
    """Create a classification request and send magic link to the client."""
    await verify_connection_access(connection_id, session, user)
    service = ClassificationService(session)
    result = await service.create_request(
        session_id=session_id,
        tenant_id=user.tenant_id,
        user_id=user.id,
        connection_id=connection_id,
        message=body.message,
        transaction_ids=body.transaction_ids,
        email_override=body.email_override,
        manual_receipt_flags=[f.model_dump() for f in body.manual_receipt_flags]
        if body.manual_receipt_flags
        else None,
    )
    return ClassificationRequestResponse(**result)


@router.get(
    "/{connection_id}/bas/sessions/{session_id}/classification/request",
    response_model=ClassificationRequestStatusResponse,
    summary="Get classification request status",
)
async def get_classification_request_status(
    connection_id: UUID,
    session_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> ClassificationRequestStatusResponse:
    """Get the current status of a classification request."""
    await verify_connection_access(connection_id, session, user)
    service = ClassificationService(session)
    result = await service.get_request_status(session_id, user.tenant_id)
    return ClassificationRequestStatusResponse(**result)


@router.post(
    "/{connection_id}/bas/sessions/{session_id}/classification/request/cancel",
    summary="Cancel a classification request",
)
async def cancel_classification_request(
    connection_id: UUID,
    session_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> dict:
    """Cancel an active classification request."""
    await verify_connection_access(connection_id, session, user)
    service = ClassificationService(session)
    return await service.cancel_request(session_id, user.tenant_id, user.id)


@router.get(
    "/{connection_id}/bas/sessions/{session_id}/classification/review",
    response_model=ClassificationReviewResponse,
    summary="Get classifications for review",
)
async def get_classification_review(
    connection_id: UUID,
    session_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
    filter: str = "all",
) -> ClassificationReviewResponse:
    """Get all client classifications with AI mappings for accountant review."""
    await verify_connection_access(connection_id, session, user)
    service = ClassificationService(session)
    result = await service.get_review(session_id, user.tenant_id, filter)
    return ClassificationReviewResponse(**result)


@router.post(
    "/{connection_id}/bas/sessions/{session_id}/classification/{classification_id}/resolve",
    response_model=ClassificationResolveResponse,
    summary="Resolve a classification",
)
async def resolve_classification(
    connection_id: UUID,
    session_id: UUID,
    classification_id: UUID,
    body: ClassificationResolve,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> ClassificationResolveResponse:
    """Approve, override, or reject a client classification."""
    await verify_connection_access(connection_id, session, user)
    service = ClassificationService(session)
    result = await service.resolve_classification(
        classification_id,
        user.tenant_id,
        user.id,
        body.action,
        body.tax_type,
        body.reason,
    )
    return ClassificationResolveResponse(**result)


@router.post(
    "/{connection_id}/bas/sessions/{session_id}/classification/bulk-approve",
    response_model=ClassificationBulkApproveResponse,
    summary="Bulk approve classifications",
)
async def bulk_approve_classifications(
    connection_id: UUID,
    session_id: UUID,
    body: ClassificationBulkApprove,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> ClassificationBulkApproveResponse:
    """Bulk approve classifications above a confidence threshold."""
    await verify_connection_access(connection_id, session, user)
    service = ClassificationService(session)
    # Need to get request_id from session_id
    request = await service.repo.get_classification_request_by_session(session_id)
    if not request:
        raise HTTPException(status_code=404, detail="No classification request for this session")
    result = await service.bulk_approve(
        request.id,
        user.tenant_id,
        user.id,
        body.min_confidence,
        body.exclude_personal,
        body.exclude_needs_help,
    )
    return ClassificationBulkApproveResponse(**result)


@router.get(
    "/{connection_id}/bas/sessions/{session_id}/classification/audit-export",
    summary="Export classification audit trail",
)
async def export_classification_audit(
    connection_id: UUID,
    session_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
    format: str = "json",
) -> Response:
    """Export the full audit trail for client classifications."""
    await verify_connection_access(connection_id, session, user)
    service = ClassificationService(session)
    rows = await service.export_audit_trail(session_id, user.tenant_id, format)

    if format == "csv":
        import csv
        import io

        output = io.StringIO()
        if rows:
            writer = csv.DictWriter(output, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=classification-audit-{session_id}.csv"
            },
        )

    return Response(
        content=__import__("json").dumps(rows, default=str),
        media_type="application/json",
    )


# =============================================================================
# Write-Back Endpoints (Spec 049)
# =============================================================================


@router.post(
    "/{connection_id}/bas/sessions/{session_id}/writeback",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger Xero tax code write-back for a BAS session",
)
async def trigger_writeback(
    connection_id: UUID,
    session_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
):
    """Trigger write-back of all approved, unsynced tax code overrides to Xero.

    Returns a 202 with the created job record. The actual Xero API calls
    happen asynchronously via Celery.
    """
    from app.modules.integrations.xero.exceptions import WritebackError
    from app.modules.integrations.xero.writeback_schemas import WritebackJobResponse
    from app.modules.integrations.xero.writeback_service import XeroWritebackService

    await verify_connection_access(connection_id, session, user)
    service = XeroWritebackService(session)

    try:
        job = await service.initiate_writeback(
            session_id=session_id,
            triggered_by=user.id,
            tenant_id=user.tenant_id,
        )
        await session.commit()
        return WritebackJobResponse.model_validate(job)
    except WritebackError as e:
        if e.code == "job_in_progress":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/{connection_id}/bas/sessions/{session_id}/writeback/jobs",
    summary="List write-back jobs for a BAS session",
)
async def list_writeback_jobs(
    connection_id: UUID,
    session_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
):
    """List all write-back jobs for a BAS session, newest first."""
    from app.modules.integrations.xero.writeback_repository import XeroWritebackRepository
    from app.modules.integrations.xero.writeback_schemas import WritebackJobResponse

    await verify_connection_access(connection_id, session, user)
    repo = XeroWritebackRepository(session)
    jobs = await repo.list_jobs_for_session(session_id, user.tenant_id)
    return [WritebackJobResponse.model_validate(j) for j in jobs]


@router.get(
    "/{connection_id}/bas/sessions/{session_id}/writeback/jobs/{job_id}",
    summary="Get write-back job detail with items",
)
async def get_writeback_job(
    connection_id: UUID,
    session_id: UUID,
    job_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
):
    """Get write-back job detail including all items."""
    from uuid import UUID as _UUID

    from sqlalchemy import select

    from app.modules.bas.models import TaxCodeSuggestion
    from app.modules.integrations.xero.exceptions import WritebackJobNotFoundError
    from app.modules.integrations.xero.writeback_schemas import (
        WritebackJobDetailResponse,
        WritebackTransactionContext,
    )
    from app.modules.integrations.xero.writeback_service import XeroWritebackService

    await verify_connection_access(connection_id, session, user)
    service = XeroWritebackService(session)

    try:
        job = await service.get_job(job_id, user.tenant_id)
    except WritebackJobNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    # Build response base
    response = WritebackJobDetailResponse.model_validate(job)

    # Enrich items with transaction context from TaxCodeSuggestion
    if job.items:
        local_doc_ids = [item.local_document_id for item in job.items]
        rows = (
            await session.execute(
                select(
                    TaxCodeSuggestion.source_id,
                    TaxCodeSuggestion.contact_name,
                    TaxCodeSuggestion.transaction_date,
                    TaxCodeSuggestion.description,
                    TaxCodeSuggestion.line_amount,
                ).where(
                    TaxCodeSuggestion.source_id.in_(local_doc_ids),
                    TaxCodeSuggestion.tenant_id == user.tenant_id,
                )
            )
        ).all()

        # Aggregate per document: first contact/date/description, sum line amounts
        ctx_by_doc: dict[_UUID, dict] = {}
        for row in rows:
            doc_id = row.source_id
            if doc_id not in ctx_by_doc:
                ctx_by_doc[doc_id] = {
                    "contact_name": row.contact_name,
                    "transaction_date": row.transaction_date,
                    "description": row.description,
                    "total_line_amount": float(row.line_amount)
                    if row.line_amount is not None
                    else None,
                }
            else:
                if row.line_amount is not None:
                    prev = ctx_by_doc[doc_id]["total_line_amount"]
                    ctx_by_doc[doc_id]["total_line_amount"] = (prev or 0.0) + float(row.line_amount)

        for item_resp in response.items:
            ctx = ctx_by_doc.get(item_resp.local_document_id)
            if ctx:
                item_resp.transaction_context = WritebackTransactionContext(**ctx)

    return response


@router.post(
    "/{connection_id}/bas/sessions/{session_id}/writeback/jobs/{job_id}/retry",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Retry failed items from a write-back job",
)
async def retry_writeback_job(
    connection_id: UUID,
    session_id: UUID,
    job_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
):
    """Create a new write-back job retrying only failed items from the given job."""
    from app.modules.integrations.xero.exceptions import WritebackError, WritebackJobNotFoundError
    from app.modules.integrations.xero.writeback_schemas import WritebackJobResponse
    from app.modules.integrations.xero.writeback_service import XeroWritebackService

    await verify_connection_access(connection_id, session, user)
    service = XeroWritebackService(session)

    try:
        job = await service.retry_failed_items(
            job_id=job_id,
            triggered_by=user.id,
            tenant_id=user.tenant_id,
        )
        await session.commit()
        return WritebackJobResponse.model_validate(job)
    except WritebackJobNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except WritebackError as e:
        if e.code == "job_in_progress":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


# =============================================================================
# Classification Send-Back Endpoints (Spec 049)
# =============================================================================


@router.post(
    "/{connection_id}/bas/sessions/{session_id}/classification-requests/{request_id}/send-back",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Send IDK items back to client with agent guidance",
)
async def send_back_classifications(
    connection_id: UUID,
    session_id: UUID,
    request_id: UUID,
    body: SendBackRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
):
    """Send selected IDK classification items back to the client with agent comments."""
    from app.modules.bas.classification_schemas import SendBackResponse
    from app.modules.bas.exceptions import ClassificationValidationError

    await verify_connection_access(connection_id, session, user)
    service = ClassificationService(session)

    try:
        result = await service.send_items_back(
            request_id=request_id,
            items_with_comments=[
                {"classification_id": item.classification_id, "agent_comment": item.agent_comment}
                for item in body.items
            ],
            triggered_by=user.id,
            tenant_id=user.tenant_id,
        )
        await session.commit()
        return SendBackResponse(**result)
    except ClassificationValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/{connection_id}/bas/sessions/{session_id}/classification-requests/{request_id}/notes",
    summary="List agent notes for a classification request",
)
async def list_agent_notes(
    connection_id: UUID,
    session_id: UUID,
    request_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
):
    """List all agent transaction notes for a classification request."""
    from app.modules.bas.classification_schemas import AgentNoteResponse
    from app.modules.bas.repository import BASRepository

    await verify_connection_access(connection_id, session, user)
    repo = BASRepository(session)
    notes = await repo.list_notes_for_request(request_id, user.tenant_id)
    return [AgentNoteResponse.model_validate(n) for n in notes]


@router.post(
    "/{connection_id}/bas/sessions/{session_id}/classification-requests/{request_id}/notes",
    status_code=status.HTTP_201_CREATED,
    summary="Create an agent note for a classification request",
)
async def create_agent_note(
    connection_id: UUID,
    session_id: UUID,
    request_id: UUID,
    body: AgentNoteCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
):
    """Create a per-transaction agent note (initial context or send-back guidance)."""
    from app.modules.bas.classification_schemas import AgentNoteResponse
    from app.modules.bas.repository import BASRepository

    await verify_connection_access(connection_id, session, user)
    repo = BASRepository(session)
    note = await repo.create_agent_note(
        tenant_id=user.tenant_id,
        request_id=request_id,
        source_type=body.source_type,
        source_id=body.source_id,
        line_item_index=body.line_item_index,
        note_text=body.note_text,
        is_send_back_comment=body.is_send_back_comment,
        created_by=user.id,
    )
    await session.commit()
    return AgentNoteResponse.model_validate(note)


@router.get(
    "/{connection_id}/xero/tax-rates",
    summary="Get active tax rate codes for a Xero organisation",
)
async def get_org_tax_rates(
    connection_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
):
    """Return the active tax type codes configured for the org in Xero.

    Used by the override dropdown to filter out codes not available for this org.
    Falls back gracefully — if Xero is unreachable the UI falls back to the static list.
    """
    from app.config import get_settings
    from app.modules.integrations.xero.client import XeroClient
    from app.modules.integrations.xero.encryption import TokenEncryption
    from app.modules.integrations.xero.repository import XeroConnectionRepository

    await verify_connection_access(connection_id, session, user)

    repo = XeroConnectionRepository(session)
    connection = await repo.get_by_id(connection_id)

    settings = get_settings()
    encryption = TokenEncryption(settings.token_encryption.key.get_secret_value())
    access_token = encryption.decrypt(connection.access_token)

    async with XeroClient(settings.xero) as xero_client:
        try:
            tax_rates = await xero_client.get_tax_rates(access_token, connection.xero_tenant_id)
        except Exception:
            # Return empty list; frontend falls back to static VALID_TAX_TYPES
            return {"tax_types": []}

    active = [
        {"tax_type": r["TaxType"], "name": r.get("Name", r["TaxType"])}
        for r in tax_rates
        if r.get("Status") == "ACTIVE" and r.get("TaxType")
    ]
    return {"tax_types": active}


@router.get(
    "/{connection_id}/bas/sessions/{session_id}/transactions/{source_type}/{source_id}/{line_item_index}/rounds",
    summary="Get classification thread history for a transaction",
)
async def get_classification_rounds(
    connection_id: UUID,
    session_id: UUID,
    source_type: str,
    source_id: UUID,
    line_item_index: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
):
    """Get the full send-back conversation thread for a specific transaction."""
    from app.modules.bas.classification_schemas import ClassificationRoundResponse
    from app.modules.bas.classification_service import ClassificationService

    await verify_connection_access(connection_id, session, user)
    service = ClassificationService(session)
    rounds = await service.get_classification_thread(
        session_id=session_id,
        source_type=source_type,
        source_id=source_id,
        line_item_index=line_item_index,
        tenant_id=user.tenant_id,
    )
    return [ClassificationRoundResponse.model_validate(r) for r in rounds]


# ---------------------------------------------------------------------------
# Split management endpoints (Spec 049 line-items extension)
# ---------------------------------------------------------------------------


@router.get(
    "/{connection_id}/bas/sessions/{session_id}/bank-transactions/{source_id}/splits",
    response_model=TransactionSplitsResponse,
    summary="List original Xero line items and any active overrides for a bank transaction",
)
async def list_transaction_splits(
    connection_id: UUID,
    session_id: UUID,
    source_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
):
    """Return the original XeroBankTransaction.line_items alongside any active overrides."""
    from sqlalchemy import and_, select

    from app.modules.bas.repository import BASRepository
    from app.modules.integrations.xero.models import XeroBankTransaction

    await verify_connection_access(connection_id, session, user)
    repo = BASRepository(session)

    # Fetch the Xero bank transaction to get its stored line_items array
    result = await session.execute(
        select(XeroBankTransaction).where(
            and_(
                XeroBankTransaction.id == source_id,
                XeroBankTransaction.tenant_id == user.tenant_id,
            )
        )
    )
    txn = result.scalar_one_or_none()
    raw_line_items: list[dict] = txn.line_items if txn and txn.line_items else []

    original_line_items = [
        XeroLineItemView(
            index=i,
            tax_type=li.get("TaxType") or li.get("tax_type"),
            line_amount=li.get("LineAmount") or li.get("line_amount"),
            description=li.get("Description") or li.get("description"),
            account_code=li.get("AccountCode") or li.get("account_code"),
        )
        for i, li in enumerate(raw_line_items)
    ]

    overrides = await repo.get_overrides_for_transaction(source_id, user.tenant_id)
    return TransactionSplitsResponse(
        original_line_items=original_line_items,
        overrides=[TaxCodeOverrideWithSplitResponse.model_validate(o) for o in overrides],
    )


@router.post(
    "/{connection_id}/bas/sessions/{session_id}/bank-transactions/{source_id}/splits",
    response_model=TaxCodeOverrideWithSplitResponse,
    status_code=201,
    summary="Create a new agent-defined split on a bank transaction",
)
async def create_split_override(
    connection_id: UUID,
    session_id: UUID,
    source_id: UUID,
    body: SplitCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
):
    """Create a split override with is_new_split=True. Validates balance after insert."""
    from fastapi import HTTPException

    await verify_connection_access(connection_id, session, user)
    service = TaxCodeService(session)
    try:
        override = await service.create_split_override(
            source_id=source_id,
            connection_id=connection_id,
            line_item_index=body.line_item_index,
            override_tax_type=body.override_tax_type,
            applied_by=user.id,
            tenant_id=user.tenant_id,
            db=session,
            line_amount=body.line_amount,
            line_description=body.line_description,
            line_account_code=body.line_account_code,
            is_new_split=body.is_new_split,
            is_deleted=body.is_deleted,
        )
    except SplitAmountMismatchError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "detail": "split_amount_mismatch",
                "expected_total": str(exc.expected_total),
                "actual_total": str(exc.actual_total),
            },
        ) from exc
    return TaxCodeOverrideWithSplitResponse.model_validate(override)


@router.patch(
    "/{connection_id}/bas/sessions/{session_id}/bank-transactions/{source_id}/splits/{override_id}",
    response_model=TaxCodeOverrideWithSplitResponse,
    summary="Update an existing split or override",
)
async def update_split_override(
    connection_id: UUID,
    session_id: UUID,
    source_id: UUID,
    override_id: UUID,
    body: SplitUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
):
    """Update fields on a split. Re-validates balance after update."""
    from fastapi import HTTPException

    await verify_connection_access(connection_id, session, user)
    service = TaxCodeService(session)
    try:
        override = await service.update_split_override(
            override_id=override_id,
            tenant_id=user.tenant_id,
            db=session,
            override_tax_type=body.override_tax_type,
            line_amount=body.line_amount,
            line_description=body.line_description,
            line_account_code=body.line_account_code,
            is_deleted=body.is_deleted,
        )
    except SplitOverrideNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SplitAmountMismatchError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "detail": "split_amount_mismatch",
                "expected_total": str(exc.expected_total),
                "actual_total": str(exc.actual_total),
            },
        ) from exc
    return TaxCodeOverrideWithSplitResponse.model_validate(override)


@router.delete(
    "/{connection_id}/bas/sessions/{session_id}/bank-transactions/{source_id}/splits/{override_id}",
    status_code=204,
    summary="Remove a split (sets is_active=False)",
)
async def delete_split_override(
    connection_id: UUID,
    session_id: UUID,
    source_id: UUID,
    override_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
):
    """Deactivate a split override and re-validate balance."""
    from fastapi import HTTPException

    await verify_connection_access(connection_id, session, user)
    service = TaxCodeService(session)
    try:
        await service.delete_split_override(
            override_id=override_id,
            tenant_id=user.tenant_id,
            db=session,
        )
    except SplitOverrideNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SplitAmountMismatchError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "detail": "split_amount_mismatch",
                "expected_total": str(exc.expected_total),
                "actual_total": str(exc.actual_total),
            },
        ) from exc
