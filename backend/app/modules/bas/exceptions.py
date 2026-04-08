"""Custom exceptions for BAS lodgement operations.

Spec 011: Interim Lodgement
"""


class BasLodgementError(Exception):
    """Base exception for lodgement errors."""

    def __init__(self, message: str = "A lodgement error occurred"):
        self.message = message
        super().__init__(self.message)


class LodgementNotAllowedError(BasLodgementError):
    """Raised when lodgement is attempted on a non-approved session."""

    def __init__(self, session_id: str | None = None, current_status: str | None = None):
        if session_id and current_status:
            message = (
                f"Cannot record lodgement for session {session_id}. "
                f"Current status is '{current_status}', but must be 'approved'."
            )
        else:
            message = "BAS must be approved before lodgement can be recorded."
        super().__init__(message)
        self.session_id = session_id
        self.current_status = current_status


class LodgementAlreadyRecordedError(BasLodgementError):
    """Raised when lodgement has already been recorded for a session."""

    def __init__(self, session_id: str | None = None):
        if session_id:
            message = f"Lodgement has already been recorded for session {session_id}."
        else:
            message = "Lodgement has already been recorded for this BAS."
        super().__init__(message)
        self.session_id = session_id


class InvalidLodgementMethodError(BasLodgementError):
    """Raised when 'OTHER' method is selected without a description."""

    def __init__(self):
        message = "Description is required when lodgement method is 'Other'."
        super().__init__(message)


class ExportNotAllowedError(BasLodgementError):
    """Raised when lodgement export is attempted on an unapproved session."""

    def __init__(self, session_id: str | None = None, current_status: str | None = None):
        if session_id and current_status:
            message = (
                f"Cannot generate lodgement export for session {session_id}. "
                f"Current status is '{current_status}', but must be 'approved' or 'lodged'."
            )
        else:
            message = "Lodgement exports require an approved or lodged BAS session."
        super().__init__(message)
        self.session_id = session_id
        self.current_status = current_status


class SessionNotFoundError(BasLodgementError):
    """Raised when a BAS session is not found."""

    def __init__(self, session_id: str | None = None) -> None:
        message = f"BAS session {session_id} not found." if session_id else "BAS session not found."
        super().__init__(message)
        self.session_id = session_id


class ConcurrentModificationError(BasLodgementError):
    """Raised when optimistic locking detects a concurrent modification."""

    def __init__(self) -> None:
        message = "This record was modified by another user. Please refresh and try again."
        super().__init__(message)


# =============================================================================
# Tax Code Resolution Exceptions (Spec 046)
# =============================================================================

from app.core.exceptions import DomainError  # noqa: E402


class SuggestionNotFoundError(DomainError):
    """Raised when a tax code suggestion is not found."""

    def __init__(self, suggestion_id: str | None = None) -> None:
        message = (
            f"Tax code suggestion {suggestion_id} not found."
            if suggestion_id
            else "Tax code suggestion not found."
        )
        super().__init__(message=message, code="SUGGESTION_NOT_FOUND", status_code=404)


class SuggestionAlreadyResolvedError(DomainError):
    """Raised when trying to resolve an already-resolved suggestion."""

    def __init__(self, suggestion_id: str | None = None, current_status: str | None = None) -> None:
        message = (
            f"Suggestion {suggestion_id} is already {current_status}."
            if suggestion_id and current_status
            else "This suggestion has already been resolved."
        )
        super().__init__(message=message, code="SUGGESTION_ALREADY_RESOLVED", status_code=409)


class InvalidTaxTypeError(DomainError):
    """Raised when an invalid tax type is provided for override."""

    def __init__(self, tax_type: str | None = None) -> None:
        message = (
            f"'{tax_type}' is not a valid tax type for BAS classification."
            if tax_type
            else "Invalid tax type provided."
        )
        super().__init__(message=message, code="INVALID_TAX_TYPE", status_code=422)


class SessionNotEditableForSuggestionsError(DomainError):
    """Raised when trying to modify suggestions on a non-editable session."""

    def __init__(self, session_id: str | None = None, current_status: str | None = None) -> None:
        message = (
            f"Session {session_id} is in '{current_status}' status and cannot accept suggestion changes."
            if session_id and current_status
            else "BAS session is not in an editable state for tax code changes."
        )
        super().__init__(message=message, code="SESSION_NOT_EDITABLE", status_code=409)


