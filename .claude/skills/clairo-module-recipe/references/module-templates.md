# Module Code Templates

Complete templates for each file in a Clairo module. Placeholders use `{ModuleName}` (PascalCase), `{module_name}` (snake_case), `{table_name}` (plural snake_case).

---

## 1. models.py

Two patterns exist in production. Choose based on whether the module owns its own base model fields or needs full control.

### Pattern A: Using BaseModel + TenantMixin (standard CRUD modules)

Used by: `_template`, `quality`, `action_items`, `triggers`

```python
"""SQLAlchemy models for {module_name} module."""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import BaseModel, TenantMixin


class {ModuleName}(BaseModel, TenantMixin):
    """
    Inherits from:
    - BaseModel: Provides id (UUID pk), created_at, updated_at
    - TenantMixin: Provides tenant_id (UUID, indexed)
    """

    __tablename__ = "{table_name}"

    # Domain-specific columns
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<{ModuleName}(id={self.id}, name={self.name})>"
```

### Pattern B: Using Base directly (full control over columns)

Used by: `billing` (BillingEvent, UsageSnapshot), `insights` (Insight), `auth` (Tenant, User)

Use this when you need: `server_default=func.gen_random_uuid()` for the PK, custom timestamp columns, ForeignKey on tenant_id with ondelete, or multiple models in one file with different column layouts.

```python
"""SQLAlchemy models for {module_name} module."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.modules.auth.models import Tenant


class {ModuleName}Status(str, enum.Enum):
    """Status enum for {ModuleName}."""
    ACTIVE = "active"
    INACTIVE = "inactive"


class {ModuleName}(Base):
    """{ModuleName} model."""

    __tablename__ = "{table_name}"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Domain columns here
    status: Mapped[{ModuleName}Status] = mapped_column(
        Enum(
            {ModuleName}Status,
            name="{module_name}_status",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default={ModuleName}Status.ACTIVE,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="{table_name}")

    __table_args__ = (
        Index("ix_{table_name}_tenant_id", "tenant_id"),
    )

    def __repr__(self) -> str:
        return f"<{ModuleName}(id={self.id}, status={self.status})>"
```

**Key differences**:
- Pattern A: 5 lines for the class, BaseModel handles id/timestamps/UUID
- Pattern B: Full column definitions, explicit `__table_args__` for composite indexes, explicit `server_default=func.gen_random_uuid()` for PK
- Pattern B Enum convention: `create_constraint=False, native_enum=True, values_callable=lambda obj: [e.value for e in obj]`

---

## 2. schemas.py

The naming convention is `{ModuleName}Base`, `{ModuleName}Create`, `{ModuleName}Update`, `{ModuleName}Response`, `{ModuleName}ListResponse`.

```python
"""Pydantic schemas for {module_name} module."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class {ModuleName}Base(BaseModel):
    """Base schema with common fields shared across operations."""

    name: str = Field(..., min_length=1, max_length=255, description="{ModuleName} name")
    description: str | None = Field(default=None, max_length=1000, description="Description")


class {ModuleName}Create({ModuleName}Base):
    """Schema for creating a new {module_name}.

    Inherits all fields from Base. Add create-specific fields here.
    """
    pass


class {ModuleName}Update(BaseModel):
    """Schema for updating a {module_name}.

    All fields optional to support PATCH semantics.
    Note: inherits from BaseModel directly, NOT from {ModuleName}Base.
    """

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)


class {ModuleName}Response({ModuleName}Base):
    """Schema for {module_name} API responses.

    ConfigDict(from_attributes=True) is REQUIRED for ORM object serialization.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Unique identifier")
    tenant_id: UUID = Field(..., description="Tenant identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class {ModuleName}ListResponse(BaseModel):
    """Paginated list response."""

    items: list[{ModuleName}Response] = Field(default_factory=list)
    total: int = Field(..., ge=0, description="Total count")
    skip: int = Field(..., ge=0, description="Items skipped")
    limit: int = Field(..., ge=1, description="Max items returned")

    @property
    def has_more(self) -> bool:
        """Check if there are more items beyond this page."""
        return self.skip + len(self.items) < self.total
```

**Production variation (clients module)**: When the module is read-only or has complex response shapes, you may skip Create/Update schemas entirely and define only Response schemas. The clients module has `ClientDetailResponse`, `ContactListResponse`, `InvoiceListResponse` etc. with no Create/Update.

**Production variation (billing module)**: Uses `Literal` types instead of Pydantic enums for API-facing types: `SubscriptionTierType = Literal["starter", "professional", "growth", "enterprise"]`

---

## 3. exceptions.py

Module-specific exceptions extend `DomainError` from `app.core.exceptions`. The global exception handler in `main.py` converts these to HTTP responses automatically.

