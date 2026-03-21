# Clairo Constitution

**Project**: Clairo - Intelligent Business Advisory Platform for Australian Accounting Practices
**Version**: 1.1.0
**Created**: 2025-12-28
**Purpose**: Production-grade development guidelines for the Clairo platform

---

## Vision: Three Pillars, Four Layers

### The Three Pillars (CORE DIFFERENTIATOR)

```
┌─────────────────────────────────────────────────────────────┐
│                    THE MAGIC ZONE                            │
│         Personalized insights using ALL THREE pillars        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  PILLAR 1: DATA       PILLAR 2: COMPLIANCE   PILLAR 3: STRATEGY
│  ─────────────────    ────────────────────   ─────────────────
│  • Xero/MYOB APIs     • ATO Guidelines       • Business Growth
│  • Bank Transactions  • Tax Rulings          • Tax Optimization
│  • Document Uploads   • GST Rules            • Entity Structuring
│  • Historical Data    • Compliance RAG       • Advisory RAG
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### The Four Layers (BUILD ORDER - NON-NEGOTIABLE)

| Layer | Focus | Priority | Description |
|-------|-------|----------|-------------|
| **Layer 1** | Core BAS Platform | ★ FOUNDATION | BAS prep, workflow, lodgement - BUILD FIRST |
| **Layer 2** | Business Owner Engagement | After L1 | Portal, mobile PWA, document upload |
| **Layer 3** | Knowledge & AI | After L2 | RAG systems, AI agents, suggestions |
| **Layer 4** | Proactive Advisory | After L3 | Magic Zone - automatic insights |

**CRITICAL**: Layer 1 MUST be complete and validated before building Layer 2. Each layer builds on the previous.

---

## Implementation Roadmap (SOURCE OF TRUTH)

**Location**: `specs/ROADMAP.md`

The ROADMAP.md file is the **single source of truth** for:
- Current implementation focus
- Spec order and dependencies
- Release/Phase/Milestone mapping
- Status tracking across sessions

### AI Agent Session Protocol

**Every new session MUST start with**:
1. Read `specs/ROADMAP.md` - Check current focus
2. Read `.specify/memory/constitution.md` - Understand standards
3. Check spec folder for in-progress work
4. Continue from last state or start next spec

### Implementation Rules (NON-NEGOTIABLE)

1. **Vertical Slices**: Each spec delivers working, testable functionality
2. **Respect Dependencies**: Never skip ahead in the spec registry
3. **One Spec at a Time**: Complete current before starting next
4. **Update ROADMAP.md**: Mark status as you progress
5. **Validate Before Moving**: Each phase has gates - don't skip

---

## Core Principles

### I. Architecture: Modular Monolith (NON-NEGOTIABLE)

**Approach**:
- Single deployable unit with clear internal module boundaries
- Modules communicate via service layer (not direct DB queries)
- Internal event bus for loose coupling where needed
- Can extract to microservices when scale demands (AI module most likely)

**Structure** (NON-NEGOTIABLE):
```
clairo/
├── backend/
│   └── app/
│       ├── main.py                  # FastAPI application entry
│       ├── config.py                # Pydantic settings
│       ├── database.py              # Async SQLAlchemy setup
│       │
│       ├── core/                    # Shared kernel
│       │   ├── audit.py             # Audit logging (FIRST-CLASS)
│       │   ├── events.py            # In-process event bus
│       │   ├── exceptions.py        # Domain exceptions
│       │   ├── security.py          # Auth utilities
│       │   └── logging.py           # Structured logging
│       │
│       ├── modules/                 # Feature modules
│       │   ├── auth/                # Authentication, tenants
│       │   ├── integrations/        # Xero, MYOB, GovReports
│       │   │   ├── xero/
│       │   │   ├── myob/
│       │   │   └── govreports/
│       │   ├── clients/             # Client management
│       │   ├── bas/                 # BAS workflow, calculations
│       │   ├── quality/             # Data quality scoring
│       │   ├── documents/           # OCR, document processing
│       │   ├── knowledge/           # RAG systems (L3)
│       │   ├── agents/              # AI agents (L3-4)
│       │   ├── portal/              # Business owner features (L2)
│       │   └── notifications/       # Email, push, in-app
│       │
│       └── tasks/                   # Celery background tasks
│
├── frontend/
│   └── src/
│       ├── app/                     # Next.js App Router
│       ├── components/
│       ├── hooks/
│       ├── stores/                  # Zustand
│       ├── lib/
│       └── types/                   # Generated from OpenAPI
│
├── shared/
│   └── openapi/                     # API contracts
│
└── infrastructure/
    ├── docker/
    └── deployment/
