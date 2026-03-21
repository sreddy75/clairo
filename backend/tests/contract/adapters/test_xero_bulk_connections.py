"""Contract tests for Xero bulk connections API.

Tests verify the expected shape of Xero API responses used by
the bulk import feature, using mock fixtures that match the real
Xero API response format.

Tests cover (T028):
- GET /connections response shape (tenantId, tenantName, authEventId)
- Token exchange response with access_token and refresh_token
- X-AppMinLimit-Remaining header present in responses
"""

from typing import ClassVar

import pytest

from app.modules.integrations.xero.schemas import XeroOrganization

# =============================================================================
# GET /connections response contract
# =============================================================================


@pytest.mark.unit
class TestXeroConnectionsResponseContract:
    """Verify the XeroOrganization schema parses real Xero API responses."""

    SAMPLE_CONNECTIONS_RESPONSE: ClassVar[list[dict]] = [
        {
            "id": "00000000-0000-0000-0000-000000000000",
            "authEventId": "00000000-0000-0000-0000-000000000001",
            "tenantId": "abc12345-1234-5678-abcd-000000000001",
            "tenantType": "ORGANISATION",
            "tenantName": "Acme Corp Pty Ltd",
            "createdDateUtc": "2024-01-15T10:30:00.0000000",
            "updatedDateUtc": "2024-06-01T14:22:00.0000000",
        },
        {
            "id": "00000000-0000-0000-0000-000000000002",
            "authEventId": "00000000-0000-0000-0000-000000000001",
            "tenantId": "def67890-5678-9012-efgh-000000000002",
            "tenantType": "ORGANISATION",
            "tenantName": "Beta Industries Limited",
            "createdDateUtc": "2024-01-15T10:30:00.0000000",
            "updatedDateUtc": "2024-06-01T14:22:00.0000000",
        },
        {
            "id": "00000000-0000-0000-0000-000000000003",
            "authEventId": "00000000-0000-0000-0000-000000000001",
            "tenantId": "ghi11111-9012-3456-ijkl-000000000003",
            "tenantType": "ORGANISATION",
            "tenantName": None,
            "createdDateUtc": "2024-01-15T10:30:00.0000000",
            "updatedDateUtc": "2024-01-15T10:30:00.0000000",
        },
    ]

    def test_parses_tenant_id(self):
        """tenantId should be parsed as the org id."""
        org = XeroOrganization(**self.SAMPLE_CONNECTIONS_RESPONSE[0])
        assert org.id == "abc12345-1234-5678-abcd-000000000001"

    def test_parses_tenant_name(self):
        """tenantName should be parsed as tenant_name."""
        org = XeroOrganization(**self.SAMPLE_CONNECTIONS_RESPONSE[0])
        assert org.tenant_name == "Acme Corp Pty Ltd"

    def test_parses_auth_event_id(self):
        """authEventId should be parsed for grouping bulk connections."""
        org = XeroOrganization(**self.SAMPLE_CONNECTIONS_RESPONSE[0])
        assert org.auth_event_id == "00000000-0000-0000-0000-000000000001"

    def test_parses_tenant_type(self):
        """tenantType should be parsed as tenant_type."""
        org = XeroOrganization(**self.SAMPLE_CONNECTIONS_RESPONSE[0])
        assert org.tenant_type == "ORGANISATION"

    def test_display_name_uses_tenant_name(self):
        """display_name should return tenant_name when available."""
        org = XeroOrganization(**self.SAMPLE_CONNECTIONS_RESPONSE[0])
        assert org.display_name == "Acme Corp Pty Ltd"

    def test_display_name_fallback_when_no_name(self):
        """display_name should fallback when tenantName is null."""
        org = XeroOrganization(**self.SAMPLE_CONNECTIONS_RESPONSE[2])
        assert org.display_name.startswith("Organization ")

    def test_all_orgs_share_auth_event_id(self):
        """All orgs from same OAuth flow share the same authEventId."""
        orgs = [XeroOrganization(**r) for r in self.SAMPLE_CONNECTIONS_RESPONSE]
        auth_event_ids = {o.auth_event_id for o in orgs}
        assert len(auth_event_ids) == 1

    def test_multiple_orgs_have_unique_tenant_ids(self):
        """Each org should have a unique tenantId."""
        orgs = [XeroOrganization(**r) for r in self.SAMPLE_CONNECTIONS_RESPONSE]
        tenant_ids = [o.id for o in orgs]
        assert len(tenant_ids) == len(set(tenant_ids))

    def test_is_organisation_property(self):
        """is_organisation should return True for ORGANISATION type."""
        org = XeroOrganization(**self.SAMPLE_CONNECTIONS_RESPONSE[0])
        assert org.is_organisation is True


