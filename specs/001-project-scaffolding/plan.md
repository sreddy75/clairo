# Design Document: Project Scaffolding

**Specification:** 001-project-scaffolding
**Version:** 1.0.0
**Date:** 2025-12-28
**Status:** Draft

---

## Overview

This design document defines the technical architecture and implementation details for the Clairo project scaffolding. The scaffolding establishes the foundational development environment for the Clairo platform - an Intelligent Business Advisory Platform for Australian Accounting Practices.

### Design Goals

1. **Modular Monolith Foundation** - Single deployable unit with clear module boundaries as mandated by the constitution
2. **Developer Experience** - Fast setup, hot reload, consistent tooling across Python and TypeScript
3. **Type Safety** - End-to-end type safety from database models to frontend components
4. **Production Parity** - Local development environment mirrors production infrastructure
5. **Extensibility** - Template structures that scale with feature development

### Scope

- Docker Compose local development environment
- Backend project structure (FastAPI modular monolith)
- Frontend project structure (Next.js 14 App Router)
- Development tooling configuration
- Environment variable management

---

## Architecture Design

### System Architecture Diagram

```mermaid
graph TB
    subgraph "Development Machine"
        subgraph "Docker Compose Environment"
            PG[(PostgreSQL 16<br/>+ pgvector)]
            REDIS[(Redis 7)]
            QDRANT[(Qdrant)]
            MINIO[(MinIO)]

            subgraph "Application Services"
                BACKEND[FastAPI Backend<br/>:8000]
                CELERY[Celery Worker]
            end
        end

        FRONTEND[Next.js Frontend<br/>:3000]
    end

    FRONTEND -->|HTTP/REST| BACKEND
    BACKEND -->|AsyncPG| PG
    BACKEND -->|Redis Protocol| REDIS
    BACKEND -->|gRPC/REST| QDRANT
    BACKEND -->|S3 API| MINIO
    CELERY -->|AsyncPG| PG
    CELERY -->|Redis Protocol| REDIS
    CELERY -->|gRPC/REST| QDRANT
    CELERY -->|S3 API| MINIO
```

### Data Flow Diagram

```mermaid
graph LR
    subgraph "Frontend Layer"
        UI[React Components]
        QUERY[TanStack Query]
        STORE[Zustand Store]
    end

    subgraph "API Layer"
        ROUTER[FastAPI Router]
        DEPS[Dependency Injection]
    end

    subgraph "Service Layer"
        SERVICE[Module Services]
        EVENTS[Event Bus]
    end

    subgraph "Data Layer"
        REPO[Repositories]
        SESSION[AsyncSession]
    end

    subgraph "Storage"
        DB[(PostgreSQL)]
        CACHE[(Redis)]
    end

    UI --> QUERY
    UI --> STORE
    QUERY -->|fetch| ROUTER
    ROUTER --> DEPS
    DEPS --> SERVICE
    SERVICE --> EVENTS
    SERVICE --> REPO
    REPO --> SESSION
    SESSION --> DB
    SERVICE --> CACHE
```

---

## Component Design

### Directory Structure

```
clairo/
├── .env.example                    # Environment variable template
├── .gitignore                      # Git ignore patterns
├── .pre-commit-config.yaml         # Pre-commit hooks configuration
├── docker-compose.yml              # Local development services
├── docker-compose.override.yml     # Local overrides (git-ignored)
├── README.md                       # Project documentation
│
├── backend/
│   ├── .env.example                # Backend-specific env template
│   ├── Dockerfile                  # Backend container definition
│   ├── Dockerfile.dev              # Development container with hot reload
│   ├── pyproject.toml              # Python project configuration
│   ├── alembic.ini                 # Alembic configuration
│   │
│   ├── alembic/                    # Database migrations
│   │   ├── env.py                  # Alembic environment config
│   │   ├── script.py.mako          # Migration template
│   │   └── versions/               # Migration files
│   │       └── .gitkeep
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI application entry
│   │   ├── config.py               # Pydantic Settings configuration
│   │   ├── database.py             # Async SQLAlchemy setup
│   │   │
│   │   ├── core/                   # Shared kernel
│   │   │   ├── __init__.py
│   │   │   ├── events.py           # In-process event bus
│   │   │   ├── exceptions.py       # Domain exceptions
│   │   │   ├── security.py         # Auth utilities
│   │   │   ├── logging.py          # Structured logging
│   │   │   └── dependencies.py     # Common FastAPI dependencies
│   │   │
│   │   ├── modules/                # Feature modules
│   │   │   ├── __init__.py
│   │   │   └── _template/          # Module template (reference only)
│   │   │       ├── __init__.py
│   │   │       ├── router.py       # API endpoints
│   │   │       ├── service.py      # Business logic
│   │   │       ├── schemas.py      # Pydantic models
│   │   │       ├── models.py       # SQLAlchemy models
│   │   │       └── repository.py   # Data access layer
│   │   │
│   │   └── tasks/                  # Celery background tasks
│   │       ├── __init__.py
│   │       └── celery_app.py       # Celery configuration
│   │
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py             # Pytest fixtures
│       ├── unit/
│       │   └── .gitkeep
│       ├── integration/
│       │   └── .gitkeep
│       └── e2e/
│           └── .gitkeep
│
├── frontend/
│   ├── .env.example                # Frontend-specific env template
│   ├── .eslintrc.json              # ESLint configuration
│   ├── .prettierrc                 # Prettier configuration
│   ├── next.config.js              # Next.js configuration
│   ├── tailwind.config.ts          # Tailwind CSS configuration
│   ├── tsconfig.json               # TypeScript configuration
│   ├── package.json                # NPM dependencies and scripts
│   ├── components.json             # shadcn/ui configuration
│   │
│   ├── public/                     # Static assets
│   │   └── .gitkeep
│   │
│   └── src/
│       ├── app/                    # Next.js App Router
│       │   ├── layout.tsx          # Root layout
│       │   ├── page.tsx            # Home page
│       │   ├── globals.css         # Global styles
│       │   └── providers.tsx       # Client providers wrapper
│       │
│       ├── components/
│       │   ├── ui/                 # shadcn/ui components
│       │   │   └── .gitkeep
│       │   └── .gitkeep
│       │
│       ├── hooks/
│       │   └── .gitkeep
│       │
│       ├── stores/                 # Zustand stores
│       │   └── example.store.ts    # Store template
│       │
│       ├── lib/
│       │   ├── api.ts              # API client configuration
│       │   ├── utils.ts            # Utility functions (cn helper)
│       │   └── query-client.ts     # TanStack Query client
│       │
│       └── types/
│           ├── api.ts              # Generated OpenAPI types
│           └── index.ts            # Shared type definitions
│
├── scripts/
│   ├── generate-api-types.sh       # OpenAPI type generation
│   ├── init-minio.sh               # MinIO bucket initialization
│   └── wait-for-it.sh              # Service readiness helper
│
└── shared/
    └── openapi/
        └── .gitkeep                # Generated OpenAPI specs
```

