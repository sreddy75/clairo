# Research: AI Interaction Capture & Learning

**Spec**: 029-ai-interaction-capture-learning
**Date**: 2026-01-01

---

## 1. Query Auto-Classification

### Decision: Claude 3.5 Haiku for Classification

**Rationale**: Fast, cheap, and accurate for simple 4-category classification.

**Alternatives Considered**:
- **Fine-tuned classifier**: Higher accuracy but requires training data we don't have yet
- **Rule-based**: Too brittle, won't handle edge cases
- **Local model (BERT)**: Added infrastructure complexity

**Implementation**:

```python
CLASSIFICATION_CATEGORIES = {
    "COMPLIANCE": "Tax rules, ATO requirements, BAS/GST/PAYG/Super questions",
    "STRATEGY": "Business advice, cash flow, growth, forecasting, planning",
    "DATA_QUALITY": "Reconciliation issues, missing data, discrepancies, errors",
    "WORKFLOW": "Tasks, reminders, notifications, process questions",
}

SUBCATEGORIES = {
    "COMPLIANCE": ["GST", "PAYG", "SUPER", "FBT", "CGT", "INCOME_TAX", "LODGEMENT"],
    "STRATEGY": ["CASHFLOW", "GROWTH", "PRICING", "BENCHMARKING", "FORECASTING"],
    "DATA_QUALITY": ["RECONCILIATION", "MISSING_DATA", "DUPLICATE", "VARIANCE"],
    "WORKFLOW": ["TASKS", "DEADLINES", "NOTIFICATIONS", "SETTINGS"],
}
```

**Prompt Design**:

```python
CLASSIFY_PROMPT = """
You are classifying accountant queries for a BAS management system.

CATEGORIES:
- COMPLIANCE: {definitions[COMPLIANCE]}
- STRATEGY: {definitions[STRATEGY]}
- DATA_QUALITY: {definitions[DATA_QUALITY]}
- WORKFLOW: {definitions[WORKFLOW]}

EXAMPLES:
- "What's the GST credit for this invoice?" → COMPLIANCE / GST
- "How can I improve this client's cash flow?" → STRATEGY / CASHFLOW
- "Why doesn't this bank balance match?" → DATA_QUALITY / RECONCILIATION
- "Remind me about the BAS deadline" → WORKFLOW / DEADLINES

Query: {query}

Return ONLY valid JSON: {"category": "...", "subcategory": "..." or null}
"""
```

**Expected Performance**:
- Latency: ~200ms (Haiku)
- Cost: ~$0.0001 per classification
- Accuracy: >90% (validated on sample set)

---

## 2. Query Embedding Strategy

### Decision: OpenAI text-embedding-3-small

**Rationale**: Best price/performance for semantic similarity. Already using OpenAI for other embeddings.

**Alternatives Considered**:
- **text-embedding-3-large**: 2x cost, marginal improvement for query similarity
- **Voyage AI**: Slightly better but adds vendor dependency
- **Local model**: Infrastructure overhead not worth it

**Implementation**:

```python
from openai import AsyncOpenAI

class QueryEmbedder:
    def __init__(self):
        self.client = AsyncOpenAI()
        self.model = "text-embedding-3-small"
        self.dimensions = 1536

    async def embed(self, text: str) -> list[float]:
        response = await self.client.embeddings.create(
            model=self.model,
            input=text,
            dimensions=self.dimensions,
        )
        return response.data[0].embedding
```

**Qdrant Collection Config**:

```python
from qdrant_client.models import VectorParams, Distance

COLLECTION_CONFIG = {
    "name": "ai_queries",
    "vectors_config": VectorParams(
        size=1536,
        distance=Distance.COSINE,
    ),
    "on_disk_payload": True,  # Store metadata on disk
}
```

**Cost Estimate**:
- 100K queries/month × $0.00002/query = $2/month

---

## 3. Pattern Clustering Approach

### Decision: Qdrant Nearest Neighbor + Agglomerative Clustering

**Rationale**: Leverage existing Qdrant infrastructure for similarity search, then cluster locally.

**Algorithm**:

```python
from sklearn.cluster import AgglomerativeClustering
import numpy as np

class PatternClusterer:
    def __init__(self, qdrant_client, min_cluster_size: int = 50):
        self.qdrant = qdrant_client
        self.min_cluster_size = min_cluster_size
        self.similarity_threshold = 0.85

    async def find_patterns(
        self,
        tenant_id: UUID,
        days_back: int = 7,
    ) -> list[QueryPattern]:
        # 1. Fetch recent query embeddings
        embeddings = await self._fetch_recent_embeddings(tenant_id, days_back)

        # 2. Compute pairwise distances
        distances = 1 - cosine_similarity(embeddings)

        # 3. Agglomerative clustering
        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=1 - self.similarity_threshold,
            metric="precomputed",
            linkage="average",
        )
        labels = clustering.fit_predict(distances)

        # 4. Filter to significant clusters
        patterns = []
        for cluster_id in set(labels):
            mask = labels == cluster_id
            if mask.sum() >= self.min_cluster_size:
                patterns.append(self._create_pattern(cluster_id, mask))

        return patterns
```

