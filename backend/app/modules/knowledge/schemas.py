"""Pydantic schemas for knowledge base module.

Provides request/response schemas for:
- Knowledge source management
- Content chunk metadata
- Ingestion job tracking
- Search operations
"""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# Knowledge Source Schemas
# =============================================================================


class KnowledgeSourceBase(BaseModel):
    """Base schema for knowledge source."""

    name: str = Field(..., max_length=100, description="Human-readable source name")
    source_type: str = Field(
        ...,
        max_length=50,
        description="Source type: ato_rss, ato_web, austlii, business_gov, fair_work",
    )
    base_url: str = Field(..., max_length=500, description="Base URL for the source")
    collection_name: str = Field(
        ...,
        max_length=100,
        description="Target Qdrant collection name",
    )
    scrape_config: dict[str, Any] = Field(
        default_factory=dict,
        description="Source-specific configuration",
    )
    is_active: bool = Field(default=True, description="Whether source is active")


class KnowledgeSourceCreate(KnowledgeSourceBase):
    """Schema for creating a knowledge source."""

    pass


class KnowledgeSourceUpdate(BaseModel):
    """Schema for updating a knowledge source."""

    name: str | None = Field(None, max_length=100)
    scrape_config: dict[str, Any] | None = None
    is_active: bool | None = None


class KnowledgeSourceResponse(KnowledgeSourceBase):
    """Schema for knowledge source response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    last_scraped_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


# =============================================================================
# Content Chunk Schemas
# =============================================================================


class ChunkPayload(BaseModel):
    """Qdrant point payload structure.

    This schema defines the metadata stored with each vector in Qdrant.
    """

    # Identification
    chunk_id: str = Field(..., description="UUID as string")
    source_id: str = Field(..., description="KnowledgeSource UUID as string")
    source_url: str = Field(..., description="Original content URL")
    title: str | None = Field(None, description="Document/page title")

    # Content
    text: str = Field(..., description="Original chunk text for display")
    chunk_index: int = Field(..., ge=0, description="Position in source document")

    # Classification
    source_type: str = Field(..., description="ato_ruling, ato_guide, legislation, business_guide")
    collection_namespace: str = Field(
        ..., description="Namespace within collection (e.g., gst, income_tax)"
    )

    # Applicability filters
    entity_types: list[str] = Field(
        default_factory=list,
        description="Applicable entity types: sole_trader, company, trust, partnership",
    )
    industries: list[str] = Field(
        default_factory=list,
        description="Applicable industries (ANZSIC codes or labels)",
    )
    revenue_brackets: list[str] = Field(
        default_factory=list,
        description="Applicable revenue brackets: under_75k, 75k_to_500k, 500k_to_2m, over_2m",
    )

    # Temporal
    effective_date: str | None = Field(None, description="ISO date when rule became effective")
    expiry_date: str | None = Field(None, description="ISO date when rule expires")
    scraped_at: str = Field(..., description="ISO datetime when content was scraped")

    # Rulings specific
    ruling_number: str | None = Field(
        None, description="Ruling reference: TR 2024/1, GSTR 2024/1, etc."
    )
    is_superseded: bool = Field(default=False, description="Whether content is superseded")

    # Quality
    confidence_level: str = Field(
        default="medium", description="Content confidence: high, medium, low"
    )


class ContentChunkResponse(BaseModel):
    """Schema for content chunk response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_id: UUID
    qdrant_point_id: str
    collection_name: str
    source_url: str
    title: str | None
    source_type: str
    effective_date: date | None
    expiry_date: date | None
    entity_types: list[str]
    industries: list[str]
    ruling_number: str | None
    is_superseded: bool
    created_at: datetime
    updated_at: datetime


# =============================================================================
# Ingestion Job Schemas
# =============================================================================


class IngestionJobCreate(BaseModel):
    """Schema for creating an ingestion job."""

    source_id: UUID
    triggered_by: str = Field(default="manual", max_length=50)


