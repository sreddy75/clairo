"""Feedback module Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.feedback.enums import (
    ContentType,
    MessageRole,
    SubmissionStatus,
    SubmissionType,
)

if TYPE_CHECKING:
    from app.modules.feedback.models import FeedbackComment, FeedbackMessage, FeedbackSubmission


# --- Request schemas ---


class SubmissionCreate(BaseModel):
    """Schema for creating a feedback submission."""

    type: SubmissionType


class StatusUpdate(BaseModel):
    """Schema for updating submission status."""

    status: SubmissionStatus


class BriefConfirmRequest(BaseModel):
    """Schema for confirming or requesting revisions to a brief."""

    revisions: str | None = None


class MessageCreate(BaseModel):
    """Schema for sending a message in a conversation."""

    content: str = Field(..., min_length=1)
    content_type: str = Field(default="text")


class CommentCreate(BaseModel):
    """Schema for creating a comment on a submission."""

    content: str = Field(..., min_length=1, max_length=5000)


# --- Response schemas ---


class MessageResponse(BaseModel):
    """Schema for a conversation message response."""

    id: UUID
    role: MessageRole
    content: str
    content_type: ContentType
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, message: FeedbackMessage) -> MessageResponse:
        """Create response from model."""
        return cls(
            id=message.id,
            role=MessageRole(message.role),
            content=message.content,
            content_type=ContentType(message.content_type),
            created_at=message.created_at,
        )


class CommentResponse(BaseModel):
    """Schema for a comment response."""

    id: UUID
    author_id: UUID
    author_name: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, comment: FeedbackComment) -> CommentResponse:
        """Create response from model."""
        return cls(
            id=comment.id,
            author_id=comment.author_id,
            author_name=comment.author_name,
            content=comment.content,
            created_at=comment.created_at,
        )


class SubmissionResponse(BaseModel):
    """Schema for submission response."""

    id: UUID
    tenant_id: UUID
    submitter_id: UUID
    submitter_name: str
    title: str | None
    type: SubmissionType
    status: SubmissionStatus
    severity: str | None
    audio_file_key: str | None
    conversation_complete: bool
    created_at: datetime
    updated_at: datetime

    # Computed fields
    has_brief: bool = False

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, submission: FeedbackSubmission) -> SubmissionResponse:
        """Create response from model with computed fields."""
        return cls(
            id=submission.id,
            tenant_id=submission.tenant_id,
            submitter_id=submission.submitter_id,
            submitter_name=submission.submitter_name,
            title=submission.title,
            type=SubmissionType(submission.type),
            status=SubmissionStatus(submission.status),
            severity=submission.severity,
            audio_file_key=submission.audio_file_key,
            conversation_complete=submission.conversation_complete,
            created_at=submission.created_at,
            updated_at=submission.updated_at,
            has_brief=submission.brief_data is not None,
        )


class SubmissionDetailResponse(SubmissionResponse):
    """Schema for detailed submission response with transcript and brief."""

    transcript: str | None = None
    brief_data: dict | None = None
    brief_markdown: str | None = None
    audio_duration_seconds: int | None = None
    message_count: int = 0
    comment_count: int = 0

    @classmethod
    def from_model(  # type: ignore[override]
        cls,
        submission: FeedbackSubmission,
        *,
        message_count: int = 0,
        comment_count: int = 0,
    ) -> SubmissionDetailResponse:
        """Create detailed response from model with counts."""
        return cls(
            id=submission.id,
            tenant_id=submission.tenant_id,
            submitter_id=submission.submitter_id,
            submitter_name=submission.submitter_name,
            title=submission.title,
            type=SubmissionType(submission.type),
            status=SubmissionStatus(submission.status),
            severity=submission.severity,
            audio_file_key=submission.audio_file_key,
            conversation_complete=submission.conversation_complete,
            created_at=submission.created_at,
            updated_at=submission.updated_at,
            has_brief=submission.brief_data is not None,
            transcript=submission.transcript,
            brief_data=submission.brief_data,
            brief_markdown=submission.brief_markdown,
            audio_duration_seconds=submission.audio_duration_seconds,
            message_count=message_count,
            comment_count=comment_count,
        )


class SubmissionListResponse(BaseModel):
    """Schema for paginated submission list."""

    items: list[SubmissionResponse]
    total: int
    limit: int
    offset: int


class ConversationResponse(BaseModel):
    """Schema for full conversation history."""

    messages: list[MessageResponse]


class ConversationTurnResponse(BaseModel):
    """Schema for a single conversation turn (user + assistant)."""

    user_message: MessageResponse
    assistant_message: MessageResponse
    brief_ready: bool
    brief_data: dict | None = None
    brief_markdown: str | None = None


class VoiceConversationTurnResponse(ConversationTurnResponse):
    """Schema for a voice conversation turn with transcript."""

    transcript: str


class FeedbackStats(BaseModel):
    """Schema for feedback statistics."""

    total: int = 0

    # By status
    by_status: dict = Field(
        default_factory=lambda: {
            "draft": 0,
            "new": 0,
            "in_review": 0,
            "planned": 0,
            "in_progress": 0,
            "done": 0,
        }
    )

    # By type
    by_type: dict = Field(
        default_factory=lambda: {
            "feature_request": 0,
            "bug_enhancement": 0,
        }
    )
