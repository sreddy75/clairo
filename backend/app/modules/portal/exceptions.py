"""Portal module domain exceptions.

These exceptions extend DomainError and are automatically handled
by the global exception handler to return appropriate HTTP responses.

Spec: 030-client-portal-document-requests
"""

from typing import Any
from uuid import UUID

from app.core.exceptions import DomainError


class PortalError(DomainError):
    """Base exception for portal module errors."""

    def __init__(
        self,
        message: str,
        code: str = "PORTAL_ERROR",
        details: dict[str, Any] | None = None,
        status_code: int = 400,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            details=details or {},
            status_code=status_code,
        )


# =============================================================================
# Invitation Exceptions
# =============================================================================


class InvitationNotFoundError(PortalError):
    """Invitation not found error."""

    def __init__(self, invitation_id: UUID | str | None = None) -> None:
        message = "Portal invitation not found"
        details: dict[str, Any] = {}
        if invitation_id:
            message = f"Portal invitation '{invitation_id}' not found"
            details["invitation_id"] = str(invitation_id)

        super().__init__(
            message=message,
            code="INVITATION_NOT_FOUND",
            details=details,
            status_code=404,
        )


class InvitationExpiredError(PortalError):
    """Invitation has expired error."""

    def __init__(self, invitation_id: UUID | str | None = None) -> None:
        message = "Portal invitation has expired"
        details: dict[str, Any] = {}
        if invitation_id:
            details["invitation_id"] = str(invitation_id)

        super().__init__(
            message=message,
            code="INVITATION_EXPIRED",
            details=details,
            status_code=410,  # Gone
        )


class InvitationAlreadyAcceptedError(PortalError):
    """Invitation has already been accepted error."""

    def __init__(self, invitation_id: UUID | str | None = None) -> None:
        message = "Portal invitation has already been accepted"
        details: dict[str, Any] = {}
        if invitation_id:
            details["invitation_id"] = str(invitation_id)

        super().__init__(
            message=message,
            code="INVITATION_ALREADY_ACCEPTED",
            details=details,
            status_code=409,  # Conflict
        )


class InvitationInvalidTokenError(PortalError):
    """Invalid invitation token error."""

    def __init__(self) -> None:
        super().__init__(
            message="Invalid or malformed invitation token",
            code="INVITATION_INVALID_TOKEN",
            status_code=400,
        )


# =============================================================================
# Session Exceptions
# =============================================================================


class PortalSessionNotFoundError(PortalError):
    """Portal session not found error."""

    def __init__(self, session_id: UUID | str | None = None) -> None:
        message = "Portal session not found"
        details: dict[str, Any] = {}
        if session_id:
            message = f"Portal session '{session_id}' not found"
            details["session_id"] = str(session_id)

        super().__init__(
            message=message,
            code="SESSION_NOT_FOUND",
            details=details,
            status_code=404,
        )


class PortalSessionExpiredError(PortalError):
    """Portal session has expired error."""

    def __init__(self) -> None:
        super().__init__(
            message="Portal session has expired. Please log in again.",
            code="SESSION_EXPIRED",
            status_code=401,
        )


class PortalSessionRevokedError(PortalError):
    """Portal session has been revoked error."""

    def __init__(self, reason: str | None = None) -> None:
        message = "Portal session has been revoked"
        details: dict[str, Any] = {}
        if reason:
            message = f"Portal session has been revoked: {reason}"
            details["reason"] = reason

        super().__init__(
            message=message,
            code="SESSION_REVOKED",
            details=details,
            status_code=401,
        )


class PortalAuthenticationError(PortalError):
    """Portal authentication failure error."""

    def __init__(self, message: str = "Portal authentication failed") -> None:
        super().__init__(
            message=message,
            code="PORTAL_AUTH_ERROR",
            status_code=401,
        )


# =============================================================================
# Document Request Exceptions
# =============================================================================


class RequestNotFoundError(PortalError):
    """Document request not found error."""

    def __init__(self, request_id: UUID | str | None = None) -> None:
        message = "Document request not found"
        details: dict[str, Any] = {}
        if request_id:
            message = f"Document request '{request_id}' not found"
            details["request_id"] = str(request_id)

        super().__init__(
            message=message,
            code="REQUEST_NOT_FOUND",
            details=details,
            status_code=404,
        )


