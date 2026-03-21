# Research: ATO Correspondence Parsing

**Feature**: 027-ato-correspondence-parsing
**Date**: 2026-01-01
**Status**: Complete

---

## Research Tasks

### 1. Claude Structured Output

**Decision**: Use Claude 3.5 Sonnet with JSON mode for structured extraction

**Model Comparison**:

| Model | Speed | Cost | Accuracy | Notes |
|-------|-------|------|----------|-------|
| Claude 3.5 Sonnet | Fast | $3/$15 per 1M tokens | High | Best balance |
| Claude 3 Opus | Slow | $15/$75 per 1M tokens | Highest | Overkill for parsing |
| Claude 3.5 Haiku | Fastest | $0.25/$1.25 per 1M tokens | Good | May miss nuances |

**Structured Output Configuration**:

```python
from anthropic import Anthropic

client = Anthropic()

response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    messages=[
        {
            "role": "user",
            "content": f"""Extract structured information from this ATO email.

<email>
{email_content}
</email>

Return a JSON object with these fields:
- notice_type: one of {NOTICE_TYPES}
- reference_number: ATO reference if present, null otherwise
- due_date: in YYYY-MM-DD format if present, null otherwise
- amount: numeric amount if present (for penalties/debts), null otherwise
- client_identifier: object with {{type: "abn"|"tfn"|"name", value: string}}
- required_action: brief summary of what action is needed
- confidence: 0-100 score for overall extraction confidence

Return ONLY valid JSON, no other text."""
        }
    ]
)
```

**Token Usage Estimate**:
- Average ATO email: ~500 tokens input
- Structured output: ~200 tokens output
- Cost per email: ~$0.002 (Sonnet pricing)
- 1,000 emails/month: ~$2/tenant

**Rationale**: Claude 3.5 Sonnet provides excellent accuracy for structured extraction at reasonable cost. JSON mode ensures parseable output.

---

### 2. Notice Type Taxonomy

**Decision**: Implement hierarchical notice type classification

**Primary Categories**:

```python
class ATONoticeType(str, Enum):
    # Activity Statements
    ACTIVITY_STATEMENT_REMINDER = "activity_statement_reminder"
    ACTIVITY_STATEMENT_CONFIRMATION = "activity_statement_confirmation"
    ACTIVITY_STATEMENT_AMENDMENT = "activity_statement_amendment"

    # Compliance
    AUDIT_NOTICE = "audit_notice"
    AUDIT_OUTCOME = "audit_outcome"
    INFORMATION_REQUEST = "information_request"

    # Debt & Penalties
    PENALTY_NOTICE = "penalty_notice"
    DEBT_NOTICE = "debt_notice"
    PAYMENT_REMINDER = "payment_reminder"
    PAYMENT_PLAN = "payment_plan"

    # Running Balance
    RUNNING_BALANCE_ACCOUNT = "running_balance_account"
    CREDIT_NOTICE = "credit_notice"

    # Tax Returns
    TAX_RETURN_REMINDER = "tax_return_reminder"
    TAX_ASSESSMENT = "tax_assessment"
    TAX_AMENDMENT = "tax_amendment"

    # Obligations
    SUPERANNUATION_NOTICE = "superannuation_notice"
    PAYG_WITHHOLDING = "payg_withholding"
    FBT_NOTICE = "fringe_benefits_tax"

    # Other
    REGISTRATION = "registration"
    GENERAL = "general"
    UNKNOWN = "unknown"
```

**Category Metadata**:

```python
NOTICE_TYPE_METADATA = {
    ATONoticeType.AUDIT_NOTICE: {
        "urgency": "high",
        "typical_response_days": 28,
        "requires_action": True,
        "category": "compliance",
    },
    ATONoticeType.PENALTY_NOTICE: {
        "urgency": "high",
        "typical_response_days": 21,
        "requires_action": True,
        "category": "debt",
    },
    ATONoticeType.ACTIVITY_STATEMENT_REMINDER: {
        "urgency": "medium",
        "typical_response_days": 14,
        "requires_action": True,
        "category": "lodgement",
    },
    # ... etc
}
```

**Rationale**: Granular notice types enable accurate prioritization and workflow routing. Metadata supports automatic urgency classification.

