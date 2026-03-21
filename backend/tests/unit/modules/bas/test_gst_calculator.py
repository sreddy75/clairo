"""Unit tests for GST Calculator with credit note adjustments (Spec 024).

Tests cover:
- GSTResult dataclass calculations
- Credit note processing
- Net GST calculation with credit notes
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from app.modules.bas.calculator import GSTCalculator, GSTResult
from app.modules.integrations.xero.models import (
    XeroCreditNote,
    XeroCreditNoteStatus,
    XeroCreditNoteType,
)

# =============================================================================
# GSTResult Tests
# =============================================================================


class TestGSTResult:
    """Tests for GSTResult dataclass."""

    def test_default_values(self):
        """All values should default to zero."""
        result = GSTResult()

        assert result.g1_total_sales == Decimal("0")
        assert result.g2_export_sales == Decimal("0")
        assert result.g3_gst_free_sales == Decimal("0")
        assert result.g10_capital_purchases == Decimal("0")
        assert result.g11_non_capital_purchases == Decimal("0")
        assert result.field_1a_gst_on_sales == Decimal("0")
        assert result.field_1b_gst_on_purchases == Decimal("0")
        assert result.gst_payable == Decimal("0")
        assert result.sales_credit_notes == Decimal("0")
        assert result.sales_credit_notes_gst == Decimal("0")
        assert result.purchase_credit_notes == Decimal("0")
        assert result.purchase_credit_notes_gst == Decimal("0")
        assert result.credit_note_count == 0

    def test_calculate_gst_payable_no_credit_notes(self):
        """GST payable = 1A - 1B when no credit notes."""
        result = GSTResult(
            field_1a_gst_on_sales=Decimal("1000"),
            field_1b_gst_on_purchases=Decimal("400"),
        )
        result.calculate_gst_payable()

        assert result.gst_payable == Decimal("600")

    def test_calculate_gst_payable_with_sales_credit_notes(self):
        """Sales credit notes reduce GST on sales (1A)."""
        result = GSTResult(
            field_1a_gst_on_sales=Decimal("1000"),
            field_1b_gst_on_purchases=Decimal("400"),
            sales_credit_notes_gst=Decimal("100"),  # $100 GST reduction
        )
        result.calculate_gst_payable()

        # Net 1A = 1000 - 100 = 900
        # GST payable = 900 - 400 = 500
        assert result.gst_payable == Decimal("500")

    def test_calculate_gst_payable_with_purchase_credit_notes(self):
        """Purchase credit notes reduce input tax credits (1B)."""
        result = GSTResult(
            field_1a_gst_on_sales=Decimal("1000"),
            field_1b_gst_on_purchases=Decimal("400"),
            purchase_credit_notes_gst=Decimal("50"),  # $50 GST reduction
        )
        result.calculate_gst_payable()

        # Net 1B = 400 - 50 = 350
        # GST payable = 1000 - 350 = 650
        assert result.gst_payable == Decimal("650")

    def test_calculate_gst_payable_with_both_credit_notes(self):
        """Both sales and purchase credit notes affect GST payable."""
        result = GSTResult(
            field_1a_gst_on_sales=Decimal("1000"),
            field_1b_gst_on_purchases=Decimal("400"),
            sales_credit_notes_gst=Decimal("100"),
            purchase_credit_notes_gst=Decimal("50"),
        )
        result.calculate_gst_payable()

        # Net 1A = 1000 - 100 = 900
        # Net 1B = 400 - 50 = 350
        # GST payable = 900 - 350 = 550
        assert result.gst_payable == Decimal("550")

    def test_net_gst_on_sales_property(self):
        """net_gst_on_sales = 1A - sales credit notes GST."""
        result = GSTResult(
            field_1a_gst_on_sales=Decimal("1000"),
            sales_credit_notes_gst=Decimal("150"),
        )

        assert result.net_gst_on_sales == Decimal("850")

    def test_net_gst_on_purchases_property(self):
        """net_gst_on_purchases = 1B - purchase credit notes GST."""
        result = GSTResult(
            field_1b_gst_on_purchases=Decimal("500"),
            purchase_credit_notes_gst=Decimal("75"),
        )

        assert result.net_gst_on_purchases == Decimal("425")

    def test_net_total_sales_property(self):
        """net_total_sales = G1 - sales credit notes."""
        result = GSTResult(
            g1_total_sales=Decimal("10000"),
            sales_credit_notes=Decimal("500"),
        )

        assert result.net_total_sales == Decimal("9500")

    def test_is_refund_false(self):
        """is_refund is False when GST payable is positive."""
        result = GSTResult(
            field_1a_gst_on_sales=Decimal("1000"),
            field_1b_gst_on_purchases=Decimal("400"),
        )
        result.calculate_gst_payable()

        assert result.is_refund is False

    def test_is_refund_true(self):
        """is_refund is True when 1B > 1A (more input credits than output GST)."""
        result = GSTResult(
            field_1a_gst_on_sales=Decimal("400"),
            field_1b_gst_on_purchases=Decimal("1000"),
        )
        result.calculate_gst_payable()

        assert result.is_refund is True
        assert result.gst_payable == Decimal("-600")

    def test_credit_notes_can_cause_refund(self):
        """Large sales credit notes can push GST payable into refund territory."""
        result = GSTResult(
            field_1a_gst_on_sales=Decimal("500"),
            field_1b_gst_on_purchases=Decimal("300"),
            sales_credit_notes_gst=Decimal("400"),  # Large credit note
        )
        result.calculate_gst_payable()

        # Net 1A = 500 - 400 = 100
        # GST payable = 100 - 300 = -200 (refund)
        assert result.gst_payable == Decimal("-200")
        assert result.is_refund is True


# =============================================================================
# GSTCalculator Credit Note Processing Tests
# =============================================================================


class TestGSTCalculatorCreditNotes:
    """Tests for GSTCalculator credit note processing."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_session = AsyncMock()
        self.calculator = GSTCalculator(self.mock_session)

    def _create_credit_note(
        self,
        credit_note_type: XeroCreditNoteType,
        total_amount: Decimal,
        tax_amount: Decimal,
        status: XeroCreditNoteStatus = XeroCreditNoteStatus.AUTHORISED,
    ) -> XeroCreditNote:
        """Helper to create a mock credit note."""
        mock_cn = MagicMock(spec=XeroCreditNote)
        mock_cn.credit_note_type = credit_note_type
        mock_cn.total_amount = total_amount
        mock_cn.tax_amount = tax_amount
        mock_cn.status = status
        return mock_cn

    def test_process_sales_credit_note(self):
        """Sales credit notes (ACCRECCREDIT) reduce GST on sales."""
        result = GSTResult()
        credit_notes = [
            self._create_credit_note(
                XeroCreditNoteType.ACCRECCREDIT,
                total_amount=Decimal("1100"),
                tax_amount=Decimal("100"),
            )
        ]

        self.calculator._process_credit_notes(credit_notes, result)

        assert result.sales_credit_notes == Decimal("1100")
        assert result.sales_credit_notes_gst == Decimal("100")
        assert result.purchase_credit_notes == Decimal("0")
        assert result.purchase_credit_notes_gst == Decimal("0")

    def test_process_purchase_credit_note(self):
        """Purchase credit notes (ACCPAYCREDIT) reduce input tax credits."""
        result = GSTResult()
        credit_notes = [
            self._create_credit_note(
                XeroCreditNoteType.ACCPAYCREDIT,
                total_amount=Decimal("550"),
                tax_amount=Decimal("50"),
            )
        ]

        self.calculator._process_credit_notes(credit_notes, result)

        assert result.sales_credit_notes == Decimal("0")
        assert result.sales_credit_notes_gst == Decimal("0")
        assert result.purchase_credit_notes == Decimal("550")
        assert result.purchase_credit_notes_gst == Decimal("50")

    def test_process_multiple_credit_notes(self):
        """Multiple credit notes of different types are processed correctly."""
        result = GSTResult()
        credit_notes = [
            # Two sales credit notes
            self._create_credit_note(
                XeroCreditNoteType.ACCRECCREDIT,
                total_amount=Decimal("1100"),
                tax_amount=Decimal("100"),
            ),
            self._create_credit_note(
                XeroCreditNoteType.ACCRECCREDIT,
                total_amount=Decimal("550"),
                tax_amount=Decimal("50"),
            ),
            # One purchase credit note
            self._create_credit_note(
                XeroCreditNoteType.ACCPAYCREDIT,
                total_amount=Decimal("330"),
                tax_amount=Decimal("30"),
            ),
        ]

        self.calculator._process_credit_notes(credit_notes, result)

        # Sales: 1100 + 550 = 1650, GST: 100 + 50 = 150
        assert result.sales_credit_notes == Decimal("1650")
        assert result.sales_credit_notes_gst == Decimal("150")
        # Purchases: 330, GST: 30
        assert result.purchase_credit_notes == Decimal("330")
        assert result.purchase_credit_notes_gst == Decimal("30")

    def test_process_credit_note_with_none_amounts(self):
        """Credit notes with None amounts are treated as zero."""
        result = GSTResult()
        mock_cn = MagicMock(spec=XeroCreditNote)
        mock_cn.credit_note_type = XeroCreditNoteType.ACCRECCREDIT
        mock_cn.total_amount = None
        mock_cn.tax_amount = None

        self.calculator._process_credit_notes([mock_cn], result)

        assert result.sales_credit_notes == Decimal("0")
        assert result.sales_credit_notes_gst == Decimal("0")

    def test_process_empty_credit_notes(self):
        """Empty credit notes list doesn't affect result."""
        result = GSTResult(
            field_1a_gst_on_sales=Decimal("1000"),
            field_1b_gst_on_purchases=Decimal("400"),
        )

        self.calculator._process_credit_notes([], result)

        assert result.sales_credit_notes == Decimal("0")
        assert result.purchase_credit_notes == Decimal("0")


