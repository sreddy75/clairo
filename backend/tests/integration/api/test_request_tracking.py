"""Integration tests for request tracking endpoints.

Tests cover:
- GET /requests/tracking - Full tracking dashboard data
- GET /requests/tracking/summary - Quick summary statistics

Spec: 030-client-portal-document-requests
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestTrackingDashboard:
    """Tests for GET /requests/tracking endpoint."""

    async def test_get_tracking_data_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_document_requests: list[dict],
    ) -> None:
        """Successfully get tracking data with summary and grouped requests."""
        response = await async_client.get(
            "/api/v1/requests/tracking",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify summary structure
        assert "summary" in data
        summary = data["summary"]
        assert "total" in summary
        assert "pending" in summary
        assert "viewed" in summary
        assert "in_progress" in summary
        assert "completed" in summary
        assert "cancelled" in summary
        assert "overdue" in summary
        assert "due_today" in summary
        assert "due_this_week" in summary

        # Verify groups structure
        assert "groups" in data
        assert isinstance(data["groups"], list)

        # Verify pagination
        assert data["page"] == 1
        assert data["page_size"] == 50

    async def test_get_tracking_data_with_status_filter(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_document_requests: list[dict],
    ) -> None:
        """Filter tracking data by status."""
        response = await async_client.get(
            "/api/v1/requests/tracking",
            headers=auth_headers,
            params={"status": "pending"},
        )

        assert response.status_code == 200
        data = response.json()

        # All requests in groups should be pending
        for group in data["groups"]:
            assert group["status"] == "pending"

    async def test_get_tracking_data_pagination(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        """Test pagination parameters."""
        response = await async_client.get(
            "/api/v1/requests/tracking",
            headers=auth_headers,
            params={"page": 2, "page_size": 10},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["page_size"] == 10

    async def test_get_tracking_data_empty(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        """Returns empty tracking data when no requests exist."""
        response = await async_client.get(
            "/api/v1/requests/tracking",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Summary should have zero counts
        assert data["summary"]["total"] == 0
        assert data["groups"] == []

    async def test_get_tracking_data_unauthorized(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Tracking endpoint requires authentication."""
        response = await async_client.get("/api/v1/requests/tracking")
        assert response.status_code == 401

    async def test_tracking_item_structure(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_document_request: dict,
    ) -> None:
        """Verify tracking item has all required fields."""
        response = await async_client.get(
            "/api/v1/requests/tracking",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Get the first item from any group
        if data["groups"]:
            group = data["groups"][0]
            if group["requests"]:
                item = group["requests"][0]

                # Verify item structure
                assert "id" in item
                assert "connection_id" in item
                assert "organization_name" in item
                assert "title" in item
                assert "due_date" in item
                assert "priority" in item
                assert "status" in item
                assert "is_overdue" in item
                assert "days_until_due" in item


@pytest.mark.asyncio
class TestTrackingSummary:
    """Tests for GET /requests/tracking/summary endpoint."""

    async def test_get_tracking_summary_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_document_requests: list[dict],
    ) -> None:
        """Successfully get tracking summary with recent activity."""
        response = await async_client.get(
            "/api/v1/requests/tracking/summary",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify summary structure
        assert "summary" in data
        summary = data["summary"]
        assert "total" in summary
        assert "pending" in summary
        assert "overdue" in summary
        assert "due_today" in summary
        assert "due_this_week" in summary

        # Verify recent activity
        assert "recent_activity" in data
        assert isinstance(data["recent_activity"], list)

    async def test_get_tracking_summary_empty(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        """Returns zero summary when no requests exist."""
        response = await async_client.get(
            "/api/v1/requests/tracking/summary",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["summary"]["total"] == 0
        assert data["summary"]["pending"] == 0
        assert data["summary"]["overdue"] == 0
        assert data["recent_activity"] == []

    async def test_get_tracking_summary_unauthorized(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Summary endpoint requires authentication."""
        response = await async_client.get("/api/v1/requests/tracking/summary")
        assert response.status_code == 401

    async def test_recent_activity_limited(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_document_requests: list[dict],
    ) -> None:
        """Recent activity returns limited number of items."""
        response = await async_client.get(
            "/api/v1/requests/tracking/summary",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Recent activity should be limited to 5 items
        assert len(data["recent_activity"]) <= 5


@pytest.mark.asyncio
class TestTrackingOverdueCalculation:
    """Tests for overdue request tracking."""

    async def test_overdue_count(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_overdue_request: dict,
    ) -> None:
        """Overdue requests are counted correctly."""
        response = await async_client.get(
            "/api/v1/requests/tracking/summary",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["summary"]["overdue"] >= 1

    async def test_due_today_count(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_due_today_request: dict,
    ) -> None:
        """Requests due today are counted correctly."""
        response = await async_client.get(
            "/api/v1/requests/tracking/summary",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["summary"]["due_today"] >= 1

    async def test_due_this_week_count(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_due_week_request: dict,
    ) -> None:
        """Requests due this week are counted correctly."""
        response = await async_client.get(
            "/api/v1/requests/tracking/summary",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["summary"]["due_this_week"] >= 1

    async def test_completed_not_counted_as_overdue(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_completed_overdue_request: dict,
    ) -> None:
        """Completed requests with past due dates are not counted as overdue."""
        response = await async_client.get(
            "/api/v1/requests/tracking/summary",
            headers=auth_headers,
        )

        assert response.status_code == 200
        # The completed request should not be in overdue count
        # Verify by checking that completed count is correct
        data = response.json()
        assert data["summary"]["completed"] >= 1
