"""Client-Context AI Chatbot Service.

Extends the base KnowledgeChatbot with client-specific financial context
for personalized question answering.

Enhanced (Spec 045 T027) with ``chat_with_knowledge()`` which combines the
hybrid search pipeline (BM25 + semantic + cross-encoder re-ranking) with
client financial context for client-contextual tax research.
"""

import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import AnthropicSettings
from app.core.pinecone_service import PineconeService
from app.core.voyage import VoyageService
from app.modules.integrations.xero.models import XeroClient, XeroConnection
from app.modules.knowledge.chatbot import ChatContext, Citation, KnowledgeChatbot
from app.modules.knowledge.context_builder import ClientContext, ContextBuilderService

logger = logging.getLogger(__name__)


@dataclass
class ClientSearchResult:
    """Result from client search."""

    id: UUID
    name: str
    abn: str | None
    connection_id: UUID
    organization_name: str | None
    is_active: bool


@dataclass
class ClientChatMetadata:
    """Metadata about a client-context chat response."""

    client_id: UUID
    client_name: str
    query_intent: str
    context_token_count: int
    rag_token_count: int
    data_freshness: str | None
    is_stale: bool
    citations: list[Citation]


# System prompt for knowledge-grounded client-contextual tax research (T027).
# Combines legislation/ruling grounding with client financial data.
KNOWLEDGE_GROUNDED_CLIENT_PROMPT = """You are Clairo AI, a tax compliance assistant for Australian accountants and bookkeepers.

Your audience is accounting professionals. Be direct, concise, and practical. Skip introductions and filler text - get straight to the answer.

## Knowledge-Grounded Client Context Mode
You are providing tax advice for a specific client. You MUST ground your answer in BOTH:
1. **Tax knowledge base** — legislation sections, ATO rulings, and guidance (provided as SOURCES below)
2. **Client financial data** — actual figures from the client's Xero accounting data (provided as CLIENT DATA below)

## IMPORTANT GROUNDING RULES
- Answer ONLY based on the provided SOURCES and CLIENT DATA
- If the sources don't contain enough information to answer, say so explicitly
- NEVER fabricate section numbers, ruling numbers, or case citations
- When referencing tax rules, cite the specific source using numbered citations [1], [2], etc.
- When referencing client data, use actual figures (e.g., "Based on your client's $150K shareholder loan...")
- Clearly distinguish between:
  - Facts from the client data (use specific numbers, label as "Client Data")
  - Tax rules and legislation (use numbered citations [1], [2], label as source)
  - Your recommendations (explain reasoning based on both)

## Structure
- Use headings and bullet points for complex answers
- Show calculations and methodology so the accountant can verify
- If the client data seems incomplete or stale, note this in your response
- For time-sensitive matters (rates, deadlines), note these may change - verify on ato.gov.au"""


# Extended system prompt for client context
CLIENT_CONTEXT_SYSTEM_PROMPT = """You are Clairo AI, a tax compliance assistant for Australian accountants and bookkeepers.

Your audience is accounting professionals. Be direct, concise, and practical. Skip introductions and filler text - get straight to the answer.

## Client Context Mode
You are currently providing advice for a specific client. Use the CLIENT DATA provided to give personalized, data-driven answers.

Guidelines for client context:
1. Reference specific client data in your answers (e.g., "Based on your client's AR aging of $X...")
2. When showing numbers, be specific - use actual figures from the client data
3. Distinguish clearly between:
   - Facts from the client data (use specific numbers)
   - General tax/compliance rules (cite knowledge base sources)
   - Recommendations (explain your reasoning)
4. If the client data seems incomplete or stale, note this in your response
5. For calculations, show your methodology so the accountant can verify

## Citations
- Use numbered citations [1], [2], etc. for knowledge base sources
- Clearly label when you're using client data vs. knowledge base
- Structure complex answers with headings and bullets

For time-sensitive matters (rates, deadlines), note these may change - verify on ato.gov.au."""


