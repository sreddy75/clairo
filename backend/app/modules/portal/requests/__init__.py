"""Portal requests module.

Provides document request functionality for the client portal:
- Request templates (system and custom)
- Document request creation and management
- Bulk request operations
- Request tracking and events

Spec: 030-client-portal-document-requests
"""

from app.modules.portal.requests.router import requests_router, router
from app.modules.portal.requests.service import DocumentRequestService
from app.modules.portal.requests.templates import SYSTEM_TEMPLATES, get_system_templates

__all__ = [
    "SYSTEM_TEMPLATES",
    "DocumentRequestService",
    "get_system_templates",
    "requests_router",
    "router",
]
