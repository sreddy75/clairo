"""Portal dashboard module.

Provides the client dashboard with BAS status and pending items.
"""

from app.modules.portal.dashboard.router import router
from app.modules.portal.dashboard.service import PortalDashboardService

__all__ = [
    "PortalDashboardService",
    "router",
]