```python
"""Domain exceptions for {module_name} module."""

from typing import Any

from app.core.exceptions import DomainError


class {ModuleName}Error(DomainError):
    """Base exception for {module_name} module errors."""

    def __init__(
        self,
        message: str,
        code: str = "{MODULE_NAME}_ERROR",
        details: dict[str, Any] | None = None,
        status_code: int = 400,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            details=details or {},
            status_code=status_code,
        )
```

**Production example (billing module)** -- Shows the hierarchy pattern:
- `BillingError(DomainError)` -- base for all billing errors
- `SubscriptionError(BillingError)` -- specific subscription error (400)
- `FeatureNotAvailableError(BillingError)` -- feature gating (403)
- `ClientLimitExceededError(BillingError)` -- limit exceeded (403)
- `InvalidTierChangeError(BillingError)` -- invalid operation (400)

You can also use the built-in exceptions from `app.core.exceptions` directly: `NotFoundError`, `ValidationError`, `ConflictError`, `AuthorizationError`, `ExternalServiceError`.

---

## 4. repository.py

The repository takes `AsyncSession` in its constructor and uses `flush()` (not `commit()`) for write operations.

```python
"""Repository for {module_name} data access."""

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import {ModuleName}


class {ModuleName}Repository:
    """Repository for {ModuleName} CRUD operations.

    All queries are tenant-scoped unless explicitly stated.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, {module_name}_id: UUID) -> {ModuleName} | None:
        """Get by ID (no tenant filter -- use get_by_tenant for safe access)."""
        result = await self.session.execute(
            select({ModuleName}).where({ModuleName}.id == {module_name}_id)
        )
        return result.scalar_one_or_none()

    async def get_by_tenant(
        self, {module_name}_id: UUID, tenant_id: UUID
    ) -> {ModuleName} | None:
        """Get by ID with tenant filtering (safe for API use)."""
        result = await self.session.execute(
            select({ModuleName}).where(
                {ModuleName}.id == {module_name}_id,
                {ModuleName}.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_tenant(
        self,
        tenant_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[{ModuleName}]:
        """List for a tenant with pagination."""
        result = await self.session.execute(
            select({ModuleName})
            .where({ModuleName}.tenant_id == tenant_id)
            .order_by({ModuleName}.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_by_tenant(self, tenant_id: UUID) -> int:
        """Count items for a tenant."""
        result = await self.session.execute(
            select(func.count())
            .select_from({ModuleName})
            .where({ModuleName}.tenant_id == tenant_id)
        )
        return result.scalar_one()

    async def create(self, {module_name}: {ModuleName}) -> {ModuleName}:
        """Create a new record.

        Uses flush()+refresh() instead of commit() because the session
        lifecycle is managed by get_db dependency (commits on success,
        rolls back on exception).
        """
        self.session.add({module_name})
        await self.session.flush()
        await self.session.refresh({module_name})
        return {module_name}

    async def update(
        self, {module_name}_id: UUID, data: dict[str, Any]
    ) -> {ModuleName} | None:
        """Update an existing record. Returns None if not found."""
        {module_name} = await self.get({module_name}_id)
        if not {module_name}:
            return None

        for key, value in data.items():
            if hasattr({module_name}, key) and value is not None:
                setattr({module_name}, key, value)

        await self.session.flush()
        await self.session.refresh({module_name})
        return {module_name}

    async def delete(self, {module_name}_id: UUID) -> bool:
        """Delete a record. Returns True if deleted, False if not found."""
        {module_name} = await self.get({module_name}_id)
        if not {module_name}:
            return False

        await self.session.delete({module_name})
        await self.session.flush()
        return True
```

**Production variation (billing module)**: Uses keyword-only args in create method: `async def create(self, *, tenant_id: UUID, stripe_event_id: str, ...)` -- constructs the model internally rather than receiving a pre-built model object.

**Production variation (clients module)**: Repository returns `dict[str, Any]` from complex queries with joins/subqueries rather than model objects. The `get_connection_with_financials` method builds the result dict manually from a joined query.

---

## 5. service.py

The service takes `AsyncSession` in its constructor and instantiates repositories internally.

