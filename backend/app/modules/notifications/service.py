"""Service for in-app notifications.

Spec 011: Interim Lodgement - In-app deadline notifications
"""

import contextlib
import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.models import Notification, NotificationType

logger = logging.getLogger(__name__)

# Notification types that indicate high priority (overdue/urgent)
HIGH_PRIORITY_TYPES = {
    "deadline_overdue",
    "deadline_today",
    "deadline_tomorrow",
    "review_overdue",
}

# Notification types that indicate medium priority (upcoming)
MEDIUM_PRIORITY_TYPES = {
    "deadline_approaching",
    "review_approaching",
    "review_assigned",
}


class NotificationService:
    """Service for managing in-app notifications."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_notification(
        self,
        tenant_id: UUID,
        user_id: UUID,
        notification_type: NotificationType,
        title: str,
        message: str,
        entity_type: str | None = None,
        entity_id: UUID | None = None,
        entity_context: dict[str, Any] | None = None,
    ) -> Notification:
        """Create a new notification for a user.

        Args:
            tenant_id: The tenant ID
            user_id: The user to notify
            notification_type: Type of notification
            title: Notification title
            message: Notification message
            entity_type: Optional entity type (e.g., "bas_session")
            entity_id: Optional entity ID
            entity_context: Optional additional context

        Returns:
            Created notification
        """
        notification = Notification(
            tenant_id=tenant_id,
            user_id=user_id,
            notification_type=notification_type.value,
            title=title,
            message=message,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_context=entity_context,
            is_read=False,
        )

        self.session.add(notification)
        await self.session.flush()

        logger.info(f"Created notification for user {user_id}: {title}")

        return notification

    async def get_user_notifications(
        self,
        user_id: UUID,
        tenant_id: UUID,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Notification]:
        """Get notifications for a user.

        Args:
            user_id: The user ID
            tenant_id: The tenant ID
            unread_only: Only return unread notifications
            limit: Max number of notifications
            offset: Pagination offset

        Returns:
            List of notifications
        """
        stmt = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .where(Notification.tenant_id == tenant_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        if unread_only:
            stmt = stmt.where(Notification.is_read == False)  # noqa: E712

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_unread_count(
        self,
        user_id: UUID,
        tenant_id: UUID,
    ) -> int:
        """Get count of unread notifications for a user.

        Args:
            user_id: The user ID
            tenant_id: The tenant ID

        Returns:
            Count of unread notifications
        """
        from sqlalchemy import func

        stmt = (
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id)
            .where(Notification.tenant_id == tenant_id)
            .where(Notification.is_read == False)  # noqa: E712
        )

        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def mark_as_read(
        self,
        notification_id: UUID,
        user_id: UUID,
        tenant_id: UUID,
    ) -> bool:
        """Mark a notification as read.

        Args:
            notification_id: The notification ID
            user_id: The user ID (for verification)
            tenant_id: The tenant ID

        Returns:
            True if notification was updated
        """
        stmt = (
            update(Notification)
            .where(Notification.id == notification_id)
            .where(Notification.user_id == user_id)
            .where(Notification.tenant_id == tenant_id)
            .where(Notification.is_read == False)  # noqa: E712
            .values(is_read=True, read_at=datetime.now(UTC))
        )

        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def mark_all_as_read(
        self,
        user_id: UUID,
        tenant_id: UUID,
    ) -> int:
        """Mark all notifications as read for a user.

        Args:
            user_id: The user ID
            tenant_id: The tenant ID

        Returns:
            Number of notifications marked as read
        """
        stmt = (
            update(Notification)
            .where(Notification.user_id == user_id)
            .where(Notification.tenant_id == tenant_id)
            .where(Notification.is_read == False)  # noqa: E712
            .values(is_read=True, read_at=datetime.now(UTC))
        )

        result = await self.session.execute(stmt)
        return result.rowcount

    async def delete_notification(
        self,
        notification_id: UUID,
        user_id: UUID,
        tenant_id: UUID,
    ) -> bool:
        """Delete a notification.

        Args:
            notification_id: The notification ID
            user_id: The user ID (for verification)
            tenant_id: The tenant ID

        Returns:
            True if notification was deleted
        """
        stmt = select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
            Notification.tenant_id == tenant_id,
        )

        result = await self.session.execute(stmt)
        notification = result.scalar_one_or_none()

        if notification:
            await self.session.delete(notification)
            return True

        return False

    def _calculate_priority(
        self,
        notification_type: str,
        entity_context: dict[str, Any] | None,
    ) -> Literal["high", "medium", "low"]:
        """Calculate priority based on notification type and context.

        Args:
            notification_type: The type of notification
            entity_context: Optional context containing due_date

        Returns:
            Priority level: high, medium, or low
        """
        # Check notification type first
        if notification_type in HIGH_PRIORITY_TYPES:
            return "high"

        if notification_type in MEDIUM_PRIORITY_TYPES:
            return "medium"

        # Check due date in context if available
        if entity_context and "due_date" in entity_context:
            try:
                due_date_str = entity_context["due_date"]
                if isinstance(due_date_str, str):
                    due_date = date.fromisoformat(due_date_str)
                else:
                    due_date = due_date_str

                today = date.today()
                days_until_due = (due_date - today).days

                if days_until_due < 0:
                    return "high"  # Overdue
                elif days_until_due <= 7:
                    return "medium"  # Due within a week
            except (ValueError, TypeError):
                pass

        return "low"

    def _extract_due_date(
        self,
        entity_context: dict[str, Any] | None,
    ) -> date | None:
        """Extract due date from entity context.

        Args:
            entity_context: Optional context containing due_date

        Returns:
            Due date if present, None otherwise
        """
        if not entity_context or "due_date" not in entity_context:
            return None

        try:
            due_date_str = entity_context["due_date"]
            if isinstance(due_date_str, str):
                return date.fromisoformat(due_date_str)
            elif isinstance(due_date_str, date):
                return due_date_str
        except (ValueError, TypeError):
            pass

        return None

    def _calculate_days_remaining(
        self,
        due_date: date | None,
    ) -> int | None:
        """Calculate days remaining until due date.

        Args:
            due_date: The due date

        Returns:
            Days remaining (negative if overdue), None if no due date
        """
        if not due_date:
            return None

        return (due_date - date.today()).days

    async def get_notifications_with_filters(
        self,
        user_id: UUID,
        tenant_id: UUID,
        status: Literal["all", "unread", "read"] = "all",
        notification_types: list[str] | None = None,
        priority: Literal["all", "high", "medium", "low"] = "all",
        search: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        sort_by: Literal["priority", "due_date", "created_at", "client_name"] = "created_at",
        sort_order: Literal["asc", "desc"] = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Get notifications with comprehensive filtering, search, and pagination.

        Args:
            user_id: The user ID
            tenant_id: The tenant ID
            status: Filter by read status
            notification_types: Filter by notification types
            priority: Filter by priority level
            search: Search term for title/message/client
            date_from: Filter by created date start
            date_to: Filter by created date end
            sort_by: Sort column
            sort_order: Sort direction
            limit: Max results per page
            offset: Pagination offset

        Returns:
            Tuple of (notifications with priority, total count)
        """
        # Build base query
        base_conditions = [
            Notification.user_id == user_id,
            Notification.tenant_id == tenant_id,
        ]

        # Status filter
        if status == "unread":
            base_conditions.append(Notification.is_read == False)  # noqa: E712
        elif status == "read":
            base_conditions.append(Notification.is_read == True)  # noqa: E712

        # Type filter
        if notification_types:
            base_conditions.append(Notification.notification_type.in_(notification_types))

        # Date range filter
        if date_from:
            base_conditions.append(
                Notification.created_at >= datetime.combine(date_from, datetime.min.time())
            )
        if date_to:
            base_conditions.append(
                Notification.created_at <= datetime.combine(date_to, datetime.max.time())
            )

        # Search filter (across title, message, and client name in entity_context)
        if search:
            search_pattern = f"%{search}%"
            base_conditions.append(
                or_(
                    Notification.title.ilike(search_pattern),
                    Notification.message.ilike(search_pattern),
                    # Search in entity_context for client_name
                    Notification.entity_context["client_name"].astext.ilike(search_pattern),
                )
            )

        # Get total count first
        count_stmt = select(func.count()).select_from(Notification).where(and_(*base_conditions))
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar() or 0

        # Build main query with sorting
        stmt = select(Notification).where(and_(*base_conditions))

        # Apply sorting
        if sort_by == "created_at":
            order_col = Notification.created_at
        elif sort_by == "due_date":
            # Sort by due_date extracted from entity_context (nulls last)
            order_col = Notification.entity_context["due_date"].astext
        elif sort_by == "client_name":
            order_col = Notification.entity_context["client_name"].astext
        else:
            # Default to created_at for priority (we'll re-sort in memory)
            order_col = Notification.created_at

        if sort_order == "desc":
            stmt = stmt.order_by(order_col.desc().nullslast())
        else:
            stmt = stmt.order_by(order_col.asc().nullsfirst())

        # Apply pagination
        stmt = stmt.limit(limit).offset(offset)

        result = await self.session.execute(stmt)
        notifications = list(result.scalars().all())

        # Transform to response format with calculated priority
        enhanced_notifications = []
        for n in notifications:
            n_priority = self._calculate_priority(n.notification_type, n.entity_context)

            # Apply priority filter (post-query since priority is calculated)
            if priority != "all" and n_priority != priority:
                continue

            due_date = self._extract_due_date(n.entity_context)
            days_remaining = self._calculate_days_remaining(due_date)

            # Extract client info from entity_context
            client_name = None
            connection_id = None
            if n.entity_context:
                client_name = n.entity_context.get("client_name")
                conn_id = n.entity_context.get("connection_id")
                if conn_id:
                    with contextlib.suppress(ValueError):
                        connection_id = UUID(conn_id) if isinstance(conn_id, str) else conn_id

            enhanced_notifications.append(
                {
                    "id": n.id,
                    "notification_type": n.notification_type,
                    "title": n.title,
                    "message": n.message,
                    "entity_type": n.entity_type,
                    "entity_id": n.entity_id,
                    "entity_context": n.entity_context,
                    "is_read": n.is_read,
                    "read_at": n.read_at,
                    "created_at": n.created_at,
                    "priority": n_priority,
                    "due_date": due_date,
                    "days_remaining": days_remaining,
                    "client_name": client_name,
                    "connection_id": connection_id,
                }
            )

        # Sort by priority if requested (high > medium > low)
        if sort_by == "priority":
            priority_order = {"high": 0, "medium": 1, "low": 2}
            reverse = sort_order == "desc"
            enhanced_notifications.sort(
                key=lambda x: (priority_order.get(x["priority"], 3), x["created_at"]),
                reverse=reverse,
            )

        return enhanced_notifications, total

    async def get_summary(
        self,
        user_id: UUID,
        tenant_id: UUID,
    ) -> dict[str, int]:
        """Get notification summary statistics.

        Args:
            user_id: The user ID
            tenant_id: The tenant ID

        Returns:
            Summary with unread, high priority, overdue, due this week counts
        """
        # Get all unread notifications to calculate statistics
        stmt = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .where(Notification.tenant_id == tenant_id)
            .where(Notification.is_read == False)  # noqa: E712
        )

        result = await self.session.execute(stmt)
        notifications = list(result.scalars().all())

        total_unread = len(notifications)
        high_priority = 0
        overdue = 0
        due_this_week = 0

        today = date.today()
        week_from_now = today + timedelta(days=7)

        for n in notifications:
            priority = self._calculate_priority(n.notification_type, n.entity_context)

            if priority == "high":
                high_priority += 1

            due_date = self._extract_due_date(n.entity_context)
            if due_date:
                if due_date < today:
                    overdue += 1
                elif due_date <= week_from_now:
                    due_this_week += 1

        return {
            "total_unread": total_unread,
            "high_priority": high_priority,
            "overdue": overdue,
            "due_this_week": due_this_week,
        }

    async def bulk_mark_as_read(
        self,
        notification_ids: list[UUID],
        user_id: UUID,
        tenant_id: UUID,
    ) -> int:
        """Mark multiple notifications as read.

        Args:
            notification_ids: List of notification IDs to mark as read
            user_id: The user ID (for verification)
            tenant_id: The tenant ID

        Returns:
            Number of notifications marked as read
        """
        stmt = (
            update(Notification)
            .where(Notification.id.in_(notification_ids))
            .where(Notification.user_id == user_id)
            .where(Notification.tenant_id == tenant_id)
            .where(Notification.is_read == False)  # noqa: E712
            .values(is_read=True, read_at=datetime.now(UTC))
        )

        result = await self.session.execute(stmt)
        return result.rowcount

    async def bulk_dismiss(
        self,
        notification_ids: list[UUID],
        user_id: UUID,
        tenant_id: UUID,
    ) -> int:
        """Dismiss (delete) multiple notifications.

        Args:
            notification_ids: List of notification IDs to dismiss
            user_id: The user ID (for verification)
            tenant_id: The tenant ID

        Returns:
            Number of notifications dismissed
        """
        # First get the notifications to delete
        stmt = select(Notification).where(
            Notification.id.in_(notification_ids),
            Notification.user_id == user_id,
            Notification.tenant_id == tenant_id,
        )

        result = await self.session.execute(stmt)
        notifications = list(result.scalars().all())

        count = len(notifications)
        for notification in notifications:
            await self.session.delete(notification)

        return count
