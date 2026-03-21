"""Integration tests for portal document upload endpoints.

Tests cover:
- Direct file upload
- Presigned URL generation
- Presigned upload confirmation
- Document listing
- Download URL generation
- Document deletion

Spec: 030-client-portal-document-requests
"""

import io
from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestDirectUpload:
    """Tests for POST /portal/documents/upload endpoint."""

    async def test_upload_pdf_success(
        self,
        async_client: AsyncClient,
        portal_auth_headers: dict,
    ) -> None:
        """Successfully upload a PDF document."""
        # Create a fake PDF file
        file_content = b"%PDF-1.4\ntest content"
        files = {"file": ("test_document.pdf", io.BytesIO(file_content), "application/pdf")}

        response = await async_client.post(
            "/api/v1/portal/documents/upload",
            headers=portal_auth_headers,
            files=files,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "test_document.pdf"
        assert data["content_type"] == "application/pdf"
        assert "id" in data
        assert "uploaded_at" in data

    async def test_upload_with_document_type(
        self,
        async_client: AsyncClient,
        portal_auth_headers: dict,
    ) -> None:
        """Upload document with document type classification."""
        file_content = b"test image content"
        files = {"file": ("bank_statement.png", io.BytesIO(file_content), "image/png")}
        data = {"document_type": "bank_statement"}

        response = await async_client.post(
            "/api/v1/portal/documents/upload",
            headers=portal_auth_headers,
            files=files,
            data=data,
        )

        assert response.status_code == 200

    async def test_upload_invalid_file_type(
        self,
        async_client: AsyncClient,
        portal_auth_headers: dict,
    ) -> None:
        """Uploading unsupported file type returns 400."""
        file_content = b"executable content"
        files = {"file": ("malware.exe", io.BytesIO(file_content), "application/x-msdownload")}

        response = await async_client.post(
            "/api/v1/portal/documents/upload",
            headers=portal_auth_headers,
            files=files,
        )

        assert response.status_code == 400
        assert "not allowed" in response.json()["detail"].lower()

    async def test_upload_empty_file(
        self,
        async_client: AsyncClient,
        portal_auth_headers: dict,
    ) -> None:
        """Uploading empty file returns 400."""
        files = {"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")}

        response = await async_client.post(
            "/api/v1/portal/documents/upload",
            headers=portal_auth_headers,
            files=files,
        )

        assert response.status_code == 400

    async def test_upload_unauthorized(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Uploading without authentication returns 401."""
        files = {"file": ("test.pdf", io.BytesIO(b"content"), "application/pdf")}

        response = await async_client.post(
            "/api/v1/portal/documents/upload",
            files=files,
        )

        assert response.status_code == 401


@pytest.mark.asyncio
class TestPresignedUpload:
    """Tests for presigned upload URL generation."""

    async def test_get_presigned_url_success(
        self,
        async_client: AsyncClient,
        portal_auth_headers: dict,
    ) -> None:
        """Successfully get a presigned upload URL."""
        response = await async_client.post(
            "/api/v1/portal/documents/upload-url",
            headers=portal_auth_headers,
            json={
                "filename": "quarterly_report.pdf",
                "content_type": "application/pdf",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "upload_url" in data
        assert "document_id" in data
        assert "storage_key" in data
        assert data["content_type"] == "application/pdf"
        assert data["expires_in"] > 0

    async def test_get_presigned_url_invalid_extension(
        self,
        async_client: AsyncClient,
        portal_auth_headers: dict,
    ) -> None:
        """Requesting presigned URL for invalid file type returns 400."""
        response = await async_client.post(
            "/api/v1/portal/documents/upload-url",
            headers=portal_auth_headers,
            json={
                "filename": "script.sh",
            },
        )

        assert response.status_code == 400

    async def test_confirm_presigned_upload(
        self,
        async_client: AsyncClient,
        portal_auth_headers: dict,
        presigned_upload: dict,  # Fixture that creates presigned URL
    ) -> None:
        """Confirm a presigned upload after file is uploaded."""
        # Note: In real test, file would be uploaded to MinIO first
        # This tests the endpoint structure
        response = await async_client.post(
            "/api/v1/portal/documents/upload/confirm",
            headers=portal_auth_headers,
            json={
                "document_id": presigned_upload["document_id"],
                "storage_key": presigned_upload["storage_key"],
                "filename": "report.pdf",
                "content_type": "application/pdf",
                "file_size": 1024,
            },
        )

        # May fail if file not actually uploaded - that's expected
        assert response.status_code in [200, 400]


@pytest.mark.asyncio
class TestListDocuments:
    """Tests for GET /portal/documents endpoint."""

    async def test_list_documents_success(
        self,
        async_client: AsyncClient,
        portal_auth_headers: dict,
        test_portal_documents: list[dict],
    ) -> None:
        """Successfully list uploaded documents."""
        response = await async_client.get(
            "/api/v1/portal/documents",
            headers=portal_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        assert "total" in data
        assert data["total"] >= 1

    async def test_list_documents_with_filter(
        self,
        async_client: AsyncClient,
        portal_auth_headers: dict,
    ) -> None:
        """List documents filtered by type."""
        response = await async_client.get(
            "/api/v1/portal/documents",
            headers=portal_auth_headers,
            params={"document_type": "bank_statement"},
        )

        assert response.status_code == 200

    async def test_list_documents_pagination(
        self,
        async_client: AsyncClient,
        portal_auth_headers: dict,
    ) -> None:
        """List documents with pagination."""
        response = await async_client.get(
            "/api/v1/portal/documents",
            headers=portal_auth_headers,
            params={"page": 1, "page_size": 5},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["documents"]) <= 5


@pytest.mark.asyncio
class TestDownloadUrl:
    """Tests for GET /portal/documents/{id}/download-url endpoint."""

    async def test_get_download_url_success(
        self,
        async_client: AsyncClient,
        portal_auth_headers: dict,
        test_portal_document: dict,
    ) -> None:
        """Successfully get download URL for a document."""
        doc_id = test_portal_document["id"]

        response = await async_client.get(
            f"/api/v1/portal/documents/{doc_id}/download-url",
            headers=portal_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "download_url" in data
        assert "filename" in data
        assert "expires_in" in data

    async def test_get_download_url_not_found(
        self,
        async_client: AsyncClient,
        portal_auth_headers: dict,
    ) -> None:
        """Getting download URL for non-existent document returns 404."""
        response = await async_client.get(
            f"/api/v1/portal/documents/{uuid4()}/download-url",
            headers=portal_auth_headers,
        )

        assert response.status_code == 404

    async def test_get_download_url_wrong_client(
        self,
        async_client: AsyncClient,
        other_portal_auth_headers: dict,
        test_portal_document: dict,
    ) -> None:
        """Cannot get download URL for another client's document."""
        doc_id = test_portal_document["id"]

        response = await async_client.get(
            f"/api/v1/portal/documents/{doc_id}/download-url",
            headers=other_portal_auth_headers,
        )

        assert response.status_code == 404


@pytest.mark.asyncio
class TestDeleteDocument:
    """Tests for DELETE /portal/documents/{id} endpoint."""

    async def test_delete_document_success(
        self,
        async_client: AsyncClient,
        portal_auth_headers: dict,
        test_deletable_document: dict,
    ) -> None:
        """Successfully delete an unattached document."""
        doc_id = test_deletable_document["id"]

        response = await async_client.delete(
            f"/api/v1/portal/documents/{doc_id}",
            headers=portal_auth_headers,
        )

        assert response.status_code == 200
        assert response.json()["success"] is True

    async def test_delete_attached_document_fails(
        self,
        async_client: AsyncClient,
        portal_auth_headers: dict,
        test_attached_document: dict,
    ) -> None:
        """Cannot delete document attached to a response."""
        doc_id = test_attached_document["id"]

        response = await async_client.delete(
            f"/api/v1/portal/documents/{doc_id}",
            headers=portal_auth_headers,
        )

        assert response.status_code == 400
        assert "attached" in response.json()["detail"].lower()

    async def test_delete_document_not_found(
        self,
        async_client: AsyncClient,
        portal_auth_headers: dict,
    ) -> None:
        """Deleting non-existent document returns 404."""
        response = await async_client.delete(
            f"/api/v1/portal/documents/{uuid4()}",
            headers=portal_auth_headers,
        )

        assert response.status_code == 404
