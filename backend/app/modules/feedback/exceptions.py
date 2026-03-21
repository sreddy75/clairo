"""Domain exceptions for the feedback module."""

from app.core.exceptions import DomainError


class FeedbackError(DomainError):
    """Base exception for feedback module errors."""

    def __init__(
        self,
        message: str,
        code: str = "FEEDBACK_ERROR",
        details: dict | None = None,
        status_code: int = 400,
    ):
        super().__init__(
            message=message,
            code=code,
            details=details or {},
            status_code=status_code,
        )


class SubmissionNotFoundError(FeedbackError):
    def __init__(self, submission_id=None):
        super().__init__(
            message=f"Feedback submission '{submission_id}' not found",
            code="SUBMISSION_NOT_FOUND",
            status_code=404,
        )


class ConversationCompleteError(FeedbackError):
    def __init__(self, submission_id=None):
        super().__init__(
            message=f"Conversation for submission '{submission_id}' is already complete",
            code="CONVERSATION_COMPLETE",
            status_code=400,
        )


class InvalidAudioError(FeedbackError):
    def __init__(self, reason: str = "Invalid audio file"):
        super().__init__(
            message=reason,
            code="INVALID_AUDIO",
            status_code=400,
        )


class BriefNotReadyError(FeedbackError):
    def __init__(self, submission_id=None):
        super().__init__(
            message=f"Brief for submission '{submission_id}' has not been generated yet",
            code="BRIEF_NOT_READY",
            status_code=400,
        )
