"""
Day Summary Agent

Generates personalized end-of-day summaries using A2UI components.
Shows completed work, pending items, highlights, and tomorrow's priorities.
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any
from uuid import uuid4

from app.core.a2ui import (
    A2UIBuilder,
    ActionType,
    DeviceContext,
    LayoutHint,
    Severity,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Summary Data Types
# =============================================================================


class SummaryMetrics:
    """Metrics for the day summary."""

    def __init__(
        self,
        clients_worked: int = 0,
        bas_completed: int = 0,
        bas_submitted: int = 0,
        queries_answered: int = 0,
        documents_processed: int = 0,
        total_time_saved_minutes: int = 0,
    ):
        self.clients_worked = clients_worked
        self.bas_completed = bas_completed
        self.bas_submitted = bas_submitted
        self.queries_answered = queries_answered
        self.documents_processed = documents_processed
        self.total_time_saved_minutes = total_time_saved_minutes


class CompletedItem:
    """A completed work item."""

    def __init__(
        self,
        title: str,
        client_name: str | None = None,
        completed_at: datetime | None = None,
        item_type: str = "task",
    ):
        self.title = title
        self.client_name = client_name
        self.completed_at = completed_at or datetime.now()
        self.item_type = item_type


class PendingItem:
    """A pending work item."""

    def __init__(
        self,
        title: str,
        client_name: str | None = None,
        due_date: date | None = None,
        priority: str = "normal",
        reason: str | None = None,
    ):
        self.title = title
        self.client_name = client_name
        self.due_date = due_date
        self.priority = priority
        self.reason = reason


class Highlight:
    """A notable highlight from the day."""

    def __init__(
        self,
        title: str,
        description: str,
        highlight_type: str = "achievement",  # achievement, alert, insight
        severity: str = "info",
    ):
        self.title = title
        self.description = description
        self.highlight_type = highlight_type
        self.severity = severity


# =============================================================================
# Day Summary Agent
# =============================================================================


class DaySummaryAgent:
    """
    Agent that generates personalized end-of-day summaries with A2UI.

    Shows:
    - Key metrics (clients worked, BAS completed, time saved)
    - Completed items (collapsible)
    - Highlights and achievements
    - Pending items and blockers
    - Tomorrow's priorities
    """

    def __init__(self, device_context: DeviceContext | None = None):
        self.device_context = device_context or DeviceContext(
            isMobile=False,
            isTablet=False,
        )

    async def generate_summary(
        self,
        user_id: str,
        summary_date: date | None = None,
        metrics: SummaryMetrics | None = None,
        completed_items: list[CompletedItem] | None = None,
        pending_items: list[PendingItem] | None = None,
        highlights: list[Highlight] | None = None,
        tomorrow_priorities: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Generate end-of-day summary.

        Args:
            user_id: The user's ID
            summary_date: The date for the summary (defaults to today)
            metrics: Summary metrics
            completed_items: List of completed work items
            pending_items: List of pending items
            highlights: Notable highlights
            tomorrow_priorities: Suggested priorities for tomorrow

        Returns:
            Dict with text_summary and a2ui_message
        """
        summary_date = summary_date or date.today()
        metrics = metrics or self._get_mock_metrics()
        completed_items = completed_items or self._get_mock_completed()
        pending_items = pending_items or self._get_mock_pending()
        highlights = highlights or self._get_mock_highlights()
        tomorrow_priorities = tomorrow_priorities or self._get_mock_priorities()

        # Build the summary UI
        builder = A2UIBuilder(self.device_context)
        builder.set_agent_id("day-summary")
        builder.set_layout(LayoutHint.STACK)

        # Add header with date and greeting
        self._add_header(builder, summary_date)

        # Add key metrics
        self._add_metrics(builder, metrics)

        # Add highlights (achievements, alerts)
        self._add_highlights(builder, highlights)

        # Add completed items (collapsible)
        self._add_completed_items(builder, completed_items)

        # Add pending items
        self._add_pending_items(builder, pending_items)

        # Add tomorrow's priorities
        self._add_tomorrow_priorities(builder, tomorrow_priorities)

        # Add action buttons
        self._add_actions(builder)

        # Generate text summary
        text_summary = self._generate_text_summary(
            summary_date, metrics, completed_items, pending_items, highlights
        )

        return {
            "correlation_id": str(uuid4()),
            "summary_date": summary_date.isoformat(),
            "text_summary": text_summary,
            "a2ui_message": builder.build(fallback_text=text_summary[:200]),
            "metrics": {
                "clients_worked": metrics.clients_worked,
                "bas_completed": metrics.bas_completed,
                "bas_submitted": metrics.bas_submitted,
                "time_saved_minutes": metrics.total_time_saved_minutes,
            },
        }

    def _add_header(self, builder: A2UIBuilder, summary_date: date) -> None:
        """Add header section with greeting."""
        # Determine time of day greeting
        hour = datetime.now().hour
        if hour < 12:
            greeting = "Good morning"
        elif hour < 17:
            greeting = "Good afternoon"
        else:
            greeting = "Good evening"

        # Format the date
        date_str = summary_date.strftime("%A, %B %d, %Y")

        builder.add_alert(
            title=f"{greeting}! Here's your day summary",
            description=f"Summary for {date_str}",
            severity=Severity.INFO,
        )

    def _add_metrics(self, builder: A2UIBuilder, metrics: SummaryMetrics) -> None:
        """Add key metrics as stat cards."""
        # Clients worked
        builder.add_stat_card(
            label="Clients Worked",
            value=str(metrics.clients_worked),
            icon="users",
        )

        # BAS completed
        builder.add_stat_card(
            label="BAS Completed",
            value=str(metrics.bas_completed),
            icon="check-circle",
        )

        # BAS submitted to ATO
        if metrics.bas_submitted > 0:
            builder.add_stat_card(
                label="Submitted to ATO",
                value=str(metrics.bas_submitted),
                icon="send",
            )

        # Time saved
        if metrics.total_time_saved_minutes > 0:
            hours = metrics.total_time_saved_minutes // 60
            mins = metrics.total_time_saved_minutes % 60
            if hours > 0:
                time_str = f"{hours}h {mins}m"
            else:
                time_str = f"{mins} min"
            builder.add_stat_card(
                label="Time Saved (AI)",
                value=time_str,
                icon="clock",
                change_direction="up",
            )

    def _add_highlights(self, builder: A2UIBuilder, highlights: list[Highlight]) -> None:
        """Add highlights section."""
        if not highlights:
            return

        for highlight in highlights:
            severity = {
                "success": Severity.SUCCESS,
                "warning": Severity.WARNING,
                "error": Severity.ERROR,
                "info": Severity.INFO,
            }.get(highlight.severity, Severity.INFO)

            builder.add_alert(
                title=highlight.title,
                description=highlight.description,
                severity=severity,
            )

    def _add_completed_items(
        self, builder: A2UIBuilder, completed_items: list[CompletedItem]
    ) -> None:
        """Add completed items as collapsible accordion."""
        if not completed_items:
            return

        # Group by type
        items_by_type: dict[str, list[CompletedItem]] = {}
        for item in completed_items:
            item_type = item.item_type
            if item_type not in items_by_type:
                items_by_type[item_type] = []
            items_by_type[item_type].append(item)

        # Create accordion items
        accordion_items = []
        for item_type, items in items_by_type.items():
            type_label = {
                "bas": "BAS Work",
                "review": "Reviews",
                "query": "Queries Answered",
                "document": "Documents Processed",
                "task": "Other Tasks",
            }.get(item_type, item_type.title())

            content_lines = []
            for item in items:
                client_str = f" ({item.client_name})" if item.client_name else ""
                time_str = item.completed_at.strftime("%H:%M") if item.completed_at else ""
                content_lines.append(f"• {item.title}{client_str} - {time_str}")

            accordion_items.append(
                {
                    "id": item_type,
                    "title": f"{type_label} ({len(items)})",
                    "content": "\n".join(content_lines),
                }
            )

        builder.add_accordion(
            items=accordion_items,
            default_open=None,  # All collapsed by default
        )

    def _add_pending_items(self, builder: A2UIBuilder, pending_items: list[PendingItem]) -> None:
        """Add pending items section."""
        if not pending_items:
            builder.add_alert(
                title="All caught up!",
                description="No pending items remaining.",
                severity=Severity.SUCCESS,
            )
            return

        # Sort by priority
        priority_order = {"high": 0, "normal": 1, "low": 2}
        sorted_items = sorted(pending_items, key=lambda x: priority_order.get(x.priority, 1))

        # Build data for table
        table_data = []
        for item in sorted_items:
            due_str = item.due_date.strftime("%b %d") if item.due_date else "-"
            client_str = item.client_name or "-"

            table_data.append(
                {
                    "task": item.title,
                    "client": client_str,
                    "due": due_str,
                    "priority": item.priority.upper(),
                }
            )

        builder.add_data_table(
            data_key="pendingItems",
            data=table_data,
            columns=[
                {"key": "task", "label": "Task", "sortable": True},
                {"key": "client", "label": "Client", "sortable": True},
                {"key": "due", "label": "Due", "sortable": True},
                {"key": "priority", "label": "Priority", "sortable": True},
            ],
            title=f"Pending Items ({len(pending_items)})",
            page_size=5,
        )

    def _add_tomorrow_priorities(self, builder: A2UIBuilder, priorities: list[str]) -> None:
        """Add tomorrow's priorities section."""
        if not priorities:
            return

        # Create a numbered list as accordion content
        priority_lines = [f"{i + 1}. {p}" for i, p in enumerate(priorities)]
        content = "\n".join(priority_lines)

        builder.add_accordion(
            items=[
                {
                    "id": "tomorrow",
                    "title": "🎯 Tomorrow's Priorities",
                    "content": content,
                }
            ],
            default_open=["tomorrow"],  # Open by default
        )

    def _add_actions(self, builder: A2UIBuilder) -> None:
        """Add action buttons."""
        builder.add_action_button(
            label="View Full Report",
            action_type=ActionType.NAVIGATE,
            target="/insights/daily-report",
            variant="primary",
            icon="file-text",
        )

        builder.add_action_button(
            label="Export Summary",
            action_type=ActionType.EXPORT,
            target="day-summary",
            variant="secondary",
            icon="download",
        )

    def _generate_text_summary(
        self,
        summary_date: date,
        metrics: SummaryMetrics,
        completed_items: list[CompletedItem],
        pending_items: list[PendingItem],
        highlights: list[Highlight],
    ) -> str:
        """Generate a text summary for fallback."""
        parts = []

        # Date
        date_str = summary_date.strftime("%A, %B %d")
        parts.append(f"Summary for {date_str}:")

        # Metrics
        if metrics.clients_worked > 0:
            parts.append(
                f"You worked on {metrics.clients_worked} clients today, "
                f"completing {metrics.bas_completed} BAS preparations."
            )

        # Time saved
        if metrics.total_time_saved_minutes > 0:
            hours = metrics.total_time_saved_minutes // 60
            mins = metrics.total_time_saved_minutes % 60
            if hours > 0:
                parts.append(f"AI assistance saved you approximately {hours}h {mins}m.")
            else:
                parts.append(f"AI assistance saved you approximately {mins} minutes.")

        # Highlights
        achievement_count = sum(1 for h in highlights if h.highlight_type == "achievement")
        if achievement_count > 0:
            parts.append(f"You achieved {achievement_count} notable milestone(s).")

        # Pending
        if pending_items:
            high_priority = sum(1 for p in pending_items if p.priority == "high")
            if high_priority > 0:
                parts.append(
                    f"You have {len(pending_items)} pending items, "
                    f"{high_priority} of which are high priority."
                )
            else:
                parts.append(f"You have {len(pending_items)} pending items remaining.")
        else:
            parts.append("All tasks are complete - great work!")

        return " ".join(parts)

    # =========================================================================
    # Mock Data (for demo/testing)
    # =========================================================================

    def _get_mock_metrics(self) -> SummaryMetrics:
        """Get mock metrics for demonstration."""
        return SummaryMetrics(
            clients_worked=8,
            bas_completed=5,
            bas_submitted=2,
            queries_answered=12,
            documents_processed=7,
            total_time_saved_minutes=95,
        )

    def _get_mock_completed(self) -> list[CompletedItem]:
        """Get mock completed items."""
        now = datetime.now()
        return [
            CompletedItem(
                title="Q2 BAS Preparation",
                client_name="Acme Corp",
                completed_at=now - timedelta(hours=2),
                item_type="bas",
            ),
            CompletedItem(
                title="Q2 BAS Preparation",
                client_name="Tech Solutions",
                completed_at=now - timedelta(hours=3),
                item_type="bas",
            ),
            CompletedItem(
                title="Exception Review",
                client_name="Global Services",
                completed_at=now - timedelta(hours=4),
                item_type="review",
            ),
            CompletedItem(
                title="GST Position Query",
                client_name="Retail Plus",
                completed_at=now - timedelta(hours=5),
                item_type="query",
            ),
            CompletedItem(
                title="Invoice Processing",
                client_name="Construction Ltd",
                completed_at=now - timedelta(hours=6),
                item_type="document",
            ),
        ]

    def _get_mock_pending(self) -> list[PendingItem]:
        """Get mock pending items."""
        today = date.today()
        return [
            PendingItem(
                title="Submit BAS to ATO",
                client_name="Acme Corp",
                due_date=today + timedelta(days=2),
                priority="high",
            ),
            PendingItem(
                title="Review variance exceptions",
                client_name="Tech Solutions",
                due_date=today + timedelta(days=3),
                priority="normal",
            ),
            PendingItem(
                title="Follow up on missing bank feed",
                client_name="Retail Plus",
                due_date=today + timedelta(days=5),
                priority="normal",
            ),
        ]

    def _get_mock_highlights(self) -> list[Highlight]:
        """Get mock highlights."""
        return [
            Highlight(
                title="5 BAS Completed!",
                description="You completed 5 BAS preparations today - above your daily average.",
                highlight_type="achievement",
                severity="success",
            ),
            Highlight(
                title="Data Quality Issue",
                description="Retail Plus has unreconciled transactions from last month.",
                highlight_type="alert",
                severity="warning",
            ),
        ]

    def _get_mock_priorities(self) -> list[str]:
        """Get mock tomorrow priorities."""
        return [
            "Submit Acme Corp BAS (due in 2 days)",
            "Review Tech Solutions exceptions",
            "Follow up with Retail Plus on bank feed",
            "Start Q2 BAS for remaining 3 clients",
        ]


# =============================================================================
# Convenience Function
# =============================================================================


async def generate_day_summary(
    user_id: str,
    summary_date: date | None = None,
    metrics: SummaryMetrics | None = None,
    completed_items: list[CompletedItem] | None = None,
    pending_items: list[PendingItem] | None = None,
    highlights: list[Highlight] | None = None,
    tomorrow_priorities: list[str] | None = None,
    device_context: DeviceContext | None = None,
) -> dict[str, Any]:
    """
    Generate end-of-day summary.

    Args:
        user_id: The user's ID
        summary_date: Date for the summary (defaults to today)
        metrics: Summary metrics
        completed_items: Completed work items
        pending_items: Pending items
        highlights: Notable highlights
        tomorrow_priorities: Tomorrow's suggested priorities
        device_context: Device context for responsive UI

    Returns:
        Dict with text_summary and a2ui_message
    """
    agent = DaySummaryAgent(device_context)
    return await agent.generate_summary(
        user_id=user_id,
        summary_date=summary_date,
        metrics=metrics,
        completed_items=completed_items,
        pending_items=pending_items,
        highlights=highlights,
        tomorrow_priorities=tomorrow_priorities,
    )
