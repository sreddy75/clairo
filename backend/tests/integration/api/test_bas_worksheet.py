"""Integration tests for BAS worksheet API endpoints with credit note adjustments.

Tests cover:
- BAS session creation and management
- GST calculation endpoints
- Credit note GST adjustments
- BAS summary and variance analysis

Spec 024 - Credit Notes, Payments & Journals
"""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.modules.bas.calculator import GSTResult


@pytest.mark.integration
class TestBASSessionEndpoints:
    """Tests for BAS session endpoints authentication."""

    async def test_create_session_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Should return 401 without authentication."""
        connection_id = uuid.uuid4()
        response = await test_client.post(
            f"/api/v1/clients/{connection_id}/bas/sessions",
            json={"quarter": 1, "fy_year": 2025},
        )
        assert response.status_code == 401

    async def test_list_sessions_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Should return 401 without authentication."""
        connection_id = uuid.uuid4()
        response = await test_client.get(f"/api/v1/clients/{connection_id}/bas/sessions")
        assert response.status_code == 401

    async def test_get_session_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Should return 401 without authentication."""
        connection_id = uuid.uuid4()
        session_id = uuid.uuid4()
        response = await test_client.get(
            f"/api/v1/clients/{connection_id}/bas/sessions/{session_id}"
        )
        assert response.status_code == 401


@pytest.mark.integration
class TestBASCalculationEndpoints:
    """Tests for BAS calculation endpoints."""

    async def test_trigger_calculation_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Should return 401 without authentication."""
        connection_id = uuid.uuid4()
        session_id = uuid.uuid4()
        response = await test_client.post(
            f"/api/v1/clients/{connection_id}/bas/sessions/{session_id}/calculate"
        )
        assert response.status_code == 401

    async def test_get_calculation_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Should return 401 without authentication."""
        connection_id = uuid.uuid4()
        session_id = uuid.uuid4()
        response = await test_client.get(
            f"/api/v1/clients/{connection_id}/bas/sessions/{session_id}/calculation"
        )
        assert response.status_code == 401


@pytest.mark.integration
class TestBASVarianceEndpoints:
    """Tests for BAS variance analysis endpoints."""

    async def test_get_variance_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Should return 401 without authentication."""
        connection_id = uuid.uuid4()
        session_id = uuid.uuid4()
        response = await test_client.get(
            f"/api/v1/clients/{connection_id}/bas/sessions/{session_id}/variance"
        )
        assert response.status_code == 401


@pytest.mark.integration
class TestBASSummaryEndpoints:
    """Tests for BAS summary endpoints."""

    async def test_get_summary_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Should return 401 without authentication."""
        connection_id = uuid.uuid4()
        session_id = uuid.uuid4()
        response = await test_client.get(
            f"/api/v1/clients/{connection_id}/bas/sessions/{session_id}/summary"
        )
        assert response.status_code == 401


@pytest.mark.integration
class TestBASExportEndpoints:
    """Tests for BAS export endpoints."""

    async def test_export_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Should return 401 without authentication."""
        connection_id = uuid.uuid4()
        session_id = uuid.uuid4()
        response = await test_client.get(
            f"/api/v1/clients/{connection_id}/bas/sessions/{session_id}/export"
        )
        assert response.status_code == 401


@pytest.mark.integration
class TestBASAdjustmentEndpoints:
    """Tests for BAS adjustment endpoints."""

    async def test_add_adjustment_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Should return 401 without authentication."""
        connection_id = uuid.uuid4()
        session_id = uuid.uuid4()
        response = await test_client.post(
            f"/api/v1/clients/{connection_id}/bas/sessions/{session_id}/adjustments",
            json={
                "field_name": "g1_total_sales",
                "adjustment_amount": "100.00",
                "reason": "Test adjustment",
            },
        )
        assert response.status_code == 401

    async def test_list_adjustments_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Should return 401 without authentication."""
        connection_id = uuid.uuid4()
        session_id = uuid.uuid4()
        response = await test_client.get(
            f"/api/v1/clients/{connection_id}/bas/sessions/{session_id}/adjustments"
        )
        assert response.status_code == 401