```python
"""Service for {module_name} module business logic."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError

from .models import {ModuleName}
from .repository import {ModuleName}Repository
from .schemas import {ModuleName}Create, {ModuleName}Update


class {ModuleName}Service:
    """Service for {module_name} operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repository = {ModuleName}Repository(db)

    async def get_by_id(
        self, {module_name}_id: UUID, tenant_id: UUID
    ) -> {ModuleName}:
        """Get a {module_name} by ID.

        Raises:
            NotFoundError: If not found or not accessible by tenant.
        """
        result = await self.repository.get_by_tenant({module_name}_id, tenant_id)
        if not result:
            raise NotFoundError("{ModuleName}", str({module_name}_id))
        return result

    async def list(
        self,
        tenant_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[{ModuleName}], int]:
        """List items for a tenant with count."""
        items = await self.repository.list_by_tenant(tenant_id, skip, limit)
        total = await self.repository.count_by_tenant(tenant_id)
        return items, total

    async def create(
        self, data: {ModuleName}Create, tenant_id: UUID
    ) -> {ModuleName}:
        """Create a new {module_name}."""
        {module_name} = {ModuleName}(
            tenant_id=tenant_id,
            **data.model_dump(),
        )
        return await self.repository.create({module_name})

    async def update(
        self,
        {module_name}_id: UUID,
        data: {ModuleName}Update,
        tenant_id: UUID,
    ) -> {ModuleName}:
        """Update an existing {module_name}.

        Raises:
            NotFoundError: If not found.
        """
        # Verify existence and tenant access
        await self.get_by_id({module_name}_id, tenant_id)

        # exclude_unset=True ensures only provided fields are updated
        update_data = data.model_dump(exclude_unset=True)
        result = await self.repository.update({module_name}_id, update_data)
        if not result:
            raise NotFoundError("{ModuleName}", str({module_name}_id))
        return result

    async def delete(
        self, {module_name}_id: UUID, tenant_id: UUID
    ) -> None:
        """Delete a {module_name}.

        Raises:
            NotFoundError: If not found.
        """
        await self.get_by_id({module_name}_id, tenant_id)
        await self.repository.delete({module_name}_id)
```

**Production variation (billing module)**: Service accepts additional dependencies beyond session: `def __init__(self, session: AsyncSession, stripe_client: StripeClient | None = None)`. Multiple repositories instantiated internally: `self.event_repository = BillingEventRepository(session)` and `self.usage_repository = UsageRepository(session)`.

**Production variation (clients module)**: Service composes multiple repositories from different modules: `self.repository = ClientsRepository(db)`, `self.payroll_repo = XeroPayrollRepository(db)`, `self.quality_repo = QualityRepository(db)`.

**Production variation (insights module)**: No separate repository. Service queries the database directly using `self.db` (the AsyncSession). This is acceptable for modules where the query logic IS the business logic and a separate repository would be pure pass-through.

---

## 6. router.py

Two DI patterns are used in production. Choose one consistently within a module.

### Pattern A: Annotated type aliases from `app.core.dependencies`

Used by: `_template`, `insights`, modules that use Clerk-based auth with `get_current_tenant_id`

```python
"""API endpoints for {module_name} module."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import DbSession, get_current_tenant_id
from app.database import get_db

from .schemas import (
    {ModuleName}Create,
    {ModuleName}ListResponse,
    {ModuleName}Response,
    {ModuleName}Update,
)
from .service import {ModuleName}Service

router = APIRouter(prefix="/api/v1/{module_name}s", tags=["{module_name}s"])

# Local type aliases
TenantIdDep = Annotated[UUID, Depends(get_current_tenant_id)]


async def get_{module_name}_service(db: DbSession) -> {ModuleName}Service:
    """Dependency to get service instance."""
    return {ModuleName}Service(db)


{ModuleName}ServiceDep = Annotated[{ModuleName}Service, Depends(get_{module_name}_service)]


@router.get("", response_model={ModuleName}ListResponse)
async def list_{module_name}s(
    service: {ModuleName}ServiceDep,
    tenant_id: TenantIdDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
) -> {ModuleName}ListResponse:
    """List all {module_name}s for the current tenant."""
    items, total = await service.list(tenant_id=tenant_id, skip=skip, limit=limit)
    return {ModuleName}ListResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/{{{module_name}_id}}", response_model={ModuleName}Response)
async def get_{module_name}(
    {module_name}_id: UUID,
    service: {ModuleName}ServiceDep,
    tenant_id: TenantIdDep,
) -> {ModuleName}Response:
    """Get a single {module_name} by ID."""
    return await service.get_by_id({module_name}_id, tenant_id=tenant_id)


@router.post("", status_code=status.HTTP_201_CREATED, response_model={ModuleName}Response)
async def create_{module_name}(
    data: {ModuleName}Create,
    service: {ModuleName}ServiceDep,
    tenant_id: TenantIdDep,
) -> {ModuleName}Response:
    """Create a new {module_name}."""
    return await service.create(data, tenant_id=tenant_id)


@router.patch("/{{{module_name}_id}}", response_model={ModuleName}Response)
async def update_{module_name}(
    {module_name}_id: UUID,
    data: {ModuleName}Update,
    service: {ModuleName}ServiceDep,
    tenant_id: TenantIdDep,
) -> {ModuleName}Response:
    """Update an existing {module_name}."""
    return await service.update({module_name}_id, data, tenant_id=tenant_id)


@router.delete("/{{{module_name}_id}}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_{module_name}(
    {module_name}_id: UUID,
    service: {ModuleName}ServiceDep,
    tenant_id: TenantIdDep,
) -> None:
    """Delete a {module_name}."""
    await service.delete({module_name}_id, tenant_id=tenant_id)
```

