"""Xero integration API endpoints.

Provides endpoints for:
- OAuth flow initiation and callback
- Connection listing and management
- Token refresh
- Data sync operations
- Synced entity access (clients, invoices, transactions, accounts)
- Client view and financial summary (Spec 005)
"""

from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.audit import AuditService
from app.database import get_db as get_db_session
from app.modules.auth.models import PracticeUser
from app.modules.auth.permissions import Permission, require_permission
from app.modules.billing.middleware import require_active_subscription
from app.tasks.celery_app import celery_app

from .client import XeroClientError
from .exceptions import (
    XeroConnectionInactiveError,
    XeroConnectionNotFoundError as XeroConnectionNotFoundExc,
    XeroRateLimitExceededError,
    XeroSyncInProgressError,
    XeroSyncJobNotFoundError,
)
from .models import XeroSyncType
from .repository import (
    PostSyncTaskRepository,
    XeroAccountRepository,
    XeroAssetRepository,
    XeroAssetTypeRepository,
    XeroBankTransactionRepository,
    XeroClientRepository,
    XeroConnectionRepository,
    XeroCreditNoteRepository,
    XeroInvoiceRepository,
    XeroJournalRepository,
    XeroManualJournalRepository,
    XeroOverpaymentRepository,
    XeroPaymentRepository,
    XeroPrepaymentRepository,
    XeroSyncEntityProgressRepository,
    XeroSyncJobRepository,
)
from .schemas import (
    AssetDetailSchema,
    AssetListResponse,
    AssetSchema,
    AssetTypeListResponse,
    AssetTypeSchema,
    AvailableQuartersResponse,
    BulkImportCallbackResponse,
    BulkImportConfirmRequest,
    BulkImportInitiateRequest,
    BulkImportInitiateResponse,
    BulkImportJobDetailResponse,
    BulkImportJobListResponse,
    BulkImportJobResponse,
    BulkImportOrgStatus,
    ClientFinancialSummaryResponse,
    CreditNoteDetailSchema,
    CreditNoteListResponse,
    CreditNoteSchema,
    EnhancedSyncStatus,
    EntityProgressResponse,
    JournalDetailSchema,
    JournalListResponse,
    JournalSchema,
    ManualJournalDetailSchema,
    ManualJournalListResponse,
    ManualJournalSchema,
    MultiClientConnectionStatus,
    MultiClientSyncResponse,
    MultiClientSyncStatusResponse,
    OverpaymentListResponse,
    OverpaymentSchema,
    PaymentDetailSchema,
    PaymentListResponse,
    PaymentSchema,
    PostSyncTaskResponse,
    PrepaymentListResponse,
    PrepaymentSchema,
    PurchaseOrderListResponse,
    PurchaseOrderSchema,
    PurchaseOrderSummary,
    QuoteListResponse,
    QuotePipelineSummary,
    QuoteSchema,
    RateLimitResponse,
    RecurringSummary,
    RefreshReportRequest,
    RepeatingInvoiceListResponse,
    RepeatingInvoiceSchema,
    ReportListResponse,
    ReportResponse,
    ReportStatusItem,
    SyncJobResponse,
    SyncStatusResponse,
    TrackingCategoryListResponse,
    TrackingCategorySchema,
    TransactionSyncStatus,
    XeroAccountListResponse,
    XeroAccountResponse,
    XeroAuthUrlResponse,
    XeroBankTransactionListResponse,
    XeroBankTransactionResponse,
    XeroCallbackResponse,
    XeroClientDetailResponse,
    XeroClientListResponse,
    XeroClientResponse,
    XeroConnectionDataCounts,
    XeroConnectionListResponse,
    XeroConnectionResponse,
    XeroConnectRequest,
    XeroDeleteConnectionRequest,
    XeroDisconnectRequest,
    XeroEmployeeListResponse,
    XeroEmployeeResponse,
    XeroInvoiceListResponse,
    XeroInvoiceResponse,
    XeroPayrollSummaryResponse,
    XeroPayrollSyncResponse,
    XeroPayRunListResponse,
    XeroPayRunResponse,
    XeroSyncHistoryResponse,
    XeroSyncJobResponse,
    XeroSyncRequest,
)
from .service import (
    BulkImportInProgressError,
    BulkImportService,
    BulkImportValidationError,
    XeroClientNotFoundError,
    XeroClientService,
    XeroConnectionNotFoundError,
    XeroConnectionService,
    XeroDataService,
    XeroOAuthError,
    XeroOAuthService,
    XeroReportService,
    XeroSyncService,
)

router = APIRouter(prefix="/integrations/xero", tags=["Xero Integration"])


# =============================================================================
# Helper Dependencies
# =============================================================================


async def get_oauth_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> XeroOAuthService:
    """Get XeroOAuthService instance.

    Args:
        session: Database session.
        settings: Application settings.

    Returns:
        Configured XeroOAuthService.
    """
    return XeroOAuthService(session=session, settings=settings)


async def get_connection_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> XeroConnectionService:
    """Get XeroConnectionService instance.

    Args:
        session: Database session.
        settings: Application settings.

    Returns:
        Configured XeroConnectionService.
    """
    return XeroConnectionService(session=session, settings=settings)


async def get_audit_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuditService:
    """Get AuditService instance.

    Args:
        session: Database session.

    Returns:
        Configured AuditService.
    """
    return AuditService(session=session)


async def get_sync_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> XeroSyncService:
    """Get XeroSyncService instance.

    Args:
        session: Database session.
        settings: Application settings.

    Returns:
        Configured XeroSyncService.
    """
    return XeroSyncService(session=session, settings=settings, celery_app=celery_app)


async def get_client_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> XeroClientRepository:
    """Get XeroClientRepository instance."""
    return XeroClientRepository(session=session)


async def get_invoice_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> XeroInvoiceRepository:
    """Get XeroInvoiceRepository instance."""
    return XeroInvoiceRepository(session=session)


async def get_transaction_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> XeroBankTransactionRepository:
    """Get XeroBankTransactionRepository instance."""
    return XeroBankTransactionRepository(session=session)


async def get_account_repo(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> XeroAccountRepository:
    """Get XeroAccountRepository instance."""
    return XeroAccountRepository(session=session)


async def get_client_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> XeroClientService:
    """Get XeroClientService instance."""
    return XeroClientService(session=session)


async def get_payroll_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    """Get XeroPayrollService instance."""
    from .payroll_service import XeroPayrollService

    return XeroPayrollService(session=session, settings=settings)


# =============================================================================
# OAuth Flow Endpoints
# =============================================================================


@router.post(
    "/connect",
    response_model=XeroAuthUrlResponse,
    summary="Initiate Xero OAuth flow",
    description="""
    Generate a Xero OAuth authorization URL for the user to authorize access.

    **Required Permission**: `integration.manage`

    The returned URL should be used to redirect the user to Xero's authorization page.
    After authorization, Xero will redirect to the callback endpoint.
    """,
    responses={
        200: {"description": "Authorization URL generated"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
    },
)
async def initiate_oauth(
    request: XeroConnectRequest,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_MANAGE)),
    oauth_service: XeroOAuthService = Depends(get_oauth_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> XeroAuthUrlResponse:
    """Initiate Xero OAuth flow.

    Args:
        request: Connect request with redirect URI.
        current_user: Current authenticated user.
        oauth_service: OAuth service instance.
        audit_service: Audit service instance.

    Returns:
        Authorization URL and state for CSRF protection.
    """
    response = await oauth_service.generate_auth_url(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        frontend_redirect_uri=request.redirect_uri,
    )

    # Log OAuth initiation
    await audit_service.log_event(
        event_type="xero.oauth.initiated",
        event_category="integration",
        actor_type="user",
        actor_id=current_user.user_id,
        actor_email=current_user.email,
        tenant_id=current_user.tenant_id,
        resource_type="xero_connection",
        action="connect",
        outcome="success",
        metadata={
            "redirect_uri": request.redirect_uri,
        },
    )

    return response


@router.get(
    "/callback",
    response_model=XeroCallbackResponse,
    summary="Handle Xero OAuth callback",
    description="""
    Handle the OAuth callback from Xero after user authorization.

    **Required Permission**: `integration.manage`

    This endpoint is called by the frontend after Xero redirects back
    with the authorization code and state.
    """,
    responses={
        200: {"description": "Connection created/updated"},
        400: {"description": "Invalid state or code"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
    },
)
async def handle_callback(
    code: Annotated[str, Query(description="Authorization code from Xero")],
    state: Annotated[str, Query(description="State parameter for CSRF validation")],
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_MANAGE)),
    oauth_service: XeroOAuthService = Depends(get_oauth_service),
    audit_service: AuditService = Depends(get_audit_service),
    session: AsyncSession = Depends(get_db_session),
) -> XeroCallbackResponse:
    """Handle Xero OAuth callback.

    Args:
        code: Authorization code from Xero.
        state: State parameter for CSRF validation.
        current_user: Current authenticated user.
        oauth_service: OAuth service instance.
        audit_service: Audit service instance.

    Returns:
        Created/updated connection details.
    """
    try:
        connection, xpm_client_id = await oauth_service.handle_callback(code=code, state=state)
    except XeroOAuthError as e:
        # Log OAuth failure
        await audit_service.log_event(
            event_type="xero.oauth.failed",
            event_category="integration",
            actor_type="user",
            actor_id=current_user.user_id,
            actor_email=current_user.email,
            tenant_id=current_user.tenant_id,
            resource_type="xero_connection",
            action="connect",
            outcome="failure",
            metadata={
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "OAUTH_ERROR", "message": str(e)}},
        ) from None

    # Build metadata for audit
    audit_metadata = {
        "organization_name": connection.organization_name,
        "xero_tenant_id": connection.xero_tenant_id,
    }
    if xpm_client_id:
        audit_metadata["xpm_client_id"] = str(xpm_client_id)

    # Log successful connection
    await audit_service.log_event(
        event_type="xero.oauth.connected",
        event_category="integration",
        actor_type="user",
        actor_id=current_user.user_id,
        actor_email=current_user.email,
        tenant_id=current_user.tenant_id,
        resource_type="xero_connection",
        resource_id=connection.id,
        action="connect",
        outcome="success",
        metadata=audit_metadata,
    )

    # Update onboarding progress: mark Xero as connected
    # Use a savepoint so onboarding failures don't corrupt the session
    # and prevent the connection from being committed by get_db()
    try:
        from app.modules.onboarding.service import OnboardingService

        async with session.begin_nested():
            onboarding_service = OnboardingService(session=session)
            await onboarding_service.mark_xero_connected(current_user.tenant_id)
    except Exception as e:
        logger.warning("Failed to update onboarding progress for Xero connect", error=str(e))

    # Auto-refresh Tax Plan financials now that the connection is active
    try:
        from app.tasks.tax_planning import refresh_connection_tax_plans

        refresh_connection_tax_plans.delay(
            connection_id=str(connection.id),
            tenant_id=str(current_user.tenant_id),
        )
    except Exception as e:
        logger.warning("Failed to queue tax plan refresh after reconnection", error=str(e))

    # Build message
    message = "Successfully connected to Xero"
    if xpm_client_id:
        message = f"Successfully connected client to {connection.organization_name}"

    return XeroCallbackResponse(
        connection_id=connection.id,
        organization_name=connection.organization_name,
        status=connection.status,
        message=message,
    )


# =============================================================================
# Connection Management Endpoints
# =============================================================================


@router.get(
    "/connections",
    response_model=XeroConnectionListResponse,
    summary="List Xero connections",
    description="""
    List all Xero connections for the current tenant.

    **Required Permission**: `integration.read`

    By default, only active and needs_reauth connections are returned.
    """,
    responses={
        200: {"description": "List of connections"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
    },
)
async def list_connections(
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    connection_service: XeroConnectionService = Depends(get_connection_service),
) -> XeroConnectionListResponse:
    """List Xero connections for the tenant.

    Args:
        current_user: Current authenticated user.
        connection_service: Connection service instance.

    Returns:
        List of connection summaries.
    """
    return await connection_service.list_connections(tenant_id=current_user.tenant_id)


@router.get(
    "/connections/{connection_id}",
    response_model=XeroConnectionResponse,
    summary="Get Xero connection details",
    description="""
    Get details for a specific Xero connection.

    **Required Permission**: `integration.read`
    """,
    responses={
        200: {"description": "Connection details"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Connection not found"},
    },
)
async def get_connection(
    connection_id: UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    connection_service: XeroConnectionService = Depends(get_connection_service),
) -> XeroConnectionResponse:
    """Get connection details.

    Args:
        connection_id: The connection ID.
        current_user: Current authenticated user.
        connection_service: Connection service instance.

    Returns:
        Connection details.
    """
    try:
        return await connection_service.get_connection(connection_id)
    except XeroConnectionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Connection not found"}},
        ) from None


@router.delete(
    "/connections/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disconnect Xero organization",
    description="""
    Disconnect a Xero organization, revoking tokens and marking as disconnected.

    **Required Permission**: `integration.manage`
    """,
    responses={
        204: {"description": "Connection disconnected"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Connection not found"},
    },
)
async def disconnect(
    connection_id: UUID,
    request: XeroDisconnectRequest | None = None,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_MANAGE)),
    connection_service: XeroConnectionService = Depends(get_connection_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> None:
    """Disconnect a Xero organization.

    Args:
        connection_id: The connection ID.
        request: Optional disconnect request with reason.
        current_user: Current authenticated user.
        connection_service: Connection service instance.
        audit_service: Audit service instance.
    """
    reason = request.reason if request else None

    try:
        await connection_service.disconnect(
            connection_id=connection_id,
            user_id=current_user.id,
            reason=reason,
        )
    except XeroConnectionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Connection not found"}},
        ) from None

    # Log disconnection
    await audit_service.log_event(
        event_type="xero.connection.disconnected",
        event_category="integration",
        actor_type="user",
        actor_id=current_user.user_id,
        actor_email=current_user.email,
        tenant_id=current_user.tenant_id,
        resource_type="xero_connection",
        resource_id=connection_id,
        action="disconnect",
        outcome="success",
        metadata={
            "reason": reason,
        },
    )


@router.get(
    "/connections/{connection_id}/data-counts",
    response_model=XeroConnectionDataCounts,
    summary="Get data counts for a connection",
    description="""
    Returns counts of all data associated with a connection.
    Used to show the user what will be deleted before confirming.

    **Required Permission**: `integration.manage`
    """,
    responses={
        200: {"description": "Data counts"},
        404: {"description": "Connection not found"},
    },
)
async def get_connection_data_counts(
    connection_id: UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_MANAGE)),
    connection_service: XeroConnectionService = Depends(get_connection_service),
) -> XeroConnectionDataCounts:
    """Get counts of all data associated with a connection.

    Args:
        connection_id: The connection ID.
        current_user: Current authenticated user.
        connection_service: Connection service instance.
    """
    try:
        counts = await connection_service.get_connection_data_counts(connection_id)
        return XeroConnectionDataCounts(**counts)
    except XeroConnectionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Connection not found"}},
        ) from None


