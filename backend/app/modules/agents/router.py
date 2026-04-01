"""API router for the agents module."""

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.agents.audit import AgentAuditService
from app.modules.agents.dependencies import OrchestratorDep
from app.modules.agents.schemas import (
    AgentChatRequest,
    AgentChatResponse,
    EscalationResponse,
    EscalationStatsResponse,
    EscalationStatus,
    PerspectiveResultResponse,
    ResolveEscalationRequest,
)
from app.modules.auth.models import PracticeUser
from app.modules.auth.permissions import Permission, require_permission
from app.modules.knowledge.repository import (
    ChatConversationRepository,
    ChatMessageRepository,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


def get_audit_service(db: AsyncSession = Depends(get_db)) -> AgentAuditService:
    """Get audit service instance."""
    return AgentAuditService(db)


@router.post("/chat", response_model=AgentChatResponse)
async def agent_chat(
    request: AgentChatRequest,
    orchestrator: OrchestratorDep,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    db: AsyncSession = Depends(get_db),
) -> AgentChatResponse:
    """Process a query through the multi-perspective agent system.

    The system will:
    1. Detect which perspectives are relevant to the query
    2. Build context from knowledge base and client data
    3. Generate a response with attributed perspective sections
    4. Flag for escalation if confidence is low
    """
    try:
        # Get knowledge chunks from RAG if available
        knowledge_chunks = await _fetch_knowledge_chunks(request.query, db)

        # Process through orchestrator
        result = await orchestrator.process_query(
            query=request.query,
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            connection_id=request.connection_id,
            knowledge_chunks=knowledge_chunks,
        )

        # Log the query (audit)
        audit_service = AgentAuditService(db)
        query_record = await audit_service.log_query(
            query=request.query,
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            response=result,
            connection_id=request.connection_id,
        )

        # Create escalation if required
        if result.escalation_required:
            await audit_service.create_escalation(
                query=request.query,
                query_record=query_record,
                response=result,
                tenant_id=current_user.tenant_id,
            )

        # Increment AI query counter for usage tracking (Spec 020)
        try:
            from sqlalchemy import update

            from app.modules.auth.models import Tenant

            await db.execute(
                update(Tenant)
                .where(Tenant.id == current_user.tenant_id)
                .values(ai_queries_month=Tenant.ai_queries_month + 1)
            )
        except Exception as e:
            logger.warning(f"Failed to increment AI query counter: {e}")

        await db.commit()

        # Extract data freshness from client context if available
        data_freshness = None
        if result.raw_client_context and hasattr(result.raw_client_context, "data_freshness"):
            df = result.raw_client_context.data_freshness
            if df:
                data_freshness = df.isoformat() if hasattr(df, "isoformat") else str(df)

        # Convert to API response
        return AgentChatResponse(
            correlation_id=str(result.correlation_id),
            content=result.content,
            perspectives_used=[p.value for p in result.perspectives_used],
            perspective_results=[
                PerspectiveResultResponse(
                    perspective=r.perspective.value,
                    content=r.content,
                    citations=r.citations,
                    confidence=r.confidence,
                )
                for r in result.perspective_results
            ],
            confidence=result.confidence,
            escalation_required=result.escalation_required,
            escalation_reason=result.escalation_reason,
            citations=result.citations,
            processing_time_ms=result.processing_time_ms,
            data_freshness=data_freshness,
        )

    except Exception as e:
        logger.error(f"Agent chat error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process query: {e!s}",
        ) from e


@router.post("/chat/stream")
async def agent_chat_stream(
    orchestrator: OrchestratorDep,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    db: AsyncSession = Depends(get_db),
    query: str = Form(..., min_length=1, max_length=2000),
    connection_id: str | None = Form(None),
    conversation_id: str | None = Form(None),
    file: UploadFile | None = File(None),
) -> StreamingResponse:
    """Stream a query response with thinking status updates and conversation persistence.

    Sends SSE events:
    - thinking: Status updates during processing
    - perspectives: Detected perspectives
    - response: Final response content
    - metadata: Confidence, processing time, conversation_id, etc.
    - done: Stream complete
    - error: Error occurred

    Conversations are automatically saved per client for history viewing.
    Supports optional file attachments (images, PDFs, Excel, CSV).
    """
    # Parse UUIDs from form fields
    parsed_connection_id = UUID(connection_id) if connection_id else None
    parsed_conversation_id = UUID(conversation_id) if conversation_id else None

    # Process file attachment before entering the generator
    attachment_data = None
    if file and file.filename:
        try:
            from app.core.file_processor import process_chat_attachment

            attachment_data = await process_chat_attachment(
                file,
                current_user.tenant_id,
                "assistant",
                parsed_connection_id or "general",
                f"msg-{UUID(int=0).hex[:12]}",
            )
        except ValueError as e:
            return StreamingResponse(
                iter([_sse_event("error", {"message": str(e)})]),
                media_type="text/event-stream",
            )

    async def generate_events() -> AsyncGenerator[str, None]:
        conv_id = parsed_conversation_id
        conv_repo = ChatConversationRepository(db)
        msg_repo = ChatMessageRepository(db)

        try:
            # Stage 1: Get or create conversation
            yield _sse_event(
                "thinking", {"stage": "initializing", "message": "Starting conversation..."}
            )

            user_id = current_user.clerk_id  # Clerk user ID for conversation ownership
            client_id = parsed_connection_id  # Connection ID = client context

            if conv_id:
                # Continue existing conversation
                conversation = await conv_repo.get_by_id(conv_id)
                if not conversation:
                    yield _sse_event("error", {"message": "Conversation not found"})
                    return
                if conversation.user_id != user_id:
                    yield _sse_event("error", {"message": "Access denied to conversation"})
                    return
            else:
                # Create new conversation with title from query
                title = query[:100] + ("..." if len(query) > 100 else "")
                conversation = await conv_repo.create(
                    user_id=user_id,
                    title=title,
                    client_id=client_id,
                )
                conv_id = conversation.id
                await db.commit()

            # Save user message
            await msg_repo.create(
                conversation_id=conv_id,
                role="user",
                content=query,
            )
            await db.commit()

            # Stage 2: Detecting perspectives
            yield _sse_event(
                "thinking", {"stage": "detecting", "message": "Analyzing your question..."}
            )

            # Get knowledge chunks
            yield _sse_event(
                "thinking", {"stage": "knowledge", "message": "Searching knowledge base..."}
            )
            knowledge_chunks = await _fetch_knowledge_chunks(query, db)

            # Stage 3: Process through orchestrator with status callbacks
            full_response = ""
            async for event in orchestrator.process_query_streaming(
                query=query,
                tenant_id=current_user.tenant_id,
                user_id=current_user.id,
                connection_id=parsed_connection_id,
                knowledge_chunks=knowledge_chunks,
                content_blocks=attachment_data.content_blocks if attachment_data else None,
            ):
                # Capture response content for saving
                if event["type"] == "response" and "content" in event.get("data", {}):
                    full_response = event["data"]["content"]

                # Add conversation_id to metadata event
                if event["type"] == "metadata":
                    event_data = event.get("data", {})
                    event_data["conversation_id"] = str(conv_id)
                    yield _sse_event(event["type"], event_data)
                else:
                    yield _sse_event(event["type"], event.get("data", {}))

            # Get the final result for audit logging
            result = orchestrator.last_result
            if result:
                # Save assistant response
                await msg_repo.create(
                    conversation_id=conv_id,
                    role="assistant",
                    content=result.content,
                )

                # Update conversation timestamp
                await conv_repo.touch(conv_id)

                # Log the query (audit)
                audit_service = AgentAuditService(db)
                query_record = await audit_service.log_query(
                    query=query,
                    tenant_id=current_user.tenant_id,
                    user_id=current_user.id,
                    response=result,
                    connection_id=parsed_connection_id,
                )

                # Create escalation if required
                if result.escalation_required:
                    await audit_service.create_escalation(
                        query=query,
                        query_record=query_record,
                        response=result,
                        tenant_id=current_user.tenant_id,
                    )

                # Increment AI query counter for usage tracking (Spec 020)
                try:
                    from sqlalchemy import update

                    from app.modules.auth.models import Tenant

                    await db.execute(
                        update(Tenant)
                        .where(Tenant.id == current_user.tenant_id)
                        .values(ai_queries_month=Tenant.ai_queries_month + 1)
                    )
                except Exception as e:
                    logger.warning(f"Failed to increment AI query counter: {e}")

                await db.commit()

            yield _sse_event("done", {"conversation_id": str(conv_id)})

        except Exception as e:
            logger.error(f"Agent chat stream error: {e}", exc_info=True)
            yield _sse_event("error", {"message": str(e)})

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _sse_event(event_type: str, data: dict[str, Any]) -> str:
    """Format an SSE event."""
    return f"data: {json.dumps({'type': event_type, **data})}\n\n"


async def _fetch_knowledge_chunks(
    query: str,
    db: AsyncSession,
) -> list[dict[str, Any]]:
    """Fetch relevant knowledge chunks using the enhanced hybrid search pipeline.

    Uses query routing, BM25 + semantic fusion, and cross-encoder re-ranking
    for higher quality retrieval across legislation, ATO rulings, TPB guidance,
    and other knowledge sources.

    Falls back to basic Pinecone vector search if the hybrid pipeline is
    unavailable.

    Args:
        query: The user's query.
        db: Database session for BM25 index lookup.

    Returns:
        List of knowledge chunk dictionaries with text, score, and metadata.
    """
    # Try enhanced hybrid search first
    try:
        from app.core.dependencies import get_pinecone_service, get_voyage_service
        from app.modules.knowledge.retrieval.hybrid_search import HybridSearchEngine
        from app.modules.knowledge.retrieval.query_expander import QueryExpander
        from app.modules.knowledge.retrieval.query_router import QueryRouter, QueryType
        from app.modules.knowledge.retrieval.reranker import CrossEncoderReranker

        pinecone = await get_pinecone_service()
        voyage = await get_voyage_service()

        # Step 1: Classify query for retrieval strategy
        router = QueryRouter()
        classification = router.classify(query)

        # Step 2: Expand query for conceptual/scenario queries
        expanded_queries = [query]
        if classification.query_type in (QueryType.CONCEPTUAL, QueryType.SCENARIO):
            try:
                expander = QueryExpander()
                expanded_queries = await expander.expand_query(query, classification.query_type)
            except Exception:
                logger.debug("Query expansion failed; using original query")

        # Step 3: Hybrid search (BM25 + semantic) across expanded queries
        engine = HybridSearchEngine(db, pinecone, voyage)
        semantic_weight = classification.fusion_weights[0]

        all_results = []
        for q in expanded_queries:
            results = await engine.hybrid_search(
                query=q,
                collection="compliance_knowledge",
                limit=30,
                semantic_weight=semantic_weight,
                pinecone_filter=classification.pinecone_filter,
            )
            all_results.extend(results)

        # Deduplicate by chunk_id, keeping the highest score
        seen: dict[str, object] = {}
        for chunk in all_results:
            existing = seen.get(chunk.chunk_id)
            if existing is None or chunk.score > existing.score:
                seen[chunk.chunk_id] = chunk
        unique_results = sorted(seen.values(), key=lambda c: c.score, reverse=True)

        # Step 4: Re-rank top candidates with cross-encoder
        reranker = CrossEncoderReranker()
        reranked = reranker.rerank(query, list(unique_results), top_k=12)

        # Step 5: Convert to orchestrator format (skip results with no text/metadata)
        chunks = []
        # Detect if scores are raw RRF values (all < 0.05) vs cross-encoder (0-1)
        max_score = max((c.score for c in reranked), default=0)
        needs_rescale = max_score < 0.05  # RRF scores are ~0.016
        for scored_chunk in reranked:
            payload = scored_chunk.payload or {}
            text = scored_chunk.text or payload.get("text", "")
            if not text:
                continue
            metadata = {k: v for k, v in payload.items() if k != "text"}
            metadata["source"] = payload.get("source_url") or payload.get("source_type", "Unknown")
            # Rescale RRF scores to 0-1 range for meaningful display
            score = scored_chunk.score
            if needs_rescale and max_score > 0:
                score = score / max_score * 0.85  # Top result = 85%
            chunks.append(
                {
                    "text": text,
                    "score": score,
                    "metadata": metadata,
                }
            )
        return chunks

    except ImportError:
        logger.info("Hybrid search unavailable, falling back to basic Pinecone search")
    except Exception as e:
        logger.warning("Hybrid knowledge search failed, falling back to basic: %s", e)

    # Fallback: basic Pinecone vector search
    try:
        from app.core.dependencies import get_pinecone_service, get_voyage_service
        from app.modules.knowledge.collections import (
            INDEX_NAME,
            get_namespace_with_env,
        )

        pinecone = await get_pinecone_service()
        voyage = await get_voyage_service()

        query_vector = await voyage.embed_query(query)

        namespaces = [
            get_namespace_with_env(ns)
            for ns in [
                "compliance_knowledge",
                "strategic_advisory",
                "industry_knowledge",
                "business_fundamentals",
                "financial_management",
                "people_operations",
            ]
        ]

        results = await pinecone.search_multi_namespace(
            index_name=INDEX_NAME,
            namespaces=namespaces,
            query_vector=query_vector,
            limit_per_namespace=3,
            total_limit=8,
            score_threshold=0.3,
        )

        chunks = []
        for point in results:
            payload = point.payload or {}
            metadata = {k: v for k, v in payload.items() if k != "text"}
            metadata["source"] = payload.get("source_url") or payload.get("source_type", "Unknown")
            chunks.append(
                {
                    "text": payload.get("text", ""),
                    "score": point.score,
                    "metadata": metadata,
                }
            )
        return chunks
    except Exception as e:
        logger.warning("Knowledge search failed: %s", e)
        return []


@router.get("/escalations", response_model=list[EscalationResponse])
async def list_escalations(
    status: str | None = Query(None, description="Filter by status (pending, resolved, dismissed)"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    audit_service: AgentAuditService = Depends(get_audit_service),
) -> list[EscalationResponse]:
    """List escalations for the current tenant.

    Returns pending escalations by default, or filter by status.
    """
    # Validate status if provided
    if status and status not in [s.value for s in EscalationStatus]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {[s.value for s in EscalationStatus]}",
        )

    escalations = await audit_service.list_escalations(
        tenant_id=current_user.tenant_id,
        status=status,
        limit=limit,
        offset=offset,
    )

    return [
        EscalationResponse(
            id=e.id,
            query_id=e.query_id,
            reason=e.reason,
            confidence=e.confidence,
            status=EscalationStatus(e.status),
            query_preview=e.query_text[:200] if e.query_text else "",
            perspectives_used=e.perspectives_used,
            connection_id=None,  # Could join with AgentQuery if needed
            created_at=e.created_at,
            resolved_at=e.resolved_at,
            resolved_by_name=None,  # Could join with PracticeUser if needed
        )
        for e in escalations
    ]


@router.get("/escalations/stats", response_model=EscalationStatsResponse)
async def get_escalation_stats(
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    audit_service: AgentAuditService = Depends(get_audit_service),
) -> EscalationStatsResponse:
    """Get escalation statistics for the current tenant."""
    stats = await audit_service.get_escalation_stats(current_user.tenant_id)

    return EscalationStatsResponse(
        pending_count=stats["pending_count"],
        resolved_today=stats["resolved_today"],
        average_confidence=stats["average_confidence"],
        top_reasons=stats["top_reasons"],
    )


@router.get("/escalations/{escalation_id}", response_model=EscalationResponse)
async def get_escalation(
    escalation_id: UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    audit_service: AgentAuditService = Depends(get_audit_service),
) -> EscalationResponse:
    """Get a specific escalation by ID."""
    escalation = await audit_service.get_escalation(
        escalation_id=escalation_id,
        tenant_id=current_user.tenant_id,
    )

    if not escalation:
        raise HTTPException(status_code=404, detail="Escalation not found")

    return EscalationResponse(
        id=escalation.id,
        query_id=escalation.query_id,
        reason=escalation.reason,
        confidence=escalation.confidence,
        status=EscalationStatus(escalation.status),
        query_preview=escalation.query_text[:200] if escalation.query_text else "",
        perspectives_used=escalation.perspectives_used,
        connection_id=None,
        created_at=escalation.created_at,
        resolved_at=escalation.resolved_at,
        resolved_by_name=None,
    )


@router.post("/escalations/{escalation_id}/resolve", response_model=EscalationResponse)
async def resolve_escalation(
    escalation_id: UUID,
    request: ResolveEscalationRequest,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_MANAGE)),
    audit_service: AgentAuditService = Depends(get_audit_service),
    db: AsyncSession = Depends(get_db),
) -> EscalationResponse:
    """Resolve an escalation with accountant input.

    The accountant can provide:
    - Resolution notes explaining the outcome
    - Their own response to the query (optional)
    - Feedback on whether the agent's analysis was useful
    """
    escalation = await audit_service.resolve_escalation(
        escalation_id=escalation_id,
        tenant_id=current_user.tenant_id,
        resolved_by=current_user.id,
        resolution_notes=request.resolution_notes,
        accountant_response=request.accountant_response,
        feedback_useful=request.feedback_useful,
    )

    if not escalation:
        raise HTTPException(status_code=404, detail="Escalation not found")

    await db.commit()

    return EscalationResponse(
        id=escalation.id,
        query_id=escalation.query_id,
        reason=escalation.reason,
        confidence=escalation.confidence,
        status=EscalationStatus(escalation.status),
        query_preview=escalation.query_text[:200] if escalation.query_text else "",
        perspectives_used=escalation.perspectives_used,
        connection_id=None,
        created_at=escalation.created_at,
        resolved_at=escalation.resolved_at,
        resolved_by_name=f"{current_user.first_name} {current_user.last_name}",
    )


