"""Enums for the feedback module."""

from enum import Enum


class SubmissionType(str, Enum):
    FEATURE_REQUEST = "feature_request"
    BUG_ENHANCEMENT = "bug_enhancement"


class SubmissionStatus(str, Enum):
    DRAFT = "draft"
    NEW = "new"
    IN_REVIEW = "in_review"
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ContentType(str, Enum):
    TEXT = "text"
    TRANSCRIPT = "transcript"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
