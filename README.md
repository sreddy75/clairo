# Clairo

**AI-Powered Tax & Advisory Platform for Australian Accounting Practices**

Clairo helps Australian accountants manage tax compliance (BAS, IAS, FBT), advisory services, and client relationships through a three-pillar approach:

1. **Data** - Integration with Xero/MYOB for real-time financial data
2. **Compliance** - ATO guidelines and tax rulings via RAG system
3. **Strategy** - Business growth and tax optimization insights

## Architecture

- **Backend**: Python 3.12 + FastAPI (Modular Monolith)
- **Frontend**: Next.js 14 + React + Tailwind + shadcn/ui
- **Database**: PostgreSQL 16 + Qdrant (vectors)
- **Cache/Queue**: Redis + Celery
- **Storage**: MinIO (S3-compatible)

## Prerequisites

- **Docker** 24.0+ and Docker Compose v2
- **Python** 3.12+ (for local development outside Docker)
- **Node.js** 20+ (for frontend development)
- **uv** (recommended) or pip for Python package management

## Quick Start

### 1. Clone and Setup Environment

```bash
# Clone the repository
git clone <repository-url>
cd BAS

# Copy environment file
cp .env.example .env
cp backend/.env.example backend/.env
```

### 2. Start Infrastructure Services

```bash
# Start all services (PostgreSQL, Redis, Qdrant, MinIO, Backend, Celery)
docker-compose up -d

# Check service health
docker-compose ps

# View logs
docker-compose logs -f backend
```

### 3. Access Services

| Service | URL | Purpose |
|---------|-----|---------|
| Backend API | http://localhost:8000 | FastAPI application |
| API Docs | http://localhost:8000/docs | Swagger UI |
| MinIO Console | http://localhost:9001 | Object storage admin |
| Qdrant Dashboard | http://localhost:6333/dashboard | Vector DB admin |

### 4. Frontend Development (separate terminal)

```bash
cd frontend
npm install
npm run dev
```

Frontend will be available at http://localhost:3000

## Development Commands

### Backend

```bash
# Enter backend directory
cd backend

# Install dependencies (using uv)
uv sync

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=app --cov-report=html

# Run linting
uv run ruff check .

# Run formatting
uv run ruff format .

# Run type checking
uv run mypy app

# Create database migration
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run alembic upgrade head
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev

# Run linting
npm run lint

# Run type checking
npm run type-check

# Build for production
npm run build

# Generate API types from OpenAPI
npm run generate-api-types
```

### Docker

```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# Stop and remove volumes (clean slate)
docker-compose down -v

# Rebuild backend after dependency changes
docker-compose build backend

# View logs
docker-compose logs -f [service-name]

# Execute command in container
docker-compose exec backend bash
```

## Project Structure

```
BAS/
├── backend/                 # Python FastAPI backend
│   ├── app/
│   │   ├── core/           # Shared kernel (events, exceptions, security)
│   │   ├── modules/        # Feature modules
│   │   └── tasks/          # Celery background tasks
│   ├── tests/              # Test suite
│   └── alembic/            # Database migrations
│
├── frontend/               # Next.js frontend
│   └── src/
│       ├── app/            # App Router pages
│       ├── components/     # React components
│       └── lib/            # Utilities and API client
│
├── specs/                  # Feature specifications
│   └── 001-project-scaffolding/
│
├── planning/               # Planning documentation
├── docs/                   # Additional documentation
├── scripts/                # Utility scripts
└── infrastructure/         # Deployment configuration
```

## Documentation

| Document | Description |
|----------|-------------|
| [specs/ROADMAP.md](specs/ROADMAP.md) | Implementation roadmap and current focus |
| [planning/README.md](planning/README.md) | GTM strategy and milestones |
| [.specify/memory/constitution.md](.specify/memory/constitution.md) | Development standards |

## Authentication

Clairo uses [Clerk](https://clerk.com) for authentication with the following features:

- Email/password and social login support
- Multi-factor authentication (MFA)
- Team invitations with role-based access
- Session management

### Setup for Development

1. Create a Clerk account at https://clerk.com
2. Create a new application
3. Get your API keys from the Clerk Dashboard
4. Configure environment variables:

**Frontend** (`frontend/.env.local`):
```bash
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
```

**Backend** (`.env` or `backend/.env`):
```bash
CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
CLERK_JWKS_URL=https://your-app.clerk.accounts.dev/.well-known/jwks.json
```

### Auth Flow

1. User signs up via Clerk at `/sign-up`
2. After Clerk signup, user is redirected to `/onboarding`
3. Onboarding creates their practice (tenant) in the backend
4. User receives a welcome email via Resend
5. User is redirected to `/dashboard`

## Email Notifications

Clairo uses [Resend](https://resend.com) for transactional emails:

- Welcome emails on signup
- Team invitation emails
- Tax lodgement reminders
- Lodgement confirmations

Configure in backend `.env`:
```bash
RESEND_API_KEY=re_...
RESEND_FROM_EMAIL=Clairo <noreply@clairo.ai>
RESEND_ENABLED=true  # Set to false for testing
```

## Environment Variables

See `.env.example` for all available configuration options.

Key variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_*` | PostgreSQL connection | clairo/clairo_dev |
| `REDIS_URL` | Redis connection | redis://redis:6379/0 |
| `QDRANT_HOST` | Qdrant host | qdrant |
| `MINIO_*` | MinIO S3 storage | clairo/clairo_dev |
| `JWT_SECRET_KEY` | JWT signing key | (generate for production) |
| `CLERK_*` | Clerk authentication | (required) |
| `RESEND_*` | Email notifications | (required for emails) |

## Testing

```bash
# Backend tests
cd backend
uv run pytest

# With coverage
uv run pytest --cov=app --cov-report=term-missing

# Frontend tests
cd frontend
npm run test
```

## Contributing

1. Read the [constitution](.specify/memory/constitution.md) for development standards
2. Check [ROADMAP.md](specs/ROADMAP.md) for current focus
3. Follow the speckit workflow for new features:
   - `/speckit.specify` - Create specification
   - `/speckit.plan` - Create implementation plan
   - `/speckit.tasks` - Generate task list
   - `/speckit.implement` - Execute with TDD

## License

Proprietary - All rights reserved

---

*Clairo - AI-Powered Tax & Advisory Platform*
