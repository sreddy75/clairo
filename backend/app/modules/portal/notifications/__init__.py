"""Portal notifications module.

Provides email templates and notification services for the client portal.

Spec: 030-client-portal-document-requests
"""

from app.modules.portal.notifications.templates import PortalEmailTemplates

__all__ = ["PortalEmailTemplates"]