@router.delete(
    "/connections/{connection_id}/all-data",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete connection and all associated data",
    description="""
    Permanently delete a Xero connection and ALL associated data including
    clients, invoices, transactions, journals, BAS periods, quality scores,
    sync history, and all other related records.

    **This action is irreversible.**

    The request body must include `confirmation_name` matching the
    organization name exactly.

    **Required Permission**: `integration.manage`
    """,
    responses={
        204: {"description": "Connection and all data deleted"},
        400: {"description": "Confirmation name does not match"},
        404: {"description": "Connection not found"},
    },
)
async def delete_connection_and_data(
    connection_id: UUID,
    request: XeroDeleteConnectionRequest,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_MANAGE)),
    connection_service: XeroConnectionService = Depends(get_connection_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> None:
    """Permanently delete a connection and all associated data.

    Args:
        connection_id: The connection ID.
        request: Delete request with confirmation name.
        current_user: Current authenticated user.
        connection_service: Connection service instance.
        audit_service: Audit service instance.
    """
    # Verify the connection exists and get the name for confirmation check
    try:
        connection = await connection_service.get_connection(connection_id)
    except XeroConnectionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Connection not found"}},
        ) from None

    # Verify confirmation name matches
    if request.confirmation_name.strip() != connection.organization_name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "CONFIRMATION_MISMATCH",
                    "message": "Organization name does not match. Please type the exact name to confirm.",
                }
            },
        )

    # Get counts for audit log before deletion
    counts = await connection_service.get_connection_data_counts(connection_id)

    # Perform the deletion
    try:
        await connection_service.delete_connection(
            connection_id=connection_id,
            user_id=current_user.id,
        )
    except XeroConnectionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Connection not found"}},
        ) from None

    # Audit log
    await audit_service.log_event(
        event_type="xero.connection.deleted",
        event_category="integration",
        actor_type="user",
        actor_id=current_user.user_id,
        actor_email=current_user.email,
        tenant_id=current_user.tenant_id,
        resource_type="xero_connection",
        resource_id=connection_id,
        action="delete",
        outcome="success",
        metadata={
            "organization_name": connection.organization_name,
            "reason": request.reason,
            "deleted_records": counts,
        },
    )


@router.post(
    "/connections/{connection_id}/refresh",
    response_model=XeroConnectionResponse,
    summary="Refresh Xero connection tokens",
    description="""
    Manually trigger a token refresh for a Xero connection.

    **Required Permission**: `integration.manage`

    Note: Tokens are normally refreshed automatically when needed.
    This endpoint is for troubleshooting or forcing a refresh.
    """,
    responses={
        200: {"description": "Tokens refreshed"},
        400: {"description": "Refresh failed (connection inactive)"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Connection not found"},
    },
)
async def refresh_connection(
    connection_id: UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_MANAGE)),
    connection_service: XeroConnectionService = Depends(get_connection_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> XeroConnectionResponse:
    """Manually refresh connection tokens.

    Args:
        connection_id: The connection ID.
        current_user: Current authenticated user.
        connection_service: Connection service instance.
        audit_service: Audit service instance.

    Returns:
        Updated connection details.
    """
    try:
        connection = await connection_service.refresh_tokens(connection_id)
    except XeroConnectionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Connection not found"}},
        ) from None
    except XeroOAuthError as e:
        # Log refresh failure
        await audit_service.log_event(
            event_type="xero.token.refresh.failed",
            event_category="integration",
            actor_type="user",
            actor_id=current_user.user_id,
            actor_email=current_user.email,
            tenant_id=current_user.tenant_id,
            resource_type="xero_connection",
            resource_id=connection_id,
            action="refresh",
            outcome="failure",
            metadata={
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "REFRESH_ERROR", "message": str(e)}},
        ) from None

    # Log successful refresh
    await audit_service.log_event(
        event_type="xero.token.refresh.success",
        event_category="integration",
        actor_type="user",
        actor_id=current_user.user_id,
        actor_email=current_user.email,
        tenant_id=current_user.tenant_id,
        resource_type="xero_connection",
        resource_id=connection_id,
        action="refresh",
        outcome="success",
    )

    return XeroConnectionResponse(
        id=connection.id,
        xero_tenant_id=connection.xero_tenant_id,
        organization_name=connection.organization_name,
        status=connection.status,
        scopes=connection.scopes,
        connected_at=connection.connected_at,
        last_used_at=connection.last_used_at,
        rate_limit_daily_remaining=connection.rate_limit_daily_remaining,
        rate_limit_minute_remaining=connection.rate_limit_minute_remaining,
    )


# =============================================================================
# Health Check Endpoint
# =============================================================================


@router.get(
    "/health",
    summary="Xero integration health check",
    description="Returns health status of the Xero integration module.",
    responses={
        200: {"description": "Module is healthy"},
    },
)
async def xero_health(
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """Health check for Xero integration.

    Args:
        settings: Application settings.

    Returns:
        Health status.
    """
    return {
        "status": "healthy",
        "module": "xero_integration",
        "client_id_configured": bool(settings.xero.client_id),
        "redirect_uri": settings.xero.redirect_uri,
    }


# =============================================================================
# Data Sync Endpoints
# =============================================================================


# --- Multi-Client Sync Endpoints (must be before parameterized routes) ---


@router.post(
    "/sync/all",
    response_model=MultiClientSyncResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Sync all Xero connections",
    description="""
    Start phased sync for all active Xero connections in the tenant.

    **Required Permission**: `integration.manage`

    Skips connections that already have an active sync job.
    Staggers task dispatches by 2 seconds per connection to avoid
    Xero API rate limit spikes.

    Returns 202 with a batch summary including per-connection details.
    """,
    responses={
        202: {"description": "Multi-client sync initiated"},
    },
)
async def sync_all_connections(
    force_full: bool = False,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_MANAGE)),
    sync_service: XeroSyncService = Depends(get_sync_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> MultiClientSyncResponse:
    """Start phased sync for all active Xero connections.

    Skips connections with active syncs. Staggers dispatches for rate limit safety.

    Args:
        force_full: Force full sync even if incremental is available.
        current_user: Current authenticated user.
        sync_service: Sync service instance.
        audit_service: Audit service instance.

    Returns:
        MultiClientSyncResponse with batch summary and per-connection details.
    """
    result = await sync_service.start_multi_client_sync(
        tenant_id=current_user.tenant_id,
        force_full=force_full,
    )

    # Audit the multi-client sync initiation
    await audit_service.log(
        action="integration.xero.sync_all.started",
        actor_id=current_user.id,
        tenant_id=current_user.tenant_id,
        details={
            "batch_id": str(result.batch_id),
            "total_connections": result.total_connections,
            "jobs_queued": result.jobs_queued,
            "jobs_skipped": result.jobs_skipped,
            "force_full": force_full,
        },
    )

    return result


@router.get(
    "/sync/all/status",
    response_model=MultiClientSyncStatusResponse,
    summary="Get aggregate sync status for all connections",
    description="""
    Get aggregate sync status across all active connections for this tenant.

    **Required Permission**: `integration.read`

    Returns per-connection sync status including the latest job status,
    records processed, current sync phase, and last sync timestamp.
    """,
    responses={
        200: {"description": "Aggregate sync status"},
    },
)
async def get_all_sync_status(
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> MultiClientSyncStatusResponse:
    """Get aggregate sync status across all connections for this tenant.

    Args:
        current_user: Current authenticated user.
        session: Database session.

    Returns:
        MultiClientSyncStatusResponse with per-connection status summaries.
    """
    conn_repo = XeroConnectionRepository(session)
    job_repo = XeroSyncJobRepository(session)

    connections = await conn_repo.get_all_active(current_user.tenant_id)

    connection_statuses: list[MultiClientConnectionStatus] = []
    total_syncing = 0
    total_completed = 0
    total_failed = 0
    total_pending = 0

    for conn in connections:
        # Get latest job for this connection
        latest_job = await job_repo.get_latest_for_connection(conn.id)

        job_status = latest_job.status.value if latest_job else "no_sync"
        status_info = MultiClientConnectionStatus(
            connection_id=conn.id,
            organization_name=conn.organization_name or "Unknown",
            status=job_status,
            records_processed=latest_job.records_processed if latest_job else 0,
            sync_phase=latest_job.sync_phase if latest_job else None,
            last_sync_at=(conn.last_full_sync_at.isoformat() if conn.last_full_sync_at else None),
        )
        connection_statuses.append(status_info)

        if latest_job:
            if latest_job.status.value == "pending":
                total_pending += 1
            elif latest_job.status.value == "in_progress":
                total_syncing += 1
            elif latest_job.status.value == "completed":
                total_completed += 1
            elif latest_job.status.value == "failed":
                total_failed += 1

    return MultiClientSyncStatusResponse(
        total_connections=len(connections),
        syncing=total_syncing,
        completed=total_completed,
        failed=total_failed,
        pending=total_pending,
        connections=connection_statuses,
    )


# --- Per-Connection Sync Endpoints ---


@router.post(
    "/connections/{connection_id}/sync",
    response_model=XeroSyncJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Initiate Xero data sync",
    description="""
    Start a sync operation to fetch data from Xero.

    **Required Permission**: `integration.manage`

    Returns immediately with a job ID. Use the sync status endpoint
    to monitor progress.
    """,
    responses={
        202: {"description": "Sync job created"},
        400: {"description": "Connection inactive"},
        404: {"description": "Connection not found"},
        409: {"description": "Sync already in progress"},
        429: {"description": "Rate limit exceeded"},
    },
)
async def initiate_sync(
    connection_id: UUID,
    request: XeroSyncRequest | None = None,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_MANAGE)),
    sync_service: XeroSyncService = Depends(get_sync_service),
    audit_service: AuditService = Depends(get_audit_service),
    _sub: None = Depends(require_active_subscription),
) -> XeroSyncJobResponse:
    """Initiate a Xero data sync.

    Args:
        connection_id: The connection ID.
        request: Optional sync request with type and force_full flag.
        current_user: Current authenticated user.
        sync_service: Sync service instance.
        audit_service: Audit service instance.

    Returns:
        Created sync job details.
    """
    sync_type = request.sync_type if request else XeroSyncType.FULL
    force_full = request.force_full if request else False

    try:
        job = await sync_service.initiate_sync(
            connection_id=connection_id,
            sync_type=sync_type,
            force_full=force_full,
        )
    except XeroConnectionNotFoundExc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Connection not found"}},
        ) from None
    except XeroConnectionInactiveError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "CONNECTION_INACTIVE",
                    "message": "Connection is not active. Please reconnect to Xero.",
                }
            },
        ) from None
    except XeroSyncInProgressError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "SYNC_IN_PROGRESS",
                    "message": str(e),
                    "job_id": str(e.job_id) if e.job_id else None,
                }
            },
        ) from None
    except XeroRateLimitExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "code": "RATE_LIMITED",
                    "message": str(e),
                    "wait_seconds": e.wait_seconds,
                }
            },
            headers={"Retry-After": str(e.wait_seconds)},
        ) from None

    # Log sync initiation
    await audit_service.log_event(
        event_type="xero.sync.initiated",
        event_category="integration",
        actor_type="user",
        actor_id=current_user.user_id,
        actor_email=current_user.email,
        tenant_id=current_user.tenant_id,
        resource_type="xero_sync_job",
        resource_id=job.id,
        action="initiate",
        outcome="success",
        metadata={
            "connection_id": str(connection_id),
            "sync_type": sync_type.value,
            "force_full": force_full,
        },
    )

    return job


@router.get(
    "/connections/{connection_id}/sync/history",
    response_model=XeroSyncHistoryResponse,
    summary="Get sync history",
    description="""
    Get the history of sync jobs for a connection.

    **Required Permission**: `integration.read`
    """,
    responses={
        200: {"description": "Sync history"},
    },
)
async def get_sync_history(
    connection_id: UUID,
    limit: Annotated[int, Query(ge=1, le=100, description="Max jobs to return")] = 10,
    offset: Annotated[int, Query(ge=0, description="Number of jobs to skip")] = 0,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    sync_service: XeroSyncService = Depends(get_sync_service),
) -> XeroSyncHistoryResponse:
    """Get sync job history.

    Args:
        connection_id: The connection ID.
        limit: Max jobs to return.
        offset: Number of jobs to skip.
        current_user: Current authenticated user.
        sync_service: Sync service instance.

    Returns:
        Paginated sync job history.
    """
    return await sync_service.get_sync_history(
        connection_id=connection_id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/connections/{connection_id}/sync/stream",
    summary="Stream sync progress via SSE",
    description="""
    Server-Sent Events stream for real-time sync progress updates.

    Subscribes to Redis pub/sub channel for this connection and yields
    SSE-formatted events (sync_started, entity_progress, phase_complete,
    sync_complete, sync_failed, post_sync_progress).

    **Authentication**: Pass the auth token as a `token` query parameter
    since the browser EventSource API does not support custom headers.

    **Required Permission**: `integration.read`
    """,
    responses={
        200: {
            "description": "SSE stream of sync progress events",
            "content": {"text/event-stream": {}},
        },
        404: {"description": "Connection not found"},
    },
)
async def stream_sync_progress(
    connection_id: UUID,
    job_id: UUID | None = Query(None, description="Optional job ID to filter events"),
    token: str | None = Query(
        None, description="Auth token for SSE (EventSource cannot send headers)"
    ),
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """Stream real-time sync progress events via Server-Sent Events.

    Subscribes to Redis pub/sub channel for this connection and yields
    SSE-formatted events. The stream automatically closes on terminal
    events (sync_complete, sync_failed).

    Args:
        connection_id: The Xero connection ID.
        job_id: Optional job ID to filter events for a specific sync job.
        token: Auth token passed as query param (SSE/EventSource fallback).
        current_user: Current authenticated user (resolved from header or query token).
        session: Database session.

    Returns:
        StreamingResponse with SSE content type.
    """
    from .sync_progress import SyncProgressSubscriber

    # Verify the connection belongs to the user's tenant
    conn_repo = XeroConnectionRepository(session)
    connection = await conn_repo.get_by_id(connection_id)
    if not connection or connection.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Connection not found"}},
        )

    subscriber = SyncProgressSubscriber(connection_id, job_id=job_id)

    async def event_generator():
        """Async generator that yields SSE events from Redis pub/sub."""
        try:
            async for event in subscriber.listen():
                yield event
        finally:
            await subscriber.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/connections/{connection_id}/sync/{job_id}",
    response_model=XeroSyncJobResponse,
    summary="Get sync job status",
    description="""
    Get the status and progress of a sync job.

    **Required Permission**: `integration.read`
    """,
    responses={
        200: {"description": "Job status"},
        404: {"description": "Job not found"},
    },
)
async def get_sync_status(
    connection_id: UUID,
    job_id: UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    sync_service: XeroSyncService = Depends(get_sync_service),
) -> XeroSyncJobResponse:
    """Get sync job status.

    Args:
        connection_id: The connection ID.
        job_id: The sync job ID.
        current_user: Current authenticated user.
        sync_service: Sync service instance.

    Returns:
        Sync job details.
    """
    try:
        return await sync_service.get_sync_status(job_id)
    except XeroSyncJobNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Sync job not found"}},
        ) from None


@router.get(
    "/connections/{connection_id}/sync/{job_id}/entities",
    response_model=list[EntityProgressResponse],
    summary="Get per-entity sync progress",
    description="""
    Get per-entity progress records for a sync job.

    Returns the sync status for each entity type (contacts, invoices,
    bank_transactions, etc.) within the specified job, including record
    counts and timing information.

    **Required Permission**: `integration.read`
    """,
    responses={
        200: {"description": "Entity progress list"},
        404: {"description": "Job not found"},
    },
)
async def get_entity_progress(
    connection_id: UUID,
    job_id: UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> list[EntityProgressResponse]:
    """Get per-entity sync progress for a job.

    Args:
        connection_id: The connection ID.
        job_id: The sync job ID.
        current_user: Current authenticated user.
        session: Database session.

    Returns:
        List of entity progress records for the job.
    """
    # Verify the job exists
    job_repo = XeroSyncJobRepository(session)
    job = await job_repo.get_by_id(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Sync job not found"}},
        )

    # Fetch entity progress records
    entity_progress_repo = XeroSyncEntityProgressRepository(session)
    progress_records = await entity_progress_repo.get_by_job_id(job_id)

    return [EntityProgressResponse.model_validate(record) for record in progress_records]


@router.get(
    "/connections/{connection_id}/sync/{job_id}/status",
    response_model=SyncStatusResponse,
    summary="Get enhanced sync status",
    description="""
    Get enhanced sync status with phase info, per-entity progress,
    aggregate record counts, and post-sync task status.

    **Required Permission**: `integration.read`
    """,
    responses={
        200: {"description": "Enhanced sync status"},
        404: {"description": "Job not found"},
    },
)
async def get_enhanced_sync_status(
    connection_id: UUID,
    job_id: UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    sync_service: XeroSyncService = Depends(get_sync_service),
    session: AsyncSession = Depends(get_db_session),
) -> SyncStatusResponse:
    """Get enhanced sync status with phase and entity details.

    Returns the job status along with per-entity progress, aggregate
    record counts across all entities, and post-sync task status.

    Args:
        connection_id: The connection ID.
        job_id: The sync job ID.
        current_user: Current authenticated user.
        sync_service: Sync service instance.
        session: Database session.

    Returns:
        Enhanced sync status with phase, entity, and post-sync details.
    """
    # Get the job via service (validates existence)
    try:
        job_response = await sync_service.get_sync_status(job_id)
    except XeroSyncJobNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Sync job not found"}},
        ) from None

    # Fetch per-entity progress records
    entity_progress_repo = XeroSyncEntityProgressRepository(session)
    progress_records = await entity_progress_repo.get_by_job_id(job_id)
    entities = [EntityProgressResponse.model_validate(record) for record in progress_records]

    # Aggregate record counts from entity progress
    total_processed = sum(e.records_processed for e in entities)
    total_created = sum(e.records_created for e in entities)
    total_updated = sum(e.records_updated for e in entities)
    total_failed = sum(e.records_failed for e in entities)

    # Fetch post-sync task records
    post_sync_repo = PostSyncTaskRepository(session)
    post_sync_records = await post_sync_repo.get_by_job_id(job_id)
    post_sync_tasks = [PostSyncTaskResponse.model_validate(record) for record in post_sync_records]

    return SyncStatusResponse(
        job=job_response,
        entities=entities,
        phase=job_response.sync_phase,
        total_phases=3,
        records_processed=total_processed,
        records_created=total_created,
        records_updated=total_updated,
        records_failed=total_failed,
        post_sync_tasks=post_sync_tasks,
    )


