"""SQLAlchemy models for practice client management.

This module defines:
- Enums: AccountingSoftwareType, ManualBASStatus, ExclusionReason
- Models: PracticeClient, ClientQuarterExclusion, ClientNoteHistory

RLS (Row-Level Security):
- RLS is enforced on all tenant-scoped tables
- RLS uses PostgreSQL session variable `app.current_tenant_id`
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TenantMixin, TimestampMixin

if TYPE_CHECKING:
    from app.modules.auth.models import PracticeUser
    from app.modules.integrations.xero.models import XeroConnection


# =============================================================================
# Enums
# =============================================================================


class AccountingSoftwareType(str, enum.Enum):
    """Accounting software used by a client business."""

    XERO = "xero"
    QUICKBOOKS = "quickbooks"
    MYOB = "myob"
    EMAIL = "email"
    OTHER = "other"
    UNKNOWN = "unknown"


class ManualBASStatus(str, enum.Enum):
    """Manual BAS status for non-Xero clients."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    LODGED = "lodged"


class ExclusionReason(str, enum.Enum):
    """Reason for excluding a client from a BAS quarter."""

    DORMANT = "dormant"
    LODGED_EXTERNALLY = "lodged_externally"
    GST_CANCELLED = "gst_cancelled"
    LEFT_PRACTICE = "left_practice"
    OTHER = "other"


# =============================================================================
# PracticeClient
# =============================================================================


class PracticeClient(Base, TenantMixin, TimestampMixin):
    """Universal practice client entity.

    One record per client the practice manages, regardless of
    accounting software. Wraps both Xero-connected and manually-added
    clients into a unified dashboard view.

    Attributes:
        id: Unique identifier (UUID).
        tenant_id: FK to tenants (multi-tenancy, via TenantMixin).
        name: Client business name.
        abn: Australian Business Number (11 digits, optional).
        accounting_software: Software the client uses.
        xero_connection_id: Optional FK to xero_connections (unique).
        assigned_user_id: FK to practice_users (team member responsible).
        notes: Persistent client notes (carries across quarters).
        notes_updated_at: When notes were last edited.
        notes_updated_by: FK to practice_users (who last edited notes).
        manual_status: BAS status for non-Xero clients.
    """

    __tablename__ = "practice_clients"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Client identity
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Client business name",
    )
    abn: Mapped[str | None] = mapped_column(
        String(11),
        nullable=True,
        comment="Australian Business Number (11 digits)",
    )
    accounting_software: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=AccountingSoftwareType.UNKNOWN.value,
        server_default="unknown",
        comment="Accounting software: xero, quickbooks, myob, email, other, unknown",
    )

    # Xero connection (optional — NULL for non-Xero clients)
    xero_connection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        comment="FK to xero_connections (NULL for non-Xero clients)",
    )

    # Team assignment
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practice_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Team member responsible for this client",
    )

    # Persistent notes
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Persistent client notes (carries across quarters)",
    )
    notes_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When notes were last edited",
    )
    notes_updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practice_users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Who last edited notes",
    )

    # Manual BAS status (non-Xero clients only)
    manual_status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="BAS status for non-Xero clients: not_started, in_progress, completed, lodged",
    )

    # GST reporting basis preference (Spec 062)
    gst_reporting_basis: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        comment="'cash' or 'accrual'; NULL = not yet confirmed by accountant",
    )
    gst_basis_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the GST reporting basis was last changed",
    )
    gst_basis_updated_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("practice_users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Which accountant last changed the GST reporting basis",
    )

    # Relationships
    xero_connection: Mapped["XeroConnection | None"] = relationship(
        "XeroConnection",
        foreign_keys=[xero_connection_id],
        lazy="joined",
    )
    assigned_user: Mapped["PracticeUser | None"] = relationship(
        "PracticeUser",
        foreign_keys=[assigned_user_id],
        lazy="joined",
    )
    notes_editor: Mapped["PracticeUser | None"] = relationship(
        "PracticeUser",
        foreign_keys=[notes_updated_by],
        lazy="select",
    )
    exclusions: Mapped[list["ClientQuarterExclusion"]] = relationship(
        "ClientQuarterExclusion",
        back_populates="client",
        lazy="select",
    )
    note_history: Mapped[list["ClientNoteHistory"]] = relationship(
        "ClientNoteHistory",
        back_populates="client",
        lazy="select",
    )

    # Indexes
    __table_args__ = (
        Index("ix_practice_clients_tenant_software", "tenant_id", "accounting_software"),
        Index("ix_practice_clients_tenant_name", "tenant_id", "name"),
        CheckConstraint(
            "accounting_software IN ('xero', 'quickbooks', 'myob', 'email', 'other', 'unknown')",
            name="ck_practice_clients_software",
        ),
        CheckConstraint(
            "manual_status IS NULL OR manual_status IN ('not_started', 'in_progress', 'completed', 'lodged')",
            name="ck_practice_clients_manual_status",
        ),
    )

    def __repr__(self) -> str:
        return f"<PracticeClient(id={self.id}, name={self.name!r}, software={self.accounting_software})>"

    @property
    def has_xero_connection(self) -> bool:
        """Check if client is connected to Xero."""
        return self.xero_connection_id is not None

    @property
    def assigned_user_name(self) -> str | None:
        """Get assigned team member's display name or email."""
        if self.assigned_user is None:
            return None
        if hasattr(self.assigned_user, "display_name") and self.assigned_user.display_name:
            return self.assigned_user.display_name
        return self.assigned_user.email

    @property
    def notes_preview(self) -> str | None:
        """Get first 100 chars of notes for dashboard display."""
        if not self.notes:
            return None
        return self.notes[:100] + ("..." if len(self.notes) > 100 else "")


