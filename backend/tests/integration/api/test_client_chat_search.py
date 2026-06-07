"""Integration tests for the AI Assistant client search endpoint.

Covers GET /api/v1/knowledge/client-chat/clients/search.

Regression context: the search originally queried XeroConnection directly with
a strict ``status == "active"`` filter, so clients whose Xero connection was in
``needs_reauth`` (still shown in the dashboard) silently disappeared from the
assistant. The search now drives off PracticeClient (the authoritative client
list) joined to XeroConnection, with no status filter — matching the dashboard.

Auth comes from the shared ``auth_headers`` / ``auth_tenant`` fixtures in
tests/integration/api/conftest.py; the ``test_client`` fixture patches Clerk
token validation to accept the HS256 test token.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import SubscriptionStatus, SubscriptionTier, Tenant
from app.modules.clients.models import PracticeClient
from app.modules.integrations.xero.models import (
    XeroConnection,
    XeroConnectionStatus,
    XeroConnectionType,
)

SEARCH_URL = "/api/v1/knowledge/client-chat/clients/search"


async def _make_xero_client(
    db_session: AsyncSession,
    tenant_id: UUID,
    *,
    name: str,
    org_name: str,
    status: XeroConnectionStatus,
) -> tuple[PracticeClient, XeroConnection]:
    """Create a PracticeClient backed by a XeroConnection with ``status``."""
    conn = XeroConnection(
        id=uuid4(),
        tenant_id=tenant_id,
        xero_tenant_id=f"xero-{uuid4().hex[:16]}",
        organization_name=org_name,
        status=status,
        connection_type=XeroConnectionType.CLIENT,
        access_token=f"access-{uuid4().hex}",
        refresh_token=f"refresh-{uuid4().hex}",
        token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        scopes=["openid", "profile", "accounting.transactions"],
    )
    db_session.add(conn)
    await db_session.flush()

    client = PracticeClient(
        id=uuid4(),
        tenant_id=tenant_id,
        name=name,
        accounting_software="xero",
        xero_connection_id=conn.id,
    )
    db_session.add(client)
    await db_session.flush()
    return client, conn


@pytest.mark.integration
class TestClientChatSearch:
    """Tests for the assistant 'Select a Client' search."""

    async def test_needs_reauth_client_is_returned(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
        auth_tenant: Tenant,
        auth_headers: dict[str, str],
    ) -> None:
        """Regression: a client whose connection needs re-auth must still appear.

        This is the bug that produced 'No clients found' for clients that were
        visible in the dashboard.
        """
        await _make_xero_client(
            db_session,
            auth_tenant.id,
            name="KR8 Active Pty Ltd",
            org_name="KR8 Active (Xero)",
            status=XeroConnectionStatus.ACTIVE,
        )
        _, reauth_conn = await _make_xero_client(
            db_session,
            auth_tenant.id,
            name="KR8 Stale Pty Ltd",
            org_name="KR8 Stale (Xero)",
            status=XeroConnectionStatus.NEEDS_REAUTH,
        )

        response = await test_client.get(SEARCH_URL, params={"q": "kr8"}, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        names = {r["name"] for r in data["results"]}
        assert names == {"KR8 Active Pty Ltd", "KR8 Stale Pty Ltd"}

        # The needs_reauth client is present and flagged inactive.
        reauth_result = next(r for r in data["results"] if r["name"] == "KR8 Stale Pty Ltd")
        assert reauth_result["is_active"] is False
        # id/connection_id stay the XeroConnection id (downstream chat contract).
        assert reauth_result["id"] == str(reauth_conn.id)
        assert reauth_result["connection_id"] == str(reauth_conn.id)

    async def test_search_matches_practice_client_name(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
        auth_tenant: Tenant,
        auth_headers: dict[str, str],
    ) -> None:
        """Search matches the PracticeClient name, not the Xero org name."""
        await _make_xero_client(
            db_session,
            auth_tenant.id,
            name="Renamed Client Pty Ltd",
            org_name="Old Xero Org Name",
            status=XeroConnectionStatus.ACTIVE,
        )

        # Matches the practice-client name...
        match = await test_client.get(SEARCH_URL, params={"q": "renamed"}, headers=auth_headers)
        assert match.status_code == 200
        assert match.json()["total"] == 1

        # ...and does not leak via the stale Xero org name.
        no_match = await test_client.get(SEARCH_URL, params={"q": "old xero"}, headers=auth_headers)
        assert no_match.status_code == 200
        assert no_match.json()["total"] == 0

    async def test_non_xero_client_is_excluded(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
        auth_tenant: Tenant,
        auth_headers: dict[str, str],
    ) -> None:
        """Manually-added (non-Xero) clients have no connection and are skipped.

        The client-context chat pipeline keys on XeroConnection.id, so a client
        with no connection can't be chatted and must not be selectable here.
        """
        manual_client = PracticeClient(
            id=uuid4(),
            tenant_id=auth_tenant.id,
            name="Manual Only Pty Ltd",
            accounting_software="myob",
            xero_connection_id=None,
        )
        db_session.add(manual_client)
        await db_session.flush()

        response = await test_client.get(SEARCH_URL, params={"q": "manual"}, headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["total"] == 0

    async def test_other_tenant_clients_not_returned(
        self,
        test_client: AsyncClient,
        db_session: AsyncSession,
        auth_tenant: Tenant,
        auth_headers: dict[str, str],
    ) -> None:
        """Search is scoped to the caller's tenant."""
        other_tenant = Tenant(
            id=uuid4(),
            name="Other Practice",
            slug=f"other-{uuid4().hex[:8]}",
            tier=SubscriptionTier.STARTER,
            subscription_status=SubscriptionStatus.ACTIVE,
            owner_email=f"other-{uuid4().hex[:8]}@test.com",
            client_count=0,
        )
        db_session.add(other_tenant)
        await db_session.flush()

        await _make_xero_client(
            db_session,
            other_tenant.id,
            name="KR8 Foreign Pty Ltd",
            org_name="KR8 Foreign (Xero)",
            status=XeroConnectionStatus.ACTIVE,
        )

        response = await test_client.get(SEARCH_URL, params={"q": "kr8"}, headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["total"] == 0