### Component: Docker Compose Services

**Responsibilities:**
- Orchestrate all infrastructure services for local development
- Provide health checks and dependency ordering
- Enable port remapping via environment variables
- Support data persistence and cleanup

**Service Definitions:**

| Service | Image | Ports | Purpose |
|---------|-------|-------|---------|
| postgres | postgres:16-alpine | 5432 | Primary database with pgvector |
| redis | redis:7-alpine | 6379 | Cache and Celery broker |
| qdrant | qdrant/qdrant:latest | 6333, 6334 | Vector database |
| minio | minio/minio:latest | 9000, 9001 | S3-compatible object storage |
| backend | Custom Dockerfile | 8000 | FastAPI application |
| celery-worker | Custom Dockerfile | - | Background task processor |

### Component: Backend Core Module

**Responsibilities:**
- Provide shared infrastructure for all feature modules
- Handle cross-cutting concerns (logging, security, events)
- Define domain exception hierarchy
- Manage dependency injection patterns

**Interfaces:**

```python
# core/events.py
class EventBus:
    async def publish(self, event: DomainEvent) -> None: ...
    def subscribe(self, event_type: Type[DomainEvent], handler: EventHandler) -> None: ...

# core/exceptions.py
class DomainError(Exception):
    """Base class for domain-specific errors."""

class NotFoundError(DomainError):
    """Resource not found."""

class ValidationError(DomainError):
    """Business rule validation failed."""

# core/security.py
async def get_current_user(token: str) -> User: ...
async def verify_tenant_access(user: User, tenant_id: UUID) -> bool: ...
```

**Dependencies:**
- None (core is the foundational layer)

### Component: Module Template

**Responsibilities:**
- Define standard structure for feature modules
- Enforce separation of concerns (router/service/repository)
- Provide type-safe data access patterns

**Interfaces:**

```python
# modules/{module}/router.py
router = APIRouter(prefix="/{module}", tags=["{module}"])

@router.get("/{id}")
async def get_item(id: UUID, service: Service = Depends()) -> Response: ...

# modules/{module}/service.py
class ModuleService:
    def __init__(self, repository: Repository, event_bus: EventBus): ...
    async def get_by_id(self, id: UUID) -> Entity | None: ...
    async def create(self, data: CreateSchema) -> Entity: ...

# modules/{module}/repository.py
class ModuleRepository:
    def __init__(self, session: AsyncSession): ...
    async def get(self, id: UUID) -> Model | None: ...
    async def create(self, model: Model) -> Model: ...
```

**Dependencies:**
- `core/` - Events, exceptions, security
- `database.py` - AsyncSession provider

---

## Data Models

### Core Data Structure Definitions

```typescript
// Configuration Schema (Pydantic Settings)
interface Settings {
  // Application
  app_name: string;
  app_version: string;
  debug: boolean;
  environment: "development" | "staging" | "production";

  // Database
  database: {
    url: string;  // PostgreSQL async URL
    pool_size: number;
    max_overflow: number;
    pool_timeout: number;
    pool_recycle: number;
    echo: boolean;  // SQL logging
  };

  // Redis
  redis: {
    url: string;
    max_connections: number;
  };

  // Qdrant
  qdrant: {
    host: string;
    port: number;
    grpc_port: number;
    api_key?: string;
  };

  // MinIO
  minio: {
    endpoint: string;
    access_key: string;
    secret_key: string;
    bucket_name: string;
    secure: boolean;
  };

  // Celery
  celery: {
    broker_url: string;
    result_backend: string;
    task_default_queue: string;
    task_time_limit: number;
  };

  // Security
  security: {
    secret_key: string;
    algorithm: string;
    access_token_expire_minutes: number;
    clerk_secret_key?: string;
    clerk_publishable_key?: string;
  };

  // CORS
  cors: {
    origins: string[];
    allow_credentials: boolean;
    allow_methods: string[];
    allow_headers: string[];
  };
}
```

```python
# SQLAlchemy Base Model
from sqlalchemy import Column, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase
import uuid

class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass

class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

class TenantMixin:
    """Mixin for multi-tenant tables."""
    tenant_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True
    )

class BaseModel(Base, TimestampMixin):
    """Base model with UUID primary key and timestamps."""
    __abstract__ = True

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
```

### Data Model Diagram

```mermaid
classDiagram
    class Base {
        <<abstract>>
    }

    class TimestampMixin {
        +DateTime created_at
        +DateTime updated_at
    }

    class TenantMixin {
        +UUID tenant_id
    }

    class BaseModel {
        +UUID id
        +DateTime created_at
        +DateTime updated_at
    }

    Base <|-- BaseModel
    TimestampMixin <|-- BaseModel

    class TenantBaseModel {
        +UUID id
        +UUID tenant_id
        +DateTime created_at
        +DateTime updated_at
    }

    BaseModel <|-- TenantBaseModel
    TenantMixin <|-- TenantBaseModel

    note for BaseModel "All entities extend this"
    note for TenantBaseModel "Tenant-scoped entities extend this"
```

---

## Business Processes

### Process 1: Application Startup

```mermaid
flowchart TD
    A[Application Start] --> B[Load Settings from Environment]
    B --> C{Settings Valid?}
    C -->|No| D[Log Error & Exit]
    C -->|Yes| E[Initialize Database Engine]
    E --> F[Create AsyncSession Factory]
    F --> G[Initialize Event Bus]
    G --> H[Register Module Routers]
    H --> I[Configure CORS Middleware]
    I --> J[Configure Exception Handlers]
    J --> K[Start Uvicorn Server]
    K --> L[Application Ready]

    D --> M[Exit with Error Code 1]
```

**Component Interactions:**
1. `config.py` - `Settings.from_env()` loads and validates environment
2. `database.py` - `create_async_engine()` with pool configuration
3. `database.py` - `async_sessionmaker()` for dependency injection
4. `core/events.py` - `EventBus()` initialization
5. `main.py` - `app.include_router()` for each module
6. `main.py` - `app.add_middleware(CORSMiddleware)` configuration
7. `main.py` - `app.add_exception_handler()` for domain exceptions

### Process 2: Database Session Lifecycle

```mermaid
flowchart TD
    A[API Request] --> B[get_db Dependency Called]
    B --> C[Create AsyncSession]
    C --> D[Inject Session to Route Handler]
    D --> E[Repository Uses Session]
    E --> F[Execute Database Operations]
    F --> G{Operations Successful?}
    G -->|Yes| H[Commit Transaction]
    G -->|No| I[Rollback Transaction]
    H --> J[Close Session]
    I --> J
    J --> K[Return Response]
```

