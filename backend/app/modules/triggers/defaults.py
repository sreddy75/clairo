"""Default trigger configurations for new tenants.

These triggers are automatically seeded when a new tenant is created,
providing a baseline of proactive insight generation without manual
configuration.

All default triggers are marked as `is_system_default=True` and cannot
be deleted (only disabled).
"""

from __future__ import annotations

from typing import Any

from app.modules.triggers.models import TriggerType

# Default triggers seeded for all tenants
DEFAULT_TRIGGERS: list[dict[str, Any]] = [
    # ==========================================================================
    # Data Threshold Triggers
    # Fire when metrics cross specific thresholds (evaluated after Xero sync)
    # ==========================================================================
    {
        "name": "GST Registration Threshold Alert",
        "description": (
            "Alerts when a client's year-to-date revenue approaches or exceeds "
            "the $75,000 GST registration threshold. Early warning helps ensure "
            "timely GST registration and compliance."
        ),
        "trigger_type": TriggerType.DATA_THRESHOLD,
        "config": {
            "metric": "revenue_ytd",
            "operator": "gte",
            "threshold": 75000,
        },
        "target_analyzers": ["compliance"],
        "dedup_window_hours": 168,  # 7 days
    },
    {
        "name": "Cash Flow Warning - Overdue Receivables",
        "description": (
            "Triggers when total overdue accounts receivable exceeds $20,000. "
            "Helps identify clients who may face cash flow issues due to "
            "slow-paying customers."
        ),
        "trigger_type": TriggerType.DATA_THRESHOLD,
        "config": {
            "metric": "ar_overdue_total",
            "operator": "gte",
            "threshold": 20000,
        },
        "target_analyzers": ["cash_flow"],
        "dedup_window_hours": 72,  # 3 days
    },
    {
        "name": "Data Quality Alert - Unreconciled Transactions",
        "description": (
            "Fires when a client has 10 or more unreconciled bank transactions. "
            "Helps maintain data quality and ensures accurate reporting."
        ),
        "trigger_type": TriggerType.DATA_THRESHOLD,
        "config": {
            "metric": "unreconciled_count",
            "operator": "gte",
            "threshold": 10,
        },
        "target_analyzers": ["quality"],
        "dedup_window_hours": 24,  # 1 day
    },
    # ==========================================================================
    # Time-Scheduled Triggers
    # Fire on a schedule (evaluated by Celery Beat)
    # ==========================================================================
    {
        "name": "Daily Insight Generation",
        "description": (
            "Generates insights for all clients daily at 6am Sydney time. "
            "Ensures accountants start their day with fresh insights even "
            "if individual client syncs haven't triggered."
        ),
        "trigger_type": TriggerType.TIME_SCHEDULED,
        "config": {
            "cron": "0 6 * * *",  # 6am daily
            "timezone": "Australia/Sydney",
        },
        "target_analyzers": ["cash_flow", "quality", "compliance"],
        "dedup_window_hours": 24,  # 1 day
    },
    {
        "name": "BAS Deadline Reminder",
        "description": (
            "Checks for approaching BAS deadlines at 9am daily. "
            "Generates compliance insights for clients with deadlines "
            "within 14 days to ensure timely lodgement."
        ),
        "trigger_type": TriggerType.TIME_SCHEDULED,
        "config": {
            "cron": "0 9 * * *",  # 9am daily
            "timezone": "Australia/Sydney",
            "days_before_deadline": 14,
        },
        "target_analyzers": ["compliance"],
        "dedup_window_hours": 168,  # 7 days
    },
    # ==========================================================================
    # Event-Based Triggers
    # Fire when specific business events occur
    # ==========================================================================
    {
        "name": "New Client Welcome Analysis",
        "description": (
            "Runs a comprehensive analysis when a new Xero connection is "
            "established. Provides initial insights for new clients covering "
            "cash flow, data quality, and compliance status."
        ),
        "trigger_type": TriggerType.EVENT_BASED,
        "config": {
            "event": "xero_connection_created",
        },
        "target_analyzers": ["cash_flow", "quality", "compliance"],
        "dedup_window_hours": 0,  # Always run for new clients
    },
    {
        "name": "Post-Lodgement Review",
        "description": (
            "Generates a compliance review insight after a BAS has been lodged. "
            "Helps track lodgement patterns and identify any follow-up actions."
        ),
        "trigger_type": TriggerType.EVENT_BASED,
        "config": {
            "event": "bas_lodged",
        },
        "target_analyzers": ["compliance"],
        "dedup_window_hours": 0,  # Always run after lodgement
    },
]
