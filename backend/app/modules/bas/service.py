"""Service layer for BAS preparation workflow."""

import logging
import time
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditService
from app.modules.bas.calculator import GSTCalculator, PAYGCalculator
from app.modules.bas.repository import BASRepository

if TYPE_CHECKING:
    from app.modules.auth.models import PracticeUser
    from app.modules.bas.models import BASCalculation, BASPeriod, BASSession
    from app.modules.bas.schemas import (
        BASSummaryResponse,
        VarianceAnalysisResponse,
        VarianceComparison,
    )
from app.modules.bas.schemas import (
    BASAdjustmentListResponse,
    BASAdjustmentResponse,
    BASCalculateTriggerResponse,
    BASCalculationResponse,
    BASFieldTransaction,
    BASFieldTransactionsResponse,
    BASPeriodListResponse,
    BASPeriodResponse,
    BASSessionListResponse,
    BASSessionResponse,
    GSTBreakdown,
    PAYGBreakdown,
)
from app.modules.bas.utils import get_due_date, get_period_dates
from app.modules.integrations.xero.repository import XeroConnectionRepository
from app.modules.quality.service import QualityService

ExportFormat = Literal["pdf", "excel", "csv"]

logger = logging.getLogger(__name__)


def _get_user_display_name(practice_user: "PracticeUser | None") -> str | None:
    """Resolve a display name for a practice user.

    Tries the Clerk full name via the user relationship, falls back to
    a cleaned-up email. Handles Clerk-generated emails like
    ``user_XXX@accounts.holder.clairo.com`` gracefully.
    """
    if practice_user is None:
        return None
    email = practice_user.email
    # Clerk-generated emails start with the clerk_id prefix
    if email and not email.startswith("user_"):
        return email
    # Fallback: use clerk_id to show a nicer label
    return practice_user.role.value.title() if practice_user.role else "Accountant"