@router.delete(
    "/connections/{connection_id}/sync/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel sync job",
    description="""
    Cancel a pending or in-progress sync job.

    **Required Permission**: `integration.manage`
    """,
    responses={
        204: {"description": "Job cancelled"},
        404: {"description": "Job not found"},
    },
)
async def cancel_sync(
    connection_id: UUID,
    job_id: UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_MANAGE)),
    sync_service: XeroSyncService = Depends(get_sync_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> None:
    """Cancel a sync job.

    Args:
        connection_id: The connection ID.
        job_id: The sync job ID.
        current_user: Current authenticated user.
        sync_service: Sync service instance.
        audit_service: Audit service instance.
    """
    try:
        await sync_service.cancel_sync(job_id)
    except XeroSyncJobNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Sync job not found"}},
        ) from None

    # Log cancellation
    await audit_service.log_event(
        event_type="xero.sync.cancelled",
        event_category="integration",
        actor_type="user",
        actor_id=current_user.user_id,
        actor_email=current_user.email,
        tenant_id=current_user.tenant_id,
        resource_type="xero_sync_job",
        resource_id=job_id,
        action="cancel",
        outcome="success",
        metadata={
            "connection_id": str(connection_id),
        },
    )


# =============================================================================
# Synced Entity Endpoints
# =============================================================================


@router.get(
    "/connections/{connection_id}/clients",
    response_model=XeroClientListResponse,
    summary="List synced clients",
    description="""
    List Xero contacts synced for a connection.

    **Required Permission**: `integration.read`
    """,
    responses={
        200: {"description": "Client list"},
    },
)
async def list_clients(
    connection_id: UUID,
    is_active: Annotated[bool | None, Query(description="Filter by active status")] = None,
    search: Annotated[str | None, Query(description="Search by name")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Max clients to return")] = 50,
    offset: Annotated[int, Query(ge=0, description="Number of clients to skip")] = 0,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    client_repo: XeroClientRepository = Depends(get_client_repo),
) -> XeroClientListResponse:
    """List synced clients.

    Args:
        connection_id: The connection ID.
        is_active: Filter by active status.
        search: Search by name.
        limit: Max clients to return.
        offset: Number of clients to skip.
        current_user: Current authenticated user.
        client_repo: Client repository instance.

    Returns:
        Paginated client list.
    """
    clients, total = await client_repo.list_by_connection(
        connection_id=connection_id,
        is_active=is_active,
        search=search,
        limit=limit,
        offset=offset,
    )

    return XeroClientListResponse(
        clients=[XeroClientResponse.model_validate(c) for c in clients],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/connections/{connection_id}/clients/{client_id}",
    response_model=XeroClientResponse,
    summary="Get synced client",
    description="""
    Get details for a specific synced client.

    **Required Permission**: `integration.read`
    """,
    responses={
        200: {"description": "Client details"},
        404: {"description": "Client not found"},
    },
)
async def get_client(
    connection_id: UUID,
    client_id: UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    client_repo: XeroClientRepository = Depends(get_client_repo),
) -> XeroClientResponse:
    """Get synced client details.

    Args:
        connection_id: The connection ID.
        client_id: The client ID.
        current_user: Current authenticated user.
        client_repo: Client repository instance.

    Returns:
        Client details.
    """
    client = await client_repo.get_by_id(client_id)
    if client is None or client.connection_id != connection_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Client not found"}},
        )

    return XeroClientResponse.model_validate(client)


@router.get(
    "/connections/{connection_id}/invoices",
    response_model=XeroInvoiceListResponse,
    summary="List synced invoices",
    description="""
    List Xero invoices synced for a connection.

    **Required Permission**: `integration.read`
    """,
    responses={
        200: {"description": "Invoice list"},
    },
)
async def list_invoices(
    connection_id: UUID,
    client_id: Annotated[UUID | None, Query(description="Filter by client")] = None,
    invoice_type: Annotated[str | None, Query(description="Filter by type (ACCREC/ACCPAY)")] = None,
    invoice_status: Annotated[
        str | None, Query(alias="status", description="Filter by status")
    ] = None,
    date_from: Annotated[datetime | None, Query(description="Filter by issue date from")] = None,
    date_to: Annotated[datetime | None, Query(description="Filter by issue date to")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Max invoices to return")] = 50,
    offset: Annotated[int, Query(ge=0, description="Number of invoices to skip")] = 0,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    invoice_repo: XeroInvoiceRepository = Depends(get_invoice_repo),
) -> XeroInvoiceListResponse:
    """List synced invoices.

    Args:
        connection_id: The connection ID.
        client_id: Filter by client.
        invoice_type: Filter by type.
        invoice_status: Filter by status.
        date_from: Filter by issue date from.
        date_to: Filter by issue date to.
        limit: Max invoices to return.
        offset: Number of invoices to skip.
        current_user: Current authenticated user.
        invoice_repo: Invoice repository instance.

    Returns:
        Paginated invoice list.
    """
    invoices, total = await invoice_repo.list_by_connection(
        connection_id=connection_id,
        client_id=client_id,
        invoice_type=invoice_type,
        status=invoice_status,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )

    return XeroInvoiceListResponse(
        invoices=[XeroInvoiceResponse.model_validate(i) for i in invoices],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/connections/{connection_id}/invoices/{invoice_id}",
    response_model=XeroInvoiceResponse,
    summary="Get synced invoice",
    description="""
    Get details for a specific synced invoice.

    **Required Permission**: `integration.read`
    """,
    responses={
        200: {"description": "Invoice details"},
        404: {"description": "Invoice not found"},
    },
)
async def get_invoice(
    connection_id: UUID,
    invoice_id: UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    invoice_repo: XeroInvoiceRepository = Depends(get_invoice_repo),
) -> XeroInvoiceResponse:
    """Get synced invoice details.

    Args:
        connection_id: The connection ID.
        invoice_id: The invoice ID.
        current_user: Current authenticated user.
        invoice_repo: Invoice repository instance.

    Returns:
        Invoice details.
    """
    invoice = await invoice_repo.get_by_id(invoice_id)
    if invoice is None or invoice.connection_id != connection_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Invoice not found"}},
        )

    return XeroInvoiceResponse.model_validate(invoice)


@router.get(
    "/connections/{connection_id}/transactions",
    response_model=XeroBankTransactionListResponse,
    summary="List synced bank transactions",
    description="""
    List Xero bank transactions synced for a connection.

    **Required Permission**: `integration.read`
    """,
    responses={
        200: {"description": "Transaction list"},
    },
)
async def list_transactions(
    connection_id: UUID,
    client_id: Annotated[UUID | None, Query(description="Filter by client")] = None,
    transaction_type: Annotated[str | None, Query(description="Filter by type")] = None,
    date_from: Annotated[datetime | None, Query(description="Filter by date from")] = None,
    date_to: Annotated[datetime | None, Query(description="Filter by date to")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Max transactions to return")] = 50,
    offset: Annotated[int, Query(ge=0, description="Number of transactions to skip")] = 0,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    transaction_repo: XeroBankTransactionRepository = Depends(get_transaction_repo),
) -> XeroBankTransactionListResponse:
    """List synced bank transactions.

    Args:
        connection_id: The connection ID.
        client_id: Filter by client.
        transaction_type: Filter by type.
        date_from: Filter by date from.
        date_to: Filter by date to.
        limit: Max transactions to return.
        offset: Number of transactions to skip.
        current_user: Current authenticated user.
        transaction_repo: Transaction repository instance.

    Returns:
        Paginated transaction list.
    """
    transactions, total = await transaction_repo.list_by_connection(
        connection_id=connection_id,
        client_id=client_id,
        transaction_type=transaction_type,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )

    return XeroBankTransactionListResponse(
        transactions=[XeroBankTransactionResponse.model_validate(t) for t in transactions],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/connections/{connection_id}/transactions/{transaction_id}",
    response_model=XeroBankTransactionResponse,
    summary="Get synced bank transaction",
    description="""
    Get details for a specific synced bank transaction.

    **Required Permission**: `integration.read`
    """,
    responses={
        200: {"description": "Transaction details"},
        404: {"description": "Transaction not found"},
    },
)
async def get_transaction(
    connection_id: UUID,
    transaction_id: UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    transaction_repo: XeroBankTransactionRepository = Depends(get_transaction_repo),
) -> XeroBankTransactionResponse:
    """Get synced bank transaction details.

    Args:
        connection_id: The connection ID.
        transaction_id: The transaction ID.
        current_user: Current authenticated user.
        transaction_repo: Transaction repository instance.

    Returns:
        Transaction details.
    """
    transaction = await transaction_repo.get_by_id(transaction_id)
    if transaction is None or transaction.connection_id != connection_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Transaction not found"}},
        )

    return XeroBankTransactionResponse.model_validate(transaction)


@router.get(
    "/connections/{connection_id}/accounts",
    response_model=XeroAccountListResponse,
    summary="List synced chart of accounts",
    description="""
    List Xero accounts synced for a connection.

    **Required Permission**: `integration.read`
    """,
    responses={
        200: {"description": "Account list"},
    },
)
async def list_accounts(
    connection_id: UUID,
    is_active: Annotated[bool | None, Query(description="Filter by active status")] = None,
    is_bas_relevant: Annotated[bool | None, Query(description="Filter by BAS relevance")] = None,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    account_repo: XeroAccountRepository = Depends(get_account_repo),
) -> XeroAccountListResponse:
    """List synced chart of accounts.

    Args:
        connection_id: The connection ID.
        is_active: Filter by active status.
        is_bas_relevant: Filter by BAS relevance.
        current_user: Current authenticated user.
        account_repo: Account repository instance.

    Returns:
        Account list.
    """
    accounts = await account_repo.list_by_connection(
        connection_id=connection_id,
        is_active=is_active,
        is_bas_relevant=is_bas_relevant,
    )

    return XeroAccountListResponse(
        accounts=[XeroAccountResponse.model_validate(a) for a in accounts],
        total=len(accounts),
    )


# =============================================================================
# Client View Endpoints (Spec 005)
# =============================================================================


@router.get(
    "/clients",
    response_model=XeroClientListResponse,
    summary="List all clients across connections",
    description="""
    List all Xero clients/contacts for the current tenant across all connections.

    **Required Permission**: `integration.read`

    This endpoint provides a unified view of all clients regardless of which
    Xero organization they belong to.
    """,
    responses={
        200: {"description": "Client list"},
    },
)
async def list_all_clients(
    search: Annotated[str | None, Query(description="Search by name or email")] = None,
    contact_type: Annotated[
        str | None, Query(description="Filter by contact type (CUSTOMER, SUPPLIER)")
    ] = None,
    is_active: Annotated[bool | None, Query(description="Filter by active status")] = None,
    sort_by: Annotated[
        str, Query(description="Sort by field (name, contact_type, created_at)")
    ] = "name",
    sort_order: Annotated[str, Query(description="Sort order (asc, desc)")] = "asc",
    limit: Annotated[int, Query(ge=1, le=100, description="Max clients to return")] = 25,
    offset: Annotated[int, Query(ge=0, description="Number of clients to skip")] = 0,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    client_service: XeroClientService = Depends(get_client_service),
) -> XeroClientListResponse:
    """List all clients across Xero connections.

    Args:
        search: Search term for name/email.
        contact_type: Filter by contact type.
        is_active: Filter by active status.
        sort_by: Field to sort by.
        sort_order: Sort direction.
        limit: Max clients to return.
        offset: Number of clients to skip.
        current_user: Current authenticated user.
        client_service: Client service instance.

    Returns:
        Paginated client list.
    """
    return await client_service.list_clients(
        search=search,
        contact_type=contact_type,
        is_active=is_active,
        sort_by=sort_by,  # type: ignore[arg-type]
        sort_order=sort_order,  # type: ignore[arg-type]
        limit=limit,
        offset=offset,
    )


@router.get(
    "/clients/{client_id}",
    response_model=XeroClientDetailResponse,
    summary="Get client details",
    description="""
    Get detailed information for a specific client including connection metadata.

    **Required Permission**: `integration.read`
    """,
    responses={
        200: {"description": "Client details"},
        404: {"description": "Client not found"},
    },
)
async def get_client_detail(
    client_id: UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    client_service: XeroClientService = Depends(get_client_service),
) -> XeroClientDetailResponse:
    """Get client details with connection metadata.

    Args:
        client_id: The client ID.
        current_user: Current authenticated user.
        client_service: Client service instance.

    Returns:
        Client details with connection info.
    """
    try:
        return await client_service.get_client_detail(client_id)
    except XeroClientNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Client not found"}},
        ) from None


@router.get(
    "/clients/{client_id}/invoices",
    response_model=XeroInvoiceListResponse,
    summary="Get client invoices",
    description="""
    Get invoices for a specific client with optional date and type filtering.

    **Required Permission**: `integration.read`
    """,
    responses={
        200: {"description": "Invoice list"},
        404: {"description": "Client not found"},
    },
)
async def get_client_invoices(
    client_id: UUID,
    from_date: Annotated[date | None, Query(description="Filter by issue date from")] = None,
    to_date: Annotated[date | None, Query(description="Filter by issue date to")] = None,
    invoice_status: Annotated[str | None, Query(description="Filter by status")] = None,
    invoice_type: Annotated[
        str | None, Query(description="Filter by type (ACCREC, ACCPAY)")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Max invoices to return")] = 25,
    offset: Annotated[int, Query(ge=0, description="Number of invoices to skip")] = 0,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    client_service: XeroClientService = Depends(get_client_service),
) -> XeroInvoiceListResponse:
    """Get invoices for a client.

    Args:
        client_id: The client ID.
        from_date: Filter by issue date from.
        to_date: Filter by issue date to.
        invoice_status: Filter by status.
        invoice_type: Filter by type.
        limit: Max invoices to return.
        offset: Number of invoices to skip.
        current_user: Current authenticated user.
        client_service: Client service instance.

    Returns:
        Paginated invoice list.
    """
    try:
        return await client_service.get_client_invoices(
            client_id=client_id,
            from_date=from_date,
            to_date=to_date,
            status=invoice_status,
            invoice_type=invoice_type,
            limit=limit,
            offset=offset,
        )
    except XeroClientNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Client not found"}},
        ) from None


