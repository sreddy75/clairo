# Requirements Document: Project Scaffolding

## Introduction

This document defines the requirements for Clairo project scaffolding (Spec 001 - M0: Foundation). The scaffolding establishes the foundational development environment and codebase structure for the Clairo platform - an Intelligent Business Advisory Platform for Australian Accounting Practices.

The scaffolding must implement a modular monolith architecture as mandated by the constitution, with clear module boundaries, async database access via repository pattern, and comprehensive development tooling. This foundation will support all four layers of the platform: Core BAS Platform (L1), Business Owner Engagement (L2), Knowledge & AI (L3), and Proactive Advisory (L4).

---

## Requirements

### Requirement 1: Docker Compose Local Development Environment

**User Story:** As a developer, I want a containerized local development environment, so that I can run all required services consistently across different machines without manual installation.

#### Acceptance Criteria

1. WHEN a developer runs `docker-compose up` THEN the system SHALL start all required services (PostgreSQL, Redis, Qdrant, MinIO) in the correct order with health checks.

2. WHEN PostgreSQL container starts THEN the system SHALL provision PostgreSQL 16 with the pgvector extension enabled for vector similarity search.

3. WHEN Redis container starts THEN the system SHALL provision Redis 7 configured for both caching and Celery broker functionality with appropriate memory limits.

4. WHEN Qdrant container starts THEN the system SHALL provision Qdrant vector database with persistent storage volume and REST API exposed on a configurable port.

5. WHEN MinIO container starts THEN the system SHALL provision S3-compatible object storage with a default bucket created and credentials matching environment configuration.

6. WHEN any container stops unexpectedly THEN Docker Compose SHALL restart the container automatically up to a configurable maximum retry count.

7. WHEN the developer runs `docker-compose down -v` THEN the system SHALL cleanly remove all containers and optionally all persistent volumes.

8. IF a service port conflicts with a host port THEN the system SHALL allow port remapping via environment variables without modifying docker-compose.yml.

---

### Requirement 2: Backend Project Structure (Modular Monolith)

**User Story:** As a developer, I want a well-organized modular monolith backend structure, so that I can develop features in isolated modules while maintaining a single deployable unit.

#### Acceptance Criteria

1. WHEN the backend is scaffolded THEN the system SHALL create the directory structure as defined in the constitution: `backend/app/` with `main.py`, `config.py`, `database.py`, `core/`, `modules/`, and `tasks/` directories.

2. WHEN the core module is created THEN it SHALL contain `events.py` (in-process event bus), `exceptions.py` (domain exceptions), `security.py` (auth utilities), and `logging.py` (structured logging).

3. WHEN a module template is created THEN it SHALL contain `router.py`, `service.py`, `schemas.py`, `models.py`, and `repository.py` files following the repository pattern.

4. WHEN `main.py` is executed THEN the system SHALL initialize FastAPI with CORS, middleware, and modular router registration.

5. WHEN modules communicate THEN they SHALL use the service layer only; direct cross-module database queries are prohibited.

6. WHEN domain errors occur in services THEN they SHALL raise domain-specific exceptions (not HTTPException); HTTP exceptions SHALL only be raised in the API layer.

---

### Requirement 3: Pydantic Settings Configuration

**User Story:** As a developer, I want centralized configuration management using Pydantic settings, so that I can manage environment-specific settings with validation and type safety.

#### Acceptance Criteria

1. WHEN the application starts THEN the system SHALL load configuration from environment variables using Pydantic Settings with validation.

2. WHEN a required configuration value is missing THEN the system SHALL fail to start with a clear error message indicating the missing variable.

3. WHEN configuration is loaded THEN it SHALL include sections for: database, Redis, Qdrant, MinIO, Celery, security, and feature flags.

4. WHEN running in development mode THEN the system SHALL load configuration from `.env` files with `.env.local` taking precedence.

5. IF a configuration value fails validation THEN the system SHALL provide a descriptive error message including the expected type and constraints.

6. WHEN secrets are logged THEN the system SHALL mask sensitive values (passwords, API keys, tokens) in log output.

---

### Requirement 4: Async SQLAlchemy 2.0 Database Setup