class BASService:
    """Service for BAS preparation operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = BASRepository(session)
        self.connection_repo = XeroConnectionRepository(session)

    # =========================================================================
    # Period Operations
    # =========================================================================

    async def get_or_create_period(
        self,
        connection_id: UUID,
        quarter: int,
        fy_year: int,
        tenant_id: UUID,
    ) -> BASPeriodResponse:
        """Get existing period or create a new one.

        Args:
            connection_id: Xero connection ID
            quarter: Quarter (1-4)
            fy_year: Financial year
            tenant_id: Tenant ID

        Returns:
            BASPeriodResponse
        """
        # Check for existing period
        period = await self.repo.get_period_by_quarter(connection_id, quarter, fy_year)

        if not period:
            # Create new period
            start_date, end_date = get_period_dates(quarter, fy_year)
            due_date = get_due_date(quarter, fy_year)

            period = await self.repo.create_period(
                tenant_id=tenant_id,
                connection_id=connection_id,
                quarter=quarter,
                fy_year=fy_year,
                start_date=start_date,
                end_date=end_date,
                due_date=due_date,
            )
            await self.session.commit()

        return self._period_to_response(period)

    async def list_periods(
        self,
        connection_id: UUID,
        limit: int = 12,
    ) -> BASPeriodListResponse:
        """List periods for a connection."""
        periods = await self.repo.list_periods(connection_id, limit)

        return BASPeriodListResponse(
            periods=[self._period_to_response(p) for p in periods],
            total=len(periods),
        )

    def _period_to_response(self, period: "BASPeriod") -> BASPeriodResponse:
        """Convert period model to response."""
        return BASPeriodResponse(
            id=period.id,
            connection_id=period.connection_id,
            period_type=period.period_type,
            quarter=period.quarter,
            month=period.month,
            fy_year=period.fy_year,
            start_date=period.start_date,
            end_date=period.end_date,
            due_date=period.due_date,
            display_name=period.display_name,
            has_session=period.session is not None,
            session_id=period.session.id if period.session else None,
            session_status=period.session.status if period.session else None,
            created_at=period.created_at,
        )

    # =========================================================================
    # Session Operations
    # =========================================================================

    async def create_session(
        self,
        connection_id: UUID,
        quarter: int,
        fy_year: int,
        user_id: UUID,
        tenant_id: UUID,
        auto_created: bool = False,
        user_name: str | None = None,
    ) -> BASSessionResponse:
        """Create a new BAS preparation session.

        Args:
            connection_id: Xero connection ID
            quarter: Quarter (1-4)
            fy_year: Financial year
            user_id: User creating the session
            tenant_id: Tenant ID
            auto_created: True if session is auto-created by system
            user_name: Name of the user (for audit log)

        Returns:
            BASSessionResponse

        Raises:
            ValueError: If session already exists for this period
        """
        # Get or create the period
        period_response = await self.get_or_create_period(
            connection_id=connection_id,
            quarter=quarter,
            fy_year=fy_year,
            tenant_id=tenant_id,
        )

        # Check if session already exists
        if period_response.has_session:
            raise ValueError(f"Session already exists for {period_response.display_name}")

        # Create session
        session = await self.repo.create_session(
            tenant_id=tenant_id,
            period_id=period_response.id,
            created_by=user_id,
            auto_created=auto_created,
        )

        # Create audit log entry
        event_type = "session_auto_created" if auto_created else "session_created"
        event_description = (
            f"BAS session auto-created by system for {period_response.display_name}"
            if auto_created
            else f"BAS session created for {period_response.display_name}"
        )
        await self.repo.create_audit_log(
            tenant_id=tenant_id,
            session_id=session.id,
            event_type=event_type,
            event_description=event_description,
            to_status="draft",
            performed_by=user_id if not auto_created else None,
            performed_by_name=user_name if not auto_created else "System",
            is_system_action=auto_created,
            event_metadata={
                "quarter": quarter,
                "fy_year": fy_year,
                "connection_id": str(connection_id),
            },
        )

        await self.session.commit()

        # Refresh to get relationships
        refreshed_session = await self.repo.get_session(session.id)
        if not refreshed_session:
            raise ValueError(f"Failed to retrieve created session {session.id}")

        return await self._session_to_response(refreshed_session)

    async def get_session(
        self,
        session_id: UUID,
    ) -> BASSessionResponse | None:
        """Get a session by ID."""
        session = await self.repo.get_session(session_id)
        if not session:
            return None
        return await self._session_to_response(session)

    async def list_sessions(
        self,
        connection_id: UUID,
        limit: int = 20,
        lodgement_status: str = "all",
    ) -> BASSessionListResponse:
        """List sessions for a connection with optional lodgement filter.

        Args:
            connection_id: Xero connection ID
            limit: Maximum sessions to return
            lodgement_status: Filter by lodgement status ("all", "lodged", "not_lodged")
        """
        sessions = await self.repo.list_sessions_by_lodgement_status(
            connection_id, lodgement_status, limit
        )

        if not sessions:
            return BASSessionListResponse(sessions=[], total=0)

        # Batch-fetch quality scores and override counts to avoid N+1 queries
        from sqlalchemy import and_, func, select

        from app.modules.bas.models import (
            TaxCodeOverride,
            TaxCodeOverrideWritebackStatus,
            TaxCodeSuggestion,
        )

        session_ids = [s.id for s in sessions]

        # Batch query: approved unsynced override counts per session
        unsynced_map: dict = {}
        try:
            count_result = await self.session.execute(
                select(
                    TaxCodeSuggestion.session_id,
                    func.count().label("cnt"),
                )
                .select_from(TaxCodeOverride)
                .join(TaxCodeSuggestion, TaxCodeOverride.suggestion_id == TaxCodeSuggestion.id)
                .where(
                    and_(
                        TaxCodeSuggestion.session_id.in_(session_ids),
                        TaxCodeOverride.is_active.is_(True),
                        TaxCodeOverride.writeback_status
                        == TaxCodeOverrideWritebackStatus.PENDING_SYNC.value,
                    )
                )
                .group_by(TaxCodeSuggestion.session_id)
            )
            for row in count_result:
                unsynced_map[row.session_id] = row.cnt
        except Exception as e:
            logger.debug(f"Could not batch-fetch approved_unsynced_count: {e}")

        # Quality scores are skipped in the list endpoint for performance.
        # They are fetched per-session when a specific session is selected.

        responses = []
        for session in sessions:
            quality_score = None
            approved_unsynced_count = unsynced_map.get(session.id, 0)
            responses.append(
                self._session_to_list_response(session, quality_score, approved_unsynced_count)
            )

        return BASSessionListResponse(
            sessions=responses,
            total=len(responses),
        )

    async def update_session_status(
        self,
        session_id: UUID,
        new_status: str,
        user_id: UUID,
    ) -> BASSessionResponse:
        """Update session status.

        Args:
            session_id: Session ID
            new_status: New status value
            user_id: User making the change

        Returns:
            Updated BASSessionResponse

        Raises:
            ValueError: If transition is invalid
        """
        session = await self.repo.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Validate transition
        current_status = session.status
        valid_transitions = {
            "draft": ["in_progress"],
            "in_progress": ["ready_for_review", "draft"],
            "ready_for_review": ["approved", "in_progress"],
            "approved": ["lodged", "ready_for_review"],
            "lodged": [],  # Terminal state
        }

        if new_status not in valid_transitions.get(current_status, []):
            raise ValueError(f"Cannot transition from {current_status} to {new_status}")

        # Update status
        update_kwargs = {
            "status": new_status,
            "last_modified_by": user_id,
        }

        if new_status == "approved":
            update_kwargs["approved_by"] = user_id
            update_kwargs["approved_at"] = datetime.now(UTC)

        session = await self.repo.update_session(session, **update_kwargs)
        await self.session.commit()

        return await self._session_to_response(session)

    async def mark_session_reviewed(
        self,
        session_id: UUID,
        user_id: UUID,
        tenant_id: UUID,
    ) -> BASSessionResponse:
        """Mark an auto-created session as reviewed by an accountant.

        Args:
            session_id: Session ID
            user_id: User marking the session as reviewed
            tenant_id: Tenant ID for audit logging

        Returns:
            Updated BASSessionResponse

        Raises:
            ValueError: If session not found or not auto-created
        """
        session = await self.repo.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        if not session.auto_created:
            raise ValueError("Only auto-created sessions need to be reviewed")

        if session.reviewed_by:
            raise ValueError("Session has already been reviewed")

        # Update session with review info
        session = await self.repo.update_session(
            session,
            reviewed_by=user_id,
            reviewed_at=datetime.now(UTC),
        )

        # Log the review action
        await self.repo.create_audit_log(
            tenant_id=tenant_id,
            session_id=session.id,
            event_type="session_reviewed",
            event_description="BAS session reviewed and approved by accountant",
            from_status=session.status,
            to_status=session.status,
            performed_by=user_id,
            is_system_action=False,
        )

        await self.session.commit()

        return await self._session_to_response(session)

    def _session_to_list_response(
        self,
        session: "BASSession",
        quality_score: float | None,
        approved_unsynced_count: int,
    ) -> BASSessionResponse:
        """Convert session model to response with pre-fetched data (no extra queries)."""
        period = session.period
        return BASSessionResponse(
            id=session.id,
            period_id=session.period_id,
            status=session.status,
            period_display_name=period.display_name,
            quarter=period.quarter,
            fy_year=period.fy_year,
            start_date=period.start_date,
            end_date=period.end_date,
            due_date=period.due_date,
            created_by=session.created_by,
            created_by_name=_get_user_display_name(session.created_by_user),
            approved_by=session.approved_by,
            approved_at=session.approved_at,
            gst_calculated_at=session.gst_calculated_at,
            payg_calculated_at=session.payg_calculated_at,
            internal_notes=session.internal_notes,
            has_calculation=session.calculation is not None,
            quality_score=quality_score,
            auto_created=session.auto_created,
            reviewed_by=session.reviewed_by,
            reviewed_at=session.reviewed_at,
            reviewed_by_name=_get_user_display_name(session.reviewed_by_user),
            lodged_at=session.lodged_at,
            lodged_by=session.lodged_by,
            lodged_by_name=_get_user_display_name(
                session.lodged_by_user if hasattr(session, "lodged_by_user") else None
            ),
            lodgement_method=session.lodgement_method,
            lodgement_method_description=session.lodgement_method_description,
            ato_reference_number=session.ato_reference_number,
            lodgement_notes=session.lodgement_notes,
            is_lodged=session.is_lodged,
            can_record_lodgement=session.can_record_lodgement,
            approved_unsynced_count=approved_unsynced_count,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )

    async def _session_to_response(self, session: "BASSession") -> BASSessionResponse:
        """Convert session model to response (single session — used by get_session)."""
        period = session.period

        # Get quality score if available
        quality_score = None
        try:
            quality_service = QualityService(self.session)
            quality = await quality_service.get_quality_summary(
                connection_id=period.connection_id,
                quarter=period.quarter,
                fy_year=period.fy_year,
            )
            if quality.has_score:
                quality_score = quality.overall_score
        except Exception as e:
            logger.debug(f"Could not fetch quality score: {e}")

        # Count approved, unsynced overrides (Spec 049)
        from sqlalchemy import and_, func, select

        from app.modules.bas.models import (
            TaxCodeOverride,
            TaxCodeOverrideWritebackStatus,
            TaxCodeSuggestion,
        )

        approved_unsynced_count = 0
        try:
            count_result = await self.session.execute(
                select(func.count())
                .select_from(TaxCodeOverride)
                .join(TaxCodeSuggestion, TaxCodeOverride.suggestion_id == TaxCodeSuggestion.id)
                .where(
                    and_(
                        TaxCodeSuggestion.session_id == session.id,
                        TaxCodeOverride.is_active.is_(True),
                        TaxCodeOverride.writeback_status
                        == TaxCodeOverrideWritebackStatus.PENDING_SYNC.value,
                    )
                )
            )
            approved_unsynced_count = count_result.scalar() or 0
        except Exception as e:
            logger.debug(f"Could not fetch approved_unsynced_count: {e}")

        return BASSessionResponse(
            id=session.id,
            period_id=session.period_id,
            status=session.status,
            period_display_name=period.display_name,
            quarter=period.quarter,
            fy_year=period.fy_year,
            start_date=period.start_date,
            end_date=period.end_date,
            due_date=period.due_date,
            created_by=session.created_by,
            created_by_name=_get_user_display_name(session.created_by_user),
            approved_by=session.approved_by,
            approved_at=session.approved_at,
            gst_calculated_at=session.gst_calculated_at,
            payg_calculated_at=session.payg_calculated_at,
            internal_notes=session.internal_notes,
            has_calculation=session.calculation is not None,
            quality_score=quality_score,
            auto_created=session.auto_created,
            reviewed_by=session.reviewed_by,
            reviewed_at=session.reviewed_at,
            reviewed_by_name=_get_user_display_name(session.reviewed_by_user),
            # Lodgement fields (Spec 011)
            lodged_at=session.lodged_at,
            lodged_by=session.lodged_by,
            lodged_by_name=_get_user_display_name(
                session.lodged_by_user if hasattr(session, "lodged_by_user") else None
            ),
            lodgement_method=session.lodgement_method,
            lodgement_method_description=session.lodgement_method_description,
            ato_reference_number=session.ato_reference_number,
            lodgement_notes=session.lodgement_notes,
            is_lodged=session.is_lodged,
            can_record_lodgement=session.can_record_lodgement,
            approved_unsynced_count=approved_unsynced_count,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )

    # =========================================================================
    # Calculation Operations
    # =========================================================================

    async def calculate(
        self,
        session_id: UUID,
        tenant_id: UUID,
    ) -> BASCalculateTriggerResponse:
        """Trigger BAS calculation for a session.

        Args:
            session_id: Session ID
            tenant_id: Tenant ID

        Returns:
            BASCalculateTriggerResponse with calculated figures
        """
        start_time = time.time()

        # Get session and period
        session = await self.repo.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        period = session.period

        # Calculate GST
        gst_calculator = GSTCalculator(self.session)
        gst_result = await gst_calculator.calculate(
            connection_id=period.connection_id,
            start_date=period.start_date,
            end_date=period.end_date,
        )

        # Calculate PAYG
        payg_calculator = PAYGCalculator(self.session)
        payg_result = await payg_calculator.calculate(
            connection_id=period.connection_id,
            start_date=period.start_date,
            end_date=period.end_date,
        )

        # Calculate total payable
        total_payable = gst_result.gst_payable + payg_result.w2_amount_withheld

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Save calculation
        await self.repo.upsert_calculation(
            tenant_id=tenant_id,
            session_id=session_id,
            g1_total_sales=gst_result.g1_total_sales,
            g2_export_sales=gst_result.g2_export_sales,
            g3_gst_free_sales=gst_result.g3_gst_free_sales,
            g10_capital_purchases=gst_result.g10_capital_purchases,
            g11_non_capital_purchases=gst_result.g11_non_capital_purchases,
            field_1a_gst_on_sales=gst_result.field_1a_gst_on_sales,
            field_1b_gst_on_purchases=gst_result.field_1b_gst_on_purchases,
            w1_total_wages=payg_result.w1_total_wages,
            w2_amount_withheld=payg_result.w2_amount_withheld,
            gst_payable=gst_result.gst_payable,
            total_payable=total_payable,
            calculation_duration_ms=duration_ms,
            transaction_count=gst_result.transaction_count,
            invoice_count=gst_result.invoice_count,
            pay_run_count=payg_result.pay_run_count,
        )

        # Update session timestamps
        now = datetime.now(UTC)
        await self.repo.update_session(
            session,
            gst_calculated_at=now,
            payg_calculated_at=now,
            status="in_progress" if session.status == "draft" else session.status,
        )

        await self.session.commit()

        # Spec 024: Audit event for GST calculation with credit note adjustments
        if gst_result.credit_note_count > 0:
            audit_service = AuditService(self.session)
            await audit_service.log_event(
                event_type="gst.calculated.with_credit_notes",
                event_category="compliance",
                actor_type="system",
                tenant_id=tenant_id,
                resource_type="bas_session",
                resource_id=session_id,
                action="calculate",
                outcome="success",
                metadata={
                    "credit_note_count": gst_result.credit_note_count,
                    "sales_credit_notes": str(gst_result.sales_credit_notes),
                    "sales_credit_notes_gst": str(gst_result.sales_credit_notes_gst),
                    "purchase_credit_notes": str(gst_result.purchase_credit_notes),
                    "purchase_credit_notes_gst": str(gst_result.purchase_credit_notes_gst),
                    "net_gst_on_sales": str(gst_result.net_gst_on_sales),
                    "net_gst_on_purchases": str(gst_result.net_gst_on_purchases),
                    "period_start": period.start_date.isoformat(),
                    "period_end": period.end_date.isoformat(),
                },
            )
            await self.session.commit()

        logger.info(
            f"BAS calculated for session {session_id}: "
            f"GST=${gst_result.gst_payable}, PAYG=${payg_result.w2_amount_withheld}, "
            f"Total=${total_payable}, duration={duration_ms}ms"
        )

        return BASCalculateTriggerResponse(
            session_id=session_id,
            gst=GSTBreakdown(
                g1_total_sales=gst_result.g1_total_sales,
                g2_export_sales=gst_result.g2_export_sales,
                g3_gst_free_sales=gst_result.g3_gst_free_sales,
                g10_capital_purchases=gst_result.g10_capital_purchases,
                g11_non_capital_purchases=gst_result.g11_non_capital_purchases,
                field_1a_gst_on_sales=gst_result.field_1a_gst_on_sales,
                field_1b_gst_on_purchases=gst_result.field_1b_gst_on_purchases,
                gst_payable=gst_result.gst_payable,
                invoice_count=gst_result.invoice_count,
                transaction_count=gst_result.transaction_count,
            ),
            payg=PAYGBreakdown(
                w1_total_wages=payg_result.w1_total_wages,
                w2_amount_withheld=payg_result.w2_amount_withheld,
                pay_run_count=payg_result.pay_run_count,
                has_payroll=payg_result.has_payroll,
            ),
            total_payable=total_payable,
            is_refund=total_payable < 0,
            calculated_at=now,
            calculation_duration_ms=duration_ms,
        )

    async def get_calculation(
        self,
        session_id: UUID,
    ) -> BASCalculationResponse | None:
        """Get calculation for a session."""
        calculation = await self.repo.get_calculation(session_id)
        if not calculation:
            return None

        return BASCalculationResponse(
            id=calculation.id,
            session_id=calculation.session_id,
            g1_total_sales=calculation.g1_total_sales,
            g2_export_sales=calculation.g2_export_sales,
            g3_gst_free_sales=calculation.g3_gst_free_sales,
            g10_capital_purchases=calculation.g10_capital_purchases,
            g11_non_capital_purchases=calculation.g11_non_capital_purchases,
            field_1a_gst_on_sales=calculation.field_1a_gst_on_sales,
            field_1b_gst_on_purchases=calculation.field_1b_gst_on_purchases,
            w1_total_wages=calculation.w1_total_wages,
            w2_amount_withheld=calculation.w2_amount_withheld,
            gst_payable=calculation.gst_payable,
            total_payable=calculation.total_payable,
            is_refund=calculation.is_refund,
            calculated_at=calculation.calculated_at,
            calculation_duration_ms=calculation.calculation_duration_ms,
            transaction_count=calculation.transaction_count,
            invoice_count=calculation.invoice_count,
            pay_run_count=calculation.pay_run_count,
        )

    # =========================================================================
    # Adjustment Operations
    # =========================================================================

    async def add_adjustment(
        self,
        session_id: UUID,
        field_name: str,
        adjustment_amount: Decimal,
        reason: str,
        reference: str | None,
        user_id: UUID,
        tenant_id: UUID,
    ) -> BASAdjustmentResponse:
        """Add an adjustment to a session."""
        # Verify session exists and is editable
        session = await self.repo.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        if not session.is_editable:
            raise ValueError(f"Session is not editable (status: {session.status})")

        # Create adjustment
        adjustment = await self.repo.create_adjustment(
            tenant_id=tenant_id,
            session_id=session_id,
            field_name=field_name,
            adjustment_amount=adjustment_amount,
            reason=reason,
            reference=reference,
            created_by=user_id,
        )
        await self.session.commit()

        return BASAdjustmentResponse(
            id=adjustment.id,
            session_id=adjustment.session_id,
            field_name=adjustment.field_name,
            adjustment_amount=adjustment.adjustment_amount,
            reason=adjustment.reason,
            reference=adjustment.reference,
            created_by=adjustment.created_by,
            created_by_name=adjustment.created_by_user.email
            if adjustment.created_by_user
            else None,
            created_at=adjustment.created_at,
        )

    async def delete_adjustment(
        self,
        adjustment_id: UUID,
        session_id: UUID,
    ) -> bool:
        """Delete an adjustment."""
        # Verify session is editable
        session = await self.repo.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        if not session.is_editable:
            raise ValueError(f"Session is not editable (status: {session.status})")

        # Delete adjustment
        result = await self.repo.delete_adjustment(adjustment_id)
        await self.session.commit()
        return result

    async def list_adjustments(
        self,
        session_id: UUID,
    ) -> BASAdjustmentListResponse:
        """List adjustments for a session."""
        adjustments = await self.repo.list_adjustments(session_id)

        return BASAdjustmentListResponse(
            adjustments=[
                BASAdjustmentResponse(
                    id=adj.id,
                    session_id=adj.session_id,
                    field_name=adj.field_name,
                    adjustment_amount=adj.adjustment_amount,
                    reason=adj.reason,
                    reference=adj.reference,
                    created_by=adj.created_by,
                    created_by_name=adj.created_by_user.email if adj.created_by_user else None,
                    created_at=adj.created_at,
                )
                for adj in adjustments
            ],
            total=len(adjustments),
        )

    async def get_adjusted_totals(
        self,
        session_id: UUID,
    ) -> dict[str, Decimal]:
        """Get calculation totals with adjustments applied."""
        calculation = await self.repo.get_calculation(session_id)
        adjustments = await self.repo.list_adjustments(session_id)

        if not calculation:
            return {}

        # Start with base calculation values
        totals = {
            "g1_total_sales": calculation.g1_total_sales,
            "g2_export_sales": calculation.g2_export_sales,
            "g3_gst_free_sales": calculation.g3_gst_free_sales,
            "g10_capital_purchases": calculation.g10_capital_purchases,
            "g11_non_capital_purchases": calculation.g11_non_capital_purchases,
            "field_1a_gst_on_sales": calculation.field_1a_gst_on_sales,
            "field_1b_gst_on_purchases": calculation.field_1b_gst_on_purchases,
            "w1_total_wages": calculation.w1_total_wages,
            "w2_amount_withheld": calculation.w2_amount_withheld,
        }

        # Apply adjustments
        for adj in adjustments:
            if adj.field_name in totals:
                totals[adj.field_name] += adj.adjustment_amount

        # Recalculate derived fields
        totals["gst_payable"] = (
            totals["field_1a_gst_on_sales"] - totals["field_1b_gst_on_purchases"]
        )
        totals["total_payable"] = totals["gst_payable"] + totals["w2_amount_withheld"]

        return totals

    # =========================================================================
    # Variance Analysis
    # =========================================================================

    async def get_variance_analysis(
        self,
        session_id: UUID,
    ) -> "VarianceAnalysisResponse":
        """Get variance analysis comparing to prior periods.

        Args:
            session_id: Session ID

        Returns:
            VarianceAnalysisResponse with comparisons
        """
        from app.modules.bas.schemas import (
            VarianceAnalysisResponse,
        )

        session = await self.repo.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        period = session.period
        calculation = await self.repo.get_calculation(session_id)

        # Get comparison sessions
        prior_quarter_session = await self.repo.get_prior_quarter_session(
            connection_id=period.connection_id,
            current_quarter=period.quarter,
            current_fy_year=period.fy_year,
        )

        same_quarter_prior_year_session = await self.repo.get_same_quarter_prior_year_session(
            connection_id=period.connection_id,
            quarter=period.quarter,
            fy_year=period.fy_year,
        )

        # Build variance comparisons
        prior_quarter_variances = self._build_variance_comparison(
            calculation=calculation,
            prior_session=prior_quarter_session,
            comparison_type="prior_quarter",
        )

        same_quarter_variances = self._build_variance_comparison(
            calculation=calculation,
            prior_session=same_quarter_prior_year_session,
            comparison_type="same_quarter_prior_year",
        )

        return VarianceAnalysisResponse(
            session_id=session_id,
            current_period=period.display_name,
            prior_quarter=prior_quarter_variances,
            same_quarter_prior_year=same_quarter_variances,
        )

    def _build_variance_comparison(
        self,
        calculation: "BASCalculation | None",
        prior_session: "BASSession | None",
        comparison_type: str,
    ) -> "VarianceComparison":
        """Build variance comparison for a prior period."""
        from app.modules.bas.schemas import FieldVariance, VarianceComparison

        if not calculation:
            return VarianceComparison(
                comparison_type=comparison_type,  # type: ignore
                comparison_period_name=None,
                has_data=False,
                variances=[],
            )

        prior_calculation = prior_session.calculation if prior_session else None
        comparison_period = prior_session.period.display_name if prior_session else None

        # Define fields to compare with labels
        fields = [
            ("g1_total_sales", "G1 Total Sales"),
            ("g2_export_sales", "G2 Export Sales"),
            ("g3_gst_free_sales", "G3 GST-Free Sales"),
            ("g10_capital_purchases", "G10 Capital Purchases"),
            ("g11_non_capital_purchases", "G11 Non-Capital Purchases"),
            ("field_1a_gst_on_sales", "1A GST on Sales"),
            ("field_1b_gst_on_purchases", "1B GST on Purchases"),
            ("gst_payable", "Net GST Payable"),
            ("w1_total_wages", "W1 Total Wages"),
            ("w2_amount_withheld", "W2 PAYG Withheld"),
            ("total_payable", "Total Payable"),
        ]

        variances = []
        for field_name, field_label in fields:
            current_value = getattr(calculation, field_name, Decimal("0"))
            prior_value = (
                getattr(prior_calculation, field_name, None) if prior_calculation else None
            )

            # Calculate changes
            absolute_change = None
            percent_change = None
            severity = "normal"

            if prior_value is not None:
                absolute_change = current_value - prior_value
                if prior_value != 0:
                    percent_change = (absolute_change / abs(prior_value)) * 100

                    # Determine severity based on percent change
                    abs_percent = abs(percent_change)
                    if abs_percent > 50:
                        severity = "critical"
                    elif abs_percent > 25:
                        severity = "warning"

            variances.append(
                FieldVariance(
                    field_name=field_name,
                    field_label=field_label,
                    current_value=current_value,
                    prior_value=prior_value,
                    absolute_change=absolute_change,
                    percent_change=percent_change,
                    severity=severity,  # type: ignore
                    comparison_period=comparison_period,
                )
            )

        return VarianceComparison(
            comparison_type=comparison_type,  # type: ignore
            comparison_period_name=comparison_period,
            has_data=prior_calculation is not None,
            variances=variances,
        )

    # =========================================================================
    # Summary Operations
    # =========================================================================

    async def get_summary(
        self,
        session_id: UUID,
    ) -> "BASSummaryResponse":
        """Get complete BAS summary for review.

        Args:
            session_id: Session ID

        Returns:
            BASSummaryResponse with all data for review
        """
        from app.modules.bas.schemas import BASSummaryResponse

        session_response = await self.get_session(session_id)
        if not session_response:
            raise ValueError(f"Session {session_id} not found")

        calculation = await self.get_calculation(session_id)
        adjustments_response = await self.list_adjustments(session_id)
        adjusted_totals = await self.get_adjusted_totals(session_id)

        # Get quality score and issues
        quality_score = None
        quality_issues_count = 0
        blocking_issues: list[str] = []

        try:
            session = await self.repo.get_session(session_id)
            if session:
                period = session.period
                quality_service = QualityService(self.session)
                quality = await quality_service.get_quality_summary(
                    connection_id=period.connection_id,
                    quarter=period.quarter,
                    fy_year=period.fy_year,
                )
                if quality.has_score:
                    quality_score = quality.overall_score
                    quality_issues_count = quality.critical_count + quality.warning_count

                    # Add blocking issues if score is too low
                    if quality.overall_score < Decimal("70"):
                        blocking_issues.append(
                            f"Quality score ({quality.overall_score}%) is below minimum threshold (70%)"
                        )
                    if quality.critical_count > 0:
                        blocking_issues.append(
                            f"{quality.critical_count} critical quality issue(s) must be resolved"
                        )
        except Exception as e:
            logger.debug(f"Could not fetch quality data: {e}")

        # Check if calculation exists
        if not calculation:
            blocking_issues.append("BAS calculation has not been performed")

        # Check for unresolved tax code suggestions (Spec 046)
        try:
            if session:
                unresolved_count = await self.repo.count_unresolved(session_id, session.tenant_id)
                if unresolved_count > 0:
                    blocking_issues.append(
                        f"{unresolved_count} transaction(s) have unresolved tax codes"
                    )
        except Exception as e:
            logger.debug(f"Could not check tax code suggestions: {e}")

        # Determine if approval is allowed
        can_approve = len(blocking_issues) == 0

        return BASSummaryResponse(
            session=session_response,
            calculation=calculation,
            adjustments=adjustments_response.adjustments,
            adjusted_totals=adjusted_totals,
            quality_score=quality_score,
            quality_issues_count=quality_issues_count,
            can_approve=can_approve,
            blocking_issues=blocking_issues,
        )

    # =========================================================================
    # Export Operations
    # =========================================================================

    async def export_working_papers(
        self,
        session_id: UUID,
        export_format: ExportFormat,
        include_lodgement_summary: bool = True,
        user_id: UUID | None = None,
    ) -> tuple[bytes, str, str]:
        """Export BAS working papers in the specified format.

        Args:
            session_id: Session ID
            export_format: Export format ("pdf", "excel", or "csv")
            include_lodgement_summary: Include ATO-compliant lodgement summary
            user_id: User ID for audit logging

        Returns:
            Tuple of (file_bytes, filename, content_type)

        Raises:
            ValueError: If session not found or no calculation exists
            ExportNotAllowedError: If lodgement export requires approved status
        """
        from app.modules.bas.csv_exporter import CSVExporter
        from app.modules.bas.exceptions import ExportNotAllowedError
        from app.modules.bas.exporter import BASWorkingPaperExporter
        from app.modules.bas.lodgement_exporter import LodgementExporter
        from app.modules.bas.models import BASAuditEventType, BASSessionStatus

        session = await self.repo.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        period = session.period
        calculation = session.calculation

        # Get organization name and ABN from connection
        connection = await self.connection_repo.get_by_id(period.connection_id)
        organization_name = connection.organization_name if connection else "Unknown Organization"
        abn = getattr(connection, "abn", None) if connection else None

        # CSV and lodgement summary exports require approved or lodged status
        if include_lodgement_summary or export_format == "csv":
            if session.status not in (
                BASSessionStatus.APPROVED.value,
                BASSessionStatus.LODGED.value,
            ):
                raise ExportNotAllowedError(str(session_id), session.status)

        # Generate filename
        period_name = period.display_name.replace(" ", "_").replace("/", "-")
        timestamp = datetime.now(UTC).strftime("%Y%m%d")

        if export_format == "csv":
            # CSV export for data transfer
            csv_exporter = CSVExporter(
                session=session,
                period=period,
                calculation=calculation,
                organization_name=organization_name,
                abn=abn,
            )
            file_bytes = csv_exporter.generate_csv()
            filename = f"BAS_Lodgement_{period_name}_{timestamp}.csv"
            content_type = "text/csv; charset=utf-8"
            audit_event = BASAuditEventType.EXPORT_CSV.value

        elif include_lodgement_summary and session.status in (
            BASSessionStatus.APPROVED.value,
            BASSessionStatus.LODGED.value,
        ):
            # Use enhanced lodgement exporter for approved/lodged sessions
            from sqlalchemy import select

            from app.modules.auth.models import User

            approved_by_name = None
            if session.approved_by:
                # Get approver name for the export
                result = await self.session.execute(
                    select(User).where(User.id == session.approved_by)
                )
                approver = result.scalar_one_or_none()
                approved_by_name = approver.email if approver else None

            lodged_by_name = None
            if session.lodged_by:
                # Get lodger name for the export
                result = await self.session.execute(
                    select(User).where(User.id == session.lodged_by)
                )
                lodger = result.scalar_one_or_none()
                lodged_by_name = lodger.email if lodger else None

            lodgement_exporter = LodgementExporter(
                session=session,
                period=period,
                calculation=calculation,
                organization_name=organization_name,
                abn=abn,
                approved_by_name=approved_by_name,
                lodged_by_name=lodged_by_name,
            )

            if export_format == "pdf":
                file_bytes = lodgement_exporter.generate_lodgement_pdf()
                filename = f"BAS_Lodgement_{period_name}_{timestamp}.pdf"
                content_type = "application/pdf"
                audit_event = BASAuditEventType.EXPORT_PDF_LODGEMENT.value
            else:  # excel
                file_bytes = lodgement_exporter.generate_lodgement_excel()
                filename = f"BAS_Lodgement_{period_name}_{timestamp}.xlsx"
                content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                audit_event = BASAuditEventType.EXPORT_EXCEL_LODGEMENT.value
        else:
            # Use base exporter for non-lodgement exports
            exporter = BASWorkingPaperExporter(
                session=session,
                period=period,
                calculation=calculation,
                organization_name=organization_name,
            )

            if export_format == "pdf":
                file_bytes = exporter.generate_pdf()
                filename = f"BAS_Working_Paper_{period_name}_{timestamp}.pdf"
                content_type = "application/pdf"
                audit_event = None  # Don't audit working paper exports
            else:  # excel
                file_bytes = exporter.generate_excel()
                filename = f"BAS_Working_Paper_{period_name}_{timestamp}.xlsx"
                content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                audit_event = None

        # Log audit event for lodgement exports
        if audit_event and user_id:
            await self.repo.create_audit_log(
                tenant_id=session.tenant_id,
                session_id=session_id,
                event_type=audit_event,
                event_description=f"Exported BAS as {export_format.upper()} for lodgement",
                performed_by=user_id,
                event_metadata={
                    "format": export_format,
                    "filename": filename,
                    "include_lodgement_summary": include_lodgement_summary,
                },
            )
            await self.session.commit()

        logger.info(f"Exported BAS for session {session_id} as {export_format}")

        return file_bytes, filename, content_type

    # =========================================================================
    # Field Transaction Drilldown
    # =========================================================================

    async def get_field_transactions(
        self,
        session_id: UUID,
        field_name: str,
    ) -> BASFieldTransactionsResponse:
        """Get transactions that contribute to a specific BAS field.

        Args:
            session_id: BAS session ID
            field_name: BAS field name (e.g., 'g1_total_sales', 'field_1a_gst_on_sales')

        Returns:
            BASFieldTransactionsResponse with transaction details

        Raises:
            ValueError: If session not found or invalid field name
        """
        from sqlalchemy import select

        from app.modules.integrations.xero.models import (
            XeroBankTransaction,
            XeroClient,
            XeroInvoice,
        )

        # Field label mapping
        field_labels = {
            "g1_total_sales": "G1 Total Sales",
            "g2_export_sales": "G2 Export Sales",
            "g3_gst_free_sales": "G3 GST-Free Sales",
            "g10_capital_purchases": "G10 Capital Purchases",
            "g11_non_capital_purchases": "G11 Non-Capital Purchases",
            "field_1a_gst_on_sales": "1A GST on Sales",
            "field_1b_gst_on_purchases": "1B GST on Purchases",
            "gst_payable": "Net GST Payable",
            "total_payable": "Total Payable",
        }

        if field_name not in field_labels:
            raise ValueError(f"Invalid field name: {field_name}")

        # Get session with period
        session = await self.repo.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        period = await self.repo.get_period(session.period_id)
        if not period:
            raise ValueError("Period not found")

        transactions: list[BASFieldTransaction] = []
        total_amount = Decimal("0")

        # Determine which data source to query based on field
        if field_name in ["g1_total_sales", "field_1a_gst_on_sales"]:
            # Sales invoices (ACCREC)
            result = await self.session.execute(
                select(XeroInvoice, XeroClient)
                .outerjoin(XeroClient, XeroInvoice.client_id == XeroClient.id)
                .where(
                    XeroInvoice.connection_id == period.connection_id,
                    XeroInvoice.issue_date >= period.start_date,
                    XeroInvoice.issue_date <= period.end_date,
                    XeroInvoice.status.in_(["authorised", "paid"]),
                    XeroInvoice.invoice_type == "accrec",
                )
                .order_by(XeroInvoice.issue_date.desc())
            )

            for invoice, client in result.all():
                line_amount = Decimal(str(invoice.subtotal or 0))
                tax_amount = Decimal(str(invoice.tax_amount or 0))
                inv_total = Decimal(str(invoice.total_amount or 0))

                if field_name == "g1_total_sales":
                    total_amount += inv_total
                else:  # field_1a_gst_on_sales
                    total_amount += tax_amount

                transactions.append(
                    BASFieldTransaction(
                        id=str(invoice.id),
                        source="invoice",
                        date=invoice.issue_date,
                        reference=invoice.invoice_number,
                        description=f"Invoice to {client.name if client else 'Unknown'}",
                        contact_name=client.name if client else None,
                        line_amount=line_amount,
                        tax_amount=tax_amount,
                        total_amount=inv_total,
                        tax_type="OUTPUT",
                    )
                )

        elif field_name in ["g11_non_capital_purchases", "field_1b_gst_on_purchases"]:
            # Bank transactions (SPEND with GST)
            result = await self.session.execute(
                select(XeroBankTransaction)
                .where(
                    XeroBankTransaction.connection_id == period.connection_id,
                    XeroBankTransaction.transaction_date >= period.start_date,
                    XeroBankTransaction.transaction_date <= period.end_date,
                    XeroBankTransaction.status == "AUTHORISED",
                    XeroBankTransaction.transaction_type == "spend",
                )
                .order_by(XeroBankTransaction.transaction_date.desc())
            )

            for txn in result.scalars().all():
                line_items = txn.line_items or []
                txn_line_amount = Decimal("0")
                txn_tax_amount = Decimal("0")

                for item in line_items:
                    tax_type = str(item.get("tax_type") or item.get("TaxType", "")).upper()
                    if tax_type in ["INPUT", "INPUT2", "INPUT3", "INPUTTAXED"]:
                        line_amt = Decimal(
                            str(item.get("line_amount") or item.get("LineAmount", 0))
                        )
                        tax_amt = Decimal(str(item.get("tax_amount") or item.get("TaxAmount", 0)))
                        txn_line_amount += line_amt
                        txn_tax_amount += tax_amt

                if txn_tax_amount > 0 or txn_line_amount > 0:
                    if field_name == "g11_non_capital_purchases":
                        total_amount += txn_line_amount
                    else:  # field_1b_gst_on_purchases
                        total_amount += txn_tax_amount

                    # Get first line item description
                    desc = "Bank transaction"
                    if line_items:
                        desc = str(
                            line_items[0].get("description")
                            or line_items[0].get("Description", "Bank transaction")
                        )

                    transactions.append(
                        BASFieldTransaction(
                            id=str(txn.id),
                            source="bank_transaction",
                            date=txn.transaction_date,
                            reference=txn.reference,
                            description=desc[:100],  # Truncate long descriptions
                            contact_name=None,
                            line_amount=txn_line_amount,
                            tax_amount=txn_tax_amount,
                            total_amount=txn_line_amount + txn_tax_amount,
                            tax_type="INPUT",
                        )
                    )

        elif field_name == "g10_capital_purchases":
            # Bank transactions with capital tax codes
            result = await self.session.execute(
                select(XeroBankTransaction)
                .where(
                    XeroBankTransaction.connection_id == period.connection_id,
                    XeroBankTransaction.transaction_date >= period.start_date,
                    XeroBankTransaction.transaction_date <= period.end_date,
                    XeroBankTransaction.status == "AUTHORISED",
                    XeroBankTransaction.transaction_type == "spend",
                )
                .order_by(XeroBankTransaction.transaction_date.desc())
            )

            for txn in result.scalars().all():
                line_items = txn.line_items or []

                for item in line_items:
                    tax_type = str(item.get("tax_type") or item.get("TaxType", "")).upper()
                    if tax_type in ["CAPEXINPUT", "CAPEXINPUT2"]:
                        line_amt = Decimal(
                            str(item.get("line_amount") or item.get("LineAmount", 0))
                        )
                        tax_amt = Decimal(str(item.get("tax_amount") or item.get("TaxAmount", 0)))
                        total_amount += line_amt

                        desc = str(
                            item.get("description") or item.get("Description", "Capital purchase")
                        )

                        transactions.append(
                            BASFieldTransaction(
                                id=str(txn.id),
                                source="bank_transaction",
                                date=txn.transaction_date,
                                reference=txn.reference,
                                description=desc[:100],
                                contact_name=None,
                                line_amount=line_amt,
                                tax_amount=tax_amt,
                                total_amount=line_amt + tax_amt,
                                tax_type=tax_type,
                            )
                        )

        elif field_name == "g2_export_sales":
            # Export sales (EXEMPTEXPORT tax type)
            result = await self.session.execute(
                select(XeroInvoice, XeroClient)
                .outerjoin(XeroClient, XeroInvoice.client_id == XeroClient.id)
                .where(
                    XeroInvoice.connection_id == period.connection_id,
                    XeroInvoice.issue_date >= period.start_date,
                    XeroInvoice.issue_date <= period.end_date,
                    XeroInvoice.status.in_(["authorised", "paid"]),
                    XeroInvoice.invoice_type == "accrec",
                )
                .order_by(XeroInvoice.issue_date.desc())
            )

            for invoice, client in result.all():
                line_items = invoice.line_items or []
                for item in line_items:
                    tax_type = str(item.get("tax_type") or item.get("TaxType", "")).upper()
                    if tax_type in ["EXEMPTEXPORT", "GSTONEXPORTS"]:
                        line_amt = Decimal(
                            str(item.get("line_amount") or item.get("LineAmount", 0))
                        )
                        total_amount += line_amt

                        transactions.append(
                            BASFieldTransaction(
                                id=str(invoice.id),
                                source="invoice",
                                date=invoice.issue_date,
                                reference=invoice.invoice_number,
                                description=f"Export to {client.name if client else 'Unknown'}",
                                contact_name=client.name if client else None,
                                line_amount=line_amt,
                                tax_amount=Decimal("0"),
                                total_amount=line_amt,
                                tax_type=tax_type,
                            )
                        )

        elif field_name == "g3_gst_free_sales":
            # GST-free sales
            result = await self.session.execute(
                select(XeroInvoice, XeroClient)
                .outerjoin(XeroClient, XeroInvoice.client_id == XeroClient.id)
                .where(
                    XeroInvoice.connection_id == period.connection_id,
                    XeroInvoice.issue_date >= period.start_date,
                    XeroInvoice.issue_date <= period.end_date,
                    XeroInvoice.status.in_(["authorised", "paid"]),
                    XeroInvoice.invoice_type == "accrec",
                )
                .order_by(XeroInvoice.issue_date.desc())
            )

            for invoice, client in result.all():
                line_items = invoice.line_items or []
                for item in line_items:
                    tax_type = str(item.get("tax_type") or item.get("TaxType", "")).upper()
                    if tax_type in ["EXEMPTOUTPUT", "EXEMPTINCOME"]:
                        line_amt = Decimal(
                            str(item.get("line_amount") or item.get("LineAmount", 0))
                        )
                        total_amount += line_amt

                        transactions.append(
                            BASFieldTransaction(
                                id=str(invoice.id),
                                source="invoice",
                                date=invoice.issue_date,
                                reference=invoice.invoice_number,
                                description=f"GST-free sale to {client.name if client else 'Unknown'}",
                                contact_name=client.name if client else None,
                                line_amount=line_amt,
                                tax_amount=Decimal("0"),
                                total_amount=line_amt,
                                tax_type=tax_type,
                            )
                        )

        return BASFieldTransactionsResponse(
            session_id=session_id,
            field_name=field_name,
            field_label=field_labels[field_name],
            period_start=period.start_date,
            period_end=period.end_date,
            total_amount=total_amount,
            transaction_count=len(transactions),
            transactions=transactions,
        )
