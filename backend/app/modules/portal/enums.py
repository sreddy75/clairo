"""Portal module enums."""

from enum import Enum


class InvitationStatus(str, Enum):
    """Status of portal invitation."""

    PENDING = "PENDING"
    SENT = "SENT"
    ACCEPTED = "ACCEPTED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"


class RequestStatus(str, Enum):
    """Status of a document request."""

    DRAFT = "DRAFT"
    PENDING = "PENDING"
    VIEWED = "VIEWED"
    IN_PROGRESS = "IN_PROGRESS"  # Client has started responding
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"


class RequestPriority(str, Enum):
    """Priority level for requests."""

    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class RequestEventType(str, Enum):
    """Types of request events."""

    CREATED = "CREATED"
    SENT = "SENT"
    VIEWED = "VIEWED"
    UPDATED = "UPDATED"
    RESPONSE_SUBMITTED = "RESPONSE_SUBMITTED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    REMINDER_SENT = "REMINDER_SENT"
    DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"
    DOCUMENT_REMOVED = "DOCUMENT_REMOVED"


class ActorType(str, Enum):
    """Type of actor for event."""

    SYSTEM = "SYSTEM"
    USER = "USER"  # Accountant/staff user
    ACCOUNTANT = "ACCOUNTANT"  # Alias for USER
    CLIENT = "CLIENT"  # Business owner via portal


class BulkRequestStatus(str, Enum):
    """Status of bulk request batch."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class ScanStatus(str, Enum):
    """Virus scan status for documents."""

    PENDING = "PENDING"
    CLEAN = "CLEAN"
    INFECTED = "INFECTED"
