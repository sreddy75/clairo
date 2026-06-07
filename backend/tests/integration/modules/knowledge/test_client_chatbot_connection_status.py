"""Regression tests for ClientContextChatbot.get_connection_status.

The method receives a XeroConnection id (every other chatbot method, and the
profile router, treat client_id as XeroConnection.id). It previously joined
XeroClient on ``XeroClient.id == client_id`` and read ``connection_status`` /
fields that don't exist on XeroConnection — so it never resolved a real
connection. It now looks the connection up directly by id.

The method only touches ``self.db``, so we instantiate the chatbot via
``__new__`` to avoid constructing its Anthropic/Pinecone/Voyage dependencies.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import SubscriptionStatus, SubscriptionTier, Tenant
from app.modules.integrations.xero.models import (
    XeroConnection,
    XeroConnectionStatus,
    XeroConnectionType,
)
from app.modules.knowledge.client_chatbot import ClientContextChatbot


def _chatbot(db_session: AsyncSession) -> ClientContextChatbot:
    """Build a chatbot bound only to the DB (skips heavy __init__ deps)."""
    bot = ClientContextChatbot.__new__(ClientContextChatbot)
    bot.db = db_session
    return bot


async def _make_connection(
    db_session: AsyncSession,
    *,
    org_name: str,
    status: XeroConnectionStatus,
    last_full_sync_at: datetime | None,
) -> XeroConnection:
    tenant = Tenant(
        id=uuid4(),
        name="Conn Status Practice",
        slug=f"conn-status-{uuid4().hex[:8]}",
        tier=SubscriptionTier.STARTER,
        subscription_status=SubscriptionStatus.ACTIVE,
        owner_email=f"owner-{uuid4().hex[:8]}@test.com",
        client_count=0,
    )
    db_session.add(tenant)
    await db_session.flush()

    conn = XeroConnection(
        id=uuid4(),
        tenant_id=tenant.id,
        xero_tenant_id=f"xero-{uuid4().hex[:16]}",
        organization_name=org_name,
        status=status,
        connection_type=XeroConnectionType.CLIENT,
        access_token=f"access-{uuid4().hex}",
        refresh_token=f"refresh-{uuid4().hex}",
        token_expires_at=datetime.now(timezone.utc),
        scopes=["openid"],
        last_full_sync_at=last_full_sync_at,
    )
    db_session.add(conn)
    await db_session.flush()
    return conn


@pytest.mark.integration
class TestGetConnectionStatus:
    """Tests for ClientContextChatbot.get_connection_status."""

    async def test_resolves_active_connection_by_id(self, db_session: AsyncSession) -> None:
        synced_at = datetime(2026, 6, 1, 9, 30, tzinfo=timezone.utc)
        conn = await _make_connection(
            db_session,
            org_name="Acme Pty Ltd",
            status=XeroConnectionStatus.ACTIVE,
            last_full_sync_at=synced_at,
        )

        result = await _chatbot(db_session).get_connection_status(conn.id)

        assert result["status"] == "active"
        assert result["organization_name"] == "Acme Pty Ltd"
        assert result["last_sync"] == synced_at.isoformat()
        assert result["needs_reauth"] is False

    async def test_flags_needs_reauth(self, db_session: AsyncSession) -> None:
        conn = await _make_connection(
            db_session,
            org_name="Stale Pty Ltd",
            status=XeroConnectionStatus.NEEDS_REAUTH,
            last_full_sync_at=None,
        )

        result = await _chatbot(db_session).get_connection_status(conn.id)

        assert result["status"] == "needs_reauth"
        assert result["needs_reauth"] is True
        assert result["last_sync"] is None

    async def test_unknown_id_returns_not_found(self, db_session: AsyncSession) -> None:
        result = await _chatbot(db_session).get_connection_status(uuid4())

        assert result["status"] == "not_found"
