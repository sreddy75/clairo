"""Test factories for Xero integration models.

Provides factory_boy factories for:
- XeroConnectionFactory
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import factory

from app.modules.integrations.xero.models import (
    XeroConnection,
    XeroConnectionStatus,
    XeroConnectionType,
)


class XeroConnectionFactory(factory.Factory):
    """Factory for XeroConnection model."""

    class Meta:
        model = XeroConnection

    id = factory.LazyFunction(uuid4)
    tenant_id = factory.LazyFunction(uuid4)
    xero_tenant_id = factory.LazyFunction(lambda: f"xero-{uuid4().hex[:16]}")
    organization_name = factory.Faker("company")
    status = XeroConnectionStatus.ACTIVE
    connection_type = XeroConnectionType.CLIENT
    access_token = factory.LazyFunction(lambda: f"access-{uuid4().hex}")
    refresh_token = factory.LazyFunction(lambda: f"refresh-{uuid4().hex}")
    token_expires_at = factory.LazyFunction(lambda: datetime.now(timezone.utc) + timedelta(hours=1))
    scopes = ["openid", "profile", "email", "accounting.transactions"]
    rate_limit_daily_remaining = 5000
    rate_limit_minute_remaining = 60
    connected_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    has_payroll_access = False
    sync_in_progress = False


class ActiveXeroConnectionFactory(XeroConnectionFactory):
    """Factory for an active Xero connection."""

    status = XeroConnectionStatus.ACTIVE


class InactiveXeroConnectionFactory(XeroConnectionFactory):
    """Factory for an inactive (disconnected) Xero connection."""

    status = XeroConnectionStatus.DISCONNECTED


class NeedsReauthXeroConnectionFactory(XeroConnectionFactory):
    """Factory for a Xero connection needing reauthorization."""

    status = XeroConnectionStatus.NEEDS_REAUTH
