# Clairo Development Guidelines

## Commands

```sh
# Backend
cd backend && uv run pytest              # Tests
cd backend && uv run pytest -k "name"    # Single test
cd backend && uv run ruff check .        # Lint
cd backend && uv run ruff format .       # Format
cd backend && uv run alembic upgrade head # Migrations

# Frontend (must run from frontend/)
cd frontend && npm run dev               # Dev server
cd frontend && npm run lint              # Lint
cd frontend && npx tsc --noEmit          # Typecheck

# Infrastructure
docker-compose up -d                     # Start all services

# Full validation (before PR)
cd backend && uv run ruff check . && uv run pytest && cd ../frontend && npm run lint && npx tsc --noEmit
```

## Common Mistakes

<!-- Add here every time Claude makes a project-specific mistake. This is the highest-value section. -->

- Knowledge module uses **Pinecone** (not Qdrant) — field is still named `qdrant_point_id` (migration artifact), don't create new Qdrant references
- Vector embeddings use **Voyage 3.5 lite** (1024 dims, cosine similarity), not OpenAI embeddings
- Don't use `HTTPException` in service layer — raise domain exceptions from `core/exceptions.py`, convert in router
- Always include `tenant_id` in repository queries — missing it breaks multi-tenancy isolation
- Frontend uses **Next.js App Router** (not Pages Router) — routes go in `app/`, not `pages/`
- Celery tasks must be idempotent — they may be retried
- Never import from one module's internals into another — use the module's public service interface
- Repository methods use `flush()` not `commit()` — session lifecycle is managed by the caller
- Always use shadcn/ui components (`Button`, `Card`, `Table`, `Badge`) — never raw `<div>`/`<button>` with inline Tailwind
- Always use CSS variable tokens — never hardcode hex/hsl color values
- Always import shared formatters (`formatCurrency`, `formatDate`) from `@/lib/formatters` — never define locally
- Always use `cn()` from `@/lib/utils` for conditional classes — never string concatenation
- Use `stone-*` palette for dark mode grays — never `gray-*`
- Status colors have meaning: green=good, amber=attention, red=urgent — never decorative

## Active Technologies
- Python 3.12+ (backend), TypeScript/Next.js 14 (frontend) + FastAPI, SQLAlchemy 2.0, Celery, Anthropic SDK (Claude Sonnet for LLM tier), React 18 + shadcn/ui (046-ai-tax-code-resolution)
- PostgreSQL 16 (2 new tables: `tax_code_suggestions`, `tax_code_overrides`) (046-ai-tax-code-resolution)
- Python 3.12 (backend), TypeScript 5.x / Next.js 14 (frontend) + FastAPI, SQLAlchemy 2.0, Pydantic v2, anthropic SDK, Resend, Clerk (accountant auth), portal magic link (client auth) (047-client-transaction-classification)
- PostgreSQL 16 (2 new tables: `classification_requests`, `client_classifications`) (047-client-transaction-classification)
- Python 3.12+ (backend), TypeScript 5.x / Next.js 14 (frontend) + FastAPI, SQLAlchemy 2.0, Pydantic v2, anthropic SDK, OpenAI Whisper API (transcription), React 18 + shadcn/ui (048-voice-feedback-portal)
- PostgreSQL 16 (3 new tables: `feedback_submissions`, `feedback_messages`, `feedback_comments`), MinIO (audio file storage) (048-voice-feedback-portal)
- Python 3.12+ (backend), TypeScript 5.x / Next.js 14 (frontend) + FastAPI, SQLAlchemy 2.0, Pydantic v2, anthropic SDK (Claude Sonnet for AI scenarios), weasyprint (PDF), Jinja2 (PDF templates), React 18 + shadcn/ui (049-ai-tax-planning)
- PostgreSQL 16 (4 new tables: `tax_rate_configs`, `tax_plans`, `tax_scenarios`, `tax_plan_messages`) (049-ai-tax-planning)
- Python 3.12+ (backend), TypeScript 5.x / Next.js 14 (frontend) + FastAPI, SQLAlchemy 2.0, Pydantic v2, anthropic SDK, Voyage 3.5 lite, Pinecone, sentence-transformers (cross-encoder reranker) (050-rag-tax-planning)
- PostgreSQL 16 (2 new JSONB columns on `tax_plan_messages`), Pinecone `clairo-knowledge` index (`compliance_knowledge` namespace) (050-rag-tax-planning)
- Python 3.12+ (backend), TypeScript 5.x / Next.js 14 (frontend) + FastAPI, SQLAlchemy 2.0, Celery, Anthropic SDK (Claude Sonnet), Pydantic v2, React 18 + shadcn/ui (041-multi-agent-tax-planning)
- PostgreSQL 16 (2 new tables: `tax_plan_analyses`, `implementation_items`) (041-multi-agent-tax-planning)
- Python 3.12+ (backend), TypeScript 5.x / Next.js 14 (frontend) + FastAPI, SQLAlchemy 2.0, Pydantic v2, Anthropic SDK (Claude Sonnet), Voyage 3.5 lite (embeddings), Resend (email), React 18 + shadcn/ui, existing A2UI system (051-ai-discovery-agent)
- PostgreSQL 16 (9 new tables, pgvector for workflow embeddings), MinIO (artifact file storage) (051-ai-discovery-agent)
- Python 3.12+ (backend), TypeScript 5.x / Next.js 14 (frontend) + FastAPI, SQLAlchemy 2.0, Pydantic v2, Anthropic SDK, React 18 + shadcn/ui, Clerk (auth), PostHog (analytics), Sentry (error tracking) (052-beta-legal-compliance)
- PostgreSQL 16 (3 new columns on existing `users` table, no new tables) (052-beta-legal-compliance)
- Python 3.12+ (backend), TypeScript 5.x / Next.js 14 (frontend) + FastAPI, SQLAlchemy 2.0, Pydantic v2, pytest + pytest-asyncio, factory_boy (054-onboarding-hardening)
- PostgreSQL 16 (16 new RLS policies, no schema changes) (054-onboarding-hardening)

## Recent Changes
- 046-ai-tax-code-resolution: Added Python 3.12+ (backend), TypeScript/Next.js 14 (frontend) + FastAPI, SQLAlchemy 2.0, Celery, Anthropic SDK (Claude Sonnet for LLM tier), React 18 + shadcn/ui
