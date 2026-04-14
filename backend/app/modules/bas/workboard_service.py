"""Service for BAS Lodgement Workboard.

Spec 011: Interim Lodgement - User Story 8
"""

import math
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.modules.bas.models import BASPeriod, BASSession, BASSessionStatus
from app.modules.bas.schemas import (
    LodgementWorkboardItem,
    LodgementWorkboardResponse,
    LodgementWorkboardSummaryResponse,
)
from app.modules.integrations.xero.models import XeroConnection, XeroConnectionStatus


class WorkboardService:
    """Service for BAS lodgement workboard operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _calculate_urgency(
        self, days_remaining: int, is_lodged: bool
    ) -> Literal["overdue", "critical", "warning", "normal"]:
        """Calculate urgency level based on days remaining."""
        if is_lodged:
            return "normal"
        if days_remaining < 0:
            return "overdue"
        if days_remaining <= 3:
            return "critical"
        if days_remaining <= 7:
            return "warning"
        return "normal"

    def _get_financial_year_str(self, fy_year: int) -> str:
        """Convert financial year integer to string format.

        e.g., 2025 -> "2024-25"
        """
        return f"{fy_year - 1}-{str(fy_year)[2:]}"

    def _get_display_name(self, quarter: int | None, month: int | None, fy_year: int) -> str:
        """Generate display name for a BAS period."""
        if quarter:
            return f"Q{quarter} FY{fy_year}"
        return f"Month {month} FY{fy_year}"

    async def get_workboard(
        self,
        tenant_id: UUID,
        status_filter: Literal["all", "overdue", "due_this_week", "upcoming", "lodged"] = "all",
        urgency_filter: Literal["all", "overdue", "critical", "warning", "normal"] = "all",
        quarter_filter: Literal["all", "Q1", "Q2", "Q3", "Q4"] = "all",
        financial_year: str | None = None,
        search: str | None = None,
        sort_by: Literal["due_date", "client_name", "status", "days_remaining"] = "due_date",
        sort_order: Literal["asc", "desc"] = "asc",
        page: int = 1,
        limit: int = 50,
        reference_date: date | None = None,
    ) -> LodgementWorkboardResponse:
        """Get lodgement workboard data with filtering and pagination.

        Args:
            tenant_id: The tenant ID
            status_filter: Filter by deadline status
            urgency_filter: Filter by urgency level
            quarter_filter: Filter by quarter
            financial_year: Filter by financial year (e.g., "2024-25")
            search: Search by client name
            sort_by: Sort field
            sort_order: Sort direction
            page: Page number (1-indexed)
            limit: Items per page
            reference_date: Reference date for calculations (defaults to today)

        Returns:
            Paginated workboard response
        """
        if reference_date is None:
            reference_date = datetime.now(UTC).date()

        # Calculate date thresholds
        today = reference_date
        week_end = today + timedelta(days=7)

        # Build base query joining periods with connections and optional sessions
        sess_alias = aliased(BASSession)

        # Subquery to get the latest session for each period
        latest_session_subq = (
            select(
                BASSession.period_id,
                func.max(BASSession.created_at).label("max_created_at"),
            )
            .group_by(BASSession.period_id)
            .subquery()
        )

        stmt = (
            select(
                BASPeriod.id.label("period_id"),
                BASPeriod.quarter,
                BASPeriod.month,
                BASPeriod.fy_year,
                BASPeriod.due_date,
                BASPeriod.connection_id,
                XeroConnection.organization_name.label("client_name"),
                sess_alias.id.label("session_id"),
                sess_alias.status.label("session_status"),
                sess_alias.lodged_at,
            )
            .select_from(BASPeriod)
            .join(XeroConnection, BASPeriod.connection_id == XeroConnection.id)
            .outerjoin(
                latest_session_subq,
                BASPeriod.id == latest_session_subq.c.period_id,
            )
            .outerjoin(
                sess_alias,
                and_(
                    sess_alias.period_id == BASPeriod.id,
                    sess_alias.created_at == latest_session_subq.c.max_created_at,
                ),
            )
            .where(XeroConnection.tenant_id == tenant_id)
            .where(
                XeroConnection.status.in_(
                    [
                        XeroConnectionStatus.ACTIVE,
                        XeroConnectionStatus.NEEDS_REAUTH,
                    ]
                )
            )
        )

        # Apply status filter
        if status_filter == "overdue":
            stmt = stmt.where(
                and_(
                    BASPeriod.due_date < today,
                    or_(sess_alias.status.is_(None), sess_alias.status != BASSessionStatus.LODGED),
                )
            )
        elif status_filter == "due_this_week":
            stmt = stmt.where(
                and_(
                    BASPeriod.due_date >= today,
                    BASPeriod.due_date <= week_end,
                    or_(sess_alias.status.is_(None), sess_alias.status != BASSessionStatus.LODGED),
                )
            )
        elif status_filter == "upcoming":
            stmt = stmt.where(
                and_(
                    BASPeriod.due_date > week_end,
                    or_(sess_alias.status.is_(None), sess_alias.status != BASSessionStatus.LODGED),
                )
            )
        elif status_filter == "lodged":
            stmt = stmt.where(sess_alias.status == BASSessionStatus.LODGED)

        # Apply quarter filter
        if quarter_filter != "all":
            quarter_num = int(quarter_filter[1])  # Extract number from "Q1", "Q2", etc.
            stmt = stmt.where(BASPeriod.quarter == quarter_num)

        # Apply financial year filter
        if financial_year:
            # Parse "2024-25" -> 2025
            try:
                parts = financial_year.split("-")
                fy_year = int(parts[0]) + 1
                stmt = stmt.where(BASPeriod.fy_year == fy_year)
            except (ValueError, IndexError):
                pass  # Invalid format, ignore filter

        # Apply search filter
        if search:
            stmt = stmt.where(XeroConnection.organization_name.ilike(f"%{search}%"))

        # Get total count before pagination
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        # Apply sorting
        days_remaining_expr = func.extract("day", BASPeriod.due_date - today)

        order_col: Any
        if sort_by == "due_date":
            order_col = BASPeriod.due_date
        elif sort_by == "client_name":
            order_col = XeroConnection.organization_name
        elif sort_by == "status":
            order_col = case(
                (sess_alias.status == BASSessionStatus.LODGED, 4),
                (sess_alias.status == BASSessionStatus.APPROVED, 3),
                (sess_alias.status == BASSessionStatus.READY_FOR_REVIEW, 2),
                (sess_alias.status.isnot(None), 1),
                else_=0,
            )
        else:  # days_remaining
            order_col = days_remaining_expr

        if sort_order == "desc":
            stmt = stmt.order_by(order_col.desc())
        else:
            stmt = stmt.order_by(order_col.asc())

        # Apply pagination
        offset = (page - 1) * limit
        stmt = stmt.offset(offset).limit(limit)

        # Execute query
        result = await self.session.execute(stmt)
        rows = result.all()

        # Build response items
        items: list[LodgementWorkboardItem] = []
        for row in rows:
            days_remaining = (row.due_date - today).days
            # session_status can be enum or string depending on SQLAlchemy mapping
            status_value = (
                row.session_status.value
                if hasattr(row.session_status, "value")
                else row.session_status
            )
            is_lodged = status_value == BASSessionStatus.LODGED.value if status_value else False
            urgency = self._calculate_urgency(days_remaining, is_lodged)

            # Apply urgency filter
            if urgency_filter != "all" and urgency != urgency_filter:
                continue

            items.append(
                LodgementWorkboardItem(
                    connection_id=row.connection_id,
                    client_name=row.client_name or "Unknown Client",
                    period_id=row.period_id,
                    period_display_name=self._get_display_name(row.quarter, row.month, row.fy_year),
                    quarter=row.quarter,
                    financial_year=self._get_financial_year_str(row.fy_year),
                    due_date=row.due_date,
                    days_remaining=days_remaining,
                    session_id=row.session_id,
                    session_status=status_value,
                    is_lodged=is_lodged,
                    lodged_at=row.lodged_at,
                    urgency=urgency,
                )
            )

        total_pages = math.ceil(total / limit) if total > 0 else 1

        return LodgementWorkboardResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages,
        )

    async def get_workboard_summary(
        self,
        tenant_id: UUID,
        reference_date: date | None = None,
    ) -> LodgementWorkboardSummaryResponse:
        """Get workboard summary statistics.

        Args:
            tenant_id: The tenant ID
            reference_date: Reference date for calculations (defaults to today)

        Returns:
            Summary counts
        """
        if reference_date is None:
            reference_date = datetime.now(UTC).date()

        today = reference_date

        # Subquery to get the latest session for each period
        latest_session_subq = (
            select(
                BASSession.period_id,
                func.max(BASSession.created_at).label("max_created_at"),
            )
            .group_by(BASSession.period_id)
            .subquery()
        )

        sess_alias = aliased(BASSession)

        base_stmt = (
            select(
                BASPeriod.id,
                BASPeriod.due_date,
                sess_alias.status,
            )
            .select_from(BASPeriod)
            .join(XeroConnection, BASPeriod.connection_id == XeroConnection.id)
            .outerjoin(
                latest_session_subq,
                BASPeriod.id == latest_session_subq.c.period_id,
            )
            .outerjoin(
                sess_alias,
                and_(
                    sess_alias.period_id == BASPeriod.id,
                    sess_alias.created_at == latest_session_subq.c.max_created_at,
                ),
            )
            .where(XeroConnection.tenant_id == tenant_id)
            .where(
                XeroConnection.status.in_(
                    [
                        XeroConnectionStatus.ACTIVE,
                        XeroConnectionStatus.NEEDS_REAUTH,
                    ]
                )
            )
        )

        result = await self.session.execute(base_stmt)
        rows = result.all()

        # Calculate counts
        total_periods = len(rows)
        overdue = 0
        due_this_week = 0
        due_this_month = 0
        lodged = 0
        not_started = 0

        for row in rows:
            # status can be enum or string depending on SQLAlchemy mapping
            status_value = row.status.value if hasattr(row.status, "value") else row.status
            is_lodged = status_value == BASSessionStatus.LODGED.value if status_value else False
            has_session = status_value is not None

            if is_lodged:
                lodged += 1
                continue

            days_remaining = (row.due_date - today).days

            if days_remaining < 0:
                overdue += 1
            elif days_remaining <= 7:
                due_this_week += 1
            elif days_remaining <= 30:
                due_this_month += 1

            if not has_session:
                not_started += 1

        return LodgementWorkboardSummaryResponse(
            total_periods=total_periods,
            overdue=overdue,
            due_this_week=due_this_week,
            due_this_month=due_this_month,
            lodged=lodged,
            not_started=not_started,
        )
