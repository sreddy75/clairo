"""AI Knowledge Chatbot Service.

Provides RAG-based question answering with streaming responses,
numbered citations, and source metadata.

Enhanced with hybrid search pipeline (T020): query routing, query expansion,
BM25+semantic fusion, cross-encoder re-ranking, confidence scoring,
superseded content warnings, and legislation attribution.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass

import anthropic
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import AnthropicSettings
from app.core.pinecone_service import PineconeService
from app.core.voyage import VoyageService
from app.modules.knowledge.collections import COLLECTIONS, INDEX_NAME, get_namespace_with_env

# Import enhanced retrieval components (graceful fallback if not available)
try:
    from app.modules.knowledge.retrieval.hybrid_search import HybridSearchEngine
    from app.modules.knowledge.retrieval.query_expander import QueryExpander
    from app.modules.knowledge.retrieval.query_router import QueryRouter, QueryType
    from app.modules.knowledge.retrieval.reranker import CrossEncoderReranker

    _RETRIEVAL_AVAILABLE = True
except ImportError:
    _RETRIEVAL_AVAILABLE = False

from app.modules.knowledge.retrieval.citation_verifier import CitationVerifier

logger = logging.getLogger(__name__)


@dataclass
class Citation:
    """A citation reference to a knowledge source."""

    number: int
    title: str | None
    url: str
    source_type: str
    effective_date: str | None
    text_preview: str
    score: float


@dataclass
class EnhancedCitation(Citation):
    """A citation with additional verification and section reference metadata.

    Extends the base Citation with fields for section cross-referencing
    and post-generation verification status.
    """

    section_ref: str | None = None
    verified: bool = False


@dataclass
class ChatContext:
    """Context retrieved from the knowledge base for answering a question."""

    chunks: list[dict]
    citations: list[Citation]

    @property
    def formatted_context(self) -> str:
        """Format chunks as numbered context for the LLM prompt."""
        parts = []
        for i, chunk in enumerate(self.chunks, 1):
            title = chunk.get("title", "Untitled")
            text = chunk.get("text", "")
            source_type = chunk.get("source_type", "unknown")
            parts.append(f"[{i}] {title} ({source_type}):\n{text}")
        return "\n\n---\n\n".join(parts)


SYSTEM_PROMPT = """You are Clairo AI, a tax compliance assistant for Australian accountants and bookkeepers.

Your audience is accounting professionals. Be direct, concise, and practical. Skip introductions and filler text - get straight to the answer.

When context documents are provided, use numbered citations [1], [2], etc. Structure complex answers with headings and bullets.

For time-sensitive matters (rates, deadlines), note these may change - verify on ato.gov.au.

This is general information, not professional advice."""

TAX_RESEARCH_SYSTEM_PROMPT = """You are Clairo AI, a tax compliance assistant for Australian accountants.

IMPORTANT GROUNDING RULES:
- Answer ONLY based on the provided SOURCES below
- If the sources don't contain enough information, say so explicitly
- NEVER fabricate section numbers, ruling numbers, or case citations
- Use numbered citations [1], [2] etc. to reference sources
- For time-sensitive matters (rates, deadlines), note these may change

