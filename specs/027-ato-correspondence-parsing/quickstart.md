# Quickstart: ATO Correspondence Parsing

**Spec**: 027-ato-correspondence-parsing
**Time to Implement**: ~3-4 days
**Prerequisites**: Spec 026 (Email Integration), Qdrant, Claude API

---

## Overview

This guide covers implementing AI-powered parsing of ATO emails to extract structured data and match correspondence to clients.

---

## Quick Setup

### 1. Install Dependencies

```bash
cd backend
uv add anthropic qdrant-client rapidfuzz pdfplumber openai
```

### 2. Environment Variables

```bash
# Claude API (for parsing)
ANTHROPIC_API_KEY=sk-ant-...

# OpenAI API (for embeddings)
OPENAI_API_KEY=sk-...

# Qdrant (vector store)
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_API_KEY=  # Optional for local

# Parsing configuration
PARSING_MODEL=claude-3-5-sonnet-20241022
EMBEDDING_MODEL=text-embedding-3-small
MATCH_CONFIDENCE_THRESHOLD=80
```

### 3. Qdrant Setup

```bash
# Start Qdrant locally
docker run -p 6333:6333 qdrant/qdrant

# Or use Qdrant Cloud for production
```

---

## Core Implementation

### Notice Type Taxonomy

```python
# backend/app/modules/email/parsing/notice_types.py
from enum import Enum

class ATONoticeType(str, Enum):
    """Classification of ATO notice types."""
    ACTIVITY_STATEMENT_REMINDER = "activity_statement_reminder"
    ACTIVITY_STATEMENT_CONFIRMATION = "activity_statement_confirmation"
    AUDIT_NOTICE = "audit_notice"
    AUDIT_OUTCOME = "audit_outcome"
    PENALTY_NOTICE = "penalty_notice"
    DEBT_NOTICE = "debt_notice"
    PAYMENT_REMINDER = "payment_reminder"
    RUNNING_BALANCE_ACCOUNT = "running_balance_account"
    TAX_RETURN_REMINDER = "tax_return_reminder"
    TAX_ASSESSMENT = "tax_assessment"
    SUPERANNUATION_NOTICE = "superannuation_notice"
    PAYG_WITHHOLDING = "payg_withholding"
    FBT_NOTICE = "fringe_benefits_tax"
    GENERAL = "general"
    UNKNOWN = "unknown"

# Urgency and metadata for each type
NOTICE_TYPE_METADATA = {
    ATONoticeType.AUDIT_NOTICE: {
        "urgency": "high",
        "typical_response_days": 28,
        "category": "compliance",
    },
    ATONoticeType.PENALTY_NOTICE: {
        "urgency": "high",
        "typical_response_days": 21,
        "category": "debt",
    },
    ATONoticeType.ACTIVITY_STATEMENT_REMINDER: {
        "urgency": "medium",
        "typical_response_days": 14,
        "category": "lodgement",
    },
    # ... add more
}
```

### Claude Parser

```python
# backend/app/modules/email/parsing/claude_parser.py
from anthropic import Anthropic
from pydantic import BaseModel
import json

from app.config import settings
from .notice_types import ATONoticeType

class ClientIdentifier(BaseModel):
    type: str  # "abn", "tfn", "name"
    value: str

class ParsedEmail(BaseModel):
    notice_type: ATONoticeType
    reference_number: str | None
    due_date: str | None  # YYYY-MM-DD
    amount: float | None
    client_identifier: ClientIdentifier | None
    required_action: str | None
    confidence: int  # 0-100

class ClaudeParser:
    """Parse ATO emails using Claude."""

    def __init__(self):
        self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = settings.PARSING_MODEL

    async def parse(self, email_content: str) -> ParsedEmail:
        """Parse email content and extract structured data."""
        prompt = self._build_prompt(email_content)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )

        # Extract JSON from response
        response_text = response.content[0].text
        parsed_data = json.loads(response_text)

        return ParsedEmail(**parsed_data)

    def _build_prompt(self, email_content: str) -> str:
        """Build the parsing prompt with examples."""
        notice_types = ", ".join([t.value for t in ATONoticeType])

        return f"""You are an expert at extracting structured information from Australian Taxation Office (ATO) emails.

Analyze the following email and extract key information.

<email>
{email_content}
</email>

## Notice Types (choose one):
{notice_types}

## Examples:

Example 1 - Activity Statement Reminder:
Input: "Your activity statement for the period ending 31 December 2025 is due on 28 February 2026. ABN: 12 345 678 901"
Output: {{"notice_type": "activity_statement_reminder", "reference_number": null, "due_date": "2026-02-28", "amount": null, "client_identifier": {{"type": "abn", "value": "12345678901"}}, "required_action": "Lodge activity statement by due date", "confidence": 95}}

Example 2 - Penalty Notice:
Input: "We have applied a failure to lodge penalty of $1,100 to your account. Reference: 123456789. Entity: Smith Plumbing Pty Ltd."
Output: {{"notice_type": "penalty_notice", "reference_number": "123456789", "due_date": null, "amount": 1100.00, "client_identifier": {{"type": "name", "value": "Smith Plumbing Pty Ltd"}}, "required_action": "Pay penalty or request remission", "confidence": 92}}

## Your Response:
Return ONLY a valid JSON object with these exact fields:
- notice_type (string): one of the types listed above
- reference_number (string or null): ATO reference number
- due_date (string or null): date in YYYY-MM-DD format
- amount (number or null): dollar amount if applicable
- client_identifier (object or null): {{"type": "abn"|"tfn"|"name", "value": "string"}}
- required_action (string or null): brief description of action needed
- confidence (number): 0-100 confidence score

JSON Response:"""
```

