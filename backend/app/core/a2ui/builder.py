"""
A2UI Response Builder
Fluent builder for constructing A2UI messages
"""

from typing import Any
from uuid import uuid4

from .schemas import (
    A2UIComponent,
    A2UIMessage,
    A2UIMeta,
    ActionConfig,
    ActionType,
    ComponentCondition,
    ComponentType,
    ConditionOperator,
    DeviceContext,
    LayoutHint,
    RenderControl,
    Severity,
    SurfaceUpdate,
)


class A2UIBuilder:
    """Fluent builder for A2UI messages"""

    def __init__(self, device_context: DeviceContext) -> None:
        self.device_context = device_context
        self._components: list[A2UIComponent] = []
        self._data: dict[str, Any] = {}
        self._layout: LayoutHint | None = None
        self._agent_id: str | None = None

    # =========================================================================
    # Layout Configuration
    # =========================================================================

    def set_layout(self, layout: LayoutHint) -> "A2UIBuilder":
        """Set the layout hint for component arrangement"""
        self._layout = layout
        return self

    def set_agent_id(self, agent_id: str) -> "A2UIBuilder":
        """Set the agent ID for this message"""
        self._agent_id = agent_id
        return self

    # =========================================================================
    # Alert Components
    # =========================================================================

    def add_alert(
        self,
        title: str,
        description: str | None = None,
        severity: Severity = Severity.INFO,
        actions: list[ActionConfig] | None = None,
        condition: ComponentCondition | None = None,
    ) -> "A2UIBuilder":
        """Add an alert card component"""
        self._components.append(
            A2UIComponent(
                id=str(uuid4()),
                type=ComponentType.ALERT_CARD,
                props={
                    "title": title,
                    "description": description,
                    "severity": severity.value,
                    "actions": [a.model_dump(by_alias=True) for a in actions] if actions else None,
                },
                condition=condition,
            )
        )
        return self

    def add_urgency_banner(
        self,
        message: str,
        deadline: str,
        variant: str = "warning",
        condition: ComponentCondition | None = None,
    ) -> "A2UIBuilder":
        """Add an urgency banner component"""
        self._components.append(
            A2UIComponent(
                id=str(uuid4()),
                type=ComponentType.URGENCY_BANNER,
                props={
                    "message": message,
                    "deadline": deadline,
                    "variant": variant,
                },
                condition=condition,
            )
        )
        return self

    def add_badge(
        self,
        label: str,
        variant: str = "default",
        condition: ComponentCondition | None = None,
    ) -> "A2UIBuilder":
        """Add a badge component"""
        self._components.append(
            A2UIComponent(
                id=str(uuid4()),
                type=ComponentType.BADGE,
                props={"label": label, "variant": variant},
                condition=condition,
            )
        )
        return self

    # =========================================================================
    # Chart Components
    # =========================================================================

    def add_line_chart(
        self,
        data_key: str,
        data: list[dict[str, Any]],
        title: str | None = None,
        x_axis: dict[str, Any] | None = None,
        y_axis: dict[str, Any] | None = None,
        series: list[dict[str, Any]] | None = None,
        interactive: bool = True,
        condition: ComponentCondition | None = None,
    ) -> "A2UIBuilder":
        """Add a line chart component"""
        self._components.append(
            A2UIComponent(
                id=str(uuid4()),
                type=ComponentType.LINE_CHART,
                data_binding=data_key,
                props={
                    "title": title,
                    "xAxis": x_axis,
                    "yAxis": y_axis,
                    "series": series,
                    "interactive": interactive,
                },
                condition=condition,
            )
        )
        self._data[data_key] = data
        return self

    def add_bar_chart(
        self,
        data_key: str,
        data: list[dict[str, Any]],
        title: str | None = None,
        orientation: str = "vertical",
        stacked: bool = False,
        condition: ComponentCondition | None = None,
    ) -> "A2UIBuilder":
        """Add a bar chart component"""
        self._components.append(
            A2UIComponent(
                id=str(uuid4()),
                type=ComponentType.BAR_CHART,
                data_binding=data_key,
                props={
                    "title": title,
                    "orientation": orientation,
                    "stacked": stacked,
                },
                condition=condition,
            )
        )
        self._data[data_key] = data
        return self

    def add_pie_chart(
        self,
        data_key: str,
        data: list[dict[str, Any]],
        title: str | None = None,
        donut: bool = False,
        show_legend: bool = True,
        condition: ComponentCondition | None = None,
    ) -> "A2UIBuilder":
        """Add a pie chart component"""
        self._components.append(
            A2UIComponent(
                id=str(uuid4()),
                type=ComponentType.PIE_CHART,
                data_binding=data_key,
                props={
                    "title": title,
                    "donut": donut,
                    "showLegend": show_legend,
                },
                condition=condition,
            )
        )
        self._data[data_key] = data
        return self

    def add_scatter_chart(
        self,
        data_key: str,
        data: list[dict[str, Any]],
        title: str | None = None,
        x_axis: dict[str, Any] | None = None,
        y_axis: dict[str, Any] | None = None,
        condition: ComponentCondition | None = None,
    ) -> "A2UIBuilder":
        """Add a scatter chart component"""
        self._components.append(
            A2UIComponent(
                id=str(uuid4()),
                type=ComponentType.SCATTER_CHART,
                data_binding=data_key,
                props={
                    "title": title,
                    "xAxis": x_axis,
                    "yAxis": y_axis,
                },
                condition=condition,
            )
        )
        self._data[data_key] = data
        return self

    # =========================================================================
    # Data Display Components
    # =========================================================================

    def add_stat_card(
        self,
        label: str,
        value: str | int | float,
        change_value: float | None = None,
        change_direction: str | None = None,
        change_label: str | None = None,
        icon: str | None = None,
        condition: ComponentCondition | None = None,
    ) -> "A2UIBuilder":
        """Add a stat card component"""
        props: dict[str, Any] = {
            "label": label,
            "value": value,
            "icon": icon,
        }
        if change_value is not None:
            props["change"] = {
                "value": change_value,
                "direction": change_direction or ("up" if change_value > 0 else "down"),
                "label": change_label,
            }
        self._components.append(
            A2UIComponent(
                id=str(uuid4()),
                type=ComponentType.STAT_CARD,
                props=props,
                condition=condition,
            )
        )
        return self

    def add_data_table(
        self,
        data_key: str,
        data: list[dict[str, Any]],
        columns: list[dict[str, Any]],
        sortable: bool = True,
        pagination: bool = True,
        page_size: int = 10,
        title: str | None = None,
        condition: ComponentCondition | None = None,
    ) -> "A2UIBuilder":
        """Add a data table component"""
        props: dict[str, Any] = {
            "columns": columns,
            "sortable": sortable,
            "pagination": pagination,
            "pageSize": page_size,
        }
        if title:
            props["title"] = title

        self._components.append(
            A2UIComponent(
                id=str(uuid4()),
                type=ComponentType.DATA_TABLE,
                data_binding=data_key,
                props=props,
                condition=condition,
            )
        )
        self._data[data_key] = data
        return self

    def add_comparison_table(
        self,
        left_label: str,
        right_label: str,
        rows: list[dict[str, Any]],
        condition: ComponentCondition | None = None,
    ) -> "A2UIBuilder":
        """Add a comparison table component"""
        self._components.append(
            A2UIComponent(
                id=str(uuid4()),
                type=ComponentType.COMPARISON_TABLE,
                props={
                    "leftLabel": left_label,
                    "rightLabel": right_label,
                    "rows": rows,
                },
                condition=condition,
            )
        )
        return self

    # =========================================================================
    # Action Components
    # =========================================================================

    def add_action_button(
        self,
        label: str,
        action_type: ActionType,
        target: str | None = None,
        payload: dict[str, Any] | None = None,
        variant: str = "default",
        icon: str | None = None,
        disabled: bool = False,
        condition: ComponentCondition | None = None,
    ) -> "A2UIBuilder":
        """Add an action button component"""
        self._components.append(
            A2UIComponent(
                id=str(uuid4()),
                type=ComponentType.ACTION_BUTTON,
                props={
                    "label": label,
                    "action": {
                        "type": action_type.value,
                        "target": target,
                        "payload": payload,
                    },
                    "variant": variant,
                    "icon": icon,
                    "disabled": disabled,
                },
                condition=condition,
            )
        )
        return self

    def add_approval_bar(
        self,
        resource_id: str,
        options: list[dict[str, Any]] | None = None,
        condition: ComponentCondition | None = None,
    ) -> "A2UIBuilder":
        """Add an approval bar component"""
        default_options = [
            {"label": "Approve", "action": "approve", "variant": "primary"},
            {"label": "Reject", "action": "reject", "variant": "danger"},
            {"label": "Query", "action": "query", "variant": "secondary"},
        ]
        self._components.append(
            A2UIComponent(
                id=str(uuid4()),
                type=ComponentType.APPROVAL_BAR,
                props={
                    "resourceId": resource_id,
                    "options": options or default_options,
                },
                condition=condition,
            )
        )
        return self

    def add_export_button(
        self,
        data_binding: str,
        formats: list[str] | None = None,
        condition: ComponentCondition | None = None,
    ) -> "A2UIBuilder":
        """Add an export button component"""
        self._components.append(
            A2UIComponent(
                id=str(uuid4()),
                type=ComponentType.EXPORT_BUTTON,
                props={
                    "formats": formats or ["csv", "pdf", "xlsx"],
                    "dataBinding": data_binding,
                },
                condition=condition,
            )
        )
        return self

    # =========================================================================
    # Layout Components
    # =========================================================================

    def add_card(
        self,
        title: str | None = None,
        description: str | None = None,
        children: list[A2UIComponent] | None = None,
        condition: ComponentCondition | None = None,
    ) -> "A2UIBuilder":
        """Add a card container component"""
        self._components.append(
            A2UIComponent(
                id=str(uuid4()),
                type=ComponentType.CARD,
                props={
                    "title": title,
                    "description": description,
                },
                children=children,
                condition=condition,
            )
        )
        return self

    def add_accordion(
        self,
        items: list[dict[str, Any]],
        default_open: list[str] | None = None,
        condition: ComponentCondition | None = None,
    ) -> "A2UIBuilder":
        """Add an accordion component"""
        self._components.append(
            A2UIComponent(
                id=str(uuid4()),
                type=ComponentType.ACCORDION,
                props={
                    "items": items,
                    "defaultOpen": default_open,
                },
                condition=condition,
            )
        )
        return self

    def add_tabs(
        self,
        items: list[dict[str, Any]],
        default_tab: str | None = None,
        condition: ComponentCondition | None = None,
    ) -> "A2UIBuilder":
        """Add a tabs component"""
        self._components.append(
            A2UIComponent(
                id=str(uuid4()),
                type=ComponentType.TABS,
                props={
                    "items": items,
                    "defaultTab": default_tab,
                },
                condition=condition,
            )
        )
        return self

    def add_timeline(
        self,
        items: list[dict[str, Any]],
        condition: ComponentCondition | None = None,
    ) -> "A2UIBuilder":
        """Add a timeline component"""
        self._components.append(
            A2UIComponent(
                id=str(uuid4()),
                type=ComponentType.TIMELINE,
                props={"items": items},
                condition=condition,
            )
        )
        return self

    # =========================================================================
    # Media Components
    # =========================================================================

    def add_camera_capture(
        self,
        mode: str = "photo",
        multi_page: bool = False,
        hint: str | None = None,
        on_capture_action: ActionConfig | None = None,
        condition: ComponentCondition | None = None,
    ) -> "A2UIBuilder":
        """Add a camera capture component (mobile-first)"""
        self._components.append(
            A2UIComponent(
                id=str(uuid4()),
                type=ComponentType.CAMERA_CAPTURE,
                props={
                    "mode": mode,
                    "multiPage": multi_page,
                    "hint": hint,
                    "onCapture": on_capture_action.model_dump(by_alias=True)
                    if on_capture_action
                    else None,
                },
                condition=condition,
            )
        )
        return self

    def add_file_upload(
        self,
        accept: list[str] | None = None,
        max_size: int | None = None,
        multiple: bool = False,
        on_upload_action: ActionConfig | None = None,
        condition: ComponentCondition | None = None,
    ) -> "A2UIBuilder":
        """Add a file upload component"""
        self._components.append(
            A2UIComponent(
                id=str(uuid4()),
                type=ComponentType.FILE_UPLOAD,
                props={
                    "accept": accept or ["image/*", "application/pdf"],
                    "maxSize": max_size,
                    "multiple": multiple,
                    "onUpload": on_upload_action.model_dump(by_alias=True)
                    if on_upload_action
                    else None,
                },
                condition=condition,
            )
        )
        return self

    # =========================================================================
    # Form Components
    # =========================================================================

    def add_filter_bar(
        self,
        filters: list[dict[str, Any]],
        condition: ComponentCondition | None = None,
    ) -> "A2UIBuilder":
        """Add a filter bar component"""
        self._components.append(
            A2UIComponent(
                id=str(uuid4()),
                type=ComponentType.FILTER_BAR,
                props={"filters": filters},
                condition=condition,
            )
        )
        return self

    # =========================================================================
    # Feedback Components
    # =========================================================================

    def add_progress(
        self,
        value: int,
        max_value: int = 100,
        label: str | None = None,
        show_percent: bool = True,
        condition: ComponentCondition | None = None,
    ) -> "A2UIBuilder":
        """Add a progress indicator component"""
        self._components.append(
            A2UIComponent(
                id=str(uuid4()),
                type=ComponentType.PROGRESS_INDICATOR,
                props={
                    "value": value,
                    "max": max_value,
                    "label": label,
                    "showPercent": show_percent,
                },
                condition=condition,
            )
        )
        return self

    # =========================================================================
    # Conditional Helpers
    # =========================================================================

    def when(
        self, field: str, operator: ConditionOperator, value: Any = None
    ) -> ComponentCondition:
        """Create a condition for conditional rendering"""
        return ComponentCondition(field=field, operator=operator, value=value)

    def when_mobile(self) -> ComponentCondition:
        """Condition: only show on mobile devices"""
        return ComponentCondition(
            field="device.isMobile", operator=ConditionOperator.EQ, value=True
        )

    def when_desktop(self) -> ComponentCondition:
        """Condition: only show on desktop devices"""
        return ComponentCondition(
            field="device.isMobile", operator=ConditionOperator.EQ, value=False
        )

    # =========================================================================
    # Build
    # =========================================================================

    def build(
        self,
        fallback_text: str | None = None,
        streaming: bool = False,
    ) -> A2UIMessage:
        """Build the final A2UI message"""
        render_control = None
        if streaming:
            render_control = RenderControl(streaming=True, complete=False)

        return A2UIMessage(
            surface_update=SurfaceUpdate(
                components=self._components,
                layout=self._layout,
            ),
            data_model_update=self._data if self._data else None,
            render_control=render_control,
            meta=A2UIMeta(
                device_context=self.device_context,
                agent_id=self._agent_id,
                fallback_text=fallback_text,
            ),
        )

    def build_streaming_chunk(self) -> A2UIMessage:
        """Build a streaming chunk (partial message)"""
        return A2UIMessage(
            surface_update=SurfaceUpdate(
                components=self._components,
                layout=self._layout,
            ),
            data_model_update=self._data if self._data else None,
            render_control=RenderControl(streaming=True, complete=False),
            meta=A2UIMeta(
                device_context=self.device_context,
                agent_id=self._agent_id,
            ),
        )

    def build_streaming_complete(self, fallback_text: str | None = None) -> A2UIMessage:
        """Build the final streaming message (marks stream as complete)"""
        return A2UIMessage(
            surface_update=SurfaceUpdate(
                components=self._components,
                layout=self._layout,
            ),
            data_model_update=self._data if self._data else None,
            render_control=RenderControl(streaming=True, complete=True),
            meta=A2UIMeta(
                device_context=self.device_context,
                agent_id=self._agent_id,
                fallback_text=fallback_text,
            ),
        )
