"""Unit tests for ContextBuilderService report enrichment.

Tests cover:
- get_client_report_context: Fetching and structuring report data
- format_perspective_context_for_prompt: Including report data in prompts
"""

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.knowledge.context_builder import ContextBuilderService


@pytest.fixture
def mock_db_session() -> MagicMock:
    """Create a mock database session."""
    session = MagicMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def context_builder(mock_db_session: MagicMock) -> ContextBuilderService:
    """Create a ContextBuilderService with mocked dependencies."""
    return ContextBuilderService(db=mock_db_session)


@pytest.fixture
def sample_pl_report() -> MagicMock:
    """Create a sample P&L report mock."""
    report = MagicMock()
    report.summary_data = {
        "revenue": 150000.00,
        "total_income": 155000.00,
        "cost_of_sales": 60000.00,
        "gross_profit": 95000.00,
        "operating_expenses": 45000.00,
        "net_profit": 50000.00,
        "gross_margin_pct": 61.3,
        "net_margin_pct": 32.3,
        "expense_ratio_pct": 47.4,
    }
    report.period_key = "2024-Q4"
    report.fetched_at = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    return report


@pytest.fixture
def sample_bs_report() -> MagicMock:
    """Create a sample Balance Sheet report mock."""
    report = MagicMock()
    report.summary_data = {
        "total_assets": 250000.00,
        "current_assets": 100000.00,
        "non_current_assets": 150000.00,
        "total_liabilities": 80000.00,
        "current_liabilities": 50000.00,
        "equity": 170000.00,
        "current_ratio": 2.0,
        "debt_to_equity": 0.47,
    }
    report.period_key = "2024-12-31"
    report.fetched_at = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    return report


@pytest.fixture
def sample_ar_report() -> MagicMock:
    """Create a sample Aged Receivables report mock."""
    report = MagicMock()
    report.summary_data = {
        "total": 45000.00,
        "current": 30000.00,
        "overdue_30": 8000.00,
        "overdue_60": 4000.00,
        "overdue_90": 2000.00,
        "overdue_90_plus": 1000.00,
        "overdue_total": 15000.00,
        "overdue_pct": 33.3,
        "high_risk_contacts": [
            {"name": "ABC Corp", "amount": 5000.00, "days_overdue": 45},
            {"name": "XYZ Ltd", "amount": 3000.00, "days_overdue": 62},
        ],
    }
    report.period_key = "current"
    report.fetched_at = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    return report


@pytest.fixture
def sample_ap_report() -> MagicMock:
    """Create a sample Aged Payables report mock."""
    report = MagicMock()
    report.summary_data = {
        "total": 25000.00,
        "current": 20000.00,
        "overdue_total": 5000.00,
        "overdue_pct": 20.0,
    }
    report.period_key = "current"
    report.fetched_at = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    return report


