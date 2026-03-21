"""
Portal Module - Client Portal Foundation + Document Requests (ClientChase)

This module provides:
- Magic link authentication for business owner clients
- Client dashboard with BAS status and metrics
- Document request workflow (ClientChase)
- Bulk document requests
- Auto-reminders and notifications
- Document upload and auto-filing

Spec: 030-client-portal-document-requests
"""

from app.modules.portal.auth import auth_router
from app.modules.portal.enums import (
    ActorType,
    BulkRequestStatus,
    InvitationStatus,
    RequestEventType,
    RequestPriority,
    RequestStatus,
    ScanStatus,
)
from app.modules.portal.models import (
    BulkRequest,
    DocumentRequest,
    DocumentRequestTemplate,
    PortalDocument,
    PortalInvitation,
    PortalSession,
    RequestEvent,
    RequestResponse,
)
from app.modules.portal.router import client_router, router

__all__ = [
    # Routers
    "router",
    "client_router",
    "auth_router",
    # Models
    "PortalInvitation",
    "PortalSession",
    "DocumentRequestTemplate",
    "DocumentRequest",
    "RequestResponse",
    "PortalDocument",
    "RequestEvent",
    "BulkRequest",
    # Enums
    "InvitationStatus",
    "RequestStatus",
    "RequestPriority",
    "RequestEventType",
    "ActorType",
    "BulkRequestStatus",
    "ScanStatus",
]
