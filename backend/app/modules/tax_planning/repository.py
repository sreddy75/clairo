"""Repository layer for Tax Planning module.

All methods use flush() not commit() — session lifecycle managed by caller.
All tenant-scoped queries filter by tenant_id.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tax_planning.models import (
    ImplementationItem,
    TaxPlan,
    TaxPlanAnalysis,
    TaxPlanMessage,
    TaxRateConfig,
    TaxScenario,
)


class TaxPlanRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: dict[str, Any]) -> TaxPlan:
        plan = TaxPlan(**data)
        self.session.add(plan)
        await self.session.flush()
        await self.session.refresh(plan)
        return plan

    async def get_by_id(self, plan_id: uuid.UUID, tenant_id: uuid.UUID) -> TaxPlan | None:
        result = await self.session.execute(
            select(TaxPlan).where(
                TaxPlan.id == plan_id,
                TaxPlan.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_client_fy(
        self,
        xero_connection_id: uuid.UUID,
        financial_year: str,
        tenant_id: uuid.UUID,
    ) -> TaxPlan | None:
        result = await self.session.execute(
            select(TaxPlan).where(
                TaxPlan.xero_connection_id == xero_connection_id,
                TaxPlan.financial_year == financial_year,
                TaxPlan.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_tenant(
        self,
        tenant_id: uuid.UUID,
        status: str | None = None,
        financial_year: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[TaxPlan], int]:
        query = select(TaxPlan).where(TaxPlan.tenant_id == tenant_id)

        if status:
            query = query.where(TaxPlan.status == status)
        if financial_year:
            query = query.where(TaxPlan.financial_year == financial_year)

        # Count query
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar_one()

        # Paginated query
        query = query.order_by(TaxPlan.updated_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        plans = list(result.scalars().all())

        return plans, total

    async def update(self, plan: TaxPlan, data: dict[str, Any]) -> TaxPlan:
        for key, value in data.items():
            if hasattr(plan, key) and value is not None:
                setattr(plan, key, value)
        await self.session.flush()
        await self.session.refresh(plan)
        return plan

    async def list_by_connection(
        self,
        xero_connection_id: uuid.UUID,
        tenant_id: uuid.UUID,
        active_only: bool = True,
    ) -> list[TaxPlan]:
        """Return all tax plans for a Xero connection.

        Args:
            xero_connection_id: The Xero connection ID.
            tenant_id: Tenant ID for RLS.
            active_only: If True, exclude finalised plans (default True).

        Returns:
            List of matching TaxPlan records.
        """
        query = select(TaxPlan).where(
            TaxPlan.xero_connection_id == xero_connection_id,
            TaxPlan.tenant_id == tenant_id,
        )
        if active_only:
            query = query.where(TaxPlan.status.in_(["draft", "in_progress"]))
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def delete(self, plan: TaxPlan) -> None:
        await self.session.delete(plan)
        await self.session.flush()


class TaxScenarioRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: dict[str, Any]) -> TaxScenario:
        scenario = TaxScenario(**data)
        self.session.add(scenario)
        await self.session.flush()
        await self.session.refresh(scenario)
        return scenario

    async def get_by_id(self, scenario_id: uuid.UUID, tenant_id: uuid.UUID) -> TaxScenario | None:
        result = await self.session.execute(
            select(TaxScenario).where(
                TaxScenario.id == scenario_id,
                TaxScenario.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_plan(self, tax_plan_id: uuid.UUID, tenant_id: uuid.UUID) -> list[TaxScenario]:
        result = await self.session.execute(
            select(TaxScenario)
            .where(
                TaxScenario.tax_plan_id == tax_plan_id,
                TaxScenario.tenant_id == tenant_id,
            )
            .order_by(TaxScenario.sort_order)
        )
        return list(result.scalars().all())

    async def delete(self, scenario: TaxScenario) -> None:
        await self.session.delete(scenario)
        await self.session.flush()

    async def get_next_sort_order(self, tax_plan_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(func.coalesce(func.max(TaxScenario.sort_order), -1)).where(
                TaxScenario.tax_plan_id == tax_plan_id
            )
        )
        return result.scalar_one() + 1


class TaxPlanMessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: dict[str, Any]) -> TaxPlanMessage:
        message = TaxPlanMessage(**data)
        self.session.add(message)
        await self.session.flush()
        await self.session.refresh(message)
        return message

    async def list_by_plan(
        self,
        tax_plan_id: uuid.UUID,
        tenant_id: uuid.UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[TaxPlanMessage], int]:
        base = select(TaxPlanMessage).where(
            TaxPlanMessage.tax_plan_id == tax_plan_id,
            TaxPlanMessage.tenant_id == tenant_id,
        )

        count_result = await self.session.execute(select(func.count()).select_from(base.subquery()))
        total = count_result.scalar_one()

        query = base.order_by(TaxPlanMessage.created_at.asc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        messages = list(result.scalars().all())

        return messages, total

    async def get_recent_messages(
        self, tax_plan_id: uuid.UUID, max_tokens: int = 8000
    ) -> list[TaxPlanMessage]:
        """Get recent messages newest-first, up to max_tokens cumulative."""
        result = await self.session.execute(
            select(TaxPlanMessage)
            .where(TaxPlanMessage.tax_plan_id == tax_plan_id)
            .order_by(TaxPlanMessage.created_at.desc())
        )
        messages = list(result.scalars().all())

        selected: list[TaxPlanMessage] = []
        cumulative_tokens = 0
        for msg in messages:
            token_count = msg.token_count or len(msg.content) // 4
            if cumulative_tokens + token_count > max_tokens:
                break
            selected.append(msg)
            cumulative_tokens += token_count

        # Return in chronological order
        selected.reverse()
        return selected


class TaxRateConfigRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_rates_for_year(self, financial_year: str) -> list[TaxRateConfig]:
        result = await self.session.execute(
            select(TaxRateConfig).where(TaxRateConfig.financial_year == financial_year)
        )
        return list(result.scalars().all())

    async def get_rate(self, financial_year: str, rate_type: str) -> TaxRateConfig | None:
        result = await self.session.execute(
            select(TaxRateConfig).where(
                TaxRateConfig.financial_year == financial_year,
                TaxRateConfig.rate_type == rate_type,
            )
        )
        return result.scalar_one_or_none()


class AnalysisRepository:
    """Repository for TaxPlanAnalysis CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: dict[str, Any]) -> TaxPlanAnalysis:
        analysis = TaxPlanAnalysis(**data)
        self.session.add(analysis)
        await self.session.flush()
        await self.session.refresh(analysis)
        return analysis

    async def get_by_id(
        self,
        analysis_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> TaxPlanAnalysis | None:
        result = await self.session.execute(
            select(TaxPlanAnalysis).where(
                TaxPlanAnalysis.id == analysis_id,
                TaxPlanAnalysis.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_current_for_plan(
        self,
        tax_plan_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> TaxPlanAnalysis | None:
        result = await self.session.execute(
            select(TaxPlanAnalysis).where(
                TaxPlanAnalysis.tax_plan_id == tax_plan_id,
                TaxPlanAnalysis.tenant_id == tenant_id,
                TaxPlanAnalysis.is_current.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def list_versions(
        self,
        tax_plan_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> list[TaxPlanAnalysis]:
        result = await self.session.execute(
            select(TaxPlanAnalysis)
            .where(
                TaxPlanAnalysis.tax_plan_id == tax_plan_id,
                TaxPlanAnalysis.tenant_id == tenant_id,
            )
            .order_by(TaxPlanAnalysis.version.desc())
        )
        return list(result.scalars().all())

    async def update(
        self,
        analysis: TaxPlanAnalysis,
        data: dict[str, Any],
    ) -> TaxPlanAnalysis:
        for key, value in data.items():
            if hasattr(analysis, key) and value is not None:
                setattr(analysis, key, value)
        await self.session.flush()
        await self.session.refresh(analysis)
        return analysis

    async def set_current(
        self,
        tax_plan_id: uuid.UUID,
        analysis_id: uuid.UUID,
    ) -> None:
        """Mark one analysis as current, unmark all others for this plan."""
        await self.session.execute(
            update(TaxPlanAnalysis)
            .where(TaxPlanAnalysis.tax_plan_id == tax_plan_id)
            .values(is_current=False)
        )
        await self.session.execute(
            update(TaxPlanAnalysis).where(TaxPlanAnalysis.id == analysis_id).values(is_current=True)
        )
        await self.session.flush()


class ImplementationItemRepository:
    """Repository for ImplementationItem CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_batch(
        self,
        items: list[dict[str, Any]],
    ) -> list[ImplementationItem]:
        records = [ImplementationItem(**item) for item in items]
        self.session.add_all(records)
        await self.session.flush()
        for r in records:
            await self.session.refresh(r)
        return records

    async def list_by_analysis(
        self,
        analysis_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> list[ImplementationItem]:
        result = await self.session.execute(
            select(ImplementationItem)
            .where(
                ImplementationItem.analysis_id == analysis_id,
                ImplementationItem.tenant_id == tenant_id,
            )
            .order_by(ImplementationItem.sort_order)
        )
        return list(result.scalars().all())

    async def get_by_id(
        self,
        item_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> ImplementationItem | None:
        result = await self.session.execute(
            select(ImplementationItem).where(
                ImplementationItem.id == item_id,
                ImplementationItem.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        item_id: uuid.UUID,
        tenant_id: uuid.UUID,
        status: str,
        completed_by: str | None = None,
    ) -> ImplementationItem | None:
        item = await self.get_by_id(item_id, tenant_id)
        if not item:
            return None
        item.status = status
        if status == "completed":
            item.completed_at = datetime.now(UTC)
            item.completed_by = completed_by
        await self.session.flush()
        await self.session.refresh(item)
        return item