class TestGetClientReportContext:
    """Tests for get_client_report_context method."""

    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_no_reports(
        self,
        context_builder: ContextBuilderService,
        mock_db_session: MagicMock,
    ) -> None:
        """Should return empty dict when no reports exist."""
        # Mock query result - no reports found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        connection_id = uuid.uuid4()
        result = await context_builder.get_client_report_context(connection_id)

        assert result == {}

    @pytest.mark.asyncio
    async def test_includes_pl_report_when_available(
        self,
        context_builder: ContextBuilderService,
        mock_db_session: MagicMock,
        sample_pl_report: MagicMock,
    ) -> None:
        """Should include P&L data when report is available."""
        # Set up mock to return P&L for first call, None for others
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.side_effect = [
            sample_pl_report,  # P&L
            None,  # Balance Sheet
            None,  # Aged Receivables
            None,  # Aged Payables
        ]
        mock_db_session.execute.return_value = mock_result

        connection_id = uuid.uuid4()
        result = await context_builder.get_client_report_context(connection_id)

        assert "profit_and_loss" in result
        assert result["profit_and_loss"]["total_income"] == 155000.00
        assert result["profit_and_loss"]["net_profit"] == 50000.00
        assert result["profit_and_loss"]["gross_margin_pct"] == 61.3
        assert result["profit_and_loss"]["net_margin_pct"] == 32.3

    @pytest.mark.asyncio
    async def test_includes_balance_sheet_when_available(
        self,
        context_builder: ContextBuilderService,
        mock_db_session: MagicMock,
        sample_bs_report: MagicMock,
    ) -> None:
        """Should include Balance Sheet data when report is available."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.side_effect = [
            None,  # P&L
            sample_bs_report,  # Balance Sheet
            None,  # Aged Receivables
            None,  # Aged Payables
        ]
        mock_db_session.execute.return_value = mock_result

        connection_id = uuid.uuid4()
        result = await context_builder.get_client_report_context(connection_id)

        assert "balance_sheet" in result
        assert result["balance_sheet"]["total_assets"] == 250000.00
        assert result["balance_sheet"]["current_ratio"] == 2.0
        assert result["balance_sheet"]["debt_to_equity"] == 0.47

    @pytest.mark.asyncio
    async def test_includes_aged_receivables_when_available(
        self,
        context_builder: ContextBuilderService,
        mock_db_session: MagicMock,
        sample_ar_report: MagicMock,
    ) -> None:
        """Should include Aged Receivables data when report is available."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.side_effect = [
            None,  # P&L
            None,  # Balance Sheet
            sample_ar_report,  # Aged Receivables
            None,  # Aged Payables
        ]
        mock_db_session.execute.return_value = mock_result

        connection_id = uuid.uuid4()
        result = await context_builder.get_client_report_context(connection_id)

        assert "aged_receivables" in result
        assert result["aged_receivables"]["total"] == 45000.00
        assert result["aged_receivables"]["overdue_total"] == 15000.00
        assert result["aged_receivables"]["overdue_pct"] == 33.3
        assert len(result["aged_receivables"]["high_risk_contacts"]) == 2

    @pytest.mark.asyncio
    async def test_includes_all_reports_when_available(
        self,
        context_builder: ContextBuilderService,
        mock_db_session: MagicMock,
        sample_pl_report: MagicMock,
        sample_bs_report: MagicMock,
        sample_ar_report: MagicMock,
        sample_ap_report: MagicMock,
    ) -> None:
        """Should include all report types when all are available."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.side_effect = [
            sample_pl_report,
            sample_bs_report,
            sample_ar_report,
            sample_ap_report,
        ]
        mock_db_session.execute.return_value = mock_result

        connection_id = uuid.uuid4()
        result = await context_builder.get_client_report_context(connection_id)

        assert "profit_and_loss" in result
        assert "balance_sheet" in result
        assert "aged_receivables" in result
        assert "aged_payables" in result


class TestFormatPerspectiveContextForPrompt:
    """Tests for format_perspective_context_for_prompt method."""

    def test_strategy_perspective_formats_pl_data(
        self,
        context_builder: ContextBuilderService,
    ) -> None:
        """Should format P&L data for Strategy perspective."""
        perspective_context: dict[str, Any] = {
            "report_context": {
                "profit_and_loss": {
                    "total_income": 155000.00,
                    "gross_profit": 95000.00,
                    "net_profit": 50000.00,
                    "gross_margin_pct": 61.3,
                    "net_margin_pct": 32.3,
                },
            }
        }

        result = context_builder.format_perspective_context_for_prompt(
            perspective_context,
            "strategy",
        )

        assert "Profit & Loss Summary:" in result
        assert "Total Income: $155,000.00" in result
        assert "Gross Profit: $95,000.00" in result
        assert "Net Profit: $50,000.00" in result
        assert "Gross Margin: 61.3%" in result
        assert "Net Margin: 32.3%" in result

    def test_strategy_perspective_formats_balance_sheet_data(
        self,
        context_builder: ContextBuilderService,
    ) -> None:
        """Should format Balance Sheet data for Strategy perspective."""
        perspective_context: dict[str, Any] = {
            "report_context": {
                "balance_sheet": {
                    "total_assets": 250000.00,
                    "total_liabilities": 80000.00,
                    "equity": 170000.00,
                    "current_ratio": 2.0,
                    "debt_to_equity": 0.47,
                },
            }
        }

        result = context_builder.format_perspective_context_for_prompt(
            perspective_context,
            "strategy",
        )

        # Strategy perspective includes key balance sheet metrics
        assert "Balance Sheet Summary:" in result
        assert "Total Assets: $250,000.00" in result
        assert "Equity: $170,000.00" in result
        assert "Current Ratio: 2.00" in result

    def test_insight_perspective_formats_aged_receivables(
        self,
        context_builder: ContextBuilderService,
    ) -> None:
        """Should format Aged Receivables for Insight perspective."""
        perspective_context: dict[str, Any] = {
            "report_context": {
                "aged_receivables": {
                    "total": 45000.00,
                    "overdue_total": 15000.00,
                    "overdue_pct": 33.3,
                    "high_risk_contacts": [
                        {"name": "ABC Corp", "amount": 5000.00},
                        {"name": "XYZ Ltd", "amount": 3000.00},
                    ],
                },
            }
        }

        result = context_builder.format_perspective_context_for_prompt(
            perspective_context,
            "insight",
        )

        assert "Aged Receivables Summary:" in result
        assert "Total Outstanding: $45,000.00" in result
        assert "Overdue Amount: $15,000.00" in result
        assert "Overdue %: 33.3%" in result
        assert "High-Risk Contacts:" in result
        assert "ABC Corp ($5,000.00)" in result

    def test_compliance_perspective_ignores_report_context(
        self,
        context_builder: ContextBuilderService,
    ) -> None:
        """Should not include report context for Compliance perspective."""
        perspective_context: dict[str, Any] = {
            "report_context": {
                "profit_and_loss": {
                    "total_income": 155000.00,
                },
            }
        }

        result = context_builder.format_perspective_context_for_prompt(
            perspective_context,
            "compliance",
        )

        # Compliance perspective shouldn't format report data
        assert "Profit & Loss Summary:" not in result

    def test_quality_perspective_ignores_report_context(
        self,
        context_builder: ContextBuilderService,
    ) -> None:
        """Should not include report context for Quality perspective."""
        perspective_context: dict[str, Any] = {
            "report_context": {
                "balance_sheet": {
                    "total_assets": 250000.00,
                },
            }
        }

        result = context_builder.format_perspective_context_for_prompt(
            perspective_context,
            "quality",
        )

        # Quality perspective shouldn't format report data
        assert "Balance Sheet Summary:" not in result

    def test_handles_missing_report_context_gracefully(
        self,
        context_builder: ContextBuilderService,
    ) -> None:
        """Should handle missing report context without error."""
        perspective_context: dict[str, Any] = {}

        # Should not raise an error
        result = context_builder.format_perspective_context_for_prompt(
            perspective_context,
            "strategy",
        )

        # Result should still be valid (may be empty or have other context)
        assert isinstance(result, str)

    def test_handles_partial_report_data_gracefully(
        self,
        context_builder: ContextBuilderService,
    ) -> None:
        """Should handle partial/missing report fields gracefully."""
        perspective_context: dict[str, Any] = {
            "report_context": {
                "profit_and_loss": {
                    "total_income": 100000.00,
                    # Missing other fields like gross_margin_pct
                },
            }
        }

        # Should not raise an error
        result = context_builder.format_perspective_context_for_prompt(
            perspective_context,
            "strategy",
        )

        assert "Total Income: $100,000.00" in result
        # Optional fields should not cause errors when missing