### Client Matching Service

```python
# backend/app/modules/email/matching/service.py
from uuid import UUID
from rapidfuzz import fuzz, process
from pydantic import BaseModel

from app.modules.clients.repository import ClientRepository
from app.modules.email.parsing.claude_parser import ClientIdentifier

class MatchResult(BaseModel):
    client_id: UUID | None
    match_type: str  # "abn_exact", "tfn_exact", "name_fuzzy", "none"
    confidence: float  # 0-100
    requires_triage: bool
    suggested_client_id: UUID | None = None

class ClientMatchingService:
    """Match extracted identifiers to clients."""

    def __init__(self, client_repo: ClientRepository):
        self.client_repo = client_repo
        self.confidence_threshold = 80

    async def match(
        self,
        identifier: ClientIdentifier | None,
        tenant_id: UUID
    ) -> MatchResult:
        """Match identifier to a client."""
        if not identifier:
            return MatchResult(
                client_id=None,
                match_type="none",
                confidence=0,
                requires_triage=True,
            )

        # Try ABN exact match
        if identifier.type == "abn":
            return await self._match_by_abn(identifier.value, tenant_id)

        # Try TFN exact match
        if identifier.type == "tfn":
            return await self._match_by_tfn(identifier.value, tenant_id)

        # Fuzzy name match
        return await self._match_by_name(identifier.value, tenant_id)

    async def _match_by_abn(self, abn: str, tenant_id: UUID) -> MatchResult:
        """Exact match by ABN."""
        normalized = self._normalize_abn(abn)
        client = await self.client_repo.get_by_abn(normalized, tenant_id)

        if client:
            return MatchResult(
                client_id=client.id,
                match_type="abn_exact",
                confidence=100,
                requires_triage=False,
            )

        return MatchResult(
            client_id=None,
            match_type="none",
            confidence=0,
            requires_triage=True,
        )

    async def _match_by_name(self, name: str, tenant_id: UUID) -> MatchResult:
        """Fuzzy match by business name."""
        clients = await self.client_repo.get_all_with_names(tenant_id)

        if not clients:
            return MatchResult(
                client_id=None,
                match_type="none",
                confidence=0,
                requires_triage=True,
            )

        # Build name -> client mapping
        name_map = {c.name: c for c in clients}

        # Find best match
        matches = process.extract(
            name,
            list(name_map.keys()),
            scorer=fuzz.token_set_ratio,
            limit=1,
        )

        if matches and matches[0][1] >= self.confidence_threshold:
            matched_name, score, _ = matches[0]
            client = name_map[matched_name]
            return MatchResult(
                client_id=client.id,
                match_type="name_fuzzy",
                confidence=score,
                requires_triage=False,
            )

        # Below threshold - suggest but require triage
        if matches:
            matched_name, score, _ = matches[0]
            client = name_map[matched_name]
            return MatchResult(
                client_id=None,
                match_type="name_fuzzy",
                confidence=score,
                requires_triage=True,
                suggested_client_id=client.id,
            )

        return MatchResult(
            client_id=None,
            match_type="none",
            confidence=0,
            requires_triage=True,
        )

    def _normalize_abn(self, abn: str) -> str:
        """Normalize ABN by removing spaces."""
        return abn.replace(" ", "").replace("-", "")
```

### Vector Storage Service