---

### 3. Client Matching Strategy

**Decision**: Two-tier matching with confidence scoring

**Tier 1: ABN Exact Match**

```python
async def match_by_abn(abn: str, tenant_id: UUID) -> tuple[Client | None, float]:
    """Match client by ABN with 100% confidence."""
    # Normalize ABN (remove spaces, validate format)
    normalized = normalize_abn(abn)
    if not is_valid_abn(normalized):
        return None, 0.0

    client = await client_repo.get_by_abn(normalized, tenant_id)
    if client:
        return client, 100.0

    # Check historical ABNs
    client = await client_repo.get_by_historical_abn(normalized, tenant_id)
    if client:
        return client, 95.0

    return None, 0.0
```

**Tier 2: Fuzzy Name Match**

```python
from rapidfuzz import fuzz, process

async def match_by_name(name: str, tenant_id: UUID) -> tuple[Client | None, float]:
    """Match client by fuzzy name matching."""
    clients = await client_repo.get_all_names(tenant_id)

    # Use token_set_ratio for better handling of word order differences
    matches = process.extract(
        name,
        {c.id: c.name for c in clients},
        scorer=fuzz.token_set_ratio,
        limit=3,
    )

    if matches and matches[0][1] >= 80:
        client_id, score, _ = matches[0]
        client = await client_repo.get(client_id)
        return client, score

    return None, matches[0][1] if matches else 0.0
```

**Matching Algorithm**:

```python
async def match_client(
    identifier: ClientIdentifier,
    tenant_id: UUID
) -> MatchResult:
    """Match extracted identifier to a client."""

    # Try ABN first (highest confidence)
    if identifier.type == "abn":
        client, confidence = await match_by_abn(identifier.value, tenant_id)
        if client:
            return MatchResult(
                client_id=client.id,
                match_type="abn_exact",
                confidence=confidence,
                requires_triage=False,
            )

    # Try TFN if available
    if identifier.type == "tfn":
        client, confidence = await match_by_tfn(identifier.value, tenant_id)
        if client:
            return MatchResult(
                client_id=client.id,
                match_type="tfn_exact",
                confidence=confidence,
                requires_triage=False,
            )

    # Fallback to name matching
    if identifier.type == "name" or identifier.value:
        name = identifier.value if identifier.type == "name" else identifier.value
        client, confidence = await match_by_name(name, tenant_id)

        requires_triage = confidence < 80
        return MatchResult(
            client_id=client.id if client and not requires_triage else None,
            match_type="name_fuzzy",
            confidence=confidence,
            requires_triage=requires_triage,
            suggested_client_id=client.id if client else None,
        )

    return MatchResult(
        client_id=None,
        match_type="none",
        confidence=0,
        requires_triage=True,
    )
```

**Rationale**: ABN provides definitive matching; fuzzy name matching handles cases where ABN isn't in the email. 80% threshold balances automation with accuracy.

---

### 4. Vector Storage with Qdrant

**Decision**: Per-tenant collections with metadata filtering

**Collection Structure**:

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

async def create_tenant_collection(tenant_id: UUID):
    """Create a vector collection for a tenant."""
    collection_name = f"ato_correspondence_{tenant_id}"

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=1536,  # OpenAI text-embedding-3-small dimension
            distance=Distance.COSINE,
        ),
    )

async def store_correspondence_vector(
    correspondence_id: UUID,
    content: str,
    metadata: dict,
    tenant_id: UUID,
):
    """Store email content with embedding."""
    collection_name = f"ato_correspondence_{tenant_id}"

    # Generate embedding
    embedding = await generate_embedding(content)

    # Store in Qdrant
    client.upsert(
        collection_name=collection_name,
        points=[
            PointStruct(
                id=str(correspondence_id),
                vector=embedding,
                payload={
                    "correspondence_id": str(correspondence_id),
                    "notice_type": metadata["notice_type"],
                    "client_id": str(metadata["client_id"]) if metadata.get("client_id") else None,
                    "received_at": metadata["received_at"].isoformat(),
                    "subject": metadata["subject"],
                },
            )
        ],
    )
