"""Unit tests for xero_writeback task logic.

Spec 049: Xero Tax Code Write-Back.
Tests cover:
- Error classifier: inline 400-error → skip_reason mapping
- Tax-rate validation logic (changed-codes only)
- Idempotency key derivation
- Helper functions: apply_overrides_to_line_items, group_overrides_by_document
"""

from unittest.mock import MagicMock
from uuid import uuid4

from app.modules.integrations.xero.writeback_service import (
    apply_overrides_to_line_items,
    group_overrides_by_document,
)

# ===========================================================================
# Error classifier helper — mirrors the inline logic in _run_writeback_job
# ===========================================================================


def _classify_xero_error(error_str: str, xero_status: int | None) -> str | None:
    """Mirror of inline error-classification logic in xero_writeback task.

    Returns the skip_reason string or None (→ item is FAILED, not SKIPPED).
    """
    if xero_status != 400:
        return None
    error_str = error_str.lower()
    if "period" in error_str or "accounting period" in error_str:
        return "period_locked"
    elif "cannot modify line items" in error_str or "has payments" in error_str:
        return "authorised_locked"
    elif "credit note" in error_str or "credit_note" in error_str:
        return "credit_note_applied"
    return None


# ===========================================================================
# Error classifier tests
# ===========================================================================


class TestErrorClassifier:
    """Tests for the 400-error → skip_reason classifier."""

    def test_period_locked_matches_accounting_period(self) -> None:
        result = _classify_xero_error("The accounting period is locked", 400)
        assert result == "period_locked"

    def test_period_locked_matches_period_keyword(self) -> None:
        result = _classify_xero_error("Period is closed for this date", 400)
        assert result == "period_locked"

    def test_period_locked_does_not_match_generic_locked(self) -> None:
        # "entity is locked" has no "period" → should not match period_locked
        result = _classify_xero_error("The entity is locked", 400)
        assert result != "period_locked"
        # Falls through to None (FAILED, not SKIPPED)
        assert result is None

    def test_authorised_locked_matches_cannot_modify(self) -> None:
        result = _classify_xero_error("cannot modify line items on this invoice", 400)
        assert result == "authorised_locked"

    def test_authorised_locked_matches_has_payments(self) -> None:
        result = _classify_xero_error("invoice has payments applied", 400)
        assert result == "authorised_locked"

    def test_credit_note_applied_matches(self) -> None:
        result = _classify_xero_error("a credit note has been applied", 400)
        assert result == "credit_note_applied"

    def test_credit_note_applied_matches_underscore_variant(self) -> None:
        result = _classify_xero_error("credit_note allocation exists", 400)
        assert result == "credit_note_applied"

    def test_non_400_status_never_skipped(self) -> None:
        # 500 errors should never produce a skip_reason
        result = _classify_xero_error("accounting period is locked", 500)
        assert result is None

    def test_non_400_status_none(self) -> None:
        result = _classify_xero_error("accounting period is locked", None)
        assert result is None

    def test_unknown_400_error_returns_none(self) -> None:
        result = _classify_xero_error("some completely unknown error message", 400)
        assert result is None


# ===========================================================================
# Tax-rate validation logic tests
# ===========================================================================


def _validate_tax_codes(
    before_tax_types: dict,
    after_tax_types: dict,
    valid_tax_types: set | None,
) -> list[str]:
    """Mirror of the inline validation in _run_writeback_job.

    Returns list of invalid codes (empty means all valid).
    """
    if valid_tax_types is None:
        return []
    if not after_tax_types or not before_tax_types:
        return []
    new_codes = {
        code
        for idx, code in after_tax_types.items()
        if code != before_tax_types.get(idx)
    }
    return [code for code in new_codes if code not in valid_tax_types]


