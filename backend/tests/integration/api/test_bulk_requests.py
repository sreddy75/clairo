"""Integration tests for bulk document request API endpoints.

Tests cover:
- Creating bulk requests
- Previewing bulk requests
- Listing bulk requests
- Getting bulk request details

Spec: 030-client-portal-document-requests
"""

from datetime import date, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestCreateBulkRequest:
    """Tests for POST /bulk-requests endpoint."""

    async def test_create_bulk_request_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_xero_connections: list[dict],
    ) -> None:
        """Successfully create a bulk document request."""
        connection_ids = [c["id"] for c in test_xero_connections[:3]]

        response = await async_client.post(
            "/api/v1/bulk-requests",
            headers=auth_headers,
            json={
                "connection_ids": connection_ids,
                "title": "Quarterly Bank Statements",
                "description": "Please provide bank statements for Q3 2024.",
                "priority": "normal",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Quarterly Bank Statements"
        assert data["total_clients"] == 3
        assert data["status"] == "pending"
        assert data["sent_count"] == 0

    async def test_create_bulk_request_with_template(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_xero_connections: list[dict],
        test_template: dict,
    ) -> None:
        """Create a bulk request using a template."""
        connection_ids = [c["id"] for c in test_xero_connections[:2]]

        response = await async_client.post(
            "/api/v1/bulk-requests",
            headers=auth_headers,
            json={
                "connection_ids": connection_ids,
                "template_id": test_template["id"],
                "title": "Bank Statements Required",
                "description": "Please provide bank statements.",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["template_id"] == test_template["id"]

    async def test_create_bulk_request_with_due_date(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_xero_connections: list[dict],
    ) -> None:
        """Create a bulk request with a due date."""
        connection_ids = [c["id"] for c in test_xero_connections[:2]]
        due_date = (date.today() + timedelta(days=14)).isoformat()

        response = await async_client.post(
            "/api/v1/bulk-requests",
            headers=auth_headers,
            json={
                "connection_ids": connection_ids,
                "title": "Documents with Due Date",
                "description": "Please respond by the due date.",
                "due_date": due_date,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["due_date"] == due_date

    async def test_create_bulk_request_empty_connections(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        """Creating bulk request with empty connections fails."""
        response = await async_client.post(
            "/api/v1/bulk-requests",
            headers=auth_headers,
            json={
                "connection_ids": [],
                "title": "Empty Request",
                "description": "This should fail.",
            },
        )

        assert response.status_code == 422

    async def test_create_bulk_request_invalid_template(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_xero_connections: list[dict],
    ) -> None:
        """Creating bulk request with invalid template returns 404."""
        connection_ids = [c["id"] for c in test_xero_connections[:1]]

        response = await async_client.post(
            "/api/v1/bulk-requests",
            headers=auth_headers,
            json={
                "connection_ids": connection_ids,
                "template_id": str(uuid4()),
                "title": "Invalid Template",
                "description": "This should fail.",
            },
        )

        assert response.status_code == 404


@pytest.mark.asyncio
class TestPreviewBulkRequest:
    """Tests for POST /bulk-requests/preview endpoint."""

    async def test_preview_bulk_request(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_xero_connections: list[dict],
    ) -> None:
        """Preview a bulk request successfully."""
        connection_ids = [c["id"] for c in test_xero_connections[:5]]

        response = await async_client.post(
            "/api/v1/bulk-requests/preview",
            headers=auth_headers,
            json={
                "connection_ids": connection_ids,
                "title": "Preview Request",
                "description": "This is a preview.",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_clients"] == 5
        assert "valid_clients" in data
        assert "invalid_clients" in data
        assert "issues" in data


@pytest.mark.asyncio
class TestListBulkRequests:
    """Tests for GET /bulk-requests endpoint."""

    async def test_list_bulk_requests(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_bulk_request: dict,
    ) -> None:
        """List all bulk requests for the tenant."""
        response = await async_client.get(
            "/api/v1/bulk-requests",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "bulk_requests" in data
        assert "total" in data
        assert data["total"] >= 1

    async def test_list_bulk_requests_with_status_filter(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_bulk_request: dict,
    ) -> None:
        """List bulk requests filtered by status."""
        response = await async_client.get(
            "/api/v1/bulk-requests",
            headers=auth_headers,
            params={"status": "pending"},
        )

        assert response.status_code == 200
        data = response.json()
        assert all(r["status"] == "pending" for r in data["bulk_requests"])

    async def test_list_bulk_requests_with_pagination(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        """List bulk requests with pagination."""
        response = await async_client.get(
            "/api/v1/bulk-requests",
            headers=auth_headers,
            params={"page": 1, "page_size": 5},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["bulk_requests"]) <= 5


@pytest.mark.asyncio
class TestGetBulkRequest:
    """Tests for GET /bulk-requests/{bulk_id} endpoint."""

    async def test_get_bulk_request_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_bulk_request: dict,
    ) -> None:
        """Successfully get a bulk request by ID."""
        bulk_id = test_bulk_request["id"]

        response = await async_client.get(
            f"/api/v1/bulk-requests/{bulk_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == bulk_id
        assert "requests" in data
        assert "failed_connections" in data

    async def test_get_nonexistent_bulk_request(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        """Get a non-existent bulk request returns 404."""
        response = await async_client.get(
            f"/api/v1/bulk-requests/{uuid4()}",
            headers=auth_headers,
        )

        assert response.status_code == 404
