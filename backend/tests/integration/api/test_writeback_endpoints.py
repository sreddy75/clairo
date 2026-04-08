"""Integration tests for Xero write-back API endpoints.

Spec 049: Xero Tax Code Write-Back.
Tests cover:
- Auth guards (401) on all four writeback endpoints
"""

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.integration
class TestWritebackAuthGuards:
    """Auth guard tests — all writeback endpoints require authentication."""

    async def test_trigger_writeback_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        connection_id = uuid.uuid4()
        session_id = uuid.uuid4()
        response = await test_client.post(
            f"/api/v1/clients/{connection_id}/bas/sessions/{session_id}/writeback"
        )
        assert response.status_code == 401

    async def test_list_writeback_jobs_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        connection_id = uuid.uuid4()
        session_id = uuid.uuid4()
        response = await test_client.get(
            f"/api/v1/clients/{connection_id}/bas/sessions/{session_id}/writeback/jobs"
        )
        assert response.status_code == 401

    async def test_get_writeback_job_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        connection_id = uuid.uuid4()
        session_id = uuid.uuid4()
        job_id = uuid.uuid4()
        response = await test_client.get(
            f"/api/v1/clients/{connection_id}/bas/sessions/{session_id}/writeback/jobs/{job_id}"
        )
        assert response.status_code == 401

    async def test_retry_writeback_job_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        connection_id = uuid.uuid4()
        session_id = uuid.uuid4()
        job_id = uuid.uuid4()
        response = await test_client.post(
            f"/api/v1/clients/{connection_id}/bas/sessions/{session_id}/writeback/jobs/{job_id}/retry"
        )
        assert response.status_code == 401
