"""API routes for client-context AI chat.

Provides endpoints for:
- Client search with typeahead
- Client profile retrieval
- Client-context chat with streaming
- Conversation persistence with client context
"""

import json
import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.dependencies import (
    get_current_tenant_id,
    get_pinecone_service,
    get_voyage_service,
)
from app.core.pinecone_service import PineconeService
from app.core.voyage import VoyageService
from app.database import get_db
from app.modules.integrations.xero.models import XeroConnection
from app.modules.knowledge.chatbot import Citation
from app.modules.knowledge.client_chat_schemas import (
    ClientChatCitation,
    ClientChatMetadata,
    ClientChatRequest,
    ClientChatRequestWithConversation,
    ClientChatResponse,
    ClientProfileData,
    ClientProfileResponse,
    ClientSearchResponse,
    ClientSearchResult,
    ConnectionStatus,
)
from app.modules.knowledge.client_chatbot import ClientContextChatbot
from app.modules.knowledge.repository import (
    ChatConversationRepository,
    ChatMessageRepository,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/knowledge/client-chat", tags=["client-chat"])


# Type aliases for dependencies
DbSession = Annotated[AsyncSession, Depends(get_db)]
PineconeDep = Annotated[PineconeService, Depends(get_pinecone_service)]
VoyageDep = Annotated[VoyageService, Depends(get_voyage_service)]


async def get_client_chatbot(
    db: DbSession,
    pinecone: PineconeDep,
    voyage: VoyageDep,
) -> ClientContextChatbot:
    """Dependency to create client context chatbot."""
    settings = get_settings()
    return ClientContextChatbot(
        db=db,
        anthropic_settings=settings.anthropic,
        pinecone=pinecone,
        voyage=voyage,
    )


ChatbotDep = Annotated[ClientContextChatbot, Depends(get_client_chatbot)]


# =============================================================================
# Client Search (No Anthropic required)
# =============================================================================


@router.get("/clients/search", response_model=ClientSearchResponse)
async def search_clients(
    q: str,
    db: DbSession,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    limit: int = 20,
) -> ClientSearchResponse:
    """Search for clients by name with typeahead.

    Args:
        q: Search query (min 1 character, max 100).
        limit: Maximum results (default 20, max 50).

    Returns:
        List of matching clients with basic info.
    """
    if not q or len(q) < 1:
        return ClientSearchResponse(results=[], total=0, query=q)

    if len(q) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query too long (max 100 characters)",
        )

    limit = min(limit, 50)

    # Search XeroConnection directly (no Anthropic required)
    search_pattern = f"%{q}%"
    result = await db.execute(
        select(XeroConnection)
        .where(
            XeroConnection.tenant_id == tenant_id,
            XeroConnection.status == "active",
            XeroConnection.organization_name.ilike(search_pattern),
        )
        .order_by(XeroConnection.organization_name)
        .limit(limit)
    )
    connections = result.scalars().all()

    return ClientSearchResponse(
        results=[
            ClientSearchResult(
                id=conn.id,
                name=conn.organization_name,
                abn=None,
                connection_id=conn.id,
                organization_name=conn.organization_name,
                is_active=conn.status == "active",
            )
            for conn in connections
        ],
        total=len(connections),
        query=q,
    )


# =============================================================================
# Client Profile
# =============================================================================


@router.get("/clients/{client_id}/profile", response_model=ClientProfileResponse)
async def get_client_profile(
    client_id: UUID,
    chatbot: ChatbotDep,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
) -> ClientProfileResponse:
    """Get client profile for display in chat header.

    Returns profile data, connection status, and freshness info.
    Raises 404 if client not found or not authorized.
    """
    context = await chatbot.get_client_profile(client_id, tenant_id)

    if not context:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found or not authorized",
        )

    # Get connection status
    conn_status = await chatbot.get_connection_status(client_id)

    return ClientProfileResponse(
        profile=ClientProfileData(
            id=context.profile.id,
            name=context.profile.name,
            abn=context.profile.abn,
            entity_type=context.profile.entity_type,
            industry_code=context.profile.industry_code,
            gst_registered=context.profile.gst_registered,
            revenue_bracket=context.profile.revenue_bracket,
            employee_count=context.profile.employee_count,
        ),
        connection=ConnectionStatus(
            status=conn_status.get("status", "unknown"),
            organization_name=conn_status.get("organization_name"),
            last_sync=conn_status.get("last_sync"),
            needs_reauth=conn_status.get("needs_reauth", False),
        ),
        data_freshness=context.data_freshness.isoformat() if context.data_freshness else None,
        is_stale=chatbot.context_builder.is_data_stale(context),
    )


