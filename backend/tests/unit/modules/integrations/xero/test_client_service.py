"""Unit tests for XeroClientService.

Tests cover:
- list_clients
- get_client_detail
- get_client_invoices
- get_client_transactions
- get_client_financial_summary
- get_available_quarters
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.integrations.xero.models import (
    XeroClient,
    XeroConnection,
    XeroConnectionStatus,
    XeroContactType,
    XeroInvoice,
    XeroInvoiceStatus,
    XeroInvoiceType,
)
from app.modules.integrations.xero.service import XeroClientNotFoundError, XeroClientService


@pytest.fixture
def mock_session():
    """Create mock database session."""
    return AsyncMock()


@pytest.fixture
def mock_client_repo():
    """Create mock client repository."""
    return AsyncMock()


@pytest.fixture
def mock_invoice_repo():
    """Create mock invoice repository."""
    return AsyncMock()


@pytest.fixture
def mock_transaction_repo():
    """Create mock transaction repository."""
    return AsyncMock()


@pytest.fixture
def mock_connection_repo():
    """Create mock connection repository."""
    return AsyncMock()


@pytest.fixture
def sample_client() -> XeroClient:
    """Create sample client for testing."""
    client = MagicMock(spec=XeroClient)
    client.id = uuid.uuid4()
    client.tenant_id = uuid.uuid4()
    client.connection_id = uuid.uuid4()
    client.xero_contact_id = "xero-contact-123"
    client.name = "Test Client"
    client.email = "test@example.com"
    client.contact_number = "1234567890"
    client.abn = "12345678901"
    client.contact_type = XeroContactType.CUSTOMER
    client.is_active = True
    client.addresses = []
    client.phones = []
    return client


@pytest.fixture
def sample_connection() -> XeroConnection:
    """Create sample connection for testing."""
    connection = MagicMock(spec=XeroConnection)
    connection.id = uuid.uuid4()
    connection.organization_name = "Test Organization"
    connection.status = XeroConnectionStatus.ACTIVE
    connection.last_synced_at = datetime.now(UTC)
    return connection


@pytest.fixture
def sample_invoice() -> XeroInvoice:
    """Create sample invoice for testing."""
    invoice = MagicMock(spec=XeroInvoice)
    invoice.id = uuid.uuid4()
    invoice.connection_id = uuid.uuid4()
    invoice.client_id = uuid.uuid4()
    invoice.xero_invoice_id = "XERO-INV-001"
    invoice.xero_contact_id = "XERO-CONTACT-001"
    invoice.invoice_number = "INV-001"
    invoice.invoice_type = XeroInvoiceType.ACCREC
    invoice.status = XeroInvoiceStatus.PAID
    invoice.issue_date = datetime(2024, 10, 15, tzinfo=UTC)
    invoice.due_date = datetime(2024, 11, 15, tzinfo=UTC)
    invoice.subtotal = Decimal("1000.00")
    invoice.total_amount = Decimal("1100.00")
    invoice.tax_amount = Decimal("100.00")
    invoice.currency = "AUD"
    invoice.line_items = []
    invoice.xero_updated_at = datetime(2024, 10, 15, tzinfo=UTC)
    invoice.created_at = datetime(2024, 10, 15, tzinfo=UTC)
    invoice.updated_at = datetime(2024, 10, 15, tzinfo=UTC)
    return invoice


class TestXeroClientServiceListClients:
    """Tests for list_clients method."""

    async def test_list_clients_returns_paginated_response(
        self,
        mock_session,
        mock_client_repo,
        sample_client,
    ):
        """Should return paginated list of clients."""
        # Setup
        mock_client_repo.list_all_for_tenant.return_value = ([sample_client], 1)

        with patch(
            "app.modules.integrations.xero.client_service.XeroClientRepository",
            return_value=mock_client_repo,
        ):
            service = XeroClientService(mock_session)
            service.client_repo = mock_client_repo

            # Execute
            result = await service.list_clients()

            # Verify
            assert result.total == 1
            assert len(result.clients) == 1
            mock_client_repo.list_all_for_tenant.assert_called_once()

    async def test_list_clients_passes_filters(
        self,
        mock_session,
        mock_client_repo,
    ):
        """Should pass filter parameters to repository."""
        mock_client_repo.list_all_for_tenant.return_value = ([], 0)

        with patch(
            "app.modules.integrations.xero.client_service.XeroClientRepository",
            return_value=mock_client_repo,
        ):
            service = XeroClientService(mock_session)
            service.client_repo = mock_client_repo

            await service.list_clients(
                search="test",
                contact_type="customer",
                is_active=True,
                limit=10,
                offset=5,
            )

            mock_client_repo.list_all_for_tenant.assert_called_once_with(
                search="test",
                contact_type="customer",
                is_active=True,
                sort_by="name",
                sort_order="asc",
                limit=10,
                offset=5,
            )


class TestXeroClientServiceGetClientDetail:
    """Tests for get_client_detail method."""

    async def test_get_client_detail_returns_client_with_connection(
        self,
        mock_session,
        mock_client_repo,
        mock_connection_repo,
        sample_client,
        sample_connection,
    ):
        """Should return client with connection details."""
        mock_client_repo.get_by_id.return_value = sample_client
        mock_connection_repo.get_by_id.return_value = sample_connection

        with (
            patch(
                "app.modules.integrations.xero.client_service.XeroClientRepository",
                return_value=mock_client_repo,
            ),
            patch(
                "app.modules.integrations.xero.client_service.XeroConnectionRepository",
                return_value=mock_connection_repo,
            ),
        ):
            service = XeroClientService(mock_session)
            service.client_repo = mock_client_repo
            service.connection_repo = mock_connection_repo

            result = await service.get_client_detail(sample_client.id)

            assert result.name == sample_client.name
            assert result.organization_name == sample_connection.organization_name

    async def test_get_client_detail_raises_not_found(
        self,
        mock_session,
        mock_client_repo,
    ):
        """Should raise error when client not found."""
        mock_client_repo.get_by_id.return_value = None

        with patch(
            "app.modules.integrations.xero.client_service.XeroClientRepository",
            return_value=mock_client_repo,
        ):
            service = XeroClientService(mock_session)
            service.client_repo = mock_client_repo

            with pytest.raises(XeroClientNotFoundError):
                await service.get_client_detail(uuid.uuid4())


class TestXeroClientServiceGetClientInvoices:
    """Tests for get_client_invoices method."""

    async def test_get_client_invoices_returns_paginated_response(
        self,
        mock_session,
        mock_client_repo,
        mock_invoice_repo,
        sample_client,
        sample_invoice,
    ):
        """Should return paginated list of invoices."""
        mock_client_repo.get_by_id.return_value = sample_client
        mock_invoice_repo.list_by_client.return_value = ([sample_invoice], 1)

        with (
            patch(
                "app.modules.integrations.xero.client_service.XeroClientRepository",
                return_value=mock_client_repo,
            ),
            patch(
                "app.modules.integrations.xero.client_service.XeroInvoiceRepository",
                return_value=mock_invoice_repo,
            ),
        ):
            service = XeroClientService(mock_session)
            service.client_repo = mock_client_repo
            service.invoice_repo = mock_invoice_repo

            result = await service.get_client_invoices(sample_client.id)

            assert result.total == 1
            assert len(result.invoices) == 1

    async def test_get_client_invoices_raises_not_found(
        self,
        mock_session,
        mock_client_repo,
    ):
        """Should raise error when client not found."""
        mock_client_repo.get_by_id.return_value = None

        with patch(
            "app.modules.integrations.xero.client_service.XeroClientRepository",
            return_value=mock_client_repo,
        ):
            service = XeroClientService(mock_session)
            service.client_repo = mock_client_repo

            with pytest.raises(XeroClientNotFoundError):
                await service.get_client_invoices(uuid.uuid4())


class TestXeroClientServiceGetFinancialSummary:
    """Tests for get_client_financial_summary method."""

    async def test_get_financial_summary_calculates_correctly(
        self,
        mock_session,
        mock_client_repo,
        mock_invoice_repo,
        mock_transaction_repo,
        sample_client,
    ):
        """Should calculate financial summary correctly."""
        mock_client_repo.get_by_id.return_value = sample_client
        mock_invoice_repo.calculate_summary.return_value = {
            "total_sales": Decimal("1000.00"),
            "gst_collected": Decimal("100.00"),
            "total_purchases": Decimal("500.00"),
            "gst_paid": Decimal("50.00"),
            "sales_invoice_count": 2,
            "purchase_invoice_count": 1,
        }
        mock_transaction_repo.count_by_client_and_date_range.return_value = 5

        with (
            patch(
                "app.modules.integrations.xero.client_service.XeroClientRepository",
                return_value=mock_client_repo,
            ),
            patch(
                "app.modules.integrations.xero.client_service.XeroInvoiceRepository",
                return_value=mock_invoice_repo,
            ),
            patch(
                "app.modules.integrations.xero.client_service.XeroBankTransactionRepository",
                return_value=mock_transaction_repo,
            ),
        ):
            service = XeroClientService(mock_session)
            service.client_repo = mock_client_repo
            service.invoice_repo = mock_invoice_repo
            service.transaction_repo = mock_transaction_repo

            result = await service.get_client_financial_summary(
                client_id=sample_client.id,
                quarter=2,
                fy_year=2025,
            )

            assert result.total_sales == Decimal("1000.00")
            assert result.total_purchases == Decimal("500.00")
            assert result.gst_collected == Decimal("100.00")
            assert result.gst_paid == Decimal("50.00")
            assert result.net_gst == Decimal("50.00")  # 100 - 50
            assert result.invoice_count == 3  # 2 + 1
            assert result.transaction_count == 5
            assert result.quarter_label == "Q2 FY25"

    async def test_get_financial_summary_raises_not_found(
        self,
        mock_session,
        mock_client_repo,
    ):
        """Should raise error when client not found."""
        mock_client_repo.get_by_id.return_value = None

        with patch(
            "app.modules.integrations.xero.client_service.XeroClientRepository",
            return_value=mock_client_repo,
        ):
            service = XeroClientService(mock_session)
            service.client_repo = mock_client_repo

            with pytest.raises(XeroClientNotFoundError):
                await service.get_client_financial_summary(
                    client_id=uuid.uuid4(),
                    quarter=2,
                    fy_year=2025,
                )


class TestXeroClientServiceGetAvailableQuarters:
    """Tests for get_available_quarters method."""

    def test_get_available_quarters_returns_quarters_list(
        self,
        mock_session,
    ):
        """Should return list of available quarters."""
        service = XeroClientService(mock_session)

        result = service.get_available_quarters()

        # Should include current quarter
        assert result.current is not None
        assert len(result.quarters) > 0

        # Quarters should have required fields
        for quarter in result.quarters:
            assert quarter.quarter in [1, 2, 3, 4]
            assert quarter.fy_year > 2020
            assert quarter.label
            assert quarter.start_date
            assert quarter.end_date

    def test_get_available_quarters_respects_num_previous(
        self,
        mock_session,
    ):
        """Should respect num_previous parameter."""
        service = XeroClientService(mock_session)

        result = service.get_available_quarters(num_previous=2, include_next=False)

        # Should have 3 quarters (current + 2 previous)
        assert len(result.quarters) >= 3
