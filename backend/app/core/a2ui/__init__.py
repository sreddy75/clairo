"""
A2UI - Agent-to-User Interface
Dynamic UI generation for AI-driven interfaces
"""

from .audit import (
    A2UIActionType,
    A2UIAuditContext,
    A2UIAuditPayload,
    log_a2ui_action,
    log_a2ui_error,
    log_a2ui_render,
)
from .builder import A2UIBuilder
from .device import (
    detect_device_context,
    get_device_context_from_request,
    is_mobile_device,
    is_tablet_device,
    is_touch_device,
)
from .schemas import (
    A2UIComponent,
    A2UIMessage,
    A2UIMeta,
    A2UIResponse,
    ActionConfig,
    ActionType,
    ComponentCondition,
    ComponentType,
    ConditionOperator,
    DeviceContext,
    LayoutHint,
    Platform,
    QueryRequest,
    RenderControl,
    Severity,
    SurfaceUpdate,
)

__all__ = [
    "A2UIActionType",
    "A2UIAuditContext",
    "A2UIAuditPayload",
    "A2UIBuilder",
    "A2UIComponent",
    "A2UIMessage",
    "A2UIMeta",
    "A2UIResponse",
    "ActionConfig",
    "ActionType",
    "ComponentCondition",
    "ComponentType",
    "ConditionOperator",
    "DeviceContext",
    "LayoutHint",
    "Platform",
    "QueryRequest",
    "RenderControl",
    "Severity",
    "SurfaceUpdate",
    "detect_device_context",
    "get_device_context_from_request",
    "is_mobile_device",
    "is_tablet_device",
    "is_touch_device",
    "log_a2ui_action",
    "log_a2ui_error",
    "log_a2ui_render",
]
