"""SQLAlchemy models for database tables.

Models represent database tables and their relationships.
All models should inherit from BaseModel for consistent ID and timestamps,
and from TenantMixin for multi-tenant tables.

Usage:
    1. Copy and rename this file when creating a new module
    2. Define your domain-specific models
    3. Run alembic revision --autogenerate to create migrations
"""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import BaseModel, TenantMixin


class Item(BaseModel, TenantMixin):
    """Example item model demonstrating standard patterns.

    Inherits from:
    - BaseModel: Provides id, created_at, updated_at
    - TenantMixin: Provides tenant_id for multi-tenancy

    Attributes:
        id: UUID primary key (from BaseModel)
        tenant_id: UUID for multi-tenancy (from TenantMixin)
        created_at: Creation timestamp (from BaseModel)
        updated_at: Update timestamp (from BaseModel)
        name: Item name
        description: Optional item description
    """

    __tablename__ = "items"

    # Domain-specific columns
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Example of additional columns you might need:
    #
    # Foreign key example:
    # category_id: Mapped[UUID | None] = mapped_column(
    #     ForeignKey("categories.id"),
    #     nullable=True,
    # )
    #
    # Relationship example:
    # category: Mapped["Category"] = relationship(back_populates="items")
    #
    # Enum example:
    # status: Mapped[ItemStatus] = mapped_column(
    #     Enum(ItemStatus),
    #     default=ItemStatus.DRAFT,
    #     nullable=False,
    # )
    #
    # JSON column example:
    # metadata: Mapped[dict] = mapped_column(JSON, default=dict)

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<Item(id={self.id}, name={self.name})>"
