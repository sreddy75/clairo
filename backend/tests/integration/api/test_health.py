"""Integration tests for health check endpoints.

Tests verify that the health endpoints return expected responses
and that the application is properly configured.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.integration
class TestHealthEndpoints:
    """Tests for /health and related endpoints."""

    async def test_health_endpoint_returns_200(self, test_client: AsyncClient) -> None:
        """Test that /health returns HTTP 200."""
        response = await test_client.get("/health")
        assert response.status_code == 200

    async def test_health_endpoint_returns_expected_fields(self, test_client: AsyncClient) -> None:
        """Test that /health returns required fields."""
        response = await test_client.get("/health")
        data = response.json()

        assert "status" in data
        assert "version" in data
        assert "environment" in data

    async def test_health_endpoint_status_is_healthy(self, test_client: AsyncClient) -> None:
        """Test that /health returns healthy status."""
        response = await test_client.get("/health")
        data = response.json()

        assert data["status"] == "healthy"

    async def test_health_endpoint_version_matches_settings(self, test_client: AsyncClient) -> None:
        """Test that /health version matches application settings."""
        from app.config import get_settings

        settings = get_settings()
        response = await test_client.get("/health")
        data = response.json()

        assert data["version"] == settings.app_version

    async def test_health_endpoint_environment_matches_settings(
        self, test_client: AsyncClient
    ) -> None:
        """Test that /health environment matches application settings."""
        from app.config import get_settings

        settings = get_settings()
        response = await test_client.get("/health")
        data = response.json()

        assert data["environment"] == settings.environment


@pytest.mark.integration
class TestRootEndpoint:
    """Tests for the root endpoint."""

    async def test_root_endpoint_returns_200(self, test_client: AsyncClient) -> None:
        """Test that / returns HTTP 200."""
        response = await test_client.get("/")
        assert response.status_code == 200

    async def test_root_endpoint_returns_app_info(self, test_client: AsyncClient) -> None:
        """Test that / returns application information."""
        response = await test_client.get("/")
        data = response.json()

        assert "app" in data
        assert "version" in data
        assert "status" in data

    async def test_root_endpoint_status_is_running(self, test_client: AsyncClient) -> None:
        """Test that / shows running status."""
        response = await test_client.get("/")
        data = response.json()

        assert data["status"] == "running"


@pytest.mark.integration
class TestReadinessEndpoint:
    """Tests for the /health/ready endpoint."""

    async def test_readiness_endpoint_returns_200(self, test_client: AsyncClient) -> None:
        """Test that /health/ready returns HTTP 200."""
        response = await test_client.get("/health/ready")
        assert response.status_code == 200

    async def test_readiness_endpoint_returns_checks(self, test_client: AsyncClient) -> None:
        """Test that /health/ready returns health checks."""
        response = await test_client.get("/health/ready")
        data = response.json()

        assert "status" in data
        assert "checks" in data
        assert isinstance(data["checks"], dict)