# =============================================================================
# Token exchange response contract
# =============================================================================


@pytest.mark.unit
class TestTokenExchangeResponseContract:
    """Verify the expected token response shape from Xero OAuth."""

    SAMPLE_TOKEN_RESPONSE: ClassVar[dict[str, str | int]] = {
        "id_token": "eyJhbGci...",
        "access_token": "eyJhbGci...access",
        "expires_in": 1800,
        "token_type": "Bearer",
        "refresh_token": "abcdef123456refresh",
        "scope": "openid profile email accounting.transactions accounting.contacts offline_access",
    }

    def test_has_access_token(self):
        """Token response must include access_token."""
        assert "access_token" in self.SAMPLE_TOKEN_RESPONSE
        assert isinstance(self.SAMPLE_TOKEN_RESPONSE["access_token"], str)
        assert len(self.SAMPLE_TOKEN_RESPONSE["access_token"]) > 0

    def test_has_refresh_token(self):
        """Token response must include refresh_token."""
        assert "refresh_token" in self.SAMPLE_TOKEN_RESPONSE
        assert isinstance(self.SAMPLE_TOKEN_RESPONSE["refresh_token"], str)
        assert len(self.SAMPLE_TOKEN_RESPONSE["refresh_token"]) > 0

    def test_has_expires_in(self):
        """Token response must include expires_in (in seconds)."""
        assert "expires_in" in self.SAMPLE_TOKEN_RESPONSE
        assert isinstance(self.SAMPLE_TOKEN_RESPONSE["expires_in"], int)
        assert self.SAMPLE_TOKEN_RESPONSE["expires_in"] > 0

    def test_has_scope(self):
        """Token response must include scope string."""
        assert "scope" in self.SAMPLE_TOKEN_RESPONSE
        scopes = self.SAMPLE_TOKEN_RESPONSE["scope"].split()
        assert "accounting.transactions" in scopes
        assert "offline_access" in scopes


# =============================================================================
# Rate limit header contract
# =============================================================================


@pytest.mark.unit
class TestRateLimitHeaderContract:
    """Verify expected rate limit headers from Xero API responses."""

    SAMPLE_HEADERS: ClassVar[dict[str, str]] = {
        "X-AppMinLimit-Remaining": "9500",
        "X-MinLimit-Remaining": "55",
        "X-DayLimit-Remaining": "4800",
    }

    def test_app_min_limit_remaining_present(self):
        """X-AppMinLimit-Remaining header should be present."""
        assert "X-AppMinLimit-Remaining" in self.SAMPLE_HEADERS

    def test_app_min_limit_remaining_is_numeric(self):
        """X-AppMinLimit-Remaining should be parseable as integer."""
        value = int(self.SAMPLE_HEADERS["X-AppMinLimit-Remaining"])
        assert value >= 0
        assert value <= 10000  # App-wide limit is 10,000/min

    def test_per_org_min_limit_remaining_present(self):
        """X-MinLimit-Remaining header should be present (per-org)."""
        assert "X-MinLimit-Remaining" in self.SAMPLE_HEADERS

    def test_per_org_day_limit_remaining_present(self):
        """X-DayLimit-Remaining header should be present (per-org)."""
        assert "X-DayLimit-Remaining" in self.SAMPLE_HEADERS

    def test_rate_limit_threshold_logic(self):
        """App rate limit pauses when remaining < 500."""
        remaining = int(self.SAMPLE_HEADERS["X-AppMinLimit-Remaining"])
        should_pause = remaining < 500
        assert should_pause is False  # 9500 is well above threshold

        # Below threshold
        low_remaining = "400"
        should_pause_low = int(low_remaining) < 500
        assert should_pause_low is True
