# Tenant-Specific Data: Qdrant vs PostgreSQL

**Question**: Should we create per-tenant namespaces in Qdrant for user-specific data?

**Answer**: Yes, but only for specific use cases. Most tenant data stays in PostgreSQL.

---

## Decision Framework

```
WHEN TO USE VECTORS (Qdrant)          WHEN TO USE RELATIONAL (PostgreSQL)
─────────────────────────────────────────────────────────────────────────

✓ Unstructured text                    ✓ Structured/tabular data
✓ Need semantic similarity search      ✓ Need exact filtering/joins
✓ "Find similar to X"                  ✓ "Get all where X = Y"
✓ Natural language queries             ✓ Aggregations, sums, counts
✓ Documents, PDFs, notes               ✓ Transactions, invoices, contacts
✓ Fuzzy matching needed                ✓ Precise lookups needed
```

---

## Tenant Data Classification

### Keep in PostgreSQL (Structured)

| Data Type | Why PostgreSQL |
|-----------|----------------|
| **Transactions** | Structured, need aggregations, filtering by date/amount/category |
| **Invoices** | Structured, need joins to contacts, filtering by status |
| **Contacts** | Structured, need exact lookups by name/ABN |
| **BAS Sessions** | Structured, need status filtering, date queries |
| **Bank Reconciliation** | Structured, need matching algorithms |
| **Payroll Data** | Structured, need calculations |
| **Aggregation Tables** | Pre-computed summaries for AI context |

**These don't benefit from vector search** - you don't ask "find transactions similar to this one" - you ask "show me transactions over $1,000 in December".

### Consider Qdrant (Unstructured/Semantic)

| Data Type | Why Qdrant | Priority |
|-----------|------------|----------|
| **Uploaded Documents** | Receipts, contracts, agreements - need semantic search | P2 (Phase D) |
| **Accountant Notes** | Free-text notes about client - semantic search helpful | P3 |
| **Email Correspondence** | "What did we discuss about their restructure?" | P3 |
| **Chat History** | Find relevant past conversations | P3 |
| **Custom Playbooks** | Accountant's procedures for this client type | P3 |

---

## Recommended Architecture

```
DATA ARCHITECTURE
═══════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────┐
│                         QDRANT                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  SHARED COLLECTIONS (All tenants read):                          │
│  ├── compliance_knowledge    # ATO rules, legislation           │
│  ├── strategic_advisory      # Tax optimization, growth         │
│  ├── industry_knowledge      # Sector-specific content          │
│  ├── business_fundamentals   # Starting/running business        │
│  ├── financial_management    # Cash flow, pricing               │
│  └── people_operations       # HR, hiring                       │
│                                                                  │
│  TENANT COLLECTIONS (Isolated per tenant):                       │
│  └── tenant_{tenant_id}_documents                               │
│      ├── Uploaded PDFs/images (receipts, contracts)             │
│      ├── OCR-extracted text                                      │
│      ├── Accountant notes                                        │
│      └── Custom knowledge additions                              │
│                                                                  │
│  Metadata for filtering:                                         │
│  ├── connection_id (which client within tenant)                 │
│  ├── document_type (receipt, contract, note, etc.)              │
│  ├── upload_date                                                 │
│  └── uploaded_by                                                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                       POSTGRESQL                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  TENANT DATA (Row-level security):                               │
│  ├── xero_connections        # Client organizations             │
│  ├── xero_transactions       # All transactions                 │
│  ├── xero_invoices           # Invoices                         │
│  ├── xero_contacts           # Contacts                         │
│  ├── xero_employees          # Employees                        │
│  ├── xero_bank_transactions  # Bank lines                       │
│  ├── bas_sessions            # BAS preparation                  │
│  └── bas_periods             # BAS periods                      │
│                                                                  │
│  AI CONTEXT TABLES (Pre-computed):                               │
│  ├── client_ai_profile       # Profile summary                  │
│  ├── expense_category_summary                                    │
│  ├── ar_aging_summary                                            │
│  ├── gst_period_summary                                          │
│  ├── contractor_summary                                          │
│  ├── deduction_analysis                                          │
│  └── monthly_trends                                              │
│                                                                  │
│  DOCUMENT METADATA (Qdrant vectors link here):                   │
│  └── documents                                                   │
│      ├── id (UUID)                                               │
│      ├── tenant_id                                               │
│      ├── connection_id                                           │
│      ├── filename                                                │
│      ├── document_type                                           │
│      ├── storage_path (MinIO)                                    │
│      ├── qdrant_point_ids[]  # Links to vector chunks           │
│      ├── upload_date                                             │
│      └── extracted_data (JSON) # Structured data from OCR       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                         MINIO                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Object Storage for original files:                              │
│  └── clairo-documents/                                          │
│      └── {tenant_id}/                                            │
│          └── {connection_id}/                                    │
│              ├── receipts/                                       │
│              ├── contracts/                                      │
│              └── other/                                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## When Tenant Qdrant Namespace Adds Value

### Use Case 1: Document Search (Phase D)

**Scenario**: Business owner uploads receipt photo

```
User: "Find the receipt for the generator I bought last year"