```

**Module Boundaries** (NON-NEGOTIABLE):
- Each module has: `router.py`, `service.py`, `schemas.py`, `models.py`
- Modules call other modules via service layer only
- No direct cross-module database queries
- No circular dependencies between modules

```python
# GOOD: Module calls another module's service
from app.modules.clients.service import ClientService
from app.modules.quality.service import QualityService

async def get_client_with_score(client_id: str):
    client = await ClientService.get(client_id)
    score = await QualityService.calculate(client_id)
    return {"client": client, "score": score}

# BAD: Direct cross-module table access
from app.modules.quality.models import QualityScore  # DON'T DO THIS
```

---

### II. Technology Stack (NON-NEGOTIABLE)

**Backend**:
| Component | Technology | Rationale |
|-----------|------------|-----------|
| Runtime | Python 3.12+ | AI/ML native ecosystem |
| Framework | FastAPI | Async, auto-docs, Pydantic |
| Validation | Pydantic v2 | Runtime validation |
| ORM | SQLAlchemy 2.0 | Async support, mature |
| Migrations | Alembic | Industry standard |
| Task Queue | Celery + Redis | Background jobs |
| LLM | Claude API (anthropic SDK) | Best reasoning |
| RAG | Custom (BM25 + semantic + RRF) | Hybrid retrieval with cross-encoder reranking |
| Embeddings | Voyage 3.5 lite | 1024 dims, cosine similarity |
| Vector DB | Pinecone | Single index `clairo-knowledge`, 7 namespaces |

**Frontend**:
| Component | Technology | Rationale |
|-----------|------------|-----------|
| Framework | Next.js 14 (App Router) | RSC, great DX |
| UI | React 18 + Tailwind + shadcn/ui | Rapid development |
| State | TanStack Query + Zustand | Server + client state |
| API Client | openapi-fetch | Generated from OpenAPI |
| Forms | React Hook Form + Zod | Type-safe forms |

**Infrastructure**:
| Component | Technology | Rationale |
|-----------|------------|-----------|
| Database | PostgreSQL 16 | Mature, RLS for multi-tenancy |
| Vector DB | Pinecone | Managed vector search, single index with namespaces |
| Cache | Redis | Celery broker + cache |
| File Storage | MinIO | S3-compatible, self-hosted, Docker-native |
| Containers | Docker Compose | Local dev parity, easy orchestration |
| Frontend Hosting | Vercel | Optimized for Next.js |
| Backend Hosting | AWS (Sydney region) | ECS/Fargate, Australian data residency, compliance |

---

### III. Database Access: Repository Pattern (NON-NEGOTIABLE)

**Required Pattern**:
```python
# modules/clients/repository.py
class ClientRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: ClientCreate) -> Client:
        client = Client(**data.model_dump())
        self.db.add(client)
        await self.db.flush()
        await self.db.refresh(client)
        return client

    async def get_by_id(self, client_id: UUID) -> Client | None:
        return await self.db.get(Client, client_id)

    async def list_by_tenant(self, tenant_id: UUID) -> list[Client]:
        result = await self.db.execute(
            select(Client).where(Client.tenant_id == tenant_id)
        )
        return list(result.scalars().all())
