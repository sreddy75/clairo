# Quickstart: AI Interaction Capture & Learning

**Spec**: 029-ai-interaction-capture-learning
**Purpose**: Developer guide for implementing AI interaction capture, pattern analysis, knowledge gap detection, and fine-tuning dataset curation.

---

## Prerequisites

- Python 3.12+
- PostgreSQL 16 with existing tenant/user tables
- Qdrant for vector storage
- S3/MinIO for raw log storage
- Redis for real-time metrics
- Celery for background jobs
- Anthropic API key (for classification)
- OpenAI API key (for embeddings)

---

## 1. Capture Middleware

### Middleware Implementation

```python
# backend/app/modules/ai_learning/capture/middleware.py
import hashlib
import time
from uuid import UUID
from datetime import datetime
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.modules.ai_learning.models import AIInteraction, SessionType
from app.modules.ai_learning.capture.classifier import classify_query
from app.modules.ai_learning.capture.embeddings import queue_embedding_generation
from app.core.context import get_current_user, get_current_tenant


class AIInteractionMiddleware(BaseHTTPMiddleware):
    """Middleware to capture all AI interactions."""

    AI_ENDPOINTS = [
        "/api/v1/chat",
        "/api/v1/insights/generate",
        "/api/v1/magic-zone",
        "/api/v1/bas/ai-assist",
    ]

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        # Skip non-AI endpoints
        if not self._is_ai_endpoint(request.url.path):
            return await call_next(request)

        # Extract query before processing
        body = await request.body()
        query_data = await self._extract_query(body)

        if not query_data:
            return await call_next(request)

        # Start timing
        start_time = time.time()

        # Process request
        response = await call_next(request)

        # Calculate latency
        latency_ms = int((time.time() - start_time) * 1000)

        # Extract response (need to read and reconstruct)
        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk

        response_data = await self._extract_response(response_body)

        # Capture interaction (async, don't block response)
        await self._capture_interaction(
            request=request,
            query_data=query_data,
            response_data=response_data,
            latency_ms=latency_ms,
        )

        # Reconstruct response
        return Response(
            content=response_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )

    def _is_ai_endpoint(self, path: str) -> bool:
        return any(path.startswith(ep) for ep in self.AI_ENDPOINTS)

    async def _capture_interaction(
        self,
        request: Request,
        query_data: dict,
        response_data: dict,
        latency_ms: int,
    ) -> None:
        """Capture interaction to database."""
        user = get_current_user()
        tenant = get_current_tenant()

        if not user or not tenant:
            return

        # Get tenant settings for consent
        settings = await self._get_tenant_settings(tenant.id)

        # Auto-classify query (async)
        category, subcategory = await classify_query(query_data["query"])

        # Create interaction record
        interaction = AIInteraction(
            tenant_id=tenant.id,
            user_id=user.id,
            client_id=query_data.get("client_id"),
            conversation_id=query_data.get("conversation_id"),

            # Query context
            query_text=query_data["query"],
            query_hash=hashlib.sha256(query_data["query"].encode()).hexdigest(),
            query_tokens=len(query_data["query"].split()),
            category=category,
            subcategory=subcategory,

            # Session context
            session_type=self._detect_session_type(request.url.path),
            session_id=query_data.get("session_id"),

            # Response context
            response_text=response_data.get("response"),
            response_tokens=len(response_data.get("response", "").split()),
            response_latency_ms=latency_ms,
            model_version=response_data.get("model", "unknown"),

            # RAG context
            sources_count=response_data.get("sources_count"),
            sources_avg_score=response_data.get("sources_avg_score"),

            # Confidence
            confidence_score=response_data.get("confidence"),

            # Privacy
            consent_training=settings.contribute_to_training,
        )

        await self.session.add(interaction)
        await self.session.commit()

        # Queue async tasks
        await queue_embedding_generation(interaction.id, query_data["query"])
        await self._upload_raw_log(interaction.id, query_data, response_data)

    def _detect_session_type(self, path: str) -> str:
        if "/chat" in path:
            return SessionType.CHAT
        elif "/bas" in path:
            return SessionType.BAS_PREP
        elif "/insights" in path:
            return SessionType.INSIGHT_REVIEW
        elif "/magic-zone" in path:
            return SessionType.MAGIC_ZONE
        return SessionType.CHAT
```

