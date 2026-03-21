"""
A2UI Pydantic Schemas
Agent-to-User Interface data models for Clairo
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

# =============================================================================
# Enums
# =============================================================================


class LayoutHint(str, Enum):
    """Layout hint for component arrangement"""

    STACK = "stack"
    GRID = "grid"
    FLOW = "flow"
    SIDEBAR = "sidebar"


class Platform(str, Enum):
    """Device platform"""

    IOS = "ios"
    ANDROID = "android"
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"


class ComponentType(str, Enum):
    """A2UI component types"""

    # Charts
    LINE_CHART = "lineChart"
    BAR_CHART = "barChart"
    PIE_CHART = "pieChart"
    SCATTER_CHART = "scatterChart"

    # Data Display
    DATA_TABLE = "dataTable"
    COMPARISON_TABLE = "comparisonTable"
    STAT_CARD = "statCard"
    QUERY_RESULT = "queryResult"

    # Layout
    CARD = "card"
    ACCORDION = "accordion"
    EXPANDABLE_SECTION = "expandableSection"
    TABS = "tabs"
    TIMELINE = "timeline"

    # Actions
    ACTION_BUTTON = "actionButton"
    APPROVAL_BAR = "approvalBar"
    EXPORT_BUTTON = "exportButton"

    # Alerts
    ALERT_CARD = "alertCard"
    URGENCY_BANNER = "urgencyBanner"
    BADGE = "badge"

    # Forms
    TEXT_INPUT = "textInput"
    SELECT_FIELD = "selectField"
    CHECKBOX = "checkbox"
    DATE_RANGE_PICKER = "dateRangePicker"
    FILTER_BAR = "filterBar"

    # Media
    CAMERA_CAPTURE = "cameraCapture"
    FILE_UPLOAD = "fileUpload"
    AVATAR = "avatar"

    # Feedback
    PROGRESS_INDICATOR = "progressIndicator"
    SKELETON = "skeleton"
    TOOLTIP = "tooltip"
    DIALOG = "dialog"


class ActionType(str, Enum):
    """Action types for component interactions"""

    NAVIGATE = "navigate"
    CREATE_TASK = "createTask"
    APPROVE = "approve"
    EXPORT = "export"
    CUSTOM = "custom"


class Severity(str, Enum):
    """Alert severity levels"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"


class ConditionOperator(str, Enum):
    """Conditional rendering operators"""

    EQ = "eq"
    NEQ = "neq"
    GT = "gt"
    LT = "lt"
    GTE = "gte"
    LTE = "lte"
    EXISTS = "exists"
    EMPTY = "empty"


# =============================================================================
# Device Context
# =============================================================================


class DeviceContext(BaseModel):
    """Device context for adaptive UI generation"""

    is_mobile: bool = Field(alias="isMobile")
    is_tablet: bool = Field(alias="isTablet")
    platform: Platform | None = None
    browser: str | None = None

    model_config = {"populate_by_name": True}


# =============================================================================
# Component Condition
# =============================================================================


class ComponentCondition(BaseModel):
    """Conditional rendering configuration"""

    field: str
    operator: ConditionOperator
    value: Any | None = None


# =============================================================================
# Action Configuration
# =============================================================================


class ActionConfig(BaseModel):
    """Action configuration for interactive components"""

    type: ActionType
    target: str | None = None
    payload: dict[str, Any] | None = None


# =============================================================================
# Component
# =============================================================================


class A2UIComponent(BaseModel):
    """A2UI component definition"""

    id: str = Field(default_factory=lambda: str(uuid4()))
    type: ComponentType
    data_binding: str | None = Field(default=None, alias="dataBinding")
    children: list["A2UIComponent"] | None = None
    props: dict[str, Any] | None = None
    condition: ComponentCondition | None = None

    model_config = {"populate_by_name": True}


# =============================================================================
# Render Control
# =============================================================================


class RenderControl(BaseModel):
    """Rendering control for streaming and updates"""

    streaming: bool | None = None
    replace: list[str] | None = None
    append_to: str | None = Field(default=None, alias="appendTo")
    complete: bool | None = None

    model_config = {"populate_by_name": True}


# =============================================================================
# Surface Update
# =============================================================================


class SurfaceUpdate(BaseModel):
    """Surface update containing components to render"""

    components: list[A2UIComponent]
    layout: LayoutHint | None = None


# =============================================================================
# Message Metadata
# =============================================================================


class A2UIMeta(BaseModel):
    """A2UI message metadata"""

    message_id: str = Field(default_factory=lambda: str(uuid4()), alias="messageId")
    generated_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(), alias="generatedAt"
    )
    device_context: DeviceContext = Field(alias="deviceContext")
    agent_id: str | None = Field(default=None, alias="agentId")
    fallback_text: str | None = Field(default=None, alias="fallbackText")

    model_config = {"populate_by_name": True}


# =============================================================================
# A2UI Message
# =============================================================================


class A2UIMessage(BaseModel):
    """Complete A2UI message for frontend rendering"""

    surface_update: SurfaceUpdate = Field(alias="surfaceUpdate")
    data_model_update: dict[str, Any] | None = Field(default=None, alias="dataModelUpdate")
    render_control: RenderControl | None = Field(default=None, alias="renderControl")
    meta: A2UIMeta

    model_config = {"populate_by_name": True}


# =============================================================================
# Request Schemas
# =============================================================================


class QueryRequest(BaseModel):
    """Request schema for ad-hoc queries"""

    query: str = Field(..., min_length=1, max_length=1000)


# =============================================================================
# Response Schemas (API layer)
# =============================================================================


class A2UIResponse(BaseModel):
    """API response wrapper for A2UI messages"""

    data: A2UIMessage
    success: bool = True


class A2UIErrorResponse(BaseModel):
    """API error response"""

    error: str
    code: str
    details: dict[str, Any] | None = None
