"""Integration tests for client-facing document request endpoints.

Tests cover:
- Listing client requests
- Getting request details and marking as viewed
- Submitting responses
- Listing request responses

Spec: 030-client-portal-document-requests
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestListClientRequests:
    """Tests for GET /portal/requests endpoint."""

    async def test_list_requests_success(
        self,
        async_client: AsyncClient,
        portal_auth_headers: dict,
        test_document_request: dict,
    ) -> None:
        """Successfully list document requests for authenticated client."""
        response = await async_client.get(
            "/api/v1/portal/requests",
            headers=portal_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "requests" in data
        assert "total" in data
        assert data["total"] >= 1

    async def test_list_requests_excludes_drafts(
        self,
        async_client: AsyncClient,
        portal_auth_headers: dict,
        test_draft_request: dict,
    ) -> None:
        """Draft requests are not visible to clients."""
        response = await async_client.get(
            "/api/v1/portal/requests",
            headers=portal_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        # Drafts should not appear
        request_ids = [r["id"] for r in data["requests"]]
        assert test_draft_request["id"] not in request_ids

    async def test_list_requests_filter_by_status(
        self,
        async_client: AsyncClient,
        portal_auth_headers: dict,
        test_document_request: dict,
    ) -> None:
        """Filter requests by status."""
        response = await async_client.get(
            "/api/v1/portal/requests",
            headers=portal_auth_headers,
            params={"status": "pending"},
        )

        assert response.status_code == 200
        data = response.json()
        assert all(r["status"] == "pending" for r in data["requests"])

    async def test_list_requests_pagination(
        self,
        async_client: AsyncClient,
        portal_auth_headers: dict,
    ) -> None:
        """Test pagination parameters."""
        response = await async_client.get(
            "/api/v1/portal/requests",
            headers=portal_auth_headers,
            params={"page": 1, "page_size": 5},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["requests"]) <= 5
        assert data["page"] == 1
        assert data["page_size"] == 5

    async def test_list_requests_unauthorized(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Unauthenticated access returns 401."""
        response = await async_client.get("/api/v1/portal/requests")

        assert response.status_code == 401