---

## 2. Query Classification

### Classifier Service

```python
# backend/app/modules/ai_learning/capture/classifier.py
import anthropic
from functools import lru_cache

from app.config import settings


CLASSIFY_PROMPT = """
You are classifying accountant queries for a BAS management system.

CATEGORIES:
- COMPLIANCE: Tax rules, ATO requirements, BAS/GST/PAYG/Super questions
- STRATEGY: Business advice, cash flow, growth, forecasting, planning
- DATA_QUALITY: Reconciliation issues, missing data, discrepancies, errors
- WORKFLOW: Tasks, reminders, notifications, process questions

SUBCATEGORIES by category:
- COMPLIANCE: GST, PAYG, SUPER, FBT, CGT, INCOME_TAX, LODGEMENT
- STRATEGY: CASHFLOW, GROWTH, PRICING, BENCHMARKING, FORECASTING
- DATA_QUALITY: RECONCILIATION, MISSING_DATA, DUPLICATE, VARIANCE
- WORKFLOW: TASKS, DEADLINES, NOTIFICATIONS, SETTINGS

Examples:
- "What's the GST credit for this invoice?" → COMPLIANCE / GST
- "How can I improve this client's cash flow?" → STRATEGY / CASHFLOW
- "Why doesn't this bank balance match?" → DATA_QUALITY / RECONCILIATION
- "Remind me about the BAS deadline" → WORKFLOW / DEADLINES

Query: {query}

Return ONLY valid JSON: {{"category": "...", "subcategory": "..." or null}}
"""


class QueryClassifier:
    """Classify queries using Claude Haiku."""

    def __init__(self):
        self.client = anthropic.AsyncAnthropic(
            api_key=settings.ANTHROPIC_API_KEY
        )
        self.model = "claude-3-5-haiku-20241022"

    async def classify(self, query: str) -> tuple[str, str | None]:
        """Classify a query into category and subcategory."""
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=100,
                messages=[{
                    "role": "user",
                    "content": CLASSIFY_PROMPT.format(query=query[:500]),  # Truncate
                }],
            )

            result = json.loads(response.content[0].text)
            return result["category"], result.get("subcategory")

        except Exception as e:
            logger.warning(f"Classification failed: {e}")
            return "UNKNOWN", None


# Singleton instance
_classifier = None


async def classify_query(query: str) -> tuple[str, str | None]:
    """Classify a query (module-level function)."""
    global _classifier
    if _classifier is None:
        _classifier = QueryClassifier()
    return await _classifier.classify(query)
```

---

## 3. Embedding Generation

### Async Embedding Service

```python
# backend/app/modules/ai_learning/capture/embeddings.py
from uuid import UUID
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct

from app.config import settings
from app.modules.ai_learning.repository import AIInteractionRepository


class QueryEmbedder:
    """Generate and store query embeddings."""

    def __init__(self):
        self.openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.qdrant = AsyncQdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
        )
        self.collection = "ai_queries"
        self.model = "text-embedding-3-small"
        self.dimensions = 1536

    async def embed_and_store(
        self,
        interaction_id: UUID,
        query: str,
        tenant_id: UUID,
    ) -> str:
        """Generate embedding and store in Qdrant."""
        # Generate embedding
        response = await self.openai.embeddings.create(
            model=self.model,
            input=query,
            dimensions=self.dimensions,
        )
        embedding = response.data[0].embedding

        # Store in Qdrant
        point_id = str(interaction_id)
        await self.qdrant.upsert(
            collection_name=self.collection,
            points=[
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        "interaction_id": str(interaction_id),
                        "tenant_id": str(tenant_id),
                        "query": query[:200],  # Truncated for payload
                    },
                )
            ],
        )

        # Update interaction with embedding ID
        repo = AIInteractionRepository()
        await repo.update_embedding_id(interaction_id, point_id)

        return point_id

    async def find_similar(
        self,
        query: str,
        tenant_id: UUID | None = None,
        top_k: int = 10,
    ) -> list[dict]:
        """Find similar queries."""
        # Generate query embedding
        response = await self.openai.embeddings.create(
            model=self.model,
            input=query,
            dimensions=self.dimensions,
        )
        embedding = response.data[0].embedding

        # Search Qdrant
        filter_conditions = None
        if tenant_id:
            filter_conditions = {
                "must": [{"key": "tenant_id", "match": {"value": str(tenant_id)}}]
            }

        results = await self.qdrant.search(
            collection_name=self.collection,
            query_vector=embedding,
            limit=top_k,
            query_filter=filter_conditions,
        )

        return [
            {
                "interaction_id": r.payload["interaction_id"],
                "query": r.payload["query"],
                "score": r.score,
            }
            for r in results
        ]


# Celery task for async embedding
from app.tasks.celery_app import celery_app


@celery_app.task
async def generate_embedding_task(interaction_id: str, query: str, tenant_id: str):
    """Celery task for embedding generation."""
    embedder = QueryEmbedder()
    await embedder.embed_and_store(
        interaction_id=UUID(interaction_id),
        query=query,
        tenant_id=UUID(tenant_id),
    )


async def queue_embedding_generation(
    interaction_id: UUID,
    query: str,
    tenant_id: UUID,
) -> None:
    """Queue embedding generation for background processing."""
    generate_embedding_task.delay(
        str(interaction_id),
        query,
        str(tenant_id),
    )
```

