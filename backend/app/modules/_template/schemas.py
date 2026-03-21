"""Pydantic schemas for API request/response models.

Schemas define the structure of data for API endpoints:
- Base: Common fields shared across operations
- Create: Fields for creating new resources
- Update: Fields for updating existing resources
- Response: Fields returned in API responses

Usage:
    1. Copy and rename this file when creating a new module
    2. Define your domain-specific schemas
    3. Use in router endpoints for validation
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ItemBase(BaseModel):
    """Base schema with common fields.

    Shared between create, update, and response schemas.
    """

    name: str = Field(..., min_length=1, max_length=255, description="Item name")
    description: str | None = Field(default=None, max_length=1000, description="Item description")


class ItemCreate(ItemBase):
    """Schema for creating a new item.

    Inherits all fields from ItemBase. Add any create-specific
    fields or override validation here.
    """

    pass


class ItemUpdate(BaseModel):
    """Schema for updating an item.

    All fields are optional to support partial updates (PATCH semantics).
    """

    name: str | None = Field(default=None, min_length=1, max_length=255, description="Item name")
    description: str | None = Field(default=None, max_length=1000, description="Item description")


class ItemResponse(ItemBase):
    """Schema for item responses.

    Includes all base fields plus server-generated fields like ID and timestamps.
    Uses model_config for ORM mode compatibility.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Unique identifier")
    tenant_id: UUID = Field(..., description="Tenant identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class ItemListResponse(BaseModel):
    """Schema for paginated item list responses."""

    items: list[ItemResponse] = Field(default_factory=list, description="List of items")
    total: int = Field(..., ge=0, description="Total number of items")
    skip: int = Field(..., ge=0, description="Number of items skipped")
    limit: int = Field(..., ge=1, description="Maximum items returned")

    @property
    def has_more(self) -> bool:
        """Check if there are more items beyond this page."""
        return self.skip + len(self.items) < self.total
