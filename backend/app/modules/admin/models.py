"""Admin module database models.

This module defines:
- FeatureFlagOverride model for per-tenant feature flag overrides

Spec 022: Admin Dashboard (Internal)
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.modules.auth.models import PracticeUser, Tenant


# Valid feature keys for constraints
VALID_FEATURE_KEYS = (
    "ai_insights",
    "client_portal",
    "custom_triggers",
    "api_access",
    "knowledge_base",
    "magic_zone",
)


class FeatureFlagOverride(Base):
    """Per-tenant feature flag override.

    Allows admins to override tier-based feature flags for specific tenants.
    When an override exists, it takes precedence over the tier default.

    Spec 022: Admin Dashboard (Internal)
    """

    __tablename__ = "feature_flag_overrides"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    # Tenant reference
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Tenant this override applies to",
    )

    # Feature flag specification
    feature_key: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Feature identifier (e.g., 'client_portal', 'api_access')",
    )

    # Override value
    override_value: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        comment="True=enabled, False=disabled, None=use tier default",
    )

    # Audit information
    reason: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Required reason for the override",
    )

    # Created by (admin who created)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practice_users.id", ondelete="SET NULL"),
        nullable=False,
        comment="Admin who created this override",
    )

    # Updated by (admin who last updated)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practice_users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who last updated this override",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="When override was created",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="When override was last updated",
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="feature_flag_overrides",
        lazy="selectin",
    )

    creator: Mapped["PracticeUser"] = relationship(
        "PracticeUser",
        foreign_keys=[created_by],
        lazy="selectin",
    )

    updater: Mapped["PracticeUser | None"] = relationship(
        "PracticeUser",
        foreign_keys=[updated_by],
        lazy="selectin",
    )

    __table_args__ = (
        # Unique constraint: one override per feature per tenant
        UniqueConstraint(
            "tenant_id",
            "feature_key",
            name="uq_feature_flag_override_tenant_feature",
        ),
        # Check constraint: feature_key must be valid
        CheckConstraint(
            f"feature_key IN {VALID_FEATURE_KEYS}",
            name="ck_feature_flag_override_valid_key",
        ),
        # Indexes for common queries
        Index("ix_feature_flag_overrides_tenant_id", "tenant_id"),
        Index("ix_feature_flag_overrides_feature_key", "feature_key"),
        Index(
            "ix_feature_flag_overrides_tenant_feature",
            "tenant_id",
            "feature_key",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<FeatureFlagOverride("
            f"tenant_id={self.tenant_id}, "
            f"feature={self.feature_key}, "
            f"value={self.override_value}"
            f")>"
        )