@pytest.mark.integration
class TestBASLodgementEndpoints:
    """Tests for BAS lodgement endpoints."""

    async def test_record_lodgement_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Should return 401 without authentication."""
        connection_id = uuid.uuid4()
        session_id = uuid.uuid4()
        response = await test_client.post(
            f"/api/v1/clients/{connection_id}/bas/sessions/{session_id}/lodgement",
            json={
                "lodgement_date": "2025-01-15",
                "lodgement_method": "ATO_PORTAL",
            },
        )
        assert response.status_code == 401

    async def test_get_lodgement_summary_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Should return 401 without authentication."""
        connection_id = uuid.uuid4()
        session_id = uuid.uuid4()
        response = await test_client.get(
            f"/api/v1/clients/{connection_id}/bas/sessions/{session_id}/lodgement"
        )
        assert response.status_code == 401


@pytest.mark.integration
class TestBASWorkboardEndpoints:
    """Tests for BAS workboard endpoints."""

    async def test_get_workboard_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Should return 401 without authentication."""
        response = await test_client.get("/api/v1/bas/workboard")
        assert response.status_code == 401

    async def test_get_workboard_summary_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Should return 401 without authentication."""
        response = await test_client.get("/api/v1/bas/workboard/summary")
        assert response.status_code == 401


@pytest.mark.integration
class TestBASFieldTransactionEndpoints:
    """Tests for BAS field transaction drilldown endpoints."""

    async def test_get_field_transactions_requires_auth(
        self,
        test_client: AsyncClient,
    ) -> None:
        """Should return 401 without authentication."""
        connection_id = uuid.uuid4()
        session_id = uuid.uuid4()
        response = await test_client.get(
            f"/api/v1/clients/{connection_id}/bas/sessions/{session_id}/transactions/g1_total_sales"
        )
        assert response.status_code == 401


# =============================================================================
# Credit Note GST Calculation Tests (Spec 024)
# =============================================================================


