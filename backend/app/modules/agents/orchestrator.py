"""Multi-perspective orchestrator for the agents module.

This module implements the core orchestration logic for multi-perspective
analysis using a single LLM call with structured output.
"""

import hashlib
import logging
import re
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any, ClassVar
from uuid import UUID, uuid4

import anthropic
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.modules.agents.a2ui_llm import A2UI_SCHEMA_PROMPT, process_llm_response_for_a2ui
from app.modules.agents.perspective_detector import DetectionResult, PerspectiveDetector
from app.modules.agents.prompts import get_strategy_options_prompt
from app.modules.agents.schemas import (
    OrchestratorResponse,
    Perspective,
    PerspectiveResult,
)
from app.modules.agents.settings import agent_settings
from app.modules.knowledge.context_builder import ClientContext, ContextBuilderService

logger = logging.getLogger(__name__)


def _generate_contextual_thinking_message(
    query: str, stage: str, perspectives: list | None = None
) -> str:
    """Generate a dynamic, contextual thinking message based on the query and stage.

    Args:
        query: The user's question.
        stage: Current processing stage.
        perspectives: Detected perspectives (if available).

    Returns:
        A contextual status message.
    """
    query_lower = query.lower()

    # Extract key terms for more dynamic messages
    key_terms = []
    term_map = {
        "gst": "GST",
        "bas": "BAS",
        "tax": "tax",
        "expense": "expenses",
        "cost": "costs",
        "revenue": "revenue",
        "income": "income",
        "sales": "sales",
        "cash flow": "cash flow",
        "bank": "bank transactions",
        "payment": "payments",
        "payable": "payables",
        "receivable": "receivables",
        "liability": "liabilities",
        "asset": "assets",
        "super": "superannuation",
        "payg": "PAYG",
        "invoice": "invoices",
        "overdue": "overdue items",
        "outstanding": "outstanding amounts",
        "deduction": "deductions",
        "profit": "profit",
        "loss": "losses",
    }

    for term, display in term_map.items():
        if term in query_lower:
            key_terms.append(display)
            if len(key_terms) >= 2:
                break

    if stage == "perspectives":
        # Use extracted key terms for more specific messages
        if key_terms:
            if len(key_terms) == 1:
                return f"Analyzing your {key_terms[0]} question..."
            else:
                return f"Looking at {key_terms[0]} and {key_terms[1]}..."
        # Fallback to broader categories
        if any(word in query_lower for word in ["how", "what", "show", "tell"]):
            return "Understanding what you're looking for..."
        elif any(word in query_lower for word in ["why", "explain", "reason"]):
            return "Preparing to explain..."
        elif any(word in query_lower for word in ["can", "should", "recommend"]):
            return "Analyzing your options..."
        else:
            return "Processing your question..."

    elif stage == "context":
        if key_terms:
            return f"Loading {key_terms[0]} data..."
        # Fallback
        if any(word in query_lower for word in ["gst", "liability", "payable"]):
            return "Loading GST and liability data..."
        elif any(word in query_lower for word in ["expense", "deduction", "cost"]):
            return "Gathering expense records..."
        elif any(word in query_lower for word in ["revenue", "income", "sales", "receivable"]):
            return "Loading revenue and receivables..."
        elif any(word in query_lower for word in ["cash", "flow", "bank"]):
            return "Retrieving cash flow data..."
        else:
            return "Loading client financial data..."

    elif stage == "building" and perspectives:
        # Generate message based on query content AND perspectives
        if key_terms:
            # Combine query context with perspective info
            perspective_names = []
            for p in perspectives:
                if hasattr(p, "value"):
                    perspective_names.append(p.value.title())
                elif hasattr(p, "display_name"):
                    perspective_names.append(p.display_name)
                else:
                    perspective_names.append(str(p).title())

            if len(perspective_names) == 1:
                return f"Analyzing {key_terms[0]} from {perspective_names[0]} view..."
            else:
                return f"Building {' & '.join(perspective_names)} analysis for {key_terms[0]}..."
        else:
            # Just use perspective names
            perspective_names = []
            for p in perspectives:
                if hasattr(p, "value"):
                    perspective_names.append(p.value.title())
                elif hasattr(p, "display_name"):
                    perspective_names.append(p.display_name)
                else:
                    perspective_names.append(str(p).title())

            if len(perspective_names) == 1:
                return f"Building {perspective_names[0]} analysis..."
            elif len(perspective_names) == 2:
                return f"Preparing {perspective_names[0]} and {perspective_names[1]} views..."
            else:
                return "Building multi-perspective analysis..."

    elif stage == "generating":
        if key_terms:
            return f"Generating {key_terms[0]} analysis..."
        # Fallback
        if any(word in query_lower for word in ["gst", "bas", "tax"]):
            return "Calculating tax implications..."
        elif any(word in query_lower for word in ["compare", "trend", "analysis"]):
            return "Running comparative analysis..."
        elif any(word in query_lower for word in ["risk", "issue", "compliance"]):
            return "Checking compliance requirements..."
        elif any(word in query_lower for word in ["recommend", "suggest", "should"]):
            return "Formulating recommendations..."
        else:
            return "Generating your analysis..."

    return "Processing..."


