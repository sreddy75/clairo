"""Dashboard module for multi-client BAS overview."""

from app.modules.dashboard.router import router
from app.modules.dashboard.service import DashboardService

__all__ = ["DashboardService", "router"]
