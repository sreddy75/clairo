"""
A2UI Audit Logging

Provides audit logging for A2UI actions, tracking user interactions
with AI-generated interfaces for compliance and debugging.
"""

import logging
from typing import Any
from uuid import UUID

from pydantic import BaseModel

logger = logging.getLogger(__name__)


# =============================================================================
# A2UI Audit Event Types
# =============================================================================


class A2UIActionType:
    """A2UI-specific action types for audit logging."""

    # Navigation actions
    NAVIGATE = "a2ui.navigate"

    # Data actions
    EXPORT = "a2ui.export"
    FILTER = "a2ui.filter"
    SORT = "a2ui.sort"

    # Approval actions
    APPROVE = "a2ui.approve"
    REJECT = "a2ui.reject"
    QUERY = "a2ui.query"

    # Task actions
    CREATE_TASK = "a2ui.create_task"

    # Custom agent actions
    CUSTOM = "a2ui.custom"

    # Media actions
    CAPTURE = "a2ui.capture"
    UPLOAD = "a2ui.upload"


# =============================================================================
# A2UI Audit Models
# =============================================================================


class A2UIAuditContext(BaseModel):
    """Context information for A2UI audit events."""

    message_id: str
    component_id: str
    component_type: str
    agent_id: str | None = None
    device_type: str | None = None
    surface: str | None = None


class A2UIAuditPayload(BaseModel):
    """Payload for A2UI audit events."""

    action_type: str
    target: str | None = None
    payload: dict[str, Any] | None = None
    context: A2UIAuditContext


# =============================================================================
# Audit Functions
# =============================================================================


def log_a2ui_action(
    *,
    user_id: UUID,
    tenant_id: UUID,
    action_type: str,
    message_id: str,
    component_id: str,
    component_type: str,
    target: str | None = None,
    payload: dict[str, Any] | None = None,
    agent_id: str | None = None,
    device_type: str | None = None,
    surface: str | None = None,
) -> None:
    """
    Log an A2UI action for audit purposes.

    Args:
        user_id: The user who performed the action
        tenant_id: The tenant context
        action_type: Type of A2UI action (from A2UIActionType)
        message_id: The A2UI message ID that generated the component
        component_id: The ID of the component that was interacted with
        component_type: The type of A2UI component
        target: Navigation target or resource identifier
        payload: Additional action payload data
        agent_id: The AI agent that generated the UI (if known)
        device_type: The device type (mobile, desktop, tablet)
        surface: The surface/page where the action occurred
    """
    context = A2UIAuditContext(
        message_id=message_id,
        component_id=component_id,
        component_type=component_type,
        agent_id=agent_id,
        device_type=device_type,
        surface=surface,
    )

    audit_payload = A2UIAuditPayload(
        action_type=action_type,
        target=target,
        payload=payload,
        context=context,
    )

    # Log to standard logger with structured data
    logger.info(
        "A2UI action: %s on component %s (type: %s)",
        action_type,
        component_id,
        component_type,
        extra={
            "user_id": str(user_id),
            "tenant_id": str(tenant_id),
            "message_id": message_id,
            "component_type": component_type,
            "target": target,
            "audit_payload": audit_payload.model_dump(),
        },
    )


def log_a2ui_render(
    *,
    user_id: UUID,
    tenant_id: UUID,
    message_id: str,
    component_count: int,
    agent_id: str | None = None,
    device_type: str | None = None,
    surface: str | None = None,
    render_time_ms: float | None = None,
) -> None:
    """
    Log an A2UI message render event.

    Args:
        user_id: The user viewing the UI
        tenant_id: The tenant context
        message_id: The A2UI message ID
        component_count: Number of components rendered
        agent_id: The AI agent that generated the UI
        device_type: The device type
        surface: The surface/page where the render occurred
        render_time_ms: Time taken to render in milliseconds
    """
    logger.info(
        "A2UI render: message %s with %d components",
        message_id,
        component_count,
        extra={
            "user_id": str(user_id),
            "tenant_id": str(tenant_id),
            "message_id": message_id,
            "component_count": component_count,
            "agent_id": agent_id,
            "device_type": device_type,
            "surface": surface,
            "render_time_ms": render_time_ms,
        },
    )


def log_a2ui_error(
    *,
    user_id: UUID | None,
    tenant_id: UUID | None,
    message_id: str,
    error: str,
    component_id: str | None = None,
    component_type: str | None = None,
) -> None:
    """
    Log an A2UI rendering or action error.

    Args:
        user_id: The user (if known)
        tenant_id: The tenant (if known)
        message_id: The A2UI message ID
        error: Error message
        component_id: The component that caused the error (if known)
        component_type: The component type (if known)
    """
    logger.error(
        "A2UI error: %s (message: %s, component: %s)",
        error,
        message_id,
        component_id,
        extra={
            "user_id": str(user_id) if user_id else None,
            "tenant_id": str(tenant_id) if tenant_id else None,
            "message_id": message_id,
            "component_id": component_id,
            "component_type": component_type,
            "error": error,
        },
    )
