"""Unit tests for DashboardService.

Note: These tests cover the current dashboard service implementation.
The dashboard service provides aggregated financial data across all
Xero connections for a tenant.
"""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.dashboard.schemas import BASStatus
from app.modules.dashboard.service import DashboardService


@pytest.fixture
def mock_session():
    """Create mock database session."""
    return AsyncMock()


class TestDashboardServiceGetSummary:
    """Tests for get_summary method."""

    @pytest.mark.asyncio
    async def test_get_summary_returns_complete_response(
        self,
        mock_session,
    ):
        """Should return complete dashboard summary."""
        tenant_id = uuid.uuid4()

        mock_dashboard_repo = AsyncMock()
        mock_dashboard_repo.get_aggregated_summary.return_value = {
            "total_clients": 50,
            "active_clients": 35,
            "total_sales": Decimal("150000.00"),
            "total_purchases": Decimal("80000.00"),
            "gst_collected": Decimal("15000.00"),
            "gst_paid": Decimal("8000.00"),
            "last_sync_at": None,
        }
        mock_dashboard_repo.get_status_counts.return_value = {
            "ready": 25,
            "needs_review": 5,
            "no_activity": 15,
            "missing_data": 5,
        }

        mock_quality_repo = AsyncMock()
        mock_quality_repo.get_quality_summary_for_tenant.return_value = {
            "avg_score": 85.0,
            "total_issues": 10,
            "critical_issues": 2,
        }

        with patch(
            "app.modules.dashboard.service.DashboardRepository",
            return_value=mock_dashboard_repo,
        ):
            with patch(
                "app.modules.dashboard.service.QualityRepository",
                return_value=mock_quality_repo,
            ):
                service = DashboardService(mock_session)

                result = await service.get_summary(
                    tenant_id=tenant_id,
                    quarter=2,
                    fy_year=2025,
                )

                assert result.total_clients == 50
                assert result.active_clients == 35
                assert result.total_sales == Decimal("150000.00")

    @pytest.mark.asyncio
    async def test_get_summary_defaults_to_current_quarter(
        self,
        mock_session,
    ):
        """Should default to current quarter when not specified."""
        tenant_id = uuid.uuid4()

        mock_dashboard_repo = AsyncMock()
        mock_dashboard_repo.get_aggregated_summary.return_value = {
            "total_clients": 10,
            "active_clients": 5,
            "total_sales": Decimal("0"),
            "total_purchases": Decimal("0"),
            "gst_collected": Decimal("0"),
            "gst_paid": Decimal("0"),
            "last_sync_at": None,
        }
        mock_dashboard_repo.get_status_counts.return_value = {
            "ready": 0,
            "needs_review": 0,
            "no_activity": 10,
            "missing_data": 0,
        }

        mock_quality_repo = AsyncMock()
        mock_quality_repo.get_quality_summary_for_tenant.return_value = {
            "avg_score": 0.0,
            "total_issues": 0,
            "critical_issues": 0,
        }

        with patch(
            "app.modules.dashboard.service.DashboardRepository",
            return_value=mock_dashboard_repo,
        ):
            with patch(
                "app.modules.dashboard.service.QualityRepository",
                return_value=mock_quality_repo,
            ):
                service = DashboardService(mock_session)

                result = await service.get_summary(tenant_id=tenant_id)

                # Should have a valid quarter (1-4)
                assert result.quarter in [1, 2, 3, 4]
                assert result.fy_year >= 2024


class TestDashboardServiceGetClientPortfolio:
    """Tests for get_client_portfolio method."""

    @pytest.mark.asyncio
    async def test_get_client_portfolio_returns_paginated_response(
        self,
        mock_session,
    ):
        """Should return paginated client list."""
        tenant_id = uuid.uuid4()

        mock_dashboard_repo = AsyncMock()
        # Mock returns tuple of (clients_list, total_count)
        mock_dashboard_repo.list_connections_with_financials.return_value = ([], 0)

        with patch(
            "app.modules.dashboard.service.DashboardRepository",
            return_value=mock_dashboard_repo,
        ):
            service = DashboardService(mock_session)

            result = await service.get_client_portfolio(
                tenant_id=tenant_id,
                quarter=2,
                fy_year=2025,
                page=1,
                limit=25,
            )

            assert result.total == 0
            assert result.page == 1
            assert result.limit == 25

    @pytest.mark.asyncio
    async def test_get_client_portfolio_passes_filters(
        self,
        mock_session,
    ):
        """Should pass filter parameters to repository."""
        tenant_id = uuid.uuid4()

        mock_dashboard_repo = AsyncMock()
        mock_dashboard_repo.list_connections_with_financials.return_value = ([], 0)

        with patch(
            "app.modules.dashboard.service.DashboardRepository",
            return_value=mock_dashboard_repo,
        ):
            service = DashboardService(mock_session)

            await service.get_client_portfolio(
                tenant_id=tenant_id,
                quarter=2,
                fy_year=2025,
                status="ready",
                search="test",
                sort_by="total_sales",
                sort_order="desc",
                page=2,
                limit=50,
            )

            mock_dashboard_repo.list_connections_with_financials.assert_called_once()


class TestBASStatusCalculation:
    """Tests for BAS status calculation logic."""

    def test_bas_status_enum_values(self):
        """Verify BAS status enum has correct values."""
        assert BASStatus.READY.value == "ready"
        assert BASStatus.NEEDS_REVIEW.value == "needs_review"
        assert BASStatus.NO_ACTIVITY.value == "no_activity"
        assert BASStatus.MISSING_DATA.value == "missing_data"
