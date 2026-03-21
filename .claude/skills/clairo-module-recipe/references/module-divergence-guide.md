# Module Divergence Guide

Documents how production modules differ from the 7-file template, so you know when and how to deviate.

---

## Modules That Skip the Repository Layer

Some modules put query logic directly in the service. This is acceptable when:

- The query IS the business logic (no separate "data access" vs "business rules" distinction)
- The module is read-heavy with complex aggregation queries that would be pure pass-through in a repository
- The module is small enough that a repository adds indirection without value

### insights module

**Files**: `models.py`, `schemas.py`, `service.py`, `router.py`, `exceptions.py`, `__init__.py` + `analyzers/`, `generator.py`, `evidence.py`, `dedup.py`, `thresholds.py`, `a2ui_generator.py`

- **No repository.py** -- `InsightService` queries `self.db` (AsyncSession) directly with `select()`, `func.count()`, etc.
- **Why**: Insight queries are complex (multi-column filters, status transitions, aggregations for dashboard stats). A repository would be a pure pass-through that makes the code harder to follow.
- **Extra files**: `analyzers/` subdirectory (base + quality + compliance + cashflow + ai_analyzer + magic_zone), `generator.py` (orchestrates analysis), `evidence.py` (citation/evidence system), `dedup.py` (deduplication logic), `thresholds.py` (configurable threshold registry)

### action_items module

**Files**: `models.py`, `schemas.py`, `service.py`, `router.py`, `__init__.py`

- **No repository.py, no exceptions.py** -- Minimal CRUD module. Service queries directly. Uses `NotFoundError` from core exceptions.
- **Why**: Simple enough that the 5-file structure is sufficient.

### clients module

**Files**: `schemas.py`, `repository.py`, `service.py`, `router.py`, `__init__.py`

- **No models.py** -- The clients module does NOT own any database tables. It reads from `XeroConnection`, `XeroClient`, `XeroInvoice`, `XeroBankTransaction` (owned by `integrations/xero/`). It's a **read-only view module** that composes data from other modules.
- **No exceptions.py** -- Returns `None` from service methods; router converts to `HTTPException(404)` directly.
- **Why**: Follows the "clients = XeroConnections" domain model. The module provides a client-centric API over existing integration data.

---

## Modules With Extra Files

### billing module

**Extra files beyond the 7**: `stripe_client.py`, `webhooks.py`, `usage_alerts.py`

- `stripe_client.py` -- Encapsulates all Stripe API calls. Injected into `BillingService`.
- `webhooks.py` -- `WebhookHandler` class that processes Stripe webhook events. Called from the webhook endpoint in `router.py`.
- `usage_alerts.py` -- `UsageAlertService` for usage threshold monitoring and email alerts.
- **Pattern**: External service integration gets its own file. Webhook processing gets its own file. Specialized sub-services get their own file.

### triggers module

**Extra files**: `evaluators/` subdirectory, `executor.py`, `defaults.py`

- `evaluators/` -- Subdirectory with `base.py`, `time_triggers.py`, `event_triggers.py`, `data_triggers.py` (strategy pattern)
- `executor.py` -- Executes trigger actions after evaluation
- `defaults.py` -- Default trigger configurations
- **No repository.py** -- Service queries directly

### quality module

**Extra files**: `calculator.py`, `issue_detector.py`

- `calculator.py` -- Quality score calculation logic (pure functions)
- `issue_detector.py` -- Issue detection rules
- **Has repository.py** -- Standard CRUD + complex aggregation queries
- **Pattern**: Computation-heavy modules extract calculation logic into separate files

### agents module

**Extra files**: `orchestrator.py`, `query_agent.py`, `summary_agent.py`, `perspective_detector.py`, `prompts.py`, `dependencies.py`, `settings.py`, `a2ui_generator.py`, `a2ui_llm.py`, `audit.py`, `tools/` subdirectory, `context/` subdirectory, `analysis/` subdirectory

- **No repository.py, no service.py** -- Agent modules have their own architecture: orchestrator + individual agents + tools
- **Has its own `dependencies.py`** -- Module-specific FastAPI dependencies
- **Pattern**: AI/agent modules diverge significantly from CRUD patterns. Don't force them into the 7-file template.

### notifications module

**Extra files**: `email_service.py`, `templates.py`, `push/` subdirectory (sub-module with its own models/schemas/service/repository/router)

- **Pattern**: Large modules can have sub-modules. The `push/` subdirectory is a module-within-a-module.

---

## Model Pattern Variations

### Using Base vs BaseModel

| Pattern | When to Use | Examples |
|---------|-------------|---------|
| `BaseModel + TenantMixin` | Standard CRUD tables with UUID pk + timestamps + tenant | `_template`, `quality`, `action_items`, `triggers` |
| `Base` directly | Need custom PK generation, custom timestamps, ForeignKey on tenant_id, or non-standard column layout | `billing`, `insights`, `auth` |