---

## 4. Feedback Collection

### Feedback UI Component

```tsx
// frontend/src/components/ai/FeedbackButtons.tsx
import { useState } from 'react';
import { ThumbsUp, ThumbsDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { submitAIFeedback } from '@/lib/api/ai-learning';

interface FeedbackButtonsProps {
  interactionId: string;
  onFeedbackSubmitted?: () => void;
}

export function FeedbackButtons({
  interactionId,
  onFeedbackSubmitted,
}: FeedbackButtonsProps) {
  const [submitted, setSubmitted] = useState<'up' | 'down' | null>(null);
  const [showCommentDialog, setShowCommentDialog] = useState(false);
  const [comment, setComment] = useState('');
  const [loading, setLoading] = useState(false);

  const handleFeedback = async (rating: 1 | 5) => {
    if (submitted) return;

    if (rating === 1) {
      // Show comment dialog for negative feedback
      setShowCommentDialog(true);
      return;
    }

    await submitFeedback(rating);
  };

  const submitFeedback = async (rating: 1 | 5, feedbackComment?: string) => {
    setLoading(true);
    try {
      await submitAIFeedback(interactionId, {
        rating,
        comment: feedbackComment,
      });
      setSubmitted(rating === 5 ? 'up' : 'down');
      onFeedbackSubmitted?.();
    } catch (error) {
      console.error('Failed to submit feedback:', error);
    } finally {
      setLoading(false);
      setShowCommentDialog(false);
    }
  };

  if (submitted) {
    return (
      <div className="text-sm text-muted-foreground">
        Thanks for your feedback!
      </div>
    );
  }

  return (
    <>
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">Was this helpful?</span>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => handleFeedback(5)}
          disabled={loading}
        >
          <ThumbsUp className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => handleFeedback(1)}
          disabled={loading}
        >
          <ThumbsDown className="h-4 w-4" />
        </Button>
      </div>

      <Dialog open={showCommentDialog} onOpenChange={setShowCommentDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>What could be improved?</DialogTitle>
          </DialogHeader>
          <Textarea
            placeholder="Optional: Tell us what went wrong..."
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            rows={3}
          />
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              onClick={() => submitFeedback(1)}
              disabled={loading}
            >
              Skip
            </Button>
            <Button
              onClick={() => submitFeedback(1, comment)}
              disabled={loading}
            >
              Submit
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
```

---

## 5. Pattern Analysis Job

### Daily Pattern Clustering