```

**Search Implementation**:

```python
async def semantic_search(
    query: str,
    tenant_id: UUID,
    filters: dict | None = None,
    limit: int = 10,
) -> list[SearchResult]:
    """Search correspondence by semantic similarity."""
    collection_name = f"ato_correspondence_{tenant_id}"

    # Generate query embedding
    query_embedding = await generate_embedding(query)

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
    results = client.search(
        collection_name=collection_name,
        query_vector=query_embedding,
        query_filter=Filter(must=filter_conditions) if filter_conditions else None,
        limit=limit,
    )

    return [
        SearchResult(
            correspondence_id=UUID(r.payload["correspondence_id"]),
            score=r.score,
            notice_type=r.payload["notice_type"],
        )
        for r in results
    ]
```

**Rationale**: Per-tenant collections ensure data isolation. Metadata filtering enables efficient pre-filtering before vector search.

---

### 5. Embedding Model Selection

**Decision**: Use OpenAI text-embedding-3-small

**Model Comparison**:

| Model | Dimensions | Cost | Quality | Notes |
|-------|------------|------|---------|-------|
| text-embedding-3-small | 1536 | $0.02/1M tokens | Good | Best value |
| text-embedding-3-large | 3072 | $0.13/1M tokens | Better | Overkill |
| Claude embeddings | N/A | N/A | N/A | Not available |
| Cohere embed-v3 | 1024 | $0.10/1M tokens | Good | Alternative |

**Implementation**:

```python
from openai import AsyncOpenAI

client = AsyncOpenAI()

async def generate_embedding(text: str) -> list[float]:
    """Generate embedding for text content."""
    response = await client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return response.data[0].embedding
```

**Cost Estimate**:
- Average email: ~500 tokens
- Cost per embedding: ~$0.00001
- 1,000 emails/month: ~$0.01/tenant

**Rationale**: text-embedding-3-small provides excellent quality at minimal cost. Dimensions (1536) are well-supported by Qdrant.

---

### 6. PDF Text Extraction

**Decision**: Use pdfplumber with OCR fallback

**Library Comparison**:

| Library | Text Extraction | Tables | OCR | Notes |
|---------|-----------------|--------|-----|-------|
| pdfplumber | Excellent | Yes | No | Best for native PDFs |
| PyPDF2 | Good | No | No | Faster, less accurate |
| pdf2image + pytesseract | N/A | N/A | Yes | For scanned PDFs |
| pymupdf (fitz) | Good | Yes | No | Alternative |

**Implementation**:

```python
import pdfplumber
from pdf2image import convert_from_bytes
import pytesseract

async def extract_pdf_text(pdf_content: bytes) -> str:
    """Extract text from PDF, with OCR fallback."""

    # Try native text extraction first
    with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
        text_parts = []
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)

    if text_parts:
        return "\n\n".join(text_parts)

    # Fallback to OCR for scanned PDFs
    images = convert_from_bytes(pdf_content)
    ocr_parts = []
    for image in images:
        text = pytesseract.image_to_string(image)
        if text.strip():
            ocr_parts.append(text)

    return "\n\n".join(ocr_parts)