**Scaling Considerations**:
- Daily job processes last 7 days (~10K interactions)
- O(n²) distance matrix acceptable at this scale
- For 100K+ interactions, switch to HDBSCAN with sampling

---

## 4. Knowledge Gap Detection

### Decision: Satisfaction-Weighted Topic Aggregation

**Rationale**: Simple, interpretable, actionable.

**Algorithm**:

```python
@dataclass
class GapScore:
    topic: str
    interaction_count: int
    avg_satisfaction: float
    priority_score: float

def calculate_gap_priority(
    interaction_count: int,
    avg_satisfaction: float,
    days_since_first: int,
) -> float:
    """
    Priority = volume × severity × recency

    - Volume: log scale (10 interactions = 1.0, 100 = 2.0)
    - Severity: inverse satisfaction (5.0 = 0.0, 1.0 = 1.0)
    - Recency: decay over 90 days
    """
    volume_score = math.log10(max(interaction_count, 1)) / 2
    severity_score = (5.0 - avg_satisfaction) / 4.0
    recency_score = max(0, 1 - (days_since_first / 90))

    return volume_score * severity_score * recency_score
```

**Gap Detection Query**:

```sql
SELECT
    category,
    subcategory,
    COUNT(*) as interaction_count,
    AVG(feedback_rating) as avg_satisfaction,
    MIN(created_at) as first_seen
FROM ai_interactions
WHERE
    feedback_rating IS NOT NULL
    AND created_at > NOW() - INTERVAL '30 days'
GROUP BY category, subcategory
HAVING AVG(feedback_rating) < 3.5
ORDER BY priority_score DESC
LIMIT 20;
```

---

## 5. Fine-Tuning Quality Score

### Decision: Weighted Signal Composite

**Rationale**: Combines explicit and implicit signals for robust quality assessment.

**Signal Weights**:

| Signal | Weight | Rationale |
|--------|--------|-----------|
| Positive feedback | 40% | Strongest explicit signal |
| Action taken | 30% | User acted on advice |
| No follow-up | 20% | Response was sufficient |
| High confidence | 10% | Model was certain |

**Scoring Function**:

```python
def calculate_quality_score(interaction: AIInteraction) -> float:
    """Calculate 0-1 quality score from signals."""
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
        # Bonus if action wasn't modified
        if interaction.action_modified is False:
            score += 0.05

    # No follow-up needed (20%)
    if interaction.had_follow_up is False:
        score += 0.2
    elif interaction.had_follow_up is None:
        score += 0.1  # Unknown, slight positive bias

    # High confidence (10%)
    if interaction.confidence_score:
        if interaction.confidence_score > 0.8:
            score += 0.1
        elif interaction.confidence_score > 0.6:
            score += 0.05

    return min(score, 1.0)
```

**Candidate Threshold**: score >= 0.6

**Expected Volumes**:
- 100K interactions/month
- ~5K candidates (5%) after auto-filter
- ~500 examples (0.5%) after human curation

---

## 6. PII Anonymization

### Decision: Pattern-Based Redaction + Entity Recognition

**Rationale**: Must remove PII before training to protect client confidentiality.

**Patterns to Redact**:

```python
PII_PATTERNS = {
    # Australian identifiers
    "ABN": r"\b\d{2}\s?\d{3}\s?\d{3}\s?\d{3}\b",
    "ACN": r"\b\d{3}\s?\d{3}\s?\d{3}\b",
    "TFN": r"\b\d{3}\s?\d{3}\s?\d{3}\b",

    # Contact info
    "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "PHONE": r"\b(?:\+61|0)[2-9]\d{8}\b",
    "MOBILE": r"\b(?:\+61|0)4\d{8}\b",

    # Financial
    "BSB": r"\b\d{3}-?\d{3}\b",
    "ACCOUNT": r"\b\d{6,10}\b",

    # Monetary (replace with [AMOUNT])
    "MONEY": r"\$[\d,]+(?:\.\d{2})?",
}

ENTITY_TYPES = ["PERSON", "ORG", "GPE"]  # spaCy NER
```

**Anonymization Pipeline**:

```python
import spacy
import re

class Anonymizer:
    def __init__(self):
        self.nlp = spacy.load("en_core_web_sm")

    def anonymize(self, text: str) -> str:
        # Step 1: Pattern-based redaction
        for pattern_name, pattern in PII_PATTERNS.items():
            text = re.sub(pattern, f"[{pattern_name}]", text)

        # Step 2: Named entity recognition
        doc = self.nlp(text)
        for ent in reversed(doc.ents):
            if ent.label_ in ENTITY_TYPES:
                text = text[:ent.start_char] + f"[{ent.label_}]" + text[ent.end_char:]

        return text
```

---

## 7. JSONL Export Format

### Decision: Anthropic Fine-Tuning Format

**Rationale**: Standard format for Claude fine-tuning.

