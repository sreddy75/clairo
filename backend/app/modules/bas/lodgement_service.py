"""Service for BAS lodgement operations.

Spec 011: Interim Lodgement
Spec 062 FR-021: Optional insights summary in lodgement confirmation email.
"""

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.exc import StaleDataError

from app.modules.auth.models import PracticeUser
from app.modules.bas.exceptions import (
    ConcurrentModificationError,
    LodgementAlreadyRecordedError,
    LodgementNotAllowedError,
    SessionNotFoundError,
)
from app.modules.bas.models import (
    BASAuditEventType,
    BASAuditLog,
    BASSession,
    BASSessionStatus,
)
from app.modules.bas.schemas import (
    BASSessionResponse,
    LodgementRecordRequest,
    LodgementSummaryResponse,
    LodgementUpdateRequest,
)
from app.modules.bas.service import _get_user_display_name

logger = logging.getLogger(__name__)


class LodgementService:
    """Service for BAS lodgement operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def record_lodgement(
        self,
        session_id: UUID,
        lodged_by: UUID,
        tenant_id: UUID,
        request: LodgementRecordRequest,
    ) -> BASSessionResponse:
        """Record lodgement for an approved BAS session.

        Args:
            session_id: The BAS session ID
            lodged_by: The user recording the lodgement
            tenant_id: The tenant ID
            request: Lodgement details

        Returns:
            Updated BAS session response

        Raises:
            SessionNotFoundError: If session doesn't exist
            LodgementNotAllowedError: If session is not approved
            LodgementAlreadyRecordedError: If already lodged
            ConcurrentModificationError: If concurrent modification detected
        """
        # Fetch the session with all relationships
        stmt = (
            select(BASSession)
            .options(
                selectinload(BASSession.period),
                selectinload(BASSession.calculation),
                selectinload(BASSession.lodged_by_user),
                selectinload(BASSession.created_by_user),
            )
            .where(BASSession.id == session_id)
            .where(BASSession.tenant_id == tenant_id)
        )
        result = await self.session.execute(stmt)
        bas_session = result.scalar_one_or_none()

        if not bas_session:
            raise SessionNotFoundError(str(session_id))

        # Validate status is APPROVED
        if bas_session.status != BASSessionStatus.APPROVED.value:
            raise LodgementNotAllowedError(str(session_id), bas_session.status)

        # Check if already lodged
        if bas_session.lodged_at is not None:
            raise LodgementAlreadyRecordedError(str(session_id))

        # Get the user who is recording the lodgement
        user_stmt = select(PracticeUser).where(PracticeUser.id == lodged_by)
        user_result = await self.session.execute(user_stmt)
        lodged_by_user = user_result.scalar_one_or_none()

        try:
            # Update lodgement fields
            bas_session.lodged_at = datetime.now(UTC)
            bas_session.lodged_by = lodged_by
            bas_session.lodgement_method = request.lodgement_method
            bas_session.lodgement_method_description = request.lodgement_method_description
            bas_session.ato_reference_number = request.ato_reference_number
            bas_session.lodgement_notes = request.lodgement_notes
            bas_session.status = BASSessionStatus.LODGED.value

            # Create audit log entry
            audit_log = BASAuditLog(
                tenant_id=tenant_id,
                session_id=session_id,
                event_type=BASAuditEventType.LODGEMENT_RECORDED.value,
                event_description=f"BAS lodged via {request.lodgement_method}",
                from_status=BASSessionStatus.APPROVED.value,
                to_status=BASSessionStatus.LODGED.value,
                performed_by=lodged_by,
                performed_by_name=lodged_by_user.email if lodged_by_user else None,
                is_system_action=False,
                event_metadata={
                    "lodgement_date": request.lodgement_date.isoformat(),
                    "lodgement_method": request.lodgement_method,
                    "ato_reference_number": request.ato_reference_number,
                },
                created_at=datetime.now(UTC),
            )
            self.session.add(audit_log)

            await self.session.commit()
            await self.session.refresh(bas_session)

        except StaleDataError:
            await self.session.rollback()
            raise ConcurrentModificationError() from None

        # FR-021: Send lodgement confirmation email with optional insights summary.
        if request.include_insights and lodged_by_user and bas_session.period:
            await self._send_confirmation_with_insights(
                bas_session=bas_session,
                lodged_by_user=lodged_by_user,
                tenant_id=tenant_id,
                request=request,
            )

        return self._build_session_response(bas_session)

    async def _send_confirmation_with_insights(
        self,
        bas_session: BASSession,
        lodged_by_user: PracticeUser,
        tenant_id: UUID,
        request: LodgementRecordRequest,
    ) -> None:
        """Fetch top insights and send lodgement confirmation email (FR-021).

        Failures are logged but do not abort the lodgement transaction.
        """
        try:
            from app.config import get_settings
            from app.modules.insights.service import InsightService
            from app.modules.integrations.xero.models import XeroConnection
            from app.modules.notifications.email_service import EmailService

            period = bas_session.period
            connection_id = period.connection_id

            # Get client (organisation) name
            conn_result = await self.session.execute(
                select(XeroConnection).where(XeroConnection.id == connection_id)
            )
            xero_conn = conn_result.scalar_one_or_none()
            client_name = xero_conn.organization_name if xero_conn else "Unknown Client"

            # Fetch top insights for this client
            insight_service = InsightService(self.session)
            insights_html, insights_text = await insight_service.get_insights_summary(
                tenant_id=tenant_id,
                client_id=connection_id,
            )

            settings = get_settings()
            dashboard_url = f"{settings.frontend_url}/clients/{connection_id}"
            lodgement_date_str = request.lodgement_date.strftime("%-d %b %Y")
            period_name = period.display_name if period else ""

            email_service = EmailService()
            await email_service.send_lodgement_confirmation(
                to=lodged_by_user.email,
                user_name=_get_user_display_name(lodged_by_user) or lodged_by_user.email,
                client_name=client_name,
                period=period_name,
                lodgement_date=lodgement_date_str,
                reference_number=request.ato_reference_number or "N/A",
                dashboard_url=dashboard_url,
                insights_section=insights_html or None,
                insights_section_text=insights_text or None,
            )
        except Exception:
            logger.exception("Failed to send lodgement confirmation email (FR-021)")

    async def update_lodgement_details(
        self,
        session_id: UUID,
        user_id: UUID,
        tenant_id: UUID,
        request: LodgementUpdateRequest,
    ) -> BASSessionResponse:
        """Update lodgement details (reference number, notes only).

        Args:
            session_id: The BAS session ID
            user_id: The user making the update
            tenant_id: The tenant ID
            request: Update details

        Returns:
            Updated BAS session response

        Raises:
            SessionNotFoundError: If session doesn't exist
            LodgementNotAllowedError: If session is not lodged
        """
        # Fetch the session
        stmt = (
            select(BASSession)
            .options(
                selectinload(BASSession.period),
                selectinload(BASSession.calculation),
                selectinload(BASSession.lodged_by_user),
                selectinload(BASSession.created_by_user),
            )
            .where(BASSession.id == session_id)
            .where(BASSession.tenant_id == tenant_id)
        )
        result = await self.session.execute(stmt)
        bas_session = result.scalar_one_or_none()

        if not bas_session:
            raise SessionNotFoundError(str(session_id))

        # Validate session is lodged
        if bas_session.lodged_at is None:
            raise LodgementNotAllowedError(
                str(session_id),
                "Session must be lodged before updating lodgement details",
            )

        # Get the user making the update
        user_stmt = select(PracticeUser).where(PracticeUser.id == user_id)
        user_result = await self.session.execute(user_stmt)
        user = user_result.scalar_one_or_none()

        # Track changes for audit
        changes = {}
        if request.ato_reference_number is not None:
            old_ref = bas_session.ato_reference_number
            bas_session.ato_reference_number = request.ato_reference_number
            changes["ato_reference_number"] = {"from": old_ref, "to": request.ato_reference_number}

        if request.lodgement_notes is not None:
            old_notes = bas_session.lodgement_notes
            bas_session.lodgement_notes = request.lodgement_notes
            changes["lodgement_notes"] = {"from": old_notes, "to": request.lodgement_notes}

        if changes:
            # Create audit log entry
            audit_log = BASAuditLog(
                tenant_id=tenant_id,
                session_id=session_id,
                event_type=BASAuditEventType.LODGEMENT_UPDATED.value,
                event_description="Lodgement details updated",
                performed_by=user_id,
                performed_by_name=user.email if user else None,
                is_system_action=False,
                event_metadata={"changes": changes},
                created_at=datetime.now(UTC),
            )
            self.session.add(audit_log)

        await self.session.commit()
        await self.session.refresh(bas_session)

        return self._build_session_response(bas_session)

    async def get_lodgement_summary(
        self,
        session_id: UUID,
        tenant_id: UUID,
    ) -> LodgementSummaryResponse:
        """Get lodgement summary for a session.

        Args:
            session_id: The BAS session ID
            tenant_id: The tenant ID

        Returns:
            Lodgement summary response

        Raises:
            SessionNotFoundError: If session doesn't exist
        """
        stmt = (
            select(BASSession)
            .options(selectinload(BASSession.lodged_by_user))
            .where(BASSession.id == session_id)
            .where(BASSession.tenant_id == tenant_id)
        )
        result = await self.session.execute(stmt)
        bas_session = result.scalar_one_or_none()

        if not bas_session:
            raise SessionNotFoundError(str(session_id))

        return LodgementSummaryResponse(
            session_id=bas_session.id,
            is_lodged=bas_session.is_lodged,
            lodged_at=bas_session.lodged_at,
            lodged_by=bas_session.lodged_by,
            lodged_by_name=_get_user_display_name(bas_session.lodged_by_user),
            lodgement_method=bas_session.lodgement_method,
            lodgement_method_description=bas_session.lodgement_method_description,
            ato_reference_number=bas_session.ato_reference_number,
            lodgement_notes=bas_session.lodgement_notes,
        )

    def _build_session_response(self, bas_session: BASSession) -> BASSessionResponse:
        """Build a BASSessionResponse from a BASSession model."""
        period = bas_session.period

        return BASSessionResponse(
            id=bas_session.id,
            period_id=bas_session.period_id,
            status=bas_session.status,
            period_display_name=period.display_name if period else "",
            quarter=period.quarter if period else None,
            fy_year=period.fy_year if period else 0,
            start_date=period.start_date if period else datetime.now(UTC).date(),
            end_date=period.end_date if period else datetime.now(UTC).date(),
            due_date=period.due_date if period else datetime.now(UTC).date(),
            created_by=bas_session.created_by,
            created_by_name=_get_user_display_name(bas_session.created_by_user),
            approved_by=bas_session.approved_by,
            approved_at=bas_session.approved_at,
            gst_calculated_at=bas_session.gst_calculated_at,
            payg_calculated_at=bas_session.payg_calculated_at,
            internal_notes=bas_session.internal_notes,
            has_calculation=bas_session.calculation is not None,
            auto_created=bas_session.auto_created,
            reviewed_by=bas_session.reviewed_by,
            reviewed_at=bas_session.reviewed_at,
            reviewed_by_name=_get_user_display_name(bas_session.reviewed_by_user),
            # Lodgement fields
            lodged_at=bas_session.lodged_at,
            lodged_by=bas_session.lodged_by,
            lodged_by_name=_get_user_display_name(bas_session.lodged_by_user),
            lodgement_method=bas_session.lodgement_method,
            lodgement_method_description=bas_session.lodgement_method_description,
            ato_reference_number=bas_session.ato_reference_number,
            lodgement_notes=bas_session.lodgement_notes,
            is_lodged=bas_session.is_lodged,
            can_record_lodgement=bas_session.can_record_lodgement,
            created_at=bas_session.created_at,
            updated_at=bas_session.updated_at,
        )