class IngestionJobResponse(BaseModel):
    """Schema for ingestion job response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_id: UUID
    source_name: str | None = None  # Populated from related KnowledgeSource
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    items_processed: int
    items_added: int
    items_updated: int
    items_skipped: int
    items_failed: int
    tokens_used: int
    errors: list[dict[str, Any]]
    triggered_by: str
    created_at: datetime

    # Computed fields
    duration_seconds: float | None = None
    success_rate: float = 0.0


class IngestionJobSummary(BaseModel):
    """Summary schema for job listing."""

    id: UUID
    source_id: UUID
    source_name: str
    status: str
    started_at: datetime | None
    items_processed: int
    items_added: int
    created_at: datetime


# =============================================================================
# Search Schemas
# =============================================================================


class SearchFilters(BaseModel):
    """Filters for knowledge search."""

    entity_types: list[str] | None = Field(None, description="Filter by entity type")
    industries: list[str] | None = Field(None, description="Filter by industry")
    source_types: list[str] | None = Field(None, description="Filter by source type")
    effective_after: date | None = Field(None, description="Only content effective after this date")
    exclude_superseded: bool = Field(default=True, description="Exclude superseded content")


class SearchRequest(BaseModel):
    """Request schema for knowledge search."""

    query: str = Field(..., min_length=1, max_length=1000, description="Search query")
    collections: list[str] | None = Field(
        None,
        description="Collections to search (default: all)",
    )
    filters: SearchFilters | None = Field(None, description="Optional metadata filters")
    limit: int = Field(default=10, ge=1, le=50, description="Max results to return")
    score_threshold: float | None = Field(
        None, ge=0.0, le=1.0, description="Minimum similarity score"
    )


class SearchResult(BaseModel):
    """Single search result."""

    chunk_id: str
    collection: str
    score: float = Field(..., description="Similarity score (0-1)")
    text: str = Field(..., description="Chunk text content")
    source_url: str
    title: str | None
    source_type: str
    ruling_number: str | None = None
    effective_date: str | None = None
    entity_types: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    """Response schema for knowledge search."""

    query: str
    results: list[SearchResult]
    total_results: int
    collections_searched: list[str]
    latency_ms: float


# =============================================================================
# Source Content Schemas
# =============================================================================


class SourceChunkContent(BaseModel):
    """Content of a single chunk from Pinecone."""

    chunk_id: str
    text: str = Field(..., description="Full chunk text content")
    title: str | None = None
    source_url: str | None = None
    source_type: str | None = None
    chunk_index: int | None = None


class SourceContentResponse(BaseModel):
    """Response for source content viewing."""

    source_id: str
    source_name: str
    collection: str
    total_chunks: int
    chunks: list[SourceChunkContent]


# =============================================================================
# Manual Content Upload Schemas
# =============================================================================


class ManualContentUpload(BaseModel):
    """Schema for manually adding text content to a source."""

    title: str = Field(..., min_length=1, max_length=500, description="Title of the content")
    text: str = Field(..., min_length=10, description="The text content to add")
    source_url: str | None = Field(None, max_length=500, description="Optional source URL")


class ManualContentUploadResponse(BaseModel):
    """Response for manual content upload."""

    source_id: str
    chunks_created: int
    message: str


class FileUploadResponse(BaseModel):
    """Response for file upload."""

    source_id: str
    filename: str
    document_type: str
    page_count: int
    word_count: int
    chunks_created: int
    message: str


# =============================================================================
# Collection Schemas
# =============================================================================


class CollectionInfo(BaseModel):
    """Information about a Qdrant collection."""

    name: str
    description: str
    exists: bool
    vectors_count: int = 0
    status: str | None = None
    config: dict[str, Any] | None = None
    source_type_counts: dict[str, int] | None = None


class CollectionInitResponse(BaseModel):
    """Response for collection initialization."""

    collections: dict[str, bool] = Field(
        ..., description="Map of collection name to created (True) or existed (False)"
    )
    message: str


# =============================================================================
# Spec 045: Tax Knowledge Base Schemas
# =============================================================================


class TaxDomainSchema(BaseModel):
    """Schema for a specialist tax domain."""

    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str
    description: str
    topic_tags: list[str] = Field(default_factory=list)
    legislation_refs: list[str] = Field(default_factory=list)
    ruling_types: list[str] = Field(default_factory=list)
    icon: str | None = None
    display_order: int = 0
    is_active: bool = True


class TaxDomainListResponse(BaseModel):
    """Response for listing tax domains."""

    data: list[TaxDomainSchema]


class TaxDomainResponse(BaseModel):
    """Response for a single tax domain."""

    data: TaxDomainSchema


class KnowledgeSearchFilters(BaseModel):
    """Filters for knowledge search (spec 045)."""

    entity_types: list[str] | None = Field(None, description="Filter by entity type")
    source_types: list[str] | None = Field(None, description="Filter by source type")
    fy_applicable: str | None = Field(None, description="Financial year filter e.g. '2026'")
    exclude_superseded: bool = Field(default=True, description="Exclude superseded content")


class KnowledgeSearchRequest(BaseModel):
    """Request for knowledge base search with hybrid retrieval."""

    query: str = Field(..., min_length=1, max_length=2000)
    domain: str | None = Field(None, description="Optional domain slug to scope search")
    filters: KnowledgeSearchFilters | None = None
    limit: int = Field(default=10, ge=1, le=50)


class KnowledgeSearchResultSchema(BaseModel):
    """Single result from knowledge search."""

    chunk_id: str
    title: str | None = None
    text: str
    source_url: str | None = None
    source_type: str
    section_ref: str | None = None
    ruling_number: str | None = None
    effective_date: str | None = None
    is_superseded: bool = False
    relevance_score: float
    content_type: str | None = None


class KnowledgeSearchResponse(BaseModel):
    """Response for knowledge search."""

    data: dict  # Contains results, query_type, domain_detected, total_results


class LegislationSectionDetail(BaseModel):
    """Detail for a legislation section lookup."""

    section_ref: str
    act_name: str
    act_short_name: str
    heading: str | None = None
    text: str
    part: str | None = None
    division: str | None = None
    subdivision: str | None = None
    compilation_date: str
    cross_references: list[str] = Field(default_factory=list)
    defined_terms: list[str] = Field(default_factory=list)
    related_rulings: list[dict] = Field(default_factory=list)


class LegislationSectionResponse(BaseModel):
    """Response for legislation section lookup."""

    data: LegislationSectionDetail


class KnowledgeChatRequest(BaseModel):
    """Request for knowledge chat (extended with domain scoping)."""

    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: UUID | None = None
    domain: str | None = Field(None, description="Optional domain slug for scoped retrieval")
    client_id: UUID | None = Field(None, description="Optional client for contextual answers")


class EnhancedCitationSchema(BaseModel):
    """Citation with verification status."""

    number: int
    title: str | None = None
    url: str | None = None
    source_type: str
    section_ref: str | None = None
    effective_date: str | None = None
    text_preview: str
    score: float
    verified: bool = False


class KnowledgeChatResponse(BaseModel):
    """Response for knowledge chat with citations and confidence."""

    data: dict  # Contains message, citations, confidence, confidence_score, etc.


class LegislationIngestRequest(BaseModel):
    """Request to trigger legislation ingestion."""

    acts: list[str] | None = Field(
        None, description="Act IDs to ingest. Empty = all configured acts."
    )
    force_refresh: bool = Field(
        default=False, description="Re-ingest even if content hash unchanged"
    )
    dev_mode: bool = Field(default=False, description="Ingest a small subset for testing")


class CaseLawIngestRequest(BaseModel):
    """Request to trigger case law ingestion."""

    source: str = Field(default="both", description="open_legal_corpus, federal_court_rss, or both")
    filter_tax_only: bool = Field(default=True)
    dev_mode: bool = Field(default=False, description="Ingest a small subset for testing")


class AdminIngestionJobResponse(BaseModel):
    """Response for admin ingestion trigger."""

    data: dict  # Contains job_id, source_type, status, message


class FreshnessSourceReport(BaseModel):
    """Freshness info for a single source."""

    source_type: str
    source_name: str
    last_ingested_at: datetime | None = None
    chunk_count: int = 0
    error_count: int = 0
    freshness_status: str  # "fresh", "stale", "error", "never_ingested"


class FreshnessReportResponse(BaseModel):
    """Response for content freshness report."""

    data: dict  # Contains sources array, total_chunks, last_updated


class CitationAuditRequest(BaseModel):
    """Request to run citation verification audit."""

    sample_size: int = Field(default=100, description="Number of recent responses to audit")


class CitationAuditResponse(BaseModel):
    """Response for citation audit."""

    data: dict  # Contains total_audited, citations_checked, verification_rate, etc.


# =============================================================================
# Collection Content Browsing Schemas
# =============================================================================


class CollectionContentItem(BaseModel):
    """Single content chunk item for collection browsing."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str | None = None
    source_url: str
    source_type: str
    natural_key: str | None = None
    content_type: str | None = None
    section_ref: str | None = None
    created_at: datetime


