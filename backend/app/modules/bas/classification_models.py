"""SQLAlchemy models for client transaction classification.

Spec 047: Client Transaction Classification.
Extends BAS preparation workflow so accountants can send clients a magic link
to classify unresolved transactions in plain English.

Two new tables:
- classification_requests: Links a BAS session to a client classification request
- client_classifications: Per-transaction classification from the client
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.modules.auth.models import PracticeUser
    from app.modules.integrations.xero.models import XeroConnection
    from app.modules.portal.models import PortalDocument, PortalInvitation, PortalSession

    from .models import BASSession, TaxCodeSuggestion


# ---------------------------------------------------------------------------
# Status Constants
# ---------------------------------------------------------------------------


class ClassificationRequestStatus:
    """Status values for classification requests (stored as varchar)."""

    DRAFT = "draft"
    SENT = "sent"
    VIEWED = "viewed"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    REVIEWING = "reviewing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"

    TERMINAL = {COMPLETED, CANCELLED, EXPIRED}
    ACTIVE = {DRAFT, SENT, VIEWED, IN_PROGRESS, SUBMITTED, REVIEWING}


# ---------------------------------------------------------------------------
# ClassificationRequest
# ---------------------------------------------------------------------------


class ClassificationRequest(Base, TimestampMixin):
    """Accountant's request for a client to classify unresolved transactions.

    Links a BAS session to a portal invitation. One active request per session.
    """

    __tablename__ = "classification_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("xero_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bas_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    invitation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("portal_invitations.id", ondelete="SET NULL"),
        nullable=True,
    )
    requested_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practice_users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Multi-round send-back support (Spec 049)
    parent_request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classification_requests.id", ondelete="SET NULL"),
        nullable=True,
        comment="Parent request for round 2+ send-backs; NULL for initial requests",
    )
    round_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
        comment="1 = initial request; 2+ = each send-back round",
    )

    # Client contact
    client_email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional message from accountant to client",
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=ClassificationRequestStatus.DRAFT,
    )

    # Counts
    transaction_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    classified_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Timestamps
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practice_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Relationships
    connection: Mapped["XeroConnection"] = relationship(
        foreign_keys=[connection_id],
        lazy="selectin",
    )
    session: Mapped["BASSession"] = relationship(
        foreign_keys=[session_id],
        lazy="selectin",
    )
    invitation: Mapped["PortalInvitation | None"] = relationship(
        foreign_keys=[invitation_id],
        lazy="selectin",
    )
    requester: Mapped["PracticeUser"] = relationship(
        foreign_keys=[requested_by],
        lazy="selectin",
    )
    classifications: Mapped[list["ClientClassification"]] = relationship(
        back_populates="request",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    parent_request: Mapped["ClassificationRequest | None"] = relationship(
        "ClassificationRequest",
        foreign_keys=[parent_request_id],
        remote_side="ClassificationRequest.id",
        lazy="selectin",
    )
    child_requests: Mapped[list["ClassificationRequest"]] = relationship(
        "ClassificationRequest",
        foreign_keys="ClassificationRequest.parent_request_id",
        lazy="selectin",
    )

    __table_args__ = (
        # Unique per root request per session (partial index handles multi-round)
        # Migration 049 drops the old UNIQUE(session_id) and adds this partial index
        Index("ix_classification_request_connection_status", "connection_id", "status"),
    )


# ---------------------------------------------------------------------------
# ClientClassification
# ---------------------------------------------------------------------------


class ClientClassification(Base, TimestampMixin):
    """Per-transaction classification from the client.

    Records the full audit chain: what the client said, what the AI mapped,
    what the accountant approved, and whether a receipt was attached.
    """

    __tablename__ = "client_classifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classification_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Transaction reference (denormalized snapshots)
    source_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    line_item_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # Denormalized transaction context
    transaction_date: Mapped[datetime | None] = mapped_column(
        Date,
        nullable=True,
    )
    line_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Bank/payee description from Xero",
    )
    contact_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    account_code: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    # Client input
    client_category: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Category ID from taxonomy (e.g. office_supplies)",
    )
    client_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Free-text description from client",
    )
    client_is_personal: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    client_needs_help: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    # Client classification metadata
    classified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    classified_by_session: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("portal_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )

    # AI mapping
    ai_suggested_tax_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    ai_confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 2),
        nullable=True,
    )
    ai_mapped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    suggestion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tax_code_suggestions.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Accountant review
    accountant_action: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="approved / overridden / rejected",
    )
    accountant_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practice_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    accountant_tax_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Final tax type if overridden",
    )
    accountant_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    accountant_acted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Receipt / invoice
    receipt_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    receipt_flag_source: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="auto or manual",
    )
    receipt_flag_reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    receipt_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("portal_documents.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    request: Mapped["ClassificationRequest"] = relationship(
        back_populates="classifications",
    )
    portal_session: Mapped["PortalSession | None"] = relationship(
        foreign_keys=[classified_by_session],
        lazy="selectin",
    )
    suggestion: Mapped["TaxCodeSuggestion | None"] = relationship(
        foreign_keys=[suggestion_id],
        lazy="selectin",
    )
    receipt_document: Mapped["PortalDocument | None"] = relationship(
        foreign_keys=[receipt_document_id],
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint(
            "request_id",
            "source_type",
            "source_id",
            "line_item_index",
            name="uq_client_classification_request_source_line",
        ),
    )


# ---------------------------------------------------------------------------
# AgentTransactionNote (Spec 049)
# ---------------------------------------------------------------------------


class AgentTransactionNote(Base, TimestampMixin):
    """Per-transaction note added by the tax agent.

    Can be an initial context note when creating a classification request
    (is_send_back_comment=False) or a guidance note when sending items back
    to the client for clarification (is_send_back_comment=True).
    """

    __tablename__ = "agent_transaction_notes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classification_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    line_item_index: Mapped[int] = mapped_column(Integer, nullable=False)
    note_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_send_back_comment: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="False = initial context note; True = guidance on send-back",
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practice_users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    request: Mapped["ClassificationRequest"] = relationship(
        foreign_keys=[request_id],
        lazy="selectin",
    )
    created_by_user: Mapped["PracticeUser | None"] = relationship(
        foreign_keys=[created_by],
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_agent_transaction_notes_tenant_request", "tenant_id", "request_id"),
        Index(
            "ix_agent_transaction_notes_request_source",
            "request_id",
            "source_type",
            "source_id",
            "line_item_index",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AgentTransactionNote {self.id} request={self.request_id}"
            f" send_back={self.is_send_back_comment}>"
        )


# ---------------------------------------------------------------------------
# ClientClassificationRound (Spec 049)
# ---------------------------------------------------------------------------


class ClientClassificationRound(Base, TimestampMixin):
    """Tracks the per-transaction conversation thread across multiple rounds.

    Each row captures one round of the send-back loop for a specific
    transaction line item: the agent comment and the client's eventual response.
    Round 1 has no agent_comment (it's the initial classification).
    """

    __tablename__ = "client_classification_rounds"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bas_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    line_item_index: Mapped[int] = mapped_column(Integer, nullable=False)
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classification_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_response_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    client_response_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_needs_help: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    request: Mapped["ClassificationRequest"] = relationship(
        foreign_keys=[request_id],
        lazy="selectin",
    )

    __table_args__ = (
        Index(
            "ix_client_classification_rounds_tenant_session_source",
            "tenant_id",
            "session_id",
            "source_type",
            "source_id",
            "line_item_index",
        ),
        Index(
            "ix_client_classification_rounds_tenant_request",
            "tenant_id",
            "request_id",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ClientClassificationRound {self.id} round={self.round_number}"
            f" session={self.session_id}>"
        )