```python
# backend/app/tasks/ai_learning/pattern_analysis.py
from datetime import datetime, timedelta
from uuid import UUID

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_similarity
from qdrant_client import QdrantClient

from app.modules.ai_learning.models import QueryPattern
from app.modules.ai_learning.repository import (
    AIInteractionRepository,
    QueryPatternRepository,
)
from app.tasks.celery_app import celery_app


@celery_app.task
async def run_pattern_analysis(days_back: int = 7, min_cluster_size: int = 50):
    """Daily job to identify query patterns."""
    interaction_repo = AIInteractionRepository()
    pattern_repo = QueryPatternRepository()
    qdrant = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)

    # 1. Fetch recent interactions with embeddings
    since = datetime.utcnow() - timedelta(days=days_back)
    interactions = await interaction_repo.get_with_embeddings(since=since)

    if len(interactions) < min_cluster_size:
        logger.info(f"Not enough interactions ({len(interactions)}) for pattern analysis")
        return

    # 2. Fetch embeddings from Qdrant
    point_ids = [i.query_embedding_id for i in interactions if i.query_embedding_id]
    points = await qdrant.retrieve(
        collection_name="ai_queries",
        ids=point_ids,
        with_vectors=True,
    )

    embeddings = np.array([p.vector for p in points])
    interaction_map = {i.query_embedding_id: i for i in interactions}

    # 3. Compute pairwise distances
    similarities = cosine_similarity(embeddings)
    distances = 1 - similarities

    # 4. Agglomerative clustering
    clustering = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=0.15,  # 0.85 cosine similarity
        metric="precomputed",
        linkage="average",
    )
    labels = clustering.fit_predict(distances)

    # 5. Process clusters
    patterns_created = 0
    for cluster_id in set(labels):
        mask = labels == cluster_id
        cluster_size = mask.sum()

        if cluster_size < min_cluster_size:
            continue

        # Get cluster interactions
        cluster_indices = np.where(mask)[0]
        cluster_points = [points[i] for i in cluster_indices]
        cluster_interactions = [
            interaction_map[p.id] for p in cluster_points
            if p.id in interaction_map
        ]

        # Find canonical query (closest to centroid)
        centroid = embeddings[mask].mean(axis=0)
        distances_to_centroid = np.linalg.norm(embeddings[mask] - centroid, axis=1)
        canonical_idx = cluster_indices[np.argmin(distances_to_centroid)]
        canonical_interaction = interaction_map[points[canonical_idx].id]

        # Calculate metrics
        satisfaction_scores = [
            i.feedback_rating for i in cluster_interactions
            if i.feedback_rating is not None
        ]
        follow_up_count = sum(
            1 for i in cluster_interactions if i.had_follow_up
        )

        # Create or update pattern
        pattern = await pattern_repo.upsert(
            canonical_query=canonical_interaction.query_text,
            pattern_embedding_id=points[canonical_idx].id,
            category=canonical_interaction.category,
            subcategory=canonical_interaction.subcategory,
            occurrence_count=cluster_size,
            avg_satisfaction_score=(
                sum(satisfaction_scores) / len(satisfaction_scores)
                if satisfaction_scores else None
            ),
            follow_up_rate=follow_up_count / cluster_size,
            sample_interaction_ids=[str(i.id) for i in cluster_interactions[:5]],
        )
        patterns_created += 1

    logger.info(f"Pattern analysis complete: {patterns_created} patterns identified")
```

---

## 6. Knowledge Gap Detection

### Weekly Gap Analysis

