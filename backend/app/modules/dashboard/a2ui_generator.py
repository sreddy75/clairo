"""
A2UI Generator for Dashboard
Generates context-aware dashboard UI based on time of day, workload, and priorities
"""

from datetime import UTC, datetime, time
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.a2ui import (
    A2UIBuilder,
    A2UIMessage,
    ActionType,
    DeviceContext,
    LayoutHint,
    Severity,
)
from app.modules.dashboard.service import DashboardService


def _get_time_context() -> dict[str, bool]:
    """Get context based on current time of day."""
    now = datetime.now(UTC)
    current_time = now.time()
    weekday = now.weekday()  # 0 = Monday, 6 = Sunday

    return {
        "is_morning": time(6, 0) <= current_time < time(12, 0),
        "is_afternoon": time(12, 0) <= current_time < time(17, 0),
        "is_evening": time(17, 0) <= current_time < time(21, 0),
        "is_monday": weekday == 0,
        "is_friday": weekday == 4,
        "is_weekend": weekday >= 5,
        "is_eom": now.day >= 25,  # End of month
        "is_eoq": now.month in [3, 6, 9, 12] and now.day >= 20,  # End of quarter
    }


class DashboardA2UIGenerator:
    """Generates context-aware dashboard A2UI messages."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.service = DashboardService(db)

    async def generate(
        self,
        tenant_id: UUID,
        device_context: DeviceContext,
        quarter: int | None = None,
        fy_year: int | None = None,
        demo: bool = False,
    ) -> A2UIMessage:
        """Generate personalized dashboard A2UI.

        Adapts based on:
        - Time of day (morning focus, afternoon review, evening summary)
        - Day of week (Monday planning, Friday wrap-up)
        - Quarter end (BAS deadline urgency)
        - Device type
        - Current workload
        """
        builder = A2UIBuilder(device_context)
        builder.set_agent_id("dashboard-personalizer")

        # Demo mode: showcase all A2UI components
        if demo:
            return self._generate_demo(builder)

        time_context = _get_time_context()

        # Get dashboard data
        summary = await self.service.get_summary(
            tenant_id=tenant_id,
            quarter=quarter,
            fy_year=fy_year,
        )

        # Simple stack layout
        builder.set_layout(LayoutHint.STACK)

        # Add urgency banner if deadlines are near
        if time_context["is_eoq"]:
            self._add_quarter_end_urgency(builder, summary)

        # Add time-contextual greeting and focus (the unique value)
        self._add_contextual_focus(builder, time_context, summary)

        ready_count = summary.status_counts.ready if summary.status_counts else 0
        return builder.build(
            fallback_text=f"Dashboard: {summary.total_clients} clients, {ready_count} ready for BAS"
        )

    def _generate_demo(self, builder: A2UIBuilder) -> A2UIMessage:
        """Generate a demo showcasing various A2UI components."""
        builder.set_layout(LayoutHint.GRID)

        # 1. Urgency Banner - BAS deadline warning
        builder.add_urgency_banner(
            message="BAS due in 5 days - 3 clients need attention",
            deadline="2026-01-28T00:00:00Z",
            variant="critical",
        )

        # 2. Alert Cards - Different severities
        builder.add_alert(
            title="Week Ahead",
            description="Start the week with 3 clients needing review. Focus on ABC Pty Ltd first.",
            severity=Severity.INFO,
        )

        builder.add_alert(
            title="Data Quality Warning",
            description="2 clients have missing bank transactions for December.",
            severity=Severity.WARNING,
        )

        builder.add_alert(
            title="Sync Complete",
            description="All 5 client accounts synced successfully from Xero.",
            severity=Severity.SUCCESS,
        )

        # 3. Stat Cards - Key metrics
        builder.add_stat_card(
            label="Total Clients",
            value=47,
            icon="users",
        )

        builder.add_stat_card(
            label="Ready for BAS",
            value=38,
            change_value=12.5,
            change_direction="up",
            change_label="vs last quarter",
        )

        builder.add_stat_card(
            label="Needs Review",
            value=6,
            change_value=-3,
            change_direction="down",
            change_label="this week",
        )

        builder.add_stat_card(
            label="Net GST",
            value="$124,580",
            icon="dollar-sign",
        )

        # 4. Bar Chart - Client status breakdown
        builder.add_bar_chart(
            data_key="statusBreakdown",
            data=[
                {"name": "Ready", "value": 38},
                {"name": "Needs Review", "value": 6},
                {"name": "Missing Data", "value": 2},
                {"name": "No Activity", "value": 1},
            ],
            title="Client Status Breakdown",
            orientation="horizontal",
        )

        # 5. Line Chart - GST trend
        builder.add_line_chart(
            data_key="gstTrend",
            data=[
                {"month": "Jul", "collected": 45000, "paid": 32000},
                {"month": "Aug", "collected": 52000, "paid": 38000},
                {"month": "Sep", "collected": 48000, "paid": 35000},
                {"month": "Oct", "collected": 61000, "paid": 42000},
                {"month": "Nov", "collected": 58000, "paid": 41000},
                {"month": "Dec", "collected": 72000, "paid": 48000},
            ],
            title="GST Trend (Last 6 Months)",
        )

        # 6. Data Table - Clients needing attention
        builder.add_data_table(
            data_key="clientsNeedingAttention",
            data=[
                {
                    "client": "ABC Pty Ltd",
                    "issue": "Missing bank feed",
                    "days": 5,
                    "gst": "$12,450",
                },
                {"client": "XYZ Corp", "issue": "Unreconciled items", "days": 3, "gst": "$8,200"},
                {
                    "client": "Smith & Co",
                    "issue": "Stale data (7 days)",
                    "days": 7,
                    "gst": "$15,800",
                },
            ],
            columns=[
                {"key": "client", "label": "Client", "sortable": True},
                {"key": "issue", "label": "Issue", "sortable": False},
                {"key": "days", "label": "Days", "sortable": True},
                {"key": "gst", "label": "Est. GST", "sortable": True},
            ],
            page_size=5,
        )

        # 7. Progress indicator
        builder.add_progress(
            value=38,
            max_value=47,
            label="BAS Preparation Progress",
            show_percent=True,
        )

        # 8. Timeline - Recent activity
        builder.add_timeline(
            items=[
                {
                    "id": "1",
                    "title": "BAS lodged for DEF Industries",
                    "description": "Q2 FY26 submitted to ATO",
                    "timestamp": "2026-01-02T09:30:00Z",
                    "status": "completed",
                },
                {
                    "id": "2",
                    "title": "Review completed for GHI Services",
                    "description": "All items reconciled, ready for lodgement",
                    "timestamp": "2026-01-02T08:15:00Z",
                    "status": "completed",
                },
                {
                    "id": "3",
                    "title": "Data sync started",
                    "description": "Syncing 12 client accounts from Xero",
                    "timestamp": "2026-01-02T10:00:00Z",
                    "status": "current",
                },
            ]
        )

        # 9. Action buttons
        builder.add_action_button(
            label="Review Outstanding",
            action_type=ActionType.NAVIGATE,
            target="/clients?status=needs_review",
            variant="default",
        )

        builder.add_action_button(
            label="Generate Portfolio Report",
            action_type=ActionType.CUSTOM,
            payload={"action": "generate_report", "type": "portfolio"},
            variant="secondary",
        )

        return builder.build(fallback_text="A2UI Demo: Showcasing dashboard components")

    def _add_quarter_end_urgency(self, builder: A2UIBuilder, summary: object) -> None:
        """Add urgency banner for quarter end."""
        # Calculate days until BAS due (28th of month after quarter end)
        now = datetime.now(UTC)
        quarter_end_month = ((now.month - 1) // 3 + 1) * 3
        due_month = quarter_end_month + 1 if quarter_end_month < 12 else 1
        due_year = now.year if quarter_end_month < 12 else now.year + 1
        due_date = datetime(due_year, due_month, 28, tzinfo=UTC)

        days_until = (due_date - now).days

        if days_until <= 14:
            variant = "critical" if days_until <= 7 else "warning"
            status_counts = getattr(summary, "status_counts", None)
            needs_attention = 0
            if status_counts:
                needs_attention = getattr(status_counts, "needs_review", 0) + getattr(
                    status_counts, "missing_data", 0
                )
            builder.add_urgency_banner(
                message=f"BAS due in {days_until} days - {needs_attention} clients need attention",
                deadline=due_date.isoformat(),
                variant=variant,
            )

    def _add_contextual_focus(
        self,
        builder: A2UIBuilder,
        time_context: dict[str, bool],
        summary: object,
    ) -> None:
        """Add contextual focus message based on time."""
        status_counts = getattr(summary, "status_counts", None)
        needs_review = getattr(status_counts, "needs_review", 0) if status_counts else 0
        missing_data = getattr(status_counts, "missing_data", 0) if status_counts else 0

        if time_context["is_morning"]:
            if time_context["is_monday"]:
                title = "Week Ahead"
                description = (
                    f"Start the week with {needs_review + missing_data} clients needing attention"
                )
                severity = Severity.INFO
            else:
                title = "Morning Focus"
                description = f"{needs_review} clients need review today"
                severity = Severity.INFO if needs_review < 5 else Severity.WARNING
        elif time_context["is_friday"]:
            title = "Week Wrap-up"
            description = f"Complete reviews for {needs_review} clients before weekend"
            severity = Severity.WARNING if needs_review > 0 else Severity.SUCCESS
        else:
            title = "Today's Priority"
            description = f"{needs_review + missing_data} items need attention"
            severity = Severity.INFO

        builder.add_alert(
            title=title,
            description=description,
            severity=severity,
        )

    def _add_key_stats(self, builder: A2UIBuilder, summary: object) -> None:
        """Add key metric stat cards."""
        total_clients = getattr(summary, "total_clients", 0)
        status_counts = getattr(summary, "status_counts", None)
        ready_count = getattr(status_counts, "ready", 0) if status_counts else 0
        needs_review = getattr(status_counts, "needs_review", 0) if status_counts else 0
        net_gst = getattr(summary, "net_gst", 0)

        # Total clients
        builder.add_stat_card(
            label="Total Clients",
            value=total_clients,
            icon="users",
        )

        # Ready for BAS
        ready_pct = (ready_count / total_clients * 100) if total_clients > 0 else 0
        builder.add_stat_card(
            label="Ready for BAS",
            value=ready_count,
            change_value=round(ready_pct, 1),
            change_direction="up" if ready_pct >= 80 else "neutral",
            change_label="of total",
        )

        # Needs Review
        builder.add_stat_card(
            label="Needs Review",
            value=needs_review,
            change_direction="down" if needs_review < 5 else "up",
        )

        # Net GST
        builder.add_stat_card(
            label="Net GST",
            value=f"${net_gst:,.2f}" if net_gst else "$0",
            icon="dollar-sign",
        )

    def _add_client_breakdown(self, builder: A2UIBuilder, summary: object) -> None:
        """Add client status breakdown chart."""
        status_counts = getattr(summary, "status_counts", None)
        ready = getattr(status_counts, "ready", 0) if status_counts else 0
        needs_review = getattr(status_counts, "needs_review", 0) if status_counts else 0
        missing_data = getattr(status_counts, "missing_data", 0) if status_counts else 0
        no_activity = getattr(status_counts, "no_activity", 0) if status_counts else 0

        breakdown_data = [
            {"name": "Ready", "value": ready},
            {"name": "Needs Review", "value": needs_review},
            {"name": "Missing Data", "value": missing_data},
            {"name": "No Activity", "value": no_activity},
        ]

        builder.add_bar_chart(
            data_key="statusBreakdown",
            data=breakdown_data,
            title="Client Status",
            orientation="horizontal",
        )

    def _add_activity_timeline(self, builder: A2UIBuilder) -> None:
        """Add recent activity timeline."""
        # Mock timeline items - in production this would come from activity service
        now = datetime.now(UTC)
        items = [
            {
                "id": "1",
                "title": "BAS lodged for ABC Pty Ltd",
                "description": "Q2 2024 BAS submitted to ATO",
                "timestamp": (now.replace(hour=now.hour - 1)).isoformat(),
                "status": "completed",
            },
            {
                "id": "2",
                "title": "Review completed for XYZ Corp",
                "timestamp": (now.replace(hour=now.hour - 2)).isoformat(),
                "status": "completed",
            },
            {
                "id": "3",
                "title": "Data sync in progress",
                "description": "Syncing 5 client accounts from Xero",
                "timestamp": now.isoformat(),
                "status": "current",
            },
        ]

        builder.add_timeline(items=items)

    def _add_quick_actions(
        self,
        builder: A2UIBuilder,
        time_context: dict[str, bool],
    ) -> None:
        """Add contextual quick action buttons."""
        # Primary action based on context
        if time_context["is_eoq"]:
            builder.add_action_button(
                label="Review Outstanding BAS",
                action_type=ActionType.NAVIGATE,
                target="/clients?status=needs_review",
                variant="default",
            )
        else:
            builder.add_action_button(
                label="View All Clients",
                action_type=ActionType.NAVIGATE,
                target="/clients",
                variant="default",
            )

        # Generate insights action
        builder.add_action_button(
            label="Generate Insights",
            action_type=ActionType.CUSTOM,
            payload={"action": "generate_insights"},
            variant="secondary",
        )


async def generate_dashboard_ui(
    db: AsyncSession,
    tenant_id: UUID,
    device_context: DeviceContext,
    quarter: int | None = None,
    fy_year: int | None = None,
    demo: bool = False,
) -> A2UIMessage:
    """Convenience function to generate dashboard UI."""
    generator = DashboardA2UIGenerator(db)
    return await generator.generate(tenant_id, device_context, quarter, fy_year, demo)