class CollectionContentResponse(BaseModel):
    """Paginated response for browsing content in a collection."""

    items: list[CollectionContentItem]
    total: int
    page: int
    page_size: int
    total_pages: int
    source_type_counts: dict[str, int]


# =============================================================================
# Chatbot Schemas
# =============================================================================


class ChatMessage(BaseModel):
    """A single message in the conversation."""

    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    """Request schema for chatbot."""

    query: str = Field(..., min_length=1, max_length=2000, description="User's question")
    collections: list[str] | None = Field(None, description="Collections to search (default: all)")
    conversation_history: list[ChatMessage] | None = Field(
        None, description="Previous messages for context"
    )


class CitationResponse(BaseModel):
    """Citation reference in chat response."""

    number: int = Field(..., description="Citation number [1], [2], etc.")
    title: str | None = Field(None, description="Document/page title")
    url: str = Field(..., description="Source URL")
    source_type: str = Field(..., description="Type of source (e.g., ato_web)")
    effective_date: str | None = Field(None, description="When content became effective")
    text_preview: str = Field(..., description="Preview of cited text")
    score: float = Field(..., description="Relevance score (0-1)")


class ChatResponse(BaseModel):
    """Non-streaming chat response."""

    response: str = Field(..., description="Complete response text")
    citations: list[CitationResponse] = Field(default_factory=list, description="Source citations")
    query: str = Field(..., description="Original query")


