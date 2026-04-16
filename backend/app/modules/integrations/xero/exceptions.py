"""Domain exceptions for Xero sync operations.

These exceptions are raised by the service layer and should be caught
by the API layer and converted to appropriate HTTP responses.
"""

from uuid import UUID


class XeroSyncError(Exception):
    """Base exception for Xero sync operations."""

    def __init__(self, message: str = "Xero sync error occurred"):
        self.message = message
        super().__init__(self.message)


class XeroConnectionInactiveError(XeroSyncError):
    """Raised when attempting to sync with an inactive connection."""

    def __init__(self, connection_id: UUID):
        self.connection_id = connection_id
        super().__init__(
            f"Xero connection {connection_id} is not active. "
            "Please reconnect to Xero before syncing."
        )


class XeroSyncInProgressError(XeroSyncError):
    """Raised when a sync is already in progress for the connection."""

    def __init__(self, connection_id: UUID, job_id: UUID | None = None):
        self.connection_id = connection_id
        self.job_id = job_id
        message = f"A sync is already in progress for connection {connection_id}"
        if job_id:
            message += f" (job {job_id})"
        super().__init__(message)


class XeroRateLimitExceededError(XeroSyncError):
    """Raised when Xero API rate limit is exceeded."""

    def __init__(
        self,
        wait_seconds: int,
        limit_type: str = "minute",
    ):
        self.wait_seconds = wait_seconds
        self.limit_type = limit_type
        super().__init__(
            f"Xero API {limit_type} rate limit exceeded. "
            f"Please wait {wait_seconds} seconds before retrying."
        )


class XeroSyncJobNotFoundError(XeroSyncError):
    """Raised when a sync job cannot be found."""

    def __init__(self, job_id: UUID):
        self.job_id = job_id
        super().__init__(f"Sync job {job_id} not found")


class XeroDataTransformError(XeroSyncError):
    """Raised when Xero data cannot be transformed to Clairo format."""

    def __init__(
        self,
        xero_id: str,
        entity_type: str,
        reason: str,
    ):
        self.xero_id = xero_id
        self.entity_type = entity_type
        self.reason = reason
        super().__init__(f"Failed to transform Xero {entity_type} (ID: {xero_id}): {reason}")


class XeroApiError(XeroSyncError):
    """Raised when Xero API returns an error."""

    def __init__(
        self,
        status_code: int,
        message: str,
        xero_error: str | None = None,
    ):
        self.status_code = status_code
        self.xero_error = xero_error
        error_msg = f"Xero API error ({status_code}): {message}"
        if xero_error:
            error_msg += f" - {xero_error}"
        super().__init__(error_msg)


class XeroTokenExpiredError(XeroSyncError):
    """Raised when Xero tokens are expired and refresh fails."""

    def __init__(self, connection_id: UUID):
        self.connection_id = connection_id
        super().__init__(
            f"Xero tokens for connection {connection_id} have expired. Please reconnect to Xero."
        )


class XeroAuthRequiredError(XeroSyncError):
    """Raised when Xero re-authorization is required (refresh token expired/revoked).

    Distinct from XeroTokenExpiredError: this means the refresh token itself
    is no longer valid and the user must go through the OAuth flow again.
    """

    def __init__(self, connection_id: UUID, org_name: str = ""):
        self.connection_id = connection_id
        self.org_name = org_name
        detail = f" ({org_name})" if org_name else ""
        super().__init__(
            f"Xero re-authorization required for connection {connection_id}{detail}. "
            "Please reconnect to Xero."
        )


class XeroConnectionNotFoundError(XeroSyncError):
    """Raised when a Xero connection cannot be found."""

    def __init__(self, connection_id: UUID):
        self.connection_id = connection_id
        super().__init__(f"Xero connection {connection_id} not found")


# =============================================================================
# Write-back exceptions (Spec 049)
# =============================================================================


class WritebackError(XeroSyncError):
    """Base exception for Xero write-back operations."""

    def __init__(self, message: str = "Write-back error occurred", code: str | None = None):
        self.code = code or message
        super().__init__(message)


class XeroDocumentNotEditableError(WritebackError):
    """Raised when a Xero document cannot be edited (voided, deleted, locked)."""

    def __init__(self, skip_reason: str, xero_document_id: str = ""):
        self.skip_reason = skip_reason
        self.xero_document_id = xero_document_id
        super().__init__(
            f"Xero document {xero_document_id!r} is not editable: {skip_reason}",
            code=skip_reason,
        )


class XeroConflictError(WritebackError):
    """Raised when Xero document has been modified externally since last sync."""

    def __init__(self, xero_document_id: str):
        self.xero_document_id = xero_document_id
        super().__init__(
            f"Xero document {xero_document_id!r} has been modified in Xero since last sync."
            " Re-sync from Xero before writing back.",
            code="conflict_changed",
        )


class WritebackJobNotFoundError(WritebackError):
    """Raised when a write-back job cannot be found."""

    def __init__(self, job_id: UUID):
        self.job_id = job_id
        super().__init__(f"Write-back job {job_id} not found", code="job_not_found")


# =============================================================================
# OAuth & Service-level exceptions
# =============================================================================


class XeroOAuthError(Exception):
    """Error during Xero OAuth flow."""

    pass


class XeroServiceConnectionNotFoundError(Exception):
    """Xero connection not found (service-layer lookup)."""

    pass


class XeroClientNotFoundError(Exception):
    """Xero client not found."""

    def __init__(self, client_id: UUID) -> None:
        self.client_id = client_id
        super().__init__(f"Xero client {client_id} not found")


class XpmClientNotFoundError(Exception):
    """XPM client not found."""

    def __init__(self, client_id: UUID) -> None:
        self.client_id = client_id
        super().__init__(f"XPM client {client_id} not found")


# =============================================================================
# Bulk import exceptions
# =============================================================================


class BulkImportInProgressError(Exception):
    """Raised when a bulk import is already in progress for the tenant."""

    def __init__(self, tenant_id: UUID, job_id: UUID):
        self.tenant_id = tenant_id
        self.job_id = job_id
        super().__init__(
            f"A bulk import is already in progress for tenant {tenant_id} (job {job_id})"
        )


class BulkImportValidationError(Exception):
    """Raised when bulk import validation fails."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)