**Component Interactions:**
1. `core/dependencies.py` - `get_db()` async generator
2. `database.py` - `AsyncSession` from session factory
3. `modules/{module}/repository.py` - Repository receives session
4. `database.py` - Session commit/rollback in `get_db` finally block

### Process 3: Celery Task Execution

```mermaid
flowchart TD
    A[Service Layer] --> B[celery_app.send_task]
    B --> C[Task Serialized to Redis]
    C --> D[Worker Picks Up Task]
    D --> E[Create Database Session]
    E --> F[Execute Task Logic]
    F --> G{Task Successful?}
    G -->|Yes| H[Store Result in Redis]
    G -->|No| I{Retries Remaining?}
    I -->|Yes| J[Schedule Retry with Backoff]
    I -->|No| K[Log Failure & Dead Letter]
    H --> L[Task Complete]
    J --> D
    K --> L
```

**Component Interactions:**
1. `modules/{module}/service.py` - Triggers async task
2. `tasks/celery_app.py` - Task routing configuration
3. Redis - Message broker and result backend
4. `tasks/{module}_tasks.py` - Task implementation
5. `database.py` - Database session for worker

### Process 4: Frontend API Request

```mermaid
flowchart TD
    A[User Action in UI] --> B[TanStack Query Hook]
    B --> C[API Client fetch]
    C --> D{Cache Valid?}
    D -->|Yes| E[Return Cached Data]
    D -->|No| F[HTTP Request to Backend]
    F --> G[FastAPI Router Handles]
    G --> H[Service Layer Logic]
    H --> I[Return Response]
    I --> J[Update TanStack Query Cache]
    J --> K[Re-render Component]
    E --> K
```

**Component Interactions:**
1. `src/hooks/{module}.ts` - Custom query hook
2. `src/lib/query-client.ts` - TanStack Query configuration
3. `src/lib/api.ts` - OpenAPI fetch client
4. Backend - FastAPI endpoint processing

### Process 5: OpenAPI Type Generation

```mermaid
flowchart TD
    A[Developer Runs Script] --> B[scripts/generate-api-types.sh]
    B --> C[Fetch /openapi.json from Backend]
    C --> D{Backend Running?}
    D -->|No| E[Error: Start Backend First]
    D -->|Yes| F[Run openapi-typescript]
    F --> G[Generate src/types/api.ts]
    G --> H[Types Available for Import]
```

**Component Interactions:**
1. `scripts/generate-api-types.sh` - Orchestration script
2. Backend `/openapi.json` - FastAPI auto-generated schema
3. `openapi-typescript` - Type generation
4. `frontend/src/types/api.ts` - Generated types

---

## Error Handling Strategy

### Error Hierarchy

```mermaid
classDiagram
    class Exception {
        <<Python Built-in>>
    }

    class DomainError {
        +str message
        +str code
        +dict details
    }

    class NotFoundError {
        +str resource_type
        +str resource_id
    }

    class ValidationError {
        +str field
        +str reason
    }

    class AuthorizationError {
        +str action
        +str resource
    }

    class ConflictError {
        +str resource_type
        +str conflict_reason
    }

    class ExternalServiceError {
        +str service_name
        +str operation
        +int status_code
    }

    Exception <|-- DomainError
    DomainError <|-- NotFoundError
    DomainError <|-- ValidationError
    DomainError <|-- AuthorizationError
    DomainError <|-- ConflictError
    DomainError <|-- ExternalServiceError
```

### Error Handling Layers

| Layer | Error Handling Approach |
|-------|------------------------|
| **Repository** | Raise `NotFoundError` when entity not found; let database exceptions propagate |
| **Service** | Catch repository errors; raise domain-specific errors with context |
| **Router** | Catch domain errors; convert to appropriate HTTPException with status code |
| **Middleware** | Catch unhandled exceptions; log and return 500 with generic message |

### HTTP Status Code Mapping

| Domain Error | HTTP Status | Response Code |
|--------------|-------------|---------------|
| `NotFoundError` | 404 | `RESOURCE_NOT_FOUND` |
| `ValidationError` | 400 | `VALIDATION_ERROR` |
| `AuthorizationError` | 403 | `FORBIDDEN` |
| `ConflictError` | 409 | `CONFLICT` |
| `ExternalServiceError` | 502 | `EXTERNAL_SERVICE_ERROR` |
| Unhandled Exception | 500 | `INTERNAL_ERROR` |

### Error Response Format

```python
class ErrorResponse(BaseModel):
    """Standard error response format."""
    error: str           # Human-readable message
    code: str            # Machine-readable error code
    details: dict = {}   # Additional context (field errors, etc.)
    request_id: str      # For log correlation
```

---

## Testing Strategy

### Test Structure

```
backend/tests/
├── conftest.py              # Shared fixtures
├── factories/               # Factory Boy definitions
│   └── .gitkeep
├── unit/                    # Unit tests (no I/O)
│   ├── core/
│   │   ├── test_events.py
│   │   └── test_exceptions.py
│   └── modules/
│       └── .gitkeep
├── integration/             # Tests with database
│   ├── conftest.py          # Database fixtures
│   └── api/
│       └── .gitkeep
└── e2e/                     # End-to-end tests
    └── .gitkeep
```

### Test Configuration (pytest)

```toml
# pyproject.toml [tool.pytest.ini_options]
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
python_files = ["test_*.py"]
python_functions = ["test_*"]
addopts = [
    "-v",
    "--strict-markers",
    "--cov=app",
    "--cov-report=term-missing",
    "--cov-report=html:htmlcov",
    "--cov-fail-under=80"
]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks tests that require database",
    "e2e: marks end-to-end tests"
]
filterwarnings = [
    "ignore::DeprecationWarning"
]
```

### Test Database Strategy

1. **Isolation**: Each test session creates a fresh test database
2. **Transactions**: Each test runs in a transaction that is rolled back
3. **Fixtures**: Use `pytest-asyncio` for async test support
4. **Factories**: Use `factory-boy` for generating test data

```python
# tests/conftest.py
@pytest.fixture(scope="session")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        settings.database.url.replace("/clairo", "/clairo_test"),
        echo=False
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
async def db_session(test_engine):
    """Provide transactional test session."""
    async with AsyncSession(test_engine) as session:
        async with session.begin():
            yield session
            await session.rollback()
```

---

## Detailed Component Specifications

### Docker Compose Configuration