```python
# backend/app/modules/email/vector/service.py
from uuid import UUID
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)
from openai import AsyncOpenAI

from app.config import settings

class VectorService:
    """Manage vector embeddings in Qdrant."""

    def __init__(self):
        self.qdrant = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            api_key=settings.QDRANT_API_KEY or None,
        )
        self.openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.embedding_model = settings.EMBEDDING_MODEL
        self.vector_size = 1536  # text-embedding-3-small

    async def ensure_collection(self, tenant_id: UUID):
        """Create collection for tenant if it doesn't exist."""
        collection_name = self._collection_name(tenant_id)

        collections = self.qdrant.get_collections().collections
        exists = any(c.name == collection_name for c in collections)

        if not exists:
            self.qdrant.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE,
                ),
            )

    async def store(
        self,
        correspondence_id: UUID,
        content: str,
        metadata: dict,
        tenant_id: UUID,
    ) -> str:
        """Store email content with embedding."""
        await self.ensure_collection(tenant_id)

        # Generate embedding
        embedding = await self._generate_embedding(content)

        # Store in Qdrant
        point_id = str(correspondence_id)
        self.qdrant.upsert(
            collection_name=self._collection_name(tenant_id),
            points=[
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        "correspondence_id": str(correspondence_id),
                        "notice_type": metadata.get("notice_type"),
                        "client_id": str(metadata.get("client_id")) if metadata.get("client_id") else None,
                        "subject": metadata.get("subject", ""),
                        "received_at": metadata.get("received_at"),
                    },
                )
            ],
        )

        return point_id

    async def search(
        self,
        query: str,
        tenant_id: UUID,
        filters: dict | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """Semantic search correspondence."""
        # Generate query embedding
        query_embedding = await self._generate_embedding(query)

        # Build filter conditions
        filter_conditions = []
        if filters:
            if filters.get("notice_type"):
                filter_conditions.append(
                    FieldCondition(
                        key="notice_type",
                        match=MatchValue(value=filters["notice_type"]),
                    )
                )
            if filters.get("client_id"):
                filter_conditions.append(
                    FieldCondition(
                        key="client_id",
                        match=MatchValue(value=str(filters["client_id"])),
                    )
                )

        # Search
        results = self.qdrant.search(
            collection_name=self._collection_name(tenant_id),
            query_vector=query_embedding,
            query_filter=Filter(must=filter_conditions) if filter_conditions else None,
            limit=limit,
        )

        return [
            {
                "correspondence_id": UUID(r.payload["correspondence_id"]),
                "score": r.score,
                "notice_type": r.payload.get("notice_type"),
                "subject": r.payload.get("subject"),
            }
            for r in results
        ]

    async def _generate_embedding(self, text: str) -> list[float]:
        """Generate embedding using OpenAI."""
        response = await self.openai.embeddings.create(
            model=self.embedding_model,
            input=text,
        )
        return response.data[0].embedding

    def _collection_name(self, tenant_id: UUID) -> str:
        """Get collection name for tenant."""
        return f"ato_correspondence_{tenant_id}"
```

### Parsing Orchestration Service