class ClientContextChatbot:
    """AI chatbot with client-specific financial context."""

    def __init__(
        self,
        db: AsyncSession,
        anthropic_settings: AnthropicSettings,
        pinecone: PineconeService,
        voyage: VoyageService,
    ):
        """Initialize the client context chatbot.

        Args:
            db: Async database session for client data access.
            anthropic_settings: Anthropic API settings.
            pinecone: Pinecone service for RAG.
            voyage: Voyage service for embeddings.
        """
        self.db = db
        self.settings = anthropic_settings

        # Initialize base chatbot for RAG functionality
        self.base_chatbot = KnowledgeChatbot(anthropic_settings, pinecone, voyage)

        # Initialize context builder
        self.context_builder = ContextBuilderService(db)

    async def search_clients(
        self,
        query: str,
        tenant_id: UUID,
        limit: int = 20,
    ) -> list[ClientSearchResult]:
        """Search for client businesses (Xero connections) by name.

        Args:
            query: Search query (min 1 character).
            tenant_id: Tenant ID for RLS filtering.
            limit: Maximum results to return.

        Returns:
            List of matching client businesses.
        """
        if not query or len(query) < 1:
            return []

        # Search XeroConnection (the actual client businesses) by organization name
        search_pattern = f"%{query}%"

        result = await self.db.execute(
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

        return [
            ClientSearchResult(
                id=conn.id,
                name=conn.organization_name,
                abn=None,  # XeroConnection doesn't have ABN directly
                connection_id=conn.id,
                organization_name=conn.organization_name,
                is_active=conn.status == "active",
            )
            for conn in connections
        ]

    async def get_client_profile(
        self,
        client_id: UUID,
        tenant_id: UUID,
    ) -> ClientContext | None:
        """Get full client profile for display.

        Args:
            client_id: The client ID (XeroConnection ID).
            tenant_id: Tenant ID for validation.

        Returns:
            ClientContext with profile data, or None if not found.
        """
        # Verify connection belongs to tenant
        result = await self.db.execute(
            select(XeroConnection).where(
                XeroConnection.id == client_id,
                XeroConnection.tenant_id == tenant_id,
            )
        )
        connection = result.scalar_one_or_none()
        if not connection:
            return None

        # Build minimal context (profile only)
        return await self.context_builder.build_context(
            connection_id=client_id,  # client_id is XeroConnection.id
            query="",  # No query for profile view
            include_tier3=False,
        )

    async def chat_with_client_context(
        self,
        client_id: UUID,
        tenant_id: UUID,
        query: str,
        conversation_history: list[dict] | None = None,
        collections: list[str] | None = None,
    ) -> tuple[AsyncGenerator[str, None], ClientChatMetadata, ChatContext]:
        """Chat with client context and RAG integration.

        Args:
            client_id: The client ID (XeroConnection ID) for context.
            tenant_id: Tenant ID for validation.
            query: The user's question.
            conversation_history: Previous conversation messages.
            collections: Knowledge base collections to search.

        Returns:
            Tuple of (response stream, client metadata, RAG context).
        """
        # Verify connection belongs to tenant
        result = await self.db.execute(
            select(XeroConnection).where(
                XeroConnection.id == client_id,
                XeroConnection.tenant_id == tenant_id,
            )
        )
        connection = result.scalar_one_or_none()
        if not connection:
            raise ValueError(f"Client {client_id} not found or not authorized")

        # Build client context
        history_texts = [m["content"] for m in (conversation_history or []) if m["role"] == "user"]
        client_context = await self.context_builder.build_context(
            connection_id=client_id,  # client_id is XeroConnection.id
            query=query,
            conversation_history=history_texts,
            include_tier3=self.context_builder.intent_detector.is_drill_down_request(query),
        )

        # Retrieve RAG context
        rag_context = await self.base_chatbot.retrieve_context(
            query=query,
            collections=collections,
            limit=5,
            score_threshold=0.3,
        )

        # Build combined prompt
        formatted_client_context = self.context_builder.format_context_for_prompt(client_context)

        # Create metadata
        metadata = ClientChatMetadata(
            client_id=client_id,
            client_name=connection.organization_name or "Unknown",
            query_intent=client_context.query_intent.value,
            context_token_count=client_context.token_count,
            rag_token_count=len(rag_context.formatted_context) // 4,  # Approximate
            data_freshness=client_context.data_freshness.isoformat()
            if client_context.data_freshness
            else None,
            is_stale=self.context_builder.is_data_stale(client_context),
            citations=rag_context.citations,
        )

        # Generate streaming response
        response_stream = self._generate_response_stream(
            query=query,
            client_context=formatted_client_context,
            rag_context=rag_context,
            conversation_history=conversation_history,
        )

        return response_stream, metadata, rag_context

    async def chat_with_knowledge(
        self,
        query: str,
        client_id: UUID,
        tenant_id: UUID,
        domain: str | None = None,
        conversation_history: list[dict] | None = None,
        session: AsyncSession | None = None,
    ) -> dict:
        """Chat with combined knowledge-base grounding and client financial context.

        Uses the enhanced hybrid search pipeline (BM25 + semantic + cross-encoder
        re-ranking) from Spec 045 to retrieve tax knowledge, then combines it with
        client-specific financial data from Xero for a grounded, contextual answer.

        This method is the key differentiator over Tax Guru: answers reference both
        legislation/rulings AND the client's actual financial data.

        Args:
            query: The user's tax question.
            client_id: The client ID (XeroConnection ID) for financial context.
            tenant_id: Tenant ID for RLS validation.
            domain: Optional tax domain slug (e.g., "gst") to scope retrieval.
            conversation_history: Previous conversation messages for multi-turn.
            session: Async SQLAlchemy session for hybrid search BM25 index lookup.
                Falls back to ``self.db`` if not provided.

        Returns:
            Dict matching ``KnowledgeChatResponse`` schema with keys: ``message``,
            ``citations``, ``confidence``, ``confidence_score``, ``domain_detected``,
            ``query_type``, ``superseded_warnings``, ``attribution``,
            ``client_name``, ``client_id``.

        Raises:
            ValueError: If client_id is not found or not authorized for tenant.
        """
        # Step 1: Validate client belongs to tenant
        result = await self.db.execute(
            select(XeroConnection).where(
                XeroConnection.id == client_id,
                XeroConnection.tenant_id == tenant_id,
            )
        )
        connection = result.scalar_one_or_none()
        if not connection:
            raise ValueError(f"Client {client_id} not found or not authorized")

        # Step 2: Build client financial context from Xero data
        history_texts = [m["content"] for m in (conversation_history or []) if m["role"] == "user"]
        client_context = await self.context_builder.build_context(
            connection_id=client_id,
            query=query,
            conversation_history=history_texts,
            include_tier3=self.context_builder.intent_detector.is_drill_down_request(query),
        )
        formatted_client_context = self.context_builder.format_context_for_prompt(client_context)

        # Step 3: Retrieve tax knowledge via enhanced hybrid search pipeline
        search_session = session or self.db
        knowledge_context = await self.base_chatbot.retrieve_context_enhanced(
            query=query,
            domain=domain,
            session=search_session,
        )

        # Step 4: Build combined prompt with both contexts and generate response
        messages: list[dict] = []

        # Add conversation history (keep last 3 exchanges)
        if conversation_history:
            for msg in conversation_history[-6:]:
                messages.append(
                    {
                        "role": msg["role"],
                        "content": msg["content"],
                    }
                )

        # Build user message combining client data and knowledge sources
        user_content = f"CLIENT DATA:\n{formatted_client_context}\n\n"
        if knowledge_context.chunks:
            user_content += f"SOURCES:\n{knowledge_context.formatted_context}\n\n"
        user_content += f"QUESTION: {query}"

        messages.append({"role": "user", "content": user_content})

        # Generate non-streaming response with knowledge-grounded client prompt
        response = await self.base_chatbot.client.messages.create(
            model=self.settings.model,
            max_tokens=self.settings.max_tokens,
            temperature=self.settings.temperature,
            system=KNOWLEDGE_GROUNDED_CLIENT_PROMPT,
            messages=messages,
        )
        message = response.content[0].text

        # Step 5: Compute confidence from retrieval scores
        scores = [c.get("score", 0.0) for c in knowledge_context.chunks if c.get("score")]
        top_score = scores[0] if scores else 0.0
        mean_top5 = sum(scores[:5]) / min(len(scores), 5) if scores else 0.0
        # Citation verified rate: placeholder (full verification in T025)
        citation_verified_rate = 1.0 if knowledge_context.citations else 0.0
        confidence, confidence_score = self.base_chatbot.compute_confidence(
            top_score, mean_top5, citation_verified_rate
        )

        # Superseded content warnings
        superseded_warnings = self.base_chatbot.get_superseded_warnings(knowledge_context.chunks)

        # Attribution text
        has_legislation = any(
            c.get("source_type") in ("legislation", "act", "federal_register")
            for c in knowledge_context.chunks
        )
        attribution = self.base_chatbot.get_attribution_text(has_legislation)

        # Detect domain/query type from the base chatbot's router (if available)
        query_type_str = "conceptual"
        domain_detected: str | None = domain
        try:
            from app.modules.knowledge.retrieval.query_router import QueryRouter

            router = QueryRouter()
            classification = router.classify(query, domain)
            query_type_str = classification.query_type.value
            domain_detected = classification.domain_detected
        except ImportError:
            pass

        # Build citation dicts for the response
        citation_dicts = []
        for cit in knowledge_context.citations:
            citation_dicts.append(
                {
                    "number": cit.number,
                    "title": cit.title,
                    "url": cit.url,
                    "source_type": cit.source_type,
                    "effective_date": cit.effective_date,
                    "text_preview": cit.text_preview,
                    "score": cit.score,
                    "verified": getattr(cit, "verified", False),
                    "section_ref": getattr(cit, "section_ref", None),
                }
            )

        return {
            "message": message,
            "citations": citation_dicts,
            "confidence": confidence,
            "confidence_score": confidence_score,
            "domain_detected": domain_detected,
            "query_type": query_type_str,
            "superseded_warnings": superseded_warnings,
            "attribution": attribution,
            "client_name": connection.organization_name or "Unknown",
            "client_id": str(client_id),
        }

    async def _generate_response_stream(
        self,
        query: str,
        client_context: str,
        rag_context: ChatContext,
        conversation_history: list[dict] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Generate streaming response with combined context.

        Args:
            query: The user's question.
            client_context: Formatted client data.
            rag_context: Retrieved knowledge base context.
            conversation_history: Previous messages.

        Yields:
            Text chunks as they are generated.
        """
        # Build messages
        messages = []

        # Add conversation history
        if conversation_history:
            for msg in conversation_history[-6:]:
                messages.append(
                    {
                        "role": msg["role"],
                        "content": msg["content"],
                    }
                )

        # Build user message with both contexts
        user_content = f"""CLIENT DATA:
{client_context}

"""
        if rag_context.chunks:
            user_content += f"""KNOWLEDGE BASE SOURCES:
{rag_context.formatted_context}

"""
        user_content += f"QUESTION: {query}"

        messages.append(
            {
                "role": "user",
                "content": user_content,
            }
        )

        # Stream response
        async with self.base_chatbot.client.messages.stream(
            model=self.settings.model,
            max_tokens=self.settings.max_tokens,
            temperature=self.settings.temperature,
            system=CLIENT_CONTEXT_SYSTEM_PROMPT,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def get_connection_status(
        self,
        client_id: UUID,
    ) -> dict:
        """Get connection status for a client.

        Args:
            client_id: The client ID.

        Returns:
            Dict with connection status info.
        """
        result = await self.db.execute(
            select(XeroClient, XeroConnection)
            .join(XeroConnection, XeroClient.connection_id == XeroConnection.id)
            .where(XeroClient.id == client_id)
        )
        row = result.one_or_none()

        if not row:
            return {"status": "not_found", "message": "Client not found"}

        client, connection = row

        return {
            "status": connection.connection_status.value
            if connection.connection_status
            else "unknown",
            "organization_name": connection.organization_name,
            "last_sync": connection.last_full_sync_at.isoformat()
            if connection.last_full_sync_at
            else None,
            "needs_reauth": connection.connection_status
            and connection.connection_status.value == "needs_reauth",
        }