```yaml
# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    container_name: clairo-postgres
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-clairo}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-clairo_dev}
      POSTGRES_DB: ${POSTGRES_DB:-clairo}
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init-postgres.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-clairo}"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    container_name: clairo-redis
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
    ports:
      - "${REDIS_PORT:-6379}:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  qdrant:
    image: qdrant/qdrant:latest
    container_name: clairo-qdrant
    ports:
      - "${QDRANT_PORT:-6333}:6333"
      - "${QDRANT_GRPC_PORT:-6334}:6334"
    volumes:
      - qdrant_data:/qdrant/storage
    environment:
      QDRANT__SERVICE__GRPC_PORT: 6334
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/readiness"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  minio:
    image: minio/minio:latest
    container_name: clairo-minio
    command: server /data --console-address ":9001"
    ports:
      - "${MINIO_API_PORT:-9000}:9000"
      - "${MINIO_CONSOLE_PORT:-9001}:9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER:-clairo}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:-clairo_dev}
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  minio-init:
    image: minio/mc:latest
    container_name: clairo-minio-init
    depends_on:
      minio:
        condition: service_healthy
    entrypoint: >
      /bin/sh -c "
      mc alias set clairo http://minio:9000 ${MINIO_ROOT_USER:-clairo} ${MINIO_ROOT_PASSWORD:-clairo_dev};
      mc mb --ignore-existing clairo/${MINIO_BUCKET_NAME:-clairo-documents};
      exit 0;
      "

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.dev
    container_name: clairo-backend
    ports:
      - "${BACKEND_PORT:-8000}:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER:-clairo}:${POSTGRES_PASSWORD:-clairo_dev}@postgres:5432/${POSTGRES_DB:-clairo}
      - REDIS_URL=redis://redis:6379/0
      - QDRANT_HOST=qdrant
      - QDRANT_PORT=6333
      - MINIO_ENDPOINT=minio:9000
      - MINIO_ACCESS_KEY=${MINIO_ROOT_USER:-clairo}
      - MINIO_SECRET_KEY=${MINIO_ROOT_PASSWORD:-clairo_dev}
      - MINIO_BUCKET_NAME=${MINIO_BUCKET_NAME:-clairo-documents}
      - MINIO_SECURE=false
      - DEBUG=true
      - ENVIRONMENT=development
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      qdrant:
        condition: service_healthy
      minio:
        condition: service_healthy
    volumes:
      - ./backend/app:/app/app
      - ./backend/tests:/app/tests
    restart: unless-stopped

  celery-worker:
    build:
      context: ./backend
      dockerfile: Dockerfile.dev
    container_name: clairo-celery
    command: celery -A app.tasks.celery_app worker --loglevel=info
    environment:
      - DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER:-clairo}:${POSTGRES_PASSWORD:-clairo_dev}@postgres:5432/${POSTGRES_DB:-clairo}
      - REDIS_URL=redis://redis:6379/0
      - QDRANT_HOST=qdrant
      - QDRANT_PORT=6333
      - MINIO_ENDPOINT=minio:9000
      - MINIO_ACCESS_KEY=${MINIO_ROOT_USER:-clairo}
      - MINIO_SECRET_KEY=${MINIO_ROOT_PASSWORD:-clairo_dev}
    depends_on:
      - backend
      - redis
    volumes:
      - ./backend/app:/app/app
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  qdrant_data:
  minio_data:
```

### Backend Dockerfile

```dockerfile
# backend/Dockerfile.dev
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
RUN pip install uv

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies
RUN uv pip install --system -e ".[dev]"

# Copy application code
COPY . .

# Run with hot reload
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

### Pydantic Settings Configuration

```python
# backend/app/config.py
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database connection settings."""

    model_config = SettingsConfigDict(env_prefix="DATABASE_")

    url: str = Field(
        default="postgresql+asyncpg://clairo:clairo_dev@localhost:5432/clairo",
        description="PostgreSQL connection URL"
    )
    pool_size: int = Field(default=5, ge=1, le=20)
    max_overflow: int = Field(default=10, ge=0, le=50)
    pool_timeout: int = Field(default=30, ge=5, le=60)
    pool_recycle: int = Field(default=1800, ge=300, le=3600)
    echo: bool = Field(default=False)


class RedisSettings(BaseSettings):
    """Redis connection settings."""

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )
    max_connections: int = Field(default=10, ge=1, le=50)


class QdrantSettings(BaseSettings):
    """Qdrant vector database settings."""

    model_config = SettingsConfigDict(env_prefix="QDRANT_")

    host: str = Field(default="localhost")
    port: int = Field(default=6333)
    grpc_port: int = Field(default=6334)
    api_key: SecretStr | None = Field(default=None)


class MinioSettings(BaseSettings):
    """MinIO object storage settings."""

    model_config = SettingsConfigDict(env_prefix="MINIO_")

    endpoint: str = Field(default="localhost:9000")
    access_key: SecretStr = Field(default=SecretStr("clairo"))
    secret_key: SecretStr = Field(default=SecretStr("clairo_dev"))
    bucket_name: str = Field(default="clairo-documents")
    secure: bool = Field(default=False)


class CelerySettings(BaseSettings):
    """Celery task queue settings."""

    model_config = SettingsConfigDict(env_prefix="CELERY_")

    broker_url: str = Field(default="redis://localhost:6379/0")
    result_backend: str = Field(default="redis://localhost:6379/0")
    task_default_queue: str = Field(default="clairo")
    task_time_limit: int = Field(default=300, ge=30, le=3600)
    task_soft_time_limit: int = Field(default=270, ge=30, le=3600)
    worker_prefetch_multiplier: int = Field(default=1, ge=1, le=10)


class SecuritySettings(BaseSettings):
    """Security and authentication settings."""

    model_config = SettingsConfigDict(env_prefix="SECURITY_")

    secret_key: SecretStr = Field(
        default=SecretStr("CHANGE_ME_IN_PRODUCTION"),
        description="Secret key for JWT signing"
    )
    algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30, ge=5, le=1440)
    clerk_secret_key: SecretStr | None = Field(default=None)
    clerk_publishable_key: str | None = Field(default=None)


class CorsSettings(BaseSettings):
    """CORS configuration settings."""

    model_config = SettingsConfigDict(env_prefix="CORS_")

    origins: list[str] = Field(
        default=["http://localhost:3000"],
        description="Allowed CORS origins"
    )
    allow_credentials: bool = Field(default=True)
    allow_methods: list[str] = Field(default=["*"])
    allow_headers: list[str] = Field(default=["*"])


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    app_name: str = Field(default="Clairo")
    app_version: str = Field(default="0.1.0")
    debug: bool = Field(default=False)
    environment: Literal["development", "staging", "production"] = Field(
        default="development"
    )

    # Nested settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)
    minio: MinioSettings = Field(default_factory=MinioSettings)
    celery: CelerySettings = Field(default_factory=CelerySettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    cors: CorsSettings = Field(default_factory=CorsSettings)

    @field_validator("environment", mode="before")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Normalize environment value."""
        return v.lower()


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
```

### Async SQLAlchemy Setup

```python
# backend/app/database.py
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


