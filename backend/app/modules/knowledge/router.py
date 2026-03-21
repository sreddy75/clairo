"""API routes for knowledge base administration and public knowledge access.

Provides endpoints for:
- Collection management (initialize, list, reset)
- Knowledge source management (CRUD)
- Ingestion job management
- Search testing
- AI Chatbot with RAG
- Public knowledge search, domains, legislation lookup, and chat (Spec 045)
- Admin ingestion triggers and freshness reports (Spec 045)
"""

import json
import logging
import time
import uuid
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.dependencies import (
    get_chatbot_service,
    get_current_tenant_id,
    get_pinecone_service,
    get_voyage_service,
)
from app.core.pinecone_service import PineconeService
from app.core.voyage import VoyageService
from app.database import get_db
from app.modules.knowledge.chatbot import KnowledgeChatbot
from app.modules.knowledge.chunker import ChunkerConfig, SemanticChunker
from app.modules.knowledge.client_chatbot import ClientContextChatbot
from app.modules.knowledge.collections import (
    COLLECTIONS,
    INDEX_NAME,
    CollectionManager,
    get_namespace_with_env,
)
from app.modules.knowledge.document_processor import DocumentProcessor
from app.modules.knowledge.models import (
    ContentChunk,
    IngestionJob,
    KnowledgeSource,
)
from app.modules.knowledge.repository import (
    ChatConversationRepository,
    ChatMessageRepository,
    ContentChunkRepository,
    FreshnessReportRepository,
    IngestionJobRepository,
    KnowledgeSourceRepository,
    TaxDomainRepository,
)
from app.modules.knowledge.schemas import (
    AdminIngestionJobResponse,
    CaseLawIngestRequest,
    ChatRequest,
    ChatRequestWithConversation,
    ChatResponse,
    CitationAuditRequest,
    CitationAuditResponse,
    CitationResponse,
    # Collection content browsing
    CollectionContentItem,
    CollectionContentResponse,
    CollectionInfo,
    CollectionInitResponse,
    ConversationClientSummary,
    ConversationCreate,
    ConversationListItem,
    ConversationResponse,
    ConversationsWithClientsResponse,
    ConversationUpdate,
    FileUploadResponse,
    FreshnessReportResponse,
    IngestionJobResponse,
    KnowledgeChatRequest as Spec045ChatRequest,
    KnowledgeChatResponse as Spec045ChatResponse,
    KnowledgeSearchRequest as Spec045SearchRequest,
    KnowledgeSearchResponse as Spec045SearchResponse,
    KnowledgeSourceCreate,
    KnowledgeSourceResponse,
    KnowledgeSourceUpdate,
    LegislationIngestRequest,
    LegislationSectionResponse as Spec045LegislationResponse,
    ManualContentUpload,
    ManualContentUploadResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
    SourceChunkContent,
    SourceContentResponse,
    TaxDomainListResponse,
    TaxDomainResponse,
    # Spec 045: Enhanced knowledge base schemas
    TaxDomainSchema,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/admin/knowledge", tags=["knowledge-admin"])
public_router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


# Type aliases for dependencies
DbSession = Annotated[AsyncSession, Depends(get_db)]
PineconeDep = Annotated[PineconeService, Depends(get_pinecone_service)]
VoyageDep = Annotated[VoyageService, Depends(get_voyage_service)]
ChatbotDep = Annotated[KnowledgeChatbot, Depends(get_chatbot_service)]


# =============================================================================
# Collection Management
# =============================================================================


@router.post(
    "/collections/initialize",
    response_model=CollectionInitResponse,
    status_code=status.HTTP_201_CREATED,
)
async def initialize_collections(
    pinecone: PineconeDep,
) -> CollectionInitResponse:
    """Initialize the Pinecone index for knowledge base.

    Creates the index if it doesn't exist. Namespaces are created
    automatically when vectors are upserted.
    Safe to call multiple times - existing index is not modified.
    """
    manager = CollectionManager(pinecone)
    results = await manager.initialize_all()

    created_count = sum(1 for v in results.values() if v)
    existed_count = len(results) - created_count

    return CollectionInitResponse(
        collections=results,
        message=f"Created {created_count} namespaces, {existed_count} already existed",
    )


@router.get("/collections", response_model=list[CollectionInfo])
async def list_collections(
    pinecone: PineconeDep,
    db: AsyncSession = Depends(get_db),
) -> list[CollectionInfo]:
    """List all knowledge base namespaces with statistics."""
    manager = CollectionManager(pinecone)
    stats = await manager.get_all_stats()

    # Fetch source type breakdowns for active collections
    repo = ContentChunkRepository(db)
    results = []
    for name, info in stats.items():
        # Hide internal namespaces
        if name == "insight_dedup":
            continue
        source_counts = None
        if info.get("vectors_count", 0) > 0:
            source_counts = await repo.source_type_counts_by_collection(name)
        results.append(
            CollectionInfo(
                name=name,
                description=info.get("description", ""),
                exists=info.get("exists", False),
                vectors_count=info.get("vectors_count", 0),
                status=info.get("status"),
                config=info.get("config"),
                source_type_counts=source_counts if source_counts else None,
            )
        )
    return results


@router.delete("/collections/{name}")
async def reset_collection(
    name: str,
    pinecone: PineconeDep,
) -> dict:
    """Delete all vectors in a specific namespace.

    WARNING: This deletes all vectors in the namespace.
    """
    if name not in COLLECTIONS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown namespace: {name}. Valid: {list(COLLECTIONS.keys())}",
        )

    manager = CollectionManager(pinecone)
    await manager.reset_collection(name)

    return {"message": f"Namespace '{name}' has been reset", "collection": name}


# =============================================================================
# Knowledge Source Management
# =============================================================================


@router.post(
    "/sources",
    response_model=KnowledgeSourceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_source(
    source_data: KnowledgeSourceCreate,
    db: DbSession,
) -> KnowledgeSourceResponse:
    """Create a new knowledge source configuration."""
    # Validate collection name
    if source_data.collection_name not in COLLECTIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid collection: {source_data.collection_name}",
        )

    repo = KnowledgeSourceRepository(db)

    # Check for duplicate name
    existing = await repo.get_by_name(source_data.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Source with name '{source_data.name}' already exists",
        )

    source = KnowledgeSource(
        name=source_data.name,
        source_type=source_data.source_type,
        base_url=source_data.base_url,
        collection_name=source_data.collection_name,
        scrape_config=source_data.scrape_config,
        is_active=source_data.is_active,
    )

    created = await repo.create(source)
    await db.commit()

    return KnowledgeSourceResponse.model_validate(created)


