"""Billing module domain exceptions.

These exceptions extend DomainError and are automatically handled
by the global exception handler to return appropriate HTTP responses.
"""

from typing import TYPE_CHECKING, Any

from app.core.exceptions import DomainError

if TYPE_CHECKING:
    from app.modules.billing.schemas import SubscriptionTierType


class BillingError(DomainError):
    """Base exception for billing module errors."""

    def __init__(
        self,
        message: str,
        code: str = "BILLING_ERROR",
        details: dict[str, Any] | None = None,
        status_code: int = 400,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            details=details or {},
            status_code=status_code,
        )


class SubscriptionError(BillingError):
    """Error related to subscription operations."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message=message,
            code="SUBSCRIPTION_ERROR",
            status_code=400,
        )


class FeatureNotAvailableError(BillingError):
    """Error raised when a feature is not available in the current tier.

    This returns HTTP 403 with detailed upgrade information.
    """

    def __init__(
        self,
        feature: str,
        required_tier: "SubscriptionTierType",
        current_tier: "SubscriptionTierType",
    ) -> None:
        self.feature = feature
        self.required_tier = required_tier
        self.current_tier = current_tier

        message = (
            f"Feature '{feature}' requires {required_tier} tier or higher. "
            f"Current tier: {current_tier}"
        )

        super().__init__(
            message=message,
            code="FEATURE_NOT_AVAILABLE",
            details={
                "feature": feature,
                "required_tier": required_tier,
                "current_tier": current_tier,
                "upgrade_url": "/pricing",
            },
            status_code=403,
        )


class ClientLimitExceededError(BillingError):
    """Error raised when client limit is exceeded.

    This returns HTTP 403 with upgrade information.
    """

    def __init__(
        self,
        current_count: int,
        limit: int,
        required_tier: "SubscriptionTierType",
    ) -> None:
        self.current_count = current_count
        self.limit = limit
        self.required_tier = required_tier

        message = (
            f"Client limit exceeded: {current_count}/{limit}. "
            f"Upgrade to {required_tier} for more clients."
        )

        super().__init__(
            message=message,
            code="CLIENT_LIMIT_EXCEEDED",
            details={
                "current_count": current_count,
                "limit": limit,
                "required_tier": required_tier,
                "upgrade_url": "/pricing",
            },
            status_code=403,
        )


class InvalidTierChangeError(BillingError):
    """Error raised when tier change is invalid."""

    def __init__(
        self,
        current_tier: "SubscriptionTierType",
        requested_tier: "SubscriptionTierType",
        reason: str,
    ) -> None:
        self.current_tier = current_tier
        self.requested_tier = requested_tier
        self.reason = reason

        message = f"Cannot change from {current_tier} to {requested_tier}: {reason}"

        super().__init__(
            message=message,
            code="INVALID_TIER_CHANGE",
            details={
                "current_tier": current_tier,
                "requested_tier": requested_tier,
                "reason": reason,
            },
            status_code=400,
        )