```

**Database Requirements**:
- PostgreSQL 16 with pgvector extension
- Async SQLAlchemy 2.x with connection pooling
- Alembic for migrations (auto-generate from models)
- UUID primary keys for all entities
- `tenant_id` on all tenant-scoped tables (multi-tenancy)
- Proper indexes for common query patterns
- Soft deletes where audit trail needed

---

### IV. Multi-Tenancy (NON-NEGOTIABLE)

**Tenant Isolation**:
- All tenant data includes `tenant_id` column
- Row-Level Security (RLS) at database level
- Tenant context set in middleware from JWT
- Never expose data across tenants

```python
# Middleware sets tenant context
@app.middleware("http")
async def tenant_middleware(request: Request, call_next):
    tenant_id = get_tenant_from_jwt(request)
    request.state.tenant_id = tenant_id
    # Set PostgreSQL session variable for RLS
    await set_tenant_context(tenant_id)
    return await call_next(request)
```

**Two User Types**:
| User Type | Access | Auth Method |
|-----------|--------|-------------|
| Accountant | Full platform access | Clerk (primary) |
| Business Owner | Portal only (via invite) | Magic link / limited auth |

---

### V. Testing Strategy (NON-NEGOTIABLE)

**Coverage Requirements**:
| Test Type | Coverage Target | Scope |
|-----------|-----------------|-------|
| Unit Tests | 80% minimum | Services, validators, calculators |
| Integration Tests | 100% endpoints | All API endpoints |
| Contract Tests | 100% | External API contracts (Xero, GovReports) |
| E2E Tests | 100% critical | User journeys per layer |

**Test-First Development**:
1. Write test (RED)
2. Implement feature (GREEN)
3. Refactor if needed
4. Commit

**Test Structure**:
```
backend/tests/
├── unit/
│   └── modules/
│       ├── clients/
│       │   ├── test_service.py
│       │   └── test_validators.py
│       └── bas/
│           └── test_calculator.py
├── integration/
│   └── api/
│       ├── test_clients.py
│       └── test_bas_workflow.py
├── contract/
│   └── adapters/
│       ├── test_xero_adapter.py
│       └── test_govreports_adapter.py
└── e2e/
    └── test_bas_preparation_journey.py
```

**Testing Tools**:
- pytest with pytest-asyncio
- pytest-cov for coverage
- httpx for async API testing
- factory_boy for test fixtures
- Playwright for E2E (frontend)

---

### VI. Code Quality Standards (NON-NEGOTIABLE)

**Python Standards**:
```python
# Type hints everywhere (NON-NEGOTIABLE)
async def create_client(
    tenant_id: UUID,
    data: ClientCreate,
) -> ClientResponse:
    ...

# Pydantic for all schemas (NON-NEGOTIABLE)
class ClientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    abn: str | None = Field(None, pattern=r"^\d{11}$")
    xero_contact_id: str | None = None

    model_config = ConfigDict(strict=True)

# Domain exceptions (not HTTPException in services)
class ClientNotFoundError(DomainError):
    def __init__(self, client_id: UUID):
        super().__init__(f"Client {client_id} not found")

# HTTPException only in API layer
@router.get("/{client_id}")
async def get_client(client_id: UUID) -> ClientResponse:
    try:
        return await service.get_client(client_id)
    except ClientNotFoundError:
        raise HTTPException(status_code=404, detail="Client not found")
```

**Linting & Formatting**:
- Backend: Ruff (linting + formatting), mypy (type checking)
- Frontend: ESLint + Prettier
- Pre-commit hooks enforced
- CI fails on lint errors

---

### VII. API Design Standards (NON-NEGOTIABLE)

**RESTful Conventions**:
```
POST   /api/v1/clients              # Create
GET    /api/v1/clients              # List
GET    /api/v1/clients/{id}         # Read
PUT    /api/v1/clients/{id}         # Full update
PATCH  /api/v1/clients/{id}         # Partial update
DELETE /api/v1/clients/{id}         # Delete
```

**Response Format**:
```python
class APIResponse(BaseModel, Generic[T]):
    data: T
    meta: dict[str, Any] = {}

