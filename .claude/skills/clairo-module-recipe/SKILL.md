---
name: clairo-module-recipe
description: >
  Step-by-step recipe for creating new backend modules in Clairo's modular monolith.
  Provides exact code templates for the 7-file module structure (models, schemas, repository, service, router, exceptions, __init__).
  Use when creating a new module, adding a new entity to an existing module, or during /speckit.implement for backend tasks.
  Do NOT use for frontend-only work, infrastructure, or CI/CD tasks.
---

# Clairo Module Recipe

## When This Applies

- Creating a new backend module under `backend/app/modules/`
- Adding a new entity (model + CRUD) to an existing module
- During `/speckit.implement` when the task involves new backend endpoints
- Scaffolding the standard 7-file structure for any new domain concept
- Reviewing whether an existing module follows project conventions

## Architecture Overview

Each module lives in `backend/app/modules/{module_name}/` with up to 7 files:

| File | Purpose | Required? |
|------|---------|-----------|
| `models.py` | SQLAlchemy models (tables, enums, relationships) | Yes, if module owns data |
| `schemas.py` | Pydantic schemas (Create/Update/Response/ListResponse) | Yes |
| `repository.py` | Data access layer (queries, CRUD, tenant filtering) | Recommended for CRUD modules |
| `service.py` | Business logic, orchestration, domain exceptions | Yes |
| `router.py` | FastAPI endpoints, DI, HTTP error conversion | Yes |
| `exceptions.py` | Module-specific domain exceptions extending `DomainError` | If module has custom error cases |
| `__init__.py` | Public API exports, router alias | Yes |

## Implementation Checklist

Create files in this order (each step depends on the previous):

1. **`models.py`** -- Define tables first because schemas and repository depend on column names and types
2. **`schemas.py`** -- Define API contracts before business logic so service return types are clear
3. **`exceptions.py`** -- Define domain errors before service so service can raise them
4. **`repository.py`** -- Data access layer before service so service can delegate queries
5. **`service.py`** -- Business logic that composes repository + exceptions
6. **`router.py`** -- HTTP layer that instantiates service and converts exceptions
7. **`__init__.py`** -- Export public API and router alias
8. **Register in `main.py`** -- Add `app.include_router(...)` in the router registration section
9. **Alembic migration** -- Run `alembic revision --autogenerate -m "add {table_name} table"`

## Critical Traps

These are things that **will break** if forgotten:

1. **Inherit from `BaseModel` + `TenantMixin`** for tenant-scoped tables. `BaseModel` gives you `id` (UUID), `created_at`, `updated_at`. `TenantMixin` gives you `tenant_id`. If you use `Base` directly, you must define all columns manually.

2. **Use `flush()` not `commit()`** in repository create/update methods. The session is committed by the `get_db` dependency's context manager. Calling `commit()` in the repository breaks the transactional boundary.

3. **`model_config = ConfigDict(from_attributes=True)`** is required on Response schemas that are populated from ORM objects. Without it, Pydantic v2 cannot read SQLAlchemy model attributes.

4. **Tenant filtering** -- Every query that returns tenant-scoped data MUST filter by `tenant_id`. The template shows `get_by_tenant()` as the safe pattern.

5. **Service raises domain exceptions, router converts to HTTPException** -- Never raise `HTTPException` in services. Never use bare `try/except` in routers without re-raising.

6. **Two DI patterns exist** -- The template uses `DbSession` / `CurrentUser` type aliases. Production modules (billing, clients) use `Depends(get_db)` and `Depends(require_permission(...))` directly. Both work; see the templates for guidance on when to use which.

7. **Router registration** -- The router must be imported and registered in `backend/app/main.py` using `app.include_router()` with the appropriate prefix and tags. Follow the existing try/except pattern.

8. **`__tablename__`** must be set explicitly on every model. SQLAlchemy will not auto-generate it.

## Reference Files

- **[Module Templates](references/module-templates.md)** -- Complete code templates for all 7 files with placeholders and annotations
- **[Divergence Guide](references/module-divergence-guide.md)** -- How production modules differ from the template, when to skip files, common variations
