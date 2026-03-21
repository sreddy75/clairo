"""API router template for feature modules.

This template demonstrates the standard router structure for Clairo modules.
Copy and rename this file when creating a new module.

Usage:
    1. Copy this directory to app/modules/{your_module_name}/
    2. Rename classes and update table names
    3. Import router in app/main.py
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, status

from app.core.dependencies import CurrentUser, DbSession

# from .schemas import ItemCreate, ItemResponse, ItemUpdate
# from .service import ItemService

router = APIRouter(
    prefix="/template",  # Change to your module prefix
    tags=["template"],  # Change to your module name
)


# Example: List items
@router.get("/")
async def list_items(
    db: DbSession,
    user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> dict[str, Any]:
    """List all items for the current tenant.

    Args:
        db: Database session.
        user: Current authenticated user.
        skip: Number of items to skip.
        limit: Maximum number of items to return.

    Returns:
        List of items with pagination info.
    """
    # service = ItemService(db)
    # items = await service.list(tenant_id=user.tenant_id, skip=skip, limit=limit)
    # return {"items": items, "skip": skip, "limit": limit}
    return {"items": [], "skip": skip, "limit": limit}


# Example: Get single item
@router.get("/{item_id}")
async def get_item(
    item_id: UUID,
    db: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    """Get a single item by ID.

    Args:
        item_id: The item's unique identifier.
        db: Database session.
        user: Current authenticated user.

    Returns:
        The requested item.

    Raises:
        NotFoundError: If item not found.
    """
    # service = ItemService(db)
    # item = await service.get_by_id(item_id, tenant_id=user.tenant_id)
    # return item
    return {"id": str(item_id), "name": "Example Item"}


# Example: Create item
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_item(
    # data: ItemCreate,
    db: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    """Create a new item.

    Args:
        data: Item creation data.
        db: Database session.
        user: Current authenticated user.

    Returns:
        The created item.
    """
    # service = ItemService(db)
    # item = await service.create(data, tenant_id=user.tenant_id)
    # return item
    return {"id": "new-uuid", "name": "New Item"}


# Example: Update item
@router.put("/{item_id}")
async def update_item(
    item_id: UUID,
    # data: ItemUpdate,
    db: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    """Update an existing item.

    Args:
        item_id: The item's unique identifier.
        data: Item update data.
        db: Database session.
        user: Current authenticated user.

    Returns:
        The updated item.

    Raises:
        NotFoundError: If item not found.
    """
    # service = ItemService(db)
    # item = await service.update(item_id, data, tenant_id=user.tenant_id)
    # return item
    return {"id": str(item_id), "name": "Updated Item"}


# Example: Delete item
@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    item_id: UUID,
    db: DbSession,
    user: CurrentUser,
) -> None:
    """Delete an item.

    Args:
        item_id: The item's unique identifier.
        db: Database session.
        user: Current authenticated user.

    Raises:
        NotFoundError: If item not found.
    """
    # service = ItemService(db)
    # await service.delete(item_id, tenant_id=user.tenant_id)
    pass