class ErrorResponse(BaseModel):
    error: str
    code: str
    details: dict[str, Any] = {}
```

**OpenAPI Generation**:
- FastAPI auto-generates OpenAPI schema
- Frontend types generated via `openapi-typescript`
- Contracts are source of truth for API

---

### VIII. External Integrations

**Xero Integration** (Layer 1):
- Use Xero REST API directly (or xero-python SDK)
- OAuth 2.0 with token refresh handling
- Rate limit management (60/min, 5000/day)
- Polling strategy for data sync (no webhooks for XPM)

**GovReports/ATO Integration** (Layer 1):
- Partner API for BAS lodgement
- Secure credential handling
- Audit logging for all lodgements

**AI/LLM Integration** (Layer 3-4):
- Claude API via anthropic Python SDK
- Human-in-the-loop for all suggestions
- Confidence scoring on AI outputs
- Never give tax advice - provide information only

---

### IX. Security Requirements (NON-NEGOTIABLE)

**Authentication**:
- Clerk for accountant authentication
- Magic links for business owner portal
- JWT validation with python-jose
- API keys for partner integrations (future)

**Data Protection**:
- TLS 1.3 for all connections
- Encryption at rest (PostgreSQL)
- PII fields encrypted in database
- Australian data residency (Sydney region)

**Input Validation**:
- Pydantic validation on all inputs
- SQL injection prevention via ORM
- XSS prevention via React escaping

**Audit Logging**: See Section X - Auditing (dedicated section below)

---

### X. Auditing & Compliance (NON-NEGOTIABLE - FIRST-CLASS CONCERN)

> **Reference Pattern**: See [/docs/patterns/auditing-framework.md](/docs/patterns/auditing-framework.md) for complete implementation details including SQL schema, service architecture, and archival processes.

**Why Auditing is Foundational**:
Given the BAS/tax domain, auditing is NOT optional infrastructure - it's a core requirement for:
1. **ATO Compliance**: Legal requirement for 5-7 year record retention
2. **Professional Liability**: Accountants need defensible records
3. **User Trust**: Demonstrable integrity builds confidence
4. **Dispute Resolution**: Complete traceability for ATO queries

**Every Feature MUST Consider Auditing**:
- Spec templates include auditing checklist
- Code reviews verify audit coverage
- Tests validate audit events are generated

#### Audit Event Categories (ALL Required)

| Category | Events | Retention |
|----------|--------|-----------|
| **Authentication** | Login, logout, MFA, password changes | 7 years |
| **Data Access** | Views of financial data, exports, reports | 5 years |
| **Data Modification** | All CRUD on financial entities, BAS changes | 7 years |
| **Integration** | Xero/MYOB syncs, API calls, data mappings | 5 years |
| **Compliance** | BAS prep, lodgement, ATO interactions | 10 years |
| **Administrative** | User provisioning, role changes, config | 7 years |

#### Audit Implementation Patterns

**1. Context-Based Auditing** (Required for all requests):
```python
# Audit context set in middleware - available everywhere
from app.core.audit import get_audit_context, audit_event

# Every request automatically has audit context
context = get_audit_context()  # actor, tenant, IP, timestamp

# Log events with full context
await audit_event(
    event_type="bas.calculation.updated",
    resource_type="bas_period",
    resource_id=period_id,
    old_values=before,
    new_values=after,
)
```

**2. Decorator-Based Auditing** (For service methods):
```python
from app.core.audit import audited

class BASService:
    @audited("bas.calculation.updated", resource_type="bas_period")
    async def update_calculation(self, period_id: UUID, data: dict) -> BAS:
        # Automatically logs before/after, success/failure
        ...
```

**3. Model-Level Auditing** (For automatic change tracking):
```python
class AuditableMixin:
    """Mixin that automatically audits all changes via SQLAlchemy events."""
    __audit_enabled__ = True
    __audit_exclude__ = {"updated_at"}  # Fields to skip

# All financial models MUST use this mixin
class BASPeriod(BaseModel, AuditableMixin):
    ...
