"""Portal authentication module.

Provides magic link authentication for business owner clients.
"""

from app.modules.portal.auth.dependencies import (
    CurrentPortalClient,
    OptionalPortalClient,
    PortalClient,
    get_current_portal_client,
    get_optional_portal_client,
)
from app.modules.portal.auth.magic_link import MagicLinkService
from app.modules.portal.auth.router import router as auth_router

__all__ = [
    # Service
    "MagicLinkService",
    # Dependencies
    "get_current_portal_client",
    "get_optional_portal_client",
    "PortalClient",
    "CurrentPortalClient",
    "OptionalPortalClient",
    # Router
    "auth_router",
]
