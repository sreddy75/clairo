# Implementation Plan: Knowledge Base Infrastructure

**Branch**: `012-knowledge-base` | **Date**: 2025-12-29 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/012-knowledge-base/spec.md`

## Summary

Build the foundational knowledge infrastructure for Clairo's AI moat - a RAG-ready system with:
- 6 Qdrant collections for Australian tax compliance and business advisory content
- Voyage-3.5-lite embeddings (1024 dimensions)
- ATO RSS and web scraping ingestion pipeline
- Semantic chunking with rich metadata
- Fast retrieval with metadata filtering
- Admin UI for super admins to manage sources and monitor ingestion

**Research Documents**: [RESEARCH.md](./RESEARCH.md), [CONTEXT-STRATEGY.md](./CONTEXT-STRATEGY.md), [TENANT-DATA-STRATEGY.md](./TENANT-DATA-STRATEGY.md)

---

## Technical Context

**Language/Version**: Python 3.11 (backend), TypeScript/Next.js 14 (frontend)
**Primary Dependencies**: FastAPI, qdrant-client, voyageai, httpx, beautifulsoup4, feedparser, celery
**Frontend Dependencies**: Next.js, React, Tailwind CSS, lucide-react
**Storage**: Qdrant (vectors), PostgreSQL (metadata tracking), Redis (cache)
**Testing**: pytest, pytest-asyncio
**Target Platform**: Linux containers (Docker)
**Project Type**: Full-stack - backend services + super admin UI
**Performance Goals**: <100ms single collection search, <200ms multi-collection search, <2s admin dashboard load
**Constraints**: Rate limit ATO scraping (1 req/sec), Voyage API batching (128 texts/request), Super admin role required
**Scale/Scope**: ~50,000-500,000 vectors, 6 collections

---

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| Max 3 active projects | PASS | Backend-only spec |
| No premature abstraction | PASS | Direct Qdrant integration, services as needed |
| Minimal viable complexity | PASS | Single embedding model, simple chunking first |
| Clear responsibility boundaries | PASS | Separate ingestion, embedding, search services |

---

## Project Structure

### Documentation (this feature)

```text
specs/012-knowledge-base/
├── spec.md              # User stories and requirements
├── plan.md              # This file - technical architecture
├── RESEARCH.md          # Vector DB, embedding model research
├── CONTEXT-STRATEGY.md  # Tiered context architecture
├── TENANT-DATA-STRATEGY.md  # PostgreSQL vs Qdrant decisions
├── QUERY-EXAMPLES.md    # MOAT value demonstration
└── tasks.md             # Implementation tasks (next step)
```

### Source Code Changes

```text
backend/
├── app/
│   ├── core/
│   │   ├── qdrant.py              # NEW: Qdrant client wrapper
│   │   └── voyage.py              # NEW: Voyage embedding service
│   ├── modules/
│   │   └── knowledge/             # NEW MODULE
│   │       ├── __init__.py
│   │       ├── models.py          # SQLAlchemy models for tracking
│   │       ├── schemas.py         # Pydantic schemas
│   │       ├── repository.py      # Database operations
│   │       ├── service.py         # Business logic
│   │       ├── router.py          # API endpoints (admin)
│   │       ├── collections.py     # Qdrant collection management
│   │       ├── chunker.py         # Semantic text chunking
│   │       ├── scraper/           # Content scrapers
│   │       │   ├── __init__.py
│   │       │   ├── base.py        # Base scraper class
│   │       │   ├── ato_rss.py     # ATO RSS feed scraper
│   │       │   ├── ato_web.py     # ATO website scraper
│   │       │   └── austlii.py     # AustLII legislation scraper
│   │       └── audit_events.py    # Audit logging
│   └── tasks/
│       └── knowledge.py           # NEW: Celery tasks for ingestion
├── alembic/
│   └── versions/
│       └── xxxx_knowledge_base_models.py  # NEW: Migration
└── tests/
    ├── unit/
    │   └── knowledge/
    │       ├── test_chunker.py
    │       ├── test_collections.py
    │       └── test_scrapers.py
    └── integration/
        └── knowledge/
            ├── test_qdrant_integration.py
            └── test_ingestion_pipeline.py

