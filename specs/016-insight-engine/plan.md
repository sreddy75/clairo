# Plan: Insight Engine (Spec 016)

**Spec**: 016-insight-engine
**Status**: Planning
**Estimated Effort**: 5-6 days

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         INSIGHT ENGINE ARCHITECTURE                      │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  TRIGGERS    │     │  ANALYZERS   │     │  DELIVERY    │
├──────────────┤     ├──────────────┤     ├──────────────┤
│              │     │              │     │              │
│ • Xero Sync  │────▶│ • Compliance │────▶│ • Dashboard  │
│ • Daily Cron │     │ • Quality    │     │ • Notifications│
│ • Manual     │     │ • Cash Flow  │     │ • API        │
│              │     │ • Tax Optim  │     │              │
└──────────────┘     └──────────────┘     └──────────────┘
                            │
                            ▼
                    ┌──────────────┐
                    │   STORAGE    │
                    ├──────────────┤
                    │ insights     │
                    │ (PostgreSQL) │
                    └──────────────┘
```

---

## Technical Design

### 1. Module Structure

```
backend/app/modules/insights/
├── __init__.py
├── models.py              # Insight SQLAlchemy model
├── schemas.py             # Pydantic schemas
├── router.py              # API endpoints
├── service.py             # InsightService (CRUD + business logic)
├── analyzers/
│   ├── __init__.py
│   ├── base.py            # BaseAnalyzer ABC
│   ├── compliance.py      # ComplianceAnalyzer
│   ├── quality.py         # QualityAnalyzer
│   ├── cashflow.py        # CashFlowAnalyzer
│   └── tax.py             # TaxOptimizationAnalyzer
├── generator.py           # InsightGenerator (orchestrates analyzers)
└── multi_client.py        # MultiClientQueryService
```

### 2. Database Model

```python
# backend/app/modules/insights/models.py

class InsightCategory(str, Enum):
    COMPLIANCE = "compliance"
    QUALITY = "quality"
    CASH_FLOW = "cash_flow"
    TAX = "tax"
    STRATEGIC = "strategic"

class InsightPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class InsightStatus(str, Enum):
    NEW = "new"
    VIEWED = "viewed"
    ACTIONED = "actioned"
    DISMISSED = "dismissed"
    RESOLVED = "resolved"
    EXPIRED = "expired"

class Insight(Base):
    __tablename__ = "insights"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"))
    client_id: Mapped[UUID | None] = mapped_column(ForeignKey("xero_connections.id"))

    # Classification
    category: Mapped[str] = mapped_column(String(50))
    insight_type: Mapped[str] = mapped_column(String(100))
    priority: Mapped[str] = mapped_column(String(20), default="medium")

    # Content
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text)
    detail: Mapped[str | None] = mapped_column(Text)

    # Actions
    suggested_actions: Mapped[dict] = mapped_column(JSONB, default=list)
    related_url: Mapped[str | None] = mapped_column(String(500))

    # Lifecycle
    status: Mapped[str] = mapped_column(String(50), default="new")
    generated_at: Mapped[datetime] = mapped_column(default=func.now())
    expires_at: Mapped[datetime | None]
    viewed_at: Mapped[datetime | None]
    actioned_at: Mapped[datetime | None]
    dismissed_at: Mapped[datetime | None]

    # Audit
    generation_source: Mapped[str] = mapped_column(String(50))
    confidence: Mapped[float | None]
    data_snapshot: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())
```

### 3. Analyzer Interface

```python
# backend/app/modules/insights/analyzers/base.py

