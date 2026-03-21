"""Audit events for onboarding flow.

Defines event types for onboarding actions that require audit logging.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass
class OnboardingEvent:
    """Base class for onboarding audit events."""

    tenant_id: UUID
    user_id: UUID | None = None


@dataclass
class OnboardingStartedEvent(OnboardingEvent):
    """Event when onboarding is started."""

    event_type: str = "onboarding.started"


@dataclass
class TierSelectedEvent(OnboardingEvent):
    """Event when subscription tier is selected."""

    tier: str = ""
    event_type: str = "onboarding.tier_selected"


@dataclass
class TrialStartedEvent(OnboardingEvent):
    """Event when trial subscription starts."""

    tier: str = ""
    trial_days: int = 14
    event_type: str = "onboarding.trial_started"


@dataclass
class PaymentSetupEvent(OnboardingEvent):
    """Event when payment method is set up."""

    stripe_session_id: str = ""
    event_type: str = "onboarding.payment_setup"


@dataclass
class XeroConnectedEvent(OnboardingEvent):
    """Event when Xero is connected."""

    connection_type: str = ""  # "xpm" or "xero_accounting"
    organization_name: str = ""
    event_type: str = "onboarding.xero_connected"


@dataclass
class XeroSkippedEvent(OnboardingEvent):
    """Event when Xero connection is skipped."""

    event_type: str = "onboarding.xero_skipped"


@dataclass
class BulkImportStartedEvent(OnboardingEvent):
    """Event when bulk client import starts."""

    job_id: UUID | None = None
    client_count: int = 0
    source_type: str = ""
    event_type: str = "onboarding.bulk_import_started"


@dataclass
class BulkImportCompletedEvent(OnboardingEvent):
    """Event when bulk client import completes."""

    job_id: UUID | None = None
    imported_count: int = 0
    failed_count: int = 0
    event_type: str = "onboarding.bulk_import_completed"


@dataclass
class TourCompletedEvent(OnboardingEvent):
    """Event when product tour is completed."""

    skipped: bool = False
    event_type: str = "onboarding.tour_completed"


@dataclass
class OnboardingCompletedEvent(OnboardingEvent):
    """Event when onboarding is fully complete."""

    event_type: str = "onboarding.completed"


@dataclass
class ChecklistDismissedEvent(OnboardingEvent):
    """Event when onboarding checklist is dismissed."""

    event_type: str = "onboarding.checklist_dismissed"