```python
# backend/app/tasks/ai_learning/gap_detection.py
import math
from datetime import datetime, timedelta

from sqlalchemy import select, func, and_

from app.modules.ai_learning.models import AIInteraction, KnowledgeGap, GapStatus
from app.modules.ai_learning.repository import KnowledgeGapRepository
from app.tasks.celery_app import celery_app


def calculate_priority_score(
    interaction_count: int,
    avg_satisfaction: float,
    days_since_first: int,
) -> float:
    """Calculate priority score for a knowledge gap."""
    # Volume: log scale (10 interactions = 1.0, 100 = 2.0)
    volume_score = math.log10(max(interaction_count, 1)) / 2

    # Severity: inverse satisfaction (5.0 = 0.0, 1.0 = 1.0)
    severity_score = (5.0 - avg_satisfaction) / 4.0

    # Recency: decay over 90 days
    recency_score = max(0, 1 - (days_since_first / 90))

    return volume_score * severity_score * recency_score


@celery_app.task
async def run_gap_detection(
    satisfaction_threshold: float = 3.5,
    min_interactions: int = 10,
):
    """Weekly job to identify knowledge gaps."""
    gap_repo = KnowledgeGapRepository()

    # Query for low-satisfaction topics
    since = datetime.utcnow() - timedelta(days=30)

    query = (
        select(
            AIInteraction.category,
            AIInteraction.subcategory,
            func.count(AIInteraction.id).label("interaction_count"),
            func.avg(AIInteraction.feedback_rating).label("avg_satisfaction"),
            func.min(AIInteraction.created_at).label("first_seen"),
            func.array_agg(AIInteraction.query_text).label("sample_queries"),
        )
        .where(
            and_(
                AIInteraction.feedback_rating.isnot(None),
                AIInteraction.created_at > since,
            )
        )
        .group_by(AIInteraction.category, AIInteraction.subcategory)
        .having(
            and_(
                func.avg(AIInteraction.feedback_rating) < satisfaction_threshold,
                func.count(AIInteraction.id) >= min_interactions,
            )
        )
    )

    results = await session.execute(query)

    gaps_identified = 0
    for row in results:
        days_since_first = (datetime.utcnow() - row.first_seen).days

        priority_score = calculate_priority_score(
            interaction_count=row.interaction_count,
            avg_satisfaction=row.avg_satisfaction,
            days_since_first=days_since_first,
        )

        # Topic name
        topic = row.subcategory or row.category

        # Check if gap already exists
        existing = await gap_repo.get_by_topic(topic)

        if existing:
            # Update existing gap
            await gap_repo.update(
                existing.id,
                interaction_count=row.interaction_count,
                avg_satisfaction=row.avg_satisfaction,
                priority_score=priority_score,
                sample_queries=row.sample_queries[:5],  # Limit samples
            )
        else:
            # Create new gap
            await gap_repo.create(
                topic=topic,
                category=row.category,
                subcategory=row.subcategory,
                sample_queries=row.sample_queries[:5],
                interaction_count=row.interaction_count,
                avg_satisfaction=row.avg_satisfaction,
                priority_score=priority_score,
                status=GapStatus.IDENTIFIED,
            )
            gaps_identified += 1

    logger.info(f"Gap detection complete: {gaps_identified} new gaps identified")
```

---

## 7. Fine-Tuning Pipeline

### Candidate Scoring Job

```python
# backend/app/tasks/ai_learning/candidate_scoring.py
from datetime import datetime, timedelta

from app.modules.ai_learning.models import (
    AIInteraction,
    FineTuningCandidate,
    CandidateStatus,
)
from app.modules.ai_learning.repository import (
    AIInteractionRepository,
    FineTuningCandidateRepository,
)
from app.tasks.celery_app import celery_app


def calculate_quality_score(interaction: AIInteraction) -> float:
    """Calculate quality score from signals."""
    score = 0.0

    # Negative feedback is instant disqualifier
    if interaction.feedback_rating == 1:
        return 0.0

    # Explicit feedback (40%)
    if interaction.feedback_rating == 5:
        score += 0.4
    elif interaction.feedback_rating is None:
        score += 0.1  # Neutral, slight positive bias

    # Action taken (30%)
    if interaction.action_type is not None:
        score += 0.3
        if interaction.action_modified is False:
            score += 0.05

    # No follow-up needed (20%)
    if interaction.had_follow_up is False:
        score += 0.2
    elif interaction.had_follow_up is None:
        score += 0.1

    # High confidence (10%)
    if interaction.confidence_score:
        if interaction.confidence_score > 0.8:
            score += 0.1
        elif interaction.confidence_score > 0.6:
            score += 0.05

    return min(score, 1.0)


@celery_app.task
async def run_candidate_scoring(
    quality_threshold: float = 0.6,
    days_back: int = 1,
):
    """Daily job to identify fine-tuning candidates."""
    interaction_repo = AIInteractionRepository()
    candidate_repo = FineTuningCandidateRepository()

    since = datetime.utcnow() - timedelta(days=days_back)

    # Fetch interactions with consent for training
    interactions = await interaction_repo.get_for_training(
        since=since,
        consent_required=True,
    )

    candidates_created = 0
    for interaction in interactions:
        # Skip if already a candidate
        existing = await candidate_repo.get_by_interaction_id(interaction.id)
        if existing:
            continue

        # Calculate quality score
        quality_score = calculate_quality_score(interaction)

        if quality_score >= quality_threshold:
            await candidate_repo.create(
                interaction_id=interaction.id,
                quality_score=quality_score,
                has_positive_feedback=interaction.feedback_rating == 5,
                had_action_taken=interaction.action_type is not None,
                no_follow_up_needed=interaction.had_follow_up is False,
                confidence_was_high=(
                    interaction.confidence_score and
                    interaction.confidence_score > 0.8
                ),
                category=interaction.category,
                subcategory=interaction.subcategory,
                status=CandidateStatus.PENDING,
            )
            candidates_created += 1

    logger.info(f"Candidate scoring complete: {candidates_created} candidates identified")
```

