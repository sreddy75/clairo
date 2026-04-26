"""Tax code resolution service for BAS preparation.

Spec 046: AI Tax Code Resolution for BAS Preparation.

Detects excluded transactions, generates AI-powered tax code suggestions
using a 4-tier confidence waterfall, and manages the accountant review workflow.
"""

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.bas.calculator import TAX_TYPE_MAPPING, GSTCalculator
from app.modules.bas.exceptions import (
    InvalidTaxTypeError,
    SessionNotEditableForSuggestionsError,
    SplitAmountMismatchError,
    SplitOverrideNotFoundError,
    SuggestionAlreadyResolvedError,
    SuggestionNotFoundError,
)
from app.modules.bas.models import (
    BASSession,
    ConfidenceTier,
    TaxCodeOverride,
    TaxCodeSuggestion,
)
from app.modules.bas.repository import BASRepository
from app.modules.bas.schemas import VALID_TAX_TYPES

logger = logging.getLogger(__name__)

# Tax types that should be treated as excluded/unmapped
EXCLUDED_TAX_TYPES = {"BASEXCLUDED", "NONE", "NONGST", ""}


class TaxCodeService:
    """Service for tax code suggestion and resolution."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = BASRepository(session)

    # =========================================================================
    # Detection & Suggestion Generation
    # =========================================================================

    async def detect_and_generate(
        self,
        session_id: UUID,
        tenant_id: UUID,
    ) -> dict[str, Any]:
        """Detect excluded items and generate suggestions.

        Returns breakdown of generated suggestions by tier.
        """
        bas_session = await self._get_editable_session(session_id, tenant_id)
        period = bas_session.period

        # Run calculator to get excluded items
        calculator = GSTCalculator(self.session)
        gst_result = await calculator.calculate(
            connection_id=period.connection_id,
            start_date=period.start_date,
            end_date=period.end_date,
        )

        excluded = gst_result.excluded_items

        # BASEXCLUDED is a valid Xero tax code meaning "excluded from BAS" (e.g. wages).
        # These are correctly coded — do NOT flag them as needing a tax code.
        excluded = [
            item for item in excluded if item.get("tax_type", "").upper() != "BASEXCLUDED"
        ]

        # Enrich excluded items with contact names and dates
        enriched = (
            await self._enrich_excluded_items(excluded, period.connection_id, tenant_id)
            if excluded
            else []
        )

        # Build account lookup for Tier 1
        accounts_map = await self._build_accounts_map(period.connection_id)

        # Generate suggestions with tiered waterfall
        suggestions_data = []
        unclassified_indices: list[int] = []  # Track items needing LLM
        breakdown = {
            "account_default": 0,
            "client_history": 0,
            "tenant_history": 0,
            "llm_classification": 0,
            "no_suggestion": 0,
        }

        for item in enriched:
            suggestion = self._build_suggestion_record(item, session_id, tenant_id)

            # Tier 1: Account default
            result = self._suggest_from_account_default(item.get("account_code"), accounts_map)
            if result:
                suggestion.update(
                    {
                        "suggested_tax_type": result[0],
                        "confidence_score": result[1],
                        "confidence_tier": ConfidenceTier.ACCOUNT_DEFAULT,
                        "suggestion_basis": result[2],
                    }
                )
                breakdown["account_default"] += 1
            else:
                # Tier 2: Client history
                result = await self._suggest_from_client_history(
                    item.get("account_code"), period.connection_id
                )
                if result:
                    suggestion.update(
                        {
                            "suggested_tax_type": result[0],
                            "confidence_score": result[1],
                            "confidence_tier": ConfidenceTier.CLIENT_HISTORY,
                            "suggestion_basis": result[2],
                        }
                    )
                    breakdown["client_history"] += 1
                else:
                    # Tier 3: Tenant history
                    result = await self._suggest_from_tenant_history(
                        item.get("account_code"), tenant_id
                    )
                    if result:
                        suggestion.update(
                            {
                                "suggested_tax_type": result[0],
                                "confidence_score": result[1],
                                "confidence_tier": ConfidenceTier.TENANT_HISTORY,
                                "suggestion_basis": result[2],
                            }
                        )
                        breakdown["tenant_history"] += 1
                    else:
                        # Track for LLM classification
                        unclassified_indices.append(len(suggestions_data))

            suggestions_data.append(suggestion)

        # Tier 4: LLM classification for remaining unclassified items
        if unclassified_indices:
            items_for_llm = [enriched[idx] for idx in unclassified_indices if idx < len(enriched)]
            if items_for_llm:
                llm_results = await self.suggest_from_llm(items_for_llm, accounts_map)
                for i, idx in enumerate(unclassified_indices):
                    if i < len(llm_results) and llm_results[i].get("suggested_tax_type"):
                        suggestions_data[idx].update(llm_results[i])
                        breakdown["llm_classification"] += 1
                    else:
                        breakdown["no_suggestion"] += 1

        # Spec 057: Enrich suggestions with Xero reconciliation status and
        # create auto-parked suggestions for ALL unreconciled bank transactions.
        await self._apply_reconciliation_to_suggestions(
            suggestions_data,
            period.connection_id,
            tenant_id,
            session_id,
            period.start_date,
            period.end_date,
        )

        # Bulk insert (idempotent via ON CONFLICT DO NOTHING)
        created = await self.repo.bulk_create_suggestions(suggestions_data)

        # Count already-resolved items that were skipped
        skipped = len(suggestions_data) - created

        # Spec 057: Emit audit events for auto-parked suggestions (newly inserted only).
        # We emit one audit log entry summarising auto-parks rather than one per row
        # to avoid flooding the audit log on large sessions.
        auto_parked_count = sum(
            1 for s in suggestions_data if s.get("auto_park_reason") == "unreconciled_in_xero"
        )
        if auto_parked_count > 0:
            await self.repo.create_audit_log(
                tenant_id=tenant_id,
                session_id=session_id,
                event_type="transaction.auto_parked",
                event_description=(
                    f"Auto-parked {auto_parked_count} unreconciled bank transactions"
                ),
                is_system_action=True,
                event_metadata={
                    "auto_parked_count": auto_parked_count,
                    "reason": "auto_parked_unreconciled",
                },
            )

        # Audit log
        await self.repo.create_audit_log(
            tenant_id=tenant_id,
            session_id=session_id,
            event_type="tax_code_suggestions_generated",
            event_description=f"Generated {created} tax code suggestions ({skipped} already resolved)",
            is_system_action=True,
            event_metadata={
                "generated": created,
                "skipped": skipped,
                "breakdown": breakdown,
            },
        )

        return {
            "generated": created,
            "skipped_already_resolved": skipped,
            "breakdown": breakdown,
        }

    # =========================================================================
    # Reconciliation Refresh (Spec 057)
    # =========================================================================

    async def refresh_reconciliation_status(
        self,
        session_id: UUID,
        tenant_id: UUID,
        connection_id: UUID,
    ) -> dict[str, Any]:
        """Re-fetch Xero reconciliation status for all bank-transaction suggestions.

        Spec 057: Allows accountants to update the reconciled/parked grouping
        mid-session without waiting for a full Xero data re-sync.

        Returns counts of reclassified suggestions (newly_reconciled, newly_unreconciled).
        Raises ExternalServiceError if Xero is unavailable.
        """
        from app.core.exceptions import ExternalServiceError

        source_ids = await self.repo.get_bank_transaction_source_ids(session_id, tenant_id)
        if not source_ids:
            return {"reclassified_count": 0, "newly_reconciled": 0, "newly_unreconciled": 0}

        try:
            from sqlalchemy import select

            from app.modules.integrations.xero.models import XeroBankTransaction

            # source_ids are string representations of XeroBankTransaction.id (PostgreSQL UUID).
            source_uuids = [UUID(sid) for sid in source_ids]
            result = await self.session.execute(
                select(
                    XeroBankTransaction.id,
                    XeroBankTransaction.is_reconciled,
                ).where(
                    XeroBankTransaction.connection_id == connection_id,
                    XeroBankTransaction.id.in_(source_uuids),
                )
            )
            reconciled_map: dict[str, bool] = {
                str(row.id): bool(row.is_reconciled) for row in result.all()
            }
        except Exception as exc:
            raise ExternalServiceError(
                service="xero",
                message="Unable to fetch reconciliation status from Xero",
                original_error=str(exc),
            ) from exc

        counts = await self.repo.apply_reconciliation_refresh(session_id, tenant_id, reconciled_map)
        reclassified_count = counts["newly_reconciled"] + counts["newly_unreconciled"]

        await self.repo.create_audit_log(
            tenant_id=tenant_id,
            session_id=session_id,
            event_type="transaction.reconciliation_refreshed",
            event_description=(
                f"Refreshed reconciliation status: {reclassified_count} transactions reclassified"
            ),
            is_system_action=False,
            event_metadata={
                "reclassified_count": reclassified_count,
                "newly_reconciled": counts["newly_reconciled"],
                "newly_unreconciled": counts["newly_unreconciled"],
                "refresh_source": "manual",
            },
        )

        await self.session.commit()
        return {
            "reclassified_count": reclassified_count,
            "newly_reconciled": counts["newly_reconciled"],
            "newly_unreconciled": counts["newly_unreconciled"],
        }

    # =========================================================================
    # Summary
    # =========================================================================

    async def get_summary(self, session_id: UUID, tenant_id: UUID) -> dict[str, Any]:
        """Get suggestion summary for the exclusion banner."""
        return await self.repo.get_suggestion_summary(session_id, tenant_id)

    # =========================================================================
    # Recalculation
    # =========================================================================

    async def apply_and_recalculate(
        self,
        session_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
    ) -> dict[str, Any]:
        """Apply approved suggestions as overrides and recalculate BAS.

        1. Creates TaxCodeOverride records for approved/overridden suggestions
        2. Builds override lookup dict
        3. Recalculates BAS with overrides applied
        4. Returns before/after comparison
        """
        bas_session = await self._get_editable_session(session_id, tenant_id)
        period = bas_session.period

        # Get approved/overridden suggestions that need overrides
        suggestions = await self.repo.list_suggestions(session_id, tenant_id, status=None)
        to_apply = [
            s for s in suggestions if s.status in ("approved", "overridden") and s.applied_tax_type
        ]

        if not to_apply:
            from app.modules.bas.exceptions import NoApprovedSuggestionsError

            raise NoApprovedSuggestionsError()

        # Create overrides for items that don't have one yet
        applied_count = 0
        for s in to_apply:
            existing = await self.repo.get_active_override(
                period.connection_id,
                str(s.source_type.value if hasattr(s.source_type, "value") else s.source_type),
                s.source_id,
                s.line_item_index,
                tenant_id,
            )
            if not existing:
                await self.repo.create_override(
                    {
                        "tenant_id": tenant_id,
                        "connection_id": period.connection_id,
                        "source_type": s.source_type,
                        "source_id": s.source_id,
                        "line_item_index": s.line_item_index,
                        "original_tax_type": s.original_tax_type,
                        "override_tax_type": s.applied_tax_type,
                        "applied_by": user_id,
                        "applied_at": datetime.now(UTC),
                        "suggestion_id": s.id,
                    }
                )
                applied_count += 1

        # Get before values (current calculation)
        before = {}
        if bas_session.calculation:
            calc = bas_session.calculation
            before = {
                "g1_total_sales": float(calc.g1_total_sales or 0),
                "field_1a_gst_on_sales": float(calc.field_1a_gst_on_sales or 0),
                "g11_non_capital_purchases": float(calc.g11_non_capital_purchases or 0),
                "field_1b_gst_on_purchases": float(calc.field_1b_gst_on_purchases or 0),
                "g10_capital_purchases": float(calc.g10_capital_purchases or 0),
                "net_gst": float(calc.gst_payable or 0),
            }

        # Build overrides dict and recalculate
        active_overrides = await self.repo.get_active_overrides(period.connection_id, tenant_id)
        overrides_dict: dict[tuple[str, str, int], str] = {}
        for o in active_overrides:
            key = (
                str(o.source_type.value if hasattr(o.source_type, "value") else o.source_type),
                str(o.source_id),
                o.line_item_index,
            )
            overrides_dict[key] = o.override_tax_type

        calculator = GSTCalculator(self.session, overrides=overrides_dict)
        gst_result = await calculator.calculate(
            connection_id=period.connection_id,
            start_date=period.start_date,
            end_date=period.end_date,
        )

        # Save the new calculation via repo.upsert_calculation
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
            w1_total_wages=Decimal("0"),
            w2_amount_withheld=Decimal("0"),
            gst_payable=gst_result.gst_payable,
            total_payable=gst_result.gst_payable,
            calculation_duration_ms=0,
            transaction_count=gst_result.transaction_count,
            invoice_count=gst_result.invoice_count,
            pay_run_count=0,
        )

        # Build after values
        after = {
            "g1_total_sales": float(gst_result.g1_total_sales),
            "field_1a_gst_on_sales": float(gst_result.field_1a_gst_on_sales),
            "g11_non_capital_purchases": float(gst_result.g11_non_capital_purchases),
            "field_1b_gst_on_purchases": float(gst_result.field_1b_gst_on_purchases),
            "g10_capital_purchases": float(gst_result.g10_capital_purchases),
            "net_gst": float(gst_result.gst_payable),
        }

        # Build comparison dict
        recalculation = {}
        for key in after:
            recalculation[f"{key}_before"] = Decimal(str(before.get(key, 0)))
            recalculation[f"{key}_after"] = Decimal(str(after[key]))

        # Audit log
        await self.repo.create_audit_log(
            tenant_id=tenant_id,
            session_id=session_id,
            event_type="bas_recalculated_after_resolution",
            event_description=f"BAS recalculated after applying {applied_count} tax code resolutions",
            performed_by=user_id,
            event_metadata={
                "applied_count": applied_count,
                "before": before,
                "after": after,
            },
        )

        return {
            "applied_count": applied_count,
            "recalculation": recalculation,
        }

    # =========================================================================
    # Resolution Actions
    # =========================================================================

    async def approve_suggestion(
        self,
        suggestion_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        notes: str | None = None,
    ) -> TaxCodeSuggestion:
        """Approve a suggestion — apply the suggested tax code."""
        suggestion = await self._get_pending_suggestion(suggestion_id, tenant_id)
        bas_session = await self._get_editable_session(suggestion.session_id, tenant_id)

        suggestion.status = "approved"
        suggestion.applied_tax_type = suggestion.suggested_tax_type
        suggestion.resolved_by = user_id
        suggestion.resolved_at = datetime.now(UTC)

        await self.repo.update_suggestion(suggestion)

        # Create the TaxCodeOverride immediately so sync works without requiring Apply & Recalculate first.
        source_type = str(
            suggestion.source_type.value
            if hasattr(suggestion.source_type, "value")
            else suggestion.source_type
        )
        existing = await self.repo.get_active_override(
            bas_session.period.connection_id,
            source_type,
            suggestion.source_id,
            suggestion.line_item_index,
            tenant_id,
        )
        if not existing:
            await self.repo.create_override(
                {
                    "tenant_id": tenant_id,
                    "connection_id": bas_session.period.connection_id,
                    "source_type": suggestion.source_type,
                    "source_id": suggestion.source_id,
                    "line_item_index": suggestion.line_item_index,
                    "original_tax_type": suggestion.original_tax_type,
                    "override_tax_type": suggestion.applied_tax_type,
                    "applied_by": user_id,
                    "applied_at": datetime.now(UTC),
                    "suggestion_id": suggestion.id,
                }
            )

        await self.repo.create_audit_log(
            tenant_id=tenant_id,
            session_id=suggestion.session_id,
            event_type="tax_code_suggestion_approved",
            event_description=f"Approved tax code suggestion: {suggestion.original_tax_type} → {suggestion.applied_tax_type}",
            performed_by=user_id,
            event_metadata={
                "suggestion_id": str(suggestion.id),
                "original_tax_type": suggestion.original_tax_type,
                "suggested_tax_type": suggestion.suggested_tax_type,
                "applied_tax_type": suggestion.applied_tax_type,
                "confidence_score": float(suggestion.confidence_score)
                if suggestion.confidence_score
                else None,
                "confidence_tier": str(suggestion.confidence_tier)
                if suggestion.confidence_tier
                else None,
                "notes": notes,
            },
        )

        # Core audit trail for AI suggestion approval
        try:
            from app.core.audit import AuditService

            audit = AuditService(self.session)
            await audit.log_event(
                event_type="ai.suggestion.approved",
                event_category="data",
                actor_type="user",
                actor_id=user_id,
                tenant_id=tenant_id,
                resource_type="tax_code_suggestion",
                resource_id=suggestion_id,
                action="update",
                outcome="success",
                old_values={"ai_suggested": suggestion.suggested_tax_type},
                new_values={"applied": suggestion.applied_tax_type},
            )
        except Exception:
            pass

        return suggestion

    async def reject_suggestion(
        self,
        suggestion_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        reason: str | None = None,
    ) -> TaxCodeSuggestion:
        """Deprecated: maps to dismiss_suggestion internally (Spec 056)."""
        return await self.dismiss_suggestion(suggestion_id, tenant_id, user_id, reason)

    async def override_suggestion(
        self,
        suggestion_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        tax_type: str,
        reason: str | None = None,
    ) -> TaxCodeSuggestion:
        """Override a suggestion with a different tax code."""
        tax_type = tax_type.upper()
        if tax_type not in VALID_TAX_TYPES:
            raise InvalidTaxTypeError(tax_type)

        # Allow re-overriding already-approved/overridden suggestions (e.g. to
        # correct a tax code after a failed Xero write-back).
        suggestion = await self.repo.get_suggestion(suggestion_id, tenant_id)
        if not suggestion:
            raise SuggestionNotFoundError(str(suggestion_id))
        bas_session = await self._get_editable_session(suggestion.session_id, tenant_id)

        # Deactivate any existing active override for this suggestion so we can
        # create a fresh one with the new tax type immediately below.
        if suggestion.status in ("approved", "overridden"):
            from sqlalchemy import and_, update

            from app.modules.bas.models import TaxCodeOverride

            await self.repo.session.execute(
                update(TaxCodeOverride)
                .where(
                    and_(
                        TaxCodeOverride.suggestion_id == suggestion_id,
                        TaxCodeOverride.is_active.is_(True),
                    )
                )
                .values(is_active=False)
            )
            await self.repo.session.flush()

        suggestion.status = "overridden"
        suggestion.applied_tax_type = tax_type
        suggestion.resolved_by = user_id
        suggestion.resolved_at = datetime.now(UTC)

        await self.repo.update_suggestion(suggestion)

        # Create the new override immediately so sync works without requiring Apply & Recalculate first.
        await self.repo.create_override(
            {
                "tenant_id": tenant_id,
                "connection_id": bas_session.period.connection_id,
                "source_type": suggestion.source_type,
                "source_id": suggestion.source_id,
                "line_item_index": suggestion.line_item_index,
                "original_tax_type": suggestion.original_tax_type,
                "override_tax_type": tax_type,
                "applied_by": user_id,
                "applied_at": datetime.now(UTC),
                "suggestion_id": suggestion.id,
            }
        )

        await self.repo.create_audit_log(
            tenant_id=tenant_id,
            session_id=suggestion.session_id,
            event_type="tax_code_suggestion_overridden",
            event_description=f"Overrode tax code: {suggestion.suggested_tax_type} → {tax_type}",
            performed_by=user_id,
            event_metadata={
                "suggestion_id": str(suggestion.id),
                "suggested_tax_type": suggestion.suggested_tax_type,
                "override_tax_type": tax_type,
                "reason": reason,
            },
        )

        # Core audit trail for AI suggestion override (modified)
        try:
            from app.core.audit import AuditService

            audit = AuditService(self.session)
            await audit.log_event(
                event_type="ai.suggestion.modified",
                event_category="data",
                actor_type="user",
                actor_id=user_id,
                tenant_id=tenant_id,
                resource_type="tax_code_suggestion",
                resource_id=suggestion_id,
                action="update",
                outcome="success",
                old_values={"ai_suggested": suggestion.suggested_tax_type},
                new_values={"override": tax_type, "reason": reason},
            )
        except Exception:
            pass

        return suggestion

    async def dismiss_suggestion(
        self,
        suggestion_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        reason: str | None = None,
    ) -> TaxCodeSuggestion:
        """Dismiss — confirm the transaction should remain excluded."""
        suggestion = await self._get_pending_suggestion(suggestion_id, tenant_id)
        await self._get_editable_session(suggestion.session_id, tenant_id)

        suggestion.status = "dismissed"
        suggestion.resolved_by = user_id
        suggestion.resolved_at = datetime.now(UTC)
        suggestion.dismissal_reason = reason
        # Spec 056: also write reason to unified note_text field
        if reason:
            suggestion.note_text = reason
            suggestion.note_updated_by = user_id
            suggestion.note_updated_at = datetime.now(UTC)

        await self.repo.update_suggestion(suggestion)

        await self.repo.create_audit_log(
            tenant_id=tenant_id,
            session_id=suggestion.session_id,
            event_type="tax_code_transaction_dismissed",
            event_description=f"Dismissed transaction (confirmed exclusion): {suggestion.original_tax_type}",
            performed_by=user_id,
            event_metadata={
                "suggestion_id": str(suggestion.id),
                "original_tax_type": suggestion.original_tax_type,
                "reason": reason,
            },
        )

        return suggestion

    async def unpark_suggestion(
        self,
        suggestion_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
    ) -> TaxCodeSuggestion:
        """Unpark a dismissed suggestion — reset to pending (Uncoded)."""
        suggestion = await self.repo.get_suggestion(suggestion_id, tenant_id)
        if not suggestion:
            raise SuggestionNotFoundError(str(suggestion_id))
        if suggestion.status not in ("dismissed", "rejected"):
            raise SuggestionNotFoundError(str(suggestion_id))

        await self._get_editable_session(suggestion.session_id, tenant_id)

        suggestion.status = "pending"
        suggestion.resolved_by = None
        suggestion.resolved_at = None
        suggestion.dismissal_reason = None
        suggestion.auto_park_reason = None  # Spec 057: clear auto-park reason on manual unpark

        await self.repo.update_suggestion(suggestion)

        await self.repo.create_audit_log(
            tenant_id=tenant_id,
            session_id=suggestion.session_id,
            event_type="tax_code_suggestion_unparked",
            event_description=f"Unparked suggestion (back to manual): {suggestion.original_tax_type}",
            performed_by=user_id,
            event_metadata={
                "suggestion_id": str(suggestion.id),
            },
        )

        return suggestion

    async def save_note(
        self,
        suggestion_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        note_text: str,
        sync_to_xero: bool = False,
        connection_id: UUID | None = None,
    ) -> TaxCodeSuggestion:
        """Save or update a note on a suggestion (any status)."""
        suggestion = await self.repo.get_suggestion(suggestion_id, tenant_id)
        if not suggestion:
            raise SuggestionNotFoundError(str(suggestion_id))

        old_text = suggestion.note_text
        is_update = old_text is not None

        suggestion.note_text = note_text
        suggestion.note_updated_by = user_id
        suggestion.note_updated_at = datetime.now(UTC)

        await self.repo.update_suggestion(suggestion)

        event_type = "suggestion.note_updated" if is_update else "suggestion.note_created"
        await self.repo.create_audit_log(
            tenant_id=tenant_id,
            session_id=suggestion.session_id,
            event_type=event_type,
            event_description=f"{'Updated' if is_update else 'Created'} note on suggestion",
            performed_by=user_id,
            event_metadata={
                "suggestion_id": str(suggestion.id),
                "note_text": note_text,
                **({"old_text": old_text} if is_update else {}),
                "sync_to_xero": sync_to_xero,
            },
        )

        # Xero sync (Spec 056 - US3)
        logger.info(
            "save_note sync check: sync_to_xero=%s connection_id=%s", sync_to_xero, connection_id
        )
        if sync_to_xero and connection_id:
            await self._sync_note_to_xero(suggestion, tenant_id, user_id, connection_id)

        return suggestion

    async def _sync_note_to_xero(
        self,
        suggestion: TaxCodeSuggestion,
        tenant_id: UUID,
        user_id: UUID,
        connection_id: UUID | None = None,
    ) -> None:
        """Push suggestion note to Xero History & Notes API (fire-and-forget)."""
        logger.info("_sync_note_to_xero called: connection_id=%s", connection_id)
        try:
            from app.modules.integrations.xero.client import XeroClient
            from app.modules.integrations.xero.repository import XeroConnectionRepository
            from app.modules.integrations.xero.service import XeroConnectionService

            xero_repo = XeroConnectionRepository(self.session)
            connection = (
                await xero_repo.get_by_id(connection_id, tenant_id) if connection_id else None
            )
            if not connection:
                return

            from app.config import get_settings

            settings = get_settings()

            # Ensure token is fresh (refreshes if expired)
            xero_svc = XeroConnectionService(self.session, settings)
            access_token = await xero_svc.ensure_valid_token(connection_id)

            # Resolve local ID → Xero document ID
            from app.modules.integrations.xero.writeback_service import XeroWritebackService

            wb_service = XeroWritebackService(self.session)
            xero_doc_id = await wb_service._resolve_xero_document_id(
                suggestion.source_type, suggestion.source_id, tenant_id
            )

            note_for_xero = f"Clairo: {suggestion.note_text or ''}"
            logger.info(
                "Syncing note to Xero History & Notes: source_type=%s xero_id=%s note_length=%d preview=%s",
                suggestion.source_type,
                xero_doc_id,
                len(note_for_xero),
                note_for_xero[:100],
            )
            async with XeroClient(settings.xero) as client:
                result, _rl = await client.add_history_note(
                    access_token=access_token,
                    xero_tenant_id=connection.xero_tenant_id,
                    source_type=suggestion.source_type,
                    entity_id=xero_doc_id,
                    note_text=note_for_xero,
                )
            logger.info("Xero History & Notes sync result: %s", result)

            await self.repo.create_audit_log(
                tenant_id=tenant_id,
                session_id=suggestion.session_id,
                event_type="suggestion.note_xero_synced",
                event_description="Note synced to Xero History & Notes",
                performed_by=user_id,
                event_metadata={
                    "suggestion_id": str(suggestion.id),
                    "source_type": suggestion.source_type,
                    "source_id": str(suggestion.source_id),
                },
            )
        except Exception:
            logger.exception("Xero note sync failed")

    async def delete_note(
        self,
        suggestion_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
    ) -> TaxCodeSuggestion:
        """Remove a note from a suggestion."""
        suggestion = await self.repo.get_suggestion(suggestion_id, tenant_id)
        if not suggestion:
            raise SuggestionNotFoundError(str(suggestion_id))
        if not suggestion.note_text:
            raise SuggestionNotFoundError(str(suggestion_id))

        old_text = suggestion.note_text
        suggestion.note_text = None
        suggestion.note_updated_by = None
        suggestion.note_updated_at = None

        await self.repo.update_suggestion(suggestion)

        await self.repo.create_audit_log(
            tenant_id=tenant_id,
            session_id=suggestion.session_id,
            event_type="suggestion.note_deleted",
            event_description="Deleted note from suggestion",
            performed_by=user_id,
            event_metadata={
                "suggestion_id": str(suggestion.id),
                "old_text": old_text,
            },
        )

        return suggestion

    async def get_xero_bas_crosscheck(
        self,
        session_id: UUID,
        connection_id: UUID,
        tenant_id: UUID,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Fetch BAS report from Xero and compare with Clairo's calculation.

        Results are cached in Redis for 1 hour. Pass force_refresh=True to
        bypass the cache and fetch a fresh report from Xero.
        """
        from decimal import Decimal as D

        from app.core.cache import cache_get, cache_set

        cache_key = f"xero_bas_crosscheck:{connection_id}:{session_id}"

        if not force_refresh:
            cached = await cache_get(cache_key)
            if cached is not None:
                return cached

        # Get the BAS session and its calculation
        bas_session = await self.repo.get_session(session_id, tenant_id)
        if not bas_session:
            raise SuggestionNotFoundError(str(session_id))

        period_label = bas_session.period.display_name if bas_session.period else "Unknown"

        # Get Clairo figures from calculation
        clairo_figures = None
        if bas_session.calculation:
            calc = bas_session.calculation
            clairo_figures = {
                "label_1a_gst_on_sales": calc.field_1a_gst_on_sales,
                "label_1b_gst_on_purchases": calc.field_1b_gst_on_purchases,
                "net_gst": calc.gst_payable,
            }

        now = datetime.now(UTC)

        # Fetch from Xero
        try:
            from app.modules.integrations.xero.client import XeroClient
            from app.modules.integrations.xero.repository import XeroConnectionRepository

            xero_repo = XeroConnectionRepository(self.session)
            connection = await xero_repo.get_by_id(connection_id, tenant_id)
            if not connection or not connection.access_token:
                return {
                    "xero_report_found": None,
                    "xero_figures": None,
                    "clairo_figures": clairo_figures,
                    "differences": None,
                    "period_label": period_label,
                    "fetched_at": now,
                    "xero_error": "Xero connection not available",
                }

            from app.config import get_settings
            from app.modules.integrations.xero.service import XeroConnectionService

            settings = get_settings()
            xero_svc = XeroConnectionService(self.session, settings)
            access_token = await xero_svc.ensure_valid_token(connection_id)

            async with XeroClient(settings.xero) as client:
                data, _rate_limit = await client.get_bas_report(
                    access_token=access_token,
                    tenant_id=connection.xero_tenant_id,
                )

            # Parse BAS labels from report rows
            xero_1a = D("0")
            xero_1b = D("0")
            reports = data.get("Reports", [])
            if reports:
                for row in reports[0].get("Rows", []):
                    if row.get("RowType") != "Row":
                        continue
                    cells = row.get("Cells", [])
                    if len(cells) >= 2:
                        label = cells[0].get("Value", "")
                        amount_str = cells[1].get("Value", "0")
                        try:
                            amount = D(amount_str.replace(",", ""))
                        except (ValueError, ArithmeticError):
                            continue
                        if label == "1A":
                            xero_1a = amount
                        elif label == "1B":
                            xero_1b = amount

            xero_net = xero_1a - xero_1b
            has_data = reports and any(
                row.get("RowType") == "Row" for row in reports[0].get("Rows", [])
            )

            xero_figures = {
                "label_1a_gst_on_sales": xero_1a,
                "label_1b_gst_on_purchases": xero_1b,
                "net_gst": xero_net,
            }

            # Compute differences
            differences = None
            if clairo_figures and has_data:
                diffs = {}
                for key in ("label_1a_gst_on_sales", "label_1b_gst_on_purchases", "net_gst"):
                    x = xero_figures[key]
                    c = clairo_figures[key]
                    delta = x - c
                    if abs(delta) > 1:
                        diffs[key] = {
                            "xero": x,
                            "clairo": c,
                            "delta": delta,
                            "material": True,
                        }
                differences = diffs if diffs else None

            result = {
                "xero_report_found": has_data,
                "xero_figures": xero_figures if has_data else None,
                "clairo_figures": clairo_figures,
                "differences": differences,
                "period_label": period_label,
                "fetched_at": now,
            }
            await cache_set(cache_key, result, ttl=3600)
            return result

        except Exception as e:
            from app.modules.integrations.xero.client import XeroClientError

            error_msg = str(e)
            if "404" in error_msg or (isinstance(e, XeroClientError) and "404" in str(e)):
                # No BAS report exists in Xero for this org — not an error
                result = {
                    "xero_report_found": False,
                    "xero_figures": None,
                    "clairo_figures": clairo_figures,
                    "differences": None,
                    "period_label": period_label,
                    "fetched_at": now,
                }
                await cache_set(cache_key, result, ttl=3600)
                return result

            logger.warning("Xero BAS cross-check failed: %s", e)
            return {
                "xero_report_found": None,
                "xero_figures": None,
                "clairo_figures": clairo_figures,
                "differences": None,
                "period_label": period_label,
                "fetched_at": now,
                "xero_error": "Could not fetch BAS data from Xero",
            }

    async def bulk_approve(
        self,
        session_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        min_confidence: float | None = None,
        confidence_tier: str | None = None,
    ) -> dict[str, Any]:
        """Bulk approve pending suggestions matching criteria."""
        bas_session = await self._get_editable_session(session_id, tenant_id)

        suggestions = await self.repo.get_pending_suggestions_for_bulk(
            session_id, tenant_id, min_confidence, confidence_tier
        )

        now = datetime.now(UTC)
        approved_ids = []
        for s in suggestions:
            s.status = "approved"
            s.applied_tax_type = s.suggested_tax_type
            s.resolved_by = user_id
            s.resolved_at = now
            approved_ids.append(s.id)

        await self.session.flush()

        # Create TaxCodeOverride for each approved suggestion immediately so sync
        # works without requiring Apply & Recalculate first.
        connection_id = bas_session.period.connection_id
        for s in suggestions:
            if not s.applied_tax_type:
                continue
            source_type = str(
                s.source_type.value if hasattr(s.source_type, "value") else s.source_type
            )
            existing = await self.repo.get_active_override(
                connection_id, source_type, s.source_id, s.line_item_index, tenant_id
            )
            if not existing:
                await self.repo.create_override(
                    {
                        "tenant_id": tenant_id,
                        "connection_id": connection_id,
                        "source_type": s.source_type,
                        "source_id": s.source_id,
                        "line_item_index": s.line_item_index,
                        "original_tax_type": s.original_tax_type,
                        "override_tax_type": s.applied_tax_type,
                        "applied_by": user_id,
                        "applied_at": now,
                        "suggestion_id": s.id,
                    }
                )

        await self.repo.create_audit_log(
            tenant_id=tenant_id,
            session_id=session_id,
            event_type="tax_code_bulk_approved",
            event_description=f"Bulk approved {len(approved_ids)} tax code suggestions",
            performed_by=user_id,
            event_metadata={
                "count": len(approved_ids),
                "min_confidence": min_confidence,
                "confidence_tier": confidence_tier,
            },
        )

        return {
            "approved_count": len(approved_ids),
            "suggestion_ids": approved_ids,
        }

    # =========================================================================
    # Tier Suggestion Methods
    # =========================================================================

    def _suggest_from_account_default(
        self,
        account_code: str | None,
        accounts_map: dict[str, dict[str, Any]],
    ) -> tuple[str, Decimal, str] | None:
        """Tier 1: Suggest from XeroAccount.default_tax_type."""
        if not account_code or account_code not in accounts_map:
            return None

        account = accounts_map[account_code]
        default_type = (account.get("default_tax_type") or "").upper()

        if not default_type or default_type in EXCLUDED_TAX_TYPES:
            return None

        if (
            default_type not in TAX_TYPE_MAPPING
            or TAX_TYPE_MAPPING[default_type]["field"] == "excluded"
        ):
            return None

        account_name = account.get("account_name", account_code)
        return (
            default_type,
            Decimal("0.95"),
            f"Account {account_code} ({account_name}) has default tax type {default_type}",
        )

    async def _suggest_from_client_history(
        self,
        account_code: str | None,
        connection_id: UUID,
    ) -> tuple[str, Decimal, str] | None:
        """Tier 2: Suggest from same-client historical patterns."""
        if not account_code:
            return None

        return await self._query_historical_patterns(
            account_code,
            scope_column="connection_id",
            scope_value=str(connection_id),
            min_pct=0.90,
            confidence_range=(Decimal("0.85"), Decimal("0.95")),
            tier_label="prior transactions",
        )

    async def _suggest_from_tenant_history(
        self,
        account_code: str | None,
        tenant_id: UUID,
    ) -> tuple[str, Decimal, str] | None:
        """Tier 3: Suggest from cross-client patterns within tenant."""
        if not account_code:
            return None

        return await self._query_historical_patterns(
            account_code,
            scope_column="tenant_id",
            scope_value=str(tenant_id),
            min_pct=0.85,
            confidence_range=(Decimal("0.70"), Decimal("0.85")),
            tier_label="transactions across your practice",
        )

    async def _query_historical_patterns(
        self,
        account_code: str,
        scope_column: str,
        scope_value: str,
        min_pct: float,
        confidence_range: tuple[Decimal, Decimal],
        tier_label: str,
    ) -> tuple[str, Decimal, str] | None:
        """Query historical tax_type patterns for an account_code.

        Uses jsonb_array_elements to extract line item tax types from
        both invoices and bank transactions. scope_column is always
        'connection_id' or 'tenant_id' (internal, not user input).
        """
        # scope_column is always a known column name, never user input
        if scope_column not in ("connection_id", "tenant_id"):
            return None

        # Build two separate queries for invoices and bank transactions
        # using parameterized scope_value
        invoice_sql = text(
            f"SELECT upper(li.value ->> 'tax_type') AS tax_type "  # noqa: S608
            f"FROM xero_invoices i, jsonb_array_elements(i.line_items) li "
            f"WHERE i.line_items IS NOT NULL AND jsonb_typeof(i.line_items) = 'array' "
            f"AND li.value ->> 'account_code' = :account_code "
            f"AND li.value ->> 'tax_type' IS NOT NULL "
            f"AND upper(li.value ->> 'tax_type') NOT IN ('BASEXCLUDED','NONE','NONGST','') "
            f"AND i.{scope_column} = :scope_value"
        )
        txn_sql = text(
            f"SELECT upper(li.value ->> 'tax_type') AS tax_type "  # noqa: S608
            f"FROM xero_bank_transactions i, jsonb_array_elements(i.line_items) li "
            f"WHERE i.line_items IS NOT NULL AND jsonb_typeof(i.line_items) = 'array' "
            f"AND li.value ->> 'account_code' = :account_code "
            f"AND li.value ->> 'tax_type' IS NOT NULL "
            f"AND upper(li.value ->> 'tax_type') NOT IN ('BASEXCLUDED','NONE','NONGST','') "
            f"AND i.{scope_column} = :scope_value"
        )

        params = {"account_code": account_code, "scope_value": scope_value}

        # Collect all tax types
        inv_result = await self.session.execute(invoice_sql, params)
        txn_result = await self.session.execute(txn_sql, params)

        from collections import Counter

        counts: Counter[str] = Counter()
        for row in inv_result:
            counts[row.tax_type] += 1
        for row in txn_result:
            counts[row.tax_type] += 1

        total = sum(counts.values())
        if total == 0:
            return None

        # Get dominant type
        dominant_type, dominant_count = counts.most_common(1)[0]
        pct = dominant_count / total

        if pct < min_pct:
            return None

        if (
            dominant_type not in TAX_TYPE_MAPPING
            or TAX_TYPE_MAPPING[dominant_type]["field"] == "excluded"
        ):
            return None

        lo, hi = confidence_range
        confidence = lo + (hi - lo) * Decimal(str(pct))

        return (
            dominant_type,
            confidence,
            f"{int(pct * 100)}% of {tier_label} on account {account_code} used {dominant_type} ({dominant_count} of {total} matches)",
        )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _get_editable_session(self, session_id: UUID, tenant_id: UUID) -> BASSession:
        """Get a BAS session and verify it's editable."""
        from app.modules.bas.exceptions import SessionNotFoundError

        bas_session = await self.repo.get_session(session_id)
        if not bas_session:
            raise SessionNotFoundError(str(session_id))

        if not bas_session.is_editable:
            raise SessionNotEditableForSuggestionsError(str(session_id), bas_session.status)

        return bas_session

    async def _get_pending_suggestion(
        self, suggestion_id: UUID, tenant_id: UUID
    ) -> TaxCodeSuggestion:
        """Get a suggestion and verify it's actionable (pending or parked)."""
        suggestion = await self.repo.get_suggestion(suggestion_id, tenant_id)
        if not suggestion:
            raise SuggestionNotFoundError(str(suggestion_id))
        if suggestion.status not in ("pending", "dismissed", "rejected"):
            raise SuggestionAlreadyResolvedError(str(suggestion_id), str(suggestion.status))
        return suggestion

    async def _build_accounts_map(self, connection_id: UUID) -> dict[str, dict[str, Any]]:
        """Build in-memory lookup of account_code → account info."""
        from sqlalchemy import select as sa_select

        from app.modules.integrations.xero.models import XeroAccount

        result = await self.session.execute(
            sa_select(XeroAccount).where(
                XeroAccount.connection_id == connection_id,
                XeroAccount.is_active.is_(True),
            )
        )
        accounts = result.scalars().all()

        return {
            a.account_code: {
                "account_name": a.account_name,
                "default_tax_type": a.default_tax_type,
                "account_type": a.account_type,
                "account_class": str(a.account_class) if a.account_class else None,
            }
            for a in accounts
            if a.account_code
        }

    async def _enrich_excluded_items(
        self,
        excluded: list[dict[str, Any]],
        connection_id: UUID,
        _tenant_id: UUID,
    ) -> list[dict[str, Any]]:
        """Enrich excluded items with contact names and dates from source records."""
        from app.modules.integrations.xero.models import XeroBankTransaction, XeroInvoice

        # Collect source IDs by type
        invoice_ids = {UUID(i["source_id"]) for i in excluded if i["source_type"] == "invoice"}
        txn_ids = {UUID(i["source_id"]) for i in excluded if i["source_type"] == "bank_transaction"}

        # Fetch invoices
        invoice_map: dict[str, dict] = {}
        if invoice_ids:
            from sqlalchemy import select as sa_select

            result = await self.session.execute(
                sa_select(XeroInvoice).where(XeroInvoice.id.in_(invoice_ids))
            )
            for inv in result.scalars():
                invoice_map[str(inv.id)] = {
                    "contact_name": inv.contact_name if hasattr(inv, "contact_name") else None,
                    "transaction_date": inv.issue_date,
                }

        # Fetch bank transactions
        txn_map: dict[str, dict] = {}
        if txn_ids:
            from sqlalchemy import select as sa_select

            result = await self.session.execute(
                sa_select(XeroBankTransaction).where(XeroBankTransaction.id.in_(txn_ids))
            )
            for txn in result.scalars():
                txn_map[str(txn.id)] = {
                    "contact_name": txn.contact_name if hasattr(txn, "contact_name") else None,
                    "transaction_date": txn.transaction_date,
                }

        # Build accounts map for account names
        accounts_map = await self._build_accounts_map(connection_id)

        # Enrich
        for item in excluded:
            source_data = invoice_map.get(item["source_id"]) or txn_map.get(item["source_id"]) or {}
            item["contact_name"] = source_data.get("contact_name")
            item["transaction_date"] = source_data.get("transaction_date")

            acct_code = item.get("account_code")
            if acct_code and acct_code in accounts_map:
                item["account_name"] = accounts_map[acct_code]["account_name"]
            else:
                item["account_name"] = None

        return excluded

    async def _apply_reconciliation_to_suggestions(
        self,
        suggestions_data: list[dict[str, Any]],
        connection_id: UUID,
        tenant_id: UUID,
        session_id: UUID,
        start_date: Any,
        end_date: Any,
    ) -> None:
        """Populate is_reconciled on suggestion dicts AND create auto-parked suggestions
        for ALL unreconciled bank transactions in the period.

        Spec 057: Every unreconciled bank transaction in the period becomes a suggestion
        in the Parked section so accountants can approve/override/park them.
        Reconciled suggestions are tagged with is_reconciled=True.
        """
        from sqlalchemy import select

        from app.modules.integrations.xero.models import XeroBankTransaction

        # Fetch ALL bank transactions for the period
        result = await self.session.execute(
            select(XeroBankTransaction)
            .where(
                XeroBankTransaction.connection_id == connection_id,
                XeroBankTransaction.transaction_date >= start_date,
                XeroBankTransaction.transaction_date <= end_date,
                XeroBankTransaction.status == "AUTHORISED",
            )
            .where(
                # tenant_id filter for RLS — connection_id already scopes, but belt-and-suspenders
                XeroBankTransaction.tenant_id == tenant_id,
            )
        )
        all_txns = list(result.scalars().all())

        # Build reconciled lookup
        reconciled_map: dict[str, bool] = {str(t.id): bool(t.is_reconciled) for t in all_txns}

        # Tag existing suggestions with is_reconciled
        existing_source_ids: set[str] = set()
        for s in suggestions_data:
            if s.get("source_type") != "bank_transaction":
                continue
            sid = str(s["source_id"])
            existing_source_ids.add(sid)
            is_reconciled = reconciled_map.get(sid, False)
            s["is_reconciled"] = is_reconciled
            if not is_reconciled:
                s["status"] = "dismissed"
                s["auto_park_reason"] = "unreconciled_in_xero"

        # Create auto-parked suggestions for unreconciled bank transactions
        # that are NOT already in the excluded items list.
        for txn in all_txns:
            tid = str(txn.id)
            if tid in existing_source_ids:
                continue
            if txn.is_reconciled:
                continue  # Reconciled without tax code issues — no suggestion needed

            # Build suggestion for this unreconciled transaction
            # Extract description and tax type from first line item
            description = None
            tax_type = "UNKNOWN"
            line_amount = txn.total_amount
            tax_amount = txn.tax_amount
            account_code = None
            if txn.line_items and isinstance(txn.line_items, list):
                first_li = txn.line_items[0]
                description = first_li.get("description") or first_li.get("Description")
                tax_type = first_li.get("tax_type") or first_li.get("TaxType") or "UNKNOWN"
                account_code = first_li.get("account_code") or first_li.get("AccountCode")

            contact_name = None
            if txn.client:
                contact_name = getattr(txn.client, "name", None)

            line_item_id = None
            if txn.line_items and isinstance(txn.line_items, list):
                line_item_id = txn.line_items[0].get("line_item_id") or txn.line_items[0].get(
                    "LineItemID"
                )

            suggestions_data.append(
                {
                    "tenant_id": tenant_id,
                    "session_id": session_id,
                    "source_type": "bank_transaction",
                    "source_id": txn.id,
                    "line_item_index": 0,
                    "line_item_id": line_item_id,
                    "original_tax_type": tax_type,
                    "suggested_tax_type": None,
                    "confidence_score": None,
                    "confidence_tier": None,
                    "suggestion_basis": None,
                    "account_code": account_code,
                    "account_name": None,
                    "description": description,
                    "line_amount": line_amount,
                    "tax_amount": tax_amount,
                    "contact_name": contact_name,
                    "transaction_date": txn.transaction_date,
                    "status": "dismissed",
                    "auto_park_reason": "unreconciled_in_xero",
                    "is_reconciled": False,
                }
            )

    def _build_suggestion_record(
        self,
        item: dict[str, Any],
        session_id: UUID,
        tenant_id: UUID,
    ) -> dict[str, Any]:
        """Build a TaxCodeSuggestion dict from an excluded item."""
        return {
            "tenant_id": tenant_id,
            "session_id": session_id,
            "source_type": item["source_type"],
            "source_id": item["source_id"],
            "line_item_index": item["line_item_index"],
            "line_item_id": item.get("line_item_id"),
            "original_tax_type": item["tax_type"],
            "suggested_tax_type": None,
            "confidence_score": None,
            "confidence_tier": None,
            "suggestion_basis": None,
            "account_code": item.get("account_code"),
            "account_name": item.get("account_name"),
            "description": item.get("description"),
            "line_amount": item.get("line_amount"),
            "tax_amount": item.get("tax_amount"),
            "contact_name": item.get("contact_name"),
            "transaction_date": item.get("transaction_date"),
            "status": "pending",
            "is_reconciled": None,
            "auto_park_reason": None,
        }

    # =========================================================================
    # Conflict Detection (US5)
    # =========================================================================

    async def detect_conflicts(
        self,
        connection_id: UUID,
        tenant_id: UUID,
    ) -> list[dict[str, Any]]:
        """Detect re-sync conflicts for active overrides.

        Compares override's original_tax_type with current Xero line item tax_type.
        """
        from app.modules.integrations.xero.models import XeroBankTransaction, XeroInvoice

        active_overrides = await self.repo.get_active_overrides(connection_id, tenant_id)
        if not active_overrides:
            return []

        conflicts = []
        for override in active_overrides:
            source_type = str(
                override.source_type.value
                if hasattr(override.source_type, "value")
                else override.source_type
            )

            # Load source entity
            current_tax_type = None
            if source_type == "invoice":
                from sqlalchemy import select as sa_select

                result = await self.session.execute(
                    sa_select(XeroInvoice).where(XeroInvoice.id == override.source_id)
                )
                entity = result.scalar_one_or_none()
                if (
                    entity
                    and entity.line_items
                    and len(entity.line_items) > override.line_item_index
                ):
                    item = entity.line_items[override.line_item_index]
                    current_tax_type = (item.get("tax_type") or item.get("TaxType", "")).upper()

            elif source_type == "bank_transaction":
                from sqlalchemy import select as sa_select

                result = await self.session.execute(
                    sa_select(XeroBankTransaction).where(
                        XeroBankTransaction.id == override.source_id
                    )
                )
                entity = result.scalar_one_or_none()
                if (
                    entity
                    and entity.line_items
                    and len(entity.line_items) > override.line_item_index
                ):
                    item = entity.line_items[override.line_item_index]
                    current_tax_type = (item.get("tax_type") or item.get("TaxType", "")).upper()

            if current_tax_type is None:
                continue

            original = override.original_tax_type.upper()
            applied = override.override_tax_type.upper()

            if current_tax_type == original:
                # Xero unchanged — override still valid
                continue
            elif current_tax_type == applied:
                # Xero now matches our override — clear it
                override.is_active = False
                await self.session.flush()
            else:
                # Xero changed to something different — conflict
                if not override.conflict_detected:
                    override.conflict_detected = True
                    override.xero_new_tax_type = current_tax_type
                    await self.session.flush()

                    await self.repo.create_audit_log(
                        tenant_id=tenant_id,
                        session_id=override.suggestion.session_id if override.suggestion else None,
                        event_type="tax_code_conflict_detected",
                        event_description=(
                            f"Re-sync conflict: override {applied} vs Xero {current_tax_type}"
                        ),
                        is_system_action=True,
                        event_metadata={
                            "override_id": str(override.id),
                            "override_tax_type": applied,
                            "xero_new_tax_type": current_tax_type,
                            "original_tax_type": original,
                        },
                    )

                conflicts.append(
                    {
                        "override_id": str(override.id),
                        "source_type": source_type,
                        "source_id": str(override.source_id),
                        "line_item_index": override.line_item_index,
                        "override_tax_type": applied,
                        "xero_new_tax_type": current_tax_type,
                        "description": override.suggestion.description
                        if override.suggestion
                        else None,
                        "line_amount": (
                            float(override.suggestion.line_amount)
                            if override.suggestion and override.suggestion.line_amount
                            else None
                        ),
                        "account_code": (
                            override.suggestion.account_code if override.suggestion else None
                        ),
                        "detected_at": override.updated_at.isoformat()
                        if override.updated_at
                        else None,
                    }
                )

        return conflicts

    async def resolve_conflict(
        self,
        override_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        resolution: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Resolve a re-sync conflict."""
        from app.modules.bas.exceptions import OverrideNotFoundError

        override = await self.repo.get_override(override_id, tenant_id)
        if not override:
            raise OverrideNotFoundError(str(override_id))

        if resolution == "keep_override":
            override.conflict_detected = False
            override.xero_new_tax_type = None
            override.conflict_resolved_at = datetime.now(UTC)
            applied_tax_type = override.override_tax_type
        elif resolution == "accept_xero":
            override.is_active = False
            override.conflict_resolved_at = datetime.now(UTC)
            applied_tax_type = override.xero_new_tax_type or override.original_tax_type
        else:
            raise ValueError(f"Invalid resolution: {resolution}")

        await self.session.flush()

        await self.repo.create_audit_log(
            tenant_id=tenant_id,
            session_id=override.suggestion.session_id if override.suggestion else None,
            event_type="tax_code_conflict_detected",
            event_description=f"Conflict resolved: {resolution}",
            performed_by=user_id,
            event_metadata={
                "override_id": str(override.id),
                "resolution": resolution,
                "applied_tax_type": applied_tax_type,
                "reason": reason,
            },
        )

        return {
            "override_id": str(override.id),
            "resolution": resolution,
            "applied_tax_type": applied_tax_type,
        }

    async def get_conflicts(
        self,
        connection_id: UUID,
        tenant_id: UUID,
    ) -> dict[str, Any]:
        """Get active conflicts for a connection."""
        overrides = await self.repo.get_active_overrides(connection_id, tenant_id)
        conflicts = [
            {
                "override_id": str(o.id),
                "source_type": str(
                    o.source_type.value if hasattr(o.source_type, "value") else o.source_type
                ),
                "source_id": str(o.source_id),
                "line_item_index": o.line_item_index,
                "override_tax_type": o.override_tax_type,
                "xero_new_tax_type": o.xero_new_tax_type,
                "description": o.suggestion.description if o.suggestion else None,
                "line_amount": float(o.suggestion.line_amount)
                if o.suggestion and o.suggestion.line_amount
                else None,
                "account_code": o.suggestion.account_code if o.suggestion else None,
                "detected_at": o.updated_at.isoformat() if o.updated_at else None,
            }
            for o in overrides
            if o.conflict_detected
        ]
        return {"conflicts": conflicts, "total": len(conflicts)}

    # =========================================================================
    # LLM Classification (US6)
    # =========================================================================

    async def suggest_from_llm(
        self,
        items: list[dict[str, Any]],
        accounts_map: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Tier 4: Classify transactions using Claude.

        Batches items into a single LLM call and returns suggestions
        with confidence in the 0.60-0.80 range.
        """
        if not items:
            return []

        try:
            import anthropic
        except ImportError:
            logger.warning("anthropic SDK not available, skipping LLM classification")
            return [
                {
                    "suggested_tax_type": None,
                    "confidence_score": None,
                    "suggestion_basis": "LLM classification unavailable",
                }
                for _ in items
            ]

        # Build context for each item
        item_descriptions = []
        for i, item in enumerate(items):
            acct = accounts_map.get(item.get("account_code", ""), {})
            item_descriptions.append(
                f"Item {i + 1}: description='{item.get('description', 'N/A')}', "
                f"amount=${item.get('line_amount', 0)}, "
                f"account_code={item.get('account_code', 'N/A')}, "
                f"account_name={acct.get('account_name', 'N/A')}, "
                f"account_type={acct.get('account_type', 'N/A')}"
            )

        valid_types = ", ".join(sorted(VALID_TAX_TYPES))
        prompt = f"""You are an Australian tax accountant classifying transactions for BAS (Business Activity Statement) preparation.

For each transaction below, determine the most appropriate Xero tax type from this list:
{valid_types}

Context:
- OUTPUT = GST-inclusive sales (10% GST)
- INPUT = GST-inclusive purchases (10% GST claimable)
- CAPEXINPUT = Capital equipment purchases (GST claimable)
- EXEMPTOUTPUT/EXEMPTINCOME = GST-free sales
- EXEMPTEXPENSES = GST-free purchases
- EXEMPTEXPORT = Export sales (GST-free)

Transactions to classify:
{chr(10).join(item_descriptions)}

Respond with a JSON array. For each item:
{{"item": 1, "tax_type": "INPUT", "confidence": 0.8, "reasoning": "Office supplies are typically GST-inclusive purchases"}}

If you cannot classify with reasonable confidence, set tax_type to null and confidence to 0."""

        try:
            client = anthropic.Anthropic()
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )

            # Parse response
            import json

            response_text = response.content[0].text
            # Extract JSON array from response
            start = response_text.find("[")
            end = response_text.rfind("]") + 1
            if start >= 0 and end > start:
                classifications = json.loads(response_text[start:end])
            else:
                classifications = []

            results = []
            for i, _item in enumerate(items):
                classification = next((c for c in classifications if c.get("item") == i + 1), {})
                tax_type = classification.get("tax_type")
                raw_confidence = classification.get("confidence", 0)
                reasoning = classification.get("reasoning", "")

                # Map to 0.60-0.80 range
                if tax_type and raw_confidence > 0.5:
                    mapped_confidence = Decimal("0.60") + Decimal(
                        str(min(raw_confidence, 1.0))
                    ) * Decimal("0.20")
                    results.append(
                        {
                            "suggested_tax_type": tax_type.upper()
                            if tax_type in VALID_TAX_TYPES or tax_type.upper() in VALID_TAX_TYPES
                            else None,
                            "confidence_score": mapped_confidence,
                            "confidence_tier": ConfidenceTier.LLM_CLASSIFICATION,
                            "suggestion_basis": f"AI classification: {reasoning}",
                        }
                    )
                else:
                    results.append(
                        {
                            "suggested_tax_type": None,
                            "confidence_score": None,
                            "confidence_tier": None,
                            "suggestion_basis": "Could not classify with sufficient confidence",
                        }
                    )

            # Audit log AI classification
            try:
                from app.core.audit import AuditService

                audit = AuditService(self.session)
                await audit.log_event(
                    event_type="ai.bas.classification",
                    event_category="data",
                    action="create",
                    outcome="success",
                    metadata={
                        "model": "claude-sonnet-4-20250514",
                        "items_count": len(items),
                        "classified_count": sum(1 for r in results if r["suggested_tax_type"]),
                        "tier": "llm_classification",
                    },
                )
            except Exception:
                pass

            return results

        except Exception as e:
            logger.warning(f"LLM classification failed: {e}")
            return [
                {
                    "suggested_tax_type": None,
                    "confidence_score": None,
                    "confidence_tier": None,
                    "suggestion_basis": f"LLM classification failed: {e!s}",
                }
                for _ in items
            ]

    # =========================================================================
    # Client Classification LLM Mapping (Spec 047)
    # =========================================================================

    async def suggest_from_client_input(
        self,
        items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Map client-classified transactions to BAS tax codes via LLM.

        Enhanced prompt includes the client's category selection and/or
        free-text description for more accurate mapping.
        """
        if not items:
            return []

        try:
            import anthropic
        except ImportError:
            logger.warning("anthropic SDK not available for client classification mapping")
            return [
                {"suggested_tax_type": item.get("typical_tax_type"), "confidence": 0.6}
                for item in items
            ]

        prompt_lines = [
            "You are an experienced Australian BAS tax accountant.",
            "The business owner has classified their own transactions. Map each to the correct Xero tax type.",
            "",
            "Valid Xero tax types: OUTPUT (GST on Income), INPUT (GST on Expenses), INPUTTAXED (Input Taxed),",
            "EXEMPTOUTPUT (GST Free Income), EXEMPTEXPENSES (GST Free Expenses), BASEXCLUDED (BAS Excluded),",
            "GSTONIMPORTS (GST on Imports), OUTPUT2 (GST on Income 2), INPUT2 (GST on Expenses 2).",
            "",
            'For each transaction, return a JSON array with {"tax_type": "...", "confidence": 0.0-1.0}.',
            "",
            "Transactions:",
        ]

        for i, item in enumerate(items):
            client_info = ""
            if item.get("client_category"):
                client_info += f"Client classified as: {item['client_category']}. "
            if item.get("client_description"):
                client_info += f'Client says: "{item["client_description"]}". '
            if item.get("typical_tax_type"):
                client_info += f"Category typically maps to: {item['typical_tax_type']}. "

            prompt_lines.append(
                f"{i + 1}. Description: {item.get('description', 'N/A')}, "
                f"Amount: ${item.get('line_amount', '0')}, "
                f"Account: {item.get('account_code', 'N/A')}. "
                f"{client_info}"
            )

        prompt = "\n".join(prompt_lines)

        try:
            client = anthropic.Anthropic()
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )

            text = response.content[0].text
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                import json

                results = json.loads(text[start:end])
                return [
                    {
                        "suggested_tax_type": r.get("tax_type"),
                        "confidence": r.get("confidence", 0.7),
                    }
                    for r in results
                ]
        except Exception:
            logger.warning("LLM client classification mapping failed", exc_info=True)

        # Fallback
        return [
            {"suggested_tax_type": item.get("typical_tax_type"), "confidence": 0.6}
            for item in items
        ]

    # =========================================================================
    # Split management (Spec 049 line-items extension)
    # =========================================================================

    async def _validate_split_balance(
        self,
        source_id: UUID,
        tenant_id: UUID,
        db: AsyncSession,
    ) -> None:
        """Raise SplitAmountMismatchError if new-split line_amounts don't sum to transaction total.

        Only sums is_new_split=True overrides — edit/delete overrides on existing
        line items don't change the transaction total.
        """
        repo = BASRepository(db)
        total = await repo.get_bank_transaction_total(source_id, tenant_id)
        if total is None:
            return  # transaction not found — let the caller handle
        overrides = await repo.get_overrides_for_transaction(source_id, tenant_id)
        split_total = sum(
            (o.line_amount for o in overrides if o.line_amount is not None and o.is_new_split),
            Decimal("0"),
        )
        if split_total != Decimal("0") and split_total != total:
            raise SplitAmountMismatchError(expected=total, actual=split_total)

    async def create_split_override(
        self,
        source_id: UUID,
        connection_id: UUID,
        line_item_index: int,
        override_tax_type: str,
        applied_by: UUID,
        tenant_id: UUID,
        db: AsyncSession,
        line_amount: Decimal | None = None,
        line_description: str | None = None,
        line_account_code: str | None = None,
        is_new_split: bool = True,
        is_deleted: bool = False,
    ) -> TaxCodeOverride:
        """Create or upsert a line item override on a bank transaction.

        Handles three cases:
        - is_new_split=True: append a new line item (line_amount required).
        - is_new_split=False, is_deleted=False: edit an existing original line item.
        - is_new_split=False, is_deleted=True: mark an original for deletion from payload.

        Upserts if an active override already exists at the same line_item_index
        (e.g. from the suggestion-approval workflow) to avoid unique constraint violations.
        """
        if override_tax_type not in VALID_TAX_TYPES:
            raise InvalidTaxTypeError(override_tax_type)

        repo = BASRepository(db)

        # Upsert: check for an existing active override at this index
        existing = await repo.get_active_override(
            connection_id, "bank_transaction", source_id, line_item_index, tenant_id
        )
        if existing is not None:
            existing.override_tax_type = override_tax_type
            existing.is_new_split = is_new_split
            existing.is_deleted = is_deleted
            existing.writeback_status = "pending_sync"
            if line_amount is not None:
                existing.line_amount = line_amount
            if line_description is not None:
                existing.line_description = line_description
            if line_account_code is not None:
                existing.line_account_code = line_account_code
            await db.flush()
            return existing

        override = await repo.create_override(
            {
                "tenant_id": tenant_id,
                "connection_id": connection_id,
                "source_type": "bank_transaction",
                "source_id": source_id,
                "line_item_index": line_item_index,
                "original_tax_type": override_tax_type,
                "override_tax_type": override_tax_type,
                "applied_by": applied_by,
                "applied_at": datetime.now(UTC),
                "suggestion_id": None,
                "is_new_split": is_new_split,
                "is_deleted": is_deleted,
                "line_amount": line_amount,
                "line_description": line_description,
                "line_account_code": line_account_code,
                "writeback_status": "pending_sync",
            }
        )
        return override

    async def update_split_override(
        self,
        override_id: UUID,
        tenant_id: UUID,
        db: AsyncSession,
        override_tax_type: str | None = None,
        line_amount: Decimal | None = None,
        line_description: str | None = None,
        line_account_code: str | None = None,
        is_deleted: bool | None = None,
    ) -> TaxCodeOverride:
        """Update fields on an existing split or tax code override."""
        repo = BASRepository(db)
        override = await repo.get_override(override_id, tenant_id)
        if override is None:
            raise SplitOverrideNotFoundError(override_id)
        if override_tax_type is not None:
            if override_tax_type not in VALID_TAX_TYPES:
                raise InvalidTaxTypeError(override_tax_type)
            override.override_tax_type = override_tax_type
        if line_amount is not None:
            override.line_amount = line_amount
        if line_description is not None:
            override.line_description = line_description
        if line_account_code is not None:
            override.line_account_code = line_account_code
        if is_deleted is not None:
            override.is_deleted = is_deleted
        await db.flush()
        return override

    async def delete_split_override(
        self,
        override_id: UUID,
        tenant_id: UUID,
        db: AsyncSession,
    ) -> None:
        """Deactivate a split override and re-validate balance."""
        repo = BASRepository(db)
        override = await repo.get_override(override_id, tenant_id)
        if override is None:
            raise SplitOverrideNotFoundError(override_id)
        source_id = override.source_id
        override.is_active = False
        await db.flush()
