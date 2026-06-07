"""BAS calculation engines for GST and PAYG.

This module provides:
- GSTCalculator: Calculates GST figures from invoices and bank transactions
- PAYGCalculator: Aggregates PAYG withholding from pay runs
"""

import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.integrations.xero.models import (
    XeroBankTransaction,
    XeroConnection,
    XeroCreditNote,
    XeroCreditNoteStatus,
    XeroCreditNoteType,
    XeroInvoice,
    XeroPayment,
    XeroPayRun,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Tax Type Mapping
# =============================================================================

# Xero tax type → BAS field mapping
# See: https://developer.xero.com/documentation/api/accounting/types#tax-types

TAX_TYPE_MAPPING = {
    # GST on sales (1A)
    "OUTPUT": {"field": "1a", "gst": True, "sales": True},
    "OUTPUT2": {"field": "1a", "gst": True, "sales": True},
    "OUTPUTSALES": {"field": "1a", "gst": True, "sales": True},
    # GST on purchases (1B)
    "INPUT": {"field": "1b", "gst": True, "purchases": True},
    "INPUT2": {"field": "1b", "gst": True, "purchases": True},
    "INPUT3": {"field": "1b", "gst": True, "purchases": True},
    "INPUTTAXED": {"field": "1b", "gst": True, "purchases": True},
    # Capital purchases (G10 + 1B)
    "CAPEXINPUT": {"field": "g10", "gst": True, "capital": True},
    "CAPEXINPUT2": {"field": "g10", "gst": True, "capital": True},
    # GST-free sales (G3)
    "EXEMPTOUTPUT": {"field": "g3", "gst": False, "sales": True},
    "EXEMPTINCOME": {"field": "g3", "gst": False, "sales": True},
    # GST-free purchases
    "EXEMPTEXPENSES": {"field": "g11", "gst": False, "purchases": True},
    # Export sales (G2)
    "EXEMPTEXPORT": {"field": "g2", "gst": False, "exports": True},
    "GSTONEXPORTS": {"field": "g2", "gst": False, "exports": True},
    # Zero-rated (no GST but reported)
    "ZERORATEDINPUT": {"field": "g11", "gst": False, "purchases": True},
    "ZERORATEDOUTPUT": {"field": "g1", "gst": False, "sales": True},
    # Excluded from BAS
    "BASEXCLUDED": {"field": "excluded", "gst": False},
    "NONE": {"field": "excluded", "gst": False},
    "NONGST": {"field": "excluded", "gst": False},
}


@dataclass
class GSTResult:
    """Result of GST calculation."""

    # G-fields
    g1_total_sales: Decimal = Decimal("0")
    g2_export_sales: Decimal = Decimal("0")
    g3_gst_free_sales: Decimal = Decimal("0")
    g10_capital_purchases: Decimal = Decimal("0")
    g11_non_capital_purchases: Decimal = Decimal("0")

    # Calculated GST fields
    field_1a_gst_on_sales: Decimal = Decimal("0")
    field_1b_gst_on_purchases: Decimal = Decimal("0")
    gst_payable: Decimal = Decimal("0")

    # Credit note adjustments (Spec 024)
    # These are subtracted from totals as they reduce taxable amounts
    sales_credit_notes: Decimal = Decimal("0")  # Reduces G1 and 1A
    sales_credit_notes_gst: Decimal = Decimal("0")
    purchase_credit_notes: Decimal = Decimal("0")  # Reduces purchases and 1B
    purchase_credit_notes_gst: Decimal = Decimal("0")

    # Metadata
    invoice_count: int = 0
    transaction_count: int = 0
    credit_note_count: int = 0

    # Excluded items tracking (Spec 046)
    excluded_items: list[dict[str, Any]] = field(default_factory=list)

    def calculate_gst_payable(self) -> None:
        """Calculate net GST (1A - 1B).

        Credit notes reduce the GST amounts:
        - Sales credit notes reduce GST collected (1A)
        - Purchase credit notes reduce input tax credits (1B)
        """
        net_1a = self.field_1a_gst_on_sales - self.sales_credit_notes_gst
        net_1b = self.field_1b_gst_on_purchases - self.purchase_credit_notes_gst
        self.gst_payable = net_1a - net_1b

    @property
    def net_gst_on_sales(self) -> Decimal:
        """GST on sales after credit note adjustments."""
        return self.field_1a_gst_on_sales - self.sales_credit_notes_gst

    @property
    def net_gst_on_purchases(self) -> Decimal:
        """GST on purchases after credit note adjustments."""
        return self.field_1b_gst_on_purchases - self.purchase_credit_notes_gst

    @property
    def net_total_sales(self) -> Decimal:
        """Total sales after credit note adjustments."""
        return self.g1_total_sales - self.sales_credit_notes

    @property
    def is_refund(self) -> bool:
        """True if GST is a refund (1B > 1A)."""
        return self.gst_payable < 0


@dataclass
class PAYGResult:
    """Result of PAYG calculation."""

    w1_total_wages: Decimal = Decimal("0")
    w2_amount_withheld: Decimal = Decimal("0")
    pay_run_count: int = 0
    has_payroll: bool = False
    # Spec 062: source label and draft run count for UI display
    source_label: str = ""
    draft_pay_run_count: int = 0


class GSTCalculator:
    """Calculates GST fields from Xero invoices and bank transactions."""

    def __init__(
        self,
        session: AsyncSession,
        overrides: dict[tuple[str, str, int], str] | None = None,
    ):
        self.session = session
        # Overrides: {(source_type, source_id, line_item_index): tax_type}
        self._overrides = overrides or {}

    async def calculate(
        self,
        connection_id: UUID,
        start_date: date,
        end_date: date,
        gst_basis: str = "accrual",
    ) -> GSTResult:
        """Calculate GST figures for a period.

        Args:
            connection_id: Xero connection ID
            start_date: Period start date
            end_date: Period end date
            gst_basis: 'accrual' (default) filters by issue_date;
                       'cash' filters by payment_date via XeroPayment join

        Returns:
            GSTResult with all calculated fields
        """
        result = GSTResult()

        # Process invoices (basis-aware)
        invoices = await self._get_invoices(connection_id, start_date, end_date, gst_basis)
        result.invoice_count = len(invoices)
        self._process_invoices(invoices, result)

        # Process bank transactions (always by transaction_date)
        transactions = await self._get_transactions(connection_id, start_date, end_date)
        result.transaction_count = len(transactions)
        self._process_transactions(transactions, result)

        # Process credit notes (basis-aware)
        credit_notes = await self._get_credit_notes(connection_id, start_date, end_date, gst_basis)
        result.credit_note_count = len(credit_notes)
        self._process_credit_notes(credit_notes, result)

        # Calculate net GST
        result.calculate_gst_payable()

        logger.info(
            f"GST calculated for {connection_id} (basis={gst_basis}): "
            f"1A=${result.field_1a_gst_on_sales} (net: ${result.net_gst_on_sales}), "
            f"1B=${result.field_1b_gst_on_purchases} (net: ${result.net_gst_on_purchases}), "
            f"Net=${result.gst_payable}, "
            f"credit_notes={result.credit_note_count}"
        )

        return result

    async def _get_invoices(
        self,
        connection_id: UUID,
        start_date: date,
        end_date: date,
        gst_basis: str = "accrual",
    ) -> list[XeroInvoice]:
        """Get invoices for the period.

        Accrual basis: filter by issue_date (when the invoice was raised).
        Cash basis: filter by XeroPayment.payment_date (when the invoice was paid).

        Cash basis correctly uses XeroPayment.payment_date via a join — NOT invoice_date.
        ATO cash basis requires recognising GST when payment is received/made, which
        payment_date represents.
        """
        from sqlalchemy import cast
        from sqlalchemy.dialects.postgresql import DATE

        if gst_basis == "cash":
            # Cash basis: join to payments, filter by payment_date (ATO requirement)
            stmt = (
                select(XeroInvoice)
                .join(
                    XeroPayment,
                    XeroInvoice.xero_invoice_id == XeroPayment.xero_invoice_id,
                )
                .where(
                    XeroInvoice.connection_id == connection_id,
                    cast(XeroPayment.payment_date, DATE) >= start_date,
                    cast(XeroPayment.payment_date, DATE) <= end_date,
                    XeroInvoice.status.in_(["authorised", "paid"]),
                    XeroPayment.connection_id == connection_id,
                )
                .distinct()
            )
        else:
            # Accrual basis (default): filter by issue_date
            stmt = select(XeroInvoice).where(
                XeroInvoice.connection_id == connection_id,
                XeroInvoice.issue_date >= start_date,
                XeroInvoice.issue_date <= end_date,
                XeroInvoice.status.in_(["authorised", "paid"]),
            )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _get_transactions(
        self,
        connection_id: UUID,
        start_date: date,
        end_date: date,
    ) -> list[XeroBankTransaction]:
        """Get bank transactions for the period."""
        result = await self.session.execute(
            select(XeroBankTransaction).where(
                XeroBankTransaction.connection_id == connection_id,
                XeroBankTransaction.transaction_date >= start_date,
                XeroBankTransaction.transaction_date <= end_date,
                # Only include authorised transactions
                XeroBankTransaction.status == "AUTHORISED",
            )
        )
        return list(result.scalars().all())

    async def _get_credit_notes(
        self,
        connection_id: UUID,
        start_date: date,
        end_date: date,
        gst_basis: str = "accrual",
    ) -> list[XeroCreditNote]:
        """Get credit notes for the period (Spec 024).

        Accrual basis: filter by issue_date.
        Cash basis: filter by issue_date (credit notes are always recognised on issue date
        as they are not payment-dependent — this matches ATO cash basis guidance).
        """
        # Credit notes are filtered by issue_date regardless of basis
        # (credit notes don't have a separate payment date; they are adjustments)
        result = await self.session.execute(
            select(XeroCreditNote).where(
                XeroCreditNote.connection_id == connection_id,
                XeroCreditNote.issue_date >= start_date,
                XeroCreditNote.issue_date <= end_date,
                # Only include authorised/paid credit notes
                XeroCreditNote.status.in_(
                    [
                        XeroCreditNoteStatus.AUTHORISED,
                        XeroCreditNoteStatus.PAID,
                    ]
                ),
            )
        )
        return list(result.scalars().all())

    def _process_credit_notes(
        self,
        credit_notes: list[XeroCreditNote],
        result: GSTResult,
    ) -> None:
        """Process credit notes and add adjustments to result (Spec 024).

        Credit notes reduce the corresponding GST amounts:
        - ACCRECCREDIT (sales credit notes): Reduce GST collected (1A)
        - ACCPAYCREDIT (purchase credit notes): Reduce input tax credits (1B)
        """
        for credit_note in credit_notes:
            amount = Decimal(str(credit_note.total_amount or 0))
            tax = Decimal(str(credit_note.tax_amount or 0))

            if credit_note.credit_note_type == XeroCreditNoteType.ACCRECCREDIT:
                # Sales credit note - reduces GST on sales
                result.sales_credit_notes += amount
                result.sales_credit_notes_gst += tax
            elif credit_note.credit_note_type == XeroCreditNoteType.ACCPAYCREDIT:
                # Purchase credit note - reduces GST on purchases
                result.purchase_credit_notes += amount
                result.purchase_credit_notes_gst += tax

    def _process_invoices(self, invoices: list[XeroInvoice], result: GSTResult) -> None:
        """Process invoices and add to result.

        For sales invoices (ACCREC), we use invoice-level totals to avoid
        issues with tax-inclusive vs tax-exclusive line amounts.
        For purchase invoices (ACCPAY), we process line items to distinguish
        between capital (G10) and non-capital (G11) purchases.
        """
        for invoice in invoices:
            is_sales = invoice.invoice_type.value == "accrec"

            if is_sales:
                # For sales, always use invoice-level totals
                # This correctly handles both tax-inclusive and tax-exclusive invoices
                self._add_invoice_level_tax(invoice, result)
            else:
                # For purchases, process line items to categorize G10 vs G11
                line_items = invoice.line_items or []
                if not line_items:
                    self._add_invoice_level_tax(invoice, result)
                else:
                    for idx, item in enumerate(line_items):
                        self._process_line_item(item, invoice, result, line_item_index=idx)

    def _add_invoice_level_tax(self, invoice: XeroInvoice, result: GSTResult) -> None:
        """Add tax from invoice-level totals when no line items."""
        # Determine if sales (ACCREC) or purchases (ACCPAY)
        is_sales = invoice.invoice_type.value == "accrec"
        amount = Decimal(str(invoice.total_amount or 0))
        tax = Decimal(str(invoice.tax_amount or 0))

        if is_sales:
            result.g1_total_sales += amount
            result.field_1a_gst_on_sales += tax
        else:
            result.g11_non_capital_purchases += amount - tax
            result.field_1b_gst_on_purchases += tax

    def _process_line_item(
        self,
        item: dict[str, Any],
        _invoice: XeroInvoice,
        result: GSTResult,
        *,
        line_item_index: int = 0,
    ) -> None:
        """Process a single line item.

        Note: _invoice is kept to provide source context for excluded item tracking.
        """
        # Try both snake_case (our storage format) and CamelCase (Xero API format)
        tax_type = str(item.get("tax_type") or item.get("TaxType", "NONE")).upper()
        line_amount = Decimal(str(item.get("line_amount") or item.get("LineAmount", 0)))
        tax_amount = Decimal(str(item.get("tax_amount") or item.get("TaxAmount", 0)))

        # Check for overrides (Spec 046)
        if self._overrides:
            override_key = ("invoice", str(_invoice.id), line_item_index)
            if override_key in self._overrides:
                tax_type = self._overrides[override_key]

        # Get mapping for this tax type
        mapping = TAX_TYPE_MAPPING.get(tax_type, {"field": "excluded", "gst": False})

        # Track excluded items instead of silently dropping (Spec 046)
        if mapping["field"] == "excluded":
            result.excluded_items.append(
                {
                    "source_type": "invoice",
                    "source_id": str(_invoice.id),
                    "line_item_index": line_item_index,
                    "line_item_id": item.get("line_item_id") or item.get("LineItemID"),
                    "tax_type": tax_type,
                    "line_amount": float(line_amount),
                    "tax_amount": float(tax_amount),
                    "account_code": item.get("account_code") or item.get("AccountCode"),
                    "description": item.get("description") or item.get("Description"),
                }
            )
            return

        # Add to appropriate field based on tax type mapping
        if mapping["field"] == "1a":
            result.g1_total_sales += line_amount + tax_amount
            result.field_1a_gst_on_sales += tax_amount
        elif mapping["field"] == "1b":
            result.g11_non_capital_purchases += line_amount
            result.field_1b_gst_on_purchases += tax_amount
        elif mapping["field"] == "g10":
            result.g10_capital_purchases += line_amount
            result.field_1b_gst_on_purchases += tax_amount
        elif mapping["field"] == "g2":
            result.g2_export_sales += line_amount
        elif mapping["field"] == "g3":
            result.g3_gst_free_sales += line_amount
        elif mapping["field"] == "g11":
            result.g11_non_capital_purchases += line_amount
        elif mapping["field"] == "g1":
            result.g1_total_sales += line_amount

    def _process_transactions(
        self,
        transactions: list[XeroBankTransaction],
        result: GSTResult,
    ) -> None:
        """Process bank transactions and add to result."""
        for txn in transactions:
            line_items = txn.line_items or []

            if not line_items:
                # No line items, use transaction-level amount
                self._add_transaction_level(txn, result)
            else:
                # Process line items
                for idx, item in enumerate(line_items):
                    self._process_transaction_line_item(item, txn, result, line_item_index=idx)

    def _add_transaction_level(
        self,
        txn: XeroBankTransaction,
        result: GSTResult,
    ) -> None:
        """Add from transaction-level when no line items."""
        amount = Decimal(str(txn.total_amount or 0))
        # Bank transactions typically don't have separate tax field at top level
        # The amount is inclusive of any tax

        if txn.transaction_type.value == "receive":
            result.g1_total_sales += amount
        else:
            result.g11_non_capital_purchases += amount

    def _process_transaction_line_item(
        self,
        item: dict[str, Any],
        txn: XeroBankTransaction,
        result: GSTResult,
        *,
        line_item_index: int = 0,
    ) -> None:
        """Process a single bank transaction line item."""
        # Try both snake_case (our storage format) and CamelCase (Xero API format)
        tax_type = str(item.get("tax_type") or item.get("TaxType", "NONE")).upper()
        line_amount = Decimal(str(item.get("line_amount") or item.get("LineAmount", 0)))
        tax_amount = Decimal(str(item.get("tax_amount") or item.get("TaxAmount", 0)))

        # Check for overrides (Spec 046)
        if self._overrides:
            override_key = ("bank_transaction", str(txn.id), line_item_index)
            if override_key in self._overrides:
                tax_type = self._overrides[override_key]

        mapping = TAX_TYPE_MAPPING.get(tax_type, {"field": "excluded", "gst": False})

        if mapping["field"] == "excluded":
            result.excluded_items.append(
                {
                    "source_type": "bank_transaction",
                    "source_id": str(txn.id),
                    "line_item_index": line_item_index,
                    "line_item_id": item.get("line_item_id") or item.get("LineItemID"),
                    "tax_type": tax_type,
                    "line_amount": float(line_amount),
                    "tax_amount": float(tax_amount),
                    "account_code": item.get("account_code") or item.get("AccountCode"),
                    "description": item.get("description") or item.get("Description"),
                }
            )
            return

        # For bank transactions, receive = sales, spend = purchases
        is_receive = txn.transaction_type.value == "receive"

        if mapping["field"] == "1a" and is_receive:
            result.g1_total_sales += line_amount + tax_amount
            result.field_1a_gst_on_sales += tax_amount
        elif mapping["field"] == "1b" and not is_receive:
            result.g11_non_capital_purchases += line_amount
            result.field_1b_gst_on_purchases += tax_amount
        elif mapping["field"] == "g10" and not is_receive:
            result.g10_capital_purchases += line_amount
            result.field_1b_gst_on_purchases += tax_amount
        elif mapping["field"] == "g2" and is_receive:
            result.g2_export_sales += line_amount
        elif mapping["field"] == "g3":
            if is_receive:
                result.g3_gst_free_sales += line_amount
            else:
                result.g11_non_capital_purchases += line_amount


class PAYGCalculator:
    """Calculates PAYG withholding from pay runs."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def calculate(
        self,
        connection_id: UUID,
        start_date: date,
        end_date: date,
    ) -> PAYGResult:
        """Calculate PAYG figures for a period.

        Args:
            connection_id: Xero connection ID
            start_date: Period start date
            end_date: Period end date

        Returns:
            PAYGResult with W1 and W2 totals
        """
        # Check if connection has payroll access
        connection = await self._get_connection(connection_id)
        if not connection or not connection.has_payroll_access:
            return PAYGResult(has_payroll=False)

        # Get finalised (posted) and draft pay runs separately
        pay_runs = await self._get_pay_runs(
            connection_id, start_date, end_date, finalised_only=True
        )
        draft_runs = await self._get_pay_runs(
            connection_id, start_date, end_date, finalised_only=False
        )
        draft_pay_run_count = max(0, len(draft_runs) - len(pay_runs))

        if not pay_runs:
            source_label = f"From Xero Payroll — {start_date.strftime('%-d %b %Y')} to {end_date.strftime('%-d %b %Y')}"
            return PAYGResult(
                has_payroll=True,
                source_label=source_label,
                draft_pay_run_count=draft_pay_run_count,
            )

        # Aggregate totals from finalised pay runs only
        w1_total = Decimal("0")
        w2_total = Decimal("0")

        for pay_run in pay_runs:
            w1_total += Decimal(str(pay_run.total_wages or 0))
            w2_total += Decimal(str(pay_run.total_tax or 0))

        source_label = f"From Xero Payroll — {start_date.strftime('%-d %b %Y')} to {end_date.strftime('%-d %b %Y')}"

        result = PAYGResult(
            w1_total_wages=w1_total,
            w2_amount_withheld=w2_total,
            pay_run_count=len(pay_runs),
            has_payroll=True,
            source_label=source_label,
            draft_pay_run_count=draft_pay_run_count,
        )

        logger.info(
            f"PAYG calculated for {connection_id}: "
            f"W1=${result.w1_total_wages}, W2=${result.w2_amount_withheld}, "
            f"pay_runs={result.pay_run_count}"
        )

        return result

    async def _get_connection(self, connection_id: UUID) -> XeroConnection | None:
        """Get connection to check payroll access."""
        result = await self.session.execute(
            select(XeroConnection).where(XeroConnection.id == connection_id)
        )
        return result.scalar_one_or_none()

    async def _get_pay_runs(
        self,
        connection_id: UUID,
        start_date: date,
        end_date: date,
        finalised_only: bool = True,
    ) -> list[XeroPayRun]:
        """Get pay runs for the period.

        finalised_only=True: only "posted" (finalised) pay runs populate W1/W2.
        finalised_only=False: returns all pay runs (used to count draft runs).
        """
        from app.modules.integrations.xero.models import XeroPayRunStatus

        filters = [
            XeroPayRun.connection_id == connection_id,
            XeroPayRun.payment_date >= start_date,
            XeroPayRun.payment_date <= end_date,
        ]
        if finalised_only:
            filters.append(XeroPayRun.pay_run_status == XeroPayRunStatus.POSTED)

        result = await self.session.execute(select(XeroPayRun).where(*filters))
        return list(result.scalars().all())
