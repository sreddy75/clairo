"""Feature flags and tier configuration.

Defines the feature-to-tier mapping for subscription-based feature gating.
This is a static configuration loaded at startup.

Includes FastAPI dependency decorators for gating:
- require_feature(feature_name): Require a specific feature
- require_tier(minimum_tier): Require a minimum subscription tier
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal, TypedDict

from fastapi import Depends

if TYPE_CHECKING:
    from app.modules.auth.models import Tenant

# =============================================================================
# Type Definitions
# =============================================================================

SubscriptionTierType = Literal["starter", "professional", "growth", "enterprise"]
FeatureName = Literal[
    "ai_insights",
    "client_portal",
    "custom_triggers",
    "api_access",
    "knowledge_base",
    "magic_zone",
]


class TierFeatures(TypedDict):
    """Features available for a subscription tier."""

    max_clients: int | None  # None = unlimited
    ai_insights: Literal["basic", "full"]
    client_portal: bool
    custom_triggers: bool
    api_access: bool
    knowledge_base: bool
    magic_zone: bool


# =============================================================================
# Tier Configuration
# =============================================================================

TIER_FEATURES: dict[SubscriptionTierType, TierFeatures] = {
    "starter": {
        "max_clients": None,  # Unlimited — single $299 plan
        "ai_insights": "full",
        "client_portal": True,
        "custom_triggers": True,
        "api_access": False,
        "knowledge_base": True,
        "magic_zone": True,
    },
    "professional": {
        "max_clients": 100,
        "ai_insights": "full",
        "client_portal": True,
        "custom_triggers": True,
        "api_access": False,
        "knowledge_base": True,
        "magic_zone": True,
    },
    "growth": {
        "max_clients": 250,
        "ai_insights": "full",
        "client_portal": True,
        "custom_triggers": True,
        "api_access": True,
        "knowledge_base": True,
        "magic_zone": True,
    },
    "enterprise": {
        "max_clients": None,  # Unlimited
        "ai_insights": "full",
        "client_portal": True,
        "custom_triggers": True,
        "api_access": True,
        "knowledge_base": True,
        "magic_zone": True,
    },
}

# Tier order for comparison (lowest to highest)
TIER_ORDER: list[SubscriptionTierType] = [
    "starter",
    "professional",
    "growth",
    "enterprise",
]

# Pricing in AUD cents
TIER_PRICING: dict[SubscriptionTierType, int | None] = {
    "starter": 29900,  # $299
    "professional": 29900,  # $299
    "growth": 59900,  # $599
    "enterprise": None,  # Custom
}

# Feature to minimum tier mapping
FEATURE_MINIMUM_TIER: dict[FeatureName, SubscriptionTierType] = {
    "ai_insights": "starter",  # All tiers have some AI
    "client_portal": "professional",
    "custom_triggers": "professional",
    "api_access": "growth",
    "knowledge_base": "professional",
    "magic_zone": "professional",
}


# =============================================================================
# Helper Functions
# =============================================================================


def get_tier_features(tier: str) -> TierFeatures:
    """Get feature configuration for a tier.

    Args:
        tier: The subscription tier name.

    Returns:
        The TierFeatures configuration for the tier.

    Raises:
        KeyError: If the tier is not valid.
    """
    if tier not in TIER_FEATURES:
        raise KeyError(f"Invalid tier: {tier}")
    return TIER_FEATURES[tier]  # type: ignore[return-value]


def has_feature(tier: str, feature: str) -> bool:
    """Check if a tier has access to a feature.

    Args:
        tier: The subscription tier name.
        feature: The feature name to check.

    Returns:
        True if the tier has access to the feature, False otherwise.
    """
    if tier not in TIER_FEATURES:
        return False

    features = TIER_FEATURES[tier]  # type: ignore[literal-required]

    # Special case for ai_insights (level-based)
    if feature == "ai_insights":
        return True  # All tiers have some AI

    # Boolean features
    if feature in features:
        value = features.get(feature)  # type: ignore[literal-required]
        if isinstance(value, bool):
            return value

    return False


def get_minimum_tier(feature: str) -> SubscriptionTierType:
    """Get the minimum tier required for a feature.

    Args:
        feature: The feature name.

    Returns:
        The minimum tier name that has access to the feature.
    """
    return FEATURE_MINIMUM_TIER.get(feature, "professional")  # type: ignore[return-value]


def get_client_limit(tier: str) -> int | None:
    """Get the client limit for a tier.

    Args:
        tier: The subscription tier name.

    Returns:
        The client limit, or None for unlimited.
    """
    if tier not in TIER_FEATURES:
        return 0
    return TIER_FEATURES[tier]["max_clients"]  # type: ignore[literal-required]


def get_next_tier(tier: str) -> SubscriptionTierType:
    """Get the next higher tier.

    Args:
        tier: The current tier name.

    Returns:
        The next tier name, or 'enterprise' if already at highest.
    """
    try:
        current_index = TIER_ORDER.index(tier)  # type: ignore[arg-type]
        if current_index < len(TIER_ORDER) - 1:
            return TIER_ORDER[current_index + 1]
    except ValueError:
        pass
    return "enterprise"


def compare_tiers(tier_a: str, tier_b: str) -> int:
    """Compare two tiers.

    Args:
        tier_a: First tier name.
        tier_b: Second tier name.

    Returns:
        -1 if tier_a < tier_b, 0 if equal, 1 if tier_a > tier_b.
    """
    try:
        index_a = TIER_ORDER.index(tier_a)  # type: ignore[arg-type]
        index_b = TIER_ORDER.index(tier_b)  # type: ignore[arg-type]
        if index_a < index_b:
            return -1
        elif index_a > index_b:
            return 1
        return 0
    except ValueError:
        return 0


def is_upgrade(current_tier: str, new_tier: str) -> bool:
    """Check if changing to new_tier is an upgrade.

    Args:
        current_tier: Current tier name.
        new_tier: New tier name.

    Returns:
        True if new_tier is higher than current_tier.
    """
    return compare_tiers(new_tier, current_tier) > 0


def is_downgrade(current_tier: str, new_tier: str) -> bool:
    """Check if changing to new_tier is a downgrade.

    Args:
        current_tier: Current tier name.
        new_tier: New tier name.

    Returns:
        True if new_tier is lower than current_tier.
    """
    return compare_tiers(new_tier, current_tier) < 0


# =============================================================================
# FastAPI Dependencies for Feature Gating
# =============================================================================


def require_feature(feature_name: FeatureName) -> Callable[..., Any]:
    """FastAPI dependency that requires a specific feature.

    Usage:
        @router.get("/endpoint")
        async def endpoint(
            tenant: Tenant = Depends(get_current_tenant),
            _: None = Depends(require_feature("custom_triggers")),
        ):
            ...

    Args:
        feature_name: The feature that must be available.

    Returns:
        A dependency function that raises FeatureNotAvailableError if blocked.
    """
    from app.modules.auth.dependencies import get_current_tenant
    from app.modules.billing.exceptions import FeatureNotAvailableError

    async def dependency(
        tenant: "Tenant" = Depends(get_current_tenant),
    ) -> None:
        tier: SubscriptionTierType = tenant.tier.value  # type: ignore[assignment]

        if not has_feature(tier, feature_name):
            required_tier = get_minimum_tier(feature_name)
            raise FeatureNotAvailableError(
                feature=feature_name,
                required_tier=required_tier,
                current_tier=tier,
            )

    return dependency


def require_tier(minimum_tier: SubscriptionTierType) -> Callable[..., Any]:
    """FastAPI dependency that requires a minimum subscription tier.

    Usage:
        @router.get("/endpoint")
        async def endpoint(
            tenant: Tenant = Depends(get_current_tenant),
            _: None = Depends(require_tier("professional")),
        ):
            ...

    Args:
        minimum_tier: The minimum tier required.

    Returns:
        A dependency function that raises FeatureNotAvailableError if blocked.
    """
    from app.modules.auth.dependencies import get_current_tenant
    from app.modules.billing.exceptions import FeatureNotAvailableError

    async def dependency(
        tenant: "Tenant" = Depends(get_current_tenant),
    ) -> None:
        tier: SubscriptionTierType = tenant.tier.value  # type: ignore[assignment]

        # Compare tiers
        if compare_tiers(tier, minimum_tier) < 0:
            raise FeatureNotAvailableError(
                feature=f"tier:{minimum_tier}",
                required_tier=minimum_tier,
                current_tier=tier,
            )

    return dependency


class FeatureGate:
    """Class-based feature gating for more complex scenarios.

    Can be used as a dependency or called directly in route handlers.

    Usage:
        gate = FeatureGate("custom_triggers")
        await gate.check(tenant)
    """

    def __init__(self, feature_name: FeatureName) -> None:
        self.feature_name = feature_name

    def check(self, tenant: "Tenant") -> bool:
        """Check if tenant has access to the feature.

        Args:
            tenant: The tenant to check.

        Returns:
            True if allowed.

        Raises:
            FeatureNotAvailableError: If feature not available.
        """
        from app.modules.billing.exceptions import FeatureNotAvailableError

        tier: SubscriptionTierType = tenant.tier.value  # type: ignore[assignment]

        if not has_feature(tier, self.feature_name):
            required_tier = get_minimum_tier(self.feature_name)
            raise FeatureNotAvailableError(
                feature=self.feature_name,
                required_tier=required_tier,
                current_tier=tier,
            )
        return True

    def is_available(self, tenant: "Tenant") -> bool:
        """Check if feature is available without raising.

        Args:
            tenant: The tenant to check.

        Returns:
            True if feature is available, False otherwise.
        """
        tier: SubscriptionTierType = tenant.tier.value  # type: ignore[assignment]
        return has_feature(tier, self.feature_name)
