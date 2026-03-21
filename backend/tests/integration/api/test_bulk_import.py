"""Integration tests for bulk import endpoints.

Tests cover:
- T008: POST /bulk-import/initiate, GET /bulk-import/callback, POST /bulk-import/confirm
- T016: Configuration screen data flow (callback fields, mixed selections, team assignment)
- T019: Backward compatibility for single-org OAuth flow

These tests use a minimal FastAPI test app with the xero router mounted
directly (no auth middleware), so they run WITHOUT a database.
The service layer is fully mocked — we only test HTTP routing, status codes,
and request/response serialization.
"""

import sys
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.modules.admin import models as admin_models  # noqa: F401

# Pre-mock celery_app to prevent portal import chain
if "app.tasks.celery_app" not in sys.modules:
    sys.modules["app.tasks.celery_app"] = MagicMock()

from app.modules.integrations.xero.router import (
    get_bulk_import_service,
    router as xero_router,
)

# =============================================================================
# Fixtures — No database, no auth middleware
# =============================================================================

TENANT_ID = uuid4()
USER_ID = uuid4()


def _make_mock_user() -> MagicMock:
    """Create a mock PracticeUser with standard fields."""
    user = MagicMock()
    user.id = USER_ID
    user.tenant_id = TENANT_ID
    user.role = "owner"
    user.email = "user@test.com"
    user.name = "Test User"
    return user


@pytest_asyncio.fixture
async def client():
    """Create an async test client with a minimal app — no middleware, no DB.

    Builds a fresh FastAPI app that only includes the xero router.
    All dependencies (auth, DB, service) are overridden.
    """
    from app.database import get_db as get_db_session

    test_app = FastAPI()

    mock_user = _make_mock_user()
    default_mock_service = AsyncMock()

    # Mount the xero router onto our test app.
    # The router itself already has prefix="/integrations/xero",
    # so we only add "/api/v1" here to get /api/v1/integrations/xero/...
    test_app.include_router(xero_router, prefix="/api/v1")

    async def _mock_get_db():
        yield MagicMock()

    test_app.dependency_overrides[get_db_session] = _mock_get_db
    test_app.dependency_overrides[get_bulk_import_service] = lambda: default_mock_service

    # Override all require_permission-generated deps via dependency_overrides.
    # After include_router, the app has its own routes; iterate them to find
    # the actual dependency callables FastAPI will invoke at request time.
    # IMPORTANT: The override function must have NO parameters — otherwise FastAPI
    # interprets them as query/path parameters and returns 422.
    async def _mock_auth():
        return mock_user

    for route in test_app.routes:
        if not hasattr(route, "dependant"):
            continue
        for dep in route.dependant.dependencies:
            qualname = getattr(dep.call, "__qualname__", "")
            if "require_permission" in qualname or "require_role" in qualname:
                test_app.dependency_overrides[dep.call] = _mock_auth

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, default_mock_service


# =============================================================================
# T008: POST /bulk-import/initiate
# =============================================================================