@router.get("/sources", response_model=list[KnowledgeSourceResponse])
async def list_sources(
    db: DbSession,
    active_only: bool = False,
) -> list[KnowledgeSourceResponse]:
    """List all configured knowledge sources."""
    repo = KnowledgeSourceRepository(db)
    sources = await repo.get_all(active_only=active_only)
    return [KnowledgeSourceResponse.model_validate(s) for s in sources]


@router.get("/sources/{source_id}", response_model=KnowledgeSourceResponse)
async def get_source(
    source_id: UUID,
    db: DbSession,
) -> KnowledgeSourceResponse:
    """Get a specific knowledge source."""
    repo = KnowledgeSourceRepository(db)
    source = await repo.get_by_id(source_id)

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge source not found",
        )

    return KnowledgeSourceResponse.model_validate(source)


@router.patch("/sources/{source_id}", response_model=KnowledgeSourceResponse)
async def update_source(
    source_id: UUID,
    update_data: KnowledgeSourceUpdate,
    db: DbSession,
) -> KnowledgeSourceResponse:
    """Update a knowledge source configuration."""
    repo = KnowledgeSourceRepository(db)
    source = await repo.get_by_id(source_id)

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge source not found",
        )

    # Apply updates
    for field, value in update_data.model_dump(exclude_unset=True).items():
        setattr(source, field, value)

    await db.commit()
    await db.refresh(source)

    return KnowledgeSourceResponse.model_validate(source)


@router.delete("/sources/{source_id}")
async def delete_source(
    source_id: UUID,
    db: DbSession,
) -> dict:
    """Delete a knowledge source and all associated chunks."""
    repo = KnowledgeSourceRepository(db)
    source = await repo.get_by_id(source_id)

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge source not found",
        )

    # Delete chunks first (cascade should handle this, but be explicit)
    chunk_repo = ContentChunkRepository(db)
    chunks_deleted = await chunk_repo.delete_by_source(source_id)

    await repo.delete(source_id)
    await db.commit()

    return {
        "message": f"Source '{source.name}' deleted",
        "chunks_deleted": chunks_deleted,
    }


@router.get("/sources/{source_id}/content", response_model=SourceContentResponse)
async def get_source_content(
    source_id: UUID,
    db: DbSession,
    pinecone: PineconeDep,
    limit: int = 50,
    offset: int = 0,
) -> SourceContentResponse:
    """Get the actual text content stored in Pinecone for a knowledge source.

    This retrieves the vector metadata (including text) from Pinecone to allow
    admins to review what content is actually indexed for each source.
    """
    # Get the source
    source_repo = KnowledgeSourceRepository(db)
    source = await source_repo.get_by_id(source_id)

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge source not found",
        )

    # Get chunk metadata from PostgreSQL
    chunk_repo = ContentChunkRepository(db)
    chunks = await chunk_repo.get_by_source(source_id, limit=limit, offset=offset)

    # Get total count for pagination
    all_chunks = await chunk_repo.get_by_source(source_id, limit=10000, offset=0)
    total_chunks = len(all_chunks)

    if not chunks:
        return SourceContentResponse(
            source_id=str(source_id),
            source_name=source.name,
            collection=source.collection_name,
            total_chunks=0,
            chunks=[],
        )

    # Get vector IDs to fetch from Pinecone
    vector_ids = [c.qdrant_point_id for c in chunks if c.qdrant_point_id]

    if not vector_ids:
        return SourceContentResponse(
            source_id=str(source_id),
            source_name=source.name,
            collection=source.collection_name,
            total_chunks=total_chunks,
            chunks=[],
        )

    # Fetch vectors from Pinecone to get the actual text content
    namespace = get_namespace_with_env(source.collection_name)
    vectors = await pinecone.fetch_vectors(
        index_name=INDEX_NAME,
        ids=vector_ids,
        namespace=namespace,
    )

    # Build response with content from Pinecone
    chunk_contents = []
    for chunk in chunks:
        if chunk.qdrant_point_id and chunk.qdrant_point_id in vectors:
            vector_data = vectors[chunk.qdrant_point_id]
            metadata = vector_data.metadata if hasattr(vector_data, "metadata") else {}

            chunk_contents.append(
                SourceChunkContent(
                    chunk_id=str(chunk.id),
                    text=metadata.get("text", "[No text stored]"),
                    title=metadata.get("title") or chunk.title,
                    source_url=metadata.get("source_url") or chunk.source_url,
                    source_type=metadata.get("source_type") or chunk.source_type,
                    chunk_index=metadata.get("chunk_index"),
                )
            )

    return SourceContentResponse(
        source_id=str(source_id),
        source_name=source.name,
        collection=source.collection_name,
        total_chunks=total_chunks,
        chunks=chunk_contents,
    )


# =============================================================================
# Manual Content Upload
# =============================================================================


@router.post(
    "/sources/{source_id}/content",
    response_model=ManualContentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_manual_content(
    source_id: UUID,
    content: ManualContentUpload,
    db: DbSession,
    pinecone: PineconeDep,
    voyage: VoyageDep,
) -> ManualContentUploadResponse:
    """Add manual text content to a knowledge source.

    This allows admins to directly add curated content to the knowledge base
    without scraping. The text is chunked, embedded, and stored in Pinecone.
    """
    # Get the source
    source_repo = KnowledgeSourceRepository(db)
    source = await source_repo.get_by_id(source_id)

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge source not found",
        )

    # Chunk the content
    chunker = SemanticChunker(ChunkerConfig())
    chunks = chunker.chunk_text(content.text)

    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No content to add (text too short)",
        )

    # Get namespace for this source
    namespace = get_namespace_with_env(source.collection_name)

    # Process each chunk
    chunk_repo = ContentChunkRepository(db)
    vectors_to_upsert = []
    chunks_created = 0

    for chunk in chunks:
        # Generate unique ID for this chunk
        chunk_id = str(uuid.uuid4())

        # Create embedding
        embedding = await voyage.embed_text(chunk.text)

        # Prepare vector for Pinecone
        vectors_to_upsert.append(
            {
                "id": chunk_id,
                "values": embedding,
                "metadata": {
                    "text": chunk.text,
                    "title": content.title,
                    "source_url": content.source_url or source.base_url,
                    "source_type": "manual",
                    "source_id": str(source_id),
                    "chunk_index": chunk.index,
                },
            }
        )

        # Create content_chunk record in PostgreSQL
        content_chunk = ContentChunk(
            id=uuid.UUID(chunk_id),
            source_id=source_id,
            qdrant_point_id=chunk_id,
            collection_name=source.collection_name,
            content_hash=chunk.content_hash,
            source_url=content.source_url or source.base_url,
            title=content.title,
            source_type="manual",
        )
        db.add(content_chunk)
        chunks_created += 1

    # Upsert vectors to Pinecone
    if vectors_to_upsert:
        await pinecone.upsert_vectors(
            index_name=INDEX_NAME,
            vectors=vectors_to_upsert,
            namespace=namespace,
        )

    await db.commit()

    return ManualContentUploadResponse(
        source_id=str(source_id),
        chunks_created=chunks_created,
        message=f"Successfully added {chunks_created} chunks to {source.name}",
    )


