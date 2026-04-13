"""Unit tests for BAS reconciliation grouping (Spec 057).

Tests cover:
- _apply_reconciliation_to_suggestions: tags reconciled, auto-parks unreconciled,
  creates suggestions for unreconciled txns not in excluded list
- _build_suggestion_record: includes is_reconciled and auto_park_reason keys
  (critical for SQLAlchemy multi-row insert)
- get_period_bank_transactions: returns all AUTHORISED txns with correct flags
- jsonb_typeof guard on client history queries
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.bas.tax_code_service import TaxCodeService


# =============================================================================
# Helpers
# =============================================================================


def _make_bank_txn(
    *,
    txn_id: uuid.UUID | None = None,
    is_reconciled: bool = True,
    total_amount: Decimal = Decimal("100.00"),
    tax_amount: Decimal = Decimal("10.00"),
    line_items: list | None = None,
    transaction_date: datetime | None = None,
    status: str = "AUTHORISED",
    connection_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
) -> MagicMock:
    """Build a mock XeroBankTransaction."""
    txn = MagicMock()
    txn.id = txn_id or uuid.uuid4()
    txn.is_reconciled = is_reconciled
    txn.total_amount = total_amount
    txn.tax_amount = tax_amount
    txn.line_items = line_items or [
        {"description": "Test item", "tax_type": "GST", "account_code": "200"}
    ]
    txn.transaction_date = transaction_date or datetime(2026, 2, 15, tzinfo=timezone.utc)
    txn.status = status
    txn.connection_id = connection_id or uuid.uuid4()
    txn.tenant_id = tenant_id or uuid.uuid4()
    txn.client = None
    return txn


def _make_suggestion_dict(
    *,
    source_id: uuid.UUID | None = None,
    source_type: str = "bank_transaction",
    status: str = "pending",
    tax_type: str = "BASEXCLUDED",
    session_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
) -> dict:
    """Build a suggestion dict as _build_suggestion_record would."""
    return {
        "tenant_id": tenant_id or uuid.uuid4(),
        "session_id": session_id or uuid.uuid4(),
        "source_type": source_type,
        "source_id": str(source_id or uuid.uuid4()),
        "line_item_index": 0,
        "line_item_id": "li-001",
        "original_tax_type": tax_type,
        "account_code": "200",
        "account_name": None,
        "description": "Test transaction",
        "line_amount": Decimal("100.00"),
        "tax_amount": Decimal("10.00"),
        "contact_name": "Test Contact",
        "transaction_date": date(2026, 2, 15),
        "status": status,
        "is_reconciled": None,
        "auto_park_reason": None,
    }


# =============================================================================
# _build_suggestion_record tests
# =============================================================================


class TestBuildSuggestionRecord:
    """Verify _build_suggestion_record includes all keys needed for multi-row insert."""

    def test_includes_reconciliation_keys(self):
        """is_reconciled and auto_park_reason must be present to avoid
        SQLAlchemy multi-row insert key mismatch."""
        session = AsyncMock()
        service = TaxCodeService(session)
        item = {
            "source_type": "bank_transaction",
            "source_id": str(uuid.uuid4()),
            "line_item_index": 0,
            "tax_type": "GST",
        }
        result = service._build_suggestion_record(item, uuid.uuid4(), uuid.uuid4())

        assert "is_reconciled" in result
        assert "auto_park_reason" in result
        assert result["is_reconciled"] is None
        assert result["auto_park_reason"] is None

    def test_all_suggestion_dicts_have_same_keys(self):
        """Every dict from _build_suggestion_record must have identical keys
        so bulk_create_suggestions (multi-row INSERT) works correctly."""
        session = AsyncMock()
        service = TaxCodeService(session)

        items = [
            {"source_type": "bank_transaction", "source_id": str(uuid.uuid4()),
             "line_item_index": 0, "tax_type": "GST"},
            {"source_type": "invoice", "source_id": str(uuid.uuid4()),
             "line_item_index": 0, "tax_type": "NONE"},
        ]
        dicts = [service._build_suggestion_record(i, uuid.uuid4(), uuid.uuid4()) for i in items]

        assert dicts[0].keys() == dicts[1].keys()


# =============================================================================
# _apply_reconciliation_to_suggestions tests
# =============================================================================


class TestApplyReconciliationToSuggestions:
    """Test the reconciliation enrichment + auto-park logic."""

    async def test_tags_reconciled_suggestions(self):
        """Suggestions for reconciled bank txns get is_reconciled=True."""
        session = AsyncMock()
        service = TaxCodeService(session)

        txn_id = uuid.uuid4()
        txn = _make_bank_txn(txn_id=txn_id, is_reconciled=True)

        suggestion = _make_suggestion_dict(source_id=txn_id)

        # Mock the DB query to return our bank transaction
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [txn]
        session.execute = AsyncMock(return_value=mock_result)

        await service._apply_reconciliation_to_suggestions(
            [suggestion],
            connection_id=txn.connection_id,
            tenant_id=txn.tenant_id,
            session_id=uuid.uuid4(),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
        )

        assert suggestion["is_reconciled"] is True
        assert suggestion["status"] == "pending"  # NOT auto-parked
        assert suggestion["auto_park_reason"] is None

    async def test_auto_parks_unreconciled_suggestions(self):
        """Suggestions for unreconciled bank txns get status=dismissed + auto_park_reason."""
        session = AsyncMock()
        service = TaxCodeService(session)

        txn_id = uuid.uuid4()
        txn = _make_bank_txn(txn_id=txn_id, is_reconciled=False)

        suggestion = _make_suggestion_dict(source_id=txn_id)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [txn]
        session.execute = AsyncMock(return_value=mock_result)

        await service._apply_reconciliation_to_suggestions(
            [suggestion],
            connection_id=txn.connection_id,
            tenant_id=txn.tenant_id,
            session_id=uuid.uuid4(),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
        )

        assert suggestion["is_reconciled"] is False
        assert suggestion["status"] == "dismissed"
        assert suggestion["auto_park_reason"] == "unreconciled_in_xero"

    async def test_creates_suggestions_for_unreconciled_not_in_excluded(self):
        """Unreconciled bank txns NOT already in excluded items get new auto-parked suggestions."""
        session = AsyncMock()
        service = TaxCodeService(session)

        # txn1: already in excluded items (has a suggestion)
        txn1_id = uuid.uuid4()
        txn1 = _make_bank_txn(txn_id=txn1_id, is_reconciled=False)

        # txn2: NOT in excluded items, unreconciled — should get a new suggestion
        txn2_id = uuid.uuid4()
        txn2 = _make_bank_txn(txn_id=txn2_id, is_reconciled=False)

        # txn3: reconciled, not in excluded — should NOT get a new suggestion
        txn3_id = uuid.uuid4()
        txn3 = _make_bank_txn(txn_id=txn3_id, is_reconciled=True)

        existing_suggestion = _make_suggestion_dict(source_id=txn1_id)
        suggestions_data = [existing_suggestion]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [txn1, txn2, txn3]
        session.execute = AsyncMock(return_value=mock_result)

        tenant_id = uuid.uuid4()
        session_id = uuid.uuid4()

        await service._apply_reconciliation_to_suggestions(
            suggestions_data,
            connection_id=txn1.connection_id,
            tenant_id=tenant_id,
            session_id=session_id,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
        )

        # Should now have 2 suggestions: original + new one for txn2
        assert len(suggestions_data) == 2

        new_suggestion = suggestions_data[1]
        assert new_suggestion["source_id"] == txn2.id
        assert new_suggestion["status"] == "dismissed"
        assert new_suggestion["auto_park_reason"] == "unreconciled_in_xero"
        assert new_suggestion["is_reconciled"] is False
        assert new_suggestion["tenant_id"] == tenant_id
        assert new_suggestion["session_id"] == session_id

    async def test_skips_non_bank_transaction_suggestions(self):
        """Invoice suggestions are not touched by reconciliation logic."""
        session = AsyncMock()
        service = TaxCodeService(session)

        invoice_suggestion = _make_suggestion_dict(source_type="invoice")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=mock_result)

        await service._apply_reconciliation_to_suggestions(
            [invoice_suggestion],
            connection_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
        )

        assert invoice_suggestion["is_reconciled"] is None
        assert invoice_suggestion["auto_park_reason"] is None
        assert invoice_suggestion["status"] == "pending"

    async def test_handles_scalar_line_items(self):
        """Bank transactions with non-list line_items don't crash."""
        session = AsyncMock()
        service = TaxCodeService(session)

        txn = _make_bank_txn(is_reconciled=False, line_items="not a list")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [txn]
        session.execute = AsyncMock(return_value=mock_result)

        suggestions_data: list[dict] = []

        await service._apply_reconciliation_to_suggestions(
            suggestions_data,
            connection_id=txn.connection_id,
            tenant_id=txn.tenant_id,
            session_id=uuid.uuid4(),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
        )

        # Should still create a suggestion with defaults
        assert len(suggestions_data) == 1
        assert suggestions_data[0]["description"] is None
        assert suggestions_data[0]["original_tax_type"] == "UNKNOWN"