Structure complex answers with headings and bullet points. Be direct and practical."""


class KnowledgeChatbot:
    """AI chatbot with RAG for Australian tax knowledge."""

    def __init__(
        self,
        anthropic_settings: AnthropicSettings,
        pinecone: PineconeService,
        voyage: VoyageService,
    ):
        self.settings = anthropic_settings
        self.pinecone = pinecone
        self.voyage = voyage

        # Initialize Anthropic client
        api_key = anthropic_settings.api_key.get_secret_value()
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for chatbot")
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    async def retrieve_context(
        self,
        query: str,
        collections: list[str] | None = None,
        limit: int = 5,
        score_threshold: float = 0.3,
    ) -> ChatContext:
        """Retrieve relevant context from the knowledge base.

        Args:
            query: The user's question.
            collections: Namespaces to search (defaults to all).
            limit: Maximum number of chunks to retrieve.
            score_threshold: Minimum relevance score.

        Returns:
            ChatContext with retrieved chunks and formatted citations.
        """
        # Default to all namespaces (base names)
        base_namespaces = collections or list(COLLECTIONS.keys())

        # Convert to environment-aware namespace names
        target_namespaces = [get_namespace_with_env(ns) for ns in base_namespaces]

        # Embed the query
        query_vector = await self.voyage.embed_query(query)

        # Search across namespaces
        results = await self.pinecone.search_multi_namespace(
            index_name=INDEX_NAME,
            namespaces=target_namespaces,
            query_vector=query_vector,
            limit_per_namespace=max(2, limit // len(target_namespaces)),
            total_limit=limit,
            score_threshold=score_threshold,
        )

        # Build chunks and citations (deduplicated by source URL)
        chunks = []
        seen_urls: dict[str, int] = {}  # URL -> citation index
        citations = []

        for point in results:
            payload = point.payload or {}
            source_url = payload.get("source_url", "")
            chunk = {
                "text": payload.get("text", ""),
                "title": payload.get("title"),
                "source_url": source_url,
                "source_type": payload.get("source_type", "unknown"),
                "effective_date": payload.get("effective_date"),
                "score": point.score,
            }
            chunks.append(chunk)

            # Only create citation if we haven't seen this URL
            # (keep the first/highest-scored one since results are sorted by score)
            if source_url and source_url not in seen_urls:
                citation_num = len(citations) + 1
                seen_urls[source_url] = citation_num
                text_preview = (
                    chunk["text"][:200] + "..." if len(chunk["text"]) > 200 else chunk["text"]
                )
                citations.append(
                    Citation(
                        number=citation_num,
                        title=chunk["title"],
                        url=source_url,
                        source_type=chunk["source_type"],
                        effective_date=chunk["effective_date"],
                        text_preview=text_preview,
                        score=point.score,
                    )
                )

        return ChatContext(chunks=chunks, citations=citations)

    async def generate_response(
        self,
        query: str,
        context: ChatContext,
        conversation_history: list[dict] | None = None,
    ) -> str:
        """Generate a complete response (non-streaming).

        Args:
            query: The user's question.
            context: Retrieved knowledge context.
            conversation_history: Previous messages for context.

        Returns:
            The complete response text.
        """
        messages = self._build_messages(query, context, conversation_history)

        response = await self.client.messages.create(
            model=self.settings.model,
            max_tokens=self.settings.max_tokens,
            temperature=self.settings.temperature,
            system=SYSTEM_PROMPT,
            messages=messages,
        )

        return response.content[0].text

    async def generate_response_stream(
        self,
        query: str,
        context: ChatContext,
        conversation_history: list[dict] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming response.

        Args:
            query: The user's question.
            context: Retrieved knowledge context.
            conversation_history: Previous messages for context.

        Yields:
            Text chunks as they are generated.
        """
        messages = self._build_messages(query, context, conversation_history)

        async with self.client.messages.stream(
            model=self.settings.model,
            max_tokens=self.settings.max_tokens,
            temperature=self.settings.temperature,
            system=SYSTEM_PROMPT,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    def _build_messages(
        self,
        query: str,
        context: ChatContext,
        conversation_history: list[dict] | None = None,
    ) -> list[dict]:
        """Build the messages array for the Claude API.

        Args:
            query: Current user question.
            context: Retrieved knowledge context.
            conversation_history: Previous conversation messages.

        Returns:
            List of message dictionaries for the API.
        """
        messages = []

        # Add conversation history if provided
        if conversation_history:
            for msg in conversation_history[-6:]:  # Keep last 3 exchanges
                messages.append(
                    {
                        "role": msg["role"],
                        "content": msg["content"],
                    }
                )

        # Build the user message with context
        if context.chunks:
            user_content = f"""SOURCES:
{context.formatted_context}

QUESTION: {query}"""
        else:
            # No RAG results - answer from LLM knowledge
            user_content = query

        messages.append(
            {
                "role": "user",
                "content": user_content,
            }
        )

        return messages

    def _build_retrieval_query(
        self,
        query: str,
        conversation_history: list[dict] | None = None,
    ) -> str:
        """Build a context-aware query for RAG retrieval.

        Best practice: Always include recent conversation context in the retrieval
        query. This ensures follow-up questions retrieve relevant documents even
        when phrased vaguely (e.g., "tell me more", "what about X?").

        The LLM will receive full conversation history separately for response
        generation - this is just for better vector search.
        """
        if not conversation_history:
            return query

        # Extract recent context - last 2 user messages provide good retrieval context
        recent_user_messages = [
            msg["content"] for msg in conversation_history if msg["role"] == "user"
        ][-2:]  # Last 2 user questions

        if not recent_user_messages:
            return query

        # Build expanded query: recent context + current query
        # This helps vector search find relevant docs for follow-ups
        context_parts = []
        for msg in recent_user_messages:
            # Truncate long messages
            truncated = msg[:300] if len(msg) > 300 else msg
            context_parts.append(truncated)

        # Combine: previous context provides topic, current query provides specificity
        expanded_query = " ".join(context_parts) + " " + query

        # Cap total length for embedding
        if len(expanded_query) > 1000:
            expanded_query = expanded_query[:1000]

        return expanded_query

    async def chat(
        self,
        query: str,
        collections: list[str] | None = None,
        conversation_history: list[dict] | None = None,
        stream: bool = True,
    ) -> tuple[AsyncGenerator[str, None] | str, ChatContext]:
        """Main chat interface combining retrieval and generation.

        Args:
            query: The user's question.
            collections: Namespaces to search (defaults to all).
            conversation_history: Previous messages for context.
            stream: Whether to stream the response.

        Returns:
            Tuple of (response generator or string, context with citations).
        """
        # Build retrieval query with conversation context for follow-ups
        retrieval_query = self._build_retrieval_query(query, conversation_history)

        # Retrieve relevant context
        context = await self.retrieve_context(
            query=retrieval_query,
            collections=collections,
            limit=5,
            score_threshold=0.3,
        )

        # Generate response
        if stream:
            response = self.generate_response_stream(query, context, conversation_history)
        else:
            response = await self.generate_response(query, context, conversation_history)

        return response, context

    # =========================================================================
    # Enhanced retrieval and chat methods (Spec 045 - hybrid search pipeline)
    # =========================================================================

    async def retrieve_context_enhanced(
        self,
        query: str,
        domain: str | None = None,
        session: AsyncSession | None = None,
    ) -> ChatContext:
        """Retrieve context using the enhanced hybrid search pipeline.

        When an async database session is provided, uses the full hybrid
        search pipeline: query routing, query expansion, BM25+semantic
        fusion, and cross-encoder re-ranking.  When no session is provided,
        falls back to the original :meth:`retrieve_context` for backward
        compatibility.

        Args:
            query: The user's question.
            domain: Optional tax domain slug (e.g., ``"gst"``) to scope
                retrieval.
            session: Async SQLAlchemy session.  Required for hybrid search
                (BM25 index lookup).  If ``None``, falls back to the
                original Pinecone-only search.

        Returns:
            ChatContext with retrieved chunks and formatted citations.
        """
        if session is None or not _RETRIEVAL_AVAILABLE:
            # Backward-compatible fallback to direct Pinecone search
            return await self.retrieve_context(query=query)

        # Step 1: Classify the query to determine retrieval strategy
        router = QueryRouter()
        classification = router.classify(query, domain)

        # Step 2: Expand query for conceptual/scenario queries
        expanded_queries = [query]
        if classification.query_type in (QueryType.CONCEPTUAL, QueryType.SCENARIO):
            try:
                expander = QueryExpander()
                expanded_queries = await expander.expand_query(query, classification.query_type)
            except Exception:
                logger.warning(
                    "Query expansion failed; using original query",
                    exc_info=True,
                )

        # Step 3: Run hybrid search for each query variant and merge
        engine = HybridSearchEngine(session, self.pinecone, self.voyage)
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
            if existing is None or chunk.score > existing.score:  # type: ignore[union-attr]
                seen[chunk.chunk_id] = chunk
        unique_results = sorted(
            seen.values(),
            key=lambda c: c.score,
            reverse=True,  # type: ignore[union-attr]
        )

        # Step 4: Re-rank the top candidates
        reranker = CrossEncoderReranker()
        reranked = reranker.rerank(query, list(unique_results), top_k=10)  # type: ignore[arg-type]

        # Step 5: Build ChatContext from reranked results
        chunks: list[dict] = []
        citations: list[Citation] = []
        seen_urls: dict[str, int] = {}

        for scored_chunk in reranked:
            payload = scored_chunk.payload or {}
            source_url = payload.get("source_url", "")

            chunk = {
                "text": scored_chunk.text or payload.get("text", ""),
                "title": payload.get("title"),
                "source_url": source_url,
                "source_type": payload.get("source_type", "unknown"),
                "effective_date": payload.get("effective_date"),
                "section_ref": payload.get("section_ref"),
                "ruling_number": payload.get("ruling_number"),
                "is_superseded": payload.get("is_superseded", False),
                "superseded_by": payload.get("superseded_by"),
                "score": scored_chunk.score,
            }
            chunks.append(chunk)

            # Deduplicate citations by source URL
            if source_url and source_url not in seen_urls:
                citation_num = len(citations) + 1
                seen_urls[source_url] = citation_num
                text_preview = (
                    chunk["text"][:200] + "..." if len(chunk["text"]) > 200 else chunk["text"]
                )
                citations.append(
                    EnhancedCitation(
                        number=citation_num,
                        title=chunk["title"],
                        url=source_url,
                        source_type=chunk["source_type"],
                        effective_date=chunk["effective_date"],
                        text_preview=text_preview,
                        score=scored_chunk.score,
                        section_ref=chunk.get("section_ref"),
                        verified=False,  # Verification done post-generation
                    )
                )

        return ChatContext(chunks=chunks, citations=citations)

    def compute_confidence(
        self,
        top_score: float,
        mean_top5: float,
        citation_verified_rate: float,
    ) -> tuple[str, float]:
        """Compute confidence tier and score.

        The confidence score is a weighted combination of three signals:
        - Top retrieval score (40%): how relevant is the best match
        - Mean of top 5 scores (30%): overall retrieval quality
        - Citation verification rate (30%): how many citations are grounded

        Args:
            top_score: Highest retrieval relevance score.
            mean_top5: Mean score of the top 5 retrieved chunks.
            citation_verified_rate: Fraction of citations verified against
                the retrieved context (0.0 to 1.0).

        Returns:
            Tuple of ``(tier, score)`` where *tier* is ``"high"``,
            ``"medium"``, or ``"low"``.
        """
        score = 0.4 * top_score + 0.3 * mean_top5 + 0.3 * citation_verified_rate
        if score > 0.7:
            return "high", score
        elif score > 0.5:
            return "medium", score
        return "low", score

    def get_superseded_warnings(self, chunks: list[dict]) -> list[str]:
        """Check retrieved chunks for superseded content.

        Scans the chunk list for entries where ``is_superseded`` is truthy
        and builds human-readable warning messages that identify the
        superseded source and its replacement (if known).

        Args:
            chunks: List of chunk dicts from retrieval context.

        Returns:
            List of warning message strings (empty if nothing is superseded).
        """
        warnings: list[str] = []
        for chunk in chunks:
            if chunk.get("is_superseded"):
                superseded_by = chunk.get("superseded_by", "unknown")
                title = chunk.get("title", "content")
                warnings.append(f"{title} has been superseded by {superseded_by}")
        return warnings

    @staticmethod
    def get_attribution_text(has_legislation: bool) -> str:
        """Get required attribution text for the response.

        Australian legislation content sourced from the Federal Register of
        Legislation requires attribution.  All responses include a general
        professional-advice disclaimer.

        Args:
            has_legislation: Whether the response references legislation
                from the Federal Register of Legislation.

        Returns:
            Attribution and disclaimer string.
        """
        parts = ["This is general information, not professional advice."]
        if has_legislation:
            parts.append(
                "Based on content from the Federal Register of Legislation. "
                "For the latest information on Australian Government legislation "
                "please go to https://www.legislation.gov.au"
            )
        return " ".join(parts)

    async def chat_enhanced(
        self,
        query: str,
        domain: str | None = None,
        session: AsyncSession | None = None,
        conversation_history: list[dict] | None = None,
    ) -> dict:
        """Enhanced chat with hybrid search, confidence, and attribution.

        Combines the enhanced hybrid retrieval pipeline with LLM generation,
        confidence scoring, superseded-content warnings, and legislation
        attribution.  Returns a dict matching the ``KnowledgeChatResponse``
        schema.

        Args:
            query: The user's question.
            domain: Optional tax domain slug to scope retrieval.
            session: Async SQLAlchemy session for hybrid search.
            conversation_history: Previous messages for multi-turn context.

        Returns:
            Dict with keys: ``message``, ``citations``, ``confidence``,
            ``confidence_score``, ``domain_detected``, ``query_type``,
            ``superseded_warnings``, ``attribution``.
        """
        # Classify the query to capture metadata for the response
        query_type_str = "conceptual"
        domain_detected: str | None = None

        if _RETRIEVAL_AVAILABLE:
            router = QueryRouter()
            classification = router.classify(query, domain)
            query_type_str = classification.query_type.value
            domain_detected = classification.domain_detected

        # Retrieve context via enhanced pipeline
        context = await self.retrieve_context_enhanced(
            query=query,
            domain=domain,
            session=session,
        )

        # Generate non-streaming response using the tax research system prompt
        messages = self._build_messages(query, context, conversation_history)

        response = await self.client.messages.create(
            model=self.settings.model,
            max_tokens=self.settings.max_tokens,
            temperature=self.settings.temperature,
            system=TAX_RESEARCH_SYSTEM_PROMPT,
            messages=messages,
        )

        message = response.content[0].text

        # Post-generation citation verification (T025)
        verifier = CitationVerifier()
        verification_result = verifier.verify_citations(
            response_text=message,
            retrieved_chunks=context.chunks,
        )

        # Compute confidence from retrieval scores + verification rate
        scores = [c.get("score", 0.0) for c in context.chunks if c.get("score")]
        top_score = scores[0] if scores else 0.0
        mean_top5 = sum(scores[:5]) / min(len(scores), 5) if scores else 0.0
        citation_verified_rate = verification_result.verification_rate
        confidence, confidence_score = self.compute_confidence(
            top_score, mean_top5, citation_verified_rate
        )

        # If confidence is low (score < 0.5), replace response with a
        # decline message to avoid presenting poorly-grounded answers.
        if confidence == "low":
            logger.warning(
                "Low confidence response (%.2f) — declining to answer. "
                "Verification rate: %.2f, ungrounded: %d",
                confidence_score,
                citation_verified_rate,
                verification_result.ungrounded_count,
            )
            message = (
                "I don't have enough reliable information to answer this "
                "question confidently. Please try rephrasing your question, "
                "or consult the ATO website (ato.gov.au) for authoritative "
                "guidance."
            )

        # Superseded content warnings
        superseded_warnings = self.get_superseded_warnings(context.chunks)

        # Attribution text (check if any chunk is legislation)
        has_legislation = any(
            c.get("source_type") in ("legislation", "act", "federal_register")
            for c in context.chunks
        )
        attribution = self.get_attribution_text(has_legislation)

        # Build citation dicts for the response.
        # Start with the base citations from retrieval, then update
        # verified status from the verification result.
        citation_dicts = []
        verified_map: dict[int, bool] = {
            vc["number"]: vc["verified"]
            for vc in verification_result.citations
            if vc.get("number") is not None
        }

        for cit in context.citations:
            cit_dict = {
                "number": cit.number,
                "title": cit.title,
                "url": cit.url,
                "source_type": cit.source_type,
                "effective_date": cit.effective_date,
                "text_preview": cit.text_preview,
                "score": cit.score,
                "verified": verified_map.get(cit.number, getattr(cit, "verified", False)),
                "section_ref": getattr(cit, "section_ref", None),
            }
            citation_dicts.append(cit_dict)

        return {
            "message": message,
            "citations": citation_dicts,
            "confidence": confidence,
            "confidence_score": confidence_score,
            "domain_detected": domain_detected,
            "query_type": query_type_str,
            "superseded_warnings": superseded_warnings,
            "attribution": attribution,
            "verification_rate": citation_verified_rate,
            "ungrounded_citations": verification_result.ungrounded_count,
        }
