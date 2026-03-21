"""Domain exception hierarchy for Clairo.

All domain-specific errors inherit from DomainError and include:
- HTTP status code for API responses
- Error code for programmatic handling
- Detailed error information

Usage:
    from app.core.exceptions import NotFoundError, ValidationError

    raise NotFoundError("Client", client_id)
    raise ValidationError("Invalid ABN format")
"""

from typing import Any


class DomainError(Exception):
    """Base class for all domain-specific errors.

    Attributes:
        message: Human-readable error description.
        code: Machine-readable error code for API responses.
        details: Additional context about the error.
        status_code: HTTP status code for API responses.
    """

    def __init__(
        self,
        message: str,
        code: str = "DOMAIN_ERROR",
        details: dict[str, Any] | None = None,
        status_code: int = 500,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
        self.status_code = status_code

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for JSON response."""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


class NotFoundError(DomainError):
    """Resource not found error (HTTP 404).

    Raised when a requested resource does not exist.
    """

    def __init__(
        self,
        resource_type: str,
        resource_id: str | int | None = None,
        message: str | None = None,
    ) -> None:
        if message is None:
            if resource_id is not None:
                message = f"{resource_type} with ID '{resource_id}' not found"
            else:
                message = f"{resource_type} not found"

        super().__init__(
            message=message,
            code="NOT_FOUND",
            details={"resource_type": resource_type, "resource_id": str(resource_id)},
            status_code=404,
        )
        self.resource_type = resource_type
        self.resource_id = resource_id


class ValidationError(DomainError):
    """Business rule validation error (HTTP 400).

    Raised when input data fails business rule validation.
    This is separate from Pydantic validation which handles schema validation.
    """

    def __init__(
        self,
        message: str,
        field: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        error_details = details or {}
        if field:
            error_details["field"] = field

        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            details=error_details,
            status_code=400,
        )
        self.field = field


class AuthenticationError(DomainError):
    """Authentication failure error (HTTP 401).

    Raised when authentication fails (invalid or missing credentials).
    """

    def __init__(
        self,
        message: str = "Authentication required",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="AUTHENTICATION_ERROR",
            details=details or {},
            status_code=401,
        )


class AuthorizationError(DomainError):
    """Authorization failure error (HTTP 403).

    Raised when the user is authenticated but lacks permission for the action.
    """

    def __init__(
        self,
        message: str = "Permission denied",
        resource: str | None = None,
        action: str | None = None,
    ) -> None:
        details: dict[str, Any] = {}
        if resource:
            details["resource"] = resource
        if action:
            details["action"] = action

        super().__init__(
            message=message,
            code="AUTHORIZATION_ERROR",
            details=details,
            status_code=403,
        )
        self.resource = resource
        self.action = action


class ConflictError(DomainError):
    """Resource conflict error (HTTP 409).

    Raised when an operation conflicts with existing data,
    such as duplicate entries or optimistic locking failures.
    """

    def __init__(
        self,
        message: str,
        resource_type: str | None = None,
        conflict_field: str | None = None,
    ) -> None:
        details: dict[str, Any] = {}
        if resource_type:
            details["resource_type"] = resource_type
        if conflict_field:
            details["conflict_field"] = conflict_field

        super().__init__(
            message=message,
            code="CONFLICT_ERROR",
            details=details,
            status_code=409,
        )
        self.resource_type = resource_type
        self.conflict_field = conflict_field


class ExternalServiceError(DomainError):
    """External service failure error (HTTP 502).

    Raised when an external service (Xero, MYOB, ATO, etc.) fails.
    """

    def __init__(
        self,
        service: str,
        message: str | None = None,
        original_error: str | None = None,
    ) -> None:
        if message is None:
            message = f"External service '{service}' is unavailable"

        details: dict[str, Any] = {"service": service}
        if original_error:
            details["original_error"] = original_error

        super().__init__(
            message=message,
            code="EXTERNAL_SERVICE_ERROR",
            details=details,
            status_code=502,
        )
        self.service = service
        self.original_error = original_error


class RateLimitError(DomainError):
    """Rate limit exceeded error (HTTP 429).

    Raised when the user has exceeded their rate limit.
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int | None = None,
    ) -> None:
        details: dict[str, Any] = {}
        if retry_after:
            details["retry_after_seconds"] = retry_after

        super().__init__(
            message=message,
            code="RATE_LIMIT_ERROR",
            details=details,
            status_code=429,
        )
        self.retry_after = retry_after