@router.get(
    "/clients/{client_id}/transactions",
    response_model=XeroBankTransactionListResponse,
    summary="Get client transactions",
    description="""
    Get bank transactions for a specific client with optional date filtering.

    **Required Permission**: `integration.read`
    """,
    responses={
        200: {"description": "Transaction list"},
        404: {"description": "Client not found"},
    },
)
async def get_client_transactions(
    client_id: UUID,
    from_date: Annotated[date | None, Query(description="Filter by transaction date from")] = None,
    to_date: Annotated[date | None, Query(description="Filter by transaction date to")] = None,
    transaction_type: Annotated[str | None, Query(description="Filter by transaction type")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Max transactions to return")] = 25,
    offset: Annotated[int, Query(ge=0, description="Number of transactions to skip")] = 0,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    client_service: XeroClientService = Depends(get_client_service),
) -> XeroBankTransactionListResponse:
    """Get transactions for a client.

    Args:
        client_id: The client ID.
        from_date: Filter by transaction date from.
        to_date: Filter by transaction date to.
        transaction_type: Filter by type.
        limit: Max transactions to return.
        offset: Number of transactions to skip.
        current_user: Current authenticated user.
        client_service: Client service instance.

    Returns:
        Paginated transaction list.
    """
    try:
        return await client_service.get_client_transactions(
            client_id=client_id,
            from_date=from_date,
            to_date=to_date,
            transaction_type=transaction_type,
            limit=limit,
            offset=offset,
        )
    except XeroClientNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Client not found"}},
        ) from None


@router.get(
    "/clients/{client_id}/summary",
    response_model=ClientFinancialSummaryResponse,
    summary="Get client financial summary",
    description="""
    Get BAS-relevant financial summary for a client in a specific quarter.

    **Required Permission**: `integration.read`

    The summary includes:
    - Total sales and GST collected
    - Total purchases and GST paid
    - Invoice and transaction counts
    - Net GST position
    """,
    responses={
        200: {"description": "Financial summary"},
        400: {"description": "Invalid quarter"},
        404: {"description": "Client not found"},
    },
)
async def get_client_summary(
    client_id: UUID,
    quarter: Annotated[int, Query(ge=1, le=4, description="Quarter number (1-4)")] = 1,
    fy_year: Annotated[int, Query(ge=2020, le=2100, description="Financial year")] = 2025,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    client_service: XeroClientService = Depends(get_client_service),
) -> ClientFinancialSummaryResponse:
    """Get financial summary for a client in a quarter.

    Args:
        client_id: The client ID.
        quarter: Quarter number (1-4).
        fy_year: Financial year (e.g., 2025).
        current_user: Current authenticated user.
        client_service: Client service instance.

    Returns:
        Financial summary for the quarter.
    """
    try:
        return await client_service.get_client_financial_summary(
            client_id=client_id,
            quarter=quarter,
            fy_year=fy_year,
        )
    except XeroClientNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Client not found"}},
        ) from None
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_QUARTER", "message": str(e)}},
        ) from None


@router.get(
    "/quarters",
    response_model=AvailableQuartersResponse,
    summary="Get available quarters",
    description="""
    Get a list of available Australian Financial Year quarters for selection.

    **Required Permission**: `integration.read`

    Returns the current quarter plus previous quarters, and optionally
    the next quarter if near the end of the current quarter.
    """,
    responses={
        200: {"description": "Available quarters"},
    },
)
async def get_available_quarters(
    num_previous: Annotated[int, Query(ge=0, le=12, description="Number of previous quarters")] = 4,
    include_next: Annotated[
        bool, Query(description="Include next quarter if near end of current")
    ] = True,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    client_service: XeroClientService = Depends(get_client_service),
) -> AvailableQuartersResponse:
    """Get available quarters for selection.

    Args:
        num_previous: Number of previous quarters to include.
        include_next: Whether to include next quarter.
        current_user: Current authenticated user.
        client_service: Client service instance.

    Returns:
        List of available quarters.
    """
    return client_service.get_available_quarters(
        num_previous=num_previous,
        include_next=include_next,
    )


# =============================================================================
# Payroll Endpoints (Spec 007)
# =============================================================================


@router.get(
    "/connections/{connection_id}/payroll/summary",
    response_model=XeroPayrollSummaryResponse,
    summary="Get payroll summary for BAS",
    description="""
    Get payroll summary data for BAS PAYG withholding section.

    **Required Permission**: `integration.read`

    Returns aggregated payroll data for a date range:
    - W1: Total wages
    - W2/4: Total tax withheld
    - Total superannuation
    - Pay run count
    - Employee count
    """,
    responses={
        200: {"description": "Payroll summary"},
        404: {"description": "Connection not found"},
    },
)
async def get_payroll_summary(
    connection_id: UUID,
    from_date: Annotated[date, Query(description="Start date for summary")],
    to_date: Annotated[date, Query(description="End date for summary")],
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    payroll_service=Depends(get_payroll_service),
) -> XeroPayrollSummaryResponse:
    """Get payroll summary for BAS.

    Args:
        connection_id: The connection ID.
        from_date: Start date for summary.
        to_date: End date for summary.
        current_user: Current authenticated user.
        payroll_service: Payroll service instance.

    Returns:
        Payroll summary for the date range.
    """
    summary = await payroll_service.get_payroll_summary(
        connection_id=connection_id,
        from_date=from_date,
        to_date=to_date,
    )
    return XeroPayrollSummaryResponse(**summary)


