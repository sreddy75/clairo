"""Portal dependencies re-export.

The canonical location is app.modules.portal.auth.dependencies.
This module re-exports for backwards compatibility with push notification router.
"""

from app.modules.portal.auth.dependencies import (
    CurrentPortalSession,
    get_current_portal_session,
)

__all__ = ["CurrentPortalSession", "get_current_portal_session"]