### Enum Column Pattern

The billing module established the production pattern for PostgreSQL native enums:

```python
status: Mapped[MyStatus] = mapped_column(
    Enum(
        MyStatus,
        name="my_status_name",        # PostgreSQL enum type name
        create_constraint=False,       # Don't create CHECK constraint
        native_enum=True,              # Use PostgreSQL native enum
        values_callable=lambda obj: [e.value for e in obj],  # Use .value strings
    ),
    nullable=False,
    default=MyStatus.ACTIVE,
)
```

The insights module uses a simpler approach (string columns with enum values):

```python
status: Mapped[str] = mapped_column(String(50), nullable=False, default="new")
category: Mapped[str] = mapped_column(String(50), nullable=False)
```

**Guidance**: Use native enums (billing pattern) when the set of values is stable and you want DB-level validation. Use string columns (insights pattern) when values may change frequently or when simplicity is preferred.

---

## DI Pattern Variations

### Service instantiation

| Pattern | Where Used | When |
|---------|------------|------|
| Service created in endpoint | `clients` router | Simple: `service = ClientsService(db)` inline |
| Service as FastAPI dependency | `insights`, `billing` routers | Complex: `Annotated[Service, Depends(get_service)]` |

The `insights` router defines a dependency function and type alias:

```python
async def get_insight_service(db: DbSession) -> InsightService:
    return InsightService(db)

InsightServiceDep = Annotated[InsightService, Depends(get_insight_service)]
```

The `billing` router defines a dependency with extra setup:

```python
async def get_billing_service(
    session: AsyncSession = Depends(get_db),
) -> BillingService:
    return BillingService(session=session, stripe_client=StripeClient())
```

**Guidance**: Use the dependency pattern when the service needs constructor arguments beyond just the session, or when you want to mock it in tests. Use inline creation for simple cases.

### Authentication patterns

| Pattern | Import | Gives You |
|---------|--------|-----------|
| `DbSession` + `CurrentUser` | `app.core.dependencies` | AsyncSession + TokenPayload (JWT claims) |
| `Depends(get_db)` + `Depends(require_permission(...))` | `app.database` + `app.modules.auth.permissions` | AsyncSession + PracticeUser (full DB record with `.tenant_id`) |
| `Depends(get_db)` + `Depends(get_current_tenant)` | `app.database` + `app.core.dependencies` | AsyncSession + Tenant (full tenant object) |
| `TenantIdDep` | `app.core.dependencies.get_current_tenant_id` | Just the UUID tenant_id |

---

## Decision Matrix: Simple vs Full Module

| Question | If Yes | If No |
|----------|--------|-------|
| Does it own database tables? | Add `models.py` | Skip `models.py` (like `clients`) |
| Does it have CRUD operations? | Add `repository.py` | Service queries directly (like `insights`) |
| Does it have unique error cases? | Add `exceptions.py` | Use core exceptions (`NotFoundError`, `ValidationError`) |
| Does it integrate with external APIs? | Add a `{service_name}_client.py` | Keep logic in service |
| Does it have computation-heavy logic? | Extract to `calculator.py` or `utils.py` | Keep in service |
| Does it have background tasks? | Add to `backend/app/tasks/` | Keep synchronous |
| Does it need webhooks? | Add `webhooks.py` | N/A |
| Is it a sub-feature of a larger module? | Consider a subdirectory (like `notifications/push/`) | Standalone module |

### Minimum viable module (3 files)

For very simple modules (e.g., a configuration endpoint with no DB):

```
my_module/
├── __init__.py
├── schemas.py
├── router.py
```

### Standard CRUD module (5-6 files)

```
my_module/
├── __init__.py
├── models.py
├── schemas.py
├── repository.py   # optional if queries are simple
├── service.py
├── router.py
```

### Full module with extras (7+ files)

```
my_module/
├── __init__.py
├── models.py
├── schemas.py
├── repository.py
├── service.py
├── router.py
├── exceptions.py
├── {extra}.py       # webhooks.py, client.py, calculator.py, etc.
```

---

## Common Simplifications for Small Modules

1. **Skip repository.py** -- Put queries directly in the service if there are fewer than ~5 query methods
2. **Skip exceptions.py** -- Use `NotFoundError`, `ValidationError`, `ConflictError` from `app.core.exceptions`
3. **Skip Update schema** -- If the entity is create-once / read-only
4. **Combine Base + Create schemas** -- If create and base have identical fields, just use the Base directly as create input
5. **Return `None` instead of raising** -- The clients module returns `None` from service methods and lets the router raise `HTTPException(404)`. This is a valid pattern for read-only modules where "not found" is the only error case.
