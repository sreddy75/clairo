"""SQLAlchemy models for onboarding flow.

Models:
- OnboardingProgress: Tracks tenant's progress through onboarding
- BulkImportJob: Tracks bulk client import jobs with progress
- BulkImportOrganization: Tracks individual org status within a bulk import job
- EmailDrip: Tracks sent onboarding emails to prevent duplicates
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.modules.auth.models import Tenant
    from app.modules.integrations.xero.models import XeroConnection


# =============================================================================
# Enums
# =============================================================================


class OnboardingStatus(str, enum.Enum):
    """Status of tenant's onboarding progress."""

    STARTED = "started"
    TIER_SELECTED = "tier_selected"
    PAYMENT_SETUP = "payment_setup"
    XERO_CONNECTED = "xero_connected"
    CLIENTS_IMPORTED = "clients_imported"
    TOUR_COMPLETED = "tour_completed"
    COMPLETED = "completed"
    SKIPPED_XERO = "skipped_xero"

    def __str__(self) -> str:
        """Return the enum value as string."""
        return self.value


class BulkImportJobStatus(str, enum.Enum):
    """Status of bulk import job."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PARTIAL_FAILURE = "partial_failure"
    FAILED = "failed"
    CANCELLED = "cancelled"

    def __str__(self) -> str:
        """Return the enum value as string."""
        return self.value


class EmailDripType(str, enum.Enum):
    """Types of onboarding drip emails."""

    WELCOME = "welcome"
    CONNECT_XERO = "connect_xero"
    IMPORT_CLIENTS = "import_clients"
    TRIAL_MIDPOINT = "trial_midpoint"
    TRIAL_ENDING = "trial_ending"
    TRIAL_ENDED = "trial_ended"
    ONBOARDING_COMPLETE = "onboarding_complete"

    def __str__(self) -> str:
        """Return the enum value as string."""
        return self.value


# =============================================================================
# Models
# =============================================================================


class OnboardingProgress(Base, TimestampMixin):
    """Tracks each tenant's progress through the onboarding flow.

    Each tenant has exactly one OnboardingProgress record (1:1 relationship).
    The status field tracks the current state machine position.

    Attributes:
        id: Unique identifier (UUID).
        tenant_id: Foreign key to tenant (unique, 1:1).
        status: Current onboarding state.
        current_step: Current step identifier for UI routing.
        started_at: When onboarding began.
        tier_selected_at: When tier was chosen.
        payment_setup_at: When Stripe checkout completed.
        xero_connected_at: When Xero OAuth completed.
        clients_imported_at: When first client imported.
        tour_completed_at: When product tour finished.
        completed_at: When all steps done.
        checklist_dismissed_at: When user dismissed checklist.
        xero_skipped: Whether user skipped Xero connection.
        tour_skipped: Whether user skipped product tour.
        extra_data: Additional tracking data (JSONB).
    """

    __tablename__ = "onboarding_progress"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Tenant association (unique, 1:1)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Foreign key to tenant (1:1 relationship)",
    )

    # Current state
    status: Mapped[OnboardingStatus] = mapped_column(
        Enum(
            OnboardingStatus,
            name="onboarding_status",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=OnboardingStatus.STARTED,
        server_default="started",
        index=True,
        comment="Current onboarding state",
    )

    current_step: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="tier_selection",
        server_default="tier_selection",
        comment="Current step identifier for UI routing",
    )

    # Milestone timestamps
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="When onboarding began",
    )

    tier_selected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When tier was chosen",
    )

    payment_setup_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When Stripe checkout completed",
    )

    xero_connected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When Xero OAuth completed",
    )

    clients_imported_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When first client imported",
    )

    tour_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When product tour finished",
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When all steps done",
    )

    checklist_dismissed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When user dismissed checklist",
    )

    # Skip flags
    xero_skipped: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Whether user skipped Xero connection",
    )

    tour_skipped: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Whether user skipped product tour",
    )

    # Additional data
    extra_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="Additional tracking data",
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="onboarding_progress",
        lazy="joined",
    )

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"<OnboardingProgress(id={self.id}, tenant_id={self.tenant_id}, status={self.status})>"
        )

    @property
    def is_complete(self) -> bool:
        """Check if onboarding is fully complete."""
        return self.status == OnboardingStatus.COMPLETED

    @property
    def checklist_dismissed(self) -> bool:
        """Check if checklist has been dismissed."""
        return self.checklist_dismissed_at is not None


class BulkImportJob(Base, TimestampMixin):
    """Tracks bulk client import jobs with progress.

    Each import job runs as a Celery background task and updates
    progress incrementally for real-time UI updates.

    Attributes:
        id: Unique identifier (UUID).
        tenant_id: Foreign key to tenant.
        status: Current job status.
        source_type: "xpm" or "xero_accounting".
        total_clients: Total clients to import.
        imported_count: Successfully imported count.
        failed_count: Failed import count.
        client_ids: List of XPM/Xero client IDs to import (JSONB).
        imported_clients: List of imported client details (JSONB).
        failed_clients: List of failed clients with errors (JSONB).
        progress_percent: Current progress (0-100).
        started_at: Job start time.
        completed_at: Job completion time.
        error_message: Overall error if job failed.
    """

    __tablename__ = "bulk_import_jobs"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Tenant association
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Foreign key to tenant",
    )

    # Job status
    status: Mapped[BulkImportJobStatus] = mapped_column(
        Enum(
            BulkImportJobStatus,
            name="bulk_import_job_status",
            create_constraint=False,
            native_enum=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=BulkImportJobStatus.PENDING,
        server_default="pending",
        index=True,
        comment="Current job status",
    )

    # Source type
    source_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Source: 'xpm' or 'xero_accounting'",
    )

    # Progress counters
    total_clients: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Total clients to import",
    )

    imported_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Successfully imported count",
    )

    failed_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Failed import count",
    )

    progress_percent: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Current progress (0-100)",
    )

    # Client data (JSONB)
    client_ids: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
        comment="List of XPM/Xero client IDs to import",
    )

    imported_clients: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
        comment="List of imported client details",
    )

    failed_clients: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
        comment="List of failed clients with errors",
    )

    # Timestamps
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Job start time",
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Job completion time",
    )

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Overall error if job failed",
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="import_jobs",
        lazy="joined",
    )

    organizations: Mapped[list["BulkImportOrganization"]] = relationship(
        "BulkImportOrganization",
        back_populates="bulk_import_job",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<BulkImportJob(id={self.id}, status={self.status}, progress={self.progress_percent}%)>"

    @property
    def is_complete(self) -> bool:
        """Check if job has finished (success or failure)."""
        return self.status in (
            BulkImportJobStatus.COMPLETED,
            BulkImportJobStatus.PARTIAL_FAILURE,
            BulkImportJobStatus.FAILED,
        )


class BulkImportOrganization(Base, TimestampMixin):
    """Tracks individual organization status within a bulk import job.

    Each record represents one Xero organization that was discovered during
    a bulk OAuth flow and may or may not be selected for import.

    Attributes:
        id: Unique identifier (UUID).
        tenant_id: Foreign key to tenant (RLS scoping).
        bulk_import_job_id: Parent bulk import job.
        xero_tenant_id: Xero organization identifier.
        organization_name: Xero organization display name.
        status: Current status (pending/importing/syncing/completed/failed/skipped).
        connection_id: Created XeroConnection (set after import).
        connection_type: practice or client.
        assigned_user_id: Assigned team member.
        already_connected: True if org was already connected.
        selected_for_import: User's selection on config screen.
        match_status: Auto-match result (matched/suggested/unmatched).
        matched_client_name: Name of matched existing client.
        error_message: Error details if failed.
        sync_started_at: When sync was dispatched.
        sync_completed_at: When sync finished.
    """

    __tablename__ = "bulk_import_organizations"

    __table_args__ = (
        Index("ix_bulk_import_orgs_job", "bulk_import_job_id"),
        Index("ix_bulk_import_orgs_tenant", "tenant_id"),
        Index("ix_bulk_import_orgs_xero_tenant", "xero_tenant_id"),
    )

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Tenant association (RLS scoping)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        comment="Foreign key to tenant (RLS enforced)",
    )

    # Parent job
    bulk_import_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bulk_import_jobs.id", ondelete="CASCADE"),
        nullable=False,
        comment="Parent bulk import job",
    )

    # Xero organization info
    xero_tenant_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Xero organization identifier",
    )

    organization_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Xero organization display name",
    )

    # Status tracking
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
        comment="Status: pending, importing, syncing, completed, failed, skipped",
    )

    # Connection reference (set after import)
    connection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="SET NULL"),
        nullable=True,
        comment="Created XeroConnection (set after import)",
    )

    connection_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="client",
        server_default="client",
        comment="Connection type: practice or client",
    )

    # Assignment
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practice_users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Assigned team member",
    )

    # Selection flags
    already_connected: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="True if org was already connected",
    )

    selected_for_import: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        comment="User's selection on config screen",
    )

    # Auto-matching
    match_status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Auto-match result: matched, suggested, unmatched",
    )

    matched_client_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Name of matched existing client",
    )

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error details if failed",
    )

    # Sync timestamps
    sync_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When sync was dispatched",
    )

    sync_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When sync finished",
    )

    # Relationships
    bulk_import_job: Mapped["BulkImportJob"] = relationship(
        "BulkImportJob",
        back_populates="organizations",
        lazy="joined",
    )

    connection: Mapped["XeroConnection | None"] = relationship(
        "XeroConnection",
        lazy="joined",
        foreign_keys=[connection_id],
    )

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"<BulkImportOrganization(id={self.id}, "
            f"org={self.organization_name}, status={self.status})>"
        )


class EmailDrip(Base):
    """Tracks sent onboarding emails to prevent duplicates.

    Each tenant can only receive each email type once.

    Attributes:
        id: Unique identifier (UUID).
        tenant_id: Foreign key to tenant.
        email_type: Email template identifier.
        sent_at: When email was sent.
        recipient_email: Recipient email address.
        extra_data: Additional context (JSONB).
        created_at: Record creation time.
    """

    __tablename__ = "email_drips"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Tenant association
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Foreign key to tenant",
    )

    # Email tracking
    email_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Email template identifier",
    )

    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="When email was sent",
    )

    recipient_email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Recipient email address",
    )

    # Additional data
    extra_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="Additional context",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Record creation time",
    )

    # Unique constraint - one email type per tenant
    __table_args__ = (
        UniqueConstraint("tenant_id", "email_type", name="uq_email_drip_tenant_type"),
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="email_drips",
        lazy="joined",
    )

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<EmailDrip(id={self.id}, tenant_id={self.tenant_id}, type={self.email_type})>"
