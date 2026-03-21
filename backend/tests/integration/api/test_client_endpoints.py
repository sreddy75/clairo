"""Integration tests for Xero client API endpoints.

Tests cover authentication requirements for:
- GET /api/v1/integrations/xero/clients
- GET /api/v1/integrations/xero/clients/{client_id}
- GET /api/v1/integrations/xero/clients/{client_id}/invoices
- GET /api/v1/integrations/xero/clients/{client_id}/transactions
- GET /api/v1/integrations/xero/clients/{client_id}/summary
- GET /api/v1/integrations/xero/quarters
"""

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.integration
class TestClientListEndpoint:
    """Tests for GET /api/v1/integrations/xero/clients."""

    async def test_list_clients_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Should return 401 without authentication."""
        response = await test_client.get("/api/v1/integrations/xero/clients")
        assert response.status_code == 401


@pytest.mark.integration
class TestClientDetailEndpoint:
    """Tests for GET /api/v1/integrations/xero/clients/{client_id}."""

    async def test_get_client_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Should return 401 without authentication."""
        client_id = uuid.uuid4()
        response = await test_client.get(f"/api/v1/integrations/xero/clients/{client_id}")
        assert response.status_code == 401


@pytest.mark.integration
class TestClientInvoicesEndpoint:
    """Tests for GET /api/v1/integrations/xero/clients/{client_id}/invoices."""

    async def test_get_invoices_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Should return 401 without authentication."""
        client_id = uuid.uuid4()
        response = await test_client.get(f"/api/v1/integrations/xero/clients/{client_id}/invoices")
        assert response.status_code == 401


@pytest.mark.integration
class TestClientTransactionsEndpoint:
    """Tests for GET /api/v1/integrations/xero/clients/{client_id}/transactions."""

    async def test_get_transactions_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Should return 401 without authentication."""
        client_id = uuid.uuid4()
        response = await test_client.get(
            f"/api/v1/integrations/xero/clients/{client_id}/transactions"
        )
        assert response.status_code == 401


@pytest.mark.integration
class TestClientSummaryEndpoint:
    """Tests for GET /api/v1/integrations/xero/clients/{client_id}/summary."""

    async def test_get_summary_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Should return 401 without authentication."""
        client_id = uuid.uuid4()
        response = await test_client.get(f"/api/v1/integrations/xero/clients/{client_id}/summary")
        assert response.status_code == 401


@pytest.mark.integration
class TestQuartersEndpoint:
    """Tests for GET /api/v1/integrations/xero/quarters."""

    async def test_get_quarters_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Should return 401 without authentication."""
        response = await test_client.get("/api/v1/integrations/xero/quarters")
        assert response.status_code == 401
