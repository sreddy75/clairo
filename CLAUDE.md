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
- `TaxCodeOverride` has no `session_id` — join via `TaxCodeSuggestion.session_id` using `suggestion_id` FK
- Xero write-back uses queue `xero_writeback`; Celery task is `process_writeback_job` in `app.tasks.xero_writeback`
- `ClassificationRequest.session_id` is no longer unique — partial unique index `WHERE parent_request_id IS NULL` (round-1 only)
- Tax planning annualisation lives at **ingest** (`pull_xero_financials` + `save_manual_financials`) — never re-project downstream. The LLM and calculator both read `financials_data.income`/`expenses` as the single projected set; `financials_data.projection_metadata.ytd_snapshot` preserves the YTD originals. Don't add a second "projected" block.
- Every scenario numeric field must have a **`source_tags`** entry. Modeller auto-tags `before.*` as `derived` and `after.*`/`change.*`/`cash_flow_impact` as `estimated`; inline-confirm (`PATCH /assumptions/{field_path}`) flips to `confirmed`. Never instantiate a scenario without `source_tags`.
- Scenario persistence uses **`TaxScenarioRepository.upsert_by_normalized_title`**, never raw `.create()` in chat flows — a refined title on the same plan is an update, not a new row. The partial unique index `ix_tax_scenarios_plan_normalized_title` enforces this at the DB level.
- **Prompts are suggestions, code is law** — never rely on a prompt instruction to enforce a deterministic business rule. If a rule must always hold (strip meta-scenarios, round floats, coerce enums, inject correct totals), implement it in code that runs after the LLM output. Prompt instructions are hints to guide the LLM toward the right output, but the code layer is the only guarantee. Discovered during Spec 059: adding "don't create a combined scenario" to the prompt failed 5+ times across different phrasings; stripping meta-scenarios from the returned list in code fixed it immediately.

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
- Python 3.12+ (backend), TypeScript 5.x / Next.js 14 (frontend) + FastAPI, SQLAlchemy 2.0, Pydantic v2, Celery + Redis, anthropic SDK, Xero OAuth2 API, React 18, shadcn/ui, TanStack Query, Zustand (049-xero-taxcode-sync)
- PostgreSQL 16 — 4 new tables, 2 modified tables (original scope); +4 columns on `tax_code_overrides` (split scope) (049-xero-taxcode-sync)
- Python 3.12+ (backend), TypeScript 5.x / Next.js 14 (frontend) + FastAPI, SQLAlchemy 2.0, Pydantic v2, stripe SDK, React 18 + shadcn/ui, Clerk (auth) (043-stripe-billing)
- PostgreSQL 16 (no schema changes — all models exist) (043-stripe-billing)
- Python 3.12+ (backend), TypeScript 5.x / Next.js 14 (frontend) + FastAPI, gunicorn, Celery, Docker, GitHub Actions, Vercel CLI (045-infra-launch-polish)
- PostgreSQL 16 (managed), Redis (managed), S3-compatible object storage (045-infra-launch-polish)
- Python 3.12+ (backend), TypeScript 5.x / Next.js 14 (frontend) + FastAPI, SQLAlchemy 2.0, Anthropic SDK (Claude Sonnet) (046-tax-planning-intelligence)
- PostgreSQL 16 — existing `financials_data` JSONB field on TaxPlan model (046-tax-planning-intelligence)
- TypeScript 5.x / Next.js 14 (App Router) + React 18, Tailwind CSS, shadcn/ui (Sheet, Dialog, Table), lucide-react (icons), Radix UI (primitives) (055-mobile-responsive-ui)
- N/A (frontend-only) (055-mobile-responsive-ui)
- Python 3.12+ (backend), TypeScript 5.x / Next.js 14 (frontend) + FastAPI, SQLAlchemy 2.0, Pydantic v2, Alembic, React 18 + shadcn/ui, Clerk (058-bas-workflow-tracker)
- PostgreSQL 16 (3 new tables: `practice_clients`, `client_quarter_exclusions`, `client_note_history`; 1 modified: `practice_users`) (058-bas-workflow-tracker)
- Python 3.12+ (backend), TypeScript 5.x / Next.js 14 (frontend) + FastAPI, SQLAlchemy 2.0, Pydantic v2, Alembic, Anthropic SDK, Voyage 3.5 lite, Pinecone (for citation verifier swap), React 18 + shadcn/ui (059-tax-planning-calculation-correctness)
- PostgreSQL 16 — 3 new columns on `tax_scenarios`, 1 new partial-unique index on `tax_scenarios`, 1 new key on `tax_plans.financials_data` JSONB (`projection_metadata`). No new tables. (059-tax-planning-calculation-correctness)

## Recent Changes
- 049-xero-taxcode-sync: Xero write-back, multi-round client send-back, portal IDK validation, agent notes
  - New: `xero_writeback_jobs`, `xero_writeback_items`, `agent_transaction_notes`, `client_classification_rounds`
  - Altered: `tax_code_overrides` (+writeback_status), `classification_requests` (+parent_request_id, +round_number)
  - New services: `XeroWritebackService`, Celery task `process_writeback_job` (queue: `xero_writeback`)
  - New frontend: `SyncToXeroButton`, `WritebackProgressPanel`, `WritebackResultsSummary`, `SendBackModal`, `IdkItemsSection`
  - `TaxCodeOverride.writeback_status`: pending_sync → synced after write-back
- 046-ai-tax-code-resolution: Added Python 3.12+ (backend), TypeScript/Next.js 14 (frontend) + FastAPI, SQLAlchemy 2.0, Celery, Anthropic SDK (Claude Sonnet for LLM tier), React 18 + shadcn/ui