frontend/
├── src/
│   ├── app/
│   │   └── (protected)/
│   │       └── admin/
│   │           └── knowledge/           # NEW: Admin UI
│   │               ├── page.tsx         # Dashboard with tabs
│   │               ├── components/
│   │               │   ├── collections-tab.tsx
│   │               │   ├── sources-tab.tsx
│   │               │   ├── jobs-tab.tsx
│   │               │   ├── search-test-tab.tsx
│   │               │   ├── source-form-modal.tsx
│   │               │   └── job-detail-modal.tsx
│   │               └── hooks/
│   │                   ├── use-collections.ts
│   │                   ├── use-sources.ts
│   │                   ├── use-jobs.ts
│   │                   └── use-search-test.ts
│   ├── lib/
│   │   └── api/
│   │       └── knowledge.ts              # NEW: API client for knowledge endpoints
│   └── types/
│       └── knowledge.ts                  # NEW: TypeScript types for knowledge entities
```

**Structure Decision**: Follows existing module pattern with `knowledge` as a new module under `app/modules/`. Core services (qdrant, voyage) go in `app/core/` for reuse. Admin UI follows existing protected route pattern at `/admin/knowledge`.

---

## Architecture

### High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         INGESTION PIPELINE                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐          │
│  │ Sources  │───▶│ Scrapers │───▶│ Chunker  │───▶│ Embedder │          │
│  │          │    │          │    │ (512 tok)│    │ (Voyage) │          │
│  │ - ATO RSS│    │ - HTML   │    │          │    │          │          │
│  │ - ATO Web│    │ - Clean  │    │ Semantic │    │ 1024-dim │          │
│  │ - AustLII│    │ - Clean  │    │ boundaries│   │ vectors  │          │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘          │
│                                                        │                 │
│                         ┌──────────────────────────────┘                 │
│                         ▼                                                │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                         QDRANT                                     │  │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐              │  │
│  │  │ compliance_  │ │ strategic_   │ │ industry_    │              │  │
│  │  │ knowledge    │ │ advisory     │ │ knowledge    │              │  │
│  │  └──────────────┘ └──────────────┘ └──────────────┘              │  │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐              │  │
│  │  │ business_    │ │ financial_   │ │ people_      │              │  │
│  │  │ fundamentals │ │ management   │ │ operations   │              │  │
│  │  └──────────────┘ └──────────────┘ └──────────────┘              │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                         POSTGRESQL (Tracking)                            │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐      │
│  │ knowledge_sources│  │ content_chunks   │  │ ingestion_jobs   │      │
│  │                  │  │                  │  │                  │      │
│  │ - source config  │  │ - chunk metadata │  │ - job tracking   │      │
│  │ - last scraped   │  │ - vector IDs     │  │ - status/errors  │      │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘      │
└─────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility |
|-----------|----------------|
| **Qdrant Client** (`core/qdrant.py`) | Connection management, collection operations, search interface |
| **Voyage Service** (`core/voyage.py`) | Text embedding, batch processing, rate limiting |
| **Collections** (`knowledge/collections.py`) | Create/configure 6 collections with proper indexes |
| **Chunker** (`knowledge/chunker.py`) | Semantic text splitting at heading/paragraph boundaries |
| **Scrapers** (`knowledge/scraper/`) | Source-specific content extraction and cleaning |
| **Repository** (`knowledge/repository.py`) | PostgreSQL CRUD for tracking metadata |
| **Service** (`knowledge/service.py`) | Orchestrate ingestion pipeline, search operations |
| **Celery Tasks** (`tasks/knowledge.py`) | Background processing for scraping and embedding |

---

## Data Models

### PostgreSQL Models (Tracking)

```python
# backend/app/modules/knowledge/models.py