**User Story:** As a developer, I want an async database layer with connection pooling, so that I can efficiently handle concurrent database operations without blocking.

#### Acceptance Criteria

1. WHEN the database module initializes THEN it SHALL create an async SQLAlchemy 2.0 engine with connection pooling configured for production workloads.

2. WHEN a database session is requested THEN the system SHALL provide an `AsyncSession` via dependency injection that automatically handles commit/rollback.

3. WHEN connection pool is configured THEN it SHALL include configurable `pool_size`, `max_overflow`, `pool_timeout`, and `pool_recycle` parameters.

4. WHEN models are defined THEN they SHALL use UUID primary keys, include `created_at` and `updated_at` timestamps, and include `tenant_id` for tenant-scoped tables.

5. WHEN the database connection fails THEN the system SHALL implement retry logic with exponential backoff and circuit breaker pattern.

6. WHEN database sessions are used THEN they SHALL be properly closed after each request to prevent connection leaks.

---

### Requirement 5: Alembic Migrations Setup

**User Story:** As a developer, I want database migrations managed by Alembic, so that I can version control schema changes and safely apply them across environments.

#### Acceptance Criteria

1. WHEN Alembic is initialized THEN it SHALL be configured for async SQLAlchemy with auto-generation from model metadata.

2. WHEN a developer runs `alembic revision --autogenerate` THEN the system SHALL generate a migration file detecting model changes.

3. WHEN a developer runs `alembic upgrade head` THEN the system SHALL apply all pending migrations in order.

4. WHEN a migration fails THEN the system SHALL rollback the transaction and provide a clear error message.

5. WHEN migrations run in CI/CD THEN they SHALL verify migration can be applied to a clean database and rolled back successfully.

6. IF a destructive migration is detected (column drop, table drop) THEN the migration file SHALL include a warning comment requiring manual review.

---

### Requirement 6: Celery Worker Configuration

**User Story:** As a developer, I want Celery configured for background task processing, so that I can offload long-running operations without blocking API requests.

#### Acceptance Criteria

1. WHEN Celery is configured THEN it SHALL use Redis as both broker and result backend with configurable connection parameters.

2. WHEN a Celery worker starts THEN it SHALL auto-discover tasks from the `app/tasks/` directory.

3. WHEN a task is defined THEN it SHALL include retry configuration with exponential backoff, max retries, and dead letter handling.

4. WHEN a task fails after all retries THEN it SHALL log the failure with full context and optionally trigger an alert.

5. WHEN running in development THEN the system SHALL support running Celery worker with auto-reload on code changes.

6. IF task execution exceeds a configurable timeout THEN Celery SHALL terminate the task and mark it as failed.

---

### Requirement 7: Frontend Next.js 14 App Router Structure

**User Story:** As a frontend developer, I want a Next.js 14 project with App Router, so that I can build a modern React application with server components and optimal performance.

#### Acceptance Criteria

1. WHEN the frontend is scaffolded THEN it SHALL create a Next.js 14 project using App Router with the directory structure: `src/app/`, `src/components/`, `src/hooks/`, `src/stores/`, `src/lib/`, and `src/types/`.

2. WHEN the application builds THEN it SHALL use TypeScript with strict mode enabled and path aliases configured.

3. WHEN layouts are created THEN they SHALL use React Server Components by default with client components explicitly marked.

4. WHEN the dev server starts THEN it SHALL support hot module replacement with Fast Refresh.

5. WHEN environment variables are accessed THEN they SHALL be validated at build time with clear error messages for missing required values.

6. IF a page errors during rendering THEN it SHALL display a user-friendly error boundary with optional error reporting.

---

### Requirement 8: Tailwind CSS and shadcn/ui Setup

**User Story:** As a frontend developer, I want Tailwind CSS with shadcn/ui components, so that I can rapidly build consistent, accessible UI components.

#### Acceptance Criteria

1. WHEN Tailwind CSS is configured THEN it SHALL include custom theme configuration matching Clairo brand guidelines with CSS variables for theming.

2. WHEN shadcn/ui is initialized THEN it SHALL be configured with the `components/ui/` directory and New York style as default.

3. WHEN shadcn/ui components are added THEN they SHALL be fully customizable and include proper TypeScript types.