```

#### Audit Log Requirements

**Schema** (Immutable, append-only):
```sql
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY,
    event_id UUID NOT NULL UNIQUE,      -- Idempotency
    occurred_at TIMESTAMPTZ NOT NULL,

    -- Actor
    actor_type VARCHAR(50) NOT NULL,    -- user, system, api_key
    actor_id UUID,
    actor_email VARCHAR(255),
    actor_ip INET,

    -- Context
    tenant_id UUID NOT NULL,
    request_id UUID,

    -- Event
    event_category VARCHAR(50) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100),
    resource_id UUID,
    action VARCHAR(50) NOT NULL,        -- create, read, update, delete
    outcome VARCHAR(20) NOT NULL,       -- success, failure

    -- Data (JSONB for flexibility)
    old_values JSONB,
    new_values JSONB,
    metadata JSONB,

    -- Integrity (blockchain-style chaining)
    checksum VARCHAR(64) NOT NULL,
    previous_checksum VARCHAR(64)
);

-- CRITICAL: Prevent modifications
CREATE RULE audit_no_update AS ON UPDATE TO audit_logs DO INSTEAD NOTHING;
CREATE RULE audit_no_delete AS ON DELETE TO audit_logs DO INSTEAD NOTHING;
```

**Sensitive Data Handling**:
```python
# Never log sensitive data in plain text
MASKED_FIELDS = {"tax_file_number", "bank_account", "password"}

def mask_sensitive(data: dict) -> dict:
    return {
        k: "***REDACTED***" if k in MASKED_FIELDS else v
        for k, v in data.items()
    }
```

#### Module Structure Update

Every module MUST include audit considerations:
```
modules/
├── bas/
│   ├── router.py
│   ├── service.py       # Use @audited decorator
│   ├── models.py        # Include AuditableMixin
│   ├── schemas.py
│   ├── repository.py
│   └── audit_events.py  # Define module's audit event types
```

#### Compliance Reports (Built-in)

| Report | Purpose | Frequency |
|--------|---------|-----------|
| User Access Report | Who accessed what | Monthly |
| Data Modification Report | All financial data changes | Per BAS period |
| BAS Activity Report | Complete BAS preparation trail | Per lodgement |
| Integration Sync Report | Xero/MYOB sync history | Weekly |
| Chain Integrity Report | Verify audit log integrity | Weekly |

#### Testing Audit Events

```python
# Every integration test MUST verify audit events
async def test_update_bas_creates_audit_event(client, db_session):
    response = await client.patch(f"/api/v1/bas/{period_id}", json=data)

    # Verify audit event was created
    audit = await get_last_audit_event(db_session, resource_id=period_id)
    assert audit.event_type == "bas.calculation.updated"
    assert audit.old_values != audit.new_values
    assert audit.actor_id == current_user.id
```

---

### XI. AI/RAG Standards (Layer 3-4)

**Human-in-the-Loop** (NON-NEGOTIABLE):
- AI suggests, human approves
- All AI outputs clearly labeled as AI-generated
- Confidence scoring displayed to users
- Easy override/correction mechanism

**Knowledge Bases**:
| Knowledge Base | Purpose | Update Frequency |
|----------------|---------|------------------|
| Compliance (Pillar 2) | ATO rules, GST guidance | Daily scrape |
| Strategy (Pillar 3) | Business growth, tax optimization | Weekly curated |

**Regulatory Compliance**:
- Not providing financial advice (no AFSL)
- Not providing tax advice (no TPB)
- Position as "information" not "advice"
- Accountant-in-the-loop for actionable items
- Clear disclaimers on all AI outputs

---

### XII. Development Workflow

**Spec-Kit Process** (NON-NEGOTIABLE):
1. `/speckit.specify` - Create user-centric specification
2. `/speckit.plan` - Create technical implementation plan
3. `/speckit.tasks` - Generate actionable task list
4. `/speckit.implement` - Execute with TDD

**Specs Folder Structure** (at project root):
```
specs/
├── 001-foundation/              # M0: Project scaffolding
│   ├── spec.md                  # User-centric specification
│   ├── plan.md                  # Technical implementation plan
│   ├── research.md              # Phase 0 research output
│   ├── data-model.md            # Phase 1 data model
│   ├── quickstart.md            # Developer quickstart
│   ├── contracts/               # API contracts
│   └── tasks.md                 # Actionable task list
├── 002-single-client-view/      # M1: Single Client View
├── 003-multi-client-dashboard/  # M2: Multi-Client Dashboard
└── ...                          # Additional features
```

**Naming Convention**: `###-feature-name` where ### is a sequential number.

