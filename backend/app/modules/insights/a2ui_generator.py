"""
A2UI Generator for Insights
Generates dynamic UI based on insight content and severity
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.a2ui import (
    A2UIBuilder,
    A2UIMessage,
    ActionType,
    DeviceContext,
    Severity,
)
from app.modules.insights.models import Insight, InsightPriority, InsightStatus


def _map_priority_to_severity(priority: str) -> Severity:
    """Map insight priority to A2UI severity."""
    mapping = {
        InsightPriority.HIGH.value: Severity.ERROR,
        InsightPriority.MEDIUM.value: Severity.WARNING,
        InsightPriority.LOW.value: Severity.INFO,
    }
    return mapping.get(priority, Severity.INFO)


class InsightA2UIGenerator:
    """Generates A2UI messages for insights based on content and severity."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def generate(
        self,
        insight: Insight,
        device_context: DeviceContext,
    ) -> A2UIMessage:
        """Generate A2UI message for an insight.

        The UI adapts based on:
        - Insight priority/severity
        - Insight category
        - Device type (mobile vs desktop)
        - Whether it has detailed analysis
        """
        builder = A2UIBuilder(device_context)
        builder.set_agent_id("insight-presenter")

        severity = _map_priority_to_severity(insight.priority)

        # Always start with alert card showing the insight
        builder.add_alert(
            title=insight.title,
            description=insight.summary,
            severity=severity,
        )

        # Add stats if we have data snapshot with metrics
        if insight.data_snapshot:
            self._add_data_visualizations(builder, insight)

        # Add accordion for detailed content if available
        if insight.detail:
            self._add_detail_section(builder, insight)

        # Add action buttons based on status and actions
        self._add_action_buttons(builder, insight)

        # Build with fallback text
        return builder.build(fallback_text=f"{insight.title}: {insight.summary}")

    def _add_data_visualizations(
        self,
        builder: A2UIBuilder,
        insight: Insight,
    ) -> None:
        """Add charts and stats based on data snapshot."""
        snapshot = insight.data_snapshot or {}

        # Check for trend data
        if "trend" in snapshot:
            trend_data = snapshot["trend"]
            if isinstance(trend_data, list) and len(trend_data) > 1:
                builder.add_line_chart(
                    data_key="trend",
                    data=trend_data,
                    title="Trend Analysis",
                    interactive=True,
                )

        # Check for comparison data
        if "comparison" in snapshot:
            comparison = snapshot["comparison"]
            if isinstance(comparison, dict):
                # Add stat cards for key metrics
                for key, value in comparison.items():
                    if isinstance(value, dict) and "current" in value:
                        change = value.get("change", 0)
                        builder.add_stat_card(
                            label=key.replace("_", " ").title(),
                            value=value["current"],
                            change_value=change,
                            change_direction="up"
                            if change > 0
                            else "down"
                            if change < 0
                            else "neutral",
                        )

        # Check for breakdown data (pie/bar chart)
        if "breakdown" in snapshot:
            breakdown_data = snapshot["breakdown"]
            if isinstance(breakdown_data, list):
                builder.add_bar_chart(
                    data_key="breakdown",
                    data=breakdown_data,
                    title="Breakdown",
                    orientation="horizontal",
                )

        # Check for client health metrics
        if "health_score" in snapshot:
            builder.add_stat_card(
                label="Health Score",
                value=f"{snapshot['health_score']}%",
                change_value=snapshot.get("health_change", 0),
            )

    def _add_detail_section(
        self,
        builder: A2UIBuilder,
        insight: Insight,
    ) -> None:
        """Add expandable detail section for full analysis."""
        items = []

        # Main detail section
        if insight.detail:
            items.append(
                {
                    "id": "detail",
                    "title": "Full Analysis",
                    "content": [],  # Content rendered as markdown by frontend
                }
            )

        # Add OPTIONS sections if this is a magic zone insight
        if insight.generation_type == "magic_zone" and insight.options_count:
            items.append(
                {
                    "id": "options",
                    "title": f"Strategic Options ({insight.options_count})",
                    "content": [],
                }
            )

        # Suggested actions section
        if insight.suggested_actions:
            items.append(
                {
                    "id": "actions",
                    "title": "Suggested Actions",
                    "content": [],
                }
            )

        if items:
            # Default to opening the first item for high priority
            default_open = ["detail"] if insight.priority == InsightPriority.HIGH.value else []
            builder.add_accordion(items=items, default_open=default_open)

    def _add_action_buttons(
        self,
        builder: A2UIBuilder,
        insight: Insight,
    ) -> None:
        """Add action buttons based on insight status and available actions."""
        insight_id = str(insight.id)

        # Primary actions based on status
        if insight.status == InsightStatus.NEW.value:
            # View details action
            builder.add_action_button(
                label="View Details",
                action_type=ActionType.NAVIGATE,
                target=f"/insights/{insight_id}",
                variant="default",
            )

            # Mark as viewed
            builder.add_action_button(
                label="Mark Viewed",
                action_type=ActionType.CUSTOM,
                payload={"action": "mark_viewed", "insight_id": insight_id},
                variant="outline",
            )

        elif insight.status == InsightStatus.VIEWED.value:
            # Convert to action item
            builder.add_action_button(
                label="Create Action Item",
                action_type=ActionType.CREATE_TASK,
                payload={
                    "title": insight.title,
                    "description": insight.summary,
                    "insight_id": insight_id,
                    "client_id": str(insight.client_id) if insight.client_id else None,
                },
                variant="default",
            )

            # Dismiss option
            builder.add_action_button(
                label="Dismiss",
                action_type=ActionType.CUSTOM,
                payload={"action": "dismiss", "insight_id": insight_id},
                variant="ghost",
            )

        # Add expand button for non-magic-zone insights
        if insight.generation_type != "magic_zone":
            builder.add_action_button(
                label="Get AI Analysis",
                action_type=ActionType.CUSTOM,
                payload={"action": "expand", "insight_id": insight_id},
                variant="secondary",
            )

        # Related URL if available
        if insight.related_url:
            builder.add_action_button(
                label="View in Xero",
                action_type=ActionType.NAVIGATE,
                target=insight.related_url,
                variant="outline",
                icon="external-link",
            )


async def generate_insight_ui(
    db: AsyncSession,
    insight: Insight,
    device_context: DeviceContext,
) -> A2UIMessage:
    """Convenience function to generate insight UI."""
    generator = InsightA2UIGenerator(db)
    return await generator.generate(insight, device_context)