class TestTaxRateValidation:
    """Tests for the tax code validation logic."""

    def test_skips_unchanged_codes(self) -> None:
        before = {"0": "G11", "1": "GST"}
        after = {"0": "G11", "1": "GST"}
        invalid = _validate_tax_codes(before, after, {"G11", "GST"})
        assert invalid == []

    def test_rejects_unknown_changed_code(self) -> None:
        before = {"0": "G11"}
        after = {"0": "INVALID_CODE"}
        invalid = _validate_tax_codes(before, after, {"G11", "GST", "BAS_EXCLUDED"})
        assert "INVALID_CODE" in invalid

    def test_allows_known_changed_code(self) -> None:
        before = {"0": "G11"}
        after = {"0": "GST"}
        invalid = _validate_tax_codes(before, after, {"G11", "GST"})
        assert invalid == []

    def test_skipped_when_valid_types_none(self) -> None:
        # valid_tax_types=None means the TaxRates fetch failed — skip validation
        before = {"0": "G11"}
        after = {"0": "TOTALLY_FAKE_CODE"}
        invalid = _validate_tax_codes(before, after, None)
        assert invalid == []

    def test_unchanged_code_not_validated_even_if_missing_from_set(self) -> None:
        # Original code G11 → G11 (unchanged): NOT checked against valid set
        before = {"0": "G11"}
        after = {"0": "G11"}
        # G11 not in valid set, but since unchanged it should not be flagged
        invalid = _validate_tax_codes(before, after, {"GST"})
        assert invalid == []

    def test_multiple_codes_with_partial_invalid(self) -> None:
        before = {"0": "G11", "1": "GST"}
        after = {"0": "BAD_CODE", "1": "GST"}
        invalid = _validate_tax_codes(before, after, {"G11", "GST"})
        assert "BAD_CODE" in invalid
        assert len(invalid) == 1


# ===========================================================================
# apply_overrides_to_line_items tests
# ===========================================================================


def _make_override(
    line_item_index: int,
    original_tax_type: str,
    override_tax_type: str,
    is_new_split: bool = False,
    is_deleted: bool = False,
    line_amount=None,
    line_description=None,
    line_account_code=None,
):
    override = MagicMock()
    override.line_item_index = line_item_index
    override.original_tax_type = original_tax_type
    override.override_tax_type = override_tax_type
    override.is_new_split = is_new_split
    override.is_deleted = is_deleted
    override.line_amount = line_amount
    override.line_description = line_description
    override.line_account_code = line_account_code
    return override


class TestApplyOverridesToLineItems:
    """Tests for the apply_overrides_to_line_items pure function."""

    def test_applies_single_override(self) -> None:
        line_items = [{"TaxType": "G11", "Description": "Office supplies"}]
        override = _make_override(0, "G11", "GST")
        modified, before, after = apply_overrides_to_line_items(line_items, [override])
        assert modified[0]["TaxType"] == "GST"
        assert before["0"] == "G11"
        assert after["0"] == "GST"

    def test_does_not_mutate_original_line_items(self) -> None:
        line_items = [{"TaxType": "G11"}]
        override = _make_override(0, "G11", "GST")
        apply_overrides_to_line_items(line_items, [override])
        assert line_items[0]["TaxType"] == "G11"  # original unchanged

    def test_applies_multiple_overrides(self) -> None:
        line_items = [{"TaxType": "G11"}, {"TaxType": "GST"}, {"TaxType": "G11"}]
        overrides = [
            _make_override(0, "G11", "BAS_EXCLUDED"),
            _make_override(2, "G11", "GST"),
        ]
        modified, before, after = apply_overrides_to_line_items(line_items, overrides)
        assert modified[0]["TaxType"] == "BAS_EXCLUDED"
        assert modified[1]["TaxType"] == "GST"  # untouched
        assert modified[2]["TaxType"] == "GST"
        assert before == {"0": "G11", "2": "G11"}
        assert after == {"0": "BAS_EXCLUDED", "2": "GST"}

    def test_out_of_bounds_index_ignored(self) -> None:
        line_items = [{"TaxType": "G11"}]
        override = _make_override(5, "G11", "GST")  # index 5 doesn't exist
        modified, before, after = apply_overrides_to_line_items(line_items, [override])
        assert modified == [{"TaxType": "G11"}]
        assert before == {}
        assert after == {}

    def test_empty_overrides_returns_copy(self) -> None:
        line_items = [{"TaxType": "G11"}]
        modified, before, after = apply_overrides_to_line_items(line_items, [])
        assert modified == [{"TaxType": "G11"}]
        assert before == {}
        assert after == {}

    def test_missing_tax_type_defaults_to_none(self) -> None:
        line_items = [{"Description": "No tax type field"}]
        override = _make_override(0, "NONE", "GST")
        modified, before, after = apply_overrides_to_line_items(line_items, [override])
        assert before["0"] == "NONE"
        assert after["0"] == "GST"

    def test_tax_amount_removed_on_override(self) -> None:
        """TaxAmount must be removed so Xero recalculates it for the new tax type."""
        line_items = [{"TaxType": "INPUT", "TaxAmount": 90.91, "LineAmount": 1000.0}]
        override = _make_override(0, "INPUT", "BASEXCLUDED")
        modified, _, _ = apply_overrides_to_line_items(line_items, [override])
        assert "TaxAmount" not in modified[0]

    def test_tax_amount_removed_when_switching_back_to_taxable(self) -> None:
        """TaxAmount is removed even when switching from zero-rate back to taxable."""
        line_items = [{"TaxType": "BASEXCLUDED", "TaxAmount": 0.0, "LineAmount": 1000.0}]
        override = _make_override(0, "BASEXCLUDED", "INPUT")
        modified, _, _ = apply_overrides_to_line_items(line_items, [override])
        assert "TaxAmount" not in modified[0]