Without vectors:
- Search PostgreSQL: WHERE description ILIKE '%generator%'
- Misses: "Bunnings - Honda EU22i portable power unit"

With vectors:
- Semantic search in tenant_{id}_documents
- Finds receipt even with different wording
- Returns: "Bunnings receipt, $3,299, Honda EU22i generator, March 2024"
```

### Use Case 2: Accountant Notes Search

**Scenario**: Accountant searches client history

```
Accountant: "What did we discuss about restructuring to a company?"

Without vectors:
- Full-text search might miss relevant notes
- Can't find notes that say "incorporating" or "entity change"

With vectors:
- Semantic search finds conceptually related notes
- Returns notes from 6 months ago about "considering company structure"
```

### Use Case 3: Similar Document Finding

**Scenario**: Categorizing new receipt

```
System: "This receipt looks similar to previous 'Tools & Equipment'
        purchases. Suggest category: Tools & Equipment?"

- Vector similarity to previously categorized documents
- Learns from user's categorization patterns
```

---

## When NOT to Use Tenant Vectors

### Anti-Pattern 1: Vectorizing Transactions

❌ Don't do this:
```python
# Bad idea - vectorizing every transaction
for transaction in transactions:
    vector = embed(f"{transaction.description} ${transaction.amount}")
    qdrant.upsert(collection="tenant_transactions", ...)
```

**Why it's wrong:**
- Transactions are structured data
- You need exact filters: `date >= X AND amount > Y AND category = Z`
- Vector search would be slower and less accurate
- 10,000 transactions × embedding = expensive and wasteful

✅ Do this instead:
```python
# Store structured, aggregate for AI context
expense_summary = db.query("""
    SELECT category, SUM(amount), COUNT(*)
    FROM transactions
    WHERE date >= :start
    GROUP BY category
""")
```

### Anti-Pattern 2: Vectorizing Invoice Line Items

❌ Don't do this:
- Embedding every invoice line
- Searching "find invoices like this one"

✅ Do this instead:
- Store structured in PostgreSQL
- Filter by customer, date, status, amount
- Only embed if you have PDF invoices for OCR search

---

## Tenant Collection Strategy

### Option A: Single Collection with Tenant Filter (Simple)

```python
# One collection, filter by tenant_id
qdrant.search(
    collection_name="tenant_documents",
    query_vector=query_embedding,
    query_filter=Filter(
        must=[
            FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id)),
            FieldCondition(key="connection_id", match=MatchValue(value=connection_id))
        ]
    )
)
```

**Pros:**
- Simpler to manage
- Single collection to maintain

**Cons:**
- All tenant data in one collection (isolation concern)
- Filter on every query

### Option B: Collection Per Tenant (Recommended)

```python
# Separate collection per tenant
collection_name = f"tenant_{tenant_id}_documents"

