"""Test factories for Xero integration models.

Provides factory_boy factories for:
- XeroConnectionFactory
- XeroWritebackJobFactory
- XeroWritebackItemFactory
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import factory

from app.modules.integrations.xero.models import (
    XeroConnection,
    XeroConnectionStatus,
    XeroConnectionType,
)
from app.modules.integrations.xero.writeback_models import (
    XeroWritebackItem,
    XeroWritebackItemStatus,
    XeroWritebackJob,
    XeroWritebackJobStatus,
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


class XeroWritebackJobFactory(factory.Factory):
    """Factory for XeroWritebackJob model."""

    class Meta:
        model = XeroWritebackJob

    id = factory.LazyFunction(uuid4)
    tenant_id = factory.LazyFunction(uuid4)
    connection_id = factory.LazyFunction(uuid4)
    session_id = factory.LazyFunction(uuid4)
    triggered_by = None
    status = XeroWritebackJobStatus.COMPLETED
    total_count = 1
    succeeded_count = 1
    skipped_count = 0
    failed_count = 0
    started_at = None
    completed_at = None
    duration_seconds = None
    error_detail = None
    created_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    updated_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))


class XeroWritebackItemFactory(factory.Factory):
    """Factory for XeroWritebackItem model."""

    class Meta:
        model = XeroWritebackItem

    id = factory.LazyFunction(uuid4)
    tenant_id = factory.LazyFunction(uuid4)
    job_id = factory.LazyFunction(uuid4)
    source_type = "invoice"
    xero_document_id = factory.LazyFunction(lambda: str(uuid4()))
    local_document_id = factory.LazyFunction(uuid4)
    override_ids = factory.LazyFunction(list)
    line_item_indexes = factory.LazyFunction(list)
    before_tax_types = factory.LazyFunction(dict)
    after_tax_types = factory.LazyFunction(dict)
    status = XeroWritebackItemStatus.SUCCESS
    skip_reason = None
    error_detail = None
    xero_http_status = None
    processed_at = None
    created_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    updated_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