# =============================================================================
# Credit Note Integration Tests
# =============================================================================


class TestGSTCalculatorCreditNoteIntegration:
    """Integration tests for credit note processing in GST calculation.

    Note: These tests verify the flow of credit note processing through
    the GSTResult calculation methods, not the database layer.
    """

    def test_full_gst_calculation_flow_with_credit_notes(self):
        """Simulate a complete GST calculation with credit notes."""
        # Simulate a BAS period with:
        # - $10,000 sales with $1,000 GST
        # - $5,000 purchases with $500 GST
        # - $1,100 sales credit note with $100 GST
        # - $330 purchase credit note with $30 GST
        result = GSTResult(
            g1_total_sales=Decimal("10000"),
            g10_capital_purchases=Decimal("2000"),
            g11_non_capital_purchases=Decimal("3000"),
            field_1a_gst_on_sales=Decimal("1000"),
            field_1b_gst_on_purchases=Decimal("500"),
            sales_credit_notes=Decimal("1100"),
            sales_credit_notes_gst=Decimal("100"),
            purchase_credit_notes=Decimal("330"),
            purchase_credit_notes_gst=Decimal("30"),
            invoice_count=15,
            transaction_count=50,
            credit_note_count=2,
        )

        result.calculate_gst_payable()

        # Verify net amounts
        assert result.net_gst_on_sales == Decimal("900")  # 1000 - 100
        assert result.net_gst_on_purchases == Decimal("470")  # 500 - 30
        assert result.net_total_sales == Decimal("8900")  # 10000 - 1100
        assert result.gst_payable == Decimal("430")  # 900 - 470
        assert result.is_refund is False

    def test_credit_notes_resulting_in_refund(self):
        """Credit notes can result in a GST refund position."""
        result = GSTResult(
            g1_total_sales=Decimal("5000"),
            field_1a_gst_on_sales=Decimal("500"),
            field_1b_gst_on_purchases=Decimal("600"),
            sales_credit_notes=Decimal("3000"),
            sales_credit_notes_gst=Decimal("300"),  # Large credit reduces sales GST significantly
            credit_note_count=1,
        )

        result.calculate_gst_payable()

        # Net 1A = 500 - 300 = 200
        # GST payable = 200 - 600 = -400 (refund)
        assert result.net_gst_on_sales == Decimal("200")
        assert result.gst_payable == Decimal("-400")
        assert result.is_refund is True