class KnowledgeSource(TenantModel):
    """Configured content sources for ingestion."""
    __tablename__ = "knowledge_sources"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # ato_rss, ato_web, austlii, business_gov
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    collection_name: Mapped[str] = mapped_column(String(100), nullable=False)
    scrape_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(default=True)
    last_scraped_at: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # Relationships
    chunks: Mapped[list["ContentChunk"]] = relationship(back_populates="source")
    jobs: Mapped[list["IngestionJob"]] = relationship(back_populates="source")


class ContentChunk(Base):
    """Tracks individual content chunks stored in Qdrant."""
    __tablename__ = "content_chunks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_sources.id"))
    qdrant_point_id: Mapped[str] = mapped_column(String(100), unique=True)
    collection_name: Mapped[str] = mapped_column(String(100), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)  # For deduplication

    # Content metadata (mirrors Qdrant payload)
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500))
    source_type: Mapped[str] = mapped_column(String(50))
    effective_date: Mapped[date | None] = mapped_column()
    expiry_date: Mapped[date | None] = mapped_column()
    entity_types: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    industries: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    ruling_number: Mapped[str | None] = mapped_column(String(50))

    # Status
    is_superseded: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # Relationships
    source: Mapped["KnowledgeSource"] = relationship(back_populates="chunks")


class IngestionJob(Base):
    """Tracks content ingestion runs."""
    __tablename__ = "ingestion_jobs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_sources.id"))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # pending, running, completed, failed

    started_at: Mapped[datetime | None] = mapped_column()
    completed_at: Mapped[datetime | None] = mapped_column()

    # Statistics
    items_processed: Mapped[int] = mapped_column(default=0)
    items_added: Mapped[int] = mapped_column(default=0)
    items_updated: Mapped[int] = mapped_column(default=0)
    items_skipped: Mapped[int] = mapped_column(default=0)
    errors: Mapped[list[dict]] = mapped_column(JSONB, default=list)

    created_at: Mapped[datetime] = mapped_column(default=func.now())

    # Relationships
    source: Mapped["KnowledgeSource"] = relationship(back_populates="jobs")
```

### Qdrant Payload Schema

```python
# Metadata stored with each vector point

class ChunkPayload(TypedDict):
    """Qdrant point payload structure."""
    # Identification
    chunk_id: str  # UUID as string
    source_id: str  # UUID as string
    source_url: str
    title: str | None

    # Content
    text: str  # Original text for display
    chunk_index: int  # Position in source document

    # Classification
    source_type: str  # ato_ruling, ato_guide, legislation, business_guide
    collection_namespace: str  # gst, income_tax, superannuation, etc.

    # Applicability filters
    entity_types: list[str]  # ["sole_trader", "company", "trust", "partnership"]
    industries: list[str]  # ANZSIC codes or labels
    revenue_brackets: list[str]  # ["under_75k", "75k_to_500k", "500k_to_2m", "over_2m"]

    # Temporal
    effective_date: str | None  # ISO date
    expiry_date: str | None  # ISO date
    scraped_at: str  # ISO datetime

    # Rulings specific
    ruling_number: str | None  # TR 2024/1, GSTR 2024/1, PCG 2024/1
    is_superseded: bool

    # Quality
    confidence_level: str  # high, medium, low
```

---

## Qdrant Collection Configuration

```python
# backend/app/modules/knowledge/collections.py

