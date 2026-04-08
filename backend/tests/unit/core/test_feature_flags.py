"""Unit tests for feature flags module.

Tests for tier-based feature access and subscription tier utilities.
"""

import pytest

from app.core.feature_flags import (
    TIER_FEATURES,
    TIER_ORDER,
    TIER_PRICING,
    compare_tiers,
    get_client_limit,
    get_minimum_tier,
    get_next_tier,
    get_tier_features,
    has_feature,
    is_downgrade,
    is_upgrade,
)


class TestTierFeatures:
    """Tests for TIER_FEATURES configuration."""

    def test_all_tiers_defined(self):
        """All expected tiers should be defined."""
        expected_tiers = {"starter", "professional", "growth", "enterprise"}
        assert set(TIER_FEATURES.keys()) == expected_tiers

    def test_starter_tier_limits(self):
        """Starter tier is an all-inclusive $299 plan with unlimited clients."""
        features = TIER_FEATURES["starter"]
        assert features["max_clients"] is None
        assert features["ai_insights"] == "full"
        assert features["client_portal"] is True
        assert features["custom_triggers"] is True
        assert features["api_access"] is False
        assert features["knowledge_base"] is True
        assert features["magic_zone"] is True

    def test_professional_tier_features(self):
        """Professional tier should have extended features."""
        features = TIER_FEATURES["professional"]
        assert features["max_clients"] == 100
        assert features["ai_insights"] == "full"
        assert features["client_portal"] is True
        assert features["custom_triggers"] is True
        assert features["api_access"] is False
        assert features["knowledge_base"] is True
        assert features["magic_zone"] is True

    def test_growth_tier_features(self):
        """Growth tier should have API access."""
        features = TIER_FEATURES["growth"]
        assert features["max_clients"] == 250
        assert features["api_access"] is True

    def test_enterprise_tier_unlimited(self):
        """Enterprise tier should have unlimited clients."""
        features = TIER_FEATURES["enterprise"]
        assert features["max_clients"] is None
        assert features["api_access"] is True


class TestGetTierFeatures:
    """Tests for get_tier_features function."""

    def test_valid_tier(self):
        """Should return features for valid tier."""
        features = get_tier_features("starter")
        assert features["max_clients"] is None

    def test_invalid_tier_raises(self):
        """Should raise KeyError for invalid tier."""
        with pytest.raises(KeyError) as exc_info:
            get_tier_features("invalid_tier")
        assert "Invalid tier" in str(exc_info.value)


class TestHasFeature:
    """Tests for has_feature function."""

    def test_starter_has_basic_ai(self):
        """Starter tier should have AI insights (basic level)."""
        assert has_feature("starter", "ai_insights") is True

    def test_starter_has_client_portal(self):
        """Starter tier has client portal (all-inclusive plan)."""
        assert has_feature("starter", "client_portal") is True

    def test_starter_has_custom_triggers(self):
        """Starter tier has custom triggers (all-inclusive plan)."""
        assert has_feature("starter", "custom_triggers") is True

    def test_professional_has_client_portal(self):
        """Professional tier should have client portal."""
        assert has_feature("professional", "client_portal") is True

    def test_professional_has_custom_triggers(self):
        """Professional tier should have custom triggers."""
        assert has_feature("professional", "custom_triggers") is True

    def test_professional_no_api_access(self):
        """Professional tier should not have API access."""
        assert has_feature("professional", "api_access") is False

    def test_growth_has_api_access(self):
        """Growth tier should have API access."""
        assert has_feature("growth", "api_access") is True

    def test_invalid_tier_returns_false(self):
        """Invalid tier should return False."""
        assert has_feature("invalid_tier", "client_portal") is False


class TestGetMinimumTier:
    """Tests for get_minimum_tier function."""

    def test_ai_insights_minimum(self):
        """AI insights should be available from starter."""
        assert get_minimum_tier("ai_insights") == "starter"

    def test_client_portal_minimum(self):
        """Client portal should require professional."""
        assert get_minimum_tier("client_portal") == "professional"

    def test_custom_triggers_minimum(self):
        """Custom triggers should require professional."""
        assert get_minimum_tier("custom_triggers") == "professional"

    def test_api_access_minimum(self):
        """API access should require growth."""
        assert get_minimum_tier("api_access") == "growth"

    def test_unknown_feature_defaults_professional(self):
        """Unknown feature should default to professional."""
        assert get_minimum_tier("unknown_feature") == "professional"