@router.post(
    "/sources/{source_id}/upload",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    source_id: UUID,
    db: DbSession,
    pinecone: PineconeDep,
    voyage: VoyageDep,
    file: UploadFile = File(...),
    title: str | None = Form(None),
    source_url: str | None = Form(None),
) -> FileUploadResponse:
    """Upload a document (PDF, DOCX, TXT) to a knowledge source.

    The document is processed, text is extracted, chunked, embedded,
    and stored in Pinecone.
    """
    # Validate file size (max 10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    file_content = await file.read()
    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large. Maximum size is 10MB.",
        )

    # Validate file type
    try:
        doc_type = DocumentProcessor.get_document_type(
            file.filename or "unknown",
            file.content_type,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Get the source
    source_repo = KnowledgeSourceRepository(db)
    source = await source_repo.get_by_id(source_id)

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge source not found",
        )

    # Extract text from document
    try:
        extracted = DocumentProcessor.extract_text(
            file_content,
            file.filename or "document",
            file.content_type,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    if not extracted.text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No text content could be extracted from the document",
        )

    # Use provided title or extracted title
    doc_title = title or extracted.title or file.filename

    # Chunk the content
    chunker = SemanticChunker(ChunkerConfig())
    chunks = chunker.chunk_text(extracted.text)

    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document content too short to create chunks",
        )

    # Get namespace for this source
    namespace = get_namespace_with_env(source.collection_name)

    # Process each chunk
    chunk_repo = ContentChunkRepository(db)
    vectors_to_upsert = []
    chunks_created = 0

    for chunk in chunks:
        # Generate unique ID for this chunk
        chunk_id = str(uuid.uuid4())

        # Create embedding
        embedding = await voyage.embed_text(chunk.text)

        # Prepare vector for Pinecone
        vectors_to_upsert.append(
            {
                "id": chunk_id,
                "values": embedding,
                "metadata": {
                    "text": chunk.text,
                    "title": doc_title,
                    "source_url": source_url or source.base_url,
                    "source_type": f"upload_{doc_type.value}",
                    "source_id": str(source_id),
                    "chunk_index": chunk.index,
                    "filename": file.filename,
                },
            }
        )

        # Create content_chunk record in PostgreSQL
        content_chunk = ContentChunk(
            id=uuid.UUID(chunk_id),
            source_id=source_id,
            qdrant_point_id=chunk_id,
            collection_name=source.collection_name,
            content_hash=chunk.content_hash,
            source_url=source_url or source.base_url,
            title=doc_title,
            source_type=f"upload_{doc_type.value}",
        )
        db.add(content_chunk)
        chunks_created += 1

    # Upsert vectors to Pinecone
    if vectors_to_upsert:
        await pinecone.upsert_vectors(
            index_name=INDEX_NAME,
            vectors=vectors_to_upsert,
            namespace=namespace,
        )

    await db.commit()

    return FileUploadResponse(
        source_id=str(source_id),
        filename=file.filename or "unknown",
        document_type=doc_type.value,
        page_count=extracted.page_count,
        word_count=extracted.word_count,
        chunks_created=chunks_created,
        message=f"Successfully processed {file.filename} and added {chunks_created} chunks",
    )


# =============================================================================
# Ingestion Job Management
# =============================================================================


@router.post(
    "/sources/{source_id}/ingest",
    response_model=IngestionJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_ingestion(
    source_id: UUID,
    db: DbSession,
) -> IngestionJobResponse:
    """Trigger ingestion for a knowledge source.

    Creates a new ingestion job. In production, this would queue a Celery task.
    For now, it creates the job record that can be used to track progress.
    """
    source_repo = KnowledgeSourceRepository(db)
    source = await source_repo.get_by_id(source_id)

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge source not found",
        )

    if not source.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot ingest from inactive source",
        )

    # Create job record
    job_repo = IngestionJobRepository(db)
    job = IngestionJob(
        source_id=source_id,
        status="pending",
        triggered_by="manual",
    )
    created = await job_repo.create(job)
    await db.commit()

    # Queue Celery task for background processing
    from app.tasks.knowledge import ingest_source

    ingest_source.delay(str(source_id), str(created.id))

    return IngestionJobResponse(
        id=created.id,
        source_id=created.source_id,
        status=created.status,
        started_at=created.started_at,
        completed_at=created.completed_at,
        items_processed=created.items_processed,
        items_added=created.items_added,
        items_updated=created.items_updated,
        items_skipped=created.items_skipped,
        items_failed=created.items_failed,
        tokens_used=created.tokens_used,
        errors=created.errors,
        triggered_by=created.triggered_by,
        created_at=created.created_at,
    )


@router.get("/jobs", response_model=list[IngestionJobResponse])
async def list_jobs(
    db: DbSession,
    status: str | None = None,
    source_id: UUID | None = None,
    limit: int = 50,
) -> list[IngestionJobResponse]:
    """List ingestion jobs with optional filtering."""
    repo = IngestionJobRepository(db)

    if source_id:
        jobs = await repo.get_by_source(source_id, limit=limit, status=status)
    else:
        jobs = await repo.get_recent(limit=limit, status=status, with_source=True)

    return [
        IngestionJobResponse(
            id=j.id,
            source_id=j.source_id,
            source_name=j.source.name if j.source else None,
            status=j.status,
            started_at=j.started_at,
            completed_at=j.completed_at,
            items_processed=j.items_processed,
            items_added=j.items_added,
            items_updated=j.items_updated,
            items_skipped=j.items_skipped,
            items_failed=j.items_failed,
            tokens_used=j.tokens_used,
            errors=j.errors,
            triggered_by=j.triggered_by,
            created_at=j.created_at,
            duration_seconds=j.duration_seconds,
            success_rate=j.success_rate,
        )
        for j in jobs
    ]


@router.get("/jobs/{job_id}", response_model=IngestionJobResponse)
async def get_job(
    job_id: UUID,
    db: DbSession,
) -> IngestionJobResponse:
    """Get details for a specific ingestion job."""
    repo = IngestionJobRepository(db)
    job = await repo.get_by_id(job_id, with_source=True)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingestion job not found",
        )

    return IngestionJobResponse(
        id=job.id,
        source_id=job.source_id,
        status=job.status,
        started_at=job.started_at,
        completed_at=job.completed_at,
        items_processed=job.items_processed,
        items_added=job.items_added,
        items_updated=job.items_updated,
        items_skipped=job.items_skipped,
        items_failed=job.items_failed,
        tokens_used=job.tokens_used,
        errors=job.errors,
        triggered_by=job.triggered_by,
        created_at=job.created_at,
        duration_seconds=job.duration_seconds,
        success_rate=job.success_rate,
    )