@router.get(
    "/connections/{connection_id}/payroll/employees",
    response_model=XeroEmployeeListResponse,
    summary="List synced employees",
    description="""
    List employees synced from Xero Payroll.

    **Required Permission**: `integration.read`
    """,
    responses={
        200: {"description": "Employee list"},
        404: {"description": "Connection not found"},
    },
)
async def list_employees(
    connection_id: UUID,
    status: Annotated[
        str | None, Query(description="Filter by status (ACTIVE, TERMINATED)")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Max employees to return")] = 25,
    offset: Annotated[int, Query(ge=0, description="Number of employees to skip")] = 0,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    payroll_service=Depends(get_payroll_service),
) -> XeroEmployeeListResponse:
    """List synced employees.

    Args:
        connection_id: The connection ID.
        status: Filter by status.
        limit: Max employees to return.
        offset: Number of employees to skip.
        current_user: Current authenticated user.
        payroll_service: Payroll service instance.

    Returns:
        Paginated employee list.
    """
    page = (offset // limit) + 1 if limit > 0 else 1
    employees, total = await payroll_service.get_employees(
        connection_id=connection_id,
        status=status,
        page=page,
        limit=limit,
    )

    return XeroEmployeeListResponse(
        employees=[XeroEmployeeResponse(**e) for e in employees],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/connections/{connection_id}/payroll/pay-runs",
    response_model=XeroPayRunListResponse,
    summary="List synced pay runs",
    description="""
    List pay runs synced from Xero Payroll.

    **Required Permission**: `integration.read`
    """,
    responses={
        200: {"description": "Pay run list"},
        404: {"description": "Connection not found"},
    },
)
async def list_pay_runs(
    connection_id: UUID,
    status: Annotated[str | None, Query(description="Filter by status (DRAFT, POSTED)")] = None,
    from_date: Annotated[date | None, Query(description="Filter by payment date from")] = None,
    to_date: Annotated[date | None, Query(description="Filter by payment date to")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Max pay runs to return")] = 20,
    offset: Annotated[int, Query(ge=0, description="Number of pay runs to skip")] = 0,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    payroll_service=Depends(get_payroll_service),
) -> XeroPayRunListResponse:
    """List synced pay runs.

    Args:
        connection_id: The connection ID.
        status: Filter by status.
        from_date: Filter by payment date from.
        to_date: Filter by payment date to.
        limit: Max pay runs to return.
        offset: Number of pay runs to skip.
        current_user: Current authenticated user.
        payroll_service: Payroll service instance.

    Returns:
        Paginated pay run list.
    """
    page = (offset // limit) + 1 if limit > 0 else 1
    pay_runs, total = await payroll_service.get_pay_runs(
        connection_id=connection_id,
        status=status,
        from_date=from_date,
        to_date=to_date,
        page=page,
        limit=limit,
    )

    return XeroPayRunListResponse(
        pay_runs=[XeroPayRunResponse(**pr) for pr in pay_runs],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/connections/{connection_id}/payroll/sync",
    response_model=XeroPayrollSyncResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger payroll sync",
    description="""
    Trigger a payroll data sync from Xero.

    **Required Permission**: `integration.manage`

    Syncs employees and pay runs from Xero Payroll API.
    Only available for connections with payroll access.
    """,
    responses={
        202: {"description": "Sync initiated"},
        400: {"description": "Connection does not have payroll access"},
        404: {"description": "Connection not found"},
    },
)
async def trigger_payroll_sync(
    connection_id: UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_MANAGE)),
    payroll_service=Depends(get_payroll_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> XeroPayrollSyncResponse:
    """Trigger payroll sync.

    Args:
        connection_id: The connection ID.
        current_user: Current authenticated user.
        payroll_service: Payroll service instance.
        audit_service: Audit service instance.

    Returns:
        Sync result.
    """
    from .payroll_service import XeroPayrollSyncError

    try:
        result = await payroll_service.sync_payroll(connection_id)
    except XeroPayrollSyncError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "PAYROLL_SYNC_ERROR", "message": str(e)}},
        ) from None

    # Log sync
    await audit_service.log_event(
        event_type="xero.payroll.sync",
        event_category="integration",
        actor_type="user",
        actor_id=current_user.user_id,
        actor_email=current_user.email,
        tenant_id=current_user.tenant_id,
        resource_type="xero_connection",
        resource_id=connection_id,
        action="sync_payroll",
        outcome="success" if result.get("status") != "failed" else "failure",
        metadata={
            "employees_synced": result.get("employees_synced", 0),
            "pay_runs_synced": result.get("pay_runs_synced", 0),
            "status": result.get("status"),
        },
    )

    return XeroPayrollSyncResponse(
        connection_id=connection_id,
        status=result.get("status", "complete"),
        employees_synced=result.get("employees_synced", 0),
        pay_runs_synced=result.get("pay_runs_synced", 0),
        reason=result.get("reason"),
    )


# =============================================================================
# Organisation Profile Sync
# =============================================================================


@router.post(
    "/connections/{connection_id}/sync-profile",
    status_code=status.HTTP_200_OK,
    summary="Sync organisation profile",
    description="""
    Sync organisation details from Xero and populate the client AI profile.

    **Required Permission**: `integration.manage`

    Fetches organisation type, ABN, GST status from Xero Organisation API
    and creates/updates the ClientAIProfile for client-context chat.
    """,
    responses={
        200: {"description": "Profile synced successfully"},
        404: {"description": "Connection not found"},
    },
)
async def sync_organisation_profile(
    connection_id: UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_MANAGE)),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Sync organisation profile from Xero.

    Args:
        connection_id: The connection ID.
        current_user: Current authenticated user.
        session: Database session.
        settings: Application settings.

    Returns:
        Profile sync result.
    """
    data_service = XeroDataService(session, settings)

    org_data = await data_service.sync_organisation_profile(connection_id)

    if org_data:
        return {
            "status": "success",
            "connection_id": str(connection_id),
            "organisation_type": org_data.get("OrganisationType"),
            "tax_number": org_data.get("TaxNumber"),
            "gst_registered": bool(org_data.get("TaxNumber") and org_data.get("SalesTaxBasis")),
        }
    else:
        return {
            "status": "no_data",
            "connection_id": str(connection_id),
            "message": "Could not fetch organisation details from Xero",
        }


# =============================================================================
# Report Endpoints (Spec 023)
# =============================================================================


@router.get(
    "/connections/{connection_id}/reports",
    response_model=ReportListResponse,
    summary="List available reports",
    description="List all available report types and their sync status for a connection.",
)
async def list_reports(
    connection_id: UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.CLIENT_READ)),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> ReportListResponse:
    """List available reports for a Xero connection.

    Returns the status of all report types (P&L, Balance Sheet, etc.)
    including when last synced and available periods.

    Args:
        connection_id: The Xero connection ID.
        current_user: Current authenticated user.
        session: Database session.
        settings: Application settings.

    Returns:
        ReportListResponse with report statuses.

    Raises:
        HTTPException 404: Connection not found.
    """
    report_service = XeroReportService(session, settings)

    try:
        statuses = await report_service.list_report_statuses(connection_id)

        # Get connection for org name
        from .repository import XeroConnectionRepository

        connection_repo = XeroConnectionRepository(session)
        connection = await connection_repo.get_by_id(connection_id)

        return ReportListResponse(
            connection_id=connection_id,
            organization_name=connection.organization_name if connection else "Unknown",
            reports=[ReportStatusItem(**s) for s in statuses],
        )
    except XeroConnectionNotFoundExc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection {connection_id} not found",
        )


@router.get(
    "/connections/{connection_id}/reports/{report_type}",
    response_model=ReportResponse,
    summary="Get a report",
    description="Get a specific report by type and period. Returns cached data if available.",
)
async def get_report(
    connection_id: UUID,
    report_type: str,
    period: Annotated[
        str,
        Query(description="Period key: 'current', 'YYYY-FY', 'YYYY-QN', 'YYYY-MM', 'YYYY-MM-DD'"),
    ] = "current",
    force_refresh: Annotated[
        bool,
        Query(description="Force refresh from Xero, bypassing cache"),
    ] = False,
    current_user: PracticeUser = Depends(require_permission(Permission.CLIENT_READ)),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> ReportResponse:
    """Get a specific Xero report.

    Returns cached data if available and valid. Use force_refresh=true
    to fetch fresh data from Xero (subject to throttling).

    Args:
        connection_id: The Xero connection ID.
        report_type: Report type (profit_and_loss, balance_sheet, etc.).
        period: Period key (default: current).
        force_refresh: Bypass cache and fetch fresh data.
        current_user: Current authenticated user.
        session: Database session.
        settings: Application settings.

    Returns:
        ReportResponse with report data.

    Raises:
        HTTPException 404: Connection not found.
        HTTPException 400: Invalid report type.
    """
    report_service = XeroReportService(session, settings)

    # Generate period key for 'current'
    if period == "current":
        now = datetime.now()
        period = f"{now.year}-{now.month:02d}"

    try:
        report_data = await report_service.get_report(
            connection_id=connection_id,
            report_type=report_type,
            period_key=period,
            force_refresh=force_refresh,
        )
        return ReportResponse(**report_data)
    except XeroConnectionNotFoundExc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection {connection_id} not found",
        )
    except XeroConnectionInactiveError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connection is inactive. Please reconnect Xero.",
        )
    except XeroOAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Xero authentication failed. Please reconnect: {e}",
        )
    except XeroClientError as e:
        # Handle Xero API errors (e.g., aged reports require contactId)
        error_msg = str(e)
        if "contactId is mandatory" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="This report requires per-contact data which is not yet supported. "
                "Xero's API requires individual contact lookups for aged reports.",
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Xero API error: {error_msg}",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/connections/{connection_id}/reports/{report_type}/refresh",
    response_model=ReportResponse,
    responses={
        429: {"model": RateLimitResponse, "description": "Rate limit exceeded"},
    },
    summary="Refresh a report",
    description="Request a fresh sync of a specific report from Xero.",
)
async def refresh_report(
    connection_id: UUID,
    report_type: str,
    request: RefreshReportRequest,
    current_user: PracticeUser = Depends(require_permission(Permission.CLIENT_READ)),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> ReportResponse:
    """Request a fresh sync of a report from Xero.

    Enforces throttling (max 1 refresh per 5 minutes per report type).
    If throttled, returns 429 with retry_after_seconds.

    Args:
        connection_id: The Xero connection ID.
        report_type: Report type to refresh.
        request: Refresh request with period_key.
        current_user: Current authenticated user.
        session: Database session.
        settings: Application settings.

    Returns:
        ReportResponse with fresh report data.

    Raises:
        HTTPException 429: Rate limit exceeded.
        HTTPException 404: Connection not found.
    """
    report_service = XeroReportService(session, settings)

    try:
        report_data = await report_service.refresh_report(
            connection_id=connection_id,
            report_type=report_type,
            period_key=request.period_key,
            user_id=current_user.id,
        )
        return ReportResponse(**report_data)
    except XeroRateLimitExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "rate_limited",
                "message": str(e),
                "retry_after_seconds": e.wait_seconds,
                "last_sync_at": None,
            },
            headers={"Retry-After": str(e.wait_seconds)},
        )
    except XeroConnectionNotFoundExc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection {connection_id} not found",
        )
    except XeroConnectionInactiveError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connection is inactive. Please reconnect Xero.",
        )
    except XeroOAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Xero authentication failed. Please reconnect: {e}",
        )
    except XeroClientError as e:
        # Handle Xero API errors (e.g., aged reports require contactId)
        error_msg = str(e)
        if "contactId is mandatory" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="This report requires per-contact data which is not yet supported. "
                "Xero's API requires individual contact lookups for aged reports.",
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Xero API error: {error_msg}",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# =============================================================================
# Report Sync Endpoints (Spec 023 - Phase 10)
# =============================================================================


@router.post(
    "/connections/{connection_id}/reports/sync",
    response_model=SyncJobResponse,
    summary="Trigger full report sync",
    description="Queue a background sync job for all report types.",
)
async def trigger_report_sync(
    connection_id: UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.CLIENT_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> SyncJobResponse:
    """Trigger a full sync of all reports for a client.

    Queues a Celery task to sync all report types from Xero.
    Returns immediately with the job ID for status tracking.

    Args:
        connection_id: The Xero connection ID.
        current_user: Current authenticated user.
        session: Database session.

    Returns:
        SyncJobResponse with job ID for status tracking.

    Raises:
        HTTPException 404: Connection not found.
    """
    from app.modules.integrations.xero.models import XeroReportSyncJob
    from app.modules.integrations.xero.repository import XeroConnectionRepository
    from app.tasks.reports import sync_reports_for_connection

    # Validate connection exists
    conn_repo = XeroConnectionRepository(session)
    connection = await conn_repo.get_by_id(connection_id)
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connection {connection_id} not found",
        )

    if not connection.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connection is inactive. Please reconnect Xero.",
        )

    # Create sync job record
    sync_job = XeroReportSyncJob(
        tenant_id=current_user.tenant_id,
        connection_id=connection_id,
        report_type="all",
        status="pending",
        triggered_by="manual",
        user_id=current_user.id,
    )
    session.add(sync_job)
    await session.commit()
    await session.refresh(sync_job)

    # Queue Celery task
    sync_reports_for_connection.delay(
        connection_id=str(connection_id),
        tenant_id=str(current_user.tenant_id),
        triggered_by="manual",
    )

    return SyncJobResponse(
        id=sync_job.id,
        report_type="all",
        status="pending",
        started_at=None,
        triggered_by="manual",
    )


@router.get(
    "/connections/{connection_id}/reports/sync/{job_id}",
    response_model=SyncJobResponse,
    summary="Get report sync job status",
    description="Check the status of a report sync job.",
)
async def get_report_sync_status(
    connection_id: UUID,
    job_id: UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.CLIENT_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> SyncJobResponse:
    """Get the status of a report sync job.

    Args:
        connection_id: The Xero connection ID.
        job_id: The sync job ID.
        current_user: Current authenticated user.
        session: Database session.

    Returns:
        SyncJobResponse with current job status.

    Raises:
        HTTPException 404: Job not found.
    """
    from sqlalchemy import select

    from app.modules.integrations.xero.models import XeroReportSyncJob

    # Query job
    result = await session.execute(
        select(XeroReportSyncJob).where(
            XeroReportSyncJob.id == job_id,
            XeroReportSyncJob.connection_id == connection_id,
            XeroReportSyncJob.tenant_id == current_user.tenant_id,
        )
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sync job {job_id} not found",
        )

    return SyncJobResponse(
        id=job.id,
        report_type=job.report_type,
        status=job.status,
        started_at=job.started_at,
        completed_at=job.completed_at,
        duration_ms=job.duration_ms,
        rows_fetched=job.rows_fetched,
        error_code=job.error_code,
        error_message=job.error_message,
        triggered_by=job.triggered_by,
    )


# =============================================================================
# Credit Notes, Payments, Journals Endpoints (Spec 024)
# =============================================================================


@router.get(
    "/connections/{connection_id}/credit-notes",
    response_model=CreditNoteListResponse,
    summary="List Credit Notes",
    description="List credit notes synced from Xero for a connection.",
)
async def list_credit_notes(
    connection_id: UUID,
    current_user: Annotated[PracticeUser, Depends(require_permission(Permission.INTEGRATION_READ))],
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=50, ge=1, le=100, description="Number of items per page"),
    offset: int = Query(default=0, ge=0, description="Number of items to skip"),
    client_id: UUID | None = Query(default=None, description="Filter by client ID"),
    credit_note_type: str | None = Query(
        default=None, description="Filter by type: ACCPAYCREDIT or ACCRECCREDIT"
    ),
    status_filter: str | None = Query(default=None, alias="status", description="Filter by status"),
) -> CreditNoteListResponse:
    """List credit notes for a connection."""
    repo = XeroCreditNoteRepository(session)

    # Build filters
    filters = {"connection_id": connection_id, "tenant_id": current_user.tenant_id}
    if client_id:
        filters["client_id"] = client_id
    if credit_note_type:
        filters["credit_note_type"] = credit_note_type
    if status_filter:
        filters["status"] = status_filter

    credit_notes, total = await repo.list_by_connection(
        connection_id=connection_id,
        credit_note_type=credit_note_type,
        status=status_filter,
        limit=limit,
        offset=offset,
    )

    return CreditNoteListResponse(
        credit_notes=[CreditNoteSchema.model_validate(cn) for cn in credit_notes],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/connections/{connection_id}/credit-notes/{credit_note_id}",
    response_model=CreditNoteDetailSchema,
    summary="Get Credit Note",
    description="Get a specific credit note by ID.",
)
async def get_credit_note(
    connection_id: UUID,
    credit_note_id: UUID,
    current_user: Annotated[PracticeUser, Depends(require_permission(Permission.INTEGRATION_READ))],
    session: AsyncSession = Depends(get_db_session),
) -> CreditNoteDetailSchema:
    """Get a specific credit note."""
    repo = XeroCreditNoteRepository(session)
    credit_note = await repo.get_by_id(credit_note_id)

    if not credit_note or credit_note.connection_id != connection_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credit note not found",
        )

    if credit_note.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    return CreditNoteDetailSchema.model_validate(credit_note)


@router.get(
    "/connections/{connection_id}/payments",
    response_model=PaymentListResponse,
    summary="List Payments",
    description="List payments synced from Xero for a connection.",
)
async def list_payments(
    connection_id: UUID,
    current_user: Annotated[PracticeUser, Depends(require_permission(Permission.INTEGRATION_READ))],
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=50, ge=1, le=100, description="Number of items per page"),
    offset: int = Query(default=0, ge=0, description="Number of items to skip"),
    client_id: UUID | None = Query(default=None, description="Filter by client ID"),
    payment_type: str | None = Query(default=None, description="Filter by payment type"),
) -> PaymentListResponse:
    """List payments for a connection."""
    repo = XeroPaymentRepository(session)

    payments, total = await repo.list_by_connection(
        connection_id=connection_id,
        limit=limit,
        offset=offset,
    )

    return PaymentListResponse(
        payments=[PaymentSchema.model_validate(p) for p in payments],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/connections/{connection_id}/payments/{payment_id}",
    response_model=PaymentDetailSchema,
    summary="Get Payment",
    description="Get a specific payment by ID.",
)
async def get_payment(
    connection_id: UUID,
    payment_id: UUID,
    current_user: Annotated[PracticeUser, Depends(require_permission(Permission.INTEGRATION_READ))],
    session: AsyncSession = Depends(get_db_session),
) -> PaymentDetailSchema:
    """Get a specific payment."""
    repo = XeroPaymentRepository(session)
    payment = await repo.get_by_id(payment_id)

    if not payment or payment.connection_id != connection_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    if payment.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    return PaymentDetailSchema.model_validate(payment)


@router.get(
    "/connections/{connection_id}/overpayments",
    response_model=OverpaymentListResponse,
    summary="List Overpayments",
    description="List overpayments synced from Xero for a connection.",
)
async def list_overpayments(
    connection_id: UUID,
    current_user: Annotated[PracticeUser, Depends(require_permission(Permission.INTEGRATION_READ))],
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=50, ge=1, le=100, description="Number of items per page"),
    offset: int = Query(default=0, ge=0, description="Number of items to skip"),
) -> OverpaymentListResponse:
    """List overpayments for a connection."""
    repo = XeroOverpaymentRepository(session)

    overpayments, total = await repo.list_by_connection(
        connection_id=connection_id,
        limit=limit,
        offset=offset,
    )

    return OverpaymentListResponse(
        overpayments=[OverpaymentSchema.model_validate(o) for o in overpayments],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/connections/{connection_id}/prepayments",
    response_model=PrepaymentListResponse,
    summary="List Prepayments",
    description="List prepayments synced from Xero for a connection.",
)
async def list_prepayments(
    connection_id: UUID,
    current_user: Annotated[PracticeUser, Depends(require_permission(Permission.INTEGRATION_READ))],
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=50, ge=1, le=100, description="Number of items per page"),
    offset: int = Query(default=0, ge=0, description="Number of items to skip"),
) -> PrepaymentListResponse:
    """List prepayments for a connection."""
    repo = XeroPrepaymentRepository(session)

    prepayments, total = await repo.list_by_connection(
        connection_id=connection_id,
        limit=limit,
        offset=offset,
    )

    return PrepaymentListResponse(
        prepayments=[PrepaymentSchema.model_validate(p) for p in prepayments],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/connections/{connection_id}/journals",
    response_model=JournalListResponse,
    summary="List Journals",
    description="List system-generated journals synced from Xero for a connection.",
)
async def list_journals(
    connection_id: UUID,
    current_user: Annotated[PracticeUser, Depends(require_permission(Permission.INTEGRATION_READ))],
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=50, ge=1, le=100, description="Number of items per page"),
    offset: int = Query(default=0, ge=0, description="Number of items to skip"),
    source_type: str | None = Query(default=None, description="Filter by source type"),
) -> JournalListResponse:
    """List journals for a connection."""
    repo = XeroJournalRepository(session)

    journals, total = await repo.list_by_connection(
        connection_id=connection_id,
        source_type=source_type,
        limit=limit,
        offset=offset,
    )

    return JournalListResponse(
        journals=[JournalSchema.model_validate(j) for j in journals],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/connections/{connection_id}/journals/{journal_id}",
    response_model=JournalDetailSchema,
    summary="Get Journal",
    description="Get a specific journal by ID with line items.",
)
async def get_journal(
    connection_id: UUID,
    journal_id: UUID,
    current_user: Annotated[PracticeUser, Depends(require_permission(Permission.INTEGRATION_READ))],
    session: AsyncSession = Depends(get_db_session),
) -> JournalDetailSchema:
    """Get a specific journal."""
    repo = XeroJournalRepository(session)
    journal = await repo.get_by_id(journal_id)

    if not journal or journal.connection_id != connection_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Journal not found",
        )

    if journal.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    return JournalDetailSchema.model_validate(journal)


@router.get(
    "/connections/{connection_id}/manual-journals",
    response_model=ManualJournalListResponse,
    summary="List Manual Journals",
    description="List manual journals synced from Xero for a connection.",
)
async def list_manual_journals(
    connection_id: UUID,
    current_user: Annotated[PracticeUser, Depends(require_permission(Permission.INTEGRATION_READ))],
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=50, ge=1, le=100, description="Number of items per page"),
    offset: int = Query(default=0, ge=0, description="Number of items to skip"),
    status_filter: str | None = Query(default=None, alias="status", description="Filter by status"),
) -> ManualJournalListResponse:
    """List manual journals for a connection."""
    repo = XeroManualJournalRepository(session)

    manual_journals, total = await repo.list_by_connection(
        connection_id=connection_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )

    return ManualJournalListResponse(
        manual_journals=[ManualJournalSchema.model_validate(mj) for mj in manual_journals],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/connections/{connection_id}/manual-journals/{manual_journal_id}",
    response_model=ManualJournalDetailSchema,
    summary="Get Manual Journal",
    description="Get a specific manual journal by ID with line items.",
)
async def get_manual_journal(
    connection_id: UUID,
    manual_journal_id: UUID,
    current_user: Annotated[PracticeUser, Depends(require_permission(Permission.INTEGRATION_READ))],
    session: AsyncSession = Depends(get_db_session),
) -> ManualJournalDetailSchema:
    """Get a specific manual journal."""
    repo = XeroManualJournalRepository(session)
    manual_journal = await repo.get_by_id(manual_journal_id)

    if not manual_journal or manual_journal.connection_id != connection_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Manual journal not found",
        )

    if manual_journal.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    return ManualJournalDetailSchema.model_validate(manual_journal)


# =============================================================================
# Spec 025: Fixed Assets Endpoints
# =============================================================================


@router.get(
    "/connections/{connection_id}/asset-types",
    response_model=AssetTypeListResponse,
    summary="List Asset Types",
    description="List asset types (depreciation categories) synced from Xero Assets API.",
)
async def list_asset_types(
    connection_id: UUID,
    current_user: Annotated[PracticeUser, Depends(require_permission(Permission.INTEGRATION_READ))],
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=50, ge=1, le=100, description="Number of items per page"),
    offset: int = Query(default=0, ge=0, description="Number of items to skip"),
) -> AssetTypeListResponse:
    """List asset types for a connection.

    Asset types define depreciation categories with book and tax settings.
    """
    repo = XeroAssetTypeRepository(session)

    asset_types = await repo.list_by_connection(
        connection_id=connection_id,
        tenant_id=current_user.tenant_id,
    )

    # Apply pagination manually
    total = len(asset_types)
    paginated = asset_types[offset : offset + limit]

    return AssetTypeListResponse(
        asset_types=[AssetTypeSchema.model_validate(at) for at in paginated],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/connections/{connection_id}/assets",
    response_model=AssetListResponse,
    summary="List Fixed Assets",
    description="List fixed assets synced from Xero Assets API.",
)
async def list_assets(
    connection_id: UUID,
    current_user: Annotated[PracticeUser, Depends(require_permission(Permission.INTEGRATION_READ))],
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=50, ge=1, le=100, description="Number of items per page"),
    offset: int = Query(default=0, ge=0, description="Number of items to skip"),
    status_filter: str | None = Query(
        default=None,
        alias="status",
        description="Filter by asset status (Draft, Registered, Disposed)",
    ),
    asset_type_id: UUID | None = Query(default=None, description="Filter by asset type"),
) -> AssetListResponse:
    """List fixed assets for a connection.

    Assets include depreciation schedules, book values, and disposal information.
    """
    repo = XeroAssetRepository(session)

    if status_filter:
        # Convert status string to enum
        from .models import XeroAssetStatus

        try:
            status_enum = XeroAssetStatus(status_filter)
            assets = await repo.get_assets_by_status(
                connection_id=connection_id,
                status=status_enum,
            )
            total = len(assets)
            paginated = assets[offset : offset + limit]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid asset status: {status_filter}. Must be Draft, Registered, or Disposed.",
            )
    else:
        paginated, total = await repo.list_by_connection(
            connection_id=connection_id,
            asset_type_id=asset_type_id,
            limit=limit,
            offset=offset,
        )

    return AssetListResponse(
        assets=[AssetSchema.model_validate(a) for a in paginated],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/connections/{connection_id}/assets/sync",
    summary="Sync Fixed Assets",
    description="Trigger sync of fixed assets and asset types from Xero Assets API.",
)
async def sync_assets(
    connection_id: UUID,
    current_user: Annotated[
        PracticeUser, Depends(require_permission(Permission.INTEGRATION_MANAGE))
    ],
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    status_filter: str | None = Query(
        default=None,
        alias="status",
        description="Sync only assets with this status (Draft, Registered, Disposed)",
    ),
) -> dict:
    """Sync fixed assets from Xero Assets API.

    Syncs both asset types and assets. Requires 'assets' or 'assets.read' OAuth scope.
    """

    data_service = XeroDataService(session, settings)

    try:
        # First sync asset types (depreciation categories)
        asset_types_result = await data_service.sync_asset_types(connection_id)

        # Then sync assets
        assets_result = await data_service.sync_assets(
            connection_id,
            status=status_filter,
        )

        # Combine results
        total_processed = asset_types_result.records_processed + assets_result.records_processed
        total_created = asset_types_result.records_created + assets_result.records_created
        total_updated = asset_types_result.records_updated + assets_result.records_updated
        total_failed = asset_types_result.records_failed + assets_result.records_failed

        return {
            "success": True,
            "message": f"Synced {total_processed} records ({total_created} created, {total_updated} updated, {total_failed} failed)",
            "records_processed": total_processed,
            "records_created": total_created,
            "records_updated": total_updated,
            "records_failed": total_failed,
        }

    except XeroConnectionNotFoundExc as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except XeroRateLimitExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
        )
    except XeroClientError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Xero API error: {e}",
        )


@router.get(
    "/connections/{connection_id}/assets/depreciation-summary",
    summary="Get Depreciation Summary",
    description="Get comprehensive depreciation summary with tax planning insights.",
)
async def get_depreciation_summary(
    connection_id: UUID,
    current_user: Annotated[PracticeUser, Depends(require_permission(Permission.INTEGRATION_READ))],
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Get comprehensive depreciation summary for tax planning.

    Returns:
        - Total depreciation (book and tax)
        - Breakdown by asset type and depreciation method
        - Fully depreciated assets
        - Tax planning insights and recommendations
    """
    import structlog

    logger = structlog.get_logger()
    logger.info(
        "get_depreciation_summary called",
        connection_id=str(connection_id),
        user_id=str(current_user.id),
    )

    from .depreciation import DepreciationService

    depreciation_service = DepreciationService(session, settings)
    try:
        summary = await depreciation_service.get_depreciation_summary(connection_id)
        logger.info("get_depreciation_summary success", total_assets=summary.total_assets)
    except Exception as e:
        logger.error("get_depreciation_summary failed", error=str(e), error_type=type(e).__name__)
        raise

    # Convert dataclasses to dict for JSON response
    return {
        "total_assets": summary.total_assets,
        "total_purchase_price": float(summary.total_purchase_price),
        "total_book_value": float(summary.total_book_value),
        "total_book_depreciation_this_year": float(summary.total_book_depreciation_this_year),
        "total_book_accumulated_depreciation": float(summary.total_book_accumulated_depreciation),
        "total_tax_depreciation_this_year": float(summary.total_tax_depreciation_this_year)
        if summary.total_tax_depreciation_this_year
        else None,
        "by_asset_type": [
            {
                "asset_type_name": t.asset_type_name,
                "asset_count": t.asset_count,
                "total_purchase_price": float(t.total_purchase_price),
                "total_book_value": float(t.total_book_value),
                "total_depreciation_this_year": float(t.total_depreciation_this_year),
                "total_accumulated_depreciation": float(t.total_accumulated_depreciation),
            }
            for t in summary.by_asset_type
        ],
        "by_method": [
            {
                "method": m.method,
                "method_display_name": m.method_display_name,
                "asset_count": m.asset_count,
                "total_book_value": float(m.total_book_value),
                "total_depreciation_this_year": float(m.total_depreciation_this_year),
            }
            for m in summary.by_method
        ],
        "fully_depreciated_count": summary.fully_depreciated_count,
        "fully_depreciated_assets": [
            {
                "asset_id": str(a.asset_id),
                "asset_name": a.asset_name,
                "asset_number": a.asset_number,
                "asset_type_name": a.asset_type_name,
                "purchase_date": a.purchase_date.isoformat() if a.purchase_date else None,
                "purchase_price": float(a.purchase_price),
                "book_value": float(a.book_value),
            }
            for a in summary.fully_depreciated_assets
        ],
        "insights": [
            {
                "insight_type": i.insight_type,
                "title": i.title,
                "description": i.description,
                "impact_amount": float(i.impact_amount) if i.impact_amount else None,
                "affected_assets": i.affected_assets,
            }
            for i in summary.insights
        ],
        "financial_year_start": summary.financial_year_start.isoformat(),
        "financial_year_end": summary.financial_year_end.isoformat(),
    }