class BaseAnalyzer(ABC):
    """Base class for insight analyzers."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @property
    @abstractmethod
    def category(self) -> InsightCategory:
        """The category of insights this analyzer produces."""

    @abstractmethod
    async def analyze_client(
        self,
        tenant_id: UUID,
        client_id: UUID,
    ) -> list[InsightCreate]:
        """Analyze a single client and return insights."""

    async def analyze_tenant(
        self,
        tenant_id: UUID,
    ) -> list[InsightCreate]:
        """Analyze all clients for a tenant."""
        # Default implementation - override if needed for cross-client insights
        clients = await self._get_active_clients(tenant_id)
        insights = []
        for client in clients:
            client_insights = await self.analyze_client(tenant_id, client.id)
            insights.extend(client_insights)
        return insights
```

### 4. Insight Analyzers

#### ComplianceAnalyzer
```python
class ComplianceAnalyzer(BaseAnalyzer):
    """Analyzes compliance-related issues."""

    category = InsightCategory.COMPLIANCE

    async def analyze_client(self, tenant_id: UUID, client_id: UUID) -> list[InsightCreate]:
        insights = []

        # Check GST threshold
        profile = await self._get_client_profile(client_id)
        if not profile.gst_registered:
            revenue = await self._get_annual_revenue(client_id)
            if revenue > 65000:  # Approaching $75K threshold
                trend = await self._get_revenue_trend(client_id)
                if trend > 0:  # Growing
                    months_to_threshold = self._estimate_months_to_threshold(revenue, trend)
                    insights.append(InsightCreate(
                        category="compliance",
                        insight_type="gst_threshold_approaching",
                        priority="high" if months_to_threshold < 3 else "medium",
                        title="GST Registration Threshold Approaching",
                        summary=f"Revenue ${revenue:,.0f}, estimated to hit $75K in ~{months_to_threshold} months",
                        suggested_actions=[
                            {"label": "Review GST options", "url": f"/clients/{client_id}/gst"},
                            {"label": "Discuss with client", "action": "schedule_meeting"}
                        ],
                        confidence=0.85,
                        data_snapshot={"revenue": revenue, "trend": trend}
                    ))

        # Check BAS deadlines
        pending_bas = await self._get_pending_bas(client_id)
        for bas in pending_bas:
            days_until_due = (bas.due_date - date.today()).days
            if days_until_due < 7:
                insights.append(InsightCreate(
                    category="compliance",
                    insight_type="bas_deadline_approaching",
                    priority="high",
                    title=f"BAS Due in {days_until_due} Days",
                    summary=f"{bas.period} BAS due {bas.due_date.strftime('%d %b')}",
                    related_url=f"/clients/{client_id}/bas/{bas.id}",
                    suggested_actions=[
                        {"label": "Prepare BAS", "url": f"/clients/{client_id}/bas/{bas.id}/prepare"}
                    ]
                ))

        return insights
```

#### QualityAnalyzer
```python
class QualityAnalyzer(BaseAnalyzer):
    """Analyzes data quality issues."""

    category = InsightCategory.QUALITY

    async def analyze_client(self, tenant_id: UUID, client_id: UUID) -> list[InsightCreate]:
        insights = []

        # Check unreconciled transactions
        unreconciled = await self._get_unreconciled_count(client_id)
        if unreconciled > 10:
            insights.append(InsightCreate(
                category="quality",
                insight_type="unreconciled_transactions",
                priority="high" if unreconciled > 25 else "medium",
                title=f"{unreconciled} Unreconciled Transactions",
                summary=f"Bank reconciliation needed - {unreconciled} transactions pending",
                related_url=f"/clients/{client_id}/reconciliation",
                confidence=0.95
            ))

        # Check uncoded transactions (missing GST codes)
        uncoded = await self._get_uncoded_gst_count(client_id)
        if uncoded > 5:
            insights.append(InsightCreate(
                category="quality",
                insight_type="uncoded_gst_transactions",
                priority="medium",
                title=f"{uncoded} Transactions Missing GST Codes",
                summary="Review required before BAS preparation"
            ))

        return insights
```

### 5. Insight Generator (Orchestrator)

```python
# backend/app/modules/insights/generator.py

class InsightGenerator:
    """Orchestrates insight generation across all analyzers."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.analyzers: list[BaseAnalyzer] = [
            ComplianceAnalyzer(db),
            QualityAnalyzer(db),
            CashFlowAnalyzer(db),
            TaxOptimizationAnalyzer(db),
        ]
        self.service = InsightService(db)

    async def generate_for_client(
        self,
        tenant_id: UUID,
        client_id: UUID,
        source: str = "manual",
    ) -> list[Insight]:
        """Generate insights for a single client."""
        all_insights = []

        for analyzer in self.analyzers:
            try:
                insights = await analyzer.analyze_client(tenant_id, client_id)
                all_insights.extend(insights)
            except Exception as e:
                logger.error(f"Analyzer {analyzer.__class__.__name__} failed: {e}")

        # Deduplicate and save
        return await self._save_insights(tenant_id, client_id, all_insights, source)

    async def generate_for_tenant(
        self,
        tenant_id: UUID,
        source: str = "scheduled",
    ) -> list[Insight]:
        """Generate insights for all clients in a tenant."""
        clients = await self._get_active_clients(tenant_id)
        all_insights = []

        for client in clients:
            insights = await self.generate_for_client(tenant_id, client.id, source)
            all_insights.extend(insights)

        return all_insights

    async def _save_insights(
        self,
        tenant_id: UUID,
        client_id: UUID,
        insights: list[InsightCreate],
        source: str,
    ) -> list[Insight]:
        """Deduplicate and save insights."""
        saved = []
        for insight_data in insights:
            # Check for existing similar insight (not dismissed, not expired)
            existing = await self.service.find_similar(
                tenant_id=tenant_id,
                client_id=client_id,
                insight_type=insight_data.insight_type,
            )
            if not existing:
                insight = await self.service.create(
                    tenant_id=tenant_id,
                    client_id=client_id,
                    data=insight_data,
                    source=source,
                )
                saved.append(insight)
        return saved
