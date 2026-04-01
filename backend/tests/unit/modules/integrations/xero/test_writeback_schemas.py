"""Unit tests for Xero write-back schemas and enums.

Spec 049: Xero Tax Code Write-Back.
Tests cover:
- XeroWritebackSkipReason enum completeness
- WritebackItemResponse round-trip (with/without transaction_context)
- WritebackTransactionContext accepts all-null fields
"""

from datetime import datetime, timezone
from uuid import uuid4

from app.modules.integrations.xero.writeback_models import (
    XeroWritebackItemStatus,
    XeroWritebackSkipReason,
)
from app.modules.integrations.xero.writeback_schemas import (
    WritebackItemResponse,
    WritebackTransactionContext,
)


class TestXeroWritebackSkipReason:
    """Tests for the XeroWritebackSkipReason enum."""

    def test_has_all_eight_values(self) -> None:
        values = {r.value for r in XeroWritebackSkipReason}
        assert values == {
            "voided",
            "deleted",
            "period_locked",
            "reconciled",
            "authorised_locked",
            "conflict_changed",
            "credit_note_applied",
            "invalid_tax_type",
        }

    def test_voided(self) -> None:
        assert XeroWritebackSkipReason.VOIDED.value == "voided"

    def test_deleted(self) -> None:
        assert XeroWritebackSkipReason.DELETED.value == "deleted"

    def test_period_locked(self) -> None:
        assert XeroWritebackSkipReason.PERIOD_LOCKED.value == "period_locked"

    def test_reconciled(self) -> None:
        assert XeroWritebackSkipReason.RECONCILED.value == "reconciled"

    def test_authorised_locked(self) -> None:
        assert XeroWritebackSkipReason.AUTHORISED_LOCKED.value == "authorised_locked"

    def test_conflict_changed(self) -> None:
        assert XeroWritebackSkipReason.CONFLICT_CHANGED.value == "conflict_changed"

    def test_credit_note_applied(self) -> None:
        assert XeroWritebackSkipReason.CREDIT_NOTE_APPLIED.value == "credit_note_applied"

    def test_invalid_tax_type(self) -> None:
        assert XeroWritebackSkipReason.INVALID_TAX_TYPE.value == "invalid_tax_type"

    def test_str_returns_value(self) -> None:
        assert str(XeroWritebackSkipReason.PERIOD_LOCKED) == "period_locked"


class TestWritebackTransactionContext:
    """Tests for WritebackTransactionContext schema."""

    def test_all_null_fields(self) -> None:
        ctx = WritebackTransactionContext()
        assert ctx.contact_name is None
        assert ctx.transaction_date is None
        assert ctx.description is None
        assert ctx.total_line_amount is None

    def test_populated_fields(self) -> None:
        from datetime import date

        ctx = WritebackTransactionContext(
            contact_name="Acme Corp",
            transaction_date=date(2025, 3, 15),
            description="Office supplies",
            total_line_amount=550.00,
        )
        assert ctx.contact_name == "Acme Corp"
        assert ctx.total_line_amount == 550.00


class TestWritebackItemResponse:
    """Tests for WritebackItemResponse schema."""

    def _minimal_data(self) -> dict:
        now = datetime.now(timezone.utc)
        return {
            "id": uuid4(),
            "job_id": uuid4(),
            "source_type": "invoice",
            "xero_document_id": str(uuid4()),
            "local_document_id": uuid4(),
            "override_ids": [],
            "line_item_indexes": [],
            "before_tax_types": {},
            "after_tax_types": {},
            "status": XeroWritebackItemStatus.SUCCESS,
            "created_at": now,
        }

    def test_round_trip_without_context(self) -> None:
        data = self._minimal_data()
        item = WritebackItemResponse(**data)
        assert item.transaction_context is None
        assert item.skip_reason is None
        assert item.error_detail is None

    def test_round_trip_with_context(self) -> None:
        from datetime import date

        data = self._minimal_data()
        data["transaction_context"] = WritebackTransactionContext(
            contact_name="Telstra",
            transaction_date=date(2025, 6, 1),
            description="Phone bill",
            total_line_amount=120.00,
        )
        item = WritebackItemResponse(**data)
        assert item.transaction_context is not None
        assert item.transaction_context.contact_name == "Telstra"
        assert item.transaction_context.total_line_amount == 120.00

    def test_with_skip_reason(self) -> None:
        data = self._minimal_data()
        data["status"] = XeroWritebackItemStatus.SKIPPED
        data["skip_reason"] = XeroWritebackSkipReason.PERIOD_LOCKED
        item = WritebackItemResponse(**data)
        assert item.skip_reason == XeroWritebackSkipReason.PERIOD_LOCKED

    def test_with_xero_http_status(self) -> None:
        data = self._minimal_data()
        data["xero_http_status"] = 400
        item = WritebackItemResponse(**data)
        assert item.xero_http_status == 400