class NoApprovedSuggestionsError(DomainError):
    """Raised when trying to recalculate with no approved suggestions."""

    def __init__(self) -> None:
        super().__init__(
            message="No approved suggestions to apply. Approve tax code suggestions before recalculating.",
            code="NO_APPROVED_SUGGESTIONS",
            status_code=409,
        )


class OverrideNotFoundError(DomainError):
    """Raised when a tax code override is not found."""

    def __init__(self, override_id: str | None = None) -> None:
        message = (
            f"Tax code override {override_id} not found."
            if override_id
            else "Tax code override not found."
        )
        super().__init__(message=message, code="OVERRIDE_NOT_FOUND", status_code=404)


# =============================================================================
# Client Classification Exceptions (Spec 047)
# =============================================================================


class ClassificationRequestExistsError(DomainError):
    """Raised when an active classification request already exists for this session."""

    def __init__(self, session_id: str | None = None) -> None:
        message = (
            f"An active classification request already exists for session {session_id}."
            if session_id
            else "An active classification request already exists for this BAS session."
        )
        super().__init__(message=message, code="CLASSIFICATION_REQUEST_EXISTS", status_code=409)


class ClassificationRequestNotFoundError(DomainError):
    """Raised when a classification request is not found."""

    def __init__(self, request_id: str | None = None) -> None:
        message = (
            f"Classification request {request_id} not found."
            if request_id
            else "Classification request not found."
        )
        super().__init__(message=message, code="CLASSIFICATION_REQUEST_NOT_FOUND", status_code=404)


class ClassificationNotFoundError(DomainError):
    """Raised when a client classification record is not found."""

    def __init__(self, classification_id: str | None = None) -> None:
        message = (
            f"Classification {classification_id} not found."
            if classification_id
            else "Classification not found."
        )
        super().__init__(message=message, code="CLASSIFICATION_NOT_FOUND", status_code=404)


class NoUnresolvedTransactionsError(DomainError):
    """Raised when there are no unresolved transactions to classify."""

    def __init__(self) -> None:
        super().__init__(
            message="No unresolved transactions found for this BAS session.",
            code="NO_UNRESOLVED_TRANSACTIONS",
            status_code=400,
        )


class NoClientEmailError(DomainError):
    """Raised when no email is available for the client."""

    def __init__(self) -> None:
        super().__init__(
            message="No email address available for this client. Provide an email_override or update the client's Xero contact.",
            code="NO_CLIENT_EMAIL",
            status_code=400,
        )


class ClassificationRequestExpiredError(DomainError):
    """Raised when a classification request has expired."""

    def __init__(self, request_id: str | None = None) -> None:
        message = (
            f"Classification request {request_id} has expired."
            if request_id
            else "This classification request has expired."
        )
        super().__init__(message=message, code="CLASSIFICATION_REQUEST_EXPIRED", status_code=410)


class InvalidClassificationActionError(DomainError):
    """Raised when an invalid action is provided for classification resolution."""

    def __init__(self, action: str | None = None) -> None:
        valid = "approved, overridden, rejected"
        message = (
            f"'{action}' is not a valid classification action. Valid actions: {valid}."
            if action
            else f"Invalid classification action. Valid actions: {valid}."
        )
        super().__init__(message=message, code="INVALID_CLASSIFICATION_ACTION", status_code=422)


class ClassificationValidationError(DomainError):
    """Raised when portal classification submission fails validation (Spec 049)."""

    def __init__(self, code: str, message: str | None = None, count: int = 0) -> None:
        self.validation_code = code
        self.count = count
        super().__init__(
            message=message or code,
            code=code,
            status_code=400,
        )


class SplitAmountMismatchError(DomainError):
    """Raised when split line_amounts do not sum to the transaction total (Spec 049)."""

    def __init__(self, expected: object, actual: object) -> None:
        self.expected_total = expected
        self.actual_total = actual
        super().__init__(
            message=f"Split amounts {actual} do not equal transaction total {expected}",
            code="split_amount_mismatch",
            status_code=422,
        )


class SplitOverrideNotFoundError(DomainError):
    """Raised when a split override cannot be found by ID (Spec 049)."""

    def __init__(self, override_id: object) -> None:
        super().__init__(
            message=f"Split override {override_id} not found",
            code="split_override_not_found",
            status_code=404,
        )