4. WHEN components are styled THEN they SHALL use Tailwind utility classes with consistent spacing, colors, and typography scales.

5. IF dark mode is enabled THEN the system SHALL support theme switching via CSS variables and system preference detection.

6. WHEN building for production THEN unused CSS SHALL be purged to minimize bundle size.

---

### Requirement 9: State Management (TanStack Query + Zustand)

**User Story:** As a frontend developer, I want robust state management for both server and client state, so that I can efficiently manage data fetching, caching, and local UI state.

#### Acceptance Criteria

1. WHEN TanStack Query is configured THEN it SHALL include default options for stale time, cache time, retry logic, and error handling.

2. WHEN API requests are made THEN they SHALL use TanStack Query hooks with proper loading, error, and success states.

3. WHEN Zustand stores are created THEN they SHALL be typed with TypeScript interfaces and support persistence where needed.

4. WHEN server state is fetched THEN TanStack Query SHALL handle caching, background refetching, and cache invalidation.

5. IF an API request fails THEN the query SHALL retry with configurable backoff and eventually display an error state.

6. WHEN the user navigates between pages THEN cached data SHALL be reused to provide instant navigation.

---

### Requirement 10: OpenAPI Type Generation

**User Story:** As a frontend developer, I want TypeScript types automatically generated from the OpenAPI schema, so that I have type-safe API integration with the backend.

#### Acceptance Criteria

1. WHEN the type generation script runs THEN it SHALL fetch the OpenAPI schema from the backend and generate TypeScript types in `src/types/api.ts`.

2. WHEN the backend API changes THEN running the generation script SHALL update frontend types to match.

3. WHEN API client functions are generated THEN they SHALL use `openapi-fetch` for type-safe HTTP requests.

4. WHEN types are generated THEN they SHALL include request body types, response types, path parameters, and query parameters.

5. IF the OpenAPI schema is invalid THEN the generation script SHALL fail with a descriptive error message.

6. WHEN the CI pipeline runs THEN it SHALL verify that generated types are up-to-date with the current OpenAPI schema.

---

### Requirement 11: Forms with React Hook Form and Zod

**User Story:** As a frontend developer, I want type-safe forms with validation, so that I can build robust form experiences with consistent validation behavior.

#### Acceptance Criteria

1. WHEN React Hook Form is configured THEN it SHALL integrate with Zod for schema-based validation.

2. WHEN a form schema is defined with Zod THEN it SHALL be usable with React Hook Form's resolver for automatic validation.

3. WHEN form validation fails THEN error messages SHALL be displayed inline with the relevant form fields.

4. WHEN forms are submitted THEN they SHALL show loading states and disable submission during processing.

5. IF server-side validation returns errors THEN they SHALL be mapped to the appropriate form fields.

6. WHEN form values change THEN validation SHALL run according to the configured mode (onChange, onBlur, or onSubmit).

---

### Requirement 12: Python Linting and Formatting (Ruff)

**User Story:** As a developer, I want consistent Python code quality enforced by Ruff, so that the codebase maintains uniform style and catches common errors.

#### Acceptance Criteria

1. WHEN Ruff is configured THEN it SHALL enforce linting rules compatible with Black formatting, isort import sorting, and flake8 checks.

2. WHEN a developer runs `ruff check` THEN it SHALL report all linting violations in the codebase.

3. WHEN a developer runs `ruff format` THEN it SHALL format all Python files according to configured rules.

4. WHEN code violates linting rules THEN the pre-commit hook SHALL block the commit with a descriptive error.

5. IF auto-fixable issues are detected THEN running `ruff check --fix` SHALL automatically resolve them.

6. WHEN the CI pipeline runs THEN it SHALL fail if any linting violations are present.

---

### Requirement 13: TypeScript Linting and Formatting (ESLint + Prettier)

**User Story:** As a frontend developer, I want consistent TypeScript code quality enforced by ESLint and Prettier, so that the frontend codebase maintains uniform style.

#### Acceptance Criteria

1. WHEN ESLint is configured THEN it SHALL include rules for React, TypeScript, Next.js best practices, and accessibility.

2. WHEN Prettier is configured THEN it SHALL format TypeScript, TSX, JSON, and CSS files with consistent style.