### JSONL Exporter

```python
# backend/app/modules/ai_learning/finetuning/exporter.py
import json
from datetime import datetime
from uuid import UUID

import boto3

from app.config import settings
from app.modules.ai_learning.models import (
    FineTuningExample,
    FineTuningDataset,
)
from app.modules.ai_learning.finetuning.anonymizer import Anonymizer


SYSTEM_PROMPT = """You are an AI assistant for Australian accountants managing BAS and tax compliance. Provide accurate, practical advice based on ATO guidelines. Be concise but thorough. Cite relevant tax rules when applicable."""


class JSONLExporter:
    """Export training examples to JSONL format."""

    def __init__(self):
        self.s3 = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        self.bucket = settings.AI_LEARNING_BUCKET
        self.anonymizer = Anonymizer()

    async def export_dataset(
        self,
        version: str,
        examples: list[FineTuningExample],
        train_split: float = 0.9,
        created_by: UUID,
    ) -> FineTuningDataset:
        """Export examples to JSONL and create dataset record."""
        # Shuffle and split
        import random
        random.shuffle(examples)

        split_idx = int(len(examples) * train_split)
        train_examples = examples[:split_idx]
        eval_examples = examples[split_idx:]

        # Generate JSONL content
        train_lines = [self._to_jsonl(ex) for ex in train_examples]
        eval_lines = [self._to_jsonl(ex) for ex in eval_examples]

        # Upload to S3
        train_key = f"training-datasets/{version}/train.jsonl"
        eval_key = f"training-datasets/{version}/eval.jsonl"

        self.s3.put_object(
            Bucket=self.bucket,
            Key=train_key,
            Body="\n".join(train_lines).encode("utf-8"),
            ContentType="application/jsonl",
        )

        self.s3.put_object(
            Bucket=self.bucket,
            Key=eval_key,
            Body="\n".join(eval_lines).encode("utf-8"),
            ContentType="application/jsonl",
        )

        # Calculate category distribution
        category_counts = {}
        for ex in examples:
            category_counts[ex.category] = category_counts.get(ex.category, 0) + 1

        # Create dataset record
        dataset = FineTuningDataset(
            version=version,
            train_s3_key=train_key,
            eval_s3_key=eval_key,
            total_examples=len(examples),
            train_examples=len(train_examples),
            eval_examples=len(eval_examples),
            category_distribution=category_counts,
            source_date_start=min(ex.curated_at for ex in examples),
            source_date_end=max(ex.curated_at for ex in examples),
            created_by=created_by,
        )

        return dataset

    def _to_jsonl(self, example: FineTuningExample) -> str:
        """Convert example to JSONL line."""
        # Anonymize user message
        anonymized_query = self.anonymizer.anonymize(example.user_message)

        data = {
            "messages": [
                {"role": "system", "content": example.system_prompt or SYSTEM_PROMPT},
                {"role": "user", "content": anonymized_query},
                {"role": "assistant", "content": example.ideal_response},
            ]
        }

        return json.dumps(data, ensure_ascii=False)
```

---

## 8. Admin Dashboard API

### Router Implementation

