"""Integration tests for document request API endpoints.

Tests cover:
- Creating document requests
- Sending document requests
- Listing document requests
- Updating document requests
- Cancelling and completing requests

Spec: 030-client-portal-document-requests
"""

from datetime import date, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestCreateDocumentRequest:
    """Tests for POST /clients/{connection_id}/requests endpoint."""

    async def test_create_request_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_xero_connection: dict,
    ) -> None:
        """Successfully create a document request."""
        connection_id = test_xero_connection["id"]

        response = await async_client.post(
            f"/api/v1/clients/{connection_id}/requests",
            headers=auth_headers,
            json={
                "connection_id": connection_id,
                "title": "Bank Statements Required",
                "description": "Please provide bank statements for the last quarter.",
                "priority": "normal",
                "auto_remind": True,
                "send_immediately": True,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Bank Statements Required"
        assert data["status"] == "pending"  # Sent immediately
        assert data["priority"] == "normal"
        assert data["auto_remind"] is True
        assert data["connection_id"] == connection_id

    async def test_create_request_as_draft(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_xero_connection: dict,
    ) -> None:
        """Create a document request as draft."""
        connection_id = test_xero_connection["id"]

        response = await async_client.post(
            f"/api/v1/clients/{connection_id}/requests",
            headers=auth_headers,
            json={
                "connection_id": connection_id,
                "title": "Draft Request",
                "description": "This is a draft request.",
                "send_immediately": False,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "draft"
        assert data["sent_at"] is None

    async def test_create_request_with_due_date(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_xero_connection: dict,
    ) -> None:
        """Create a request with explicit due date."""
        connection_id = test_xero_connection["id"]
        due_date = (date.today() + timedelta(days=14)).isoformat()

        response = await async_client.post(
            f"/api/v1/clients/{connection_id}/requests",
            headers=auth_headers,
            json={
                "connection_id": connection_id,
                "title": "Request with Due Date",
                "description": "Please respond by the due date.",
                "due_date": due_date,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["due_date"] == due_date

    async def test_create_request_with_template(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_xero_connection: dict,
        test_template: dict,
    ) -> None:
        """Create a request using a template."""
        connection_id = test_xero_connection["id"]
        template_id = test_template["id"]

        response = await async_client.post(
            f"/api/v1/clients/{connection_id}/requests",
            headers=auth_headers,
            json={
                "connection_id": connection_id,
                "template_id": template_id,
                "title": "Request from Template",
                "description": "Based on template.",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["template_id"] == template_id

    async def test_create_request_invalid_template(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_xero_connection: dict,
    ) -> None:
        """Create a request with invalid template returns 404."""
        connection_id = test_xero_connection["id"]

        response = await async_client.post(
            f"/api/v1/clients/{connection_id}/requests",
            headers=auth_headers,
            json={
                "connection_id": connection_id,
                "template_id": str(uuid4()),
                "title": "Request with Invalid Template",
                "description": "This should fail.",
            },
        )

        assert response.status_code == 404

    async def test_create_request_missing_title(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_xero_connection: dict,
    ) -> None:
        """Create a request without title returns 422."""
        connection_id = test_xero_connection["id"]

        response = await async_client.post(
            f"/api/v1/clients/{connection_id}/requests",
            headers=auth_headers,
            json={
                "connection_id": connection_id,
                "description": "Missing title.",
            },
        )

        assert response.status_code == 422


@pytest.mark.asyncio
class TestSendDocumentRequest:
    """Tests for POST /requests/{request_id}/send endpoint."""

    async def test_send_draft_request(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_draft_request: dict,
    ) -> None:
        """Successfully send a draft request."""
        request_id = test_draft_request["id"]

        response = await async_client.post(
            f"/api/v1/requests/{request_id}/send",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"
        assert data["sent_at"] is not None

    async def test_send_already_sent_request(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_pending_request: dict,
    ) -> None:
        """Sending an already sent request returns error."""
        request_id = test_pending_request["id"]

        response = await async_client.post(
            f"/api/v1/requests/{request_id}/send",
            headers=auth_headers,
        )

        assert response.status_code == 400

    async def test_send_nonexistent_request(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        """Sending a non-existent request returns 404."""
        response = await async_client.post(
            f"/api/v1/requests/{uuid4()}/send",
            headers=auth_headers,
        )

        assert response.status_code == 404


@pytest.mark.asyncio
class TestListDocumentRequests:
    """Tests for GET /requests and /clients/{id}/requests endpoints."""

    async def test_list_requests_for_tenant(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_pending_request: dict,
    ) -> None:
        """List all requests for the tenant."""
        response = await async_client.get(
            "/api/v1/requests",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "requests" in data
        assert "total" in data
        assert data["total"] >= 1

    async def test_list_requests_for_client(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_xero_connection: dict,
        test_pending_request: dict,
    ) -> None:
        """List requests for a specific client."""
        connection_id = test_xero_connection["id"]

        response = await async_client.get(
            f"/api/v1/clients/{connection_id}/requests",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "requests" in data
        assert all(r["connection_id"] == connection_id for r in data["requests"])

    async def test_list_requests_with_status_filter(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_pending_request: dict,
    ) -> None:
        """List requests filtered by status."""
        response = await async_client.get(
            "/api/v1/requests",
            headers=auth_headers,
            params={"status": "pending"},
        )

        assert response.status_code == 200
        data = response.json()
        assert all(r["status"] == "pending" for r in data["requests"])

    async def test_list_requests_with_priority_filter(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        """List requests filtered by priority."""
        response = await async_client.get(
            "/api/v1/requests",
            headers=auth_headers,
            params={"priority": "high"},
        )

        assert response.status_code == 200

    async def test_list_requests_with_pagination(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        """List requests with pagination."""
        response = await async_client.get(
            "/api/v1/requests",
            headers=auth_headers,
            params={"page": 1, "page_size": 5},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 5
        assert len(data["requests"]) <= 5


@pytest.mark.asyncio
class TestGetDocumentRequest:
    """Tests for GET /requests/{request_id} endpoint."""

    async def test_get_request_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_pending_request: dict,
    ) -> None:
        """Successfully get a request by ID."""
        request_id = test_pending_request["id"]

        response = await async_client.get(
            f"/api/v1/requests/{request_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == request_id
        assert "organization_name" in data

    async def test_get_nonexistent_request(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        """Get a non-existent request returns 404."""
        response = await async_client.get(
            f"/api/v1/requests/{uuid4()}",
            headers=auth_headers,
        )

        assert response.status_code == 404


@pytest.mark.asyncio
class TestUpdateDocumentRequest:
    """Tests for PATCH /requests/{request_id} endpoint."""

    async def test_update_request_title(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_draft_request: dict,
    ) -> None:
        """Successfully update request title."""
        request_id = test_draft_request["id"]

        response = await async_client.patch(
            f"/api/v1/requests/{request_id}",
            headers=auth_headers,
            json={"title": "Updated Title"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"

    async def test_update_request_priority(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_draft_request: dict,
    ) -> None:
        """Successfully update request priority."""
        request_id = test_draft_request["id"]

        response = await async_client.patch(
            f"/api/v1/requests/{request_id}",
            headers=auth_headers,
            json={"priority": "urgent"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["priority"] == "urgent"

    async def test_update_nonexistent_request(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        """Update a non-existent request returns 404."""
        response = await async_client.patch(
            f"/api/v1/requests/{uuid4()}",
            headers=auth_headers,
            json={"title": "Won't Work"},
        )

        assert response.status_code == 404


@pytest.mark.asyncio
class TestCancelDocumentRequest:
    """Tests for POST /requests/{request_id}/cancel endpoint."""

    async def test_cancel_pending_request(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_pending_request: dict,
    ) -> None:
        """Successfully cancel a pending request."""
        request_id = test_pending_request["id"]

        response = await async_client.post(
            f"/api/v1/requests/{request_id}/cancel",
            headers=auth_headers,
            params={"reason": "No longer needed"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"

    async def test_cancel_nonexistent_request(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        """Cancel a non-existent request returns 404."""
        response = await async_client.post(
            f"/api/v1/requests/{uuid4()}/cancel",
            headers=auth_headers,
        )

        assert response.status_code == 404


@pytest.mark.asyncio
class TestCompleteDocumentRequest:
    """Tests for POST /requests/{request_id}/complete endpoint."""

    async def test_complete_pending_request(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_pending_request: dict,
    ) -> None:
        """Successfully complete a pending request."""
        request_id = test_pending_request["id"]

        response = await async_client.post(
            f"/api/v1/requests/{request_id}/complete",
            headers=auth_headers,
            params={"note": "All documents received"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "complete"
        assert data["completed_at"] is not None

    async def test_complete_draft_request_fails(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        test_draft_request: dict,
    ) -> None:
        """Cannot complete a draft request."""
        request_id = test_draft_request["id"]

        response = await async_client.post(
            f"/api/v1/requests/{request_id}/complete",
            headers=auth_headers,
        )

        assert response.status_code == 400

    async def test_complete_nonexistent_request(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ) -> None:
        """Complete a non-existent request returns 404."""
        response = await async_client.post(
            f"/api/v1/requests/{uuid4()}/complete",
            headers=auth_headers,
        )

        assert response.status_code == 404