# Create async engine
engine = create_async_engine(
    settings.database.url,
    pool_size=settings.database.pool_size,
    max_overflow=settings.database.max_overflow,
    pool_timeout=settings.database.pool_timeout,
    pool_recycle=settings.database.pool_recycle,
    echo=settings.database.echo,
    future=True,
)

# For testing, use NullPool
test_engine = create_async_engine(
    settings.database.url,
    poolclass=NullPool,
    echo=False,
    future=True,
)

# Session factory
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for database session (for use outside FastAPI)."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

### FastAPI Main Application

```python
# backend/app/main.py
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.exceptions import DomainError
from app.core.logging import setup_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    setup_logging()
    logger.info(
        "Starting Clairo API",
        extra={
            "version": settings.app_version,
            "environment": settings.environment,
        }
    )
    yield
    # Shutdown
    logger.info("Shutting down Clairo API")


app = FastAPI(
    title=settings.app_name,
    description="Intelligent Business Advisory Platform for Australian Accounting Practices",
    version=settings.app_version,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors.origins,
    allow_credentials=settings.cors.allow_credentials,
    allow_methods=settings.cors.allow_methods,
    allow_headers=settings.cors.allow_headers,
)


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    """Handle domain-specific errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.message,
            "code": exc.code,
            "details": exc.details,
        }
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": settings.app_version}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs" if settings.debug else None,
    }


# Register module routers here as they are created
# from app.modules.clients.router import router as clients_router
# app.include_router(clients_router, prefix="/api/v1")
```

### Core Module Files

```python
# backend/app/core/exceptions.py
from typing import Any


class DomainError(Exception):
    """Base class for domain-specific errors."""

    status_code: int = 400
    code: str = "DOMAIN_ERROR"

    def __init__(
        self,
        message: str,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        self.message = message
        if code:
            self.code = code
        self.details = details or {}
        super().__init__(self.message)


class NotFoundError(DomainError):
    """Resource not found error."""

    status_code = 404
    code = "NOT_FOUND"

    def __init__(
        self,
        resource_type: str,
        resource_id: str,
        details: dict[str, Any] | None = None,
    ):
        message = f"{resource_type} with ID '{resource_id}' not found"
        super().__init__(message, details=details)
        self.details["resource_type"] = resource_type
        self.details["resource_id"] = resource_id


class ValidationError(DomainError):
    """Business rule validation error."""

    status_code = 400
    code = "VALIDATION_ERROR"


class AuthorizationError(DomainError):
    """Authorization/permission error."""

    status_code = 403
    code = "FORBIDDEN"


class ConflictError(DomainError):
    """Resource conflict error."""

    status_code = 409
    code = "CONFLICT"


class ExternalServiceError(DomainError):
    """External service error."""

    status_code = 502
    code = "EXTERNAL_SERVICE_ERROR"

    def __init__(
        self,
        service_name: str,
        operation: str,
        original_error: str | None = None,
    ):
        message = f"External service '{service_name}' failed during '{operation}'"
        super().__init__(message)
        self.details["service_name"] = service_name
        self.details["operation"] = operation
        if original_error:
            self.details["original_error"] = original_error
```

```python
# backend/app/core/events.py
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Callable, Type
from uuid import UUID, uuid4
import asyncio
from collections import defaultdict

from pydantic import BaseModel, Field


class DomainEvent(BaseModel):
    """Base class for domain events."""

    event_id: UUID = Field(default_factory=uuid4)
    event_type: str = ""
    occurred_at: datetime = Field(default_factory=datetime.utcnow)
    aggregate_id: UUID | None = None
    aggregate_type: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)

    def __init__(self, **data):
        super().__init__(**data)
        if not self.event_type:
            self.event_type = self.__class__.__name__


EventHandler = Callable[[DomainEvent], Any]


class EventBus:
    """In-process event bus for module communication."""

    def __init__(self):
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._async_handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(
        self,
        event_type: Type[DomainEvent],
        handler: EventHandler,
        async_handler: bool = False,
    ) -> None:
        """Subscribe a handler to an event type."""
        event_name = event_type.__name__
        if async_handler:
            self._async_handlers[event_name].append(handler)
        else:
            self._handlers[event_name].append(handler)

    async def publish(self, event: DomainEvent) -> None:
        """Publish an event to all subscribers."""
        event_name = event.event_type

        # Call sync handlers
        for handler in self._handlers.get(event_name, []):
            handler(event)

        # Call async handlers concurrently
        async_handlers = self._async_handlers.get(event_name, [])
        if async_handlers:
            await asyncio.gather(
                *(handler(event) for handler in async_handlers),
                return_exceptions=True,
            )

    def clear(self) -> None:
        """Clear all handlers (useful for testing)."""
        self._handlers.clear()
        self._async_handlers.clear()


# Global event bus instance
event_bus = EventBus()
```

```python
# backend/app/core/logging.py
import logging
import sys
from typing import Any

import structlog
from structlog.types import Processor

from app.config import settings


def setup_logging() -> None:
    """Configure structured logging."""

    # Determine log level
    log_level = logging.DEBUG if settings.debug else logging.INFO

    # Configure structlog processors
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if settings.environment == "development":
        # Pretty printing for development
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        # JSON output for production
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a logger instance."""
    return structlog.get_logger(name)


def mask_sensitive(data: dict[str, Any], keys: set[str] | None = None) -> dict[str, Any]:
    """Mask sensitive values in a dictionary."""
    if keys is None:
        keys = {"password", "secret", "token", "api_key", "access_key", "secret_key"}

    result = {}
    for key, value in data.items():
        if any(sensitive in key.lower() for sensitive in keys):
            result[key] = "***MASKED***"
        elif isinstance(value, dict):
            result[key] = mask_sensitive(value, keys)
        else:
            result[key] = value
    return result
```