@router.post("/escalations/{escalation_id}/dismiss", response_model=EscalationResponse)
async def dismiss_escalation(
    escalation_id: UUID,
    reason: str = Query(..., min_length=1, max_length=500, description="Reason for dismissal"),
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_MANAGE)),
    audit_service: AgentAuditService = Depends(get_audit_service),
    db: AsyncSession = Depends(get_db),
) -> EscalationResponse:
    """Dismiss an escalation without full resolution.

    Use this when the escalation was created incorrectly or is no longer relevant.
    """
    escalation = await audit_service.dismiss_escalation(
        escalation_id=escalation_id,
        tenant_id=current_user.tenant_id,
        dismissed_by=current_user.id,
        reason=reason,
    )

    if not escalation:
        raise HTTPException(status_code=404, detail="Escalation not found")

    await db.commit()

    return EscalationResponse(
        id=escalation.id,
        query_id=escalation.query_id,
        reason=escalation.reason,
        confidence=escalation.confidence,
        status=EscalationStatus(escalation.status),
        query_preview=escalation.query_text[:200] if escalation.query_text else "",
        perspectives_used=escalation.perspectives_used,
        connection_id=None,
        created_at=escalation.created_at,
        resolved_at=escalation.resolved_at,
        resolved_by_name=f"{current_user.first_name} {current_user.last_name}",
    )


@router.get("/queries/{correlation_id}")
async def get_query_detail(
    correlation_id: UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.INTEGRATION_READ)),
    audit_service: AgentAuditService = Depends(get_audit_service),
) -> dict[str, Any]:
    """Get detailed information about a specific agent query.

    Used for audit purposes to understand what perspectives were used
    and how the response was generated.
    """
    query_record = await audit_service.get_query_by_correlation_id(
        correlation_id=correlation_id,
        tenant_id=current_user.tenant_id,
    )

    if not query_record:
        raise HTTPException(status_code=404, detail="Query not found")

    return {
        "id": str(query_record.id),
        "correlation_id": str(query_record.correlation_id),
        "perspectives_used": query_record.perspectives_used,
        "confidence": query_record.confidence,
        "escalation_required": query_record.escalation_required,
        "escalation_reason": query_record.escalation_reason,
        "processing_time_ms": query_record.processing_time_ms,
        "token_usage": query_record.token_usage,
        "created_at": query_record.created_at.isoformat() if query_record.created_at else None,
    }
