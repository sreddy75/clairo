"""Admin module domain exceptions.

Domain exceptions for admin operations. These are raised by the service layer
and converted to HTTPExceptions in the router layer.

Spec 022: Admin Dashboard (Internal)
"""

from uuid import UUID


class AdminError(Exception):
    """Base exception for admin module errors."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class TenantNotFoundError(AdminError):
    """Raised when a tenant cannot be found."""

    def __init__(self, tenant_id: UUID) -> None:
        self.tenant_id = tenant_id
        super().__init__(f"Tenant not found: {tenant_id}")


class TierChangeError(AdminError):
    """Raised when a tier change operation fails."""

    def __init__(
        self,
        message: str,
        *,
        tenant_id: UUID | None = None,
        old_tier: str | None = None,
        new_tier: str | None = None,
        reason: str | None = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.old_tier = old_tier
        self.new_tier = new_tier
        self.reason = reason
        super().__init__(message)


class TierDowngradeBlockedError(TierChangeError):
    """Raised when downgrade is blocked due to excess clients."""

    def __init__(
        self,
        *,
        tenant_id: UUID,
        current_tier: str,
        new_tier: str,
        current_clients: int,
        new_limit: int,
    ) -> None:
        self.current_clients = current_clients
        self.new_limit = new_limit
        super().__init__(
            f"Cannot downgrade: tenant has {current_clients} clients but {new_tier} tier only allows {new_limit}",
            tenant_id=tenant_id,
            old_tier=current_tier,
            new_tier=new_tier,
            reason="excess_clients",
        )


class SelfModificationBlockedError(AdminError):
    """Raised when admin tries to modify their own tenant."""

    def __init__(self, admin_id: UUID, tenant_id: UUID) -> None:
        self.admin_id = admin_id
        self.tenant_id = tenant_id
        super().__init__("Administrators cannot modify their own tenant")


class CreditApplicationError(AdminError):
    """Raised when credit application fails."""

    def __init__(
        self,
        message: str,
        *,
        tenant_id: UUID | None = None,
        amount_cents: int | None = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.amount_cents = amount_cents
        super().__init__(message)


class FeatureFlagOverrideError(AdminError):
    """Raised when feature flag override operation fails."""

    def __init__(
        self,
        message: str,
        *,
        tenant_id: UUID | None = None,
        feature_key: str | None = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.feature_key = feature_key
        super().__init__(message)


class InvalidFeatureKeyError(FeatureFlagOverrideError):
    """Raised when an invalid feature key is provided."""

    VALID_KEYS = frozenset(
        [
            "ai_insights",
            "client_portal",
            "custom_triggers",
            "api_access",
            "knowledge_base",
            "magic_zone",
        ]
    )

    def __init__(self, feature_key: str, tenant_id: UUID | None = None) -> None:
        super().__init__(
            f"Invalid feature key: {feature_key}. Valid keys: {', '.join(sorted(self.VALID_KEYS))}",
            tenant_id=tenant_id,
            feature_key=feature_key,
        )


class StripeOperationError(AdminError):
    """Raised when a Stripe operation fails."""

    def __init__(
        self,
        message: str,
        *,
        operation: str,
        stripe_error: str | None = None,
    ) -> None:
        self.operation = operation
        self.stripe_error = stripe_error
        super().__init__(f"Stripe {operation} failed: {message}")


class RevenueCalculationError(AdminError):
    """Raised when revenue metrics calculation fails."""

    def __init__(self, message: str) -> None:
        super().__init__(f"Revenue calculation failed: {message}")