@pytest.mark.asyncio
class TestGetClientRequest:
    """Tests for GET /portal/requests/{request_id} endpoint."""

    async def test_get_request_success(
        self,
        async_client: AsyncClient,
        portal_auth_headers: dict,
        test_document_request: dict,
    ) -> None:
        """Successfully get a document request."""
        request_id = test_document_request["id"]

        response = await async_client.get(
            f"/api/v1/portal/requests/{request_id}",
            headers=portal_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == request_id
        assert "title" in data
        assert "description" in data
        assert "status" in data

    async def test_get_request_marks_as_viewed(
        self,
        async_client: AsyncClient,
        portal_auth_headers: dict,
        test_pending_request: dict,
    ) -> None:
        """Getting a pending request marks it as viewed."""
        request_id = test_pending_request["id"]

        # Get the request
        response = await async_client.get(
            f"/api/v1/portal/requests/{request_id}",
            headers=portal_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        # Status should now be viewed
        assert data["status"] == "viewed"
        assert data["viewed_at"] is not None

    async def test_get_nonexistent_request(
        self,
        async_client: AsyncClient,
        portal_auth_headers: dict,
    ) -> None:
        """Getting a non-existent request returns 404."""
        response = await async_client.get(
            f"/api/v1/portal/requests/{uuid4()}",
            headers=portal_auth_headers,
        )

        assert response.status_code == 404

    async def test_get_request_wrong_client(
        self,
        async_client: AsyncClient,
        other_portal_auth_headers: dict,
        test_document_request: dict,
    ) -> None:
        """Cannot access another client's request."""
        request_id = test_document_request["id"]

        response = await async_client.get(
            f"/api/v1/portal/requests/{request_id}",
            headers=other_portal_auth_headers,
        )

        assert response.status_code == 404


@pytest.mark.asyncio
class TestSubmitResponse:
    """Tests for POST /portal/requests/{request_id}/respond endpoint."""

    async def test_submit_response_success(
        self,
        async_client: AsyncClient,
        portal_auth_headers: dict,
        test_pending_request: dict,
    ) -> None:
        """Successfully submit a response with message."""
        request_id = test_pending_request["id"]

        response = await async_client.post(
            f"/api/v1/portal/requests/{request_id}/respond",
            headers=portal_auth_headers,
            json={
                "message": "Here are the documents you requested.",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["request"]["status"] == "in_progress"
        assert data["request"]["responded_at"] is not None

    async def test_submit_response_with_documents(
        self,
        async_client: AsyncClient,
        portal_auth_headers: dict,
        test_pending_request: dict,
        test_uploaded_documents: list[dict],
    ) -> None:
        """Submit a response with attached documents."""
        request_id = test_pending_request["id"]
        doc_ids = [d["id"] for d in test_uploaded_documents[:2]]

        response = await async_client.post(
            f"/api/v1/portal/requests/{request_id}/respond",
            headers=portal_auth_headers,
            json={
                "message": "Attached documents as requested.",
                "document_ids": doc_ids,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    async def test_submit_response_no_message_no_docs(
        self,
        async_client: AsyncClient,
        portal_auth_headers: dict,
        test_pending_request: dict,
    ) -> None:
        """Submit an empty response (just acknowledging)."""
        request_id = test_pending_request["id"]

        response = await async_client.post(
            f"/api/v1/portal/requests/{request_id}/respond",
            headers=portal_auth_headers,
            json={},
        )

        assert response.status_code == 200

    async def test_submit_response_to_completed_request(
        self,
        async_client: AsyncClient,
        portal_auth_headers: dict,
        test_completed_request: dict,
    ) -> None:
        """Cannot submit response to a completed request."""
        request_id = test_completed_request["id"]

        response = await async_client.post(
            f"/api/v1/portal/requests/{request_id}/respond",
            headers=portal_auth_headers,
            json={"message": "Late response"},
        )

        assert response.status_code == 400

    async def test_submit_response_to_cancelled_request(
        self,
        async_client: AsyncClient,
        portal_auth_headers: dict,
        test_cancelled_request: dict,
    ) -> None:
        """Cannot submit response to a cancelled request."""
        request_id = test_cancelled_request["id"]

        response = await async_client.post(
            f"/api/v1/portal/requests/{request_id}/respond",
            headers=portal_auth_headers,
            json={"message": "Response to cancelled"},
        )

        assert response.status_code == 400

    async def test_submit_response_nonexistent_request(
        self,
        async_client: AsyncClient,
        portal_auth_headers: dict,
    ) -> None:
        """Cannot submit response to non-existent request."""
        response = await async_client.post(
            f"/api/v1/portal/requests/{uuid4()}/respond",
            headers=portal_auth_headers,
            json={"message": "Hello"},
        )

        assert response.status_code == 404


@pytest.mark.asyncio
class TestListRequestResponses:
    """Tests for GET /portal/requests/{request_id}/responses endpoint."""

    async def test_list_responses_success(
        self,
        async_client: AsyncClient,
        portal_auth_headers: dict,
        test_request_with_responses: dict,
    ) -> None:
        """Successfully list responses for a request."""
        request_id = test_request_with_responses["id"]

        response = await async_client.get(
            f"/api/v1/portal/requests/{request_id}/responses",
            headers=portal_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "responses" in data
        assert "total" in data
        assert data["total"] >= 1

    async def test_list_responses_nonexistent_request(
        self,
        async_client: AsyncClient,
        portal_auth_headers: dict,
    ) -> None:
        """Listing responses for non-existent request returns 404."""
        response = await async_client.get(
            f"/api/v1/portal/requests/{uuid4()}/responses",
            headers=portal_auth_headers,
        )

        assert response.status_code == 404