@router.delete("/jobs/{job_id}")
async def delete_job(
    job_id: UUID,
    db: DbSession,
) -> dict:
    """Delete an ingestion job.

    Only non-running jobs can be deleted.
    """
    repo = IngestionJobRepository(db)
    job = await repo.get_by_id(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingestion job not found",
        )

    if job.status == "running":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete a running job",
        )

    await repo.delete(job_id)
    await db.commit()

    return {"message": f"Job {job_id} deleted", "job_id": str(job_id)}


@router.post("/jobs/cancel-all")
async def cancel_all_jobs(
    db: DbSession,
) -> dict:
    """Cancel all pending and running jobs.

    Marks pending jobs as failed and running jobs as cancelled.
    Note: Running Celery tasks will continue but their results will be ignored.
    """
    # Update pending jobs to failed
    from sqlalchemy import update

    pending_result = await db.execute(
        update(IngestionJob)
        .where(IngestionJob.status == "pending")
        .values(
            status="cancelled",
            errors=[
                {"error": "Cancelled by admin", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")}
            ],
        )
    )
    pending_count = pending_result.rowcount

    # Update running jobs to cancelled
    running_result = await db.execute(
        update(IngestionJob)
        .where(IngestionJob.status == "running")
        .values(
            status="cancelled",
            errors=[
                {"error": "Cancelled by admin", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")}
            ],
        )
    )
    running_count = running_result.rowcount

    await db.commit()

    return {
        "message": f"Cancelled {pending_count} pending and {running_count} running jobs",
        "pending_cancelled": pending_count,
        "running_cancelled": running_count,
    }


@router.post(
    "/jobs/{job_id}/restart",
    response_model=IngestionJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def restart_job(
    job_id: UUID,
    db: DbSession,
) -> IngestionJobResponse:
    """Restart a failed or completed job.

    Creates a new ingestion job for the same source.
    """
    repo = IngestionJobRepository(db)
    job = await repo.get_by_id(job_id, with_source=True)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingestion job not found",
        )

    if job.status == "running":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot restart a running job",
        )

    if job.status == "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job is already pending",
        )

    # Get the source
    source_repo = KnowledgeSourceRepository(db)
    source = await source_repo.get_by_id(job.source_id)

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source no longer exists",
        )

    if not source.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source is inactive",
        )

    # Create new job
    new_job = IngestionJob(
        source_id=job.source_id,
        status="pending",
        triggered_by="restart",
    )
    created = await repo.create(new_job)
    await db.commit()

    # Queue Celery task
    from app.tasks.knowledge import ingest_source

    ingest_source.delay(str(job.source_id), str(created.id))

    return IngestionJobResponse(
        id=created.id,
        source_id=created.source_id,
        status=created.status,
        started_at=created.started_at,
        completed_at=created.completed_at,
        items_processed=created.items_processed,
        items_added=created.items_added,
        items_updated=created.items_updated,
        items_skipped=created.items_skipped,
        items_failed=created.items_failed,
        tokens_used=created.tokens_used,
        errors=created.errors,
        triggered_by=created.triggered_by,
        created_at=created.created_at,
    )


# =============================================================================
# Search Testing
# =============================================================================


