"""
LLM-Driven A2UI Generation

This module enables the LLM to dynamically decide what UI components
to show based on its response content and context.

The LLM outputs structured JSON specifying which components to render,
and this module converts that to A2UI messages.
"""

import re
from typing import Any

from app.core.a2ui import (
    A2UIBuilder,
    A2UIMessage,
    DeviceContext,
    LayoutHint,
    Severity,
)

# =============================================================================
# A2UI Component Schema (for LLM prompt)
# =============================================================================

A2UI_SCHEMA_PROMPT = """
## Dynamic UI Components

You can enhance your response with visual UI components. After your text response,
you may include a JSON block specifying components to display.

### Available Components

1. **stat_card** - Display a key metric prominently
   ```json
   {"type": "stat_card", "label": "Net GST Payable", "value": "$10,224", "trend": "up"}
   ```

2. **alert** - Show an important notice (info, warning, error, success)
   ```json
   {"type": "alert", "severity": "warning", "title": "Compliance Risk", "message": "Super contributions may be overdue"}
   ```

3. **line_chart** - Show trends over time (values MUST be raw numbers, NOT formatted strings)
   ```json
   {"type": "line_chart", "title": "Monthly Revenue", "data": [{"month": "Jan", "value": 50000}, {"month": "Feb", "value": 45000}]}
   ```

4. **bar_chart** - Compare categories (values MUST be raw numbers, NOT formatted strings)
   ```json
   {"type": "bar_chart", "title": "Expense Breakdown", "data": [{"category": "Wages", "value": 25000}, {"category": "Rent", "value": 15000}]}
   ```

5. **data_table** - Display tabular data
   ```json
   {"type": "data_table", "title": "Overdue Invoices", "columns": ["Client", "Amount", "Days"], "rows": [...]}
   ```

6. **action_button** - Suggest an action
   ```json
   {"type": "action_button", "label": "View Full Report", "action": "navigate", "target": "/reports"}
   ```

### Output Format

End your response with a JSON block wrapped in ```a2ui tags:

```a2ui
{
  "components": [
    {"type": "stat_card", "label": "GST Collected", "value": "$15,420"},
    {"type": "stat_card", "label": "GST Paid", "value": "$5,196"},
    {"type": "stat_card", "label": "Net Payable", "value": "$10,224", "trend": "up"}
  ],
  "layout": "grid"
}
```

### Guidelines

- Only add components that genuinely help visualize your response
- Use stat_cards for 2-4 key metrics the user would want to glance at
- Use alerts for compliance issues, warnings, or important notices
- Use charts when discussing trends or comparisons
- Use tables for lists of items (overdue invoices, top expenses)
- Don't add components just for decoration - they should add value
- If your response is simple text, don't add any components
"""


# =============================================================================
# Parse LLM Output
# =============================================================================


def extract_a2ui_block(content: str) -> tuple[str, dict[str, Any] | None]:
    """Extract A2UI JSON block from LLM response.

    Args:
        content: The raw LLM response text.

    Returns:
        Tuple of (clean_text, a2ui_spec) where a2ui_spec is the parsed JSON
        or None if no A2UI block was found.
    """
    import json
    import re

    # Look for ```a2ui ... ``` block
    pattern = r"```a2ui\s*\n(.*?)\n```"
    match = re.search(pattern, content, re.DOTALL)

    if not match:
        return content, None

    # Extract and parse the JSON
    json_str = match.group(1).strip()
    try:
        a2ui_spec = json.loads(json_str)
    except json.JSONDecodeError:
        # If JSON is invalid, return content as-is
        return content, None

    # Remove the A2UI block from the text
    clean_text = content[: match.start()].rstrip()

    return clean_text, a2ui_spec


# =============================================================================
# Build A2UI from LLM Specification
# =============================================================================


def build_a2ui_from_spec(
    spec: dict[str, Any],
    device_context: DeviceContext | None = None,
    fallback_text: str | None = None,
) -> A2UIMessage | None:
    """Build an A2UI message from the LLM's component specification.

    Args:
        spec: The parsed A2UI specification from the LLM.
        device_context: Optional device context for responsive rendering.
        fallback_text: Fallback text if components can't render.

    Returns:
        A2UIMessage or None if spec is invalid/empty.
    """
    components = spec.get("components", [])
    if not components:
        return None

    builder = A2UIBuilder(device_context or DeviceContext(isMobile=False, isTablet=False))
    builder.set_agent_id("knowledge-assistant")

    # Set layout
    layout_str = spec.get("layout", "stack")
    layout_map = {
        "stack": LayoutHint.STACK,
        "grid": LayoutHint.GRID,
        "flow": LayoutHint.FLOW,
        "sidebar": LayoutHint.SIDEBAR,
    }
    builder.set_layout(layout_map.get(layout_str, LayoutHint.STACK))

    # Build each component
    for comp in components:
        comp_type = comp.get("type")

        if comp_type == "stat_card":
            _add_stat_card(builder, comp)
        elif comp_type == "alert":
            _add_alert(builder, comp)
        elif comp_type == "line_chart":
            _add_line_chart(builder, comp)
        elif comp_type == "bar_chart":
            _add_bar_chart(builder, comp)
        elif comp_type == "data_table":
            _add_data_table(builder, comp)
        elif comp_type == "action_button":
            _add_action_button(builder, comp)

    return builder.build(fallback_text=fallback_text)