# =============================================================================
# Edge Cases
# =============================================================================


class TestGSTCalculatorEdgeCases:
    """Edge case tests for GST calculator."""

    def test_large_credit_note_amounts(self):
        """Handles large credit note amounts correctly."""
        result = GSTResult(
            field_1a_gst_on_sales=Decimal("1000000.00"),
            field_1b_gst_on_purchases=Decimal("500000.00"),
            sales_credit_notes=Decimal("9999999.99"),
            sales_credit_notes_gst=Decimal("909090.90"),
        )
        result.calculate_gst_payable()

        # Net 1A = 1000000 - 909090.90 = 90909.10
        # GST payable = 90909.10 - 500000 = -409090.90
        assert result.gst_payable == Decimal("90909.10") - Decimal("500000.00")

    def test_decimal_precision(self):
        """Decimal calculations maintain precision."""
        result = GSTResult(
            field_1a_gst_on_sales=Decimal("123.456789"),
            field_1b_gst_on_purchases=Decimal("45.678901"),
            sales_credit_notes_gst=Decimal("12.345678"),
            purchase_credit_notes_gst=Decimal("4.567890"),
        )
        result.calculate_gst_payable()

        # Net 1A = 123.456789 - 12.345678 = 111.111111
        # Net 1B = 45.678901 - 4.567890 = 41.111011
        # GST payable = 111.111111 - 41.111011 = 70.000100
        expected = (
            Decimal("123.456789")
            - Decimal("12.345678")
            - (Decimal("45.678901") - Decimal("4.567890"))
        )
        assert result.gst_payable == expected

    def test_zero_amounts(self):
        """Handles all zero amounts gracefully."""
        result = GSTResult()
        result.calculate_gst_payable()

        assert result.gst_payable == Decimal("0")
        assert result.is_refund is False
        assert result.net_gst_on_sales == Decimal("0")
        assert result.net_gst_on_purchases == Decimal("0")
        assert result.net_total_sales == Decimal("0")
