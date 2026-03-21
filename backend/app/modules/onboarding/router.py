"""API endpoints for onboarding flow.

Provides REST endpoints for:
- Onboarding progress management
- Tier selection and Stripe checkout
- Xero connection
- Bulk client import
- Product tour
- Checklist management
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.dependencies import (
    get_current_practice_user,
    get_current_tenant_id,
    get_or_create_onboarding_tenant,
)
from app.core.exceptions import DomainError
from app.core.logging import get_logger
from app.database import get_db
from app.modules.auth.models import PracticeUser
from app.modules.integrations.xero.models import XpmClientConnectionStatus
from app.modules.integrations.xero.schemas import (
    XeroConnectionResponse,
    XpmClientConnectionProgress,
    XpmClientConnectionUpdate,
    XpmClientConnectXeroResponse,
    XpmClientLinkByTenantIdRequest,
    XpmClientListResponse,
    XpmClientResponse,
    XpmClientUnlinkRequest,
)
from app.modules.integrations.xero.service import (
    XeroOAuthService,
    XpmClientNotFoundError,
    XpmClientService,
)
from app.modules.onboarding.exceptions import (
    ImportLimitExceededError,
)
from app.modules.onboarding.schemas import (
    AvailableClientsResponse,
    BulkImportJobResponse,
    BulkImportRequest,
    OnboardingProgressResponse,
    PaymentCompleteRequest,
    TierSelectionRequest,
    XeroConnectResponse,
)
from app.modules.onboarding.service import OnboardingService

router = APIRouter(prefix="/onboarding")
logger = get_logger(__name__)


# =============================================================================
# Progress Endpoints
# =============================================================================


@router.get(
    "/progress",
    response_model=OnboardingProgressResponse,
    summary="Get onboarding progress",
    description="Returns the current onboarding progress for the authenticated tenant",
)
async def get_onboarding_progress(
    tenant_id: UUID = Depends(get_or_create_onboarding_tenant),
    db: AsyncSession = Depends(get_db),
) -> OnboardingProgressResponse:
    """Get current onboarding progress."""
    logger.info("Getting onboarding progress", tenant_id=str(tenant_id))

    try:
        service = OnboardingService(db)
        progress = await service.get_progress(tenant_id)

        if not progress:
            logger.warning("Onboarding progress not found", tenant_id=str(tenant_id))
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No onboarding progress found",
            )

        checklist = await service.get_checklist(tenant_id)

        logger.debug(
            "Onboarding progress retrieved",
            tenant_id=str(tenant_id),
            status=progress.status.value,
        )

        return OnboardingProgressResponse(
            id=progress.id,
            status=progress.status,
            current_step=progress.current_step,
            started_at=progress.started_at,
            tier_selected_at=progress.tier_selected_at,
            payment_setup_at=progress.payment_setup_at,
            xero_connected_at=progress.xero_connected_at,
            clients_imported_at=progress.clients_imported_at,
            tour_completed_at=progress.tour_completed_at,
            completed_at=progress.completed_at,
            xero_skipped=progress.xero_skipped,
            tour_skipped=progress.tour_skipped,
            checklist=checklist,
        )
    except HTTPException:
        raise
    except DomainError as e:
        logger.error("Domain error getting progress", error=str(e))
        raise HTTPException(status_code=e.status_code, detail=e.message) from e
    except Exception as e:
        logger.exception("Unexpected error getting onboarding progress")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.post(
    "/start",
    response_model=OnboardingProgressResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start onboarding",
    description="Initialize onboarding progress for a new tenant",
)
async def start_onboarding(
    tenant_id: UUID = Depends(get_or_create_onboarding_tenant),
    db: AsyncSession = Depends(get_db),
) -> OnboardingProgressResponse:
    """Start onboarding for a new tenant."""
    service = OnboardingService(db)
    progress = await service.start_onboarding(tenant_id)
    checklist = await service.get_checklist(tenant_id)

    return OnboardingProgressResponse(
        id=progress.id,
        status=progress.status,
        current_step=progress.current_step,
        started_at=progress.started_at,
        tier_selected_at=progress.tier_selected_at,
        payment_setup_at=progress.payment_setup_at,
        xero_connected_at=progress.xero_connected_at,
        clients_imported_at=progress.clients_imported_at,
        tour_completed_at=progress.tour_completed_at,
        completed_at=progress.completed_at,
        xero_skipped=progress.xero_skipped,
        tour_skipped=progress.tour_skipped,
        checklist=checklist,
    )


# =============================================================================
# Tier Selection Endpoints
# =============================================================================


@router.post(
    "/tier",
    response_model=OnboardingProgressResponse,
    summary="Select subscription tier",
    description="Select tier and start 14-day free trial (no credit card required)",
)
async def select_tier(
    request: TierSelectionRequest,
    tenant_id: UUID = Depends(get_or_create_onboarding_tenant),
    db: AsyncSession = Depends(get_db),
) -> OnboardingProgressResponse:
    """Select subscription tier and start free trial.

    Creates a Stripe trial subscription server-side. No Stripe Checkout
    redirect — no credit card required upfront.
    """
    logger.info(
        "Selecting tier",
        tenant_id=str(tenant_id),
        tier=request.tier,
        with_trial=request.with_trial,
    )

    try:
        service = OnboardingService(db)
        progress = await service.select_tier(
            tenant_id=tenant_id,
            tier=request.tier,  # type: ignore  # validated by pydantic pattern
            with_trial=request.with_trial,
        )

        checklist = await service.get_checklist(tenant_id)

        logger.info(
            "Tier selected, trial started",
            tenant_id=str(tenant_id),
            tier=request.tier,
        )

        return OnboardingProgressResponse(
            id=progress.id,
            status=progress.status,
            current_step=progress.current_step,
            started_at=progress.started_at,
            tier_selected_at=progress.tier_selected_at,
            payment_setup_at=progress.payment_setup_at,
            xero_connected_at=progress.xero_connected_at,
            clients_imported_at=progress.clients_imported_at,
            tour_completed_at=progress.tour_completed_at,
            completed_at=progress.completed_at,
            xero_skipped=progress.xero_skipped,
            tour_skipped=progress.tour_skipped,
            checklist=checklist,
        )
    except ValueError as e:
        logger.warning("Invalid tier selection", error=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except DomainError as e:
        logger.error("Domain error selecting tier", error=str(e))
        raise HTTPException(status_code=e.status_code, detail=e.message) from e
    except Exception as e:
        logger.exception("Unexpected error selecting tier")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.post(
    "/payment-complete",
    response_model=OnboardingProgressResponse,
    summary="Mark payment setup complete",
    description="Called after Stripe checkout success to update onboarding progress",
)
async def payment_complete(
    request: PaymentCompleteRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> OnboardingProgressResponse:
    """Mark payment setup as complete.

    .. deprecated::
        Kept for in-flight edge cases. New flow creates trial
        subscription server-side in POST /tier.
    """
    service = OnboardingService(db)
    progress = await service.complete_payment(tenant_id, request.session_id)
    checklist = await service.get_checklist(tenant_id)

    return OnboardingProgressResponse(
        id=progress.id,
        status=progress.status,
        current_step=progress.current_step,
        started_at=progress.started_at,
        tier_selected_at=progress.tier_selected_at,
        payment_setup_at=progress.payment_setup_at,
        xero_connected_at=progress.xero_connected_at,
        clients_imported_at=progress.clients_imported_at,
        tour_completed_at=progress.tour_completed_at,
        completed_at=progress.completed_at,
        xero_skipped=progress.xero_skipped,
        tour_skipped=progress.tour_skipped,
        checklist=checklist,
    )


# =============================================================================
# Xero Connection Endpoints
# =============================================================================


@router.post(
    "/xero/connect",
    response_model=XeroConnectResponse,
    summary="Initiate Xero OAuth",
    description="Start Xero OAuth flow and return authorization URL",
)
async def connect_xero(
    request: Request,
    tenant_id: UUID = Depends(get_current_tenant_id),
    practice_user: PracticeUser = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
) -> XeroConnectResponse:
    """Initiate Xero OAuth connection."""
    # Build redirect URI for after OAuth completes
    # Frontend will handle the redirect to the callback
    frontend_redirect_uri = (
        f"{request.headers.get('origin', 'http://localhost:3000')}/onboarding/xero/callback"
    )

    service = OnboardingService(db)
    auth_url = await service.initiate_xero_connect(
        tenant_id=tenant_id,
        user_id=practice_user.id,  # Use practice_user.id, not user_id (FK references practice_users.id)
        frontend_redirect_uri=frontend_redirect_uri,
    )

    return XeroConnectResponse(authorization_url=auth_url)


@router.get(
    "/xero/callback",
    summary="Xero OAuth callback",
    description="Handle Xero OAuth callback and update onboarding progress",
)
async def xero_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Handle Xero OAuth callback.

    Note: This endpoint doesn't require auth as it's called by Xero redirect.
    The state parameter contains the tenant context.
    """
    # TODO: Parse tenant_id from state
    # TODO: Complete OAuth flow
    # For now, return placeholder
    return {"status": "ok", "redirect": "/onboarding/import-clients"}