```python
# backend/app/core/security.py
from datetime import datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from pydantic import BaseModel

from app.config import settings
from app.core.exceptions import AuthorizationError


class TokenPayload(BaseModel):
    """JWT token payload."""

    sub: str  # Subject (user ID)
    exp: datetime  # Expiration
    iat: datetime  # Issued at
    tenant_id: str | None = None
    roles: list[str] = []


def create_access_token(
    subject: str,
    tenant_id: str | None = None,
    roles: list[str] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a new access token."""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.security.access_token_expire_minutes
        )

    payload = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.utcnow(),
        "tenant_id": tenant_id,
        "roles": roles or [],
    }

    return jwt.encode(
        payload,
        settings.security.secret_key.get_secret_value(),
        algorithm=settings.security.algorithm,
    )


def decode_access_token(token: str) -> TokenPayload:
    """Decode and validate an access token."""
    try:
        payload = jwt.decode(
            token,
            settings.security.secret_key.get_secret_value(),
            algorithms=[settings.security.algorithm],
        )
        return TokenPayload(**payload)
    except JWTError as e:
        raise AuthorizationError(
            message="Invalid or expired token",
            details={"error": str(e)},
        )


def verify_tenant_access(token_payload: TokenPayload, tenant_id: str) -> bool:
    """Verify the token has access to the specified tenant."""
    if token_payload.tenant_id is None:
        return False
    return token_payload.tenant_id == tenant_id
```

```python
# backend/app/core/dependencies.py
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.security import TokenPayload, decode_access_token
from app.core.exceptions import AuthorizationError


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
) -> TokenPayload:
    """Get current user from authorization header."""
    if not authorization:
        raise AuthorizationError(message="Missing authorization header")

    if not authorization.startswith("Bearer "):
        raise AuthorizationError(message="Invalid authorization scheme")

    token = authorization.removeprefix("Bearer ")
    return decode_access_token(token)


# Type aliases for dependency injection
DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[TokenPayload, Depends(get_current_user)]
```

### Celery Configuration

```python
# backend/app/tasks/celery_app.py
from celery import Celery

from app.config import settings

celery_app = Celery(
    "clairo",
    broker=settings.celery.broker_url,
    backend=settings.celery.result_backend,
)

celery_app.conf.update(
    task_default_queue=settings.celery.task_default_queue,
    task_time_limit=settings.celery.task_time_limit,
    task_soft_time_limit=settings.celery.task_soft_time_limit,
    worker_prefetch_multiplier=settings.celery.worker_prefetch_multiplier,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_send_task_events=True,
    task_send_sent_event=True,
)

# Auto-discover tasks from modules
celery_app.autodiscover_tasks(["app.tasks"])


@celery_app.task(bind=True, max_retries=3)
def example_task(self, data: dict) -> dict:
    """Example task with retry configuration."""
    try:
        # Task implementation
        return {"status": "completed", "data": data}
    except Exception as exc:
        # Exponential backoff retry
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
```

### Alembic Configuration

```python
# backend/alembic/env.py
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import settings
from app.database import Base

# Import all models for Alembic to detect them
# from app.modules.clients.models import Client
# from app.modules.bas.models import BasPeriod

config = context.config

# Set the database URL from settings
config.set_main_option("sqlalchemy.url", settings.database.url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with connection."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in async mode."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### pyproject.toml

```toml
# backend/pyproject.toml
[project]
name = "clairo-backend"
version = "0.1.0"
description = "Clairo Backend API - Intelligent Business Advisory Platform"
readme = "README.md"
requires-python = ">=3.12"
license = {text = "Proprietary"}
authors = [
    {name = "Clairo Team"}
]

dependencies = [
    # Web framework
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",

    # Validation
    "pydantic>=2.6.0",
    "pydantic-settings>=2.1.0",

    # Database
    "sqlalchemy[asyncio]>=2.0.25",
    "asyncpg>=0.29.0",
    "alembic>=1.13.0",

    # Cache & Queue
    "redis>=5.0.0",
    "celery[redis]>=5.3.0",

    # Vector Database
    "qdrant-client>=1.7.0",

    # Object Storage
    "minio>=7.2.0",

    # Security
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",

    # HTTP Client
    "httpx>=0.26.0",

    # Logging
    "structlog>=24.1.0",

    # Utilities
    "python-multipart>=0.0.9",
]

[project.optional-dependencies]
dev = [
    # Testing
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "factory-boy>=3.3.0",
    "httpx>=0.26.0",

    # Type checking
    "mypy>=1.8.0",

    # Linting & Formatting
    "ruff>=0.2.0",

    # Pre-commit
    "pre-commit>=3.6.0",
]

ai = [
    # LLM
    "anthropic>=0.18.0",
    "openai>=1.12.0",

    # RAG Framework
    "langchain>=0.1.0",
    "langchain-anthropic>=0.1.0",
    "langchain-community>=0.0.20",
    "langgraph>=0.0.40",

    # Data Processing
    "pandas>=2.2.0",
    "numpy>=1.26.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["app"]

[tool.ruff]
target-version = "py312"
line-length = 88
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # Pyflakes
    "I",      # isort
    "N",      # pep8-naming
    "UP",     # pyupgrade
    "B",      # flake8-bugbear
    "C4",     # flake8-comprehensions
    "DTZ",    # flake8-datetimez
    "T10",    # flake8-debugger
    "ISC",    # flake8-implicit-str-concat
    "ICN",    # flake8-import-conventions
    "PIE",    # flake8-pie
    "PT",     # flake8-pytest-style
    "Q",      # flake8-quotes
    "RSE",    # flake8-raise
    "RET",    # flake8-return
    "SIM",    # flake8-simplify
    "TID",    # flake8-tidy-imports
    "TCH",    # flake8-type-checking
    "ARG",    # flake8-unused-arguments
    "PTH",    # flake8-use-pathlib
    "ERA",    # eradicate
    "PL",     # pylint
    "RUF",    # ruff-specific
]
ignore = [
    "E501",   # line too long (handled by formatter)
    "PLR0913", # too many arguments
]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
skip-magic-trailing-comma = false
line-ending = "auto"

[tool.ruff.isort]
known-first-party = ["app"]

[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_ignores = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
plugins = ["pydantic.mypy"]

[[tool.mypy.overrides]]
module = ["celery.*", "redis.*", "minio.*"]
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
python_files = ["test_*.py"]
python_functions = ["test_*"]
addopts = [
    "-v",
    "--strict-markers",
    "--cov=app",
    "--cov-report=term-missing",
    "--cov-report=html:htmlcov",
    "--cov-fail-under=80"
]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks tests that require database",
    "e2e: marks end-to-end tests"
]
filterwarnings = [
    "ignore::DeprecationWarning"
]