def _parse_numeric_value(value: Any) -> float | int | None:
    """Parse a numeric value from a string or return as-is if already numeric.

    Handles formats like "$46,340.62", "15%", "1,234", etc.
    """
    if isinstance(value, (int, float)):
        return value
    if not isinstance(value, str):
        return None

    # Remove currency symbols, commas, percent signs, whitespace
    cleaned = re.sub(r"[$,\s%]", "", value)

    try:
        # Try int first, then float
        if "." in cleaned:
            return float(cleaned)
        return int(cleaned)
    except (ValueError, TypeError):
        return None


def _normalize_chart_data(data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize chart data by converting string values to numbers."""
    normalized = []
    for item in data:
        new_item = {}
        for key, value in item.items():
            # Try to parse numeric values
            parsed = _parse_numeric_value(value)
            new_item[key] = parsed if parsed is not None else value
        normalized.append(new_item)
    return normalized


def _add_stat_card(builder: A2UIBuilder, comp: dict[str, Any]) -> None:
    """Add a stat card component."""
    label = comp.get("label", "")
    value = comp.get("value", "")
    trend = comp.get("trend")  # "up", "down", or None

    # Map trend to change_direction
    change_direction = None
    if trend == "up":
        change_direction = "up"
    elif trend == "down":
        change_direction = "down"

    builder.add_stat_card(
        label=label,
        value=str(value),
        change_direction=change_direction,
        icon=comp.get("icon"),
    )


def _add_alert(builder: A2UIBuilder, comp: dict[str, Any]) -> None:
    """Add an alert component."""
    severity_str = comp.get("severity", "info")
    severity_map = {
        "info": Severity.INFO,
        "warning": Severity.WARNING,
        "error": Severity.ERROR,
        "success": Severity.SUCCESS,
    }

    builder.add_alert(
        title=comp.get("title", "Notice"),
        description=comp.get("message", ""),
        severity=severity_map.get(severity_str, Severity.INFO),
    )


def _add_line_chart(builder: A2UIBuilder, comp: dict[str, Any]) -> None:
    """Add a line chart component."""
    raw_data = comp.get("data", [])
    if not raw_data:
        return

    # Normalize data to ensure numeric values
    data = _normalize_chart_data(raw_data)

    # Auto-detect x-axis key (first non-numeric field)
    x_key = None
    series_keys = []
    if data:
        first_item = data[0]
        for key, value in first_item.items():
            if isinstance(value, (int, float)):
                series_keys.append(key)
            elif x_key is None:
                x_key = key

    builder.add_line_chart(
        data_key=f"chart_{id(comp)}",
        data=data,
        title=comp.get("title"),
        x_axis={"dataKey": x_key or "date"},
        y_axis={"format": "currency"}
        if any(
            "amount" in k or "revenue" in k or "expense" in k or "value" in k for k in series_keys
        )
        else None,
    )


def _add_bar_chart(builder: A2UIBuilder, comp: dict[str, Any]) -> None:
    """Add a bar chart component."""
    raw_data = comp.get("data", [])
    if not raw_data:
        return

    # Normalize data to ensure numeric values
    data = _normalize_chart_data(raw_data)

    builder.add_bar_chart(
        data_key=f"chart_{id(comp)}",
        data=data,
        title=comp.get("title"),
        orientation=comp.get("orientation", "vertical"),
    )


def _add_data_table(builder: A2UIBuilder, comp: dict[str, Any]) -> None:
    """Add a data table component."""
    columns_raw = comp.get("columns", [])
    rows = comp.get("rows", [])

    if not columns_raw or not rows:
        return

    # Convert column names to column specs
    columns = []
    for col in columns_raw:
        if isinstance(col, str):
            columns.append({"key": col.lower().replace(" ", "_"), "label": col, "sortable": True})
        elif isinstance(col, dict):
            columns.append(col)

    # Ensure rows have the right keys
    formatted_rows = []
    for row in rows:
        if isinstance(row, list):
            # Convert list to dict using column keys
            row_dict = {}
            for i, val in enumerate(row):
                if i < len(columns):
                    row_dict[columns[i]["key"]] = val
            formatted_rows.append(row_dict)
        elif isinstance(row, dict):
            formatted_rows.append(row)

    builder.add_data_table(
        data_key=f"table_{id(comp)}",
        data=formatted_rows,
        columns=columns,
        title=comp.get("title"),
        page_size=comp.get("page_size", 5),
    )


def _add_action_button(builder: A2UIBuilder, comp: dict[str, Any]) -> None:
    """Add an action button component."""
    from app.core.a2ui import ActionType

    action_str = comp.get("action", "custom")
    action_map = {
        "navigate": ActionType.NAVIGATE,
        "export": ActionType.EXPORT,
        "approve": ActionType.APPROVE,
        "create_task": ActionType.CREATE_TASK,
        "custom": ActionType.CUSTOM,
    }

    builder.add_action_button(
        label=comp.get("label", "Action"),
        action_type=action_map.get(action_str, ActionType.CUSTOM),
        target=comp.get("target"),
        variant=comp.get("variant", "primary"),
    )


# =============================================================================
# Convenience Function
# =============================================================================


def process_llm_response_for_a2ui(
    content: str,
    device_context: DeviceContext | None = None,
) -> tuple[str, A2UIMessage | None]:
    """Process an LLM response to extract text and A2UI components.

    Args:
        content: The raw LLM response.
        device_context: Optional device context.

    Returns:
        Tuple of (clean_text, a2ui_message).
    """
    clean_text, spec = extract_a2ui_block(content)

    if spec is None:
        return clean_text, None

    a2ui_message = build_a2ui_from_spec(
        spec,
        device_context=device_context,
        fallback_text=clean_text[:200] if clean_text else None,
    )

    return clean_text, a2ui_message