class ChatStreamMetadata(BaseModel):
    """Metadata sent at end of streaming response."""

    citations: list[CitationResponse] = Field(default_factory=list, description="Source citations")
    query: str = Field(..., description="Original query")
    done: bool = Field(default=True, description="Stream completion flag")


# =============================================================================
# Conversation Persistence Schemas
# =============================================================================


class ConversationCreate(BaseModel):
    """Request to create a new conversation."""

    title: str | None = Field(None, max_length=200, description="Optional title")


class ConversationUpdate(BaseModel):
    """Request to update a conversation."""

    title: str = Field(..., max_length=200, description="New title")


class ConversationMessageResponse(BaseModel):
    """A message in a conversation response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: str
    content: str
    citations: list[dict] | None = None
    created_at: datetime


class ConversationResponse(BaseModel):
    """Response for a conversation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[ConversationMessageResponse] = Field(default_factory=list)


class ConversationListItem(BaseModel):
    """Item in conversation list (without messages)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    last_message_preview: str | None = None
    client_id: UUID | None = None
    client_name: str | None = None


class ConversationClientSummary(BaseModel):
    """Summary of a client with conversation count for filter pills."""

    client_id: UUID
    client_name: str
    conversation_count: int


class ConversationsWithClientsResponse(BaseModel):
    """Response with conversations and client filter options."""

    conversations: list[ConversationListItem]
    clients: list[ConversationClientSummary]
    total_conversations: int
    general_count: int


class ChatRequestWithConversation(BaseModel):
    """Chat request that can reference a conversation."""

    query: str = Field(..., min_length=1, max_length=2000, description="User's question")
    conversation_id: UUID | None = Field(
        None, description="Existing conversation ID (creates new if not provided)"
    )
    collections: list[str] | None = Field(None, description="Collections to search (default: all)")