```python
# backend/app/modules/email/parsing/service.py
from uuid import UUID
from datetime import datetime

from app.modules.email.models import RawEmail
from app.modules.email.correspondence.models import ATOCorrespondence, CorrespondenceStatus
from app.modules.email.correspondence.repository import CorrespondenceRepository
from app.modules.email.triage.service import TriageService
from .claude_parser import ClaudeParser
from ..matching.service import ClientMatchingService
from ..vector.service import VectorService

class ParsingService:
    """Orchestrate email parsing pipeline."""

    def __init__(
        self,
        parser: ClaudeParser,
        matcher: ClientMatchingService,
        vector_service: VectorService,
        correspondence_repo: CorrespondenceRepository,
        triage_service: TriageService,
    ):
        self.parser = parser
        self.matcher = matcher
        self.vector_service = vector_service
        self.correspondence_repo = correspondence_repo
        self.triage_service = triage_service

    async def parse_email(self, raw_email: RawEmail) -> ATOCorrespondence:
        """Parse a raw email and create correspondence record."""

        # 1. Extract content
        content = raw_email.body_text or raw_email.body_html or ""

        # 2. Parse with Claude
        parsed = await self.parser.parse(content)

        # 3. Match to client
        match_result = await self.matcher.match(
            parsed.client_identifier,
            raw_email.tenant_id,
        )

        # 4. Create correspondence record
        correspondence = ATOCorrespondence(
            tenant_id=raw_email.tenant_id,
            raw_email_id=raw_email.id,
            client_id=match_result.client_id,
            match_type=match_result.match_type,
            match_confidence=match_result.confidence,
            subject=raw_email.subject,
            from_address=raw_email.from_address,
            received_at=raw_email.received_at,
            notice_type=parsed.notice_type,
            reference_number=parsed.reference_number,
            due_date=datetime.strptime(parsed.due_date, "%Y-%m-%d").date() if parsed.due_date else None,
            amount=parsed.amount,
            required_action=parsed.required_action,
            parsing_confidence=parsed.confidence,
            parsing_model=self.parser.model,
            status=CorrespondenceStatus.NEW,
        )

        correspondence = await self.correspondence_repo.create(correspondence)

        # 5. Store in vector DB
        vector_id = await self.vector_service.store(
            correspondence_id=correspondence.id,
            content=content,
            metadata={
                "notice_type": parsed.notice_type.value,
                "client_id": match_result.client_id,
                "subject": raw_email.subject,
                "received_at": raw_email.received_at.isoformat(),
            },
            tenant_id=raw_email.tenant_id,
        )

        await self.correspondence_repo.update_vector_id(correspondence.id, vector_id)

        # 6. Create triage item if needed
        if match_result.requires_triage:
            await self.triage_service.create_triage_item(
                correspondence_id=correspondence.id,
                tenant_id=raw_email.tenant_id,
                extracted_identifier=parsed.client_identifier.value if parsed.client_identifier else None,
                identifier_type=parsed.client_identifier.type if parsed.client_identifier else None,
                suggested_client_id=match_result.suggested_client_id,
                suggested_confidence=match_result.confidence,
            )

        return correspondence
```

### Celery Task

```python
# backend/app/modules/email/parsing/tasks.py
from celery import shared_task
from uuid import UUID

from app.database import get_session
from app.modules.email.repository import EmailRepository
from app.modules.email.parsing.service import ParsingService
from app.modules.email.parsing.claude_parser import ClaudeParser
from app.modules.email.matching.service import ClientMatchingService
from app.modules.email.vector.service import VectorService
from app.modules.email.correspondence.repository import CorrespondenceRepository
from app.modules.email.triage.service import TriageService
from app.modules.clients.repository import ClientRepository

@shared_task
def parse_new_email(raw_email_id: str):
    """Celery task to parse a newly synced email."""
    import asyncio
    asyncio.run(_parse_email(UUID(raw_email_id)))

async def _parse_email(raw_email_id: UUID):
    """Parse a single email."""
    async with get_session() as session:
        # Initialize services
        email_repo = EmailRepository(session)
        client_repo = ClientRepository(session)
        correspondence_repo = CorrespondenceRepository(session)

        parser = ClaudeParser()
        matcher = ClientMatchingService(client_repo)
        vector_service = VectorService()
        triage_service = TriageService(session)

        parsing_service = ParsingService(
            parser=parser,
            matcher=matcher,
            vector_service=vector_service,
            correspondence_repo=correspondence_repo,
            triage_service=triage_service,
        )

        # Get raw email
        raw_email = await email_repo.get_email(raw_email_id)
        if not raw_email:
            return

        # Parse
        await parsing_service.parse_email(raw_email)
```

---

## API Router

```python
# backend/app/modules/email/correspondence/router.py
from fastapi import APIRouter, Depends, HTTPException, Query
from uuid import UUID

from app.core.auth import get_current_tenant
from app.modules.email.correspondence.service import CorrespondenceService
from app.modules.email.correspondence.schemas import (
    CorrespondenceListResponse,
    CorrespondenceDetail,
    SearchRequest,
    SearchResponse,
)

router = APIRouter(prefix="/correspondence", tags=["correspondence"])

@router.get("")
async def list_correspondence(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    client_id: UUID = Query(None),
    notice_type: str = Query(None),
    status: str = Query(None),
    tenant = Depends(get_current_tenant),
    service: CorrespondenceService = Depends(),
) -> CorrespondenceListResponse:
    """List ATO correspondence with filters."""
    return await service.list_correspondence(
        tenant_id=tenant.id,
        page=page,
        page_size=page_size,
        client_id=client_id,
        notice_type=notice_type,
        status=status,
    )

@router.get("/{correspondence_id}")
async def get_correspondence(
    correspondence_id: UUID,
    tenant = Depends(get_current_tenant),
    service: CorrespondenceService = Depends(),
) -> CorrespondenceDetail:
    """Get correspondence details."""
    result = await service.get_correspondence(correspondence_id, tenant.id)
    if not result:
        raise HTTPException(status_code=404, detail="Correspondence not found")
    return result

@router.post("/search")
async def search_correspondence(
    request: SearchRequest,
    tenant = Depends(get_current_tenant),
    service: CorrespondenceService = Depends(),
) -> SearchResponse:
    """Semantic search correspondence."""
    return await service.search(
        query=request.query,
        tenant_id=tenant.id,
        filters=request.filters,
        limit=request.limit,
    )

@router.post("/{correspondence_id}/assign-client")
async def assign_client(
    correspondence_id: UUID,
    client_id: UUID,
    tenant = Depends(get_current_tenant),
    service: CorrespondenceService = Depends(),
) -> CorrespondenceDetail:
    """Assign correspondence to a client."""
    return await service.assign_client(
        correspondence_id=correspondence_id,
        client_id=client_id,
        tenant_id=tenant.id,
    )
```