# =============================================================================
# Client Chat (Streaming)
# =============================================================================


def _convert_citation(c: Citation) -> dict:
    """Convert Citation to dict for JSON serialization."""
    return {
        "number": c.number,
        "title": c.title,
        "url": c.url,
        "source_type": c.source_type,
        "effective_date": c.effective_date,
        "text_preview": c.text_preview,
        "score": c.score,
    }


@router.post("/chat/stream")
async def chat_stream(
    request: ClientChatRequest,
    chatbot: ChatbotDep,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
) -> StreamingResponse:
    """Chat with client context (streaming via SSE).

    Uses client financial data combined with RAG for context-aware answers.
    Streams response as Server-Sent Events.

    Event types:
    - 'text': Text chunk from the response
    - 'done': Final event with citations and metadata
    - 'error': Error event if something goes wrong
    """

    async def generate_events():
        """Generator for SSE events."""
        try:
            # Convert conversation history
            history = None
            if request.conversation_history:
                history = [
                    {"role": m.role, "content": m.content} for m in request.conversation_history
                ]

            # Get streaming response with metadata
            stream, metadata, rag_context = await chatbot.chat_with_client_context(
                client_id=request.client_id,
                tenant_id=tenant_id,
                query=request.query,
                conversation_history=history,
                collections=request.collections,
            )

            # Stream text chunks
            async for chunk in stream:
                event_data = json.dumps({"type": "text", "content": chunk})
                yield f"data: {event_data}\n\n"

            # Build citation responses
            citations = [_convert_citation(c) for c in rag_context.citations]

            # Send final metadata
            done_data = json.dumps(
                {
                    "type": "done",
                    "citations": citations,
                    "metadata": {
                        "client_id": str(metadata.client_id),
                        "client_name": metadata.client_name,
                        "query_intent": metadata.query_intent,
                        "context_token_count": metadata.context_token_count,
                        "rag_token_count": metadata.rag_token_count,
                        "data_freshness": metadata.data_freshness,
                        "is_stale": metadata.is_stale,
                    },
                    "query": request.query,
                }
            )
            yield f"data: {done_data}\n\n"

        except ValueError as e:
            error_data = json.dumps({"type": "error", "message": str(e)})
            yield f"data: {error_data}\n\n"
        except Exception as e:
            logger.error("Client chat stream error: %s", e, exc_info=True)
            error_data = json.dumps(
                {
                    "type": "error",
                    "message": "Sorry, I encountered an issue retrieving your data. Please try again shortly.",
                }
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


@router.post("/chat/persistent/stream")
async def chat_persistent_stream(
    request: ClientChatRequestWithConversation,
    user_id: str,  # TODO: Get from auth middleware
    db: DbSession,
    chatbot: ChatbotDep,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
) -> StreamingResponse:
    """Chat with client context and conversation persistence (streaming via SSE).

    Creates or continues a conversation with client context.
    Saves messages to database and streams the response.

    Query params:
        user_id: User ID (temporary - will come from auth)
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
                # Create new conversation with client context
                title = request.query[:50] + "..." if len(request.query) > 50 else request.query
                conversation = await conv_repo.create(
                    user_id=user_id,
                    title=title,
                    client_id=request.client_id,
                )
                await db.commit()
                conversation_id = conversation.id

            # Save user message
            await msg_repo.create(
                conversation_id=conversation_id,
                role="user",
                content=request.query,
            )

            # Get conversation history
            messages = await msg_repo.get_recent(conversation_id, limit=10)
            history = [{"role": m.role, "content": m.content} for m in messages[:-1]]

            # Get streaming response with metadata
            stream, metadata, rag_context = await chatbot.chat_with_client_context(
                client_id=request.client_id,
                tenant_id=tenant_id,
                query=request.query,
                conversation_history=history if history else None,
                collections=request.collections,
            )

            # Collect full response while streaming
            full_response = []

            # Stream text chunks
            async for chunk in stream:
                full_response.append(chunk)
                event_data = json.dumps({"type": "text", "content": chunk})
                yield f"data: {event_data}\n\n"

            # Build citation responses
            citations = [_convert_citation(c) for c in rag_context.citations]

            # Save assistant message with metadata
            await msg_repo.create(
                conversation_id=conversation_id,
                role="assistant",
                content="".join(full_response),
                citations=citations,
                metadata={
                    "query_intent": metadata.query_intent,
                    "context_token_count": metadata.context_token_count,
                    "data_freshness": metadata.data_freshness,
                },
            )

            # Update conversation
            await conv_repo.touch(conversation_id)
            await db.commit()

            # Send final metadata
            done_data = json.dumps(
                {
                    "type": "done",
                    "citations": citations,
                    "metadata": {
                        "client_id": str(metadata.client_id),
                        "client_name": metadata.client_name,
                        "query_intent": metadata.query_intent,
                        "context_token_count": metadata.context_token_count,
                        "rag_token_count": metadata.rag_token_count,
                        "data_freshness": metadata.data_freshness,
                        "is_stale": metadata.is_stale,
                    },
                    "query": request.query,
                    "conversation_id": str(conversation_id),
                }
            )
            yield f"data: {done_data}\n\n"

        except ValueError as e:
            error_data = json.dumps({"type": "error", "message": str(e)})
            yield f"data: {error_data}\n\n"
        except Exception as e:
            logger.error("Client chat persistent stream error: %s", e, exc_info=True)
            error_data = json.dumps(
                {
                    "type": "error",
                    "message": "Sorry, I encountered an issue retrieving your data. Please try again shortly.",
                }
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
# Non-Streaming Chat (for testing)
# =============================================================================


@router.post("/chat", response_model=ClientChatResponse)
async def chat(
    request: ClientChatRequest,
    chatbot: ChatbotDep,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
) -> ClientChatResponse:
    """Chat with client context (non-streaming).

    For testing and simple integrations. Use /chat/stream for production.
    """
    try:
        # Convert conversation history
        history = None
        if request.conversation_history:
            history = [{"role": m.role, "content": m.content} for m in request.conversation_history]

        # Get response with metadata
        stream, metadata, rag_context = await chatbot.chat_with_client_context(
            client_id=request.client_id,
            tenant_id=tenant_id,
            query=request.query,
            conversation_history=history,
            collections=request.collections,
        )

        # Collect full response
        response_parts = []
        async for chunk in stream:
            response_parts.append(chunk)

        # Build citation responses
        citations = [
            ClientChatCitation(
                number=c.number,
                title=c.title,
                url=c.url,
                source_type=c.source_type,
                effective_date=c.effective_date,
                text_preview=c.text_preview,
                score=c.score,
            )
            for c in rag_context.citations
        ]

        return ClientChatResponse(
            response="".join(response_parts),
            citations=citations,
            metadata=ClientChatMetadata(
                client_id=metadata.client_id,
                client_name=metadata.client_name,
                query_intent=metadata.query_intent,
                context_token_count=metadata.context_token_count,
                rag_token_count=metadata.rag_token_count,
                data_freshness=metadata.data_freshness,
                is_stale=metadata.is_stale,
            ),
            query=request.query,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from None
    except Exception as e:
        logger.error("Client chat error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Sorry, I encountered an issue retrieving your data. Please try again shortly.",
        ) from None
