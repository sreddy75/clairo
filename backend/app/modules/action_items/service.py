"""Action Item service layer."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.action_items.models import (
    ActionItem,
    ActionItemPriority,
    ActionItemStatus,
)
from app.modules.action_items.schemas import (
    ActionItemCreate,
    ActionItemStats,
    ActionItemUpdate,
)

logger = logging.getLogger(__name__)


class ActionItemService:
    """Service for managing action items."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        tenant_id: UUID,
        user_id: str,
        data: ActionItemCreate,
    ) -> ActionItem:
        """Create a new action item."""
        item = ActionItem(
            tenant_id=tenant_id,
            title=data.title,
            description=data.description,
            source_insight_id=data.source_insight_id,
            client_id=data.client_id,
            client_name=data.client_name,
            assigned_to_user_id=data.assigned_to_user_id,
            assigned_to_name=data.assigned_to_name,
            assigned_by_user_id=user_id,
            due_date=data.due_date,
            priority=data.priority,
            status=ActionItemStatus.PENDING,
        )

        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)

        logger.info(f"Created action item {item.id} for tenant {tenant_id}")
        return item

    async def get_by_id(
        self,
        tenant_id: UUID,
        item_id: UUID,
    ) -> ActionItem | None:
        """Get an action item by ID."""
        result = await self.db.execute(
            select(ActionItem).where(
                ActionItem.id == item_id,
                ActionItem.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        tenant_id: UUID,
        *,
        status: list[ActionItemStatus] | None = None,
        priority: list[ActionItemPriority] | None = None,
        assigned_to_user_id: str | None = None,
        client_id: UUID | None = None,
        due_before: date | None = None,
        due_after: date | None = None,
        include_completed: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ActionItem], int]:
        """List action items with filters."""
        # Build base query
        query = select(ActionItem).where(ActionItem.tenant_id == tenant_id)

        # Status filter
        if status:
            query = query.where(ActionItem.status.in_(status))
        elif not include_completed:
            # Default: exclude completed and cancelled
            query = query.where(
                ActionItem.status.notin_(
                    [
                        ActionItemStatus.COMPLETED,
                        ActionItemStatus.CANCELLED,
                    ]
                )
            )

        # Priority filter
        if priority:
            query = query.where(ActionItem.priority.in_(priority))

        # Assignee filter
        if assigned_to_user_id:
            query = query.where(ActionItem.assigned_to_user_id == assigned_to_user_id)

        # Client filter
        if client_id:
            query = query.where(ActionItem.client_id == client_id)

        # Due date filters
        if due_before:
            query = query.where(ActionItem.due_date <= due_before)
        if due_after:
            query = query.where(ActionItem.due_date >= due_after)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply ordering and pagination
        # Order: overdue first, then by due date, then by priority
        query = query.order_by(
            ActionItem.due_date.asc().nullslast(),
            ActionItem.priority.asc(),
            ActionItem.created_at.desc(),
        )
        query = query.limit(limit).offset(offset)

        result = await self.db.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def update(
        self,
        tenant_id: UUID,
        item_id: UUID,
        data: ActionItemUpdate,
    ) -> ActionItem | None:
        """Update an action item."""
        item = await self.get_by_id(tenant_id, item_id)
        if not item:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(item, key, value)

        await self.db.commit()
        await self.db.refresh(item)

        logger.info(f"Updated action item {item_id}")
        return item

    async def delete(
        self,
        tenant_id: UUID,
        item_id: UUID,
    ) -> bool:
        """Delete an action item."""
        item = await self.get_by_id(tenant_id, item_id)
        if not item:
            return False

        await self.db.delete(item)
        await self.db.commit()

        logger.info(f"Deleted action item {item_id}")
        return True

    async def start(
        self,
        tenant_id: UUID,
        item_id: UUID,
    ) -> ActionItem | None:
        """Mark an action item as in progress."""
        item = await self.get_by_id(tenant_id, item_id)
        if not item:
            return None

        if item.status in (ActionItemStatus.COMPLETED, ActionItemStatus.CANCELLED):
            return None  # Can't start completed/cancelled items

        item.status = ActionItemStatus.IN_PROGRESS
        item.started_at = datetime.now(UTC)

        await self.db.commit()
        await self.db.refresh(item)

        logger.info(f"Started action item {item_id}")
        return item

    async def complete(
        self,
        tenant_id: UUID,
        item_id: UUID,
        resolution_notes: str | None = None,
    ) -> ActionItem | None:
        """Mark an action item as completed."""
        item = await self.get_by_id(tenant_id, item_id)
        if not item:
            return None

        if item.status == ActionItemStatus.CANCELLED:
            return None  # Can't complete cancelled items

        item.status = ActionItemStatus.COMPLETED
        item.completed_at = datetime.now(UTC)
        if resolution_notes:
            item.resolution_notes = resolution_notes

        # If wasn't started, set started_at too
        if not item.started_at:
            item.started_at = item.completed_at

        await self.db.commit()
        await self.db.refresh(item)

        logger.info(f"Completed action item {item_id}")
        return item

    async def cancel(
        self,
        tenant_id: UUID,
        item_id: UUID,
    ) -> ActionItem | None:
        """Cancel an action item."""
        item = await self.get_by_id(tenant_id, item_id)
        if not item:
            return None

        if item.status == ActionItemStatus.COMPLETED:
            return None  # Can't cancel completed items

        item.status = ActionItemStatus.CANCELLED

        await self.db.commit()
        await self.db.refresh(item)

        logger.info(f"Cancelled action item {item_id}")
        return item

    async def get_stats(
        self,
        tenant_id: UUID,
        assigned_to_user_id: str | None = None,
    ) -> ActionItemStats:
        """Get action item statistics."""
        # Base query
        base_filter = [ActionItem.tenant_id == tenant_id]
        if assigned_to_user_id:
            base_filter.append(ActionItem.assigned_to_user_id == assigned_to_user_id)

        # Count by status
        status_query = (
            select(
                ActionItem.status,
                func.count(ActionItem.id),
            )
            .where(and_(*base_filter))
            .group_by(ActionItem.status)
        )

        status_result = await self.db.execute(status_query)
        status_counts = {row[0]: row[1] for row in status_result.all()}

        # Count by priority (only active items)
        priority_query = (
            select(
                ActionItem.priority,
                func.count(ActionItem.id),
            )
            .where(
                and_(
                    *base_filter,
                    ActionItem.status.notin_(
                        [
                            ActionItemStatus.COMPLETED,
                            ActionItemStatus.CANCELLED,
                        ]
                    ),
                )
            )
            .group_by(ActionItem.priority)
        )

        priority_result = await self.db.execute(priority_query)
        priority_counts = {row[0]: row[1] for row in priority_result.all()}

        # Count overdue
        today = datetime.now(UTC).date()
        overdue_query = select(func.count(ActionItem.id)).where(
            and_(
                *base_filter,
                ActionItem.due_date < today,
                ActionItem.status.notin_(
                    [
                        ActionItemStatus.COMPLETED,
                        ActionItemStatus.CANCELLED,
                    ]
                ),
            )
        )
        overdue_result = await self.db.execute(overdue_query)
        overdue_count = overdue_result.scalar() or 0

        return ActionItemStats(
            total=sum(status_counts.values()),
            pending=status_counts.get(ActionItemStatus.PENDING, 0),
            in_progress=status_counts.get(ActionItemStatus.IN_PROGRESS, 0),
            completed=status_counts.get(ActionItemStatus.COMPLETED, 0),
            cancelled=status_counts.get(ActionItemStatus.CANCELLED, 0),
            overdue=overdue_count,
            urgent=priority_counts.get(ActionItemPriority.URGENT, 0),
            high=priority_counts.get(ActionItemPriority.HIGH, 0),
            medium=priority_counts.get(ActionItemPriority.MEDIUM, 0),
            low=priority_counts.get(ActionItemPriority.LOW, 0),
        )