@router.get(
    "/connections/{connection_id}/assets/instant-write-off",
    summary="Get Instant Write-Off Eligible Assets",
    description="Get assets eligible for instant asset write-off under ATO small business rules.",
)
async def get_instant_write_off_summary(
    connection_id: UUID,
    current_user: Annotated[PracticeUser, Depends(require_permission(Permission.INTEGRATION_READ))],
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    is_gst_registered: bool = Query(
        default=True,
        description="Whether the business is GST registered (affects threshold calculation)",
    ),
    estimated_turnover: float | None = Query(
        default=None,
        description="Estimated annual turnover for small business eligibility check",
    ),
) -> dict:
    """Get assets eligible for instant asset write-off.

    Analyzes fixed assets to identify those qualifying for instant asset write-off
    under ATO small business rules. Current threshold is $20,000 (GST-exclusive)
    for assets purchased in the current financial year.

    Returns:
        Summary including:
        - Business eligibility status
        - Applicable threshold and type
        - List of eligible assets with purchase details
        - Total potential deduction amount
    """
    from decimal import Decimal

    from .write_off import InstantWriteOffService

    write_off_service = InstantWriteOffService(session, settings)

    turnover = Decimal(str(estimated_turnover)) if estimated_turnover else None

    summary = await write_off_service.get_eligible_assets(
        connection_id=connection_id,
        is_gst_registered=is_gst_registered,
        estimated_turnover=turnover,
    )

    # Convert dataclass to dict for JSON response
    return {
        "is_eligible_business": summary.is_eligible_business,
        "ineligibility_reason": summary.ineligibility_reason,
        "write_off_threshold": float(summary.write_off_threshold),
        "threshold_type": summary.threshold_type,
        "financial_year_start": summary.financial_year_start.isoformat(),
        "financial_year_end": summary.financial_year_end.isoformat(),
        "eligible_assets": [
            {
                "asset_id": str(asset.asset_id),
                "xero_asset_id": asset.xero_asset_id,
                "asset_name": asset.asset_name,
                "asset_number": asset.asset_number,
                "purchase_date": asset.purchase_date.isoformat() if asset.purchase_date else None,
                "purchase_price": float(asset.purchase_price),
                "asset_type_name": asset.asset_type_name,
                "status": asset.status.value,
            }
            for asset in summary.eligible_assets
        ],
        "total_eligible_amount": float(summary.total_eligible_amount),
        "asset_count": summary.asset_count,
    }


@router.get(
    "/connections/{connection_id}/assets/capex-analysis",
    summary="Get Capital Expenditure Analysis",
    description="Analyze capital expenditure patterns, replacement needs, and forecasts.",
)
async def get_capex_analysis(
    connection_id: UUID,
    current_user: Annotated[PracticeUser, Depends(require_permission(Permission.INTEGRATION_READ))],
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    years_of_history: int = Query(
        default=5,
        ge=1,
        le=10,
        description="Number of years of purchase history to analyze",
    ),
    include_forecasts: bool = Query(
        default=True,
        description="Include future replacement forecasts",
    ),
) -> dict:
    """Get capital expenditure analysis for a connection.

    Returns comprehensive analysis including:
    - Historical purchase patterns by financial year
    - Spending trends (increasing, decreasing, stable)
    - Assets needing replacement (fully depreciated, near end of life)
    - Future replacement forecasts
    - Strategic insights and recommendations
    """
    from .capex import CapexAnalysisService

    capex_service = CapexAnalysisService(session, settings)
    analysis = await capex_service.analyze_capital_expenditure(
        connection_id=connection_id,
        years_of_history=years_of_history,
        include_forecasts=include_forecasts,
    )

    # Convert dataclasses to dict for JSON response
    return {
        "total_assets": analysis.total_assets,
        "total_book_value": float(analysis.total_book_value),
        "total_purchase_price": float(analysis.total_purchase_price),
        "average_asset_age_years": float(analysis.average_asset_age_years),
        "purchase_history": [
            {
                "period_label": p.period_label,
                "period_start": p.period_start.isoformat(),
                "period_end": p.period_end.isoformat(),
                "asset_count": p.asset_count,
                "total_cost": float(p.total_cost),
                "asset_types": [
                    {"type": t["type"], "count": t["count"], "cost": float(t["cost"])}
                    for t in p.asset_types
                ],
            }
            for p in analysis.purchase_history
        ],
        "trend": {
            "direction": analysis.trend.direction,
            "avg_annual_spend": float(analysis.trend.avg_annual_spend),
            "peak_year": analysis.trend.peak_year,
            "peak_amount": float(analysis.trend.peak_amount)
            if analysis.trend.peak_amount
            else None,
            "low_year": analysis.trend.low_year,
            "low_amount": float(analysis.trend.low_amount) if analysis.trend.low_amount else None,
            "trend_percentage": float(analysis.trend.trend_percentage)
            if analysis.trend.trend_percentage
            else None,
        }
        if analysis.trend
        else None,
        "replacement_candidates": [
            {
                "asset_id": str(c.asset_id),
                "asset_name": c.asset_name,
                "asset_number": c.asset_number,
                "asset_type_name": c.asset_type_name,
                "purchase_date": c.purchase_date.isoformat() if c.purchase_date else None,
                "age_years": float(c.age_years),
                "purchase_price": float(c.purchase_price),
                "book_value": float(c.book_value),
                "depreciation_percentage": float(c.depreciation_percentage),
                "replacement_reason": c.replacement_reason,
                "estimated_replacement_cost": float(c.estimated_replacement_cost)
                if c.estimated_replacement_cost
                else None,
            }
            for c in analysis.replacement_candidates
        ],
        "estimated_replacement_budget": float(analysis.estimated_replacement_budget),
        "fully_depreciated_count": analysis.fully_depreciated_count,
        "fully_depreciated_value": float(analysis.fully_depreciated_value),
        "forecasts": [
            {
                "forecast_year": f.forecast_year,
                "estimated_replacement_cost": float(f.estimated_replacement_cost),
                "assets_reaching_end_of_life": f.assets_reaching_end_of_life,
                "replacement_candidates": f.replacement_candidates,
            }
            for f in analysis.forecasts
        ],
        "insights": analysis.insights,
    }