@router.post("/search/test", response_model=SearchResponse)
async def test_search(
    request: SearchRequest,
    pinecone: PineconeDep,
    voyage: VoyageDep,
) -> SearchResponse:
    """Test knowledge base search functionality.

    This endpoint is for admin testing and debugging.
    """
    start_time = time.time()

    # Determine namespaces to search (base names)
    base_namespaces = request.collections or list(COLLECTIONS.keys())

    # Validate namespaces
    invalid = set(base_namespaces) - set(COLLECTIONS.keys())
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid namespaces: {invalid}",
        )

    # Convert to environment-aware namespace names
    pinecone_namespaces = [get_namespace_with_env(ns) for ns in base_namespaces]

    # Embed query
    query_vector = await voyage.embed_query(request.query)

    # Build filter if provided
    pinecone_filter = None
    if request.filters:
        filter_conditions: dict = {}

        if request.filters.entity_types:
            filter_conditions["entity_types"] = {"$in": request.filters.entity_types}

        if request.filters.industries:
            filter_conditions["industries"] = {"$in": request.filters.industries}

        if request.filters.source_types:
            filter_conditions["source_type"] = {"$in": request.filters.source_types}

        if request.filters.exclude_superseded:
            filter_conditions["is_superseded"] = {"$eq": False}

        if filter_conditions:
            pinecone_filter = filter_conditions

    # Search across namespaces (using environment-aware names)
    scored_points = await pinecone.search_multi_namespace(
        index_name=INDEX_NAME,
        namespaces=pinecone_namespaces,
        query_vector=query_vector,
        filters=dict.fromkeys(pinecone_namespaces, pinecone_filter) if pinecone_filter else None,
        limit_per_namespace=max(5, request.limit // len(pinecone_namespaces)),
        total_limit=request.limit,
        score_threshold=request.score_threshold,
    )

    # Format results
    results = []
    for point in scored_points:
        payload = point.payload or {}
        results.append(
            SearchResult(
                chunk_id=str(point.id),
                collection=payload.get("_collection", "unknown"),
                score=point.score,
                text=payload.get("text", ""),
                source_url=payload.get("source_url", ""),
                title=payload.get("title"),
                source_type=payload.get("source_type", "unknown"),
                ruling_number=payload.get("ruling_number"),
                effective_date=payload.get("effective_date"),
                entity_types=payload.get("entity_types", []),
                industries=payload.get("industries", []),
            )
        )

    latency_ms = (time.time() - start_time) * 1000

    return SearchResponse(
        query=request.query,
        results=results,
        total_results=len(results),
        collections_searched=base_namespaces,
        latency_ms=round(latency_ms, 2),
    )


# =============================================================================
# Embedding Testing
# =============================================================================


@router.post("/embed/test")
async def test_embedding(
    text: str,
    voyage: VoyageDep,
) -> dict:
    """Test embedding service.

    Returns the embedding vector and metadata for debugging.
    """
    start_time = time.time()
    vector = await voyage.embed_text(text)
    latency_ms = (time.time() - start_time) * 1000

    return {
        "text": text[:100] + "..." if len(text) > 100 else text,
        "model": voyage.model,
        "dimensions": len(vector),
        "latency_ms": round(latency_ms, 2),
        "vector_preview": vector[:5],  # First 5 dimensions for inspection
    }


# =============================================================================
# Health Check
# =============================================================================


@router.get("/health")
async def health_check(
    pinecone: PineconeDep,
    voyage: VoyageDep,
) -> dict:
    """Check health of knowledge base services."""
    pinecone_healthy = await pinecone.health_check()
    voyage_healthy = await voyage.health_check()

    all_healthy = pinecone_healthy and voyage_healthy

    return {
        "status": "healthy" if all_healthy else "degraded",
        "services": {
            "pinecone": "healthy" if pinecone_healthy else "unhealthy",
            "voyage": "healthy" if voyage_healthy else "unhealthy",
        },
    }


# =============================================================================
# AI Chatbot
# =============================================================================


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    chatbot: ChatbotDep,
) -> ChatResponse:
    """Send a question to the AI chatbot (non-streaming).

    Uses RAG to retrieve relevant knowledge and generate an answer.
    Returns complete response with citations.
    """
    try:
        # Convert conversation history to dict format
        history = None
        if request.conversation_history:
            history = [{"role": m.role, "content": m.content} for m in request.conversation_history]

        # Get response and context
        response_text, context = await chatbot.chat(
            query=request.query,
            collections=request.collections,
            conversation_history=history,
            stream=False,
        )

        # Build citation responses
        citations = [
            CitationResponse(
                number=c.number,
                title=c.title,
                url=c.url,
                source_type=c.source_type,
                effective_date=c.effective_date,
                text_preview=c.text_preview,
                score=c.score,
            )
            for c in context.citations
        ]

        return ChatResponse(
            response=response_text,
            citations=citations,
            query=request.query,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        ) from None
    except Exception as e:
        logger.error("Knowledge chat error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again.",
        ) from None


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    chatbot: ChatbotDep,
) -> StreamingResponse:
    """Send a question to the AI chatbot (streaming via SSE).

    Uses RAG to retrieve relevant knowledge and streams the response.
    Returns Server-Sent Events with text chunks and final metadata.

    Event types:
    - 'text': Text chunk from the response
    - 'done': Final event with citations and metadata
    - 'error': Error event if something goes wrong
    """

    async def generate_events():
        """Generator for SSE events."""
        try:
            # Convert conversation history to dict format
            history = None
            if request.conversation_history:
                history = [
                    {"role": m.role, "content": m.content} for m in request.conversation_history
                ]

            # Get streaming response and context
            stream, context = await chatbot.chat(
                query=request.query,
                collections=request.collections,
                conversation_history=history,
                stream=True,
            )

            # Stream text chunks
            async for chunk in stream:
                # SSE format: data: <content>\n\n
                event_data = json.dumps({"type": "text", "content": chunk})
                yield f"data: {event_data}\n\n"

            # Send final metadata with citations
            citations = [
                CitationResponse(
                    number=c.number,
                    title=c.title,
                    url=c.url,
                    source_type=c.source_type,
                    effective_date=c.effective_date,
                    text_preview=c.text_preview,
                    score=c.score,
                ).model_dump()
                for c in context.citations
            ]

            done_data = json.dumps(
                {
                    "type": "done",
                    "citations": citations,
                    "query": request.query,
                }
            )
            yield f"data: {done_data}\n\n"

        except ValueError as e:
            error_data = json.dumps({"type": "error", "message": str(e)})
            yield f"data: {error_data}\n\n"
        except Exception as e:
            logger.error("Knowledge chat stream error: %s", e, exc_info=True)
            error_data = json.dumps(
                {"type": "error", "message": "An unexpected error occurred. Please try again."}
            )
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.post("/chat/persistent/stream")
async def chat_persistent_stream(
    request: ChatRequestWithConversation,
    user_id: str,  # In production, get from auth middleware
    db: DbSession,
    chatbot: ChatbotDep,
) -> StreamingResponse:
    """Chat with conversation persistence (streaming via SSE).

    Creates or continues a conversation, saves messages to database,
    and streams the response. If conversation_id is not provided,
    creates a new conversation.

    Query params:
        user_id: User ID (temporary - will come from auth in production)
    """

    async def generate_events():
        """Generator for SSE events."""
        conversation_id = request.conversation_id
        conv_repo = ChatConversationRepository(db)
        msg_repo = ChatMessageRepository(db)

        try:
            # Get or create conversation
            if conversation_id:
                conversation = await conv_repo.get_by_id(conversation_id)
                if not conversation:
                    error_data = json.dumps({"type": "error", "message": "Conversation not found"})
                    yield f"data: {error_data}\n\n"
                    return
                if conversation.user_id != user_id:
                    error_data = json.dumps({"type": "error", "message": "Not authorized"})
                    yield f"data: {error_data}\n\n"
                    return
            else:
                # Create new conversation with title from query
                title = request.query[:50] + "..." if len(request.query) > 50 else request.query
                conversation = await conv_repo.create(user_id=user_id, title=title)
                await db.commit()
                conversation_id = conversation.id

            # Save user message
            await msg_repo.create(
                conversation_id=conversation_id,
                role="user",
                content=request.query,
            )

            # Get conversation history for context
            messages = await msg_repo.get_recent(conversation_id, limit=10)
            history = [
                {"role": m.role, "content": m.content} for m in messages[:-1]
            ]  # Exclude current

            # Get streaming response and context
            stream, context = await chatbot.chat(
                query=request.query,
                collections=request.collections,
                conversation_history=history if history else None,
                stream=True,
            )

            # Collect full response while streaming
            full_response = []

            # Stream text chunks
            async for chunk in stream:
                full_response.append(chunk)
                event_data = json.dumps({"type": "text", "content": chunk})
                yield f"data: {event_data}\n\n"

            # Build citation responses
            citations = [
                CitationResponse(
                    number=c.number,
                    title=c.title,
                    url=c.url,
                    source_type=c.source_type,
                    effective_date=c.effective_date,
                    text_preview=c.text_preview,
                    score=c.score,
                ).model_dump()
                for c in context.citations
            ]

            # Save assistant message with citations
            await msg_repo.create(
                conversation_id=conversation_id,
                role="assistant",
                content="".join(full_response),
                citations=citations,
            )

            # Update conversation timestamp
            await conv_repo.touch(conversation_id)
            await db.commit()

            # Send final metadata with citations and conversation ID
            done_data = json.dumps(
                {
                    "type": "done",
                    "citations": citations,
                    "query": request.query,
                    "conversation_id": str(conversation_id),
                }
            )
            yield f"data: {done_data}\n\n"

        except ValueError as e:
            error_data = json.dumps({"type": "error", "message": str(e)})
            yield f"data: {error_data}\n\n"
        except Exception as e:
            logger.error("Knowledge chat stream error: %s", e, exc_info=True)
            error_data = json.dumps(
                {"type": "error", "message": "An unexpected error occurred. Please try again."}
            )
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# =============================================================================
# Conversation Management
# =============================================================================