@router.post(
    "/xero/skip",
    response_model=OnboardingProgressResponse,
    summary="Skip Xero connection",
    description="Skip Xero connection step (with warning)",
)
async def skip_xero(
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> OnboardingProgressResponse:
    """Skip Xero connection."""
    service = OnboardingService(db)
    progress = await service.skip_xero(tenant_id)
    checklist = await service.get_checklist(tenant_id)

    return OnboardingProgressResponse(
        id=progress.id,
        status=progress.status,
        current_step=progress.current_step,
        started_at=progress.started_at,
        tier_selected_at=progress.tier_selected_at,
        payment_setup_at=progress.payment_setup_at,
        xero_connected_at=progress.xero_connected_at,
        clients_imported_at=progress.clients_imported_at,
        tour_completed_at=progress.tour_completed_at,
        completed_at=progress.completed_at,
        xero_skipped=progress.xero_skipped,
        tour_skipped=progress.tour_skipped,
        checklist=checklist,
    )


# =============================================================================
# Client Import Endpoints
# =============================================================================


@router.get(
    "/clients/available",
    response_model=AvailableClientsResponse,
    summary="Get available clients for import",
    description="Returns list of XPM/Xero clients available for import",
)
async def get_available_clients(
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
    search: str | None = Query(None, description="Search filter for client name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> AvailableClientsResponse:
    """Get clients available for import from Xero/XPM."""
    service = OnboardingService(db)
    result = await service.get_available_clients(tenant_id, search, page, page_size)

    return AvailableClientsResponse(**result)


@router.post(
    "/clients/import",
    response_model=BulkImportJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start bulk client import",
    description="Start background job to import selected clients",
)
async def start_bulk_import(
    request: BulkImportRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> BulkImportJobResponse:
    """Start bulk client import job."""
    logger.info(
        "Starting bulk import",
        tenant_id=str(tenant_id),
        client_count=len(request.client_ids),
    )

    try:
        service = OnboardingService(db)
        job = await service.start_bulk_import(tenant_id, request.client_ids)

        logger.info(
            "Bulk import job created",
            tenant_id=str(tenant_id),
            job_id=str(job.id),
            client_count=len(request.client_ids),
        )

        return BulkImportJobResponse(
            id=job.id,
            status=job.status,
            source_type=job.source_type,
            total_clients=job.total_clients,
            imported_count=job.imported_count,
            failed_count=job.failed_count,
            progress_percent=job.progress_percent,
            started_at=job.started_at,
            completed_at=job.completed_at,
        )
    except ImportLimitExceededError as e:
        logger.warning(
            "Import limit exceeded",
            tenant_id=str(tenant_id),
            requested=e.requested_count,
            limit=e.tier_limit,
        )
        raise HTTPException(status_code=e.status_code, detail=e.message) from e
    except DomainError as e:
        logger.error("Domain error starting import", error=str(e))
        raise HTTPException(status_code=e.status_code, detail=e.message) from e
    except Exception as e:
        logger.exception("Unexpected error starting bulk import")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        ) from e


@router.get(
    "/import/{job_id}",
    response_model=BulkImportJobResponse,
    summary="Get import job status",
    description="Get progress of a bulk import job",
)
async def get_import_job_status(
    job_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> BulkImportJobResponse:
    """Get bulk import job status."""
    service = OnboardingService(db)
    job = await service.get_import_job(tenant_id, job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Import job not found",
        )

    return BulkImportJobResponse(
        id=job.id,
        status=job.status,
        source_type=job.source_type,
        total_clients=job.total_clients,
        imported_count=job.imported_count,
        failed_count=job.failed_count,
        progress_percent=job.progress_percent,
        started_at=job.started_at,
        completed_at=job.completed_at,
        imported_clients=job.imported_clients,
        failed_clients=job.failed_clients,
    )


@router.post(
    "/import/{job_id}/retry",
    response_model=BulkImportJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Retry failed imports",
    description="Retry importing clients that failed in a previous job",
)
async def retry_failed_imports(
    job_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> BulkImportJobResponse:
    """Retry failed imports from a previous job."""
    service = OnboardingService(db)
    job = await service.retry_failed_imports(tenant_id, job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No failed imports to retry or job not found",
        )

    return BulkImportJobResponse(
        id=job.id,
        status=job.status,
        source_type=job.source_type,
        total_clients=job.total_clients,
        imported_count=job.imported_count,
        failed_count=job.failed_count,
        progress_percent=job.progress_percent,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


# =============================================================================
# Tour Endpoints
# =============================================================================


@router.post(
    "/tour/complete",
    response_model=OnboardingProgressResponse,
    summary="Mark tour complete",
    description="Mark product tour as completed",
)
async def complete_tour(
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> OnboardingProgressResponse:
    """Mark product tour as completed."""
    service = OnboardingService(db)
    progress = await service.complete_tour(tenant_id)
    checklist = await service.get_checklist(tenant_id)

    return OnboardingProgressResponse(
        id=progress.id,
        status=progress.status,
        current_step=progress.current_step,
        started_at=progress.started_at,
        tier_selected_at=progress.tier_selected_at,
        payment_setup_at=progress.payment_setup_at,
        xero_connected_at=progress.xero_connected_at,
        clients_imported_at=progress.clients_imported_at,
        tour_completed_at=progress.tour_completed_at,
        completed_at=progress.completed_at,
        xero_skipped=progress.xero_skipped,
        tour_skipped=progress.tour_skipped,
        checklist=checklist,
    )


@router.post(
    "/tour/skip",
    response_model=OnboardingProgressResponse,
    summary="Skip tour",
    description="Skip the product tour",
)
async def skip_tour(
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> OnboardingProgressResponse:
    """Skip product tour."""
    service = OnboardingService(db)
    progress = await service.skip_tour(tenant_id)
    checklist = await service.get_checklist(tenant_id)

    return OnboardingProgressResponse(
        id=progress.id,
        status=progress.status,
        current_step=progress.current_step,
        started_at=progress.started_at,
        tier_selected_at=progress.tier_selected_at,
        payment_setup_at=progress.payment_setup_at,
        xero_connected_at=progress.xero_connected_at,
        clients_imported_at=progress.clients_imported_at,
        tour_completed_at=progress.tour_completed_at,
        completed_at=progress.completed_at,
        xero_skipped=progress.xero_skipped,
        tour_skipped=progress.tour_skipped,
        checklist=checklist,
    )


# =============================================================================
# Checklist Endpoints
# =============================================================================


@router.post(
    "/checklist/dismiss",
    response_model=OnboardingProgressResponse,
    summary="Dismiss checklist",
    description="Permanently hide the onboarding checklist",
)
async def dismiss_checklist(
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> OnboardingProgressResponse:
    """Dismiss onboarding checklist."""
    service = OnboardingService(db)
    progress = await service.dismiss_checklist(tenant_id)
    checklist = await service.get_checklist(tenant_id)

    return OnboardingProgressResponse(
        id=progress.id,
        status=progress.status,
        current_step=progress.current_step,
        started_at=progress.started_at,
        tier_selected_at=progress.tier_selected_at,
        payment_setup_at=progress.payment_setup_at,
        xero_connected_at=progress.xero_connected_at,
        clients_imported_at=progress.clients_imported_at,
        tour_completed_at=progress.tour_completed_at,
        completed_at=progress.completed_at,
        xero_skipped=progress.xero_skipped,
        tour_skipped=progress.tour_skipped,
        checklist=checklist,
    )


# =============================================================================
# XPM Client Connection Endpoints (Phase 6b)
# =============================================================================


@router.get(
    "/xpm-clients",
    response_model=XpmClientListResponse,
    summary="List XPM clients",
    description="List practice clients from XPM with their Xero connection status",
)
async def list_xpm_clients(
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
    connection_status: XpmClientConnectionStatus | None = Query(
        default=None,
        description="Filter by Xero connection status",
    ),
    search: str | None = Query(
        default=None,
        max_length=100,
        description="Search by client name",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> XpmClientListResponse:
    """List XPM clients with their Xero connection status."""
    settings = get_settings()
    service = XpmClientService(db, settings)
    return await service.list_xpm_clients(
        tenant_id=tenant_id,
        connection_status=connection_status,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/xpm-clients/connection-progress",
    response_model=XpmClientConnectionProgress,
    summary="Get connection progress",
    description="Get summary of how many XPM clients have Xero orgs connected",
)
async def get_xpm_client_connection_progress(
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> XpmClientConnectionProgress:
    """Get XPM client Xero connection progress."""
    settings = get_settings()
    service = XpmClientService(db, settings)
    return await service.get_connection_progress(tenant_id)


@router.post(
    "/xero/sync-connections",
    summary="Sync Xero connections and match to clients",
    description=(
        "Fetch all authorized Xero connections and attempt to match them "
        "to XPM clients by name. Returns matched and unmatched results."
    ),
)
async def sync_xero_connections(
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
    connection_id: UUID = Query(
        ...,
        description="ID of an active XeroConnection to use for API authentication",
    ),
):
    """Sync Xero connections and match to XPM clients.

    This endpoint:
    1. Fetches all authorized Xero organizations from the Xero API
    2. Updates XeroConnection records in the database
    3. Attempts to match Xero orgs to XPM clients by name
    4. Returns results showing matched and unmatched items
    """
    settings = get_settings()
    service = XpmClientService(db, settings)

    try:
        # Fetch connections from Xero API
        organizations = await service.fetch_xero_connections(connection_id)

        # Sync to database
        sync_result = await service.sync_xero_connections(
            tenant_id=tenant_id,
            organizations=organizations,
        )

        # Run matching
        match_result = await service.match_connections_to_xpm_clients(tenant_id)

        return {
            "status": "success",
            "xero_organizations_found": len(organizations),
            "sync_result": sync_result,
            "match_result": match_result,
        }
    except Exception as e:
        logger.error(
            "Failed to sync Xero connections",
            tenant_id=str(tenant_id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync Xero connections: {e!s}",
        ) from e


@router.post(
    "/xpm-clients/{client_id}/link-xero",
    response_model=XpmClientResponse,
    summary="Link XPM client to Xero org",
    description="Manually link an XPM client to a specific Xero organization connection",
)
async def link_xpm_client_to_xero(
    client_id: UUID,
    request: XpmClientConnectionUpdate,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> XpmClientResponse:
    """Manually link an XPM client to a Xero connection."""
    settings = get_settings()
    service = XpmClientService(db, settings)

    try:
        return await service.link_client_to_connection(
            client_id=client_id,
            connection_id=request.xero_connection_id,
        )
    except XpmClientNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"XPM client {client_id} not found",
        ) from e


@router.post(
    "/xpm-clients/{client_id}/unlink-xero",
    response_model=XpmClientResponse,
    summary="Unlink XPM client from Xero org",
    description="Remove the link between an XPM client and their Xero organization",
)
async def unlink_xpm_client_from_xero(
    client_id: UUID,
    request: XpmClientUnlinkRequest | None = None,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> XpmClientResponse:
    """Unlink an XPM client from their Xero connection."""
    settings = get_settings()
    service = XpmClientService(db, settings)

    try:
        return await service.unlink_client_from_connection(
            client_id=client_id,
            reason=request.reason if request else None,
        )
    except XpmClientNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"XPM client {client_id} not found",
        ) from e


@router.post(
    "/xpm-clients/{client_id}/connect-xero",
    response_model=XpmClientConnectXeroResponse,
    summary="Initiate OAuth for client's Xero org",
    description=(
        "Generate OAuth authorization URL to connect a specific client's Xero organization. "
        "The accountant will be redirected to Xero to authorize access to the client's org."
    ),
)
async def connect_xpm_client_xero(
    client_id: UUID,
    redirect_uri: str = Query(
        ...,
        description="Frontend URI to redirect after OAuth completion",
    ),
    tenant_id: UUID = Depends(get_current_tenant_id),
    current_user: PracticeUser = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
) -> XpmClientConnectXeroResponse:
    """Initiate OAuth for a specific XPM client's Xero organization.

    This starts the OAuth flow to authorize access to a client's Xero org.
    The connection will be linked to this XPM client after OAuth completes.
    """
    settings = get_settings()

    # Verify client exists
    from app.modules.integrations.xero.repository import XpmClientRepository

    xpm_repo = XpmClientRepository(db)
    client = await xpm_repo.get_by_id(client_id)

    if not client or client.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"XPM client {client_id} not found",
        )

    # Generate client-specific OAuth URL
    oauth_service = XeroOAuthService(db, settings)
    auth_response = await oauth_service.generate_client_auth_url(
        tenant_id=tenant_id,
        user_id=current_user.id,  # Use practice_user.id, not user_id (FK references practice_users.id)
        xpm_client_id=client_id,
        frontend_redirect_uri=redirect_uri,
    )

    logger.info(
        "Generated client OAuth URL",
        tenant_id=str(tenant_id),
        client_id=str(client_id),
        client_name=client.name,
    )

    return XpmClientConnectXeroResponse(
        client_id=client_id,
        client_name=client.name,
        authorization_url=auth_response.auth_url,
        state=auth_response.state,
    )


@router.post(
    "/xpm-clients/connect-next",
    response_model=XpmClientConnectXeroResponse | None,
    summary="Get next unconnected client for OAuth",
    description=(
        "Returns the next XPM client that doesn't have a Xero org connected, "
        "along with the OAuth URL to connect it. Used for sequential client connection flow."
    ),
)
async def connect_next_xpm_client(
    redirect_uri: str = Query(
        ...,
        description="Frontend URI to redirect after OAuth completion",
    ),
    tenant_id: UUID = Depends(get_current_tenant_id),
    current_user: PracticeUser = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the next unconnected XPM client and initiate OAuth.

    This endpoint supports the "Connect All Remaining" workflow where
    the frontend loops through unconnected clients one by one.

    Returns null if all clients are already connected.
    """
    settings = get_settings()

    # Get next unconnected client
    from app.modules.integrations.xero.repository import XpmClientRepository

    xpm_repo = XpmClientRepository(db)
    unconnected, total = await xpm_repo.get_unconnected_clients(
        tenant_id=tenant_id,
        limit=1,
        offset=0,
    )

    if not unconnected:
        # All clients are connected
        return None

    client = unconnected[0]

    # Generate OAuth URL for this client
    oauth_service = XeroOAuthService(db, settings)
    auth_response = await oauth_service.generate_client_auth_url(
        tenant_id=tenant_id,
        user_id=current_user.id,  # Use practice_user.id, not user_id (FK references practice_users.id)
        xpm_client_id=client.id,
        frontend_redirect_uri=redirect_uri,
    )

    logger.info(
        "Generated OAuth URL for next unconnected client",
        tenant_id=str(tenant_id),
        client_id=str(client.id),
        client_name=client.name,
        remaining_unconnected=total - 1,
    )

    return XpmClientConnectXeroResponse(
        client_id=client.id,
        client_name=client.name,
        authorization_url=auth_response.auth_url,
        state=auth_response.state,
    )


# =============================================================================
# Phase 6b.6: Manual Matching & Admin Tools
# =============================================================================


@router.post(
    "/xpm-clients/{client_id}/link-xero-org",
    response_model=XpmClientResponse,
    summary="Link XPM client by Xero tenant ID",
    description=(
        "Manually link an XPM client to a Xero organization using the Xero tenant ID. "
        "Used when automatic matching fails and manual matching is needed."
    ),
)
async def link_xpm_client_by_tenant_id(
    client_id: UUID,
    request: XpmClientLinkByTenantIdRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> XpmClientResponse:
    """Link XPM client to Xero org using Xero's tenant ID.

    This is an alternative to link-xero which uses our internal connection UUID.
    Use this when you have the Xero tenant ID from an unmatched connection.
    """
    from app.modules.integrations.xero.exceptions import (
        XeroConnectionNotFoundError as XeroConnNotFound,
    )

    settings = get_settings()
    service = XpmClientService(db, settings)

    try:
        return await service.link_client_by_tenant_id(
            client_id=client_id,
            xero_tenant_id=request.xero_tenant_id,
            tenant_id=tenant_id,
        )
    except XpmClientNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"XPM client {client_id} not found",
        ) from e
    except XeroConnNotFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No Xero connection found with tenant ID: {request.xero_tenant_id}",
        ) from e


@router.get(
    "/xero/unmatched-connections",
    response_model=list[XeroConnectionResponse],
    summary="List unmatched Xero connections",
    description=(
        "Returns Xero organizations that have been authorized but couldn't be "
        "automatically matched to an XPM client. These need manual matching."
    ),
)
async def get_unmatched_xero_connections(
    tenant_id: UUID = Depends(get_current_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[XeroConnectionResponse]:
    """Get Xero connections that aren't linked to any XPM client.

    These are organizations the accountant has authorized but couldn't be
    matched to clients by name or email. Use the link-xero-org endpoint
    to manually match them.
    """
    settings = get_settings()
    service = XpmClientService(db, settings)

    return await service.get_unmatched_connections(tenant_id)
