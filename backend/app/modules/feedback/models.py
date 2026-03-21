"""SQLAlchemy models for the feedback module."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import BaseModel, TenantMixin
from app.modules.feedback.enums import (
    ContentType,
    MessageRole,
    SubmissionStatus,
    SubmissionType,
)


class FeedbackSubmission(BaseModel, TenantMixin):
    __tablename__ = "feedback_submissions"

    submitter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    submitter_name: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=SubmissionType.FEATURE_REQUEST.value
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=SubmissionStatus.DRAFT.value
    )
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    audio_file_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    audio_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    brief_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    brief_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    conversation_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    messages: Mapped[list[FeedbackMessage]] = relationship(
        back_populates="submission",
        cascade="all, delete-orphan",
        order_by="FeedbackMessage.created_at",
    )
    comments: Mapped[list[FeedbackComment]] = relationship(
        back_populates="submission",
        cascade="all, delete-orphan",
        order_by="FeedbackComment.created_at",
    )

    __table_args__ = (
        Index("ix_feedback_submissions_tenant_status", "tenant_id", "status"),
        Index("ix_feedback_submissions_tenant_submitter", "tenant_id", "submitter_id"),
        Index("ix_feedback_submissions_tenant_type", "tenant_id", "type"),
    )


class FeedbackMessage(BaseModel):
    __tablename__ = "feedback_messages"

    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("feedback_submissions.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=MessageRole.USER.value)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ContentType.TEXT.value
    )

    submission: Mapped[FeedbackSubmission] = relationship(back_populates="messages")

    __table_args__ = (
        Index("ix_feedback_messages_submission_created", "submission_id", "created_at"),
    )


class FeedbackComment(BaseModel):
    __tablename__ = "feedback_comments"

    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("feedback_submissions.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    author_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    submission: Mapped[FeedbackSubmission] = relationship(back_populates="comments")

    __table_args__ = (Index("ix_feedback_comments_submission", "submission_id"),)