@router.get("/conversations", response_model=list[ConversationListItem])
async def list_conversations(
    user_id: str,
    db: DbSession,
    limit: int = 50,
    offset: int = 0,
    client_id: UUID | None = None,
    general_only: bool = False,
) -> list[ConversationListItem]:
    """List conversations for a user with optional client filtering.

    Args:
        user_id: Clerk user ID.
        limit: Max conversations to return.
        offset: Pagination offset.
        client_id: Filter to specific client.
        general_only: Only return general (non-client) conversations.
    """
    conv_repo = ChatConversationRepository(db)
    msg_repo = ChatMessageRepository(db)

    # Get conversations with client names
    conv_with_clients = await conv_repo.get_by_user_with_clients(
        user_id, limit=limit, offset=offset
    )

    # Apply filtering
    if client_id:
        conv_with_clients = [(c, n) for c, n in conv_with_clients if c.client_id == client_id]
    elif general_only:
        conv_with_clients = [(c, n) for c, n in conv_with_clients if c.client_id is None]

    result = []
    for conv, client_name in conv_with_clients:
        # Get message count and last message preview
        message_count = await msg_repo.count_by_conversation(conv.id)
        messages = await msg_repo.get_recent(conv.id, limit=1)
        last_message = messages[0] if messages else None

        result.append(
            ConversationListItem(
                id=conv.id,
                title=conv.title,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                message_count=message_count,
                last_message_preview=last_message.content[:100] if last_message else None,
                client_id=conv.client_id,
                client_name=client_name,
            )
        )

    return result


@router.get("/conversations/with-clients", response_model=ConversationsWithClientsResponse)
async def list_conversations_with_clients(
    user_id: str,
    db: DbSession,
    limit: int = 50,
    offset: int = 0,
) -> ConversationsWithClientsResponse:
    """List conversations with client filter data for enhanced UI.

    Returns conversations with client badges and a list of clients
    the user has conversations with (for filter pills).
    """
    conv_repo = ChatConversationRepository(db)
    msg_repo = ChatMessageRepository(db)

    # Get conversations with client names
    conv_with_clients = await conv_repo.get_by_user_with_clients(
        user_id, limit=limit, offset=offset
    )

    # Get client filter options
    user_clients = await conv_repo.get_user_clients(user_id)

    # Count general conversations
    all_convs = await conv_repo.get_by_user(user_id, limit=1000)  # Get all for counting
    general_count = sum(1 for c in all_convs if c.client_id is None)

    result = []
    for conv, client_name in conv_with_clients:
        message_count = await msg_repo.count_by_conversation(conv.id)
        messages = await msg_repo.get_recent(conv.id, limit=1)
        last_message = messages[0] if messages else None

        result.append(
            ConversationListItem(
                id=conv.id,
                title=conv.title,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                message_count=message_count,
                last_message_preview=last_message.content[:100] if last_message else None,
                client_id=conv.client_id,
                client_name=client_name,
            )
        )

    return ConversationsWithClientsResponse(
        conversations=result,
        clients=[
            ConversationClientSummary(
                client_id=cid,
                client_name=cname,
                conversation_count=count,
            )
            for cid, cname, count in user_clients
        ],
        total_conversations=len(all_convs),
        general_count=general_count,
    )


@router.post(
    "/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED
)
async def create_conversation(
    request: ConversationCreate,
    user_id: str,
    db: DbSession,
) -> ConversationResponse:
    """Create a new conversation."""
    conv_repo = ChatConversationRepository(db)

    conversation = await conv_repo.create(
        user_id=user_id,
        title=request.title or "New Conversation",
    )
    await db.commit()

    return ConversationResponse(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[],
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: UUID,
    user_id: str,
    db: DbSession,
) -> ConversationResponse:
    """Get a conversation with all messages."""
    conv_repo = ChatConversationRepository(db)

    conversation = await conv_repo.get_by_id(conversation_id, with_messages=True)

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    if conversation.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this conversation",
        )

    return ConversationResponse.model_validate(conversation)


@router.patch("/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: UUID,
    request: ConversationUpdate,
    user_id: str,
    db: DbSession,
) -> ConversationResponse:
    """Update conversation title."""
    conv_repo = ChatConversationRepository(db)

    conversation = await conv_repo.get_by_id(conversation_id)

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    if conversation.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this conversation",
        )

    await conv_repo.update_title(conversation_id, request.title)
    await db.commit()

    # Refresh and return
    conversation = await conv_repo.get_by_id(conversation_id, with_messages=True)
    return ConversationResponse.model_validate(conversation)


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: UUID,
    user_id: str,
    db: DbSession,
) -> dict:
    """Delete a conversation and all its messages."""
    conv_repo = ChatConversationRepository(db)

    conversation = await conv_repo.get_by_id(conversation_id)

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    if conversation.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this conversation",
        )

    await conv_repo.delete(conversation_id)
    await db.commit()

    return {"message": "Conversation deleted", "id": str(conversation_id)}


# =============================================================================
# Collection Content Browsing
# =============================================================================


@public_router.get(
    "/collections/{name}/content",
    response_model=CollectionContentResponse,
)
async def browse_collection_content(
    name: str,
    db: DbSession,
    page: int = 1,
    page_size: int = 20,
    source_type: str | None = None,
    search: str | None = None,
) -> CollectionContentResponse:
    """Browse content chunks within a collection/namespace.

    Returns paginated content metadata with optional filtering by
    source_type and title search. Also returns a breakdown of
    chunk counts per source_type in the collection.

    Args:
        name: Collection/namespace name (e.g., "compliance_knowledge").
        page: Page number (1-based, default 1).
        page_size: Items per page (default 20, max 100).
        source_type: Optional filter by source type
            (e.g., "legislation", "ato_ruling", "case_law", "tpb_guidance").
        search: Optional text filter (ILIKE on title).
    """
    if name not in COLLECTIONS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown collection: {name}. Valid: {list(COLLECTIONS.keys())}",
        )

    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = min(max(page_size, 1), 100)

    repo = ContentChunkRepository(db)

    chunks, total = await repo.browse_by_collection(
        collection_name=name,
        page=page,
        page_size=page_size,
        source_type=source_type,
        search=search,
    )

    source_type_counts = await repo.source_type_counts_by_collection(name)

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return CollectionContentResponse(
        items=[CollectionContentItem.model_validate(c) for c in chunks],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        source_type_counts=source_type_counts,
    )


# =============================================================================
# Spec 045: Public Knowledge Endpoints (non-admin)
# =============================================================================


@public_router.get("/domains", response_model=TaxDomainListResponse)
async def list_tax_domains(
    db: DbSession,
) -> TaxDomainListResponse:
    """List all active specialist tax domains.

    Returns the configured tax domains (e.g., GST, CGT, Division 7A, FBT)
    that can be used to scope knowledge searches and chat queries.
    """
    repo = TaxDomainRepository(db)
    domains = await repo.list_active()
    return TaxDomainListResponse(data=[TaxDomainSchema.model_validate(d) for d in domains])


