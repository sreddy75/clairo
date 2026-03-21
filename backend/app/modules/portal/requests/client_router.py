"""Client-facing document request endpoints.

Portal endpoints for clients to view, respond to, and manage their document requests.

Spec: 030-client-portal-document-requests
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.portal.auth.dependencies import get_current_portal_session
from app.modules.portal.enums import RequestStatus
from app.modules.portal.exceptions import PortalError, RequestNotFoundError
from app.modules.portal.models import PortalSession
from app.modules.portal.requests.service import DocumentRequestService
from app.modules.portal.schemas import RequestResponse

router = APIRouter(prefix="/portal/requests", tags=["portal-requests"])


# =============================================================================
# Schemas
# =============================================================================


class ClientRequestListResponse(BaseModel):
    """Response for listing client requests."""

    requests: list[RequestResponse]
    total: int
    page: int
    page_size: int


class SubmitResponseRequest(BaseModel):
    """Request body for submitting a response."""

    message: str | None = Field(None, max_length=2000)
    document_ids: list[UUID] | None = None


class SubmitResponseResponse(BaseModel):
    """Response for submitting a response."""

    success: bool
    message: str
    request: RequestResponse


# =============================================================================
# Endpoints
# =============================================================================


@router.get("", response_model=ClientRequestListResponse)
async def list_client_requests(
    session: Annotated[PortalSession, Depends(get_current_portal_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Annotated[RequestStatus | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ClientRequestListResponse:
    """List document requests for the authenticated client.

    Returns all non-draft requests visible to the client, ordered by date.
    """
    service = DocumentRequestService(db)

    skip = (page - 1) * page_size
    requests, total = await service.list_client_requests(
        connection_id=session.connection_id,
        status=status_filter,
        skip=skip,
        limit=page_size,
    )

    return ClientRequestListResponse(
        requests=[service.to_response(r) for r in requests],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{request_id}", response_model=RequestResponse)
async def get_client_request(
    request_id: UUID,
    http_request: Request,
    session: Annotated[PortalSession, Depends(get_current_portal_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RequestResponse:
    """Get a specific document request.

    Also marks the request as viewed if currently pending.
    """
    service = DocumentRequestService(db)

    # Get client info for logging
    ip_address = http_request.client.host if http_request.client else None
    user_agent = http_request.headers.get("user-agent")

    try:
        # Mark as viewed (idempotent - only marks if pending)
        request = await service.mark_viewed(
            request_id=request_id,
            connection_id=session.connection_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await db.commit()
        return service.to_response(request)

    except RequestNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request not found",
        )


@router.post("/{request_id}/respond", response_model=SubmitResponseResponse)
async def submit_response(
    request_id: UUID,
    body: SubmitResponseRequest,
    http_request: Request,
    session: Annotated[PortalSession, Depends(get_current_portal_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SubmitResponseResponse:
    """Submit a response to a document request.

    Can include a message and/or document attachments.
    """
    service = DocumentRequestService(db)

    # Get client info for logging
    ip_address = http_request.client.host if http_request.client else None
    user_agent = http_request.headers.get("user-agent")

    try:
        request = await service.submit_response(
            request_id=request_id,
            connection_id=session.connection_id,
            message=body.message,
            document_ids=body.document_ids,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await db.commit()
        return SubmitResponseResponse(
            success=True,
            message="Response submitted successfully",
            request=service.to_response(request),
        )

    except RequestNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request not found",
        )
    except PortalError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/{request_id}/responses")
async def list_request_responses(
    request_id: UUID,
    session: Annotated[PortalSession, Depends(get_current_portal_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """List all responses submitted for a request."""
    from app.modules.portal.repository import RequestResponseRepository

    service = DocumentRequestService(db)

    # Verify access
    try:
        await service.get_client_request(
            request_id=request_id,
            connection_id=session.connection_id,
        )
    except RequestNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request not found",
        )

    # Get responses
    response_repo = RequestResponseRepository(db)
    responses = await response_repo.list_by_request(request_id)

    return {
        "responses": [
            {
                "id": str(r.id),
                "message": r.message,
                "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
            }
            for r in responses
        ],
        "total": len(responses),
    }