[tool.coverage.run]
source = ["app"]
omit = ["*/tests/*", "*/__pycache__/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
]
```

### Frontend package.json

```json
{
  "name": "clairo-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint && eslint . --ext .ts,.tsx",
    "lint:fix": "eslint . --ext .ts,.tsx --fix",
    "format": "prettier --write \"src/**/*.{ts,tsx,json,css}\"",
    "format:check": "prettier --check \"src/**/*.{ts,tsx,json,css}\"",
    "type-check": "tsc --noEmit",
    "generate-api-types": "openapi-typescript http://localhost:8000/openapi.json -o src/types/api.ts",
    "test": "jest",
    "test:watch": "jest --watch",
    "test:coverage": "jest --coverage"
  },
  "dependencies": {
    "next": "14.1.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",

    "@tanstack/react-query": "^5.17.0",
    "@tanstack/react-query-devtools": "^5.17.0",
    "zustand": "^4.5.0",

    "openapi-fetch": "^0.8.0",

    "react-hook-form": "^7.49.0",
    "@hookform/resolvers": "^3.3.0",
    "zod": "^3.22.0",

    "tailwindcss": "^3.4.0",
    "tailwind-merge": "^2.2.0",
    "class-variance-authority": "^0.7.0",
    "clsx": "^2.1.0",

    "@radix-ui/react-slot": "^1.0.0",
    "lucide-react": "^0.309.0"
  },
  "devDependencies": {
    "typescript": "^5.3.0",
    "@types/node": "^20.10.0",
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",

    "eslint": "^8.56.0",
    "eslint-config-next": "14.1.0",
    "eslint-config-prettier": "^9.1.0",
    "eslint-plugin-react": "^7.33.0",
    "eslint-plugin-react-hooks": "^4.6.0",
    "@typescript-eslint/eslint-plugin": "^6.19.0",
    "@typescript-eslint/parser": "^6.19.0",

    "prettier": "^3.2.0",
    "prettier-plugin-tailwindcss": "^0.5.0",

    "postcss": "^8.4.0",
    "autoprefixer": "^10.4.0",

    "openapi-typescript": "^6.7.0",

    "jest": "^29.7.0",
    "@testing-library/react": "^14.1.0",
    "@testing-library/jest-dom": "^6.2.0",
    "jest-environment-jsdom": "^29.7.0"
  }
}
```

### Frontend Configuration Files

```typescript
// frontend/tailwind.config.ts
import type { Config } from "tailwindcss";

const config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  prefix: "",
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
} satisfies Config;

export default config;
```

```json
// frontend/.eslintrc.json
{
  "extends": [
    "next/core-web-vitals",
    "prettier",
    "plugin:@typescript-eslint/recommended"
  ],
  "parser": "@typescript-eslint/parser",
  "plugins": ["@typescript-eslint"],
  "rules": {
    "@typescript-eslint/no-unused-vars": [
      "error",
      {
        "argsIgnorePattern": "^_",
        "varsIgnorePattern": "^_"
      }
    ],
    "@typescript-eslint/no-explicit-any": "error",
    "@typescript-eslint/explicit-function-return-type": "off",
    "@typescript-eslint/explicit-module-boundary-types": "off",
    "react/react-in-jsx-scope": "off",
    "react/prop-types": "off",
    "react-hooks/rules-of-hooks": "error",
    "react-hooks/exhaustive-deps": "warn",
    "import/order": [
      "error",
      {
        "groups": [
          "builtin",
          "external",
          "internal",
          "parent",
          "sibling",
          "index"
        ],
        "newlines-between": "always",
        "alphabetize": {
          "order": "asc",
          "caseInsensitive": true
        }
      }
    ]
  }
}
```

```json
// frontend/.prettierrc
{
  "semi": true,
  "trailingComma": "es5",
  "singleQuote": false,
  "tabWidth": 2,
  "useTabs": false,
  "printWidth": 80,
  "bracketSpacing": true,
  "arrowParens": "always",
  "plugins": ["prettier-plugin-tailwindcss"]
}
```

```json
// frontend/components.json (shadcn/ui config)
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "new-york",
  "rsc": true,
  "tsx": true,
  "tailwind": {
    "config": "tailwind.config.ts",
    "css": "src/app/globals.css",
    "baseColor": "slate",
    "cssVariables": true,
    "prefix": ""
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils",
    "ui": "@/components/ui",
    "lib": "@/lib",
    "hooks": "@/hooks"
  }
}
```

### Frontend Core Files

```typescript
// frontend/src/lib/utils.ts
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

```typescript
// frontend/src/lib/query-client.ts
import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      gcTime: 1000 * 60 * 30, // 30 minutes (formerly cacheTime)
      retry: 3,
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: 1,
    },
  },
});
```

```typescript
// frontend/src/lib/api.ts
import createClient from "openapi-fetch";
import type { paths } from "@/types/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = createClient<paths>({
  baseUrl: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Helper to set auth token
export function setAuthToken(token: string | null) {
  if (token) {
    api.use({
      onRequest: ({ request }) => {
        request.headers.set("Authorization", `Bearer ${token}`);
        return request;
      },
    });
  }
}
```

```typescript
// frontend/src/stores/example.store.ts
import { create } from "zustand";
import { devtools, persist } from "zustand/middleware";

interface ExampleState {
  count: number;
  increment: () => void;
  decrement: () => void;
  reset: () => void;
}

export const useExampleStore = create<ExampleState>()(
  devtools(
    persist(
      (set) => ({
        count: 0,
        increment: () => set((state) => ({ count: state.count + 1 })),
        decrement: () => set((state) => ({ count: state.count - 1 })),
        reset: () => set({ count: 0 }),
      }),
      {
        name: "example-storage",
      }
    ),
    {
      name: "ExampleStore",
    }
  )
);
```

```tsx
// frontend/src/app/providers.tsx
"use client";

import { QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { type ReactNode } from "react";

import { queryClient } from "@/lib/query-client";

interface ProvidersProps {
  children: ReactNode;
}

export function Providers({ children }: ProvidersProps) {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}
```

```tsx
// frontend/src/app/layout.tsx
import type { Metadata } from "next";
import { Inter } from "next/font/google";

import { Providers } from "./providers";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Clairo",
  description: "Intelligent Business Advisory Platform for Australian Accounting Practices",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
```

### Pre-commit Configuration

```yaml
# .pre-commit-config.yaml
repos:
  # General hooks
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-added-large-files
        args: ['--maxkb=1000']
      - id: check-merge-conflict
      - id: detect-private-key

  # Python - Ruff
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.2.0
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
        files: ^backend/
      - id: ruff-format
        files: ^backend/

  # Python - Type checking
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        files: ^backend/app/
        additional_dependencies:
          - pydantic>=2.6.0
          - types-redis
          - sqlalchemy[mypy]>=2.0.0

  # Frontend - ESLint
  - repo: local
    hooks:
      - id: eslint
        name: ESLint
        entry: bash -c 'cd frontend && npm run lint'
        language: system
        files: ^frontend/.*\.(ts|tsx)$
        pass_filenames: false

  # Frontend - Prettier
  - repo: local
    hooks:
      - id: prettier
        name: Prettier
        entry: bash -c 'cd frontend && npx prettier --write'
        language: system
        files: ^frontend/.*\.(ts|tsx|json|css)$

  # Commit message
  - repo: https://github.com/commitizen-tools/commitizen
    rev: v3.13.0
    hooks:
      - id: commitizen
        stages: [commit-msg]
```

