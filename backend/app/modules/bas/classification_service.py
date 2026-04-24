"""Business logic for client transaction classification.

Spec 047: Client Transaction Classification.
Handles the full lifecycle: create request, client classification,
AI mapping, accountant review, and audit trail export.
"""

from __future__ import annotations

import logging
import uuid as uuid_mod
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.bas.classification_constants import (
    GST_CREDIT_RECEIPT_THRESHOLD,
    RECEIPT_ALWAYS_CATEGORY_IDS,
    RECEIPT_REASON_BY_CATEGORY,
    RECEIPT_REASON_GST_THRESHOLD,
    RECEIPT_REASON_VAGUE,
    VAGUE_DESCRIPTION_MIN_LENGTH,
    VAGUE_DESCRIPTION_PATTERNS,
)
from app.modules.bas.classification_models import (
    ClassificationRequestStatus,
)
from app.modules.bas.exceptions import (
    ClassificationRequestNotFoundError,
    NoClientEmailError,
    NoUnresolvedTransactionsError,
)
from app.modules.bas.repository import BASRepository

logger = logging.getLogger(__name__)


class ClassificationService:
    """Service for client transaction classification workflow."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = BASRepository(session)

    # ------------------------------------------------------------------
    # Receipt Auto-Flag Logic (US6 — T036)
    # ------------------------------------------------------------------

    @staticmethod
    def _should_require_receipt(
        amount: Decimal,
        category_id: str | None,
        description: str | None,
        account_code: str | None = None,
    ) -> tuple[bool, str | None]:
        """Determine if a transaction should be flagged for receipt upload.

        Rules evaluated in order:
        1. GST credit claim > $82.50 (ATO tax invoice requirement)
        2. Category always requires receipt (capital, entertainment, subcontractor)
        3. Vague bank description

        Returns:
            Tuple of (should_flag, reason).
        """
        # Rule 1: ATO tax invoice threshold for expenses
        if abs(amount) > GST_CREDIT_RECEIPT_THRESHOLD and amount < 0:
            return True, RECEIPT_REASON_GST_THRESHOLD

        # Rule 2: Category-specific receipt requirement
        if category_id and category_id in RECEIPT_ALWAYS_CATEGORY_IDS:
            reason = RECEIPT_REASON_BY_CATEGORY.get(
                category_id, "Receipt required for this category"
            )
            return True, reason

        # Rule 3: Vague bank description
        if description:
            stripped = description.strip()
            if len(stripped) < VAGUE_DESCRIPTION_MIN_LENGTH:
                return True, RECEIPT_REASON_VAGUE
            for pattern in VAGUE_DESCRIPTION_PATTERNS:
                if pattern.search(stripped):
                    return True, RECEIPT_REASON_VAGUE

        return False, None

    # ------------------------------------------------------------------
    # US1: Accountant Requests Client Classification
    # ------------------------------------------------------------------

    async def create_request(
        self,
        session_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        connection_id: UUID,
        message: str | None = None,
        transaction_ids: list[dict] | None = None,
        email_override: str | None = None,
        manual_receipt_flags: list[dict] | None = None,
    ) -> dict[str, Any]:
        """Create a classification request and send magic link to client.

        Orchestrates: validate session, get unresolved transactions, look up
        client email, create records, apply receipt flags, create portal
        invitation, and send email.
        """
        from app.modules.bas.models import BASAuditEventType
        from app.modules.bas.tax_code_service import TaxCodeService
        from app.modules.integrations.xero.models import XeroClient
        from app.modules.notifications.email_service import get_email_service
        from app.modules.notifications.templates import EmailTemplate
        from app.modules.portal.auth.magic_link import MagicLinkService
        from app.modules.portal.notifications.templates import PortalEmailTemplates

        # 1. Remove any existing request for this session (allows resending)
        existing = await self.repo.get_classification_request_by_session(session_id)
        if existing:
            await self.session.delete(existing)
            await self.session.flush()

        # 2. Get the BAS session to validate it's editable
        bas_session = await self.repo.get_session(session_id)
        if not bas_session:
            raise ClassificationRequestNotFoundError(str(session_id))

        # 3. Get unresolved transactions (pending suggestions from spec 046)
        tax_code_service = TaxCodeService(self.session)
        suggestions = await self.repo.list_suggestions(session_id, tenant_id)
        pending = [s for s in suggestions if s.status == "pending"]

        if not pending:
            # Try generating suggestions first
            await tax_code_service.detect_and_generate(session_id, tenant_id)
            suggestions = await self.repo.list_suggestions(session_id, tenant_id)
            pending = [s for s in suggestions if s.status == "pending"]

        if not pending:
            raise NoUnresolvedTransactionsError()

        # Sort pending suggestions by transaction_date DESC (most recent first)
        pending = sorted(
            pending,
            key=lambda s: s.transaction_date or date(1900, 1, 1),
            reverse=True,
        )

        # 4. Filter to specific transaction IDs if provided
        if transaction_ids:
            id_set = {
                (t["source_type"], str(t["source_id"]), t["line_item_index"])
                for t in transaction_ids
            }
            pending = [
                s for s in pending if (s.source_type, str(s.source_id), s.line_item_index) in id_set
            ]
            if not pending:
                raise NoUnresolvedTransactionsError()

        # 5. Look up client email
        from sqlalchemy import select

        client_result = await self.session.execute(
            select(XeroClient)
            .where(
                XeroClient.connection_id == connection_id,
            )
            .limit(1)
        )
        xero_client = client_result.scalars().first()
        client_email = email_override or (xero_client.email if xero_client else None)
        if not client_email:
            raise NoClientEmailError()

        # 6. Build manual receipt flag lookup
        manual_flags: dict[tuple, str] = {}
        if manual_receipt_flags:
            for flag in manual_receipt_flags:
                key = (flag["source_type"], str(flag["source_id"]), flag["line_item_index"])
                manual_flags[key] = flag.get("reason", "Receipt requested by accountant")

        # 7. Create the ClassificationRequest record
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        request = await self.repo.create_classification_request(
            id=uuid_mod.uuid4(),
            tenant_id=tenant_id,
            connection_id=connection_id,
            session_id=session_id,
            requested_by=user_id,
            client_email=client_email,
            message=message,
            status=ClassificationRequestStatus.DRAFT,
            transaction_count=len(pending),
            classified_count=0,
            expires_at=expires_at,
        )

        # 8. Create ClientClassification records with receipt flags
        classification_rows = []
        for s in pending:
            flag_key = (s.source_type, str(s.source_id), s.line_item_index)

            # Auto-flag receipt
            receipt_required, receipt_reason = self._should_require_receipt(
                amount=s.line_amount or Decimal("0"),
                category_id=None,  # Not yet classified
                description=s.description,
            )
            receipt_source = "auto" if receipt_required else None

            # Manual flag overrides
            if flag_key in manual_flags:
                receipt_required = True
                receipt_reason = manual_flags[flag_key]
                receipt_source = "manual"

            classification_rows.append(
                {
                    "id": uuid_mod.uuid4(),
                    "tenant_id": tenant_id,
                    "request_id": request.id,
                    "source_type": s.source_type,
                    "source_id": s.source_id,
                    "line_item_index": s.line_item_index,
                    "suggestion_id": s.id,
                    "transaction_date": s.transaction_date,
                    "line_amount": s.line_amount or Decimal("0"),
                    "description": s.description,
                    "contact_name": s.contact_name,
                    "account_code": s.account_code,
                    "receipt_required": receipt_required,
                    "receipt_flag_source": receipt_source,
                    "receipt_flag_reason": receipt_reason,
                }
            )

        await self.repo.create_client_classifications_batch(classification_rows)

        # 9. Create portal invitation + send email
        # MagicLinkService.create_invitation expects invited_by as users.id (not practice_users.id)
        # Look up the User.id from PracticeUser
        from app.modules.auth.models import PracticeUser as PracticeUserModel

        practice_user = await self.session.get(PracticeUserModel, user_id)
        invited_by_user_id = practice_user.user_id if practice_user else user_id

        magic_link_service = MagicLinkService(self.session)
        invitation, token = await magic_link_service.create_invitation(
            tenant_id=tenant_id,
            connection_id=connection_id,
            email=client_email,
            invited_by=invited_by_user_id,
            expires_hours=7 * 24,  # 7 days
        )

        # Link invitation to request
        request.invitation_id = invitation.id
        await self.session.flush()

        magic_link_url = magic_link_service.build_magic_link_url(token)
        # Add redirect param so verify page sends client to classification page
        magic_link_url = f"{magic_link_url}&redirect=/portal/classify/{request.id}"

        # Send classification email
        email_sent = False
        try:
            # Get org name from the XeroConnection (not the contact)
            from app.modules.integrations.xero.models import XeroConnection

            connection = await self.session.get(XeroConnection, connection_id)
            org_name = connection.organization_name if connection else "your business"

            # Get practice name from tenant and accountant name from Clerk
            from app.modules.auth.clerk import ClerkClient
            from app.modules.auth.models import Tenant

            tenant = await self.session.get(Tenant, tenant_id)
            practice_name = "Your accounting practice"

            # Tenant.name may contain a proper practice name
            if tenant and tenant.name and not tenant.name.startswith("User "):
                practice_name = tenant.name

            accountant_name = practice_name
            if practice_user and practice_user.clerk_id:
                try:
                    clerk_client = ClerkClient()
                    clerk_user = await clerk_client.get_user(practice_user.clerk_id)
                    if clerk_user.full_name:
                        accountant_name = clerk_user.full_name
                    if not practice_name or practice_name == "Your accounting practice":
                        # Use Clerk org or fallback to accountant name's practice
                        practice_name = f"{accountant_name}'s Practice"
                except Exception:
                    logger.debug("Could not fetch accountant name from Clerk", exc_info=True)

            portal_template = PortalEmailTemplates.transaction_classification_request(
                business_name=org_name,
                practice_name=practice_name,
                accountant_name=accountant_name,
                portal_url=magic_link_url,
                transaction_count=len(pending),
                message=message,
            )
            email_template = EmailTemplate(
                subject=portal_template.subject,
                html=portal_template.html,
                text=portal_template.text,
            )
            email_service = get_email_service()
            await email_service.send_email(
                to=client_email,
                template=email_template,
                tags=[{"name": "type", "value": "classification_request"}],
            )
            email_sent = True
            await magic_link_service.mark_invitation_sent(
                invitation_id=invitation.id,
                delivered=True,
            )
        except Exception:
            logger.warning(
                "Failed to send classification request email to %s",
                client_email,
                exc_info=True,
            )
            await magic_link_service.mark_invitation_sent(
                invitation_id=invitation.id,
                delivered=False,
            )

        # 10. Update status to SENT
        await self.repo.update_request_status(request.id, ClassificationRequestStatus.SENT)

        # 11. Audit event
        await self.repo.create_audit_log(
            tenant_id=tenant_id,
            session_id=session_id,
            event_type=BASAuditEventType.CLASSIFICATION_REQUEST_CREATED.value,
            event_description=f"Classification request created for {client_email} ({len(pending)} transactions)",
            performed_by=user_id,
            event_metadata={
                "request_id": str(request.id),
                "transaction_count": len(pending),
                "client_email": client_email,
                "email_sent": email_sent,
            },
        )

        return {
            "id": request.id,
            "status": ClassificationRequestStatus.SENT,
            "client_email": client_email,
            "transaction_count": len(pending),
            "magic_link_sent": email_sent,
            "expires_at": expires_at,
            "created_at": request.created_at,
        }

    async def get_request_status(
        self,
        session_id: UUID,
        tenant_id: UUID,
    ) -> dict[str, Any]:
        """Get current status of a classification request."""
        request = await self.repo.get_classification_request_by_session(session_id)
        if not request or request.tenant_id != tenant_id:
            raise ClassificationRequestNotFoundError()

        # Update classified count
        classified = await self.repo.count_classified(request.id)
        if classified != request.classified_count:
            request.classified_count = classified
            await self.session.flush()

        return {
            "id": request.id,
            "status": request.status,
            "client_email": request.client_email,
            "message": request.message,
            "transaction_count": request.transaction_count,
            "classified_count": classified,
            "submitted_at": request.submitted_at,
            "expires_at": request.expires_at,
            "created_at": request.created_at,
        }

    async def cancel_request(
        self,
        session_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
    ) -> dict[str, Any]:
        """Cancel an active classification request."""
        request = await self.repo.get_classification_request_by_session(session_id)
        if not request or request.tenant_id != tenant_id:
            raise ClassificationRequestNotFoundError()

        if request.status in ClassificationRequestStatus.TERMINAL:
            raise ClassificationRequestNotFoundError()

        # Expire the portal invitation directly
        if request.invitation_id:
            from app.modules.portal.enums import InvitationStatus
            from app.modules.portal.models import PortalInvitation

            inv = await self.session.get(PortalInvitation, request.invitation_id)
            if inv and inv.status not in (
                InvitationStatus.ACCEPTED.value,
                InvitationStatus.EXPIRED.value,
            ):
                inv.status = InvitationStatus.EXPIRED.value
                await self.session.flush()

        await self.repo.update_request_status(request.id, ClassificationRequestStatus.CANCELLED)

        return {"id": request.id, "status": ClassificationRequestStatus.CANCELLED}

    # ------------------------------------------------------------------
    # US2: Client Classifies Transactions
    # ------------------------------------------------------------------

    async def get_client_view(
        self,
        request_id: UUID,
        connection_id: UUID,
    ) -> dict[str, Any]:
        """Get classification request data for the client page.

        Returns transactions with categories, hints, receipt flags, and progress.
        Does NOT expose account_codes, tax types, or Xero IDs to the client.
        """
        from app.modules.bas.classification_constants import (
            CLASSIFICATION_CATEGORIES,
        )

        request = await self.repo.get_classification_request_by_id_and_connection(
            request_id,
            connection_id,
        )
        if not request:
            raise ClassificationRequestNotFoundError(str(request_id))

        # Check expiry
        if request.expires_at < datetime.now(timezone.utc):
            await self.repo.update_request_status(request.id, ClassificationRequestStatus.EXPIRED)
            from app.modules.bas.exceptions import ClassificationRequestExpiredError

            raise ClassificationRequestExpiredError(str(request_id))

        # Update status to VIEWED on first access
        if request.status == ClassificationRequestStatus.SENT:
            await self.repo.update_request_status(request.id, ClassificationRequestStatus.VIEWED)

        classifications = await self.repo.get_classifications_by_request(request.id)

        # Build client-safe transaction views (no tax codes, no Xero IDs)
        transactions = []
        for c in classifications:
            # Generate hint from description if available
            hint = None
            if c.description and len(c.description) > 3:
                hint = f"This looks like it could be related to: {c.description}"

            transactions.append(
                {
                    "id": c.id,
                    "transaction_date": str(c.transaction_date) if c.transaction_date else None,
                    "amount": c.line_amount,
                    "description": c.description,
                    "hint": hint,
                    "current_category": c.client_category,
                    "current_description": c.client_description,
                    "is_classified": c.classified_at is not None,
                    "receipt_required": c.receipt_required,
                    "receipt_reason": c.receipt_flag_reason,
                    "receipt_attached": c.receipt_document_id is not None,
                }
            )

        # Build categories list for the UI
        categories = [
            {"id": cat["id"], "label": cat["label"], "group": cat["group"]}
            for cat in CLASSIFICATION_CATEGORIES
        ]

        classified_count = sum(1 for t in transactions if t["is_classified"])

        # Get practice name from connection
        practice_name = "Your accountant"
        if request.connection and hasattr(request.connection, "organisation_name"):
            practice_name = request.connection.organisation_name or practice_name

        return {
            "request_id": request.id,
            "practice_name": practice_name,
            "message": request.message,
            "expires_at": request.expires_at,
            "transactions": transactions,
            "categories": categories,
            "progress": {
                "total": len(transactions),
                "classified": classified_count,
                "remaining": len(transactions) - classified_count,
            },
        }

    async def save_classification(
        self,
        classification_id: UUID,
        request_id: UUID,
        connection_id: UUID,
        portal_session_id: UUID | None,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Save a client's classification for a single transaction."""
        request = await self.repo.get_classification_request_by_id_and_connection(
            request_id,
            connection_id,
        )
        if not request:
            raise ClassificationRequestNotFoundError(str(request_id))

        now = datetime.now(timezone.utc)

        # Update the classification
        update_fields: dict[str, Any] = {
            "classified_at": now,
            "classified_by_session": portal_session_id,
        }

        category = data.get("category")
        if category:
            update_fields["client_category"] = category
            update_fields["client_is_personal"] = False
            update_fields["client_needs_help"] = False
            # Handle special categories
            if category == "personal":
                update_fields["client_is_personal"] = True
                update_fields["client_category"] = "personal"
            elif category == "dont_know":
                update_fields["client_needs_help"] = True
                update_fields["client_category"] = "dont_know"

        if data.get("description"):
            update_fields["client_description"] = data["description"]
        if data.get("is_personal"):
            update_fields["client_is_personal"] = True
            update_fields["client_category"] = "personal"
        if data.get("needs_help"):
            update_fields["client_needs_help"] = True
            update_fields["client_category"] = "dont_know"

        classification = await self.repo.update_classification(
            classification_id,
            request.id,
            **update_fields,
        )
        if not classification:
            from app.modules.bas.exceptions import ClassificationNotFoundError

            raise ClassificationNotFoundError(str(classification_id))

        # Re-evaluate receipt flags based on new category (US6 — T037)
        if category and category not in ("personal", "dont_know", "other"):
            new_flag, new_reason = self._should_require_receipt(
                amount=classification.line_amount,
                category_id=category,
                description=classification.description,
            )
            if new_flag and not classification.receipt_required:
                await self.repo.update_classification(
                    classification_id,
                    request.id,
                    receipt_required=True,
                    receipt_flag_source="auto",
                    receipt_flag_reason=new_reason,
                )

        # Update request status to IN_PROGRESS on first classification
        if request.status in (ClassificationRequestStatus.SENT, ClassificationRequestStatus.VIEWED):
            await self.repo.update_request_status(
                request.id, ClassificationRequestStatus.IN_PROGRESS
            )

        # Update classified count
        count = await self.repo.count_classified(request.id)
        request.classified_count = count
        await self.session.flush()

        return {
            "id": classification.id,
            "is_classified": True,
            "classified_at": now,
        }

    async def submit_classifications(
        self,
        request_id: UUID,
        connection_id: UUID,
    ) -> dict[str, Any]:
        """Submit all classifications for a request."""
        from app.modules.bas.exceptions import ClassificationValidationError
        from app.modules.bas.models import BASAuditEventType

        request = await self.repo.get_classification_request_by_id_and_connection(
            request_id,
            connection_id,
        )
        if not request:
            raise ClassificationRequestNotFoundError(str(request_id))

        # US6 (T034): Validate IDK items have a description
        # US7 (T038): Validate all transactions are answered
        classifications = await self.repo.get_classifications_by_request(request.id)
        unanswered = []
        for c in classifications:
            if c.classified_at is None:
                unanswered.append(c.id)
            elif c.client_needs_help and not (
                c.client_description and c.client_description.strip()
            ):
                raise ClassificationValidationError(
                    code="missing_idk_description",
                    message="A description is required for 'I don't know' responses.",
                )

        if unanswered:
            raise ClassificationValidationError(
                code="unanswered_transactions",
                message=f"{len(unanswered)} transaction(s) have not been answered.",
                count=len(unanswered),
            )

        now = datetime.now(timezone.utc)
        classified_count = await self.repo.count_classified(request.id)

        await self.repo.update_request_status(
            request.id,
            ClassificationRequestStatus.SUBMITTED,
            submitted_at=now,
            classified_count=classified_count,
        )

        # Audit event
        await self.repo.create_audit_log(
            tenant_id=request.tenant_id,
            session_id=request.session_id,
            event_type=BASAuditEventType.CLASSIFICATION_REQUEST_SUBMITTED.value,
            event_description=f"Client submitted {classified_count}/{request.transaction_count} classifications",
            is_system_action=True,
            event_metadata={
                "request_id": str(request.id),
                "classified_count": classified_count,
                "total_count": request.transaction_count,
            },
        )

        # T033/T052: Emit CLIENT_ANSWERED_ROUND for round 2+ send-back responses
        if request.round_number > 1:
            from app.modules.integrations.xero.audit_events import (
                CLASSIFICATION_CLIENT_ANSWERED_ROUND,
            )

            await self.repo.create_audit_log(
                tenant_id=request.tenant_id,
                session_id=request.session_id,
                event_type=CLASSIFICATION_CLIENT_ANSWERED_ROUND,
                event_description=f"Client answered round {request.round_number} ({classified_count} items)",
                is_system_action=True,
                event_metadata={
                    "request_id": str(request.id),
                    "round_number": request.round_number,
                    "parent_request_id": str(request.parent_request_id)
                    if request.parent_request_id
                    else None,
                    "classified_count": classified_count,
                },
            )

        return {
            "request_id": request.id,
            "status": ClassificationRequestStatus.SUBMITTED,
            "classified_count": classified_count,
            "total_count": request.transaction_count,
            "submitted_at": now,
        }

    async def attach_receipt(
        self,
        classification_id: UUID,
        request_id: UUID,
        connection_id: UUID,
        document_id: UUID,
    ) -> dict[str, Any]:
        """Attach a receipt document to a classification."""
        request = await self.repo.get_classification_request_by_id_and_connection(
            request_id,
            connection_id,
        )
        if not request:
            raise ClassificationRequestNotFoundError(str(request_id))

        classification = await self.repo.update_classification(
            classification_id,
            request.id,
            receipt_document_id=document_id,
        )
        if not classification:
            from app.modules.bas.exceptions import ClassificationNotFoundError

            raise ClassificationNotFoundError(str(classification_id))

        return {
            "document_id": document_id,
            "filename": "uploaded",
        }

    # ------------------------------------------------------------------
    # US3: AI Maps Client Descriptions to Tax Codes
    # ------------------------------------------------------------------

    async def map_client_classifications(
        self,
        request_id: UUID,
        tenant_id: UUID,
    ) -> dict[str, Any]:
        """Map client descriptions to BAS tax codes via AI.

        Takes unprocessed client classifications and uses the LLM to map
        plain-English descriptions to BAS tax codes.
        """
        from app.modules.bas.classification_constants import CATEGORY_BY_ID
        from app.modules.bas.models import BASAuditEventType
        from app.modules.bas.tax_code_service import TaxCodeService

        request = await self.repo.get_classification_request_by_id(request_id, tenant_id)
        if not request:
            raise ClassificationRequestNotFoundError(str(request_id))

        unprocessed = await self.repo.get_unprocessed_classifications(request_id)
        if not unprocessed:
            return {"mapped_count": 0, "skipped_count": 0}

        now = datetime.now(timezone.utc)
        mapped_count = 0
        skipped_count = 0

        # Build items for LLM batch processing
        llm_items = []
        llm_classifications = []

        for c in unprocessed:
            # Skip "I don't know" — flagged for accountant, no AI mapping
            if c.client_needs_help:
                skipped_count += 1
                continue

            # Personal items → map to BASEXCLUDED with high confidence
            if c.client_is_personal:
                await self.repo.update_classification(
                    c.id,
                    request.id,
                    ai_suggested_tax_type="BASEXCLUDED",
                    ai_confidence=Decimal("0.95"),
                    ai_mapped_at=now,
                )
                mapped_count += 1
                continue

            # Build context for LLM
            category = CATEGORY_BY_ID.get(c.client_category or "") if c.client_category else None
            category_label = category["label"] if category else None
            typical_tax = category["typical_tax_type"] if category else None

            llm_items.append(
                {
                    "description": c.description or "",
                    "line_amount": str(c.line_amount),
                    "account_code": c.account_code or "",
                    "contact_name": c.contact_name or "",
                    "client_category": category_label,
                    "client_description": c.client_description,
                    "typical_tax_type": typical_tax,
                }
            )
            llm_classifications.append(c)

        # Call LLM for remaining items
        if llm_items:
            tax_code_service = TaxCodeService(self.session)
            try:
                llm_results = await tax_code_service.suggest_from_client_input(llm_items)
            except Exception:
                logger.warning(
                    "LLM mapping failed, falling back to category defaults", exc_info=True
                )
                # Fallback: use typical_tax_type from category
                llm_results = []
                for item in llm_items:
                    llm_results.append(
                        {
                            "suggested_tax_type": item.get("typical_tax_type"),
                            "confidence": 0.6,
                        }
                    )

            for i, result in enumerate(llm_results):
                if i >= len(llm_classifications):
                    break
                c = llm_classifications[i]
                suggested = result.get("suggested_tax_type")
                raw_confidence = result.get("confidence", 0.6)
                # Client category selection = higher confidence than free text only
                confidence = Decimal(str(min(0.90, max(0.60, raw_confidence))))
                if c.client_category and c.client_category not in ("other",):
                    confidence = max(confidence, Decimal("0.75"))

                await self.repo.update_classification(
                    c.id,
                    request.id,
                    ai_suggested_tax_type=suggested,
                    ai_confidence=confidence,
                    ai_mapped_at=now,
                )
                mapped_count += 1

        # Audit event
        await self.repo.create_audit_log(
            tenant_id=tenant_id,
            session_id=request.session_id,
            event_type=BASAuditEventType.CLASSIFICATION_AI_MAPPED.value,
            event_description=f"AI mapped {mapped_count} client classifications",
            is_system_action=True,
            event_metadata={
                "request_id": str(request_id),
                "mapped_count": mapped_count,
                "skipped_count": skipped_count,
            },
        )

        return {"mapped_count": mapped_count, "skipped_count": skipped_count}

    # ------------------------------------------------------------------
    # US4: Accountant Reviews Classifications
    # ------------------------------------------------------------------

    async def get_review(
        self,
        session_id: UUID,
        tenant_id: UUID,
        filter_type: str = "all",
    ) -> dict[str, Any]:
        """Get all classifications for accountant review.

        Triggers AI mapping on first access if not yet done.
        """
        from app.modules.bas.classification_constants import CATEGORY_BY_ID

        request = await self.repo.get_classification_request_by_session(session_id)
        if not request or request.tenant_id != tenant_id:
            raise ClassificationRequestNotFoundError()

        # Lazy AI mapping on first review access
        unprocessed = await self.repo.get_unprocessed_classifications(request.id)
        if unprocessed:
            await self.map_client_classifications(request.id, tenant_id)

        # Update status
        if request.status == ClassificationRequestStatus.SUBMITTED:
            await self.repo.update_request_status(request.id, ClassificationRequestStatus.REVIEWING)

        classifications = await self.repo.get_classifications_by_request(request.id)

        items = []
        summary = {
            "total": 0,
            "classified_by_client": 0,
            "marked_personal": 0,
            "needs_help": 0,
            "auto_mappable": 0,
            "needs_attention": 0,
            "already_reviewed": 0,
            "receipts_required": 0,
            "receipts_attached": 0,
            "receipts_missing": 0,
        }

        for c in classifications:
            # By default, only show items the client actually classified
            if filter_type != "all_including_unclassified" and c.classified_at is None:
                continue

            cat = CATEGORY_BY_ID.get(c.client_category or "") if c.client_category else None
            needs_attention = (
                (c.ai_confidence is not None and c.ai_confidence < Decimal("0.7"))
                or c.client_needs_help
                or c.client_is_personal
                or (c.receipt_required and c.receipt_document_id is None)
            )

            item = {
                "id": c.id,
                "source_type": c.source_type,
                "source_id": c.source_id,
                "line_item_index": c.line_item_index,
                "transaction_date": str(c.transaction_date) if c.transaction_date else None,
                "line_amount": c.line_amount,
                "description": c.description,
                "contact_name": c.contact_name,
                "account_code": c.account_code,
                "client_category": c.client_category,
                "client_category_label": cat["label"] if cat else None,
                "client_description": c.client_description,
                "client_is_personal": c.client_is_personal,
                "client_needs_help": c.client_needs_help,
                "classified_at": c.classified_at,
                "ai_suggested_tax_type": c.ai_suggested_tax_type,
                "ai_confidence": c.ai_confidence,
                "needs_attention": needs_attention,
                "receipt_required": c.receipt_required,
                "receipt_reason": c.receipt_flag_reason,
                "receipt_attached": c.receipt_document_id is not None,
                "receipt_document_id": c.receipt_document_id,
                "suggestion_id": c.suggestion_id,
                "accountant_action": c.accountant_action,
            }

            # Apply filter
            if filter_type == "needs_attention" and not needs_attention:
                continue
            if filter_type == "auto_mappable" and (needs_attention or c.accountant_action):
                continue

            items.append(item)

            # Update summary
            summary["total"] += 1
            if c.classified_at:
                summary["classified_by_client"] += 1
            if c.client_is_personal:
                summary["marked_personal"] += 1
            if c.client_needs_help:
                summary["needs_help"] += 1
            if c.ai_confidence and c.ai_confidence >= Decimal("0.7") and not needs_attention:
                summary["auto_mappable"] += 1
            if needs_attention:
                summary["needs_attention"] += 1
            if c.accountant_action:
                summary["already_reviewed"] += 1
            if c.receipt_required:
                summary["receipts_required"] += 1
                if c.receipt_document_id:
                    summary["receipts_attached"] += 1
                else:
                    summary["receipts_missing"] += 1

        return {
            "request_id": request.id,
            "request_status": request.status,
            "classifications": items,
            "summary": summary,
        }

    async def resolve_classification(
        self,
        classification_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        action: str,
        tax_type: str | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Approve, override, or reject a classification."""
        from app.modules.bas.exceptions import InvalidClassificationActionError
        from app.modules.bas.models import BASAuditEventType

        if action not in ("approved", "overridden", "rejected"):
            raise InvalidClassificationActionError(action)

        # Find the classification and its request
        request = None
        classification = None
        # We need to find which request this classification belongs to
        from sqlalchemy import select

        from app.modules.bas.classification_models import ClientClassification

        result = await self.session.execute(
            select(ClientClassification).where(
                ClientClassification.id == classification_id,
                ClientClassification.tenant_id == tenant_id,
            )
        )
        classification = result.scalars().first()
        if not classification:
            from app.modules.bas.exceptions import ClassificationNotFoundError

            raise ClassificationNotFoundError(str(classification_id))

        now = datetime.now(timezone.utc)
        final_tax_type = None

        if action == "approved":
            final_tax_type = classification.ai_suggested_tax_type
        elif action == "overridden":
            final_tax_type = tax_type

        classification.accountant_action = action
        classification.accountant_user_id = user_id
        classification.accountant_acted_at = now
        if action == "overridden":
            classification.accountant_tax_type = tax_type
            classification.accountant_reason = reason
        await self.session.flush()

        # Audit — get session_id from the classification request (avoid lazy load)
        cls_request = await self.repo.get_classification_request_by_id(
            classification.request_id, tenant_id
        )
        session_id_for_audit = cls_request.session_id if cls_request else None
        if session_id_for_audit:
            await self.repo.create_audit_log(
                tenant_id=tenant_id,
                session_id=session_id_for_audit,
                event_type=BASAuditEventType.CLASSIFICATION_REVIEWED.value,
                event_description=f"Classification {action}: {final_tax_type or 'N/A'}",
                performed_by=user_id,
                event_metadata={
                    "classification_id": str(classification_id),
                    "action": action,
                    "final_tax_type": final_tax_type,
                },
            )

        return {
            "id": classification.id,
            "accountant_action": action,
            "final_tax_type": final_tax_type,
            "suggestion_id": classification.suggestion_id,
        }

    async def bulk_approve(
        self,
        request_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        min_confidence: Decimal = Decimal("0.80"),
        exclude_personal: bool = True,
        exclude_needs_help: bool = True,
    ) -> dict[str, Any]:
        """Bulk approve classifications above a confidence threshold."""
        request = await self.repo.get_classification_request_by_id(request_id, tenant_id)
        if not request:
            raise ClassificationRequestNotFoundError(str(request_id))

        classifications = await self.repo.get_classifications_by_request(request.id)
        now = datetime.now(timezone.utc)
        approved = 0
        skipped = 0

        for c in classifications:
            if c.accountant_action:
                skipped += 1
                continue
            if exclude_personal and c.client_is_personal:
                skipped += 1
                continue
            if exclude_needs_help and c.client_needs_help:
                skipped += 1
                continue
            if c.ai_confidence is None or c.ai_confidence < min_confidence:
                skipped += 1
                continue

            c.accountant_action = "approved"
            c.accountant_user_id = user_id
            c.accountant_acted_at = now
            approved += 1

        await self.session.flush()
        return {"approved_count": approved, "skipped_count": skipped}

    # ------------------------------------------------------------------
    # US5: Audit Trail
    # ------------------------------------------------------------------

    async def export_audit_trail(
        self,
        session_id: UUID,
        tenant_id: UUID,
        export_format: str = "json",
    ) -> list[dict[str, Any]]:
        """Export the full audit trail for a classification request."""
        from app.modules.bas.classification_constants import CATEGORY_BY_ID

        request = await self.repo.get_classification_request_by_session(session_id)
        if not request or request.tenant_id != tenant_id:
            raise ClassificationRequestNotFoundError()

        classifications = await self.repo.get_classifications_by_request(request.id)

        rows = []
        for c in classifications:
            cat = CATEGORY_BY_ID.get(c.client_category or "") if c.client_category else None
            final_tax = c.accountant_tax_type or c.ai_suggested_tax_type

            rows.append(
                {
                    "transaction_date": str(c.transaction_date) if c.transaction_date else "",
                    "amount": str(c.line_amount),
                    "description": c.description or "",
                    "contact_name": c.contact_name or "",
                    "classified_by": str(c.classified_by_session)
                    if c.classified_by_session
                    else "",
                    "classified_at": c.classified_at.isoformat() if c.classified_at else "",
                    "client_category": cat["label"] if cat else (c.client_category or ""),
                    "client_description": c.client_description or "",
                    "client_is_personal": str(c.client_is_personal),
                    "ai_suggested_code": c.ai_suggested_tax_type or "",
                    "ai_confidence": str(c.ai_confidence) if c.ai_confidence else "",
                    "accountant_action": c.accountant_action or "",
                    "accountant_user_id": str(c.accountant_user_id) if c.accountant_user_id else "",
                    "approved_at": c.accountant_acted_at.isoformat()
                    if c.accountant_acted_at
                    else "",
                    "final_tax_code": final_tax or "",
                    "override_reason": c.accountant_reason or "",
                    "receipt_required": str(c.receipt_required),
                    "receipt_flag_reason": c.receipt_flag_reason or "",
                    "receipt_attached": str(c.receipt_document_id is not None),
                    "receipt_document_id": str(c.receipt_document_id)
                    if c.receipt_document_id
                    else "",
                }
            )

        return rows

    # ------------------------------------------------------------------
    # US9: Send-Back Loop (Spec 049)
    # ------------------------------------------------------------------

    async def send_items_back(
        self,
        request_id: UUID,
        items_with_comments: list[dict],
        triggered_by: UUID,
        tenant_id: UUID,
    ) -> dict[str, Any]:
        """Send IDK items back to the client with agent guidance comments.

        Creates a new ClassificationRequest (round N+1), copies the IDK
        ClientClassification records, creates AgentTransactionNote records,
        creates ClientClassificationRound records, generates a new magic link,
        and sends the client an email.

        Args:
            request_id: Source classification request ID.
            items_with_comments: List of dicts with classification_id and agent_comment.
            triggered_by: Practice user ID initiating the send-back.
            tenant_id: Tenant ID for RLS.

        Returns:
            Dict with new request details.
        """
        from app.modules.bas.exceptions import ClassificationValidationError
        from app.modules.integrations.xero.audit_events import CLASSIFICATION_ITEMS_SENT_BACK
        from app.modules.portal.auth.magic_link import MagicLinkService

        # Load source request
        source_request = await self.repo.get_classification_request_by_id(request_id, tenant_id)
        if not source_request:
            raise ClassificationRequestNotFoundError(str(request_id))

        # Validate all items are IDK
        classification_ids = [
            UUID(item["classification_id"])
            if isinstance(item["classification_id"], str)
            else item["classification_id"]
            for item in items_with_comments
        ]
        classifications = await self.repo.get_classifications_by_request(request_id)
        idk_map = {c.id: c for c in classifications if c.client_needs_help}

        for item in items_with_comments:
            cid = (
                UUID(item["classification_id"])
                if isinstance(item["classification_id"], str)
                else item["classification_id"]
            )
            if cid not in idk_map:
                raise ClassificationValidationError(
                    code="not_idk_item",
                    message=f"Classification {cid} is not an IDK item",
                )
            comment = item.get("agent_comment", "")
            if not comment or not comment.strip():
                raise ClassificationValidationError(
                    code="missing_agent_comment",
                    message="Agent comment is required for send-back items",
                )

        new_round_number = source_request.round_number + 1

        # Create new ClassificationRequest (round N+1)
        from app.modules.bas.classification_models import ClassificationRequest

        new_request = ClassificationRequest(
            tenant_id=tenant_id,
            connection_id=source_request.connection_id,
            session_id=source_request.session_id,
            requested_by=triggered_by,
            client_email=source_request.client_email,
            status=ClassificationRequestStatus.DRAFT,
            transaction_count=len(items_with_comments),
            parent_request_id=source_request.id,
            round_number=new_round_number,
        )
        # Calculate 7-day expiry
        from datetime import timedelta, timezone

        new_request.expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        self.session.add(new_request)
        await self.session.flush()

        # Copy IDK ClientClassification records into new request

        from app.modules.bas.classification_models import ClientClassification

        for item in items_with_comments:
            cid = (
                UUID(item["classification_id"])
                if isinstance(item["classification_id"], str)
                else item["classification_id"]
            )
            orig = idk_map[cid]
            new_cc = ClientClassification(
                tenant_id=tenant_id,
                request_id=new_request.id,
                source_type=orig.source_type,
                source_id=orig.source_id,
                line_item_index=orig.line_item_index,
                transaction_date=orig.transaction_date,
                line_amount=orig.line_amount,
                description=orig.description,
                contact_name=orig.contact_name,
                account_code=orig.account_code,
            )
            self.session.add(new_cc)
            await self.session.flush()

            # Create AgentTransactionNote (is_send_back_comment=True)
            await self.repo.create_agent_note(
                tenant_id=tenant_id,
                request_id=new_request.id,
                source_type=orig.source_type,
                source_id=orig.source_id,
                line_item_index=orig.line_item_index,
                note_text=item["agent_comment"],
                is_send_back_comment=True,
                created_by=triggered_by,
            )

            # Create ClientClassificationRound
            await self.repo.create_classification_round(
                tenant_id=tenant_id,
                session_id=source_request.session_id,
                source_type=orig.source_type,
                source_id=orig.source_id,
                line_item_index=orig.line_item_index,
                round_number=new_round_number,
                request_id=new_request.id,
                agent_comment=item["agent_comment"],
            )

        # Generate new magic link
        magic_link_service = MagicLinkService(self.session)
        invitation, token = await magic_link_service.create_invitation(
            tenant_id=tenant_id,
            connection_id=source_request.connection_id,
            email=source_request.client_email,
            invited_by=triggered_by,
            expires_hours=7 * 24,
        )
        new_request.invitation_id = invitation.id
        await self.session.flush()

        magic_link_url = magic_link_service.build_magic_link_url(token)
        magic_link_url = f"{magic_link_url}&redirect=/portal/classify/{new_request.id}"

        # Send email with new link
        try:
            from app.email.service import get_email_service
            from app.email.templates import EmailTemplate

            email_service = get_email_service()
            await email_service.send_email(
                to=source_request.client_email,
                template=EmailTemplate(
                    subject="Your accountant has a follow-up question about your transactions",
                    html=f"<p>Your accountant has reviewed your responses and has a follow-up question. "
                    f"Please click the link below to respond: <a href='{magic_link_url}'>{magic_link_url}</a></p>",
                    text=f"Your accountant has a follow-up question. Please visit: {magic_link_url}",
                ),
                tags=[{"name": "type", "value": "classification_sendback"}],
            )
            await magic_link_service.mark_invitation_sent(
                invitation_id=invitation.id, delivered=True
            )
        except Exception:
            logger.warning("Failed to send send-back email", exc_info=True)
            await magic_link_service.mark_invitation_sent(
                invitation_id=invitation.id, delivered=False
            )

        # Update status to SENT
        await self.repo.update_request_status(new_request.id, ClassificationRequestStatus.SENT)

        # Audit event
        await self.repo.create_audit_log(
            tenant_id=tenant_id,
            session_id=source_request.session_id,
            event_type=CLASSIFICATION_ITEMS_SENT_BACK,
            event_description=f"Sent {len(items_with_comments)} IDK items back (round {new_round_number})",
            performed_by=triggered_by,
            event_metadata={
                "new_request_id": str(new_request.id),
                "source_request_id": str(request_id),
                "round_number": new_round_number,
                "item_count": len(items_with_comments),
            },
        )

        return {
            "new_request_id": new_request.id,
            "round_number": new_round_number,
            "client_email": source_request.client_email,
            "item_count": len(items_with_comments),
            "expires_at": new_request.expires_at,
        }

    async def get_classification_thread(
        self,
        session_id: UUID,
        source_type: str,
        source_id: UUID,
        line_item_index: int,
        tenant_id: UUID,
    ) -> list[Any]:
        """Get the full send-back conversation thread for a transaction.

        Returns ClientClassificationRound records ordered by round_number.
        """
        return await self.repo.list_rounds_for_transaction(
            tenant_id=tenant_id,
            session_id=session_id,
            source_type=source_type,
            source_id=source_id,
            line_item_index=line_item_index,
        )
