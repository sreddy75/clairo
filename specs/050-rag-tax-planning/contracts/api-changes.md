# API Contract Changes: RAG-Grounded Tax Planning

**Feature**: 050-rag-tax-planning
**Date**: 2026-03-31

## Overview

No new endpoints are introduced. Two existing endpoints have modified response payloads.

## Modified Endpoints

### 1. POST /api/v1/tax-plans/{plan_id}/chat/stream

**Change**: Response SSE events include citation verification data.

**New SSE event type**: `verification`

```json
{
  "type": "verification",
  "data": {
    "total_citations": 3,
    "verified_count": 3,
    "unverified_count": 0,
    "verification_rate": 1.0,
    "status": "verified"
  }
}
```

**`status` values**:
- `"verified"` — all citations matched knowledge base content (verification_rate >= 0.9)
- `"partially_verified"` — some citations matched (0.5 <= verification_rate < 0.9)
- `"unverified"` — most citations could not be matched (verification_rate < 0.5)
- `"no_citations"` — response contains no citations (general advice)

**Event order**: `thinking` → `content` → `scenario` (if any) → `verification` → `done`

**Backward compatibility**: The `verification` event is new. Existing clients that don't handle it will simply ignore it (SSE clients skip unknown event types).

### 2. GET /api/v1/tax-plans/{plan_id}/messages

**Change**: Message response objects include new optional fields.

**New fields on message response**:

```json
{
  "id": "uuid",
  "role": "assistant",
  "content": "...",
  "created_at": "...",
  "scenario_ids": [],
  "token_count": 450,
  "source_chunks_used": [
    {
      "chunk_id": "uuid",
      "source_type": "ato_ruling",
      "title": "TR 98/1 - Deductibility of prepaid expenses",
      "ruling_number": "TR 98/1",
      "section_ref": null,
      "relevance_score": 0.87
    }
  ],
  "citation_verification": {
    "total_citations": 2,
    "verified_count": 2,
    "unverified_count": 0,
    "verification_rate": 1.0,
    "status": "verified"
  }
}
```

**Backward compatibility**: Both fields are nullable. Existing messages (before this feature) will have `null` for both fields. Frontend should handle null gracefully.

## No New Endpoints Required

The following operations use existing endpoints with no changes:
- Knowledge source CRUD: `POST/GET/PATCH/DELETE /api/v1/admin/knowledge/sources`
- Ingestion trigger: `POST /api/v1/admin/knowledge/sources/{source_id}/ingest`
- Ingestion job monitoring: `GET /api/v1/admin/knowledge/jobs`
- Search testing: `POST /api/v1/knowledge/search`