3. WHEN a developer runs `npm run lint` THEN it SHALL report all ESLint violations in the codebase.

4. WHEN a developer runs `npm run format` THEN it SHALL format all files according to Prettier configuration.

5. WHEN code violates linting rules THEN the pre-commit hook SHALL block the commit with descriptive errors.

6. IF ESLint and Prettier rules conflict THEN ESLint SHALL defer to Prettier for formatting-related rules.

---

### Requirement 14: Pre-commit Hooks

**User Story:** As a developer, I want pre-commit hooks enforcing code quality, so that quality issues are caught before code is committed.

#### Acceptance Criteria

1. WHEN pre-commit is configured THEN it SHALL run Ruff (Python), ESLint (TypeScript), and Prettier on staged files.

2. WHEN a developer attempts to commit THEN pre-commit hooks SHALL run automatically and block commits with violations.

3. WHEN pre-commit hooks fail THEN they SHALL provide clear output indicating which files failed and why.

4. WHEN a developer runs `pre-commit run --all-files` THEN it SHALL check all files in the repository.

5. IF a developer needs to bypass hooks THEN they SHALL be able to use `--no-verify` with a clear understanding this is exceptional.

6. WHEN the repository is cloned THEN running `pre-commit install` SHALL set up all hooks for the developer.

---

### Requirement 15: Pytest Configuration

**User Story:** As a developer, I want pytest properly configured for the project, so that I can write and run tests efficiently with proper coverage reporting.

#### Acceptance Criteria

1. WHEN pytest is configured THEN it SHALL include pytest-asyncio for async test support, pytest-cov for coverage, and factory-boy for fixtures.

2. WHEN a developer runs `pytest` THEN it SHALL discover and run all tests in the `tests/` directory.

3. WHEN tests run THEN they SHALL use a separate test database that is created and destroyed for each test session.

4. WHEN coverage is reported THEN it SHALL show line coverage, branch coverage, and highlight uncovered lines.

5. IF test coverage falls below 80% THEN the CI pipeline SHALL fail with a coverage report.

6. WHEN tests are marked with `@pytest.mark.slow` THEN they SHALL be excluded from default runs and included with `--slow` flag.

---

### Requirement 16: Environment Variable Management

**User Story:** As a developer, I want organized environment variable management, so that I can easily configure the application for different environments.

#### Acceptance Criteria

1. WHEN the repository is cloned THEN it SHALL include `.env.example` files documenting all required environment variables.

2. WHEN the application starts THEN it SHALL load variables from `.env` files with `.env.local` taking precedence over `.env`.

3. WHEN environment files are created THEN `.env`, `.env.local`, and any file containing secrets SHALL be excluded from git via `.gitignore`.

4. WHEN a new environment variable is added THEN it SHALL be documented in `.env.example` with a description comment.

5. IF required variables are missing THEN the application SHALL fail to start with a clear message listing missing variables.

6. WHEN running in Docker THEN environment variables SHALL be injectable via docker-compose environment section or env_file.

---

### Requirement 17: Python Project Configuration (pyproject.toml)

**User Story:** As a developer, I want all Python project configuration in pyproject.toml, so that I have a single source of truth for dependencies and tool configuration.

#### Acceptance Criteria

1. WHEN pyproject.toml is created THEN it SHALL define the project using modern Python packaging standards (PEP 621).

2. WHEN dependencies are listed THEN they SHALL be organized into groups: main dependencies, dev dependencies, and test dependencies.

3. WHEN Ruff configuration is defined THEN it SHALL be included in pyproject.toml under `[tool.ruff]`.

4. WHEN pytest configuration is defined THEN it SHALL be included in pyproject.toml under `[tool.pytest.ini_options]`.

5. WHEN the backend is installed THEN running `pip install -e ".[dev]"` SHALL install all development dependencies.

6. IF dependency versions conflict THEN the installation SHALL fail with a clear error message indicating the conflict.

---

### Requirement 18: Frontend Package Configuration (package.json)

**User Story:** As a frontend developer, I want all frontend dependencies and scripts in package.json, so that I have a single source of truth for the frontend project.

#### Acceptance Criteria