# =============================================================================
# ClientQuarterExclusion
# =============================================================================


class ClientQuarterExclusion(Base, TenantMixin):
    """Per-quarter exclusion record for practice clients.

    Presence of an active row (reversed_at IS NULL) means the client
    is excluded from BAS obligations for that quarter.

    Attributes:
        id: Unique identifier (UUID).
        tenant_id: FK to tenants (multi-tenancy).
        client_id: FK to practice_clients.
        quarter: Quarter number (1-4).
        fy_year: Financial year (e.g., '2025-26').
        reason: Optional exclusion reason.
        reason_detail: Free text detail (when reason = 'other').
        excluded_by: FK to practice_users (who excluded).
        excluded_at: When exclusion was created.
        reversed_at: When exclusion was reversed (soft delete).
        reversed_by: FK to practice_users (who reversed).
    """

    __tablename__ = "client_quarter_exclusions"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Client reference
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practice_clients.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Quarter identification
    quarter: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        comment="Quarter number (1-4)",
    )
    fy_year: Mapped[str] = mapped_column(
        String(7),
        nullable=False,
        comment="Financial year (e.g., '2025-26')",
    )

    # Reason
    reason: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        comment="Exclusion reason: dormant, lodged_externally, gst_cancelled, left_practice, other",
    )
    reason_detail: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Free text detail (when reason = 'other')",
    )

    # Audit fields
    excluded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practice_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    excluded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )
    reversed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    reversed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practice_users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    client: Mapped["PracticeClient"] = relationship(
        "PracticeClient",
        back_populates="exclusions",
    )
    excluded_by_user: Mapped["PracticeUser"] = relationship(
        "PracticeUser",
        foreign_keys=[excluded_by],
        lazy="joined",
    )
    reversed_by_user: Mapped["PracticeUser | None"] = relationship(
        "PracticeUser",
        foreign_keys=[reversed_by],
        lazy="select",
    )

    # Indexes and constraints
    __table_args__ = (
        # One active exclusion per client per quarter (partial unique index)
        Index(
            "uix_client_quarter_exclusion_active",
            "client_id",
            "quarter",
            "fy_year",
            unique=True,
            postgresql_where=text("reversed_at IS NULL"),
        ),
        Index("ix_exclusions_tenant_quarter", "tenant_id", "quarter", "fy_year"),
        CheckConstraint("quarter >= 1 AND quarter <= 4", name="ck_exclusion_quarter_range"),
    )

    def __repr__(self) -> str:
        return f"<ClientQuarterExclusion(client_id={self.client_id}, Q{self.quarter} {self.fy_year})>"


# =============================================================================
# ClientNoteHistory
# =============================================================================


class ClientNoteHistory(Base, TenantMixin):
    """Append-only audit trail for persistent note changes.

    Each time a client's persistent notes are updated, a new row is
    inserted capturing the note content at that point in time.

    Attributes:
        id: Unique identifier (UUID).
        tenant_id: FK to tenants (multi-tenancy).
        client_id: FK to practice_clients.
        note_text: Snapshot of note content at time of change.
        edited_by: FK to practice_users (who made the edit).
        edited_at: When this version was saved.
    """

    __tablename__ = "client_note_history"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Client reference
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practice_clients.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Note content
    note_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Snapshot of note content at time of change",
    )

    # Audit fields
    edited_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practice_users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    edited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )

    # Relationships
    client: Mapped["PracticeClient"] = relationship(
        "PracticeClient",
        back_populates="note_history",
    )
    editor: Mapped["PracticeUser"] = relationship(
        "PracticeUser",
        foreign_keys=[edited_by],
        lazy="joined",
    )

    # Indexes
    __table_args__ = (
        Index("ix_note_history_client_date", "client_id", text("edited_at DESC")),
    )

    def __repr__(self) -> str:
        return f"<ClientNoteHistory(client_id={self.client_id}, edited_at={self.edited_at})>"
