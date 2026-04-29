"""Unit tests for TaxCodeService cross-check retry logic (Spec 063 T035)."""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
class TestXeroBASCrossCheckRetry:
    """Test retry wrapper in get_xero_bas_crosscheck (Spec 063 T035)."""

    def _make_service(self):
        from app.modules.bas.tax_code_service import TaxCodeService

        session = AsyncMock()
        return TaxCodeService(session)

    def _make_bas_session(self, with_calculation: bool = True):
        calc = MagicMock()
        calc.field_1a_gst_on_sales = Decimal("1000")
        calc.field_1b_gst_on_purchases = Decimal("500")
        calc.gst_payable = Decimal("500")
        calc.g1_total_sales = Decimal("11000")
        calc.g10_capital_purchases = Decimal("0")
        calc.g11_non_capital_purchases = Decimal("5000")

        session = MagicMock()
        session.period = MagicMock()
        session.period.display_name = "Q3 FY26"
        session.calculation = calc if with_calculation else None
        return session

    async def test_retries_on_transient_error_and_succeeds(self):
        """A transient (non-429) error on the first attempt triggers a retry;
        success on the second attempt returns the normal result."""
        service = self._make_service()
        bas_session = self._make_bas_session()

        good_data = {
            "Reports": [
                {
                    "Rows": [
                        {"RowType": "Row", "Cells": [{"Value": "1A"}, {"Value": "1000"}]},
                        {"RowType": "Row", "Cells": [{"Value": "1B"}, {"Value": "500"}]},
                    ]
                }
            ]
        }

        call_count = 0

        async def flaky_get_bas_report(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Transient server error")
            return good_data, {}

        with (
            patch.object(service.repo, "get_session", return_value=bas_session),
            patch("app.core.cache.cache_get", return_value=None),
            patch("app.core.cache.cache_set"),
            patch(
                "app.modules.integrations.xero.repository.XeroConnectionRepository.get_by_id",
                new_callable=AsyncMock,
            ) as mock_get_conn,
            patch(
                "app.modules.integrations.xero.service.XeroConnectionService.ensure_valid_token",
                new_callable=AsyncMock,
                return_value="tok",
            ),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_conn = MagicMock()
            mock_conn.access_token = "tok"
            mock_conn.xero_tenant_id = "tenant-123"
            mock_get_conn.return_value = mock_conn

            with patch("app.modules.integrations.xero.client.XeroClient") as MockClient:
                mock_client_instance = AsyncMock()
                mock_client_instance.get_bas_report = AsyncMock(side_effect=flaky_get_bas_report)
                MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
                MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

                result = await service.get_xero_bas_crosscheck(
                    session_id=uuid.uuid4(),
                    connection_id=uuid.uuid4(),
                    tenant_id=uuid.uuid4(),
                )

        assert result.get("xero_error") is None
        assert result["xero_report_found"] is True

    async def test_returns_xero_error_after_3_consecutive_failures(self):
        """After 3 consecutive failures the method returns a dict with
        xero_error set — it must NOT raise."""
        service = self._make_service()
        bas_session = self._make_bas_session()

        with (
            patch.object(service.repo, "get_session", return_value=bas_session),
            patch("app.core.cache.cache_get", return_value=None),
            patch("app.core.cache.cache_set"),
            patch(
                "app.modules.integrations.xero.repository.XeroConnectionRepository.get_by_id",
                new_callable=AsyncMock,
            ) as mock_get_conn,
            patch(
                "app.modules.integrations.xero.service.XeroConnectionService.ensure_valid_token",
                new_callable=AsyncMock,
                return_value="tok",
            ),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_conn = MagicMock()
            mock_conn.access_token = "tok"
            mock_conn.xero_tenant_id = "tenant-123"
            mock_get_conn.return_value = mock_conn

            with patch("app.modules.integrations.xero.client.XeroClient") as MockClient:
                mock_client_instance = AsyncMock()
                mock_client_instance.get_bas_report = AsyncMock(
                    side_effect=RuntimeError("Always fails")
                )
                MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
                MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

                result = await service.get_xero_bas_crosscheck(
                    session_id=uuid.uuid4(),
                    connection_id=uuid.uuid4(),
                    tenant_id=uuid.uuid4(),
                )

        assert "xero_error" in result
        assert result["xero_error"] is not None
        assert result["xero_report_found"] is None

    async def test_rate_limit_error_is_reraised_without_retry(self):
        """A XeroRateLimitError must be re-raised immediately — no retry attempts."""
        from app.modules.integrations.xero.client import XeroRateLimitError

        service = self._make_service()
        bas_session = self._make_bas_session()

        call_count = 0

        async def rate_limited(**kwargs):
            nonlocal call_count
            call_count += 1
            raise XeroRateLimitError("Rate limited", retry_after=60)

        with (
            patch.object(service.repo, "get_session", return_value=bas_session),
            patch("app.core.cache.cache_get", return_value=None),
            patch("app.core.cache.cache_set"),
            patch(
                "app.modules.integrations.xero.repository.XeroConnectionRepository.get_by_id",
                new_callable=AsyncMock,
            ) as mock_get_conn,
            patch(
                "app.modules.integrations.xero.service.XeroConnectionService.ensure_valid_token",
                new_callable=AsyncMock,
                return_value="tok",
            ),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_conn = MagicMock()
            mock_conn.access_token = "tok"
            mock_conn.xero_tenant_id = "tenant-123"
            mock_get_conn.return_value = mock_conn

            with patch("app.modules.integrations.xero.client.XeroClient") as MockClient:
                mock_client_instance = AsyncMock()
                mock_client_instance.get_bas_report = AsyncMock(side_effect=rate_limited)
                MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
                MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

                with pytest.raises(XeroRateLimitError):
                    await service.get_xero_bas_crosscheck(
                        session_id=uuid.uuid4(),
                        connection_id=uuid.uuid4(),
                        tenant_id=uuid.uuid4(),
                    )

        # Must have only tried once — no retries for rate-limit errors
        assert call_count == 1
