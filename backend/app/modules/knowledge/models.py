"""SQLAlchemy models for knowledge base tracking.

These models track content sources, ingested chunks, ingestion jobs,
and AI assistant conversations in PostgreSQL.
The actual vector content is stored in Pinecone.

Models:
- KnowledgeSource: Configured content sources for ingestion
- ContentChunk: Tracks individual chunks stored in Pinecone
- IngestionJob: Tracks ingestion pipeline runs
- LegislationSection: Tracks ingested legislation sections for cross-referencing (Spec 045)
- ContentCrossReference: Links between content chunks for graph traversal (Spec 045)
- TaxDomain: Specialist tax domain configuration for scoped retrieval (Spec 045)
- BM25IndexEntry: Lightweight BM25 keyword index for hybrid search (Spec 045)
- ScraperCircuitBreakerState: Per-source-host circuit breaker state (Spec 045)
- ChatConversation: User chat conversations with AI assistant
- ChatMessage: Individual messages in a conversation
"""

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import ARRAY, Date, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class KnowledgeSource(Base):
    """Configured content sources for knowledge base ingestion.

    Represents a source of content like ATO RSS feeds, ATO website pages,
    or AustLII legislation. Contains configuration for scraping and tracking
    of last successful scrape.
    """

    __tablename__ = "knowledge_sources"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Source identification
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # source_type values: ato_rss, ato_web, austlii, business_gov, fair_work

    # Configuration
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    collection_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Target Qdrant collection (e.g., compliance_knowledge)

    scrape_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Configuration specific to source type:
    # - ato_rss: feed_urls, categories
    # - ato_web: selectors, rate_limit
    # - austlii: acts, sections

    # Status
    is_active: Mapped[bool] = mapped_column(default=True)
    last_scraped_at: Mapped[datetime | None] = mapped_column(default=None)
    last_error: Mapped[str | None] = mapped_column(Text, default=None)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    # Relationships
    chunks: Mapped[list["ContentChunk"]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
    )
    jobs: Mapped[list["IngestionJob"]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<KnowledgeSource {self.name} ({self.source_type})>"


class ContentChunk(Base):
    """Tracks individual content chunks stored in Qdrant.

    Each chunk represents a piece of content that has been processed,
    embedded, and stored in Qdrant. This model provides the link between
    PostgreSQL metadata and Qdrant vectors.

    The content_hash is used for deduplication - if the same content is
    encountered again during scraping, we can skip re-embedding.
    """

    __tablename__ = "content_chunks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Qdrant linkage
    source_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_sources.id", ondelete="CASCADE"))
    qdrant_point_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    collection_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Deduplication
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    # SHA-256 hash of chunk text for detecting duplicates

    # Content metadata (mirrors Qdrant payload for queryability)
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500))
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # source_type: ato_ruling, ato_guide, legislation, business_guide

    # Temporal metadata
    effective_date: Mapped[date | None] = mapped_column()
    expiry_date: Mapped[date | None] = mapped_column()

    # Classification metadata (stored as arrays for flexibility)
    entity_types: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)), default=list, server_default="{}"
    )
    # Values: sole_trader, company, trust, partnership

    industries: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)), default=list, server_default="{}"
    )
    # Values: construction, retail, hospitality, professional_services, etc.

    # Ruling-specific
    ruling_number: Mapped[str | None] = mapped_column(String(50), index=True)
    # Format: TR 2024/1, GSTR 2024/1, TD 2024/1, PCG 2024/1

    # Status
    is_superseded: Mapped[bool] = mapped_column(default=False)
    superseded_by: Mapped[str | None] = mapped_column(String(50))
    # Reference to new ruling number if superseded

    # === Spec 045: Tax Knowledge Base extensions ===
    content_type: Mapped[str | None] = mapped_column(String(50))
    # "operative_provision", "definition", "example", "headnote", "reasoning", "ruling", "explanation"
    section_ref: Mapped[str | None] = mapped_column(String(100))
    # "s104-10 ITAA 1997", "TR 2024/1 para 15"
    cross_references: Mapped[list | None] = mapped_column(JSONB)
    defined_terms_used: Mapped[list | None] = mapped_column(JSONB)
    topic_tags: Mapped[list | None] = mapped_column(JSONB)
    fy_applicable: Mapped[list | None] = mapped_column(JSONB)
    court: Mapped[str | None] = mapped_column(String(20))
    # "HCA", "FCA", "FCAFC", "AATA"
    case_citation: Mapped[str | None] = mapped_column(String(100))
    legislation_section_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("legislation_sections.id", ondelete="SET NULL")
    )
    document_hash: Mapped[str | None] = mapped_column(String(64))
    # SHA-256 of FULL source document for change detection
    natural_key: Mapped[str | None] = mapped_column(String(200))
    # Idempotency key: "legislation:s109D-ITAA1936", "ruling:TR2024-1"

    # === Spec 060: Tax strategies linkage ===
    # Nullable — existing rows stay NULL; populated only for tax_strategy chunks.
    tax_strategy_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tax_strategies.id", ondelete="CASCADE"), index=True
    )
    chunk_section: Mapped[str | None] = mapped_column(String(32))
    # "implementation" | "explanation" | "header" (Phase 1 uses first two only)
    context_header: Mapped[str | None] = mapped_column(String(300))
    # Prefix prepended to chunk text; stored for debuggability.

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    # Relationships
    source: Mapped["KnowledgeSource"] = relationship(back_populates="chunks")
    legislation_section: Mapped["LegislationSection | None"] = relationship(
        back_populates="chunks", foreign_keys=[legislation_section_id]
    )

    # Indexes for common queries
    __table_args__ = (
        Index("ix_content_chunks_source_collection", "source_id", "collection_name"),
        Index("ix_content_chunks_effective_date", "effective_date"),
        Index("ix_content_chunks_section_ref", "section_ref"),
        Index("ix_content_chunks_content_type", "content_type"),
        Index("ix_content_chunks_document_hash", "document_hash"),
        Index("ix_content_chunks_natural_key", "natural_key"),
    )

    def __repr__(self) -> str:
        return f"<ContentChunk {self.qdrant_point_id[:8]}... ({self.source_type})>"


