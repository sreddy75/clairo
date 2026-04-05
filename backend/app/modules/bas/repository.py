"""Repository for BAS preparation workflow data access."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.bas.classification_models import (
    ClassificationRequest,
    ClientClassification,
)
from app.modules.bas.models import (
    BASAdjustment,
    BASAuditLog,
    BASCalculation,
    BASPeriod,
    BASSession,
    TaxCodeOverride,
    TaxCodeSuggestion,
)


class BASRepository:
    """Repository for BAS data operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # =========================================================================
    # Period Operations
    # =========================================================================

    async def create_period(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        quarter: int,
        fy_year: int,
        start_date: datetime | date,
        end_date: datetime | date,
        due_date: datetime | date,
    ) -> BASPeriod:
        """Create a new BAS period."""
        period = BASPeriod(
            tenant_id=tenant_id,
            connection_id=connection_id,
            period_type="quarterly",
            quarter=quarter,
            fy_year=fy_year,
            start_date=start_date.date() if isinstance(start_date, datetime) else start_date,
            end_date=end_date.date() if isinstance(end_date, datetime) else end_date,
            due_date=due_date.date() if isinstance(due_date, datetime) else due_date,
        )
        self.session.add(period)
        await self.session.flush()
        await self.session.refresh(period)
        return period

    async def get_period(
        self,
        period_id: UUID,
        tenant_id: UUID | None = None,
    ) -> BASPeriod | None:
        """Get a period by ID."""
        query = (
            select(BASPeriod)
            .options(selectinload(BASPeriod.session))
            .where(BASPeriod.id == period_id)
        )
        if tenant_id is not None:
            query = query.where(BASPeriod.tenant_id == tenant_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_period_by_quarter(
        self,
        connection_id: UUID,
        quarter: int,
        fy_year: int,
    ) -> BASPeriod | None:
        """Get a period by connection and quarter."""
        result = await self.session.execute(
            select(BASPeriod)
            .options(selectinload(BASPeriod.session))
            .where(
                BASPeriod.connection_id == connection_id,
                BASPeriod.quarter == quarter,
                BASPeriod.fy_year == fy_year,
            )
        )
        return result.scalar_one_or_none()

    async def list_periods(
        self,
        connection_id: UUID,
        limit: int = 12,
    ) -> list[BASPeriod]:
        """List periods for a connection, most recent first."""
        result = await self.session.execute(
            select(BASPeriod)
            .options(selectinload(BASPeriod.session))
            .where(BASPeriod.connection_id == connection_id)
            .order_by(BASPeriod.fy_year.desc(), BASPeriod.quarter.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # =========================================================================
    # Session Operations
    # =========================================================================

    async def create_session(
        self,
        tenant_id: UUID,
        period_id: UUID,
        created_by: UUID,
        auto_created: bool = False,
    ) -> BASSession:
        """Create a new BAS session."""
        session = BASSession(
            tenant_id=tenant_id,
            period_id=period_id,
            status="draft",
            created_by=created_by,
            auto_created=auto_created,
        )
        self.session.add(session)
        await self.session.flush()
        await self.session.refresh(session)
        return session

    async def get_session(
        self,
        session_id: UUID,
        tenant_id: UUID | None = None,
    ) -> BASSession | None:
        """Get a session by ID with all related data."""
        query = (
            select(BASSession)
            .options(
                selectinload(BASSession.period),
                selectinload(BASSession.calculation),
                selectinload(BASSession.adjustments),
            )
            .where(BASSession.id == session_id)
        )
        if tenant_id is not None:
            query = query.where(BASSession.tenant_id == tenant_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_session_by_period(
        self,
        period_id: UUID,
    ) -> BASSession | None:
        """Get a session by period ID."""
        result = await self.session.execute(
            select(BASSession)
            .options(
                selectinload(BASSession.period),
                selectinload(BASSession.calculation),
            )
            .where(BASSession.period_id == period_id)
        )
        return result.scalar_one_or_none()

    async def list_sessions(
        self,
        connection_id: UUID,
        limit: int = 20,
    ) -> list[BASSession]:
        """List sessions for a connection."""
        result = await self.session.execute(
            select(BASSession)
            .join(BASPeriod)
            .options(
                selectinload(BASSession.period),
                selectinload(BASSession.calculation),
            )
            .where(BASPeriod.connection_id == connection_id)
            .order_by(BASPeriod.fy_year.desc(), BASPeriod.quarter.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_session(
        self,
        session: BASSession,
        **kwargs: object,
    ) -> BASSession:
        """Update session fields."""
        for key, value in kwargs.items():
            if hasattr(session, key):
                setattr(session, key, value)
        session.updated_at = datetime.now(UTC)
        await self.session.flush()
        await self.session.refresh(session)
        return session

    # =========================================================================
    # Calculation Operations
    # =========================================================================

    async def upsert_calculation(
        self,
        tenant_id: UUID,
        session_id: UUID,
        g1_total_sales: Decimal,
        g2_export_sales: Decimal,
        g3_gst_free_sales: Decimal,
        g10_capital_purchases: Decimal,
        g11_non_capital_purchases: Decimal,
        field_1a_gst_on_sales: Decimal,
        field_1b_gst_on_purchases: Decimal,
        w1_total_wages: Decimal,
        w2_amount_withheld: Decimal,
        gst_payable: Decimal,
        total_payable: Decimal,
        calculation_duration_ms: int,
        transaction_count: int,
        invoice_count: int,
        pay_run_count: int,
    ) -> BASCalculation:
        """Create or update a calculation."""
        # Check for existing calculation
        result = await self.session.execute(
            select(BASCalculation).where(BASCalculation.session_id == session_id)
        )
        calculation = result.scalar_one_or_none()

        now = datetime.now(UTC)

        if calculation:
            # Update existing
            calculation.g1_total_sales = g1_total_sales
            calculation.g2_export_sales = g2_export_sales
            calculation.g3_gst_free_sales = g3_gst_free_sales
            calculation.g10_capital_purchases = g10_capital_purchases
            calculation.g11_non_capital_purchases = g11_non_capital_purchases
            calculation.field_1a_gst_on_sales = field_1a_gst_on_sales
            calculation.field_1b_gst_on_purchases = field_1b_gst_on_purchases
            calculation.w1_total_wages = w1_total_wages
            calculation.w2_amount_withheld = w2_amount_withheld
            calculation.gst_payable = gst_payable
            calculation.total_payable = total_payable
            calculation.calculated_at = now
            calculation.calculation_duration_ms = calculation_duration_ms
            calculation.transaction_count = transaction_count
            calculation.invoice_count = invoice_count
            calculation.pay_run_count = pay_run_count
            calculation.updated_at = now
        else:
            # Create new
            calculation = BASCalculation(
                tenant_id=tenant_id,
                session_id=session_id,
                g1_total_sales=g1_total_sales,
                g2_export_sales=g2_export_sales,
                g3_gst_free_sales=g3_gst_free_sales,
                g10_capital_purchases=g10_capital_purchases,
                g11_non_capital_purchases=g11_non_capital_purchases,
                field_1a_gst_on_sales=field_1a_gst_on_sales,
                field_1b_gst_on_purchases=field_1b_gst_on_purchases,
                w1_total_wages=w1_total_wages,
                w2_amount_withheld=w2_amount_withheld,
                gst_payable=gst_payable,
                total_payable=total_payable,
                calculated_at=now,
                calculation_duration_ms=calculation_duration_ms,
                transaction_count=transaction_count,
                invoice_count=invoice_count,
                pay_run_count=pay_run_count,
            )
            self.session.add(calculation)

        await self.session.flush()
        await self.session.refresh(calculation)
        return calculation

    async def get_calculation(
        self,
        session_id: UUID,
    ) -> BASCalculation | None:
        """Get calculation for a session."""
        result = await self.session.execute(
            select(BASCalculation).where(BASCalculation.session_id == session_id)
        )
        return result.scalar_one_or_none()

    # =========================================================================
    # Adjustment Operations
    # =========================================================================

    async def create_adjustment(
        self,
        tenant_id: UUID,
        session_id: UUID,
        field_name: str,
        adjustment_amount: Decimal,
        reason: str,
        reference: str | None,
        created_by: UUID,
    ) -> BASAdjustment:
        """Create a new adjustment."""
        adjustment = BASAdjustment(
            tenant_id=tenant_id,
            session_id=session_id,
            field_name=field_name,
            adjustment_amount=adjustment_amount,
            reason=reason,
            reference=reference,
            created_by=created_by,
        )
        self.session.add(adjustment)
        await self.session.flush()
        await self.session.refresh(adjustment)
        return adjustment

    async def get_adjustment(
        self,
        adjustment_id: UUID,
        tenant_id: UUID | None = None,
    ) -> BASAdjustment | None:
        """Get an adjustment by ID."""
        query = select(BASAdjustment).where(BASAdjustment.id == adjustment_id)
        if tenant_id is not None:
            query = query.where(BASAdjustment.tenant_id == tenant_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_adjustments(
        self,
        session_id: UUID,
    ) -> list[BASAdjustment]:
        """List adjustments for a session."""
        result = await self.session.execute(
            select(BASAdjustment)
            .where(BASAdjustment.session_id == session_id)
            .order_by(BASAdjustment.created_at)
        )
        return list(result.scalars().all())

    async def delete_adjustment(
        self,
        adjustment_id: UUID,
    ) -> bool:
        """Delete an adjustment."""
        adjustment = await self.get_adjustment(adjustment_id)
        if adjustment:
            await self.session.delete(adjustment)
            await self.session.flush()
            return True
        return False

    # =========================================================================
    # Prior Period Lookup (for variance analysis)
    # =========================================================================

    async def get_prior_quarter_session(
        self,
        connection_id: UUID,
        current_quarter: int,
        current_fy_year: int,
    ) -> BASSession | None:
        """Get the session for the prior quarter."""
        # Calculate prior quarter
        if current_quarter == 1:
            prior_quarter = 4
            prior_fy_year = current_fy_year - 1
        else:
            prior_quarter = current_quarter - 1
            prior_fy_year = current_fy_year

        # Find the period and session
        result = await self.session.execute(
            select(BASSession)
            .join(BASPeriod)
            .options(
                selectinload(BASSession.period),
                selectinload(BASSession.calculation),
            )
            .where(
                BASPeriod.connection_id == connection_id,
                BASPeriod.quarter == prior_quarter,
                BASPeriod.fy_year == prior_fy_year,
            )
        )
        return result.scalar_one_or_none()

    async def get_same_quarter_prior_year_session(
        self,
        connection_id: UUID,
        quarter: int,
        fy_year: int,
    ) -> BASSession | None:
        """Get the session for the same quarter in the prior year."""
        prior_fy_year = fy_year - 1

        result = await self.session.execute(
            select(BASSession)
            .join(BASPeriod)
            .options(
                selectinload(BASSession.period),
                selectinload(BASSession.calculation),
            )
            .where(
                BASPeriod.connection_id == connection_id,
                BASPeriod.quarter == quarter,
                BASPeriod.fy_year == prior_fy_year,
            )
        )
        return result.scalar_one_or_none()

    # =========================================================================
    # Audit Log Operations
    # =========================================================================

    async def create_audit_log(
        self,
        tenant_id: UUID,
        session_id: UUID,
        event_type: str,
        event_description: str,
        from_status: str | None = None,
        to_status: str | None = None,
        performed_by: UUID | None = None,
        performed_by_name: str | None = None,
        is_system_action: bool = False,
        event_metadata: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> BASAuditLog:
        """Create an audit log entry."""
        audit_log = BASAuditLog(
            tenant_id=tenant_id,
            session_id=session_id,
            event_type=event_type,
            event_description=event_description,
            from_status=from_status,
            to_status=to_status,
            performed_by=performed_by,
            performed_by_name=performed_by_name,
            is_system_action=is_system_action,
            event_metadata=event_metadata,
            ip_address=ip_address,
            created_at=datetime.now(UTC),
        )
        self.session.add(audit_log)
        await self.session.flush()
        return audit_log

    async def list_audit_logs(
        self,
        session_id: UUID,
        limit: int = 100,
    ) -> list[BASAuditLog]:
        """List audit logs for a session, most recent first."""
        result = await self.session.execute(
            select(BASAuditLog)
            .where(BASAuditLog.session_id == session_id)
            .order_by(BASAuditLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # =========================================================================
    # Lodgement Operations (Spec 011)
    # =========================================================================

    async def list_sessions_by_lodgement_status(
        self,
        connection_id: UUID,
        lodgement_status: str = "all",
        limit: int = 20,
    ) -> list[BASSession]:
        """List sessions for a connection filtered by lodgement status.

        Args:
            connection_id: The Xero connection ID
            lodgement_status: Filter by lodgement status:
                - "all": Return all sessions
                - "lodged": Return only lodged sessions
                - "not_lodged": Return only unlodged sessions
            limit: Maximum number of sessions to return

        Returns:
            List of BASSession objects
        """
        stmt = (
            select(BASSession)
            .join(BASPeriod)
            .options(
                selectinload(BASSession.period),
                selectinload(BASSession.calculation),
                selectinload(BASSession.lodged_by_user),
            )
            .where(BASPeriod.connection_id == connection_id)
        )

        if lodgement_status == "lodged":
            stmt = stmt.where(BASSession.lodged_at.isnot(None))
        elif lodgement_status == "not_lodged":
            stmt = stmt.where(BASSession.lodged_at.is_(None))

        stmt = stmt.order_by(BASPeriod.fy_year.desc(), BASPeriod.quarter.desc()).limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_sessions_with_approaching_deadlines(
        self,
        tenant_id: UUID,
        days_ahead: int = 7,
        reference_date: date | None = None,
    ) -> list[BASSession]:
        """Get BAS sessions with deadlines approaching within specified days.

        Args:
            tenant_id: The tenant ID
            days_ahead: Number of days to look ahead
            reference_date: Reference date for calculation (defaults to today)

        Returns:
            List of BASSession objects with approaching deadlines that are not yet lodged
        """
        from datetime import timedelta

        if reference_date is None:
            reference_date = date.today()

        deadline_cutoff = reference_date + timedelta(days=days_ahead)

        stmt = (
            select(BASSession)
            .join(BASPeriod)
            .options(
                selectinload(BASSession.period),
                selectinload(BASSession.calculation),
            )
            .where(
                BASSession.tenant_id == tenant_id,
                BASSession.lodged_at.is_(None),  # Not lodged
                BASPeriod.due_date <= deadline_cutoff,
                BASPeriod.due_date >= reference_date,  # Not past due
            )
            .order_by(BASPeriod.due_date.asc())
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_all_unlodged_sessions_by_tenant(
        self,
        days_ahead: int = 7,
        reference_date: date | None = None,
    ) -> list[tuple[UUID, BASSession]]:
        """Get all unlodged BAS sessions with approaching deadlines across all tenants.

        Used by the deadline notification scheduled task.

        Args:
            days_ahead: Number of days to look ahead
            reference_date: Reference date for calculation (defaults to today)

        Returns:
            List of (tenant_id, BASSession) tuples
        """
        from datetime import timedelta

        if reference_date is None:
            reference_date = date.today()

        deadline_cutoff = reference_date + timedelta(days=days_ahead)

        stmt = (
            select(BASSession)
            .join(BASPeriod)
            .options(
                selectinload(BASSession.period),
            )
            .where(
                BASSession.lodged_at.is_(None),  # Not lodged
                BASPeriod.due_date <= deadline_cutoff,
                BASPeriod.due_date >= reference_date,  # Not past due
            )
            .order_by(BASSession.tenant_id, BASPeriod.due_date.asc())
        )

        result = await self.session.execute(stmt)
        sessions = list(result.scalars().all())
        return [(s.tenant_id, s) for s in sessions]

    # =========================================================================
    # Tax Code Suggestion Operations (Spec 046)
    # =========================================================================

    async def create_suggestion(self, data: dict[str, Any]) -> TaxCodeSuggestion:
        """Create a single tax code suggestion."""
        suggestion = TaxCodeSuggestion(**data)
        self.session.add(suggestion)
        await self.session.flush()
        await self.session.refresh(suggestion)
        return suggestion

    async def bulk_create_suggestions(self, items: list[dict[str, Any]]) -> int:
        """Bulk insert suggestions with ON CONFLICT DO NOTHING for idempotency.

        Returns the number of rows actually inserted.
        """
        if not items:
            return 0

        stmt = insert(TaxCodeSuggestion).values(items)
        stmt = stmt.on_conflict_do_nothing(
            constraint="uq_tax_code_suggestion_session_source_line",
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

    async def get_suggestion(
        self, suggestion_id: UUID, tenant_id: UUID
    ) -> TaxCodeSuggestion | None:
        """Get a suggestion by ID with tenant scoping."""
        result = await self.session.execute(
            select(TaxCodeSuggestion).where(
                TaxCodeSuggestion.id == suggestion_id,
                TaxCodeSuggestion.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_suggestions(
        self,
        session_id: UUID,
        tenant_id: UUID,
        status: str | None = None,
        confidence_tier: str | None = None,
        min_confidence: float | None = None,
    ) -> list[TaxCodeSuggestion]:
        """List suggestions for a BAS session with optional filters."""
        query = select(TaxCodeSuggestion).where(
            TaxCodeSuggestion.session_id == session_id,
            TaxCodeSuggestion.tenant_id == tenant_id,
        )
        if status:
            query = query.where(TaxCodeSuggestion.status == status)
        if confidence_tier:
            query = query.where(TaxCodeSuggestion.confidence_tier == confidence_tier)
        if min_confidence is not None:
            query = query.where(TaxCodeSuggestion.confidence_score >= min_confidence)

        query = query.order_by(
            TaxCodeSuggestion.confidence_score.desc().nulls_last(),
            TaxCodeSuggestion.line_amount.desc().nulls_last(),
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_suggestion_summary(self, session_id: UUID, tenant_id: UUID) -> dict[str, Any]:
        """Get summary counts and amounts for the exclusion banner."""
        # Total count and amount
        total_q = select(
            func.count(TaxCodeSuggestion.id).label("total"),
            func.coalesce(func.sum(TaxCodeSuggestion.line_amount), 0).label("total_amount"),
        ).where(
            TaxCodeSuggestion.session_id == session_id,
            TaxCodeSuggestion.tenant_id == tenant_id,
        )
        total_result = await self.session.execute(total_q)
        total_row = total_result.one()

        # Pending count
        pending_q = select(func.count(TaxCodeSuggestion.id)).where(
            TaxCodeSuggestion.session_id == session_id,
            TaxCodeSuggestion.tenant_id == tenant_id,
            TaxCodeSuggestion.status == "pending",
        )
        pending_result = await self.session.execute(pending_q)
        pending_count = pending_result.scalar() or 0

        # Resolved amount
        resolved_q = select(
            func.count(TaxCodeSuggestion.id).label("count"),
            func.coalesce(func.sum(TaxCodeSuggestion.line_amount), 0).label("amount"),
        ).where(
            TaxCodeSuggestion.session_id == session_id,
            TaxCodeSuggestion.tenant_id == tenant_id,
            TaxCodeSuggestion.status.in_(
                [
                    "approved",
                    "overridden",
                    "dismissed",
                ]
            ),
        )
        resolved_result = await self.session.execute(resolved_q)
        resolved_row = resolved_result.one()

        # High confidence pending
        high_conf_q = select(func.count(TaxCodeSuggestion.id)).where(
            TaxCodeSuggestion.session_id == session_id,
            TaxCodeSuggestion.tenant_id == tenant_id,
            TaxCodeSuggestion.status == "pending",
            TaxCodeSuggestion.confidence_score >= 0.90,
        )
        high_conf_result = await self.session.execute(high_conf_q)
        high_conf_count = high_conf_result.scalar() or 0

        return {
            "excluded_count": total_row.total,
            "excluded_amount": total_row.total_amount,
            "resolved_count": resolved_row.count,
            "unresolved_count": pending_count,
            "has_suggestions": total_row.total > 0,
            "high_confidence_pending": high_conf_count,
            "can_bulk_approve": high_conf_count > 0,
            "blocks_approval": pending_count > 0,
        }

    async def count_unresolved(self, session_id: UUID, tenant_id: UUID) -> int:
        """Count pending (unresolved) suggestions for a session."""
        result = await self.session.execute(
            select(func.count(TaxCodeSuggestion.id)).where(
                TaxCodeSuggestion.session_id == session_id,
                TaxCodeSuggestion.tenant_id == tenant_id,
                TaxCodeSuggestion.status == "pending",
            )
        )
        return result.scalar() or 0

    async def update_suggestion(self, suggestion: TaxCodeSuggestion) -> TaxCodeSuggestion:
        """Update a suggestion (flush only)."""
        await self.session.flush()
        await self.session.refresh(suggestion)
        return suggestion

    async def get_pending_suggestions_for_bulk(
        self,
        session_id: UUID,
        tenant_id: UUID,
        min_confidence: float | None = None,
        confidence_tier: str | None = None,
    ) -> list[TaxCodeSuggestion]:
        """Get pending suggestions matching bulk criteria."""
        query = select(TaxCodeSuggestion).where(
            TaxCodeSuggestion.session_id == session_id,
            TaxCodeSuggestion.tenant_id == tenant_id,
            TaxCodeSuggestion.status == "pending",
            TaxCodeSuggestion.suggested_tax_type.isnot(None),
        )
        if min_confidence is not None:
            query = query.where(TaxCodeSuggestion.confidence_score >= min_confidence)
        if confidence_tier:
            query = query.where(TaxCodeSuggestion.confidence_tier == confidence_tier)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    # =========================================================================
    # Tax Code Override Operations (Spec 046)
    # =========================================================================

    async def create_override(self, data: dict[str, Any]) -> TaxCodeOverride:
        """Create a tax code override."""
        override = TaxCodeOverride(**data)
        self.session.add(override)
        await self.session.flush()
        await self.session.refresh(override)
        return override

    async def get_active_overrides(
        self, connection_id: UUID, tenant_id: UUID
    ) -> list[TaxCodeOverride]:
        """Get all active overrides for a connection."""
        result = await self.session.execute(
            select(TaxCodeOverride).where(
                TaxCodeOverride.connection_id == connection_id,
                TaxCodeOverride.tenant_id == tenant_id,
                TaxCodeOverride.is_active.is_(True),
            )
        )
        return list(result.scalars().all())

    async def get_active_override(
        self,
        connection_id: UUID,
        source_type: str,
        source_id: UUID,
        line_item_index: int,
        tenant_id: UUID,
    ) -> TaxCodeOverride | None:
        """Get active override for a specific line item."""
        result = await self.session.execute(
            select(TaxCodeOverride).where(
                TaxCodeOverride.connection_id == connection_id,
                TaxCodeOverride.source_type == source_type,
                TaxCodeOverride.source_id == source_id,
                TaxCodeOverride.line_item_index == line_item_index,
                TaxCodeOverride.tenant_id == tenant_id,
                TaxCodeOverride.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def get_override(self, override_id: UUID, tenant_id: UUID) -> TaxCodeOverride | None:
        """Get override by ID."""
        result = await self.session.execute(
            select(TaxCodeOverride).where(
                TaxCodeOverride.id == override_id,
                TaxCodeOverride.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def deactivate_override(self, override_id: UUID, tenant_id: UUID) -> None:
        """Deactivate an override."""
        override = await self.get_override(override_id, tenant_id)
        if override:
            override.is_active = False
            await self.session.flush()

    # =================================================================
    # Classification Request Methods (Spec 047)
    # =================================================================

    async def create_classification_request(
        self, **kwargs: Any
    ) -> ClassificationRequest:
        """Create a classification request."""
        request = ClassificationRequest(**kwargs)
        self.session.add(request)
        await self.session.flush()
        await self.session.refresh(request)
        return request

    async def get_classification_request_by_session(
        self, session_id: UUID
    ) -> ClassificationRequest | None:
        """Get the classification request for a BAS session."""
        result = await self.session.execute(
            select(ClassificationRequest).where(
                ClassificationRequest.session_id == session_id,
            )
        )
        return result.scalars().first()

    async def get_classification_request_by_id(
        self, request_id: UUID, tenant_id: UUID
    ) -> ClassificationRequest | None:
        """Get a classification request by ID with tenant filter."""
        result = await self.session.execute(
            select(ClassificationRequest).where(
                ClassificationRequest.id == request_id,
                ClassificationRequest.tenant_id == tenant_id,
            )
        )
        return result.scalars().first()

    async def get_classification_request_by_id_and_connection(
        self, request_id: UUID, connection_id: UUID
    ) -> ClassificationRequest | None:
        """Get a classification request by ID with connection filter (for portal auth)."""
        result = await self.session.execute(
            select(ClassificationRequest).where(
                ClassificationRequest.id == request_id,
                ClassificationRequest.connection_id == connection_id,
            )
        )
        return result.scalars().first()

    async def create_client_classifications_batch(
        self, classifications: list[dict[str, Any]]
    ) -> int:
        """Bulk insert client classification rows.

        Uses INSERT ... ON CONFLICT DO NOTHING for idempotency.
        Returns the number of rows inserted.
        """
        if not classifications:
            return 0
        stmt = insert(ClientClassification).values(classifications)
        stmt = stmt.on_conflict_do_nothing(
            constraint="uq_client_classification_request_source_line"
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount  # type: ignore[return-value]

    async def get_classifications_by_request(
        self, request_id: UUID
    ) -> list[ClientClassification]:
        """List all classifications for a request."""
        result = await self.session.execute(
            select(ClientClassification)
            .where(ClientClassification.request_id == request_id)
            .order_by(ClientClassification.transaction_date, ClientClassification.line_amount)
        )
        return list(result.scalars().all())

    async def get_classification_by_id(
        self, classification_id: UUID, request_id: UUID
    ) -> ClientClassification | None:
        """Get a single classification by ID within a request."""
        result = await self.session.execute(
            select(ClientClassification).where(
                ClientClassification.id == classification_id,
                ClientClassification.request_id == request_id,
            )
        )
        return result.scalars().first()

    async def update_classification(
        self,
        classification_id: UUID,
        request_id: UUID,
        **kwargs: Any,
    ) -> ClientClassification | None:
        """Update a client classification record."""
        classification = await self.get_classification_by_id(classification_id, request_id)
        if not classification:
            return None
        for key, value in kwargs.items():
            setattr(classification, key, value)
        await self.session.flush()
        return classification

    async def update_request_status(
        self, request_id: UUID, status: str, tenant_id: UUID | None = None, **kwargs: Any
    ) -> ClassificationRequest | None:
        """Update the status of a classification request."""
        query = select(ClassificationRequest).where(
            ClassificationRequest.id == request_id,
        )
        if tenant_id is not None:
            query = query.where(ClassificationRequest.tenant_id == tenant_id)
        result = await self.session.execute(query)
        request = result.scalars().first()
        if not request:
            return None
        request.status = status
        for key, value in kwargs.items():
            setattr(request, key, value)
        await self.session.flush()
        return request

    async def count_classified(self, request_id: UUID) -> int:
        """Count classifications where the client has provided input."""
        result = await self.session.execute(
            select(func.count())
            .select_from(ClientClassification)
            .where(
                ClientClassification.request_id == request_id,
                ClientClassification.classified_at.isnot(None),
            )
        )
        return result.scalar() or 0

    async def get_unprocessed_classifications(
        self, request_id: UUID
    ) -> list[ClientClassification]:
        """Get classifications that have been classified by client but not yet AI-mapped."""
        result = await self.session.execute(
            select(ClientClassification).where(
                ClientClassification.request_id == request_id,
                ClientClassification.classified_at.isnot(None),
                ClientClassification.ai_mapped_at.is_(None),
            )
        )
        return list(result.scalars().all())
