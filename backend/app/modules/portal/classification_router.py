"""Client-facing API endpoints for transaction classification.

Spec 047: Client Transaction Classification.
These endpoints are authenticated via portal magic link (not Clerk).
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.modules.bas.classification_schemas import (
    ClientClassificationSave,
    ClientClassificationSaveResponse,
    ClientClassificationSubmitResponse,
    ClientClassifyPageResponse,
)
from app.modules.bas.classification_service import ClassificationService
from app.modules.bas.exceptions import (
    ClassificationNotFoundError,
    ClassificationRequestExpiredError,
    ClassificationRequestNotFoundError,
)
from app.modules.portal.auth.dependencies import CurrentPortalClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/client-portal/classify", tags=["portal-classification"])


@router.get(
    "/pending",
    summary="Get pending classification requests for this client",
)
async def get_pending_classifications(
    portal_client: CurrentPortalClient,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Check if there are any active classification requests for this client's connection."""
    from sqlalchemy import select

    from app.modules.bas.classification_models import (
        ClassificationRequest,
        ClassificationRequestStatus,
    )

    result = await db.execute(
        select(ClassificationRequest).where(
            ClassificationRequest.connection_id == portal_client.connection_id,
            ClassificationRequest.status.in_(ClassificationRequestStatus.ACTIVE),
        )
    )
    requests = result.scalars().all()

    return [
        {
            "id": str(r.id),
            "status": r.status,
            "transaction_count": r.transaction_count,
            "classified_count": r.classified_count,
            "message": r.message,
            "expires_at": r.expires_at.isoformat() if r.expires_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in requests
    ]


@router.get(
    "/{request_id}",
    response_model=ClientClassifyPageResponse,
    summary="Get classification request for client",
)
async def get_classification_request_client(
    request_id: UUID,
    portal_client: CurrentPortalClient,
    db: AsyncSession = Depends(get_db),
) -> ClientClassifyPageResponse:
    """Get the classification page data for a client.

    Authenticated via portal magic link. Returns transactions with
    plain-English categories — no tax codes exposed.
    """
    try:
        service = ClassificationService(db)
        result = await service.get_client_view(request_id, portal_client.connection_id)
        return ClientClassifyPageResponse(**result)
    except ClassificationRequestNotFoundError:
        raise HTTPException(status_code=404, detail="Classification request not found")
    except ClassificationRequestExpiredError:
        raise HTTPException(status_code=410, detail="This classification request has expired")


@router.put(
    "/{request_id}/transactions/{classification_id}",
    response_model=ClientClassificationSaveResponse,
    summary="Save a transaction classification",
)
async def save_classification(
    request_id: UUID,
    classification_id: UUID,
    body: ClientClassificationSave,
    portal_client: CurrentPortalClient,
    db: AsyncSession = Depends(get_db),
) -> ClientClassificationSaveResponse:
    """Save a client's classification for a single transaction.

    Auto-saves as the client works through the list.
    """
    try:
        service = ClassificationService(db)
        result = await service.save_classification(
            classification_id=classification_id,
            request_id=request_id,
            connection_id=portal_client.connection_id,
            portal_session_id=getattr(portal_client, "session_id", None),
            data=body.model_dump(exclude_none=True),
        )
        return ClientClassificationSaveResponse(**result)
    except ClassificationRequestNotFoundError:
        raise HTTPException(status_code=404, detail="Classification request not found")
    except ClassificationNotFoundError:
        raise HTTPException(status_code=404, detail="Classification not found")


@router.post(
    "/{request_id}/submit",
    response_model=ClientClassificationSubmitResponse,
    summary="Submit classifications",
)
async def submit_classifications(
    request_id: UUID,
    portal_client: CurrentPortalClient,
    db: AsyncSession = Depends(get_db),
) -> ClientClassificationSubmitResponse:
    """Submit all classifications for a request.

    Partial submissions accepted — not all transactions must be classified.
    """
    try:
        service = ClassificationService(db)
        result = await service.submit_classifications(request_id, portal_client.connection_id)
        return ClientClassificationSubmitResponse(**result)
    except ClassificationRequestNotFoundError:
        raise HTTPException(status_code=404, detail="Classification request not found")


@router.post(
    "/{request_id}/transactions/{classification_id}/receipt",
    summary="Upload a receipt for a transaction",
)
async def upload_receipt(
    request_id: UUID,
    classification_id: UUID,
    file: UploadFile,
    portal_client: CurrentPortalClient,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Upload a receipt or invoice for a specific transaction.

    Uses the existing portal document upload infrastructure.
    """
    # TODO: Integrate with PortalDocument upload service
    # For now, return a placeholder — the full upload flow requires
    # the portal document service which handles S3, virus scan, etc.
    try:
        service = ClassificationService(db)
        # In a full implementation, we'd first upload via PortalDocumentService,
        # get the document_id, then attach it to the classification.
        return {
            "document_id": None,
            "filename": file.filename,
            "size": file.size,
            "message": "Receipt upload endpoint ready — full S3 integration pending",
        }
    except ClassificationRequestNotFoundError:
        raise HTTPException(status_code=404, detail="Classification request not found")
    except ClassificationNotFoundError:
        raise HTTPException(status_code=404, detail="Classification not found")