```

### 6. Multi-Client Query Service

```python
# backend/app/modules/insights/multi_client.py

class MultiClientQueryService:
    """Handles cross-portfolio queries."""

    def __init__(
        self,
        db: AsyncSession,
        orchestrator: MultiPerspectiveOrchestrator,
    ):
        self.db = db
        self.orchestrator = orchestrator

    async def query(
        self,
        tenant_id: UUID,
        user_id: UUID,
        query: str,
    ) -> MultiClientResponse:
        """Execute a multi-client query."""

        # Build portfolio context
        context = await self._build_portfolio_context(tenant_id, query)

        # Get active insights for context
        insights = await self._get_active_insights(tenant_id)

        # Construct prompt with portfolio data
        enhanced_query = self._enhance_query_with_context(query, context, insights)

        # Use orchestrator for multi-perspective response
        response = await self.orchestrator.process_query(
            query=enhanced_query,
            tenant_id=tenant_id,
            user_id=user_id,
            knowledge_chunks=await self._get_relevant_knowledge(query),
        )

        # Extract referenced clients from response
        referenced_clients = self._extract_client_references(response, context)

        return MultiClientResponse(
            response=response.content,
            clients_referenced=referenced_clients,
            perspectives_used=response.perspectives_used,
            confidence=response.confidence,
        )

    async def _build_portfolio_context(
        self,
        tenant_id: UUID,
        query: str,
    ) -> PortfolioContext:
        """Build aggregated context across all clients."""
        clients = await self._get_all_clients(tenant_id)

        return PortfolioContext(
            total_clients=len(clients),
            clients_summary=[
                ClientSummary(
                    id=c.id,
                    name=c.organization_name,
                    gst_registered=c.profile.gst_registered if c.profile else None,
                    revenue_bracket=c.profile.revenue_bracket if c.profile else None,
                    active_issues=await self._count_issues(c.id),
                )
                for c in clients
            ],
            # Add more aggregations based on query intent
        )
```

### 7. Celery Tasks

```python
# backend/app/tasks/insights.py

@celery_app.task
def generate_daily_insights():
    """Run daily insight generation for all tenants."""
    async def _run():
        async with get_async_session() as db:
            tenants = await get_active_tenants(db)
            for tenant in tenants:
                generator = InsightGenerator(db)
                await generator.generate_for_tenant(tenant.id, source="scheduled_daily")
                await db.commit()

    asyncio.run(_run())

