"""Repository layer for client AI context aggregations.

Provides CRUD operations and upsert methods for all aggregation models.
All methods are tenant-aware via RLS.

IMPORTANT: All aggregation tables use connection_id (XeroConnection/organization)
as the primary grouping key, NOT client_id (XeroClient/contact). This is because
financial data belongs to the organization, not individual contacts.
"""

from collections.abc import Sequence
from datetime import date
from uuid import UUID

from sqlalchemy import case, delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.knowledge.aggregation_models import (
    ClientAIProfile,
    ClientAPAgingSummary,
    ClientARAgingSummary,
    ClientComplianceSummary,
    ClientExpenseSummary,
    ClientGSTSummary,
    ClientMonthlyTrend,
    PeriodType,
)


class AggregationRepository:
    """Repository for client AI context aggregations.

    All methods use connection_id to identify the organization, which is
    the correct grouping for financial data in Clairo.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # ClientAIProfile
    # =========================================================================

    async def get_profile_by_connection(
        self,
        connection_id: UUID,
    ) -> ClientAIProfile | None:
        """Get client AI profile by connection ID (XeroConnection/organization).

        This is the primary method for client-context chat since we
        identify clients by their organization (XeroConnection).
        """
        result = await self.db.execute(
            select(ClientAIProfile).where(ClientAIProfile.connection_id == connection_id)
        )
        return result.scalar_one_or_none()

    async def upsert_client_profile(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        client_id: UUID | None = None,
        **data,
    ) -> ClientAIProfile:
        """Insert or update client AI profile.

        Args:
            tenant_id: The tenant ID for RLS
            connection_id: The XeroConnection ID (organization) - required
            client_id: Optional XeroClient ID (contact) - nullable
            **data: Additional profile fields
        """
        stmt = insert(ClientAIProfile).values(
            tenant_id=tenant_id,
            connection_id=connection_id,
            client_id=client_id,
            **data,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_client_ai_profile_connection",
            set_={
                "client_id": stmt.excluded.client_id,
                "entity_type": func.coalesce(
                    stmt.excluded.entity_type, ClientAIProfile.entity_type
                ),
                "industry_code": func.coalesce(
                    stmt.excluded.industry_code, ClientAIProfile.industry_code
                ),
                # Never downgrade gst_registered from True to False — the Xero
                # Organisation API (TaxNumber + SalesTaxBasis) is authoritative
                # and heuristic-based recomputation must not overwrite it.
                "gst_registered": case(
                    (ClientAIProfile.gst_registered == True, True),  # noqa: E712
                    else_=stmt.excluded.gst_registered,
                ),
                "revenue_bracket": func.coalesce(
                    stmt.excluded.revenue_bracket, ClientAIProfile.revenue_bracket
                ),
                "employee_count": stmt.excluded.employee_count,
                "computed_at": stmt.excluded.computed_at,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        await self.db.execute(stmt)
        await self.db.flush()
        return await self.get_profile_by_connection(connection_id)  # type: ignore

    async def delete_client_profile(self, connection_id: UUID) -> bool:
        """Delete client AI profile by connection ID."""
        result = await self.db.execute(
            delete(ClientAIProfile).where(ClientAIProfile.connection_id == connection_id)
        )
        return result.rowcount > 0

    # =========================================================================
    # ClientExpenseSummary
    # =========================================================================

    async def get_expense_summary(
        self,
        connection_id: UUID,
        period_type: PeriodType,
        period_start: date,
    ) -> ClientExpenseSummary | None:
        """Get expense summary for a specific period."""
        result = await self.db.execute(
            select(ClientExpenseSummary).where(
                ClientExpenseSummary.connection_id == connection_id,
                ClientExpenseSummary.period_type == period_type,
                ClientExpenseSummary.period_start == period_start,
            )
        )
        return result.scalar_one_or_none()

    async def get_expense_summaries(
        self,
        connection_id: UUID,
        period_type: PeriodType | None = None,
        limit: int = 12,
    ) -> Sequence[ClientExpenseSummary]:
        """Get expense summaries for an organization, ordered by period descending."""
        query = select(ClientExpenseSummary).where(
            ClientExpenseSummary.connection_id == connection_id
        )
        if period_type:
            query = query.where(ClientExpenseSummary.period_type == period_type)
        query = query.order_by(ClientExpenseSummary.period_start.desc()).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def upsert_expense_summary(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        period_type: PeriodType,
        period_start: date,
        period_end: date,
        **data,
    ) -> ClientExpenseSummary:
        """Insert or update expense summary."""
        stmt = insert(ClientExpenseSummary).values(
            tenant_id=tenant_id,
            connection_id=connection_id,
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
            **data,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_expense_summary_connection_period",
            set_={
                "period_end": stmt.excluded.period_end,
                "by_account_code": stmt.excluded.by_account_code,
                "by_category": stmt.excluded.by_category,
                "total_expenses": stmt.excluded.total_expenses,
                "total_gst": stmt.excluded.total_gst,
                "transaction_count": stmt.excluded.transaction_count,
                "computed_at": stmt.excluded.computed_at,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        await self.db.execute(stmt)
        await self.db.flush()
        return await self.get_expense_summary(connection_id, period_type, period_start)  # type: ignore

    # =========================================================================
    # ClientARAgingSummary
    # =========================================================================

    async def get_ar_aging(
        self,
        connection_id: UUID,
        as_of_date: date,
    ) -> ClientARAgingSummary | None:
        """Get AR aging summary for a specific date."""
        result = await self.db.execute(
            select(ClientARAgingSummary).where(
                ClientARAgingSummary.connection_id == connection_id,
                ClientARAgingSummary.as_of_date == as_of_date,
            )
        )
        return result.scalar_one_or_none()

    async def get_latest_ar_aging(
        self,
        connection_id: UUID,
    ) -> ClientARAgingSummary | None:
        """Get the most recent AR aging summary."""
        result = await self.db.execute(
            select(ClientARAgingSummary)
            .where(ClientARAgingSummary.connection_id == connection_id)
            .order_by(ClientARAgingSummary.as_of_date.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def upsert_ar_aging(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        as_of_date: date,
        **data,
    ) -> ClientARAgingSummary:
        """Insert or update AR aging summary."""
        stmt = insert(ClientARAgingSummary).values(
            tenant_id=tenant_id,
            connection_id=connection_id,
            as_of_date=as_of_date,
            **data,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_ar_aging_connection_date",
            set_={
                "current_amount": stmt.excluded.current_amount,
                "days_31_60": stmt.excluded.days_31_60,
                "days_61_90": stmt.excluded.days_61_90,
                "over_90_days": stmt.excluded.over_90_days,
                "total_outstanding": stmt.excluded.total_outstanding,
                "top_debtors": stmt.excluded.top_debtors,
                "computed_at": stmt.excluded.computed_at,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        await self.db.execute(stmt)
        await self.db.flush()
        return await self.get_ar_aging(connection_id, as_of_date)  # type: ignore

    # =========================================================================
    # ClientAPAgingSummary
    # =========================================================================

    async def get_ap_aging(
        self,
        connection_id: UUID,
        as_of_date: date,
    ) -> ClientAPAgingSummary | None:
        """Get AP aging summary for a specific date."""
        result = await self.db.execute(
            select(ClientAPAgingSummary).where(
                ClientAPAgingSummary.connection_id == connection_id,
                ClientAPAgingSummary.as_of_date == as_of_date,
            )
        )
        return result.scalar_one_or_none()

    async def get_latest_ap_aging(
        self,
        connection_id: UUID,
    ) -> ClientAPAgingSummary | None:
        """Get the most recent AP aging summary."""
        result = await self.db.execute(
            select(ClientAPAgingSummary)
            .where(ClientAPAgingSummary.connection_id == connection_id)
            .order_by(ClientAPAgingSummary.as_of_date.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def upsert_ap_aging(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        as_of_date: date,
        **data,
    ) -> ClientAPAgingSummary:
        """Insert or update AP aging summary."""
        stmt = insert(ClientAPAgingSummary).values(
            tenant_id=tenant_id,
            connection_id=connection_id,
            as_of_date=as_of_date,
            **data,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_ap_aging_connection_date",
            set_={
                "current_amount": stmt.excluded.current_amount,
                "days_31_60": stmt.excluded.days_31_60,
                "days_61_90": stmt.excluded.days_61_90,
                "over_90_days": stmt.excluded.over_90_days,
                "total_outstanding": stmt.excluded.total_outstanding,
                "top_creditors": stmt.excluded.top_creditors,
                "computed_at": stmt.excluded.computed_at,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        await self.db.execute(stmt)
        await self.db.flush()
        return await self.get_ap_aging(connection_id, as_of_date)  # type: ignore

    # =========================================================================
    # ClientGSTSummary
    # =========================================================================

    async def get_gst_summary(
        self,
        connection_id: UUID,
        period_type: PeriodType,
        period_start: date,
    ) -> ClientGSTSummary | None:
        """Get GST summary for a specific period."""
        result = await self.db.execute(
            select(ClientGSTSummary).where(
                ClientGSTSummary.connection_id == connection_id,
                ClientGSTSummary.period_type == period_type,
                ClientGSTSummary.period_start == period_start,
            )
        )
        return result.scalar_one_or_none()

    async def get_gst_summaries(
        self,
        connection_id: UUID,
        period_type: PeriodType | None = None,
        limit: int = 8,
    ) -> Sequence[ClientGSTSummary]:
        """Get GST summaries for an organization, ordered by period descending."""
        query = select(ClientGSTSummary).where(ClientGSTSummary.connection_id == connection_id)
        if period_type:
            query = query.where(ClientGSTSummary.period_type == period_type)
        query = query.order_by(ClientGSTSummary.period_start.desc()).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def upsert_gst_summary(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        period_type: PeriodType,
        period_start: date,
        period_end: date,
        **data,
    ) -> ClientGSTSummary:
        """Insert or update GST summary."""
        stmt = insert(ClientGSTSummary).values(
            tenant_id=tenant_id,
            connection_id=connection_id,
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
            **data,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_gst_summary_connection_period",
            set_={
                "period_end": stmt.excluded.period_end,
                "gst_on_sales_1a": stmt.excluded.gst_on_sales_1a,
                "gst_on_purchases_1b": stmt.excluded.gst_on_purchases_1b,
                "net_gst": stmt.excluded.net_gst,
                "total_sales": stmt.excluded.total_sales,
                "total_purchases": stmt.excluded.total_purchases,
                "adjustments": stmt.excluded.adjustments,
                "computed_at": stmt.excluded.computed_at,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        await self.db.execute(stmt)
        await self.db.flush()
        return await self.get_gst_summary(connection_id, period_type, period_start)  # type: ignore

    # =========================================================================
    # ClientMonthlyTrend
    # =========================================================================

    async def get_monthly_trend(
        self,
        connection_id: UUID,
        year: int,
        month: int,
    ) -> ClientMonthlyTrend | None:
        """Get monthly trend for a specific month."""
        result = await self.db.execute(
            select(ClientMonthlyTrend).where(
                ClientMonthlyTrend.connection_id == connection_id,
                ClientMonthlyTrend.year == year,
                ClientMonthlyTrend.month == month,
            )
        )
        return result.scalar_one_or_none()

    async def get_monthly_trends(
        self,
        connection_id: UUID,
        months: int = 12,
    ) -> Sequence[ClientMonthlyTrend]:
        """Get monthly trends for an organization, ordered by date descending."""
        result = await self.db.execute(
            select(ClientMonthlyTrend)
            .where(ClientMonthlyTrend.connection_id == connection_id)
            .order_by(
                ClientMonthlyTrend.year.desc(),
                ClientMonthlyTrend.month.desc(),
            )
            .limit(months)
        )
        return result.scalars().all()

    async def upsert_monthly_trend(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        year: int,
        month: int,
        **data,
    ) -> ClientMonthlyTrend:
        """Insert or update monthly trend."""
        stmt = insert(ClientMonthlyTrend).values(
            tenant_id=tenant_id,
            connection_id=connection_id,
            year=year,
            month=month,
            **data,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_monthly_trend_connection_period",
            set_={
                "revenue": stmt.excluded.revenue,
                "expenses": stmt.excluded.expenses,
                "gross_profit": stmt.excluded.gross_profit,
                "net_cashflow": stmt.excluded.net_cashflow,
                "computed_at": stmt.excluded.computed_at,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        await self.db.execute(stmt)
        await self.db.flush()
        return await self.get_monthly_trend(connection_id, year, month)  # type: ignore

    # =========================================================================
    # ClientComplianceSummary
    # =========================================================================

    async def get_compliance_summary(
        self,
        connection_id: UUID,
        period_type: PeriodType,
        period_start: date,
    ) -> ClientComplianceSummary | None:
        """Get compliance summary for a specific period."""
        result = await self.db.execute(
            select(ClientComplianceSummary).where(
                ClientComplianceSummary.connection_id == connection_id,
                ClientComplianceSummary.period_type == period_type,
                ClientComplianceSummary.period_start == period_start,
            )
        )
        return result.scalar_one_or_none()

    async def get_compliance_summaries(
        self,
        connection_id: UUID,
        period_type: PeriodType | None = None,
        limit: int = 8,
    ) -> Sequence[ClientComplianceSummary]:
        """Get compliance summaries for an organization, ordered by period descending."""
        query = select(ClientComplianceSummary).where(
            ClientComplianceSummary.connection_id == connection_id
        )
        if period_type:
            query = query.where(ClientComplianceSummary.period_type == period_type)
        query = query.order_by(ClientComplianceSummary.period_start.desc()).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def upsert_compliance_summary(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        period_type: PeriodType,
        period_start: date,
        period_end: date,
        **data,
    ) -> ClientComplianceSummary:
        """Insert or update compliance summary."""
        stmt = insert(ClientComplianceSummary).values(
            tenant_id=tenant_id,
            connection_id=connection_id,
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
            **data,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_compliance_summary_connection_period",
            set_={
                "period_end": stmt.excluded.period_end,
                "total_wages": stmt.excluded.total_wages,
                "total_payg_withheld": stmt.excluded.total_payg_withheld,
                "total_super": stmt.excluded.total_super,
                "employee_count": stmt.excluded.employee_count,
                "contractor_payments": stmt.excluded.contractor_payments,
                "contractor_count": stmt.excluded.contractor_count,
                "computed_at": stmt.excluded.computed_at,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        await self.db.execute(stmt)
        await self.db.flush()
        return await self.get_compliance_summary(connection_id, period_type, period_start)  # type: ignore

    # =========================================================================
    # Bulk Operations
    # =========================================================================

    async def delete_all_for_connection(self, connection_id: UUID) -> dict[str, int]:
        """Delete all aggregations for an organization. Returns counts per table."""
        counts = {}
        tables = [
            ("profiles", ClientAIProfile),
            ("expenses", ClientExpenseSummary),
            ("ar_aging", ClientARAgingSummary),
            ("ap_aging", ClientAPAgingSummary),
            ("gst", ClientGSTSummary),
            ("trends", ClientMonthlyTrend),
            ("compliance", ClientComplianceSummary),
        ]
        for name, model in tables:
            result = await self.db.execute(
                delete(model).where(model.connection_id == connection_id)
            )
            counts[name] = result.rowcount
        return counts