COLLECTIONS = {
    "compliance_knowledge": {
        "description": "ATO rules, legislation, tax compliance guidance",
        "vector_size": 1024,
        "distance": Distance.COSINE,
        "payload_indexes": [
            ("source_type", PayloadSchemaType.KEYWORD),
            ("entity_types", PayloadSchemaType.KEYWORD),
            ("industries", PayloadSchemaType.KEYWORD),
            ("effective_date", PayloadSchemaType.DATETIME),
            ("ruling_number", PayloadSchemaType.KEYWORD),
            ("is_superseded", PayloadSchemaType.BOOL),
        ]
    },
    "strategic_advisory": {
        "description": "Tax optimization, entity structuring, growth strategies",
        "vector_size": 1024,
        "distance": Distance.COSINE,
        "payload_indexes": [
            ("entity_types", PayloadSchemaType.KEYWORD),
            ("industries", PayloadSchemaType.KEYWORD),
            ("revenue_brackets", PayloadSchemaType.KEYWORD),
        ]
    },
    "industry_knowledge": {
        "description": "Industry-specific deductions, benchmarks, practices",
        "vector_size": 1024,
        "distance": Distance.COSINE,
        "payload_indexes": [
            ("industries", PayloadSchemaType.KEYWORD),
            ("entity_types", PayloadSchemaType.KEYWORD),
        ]
    },
    "business_fundamentals": {
        "description": "Starting business, ABN, planning, legal basics",
        "vector_size": 1024,
        "distance": Distance.COSINE,
        "payload_indexes": [
            ("entity_types", PayloadSchemaType.KEYWORD),
        ]
    },
    "financial_management": {
        "description": "Cash flow, debtor management, pricing, KPIs",
        "vector_size": 1024,
        "distance": Distance.COSINE,
        "payload_indexes": [
            ("revenue_brackets", PayloadSchemaType.KEYWORD),
        ]
    },
    "people_operations": {
        "description": "Hiring, employment, payroll basics, WHS",
        "vector_size": 1024,
        "distance": Distance.COSINE,
        "payload_indexes": [
            ("entity_types", PayloadSchemaType.KEYWORD),
        ]
    },
}
```

---

## Core Services

### Qdrant Client Wrapper

```python
# backend/app/core/qdrant.py

from qdrant_client import QdrantClient, AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter

class QdrantService:
    """Async Qdrant client wrapper with collection management."""

    def __init__(self, settings: QdrantSettings):
        self.client = AsyncQdrantClient(
            host=settings.host,
            port=settings.port,
            api_key=settings.api_key.get_secret_value() if settings.api_key else None,
        )

    async def create_collection(
        self,
        name: str,
        vector_size: int = 1024,
        distance: Distance = Distance.COSINE,
    ) -> None:
        """Create collection if not exists."""
        ...

    async def create_payload_index(
        self, collection: str, field: str, schema_type: PayloadSchemaType
    ) -> None:
        """Create index on payload field for efficient filtering."""
        ...

    async def upsert_points(
        self, collection: str, points: list[PointStruct]
    ) -> None:
        """Upsert vectors with payloads."""
        ...

    async def search(
        self,
        collection: str,
        query_vector: list[float],
        filter: Filter | None = None,
        limit: int = 10,
    ) -> list[ScoredPoint]:
        """Vector similarity search with optional filtering."""
        ...

    async def search_multi_collection(
        self,
        collections: list[str],
        query_vector: list[float],
        filters: dict[str, Filter] | None = None,
        limit_per_collection: int = 5,
    ) -> list[ScoredPoint]:
        """Search multiple collections in parallel."""
        ...
```

### Voyage Embedding Service

```python
# backend/app/core/voyage.py

import voyageai
from tenacity import retry, stop_after_attempt, wait_exponential