class RequestAlreadyCompleteError(PortalError):
    """Document request is already complete error."""

    def __init__(self, request_id: UUID | str | None = None) -> None:
        message = "Document request has already been completed"
        details: dict[str, Any] = {}
        if request_id:
            details["request_id"] = str(request_id)

        super().__init__(
            message=message,
            code="REQUEST_ALREADY_COMPLETE",
            details=details,
            status_code=409,
        )


class RequestCancelledError(PortalError):
    """Document request has been cancelled error."""

    def __init__(self, request_id: UUID | str | None = None) -> None:
        message = "Document request has been cancelled"
        details: dict[str, Any] = {}
        if request_id:
            details["request_id"] = str(request_id)

        super().__init__(
            message=message,
            code="REQUEST_CANCELLED",
            details=details,
            status_code=410,
        )


class RequestTemplateNotFoundError(PortalError):
    """Document request template not found error."""

    def __init__(self, template_id: UUID | str | None = None) -> None:
        message = "Document request template not found"
        details: dict[str, Any] = {}
        if template_id:
            message = f"Document request template '{template_id}' not found"
            details["template_id"] = str(template_id)

        super().__init__(
            message=message,
            code="TEMPLATE_NOT_FOUND",
            details=details,
            status_code=404,
        )


# =============================================================================
# Document Exceptions
# =============================================================================


class DocumentNotFoundError(PortalError):
    """Portal document not found error."""

    def __init__(self, document_id: UUID | str | None = None) -> None:
        message = "Document not found"
        details: dict[str, Any] = {}
        if document_id:
            message = f"Document '{document_id}' not found"
            details["document_id"] = str(document_id)

        super().__init__(
            message=message,
            code="DOCUMENT_NOT_FOUND",
            details=details,
            status_code=404,
        )


class DocumentUploadError(PortalError):
    """Document upload failure error."""

    def __init__(
        self, message: str = "Failed to upload document", reason: str | None = None
    ) -> None:
        details: dict[str, Any] = {}
        if reason:
            details["reason"] = reason

        super().__init__(
            message=message,
            code="DOCUMENT_UPLOAD_ERROR",
            details=details,
            status_code=500,
        )


class DocumentScanFailedError(PortalError):
    """Document failed virus scan error."""

    def __init__(self, document_id: UUID | str | None = None) -> None:
        message = "Document failed security scan and cannot be processed"
        details: dict[str, Any] = {}
        if document_id:
            details["document_id"] = str(document_id)

        super().__init__(
            message=message,
            code="DOCUMENT_SCAN_FAILED",
            details=details,
            status_code=422,
        )


class DocumentFileTooLargeError(PortalError):
    """Document file size exceeds limit error."""

    def __init__(self, file_size: int, max_size: int) -> None:
        message = f"File size ({file_size} bytes) exceeds maximum allowed size ({max_size} bytes)"

        super().__init__(
            message=message,
            code="DOCUMENT_TOO_LARGE",
            details={
                "file_size": file_size,
                "max_size": max_size,
            },
            status_code=413,
        )


class DocumentInvalidTypeError(PortalError):
    """Document type not allowed error."""

    def __init__(self, content_type: str, allowed_types: list[str]) -> None:
        message = f"File type '{content_type}' is not allowed"

        super().__init__(
            message=message,
            code="DOCUMENT_INVALID_TYPE",
            details={
                "content_type": content_type,
                "allowed_types": allowed_types,
            },
            status_code=415,
        )


# =============================================================================
# Bulk Request Exceptions
# =============================================================================


class BulkRequestNotFoundError(PortalError):
    """Bulk request not found error."""

    def __init__(self, bulk_request_id: UUID | str | None = None) -> None:
        message = "Bulk request not found"
        details: dict[str, Any] = {}
        if bulk_request_id:
            message = f"Bulk request '{bulk_request_id}' not found"
            details["bulk_request_id"] = str(bulk_request_id)

        super().__init__(
            message=message,
            code="BULK_REQUEST_NOT_FOUND",
            details=details,
            status_code=404,
        )


class BulkRequestInProgressError(PortalError):
    """Bulk request is still processing error."""

    def __init__(self, bulk_request_id: UUID | str | None = None) -> None:
        message = "Bulk request is still being processed"
        details: dict[str, Any] = {}
        if bulk_request_id:
            details["bulk_request_id"] = str(bulk_request_id)

        super().__init__(
            message=message,
            code="BULK_REQUEST_IN_PROGRESS",
            details=details,
            status_code=409,
        )