```

**Rationale**: ATO PDFs are typically native (not scanned), so pdfplumber handles most cases. OCR fallback ensures coverage for any scanned documents.

---

### 7. Parsing Prompt Engineering

**Decision**: Few-shot prompting with ATO-specific examples

**Prompt Template**:

```python
PARSING_PROMPT = """You are an expert at extracting structured information from Australian Taxation Office (ATO) emails and notices.

Analyze the following email content and extract key information.

<email>
{email_content}
</email>

Extract the following fields. If a field is not present, use null.

## Notice Types (choose one):
- activity_statement_reminder: BAS/IAS lodgement reminders
- activity_statement_confirmation: Lodgement confirmations
- audit_notice: Compliance audit notifications
- audit_outcome: Results of audits
- penalty_notice: Penalty assessments
- debt_notice: Outstanding debt notifications
- payment_reminder: Payment due reminders
- running_balance_account: Account balance statements
- tax_return_reminder: Tax return due reminders
- tax_assessment: Tax assessments
- superannuation_notice: Super-related notices
- payg_withholding: PAYG withholding notices
- general: Other ATO correspondence

## Examples:

Example 1 - Activity Statement Reminder:
Input: "Your activity statement for the period ending 31 December 2025 is due on 28 February 2026. ABN: 12 345 678 901"
Output: {{"notice_type": "activity_statement_reminder", "reference_number": null, "due_date": "2026-02-28", "amount": null, "client_identifier": {{"type": "abn", "value": "12345678901"}}, "required_action": "Lodge activity statement by due date", "confidence": 95}}

Example 2 - Penalty Notice:
Input: "We have applied a failure to lodge penalty of $1,100 to your account for the activity statement period ending 30 September 2025. Reference: 123456789. Entity: Smith Plumbing Pty Ltd."
Output: {{"notice_type": "penalty_notice", "reference_number": "123456789", "due_date": null, "amount": 1100.00, "client_identifier": {{"type": "name", "value": "Smith Plumbing Pty Ltd"}}, "required_action": "Pay penalty or request remission", "confidence": 92}}

## Your Response:
Return ONLY a valid JSON object with these exact fields:
- notice_type (string): one of the types listed above
- reference_number (string or null): ATO reference number
- due_date (string or null): date in YYYY-MM-DD format
- amount (number or null): dollar amount if applicable
- client_identifier (object or null): {{"type": "abn"|"tfn"|"name", "value": "string"}}
- required_action (string): brief description of action needed
- confidence (number): 0-100 confidence score

JSON Response:"""
```

**Rationale**: Few-shot examples improve accuracy for domain-specific content. Explicit type definitions ensure consistent output.

---

### 8. Error Handling & Retry Strategy

**Decision**: Exponential backoff with fallback parsing

**Implementation**:

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
)
async def parse_email_with_retry(content: str) -> ParsedEmail:
    """Parse email with automatic retry on transient failures."""
    try:
        return await claude_parser.parse(content)
    except JSONDecodeError as e:
        # If Claude returns invalid JSON, try to extract what we can
        return await fallback_parser.parse(content)
    except Exception as e:
        logger.error(f"Parsing failed: {e}")
        raise
```

**Fallback Parser**:

```python
async def fallback_parse(content: str) -> ParsedEmail:
    """Basic regex-based fallback when AI parsing fails."""
    import re

    # Extract ABN
    abn_match = re.search(r'\b(\d{2}\s?\d{3}\s?\d{3}\s?\d{3})\b', content)
    abn = abn_match.group(1).replace(" ", "") if abn_match else None

    # Extract dates
    date_match = re.search(r'\b(\d{1,2})\s*(January|February|March|April|May|June|July|August|September|October|November|December)\s*(\d{4})\b', content, re.I)

    # Extract amounts
    amount_match = re.search(r'\$[\d,]+(?:\.\d{2})?', content)

    return ParsedEmail(
        notice_type=ATONoticeType.UNKNOWN,
        reference_number=None,
        due_date=parse_date(date_match) if date_match else None,
        amount=parse_amount(amount_match) if amount_match else None,
        client_identifier=ClientIdentifier(type="abn", value=abn) if abn else None,
        required_action="Review email manually",
        confidence=30,  # Low confidence for fallback
    )
```

**Rationale**: Retry handles transient API failures. Fallback parser ensures emails aren't lost if AI parsing fails.

---

## Summary of Decisions

| Area | Decision |
|------|----------|
| AI Model | Claude 3.5 Sonnet for parsing |
| Structured Output | JSON mode with schema validation |
| Embedding Model | OpenAI text-embedding-3-small |
| Vector Store | Qdrant with per-tenant collections |
| Client Matching | ABN exact → Fuzzy name, 80% threshold |
| PDF Extraction | pdfplumber + OCR fallback |
| Notice Types | 20+ granular types with metadata |
| Error Handling | Exponential backoff + regex fallback |

---

## Sources

- [Claude API Documentation](https://docs.anthropic.com/en/docs)
- [OpenAI Embeddings](https://platform.openai.com/docs/guides/embeddings)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [rapidfuzz Documentation](https://rapidfuzz.github.io/RapidFuzz/)
- [pdfplumber Documentation](https://github.com/jsvine/pdfplumber)
- [ATO Email Formats](https://www.ato.gov.au/) (observed patterns)
