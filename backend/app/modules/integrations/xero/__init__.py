"""Xero integration module.

Provides OAuth 2.0 authentication and API client for Xero accounting software.

Components:
- router: API endpoints for OAuth flow and connection management
- service: Business logic for connections and token management
- repository: Database operations for connections and OAuth states
- models: SQLAlchemy models (XeroConnection, XeroOAuthState, XpmClient, XeroReport)
- schemas: Pydantic request/response schemas
- oauth: PKCE flow utilities
- client: Xero API HTTP client
- rate_limiter: Rate limit tracking and enforcement
- encryption: Token encryption/decryption
- audit_events: Audit event definitions
"""

from app.modules.integrations.xero.models import (
    XeroConnection,
    XeroConnectionStatus,
    XeroConnectionType,
    XeroReport,
    XeroReportSyncJob,
    XeroReportSyncStatus,
    XeroReportType,
    XpmClient,
    XpmClientConnectionStatus,
)

__all__ = [
    "XeroConnection",
    "XeroConnectionStatus",
    "XeroConnectionType",
    "XeroReport",
    "XeroReportSyncJob",
    "XeroReportSyncStatus",
    "XeroReportType",
    "XpmClient",
    "XpmClientConnectionStatus",
]