1. WHEN package.json is created THEN it SHALL include all required dependencies for Next.js 14, React 18, Tailwind CSS, shadcn/ui, TanStack Query, Zustand, React Hook Form, and Zod.

2. WHEN development dependencies are listed THEN they SHALL include ESLint, Prettier, TypeScript, and type definitions.

3. WHEN npm scripts are defined THEN they SHALL include: `dev`, `build`, `start`, `lint`, `format`, `type-check`, and `generate-api-types`.

4. WHEN a developer runs `npm install` THEN all dependencies SHALL be installed with compatible versions.

5. IF a package has a security vulnerability THEN `npm audit` SHALL report it with suggested remediation.

6. WHEN dependencies are updated THEN a lockfile (package-lock.json) SHALL be committed to ensure reproducible builds.

---

### Requirement 19: Git Configuration (.gitignore)

**User Story:** As a developer, I want a comprehensive .gitignore file, so that sensitive files and build artifacts are never accidentally committed.

#### Acceptance Criteria

1. WHEN .gitignore is created THEN it SHALL exclude: Python virtual environments, `__pycache__`, `.pytest_cache`, coverage reports.

2. WHEN .gitignore is created THEN it SHALL exclude: `node_modules/`, `.next/`, `out/`, and build artifacts.

3. WHEN .gitignore is created THEN it SHALL exclude: `.env`, `.env.local`, `.env.*.local`, and any files containing secrets.

4. WHEN .gitignore is created THEN it SHALL exclude: IDE-specific files (`.idea/`, `.vscode/`, `*.swp`).

5. WHEN .gitignore is created THEN it SHALL exclude: Docker volumes, MinIO data, and local database files.

6. IF a file matching .gitignore is already tracked THEN a developer note SHALL document how to untrack it.

---

### Requirement 20: Project README

**User Story:** As a developer, I want a comprehensive README with setup instructions, so that new team members can quickly set up their development environment.

#### Acceptance Criteria

1. WHEN the README is created THEN it SHALL include a project overview describing Clairo and its purpose.

2. WHEN the README is created THEN it SHALL include prerequisites listing required software versions (Docker, Python 3.12+, Node.js 20+).

3. WHEN the README is created THEN it SHALL include step-by-step quick start instructions for running the project locally.

4. WHEN the README is created THEN it SHALL document available npm/python scripts and their purposes.

5. WHEN the README is created THEN it SHALL include links to additional documentation in the specs/ folder.

6. IF setup steps change THEN the README SHALL be updated as part of that change to stay current.

---

## Non-Functional Requirements

### NFR-1: Development Environment Startup Time

**Requirement:** WHEN Docker Compose starts all services THEN they SHALL be fully operational within 60 seconds on a standard development machine (8GB RAM, SSD).

### NFR-2: Hot Reload Performance

**Requirement:** WHEN code changes are saved in development THEN both backend (uvicorn) and frontend (Next.js) SHALL reflect changes within 3 seconds.

### NFR-3: Type Safety

**Requirement:** WHERE TypeScript is used THEN strict mode SHALL be enabled and no `any` types SHALL be used except in explicitly documented exceptions.

### NFR-4: Documentation Completeness

**Requirement:** WHEN any new environment variable, configuration option, or script is added THEN it SHALL be documented before the change is merged.

### NFR-5: Reproducible Builds

**Requirement:** WHEN dependencies are installed from lockfiles THEN the same versions SHALL be installed regardless of when or where the install runs.

---

## Out of Scope

The following items are explicitly out of scope for this scaffolding specification:

1. Authentication implementation (Clerk integration) - covered in separate spec
2. Business logic for any module (clients, BAS, etc.)
3. CI/CD pipeline setup (GitHub Actions, deployment)
4. Production infrastructure (AWS, Vercel configuration)
5. Monitoring and observability setup (logging aggregation, APM)
6. API endpoint implementations
7. Database schema and initial migrations (beyond Alembic setup)
8. Frontend pages and features

---

## Dependencies

This specification has no dependencies on other specifications as it is the foundation (M0).

## Dependents

All subsequent specifications depend on this scaffolding being complete:
- 002-single-client-view
- 003-multi-client-dashboard
- All Layer 1-4 specifications