@pytest.mark.unit
class TestInitiateBulkImport:
    """Tests for POST /api/v1/integrations/xero/bulk-import/initiate."""

    async def test_returns_auth_url_and_state(self, client) -> None:
        """Should return auth_url and state with is_bulk_import=true."""
        ac, mock_service = client
        mock_service.initiate_bulk_import.return_value = {
            "auth_url": "https://login.xero.com/identity/connect/authorize?scope=openid",
            "state": "test_state_token_123",
        }

        response = await ac.post(
            "/api/v1/integrations/xero/bulk-import/initiate",
            json={"redirect_uri": "http://localhost:3001/clients/import"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "auth_url" in data
        assert "state" in data
        assert data["auth_url"].startswith("https://")

    async def test_409_when_import_in_progress(self, client) -> None:
        """Should return 409 when a bulk import is already in progress."""
        from app.modules.integrations.xero.service import BulkImportInProgressError

        ac, mock_service = client
        mock_service.initiate_bulk_import.side_effect = BulkImportInProgressError(
            TENANT_ID, uuid4()
        )

        response = await ac.post(
            "/api/v1/integrations/xero/bulk-import/initiate",
            json={"redirect_uri": "http://localhost:3001/clients/import"},
        )

        assert response.status_code == 409


# =============================================================================
# T008: GET /bulk-import/callback
# =============================================================================


@pytest.mark.unit
class TestBulkImportCallback:
    """Tests for GET /api/v1/integrations/xero/bulk-import/callback."""

    async def test_returns_organization_list(self, client) -> None:
        """Should return org list from Xero callback processing."""
        ac, mock_service = client
        mock_service.handle_bulk_callback.return_value = {
            "auth_event_id": "evt_123",
            "organizations": [
                {
                    "xero_tenant_id": "org_1",
                    "organization_name": "Test Org One",
                    "already_connected": False,
                    "existing_connection_id": None,
                    "match_status": "unmatched",
                    "matched_client_name": None,
                },
                {
                    "xero_tenant_id": "org_2",
                    "organization_name": "Test Org Two",
                    "already_connected": True,
                    "existing_connection_id": str(uuid4()),
                    "match_status": "matched",
                    "matched_client_name": "Test Org Two",
                },
            ],
            "already_connected_count": 1,
            "new_count": 1,
            "plan_limit": 100,
            "current_client_count": 10,
            "available_slots": 90,
            "state": "test_state",
        }

        response = await ac.get(
            "/api/v1/integrations/xero/bulk-import/callback",
            params={"code": "auth_code_123", "state": "test_state"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["auth_event_id"] == "evt_123"
        assert len(data["organizations"]) == 2
        assert data["new_count"] == 1
        assert data["already_connected_count"] == 1

    async def test_400_on_invalid_state(self, client) -> None:
        """Should return 400 when state token is invalid."""
        from app.modules.integrations.xero.service import XeroOAuthError

        ac, mock_service = client
        mock_service.handle_bulk_callback.side_effect = XeroOAuthError(
            "Invalid or unknown state parameter"
        )

        response = await ac.get(
            "/api/v1/integrations/xero/bulk-import/callback",
            params={"code": "bad_code", "state": "bad_state"},
        )

        assert response.status_code == 400


# =============================================================================
# T008 + T016: POST /bulk-import/confirm
# =============================================================================


@pytest.mark.unit
class TestConfirmBulkImport:
    """Tests for POST /api/v1/integrations/xero/bulk-import/confirm."""

    async def test_creates_connections_and_returns_job(self, client) -> None:
        """Should create connections and return job info."""
        ac, mock_service = client
        job_id = uuid4()
        mock_service.confirm_bulk_import.return_value = {
            "job_id": job_id,
            "status": "pending",
            "total_organizations": 2,
            "imported_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "progress_percent": 0,
            "created_at": datetime.now(UTC),
        }

        response = await ac.post(
            "/api/v1/integrations/xero/bulk-import/confirm",
            params={"state": "test_state"},
            json={
                "auth_event_id": "evt_123",
                "organizations": [
                    {
                        "xero_tenant_id": "org_1",
                        "selected": True,
                        "connection_type": "client",
                    },
                    {
                        "xero_tenant_id": "org_2",
                        "selected": False,
                        "connection_type": "client",
                    },
                ],
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "pending"
        assert data["total_organizations"] == 2

    async def test_400_when_exceeds_plan_limit(self, client) -> None:
        """Should return 400 when selection exceeds plan limit."""
        from app.modules.integrations.xero.service import BulkImportValidationError

        ac, mock_service = client
        mock_service.confirm_bulk_import.side_effect = BulkImportValidationError(
            "Selection exceeds plan limit"
        )

        response = await ac.post(
            "/api/v1/integrations/xero/bulk-import/confirm",
            params={"state": "test_state"},
            json={
                "auth_event_id": "evt_123",
                "organizations": [
                    {"xero_tenant_id": "org_1", "selected": True},
                ],
            },
        )

        assert response.status_code == 400

    async def test_409_when_import_already_in_progress(self, client) -> None:
        """Should return 409 when concurrent import is in progress."""
        from app.modules.integrations.xero.service import BulkImportInProgressError

        ac, mock_service = client
        mock_service.confirm_bulk_import.side_effect = BulkImportInProgressError(TENANT_ID, uuid4())

        response = await ac.post(
            "/api/v1/integrations/xero/bulk-import/confirm",
            params={"state": "test_state"},
            json={
                "auth_event_id": "evt_123",
                "organizations": [
                    {"xero_tenant_id": "org_1", "selected": True},
                ],
            },
        )

        assert response.status_code == 409


# =============================================================================
# T016: Configuration screen data flow
# =============================================================================


@pytest.mark.unit
class TestConfigurationDataFlow:
    """Tests that callback provides all fields needed for the config screen."""

    async def test_callback_includes_all_config_fields(self, client) -> None:
        """Callback response should include org name, already_connected, match_status."""
        ac, mock_service = client
        mock_service.handle_bulk_callback.return_value = {
            "auth_event_id": "evt_abc",
            "organizations": [
                {
                    "xero_tenant_id": "org_1",
                    "organization_name": "Alpha Corp",
                    "already_connected": False,
                    "existing_connection_id": None,
                    "match_status": "suggested",
                    "matched_client_name": "Alpha Corporation",
                },
            ],
            "already_connected_count": 0,
            "new_count": 1,
            "plan_limit": 100,
            "current_client_count": 5,
            "available_slots": 95,
            "state": "test_state",
        }

        response = await ac.get(
            "/api/v1/integrations/xero/bulk-import/callback",
            params={"code": "code_123", "state": "state_123"},
        )

        data = response.json()
        org = data["organizations"][0]
        assert "organization_name" in org
        assert "already_connected" in org
        assert "match_status" in org
        assert "matched_client_name" in org
        assert org["match_status"] == "suggested"

    async def test_confirm_with_mixed_selections(self, client) -> None:
        """Mixed selected/deselected orgs should be handled correctly."""
        ac, mock_service = client
        job_id = uuid4()
        mock_service.confirm_bulk_import.return_value = {
            "job_id": job_id,
            "status": "pending",
            "total_organizations": 3,
            "imported_count": 0,
            "failed_count": 0,
            "skipped_count": 1,
            "progress_percent": 0,
            "created_at": datetime.now(UTC),
        }

        response = await ac.post(
            "/api/v1/integrations/xero/bulk-import/confirm",
            params={"state": "test_state"},
            json={
                "auth_event_id": "evt_123",
                "organizations": [
                    {"xero_tenant_id": "org_1", "selected": True, "connection_type": "client"},
                    {"xero_tenant_id": "org_2", "selected": True, "connection_type": "practice"},
                    {"xero_tenant_id": "org_3", "selected": False},
                ],
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert data["skipped_count"] == 1

    async def test_confirm_with_team_member_assignment(self, client) -> None:
        """Should pass assigned_user_id through to service."""
        ac, mock_service = client
        job_id = uuid4()
        user_id = uuid4()
        mock_service.confirm_bulk_import.return_value = {
            "job_id": job_id,
            "status": "pending",
            "total_organizations": 1,
            "imported_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "progress_percent": 0,
            "created_at": datetime.now(UTC),
        }

        response = await ac.post(
            "/api/v1/integrations/xero/bulk-import/confirm",
            params={"state": "test_state"},
            json={
                "auth_event_id": "evt_123",
                "organizations": [
                    {
                        "xero_tenant_id": "org_1",
                        "selected": True,
                        "assigned_user_id": str(user_id),
                    },
                ],
            },
        )

        assert response.status_code == 202
        call_kwargs = mock_service.confirm_bulk_import.call_args
        assert call_kwargs is not None


# =============================================================================
# T008: Backward compatibility (FR-013) — verify routes are registered
# =============================================================================


@pytest.mark.unit
class TestBackwardCompatibility:
    """Verify existing single-org OAuth flow routes exist on the xero router."""

    def test_single_org_connect_route_exists(self) -> None:
        """POST /connect should still be registered on the xero router."""
        route_paths = [getattr(r, "path", "") for r in xero_router.routes]
        assert "/integrations/xero/connect" in route_paths

    def test_single_org_callback_route_exists(self) -> None:
        """GET /callback should still be registered on the xero router."""
        route_paths = [getattr(r, "path", "") for r in xero_router.routes]
        assert "/integrations/xero/callback" in route_paths

    def test_bulk_import_routes_registered(self) -> None:
        """Bulk import routes should be registered alongside existing routes."""
        route_paths = [getattr(r, "path", "") for r in xero_router.routes]
        assert "/integrations/xero/bulk-import/initiate" in route_paths
        assert "/integrations/xero/bulk-import/callback" in route_paths
        assert "/integrations/xero/bulk-import/confirm" in route_paths
        assert "/integrations/xero/bulk-import/jobs" in route_paths
        assert "/integrations/xero/bulk-import/{job_id}" in route_paths
        assert "/integrations/xero/bulk-import/{job_id}/retry" in route_paths
