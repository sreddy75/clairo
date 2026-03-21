"""Repository pattern for feedback data access.

Provides database operations for:
- FeedbackSubmission
- FeedbackMessage
- FeedbackComment
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.feedback.models import (
    FeedbackComment,
    FeedbackMessage,
    FeedbackSubmission,
)


class FeedbackRepository:
    """Repository for feedback module data access."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session

    # =========================================================================
    # Submission CRUD
    # =========================================================================

    async def create_submission(self, submission: FeedbackSubmission) -> FeedbackSubmission:
        """Create a new feedback submission."""
        self.session.add(submission)
        await self.session.flush()
        await self.session.refresh(submission)
        return submission

    async def get_submission(
        self, submission_id: UUID, tenant_id: UUID
    ) -> FeedbackSubmission | None:
        """Get submission by ID with tenant filtering."""
        result = await self.session.execute(
            select(FeedbackSubmission).where(
                FeedbackSubmission.id == submission_id,
                FeedbackSubmission.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_submissions(
        self,
        tenant_id: UUID,
        status: str | None = None,
        type: str | None = None,
        submitter_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[FeedbackSubmission], int]:
        """List submissions with optional filters and pagination.

        Returns (items, total_count).
        """
        base_query = select(FeedbackSubmission).where(FeedbackSubmission.tenant_id == tenant_id)

        if status is not None:
            base_query = base_query.where(FeedbackSubmission.status == status)
        if type is not None:
            base_query = base_query.where(FeedbackSubmission.type == type)
        if submitter_id is not None:
            base_query = base_query.where(FeedbackSubmission.submitter_id == submitter_id)

        # Count total
        count_result = await self.session.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar() or 0

        # Fetch paginated
        query = (
            base_query.order_by(FeedbackSubmission.created_at.desc()).offset(offset).limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def update_submission(self, submission: FeedbackSubmission) -> FeedbackSubmission:
        """Update an existing submission (caller mutates, we flush)."""
        await self.session.flush()
        await self.session.refresh(submission)
        return submission

    async def update_status(
        self, submission_id: UUID, tenant_id: UUID, new_status: str
    ) -> FeedbackSubmission | None:
        """Update the status of a submission. Returns None if not found."""
        submission = await self.get_submission(submission_id, tenant_id)
        if not submission:
            return None

        submission.status = new_status
        await self.session.flush()
        await self.session.refresh(submission)
        return submission

    async def get_stats(self, tenant_id: UUID, submitter_id: UUID | None = None) -> dict:
        """Get submission statistics grouped by status and type.

        Returns dict with total, by_status, and by_type.
        """
        base_filter = [FeedbackSubmission.tenant_id == tenant_id]
        if submitter_id is not None:
            base_filter.append(FeedbackSubmission.submitter_id == submitter_id)

        # Count by status
        status_result = await self.session.execute(
            select(FeedbackSubmission.status, func.count(FeedbackSubmission.id))
            .where(*base_filter)
            .group_by(FeedbackSubmission.status)
        )
        by_status = {status: count for status, count in status_result.all()}

        # Count by type
        type_result = await self.session.execute(
            select(FeedbackSubmission.type, func.count(FeedbackSubmission.id))
            .where(*base_filter)
            .group_by(FeedbackSubmission.type)
        )
        by_type = {sub_type: count for sub_type, count in type_result.all()}

        return {
            "total": sum(by_status.values()),
            "by_status": by_status,
            "by_type": by_type,
        }

    # =========================================================================
    # Messages
    # =========================================================================

    async def create_message(self, message: FeedbackMessage) -> FeedbackMessage:
        """Create a new feedback message."""
        self.session.add(message)
        await self.session.flush()
        await self.session.refresh(message)
        return message

    async def list_messages(self, submission_id: UUID) -> list[FeedbackMessage]:
        """List messages for a submission, ordered by created_at."""
        result = await self.session.execute(
            select(FeedbackMessage)
            .where(FeedbackMessage.submission_id == submission_id)
            .order_by(FeedbackMessage.created_at)
        )
        return list(result.scalars().all())

    async def count_messages(self, submission_id: UUID) -> int:
        """Count messages for a submission."""
        result = await self.session.execute(
            select(func.count(FeedbackMessage.id)).where(
                FeedbackMessage.submission_id == submission_id
            )
        )
        return result.scalar() or 0

    # =========================================================================
    # Comments
    # =========================================================================

    async def create_comment(self, comment: FeedbackComment) -> FeedbackComment:
        """Create a new feedback comment."""
        self.session.add(comment)
        await self.session.flush()
        await self.session.refresh(comment)
        return comment

    async def list_comments(self, submission_id: UUID) -> list[FeedbackComment]:
        """List comments for a submission, ordered by created_at."""
        result = await self.session.execute(
            select(FeedbackComment)
            .where(FeedbackComment.submission_id == submission_id)
            .order_by(FeedbackComment.created_at)
        )
        return list(result.scalars().all())

    async def count_comments(self, submission_id: UUID) -> int:
        """Count comments for a submission."""
        result = await self.session.execute(
            select(func.count(FeedbackComment.id)).where(
                FeedbackComment.submission_id == submission_id
            )
        )
        return result.scalar() or 0
