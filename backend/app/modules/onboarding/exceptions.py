"""Domain exceptions for onboarding module.

All exceptions inherit from DomainError and include:
- HTTP status code for API responses
- Error code for programmatic handling
- Detailed error information
"""

from typing import Any
from uuid import UUID

from app.core.exceptions import DomainError, NotFoundError, ValidationError


class OnboardingError(DomainError):
    """Base class for onboarding-specific errors."""

    def __init__(
        self,
        message: str,
        code: str = "ONBOARDING_ERROR",
        details: dict[str, Any] | None = None,
        status_code: int = 400,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            details=details or {},
            status_code=status_code,
        )


class OnboardingNotFoundError(NotFoundError):
    """Onboarding progress not found for tenant."""

    def __init__(self, tenant_id: UUID) -> None:
        super().__init__(
            resource_type="OnboardingProgress",
            resource_id=str(tenant_id),
            message=f"No onboarding progress found for tenant {tenant_id}",
        )
        self.tenant_id = tenant_id


class OnboardingAlreadyStartedError(OnboardingError):
    """Onboarding already started for tenant."""

    def __init__(self, tenant_id: UUID) -> None:
        super().__init__(
            message=f"Onboarding already started for tenant {tenant_id}",
            code="ONBOARDING_ALREADY_STARTED",
            details={"tenant_id": str(tenant_id)},
            status_code=409,
        )
        self.tenant_id = tenant_id


class InvalidTierError(ValidationError):
    """Invalid subscription tier selected."""

    def __init__(self, tier: str) -> None:
        valid_tiers = ["starter", "professional", "growth"]
        super().__init__(
            message=f"Invalid tier '{tier}'. Valid tiers: {', '.join(valid_tiers)}",
            field="tier",
            details={"tier": tier, "valid_tiers": valid_tiers},
        )
        self.tier = tier


class TierRequiresContactError(OnboardingError):
    """Enterprise tier requires contact (manual setup)."""

    def __init__(self) -> None:
        super().__init__(
            message="Enterprise tier requires contacting sales for manual setup",
            code="TIER_REQUIRES_CONTACT",
            details={"tier": "enterprise", "contact_url": "/contact-sales"},
            status_code=400,
        )


class PaymentNotVerifiedError(OnboardingError):
    """Payment could not be verified."""

    def __init__(self, session_id: str) -> None:
        super().__init__(
            message="Payment session could not be verified",
            code="PAYMENT_NOT_VERIFIED",
            details={"session_id": session_id},
            status_code=400,
        )
        self.session_id = session_id


class XeroConnectionError(OnboardingError):
    """Error connecting to Xero."""

    def __init__(self, message: str, original_error: str | None = None) -> None:
        details: dict[str, Any] = {"service": "xero"}
        if original_error:
            details["original_error"] = original_error

        super().__init__(
            message=message,
            code="XERO_CONNECTION_ERROR",
            details=details,
            status_code=502,
        )
        self.original_error = original_error


class ImportJobNotFoundError(NotFoundError):
    """Import job not found."""

    def __init__(self, job_id: UUID) -> None:
        super().__init__(
            resource_type="BulkImportJob",
            resource_id=str(job_id),
            message=f"Import job {job_id} not found",
        )
        self.job_id = job_id


class ImportLimitExceededError(OnboardingError):
    """Import would exceed tier client limit."""

    def __init__(
        self,
        requested_count: int,
        current_count: int,
        tier_limit: int,
        tier: str,
    ) -> None:
        remaining = max(0, tier_limit - current_count)
        super().__init__(
            message=f"Cannot import {requested_count} clients. Tier limit is {tier_limit}, "
            f"currently at {current_count}. {remaining} slots remaining.",
            code="IMPORT_LIMIT_EXCEEDED",
            details={
                "requested_count": requested_count,
                "current_count": current_count,
                "tier_limit": tier_limit,
                "remaining_slots": remaining,
                "tier": tier,
            },
            status_code=400,
        )
        self.requested_count = requested_count
        self.current_count = current_count
        self.tier_limit = tier_limit


class NoFailedImportsError(OnboardingError):
    """No failed imports to retry."""

    def __init__(self, job_id: UUID) -> None:
        super().__init__(
            message=f"No failed imports to retry for job {job_id}",
            code="NO_FAILED_IMPORTS",
            details={"job_id": str(job_id)},
            status_code=400,
        )
        self.job_id = job_id


class InvalidOnboardingStateError(OnboardingError):
    """Invalid onboarding state transition."""

    def __init__(
        self,
        current_status: str,
        attempted_action: str,
        required_status: str | None = None,
    ) -> None:
        message = f"Cannot {attempted_action} when onboarding status is {current_status}"
        if required_status:
            message += f". Required status: {required_status}"

        super().__init__(
            message=message,
            code="INVALID_ONBOARDING_STATE",
            details={
                "current_status": current_status,
                "attempted_action": attempted_action,
                "required_status": required_status,
            },
            status_code=409,
        )
        self.current_status = current_status
        self.attempted_action = attempted_action
