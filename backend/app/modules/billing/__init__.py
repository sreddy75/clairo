"""Billing module for subscription management and feature gating.

This module provides:
- Stripe integration for payment processing
- Subscription tier management
- Feature gating and client limits
- Billing event tracking
"""

from app.modules.billing.exceptions import (
    ClientLimitExceededError,
    FeatureNotAvailableError,
    InvalidTierChangeError,
    SubscriptionError,
)
from app.modules.billing.models import BillingEvent, BillingEventStatus
from app.modules.billing.router import router as billing_router

__all__ = [
    "BillingEvent",
    "BillingEventStatus",
    "ClientLimitExceededError",
    "FeatureNotAvailableError",
    "InvalidTierChangeError",
    "SubscriptionError",
    "billing_router",
]