class VoyageService:
    """Voyage AI embedding service with batching and retry logic."""

    MODEL = "voyage-3.5-lite"
    DIMENSION = 1024
    MAX_BATCH_SIZE = 128  # Voyage API limit

    def __init__(self, api_key: str):
        self.client = voyageai.Client(api_key=api_key)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def embed_text(self, text: str) -> list[float]:
        """Embed single text."""
        result = await self.client.embed(
            texts=[text],
            model=self.MODEL,
            input_type="document",
        )
        return result.embeddings[0]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def embed_query(self, query: str) -> list[float]:
        """Embed search query (different input_type for better retrieval)."""
        result = await self.client.embed(
            texts=[query],
            model=self.MODEL,
            input_type="query",
        )
        return result.embeddings[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts with automatic batching."""
        all_embeddings = []
        for i in range(0, len(texts), self.MAX_BATCH_SIZE):
            batch = texts[i:i + self.MAX_BATCH_SIZE]
            result = await self.client.embed(
                texts=batch,
                model=self.MODEL,
                input_type="document",
            )
            all_embeddings.extend(result.embeddings)
        return all_embeddings
```

### Semantic Chunker

```python
# backend/app/modules/knowledge/chunker.py

from dataclasses import dataclass
import re

@dataclass
class Chunk:
    text: str
    index: int
    metadata: dict  # title, heading_path, etc.

class SemanticChunker:
    """Split text at semantic boundaries (headings, paragraphs)."""

    MAX_CHUNK_SIZE = 512  # tokens (approximately)
    OVERLAP = 50  # token overlap between chunks

    def __init__(self):
        self.heading_pattern = re.compile(r'^#{1,6}\s+.+$', re.MULTILINE)

    def chunk_document(
        self,
        text: str,
        title: str | None = None,
        preserve_headings: bool = True,
    ) -> list[Chunk]:
        """Split document into semantic chunks."""
        # 1. Split by major headings first
        # 2. Within each section, split by paragraphs
        # 3. Merge small chunks, split large ones
        # 4. Add overlap for context continuity
        ...

    def chunk_legislation(
        self,
        text: str,
        act_name: str,
        section_number: str,
    ) -> list[Chunk]:
        """Special chunking for legislation to preserve section references."""
        ...
```

---

## API Endpoints

### Admin API (Internal Use)

```python
# backend/app/modules/knowledge/router.py

router = APIRouter(prefix="/api/v1/admin/knowledge", tags=["knowledge-admin"])

# Collection Management
@router.post("/collections/initialize")
async def initialize_collections() -> dict:
    """Create all 6 collections with proper configuration."""

@router.get("/collections")
async def list_collections() -> list[CollectionInfo]:
    """List all collections with stats."""

@router.delete("/collections/{name}")
async def delete_collection(name: str) -> dict:
    """Delete and recreate a collection."""

# Source Management
@router.post("/sources")
async def create_source(source: KnowledgeSourceCreate) -> KnowledgeSourceResponse:
    """Configure a new content source."""

@router.get("/sources")
async def list_sources() -> list[KnowledgeSourceResponse]:
    """List all configured sources."""

@router.post("/sources/{source_id}/ingest")
async def trigger_ingestion(source_id: UUID) -> IngestionJobResponse:
    """Trigger manual ingestion for a source."""

# Job Management
@router.get("/jobs")
async def list_jobs(
    status: str | None = None,
    source_id: UUID | None = None,
) -> list[IngestionJobResponse]:
    """List ingestion jobs with filtering."""

@router.get("/jobs/{job_id}")
async def get_job(job_id: UUID) -> IngestionJobResponse:
    """Get job details and progress."""

# Search Testing
@router.post("/search/test")
async def test_search(
    query: str,
    collections: list[str] | None = None,
    filters: dict | None = None,
    limit: int = 10,
) -> SearchTestResponse:
    """Test search functionality (admin debugging)."""
```

---

## Admin UI Architecture

### Component Structure

The Admin UI at `/admin/knowledge` provides super admin access to manage the knowledge base:

```
/admin/knowledge
├── Dashboard (default tab)
│   ├── Collection health cards (6 collections)
│   ├── Last ingestion timestamp
│   └── Quick actions (Initialize, Refresh)
├── Sources Tab
│   ├── Source list table
│   ├── Create source modal
│   ├── Edit source modal
│   └── Per-source ingestion trigger
├── Jobs Tab
│   ├── Job history table with filtering
│   ├── Job detail modal (stats, errors)
│   └── Real-time status updates
└── Search Test Tab
    ├── Query input
    ├── Collection/filter selection
    └── Results display with metadata
```

### Key UI Components

| Component | Purpose | API Endpoint |
|-----------|---------|--------------|
| `CollectionsTab` | Display/manage 6 collections | `GET /api/v1/admin/knowledge/collections` |
| `SourcesTab` | CRUD for knowledge sources | `GET/POST/PUT/DELETE /api/v1/admin/knowledge/sources` |
| `JobsTab` | Job history and monitoring | `GET /api/v1/admin/knowledge/jobs` |
| `SourceFormModal` | Create/edit source form | `POST/PUT /api/v1/admin/knowledge/sources` |
| `JobDetailModal` | Job stats and error list | `GET /api/v1/admin/knowledge/jobs/{id}` |
| `SearchTestTab` | Test search functionality | `POST /api/v1/admin/knowledge/search/test` |

### State Management

```typescript
// React hooks for each entity type
useCollections()  // Fetch collection stats, trigger refresh
useSources()      // CRUD operations, trigger ingestion
useJobs()         // Job list with filtering, polling for running jobs
useSearchTest()   // Execute test searches
```

### Access Control

- Route protected by Clerk authentication
- Super admin role required (checked via `useAuth().sessionClaims?.role`)
- Non-super-admins redirected to dashboard with error toast

### Polling Strategy

For running jobs, the UI uses polling (not WebSockets):
- Poll interval: 3 seconds while job is `running`
- Stop polling when job reaches terminal state (`completed`/`failed`)
- Manual refresh button for on-demand updates

---

## Celery Tasks

```python
# backend/app/tasks/knowledge.py

from app.tasks.celery_app import celery_app

@celery_app.task(bind=True, max_retries=3)
def ingest_source(self, source_id: str) -> dict:
    """
    Run full ingestion pipeline for a source.

    1. Create ingestion job record
    2. Fetch content (scrape or RSS)
    3. Clean and chunk content
    4. Embed chunks via Voyage
    5. Upsert to Qdrant
    6. Update tracking records
    7. Log completion
    """
    ...

@celery_app.task
def check_rss_feeds() -> dict:
    """
    Daily task to check ATO RSS feeds for new content.

    1. Fetch RSS feeds
    2. Compare with last seen items
    3. Queue new items for ingestion
    """
    ...

@celery_app.task
def update_superseded_content() -> dict:
    """
    Weekly task to check for superseded rulings.

    1. Query ATO for superseded rulings
    2. Update is_superseded flag in Qdrant
    3. Log changes
    """
    ...
```

---

## Configuration Updates

### Environment Variables

```bash
# .env additions
VOYAGE_API_KEY=pa-xxxxxxxxxxxxxxxx

# Qdrant already configured
QDRANT_HOST=localhost
QDRANT_PORT=6333
```

### Settings Addition

```python
# backend/app/config.py

class VoyageSettings(BaseSettings):
    """Voyage AI embedding service configuration."""

    model_config = SettingsConfigDict(
        env_prefix="VOYAGE_",
        env_file=(".env", ".env.local"),
        extra="ignore",
    )

    api_key: SecretStr = Field(
        description="Voyage AI API key"
    )
    model: str = Field(
        default="voyage-3.5-lite",
        description="Embedding model to use"
    )
    batch_size: int = Field(
        default=128,
        ge=1,
        le=128,
        description="Max texts per embedding request"
    )
```

---

## Testing Strategy

### Unit Tests

| Test File | Coverage |
|-----------|----------|
| `test_chunker.py` | Semantic chunking at boundaries, overlap handling |
| `test_collections.py` | Collection creation, index configuration |
| `test_scrapers.py` | HTML parsing, content extraction, metadata |

### Integration Tests

| Test File | Coverage |
|-----------|----------|
| `test_qdrant_integration.py` | Collection ops, upsert, search, filters |
| `test_ingestion_pipeline.py` | End-to-end: scrape → chunk → embed → store |

### Test Fixtures

```python
# tests/conftest.py additions

@pytest.fixture
async def qdrant_test_collection(qdrant_client):
    """Create test collection, yield, cleanup."""
    name = f"test_collection_{uuid4().hex[:8]}"
    await qdrant_client.create_collection(name, vector_size=1024)
    yield name
    await qdrant_client.delete_collection(name)

@pytest.fixture
def sample_ato_html():
    """Sample ATO webpage HTML for scraper tests."""
    return Path("tests/fixtures/ato_gst_page.html").read_text()
```

---

## Implementation Phases

### Phase 1: Infrastructure (P1)

1. Create `app/core/qdrant.py` - Qdrant client wrapper
2. Create `app/core/voyage.py` - Voyage embedding service
3. Create `app/modules/knowledge/collections.py` - Collection management
4. Add VoyageSettings to config
5. Write unit tests for core services
6. Verify Qdrant connection and collection creation

### Phase 2: Ingestion Pipeline (P1)

1. Create PostgreSQL models and migration
2. Create `app/modules/knowledge/chunker.py`
3. Create base scraper interface
4. Implement ATO RSS scraper
5. Implement ATO web scraper
6. Implement service layer
7. Write integration tests

### Phase 3: Celery Integration (P1)

1. Create `app/tasks/knowledge.py`
2. Add scheduled tasks (RSS check, superseded check)
3. Wire up to celery-beat
4. Test background processing

### Phase 4: Admin API & Verification (P1)

1. Create admin router endpoints
2. Test search functionality
3. Verify metadata filtering
4. Document API endpoints

### Phase 5: Content Population (P2)

1. Configure initial ATO sources
2. Run initial ingestion
3. Verify search quality
4. Iterate on chunking strategy

### Phase 6: Extended Sources (P2)

1. Implement AustLII scraper
2. Implement Business.gov.au scraper
3. Add Fair Work content
4. Populate advisory collections

### Phase 7: Admin UI (P1)

1. Create frontend route `/admin/knowledge` with super admin protection
2. Implement Collections dashboard tab with health status
3. Implement Sources tab with CRUD operations
4. Implement Jobs tab with history and polling for status
5. Implement Search Test tab for verification
6. Create API client hooks (useCollections, useSources, useJobs, useSearchTest)
7. Add TypeScript types for knowledge entities
8. Style with Tailwind CSS matching existing Clairo design

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Collections created | 6 | Count collections in Qdrant |
| Chunks ingested | >50,000 | Count points across collections |
| Search latency (single) | <100ms | p95 from test queries |
| Search latency (multi) | <200ms | p95 from test queries |
| Embedding throughput | 1,000 chunks / 5 min | Timed batch processing |
| Pipeline reliability | Zero unhandled errors / 7 days | Error monitoring |
| Admin UI load time | <2s | Dashboard initial load |
| Job status update | <5s | Polling interval for running jobs |

---

## Dependencies

### Python Packages (add to pyproject.toml)

```toml
[project.dependencies]
qdrant-client = "^1.12"
voyageai = "^0.3"
feedparser = "^6.0"
beautifulsoup4 = "^4.12"
lxml = "^5.2"
tenacity = "^9.0"  # Already have this
```

### External Services

| Service | Purpose | Required |
|---------|---------|----------|
| Qdrant | Vector storage | Yes (already configured) |
| Voyage AI | Text embeddings | Yes (need API key) |
| ATO Website | Content source | Yes (public) |
| AustLII | Legislation source | Yes (public) |

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| ATO blocks scraping | Respect robots.txt, rate limit 1 req/sec, rotate user agents |
| Voyage API quota | Batch efficiently, implement queue-based processing |
| Qdrant memory limits | Monitor collection sizes, implement pagination |
| Stale content | Daily RSS checks, quarterly full audit |
| Poor search relevance | Test with real queries, iterate on chunking, add reranking |

---

## Next Steps

1. **Create tasks.md** - Break down into implementable tasks with time estimates
2. **Get Voyage API key** - Sign up at voyageai.com
3. **Start Phase 1** - Infrastructure implementation
