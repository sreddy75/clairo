"""Portal requests API router.

Provides endpoints for:
- Document request templates (CRUD)
- Document request management

Spec: 030-client-portal-document-requests
"""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_practice_user, get_db
from app.modules.auth.models import PracticeUser
from app.modules.portal.enums import BulkRequestStatus, RequestPriority, RequestStatus
from app.modules.portal.exceptions import (
    BulkRequestNotFoundError,
    PortalError,
    RequestNotFoundError,
    RequestTemplateNotFoundError,
)
from app.modules.portal.models import DocumentRequestTemplate
from app.modules.portal.repository import DocumentRequestTemplateRepository
from app.modules.portal.requests.bulk import BulkRequestService
from app.modules.portal.requests.service import DocumentRequestService
from app.modules.portal.requests.templates import SYSTEM_TEMPLATES
from app.modules.portal.schemas import (
    AutoRemindResponse,
    AutoRemindToggleRequest,
    BulkRequestCreateRequest,
    BulkRequestDetailResponse,
    BulkRequestListResponse,
    BulkRequestResponse,
    DocumentResponse,
    EventResponse,
    ReminderSettingsRequest,
    ReminderSettingsResponse,
    RequestCreateRequest,
    RequestDetailResponse,
    RequestListResponse,
    RequestResponse,
    RequestUpdateRequest,
    ResponseDetailResponse,
    SendReminderResponse,
    TemplateCreateRequest,
    TemplateListResponse,
    TemplateResponse,
    TemplateUpdateRequest,
    TrackingRequestItem,
    TrackingResponse,
    TrackingStatusGroup,
    TrackingSummary,
    TrackingSummaryResponse,
)

router = APIRouter(prefix="/request-templates", tags=["Document Request Templates"])
requests_router = APIRouter(tags=["Document Requests"])


# =============================================================================
# Template Endpoints
# =============================================================================


@router.get(
    "",
    response_model=TemplateListResponse,
    summary="List available templates",
)
async def list_templates(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
    include_inactive: bool = Query(
        default=False,
        description="Include inactive templates",
    ),
) -> TemplateListResponse:
    """List all document request templates available to the tenant.

    Returns both system templates and tenant-specific templates.
    System templates are shared across all tenants.
    """
    repo = DocumentRequestTemplateRepository(db)
    templates = await repo.list_available(
        tenant_id=user.tenant_id,
        include_inactive=include_inactive,
    )

    # If no templates in DB, seed system templates first
    if not templates:
        await _seed_system_templates(db)
        templates = await repo.list_available(
            tenant_id=user.tenant_id,
            include_inactive=include_inactive,
        )

    return TemplateListResponse(
        templates=[TemplateResponse.model_validate(t) for t in templates],
        total=len(templates),
    )