class IngestionJob(Base):
    """Tracks content ingestion pipeline runs.

    Each job represents a single run of the ingestion pipeline for a
    knowledge source. Tracks progress, statistics, and any errors.
    """

    __tablename__ = "ingestion_jobs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Job identification
    source_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_sources.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    # Status values: pending, running, completed, failed, cancelled

    # Timing
    started_at: Mapped[datetime | None] = mapped_column()
    completed_at: Mapped[datetime | None] = mapped_column()

    # Statistics
    items_processed: Mapped[int] = mapped_column(default=0)
    items_added: Mapped[int] = mapped_column(default=0)
    items_updated: Mapped[int] = mapped_column(default=0)
    items_skipped: Mapped[int] = mapped_column(default=0)
    # Skipped = already exists with same hash

    items_failed: Mapped[int] = mapped_column(default=0)
    tokens_used: Mapped[int] = mapped_column(default=0)
    # Estimated embedding tokens consumed

    # Error tracking
    errors: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    # List of error dicts: {url, error, timestamp}

    # Trigger info
    triggered_by: Mapped[str] = mapped_column(String(50), default="manual")
    # Values: manual, scheduled, webhook

    # === Spec 045: Checkpoint/resume support ===
    completed_items: Mapped[list | None] = mapped_column(JSONB, default=list)
    failed_items: Mapped[list | None] = mapped_column(JSONB, default=list)
    total_items: Mapped[int | None] = mapped_column()
    is_resumable: Mapped[bool] = mapped_column(default=True)
    parent_job_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ingestion_jobs.id", ondelete="SET NULL")
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    source: Mapped["KnowledgeSource"] = relationship(back_populates="jobs")

    # Indexes
    __table_args__ = (
        Index("ix_ingestion_jobs_source_status", "source_id", "status"),
        Index("ix_ingestion_jobs_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<IngestionJob {self.id} ({self.status})>"

    @property
    def duration_seconds(self) -> float | None:
        """Calculate job duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.items_processed == 0:
            return 0.0
        successful = self.items_added + self.items_updated + self.items_skipped
        return (successful / self.items_processed) * 100


class LegislationSection(Base):
    """Tracks ingested legislation sections for cross-referencing."""

    __tablename__ = "legislation_sections"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    act_id: Mapped[str] = mapped_column(String(20), nullable=False)
    act_name: Mapped[str] = mapped_column(String(255), nullable=False)
    act_short_name: Mapped[str] = mapped_column(String(50), nullable=False)
    section_ref: Mapped[str] = mapped_column(String(50), nullable=False)
    part: Mapped[str | None] = mapped_column(String(20))
    division: Mapped[str | None] = mapped_column(String(20))
    subdivision: Mapped[str | None] = mapped_column(String(20))
    heading: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    compilation_date: Mapped[date] = mapped_column(Date, nullable=False)
    compilation_number: Mapped[str | None] = mapped_column(String(20))
    cross_references: Mapped[list] = mapped_column(JSONB, default=list)
    defined_terms: Mapped[list] = mapped_column(JSONB, default=list)
    topic_tags: Mapped[list] = mapped_column(JSONB, default=list)
    is_current: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    # Relationships
    chunks: Mapped[list["ContentChunk"]] = relationship(
        back_populates="legislation_section",
        foreign_keys="ContentChunk.legislation_section_id",
    )

    __table_args__ = (
        UniqueConstraint(
            "act_id",
            "section_ref",
            "compilation_date",
            name="uq_legislation_section",
        ),
        Index("ix_legislation_sections_act", "act_id"),
        Index("ix_legislation_sections_ref", "section_ref"),
    )

    def __repr__(self) -> str:
        return f"<LegislationSection {self.section_ref} ({self.act_short_name})>"


class ContentCrossReference(Base):
    """Links between content chunks for graph traversal."""

    __tablename__ = "content_cross_references"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_chunk_id: Mapped[UUID] = mapped_column(
        ForeignKey("content_chunks.id", ondelete="CASCADE"), nullable=False
    )
    target_section_ref: Mapped[str] = mapped_column(String(100), nullable=False)
    target_chunk_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("content_chunks.id", ondelete="SET NULL")
    )
    reference_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # "cites", "defines", "supersedes", "amends"
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    source_chunk: Mapped["ContentChunk"] = relationship(foreign_keys=[source_chunk_id])
    target_chunk: Mapped["ContentChunk | None"] = relationship(foreign_keys=[target_chunk_id])

    __table_args__ = (
        UniqueConstraint(
            "source_chunk_id",
            "target_section_ref",
            "reference_type",
            name="uq_cross_ref",
        ),
        Index("ix_cross_ref_source", "source_chunk_id"),
        Index("ix_cross_ref_target", "target_section_ref"),
    )

    def __repr__(self) -> str:
        return f"<ContentCrossReference {self.source_chunk_id} -> {self.target_section_ref}>"


class TaxDomain(Base):
    """Specialist tax domain configuration for scoped retrieval."""

    __tablename__ = "tax_domains"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    topic_tags: Mapped[list] = mapped_column(JSONB, default=list)
    legislation_refs: Mapped[list] = mapped_column(JSONB, default=list)
    ruling_types: Mapped[list] = mapped_column(JSONB, default=list)
    icon: Mapped[str | None] = mapped_column(String(50))
    display_order: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<TaxDomain {self.slug} ({self.name})>"


class BM25IndexEntry(Base):
    """Lightweight BM25 keyword index for hybrid search."""

    __tablename__ = "bm25_index_entries"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    chunk_id: Mapped[UUID] = mapped_column(
        ForeignKey("content_chunks.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    collection_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tokens: Mapped[list] = mapped_column(JSONB, nullable=False)
    section_refs: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    chunk: Mapped["ContentChunk"] = relationship()

    __table_args__ = (Index("ix_bm25_collection", "collection_name"),)

    def __repr__(self) -> str:
        return f"<BM25IndexEntry chunk={self.chunk_id}>"


class ScraperCircuitBreakerState(Base):
    """Tracks per-source-host circuit breaker state."""

    __tablename__ = "scraper_circuit_breakers"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_host: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    state: Mapped[str] = mapped_column(String(20), default="closed", nullable=False)
    # "closed" (healthy), "open" (tripped), "half_open" (testing)
    failure_count: Mapped[int] = mapped_column(default=0)
    last_failure_at: Mapped[datetime | None] = mapped_column()
    last_success_at: Mapped[datetime | None] = mapped_column()
    opened_at: Mapped[datetime | None] = mapped_column()
    recovery_timeout_seconds: Mapped[int] = mapped_column(default=3600)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<ScraperCircuitBreaker {self.source_host} ({self.state})>"


class ChatConversation(Base):
    """User chat conversations with the AI assistant.

    Each conversation contains a series of messages between the user
    and the AI assistant. Conversations are scoped to individual users.
    May optionally be associated with a specific client for context.
    """

    __tablename__ = "chat_conversations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # User identification (Clerk user ID)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Optional client context (Spec 013)
    # References XeroConnection (client business) not XeroClient (contacts)
    client_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("xero_connections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Conversation metadata
    title: Mapped[str] = mapped_column(String(200), default="New Conversation")
    # Auto-generated from first user message or manually set

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    # Relationships
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )

    # Indexes
    __table_args__ = (Index("ix_chat_conversations_user_updated", "user_id", "updated_at"),)

    def __repr__(self) -> str:
        return f"<ChatConversation {self.id} ({self.title[:30]})>"


class ChatMessage(Base):
    """Individual messages in a chat conversation.

    Stores both user questions and AI assistant responses,
    including citations for AI responses and client context metadata.
    """

    __tablename__ = "chat_messages"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Conversation linkage
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("chat_conversations.id", ondelete="CASCADE")
    )

    # Message content
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    # Values: user, assistant

    content: Mapped[str] = mapped_column(Text, nullable=False)

    # AI response metadata (only for assistant messages)
    citations: Mapped[list[dict] | None] = mapped_column(JSONB, default=None)
    # List of citation dicts: {number, title, url, source_type, score}

    # Client context metadata (Spec 013)
    # Note: Column is named 'metadata' in DB but we use 'message_metadata' in Python
    # because 'metadata' is reserved in SQLAlchemy
    message_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, default=None)
    # Query intent, token count, data freshness for client-context messages

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    conversation: Mapped["ChatConversation"] = relationship(back_populates="messages")

    # Indexes
    __table_args__ = (
        Index("ix_chat_messages_conversation_created", "conversation_id", "created_at"),
    )

    def __repr__(self) -> str:
        preview = self.content[:30] + "..." if len(self.content) > 30 else self.content
        return f"<ChatMessage {self.role}: {preview}>"
