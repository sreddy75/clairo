"""CSV Exporter for BAS data transfer.

Spec 011: Interim Lodgement
"""

import csv
import io
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.bas.models import BASCalculation, BASPeriod, BASSession


class CSVExporter:
    """CSV exporter for BAS data transfer.

    Generates ATO-compliant CSV with:
    - Metadata rows at top (client, ABN, period, export date)
    - Field Code, Field Description, Amount columns
    - Whole dollar amounts without currency symbols
    - UTF-8 encoding for Excel compatibility
    """

    def __init__(
        self,
        session: "BASSession",
        period: "BASPeriod",
        calculation: "BASCalculation | None",
        organization_name: str,
        abn: str | None = None,
    ):
        self.session = session
        self.period = period
        self.calculation = calculation
        self.organization_name = organization_name
        self.abn = abn

    def _round_to_whole_dollars(self, amount: Decimal | None) -> int:
        """Round amount to whole dollars per ATO requirements."""
        if amount is None:
            return 0
        return int(Decimal(str(amount)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    def generate_csv(self) -> bytes:
        """Generate CSV file as bytes.

        Returns:
            UTF-8 encoded CSV content with:
            - Metadata rows at top
            - Field Code, Field Description, Amount columns
            - Whole dollar amounts (no currency symbols)
        """
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_ALL)

        # Metadata rows
        writer.writerow(["BAS Export - ATO Lodgement Data"])
        writer.writerow([])
        writer.writerow(["Client Name", self.organization_name])
        if self.abn:
            writer.writerow(["ABN", self.abn])
        writer.writerow(["Period", self.period.display_name])
        writer.writerow(["Period Start", self.period.start_date.isoformat()])
        writer.writerow(["Period End", self.period.end_date.isoformat()])
        writer.writerow(["Due Date", self.period.due_date.isoformat()])
        writer.writerow(["Export Date", datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")])
        writer.writerow([])

        # Header row
        writer.writerow(["Field Code", "Field Description", "Amount"])

        if self.calculation:
            # GST fields in ATO form order
            gst_fields = [
                ("G1", "Total sales (including any GST)", self.calculation.g1_total_sales),
                ("G2", "Export sales", self.calculation.g2_export_sales),
                ("G3", "Other GST-free sales", self.calculation.g3_gst_free_sales),
                (
                    "G10",
                    "Capital purchases (including any GST)",
                    self.calculation.g10_capital_purchases,
                ),
                (
                    "G11",
                    "Non-capital purchases (including any GST)",
                    self.calculation.g11_non_capital_purchases,
                ),
                ("1A", "GST on sales", self.calculation.field_1a_gst_on_sales),
                ("1B", "GST on purchases", self.calculation.field_1b_gst_on_purchases),
            ]

            for code, desc, amount in gst_fields:
                writer.writerow([code, desc, self._round_to_whole_dollars(amount)])

            # PAYG fields (if applicable)
            if (
                self.calculation.w1_total_wages
                and Decimal(str(self.calculation.w1_total_wages)) > 0
            ):
                writer.writerow([])  # Blank row separator
                writer.writerow(
                    [
                        "W1",
                        "Total salary, wages and other payments",
                        self._round_to_whole_dollars(self.calculation.w1_total_wages),
                    ]
                )
                writer.writerow(
                    [
                        "W2",
                        "Amount withheld from payments shown at W1",
                        self._round_to_whole_dollars(self.calculation.w2_amount_withheld),
                    ]
                )

            # Summary section
            writer.writerow([])
            writer.writerow(["SUMMARY", "", ""])

            gst_payable = self._round_to_whole_dollars(self.calculation.gst_payable)
            if gst_payable >= 0:
                writer.writerow(["NET_GST", "Net GST payable", gst_payable])
            else:
                writer.writerow(["NET_GST", "GST refundable", abs(gst_payable)])

            if (
                self.calculation.w2_amount_withheld
                and Decimal(str(self.calculation.w2_amount_withheld)) > 0
            ):
                writer.writerow(
                    [
                        "PAYG",
                        "PAYG withholding",
                        self._round_to_whole_dollars(self.calculation.w2_amount_withheld),
                    ]
                )

            total = self._round_to_whole_dollars(self.calculation.total_payable)
            if total >= 0:
                writer.writerow(["TOTAL", "Total amount payable to ATO", total])
            else:
                writer.writerow(["TOTAL", "Total refund from ATO", abs(total)])

        # Convert to bytes with UTF-8 BOM for Excel compatibility
        csv_content = output.getvalue()
        # Add BOM for Excel to recognize UTF-8
        return ("\ufeff" + csv_content).encode("utf-8")