**Feature Branch Workflow**:
- `main` - Production-ready code
- `develop` - Integration branch
- `feature/###-name` - Feature branches (from specs)
- `hotfix/###-name` - Emergency fixes

**Code Review Requirements**:
- All changes require PR
- Minimum 1 approval
- All CI checks must pass
- No merge with unresolved comments

**Git Conventions**:
- Conventional commits (feat:, fix:, docs:, etc.)
- Squash merge for features
- No force push to main/develop

---

### XIII. Layer-Specific Standards

**Layer 1 (Core BAS) - PRIORITY**:
- Must work without Layers 2-4
- All BAS calculations deterministic and testable
- Full audit trail for compliance
- Offline calculation capability

**Layer 2 (Business Owner)**:
- Progressive Web App (PWA) first
- Mobile-responsive design
- Push notifications via Web Push API
- Graceful degradation without network

**Layer 3 (Knowledge & AI)**:
- RAG retrieval < 3 seconds
- AI suggestion accuracy > 80%
- Source citations on all answers
- Fallback to "ask your accountant"

**Layer 4 (Proactive Advisory)**:
- Insight generation async (Celery)
- Delivery via multiple channels
- Action tracking (was insight useful?)
- A/B testing framework for insights

---

### XIV. Success Criteria

**Technical**:
- [ ] All tests passing with coverage targets met
- [ ] API latency P95 < 200ms (standard endpoints)
- [ ] Zero critical security vulnerabilities
- [ ] CI/CD pipeline operational

**Layer 1 Success**:
- [ ] BAS prep time < 2 hours per client
- [ ] Data quality issues caught > 80%
- [ ] Lodgement success rate > 99%

**Layer 2 Success**:
- [ ] Business owner portal adoption > 60%
- [ ] Document upload rate > 40% proactive
- [ ] Email reduction > 50%

**Layer 3 Success**:
- [ ] AI answer accuracy > 85%
- [ ] RAG retrieval accuracy > 90%
- [ ] Suggestion acceptance > 60%

**Layer 4 Success**:
- [ ] Proactive insights generated > 5/client/quarter
- [ ] Insight action rate > 30%

---

## Module-to-Layer Mapping

| Module | Layer | Description |
|--------|-------|-------------|
| `auth` | All | Authentication, tenants |
| `integrations` | L1 | Xero, MYOB, GovReports |
| `clients` | L1 | Client management |
| `bas` | L1 | BAS workflow, calculations |
| `quality` | L1 | Data quality scoring |
| `documents` | L2 | OCR, document uploads |
| `portal` | L2 | Business owner features |
| `notifications` | L2 | Email, push, in-app |
| `knowledge` | L3 | RAG systems |
| `agents` | L3-4 | AI agents, advisory |

---

## Governance

**Constitution Authority**:
- This constitution is the source of truth for development standards
- All code must comply with these standards
- Exceptions require documented justification
- Updates require team consensus

**Quality Enforcement**:
- Pre-commit hooks for formatting/linting
- CI/CD gates for testing
- Code review for architecture compliance

---

**Version**: 1.1.0
**Ratified**: 2025-12-28
**Amended**: 2026-03-09 — Fixed stale tech stack refs (Qdrant→Pinecone, added Voyage, replaced LangChain with custom RAG, fixed Supabase→PostgreSQL)
**Review Date**: Quarterly