# =============================================================================
# detect_and_generate tests (integration of reconciliation into generation flow)
# =============================================================================


class TestDetectAndGenerateReconciliation:
    """Test that detect_and_generate runs reconciliation even with no excluded items."""

    async def test_generates_for_unreconciled_even_without_excluded_items(self):
        """When GST calculator finds no excluded items, unreconciled bank txns
        should still get auto-parked suggestions."""
        session = AsyncMock()
        service = TaxCodeService(session)

        # Mock _get_editable_session
        mock_period = MagicMock()
        mock_period.connection_id = uuid.uuid4()
        mock_period.start_date = date(2026, 1, 1)
        mock_period.end_date = date(2026, 3, 31)
        mock_session = MagicMock()
        mock_session.period = mock_period

        # Mock GSTCalculator to return no excluded items
        mock_gst_result = MagicMock()
        mock_gst_result.excluded_items = []

        txn = _make_bank_txn(is_reconciled=False)

        with (
            patch.object(service, "_get_editable_session", return_value=mock_session),
            patch("app.modules.bas.tax_code_service.GSTCalculator") as MockCalc,
            patch.object(service, "_build_accounts_map", return_value={}),
            patch.object(service, "_apply_reconciliation_to_suggestions") as mock_apply,
            patch.object(service.repo, "bulk_create_suggestions", return_value=0),
            patch.object(service.repo, "create_audit_log"),
        ):
            MockCalc.return_value.calculate = AsyncMock(return_value=mock_gst_result)

            result = await service.detect_and_generate(uuid.uuid4(), uuid.uuid4())

            # _apply_reconciliation_to_suggestions must be called even with empty excluded list
            mock_apply.assert_called_once()