@router.get(
    "/connections/{connection_id}/assets/fully-depreciated",
    summary="Get Fully Depreciated Assets",
    description="Get all fully depreciated assets for replacement planning.",
)
async def get_fully_depreciated_assets(
    connection_id: UUID,
    current_user: Annotated[PracticeUser, Depends(require_permission(Permission.INTEGRATION_READ))],
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Get fully depreciated assets for a connection.

    Returns assets with zero book value or 100% depreciation
    for replacement planning and disposal decisions.
    """
    from .capex import CapexAnalysisService

    capex_service = CapexAnalysisService(session, settings)
    candidates = await capex_service.get_fully_depreciated_assets(connection_id)

    return {
        "count": len(candidates),
        "total_original_cost": float(sum(c.purchase_price for c in candidates)),
        "total_replacement_estimate": float(
            sum(c.estimated_replacement_cost or c.purchase_price for c in candidates)
        ),
        "assets": [
            {
                "asset_id": str(c.asset_id),
                "asset_name": c.asset_name,
                "asset_number": c.asset_number,
                "asset_type_name": c.asset_type_name,
                "purchase_date": c.purchase_date.isoformat() if c.purchase_date else None,
                "age_years": float(c.age_years),
                "purchase_price": float(c.purchase_price),
                "book_value": float(c.book_value),
                "estimated_replacement_cost": float(c.estimated_replacement_cost)
                if c.estimated_replacement_cost
                else None,
            }
            for c in candidates
        ],
    }


# NOTE: This route MUST come after all specific /assets/* routes
# because FastAPI matches routes in order, and {asset_id} would match
# "depreciation-summary", "instant-write-off", etc. as invalid UUIDs
@router.get(
    "/connections/{connection_id}/assets/{asset_id}",
    response_model=AssetDetailSchema,
    summary="Get Fixed Asset",
    description="Get a specific fixed asset by ID with full depreciation details.",
)
async def get_asset(
    connection_id: UUID,
    asset_id: UUID,
    current_user: Annotated[PracticeUser, Depends(require_permission(Permission.INTEGRATION_READ))],
    session: AsyncSession = Depends(get_db_session),
) -> AssetDetailSchema:
    """Get a specific fixed asset with full details."""
    repo = XeroAssetRepository(session)
    asset = await repo.get_by_id(asset_id)

    if not asset or asset.connection_id != connection_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )

    if asset.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    return AssetDetailSchema.model_validate(asset)


# =============================================================================
# Spec 024: Transaction Sync Status
# =============================================================================


@router.get(
    "/connections/{connection_id}/transactions/sync-status",
    response_model=TransactionSyncStatus,
    summary="Get Transaction Sync Status",
    description="Get sync status for all Spec 024 transaction types (credit notes, payments, journals).",
)
async def get_transaction_sync_status(
    connection_id: UUID,
    current_user: Annotated[PracticeUser, Depends(require_permission(Permission.INTEGRATION_READ))],
    session: AsyncSession = Depends(get_db_session),
) -> TransactionSyncStatus:
    """Get transaction sync status for a connection.

    Returns counts and last sync timestamps for:
    - Credit notes
    - Payments
    - Overpayments
    - Prepayments
    - Journals
    - Manual journals
    """
    credit_note_repo = XeroCreditNoteRepository(session)
    payment_repo = XeroPaymentRepository(session)
    overpayment_repo = XeroOverpaymentRepository(session)
    prepayment_repo = XeroPrepaymentRepository(session)
    journal_repo = XeroJournalRepository(session)
    manual_journal_repo = XeroManualJournalRepository(session)

    # Get counts
    credit_note_count = await credit_note_repo.count_by_connection(
        connection_id, current_user.tenant_id
    )
    payment_count = await payment_repo.count_by_connection(connection_id, current_user.tenant_id)
    overpayment_count = await overpayment_repo.count_by_connection(
        connection_id, current_user.tenant_id
    )
    prepayment_count = await prepayment_repo.count_by_connection(
        connection_id, current_user.tenant_id
    )
    journal_count = await journal_repo.count_by_connection(connection_id, current_user.tenant_id)
    manual_journal_count = await manual_journal_repo.count_by_connection(
        connection_id, current_user.tenant_id
    )

    # Get last sync timestamps (from most recently updated record)
    credit_notes = await credit_note_repo.list_by_connection(
        connection_id, current_user.tenant_id, limit=1, offset=0
    )
    payments = await payment_repo.list_by_connection(
        connection_id, current_user.tenant_id, limit=1, offset=0
    )
    overpayments = await overpayment_repo.list_by_connection(
        connection_id, current_user.tenant_id, limit=1, offset=0
    )
    prepayments = await prepayment_repo.list_by_connection(
        connection_id, current_user.tenant_id, limit=1, offset=0
    )
    journals = await journal_repo.list_by_connection(
        connection_id, current_user.tenant_id, limit=1, offset=0
    )
    manual_journals = await manual_journal_repo.list_by_connection(
        connection_id, current_user.tenant_id, limit=1, offset=0
    )

    return TransactionSyncStatus(
        credit_notes={
            "count": credit_note_count,
            "last_sync": credit_notes[0].updated_at.isoformat() if credit_notes else None,
        },
        payments={
            "count": payment_count,
            "last_sync": payments[0].updated_at.isoformat() if payments else None,
        },
        overpayments={
            "count": overpayment_count,
            "last_sync": overpayments[0].updated_at.isoformat() if overpayments else None,
        },
        prepayments={
            "count": prepayment_count,
            "last_sync": prepayments[0].updated_at.isoformat() if prepayments else None,
        },
        journals={
            "count": journal_count,
            "last_sync": journals[0].updated_at.isoformat() if journals else None,
        },
        manual_journals={
            "count": manual_journal_count,
            "last_sync": manual_journals[0].updated_at.isoformat() if manual_journals else None,
        },
    )


# =============================================================================
# Spec 025: Purchase Orders
# =============================================================================


@router.get(
    "/connections/{connection_id}/purchase-orders",
    response_model=PurchaseOrderListResponse,
    summary="List Purchase Orders",
    description="Get all purchase orders for a connection with optional filtering.",
)
async def list_purchase_orders(
    connection_id: UUID,
    current_user: Annotated[PracticeUser, Depends(require_permission(Permission.INTEGRATION_READ))],
    session: AsyncSession = Depends(get_db_session),
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> PurchaseOrderListResponse:
    """List purchase orders for a connection."""
    from .repository import XeroPurchaseOrderRepository

    repo = XeroPurchaseOrderRepository(session)
    orders, total = await repo.list_by_connection(
        connection_id=connection_id,
        tenant_id=current_user.tenant_id,
        status=status,
        limit=limit,
        offset=offset,
    )

    return PurchaseOrderListResponse(
        orders=[PurchaseOrderSchema.model_validate(o) for o in orders],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/connections/{connection_id}/purchase-orders/summary",
    response_model=PurchaseOrderSummary,
    summary="Get Purchase Order Summary",
    description="Get summary of outstanding purchase orders for cash flow planning.",
)
async def get_purchase_order_summary(
    connection_id: UUID,
    current_user: Annotated[PracticeUser, Depends(require_permission(Permission.INTEGRATION_READ))],
    session: AsyncSession = Depends(get_db_session),
) -> PurchaseOrderSummary:
    """Get purchase order summary for cash flow planning."""
    from datetime import timedelta
    from decimal import Decimal

    from .repository import XeroPurchaseOrderRepository

    repo = XeroPurchaseOrderRepository(session)

    # Get all non-deleted orders
    orders, _ = await repo.list_by_connection(
        connection_id=connection_id,
        tenant_id=current_user.tenant_id,
        limit=1000,
        offset=0,
    )

    # Calculate summary
    outstanding_statuses = {"DRAFT", "SUBMITTED", "AUTHORISED"}
    outstanding = [o for o in orders if o.status in outstanding_statuses]
    outstanding_total = sum((o.total for o in outstanding), Decimal("0"))

    by_status: dict[str, int] = {}
    for order in orders:
        by_status[order.status] = by_status.get(order.status, 0) + 1

    # Find upcoming deliveries (next 30 days)
    today = date.today()
    upcoming_cutoff = today + timedelta(days=30)
    upcoming_deliveries = [
        {
            "po_number": o.purchase_order_number,
            "contact_name": o.contact_name,
            "expected_date": o.expected_arrival_date.isoformat()
            if o.expected_arrival_date
            else o.delivery_date.isoformat()
            if o.delivery_date
            else None,
            "total": float(o.total),
        }
        for o in outstanding
        if (o.expected_arrival_date and o.expected_arrival_date <= upcoming_cutoff)
        or (o.delivery_date and o.delivery_date <= upcoming_cutoff)
    ]

    return PurchaseOrderSummary(
        outstanding_count=len(outstanding),
        outstanding_total=outstanding_total,
        by_status=by_status,
        upcoming_deliveries=upcoming_deliveries,
    )


@router.get(
    "/connections/{connection_id}/purchase-orders/{po_id}",
    response_model=PurchaseOrderSchema,
    summary="Get Purchase Order",
    description="Get a specific purchase order by ID.",
)
async def get_purchase_order(
    connection_id: UUID,
    po_id: UUID,
    current_user: Annotated[PracticeUser, Depends(require_permission(Permission.INTEGRATION_READ))],
    session: AsyncSession = Depends(get_db_session),
) -> PurchaseOrderSchema:
    """Get a specific purchase order."""
    from .repository import XeroPurchaseOrderRepository

    repo = XeroPurchaseOrderRepository(session)
    order = await repo.get_by_id(po_id, current_user.tenant_id)

    if not order or order.connection_id != connection_id:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    return PurchaseOrderSchema.model_validate(order)


@router.post(
    "/connections/{connection_id}/purchase-orders/sync",
    summary="Sync Purchase Orders",
    description="Sync purchase orders from Xero.",
)
async def sync_purchase_orders(
    connection_id: UUID,
    current_user: Annotated[
        PracticeUser, Depends(require_permission(Permission.INTEGRATION_MANAGE))
    ],
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    status: str | None = Query(None, description="Filter by status"),
) -> dict:
    """Sync purchase orders from Xero."""
    data_service = XeroDataService(session, settings)
    result = await data_service.sync_purchase_orders(connection_id, status=status)

    return {
        "synced": result.records_processed,
        "created": result.records_created,
        "updated": result.records_updated,
        "errors": result.records_failed,
    }


# =============================================================================
# Spec 025: Repeating Invoices
# =============================================================================


@router.get(
    "/connections/{connection_id}/repeating-invoices",
    response_model=RepeatingInvoiceListResponse,
    summary="List Repeating Invoices",
    description="Get all repeating invoice templates for a connection.",
)
async def list_repeating_invoices(
    connection_id: UUID,
    current_user: Annotated[PracticeUser, Depends(require_permission(Permission.INTEGRATION_READ))],
    session: AsyncSession = Depends(get_db_session),
    invoice_type: str | None = Query(None, description="Filter by type: ACCPAY or ACCREC"),
    status: str | None = Query(None, description="Filter by status: DRAFT or AUTHORISED"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> RepeatingInvoiceListResponse:
    """List repeating invoices for a connection."""
    from .repository import XeroRepeatingInvoiceRepository

    repo = XeroRepeatingInvoiceRepository(session)
    invoices, total = await repo.list_by_connection(
        connection_id=connection_id,
        tenant_id=current_user.tenant_id,
        invoice_type=invoice_type,
        status=status,
        limit=limit,
        offset=offset,
    )

    return RepeatingInvoiceListResponse(
        invoices=[RepeatingInvoiceSchema.model_validate(i) for i in invoices],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/connections/{connection_id}/repeating-invoices/summary",
    response_model=RecurringSummary,
    summary="Get Recurring Summary",
    description="Get summary of recurring revenue and expenses.",
)
async def get_recurring_summary(
    connection_id: UUID,
    current_user: Annotated[PracticeUser, Depends(require_permission(Permission.INTEGRATION_READ))],
    session: AsyncSession = Depends(get_db_session),
) -> RecurringSummary:
    """Get recurring revenue/expense summary."""
    from decimal import Decimal

    from .repository import XeroRepeatingInvoiceRepository

    repo = XeroRepeatingInvoiceRepository(session)

    # Get all active repeating invoices
    invoices, _ = await repo.list_by_connection(
        connection_id=connection_id,
        tenant_id=current_user.tenant_id,
        status="AUTHORISED",
        limit=1000,
        offset=0,
    )

    # Calculate monthly amounts based on schedule
    def monthly_amount(invoice) -> Decimal:
        """Convert invoice amount to monthly equivalent."""
        unit = invoice.schedule_unit
        period = invoice.schedule_period or 1
        total = invoice.total or Decimal("0")

        if unit == "WEEKLY":
            return total * Decimal("52") / Decimal("12") / Decimal(str(period))
        elif unit == "MONTHLY":
            return total / Decimal(str(period))
        elif unit == "YEARLY":
            return total / Decimal("12") / Decimal(str(period))
        return total

    receivables = [i for i in invoices if i.invoice_type == "ACCREC"]
    payables = [i for i in invoices if i.invoice_type == "ACCPAY"]

    monthly_receivables = sum((monthly_amount(i) for i in receivables), Decimal("0"))
    monthly_payables = sum((monthly_amount(i) for i in payables), Decimal("0"))

    return RecurringSummary(
        monthly_receivables=monthly_receivables,
        monthly_payables=monthly_payables,
        annual_receivables=monthly_receivables * 12,
        annual_payables=monthly_payables * 12,
        active_receivable_count=len(receivables),
        active_payable_count=len(payables),
    )


@router.post(
    "/connections/{connection_id}/repeating-invoices/sync",
    summary="Sync Repeating Invoices",
    description="Sync repeating invoices from Xero.",
)
async def sync_repeating_invoices(
    connection_id: UUID,
    current_user: Annotated[
        PracticeUser, Depends(require_permission(Permission.INTEGRATION_MANAGE))
    ],
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    status: str | None = Query(None, description="Filter by status"),
) -> dict:
    """Sync repeating invoices from Xero."""
    data_service = XeroDataService(session, settings)
    result = await data_service.sync_repeating_invoices(connection_id, status=status)

    return {
        "synced": result.records_processed,
        "created": result.records_created,
        "updated": result.records_updated,
        "errors": result.records_failed,
    }


# =============================================================================
# Spec 025: Tracking Categories
# =============================================================================


@router.get(
    "/connections/{connection_id}/tracking-categories",
    response_model=TrackingCategoryListResponse,
    summary="List Tracking Categories",
    description="Get all tracking categories and their options for a connection.",
)
async def list_tracking_categories(
    connection_id: UUID,
    current_user: Annotated[PracticeUser, Depends(require_permission(Permission.INTEGRATION_READ))],
    session: AsyncSession = Depends(get_db_session),
    include_archived: bool = Query(False, description="Include archived categories"),
) -> TrackingCategoryListResponse:
    """List tracking categories for a connection."""
    from .repository import XeroTrackingCategoryRepository, XeroTrackingOptionRepository

    category_repo = XeroTrackingCategoryRepository(session)
    option_repo = XeroTrackingOptionRepository(session)

    categories = await category_repo.list_by_connection(
        connection_id=connection_id,
        tenant_id=current_user.tenant_id,
        include_archived=include_archived,
    )

    # Load options for each category
    result = []
    for cat in categories:
        options = await option_repo.list_by_category(cat.id, current_user.tenant_id)
        cat_dict = {
            "id": cat.id,
            "xero_tracking_category_id": cat.xero_tracking_category_id,
            "name": cat.name,
            "status": cat.status,
            "option_count": len(options),
            "options": [{"id": str(o.id), "name": o.name, "status": o.status} for o in options],
            "created_at": cat.created_at,
            "updated_at": cat.updated_at,
        }
        result.append(TrackingCategorySchema.model_validate(cat_dict))

    return TrackingCategoryListResponse(
        categories=result,
        total=len(result),
    )


@router.post(
    "/connections/{connection_id}/tracking-categories/sync",
    summary="Sync Tracking Categories",
    description="Sync tracking categories from Xero.",
)
async def sync_tracking_categories(
    connection_id: UUID,
    current_user: Annotated[
        PracticeUser, Depends(require_permission(Permission.INTEGRATION_MANAGE))
    ],
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    include_archived: bool = Query(False, description="Include archived categories"),
) -> dict:
    """Sync tracking categories from Xero."""
    data_service = XeroDataService(session, settings)
    result = await data_service.sync_tracking_categories(
        connection_id, include_archived=include_archived
    )

    return {
        "synced": result.records_processed,
        "created": result.records_created,
        "updated": result.records_updated,
        "errors": result.records_failed,
    }


# =============================================================================
# Spec 025: Quotes
# =============================================================================


@router.get(
    "/connections/{connection_id}/quotes",
    response_model=QuoteListResponse,
    summary="List Quotes",
    description="Get all quotes for a connection with optional filtering.",
)
async def list_quotes(
    connection_id: UUID,
    current_user: Annotated[PracticeUser, Depends(require_permission(Permission.INTEGRATION_READ))],
    session: AsyncSession = Depends(get_db_session),
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> QuoteListResponse:
    """List quotes for a connection."""
    from .repository import XeroQuoteRepository

    repo = XeroQuoteRepository(session)
    quotes, total = await repo.list_by_connection(
        connection_id=connection_id,
        tenant_id=current_user.tenant_id,
        status=status,
        limit=limit,
        offset=offset,
    )

    return QuoteListResponse(
        quotes=[QuoteSchema.model_validate(q) for q in quotes],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/connections/{connection_id}/quotes/pipeline",
    response_model=QuotePipelineSummary,
    summary="Get Quote Pipeline Summary",
    description="Get quote pipeline summary for sales forecasting.",
)
async def get_quote_pipeline(
    connection_id: UUID,
    current_user: Annotated[PracticeUser, Depends(require_permission(Permission.INTEGRATION_READ))],
    session: AsyncSession = Depends(get_db_session),
) -> QuotePipelineSummary:
    """Get quote pipeline summary."""
    from decimal import Decimal

    from .repository import XeroQuoteRepository

    repo = XeroQuoteRepository(session)
    quotes, total = await repo.list_by_connection(
        connection_id=connection_id,
        tenant_id=current_user.tenant_id,
        limit=1000,
        offset=0,
    )

    total_value = sum((q.total for q in quotes), Decimal("0"))

    by_status: dict[str, dict] = {}
    for quote in quotes:
        if quote.status not in by_status:
            by_status[quote.status] = {"count": 0, "value": Decimal("0")}
        by_status[quote.status]["count"] += 1
        by_status[quote.status]["value"] += quote.total

    # Convert Decimals to floats for JSON
    for status in by_status:
        by_status[status]["value"] = float(by_status[status]["value"])

    # Calculate conversion rate (invoiced / (invoiced + declined + accepted))
    invoiced = by_status.get("INVOICED", {}).get("count", 0)
    accepted = by_status.get("ACCEPTED", {}).get("count", 0)
    declined = by_status.get("DECLINED", {}).get("count", 0)
    resolved = invoiced + accepted + declined
    conversion_rate = (invoiced + accepted) / resolved * 100 if resolved > 0 else None

    average_quote_value = total_value / total if total > 0 else None

    return QuotePipelineSummary(
        total_quotes=total,
        total_value=total_value,
        by_status=by_status,
        conversion_rate=conversion_rate,
        average_quote_value=average_quote_value,
    )


@router.get(
    "/connections/{connection_id}/quotes/{quote_id}",
    response_model=QuoteSchema,
    summary="Get Quote",
    description="Get a specific quote by ID.",
)
async def get_quote(
    connection_id: UUID,
    quote_id: UUID,
    current_user: Annotated[PracticeUser, Depends(require_permission(Permission.INTEGRATION_READ))],
    session: AsyncSession = Depends(get_db_session),
) -> QuoteSchema:
    """Get a specific quote."""
    from .repository import XeroQuoteRepository

    repo = XeroQuoteRepository(session)
    quote = await repo.get_by_id(quote_id, current_user.tenant_id)

    if not quote or quote.connection_id != connection_id:
        raise HTTPException(status_code=404, detail="Quote not found")

    return QuoteSchema.model_validate(quote)


@router.post(
    "/connections/{connection_id}/quotes/sync",
    summary="Sync Quotes",
    description="Sync quotes from Xero.",
)
async def sync_quotes(
    connection_id: UUID,
    current_user: Annotated[
        PracticeUser, Depends(require_permission(Permission.INTEGRATION_MANAGE))
    ],
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    status: str | None = Query(None, description="Filter by status"),
) -> dict:
    """Sync quotes from Xero."""
    data_service = XeroDataService(session, settings)
    result = await data_service.sync_quotes(connection_id, status=status)

    return {
        "synced": result.records_processed,
        "created": result.records_created,
        "updated": result.records_updated,
        "errors": result.records_failed,
    }


# =============================================================================
# Spec 025: Enhanced Sync Status
# =============================================================================


@router.get(
    "/connections/{connection_id}/enhanced-sync-status",
    response_model=EnhancedSyncStatus,
    summary="Get Enhanced Sync Status",
    description="""
    Get sync status for all Spec 025 entity types.

    Provides a comprehensive view of sync status for:
    - Fixed assets (requires assets scope)
    - Purchase orders
    - Repeating invoices
    - Tracking categories
    - Quotes

    **Required Permission**: `integration.read`
    """,
)
async def get_enhanced_sync_status(
    connection_id: UUID,
    current_user: Annotated[PracticeUser, Depends(require_permission(Permission.INTEGRATION_READ))],
    session: AsyncSession = Depends(get_db_session),
) -> EnhancedSyncStatus:
    """Get enhanced sync status for a connection.

    Returns counts, last sync timestamps, and summary metrics for
    all Spec 025 entity types (assets, purchase orders, repeating
    invoices, tracking categories, quotes).
    """

    from .repository import (
        XeroAssetRepository,
        XeroAssetTypeRepository,
        XeroConnectionRepository,
        XeroPurchaseOrderRepository,
        XeroQuoteRepository,
        XeroRepeatingInvoiceRepository,
        XeroTrackingCategoryRepository,
        XeroTrackingOptionRepository,
    )

    conn_repo = XeroConnectionRepository(session)
    connection = await conn_repo.get_by_id(connection_id)

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "Connection not found"}},
        )

    # Check if connection has assets scope
    has_assets_scope = any("assets" in scope.lower() for scope in (connection.scopes or []))

    # Initialize repos
    asset_repo = XeroAssetRepository(session)
    asset_type_repo = XeroAssetTypeRepository(session)
    po_repo = XeroPurchaseOrderRepository(session)
    ri_repo = XeroRepeatingInvoiceRepository(session)
    tc_repo = XeroTrackingCategoryRepository(session)
    to_repo = XeroTrackingOptionRepository(session)
    quote_repo = XeroQuoteRepository(session)

    # Get counts
    assets_count = 0
    asset_types_count = 0
    last_assets_sync = None

    if has_assets_scope:
        assets_count = await asset_repo.count_by_connection(connection_id, current_user.tenant_id)
        asset_types_count = await asset_type_repo.count_by_connection(
            connection_id, current_user.tenant_id
        )
        # Get most recent asset for last sync time
        assets, _ = await asset_repo.list_by_connection(connection_id, limit=1, offset=0)
        if assets:
            last_assets_sync = assets[0].updated_at

    # Purchase Orders
    po_count = await po_repo.count_by_connection(connection_id, current_user.tenant_id)
    outstanding_po, outstanding_po_value = await po_repo.get_outstanding_summary(
        connection_id, current_user.tenant_id
    )
    pos, _ = await po_repo.list_by_connection(connection_id, limit=1, offset=0)
    last_po_sync = pos[0].updated_at if pos else None

    # Repeating Invoices
    ri_count = await ri_repo.count_by_connection(connection_id, current_user.tenant_id)
    active_ri = await ri_repo.count_active(connection_id, current_user.tenant_id)
    monthly_revenue, monthly_expense = await ri_repo.get_monthly_recurring_summary(
        connection_id, current_user.tenant_id
    )
    ris, _ = await ri_repo.list_by_connection(connection_id, limit=1, offset=0)
    last_ri_sync = ris[0].updated_at if ris else None

    # Tracking Categories
    tc_count = await tc_repo.count_by_connection(connection_id, current_user.tenant_id)
    active_options = await to_repo.count_active_by_connection(connection_id, current_user.tenant_id)
    tcs = await tc_repo.list_by_connection(connection_id)
    last_tc_sync = tcs[0].updated_at if tcs else None

    # Quotes
    quotes_count = await quote_repo.count_by_connection(connection_id, current_user.tenant_id)
    open_quotes, open_quotes_value = await quote_repo.get_open_quotes_summary(
        connection_id, current_user.tenant_id
    )
    quotes, _ = await quote_repo.list_by_connection(connection_id, limit=1, offset=0)
    last_quotes_sync = quotes[0].updated_at if quotes else None

    return EnhancedSyncStatus(
        connection_id=connection_id,
        organization_name=connection.organization_name,
        # Assets
        assets_count=assets_count,
        asset_types_count=asset_types_count,
        has_assets_scope=has_assets_scope,
        last_assets_sync_at=last_assets_sync,
        # Purchase Orders
        purchase_orders_count=po_count,
        outstanding_purchase_orders=outstanding_po,
        outstanding_purchase_orders_value=outstanding_po_value,
        last_purchase_orders_sync_at=last_po_sync,
        # Repeating Invoices
        repeating_invoices_count=ri_count,
        active_repeating_invoices=active_ri,
        monthly_recurring_revenue=monthly_revenue,
        monthly_recurring_expense=monthly_expense,
        last_repeating_invoices_sync_at=last_ri_sync,
        # Tracking Categories
        tracking_categories_count=tc_count,
        active_tracking_options=active_options,
        last_tracking_categories_sync_at=last_tc_sync,
        # Quotes
        quotes_count=quotes_count,
        open_quotes_count=open_quotes,
        open_quotes_value=open_quotes_value,
        last_quotes_sync_at=last_quotes_sync,
        # Sync status
        sync_in_progress=False,  # TODO: Check for active sync jobs
        last_full_sync_at=connection.last_full_sync_at,
    )


# =============================================================================
# Bulk Import Helper Dependencies
# =============================================================================


async def get_bulk_import_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> BulkImportService:
    """Get BulkImportService instance."""
    return BulkImportService(session=session, settings=settings)


# =============================================================================
# Bulk Import Endpoints (Phase 035)
# =============================================================================


@router.post(
    "/bulk-import/initiate",
    response_model=BulkImportInitiateResponse,
    summary="Initiate bulk import OAuth flow",
    description="""
    Generates a Xero OAuth authorization URL for bulk import.
    Sets is_bulk_import=true on the OAuth state to trigger multi-org
    processing on callback.

    **Required Permission**: `integration.manage`
    """,
    responses={
        200: {"description": "OAuth authorization URL generated"},
        409: {"description": "A bulk import is already in progress for this tenant"},
    },
)
async def initiate_bulk_import(
    request: BulkImportInitiateRequest,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_MANAGE)),
    service: BulkImportService = Depends(get_bulk_import_service),
) -> BulkImportInitiateResponse:
    """Initiate bulk import OAuth flow."""
    try:
        result = await service.initiate_bulk_import(
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            redirect_uri=request.redirect_uri,
        )
        return BulkImportInitiateResponse(
            auth_url=result["auth_url"],
            state=result["state"],
        )
    except BulkImportInProgressError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e


@router.get(
    "/bulk-import/callback",
    response_model=BulkImportCallbackResponse,
    summary="Handle OAuth callback for bulk import",
    description="""
    Processes the Xero OAuth callback, fetches all authorized organizations,
    identifies new vs existing connections, and returns the list for configuration.
    Does NOT create connections yet — that happens on confirm.
    """,
    responses={
        200: {"description": "Organizations fetched and ready for configuration"},
        400: {"description": "Invalid or expired state token"},
    },
)
async def bulk_import_callback(
    code: str = Query(..., description="Authorization code from Xero"),
    state: str = Query(..., description="OAuth state token"),
    service: BulkImportService = Depends(get_bulk_import_service),
) -> BulkImportCallbackResponse:
    """Handle bulk import OAuth callback."""
    try:
        result = await service.handle_bulk_callback(code=code, state=state)
        return BulkImportCallbackResponse(**{k: v for k, v in result.items() if k != "state"})
    except XeroOAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post(
    "/bulk-import/confirm",
    response_model=BulkImportJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Confirm selected organizations and start import",
    description="""
    Creates XeroConnection records for selected organizations,
    creates a BulkImportJob, and queues background sync for each.

    **Required Permission**: `integration.manage`
    """,
    responses={
        202: {"description": "Import job created and sync queued"},
        400: {"description": "Validation error (e.g., exceeds plan limit)"},
        409: {"description": "A bulk import is already in progress"},
    },
)
async def confirm_bulk_import(
    request: BulkImportConfirmRequest,
    state: str = Query(..., description="OAuth state token from callback"),
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_MANAGE)),
    service: BulkImportService = Depends(get_bulk_import_service),
) -> BulkImportJobResponse:
    """Confirm bulk import selections and start sync."""
    try:
        result = await service.confirm_bulk_import(
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            state=state,
            auth_event_id=request.auth_event_id,
            organizations=[org.model_dump() for org in request.organizations],
        )
        return BulkImportJobResponse(**result)
    except BulkImportInProgressError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    except BulkImportValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message,
        ) from e
    except XeroOAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get(
    "/bulk-import/jobs",
    response_model=BulkImportJobListResponse,
    summary="List bulk import jobs for the tenant",
    description="""
    Returns paginated list of bulk import jobs ordered by creation date.

    **Required Permission**: `integration.read`
    """,
    responses={
        200: {"description": "List of bulk import jobs"},
    },
)
async def list_bulk_import_jobs(
    limit: int = Query(default=20, le=100, ge=1),
    offset: int = Query(default=0, ge=0),
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> BulkImportJobListResponse:
    """List bulk import jobs."""
    from app.modules.onboarding.repository import (
        BulkImportJobRepository,
        BulkImportOrganizationRepository,
    )

    job_repo = BulkImportJobRepository(session)
    org_repo = BulkImportOrganizationRepository(session)

    jobs = await job_repo.list_by_tenant(
        tenant_id=current_user.tenant_id,
        skip=offset,
        limit=limit,
    )

    job_responses = []
    for job in jobs:
        orgs = await org_repo.get_by_job_id(job.id, tenant_id=current_user.tenant_id)
        skipped_count = len([o for o in orgs if o.status == "skipped"])

        job_responses.append(
            BulkImportJobResponse(
                job_id=job.id,
                status=str(job.status),
                total_organizations=job.total_clients,
                imported_count=job.imported_count,
                failed_count=job.failed_count,
                skipped_count=skipped_count,
                progress_percent=job.progress_percent,
                created_at=job.created_at,
            )
        )

    # Get total count (all jobs, not paginated)
    all_jobs = await job_repo.list_by_tenant(
        tenant_id=current_user.tenant_id,
        skip=0,
        limit=1000,
    )

    return BulkImportJobListResponse(
        jobs=job_responses,
        total=len(all_jobs),
        limit=limit,
        offset=offset,
    )


@router.get(
    "/bulk-import/{job_id}",
    response_model=BulkImportJobDetailResponse,
    summary="Get bulk import job status with per-org details",
    description="""
    Returns the current status of a bulk import job including
    overall progress and per-organization sync status.

    **Required Permission**: `integration.read`
    """,
    responses={
        200: {"description": "Job status with per-org details"},
        404: {"description": "Job not found"},
    },
)
async def get_bulk_import_status(
    job_id: UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    session: AsyncSession = Depends(get_db_session),
) -> BulkImportJobDetailResponse:
    """Get bulk import job status."""
    from app.modules.onboarding.repository import (
        BulkImportJobRepository,
        BulkImportOrganizationRepository,
    )

    job_repo = BulkImportJobRepository(session)
    org_repo = BulkImportOrganizationRepository(session)

    job = await job_repo.get_by_id_and_tenant(job_id, current_user.tenant_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bulk import job {job_id} not found",
        )

    orgs = await org_repo.get_by_job_id(job_id, tenant_id=current_user.tenant_id)
    org_statuses = [
        BulkImportOrgStatus(
            xero_tenant_id=org.xero_tenant_id,
            organization_name=org.organization_name,
            status=org.status,
            connection_id=org.connection_id,
            connection_type=org.connection_type,
            assigned_user_id=org.assigned_user_id,
            error_message=org.error_message,
            sync_started_at=org.sync_started_at,
            sync_completed_at=org.sync_completed_at,
        )
        for org in orgs
    ]

    skipped_count = len([o for o in orgs if o.status == "skipped"])

    return BulkImportJobDetailResponse(
        job_id=job.id,
        status=str(job.status),
        total_organizations=job.total_clients,
        imported_count=job.imported_count,
        failed_count=job.failed_count,
        skipped_count=skipped_count,
        progress_percent=job.progress_percent,
        created_at=job.created_at,
        organizations=org_statuses,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


@router.post(
    "/bulk-import/{job_id}/retry",
    response_model=BulkImportJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Retry failed organization syncs",
    description="""
    Re-queues sync for organizations that failed in the specified job.

    **Required Permission**: `integration.manage`
    """,
    responses={
        202: {"description": "Retry queued for failed organizations"},
        400: {"description": "No failed organizations to retry"},
        404: {"description": "Job not found"},
    },
)
async def retry_failed_orgs(
    job_id: UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_MANAGE)),
    session: AsyncSession = Depends(get_db_session),
) -> BulkImportJobResponse:
    """Retry failed organizations in a bulk import job."""
    from app.modules.onboarding.models import BulkImportJobStatus
    from app.modules.onboarding.repository import (
        BulkImportJobRepository,
        BulkImportOrganizationRepository,
    )

    job_repo = BulkImportJobRepository(session)
    org_repo = BulkImportOrganizationRepository(session)

    job = await job_repo.get_by_id_and_tenant(job_id, current_user.tenant_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bulk import job {job_id} not found",
        )

    failed_orgs = await org_repo.get_failed_by_job_id(job_id, tenant_id=current_user.tenant_id)
    if not failed_orgs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No failed organizations to retry",
        )

    # Reset failed orgs to pending
    for org in failed_orgs:
        await org_repo.update_status(org.id, "pending", error_message=None)

    # Update job status back to in_progress
    await job_repo.update(
        job_id,
        {
            "status": BulkImportJobStatus.IN_PROGRESS,
            "failed_count": max(0, job.failed_count - len(failed_orgs)),
        },
    )

    # TODO: Queue Celery task for retry (T020)

    orgs = await org_repo.get_by_job_id(job_id, tenant_id=current_user.tenant_id)
    skipped_count = len([o for o in orgs if o.status == "skipped"])

    return BulkImportJobResponse(
        job_id=job.id,
        status=str(BulkImportJobStatus.IN_PROGRESS),
        total_organizations=job.total_clients,
        imported_count=job.imported_count,
        failed_count=max(0, job.failed_count - len(failed_orgs)),
        skipped_count=skipped_count,
        progress_percent=job.progress_percent,
        created_at=job.created_at,
    )


# =============================================================================
# Xero Webhooks (Phase 8 — US6)
# =============================================================================


@router.post(
    "/webhooks",
    status_code=status.HTTP_200_OK,
    summary="Receive Xero webhook events",
    description=(
        "Receives webhook events from Xero. Verifies HMAC-SHA256 signature "
        "using the X-Xero-Signature header. On initial registration, responds "
        "to intent-to-receive validation with HTTP 200. Events are stored "
        "asynchronously and processed via a background Celery task."
    ),
    tags=["Xero Integration"],
)
async def xero_webhook(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    x_xero_signature: Annotated[str | None, Header(alias="x-xero-signature")] = None,
) -> dict[str, str]:
    """Handle incoming Xero webhook events.

    This endpoint does NOT require Clerk JWT authentication since Xero
    sends webhooks directly. It is excluded from JWTMiddleware via
    DEFAULT_EXCLUDE_PATHS. Instead, requests are authenticated via
    HMAC-SHA256 signature verification.

    The endpoint:
    1. Reads the raw request body for signature verification
    2. Verifies the X-Xero-Signature header against the webhook signing key
    3. Handles intent-to-receive validation (empty events = registration check)
    4. Stores events as XeroWebhookEvent records for async processing
    5. Dispatches a Celery task to process the events
    6. Returns 200 immediately

    Args:
        request: FastAPI request object (for raw body access).
        session: Database session.
        settings: Application settings.
        x_xero_signature: Xero's HMAC-SHA256 signature of the payload.

    Returns:
        Simple acknowledgement dict.

    Raises:
        HTTPException: 401 if signature is invalid or missing.
    """
    import json

    from .webhook_handler import (
        is_intent_to_receive,
        store_webhook_events,
        verify_webhook_signature,
    )

    # Read raw body for signature verification
    raw_body = await request.body()

    # Verify signature
    if not x_xero_signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Xero-Signature header",
        )

    webhook_key = settings.xero.webhook_key
    if not verify_webhook_signature(raw_body, x_xero_signature, webhook_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    # Parse payload
    try:
        payload_data = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        ) from None

    # Handle intent-to-receive validation
    if is_intent_to_receive(payload_data):
        return {"status": "ok"}

    # Store events (with deduplication)
    stored_events = await store_webhook_events(session, payload_data)
    await session.commit()

    # Dispatch background processing task if any events were stored
    if stored_events:
        celery_app.send_task(
            "app.tasks.xero.process_webhook_events",
        )

    return {"status": "ok"}
