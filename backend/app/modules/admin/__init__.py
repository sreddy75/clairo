"""Admin module for platform-level operations.

Provides administrative functionality for platform operators including:
- Aggregate usage statistics across tenants
- Upsell opportunity identification
- Tenant usage details

Spec 020: Usage Tracking & Limits
"""

from app.modules.admin.router import router
from app.modules.admin.usage_service import AdminUsageService

__all__ = ["AdminUsageService", "router"]