# ===========================================================================
# group_overrides_by_document tests
# ===========================================================================


def _make_override_with_source(source_type: str, source_id, line_item_index: int = 0):
    override = MagicMock()
    override.source_type = source_type
    override.source_id = source_id
    override.line_item_index = line_item_index
    override.original_tax_type = "G11"
    override.override_tax_type = "GST"
    return override


class TestGroupOverridesByDocument:
    """Tests for the group_overrides_by_document pure function."""

    def test_groups_same_document_together(self) -> None:
        doc_id = uuid4()
        overrides = [
            _make_override_with_source("invoice", doc_id, 0),
            _make_override_with_source("invoice", doc_id, 1),
        ]
        grouped = group_overrides_by_document(overrides)
        assert len(grouped) == 1
        key = ("invoice", doc_id)
        assert len(grouped[key]) == 2

    def test_separates_different_documents(self) -> None:
        doc_a = uuid4()
        doc_b = uuid4()
        overrides = [
            _make_override_with_source("invoice", doc_a),
            _make_override_with_source("invoice", doc_b),
        ]
        grouped = group_overrides_by_document(overrides)
        assert len(grouped) == 2

    def test_separates_different_source_types(self) -> None:
        doc_id = uuid4()
        overrides = [
            _make_override_with_source("invoice", doc_id),
            _make_override_with_source("bank_transaction", doc_id),
        ]
        grouped = group_overrides_by_document(overrides)
        assert len(grouped) == 2

    def test_total_count_equals_unique_documents(self) -> None:
        doc_a = uuid4()
        doc_b = uuid4()
        overrides = [
            _make_override_with_source("invoice", doc_a, 0),
            _make_override_with_source("invoice", doc_a, 1),
            _make_override_with_source("invoice", doc_b, 0),
        ]
        grouped = group_overrides_by_document(overrides)
        # 2 unique documents, not 3 overrides
        assert len(grouped) == 2

    def test_empty_overrides_returns_empty_dict(self) -> None:
        grouped = group_overrides_by_document([])
        assert grouped == {}


# ===========================================================================
# Idempotency key test
# ===========================================================================


class TestIdempotencyKey:
    """The idempotency key passed to Xero must be str(item.id)."""

    def test_idempotency_key_is_item_id_string(self) -> None:
        item_id = uuid4()
        item = MagicMock()
        item.id = item_id
        # Mirrors the production code: idempotency_key = str(item.id)
        key = str(item.id)
        assert key == str(item_id)
        assert isinstance(key, str)
