"""Repository pattern for data access.

Repositories encapsulate database queries and provide a clean interface
for services to access data. They should:
- Accept and return domain models, not SQLAlchemy internals
- Handle query building and optimization
- Implement tenant filtering for multi-tenant queries

Usage:
    1. Copy and rename this file when creating a new module
    2. Define your domain-specific queries
    3. Inject repository into services
"""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Item


class ItemRepository:
    """Repository for Item data access.

    Provides CRUD operations and complex queries for Items.
    All queries are automatically scoped to the appropriate tenant.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: Async database session.
        """
        self.session = session

    async def get(self, item_id: UUID) -> Item | None:
        """Get an item by ID.

        Args:
            item_id: The item's unique identifier.

        Returns:
            The item if found, None otherwise.
        """
        result = await self.session.execute(select(Item).where(Item.id == item_id))
        return result.scalar_one_or_none()

    async def get_by_tenant(self, item_id: UUID, tenant_id: UUID) -> Item | None:
        """Get an item by ID with tenant filtering.

        Args:
            item_id: The item's unique identifier.
            tenant_id: The tenant context.

        Returns:
            The item if found and belongs to tenant, None otherwise.
        """
        result = await self.session.execute(
            select(Item).where(
                Item.id == item_id,
                Item.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_tenant(
        self,
        tenant_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Item]:
        """List items for a tenant with pagination.

        Args:
            tenant_id: The tenant context.
            skip: Number of items to skip.
            limit: Maximum items to return.

        Returns:
            List of items.
        """
        result = await self.session.execute(
            select(Item)
            .where(Item.tenant_id == tenant_id)
            .order_by(Item.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_by_tenant(self, tenant_id: UUID) -> int:
        """Count items for a tenant.

        Args:
            tenant_id: The tenant context.

        Returns:
            Total number of items.
        """
        from sqlalchemy import func

        result = await self.session.execute(
            select(func.count()).select_from(Item).where(Item.tenant_id == tenant_id)
        )
        return result.scalar_one()

    async def create(self, item: Item) -> Item:
        """Create a new item.

        Args:
            item: The item to create.

        Returns:
            The created item with generated ID.
        """
        self.session.add(item)
        await self.session.flush()
        await self.session.refresh(item)
        return item

    async def update(self, item_id: UUID, data: dict[str, Any]) -> Item | None:
        """Update an existing item.

        Args:
            item_id: The item's unique identifier.
            data: Fields to update.

        Returns:
            The updated item if found, None otherwise.
        """
        item = await self.get(item_id)
        if not item:
            return None

        for key, value in data.items():
            if hasattr(item, key) and value is not None:
                setattr(item, key, value)

        await self.session.flush()
        await self.session.refresh(item)
        return item

    async def delete(self, item_id: UUID) -> bool:
        """Delete an item.

        Args:
            item_id: The item's unique identifier.

        Returns:
            True if deleted, False if not found.
        """
        item = await self.get(item_id)
        if not item:
            return False

        await self.session.delete(item)
        await self.session.flush()
        return True

    async def exists(self, item_id: UUID, tenant_id: UUID | None = None) -> bool:
        """Check if an item exists.

        Args:
            item_id: The item's unique identifier.
            tenant_id: Optional tenant context.

        Returns:
            True if item exists, False otherwise.
        """
        from sqlalchemy import exists as sql_exists

        query = select(Item.id).where(Item.id == item_id)
        if tenant_id:
            query = query.where(Item.tenant_id == tenant_id)

        result = await self.session.execute(select(sql_exists(query)))
        return result.scalar_one()