### Pattern B: Explicit Depends() with require_permission

Used by: `clients`, `quality`, `bas` -- modules that need permission-based access control

```python
"""API endpoints for {module_name} module."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.auth.models import PracticeUser
from app.modules.auth.permissions import Permission, require_permission

from .schemas import {ModuleName}ListResponse, {ModuleName}Response
from .service import {ModuleName}Service

router = APIRouter(prefix="/{module_name}s", tags=["{ModuleName}s"])


@router.get("", response_model={ModuleName}ListResponse)
async def list_{module_name}s(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    current_user: PracticeUser = Depends(require_permission(Permission.{PERMISSION}_READ)),
    db: AsyncSession = Depends(get_db),
) -> {ModuleName}ListResponse:
    """List {module_name}s for the current tenant."""
    service = {ModuleName}Service(db)
    # current_user.tenant_id is available from the PracticeUser model
    return await service.list(
        tenant_id=current_user.tenant_id,
        page=page,
        limit=limit,
    )


@router.get("/{{{module_name}_id}}", response_model={ModuleName}Response)
async def get_{module_name}(
    {module_name}_id: UUID,
    current_user: PracticeUser = Depends(require_permission(Permission.{PERMISSION}_READ)),
    db: AsyncSession = Depends(get_db),
) -> {ModuleName}Response:
    """Get a single {module_name}."""
    service = {ModuleName}Service(db)
    result = await service.get_by_id({module_name}_id, tenant_id=current_user.tenant_id)
    if not result:
        raise HTTPException(status_code=404, detail="{ModuleName} not found")
    return result
```

### Pattern C: Tenant object dependency (billing pattern)

Used by: `billing` -- when you need the full Tenant object (not just tenant_id)

```python
from typing import Annotated
from fastapi import APIRouter, Depends
from app.core.dependencies import get_current_tenant
from app.modules.auth.models import Tenant

router = APIRouter(tags=["{module_name}"])


@router.get("/something")
async def get_something(
    tenant: Annotated[Tenant, Depends(get_current_tenant)],
    service: Annotated[{ModuleName}Service, Depends(get_{module_name}_service)],
) -> SomeResponse:
    """Endpoint that needs the full tenant object."""
    return await service.do_something(tenant=tenant)
```

**When to use which**:
- **Pattern A** (Annotated aliases): Clean, modern style. Use for new modules where you only need `tenant_id`.
- **Pattern B** (require_permission): Use when endpoints need RBAC permission checks (e.g., `Permission.INTEGRATION_READ`).
- **Pattern C** (full Tenant): Use when the service needs tenant attributes beyond `tenant_id` (e.g., `tenant.tier`, `tenant.stripe_customer_id`).

---

## 7. __init__.py

```python
"""{ModuleName} module for {description}.

This module provides:
- {Brief list of capabilities}
"""

from .models import {ModuleName}
from .router import router as {module_name}_router

__all__ = [
    "{ModuleName}",
    "{module_name}_router",
]
```

**Production example (billing)** -- Exports exceptions too:
```python
from app.modules.billing.exceptions import (
    ClientLimitExceededError,
    FeatureNotAvailableError,
)
from app.modules.billing.models import BillingEvent, BillingEventStatus
from app.modules.billing.router import router as billing_router

__all__ = [
    "BillingEvent",
    "BillingEventStatus",
    "ClientLimitExceededError",
    "FeatureNotAvailableError",
    "billing_router",
]
```

---

## 8. Registration in main.py

Add to the router registration section in `backend/app/main.py`, following the existing try/except pattern:

```python
    try:
        from app.modules.{module_name}.router import router as {module_name}_router
        app.include_router({module_name}_router, prefix="/api/v1", tags=["{module_name}"])
    except ImportError:
        logger.warning("{module_name}_router_not_available")
```

**Note**: Some modules define the prefix in the router itself (`prefix="/api/v1/{module_name}s"`) and use `prefix=""` or no prefix in `include_router`. Others define just `prefix="/{module_name}s"` in the router and add `/api/v1` in `include_router`. Check the router's `prefix=` to avoid double-prefixing.
