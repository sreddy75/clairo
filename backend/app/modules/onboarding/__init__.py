"""Onboarding module for guiding new accountants through setup.

This module provides:
- Onboarding progress tracking
- Tier selection and Stripe checkout integration
- Xero/XPM connection flow
- Bulk client import with background processing
- Product tour management
- Onboarding checklist
- Welcome email drip sequence

Spec: 021-onboarding-flow
"""

from app.modules.onboarding.models import (
    BulkImportJob,
    BulkImportJobStatus,
    EmailDrip,
    EmailDripType,
    OnboardingProgress,
    OnboardingStatus,
)

# Note: router is imported separately in main.py to avoid circular dependencies
# from app.modules.onboarding.router import router

__all__ = [
    "BulkImportJob",
    "BulkImportJobStatus",
    "EmailDrip",
    "EmailDripType",
    "OnboardingProgress",
    "OnboardingStatus",
]