@public_router.get("/domains/{slug}", response_model=TaxDomainResponse)
async def get_tax_domain(
    slug: str,
    db: DbSession,
) -> TaxDomainResponse:
    """Get a single tax domain by slug.

    Args:
        slug: Domain slug (e.g., "gst", "division-7a", "cgt").
    """
    repo = TaxDomainRepository(db)
    domain = await repo.get_by_slug(slug)

    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tax domain '{slug}' not found",
        )

    return TaxDomainResponse(data=TaxDomainSchema.model_validate(domain))


@public_router.post("/search", response_model=Spec045SearchResponse)
async def search_knowledge(
    request: Spec045SearchRequest,
    db: DbSession,
    pinecone: PineconeDep,
    voyage: VoyageDep,
) -> Spec045SearchResponse:
    """Hybrid search across the knowledge base.

    Combines semantic (Pinecone) and keyword (BM25) search with
    cross-encoder re-ranking. Supports domain scoping and metadata
    filtering (source type, entity type, financial year, superseded status).
    """
    from app.modules.knowledge.service import KnowledgeService

    service = KnowledgeService(db=db, pinecone=pinecone, voyage=voyage)
    return await service.search_knowledge(request)


@public_router.get(
    "/legislation/{section_ref:path}",
    response_model=Spec045LegislationResponse,
)
async def get_legislation_section(
    section_ref: str,
    db: DbSession,
    pinecone: PineconeDep,
    voyage: VoyageDep,
) -> Spec045LegislationResponse:
    """Look up a legislation section by reference.

    Accepts flexible section references such as:
    - "s109D-ITAA1936"
    - "s104-10-ITAA1997"
    - "s109D"
    - "section 109D"

    The ``section_ref`` path parameter uses the ``:path`` converter so
    references containing slashes (e.g. ``s104-10/ITAA1997``) are captured
    correctly.

    Returns the section text, metadata, cross-references, defined terms,
    and related rulings.
    """
    from app.modules.knowledge.service import KnowledgeService

    service = KnowledgeService(db=db, pinecone=pinecone, voyage=voyage)
    result = await service.get_legislation_section(section_ref)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Legislation section '{section_ref}' not found",
        )

    return Spec045LegislationResponse(data=result)


@public_router.post("/chat", response_model=Spec045ChatResponse)
async def knowledge_chat(
    request: Spec045ChatRequest,
    chatbot: ChatbotDep,
    db: DbSession,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
) -> Spec045ChatResponse:
    """Extended knowledge chat with domain scoping and optional client context.

    When ``client_id`` is provided in the request, validates the client
    belongs to the tenant and routes to :meth:`ClientContextChatbot.chat_with_knowledge`
    which combines the enhanced hybrid search pipeline with the client's
    Xero financial data.

    When ``client_id`` is *not* provided, delegates to
    :meth:`KnowledgeChatbot.chat_enhanced` for standard tax research
    with the hybrid search pipeline (US1 flow from T020).
    """
    try:
        # Route based on whether client context is requested
        if request.client_id is not None:
            # --- Client-contextual knowledge chat (US2 / T027) ---
            # Validate client exists and belongs to tenant by constructing
            # the client chatbot and delegating to chat_with_knowledge().
            pinecone = await get_pinecone_service()
            voyage = await get_voyage_service()
            settings = get_settings()
            client_chatbot = ClientContextChatbot(
                db=db,
                anthropic_settings=settings.anthropic,
                pinecone=pinecone,
                voyage=voyage,
            )

            result = await client_chatbot.chat_with_knowledge(
                query=request.message,
                client_id=request.client_id,
                tenant_id=tenant_id,
                domain=request.domain,
                conversation_history=None,
                session=db,
            )

            return Spec045ChatResponse(data=result)

        # --- Standard knowledge chat (US1 / T020) ---
        result = await chatbot.chat_enhanced(
            query=request.message,
            domain=request.domain,
            session=db,
            conversation_history=None,
        )

        return Spec045ChatResponse(data=result)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        ) from None
    except Exception as e:
        logger.error("Knowledge chat error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again.",
        ) from None


# =============================================================================
# Spec 045: Admin Ingestion & Freshness Endpoints
# =============================================================================


