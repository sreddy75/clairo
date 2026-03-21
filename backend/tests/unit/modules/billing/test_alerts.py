"""Unit tests for UsageAlertService.

Tests for usage threshold detection, alert sending, and deduplication.

Spec 020: Usage Tracking & Limits
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.billing.models import UsageAlertType
from app.modules.billing.usage_alerts import UsageAlertService


class MockTenant:
    """Mock Tenant for testing."""

    def __init__(
        self,
        tier: str = "starter",
        client_count: int = 0,
        owner_email: str = "owner@test.com",
        name: str = "Test Practice",
    ):
        self.id = uuid4()
        self.name = name
        self.owner_email = owner_email
        self.client_count = client_count
        self._tier = tier

    @property
    def tier(self):
        """Return mock tier with value attribute."""
        mock = MagicMock()
        mock.value = self._tier
        return mock


class TestGetCurrentBillingPeriod:
    """Tests for get_current_billing_period static method."""

    def test_returns_yyyy_mm_format(self):
        """Should return period in YYYY-MM format."""
        result = UsageAlertService.get_current_billing_period()

        # Should match YYYY-MM pattern
        assert len(result) == 7
        assert result[4] == "-"
        year, month = result.split("-")
        assert year.isdigit()
        assert month.isdigit()
        assert 1 <= int(month) <= 12

    def test_uses_current_date(self):
        """Should use the current date."""
        now = datetime.now()
        expected = now.strftime("%Y-%m")

        result = UsageAlertService.get_current_billing_period()

        assert result == expected


class TestCheckAndSendThresholdAlerts:
    """Tests for check_and_send_threshold_alerts method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.fixture
    def mock_email_service(self):
        """Create a mock email service."""
        service = MagicMock()
        service.send_usage_threshold_alert = AsyncMock()
        service.send_usage_limit_reached = AsyncMock()
        return service

    @pytest.fixture
    def mock_usage_repo(self):
        """Create a mock usage repository."""
        repo = MagicMock()
        repo.check_alert_exists = AsyncMock(return_value=False)
        repo.create_alert = AsyncMock()
        return repo

    @pytest.mark.asyncio
    async def test_no_alerts_for_unlimited_tier(
        self, mock_session, mock_email_service, mock_usage_repo
    ):
        """Enterprise tier should not trigger any alerts."""
        tenant = MockTenant(tier="enterprise", client_count=500)

        with patch.object(UsageAlertService, "__init__", lambda self, s, e=None: None):
            service = UsageAlertService.__new__(UsageAlertService)
            service.session = mock_session
            service.email_service = mock_email_service
            service.usage_repository = mock_usage_repo

            alerts = await service.check_and_send_threshold_alerts(tenant)

        assert alerts == []
        mock_email_service.send_usage_threshold_alert.assert_not_called()
        mock_email_service.send_usage_limit_reached.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_alerts_below_80_percent(
        self, mock_session, mock_email_service, mock_usage_repo
    ):
        """Below 80% usage should not trigger any alerts."""
        tenant = MockTenant(tier="starter", client_count=15)  # 60% of 25

        with patch.object(UsageAlertService, "__init__", lambda self, s, e=None: None):
            service = UsageAlertService.__new__(UsageAlertService)
            service.session = mock_session
            service.email_service = mock_email_service
            service.usage_repository = mock_usage_repo

            alerts = await service.check_and_send_threshold_alerts(tenant)

        assert alerts == []

    @pytest.mark.asyncio
    async def test_80_threshold_alert_sent(self, mock_session, mock_email_service, mock_usage_repo):
        """At 80% should send threshold_80 alert."""
        tenant = MockTenant(tier="starter", client_count=20)  # 80% of 25

        with patch.object(UsageAlertService, "__init__", lambda self, s, e=None: None):
            service = UsageAlertService.__new__(UsageAlertService)
            service.session = mock_session
            service.email_service = mock_email_service
            service.usage_repository = mock_usage_repo

            alerts = await service.check_and_send_threshold_alerts(tenant)

        assert UsageAlertType.THRESHOLD_80 in alerts
        mock_email_service.send_usage_threshold_alert.assert_called_once()
        mock_usage_repo.create_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_90_threshold_alert_sent(self, mock_session, mock_email_service, mock_usage_repo):
        """At 90% should send both threshold_80 and threshold_90 alerts."""
        tenant = MockTenant(tier="professional", client_count=90)  # 90% of 100

        with patch.object(UsageAlertService, "__init__", lambda self, s, e=None: None):
            service = UsageAlertService.__new__(UsageAlertService)
            service.session = mock_session
            service.email_service = mock_email_service
            service.usage_repository = mock_usage_repo

            alerts = await service.check_and_send_threshold_alerts(tenant)

        # Should send both 80% and 90% alerts
        assert UsageAlertType.THRESHOLD_90 in alerts
        assert UsageAlertType.THRESHOLD_80 in alerts

    @pytest.mark.asyncio
    async def test_limit_reached_alert_sent(
        self, mock_session, mock_email_service, mock_usage_repo
    ):
        """At 100% should send limit_reached alert."""
        tenant = MockTenant(tier="starter", client_count=25)  # 100% of 25

        with patch.object(UsageAlertService, "__init__", lambda self, s, e=None: None):
            service = UsageAlertService.__new__(UsageAlertService)
            service.session = mock_session
            service.email_service = mock_email_service
            service.usage_repository = mock_usage_repo

            alerts = await service.check_and_send_threshold_alerts(tenant)

        assert UsageAlertType.LIMIT_REACHED in alerts
        mock_email_service.send_usage_limit_reached.assert_called_once()

    @pytest.mark.asyncio
    async def test_deduplication_prevents_duplicate_alerts(
        self, mock_session, mock_email_service, mock_usage_repo
    ):
        """Should not send alert if already sent this billing period."""
        tenant = MockTenant(tier="starter", client_count=20)  # 80% of 25

        # Alert already exists
        mock_usage_repo.check_alert_exists = AsyncMock(return_value=True)

        with patch.object(UsageAlertService, "__init__", lambda self, s, e=None: None):
            service = UsageAlertService.__new__(UsageAlertService)
            service.session = mock_session
            service.email_service = mock_email_service
            service.usage_repository = mock_usage_repo

            alerts = await service.check_and_send_threshold_alerts(tenant)

        # No alerts should be sent
        assert alerts == []
        mock_email_service.send_usage_threshold_alert.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_email_if_no_owner_email(
        self, mock_session, mock_email_service, mock_usage_repo
    ):
        """Should not send alert if tenant has no owner email."""
        tenant = MockTenant(tier="starter", client_count=20, owner_email=None)

        with patch.object(UsageAlertService, "__init__", lambda self, s, e=None: None):
            service = UsageAlertService.__new__(UsageAlertService)
            service.session = mock_session
            service.email_service = mock_email_service
            service.usage_repository = mock_usage_repo

            alerts = await service.check_and_send_threshold_alerts(tenant)

        assert alerts == []
        mock_email_service.send_usage_threshold_alert.assert_not_called()

    @pytest.mark.asyncio
    async def test_alert_records_created_after_email(
        self, mock_session, mock_email_service, mock_usage_repo
    ):
        """Should create alert record after sending email."""
        tenant = MockTenant(tier="starter", client_count=20)  # 80% of 25

        with patch.object(UsageAlertService, "__init__", lambda self, s, e=None: None):
            service = UsageAlertService.__new__(UsageAlertService)
            service.session = mock_session
            service.email_service = mock_email_service
            service.usage_repository = mock_usage_repo

            await service.check_and_send_threshold_alerts(tenant)

        # Verify alert record created with correct parameters
        mock_usage_repo.create_alert.assert_called()
        call_kwargs = mock_usage_repo.create_alert.call_args.kwargs
        assert call_kwargs["tenant_id"] == tenant.id
        assert call_kwargs["alert_type"] == UsageAlertType.THRESHOLD_80
        assert call_kwargs["threshold_percentage"] == 80
        assert call_kwargs["client_count_at_alert"] == 20
        assert call_kwargs["client_limit_at_alert"] == 25