@celery_app.task
def generate_post_sync_insights(connection_id: str):
    """Generate insights after Xero sync completes."""
    async def _run():
        async with get_async_session() as db:
            connection = await get_connection(db, UUID(connection_id))
            if connection:
                generator = InsightGenerator(db)
                await generator.generate_for_client(
                    tenant_id=connection.tenant_id,
                    client_id=connection.id,
                    source="post_sync",
                )
                await db.commit()

    asyncio.run(_run())

# Add to Celery beat schedule
celery_app.conf.beat_schedule.update({
    'generate-daily-insights': {
        'task': 'app.tasks.insights.generate_daily_insights',
        'schedule': crontab(hour=6, minute=0),  # 6am daily
    },
})
```

### 8. API Router

```python
# backend/app/modules/insights/router.py

router = APIRouter(prefix="/api/v1/insights", tags=["insights"])

@router.get("", response_model=InsightListResponse)
async def list_insights(
    status: list[str] | None = Query(None),
    priority: list[str] | None = Query(None),
    category: list[str] | None = Query(None),
    client_id: UUID | None = None,
    limit: int = 20,
    offset: int = 0,
    service: InsightServiceDep,
    tenant_id: TenantIdDep,
) -> InsightListResponse:
    """List insights with filtering."""

@router.get("/dashboard", response_model=InsightDashboardResponse)
async def get_dashboard(
    service: InsightServiceDep,
    tenant_id: TenantIdDep,
) -> InsightDashboardResponse:
    """Get dashboard summary with top insights."""

@router.post("/{insight_id}/view")
async def mark_viewed(insight_id: UUID, ...): ...

@router.post("/{insight_id}/action")
async def mark_actioned(insight_id: UUID, ...): ...

@router.post("/{insight_id}/dismiss")
async def dismiss_insight(insight_id: UUID, ...): ...

@router.post("/generate")
async def trigger_generation(
    client_id: UUID | None = None,
    ...
) -> InsightGenerationResponse:
    """Manually trigger insight generation."""
```

### 9. Frontend Components

```
frontend/src/
├── components/insights/
│   ├── InsightCard.tsx           # Single insight display
│   ├── InsightList.tsx           # List of insights
│   ├── InsightDashboardWidget.tsx # Dashboard widget
│   ├── InsightFilters.tsx        # Filter controls
│   └── InsightBadge.tsx          # Priority badge
├── app/(protected)/
│   ├── insights/
│   │   └── page.tsx              # Full insights page
│   └── dashboard/
│       └── page.tsx              # Add insights widget
└── lib/api/
    └── insights.ts               # API client functions
```

---

## Implementation Phases

### Phase 1: Foundation (Day 1-2)
- Database migration for insights table
- Models, schemas, base service
- Basic CRUD API endpoints

### Phase 2: Analyzers (Day 2-3)
- BaseAnalyzer interface
- ComplianceAnalyzer (GST threshold, BAS deadlines)
- QualityAnalyzer (unreconciled, uncoded)
- InsightGenerator orchestrator

### Phase 3: Automation (Day 3-4)
- Celery tasks for scheduled generation
- Post-sync trigger integration
- Deduplication logic

### Phase 4: Multi-Client Queries (Day 4-5)
- MultiClientQueryService
- Portfolio context builder
- API endpoint for multi-client chat

### Phase 5: Frontend (Day 5-6)
- Insights dashboard widget
- Full insights page
- Integration with existing notification system

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Too many insights (noise) | Strict deduplication, expiry, priority thresholds |
| False positives | Conservative triggers, confidence scoring, easy dismiss |
| Performance (many clients) | Async processing, batch operations, caching |
| Stale insights | Expiry timestamps, re-evaluation on data change |

---

## Testing Strategy

- Unit tests for each analyzer
- Integration tests for generator pipeline
- E2E tests for API endpoints
- Performance tests for multi-tenant generation
