"""Triggers module for proactive insight generation.

This module provides event/time-based triggers that automatically
generate insights without manual intervention.
"""

from app.modules.triggers.models import (
    Trigger,
    TriggerExecution,
    TriggerStatus,
    TriggerType,
)
from app.modules.triggers.router import router
from app.modules.triggers.service import TriggerService

__all__ = [
    "Trigger",
    "TriggerExecution",
    "TriggerService",
    "TriggerStatus",
    "TriggerType",
    "router",
]