class TestGetAlertsForTenant:
    """Tests for get_alerts_for_tenant method."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_returns_formatted_alerts(self, mock_session):
        """Should return alerts formatted as dicts."""
        tenant_id = uuid4()

        # Create mock alerts
        mock_alert = MagicMock()
        mock_alert.id = uuid4()
        mock_alert.alert_type.value = "threshold_80"
        mock_alert.billing_period = "2025-01"
        mock_alert.threshold_percentage = 80
        mock_alert.client_count_at_alert = 20
        mock_alert.client_limit_at_alert = 25
        mock_alert.sent_at = datetime.now()

        mock_usage_repo = MagicMock()
        mock_usage_repo.get_usage_alerts_for_tenant = AsyncMock(return_value=([mock_alert], 1))

        with patch.object(UsageAlertService, "__init__", lambda self, s, e=None: None):
            service = UsageAlertService.__new__(UsageAlertService)
            service.session = mock_session
            service.usage_repository = mock_usage_repo

            alerts, total = await service.get_alerts_for_tenant(tenant_id)

        assert total == 1
        assert len(alerts) == 1
        assert alerts[0]["alert_type"] == "threshold_80"
        assert alerts[0]["threshold_percentage"] == 80

    @pytest.mark.asyncio
    async def test_respects_pagination(self, mock_session):
        """Should pass pagination parameters to repository."""
        tenant_id = uuid4()

        mock_usage_repo = MagicMock()
        mock_usage_repo.get_usage_alerts_for_tenant = AsyncMock(return_value=([], 0))

        with patch.object(UsageAlertService, "__init__", lambda self, s, e=None: None):
            service = UsageAlertService.__new__(UsageAlertService)
            service.session = mock_session
            service.usage_repository = mock_usage_repo

            await service.get_alerts_for_tenant(tenant_id, limit=10, offset=5)

        mock_usage_repo.get_usage_alerts_for_tenant.assert_called_once_with(
            tenant_id=tenant_id,
            limit=10,
            offset=5,
        )
