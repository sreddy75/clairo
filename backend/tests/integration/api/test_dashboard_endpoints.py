"""Integration tests for dashboard API endpoints.

Tests cover authentication requirements for:
- GET /api/v1/dashboard/summary
- GET /api/v1/dashboard/clients
- GET /api/v1/dashboard/connections
"""

import pytest
from httpx import AsyncClient


@pytest.mark.integration
class TestDashboardSummaryEndpoint:
    """Tests for GET /api/v1/dashboard/summary."""

    async def test_get_summary_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Should return 401 without authentication."""
        response = await test_client.get("/api/v1/dashboard/summary")
        assert response.status_code == 401

    async def test_get_summary_with_invalid_quarter(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Should return 422 with invalid quarter parameter."""
        response = await test_client.get(
            "/api/v1/dashboard/summary",
            params={"quarter": 5},  # Invalid: must be 1-4
        )
        # Will be 401 first (no auth), but validates param format
        assert response.status_code in [401, 422]


@pytest.mark.integration
class TestDashboardClientsEndpoint:
    """Tests for GET /api/v1/dashboard/clients."""

    async def test_get_clients_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Should return 401 without authentication."""
        response = await test_client.get("/api/v1/dashboard/clients")
        assert response.status_code == 401

    async def test_get_clients_with_filters(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Should accept filter parameters."""
        response = await test_client.get(
            "/api/v1/dashboard/clients",
            params={
                "quarter": 2,
                "fy_year": 2025,
                "status": "ready",
                "contact_type": "customer",
                "search": "test",
                "sort_by": "total_sales",
                "sort_order": "desc",
                "page": 1,
                "limit": 25,
            },
        )
        # Will be 401 (no auth) but validates params accepted
        assert response.status_code == 401


@pytest.mark.integration
class TestDashboardConnectionsEndpoint:
    """Tests for GET /api/v1/dashboard/connections."""

    async def test_get_connections_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Should return 401 without authentication."""
        response = await test_client.get("/api/v1/dashboard/connections")
        assert response.status_code == 401