@router.post(
    "/ingest/legislation",
    response_model=AdminIngestionJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_legislation_ingestion(
    request: LegislationIngestRequest,
) -> AdminIngestionJobResponse:
    """Trigger ingestion of Australian legislation from legislation.gov.au.

    Dispatches a Celery background task to scrape, chunk, embed, and store
    legislation sections. Supports targeting specific acts by ID or ingesting
    all configured tax acts.

    Returns a 202 Accepted with the background job details.
    """
    from app.tasks.knowledge import ingest_legislation

    task = ingest_legislation.delay(
        acts=request.acts,
        dev_mode=request.dev_mode,
    )

    return AdminIngestionJobResponse(
        data={
            "job_id": task.id,
            "source_type": "legislation",
            "status": "pending",
            "message": (
                f"Legislation ingestion queued for acts: {request.acts or 'all configured'}. "
                f"Force refresh: {request.force_refresh}. Dev mode: {request.dev_mode}"
            ),
        }
    )


@router.post(
    "/ingest/case-law",
    response_model=AdminIngestionJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_case_law_ingestion(
    request: CaseLawIngestRequest,
) -> AdminIngestionJobResponse:
    """Trigger ingestion of tax-relevant case law.

    Dispatches a Celery background task to ingest case law from the
    Open Australian Legal Corpus and/or Federal Court RSS feed. Uses
    IngestionManager for document-level idempotency with natural key
    ``case_law:{citation}``.

    Returns a 202 Accepted with the background job details.
    """
    from app.tasks.knowledge import ingest_case_law

    task = ingest_case_law.delay(
        source=request.source,
        filter_tax_only=request.filter_tax_only,
        dev_mode=request.dev_mode,
    )

    return AdminIngestionJobResponse(
        data={
            "job_id": task.id,
            "source_type": "case_law",
            "status": "pending",
            "message": (
                f"Case law ingestion queued. Source: {request.source}, "
                f"tax-only filter: {request.filter_tax_only}. Dev mode: {request.dev_mode}"
            ),
        }
    )


@router.post(
    "/ingest/ato-legal-db",
    response_model=AdminIngestionJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_ato_legal_db_ingestion(
    dev_mode: bool = False,
) -> AdminIngestionJobResponse:
    """Trigger ingestion of ATO rulings from the ATO Legal Database.

    Dispatches a Celery background task to crawl ATO rulings (TRs, GSTRs, TDs,
    PCGs, etc.), chunk with the ruling chunker, and store in Pinecone.

    Returns a 202 Accepted with the background job details.
    """
    from app.tasks.knowledge import ingest_ato_legal_database

    task = ingest_ato_legal_database.delay(dev_mode=dev_mode)

    return AdminIngestionJobResponse(
        data={
            "job_id": task.id,
            "source_type": "ato_legal_db",
            "status": "pending",
            "message": f"ATO Legal Database ingestion queued. Dev mode: {dev_mode}",
        }
    )


@router.post(
    "/ingest/tpb-treasury",
    response_model=AdminIngestionJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_tpb_treasury_ingestion(
    dev_mode: bool = False,
) -> AdminIngestionJobResponse:
    """Trigger ingestion of TPB and Treasury practitioner guidance.

    Returns a 202 Accepted with the background job details.
    """
    from app.tasks.knowledge import ingest_tpb_treasury

    task = ingest_tpb_treasury.delay(dev_mode=dev_mode)

    return AdminIngestionJobResponse(
        data={
            "job_id": task.id,
            "source_type": "tpb_treasury",
            "status": "pending",
            "message": f"TPB & Treasury ingestion queued. Dev mode: {dev_mode}",
        }
    )


@router.get("/ingest/status/{task_id}")
async def get_ingestion_task_status(task_id: str) -> dict:
    """Get the live status of a Celery ingestion task.

    Reads the Celery AsyncResult to return current progress without
    needing to poll the database. Works for all Spec 045 ingestion tasks.

    Returns status, progress counters, and any error information.
    """
    from celery.result import AsyncResult

    from app.tasks.celery_app import celery_app as app

    result = AsyncResult(task_id, app=app)
    state = result.state  # PENDING, STARTED, PROGRESS, SUCCESS, FAILURE, REVOKED

    response: dict = {
        "task_id": task_id,
        "status": state,
    }

    if state == "PENDING":
        # Task hasn't started yet (or unknown task ID)
        response["progress"] = {
            "processed": 0,
            "added": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0,
            "source_type": None,
        }
    elif state == "STARTED":
        response["progress"] = {
            "processed": 0,
            "added": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0,
            "source_type": (result.info or {}).get("source_type"),
        }
    elif state == "PROGRESS":
        meta = result.info or {}
        response["progress"] = {
            "processed": meta.get("processed", 0),
            "added": meta.get("added", 0),
            "updated": meta.get("updated", 0),
            "skipped": meta.get("skipped", 0),
            "failed": meta.get("failed", 0),
            "source_type": meta.get("source_type"),
            "current_item": meta.get("current_item"),
        }
    elif state == "SUCCESS":
        info = result.info or {}
        response["progress"] = {
            "processed": info.get("items_processed", 0),
            "added": info.get("items_added", 0),
            "updated": info.get("items_updated", 0),
            "skipped": info.get("items_skipped", 0),
            "failed": info.get("items_failed", 0),
            "source_type": info.get("source_type"),
        }
        response["result"] = info
    elif state == "FAILURE":
        response["error"] = str(result.info) if result.info else "Unknown error"
        response["progress"] = {
            "processed": 0,
            "added": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0,
            "source_type": None,
        }
    else:
        # REVOKED or other states
        response["progress"] = {
            "processed": 0,
            "added": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0,
            "source_type": None,
        }

    return response


@router.get("/freshness", response_model=FreshnessReportResponse)
async def get_freshness_report(
    db: DbSession,
) -> FreshnessReportResponse:
    """Get content freshness report across all knowledge sources.

    Returns per-source freshness status including last ingestion time,
    chunk counts, error counts, and freshness classification
    (fresh/stale/error/never_ingested).
    """
    repo = FreshnessReportRepository(db)
    report = await repo.get_freshness_report()

    total_chunks = sum(item.get("chunk_count", 0) for item in report)

    return FreshnessReportResponse(
        data={
            "sources": report,
            "total_chunks": total_chunks,
            "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    )


# =============================================================================
# Citation Verification Audit (Spec 044)
# =============================================================================


@router.post("/verify-citations", response_model=CitationAuditResponse)
async def verify_citations_audit(
    request: CitationAuditRequest,
    db: DbSession,
) -> CitationAuditResponse:
    """Run a citation verification audit on recent assistant responses.

    Fetches recent chat messages with role='assistant' that have citations,
    then runs the CitationVerifier on each to produce aggregate audit
    statistics.

    Note: Full deep auditing (re-running retrieval against stored responses)
    is not yet supported because we do not store the original retrieved
    chunks alongside each response. This endpoint provides placeholder
    audit stats based on stored citation metadata and can be enhanced
    later once chunk-level provenance is stored.
    """
    from sqlalchemy import select as sa_select

    from app.modules.knowledge.models import ChatMessage as ChatMessageModel

    # Query recent assistant messages that have citations.
    # ChatMessageRepository does not have a method for this yet, so we
    # query directly via the session.
    stmt = (
        sa_select(ChatMessageModel)
        .where(
            ChatMessageModel.role == "assistant",
            ChatMessageModel.citations.isnot(None),
        )
        .order_by(ChatMessageModel.created_at.desc())
        .limit(request.sample_size)
    )
    result = await db.execute(stmt)
    messages = result.scalars().all()

    total_audited = 0
    total_citations_checked = 0
    total_verified = 0
    total_ungrounded = 0
    messages_with_ungrounded = 0

    for msg in messages:
        citations_list = msg.citations or []
        if not citations_list:
            continue

        total_audited += 1

        # Without the original retrieved chunks stored alongside the
        # response, we cannot perform full re-verification. Instead,
        # we use the stored citation metadata to report basic stats.
        # Citations that already have a "verified" field are counted
        # accordingly; those without default to unverified.
        msg_verified = 0
        msg_unverified = 0

        for cit in citations_list:
            total_citations_checked += 1
            if cit.get("verified", False):
                msg_verified += 1
                total_verified += 1
            else:
                msg_unverified += 1
                total_ungrounded += 1

        if msg_unverified > 0:
            messages_with_ungrounded += 1

    verification_rate = (
        total_verified / total_citations_checked if total_citations_checked > 0 else 1.0
    )

    return CitationAuditResponse(
        data={
            "total_audited": total_audited,
            "total_messages_sampled": len(messages),
            "citations_checked": total_citations_checked,
            "citations_verified": total_verified,
            "citations_ungrounded": total_ungrounded,
            "verification_rate": round(verification_rate, 4),
            "messages_with_ungrounded": messages_with_ungrounded,
            "sample_size_requested": request.sample_size,
            "note": (
                "Audit based on stored citation metadata. "
                "Full chunk-level re-verification will be available "
                "once response provenance storage is implemented."
            ),
        }
    )
