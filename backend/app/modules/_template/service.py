"""Service template for feature modules.

Services contain business logic and orchestrate between repositories,
external services, and domain events. They should not contain database
queries directly - use repositories for that.

Usage:
    1. Copy and rename this file when creating a new module
    2. Inject dependencies (repository, event_bus) via constructor
    3. Keep methods focused on business logic
"""

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import DomainEvent, event_bus
from app.core.exceptions import NotFoundError

# from .models import Item
# from .repository import ItemRepository
# from .schemas import ItemCreate, ItemUpdate


class TemplateService:
    """Service for template module business logic.

    This service demonstrates the standard patterns for Clairo services:
    - Constructor injection of dependencies
    - Business rule validation
    - Domain event publishing
    - Error handling
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize service with dependencies.

        Args:
            session: Database session for repository operations.
        """
        self.session = session
        # self.repository = ItemRepository(session)

    async def get_by_id(self, item_id: UUID, tenant_id: UUID) -> dict[str, Any]:  # noqa: ARG002
        """Get an item by ID.

        Args:
            item_id: The item's unique identifier.
            tenant_id: The tenant context.

        Returns:
            The item data.

        Raises:
            NotFoundError: If item not found or not accessible.
        """
        # item = await self.repository.get(item_id)
        # if not item:
        #     raise NotFoundError("Item", str(item_id))
        # if item.tenant_id != tenant_id:
        #     raise NotFoundError("Item", str(item_id))
        # return item
        raise NotFoundError("Item", str(item_id))

    async def list(
        self,
        tenant_id: UUID,  # noqa: ARG002
        skip: int = 0,  # noqa: ARG002
        limit: int = 100,  # noqa: ARG002
    ) -> list[dict[str, Any]]:
        """List items for a tenant.

        Args:
            tenant_id: The tenant context.
            skip: Number of items to skip.
            limit: Maximum items to return.

        Returns:
            List of items.
        """
        # return await self.repository.list_by_tenant(tenant_id, skip, limit)
        return []

    async def create(self, data: dict[str, Any], tenant_id: UUID) -> dict[str, Any]:
        """Create a new item.

        Args:
            data: Item creation data.
            tenant_id: The tenant context.

        Returns:
            The created item.

        Raises:
            ValidationError: If business rules are violated.
        """
        # Validate business rules
        await self._validate_create(data, tenant_id)

        # Create item via repository
        # item = Item(tenant_id=tenant_id, **data)
        # created = await self.repository.create(item)

        # Publish domain event
        await event_bus.publish(
            DomainEvent(
                aggregate_type="Item",
                aggregate_id="new-uuid",  # str(created.id)
                payload={"action": "created", "tenant_id": str(tenant_id)},
            )
        )

        # return created
        return {"id": "new-uuid", **data}

    async def update(self, item_id: UUID, data: dict[str, Any], tenant_id: UUID) -> dict[str, Any]:
        """Update an existing item.

        Args:
            item_id: The item's unique identifier.
            data: Item update data.
            tenant_id: The tenant context.

        Returns:
            The updated item.

        Raises:
            NotFoundError: If item not found.
            ValidationError: If business rules are violated.
        """
        # Get existing item
        item = await self.get_by_id(item_id, tenant_id)

        # Validate business rules
        await self._validate_update(item, data, tenant_id)

        # Update via repository
        # updated = await self.repository.update(item_id, data)

        # Publish domain event
        await event_bus.publish(
            DomainEvent(
                aggregate_type="Item",
                aggregate_id=str(item_id),
                payload={"action": "updated", "tenant_id": str(tenant_id)},
            )
        )

        # return updated
        return {"id": str(item_id), **data}

    async def delete(self, item_id: UUID, tenant_id: UUID) -> None:
        """Delete an item.

        Args:
            item_id: The item's unique identifier.
            tenant_id: The tenant context.

        Raises:
            NotFoundError: If item not found.
            ValidationError: If item cannot be deleted.
        """
        # Verify item exists and is accessible
        await self.get_by_id(item_id, tenant_id)

        # Check deletion constraints
        await self._validate_delete(item_id, tenant_id)

        # Delete via repository
        # await self.repository.delete(item_id)

        # Publish domain event
        await event_bus.publish(
            DomainEvent(
                aggregate_type="Item",
                aggregate_id=str(item_id),
                payload={"action": "deleted", "tenant_id": str(tenant_id)},
            )
        )

    async def _validate_create(self, data: dict[str, Any], tenant_id: UUID) -> None:
        """Validate business rules for item creation.

        Override this method to add domain-specific validation.
        """
        # Example validation
        # if not data.get("name"):
        #     raise ValidationError("Name is required", field="name")
        pass

    async def _validate_update(
        self, item: dict[str, Any], data: dict[str, Any], tenant_id: UUID
    ) -> None:
        """Validate business rules for item update.

        Override this method to add domain-specific validation.
        """
        pass

    async def _validate_delete(self, item_id: UUID, tenant_id: UUID) -> None:
        """Validate business rules for item deletion.

        Override this method to add domain-specific constraints.
        """
        # Example: Check if item has dependencies
        # if await self._has_dependencies(item_id):
        #     raise ValidationError("Item has dependencies and cannot be deleted")
        pass