**Format**:

```jsonl
{"messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
{"messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
```

**Example**:

```json
{
  "messages": [
    {
      "role": "system",
      "content": "You are an AI assistant for Australian accountants managing BAS and tax compliance. Provide accurate, practical advice based on ATO guidelines."
    },
    {
      "role": "user",
      "content": "What's the GST treatment for [ORG]'s export sales to [GPE]?"
    },
    {
      "role": "assistant",
      "content": "Export sales to overseas customers are generally GST-free under Division 38 of the GST Act. To qualify:\n\n1. The goods must be exported within 60 days of payment or invoice\n2. You must have evidence of export (shipping docs, customs declaration)\n3. The supply must be to a non-resident customer\n\nRecord these as G2 (GST-free exports) in your BAS. Keep export documentation for 5 years."
    }
  ]
}
```

**Export Configuration**:

```python
@dataclass
class ExportConfig:
    train_split: float = 0.9
    eval_split: float = 0.1
    min_examples_per_category: int = 50
    max_examples_total: int = 10_000
```

---

## 8. Real-Time Metrics (Redis)

### Decision: Redis Counters with TTL

**Rationale**: Fast, atomic increments for live dashboard. Auto-expire old data.

**Key Schema**:

```python
REDIS_KEYS = {
    # Rolling counters (1-hour buckets, 24-hour retention)
    "interactions": "ai:metrics:{tenant_id}:interactions:{hour}",
    "feedback_positive": "ai:metrics:{tenant_id}:feedback:positive:{hour}",
    "feedback_negative": "ai:metrics:{tenant_id}:feedback:negative:{hour}",

    # Category counters (daily, 30-day retention)
    "category": "ai:metrics:{tenant_id}:category:{category}:{date}",

    # Aggregates (daily snapshots)
    "daily_summary": "ai:metrics:{tenant_id}:summary:{date}",
}

TTL_SECONDS = {
    "hourly": 86400,      # 24 hours
    "daily": 2592000,     # 30 days
    "summary": 7776000,   # 90 days
}
```

**Increment Pattern**:

```python
async def record_interaction(
    redis: Redis,
    tenant_id: UUID,
    category: str,
) -> None:
    hour = datetime.utcnow().strftime("%Y%m%d%H")
    date = datetime.utcnow().strftime("%Y%m%d")

    pipe = redis.pipeline()
    pipe.incr(f"ai:metrics:{tenant_id}:interactions:{hour}")
    pipe.expire(f"ai:metrics:{tenant_id}:interactions:{hour}", TTL_SECONDS["hourly"])
    pipe.incr(f"ai:metrics:{tenant_id}:category:{category}:{date}")
    pipe.expire(f"ai:metrics:{tenant_id}:category:{category}:{date}", TTL_SECONDS["daily"])
    await pipe.execute()
```

---

## 9. Storage Cost Estimates

### S3 Storage (Raw Logs)

| Volume | Size/Log | Monthly Storage | Cost (Sydney) |
|--------|----------|-----------------|---------------|
| 100K interactions | 5 KB | 500 MB | $0.01 |
| 500K interactions | 5 KB | 2.5 GB | $0.06 |
| 1M interactions | 5 KB | 5 GB | $0.12 |

**Lifecycle Policy**: Move to Glacier after 90 days, delete after 2 years.

### PostgreSQL Storage

| Table | Rows/Month | Row Size | Monthly Growth |
|-------|------------|----------|----------------|
| ai_interactions | 100K | 2 KB | 200 MB |
| query_patterns | 500 | 1 KB | 0.5 MB |
| knowledge_gaps | 50 | 1 KB | 0.05 MB |
| fine_tuning_* | 5K | 5 KB | 25 MB |

**Total**: ~225 MB/month, negligible cost.

### Qdrant Storage

| Collection | Vectors/Month | Dimensions | Monthly Growth |
|------------|---------------|------------|----------------|
| ai_queries | 100K | 1536 | ~600 MB |

**Note**: Vectors can be pruned after 90 days if needed.

---

## 10. Consent & Privacy Model

### Decision: Opt-Out with Granular Controls

**Rationale**: Most tenants benefit from contributing; privacy-conscious can opt out.

**Settings**:

```python
class TenantAISettings(Base):
    tenant_id: UUID

    # Training consent (default: True)
    contribute_to_training: bool = True

    # Analysis consent (default: True)
    allow_pattern_analysis: bool = True

    # Benchmarking consent (default: True)
    allow_anonymized_benchmarking: bool = True

    # Retention period (default: 730 days = 2 years)
    raw_log_retention_days: int = 730
```

**Consent Flow**:
1. Default: All tenants contribute (ToS includes this)
2. Settings page: Toggle each preference
3. Changes apply to new interactions only
4. Existing data follows original consent

**Enforcement**:
- `consent_training=False` → Excluded from fine-tuning pipeline
- `allow_pattern_analysis=False` → Excluded from pattern clustering
- `allow_anonymized_benchmarking=False` → Excluded from aggregate stats