qdrant.search(
    collection_name=collection_name,
    query_vector=query_embedding,
    query_filter=Filter(
        must=[
            FieldCondition(key="connection_id", match=MatchValue(value=connection_id))
        ]
    )
)
```

**Pros:**
- Complete tenant isolation
- No risk of cross-tenant data leakage
- Can delete entire tenant easily
- Better for compliance (data sovereignty)

**Cons:**
- More collections to manage
- Need to handle collection lifecycle

### Recommendation: **Option B - Collection Per Tenant**

For tenant-uploaded documents, isolation is critical. Each tenant gets their own collection.

---

## Implementation Plan

### Phase B (Current - Knowledge Base)

Focus on **shared knowledge only**:
- compliance_knowledge
- strategic_advisory
- industry_knowledge
- business_fundamentals
- financial_management
- people_operations

**No tenant vectors yet** - keep scope focused.

### Phase D (Business Owner Experience)

Add tenant document collections:

```python
# When tenant first uploads a document
async def ensure_tenant_collection(tenant_id: UUID):
    collection_name = f"tenant_{tenant_id}_documents"

    if not await qdrant.collection_exists(collection_name):
        await qdrant.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=512,  # voyage-3.5-lite
                distance=Distance.COSINE
            )
        )

    return collection_name
```

```python
# Document upload flow
async def process_uploaded_document(
    tenant_id: UUID,
    connection_id: UUID,
    file: UploadFile
):
    # 1. Store original in MinIO
    storage_path = await minio.upload(file, tenant_id, connection_id)

    # 2. Create metadata in PostgreSQL
    doc = await db.create(Document(
        tenant_id=tenant_id,
        connection_id=connection_id,
        filename=file.filename,
        storage_path=storage_path,
        document_type=detect_type(file)
    ))

    # 3. Extract text (OCR if image/PDF)
    text = await extract_text(file)

    # 4. Chunk and embed
    chunks = chunk_text(text)
    embeddings = await voyage.embed(chunks)

    # 5. Store vectors in tenant collection
    collection = f"tenant_{tenant_id}_documents"
    point_ids = await qdrant.upsert(
        collection_name=collection,
        points=[
            PointStruct(
                id=uuid4(),
                vector=emb,
                payload={
                    "document_id": str(doc.id),
                    "connection_id": str(connection_id),
                    "chunk_index": i,
                    "text": chunk,
                    "document_type": doc.document_type
                }
            )
            for i, (chunk, emb) in enumerate(zip(chunks, embeddings))
        ]
    )

    # 6. Link vector IDs back to document
    doc.qdrant_point_ids = point_ids
    await db.commit()

    return doc
```

---

## Summary: Where Data Lives

| Data Type | Storage | Why |
|-----------|---------|-----|
| **Xero transactions** | PostgreSQL | Structured, need aggregations |
| **Xero invoices** | PostgreSQL | Structured, need joins/filters |
| **BAS calculations** | PostgreSQL | Structured, need precise math |
| **AI context summaries** | PostgreSQL | Pre-computed aggregations |
| **ATO compliance rules** | Qdrant (shared) | Semantic search needed |
| **Strategic advisory** | Qdrant (shared) | Semantic search needed |
| **Industry knowledge** | Qdrant (shared) | Semantic search needed |
| **Uploaded documents** | MinIO + Qdrant (tenant) | Files in object storage, text chunks in vectors |
| **Accountant notes** | PostgreSQL + Qdrant (tenant) | Metadata in PG, semantic search in Qdrant |
| **OCR extracted data** | PostgreSQL (JSON) + Qdrant | Structured fields in PG, full text in vectors |

---

## Key Decisions

| Question | Decision | Rationale |
|----------|----------|-----------|
| Tenant vectors in Qdrant? | **Yes, but only for documents** | Semantic search over unstructured content |
| Transactions in vectors? | **No** | Structured data, use PostgreSQL |
| One collection or per-tenant? | **Per-tenant collections** | Isolation, compliance, easy deletion |
| When to implement? | **Phase D** (Business Owner) | Focus on knowledge base first |
| What's the trigger? | **Document upload feature** | First need for tenant vectors |

---

## Cost Implications

### Shared Knowledge (Phase B)
- ~1-5M vectors
- Storage: ~2-10 GB
- One-time ingestion cost

### Tenant Documents (Phase D)
- Estimate: 100-500 documents per client
- Average: 5 chunks per document
- Per tenant: 500-2,500 vectors
- 100 tenants: 50K-250K vectors
- Storage: ~100-500 MB
- Manageable scale

### Bottom Line
Tenant vectors add minimal overhead and significant value for document search.
But don't over-engineer - implement when the feature requires it (Phase D).