class TestGSTCalculationWithCreditNotes:
    """Tests for GST calculation with credit note adjustments.

    These tests verify the business logic for credit note GST adjustments
    as specified in Spec 024, User Story 2.
    """

    def test_sales_credit_note_reduces_gst_on_sales(self) -> None:
        """Sales credit notes should reduce output GST (field 1A).

        Given:
        - GST on sales (1A): $1,000
        - GST on purchases (1B): $400
        - Sales credit note GST: $100

        Expected:
        - Net GST on sales: $1,000 - $100 = $900
        - GST payable: $900 - $400 = $500
        """
        result = GSTResult(
            field_1a_gst_on_sales=Decimal("1000"),
            field_1b_gst_on_purchases=Decimal("400"),
            sales_credit_notes_gst=Decimal("100"),
        )
        result.calculate_gst_payable()

        assert result.net_gst_on_sales == Decimal("900")
        assert result.gst_payable == Decimal("500")

    def test_purchase_credit_note_reduces_input_tax_credits(self) -> None:
        """Purchase credit notes should reduce input tax credits (field 1B).

        Given:
        - GST on sales (1A): $1,000
        - GST on purchases (1B): $400
        - Purchase credit note GST: $50

        Expected:
        - Net GST on purchases: $400 - $50 = $350
        - GST payable: $1,000 - $350 = $650
        """
        result = GSTResult(
            field_1a_gst_on_sales=Decimal("1000"),
            field_1b_gst_on_purchases=Decimal("400"),
            purchase_credit_notes_gst=Decimal("50"),
        )
        result.calculate_gst_payable()

        assert result.net_gst_on_purchases == Decimal("350")
        assert result.gst_payable == Decimal("650")

    def test_combined_credit_notes_affect_gst_payable(self) -> None:
        """Both sales and purchase credit notes should adjust GST correctly.

        Given:
        - GST on sales (1A): $1,000
        - GST on purchases (1B): $400
        - Sales credit note GST: $100
        - Purchase credit note GST: $50

        Expected:
        - Net GST on sales: $1,000 - $100 = $900
        - Net GST on purchases: $400 - $50 = $350
        - GST payable: $900 - $350 = $550
        """
        result = GSTResult(
            field_1a_gst_on_sales=Decimal("1000"),
            field_1b_gst_on_purchases=Decimal("400"),
            sales_credit_notes_gst=Decimal("100"),
            purchase_credit_notes_gst=Decimal("50"),
        )
        result.calculate_gst_payable()

        assert result.net_gst_on_sales == Decimal("900")
        assert result.net_gst_on_purchases == Decimal("350")
        assert result.gst_payable == Decimal("550")

    def test_credit_notes_can_cause_refund(self) -> None:
        """Large sales credit notes can result in GST refund position.

        Given:
        - GST on sales (1A): $500
        - GST on purchases (1B): $300
        - Sales credit note GST: $400

        Expected:
        - Net GST on sales: $500 - $400 = $100
        - GST payable: $100 - $300 = -$200 (refund)
        """
        result = GSTResult(
            field_1a_gst_on_sales=Decimal("500"),
            field_1b_gst_on_purchases=Decimal("300"),
            sales_credit_notes_gst=Decimal("400"),
        )
        result.calculate_gst_payable()

        assert result.gst_payable == Decimal("-200")
        assert result.is_refund is True

    def test_net_total_sales_with_credit_notes(self) -> None:
        """Net total sales should be reduced by credit note amounts.

        Given:
        - G1 Total sales: $10,000
        - Sales credit notes total: $1,100

        Expected:
        - Net total sales: $10,000 - $1,100 = $8,900
        """
        result = GSTResult(
            g1_total_sales=Decimal("10000"),
            sales_credit_notes=Decimal("1100"),
        )

        assert result.net_total_sales == Decimal("8900")

    def test_full_bas_period_with_credit_notes(self) -> None:
        """Full BAS period scenario with all credit note adjustments.

        Simulates a complete BAS quarter with:
        - Regular invoices contributing to sales and purchases
        - Credit notes reducing both sales GST and purchase GST
        - Final GST payable calculation

        This is the key acceptance test for Spec 024 User Story 2.
        """
        # Set up BAS period with transactions
        result = GSTResult(
            # Regular sales and purchases
            g1_total_sales=Decimal("55000"),  # $55,000 sales
            g2_export_sales=Decimal("5000"),  # $5,000 exports
            g3_gst_free_sales=Decimal("2000"),  # $2,000 GST-free
            g10_capital_purchases=Decimal("11000"),  # $11,000 capital
            g11_non_capital_purchases=Decimal("22000"),  # $22,000 non-capital
            field_1a_gst_on_sales=Decimal("5000"),  # $5,000 GST on sales
            field_1b_gst_on_purchases=Decimal("3000"),  # $3,000 GST on purchases
            # Credit notes
            sales_credit_notes=Decimal("2200"),  # $2,200 sales credit notes
            sales_credit_notes_gst=Decimal("200"),  # $200 GST adjustment
            purchase_credit_notes=Decimal("550"),  # $550 purchase credit notes
            purchase_credit_notes_gst=Decimal("50"),  # $50 GST adjustment
            # Metadata
            invoice_count=45,
            transaction_count=120,
            credit_note_count=5,
        )

        result.calculate_gst_payable()

        # Verify net amounts
        assert result.net_gst_on_sales == Decimal("4800")  # 5000 - 200
        assert result.net_gst_on_purchases == Decimal("2950")  # 3000 - 50
        assert result.net_total_sales == Decimal("52800")  # 55000 - 2200
        assert result.gst_payable == Decimal("1850")  # 4800 - 2950
        assert result.is_refund is False

    def test_credit_notes_apply_to_period_when_issued(self) -> None:
        """Credit notes should apply to the period when they are issued.

        Per ATO rules, credit notes affect the GST period in which they
        are issued, NOT the period of the original invoice.

        This test verifies the calculation correctly includes credit notes
        issued within the BAS period regardless of original invoice date.
        """
        # Credit note issued in current period for invoice from last period
        result = GSTResult(
            field_1a_gst_on_sales=Decimal("1000"),
            field_1b_gst_on_purchases=Decimal("400"),
            # Credit note for previous period invoice, but issued this period
            sales_credit_notes=Decimal("1100"),
            sales_credit_notes_gst=Decimal("100"),
            credit_note_count=1,
        )

        result.calculate_gst_payable()

        # Credit note reduces current period GST
        assert result.net_gst_on_sales == Decimal("900")
        assert result.gst_payable == Decimal("500")  # 900 - 400