class TestGetClientLimit:
    """Tests for get_client_limit function."""

    def test_starter_limit(self):
        """Starter tier has unlimited clients (None)."""
        assert get_client_limit("starter") is None

    def test_professional_limit(self):
        """Professional tier should have 100 client limit."""
        assert get_client_limit("professional") == 100

    def test_growth_limit(self):
        """Growth tier should have 250 client limit."""
        assert get_client_limit("growth") == 250

    def test_enterprise_unlimited(self):
        """Enterprise tier should have no limit (None)."""
        assert get_client_limit("enterprise") is None

    def test_invalid_tier_returns_zero(self):
        """Invalid tier should return 0."""
        assert get_client_limit("invalid_tier") == 0


class TestGetNextTier:
    """Tests for get_next_tier function."""

    def test_starter_next_is_professional(self):
        """Next tier after starter should be professional."""
        assert get_next_tier("starter") == "professional"

    def test_professional_next_is_growth(self):
        """Next tier after professional should be growth."""
        assert get_next_tier("professional") == "growth"

    def test_growth_next_is_enterprise(self):
        """Next tier after growth should be enterprise."""
        assert get_next_tier("growth") == "enterprise"

    def test_enterprise_stays_enterprise(self):
        """Enterprise is highest, should return enterprise."""
        assert get_next_tier("enterprise") == "enterprise"

    def test_invalid_tier_returns_enterprise(self):
        """Invalid tier should return enterprise."""
        assert get_next_tier("invalid") == "enterprise"


class TestCompareTiers:
    """Tests for compare_tiers function."""

    def test_starter_less_than_professional(self):
        """Starter should be less than professional."""
        assert compare_tiers("starter", "professional") < 0

    def test_professional_greater_than_starter(self):
        """Professional should be greater than starter."""
        assert compare_tiers("professional", "starter") > 0

    def test_same_tier_equal(self):
        """Same tier should return 0."""
        assert compare_tiers("professional", "professional") == 0

    def test_enterprise_greater_than_all(self):
        """Enterprise should be greater than all other tiers."""
        assert compare_tiers("enterprise", "starter") > 0
        assert compare_tiers("enterprise", "professional") > 0
        assert compare_tiers("enterprise", "growth") > 0


class TestIsUpgrade:
    """Tests for is_upgrade function."""

    def test_starter_to_professional_is_upgrade(self):
        """Starter to professional should be upgrade."""
        assert is_upgrade("starter", "professional") is True

    def test_professional_to_starter_not_upgrade(self):
        """Professional to starter should not be upgrade."""
        assert is_upgrade("professional", "starter") is False

    def test_same_tier_not_upgrade(self):
        """Same tier should not be upgrade."""
        assert is_upgrade("professional", "professional") is False


class TestIsDowngrade:
    """Tests for is_downgrade function."""

    def test_professional_to_starter_is_downgrade(self):
        """Professional to starter should be downgrade."""
        assert is_downgrade("professional", "starter") is True

    def test_starter_to_professional_not_downgrade(self):
        """Starter to professional should not be downgrade."""
        assert is_downgrade("starter", "professional") is False

    def test_same_tier_not_downgrade(self):
        """Same tier should not be downgrade."""
        assert is_downgrade("professional", "professional") is False


class TestTierOrder:
    """Tests for TIER_ORDER configuration."""

    def test_tier_order_correct(self):
        """Tier order should be from lowest to highest."""
        assert TIER_ORDER == ["starter", "professional", "growth", "enterprise"]


class TestTierPricing:
    """Tests for TIER_PRICING configuration."""

    def test_starter_pricing(self):
        """Starter should be $299 (29900 cents)."""
        assert TIER_PRICING["starter"] == 29900

    def test_professional_pricing(self):
        """Professional should be $299 (29900 cents)."""
        assert TIER_PRICING["professional"] == 29900

    def test_growth_pricing(self):
        """Growth should be $599 (59900 cents)."""
        assert TIER_PRICING["growth"] == 59900

    def test_enterprise_custom_pricing(self):
        """Enterprise should have custom pricing (None)."""
        assert TIER_PRICING["enterprise"] is None