```python
# backend/app/modules/ai_learning/router.py
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_current_user, require_admin
from app.modules.ai_learning.service import AILearningService
from app.modules.ai_learning.schemas import (
    DashboardResponse,
    PatternListResponse,
    GapListResponse,
    CandidateListResponse,
)

router = APIRouter(prefix="/admin/ai-intelligence", tags=["AI Intelligence"])


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    period: str = "week",
    current_user=Depends(require_admin),
    service: AILearningService = Depends(),
):
    """Get AI intelligence dashboard data."""
    return await service.get_dashboard(period=period)


@router.get("/patterns", response_model=PatternListResponse)
async def list_patterns(
    category: str | None = None,
    min_occurrences: int = 10,
    sort_by: str = "occurrence_count",
    page: int = 1,
    per_page: int = 25,
    current_user=Depends(require_admin),
    service: AILearningService = Depends(),
):
    """List query patterns."""
    return await service.list_patterns(
        category=category,
        min_occurrences=min_occurrences,
        sort_by=sort_by,
        page=page,
        per_page=per_page,
    )


@router.get("/gaps", response_model=GapListResponse)
async def list_gaps(
    status: str | None = None,
    category: str | None = None,
    page: int = 1,
    per_page: int = 25,
    current_user=Depends(require_admin),
    service: AILearningService = Depends(),
):
    """List knowledge gaps."""
    return await service.list_gaps(
        status=status,
        category=category,
        page=page,
        per_page=per_page,
    )


@router.get("/finetuning/candidates", response_model=CandidateListResponse)
async def list_candidates(
    status: str = "PENDING",
    category: str | None = None,
    min_quality: float = 0.6,
    page: int = 1,
    per_page: int = 25,
    current_user=Depends(require_admin),
    service: AILearningService = Depends(),
):
    """List fine-tuning candidates."""
    return await service.list_candidates(
        status=status,
        category=category,
        min_quality=min_quality,
        page=page,
        per_page=per_page,
    )


@router.post("/finetuning/candidates/{id}/approve")
async def approve_candidate(
    id: UUID,
    quality_score: int,
    edited_response: str | None = None,
    current_user=Depends(require_admin),
    service: AILearningService = Depends(),
):
    """Approve candidate and create training example."""
    return await service.approve_candidate(
        candidate_id=id,
        quality_score=quality_score,
        edited_response=edited_response,
        curated_by=current_user.id,
    )
```

---

## Testing

### Unit Test Example

```python
# backend/tests/unit/modules/ai_learning/test_quality_score.py
import pytest
from unittest.mock import MagicMock

from app.modules.ai_learning.models import AIInteraction
from app.tasks.ai_learning.candidate_scoring import calculate_quality_score


class TestQualityScore:
    def test_negative_feedback_returns_zero(self):
        interaction = MagicMock(spec=AIInteraction)
        interaction.feedback_rating = 1

        score = calculate_quality_score(interaction)

        assert score == 0.0

    def test_positive_feedback_adds_40_percent(self):
        interaction = MagicMock(spec=AIInteraction)
        interaction.feedback_rating = 5
        interaction.action_type = None
        interaction.had_follow_up = None
        interaction.confidence_score = None

        score = calculate_quality_score(interaction)

        assert score == 0.4

    def test_action_taken_adds_30_percent(self):
        interaction = MagicMock(spec=AIInteraction)
        interaction.feedback_rating = None
        interaction.action_type = "created_insight"
        interaction.action_modified = False
        interaction.had_follow_up = None
        interaction.confidence_score = None

        score = calculate_quality_score(interaction)

        assert score == 0.45  # 0.1 (neutral) + 0.3 + 0.05

    def test_perfect_score(self):
        interaction = MagicMock(spec=AIInteraction)
        interaction.feedback_rating = 5
        interaction.action_type = "created_task"
        interaction.action_modified = False
        interaction.had_follow_up = False
        interaction.confidence_score = 0.9

        score = calculate_quality_score(interaction)

        assert score == 1.0  # 0.4 + 0.35 + 0.2 + 0.1 = 1.05 capped at 1.0
```

---

## Performance Considerations

1. **Capture Overhead**: All async operations (embedding, S3 upload) happen after response
2. **Classification Latency**: Use Haiku model (~200ms) in async task
3. **Pattern Analysis**: Run daily, O(n²) acceptable for 10K interactions
4. **Redis Metrics**: Use pipelines for batch increments
5. **JSONL Export**: Stream to S3 for large datasets
