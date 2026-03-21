"""Portal Document Upload Endpoints.

Endpoints for uploading and managing documents in the client portal.

Spec: 030-client-portal-document-requests
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.portal.auth.dependencies import get_current_portal_session
from app.modules.portal.documents.upload import PortalUploadService, UploadError
from app.modules.portal.models import PortalSession
from app.modules.portal.repository import PortalDocumentRepository

router = APIRouter(prefix="/portal/documents", tags=["portal-documents"])


# =============================================================================
# Schemas
# =============================================================================


class DocumentUploadResponse(BaseModel):
    """Response for successful document upload."""

    id: str
    filename: str
    content_type: str
    file_size: int
    uploaded_at: datetime


class PresignedUploadRequest(BaseModel):
    """Request for presigned upload URL."""

    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str | None = None
    file_size: int | None = Field(None, ge=1, le=50 * 1024 * 1024)


class PresignedUploadResponse(BaseModel):
    """Response with presigned upload URL."""

    upload_url: str
    document_id: str
    storage_key: str
    content_type: str
    expires_in: int


class ConfirmUploadRequest(BaseModel):
    """Request to confirm a presigned upload."""

    document_id: str
    storage_key: str
    filename: str
    content_type: str
    file_size: int = Field(..., ge=1)
    document_type: str | None = None


class DocumentListResponse(BaseModel):
    """Response for listing documents."""

    documents: list[DocumentUploadResponse]
    total: int


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    session: Annotated[PortalSession, Depends(get_current_portal_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
    document_type: str | None = Form(None),
) -> DocumentUploadResponse:
    """Upload a document directly.

    Accepts multipart/form-data with the file and optional metadata.
    Maximum file size: 50MB.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    # Get file size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning

    service = PortalUploadService(db)

    try:
        document = await service.upload_document(
            file=file.file,
            filename=file.filename,
            content_type=file.content_type,
            file_size=file_size,
            tenant_id=session.tenant_id,
            connection_id=session.connection_id,
            document_type=document_type,
        )

        await db.commit()

        return DocumentUploadResponse(
            id=str(document.id),
            filename=document.original_filename,
            content_type=document.content_type,
            file_size=document.file_size,
            uploaded_at=document.uploaded_at,
        )

    except UploadError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/upload-url", response_model=PresignedUploadResponse)
async def get_presigned_upload_url(
    body: PresignedUploadRequest,
    session: Annotated[PortalSession, Depends(get_current_portal_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PresignedUploadResponse:
    """Get a presigned URL for direct upload to storage.

    Use this for large files or when you need upload progress.
    After uploading, call /upload/confirm to create the database record.
    """
    service = PortalUploadService(db)

    try:
        result = service.get_presigned_upload_url(
            tenant_id=session.tenant_id,
            connection_id=session.connection_id,
            filename=body.filename,
            content_type=body.content_type,
        )

        return PresignedUploadResponse(
            upload_url=result["upload_url"],
            document_id=result["document_id"],
            storage_key=result["storage_key"],
            content_type=result["content_type"],
            expires_in=result["expires_in"],
        )

    except UploadError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/upload/confirm", response_model=DocumentUploadResponse)
async def confirm_presigned_upload(
    body: ConfirmUploadRequest,
    session: Annotated[PortalSession, Depends(get_current_portal_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DocumentUploadResponse:
    """Confirm a presigned upload and create database record.

    Call this after successfully uploading to the presigned URL.
    """
    service = PortalUploadService(db)

    try:
        document = await service.confirm_presigned_upload(
            document_id=UUID(body.document_id),
            storage_key=body.storage_key,
            filename=body.filename,
            content_type=body.content_type,
            file_size=body.file_size,
            tenant_id=session.tenant_id,
            connection_id=session.connection_id,
            document_type=body.document_type,
        )

        await db.commit()

        return DocumentUploadResponse(
            id=str(document.id),
            filename=document.original_filename,
            content_type=document.content_type,
            file_size=document.file_size,
            uploaded_at=document.uploaded_at,
        )

    except UploadError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    session: Annotated[PortalSession, Depends(get_current_portal_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
    document_type: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> DocumentListResponse:
    """List documents uploaded by the client."""
    repo = PortalDocumentRepository(db)

    skip = (page - 1) * page_size
    documents, total = await repo.list_by_connection(
        connection_id=session.connection_id,
        document_type=document_type,
        skip=skip,
        limit=page_size,
    )

    return DocumentListResponse(
        documents=[
            DocumentUploadResponse(
                id=str(doc.id),
                filename=doc.original_filename,
                content_type=doc.content_type,
                file_size=doc.file_size,
                uploaded_at=doc.uploaded_at,
            )
            for doc in documents
        ],
        total=total,
    )


@router.get("/{document_id}/download-url")
async def get_download_url(
    document_id: UUID,
    session: Annotated[PortalSession, Depends(get_current_portal_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Get a presigned URL for downloading a document."""
    repo = PortalDocumentRepository(db)

    document = await repo.get_by_id_and_connection(
        document_id=document_id,
        connection_id=session.connection_id,
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    service = PortalUploadService(db)

    try:
        url = service.get_presigned_download_url(
            storage_key=document.s3_key,
            filename=document.original_filename,
        )

        return {
            "download_url": url,
            "filename": document.original_filename,
            "content_type": document.content_type,
            "expires_in": 3600,
        }

    except UploadError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.delete("/{document_id}")
async def delete_document(
    document_id: UUID,
    session: Annotated[PortalSession, Depends(get_current_portal_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Delete a document."""
    # For now, only allow deletion of own documents via portal
    repo = PortalDocumentRepository(db)

    document = await repo.get_by_id_and_connection(
        document_id=document_id,
        connection_id=session.connection_id,
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Only allow deletion of documents not attached to responses
    if document.response_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete document attached to a response",
        )

    service = PortalUploadService(db)
    await service.delete_document(document_id, session.tenant_id)
    await db.commit()

    return {"success": True, "message": "Document deleted"}