@dataclass
class ParsedPerspectiveSection:
    """A parsed section from the LLM response."""

    perspective: Perspective
    content: str
    start_pos: int
    end_pos: int


class MultiPerspectiveOrchestrator:
    """Orchestrates multi-perspective analysis through a single LLM call.

    This class coordinates:
    1. Perspective detection - which lenses to apply
    2. Context building - gather relevant data for each perspective
    3. Prompt construction - build multi-perspective prompt
    4. LLM invocation - single Claude call
    5. Response parsing - extract attributed sections
    6. Confidence scoring - assess response quality
    7. Escalation checking - flag for human review if needed
    """

    # Perspective order for consistent output
    PERSPECTIVE_ORDER: ClassVar[list[Perspective]] = [
        Perspective.COMPLIANCE,
        Perspective.QUALITY,
        Perspective.STRATEGY,
        Perspective.INSIGHT,
    ]

    def __init__(self, db: AsyncSession):
        """Initialize the orchestrator.

        Args:
            db: Database session for context building.
        """
        self.db = db
        self.detector = PerspectiveDetector()
        self.context_builder = ContextBuilderService(db)

        # Get API key from app config (same as existing chatbot)
        app_settings = get_settings()
        api_key = app_settings.anthropic.api_key.get_secret_value()
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.settings = agent_settings

        # Store last result for streaming endpoint to access after processing
        self.last_result: OrchestratorResponse | None = None

    async def process_query(
        self,
        query: str,
        tenant_id: UUID,  # noqa: ARG002 - reserved for audit logging
        user_id: UUID,  # noqa: ARG002 - reserved for audit logging
        connection_id: UUID | None = None,
        knowledge_chunks: list[dict[str, Any]] | None = None,
        options_format: bool = False,
    ) -> OrchestratorResponse:
        """Process a query through multi-perspective analysis.

        Args:
            query: The user's question.
            tenant_id: The tenant ID for audit logging.
            user_id: The user ID for audit logging.
            connection_id: Optional client connection for client-specific queries.
            knowledge_chunks: Optional pre-fetched knowledge base chunks.
            options_format: If True, force Strategy perspective to output OPTIONS format.
                           Used by Magic Zone insights for strategic decisions.

        Returns:
            OrchestratorResponse with attributed perspective results.
        """
        start_time = time.time()
        correlation_id = uuid4()

        logger.info(
            f"Processing query correlation_id={correlation_id}, "
            f"connection_id={connection_id}, query='{query[:50]}...'"
        )

        # 1. Detect relevant perspectives
        client_context = None
        if connection_id:
            client_context = await self.context_builder.build_context(connection_id, query)

        detection = self.detector.detect(query, client_context)
        perspectives = detection.perspectives

        logger.info(
            f"Detected perspectives: {[p.value for p in perspectives]}, "
            f"confidence={detection.confidence}, reasoning={detection.reasoning}"
        )

        # 2. Build context for all perspectives
        perspective_contexts = {}
        multi_context: dict[str, Any] | None = None
        if connection_id:
            multi_context = await self.context_builder.build_perspective_context(
                connection_id,
                [p.value for p in perspectives],
                query,
            )
            perspective_contexts = multi_context.get("perspectives", {})

        # 3. Construct multi-perspective prompt
        system_prompt = self._build_system_prompt(perspectives, client_context, options_format)
        user_prompt = self._build_user_prompt(
            query,
            perspectives,
            perspective_contexts,
            knowledge_chunks,
            client_context,
        )

        # 4. Make single Claude call
        try:
            response = self.client.messages.create(
                model=self.settings.model,
                max_tokens=self.settings.max_response_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            # Extract text from the first content block
            first_block = response.content[0]
            content = first_block.text if hasattr(first_block, "text") else str(first_block)
            token_usage = response.usage.input_tokens + response.usage.output_tokens
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

        # 5. Parse attributed response
        perspective_results = self._parse_response(content, perspectives)

        # 6. Calculate confidence
        confidence = self._calculate_confidence(
            perspectives=perspectives,
            perspective_results=perspective_results,
            detection=detection,
            knowledge_chunks=knowledge_chunks,
            client_context=client_context,
        )

        # 7. Check escalation
        escalation_required, escalation_reason = self._check_escalation(
            query=query,
            confidence=confidence,
            perspectives=perspectives,
        )

        processing_time_ms = int((time.time() - start_time) * 1000)

        # Build citations from knowledge chunks
        citations = self._build_citations(knowledge_chunks)

        # Process LLM response to extract A2UI components (LLM-driven)
        clean_content, a2ui_message = process_llm_response_for_a2ui(content)

        # Update perspective results to use clean content (without A2UI block)
        if a2ui_message and clean_content != content:
            # Re-parse perspective results from clean content
            content = clean_content

        result = OrchestratorResponse(
            correlation_id=correlation_id,
            content=content,
            perspectives_used=perspectives,
            perspective_results=perspective_results,
            confidence=confidence,
            escalation_required=escalation_required,
            escalation_reason=escalation_reason,
            citations=citations,
            processing_time_ms=processing_time_ms,
            token_usage=token_usage,
            a2ui_message=a2ui_message,
            raw_client_context=client_context,
            raw_perspective_contexts=multi_context if connection_id else None,
        )

        logger.info(
            f"Query processed correlation_id={correlation_id}, "
            f"confidence={confidence:.2f}, escalation={escalation_required}, "
            f"time_ms={processing_time_ms}, tokens={token_usage}"
        )

        return result

    async def process_query_streaming(
        self,
        query: str,
        tenant_id: UUID,  # noqa: ARG002 - reserved for audit logging
        user_id: UUID,  # noqa: ARG002 - reserved for audit logging
        connection_id: UUID | None = None,
        knowledge_chunks: list[dict[str, Any]] | None = None,
        options_format: bool = False,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Process a query with streaming status updates.

        Yields events for each processing stage for real-time UX feedback.

        Args:
            query: The user's question.
            tenant_id: The tenant ID for audit logging.
            user_id: The user ID for audit logging.
            connection_id: Optional client connection for client-specific queries.
            knowledge_chunks: Optional pre-fetched knowledge base chunks.
            options_format: If True, force Strategy perspective to output OPTIONS format.

        Yields:
            Dict events with type and data for each stage.
        """
        start_time = time.time()
        correlation_id = uuid4()

        logger.info(
            f"Processing query (streaming) correlation_id={correlation_id}, "
            f"connection_id={connection_id}, query='{query[:50]}...'"
        )

        # Stage 1: Detect perspectives
        yield {
            "type": "thinking",
            "data": {
                "stage": "perspectives",
                "message": _generate_contextual_thinking_message(query, "perspectives"),
            },
        }

        client_context = None
        if connection_id:
            yield {
                "type": "thinking",
                "data": {
                    "stage": "context",
                    "message": _generate_contextual_thinking_message(query, "context"),
                },
            }
            client_context = await self.context_builder.build_context(connection_id, query)

        detection = self.detector.detect(query, client_context)
        perspectives = detection.perspectives

        # Send detected perspectives
        yield {
            "type": "perspectives",
            "data": {
                "perspectives": [p.value for p in perspectives],
                "message": f"Analyzing from {len(perspectives)} perspective{'s' if len(perspectives) != 1 else ''}...",
            },
        }

        # Stage 2: Build context
        perspective_contexts = {}
        if connection_id and perspectives:
            yield {
                "type": "thinking",
                "data": {
                    "stage": "building",
                    "message": _generate_contextual_thinking_message(
                        query, "building", perspectives
                    ),
                },
            }
            multi_context = await self.context_builder.build_perspective_context(
                connection_id,
                [p.value for p in perspectives],
                query,
            )
            perspective_contexts = multi_context.get("perspectives", {})

        # Stage 3: Generate response
        yield {
            "type": "thinking",
            "data": {
                "stage": "generating",
                "message": _generate_contextual_thinking_message(query, "generating"),
            },
        }

        system_prompt = self._build_system_prompt(perspectives, client_context, options_format)
        user_prompt = self._build_user_prompt(
            query,
            perspectives,
            perspective_contexts,
            knowledge_chunks,
            client_context,
        )

        try:
            response = self.client.messages.create(
                model=self.settings.model,
                max_tokens=self.settings.max_response_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            first_block = response.content[0]
            content = first_block.text if hasattr(first_block, "text") else str(first_block)
            token_usage = response.usage.input_tokens + response.usage.output_tokens
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

        # Parse response
        perspective_results = self._parse_response(content, perspectives)

        # Calculate confidence
        confidence = self._calculate_confidence(
            perspectives=perspectives,
            perspective_results=perspective_results,
            detection=detection,
            knowledge_chunks=knowledge_chunks,
            client_context=client_context,
        )

        # Check escalation
        escalation_required, escalation_reason = self._check_escalation(
            query=query,
            confidence=confidence,
            perspectives=perspectives,
        )

        processing_time_ms = int((time.time() - start_time) * 1000)
        citations = self._build_citations(knowledge_chunks)

        # Process LLM response to extract A2UI components (LLM-driven)
        clean_content, a2ui_message = process_llm_response_for_a2ui(content)

        # Update content to clean version (without A2UI block)
        if a2ui_message and clean_content != content:
            content = clean_content

        # Store result for audit logging
        self.last_result = OrchestratorResponse(
            correlation_id=correlation_id,
            content=content,
            perspectives_used=perspectives,
            perspective_results=perspective_results,
            confidence=confidence,
            escalation_required=escalation_required,
            escalation_reason=escalation_reason,
            citations=citations,
            processing_time_ms=processing_time_ms,
            token_usage=token_usage,
            a2ui_message=a2ui_message,
        )

        # Send response with A2UI components
        yield {
            "type": "response",
            "data": {
                "content": content,
                "perspective_results": [
                    {
                        "perspective": r.perspective.value,
                        "content": r.content,
                    }
                    for r in perspective_results
                ],
                "a2ui_message": a2ui_message.model_dump(by_alias=True) if a2ui_message else None,
            },
        }

        # Extract data freshness from client context
        data_freshness_str = None
        if (
            client_context
            and hasattr(client_context, "data_freshness")
            and client_context.data_freshness
        ):
            df = client_context.data_freshness
            data_freshness_str = df.isoformat() if hasattr(df, "isoformat") else str(df)

        # Send metadata
        yield {
            "type": "metadata",
            "data": {
                "correlation_id": str(correlation_id),
                "perspectives_used": [p.value for p in perspectives],
                "confidence": confidence,
                "escalation_required": escalation_required,
                "escalation_reason": escalation_reason,
                "processing_time_ms": processing_time_ms,
                "citations": citations,
                "a2ui_message": a2ui_message.model_dump(by_alias=True) if a2ui_message else None,
                "data_freshness": data_freshness_str,
            },
        }

        logger.info(
            f"Query processed (streaming) correlation_id={correlation_id}, "
            f"confidence={confidence:.2f}, escalation={escalation_required}, "
            f"time_ms={processing_time_ms}, tokens={token_usage}"
        )

    def _build_system_prompt(
        self,
        perspectives: list[Perspective],
        client_context: ClientContext | None,  # noqa: ARG002 - reserved for future context-aware prompts
        options_format: bool = False,
    ) -> str:
        """Build the system prompt for multi-perspective analysis.

        Args:
            perspectives: The perspectives to analyze from.
            client_context: Optional client context.
            options_format: If True and Strategy is included, use OPTIONS format prompt.

        Returns:
            System prompt string.
        """
        # For Magic Zone insights with options_format, use the specialized OPTIONS prompt
        # when Strategy perspective is included
        if options_format and Perspective.STRATEGY in perspectives:
            # Use the OPTIONS-format prompt for strategic decisions
            options_prompt = get_strategy_options_prompt()

            # Add other perspective descriptions if present
            other_perspectives = [p for p in perspectives if p != Perspective.STRATEGY]
            if other_perspectives:
                other_descs = []
                for p in other_perspectives:
                    desc = self.detector.get_perspective_description(p)
                    other_descs.append(f"- **{p.display_name}**: {desc}")

                return f"""{options_prompt}

## Additional Perspectives to Include

Also analyze from these perspectives where relevant:
{chr(10).join(other_descs)}

Use [Perspective] markers to separate your analysis:
{self._get_perspective_format_example(other_perspectives)}
"""
            return options_prompt

        # Standard multi-perspective prompt
        perspective_descriptions = []
        for p in perspectives:
            desc = self.detector.get_perspective_description(p)
            perspective_descriptions.append(f"- **{p.display_name}**: {desc}")

        return f"""You are an expert Australian accounting advisor providing multi-perspective analysis for accounting practices.

## Your Role
You help accountants understand their clients' situations by analyzing queries from multiple professional perspectives. Each perspective provides a different analytical lens.

## Active Perspectives
{chr(10).join(perspective_descriptions)}

## Response Format
Structure your response with clear perspective sections. Use [Perspective] markers:

{self._get_perspective_format_example(perspectives)}

## Guidelines
1. **Be specific**: Reference actual numbers and dates from the provided context.
2. **Be practical**: Provide actionable insights accountants can use.
3. **Be confident but honest**: If data is missing or uncertain, say so.
4. **Australian focus**: All advice should be relevant to Australian tax law and ATO requirements.
5. **Professional tone**: Write as a peer advisor, not a generic chatbot.

## Important
- Only include perspectives that are relevant to the query.
- If a perspective has nothing meaningful to add, skip it.
- Keep each perspective section focused and concise.
- Cross-reference between perspectives when relevant (e.g., "This data quality issue affects the GST calculation mentioned in Compliance").

{A2UI_SCHEMA_PROMPT}
"""

    def _get_perspective_format_example(self, perspectives: list[Perspective]) -> str:
        """Get format example for the active perspectives."""
        examples = []
        for p in perspectives:
            if p == Perspective.COMPLIANCE:
                examples.append("[Compliance] Based on ATO requirements, [specific analysis]...")
            elif p == Perspective.QUALITY:
                examples.append("[Quality] The data shows [quality observations]...")
            elif p == Perspective.STRATEGY:
                examples.append(
                    "[Strategy] Considering the business situation, [strategic advice]..."
                )
            elif p == Perspective.INSIGHT:
                examples.append("[Insight] Looking at the trends, [analytical observations]...")
        return "\n".join(examples)

    def _build_user_prompt(
        self,
        query: str,
        perspectives: list[Perspective],
        perspective_contexts: dict[str, Any],
        knowledge_chunks: list[dict[str, Any]] | None,
        client_context: ClientContext | None,
    ) -> str:
        """Build the user prompt with context.

        Args:
            query: The user's question.
            perspectives: Active perspectives.
            perspective_contexts: Context data per perspective.
            knowledge_chunks: RAG results.
            client_context: Client profile and summaries.

        Returns:
            User prompt string.
        """
        sections = []

        # Client context section
        if client_context:
            sections.append("## Client Information")
            sections.append(self.context_builder.format_context_for_prompt(client_context))

        # Perspective-specific context
        if perspective_contexts:
            sections.append("\n## Perspective Context")
            for p in perspectives:
                p_name = p.value
                if p_name in perspective_contexts:
                    formatted = self.context_builder.format_perspective_context_for_prompt(
                        perspective_contexts[p_name], p_name
                    )
                    sections.append(formatted)

        # Knowledge base context
        if knowledge_chunks:
            sections.append("\n## Knowledge Base")
            for chunk in knowledge_chunks[:10]:  # Limit chunks
                source = chunk.get("metadata", {}).get("source", "Unknown")
                text = chunk.get("text", "")[:500]  # Truncate
                sections.append(f"[Source: {source}]\n{text}\n")

        # Query section
        sections.append(f"\n## Question\n{query}")

        # Instructions
        perspective_list = ", ".join(p.display_name for p in perspectives)
        sections.append(
            f"\nAnalyze this from: {perspective_list} perspectives. "
            f"Use [Perspective] markers for each section."
        )

        return "\n".join(sections)

    def _parse_response(
        self,
        content: str,
        expected_perspectives: list[Perspective],
    ) -> list[PerspectiveResult]:
        """Parse perspective sections from the LLM response.

        Args:
            content: The raw LLM response.
            expected_perspectives: The perspectives we asked for.

        Returns:
            List of parsed PerspectiveResult objects.
        """
        results = []

        # Pattern to match [Perspective] markers
        pattern = r"\[(\w+)\]\s*(.*?)(?=\[(?:Compliance|Quality|Strategy|Insight)\]|$)"
        matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)

        found_perspectives = set()

        for match in matches:
            perspective_name, section_content = match
            section_content = section_content.strip()

            if not section_content:
                continue

            # Map to Perspective enum
            try:
                perspective = Perspective(perspective_name.lower())
                found_perspectives.add(perspective)

                results.append(
                    PerspectiveResult(
                        perspective=perspective,
                        content=section_content,
                        citations=[],  # Could extract inline citations
                        confidence=0.7,  # Default, could be refined
                    )
                )
            except ValueError:
                logger.warning(f"Unknown perspective in response: {perspective_name}")
                continue

        # If no markers found, treat entire response as single perspective
        if not results and expected_perspectives:
            primary = expected_perspectives[0]
            results.append(
                PerspectiveResult(
                    perspective=primary,
                    content=content,
                    citations=[],
                    confidence=0.5,  # Lower confidence for unparsed response
                )
            )

        # Sort by perspective order
        perspective_order = {p: i for i, p in enumerate(self.PERSPECTIVE_ORDER)}
        results.sort(key=lambda r: perspective_order.get(r.perspective, 99))

        return results

    def _calculate_confidence(
        self,
        perspectives: list[Perspective],
        perspective_results: list[PerspectiveResult],
        detection: DetectionResult,
        knowledge_chunks: list[dict[str, Any]] | None,
        client_context: ClientContext | None,
    ) -> float:
        """Calculate overall confidence score.

        Factors:
        - Perspective detection confidence
        - Response completeness (all perspectives covered)
        - Knowledge base citation quality
        - Client data availability

        Args:
            perspectives: Expected perspectives.
            perspective_results: Actual parsed results.
            detection: Perspective detection result.
            knowledge_chunks: RAG results.
            client_context: Client context.

        Returns:
            Confidence score between 0.0 and 1.0.
        """
        # Start with detection confidence
        base_score = detection.confidence * 0.3  # 30% weight

        # Response completeness (30% weight)
        found_perspectives = {r.perspective for r in perspective_results}
        if perspectives:
            completeness = len(found_perspectives.intersection(perspectives)) / len(perspectives)
        else:
            completeness = 0.5
        base_score += completeness * 0.3

        # Knowledge base quality (20% weight)
        if knowledge_chunks:
            # Score based on chunk quality (similarity scores if available)
            chunk_scores = [c.get("score", 0.5) for c in knowledge_chunks if "score" in c]
            if chunk_scores:
                kb_quality = sum(chunk_scores) / len(chunk_scores)
            else:
                kb_quality = 0.5 if knowledge_chunks else 0.0
        else:
            kb_quality = 0.3  # Penalty for no KB support
        base_score += kb_quality * 0.2

        # Client data availability (20% weight)
        if client_context:
            # Check data freshness (stale data gets penalty)
            data_score = 0.8 if not self.context_builder.is_data_stale(client_context) else 0.5
            # Bonus for complete context
            if client_context.summaries:
                data_score += 0.1
        else:
            data_score = 0.4  # General knowledge query
        base_score += min(1.0, data_score) * 0.2

        return min(1.0, max(0.0, base_score))

    def _check_escalation(
        self,
        query: str,
        confidence: float,
        perspectives: list[Perspective],  # noqa: ARG002 - reserved for perspective-specific escalation rules
    ) -> tuple[bool, str | None]:
        """Check if escalation is required.

        Args:
            query: The original query.
            confidence: Calculated confidence score.
            perspectives: Perspectives used.

        Returns:
            Tuple of (escalation_required, escalation_reason).
        """
        query_lower = query.lower()

        # Check mandatory escalation keywords
        for keyword in self.settings.escalation_keywords:
            if keyword.lower() in query_lower:
                return True, f"Complex scenario detected: {keyword}"

        # Check confidence thresholds
        if confidence < self.settings.confidence_escalation_threshold:
            return True, f"Low confidence ({confidence:.2f}) below escalation threshold"

        if confidence < self.settings.confidence_review_threshold:
            return False, f"Moderate confidence ({confidence:.2f}) - review recommended"

        return False, None

    def _build_citations(
        self,
        knowledge_chunks: list[dict[str, Any]] | None,
    ) -> list[dict[str, Any]]:
        """Build citation list from knowledge chunks.

        Args:
            knowledge_chunks: RAG results.

        Returns:
            List of citation dictionaries.
        """
        if not knowledge_chunks:
            return []

        # Deduplicate by source_url to avoid showing the same document multiple times
        seen_urls: set[str] = set()
        citations = []
        for chunk in knowledge_chunks:
            if len(citations) >= 8:
                break
            metadata = chunk.get("metadata", {})
            url = metadata.get("source_url", "")
            # Skip duplicate URLs (different chunks from the same document)
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            citations.append(
                {
                    "id": f"cite_{len(citations) + 1}",
                    "source": metadata.get("source", "Unknown"),
                    "title": metadata.get("title", ""),
                    "section": metadata.get("section", ""),
                    "url": url,
                    "score": chunk.get("score", 0.0),
                }
            )

        return citations

    @staticmethod
    def hash_query(query: str) -> str:
        """Generate a hash of the query for audit logging.

        We hash the query to avoid storing sensitive content while
        still being able to identify duplicate queries.

        Args:
            query: The query text.

        Returns:
            SHA-256 hash of the query.
        """
        return hashlib.sha256(query.encode()).hexdigest()
