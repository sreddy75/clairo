"""Billing middleware for subscription access gating.

Provides a FastAPI dependency that blocks write operations
when a tenant's subscription is suspended or cancelled.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.core.dependencies import get_current_tenant
from app.modules.auth.models import Tenant


async def require_active_subscription(
    tenant: Annotated[Tenant, Depends(get_current_tenant)],
) -> None:
    """FastAPI dependency that requires an active subscription.

    Allows access for TRIAL, ACTIVE, PAST_DUE, and GRANDFATHERED statuses.
    Blocks access for SUSPENDED and CANCELLED statuses with a 403 response.

    Usage:
        @router.post("/endpoint")
        async def endpoint(
            _sub: None = Depends(require_active_subscription),
        ):
            ...
    """
    if not tenant.can_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "SUBSCRIPTION_REQUIRED",
                "message": "Your subscription is inactive. Please update your billing to continue.",
                "details": {
                    "subscription_status": tenant.subscription_status.value,
                    "billing_url": "/settings/billing",
                },
            },
        )
