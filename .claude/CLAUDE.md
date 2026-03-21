# Clairo — AI-Powered Tax & Advisory Platform

Australian accounting practices are the paying subscribers (tenants). They manage BAS/IAS/FBT compliance and advisory for their clients (businesses). Business owners access a read-only portal.

## Key Terminology

| Term | Meaning |
|------|---------|
| **Tenant** | Accounting practice/firm (the subscriber) |
| **Client** | A business whose BAS the accountant manages |
| **Business Owner** | Owner of a client business (portal user, not subscriber) |

**Tenants pay. Clients are served. Do NOT confuse these.**

## Architecture

Modular monolith: `backend/app/modules/[name]/` — each module has models, schemas, repository, service, router, exceptions. Shared kernel in `core/`. Celery tasks in `tasks/`.

Frontend: Next.js 14 App Router at `frontend/src/app/`. State: Zustand + TanStack Query. Components: shadcn/ui.

### Design Principles

1. **Three Pillars**: Data (Xero) + Compliance (ATO RAG) + Strategy (AI Advisory)
2. **Multi-tenancy**: `tenant_id` on all tables, Row-Level Security
3. **Audit-First**: All financial data changes audited for ATO compliance
4. **Repository Pattern**: All DB access via repositories
5. **AI Human-in-the-Loop**: AI suggests, accountants approve

### Design System

Design skill: `.claude/skills/clairo-design-system/` — read SKILL.md + references/ for all frontend work. Data is the hero. Warm off-white bg, white cards, coral primary CTA, minimal borders, generous whitespace.

### Non-obvious tech choices

- Vector DB: **Pinecone** (single index `clairo-knowledge`, 7 namespaces)
- Embeddings: **Voyage 3.5 lite** (1024 dims, cosine)
- Auth: **Clerk** (OAuth, MFA)
- Email: **Resend**
- Billing: **Stripe**
- RAG retrieval: BM25 + semantic + RRF fusion + cross-encoder reranking

## Speckit Workflow

`/speckit.specify` → `/speckit.plan` → `/speckit.tasks` → `/speckit.implement`

Standards in `.specify/memory/constitution.md`. Roadmap in `specs/ROADMAP.md` (source of truth).

## Key Docs

| Path | What |
|------|------|
| `specs/ROADMAP.md` | Implementation roadmap (SOURCE OF TRUTH) |
| `.specify/memory/constitution.md` | Development standards |
| `docs/solution-design.md` | Technical architecture |
| `docs/xero-api-mapping.md` | Xero integration details |

## Domain Rules

- Australian compliance context: GST, BAS, IAS, PAYG-W, PAYG-I, FBT, STP
- Sydney region, ATO guidelines — platform does NOT give financial advice
- Phases A-E complete, Phase E.5 (ATOtrack) next, F-H not started