@router.get(
    "/{template_id}",
    response_model=TemplateResponse,
    summary="Get template by ID",
)
async def get_template(
    template_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> TemplateResponse:
    """Get a specific template by ID.

    Returns the template if it's a system template or belongs to the tenant.
    """
    repo = DocumentRequestTemplateRepository(db)
    template = await repo.get_by_id_and_tenant(
        template_id=template_id,
        tenant_id=user.tenant_id,
    )

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    return TemplateResponse.model_validate(template)


@router.post(
    "",
    response_model=TemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a custom template",
)
async def create_template(
    request: TemplateCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> TemplateResponse:
    """Create a new custom template for the tenant.

    Custom templates are only available to the creating tenant.
    """
    repo = DocumentRequestTemplateRepository(db)

    template = DocumentRequestTemplate(
        tenant_id=user.tenant_id,
        name=request.name,
        description_template=request.description_template,
        expected_document_types=request.expected_document_types,
        icon=request.icon,
        default_priority=request.default_priority.value,
        default_due_days=request.default_due_days,
        is_system=False,
        is_active=True,
        created_by=user.user_id,
    )

    created = await repo.create(template)
    await db.commit()

    return TemplateResponse.model_validate(created)


@router.patch(
    "/{template_id}",
    response_model=TemplateResponse,
    summary="Update a template",
)
async def update_template(
    template_id: UUID,
    request: TemplateUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> TemplateResponse:
    """Update an existing template.

    Only tenant-owned templates can be updated.
    System templates cannot be modified.
    """
    repo = DocumentRequestTemplateRepository(db)

    # Get the template
    template = await repo.get_by_id_and_tenant(
        template_id=template_id,
        tenant_id=user.tenant_id,
    )

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    # Cannot modify system templates
    if template.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify system templates",
        )

    # Build update data
    update_data = {}
    if request.name is not None:
        update_data["name"] = request.name
    if request.description_template is not None:
        update_data["description_template"] = request.description_template
    if request.expected_document_types is not None:
        update_data["expected_document_types"] = request.expected_document_types
    if request.icon is not None:
        update_data["icon"] = request.icon
    if request.default_priority is not None:
        update_data["default_priority"] = request.default_priority.value
    if request.default_due_days is not None:
        update_data["default_due_days"] = request.default_due_days
    if request.is_active is not None:
        update_data["is_active"] = request.is_active

    if not update_data:
        return TemplateResponse.model_validate(template)

    updated = await repo.update(template_id, update_data)
    await db.commit()

    return TemplateResponse.model_validate(updated)


@router.delete(
    "/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a template",
)
async def delete_template(
    template_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> None:
    """Delete a template (soft delete by marking inactive).

    Only tenant-owned templates can be deleted.
    System templates cannot be deleted.
    """
    repo = DocumentRequestTemplateRepository(db)

    # Get the template
    template = await repo.get_by_id_and_tenant(
        template_id=template_id,
        tenant_id=user.tenant_id,
    )

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    # Cannot delete system templates
    if template.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete system templates",
        )

    # Soft delete
    await repo.update(template_id, {"is_active": False})
    await db.commit()


# =============================================================================
# Helper Functions
# =============================================================================


async def _seed_system_templates(db: AsyncSession) -> None:
    """Seed system templates into the database.

    This is called on first access to ensure templates are available.
    Uses individual inserts with conflict handling to be idempotent.
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    for sys_template in SYSTEM_TEMPLATES:
        stmt = (
            pg_insert(DocumentRequestTemplate)
            .values(
                id=sys_template.id,
                tenant_id=None,
                name=sys_template.name,
                description_template=sys_template.description_template,
                expected_document_types=sys_template.expected_document_types,
                icon=sys_template.icon,
                default_priority=sys_template.default_priority.value,
                default_due_days=sys_template.default_due_days,
                is_system=True,
                is_active=True,
                created_by=None,
            )
            .on_conflict_do_nothing(index_elements=["id"])
        )

        await db.execute(stmt)

    await db.commit()


# =============================================================================
# Document Request Endpoints
# =============================================================================


@requests_router.post(
    "/clients/{connection_id}/requests",
    response_model=RequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a document request for a client",
)
async def create_request(
    connection_id: UUID,
    request: RequestCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> RequestResponse:
    """Create a new document request for a client.

    If send_immediately is True (default), the request is sent immediately.
    Otherwise, it's saved as a draft for later sending.
    """
    # Override connection_id from path
    request_data = RequestCreateRequest(
        connection_id=connection_id,
        template_id=request.template_id,
        title=request.title,
        description=request.description,
        recipient_email=request.recipient_email,
        due_date=request.due_date,
        priority=request.priority,
        period_start=request.period_start,
        period_end=request.period_end,
        auto_remind=request.auto_remind,
        send_immediately=request.send_immediately,
    )

    service = DocumentRequestService(db)

    try:
        doc_request = await service.create_request(
            tenant_id=user.tenant_id,
            user_id=user.user_id,
            data=request_data,
        )
        await db.commit()
        return service.to_response(doc_request)
    except RequestTemplateNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PortalError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=str(e),
        )


@requests_router.post(
    "/requests/{request_id}/send",
    response_model=RequestResponse,
    summary="Send a draft document request",
)
async def send_request(
    request_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> RequestResponse:
    """Send a draft document request.

    Changes the status from draft to pending and triggers notifications.
    """
    service = DocumentRequestService(db)

    try:
        doc_request = await service.send_request(
            request_id=request_id,
            tenant_id=user.tenant_id,
            user_id=user.user_id,
        )
        await db.commit()
        return service.to_response(doc_request)
    except RequestNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PortalError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=str(e),
        )


@requests_router.get(
    "/clients/{connection_id}/requests",
    response_model=RequestListResponse,
    summary="List document requests for a client",
)
async def list_client_requests(
    connection_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
    status_filter: RequestStatus | None = Query(None, alias="status"),
    priority: RequestPriority | None = None,
    is_overdue: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> RequestListResponse:
    """List all document requests for a specific client."""
    service = DocumentRequestService(db)
    skip = (page - 1) * page_size

    requests, total = await service.list_requests(
        tenant_id=user.tenant_id,
        connection_id=connection_id,
        status=status_filter,
        priority=priority,
        is_overdue=is_overdue,
        skip=skip,
        limit=page_size,
    )

    return RequestListResponse(
        requests=[service.to_response(r) for r in requests],
        total=total,
        page=page,
        page_size=page_size,
    )


@requests_router.get(
    "/requests",
    response_model=RequestListResponse,
    summary="List all document requests for the tenant",
)
async def list_requests(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
    connection_id: UUID | None = None,
    status_filter: RequestStatus | None = Query(None, alias="status"),
    priority: RequestPriority | None = None,
    is_overdue: bool | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    search: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> RequestListResponse:
    """List all document requests for the tenant with filters."""
    service = DocumentRequestService(db)
    skip = (page - 1) * page_size

    requests, total = await service.list_requests(
        tenant_id=user.tenant_id,
        connection_id=connection_id,
        status=status_filter,
        priority=priority,
        is_overdue=is_overdue,
        from_date=from_date,
        to_date=to_date,
        search=search,
        skip=skip,
        limit=page_size,
    )

    return RequestListResponse(
        requests=[service.to_response(r) for r in requests],
        total=total,
        page=page,
        page_size=page_size,
    )


@requests_router.get(
    "/requests/{request_id}",
    response_model=RequestDetailResponse,
    summary="Get a document request by ID",
)
async def get_request(
    request_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> RequestDetailResponse:
    """Get a specific document request with all details."""
    service = DocumentRequestService(db)

    try:
        doc_request = await service.get_request_with_details(
            request_id=request_id,
            tenant_id=user.tenant_id,
        )

        # Get organization name from connection (avoid lazy load)
        org_name = "Unknown"
        if "connection" in doc_request.__dict__ and doc_request.connection:
            org_name = doc_request.connection.organization_name or "Unknown"

        # Convert responses with documents
        response_details = []
        if "responses" in doc_request.__dict__ and doc_request.responses:
            for resp in doc_request.responses:
                # Convert documents
                doc_list = []
                if "documents" in resp.__dict__ and resp.documents:
                    for doc in resp.documents:
                        doc_list.append(
                            DocumentResponse(
                                id=doc.id,
                                connection_id=doc.connection_id,
                                response_id=doc.response_id,
                                filename=doc.filename,
                                original_filename=doc.original_filename,
                                content_type=doc.content_type,
                                file_size=doc.file_size,
                                document_type=doc.document_type,
                                period_start=doc.period_start,
                                period_end=doc.period_end,
                                tags=doc.tags,
                                uploaded_at=doc.uploaded_at,
                                uploaded_by_client=doc.uploaded_by_client,
                                scan_status=doc.scan_status,
                                scanned_at=doc.scanned_at,
                            )
                        )
                response_details.append(
                    ResponseDetailResponse(
                        id=resp.id,
                        request_id=resp.request_id,
                        note=resp.note,
                        submitted_at=resp.submitted_at,
                        document_count=len(doc_list),
                        documents=doc_list,
                    )
                )

        # Convert events
        event_responses = []
        if "events" in doc_request.__dict__ and doc_request.events:
            for evt in doc_request.events:
                event_responses.append(
                    EventResponse(
                        id=evt.id,
                        request_id=evt.request_id,
                        event_type=evt.event_type,
                        event_data=evt.event_data,
                        actor_type=evt.actor_type,
                        actor_id=evt.actor_id,
                        created_at=evt.created_at,
                    )
                )

        response = service.to_response(doc_request)
        return RequestDetailResponse(
            **response.model_dump(),
            organization_name=org_name,
            responses=response_details,
            events=event_responses,
        )
    except RequestNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@requests_router.get(
    "/documents/{document_id}/download",
    summary="Download a portal document",
)
async def download_document(
    document_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> StreamingResponse:
    """Download a portal document directly.

    Accountants can download documents uploaded by their clients.
    Streams the file from MinIO through the backend.
    """
    from io import BytesIO
    from urllib.parse import quote

    from minio import Minio
    from minio.error import S3Error

    from app.config import MinioSettings
    from app.modules.portal.repository import PortalDocumentRepository

    doc_repo = PortalDocumentRepository(db)

    # Get document and verify tenant access
    document = await doc_repo.get_by_id_and_tenant(document_id, user.tenant_id)
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Get file from MinIO
    settings = MinioSettings()
    client = Minio(
        settings.endpoint,
        access_key=settings.access_key,
        secret_key=settings.secret_key.get_secret_value(),
        secure=settings.use_ssl,
    )

    try:
        response = client.get_object(settings.bucket, document.s3_key)
        file_data = response.read()
        response.close()
        response.release_conn()
    except S3Error as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve document: {e}",
        )

    # Return as streaming response with proper headers
    return StreamingResponse(
        BytesIO(file_data),
        media_type=document.content_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{quote(document.original_filename)}"',
            "Content-Length": str(document.file_size),
        },
    )


@requests_router.patch(
    "/requests/{request_id}",
    response_model=RequestResponse,
    summary="Update a document request",
)
async def update_request(
    request_id: UUID,
    request: RequestUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> RequestResponse:
    """Update a document request.

    Limited updates are allowed once a request has been viewed.
    """
    service = DocumentRequestService(db)

    # Build update data from request
    update_data = {}
    if request.title is not None:
        update_data["title"] = request.title
    if request.description is not None:
        update_data["description"] = request.description
    if request.due_date is not None:
        update_data["due_date"] = request.due_date
    if request.priority is not None:
        update_data["priority"] = request.priority.value
    if request.auto_remind is not None:
        update_data["auto_remind"] = request.auto_remind

    try:
        doc_request = await service.update_request(
            request_id=request_id,
            tenant_id=user.tenant_id,
            user_id=user.user_id,
            **update_data,
        )
        await db.commit()
        return service.to_response(doc_request)
    except RequestNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PortalError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=str(e),
        )


@requests_router.post(
    "/requests/{request_id}/cancel",
    response_model=RequestResponse,
    summary="Cancel a document request",
)
async def cancel_request(
    request_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
    reason: str | None = Query(None, max_length=255),
) -> RequestResponse:
    """Cancel a document request."""
    service = DocumentRequestService(db)

    try:
        doc_request = await service.cancel_request(
            request_id=request_id,
            tenant_id=user.tenant_id,
            user_id=user.user_id,
            reason=reason,
        )
        await db.commit()
        return service.to_response(doc_request)
    except RequestNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PortalError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=str(e),
        )


@requests_router.post(
    "/requests/{request_id}/complete",
    response_model=RequestResponse,
    summary="Mark a document request as complete",
)
async def complete_request(
    request_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
    note: str | None = Query(None, max_length=500),
) -> RequestResponse:
    """Mark a document request as complete."""
    service = DocumentRequestService(db)

    try:
        doc_request = await service.complete_request(
            request_id=request_id,
            tenant_id=user.tenant_id,
            user_id=user.user_id,
            note=note,
        )
        await db.commit()
        return service.to_response(doc_request)
    except RequestNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PortalError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=str(e),
        )


# =============================================================================
# Bulk Request Endpoints
# =============================================================================


@requests_router.post(
    "/bulk-requests",
    response_model=BulkRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a bulk document request",
)
async def create_bulk_request(
    request: BulkRequestCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> BulkRequestResponse:
    """Create a bulk document request to send to multiple clients.

    The individual requests are processed asynchronously via Celery.
    """
    service = BulkRequestService(db)

    try:
        bulk_request = await service.create_bulk_request(
            tenant_id=user.tenant_id,
            user_id=user.user_id,
            data=request,
        )
        await db.commit()

        # Queue Celery task to process the bulk request
        try:
            from app.tasks.portal.send_bulk_requests import process_bulk_request_task

            process_bulk_request_task.delay(
                bulk_id=str(bulk_request.id),
                connection_ids=[str(c) for c in request.connection_ids],
                title=request.title,
                description=request.description,
                priority=request.priority.value,
                due_date=request.due_date.isoformat() if request.due_date else None,
                template_id=str(request.template_id) if request.template_id else None,
                tenant_id=str(user.tenant_id),
                user_id=str(user.user_id),
            )
        except ImportError:
            # Celery not available in test environment
            pass

        return service.to_response(bulk_request)
    except RequestTemplateNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PortalError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=str(e),
        )


@requests_router.post(
    "/bulk-requests/preview",
    summary="Preview a bulk document request",
)
async def preview_bulk_request(
    request: BulkRequestCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> dict:
    """Preview a bulk request before sending.

    Returns information about the clients that will receive the request.
    """
    service = BulkRequestService(db)
    return await service.preview_bulk_request(
        tenant_id=user.tenant_id,
        connection_ids=request.connection_ids,
    )


@requests_router.get(
    "/bulk-requests",
    response_model=BulkRequestListResponse,
    summary="List bulk document requests",
)
async def list_bulk_requests(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
    status_filter: BulkRequestStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> BulkRequestListResponse:
    """List all bulk document requests for the tenant."""
    service = BulkRequestService(db)
    skip = (page - 1) * page_size

    bulk_requests, total = await service.list_bulk_requests(
        tenant_id=user.tenant_id,
        status=status_filter,
        skip=skip,
        limit=page_size,
    )

    return BulkRequestListResponse(
        bulk_requests=[service.to_response(r) for r in bulk_requests],
        total=total,
    )


@requests_router.get(
    "/bulk-requests/{bulk_id}",
    response_model=BulkRequestDetailResponse,
    summary="Get a bulk document request by ID",
)
async def get_bulk_request(
    bulk_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> BulkRequestDetailResponse:
    """Get a specific bulk request with details."""
    service = BulkRequestService(db)

    try:
        bulk_request = await service.get_bulk_request(
            bulk_id=bulk_id,
            tenant_id=user.tenant_id,
        )

        response = service.to_response(bulk_request)
        return BulkRequestDetailResponse(
            **response.model_dump(),
            requests=[],  # Would be populated from relationships
            failed_connections=[],
        )
    except BulkRequestNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# =============================================================================
# Request Tracking Endpoints
# =============================================================================


@requests_router.get(
    "/requests/tracking",
    response_model=TrackingResponse,
    summary="Get request tracking data",
)
async def get_tracking_data(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
    status_filter: RequestStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> TrackingResponse:
    """Get request tracking dashboard data.

    Returns summary statistics and requests grouped by status.
    Use this for the main tracking dashboard view.
    """
    from datetime import date as date_type

    service = DocumentRequestService(db)
    skip = (page - 1) * page_size

    summary, requests = await service.get_tracking_data(
        tenant_id=user.tenant_id,
        status=status_filter,
        skip=skip,
        limit=page_size,
    )

    # Convert requests to tracking items
    today = date_type.today()
    tracking_items = []
    for req in requests:
        org_name = "Unknown"
        if hasattr(req, "connection") and req.connection:
            org_name = req.connection.organization_name or "Unknown"

        is_overdue = False
        days_until_due = None
        if req.due_date:
            days_until_due = (req.due_date - today).days
            if days_until_due < 0 and req.status not in [
                RequestStatus.COMPLETE.value,
                RequestStatus.CANCELLED.value,
            ]:
                is_overdue = True

        tracking_items.append(
            TrackingRequestItem(
                id=req.id,
                connection_id=req.connection_id,
                organization_name=org_name,
                title=req.title,
                due_date=req.due_date,
                priority=RequestPriority(req.priority),
                status=RequestStatus(req.status),
                sent_at=req.sent_at,
                viewed_at=req.viewed_at,
                responded_at=req.responded_at,
                is_overdue=is_overdue,
                days_until_due=days_until_due,
                response_count=len(req.responses)
                if hasattr(req, "responses") and req.responses
                else 0,
            )
        )

    # Group by status
    groups: dict[RequestStatus, list[TrackingRequestItem]] = {}
    for item in tracking_items:
        if item.status not in groups:
            groups[item.status] = []
        groups[item.status].append(item)

    status_groups = [
        TrackingStatusGroup(
            status=status,
            count=len(items),
            requests=items,
        )
        for status, items in groups.items()
    ]

    return TrackingResponse(
        summary=TrackingSummary(**summary),
        groups=status_groups,
        page=page,
        page_size=page_size,
    )


@requests_router.get(
    "/requests/tracking/summary",
    response_model=TrackingSummaryResponse,
    summary="Get request tracking summary",
)
async def get_tracking_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> TrackingSummaryResponse:
    """Get quick summary of request tracking statistics.

    Returns counts by status plus overdue, due today, due this week.
    Also includes recent activity for quick reference.
    """
    from datetime import date as date_type

    service = DocumentRequestService(db)

    summary = await service.get_tracking_summary(user.tenant_id)
    recent_requests = await service.get_recent_activity(user.tenant_id, limit=5)

    # Convert recent requests to tracking items
    today = date_type.today()
    recent_items = []
    for req in recent_requests:
        org_name = "Unknown"
        if hasattr(req, "connection") and req.connection:
            org_name = req.connection.organization_name or "Unknown"

        is_overdue = False
        days_until_due = None
        if req.due_date:
            days_until_due = (req.due_date - today).days
            if days_until_due < 0 and req.status not in [
                RequestStatus.COMPLETE.value,
                RequestStatus.CANCELLED.value,
            ]:
                is_overdue = True

        recent_items.append(
            TrackingRequestItem(
                id=req.id,
                connection_id=req.connection_id,
                organization_name=org_name,
                title=req.title,
                due_date=req.due_date,
                priority=RequestPriority(req.priority),
                status=RequestStatus(req.status),
                sent_at=req.sent_at,
                viewed_at=req.viewed_at,
                responded_at=req.responded_at,
                is_overdue=is_overdue,
                days_until_due=days_until_due,
                response_count=len(req.responses)
                if hasattr(req, "responses") and req.responses
                else 0,
            )
        )

    return TrackingSummaryResponse(
        summary=TrackingSummary(**summary),
        recent_activity=recent_items,
    )


# =============================================================================
# Auto-Remind Endpoints
# =============================================================================


@requests_router.get(
    "/requests/{request_id}/auto-remind",
    response_model=AutoRemindResponse,
    summary="Get auto-remind status for a request",
)
async def get_auto_remind_status(
    request_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> AutoRemindResponse:
    """Get the auto-remind status for a document request."""
    service = DocumentRequestService(db)

    try:
        doc_request = await service.get_request(
            request_id=request_id,
            tenant_id=user.tenant_id,
        )
        return AutoRemindResponse(
            request_id=doc_request.id,
            auto_remind=doc_request.auto_remind,
            last_reminder_at=doc_request.last_reminder_at,
            reminder_count=doc_request.reminder_count,
        )
    except RequestNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@requests_router.patch(
    "/requests/{request_id}/auto-remind",
    response_model=AutoRemindResponse,
    summary="Toggle auto-remind for a request",
)
async def toggle_auto_remind(
    request_id: UUID,
    request: AutoRemindToggleRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> AutoRemindResponse:
    """Enable or disable auto-remind for a document request."""
    service = DocumentRequestService(db)

    try:
        doc_request = await service.toggle_auto_remind(
            request_id=request_id,
            tenant_id=user.tenant_id,
            user_id=user.user_id,
            enabled=request.enabled,
        )
        await db.commit()
        return AutoRemindResponse(
            request_id=doc_request.id,
            auto_remind=doc_request.auto_remind,
            last_reminder_at=doc_request.last_reminder_at,
            reminder_count=doc_request.reminder_count,
        )
    except RequestNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PortalError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=str(e),
        )


@requests_router.post(
    "/requests/{request_id}/send-reminder",
    response_model=SendReminderResponse,
    summary="Send a manual reminder for a request",
)
async def send_manual_reminder(
    request_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> SendReminderResponse:
    """Send a manual reminder for a document request.

    This bypasses the auto-remind schedule and sends a reminder immediately.
    """
    service = DocumentRequestService(db)

    try:
        doc_request = await service.send_reminder(
            request_id=request_id,
            tenant_id=user.tenant_id,
            reminder_type="manual",
        )
        await db.commit()
        return SendReminderResponse(
            request_id=doc_request.id,
            reminder_count=doc_request.reminder_count,
            last_reminder_at=doc_request.last_reminder_at,
        )
    except RequestNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except PortalError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=str(e),
        )


# =============================================================================
# Reminder Settings Endpoints
# =============================================================================


@requests_router.get(
    "/settings/reminders",
    response_model=ReminderSettingsResponse,
    summary="Get tenant reminder settings",
)
async def get_reminder_settings(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> ReminderSettingsResponse:
    """Get the reminder settings for the current tenant.

    Returns default settings if none are configured.
    """
    # TODO: Load from tenant settings table when implemented
    # For now, return default settings
    return ReminderSettingsResponse(
        tenant_id=user.tenant_id,
        days_before_due=3,
        overdue_reminder_days=[1, 3, 7],
        min_days_between_reminders=3,
        auto_remind_enabled=True,
    )


@requests_router.patch(
    "/settings/reminders",
    response_model=ReminderSettingsResponse,
    summary="Update tenant reminder settings",
)
async def update_reminder_settings(
    request: ReminderSettingsRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[PracticeUser, Depends(get_current_practice_user)],
) -> ReminderSettingsResponse:
    """Update the reminder settings for the current tenant.

    These settings control automatic reminders for all document requests.
    """
    # TODO: Save to tenant settings table when implemented
    # For now, just return the requested settings as confirmation
    return ReminderSettingsResponse(
        tenant_id=user.tenant_id,
        days_before_due=request.days_before_due,
        overdue_reminder_days=request.overdue_reminder_days,
        min_days_between_reminders=request.min_days_between_reminders,
        auto_remind_enabled=request.auto_remind_enabled,
    )