---

## Testing

### Unit Test: Claude Parser

```python
# backend/tests/unit/modules/email/test_claude_parser.py
import pytest
from unittest.mock import AsyncMock, patch

from app.modules.email.parsing.claude_parser import ClaudeParser, ParsedEmail
from app.modules.email.parsing.notice_types import ATONoticeType

@pytest.fixture
def parser():
    return ClaudeParser()

@pytest.fixture
def mock_claude_response():
    return {
        "notice_type": "penalty_notice",
        "reference_number": "123456789",
        "due_date": "2026-01-15",
        "amount": 1100.00,
        "client_identifier": {"type": "abn", "value": "12345678901"},
        "required_action": "Pay penalty or request remission",
        "confidence": 92,
    }

@pytest.mark.asyncio
async def test_parse_penalty_notice(parser, mock_claude_response):
    """Test parsing a penalty notice email."""
    with patch.object(parser.client.messages, 'create') as mock_create:
        mock_create.return_value.content = [
            type('obj', (object,), {'text': json.dumps(mock_claude_response)})()
        ]

        result = await parser.parse("Penalty notice content...")

        assert result.notice_type == ATONoticeType.PENALTY_NOTICE
        assert result.amount == 1100.00
        assert result.reference_number == "123456789"
        assert result.confidence == 92
```

### Unit Test: Client Matching

```python
# backend/tests/unit/modules/email/test_client_matching.py
import pytest
from unittest.mock import AsyncMock
from uuid import uuid4

from app.modules.email.matching.service import ClientMatchingService
from app.modules.email.parsing.claude_parser import ClientIdentifier

@pytest.fixture
def mock_client_repo():
    repo = AsyncMock()
    return repo

@pytest.fixture
def matching_service(mock_client_repo):
    return ClientMatchingService(mock_client_repo)

@pytest.mark.asyncio
async def test_match_by_abn_exact(matching_service, mock_client_repo):
    """Test exact ABN matching."""
    client_id = uuid4()
    mock_client_repo.get_by_abn.return_value = type('obj', (object,), {'id': client_id})()

    identifier = ClientIdentifier(type="abn", value="12 345 678 901")
    result = await matching_service.match(identifier, uuid4())

    assert result.client_id == client_id
    assert result.match_type == "abn_exact"
    assert result.confidence == 100
    assert result.requires_triage is False

@pytest.mark.asyncio
async def test_match_by_name_fuzzy(matching_service, mock_client_repo):
    """Test fuzzy name matching."""
    client_id = uuid4()
    mock_client = type('obj', (object,), {'id': client_id, 'name': 'Smith Plumbing Pty Ltd'})()
    mock_client_repo.get_all_with_names.return_value = [mock_client]

    identifier = ClientIdentifier(type="name", value="Smith Plumbing")
    result = await matching_service.match(identifier, uuid4())

    assert result.confidence >= 80
    assert result.requires_triage is False
```

---

## Verification Checklist

- [ ] Claude API key configured
- [ ] OpenAI API key configured (for embeddings)
- [ ] Qdrant running and accessible
- [ ] Parsing task triggered on email.received event
- [ ] Notice types correctly classified
- [ ] ABN matching works with 100% confidence
- [ ] Fuzzy matching triggers triage below 80%
- [ ] Vector embeddings stored per tenant
- [ ] Semantic search returns relevant results
- [ ] Triage queue shows unmatched items

---

## Common Issues

| Issue | Solution |
|-------|----------|
| "Invalid JSON from Claude" | Improve prompt, add error handling |
| "Embedding rate limited" | Batch embeddings, add retry |
| "No clients matched" | Check client data has ABNs populated |
| "Qdrant connection failed" | Verify host/port, check API key |
| "Low parsing confidence" | Review prompt examples, add domain-specific context |