### Environment Templates

```bash
# .env.example (root)
# Docker Compose Configuration
COMPOSE_PROJECT_NAME=clairo

# PostgreSQL
POSTGRES_USER=clairo
POSTGRES_PASSWORD=clairo_dev
POSTGRES_DB=clairo
POSTGRES_PORT=5432

# Redis
REDIS_PORT=6379

# Qdrant
QDRANT_PORT=6333
QDRANT_GRPC_PORT=6334

# MinIO
MINIO_API_PORT=9000
MINIO_CONSOLE_PORT=9001
MINIO_ROOT_USER=clairo
MINIO_ROOT_PASSWORD=clairo_dev
MINIO_BUCKET_NAME=clairo-documents

# Backend
BACKEND_PORT=8000
```

```bash
# backend/.env.example
# Application
APP_NAME=Clairo
APP_VERSION=0.1.0
DEBUG=true
ENVIRONMENT=development

# Database
DATABASE_URL=postgresql+asyncpg://clairo:clairo_dev@localhost:5432/clairo
DATABASE_POOL_SIZE=5
DATABASE_MAX_OVERFLOW=10
DATABASE_POOL_TIMEOUT=30
DATABASE_POOL_RECYCLE=1800
DATABASE_ECHO=false

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_MAX_CONNECTIONS=10

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_GRPC_PORT=6334
# QDRANT_API_KEY=  # Set in production

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=clairo
MINIO_SECRET_KEY=clairo_dev
MINIO_BUCKET_NAME=clairo-documents
MINIO_SECURE=false

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
CELERY_TASK_DEFAULT_QUEUE=clairo
CELERY_TASK_TIME_LIMIT=300

# Security
SECURITY_SECRET_KEY=CHANGE_ME_IN_PRODUCTION_USE_LONG_RANDOM_STRING
SECURITY_ALGORITHM=HS256
SECURITY_ACCESS_TOKEN_EXPIRE_MINUTES=30
# SECURITY_CLERK_SECRET_KEY=  # Set when using Clerk
# SECURITY_CLERK_PUBLISHABLE_KEY=  # Set when using Clerk

# CORS
CORS_ORIGINS=["http://localhost:3000"]
```

```bash
# frontend/.env.example
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:8000

# Clerk (when enabled)
# NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=
# CLERK_SECRET_KEY=
```

### .gitignore

```gitignore
# .gitignore

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Virtual environments
venv/
.venv/
ENV/
env/
.env/

# IDE
.idea/
.vscode/
*.swp
*.swo
*~
.project
.pydevproject
.settings/
*.sublime-workspace
*.sublime-project

# Testing
.tox/
.nox/
.coverage
.coverage.*
htmlcov/
.pytest_cache/
nosetests.xml
coverage.xml
*.cover
*.py,cover
.hypothesis/

# mypy
.mypy_cache/
.dmypy.json
dmypy.json

# Ruff
.ruff_cache/

# Node.js
node_modules/
.pnp
.pnp.js

# Next.js
.next/
out/
build/

# Vercel
.vercel

# TypeScript
*.tsbuildinfo
next-env.d.ts

# Environment files
.env
.env.local
.env.development.local
.env.test.local
.env.production.local
*.env.local

# Docker
docker-compose.override.yml

# Logs
logs/
*.log
npm-debug.log*
yarn-debug.log*
yarn-error.log*
pnpm-debug.log*

# OS
.DS_Store
Thumbs.db

# Secrets (never commit these)
*.pem
*.key
secrets/
credentials/

# Database files
*.db
*.sqlite
*.sqlite3

# Generated files
src/types/api.ts

# Coverage
coverage/
```

---

## Appendix: Scripts

### generate-api-types.sh

```bash
#!/bin/bash
# scripts/generate-api-types.sh

set -e

BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
OUTPUT_FILE="${OUTPUT_FILE:-frontend/src/types/api.ts}"

echo "Fetching OpenAPI schema from $BACKEND_URL/openapi.json..."

# Check if backend is running
if ! curl -s "$BACKEND_URL/health" > /dev/null; then
    echo "Error: Backend is not running at $BACKEND_URL"
    echo "Please start the backend first: docker-compose up backend"
    exit 1
fi

# Generate types
cd frontend
npx openapi-typescript "$BACKEND_URL/openapi.json" -o "src/types/api.ts"

echo "Types generated successfully at $OUTPUT_FILE"
```

### init-postgres.sql

```sql
-- scripts/init-postgres.sql
-- Enable required extensions

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
-- pgvector extension for vector similarity search (Layer 3)
-- CREATE EXTENSION IF NOT EXISTS vector;

-- Create application role
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'clairo_app') THEN
        CREATE ROLE clairo_app WITH LOGIN PASSWORD 'clairo_app_dev';
    END IF;
END
$$;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE clairo TO clairo_app;
```

---

## Design Decisions

### Decision 1: uv over Poetry

**Context:** Python dependency management tool selection.

**Options Considered:**
1. Poetry - Mature, widely adopted
2. uv - Newer, Rust-based, significantly faster

**Decision:** Use uv for development, but structure pyproject.toml to be compatible with both.

**Rationale:**
- uv is 10-100x faster than pip/Poetry for dependency resolution
- pyproject.toml works with both tools
- Development speed matters for DX
- Can switch to Poetry if uv has issues

### Decision 2: Modular Monolith Module Structure

**Context:** How to organize feature modules within the backend.

**Decision:** Each module contains router.py, service.py, schemas.py, models.py, repository.py.

**Rationale:**
- Clear separation of concerns
- Repository pattern enables testing with mocks
- Service layer enforces cross-module communication rules
- Aligns with constitution requirements

### Decision 3: In-Process Event Bus

**Context:** How modules should communicate asynchronously.

**Decision:** Use a simple in-process event bus rather than external message broker.

**Rationale:**
- Simpler infrastructure for MVP
- Sufficient for current scale requirements
- Can upgrade to Redis pub/sub or external broker later
- Reduces operational complexity

### Decision 4: AsyncSession Dependency Injection

**Context:** How to provide database sessions to request handlers.

**Decision:** Use FastAPI dependency injection with get_db generator.

**Rationale:**
- Automatic session lifecycle management
- Proper commit/rollback handling
- Easy to mock in tests
- Aligns with FastAPI best practices

---

Does the design look good? If so, we can move on to the implementation plan.
