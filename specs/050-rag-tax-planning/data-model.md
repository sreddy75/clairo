# Data Model: RAG-Grounded Tax Planning

**Feature**: 050-rag-tax-planning
**Date**: 2026-03-31

## Overview

This feature does NOT introduce new database tables. It wires existing models together:
- `TaxPlan` + `TaxPlanMessage` (from spec 049, tax_planning module)
- `KnowledgeSource` + `ContentChunk` + `BM25IndexEntry` (from spec 045, knowledge module)

The only data model change is adding fields to `TaxPlanMessage` to track RAG context.

## Modified Entity: TaxPlanMessage

**Module**: `backend/app/modules/tax_planning/models.py`

### New Fields

| Field | Type | Nullable | Default | Description |
|-------|------|----------|---------|-------------|
| `source_chunks_used` | JSONB | Yes | None | Array of chunk references used in RAG retrieval for this message. Each entry: `{chunk_id, source_type, title, ruling_number, section_ref, relevance_score}` |
| `citation_verification` | JSONB | Yes | None | Citation verification result: `{total_citations, verified_count, unverified_count, verification_rate, details: [{citation, verified, matched_chunk_id}]}` |

### Rationale

Storing the retrieval context and verification result on the message enables:
1. Audit trail — which sources informed which response (FR-001, audit requirement)
2. Debugging — can review what was retrieved vs what was cited
3. UI rendering — frontend reads `citation_verification` to show the badge without a separate API call

## Existing Entities Used (No Changes)

### KnowledgeSource
- Already supports all needed source types: `ato_web`, `ato_ruling`, `legislation`
- Already has `scrape_config` JSONB for URLs, DocIDs, depth settings
- Admin creates sources via existing UI; no changes needed

### ContentChunk
- Already has `entity_types` (array), `topic_tags` (JSONB), `fy_applicable` (JSONB)
- Already has `ruling_number`, `section_ref`, `source_type`, `content_type`
- These metadata fields are used for filtered retrieval (FR-008)

### BM25IndexEntry
- Already tokenized per chunk for hybrid keyword search
- No changes needed — BM25 search works for tax planning queries

## Pinecone Metadata (No Changes)

Vectors in `compliance_knowledge` namespace already store:
- `source_type`, `ruling_number`, `section_ref`, `entity_types`, `topic_tags`
- `text` (truncated to 30KB), `title`, `source_url`
- These fields support the metadata filtering needed for entity-type and topic-aware retrieval

## Data Flow

```
User message
  → QueryRouter classifies (skip if conversational)
  → KnowledgeService.search_knowledge(query, filters={entity_types, topic_tags})
    → Query expansion (synonym + optional LLM)
    → Hybrid search (BM25 + Pinecone semantic)
    → RRF fusion
    → Cross-encoder reranking
    → Top 5 chunks returned
  → TaxPlanningAgent.process_message_streaming(message, reference_material=chunks)
    → System prompt includes reference material
    → Claude generates response with inline citations
    → Tool-use loop for tax calculations (unchanged)
  → CitationVerifier.verify(response, retrieved_chunks)
    → Citation verification result
  → Save TaxPlanMessage with source_chunks_used + citation_verification
  → Stream response + verification badge to frontend
```

## Migration

One Alembic migration to add `source_chunks_used` and `citation_verification` columns to `tax_plan_messages` table. Both nullable JSONB with no default — existing messages remain unchanged.
