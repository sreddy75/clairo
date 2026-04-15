"""Data transformers for Xero API responses.

Transforms Xero API response data into Clairo model format.
Includes ABN validation and field mapping.
"""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from app.modules.integrations.xero.models import (
    XeroAccountClass,
    XeroContactType,
    XeroCreditNoteStatus,
    XeroCreditNoteType,
    XeroInvoiceStatus,
    XeroInvoiceType,
    XeroJournalSourceType,
    XeroManualJournalStatus,
    XeroOverpaymentStatus,
    XeroPaymentStatus,
    XeroPaymentType,
    XeroPrepaymentStatus,
)

# =============================================================================
# ABN Validator (Task 17)
# =============================================================================


def validate_abn(abn: str | None) -> str | None:
    """Validate and clean an Australian Business Number.

    Implements the official ABN validation algorithm:
    1. Subtract 1 from the first digit
    2. Multiply each digit by its weighting factor
    3. Sum the results
    4. If divisible by 89, ABN is valid

    Args:
        abn: The ABN string to validate (may contain spaces/dashes).

    Returns:
        Cleaned 11-digit ABN if valid, None otherwise.
    """
    if not abn:
        return None

    # Remove non-digit characters
    cleaned = re.sub(r"\D", "", abn)

    # Must be exactly 11 digits
    if len(cleaned) != 11:
        return None

    # ABN weighting factors
    weights = [10, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19]

    # Convert to list of integers
    digits = [int(d) for d in cleaned]

    # Subtract 1 from first digit
    digits[0] -= 1

    # Calculate weighted sum
    total = sum(d * w for d, w in zip(digits, weights, strict=False))

    # Valid if divisible by 89
    if total % 89 == 0:
        return cleaned

    return None


# =============================================================================
# Contact Transformer (Task 18)
# =============================================================================


class ContactTransformer:
    """Transforms Xero Contact API response to XeroClient format."""

    @staticmethod
    def transform(xero_contact: dict[str, Any]) -> dict[str, Any]:
        """Transform a Xero contact to XeroClient data.

        Args:
            xero_contact: Contact data from Xero API.

        Returns:
            Dict suitable for XeroClient model.
        """
        # Determine contact type based on IsCustomer/IsSupplier flags
        is_customer = xero_contact.get("IsCustomer", False)
        is_supplier = xero_contact.get("IsSupplier", False)

        if is_customer and is_supplier:
            contact_type = XeroContactType.BOTH
        elif is_supplier:
            contact_type = XeroContactType.SUPPLIER
        else:
            contact_type = XeroContactType.CUSTOMER

        # Map contact status to is_active
        status = xero_contact.get("ContactStatus", "ACTIVE")
        is_active = status == "ACTIVE"

        # Extract and validate ABN from TaxNumber
        raw_abn = xero_contact.get("TaxNumber")
        abn = validate_abn(raw_abn)

        # Extract primary email
        email = xero_contact.get("EmailAddress")

        # Extract first phone number
        phones = xero_contact.get("Phones", [])
        contact_number = None
        if phones:
            for phone in phones:
                number = phone.get("PhoneNumber")
                if number:
                    contact_number = number
                    break

        # Transform addresses
        addresses = ContactTransformer._transform_addresses(xero_contact.get("Addresses", []))

        # Transform phones
        phone_list = ContactTransformer._transform_phones(phones)

        # Parse updated date
        xero_updated_at = ContactTransformer._parse_xero_date(xero_contact.get("UpdatedDateUTC"))

        return {
            "xero_contact_id": xero_contact["ContactID"],
            "name": xero_contact.get("Name", "Unknown"),
            "email": email,
            "contact_number": contact_number,
            "abn": abn,
            "contact_type": contact_type,
            "is_active": is_active,
            "addresses": addresses if addresses else None,
            "phones": phone_list if phone_list else None,
            "xero_updated_at": xero_updated_at,
        }

    @staticmethod
    def _transform_addresses(addresses: list[dict]) -> list[dict[str, Any]]:
        """Transform Xero addresses to simplified format."""
        result = []
        for addr in addresses:
            if not any(
                [
                    addr.get("AddressLine1"),
                    addr.get("City"),
                    addr.get("PostalCode"),
                ]
            ):
                continue

            result.append(
                {
                    "type": addr.get("AddressType", "UNKNOWN"),
                    "line1": addr.get("AddressLine1"),
                    "line2": addr.get("AddressLine2"),
                    "line3": addr.get("AddressLine3"),
                    "line4": addr.get("AddressLine4"),
                    "city": addr.get("City"),
                    "region": addr.get("Region"),
                    "postal_code": addr.get("PostalCode"),
                    "country": addr.get("Country"),
                }
            )
        return result

    @staticmethod
    def _transform_phones(phones: list[dict]) -> list[dict[str, Any]]:
        """Transform Xero phones to simplified format."""
        result = []
        for phone in phones:
            number = phone.get("PhoneNumber")
            if not number:
                continue

            result.append(
                {
                    "type": phone.get("PhoneType", "UNKNOWN"),
                    "country_code": phone.get("PhoneCountryCode"),
                    "area_code": phone.get("PhoneAreaCode"),
                    "number": number,
                }
            )
        return result

    @staticmethod
    def _parse_xero_date(date_str: str | None) -> datetime | None:
        """Parse Xero's date format to datetime.

        Xero returns dates like: /Date(1234567890000)/
        or ISO format: 2024-01-15T10:30:00
        """
        if not date_str:
            return None

        # Handle Xero's /Date(...)/ format
        match = re.search(r"/Date\((\d+)", date_str)
        if match:
            timestamp_ms = int(match.group(1))
            return datetime.utcfromtimestamp(timestamp_ms / 1000)

        # Try ISO format
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None


# =============================================================================
# Invoice Transformer (Task 19)
# =============================================================================


class InvoiceTransformer:
    """Transforms Xero Invoice API response to XeroInvoice format."""

    # Map Xero invoice types to our enum
    TYPE_MAP = {
        "ACCREC": XeroInvoiceType.ACCREC,
        "ACCPAY": XeroInvoiceType.ACCPAY,
    }

    # Map Xero invoice statuses to our enum
    STATUS_MAP = {
        "DRAFT": XeroInvoiceStatus.DRAFT,
        "SUBMITTED": XeroInvoiceStatus.SUBMITTED,
        "AUTHORISED": XeroInvoiceStatus.AUTHORISED,
        "PAID": XeroInvoiceStatus.PAID,
        "VOIDED": XeroInvoiceStatus.VOIDED,
        "DELETED": XeroInvoiceStatus.DELETED,
    }

    @staticmethod
    def transform(xero_invoice: dict[str, Any]) -> dict[str, Any]:
        """Transform a Xero invoice to XeroInvoice data.

        Args:
            xero_invoice: Invoice data from Xero API.

        Returns:
            Dict suitable for XeroInvoice model.
        """
        # Map type and status
        invoice_type = InvoiceTransformer.TYPE_MAP.get(
            xero_invoice.get("Type", "ACCREC"),
            XeroInvoiceType.ACCREC,
        )
        status = InvoiceTransformer.STATUS_MAP.get(
            xero_invoice.get("Status", "DRAFT"),
            XeroInvoiceStatus.DRAFT,
        )

        # Extract contact ID
        contact = xero_invoice.get("Contact", {})
        xero_contact_id = contact.get("ContactID")

        # Parse dates
        issue_date = InvoiceTransformer._parse_date(xero_invoice.get("Date"))
        due_date = InvoiceTransformer._parse_date(xero_invoice.get("DueDate"))
        xero_updated_at = ContactTransformer._parse_xero_date(xero_invoice.get("UpdatedDateUTC"))

        # Extract monetary values
        subtotal = Decimal(str(xero_invoice.get("SubTotal", 0)))
        tax_amount = Decimal(str(xero_invoice.get("TotalTax", 0)))
        total_amount = Decimal(str(xero_invoice.get("Total", 0)))

        # Transform line items
        line_items = InvoiceTransformer._transform_line_items(xero_invoice.get("LineItems", []))

        return {
            "xero_invoice_id": xero_invoice["InvoiceID"],
            "xero_contact_id": xero_contact_id,
            "invoice_number": xero_invoice.get("InvoiceNumber"),
            "invoice_type": invoice_type,
            "status": status,
            "issue_date": issue_date or datetime.utcnow(),
            "due_date": due_date,
            "subtotal": subtotal,
            "tax_amount": tax_amount,
            "total_amount": total_amount,
            "currency": xero_invoice.get("CurrencyCode", "AUD"),
            "line_items": line_items if line_items else None,
            "xero_updated_at": xero_updated_at,
        }

    @staticmethod
    def _parse_date(date_str: str | None) -> datetime | None:
        """Parse Xero date to datetime."""
        return ContactTransformer._parse_xero_date(date_str)

    @staticmethod
    def _transform_line_items(items: list[dict]) -> list[dict[str, Any]]:
        """Transform invoice line items preserving BAS-relevant data."""
        result = []
        for item in items:
            result.append(
                {
                    "line_item_id": item.get("LineItemID"),
                    "description": item.get("Description"),
                    "quantity": float(item.get("Quantity", 0)),
                    "unit_amount": float(item.get("UnitAmount", 0)),
                    "line_amount": float(item.get("LineAmount", 0)),
                    "account_code": item.get("AccountCode"),
                    "tax_type": item.get("TaxType"),
                    "tax_amount": float(item.get("TaxAmount", 0)),
                }
            )
        return result


# =============================================================================
# Bank Transaction Transformer (Task 20)
# =============================================================================


class BankTransactionTransformer:
    """Transforms Xero BankTransaction API response to XeroBankTransaction format."""

    # Map Xero transaction types to lowercase
    TYPE_MAP = {
        "RECEIVE": "receive",
        "SPEND": "spend",
        "RECEIVE-OVERPAYMENT": "receive_overpayment",
        "SPEND-OVERPAYMENT": "spend_overpayment",
        "RECEIVE-PREPAYMENT": "receive_prepayment",
        "SPEND-PREPAYMENT": "spend_prepayment",
    }

    @staticmethod
    def transform(xero_transaction: dict[str, Any]) -> dict[str, Any]:
        """Transform a Xero bank transaction to XeroBankTransaction data.

        Args:
            xero_transaction: Transaction data from Xero API.

        Returns:
            Dict suitable for XeroBankTransaction model.
        """
        # Map transaction type
        raw_type = xero_transaction.get("Type", "RECEIVE")
        transaction_type = BankTransactionTransformer.TYPE_MAP.get(raw_type.upper(), "receive")

        # Extract contact ID
        contact = xero_transaction.get("Contact", {})
        xero_contact_id = contact.get("ContactID")

        # Extract bank account ID
        bank_account = xero_transaction.get("BankAccount", {})
        xero_bank_account_id = bank_account.get("AccountID")

        # Parse date
        transaction_date = ContactTransformer._parse_xero_date(xero_transaction.get("Date"))
        xero_updated_at = ContactTransformer._parse_xero_date(
            xero_transaction.get("UpdatedDateUTC")
        )

        # Extract monetary values
        subtotal = Decimal(str(xero_transaction.get("SubTotal", 0)))
        tax_amount = Decimal(str(xero_transaction.get("TotalTax", 0)))
        total_amount = Decimal(str(xero_transaction.get("Total", 0)))

        # Transform line items with GST data
        line_items = BankTransactionTransformer._transform_line_items(
            xero_transaction.get("LineItems", [])
        )

        return {
            "xero_transaction_id": xero_transaction["BankTransactionID"],
            "xero_contact_id": xero_contact_id,
            "xero_bank_account_id": xero_bank_account_id,
            "transaction_type": transaction_type,
            "status": xero_transaction.get("Status", "AUTHORISED"),
            "transaction_date": transaction_date or datetime.utcnow(),
            "reference": xero_transaction.get("Reference"),
            "subtotal": subtotal,
            "tax_amount": tax_amount,
            "total_amount": total_amount,
            "line_items": line_items if line_items else None,
            "xero_updated_at": xero_updated_at,
            "is_reconciled": xero_transaction.get("IsReconciled", False),
        }

    @staticmethod
    def _transform_line_items(items: list[dict]) -> list[dict[str, Any]]:
        """Transform transaction line items preserving GST data."""
        result = []
        for item in items:
            result.append(
                {
                    "line_item_id": item.get("LineItemID"),
                    "description": item.get("Description"),
                    "quantity": float(item.get("Quantity", 0)),
                    "unit_amount": float(item.get("UnitAmount", 0)),
                    "line_amount": float(item.get("LineAmount", 0)),
                    "account_code": item.get("AccountCode"),
                    "tax_type": item.get("TaxType"),
                    "tax_amount": float(item.get("TaxAmount", 0)),
                }
            )
        return result


# =============================================================================
# Account Transformer (Task 21)
# =============================================================================


class AccountTransformer:
    """Transforms Xero Account API response to XeroAccount format."""

    # Map Xero account classes to our enum
    CLASS_MAP = {
        "ASSET": XeroAccountClass.ASSET,
        "EQUITY": XeroAccountClass.EQUITY,
        "EXPENSE": XeroAccountClass.EXPENSE,
        "LIABILITY": XeroAccountClass.LIABILITY,
        "REVENUE": XeroAccountClass.REVENUE,
    }

    # Tax types that indicate BAS relevance
    BAS_RELEVANT_TAX_TYPES = {
        "OUTPUT",
        "OUTPUT2",  # GST on sales
        "INPUT",
        "INPUT2",  # GST on purchases
        "GSTONIMPORTS",  # GST on imports
        "CAPEXINPUT",  # GST on capital acquisitions
        "BASEXCLUDED",  # BAS excluded
        "PAYGW",  # PAYG withholding
    }

    # Account types that are BAS relevant
    BAS_RELEVANT_ACCOUNT_TYPES = {
        "PAYGLIABILITY",  # PAYG withholding liability
        "SUPERANNUATIONLIABILITY",  # Superannuation liability
    }

    @staticmethod
    def transform(xero_account: dict[str, Any]) -> dict[str, Any]:
        """Transform a Xero account to XeroAccount data.

        Args:
            xero_account: Account data from Xero API.

        Returns:
            Dict suitable for XeroAccount model.
        """
        # Map account class
        raw_class = xero_account.get("Class", "")
        account_class = AccountTransformer.CLASS_MAP.get(raw_class.upper())

        # Determine if BAS relevant
        tax_type = xero_account.get("TaxType", "")
        account_type = xero_account.get("Type", "")

        is_bas_relevant = (
            tax_type.upper() in AccountTransformer.BAS_RELEVANT_TAX_TYPES
            or account_type.upper() in AccountTransformer.BAS_RELEVANT_ACCOUNT_TYPES
        )

        # Map status to is_active
        status = xero_account.get("Status", "ACTIVE")
        is_active = status == "ACTIVE"

        return {
            "xero_account_id": xero_account["AccountID"],
            "account_code": xero_account.get("Code"),
            "account_name": xero_account.get("Name", "Unknown"),
            "account_type": account_type,
            "account_class": account_class,
            "default_tax_type": tax_type if tax_type else None,
            "is_active": is_active,
            "reporting_code": xero_account.get("ReportingCode"),
            "is_bas_relevant": is_bas_relevant,
        }


# =============================================================================
# Report Transformer (Spec 023)
# =============================================================================


def parse_xero_date(date_str: str | None) -> datetime | None:
    """Parse Xero's date format to datetime.

    Xero returns dates like: /Date(1234567890000)/
    or ISO format: 2024-01-15T10:30:00

    This is a standalone helper for report transformers.
    """
    return ContactTransformer._parse_xero_date(date_str)


class XeroReportTransformer:
    """Base transformer for Xero Report API responses.

    Provides common functionality for transforming Xero's report structure
    into a format suitable for our models.

    Xero report structure:
    {
        "Reports": [{
            "ReportID": "uuid",
            "ReportName": "Profit and Loss",
            "ReportType": "ProfitAndLoss",
            "ReportTitles": ["Title", "Date Range", "Basis"],
            "ReportDate": "2025-12-31",
            "UpdatedDateUTC": "/Date(1735689600000)/",
            "Rows": [
                {"RowType": "Header", "Cells": [...]},
                {"RowType": "Section", "Title": "Revenue", "Rows": [...]},
                {"RowType": "SummaryRow", "Cells": [...]}
            ]
        }]
    }
    """

    # Map report types to display names
    REPORT_TYPE_DISPLAY_NAMES = {
        "profit_and_loss": "Profit & Loss",
        "balance_sheet": "Balance Sheet",
        "aged_receivables_by_contact": "Aged Receivables",
        "aged_payables_by_contact": "Aged Payables",
        "trial_balance": "Trial Balance",
        "bank_summary": "Bank Summary",
        "budget_summary": "Budget Summary",
    }

    @staticmethod
    def extract_report_metadata(xero_response: dict[str, Any]) -> dict[str, Any]:
        """Extract metadata from a Xero report response.

        Args:
            xero_response: Full response from Xero Reports API.

        Returns:
            Dict with report metadata.
        """
        if not xero_response or "Reports" not in xero_response:
            return {}

        reports = xero_response.get("Reports", [])
        if not reports:
            return {}

        report = reports[0]

        return {
            "xero_report_id": report.get("ReportID"),
            "report_name": report.get("ReportName", "Unknown Report"),
            "report_titles": report.get("ReportTitles", []),
            "xero_updated_at": parse_xero_date(report.get("UpdatedDateUTC")),
        }

    @staticmethod
    def extract_rows(xero_response: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract the Rows array from a Xero report response.

        Args:
            xero_response: Full response from Xero Reports API.

        Returns:
            List of row dicts (preserves original structure).
        """
        if not xero_response or "Reports" not in xero_response:
            return []

        reports = xero_response.get("Reports", [])
        if not reports:
            return []

        return reports[0].get("Rows", [])

    @staticmethod
    def count_data_rows(rows: list[dict[str, Any]]) -> int:
        """Count the total number of data rows (excluding headers).

        Args:
            rows: Rows array from Xero report.

        Returns:
            Total count of Row-type entries.
        """
        count = 0
        for row in rows:
            if row.get("RowType") == "Row":
                count += 1
            # Recurse into sections
            if "Rows" in row:
                count += XeroReportTransformer.count_data_rows(row["Rows"])
        return count

    @staticmethod
    def find_section(rows: list[dict[str, Any]], title: str) -> dict[str, Any] | None:
        """Find a section by title.

        Args:
            rows: Rows array from Xero report.
            title: Section title to find (case-insensitive).

        Returns:
            Section row dict if found, None otherwise.
        """
        title_lower = title.lower()
        for row in rows:
            if row.get("RowType") == "Section":
                row_title = row.get("Title", "")
                if row_title.lower() == title_lower:
                    return row
        return None

    @staticmethod
    def extract_cell_value(row: dict[str, Any], cell_index: int, default: str = "0") -> str:
        """Extract a cell value from a row.

        Args:
            row: A row dict from the report.
            cell_index: Index of the cell to extract.
            default: Default value if cell not found.

        Returns:
            Cell value as string.
        """
        cells = row.get("Cells", [])
        if cell_index < len(cells):
            cell = cells[cell_index]
            return cell.get("Value", default) or default
        return default

    @staticmethod
    def parse_decimal(value: str | None) -> Decimal:
        """Parse a string value to Decimal, handling formatting.

        Args:
            value: String value (may contain commas, parentheses for negatives).

        Returns:
            Decimal value.
        """
        if not value:
            return Decimal("0.00")

        # Remove currency symbols and whitespace
        cleaned = re.sub(r"[^0-9.\-()]", "", value)

        # Handle parentheses for negatives: (123.45) -> -123.45
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = "-" + cleaned[1:-1]

        try:
            return Decimal(cleaned)
        except Exception:
            return Decimal("0.00")

    @staticmethod
    def find_summary_row(rows: list[dict[str, Any]], title_contains: str) -> dict[str, Any] | None:
        """Find a SummaryRow by title content.

        Args:
            rows: Rows array from Xero report.
            title_contains: Text that the first cell should contain.

        Returns:
            SummaryRow dict if found, None otherwise.
        """
        title_lower = title_contains.lower()
        for row in rows:
            if row.get("RowType") == "SummaryRow":
                cells = row.get("Cells", [])
                if cells:
                    first_cell = cells[0].get("Value", "")
                    if first_cell and title_lower in first_cell.lower():
                        return row
            # Recurse into sections
            if row.get("RowType") == "Section" and "Rows" in row:
                found = XeroReportTransformer.find_summary_row(row["Rows"], title_contains)
                if found:
                    return found
        return None

    @staticmethod
    def extract_summary(rows: list[dict[str, Any]], report_type: str) -> dict[str, Any]:
        """Extract summary metrics from report rows.

        This is a base implementation that returns an empty dict.
        Subclasses should override for specific report types.

        Args:
            rows: Rows array from Xero report.
            report_type: Type of report for specialized extraction.

        Returns:
            Dict of summary metrics.
        """
        # This base method returns empty dict.
        # Specialized extractors in subclasses or specific transformer classes
        # will implement actual extraction logic.
        return {}

    @staticmethod
    def get_display_name(report_type: str) -> str:
        """Get human-readable display name for report type.

        Args:
            report_type: Report type enum value.

        Returns:
            Display name string.
        """
        return XeroReportTransformer.REPORT_TYPE_DISPLAY_NAMES.get(
            report_type, report_type.replace("_", " ").title()
        )


class ProfitAndLossTransformer(XeroReportTransformer):
    """Transformer for Profit & Loss report data.

    Xero P&L structure:
    - Section: "Income" or "Revenue" (Trading Income, Other Income)
    - Section: "Less Cost of Sales"
    - SummaryRow: "Gross Profit"
    - Section: "Less Operating Expenses"
    - SummaryRow: "Total Operating Expenses"
    - SummaryRow: "Net Profit"
    """

    # Section titles to look for (Xero uses various labels)
    REVENUE_TITLES = ["income", "revenue", "trading income"]
    OTHER_INCOME_TITLES = ["other income", "other revenue"]
    COST_OF_SALES_TITLES = ["less cost of sales", "cost of sales", "cost of goods sold"]
    OPERATING_EXPENSES_TITLES = [
        "less operating expenses",
        "operating expenses",
        "expenses",
    ]

    @classmethod
    def extract_profit_and_loss_summary(
        cls,
        rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Extract P&L summary metrics from report rows.

        Parses Xero's row structure to extract:
        - Revenue components (trading income, other income)
        - Cost of sales
        - Operating expenses
        - Gross profit and net profit
        - Margin ratios

        Args:
            rows: Rows array from Xero P&L report response.

        Returns:
            Dict with P&L summary metrics matching ProfitAndLossSummary schema.
        """
        # Initialize values
        revenue = Decimal("0.00")
        other_income = Decimal("0.00")
        cost_of_sales = Decimal("0.00")
        operating_expenses = Decimal("0.00")

        # Find and extract section totals
        for row in rows:
            if row.get("RowType") != "Section":
                continue

            title = (row.get("Title") or "").lower()
            section_rows = row.get("Rows", [])

            # Check for revenue/income section
            if any(t in title for t in cls.REVENUE_TITLES):
                revenue = cls._extract_section_total(section_rows)

            # Check for other income section
            elif any(t in title for t in cls.OTHER_INCOME_TITLES):
                other_income = cls._extract_section_total(section_rows)

            # Check for cost of sales section
            elif any(t in title for t in cls.COST_OF_SALES_TITLES):
                cost_of_sales = cls._extract_section_total(section_rows)

            # Check for operating expenses section
            elif any(t in title for t in cls.OPERATING_EXPENSES_TITLES):
                operating_expenses = cls._extract_section_total(section_rows)

        # Calculate derived values
        total_income = revenue + other_income
        gross_profit = total_income - cost_of_sales
        total_expenses = cost_of_sales + operating_expenses
        operating_profit = gross_profit - operating_expenses

        # Try to get net profit from summary row (most accurate)
        net_profit_row = cls.find_summary_row(rows, "net profit")
        if net_profit_row:
            net_profit = cls.parse_decimal(cls.extract_cell_value(net_profit_row, 1))
        else:
            # Fall back to calculated value
            net_profit = operating_profit

        # Calculate ratios (as percentages, None if division by zero)
        gross_margin_pct = None
        net_margin_pct = None
        expense_ratio_pct = None

        if total_income > 0:
            gross_margin_pct = float((gross_profit / total_income * 100).quantize(Decimal("0.01")))
            net_margin_pct = float((net_profit / total_income * 100).quantize(Decimal("0.01")))
            expense_ratio_pct = float(
                (total_expenses / total_income * 100).quantize(Decimal("0.01"))
            )

        return {
            "revenue": float(revenue),
            "other_income": float(other_income),
            "total_income": float(total_income),
            "cost_of_sales": float(cost_of_sales),
            "gross_profit": float(gross_profit),
            "operating_expenses": float(operating_expenses),
            "total_expenses": float(total_expenses),
            "operating_profit": float(operating_profit),
            "net_profit": float(net_profit),
            "gross_margin_pct": gross_margin_pct,
            "net_margin_pct": net_margin_pct,
            "expense_ratio_pct": expense_ratio_pct,
        }

    @classmethod
    def _extract_section_total(cls, section_rows: list[dict[str, Any]]) -> Decimal:
        """Extract the total from a section's rows.

        Looks for a SummaryRow with "Total" in the first cell,
        or sums all Row values if no summary found.

        Args:
            section_rows: Rows within a Section.

        Returns:
            Decimal total for the section.
        """
        # First, look for a summary row with "Total"
        for row in section_rows:
            if row.get("RowType") == "SummaryRow":
                first_cell = cls.extract_cell_value(row, 0, "")
                if "total" in first_cell.lower():
                    # The value is typically in cell index 1
                    return cls.parse_decimal(cls.extract_cell_value(row, 1))

        # If no summary row, sum all Row entries
        total = Decimal("0.00")
        for row in section_rows:
            if row.get("RowType") == "Row":
                # Value is typically in cell index 1
                value = cls.parse_decimal(cls.extract_cell_value(row, 1))
                total += value

        return total


class BalanceSheetTransformer(XeroReportTransformer):
    """Transformer for Balance Sheet report data.

    Xero Balance Sheet structure:
    - Section: "Assets" with subsections "Current Assets", "Non-current Assets"
    - Section: "Liabilities" with subsections "Current Liabilities", "Non-current Liabilities"
    - Section: "Equity"
    """

    # Section titles to look for
    ASSETS_TITLES = ["assets", "total assets"]
    CURRENT_ASSETS_TITLES = ["current assets", "bank"]
    NON_CURRENT_ASSETS_TITLES = ["non-current assets", "fixed assets"]
    LIABILITIES_TITLES = ["liabilities", "total liabilities"]
    CURRENT_LIABILITIES_TITLES = ["current liabilities"]
    NON_CURRENT_LIABILITIES_TITLES = ["non-current liabilities"]
    EQUITY_TITLES = ["equity", "net assets"]

    @classmethod
    def extract_balance_sheet_summary(
        cls,
        rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Extract Balance Sheet summary metrics from report rows.

        Args:
            rows: Rows array from Xero Balance Sheet report response.

        Returns:
            Dict with Balance Sheet summary metrics.
        """
        current_assets = Decimal("0.00")
        non_current_assets = Decimal("0.00")
        current_liabilities = Decimal("0.00")
        non_current_liabilities = Decimal("0.00")
        equity = Decimal("0.00")

        for row in rows:
            if row.get("RowType") != "Section":
                continue

            title = (row.get("Title") or "").lower()
            section_rows = row.get("Rows", [])

            # Check for current assets
            if any(t in title for t in cls.CURRENT_ASSETS_TITLES):
                current_assets = cls._extract_section_total(section_rows)

            # Check for non-current assets
            elif any(t in title for t in cls.NON_CURRENT_ASSETS_TITLES):
                non_current_assets = cls._extract_section_total(section_rows)

            # Check for current liabilities
            elif any(t in title for t in cls.CURRENT_LIABILITIES_TITLES):
                current_liabilities = cls._extract_section_total(section_rows)

            # Check for non-current liabilities
            elif any(t in title for t in cls.NON_CURRENT_LIABILITIES_TITLES):
                non_current_liabilities = cls._extract_section_total(section_rows)

            # Check for equity
            elif any(t in title for t in cls.EQUITY_TITLES):
                equity = cls._extract_section_total(section_rows)

        # Calculate totals
        total_assets = current_assets + non_current_assets
        total_liabilities = current_liabilities + non_current_liabilities

        # Try to get total assets from summary row
        total_assets_row = cls.find_summary_row(rows, "total assets")
        if total_assets_row:
            total_assets = cls.parse_decimal(cls.extract_cell_value(total_assets_row, 1))

        # Try to get total liabilities from summary row
        total_liabilities_row = cls.find_summary_row(rows, "total liabilities")
        if total_liabilities_row:
            total_liabilities = cls.parse_decimal(cls.extract_cell_value(total_liabilities_row, 1))

        # Try to get equity from summary row
        equity_row = cls.find_summary_row(rows, "net assets")
        if equity_row:
            equity = cls.parse_decimal(cls.extract_cell_value(equity_row, 1))

        # Calculate ratios
        current_ratio = None
        debt_to_equity = None

        if current_liabilities > 0:
            current_ratio = float((current_assets / current_liabilities).quantize(Decimal("0.01")))

        if equity != 0:
            debt_to_equity = float((total_liabilities / abs(equity)).quantize(Decimal("0.01")))

        return {
            "current_assets": float(current_assets),
            "non_current_assets": float(non_current_assets),
            "total_assets": float(total_assets),
            "current_liabilities": float(current_liabilities),
            "non_current_liabilities": float(non_current_liabilities),
            "total_liabilities": float(total_liabilities),
            "equity": float(equity),
            "current_ratio": current_ratio,
            "debt_to_equity": debt_to_equity,
        }

    @classmethod
    def _extract_section_total(cls, section_rows: list[dict[str, Any]]) -> Decimal:
        """Extract the total from a section's rows."""
        for row in section_rows:
            if row.get("RowType") == "SummaryRow":
                first_cell = cls.extract_cell_value(row, 0, "")
                if "total" in first_cell.lower():
                    return cls.parse_decimal(cls.extract_cell_value(row, 1))

        total = Decimal("0.00")
        for row in section_rows:
            if row.get("RowType") == "Row":
                value = cls.parse_decimal(cls.extract_cell_value(row, 1))
                total += value
        return total


class AgedReceivablesTransformer(XeroReportTransformer):
    """Transformer for Aged Receivables report data.

    Xero Aged Receivables structure:
    - Header row with aging bucket columns (Current, 1-30, 31-60, 61-90, 90+, Total)
    - Row per contact with amounts in each bucket
    - SummaryRow with totals
    """

    # Aging bucket column indices (0 is contact name)
    BUCKET_INDICES = {
        "current": 1,
        "overdue_30": 2,
        "overdue_60": 3,
        "overdue_90": 4,
        "overdue_90_plus": 5,
        "total": 6,
    }

    # High-risk threshold
    HIGH_RISK_AMOUNT = Decimal("5000.00")

    @classmethod
    def extract_aged_receivables_summary(
        cls,
        rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Extract Aged Receivables summary metrics from report rows.

        Args:
            rows: Rows array from Xero Aged Receivables report response.

        Returns:
            Dict with Aged Receivables summary metrics.
        """
        current = Decimal("0.00")
        overdue_30 = Decimal("0.00")
        overdue_60 = Decimal("0.00")
        overdue_90 = Decimal("0.00")
        overdue_90_plus = Decimal("0.00")
        total = Decimal("0.00")
        high_risk_contacts: list[dict[str, Any]] = []

        # Find the summary row for totals
        summary_row = cls.find_summary_row(rows, "total")
        if summary_row:
            cells = summary_row.get("Cells", [])
            if len(cells) > 6:
                current = cls.parse_decimal(cells[1].get("Value"))
                overdue_30 = cls.parse_decimal(cells[2].get("Value"))
                overdue_60 = cls.parse_decimal(cells[3].get("Value"))
                overdue_90 = cls.parse_decimal(cells[4].get("Value"))
                overdue_90_plus = cls.parse_decimal(cells[5].get("Value"))
                total = cls.parse_decimal(cells[6].get("Value"))

        # Identify high-risk contacts (90+ days with amount > threshold)
        for row in rows:
            if row.get("RowType") == "Row":
                cells = row.get("Cells", [])
                if len(cells) > 5:
                    contact_name = cells[0].get("Value", "Unknown")
                    over_90_amount = cls.parse_decimal(cells[5].get("Value"))
                    if over_90_amount >= cls.HIGH_RISK_AMOUNT:
                        high_risk_contacts.append(
                            {
                                "name": contact_name,
                                "amount": float(over_90_amount),
                            }
                        )

        # Calculate overdue totals and percentage
        overdue_total = overdue_30 + overdue_60 + overdue_90 + overdue_90_plus
        overdue_pct = None
        if total > 0:
            overdue_pct = float((overdue_total / total * 100).quantize(Decimal("0.01")))

        return {
            "total": float(total),
            "current": float(current),
            "overdue_30": float(overdue_30),
            "overdue_60": float(overdue_60),
            "overdue_90": float(overdue_90),
            "overdue_90_plus": float(overdue_90_plus),
            "overdue_total": float(overdue_total),
            "overdue_pct": overdue_pct,
            "high_risk_contacts": high_risk_contacts,
        }


class AgedPayablesTransformer(XeroReportTransformer):
    """Transformer for Aged Payables report data.

    Similar structure to Aged Receivables but for creditors.
    """

    @classmethod
    def extract_aged_payables_summary(
        cls,
        rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Extract Aged Payables summary metrics from report rows.

        Args:
            rows: Rows array from Xero Aged Payables report response.

        Returns:
            Dict with Aged Payables summary metrics.
        """
        current = Decimal("0.00")
        overdue_30 = Decimal("0.00")
        overdue_60 = Decimal("0.00")
        overdue_90 = Decimal("0.00")
        overdue_90_plus = Decimal("0.00")
        total = Decimal("0.00")

        # Find the summary row for totals
        summary_row = cls.find_summary_row(rows, "total")
        if summary_row:
            cells = summary_row.get("Cells", [])
            if len(cells) > 6:
                current = cls.parse_decimal(cells[1].get("Value"))
                overdue_30 = cls.parse_decimal(cells[2].get("Value"))
                overdue_60 = cls.parse_decimal(cells[3].get("Value"))
                overdue_90 = cls.parse_decimal(cells[4].get("Value"))
                overdue_90_plus = cls.parse_decimal(cells[5].get("Value"))
                total = cls.parse_decimal(cells[6].get("Value"))

        # Calculate overdue totals
        overdue_total = overdue_30 + overdue_60 + overdue_90 + overdue_90_plus

        return {
            "total": float(total),
            "current": float(current),
            "overdue_30": float(overdue_30),
            "overdue_60": float(overdue_60),
            "overdue_90": float(overdue_90),
            "overdue_90_plus": float(overdue_90_plus),
            "overdue_total": float(overdue_total),
        }


class TrialBalanceTransformer(XeroReportTransformer):
    """Transformer for Trial Balance report data.

    Xero Trial Balance structure:
    - Header row with columns (Account, Debit, Credit)
    - Row per account with debit/credit amounts
    - SummaryRow with totals
    """

    @classmethod
    def extract_trial_balance_summary(
        cls,
        rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Extract Trial Balance summary metrics from report rows.

        Args:
            rows: Rows array from Xero Trial Balance report response.

        Returns:
            Dict with Trial Balance summary metrics.
        """
        total_debits = Decimal("0.00")
        total_credits = Decimal("0.00")
        account_count = 0

        # Find the summary row for totals
        summary_row = cls.find_summary_row(rows, "total")
        if summary_row:
            cells = summary_row.get("Cells", [])
            if len(cells) >= 3:
                total_debits = cls.parse_decimal(cells[1].get("Value"))
                total_credits = cls.parse_decimal(cells[2].get("Value"))

        # Count accounts
        for row in rows:
            if row.get("RowType") == "Row":
                account_count += 1

        # Check if balanced (debits should equal credits)
        is_balanced = abs(total_debits - total_credits) < Decimal("0.01")

        return {
            "total_debits": float(total_debits),
            "total_credits": float(total_credits),
            "is_balanced": is_balanced,
            "account_count": account_count,
        }


class BankSummaryTransformer(XeroReportTransformer):
    """Transformer for Bank Summary report data.

    Xero Bank Summary structure:
    - Header row with columns (Bank Account, Opening, Received, Spent, Closing)
    - Row per bank account
    - SummaryRow with totals
    """

    @classmethod
    def extract_bank_summary_summary(
        cls,
        rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Extract Bank Summary metrics from report rows.

        Args:
            rows: Rows array from Xero Bank Summary report response.

        Returns:
            Dict with Bank Summary metrics.
        """
        total_opening = Decimal("0.00")
        total_received = Decimal("0.00")
        total_spent = Decimal("0.00")
        total_closing = Decimal("0.00")
        account_count = 0

        # Find the summary row for totals
        summary_row = cls.find_summary_row(rows, "total")
        if summary_row:
            cells = summary_row.get("Cells", [])
            if len(cells) >= 5:
                total_opening = cls.parse_decimal(cells[1].get("Value"))
                total_received = cls.parse_decimal(cells[2].get("Value"))
                total_spent = cls.parse_decimal(cells[3].get("Value"))
                total_closing = cls.parse_decimal(cells[4].get("Value"))

        # Count bank accounts
        for row in rows:
            if row.get("RowType") == "Row":
                account_count += 1

        # Calculate net movement
        net_movement = total_received - total_spent

        return {
            "total_opening": float(total_opening),
            "total_received": float(total_received),
            "total_spent": float(total_spent),
            "total_closing": float(total_closing),
            "net_movement": float(net_movement),
            "account_count": account_count,
        }

    @classmethod
    def extract_per_account_summary(
        cls,
        rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Extract per-bank-account balances from Bank Summary rows.

        Recurses into Section rows because Xero Bank Summary nests
        data rows inside a Section container.

        Args:
            rows: Rows array from Xero Bank Summary report response.

        Returns:
            List of dicts with per-account opening/closing balances.
        """
        accounts = []
        for row in rows:
            # Recurse into sections — Xero wraps bank account rows
            # inside a Section RowType
            if row.get("RowType") == "Section" and "Rows" in row:
                accounts.extend(cls.extract_per_account_summary(row["Rows"]))
                continue
            if row.get("RowType") != "Row":
                continue
            cells = row.get("Cells", [])
            if len(cells) < 5:
                continue
            # Cell 0 = account name (may contain AccountID in Attributes)
            account_cell = cells[0]
            account_name = account_cell.get("Value", "Unknown")
            account_id = None
            for attr in account_cell.get("Attributes", []):
                if attr.get("Id") == "account" or attr.get("Name") == "account":
                    account_id = attr.get("Value")
                    break

            accounts.append(
                {
                    "account_name": account_name,
                    "account_id": account_id,
                    "opening_balance": float(cls.parse_decimal(cells[1].get("Value"))),
                    "cash_received": float(cls.parse_decimal(cells[2].get("Value"))),
                    "cash_spent": float(cls.parse_decimal(cells[3].get("Value"))),
                    "closing_balance": float(cls.parse_decimal(cells[4].get("Value"))),
                }
            )
        return accounts


# =============================================================================
# Credit Note, Payment, Journal Transformers (Spec 024)
# =============================================================================


class CreditNoteTransformer:
    """Transforms Xero CreditNote API response to XeroCreditNote format."""

    @staticmethod
    def transform(xero_credit_note: dict[str, Any]) -> dict[str, Any]:
        """Transform a Xero credit note to XeroCreditNote data.

        Args:
            xero_credit_note: Credit note data from Xero API.

        Returns:
            Dict suitable for XeroCreditNote model.
        """
        # Map credit note type
        type_str = xero_credit_note.get("Type", "ACCRECCREDIT")
        try:
            credit_note_type = XeroCreditNoteType(type_str)
        except ValueError:
            credit_note_type = XeroCreditNoteType.ACCRECCREDIT

        # Map status
        status_str = xero_credit_note.get("Status", "DRAFT")
        try:
            status = XeroCreditNoteStatus(status_str)
        except ValueError:
            status = XeroCreditNoteStatus.DRAFT

        # Parse dates
        issue_date = CreditNoteTransformer._parse_xero_date(xero_credit_note.get("Date"))
        due_date = CreditNoteTransformer._parse_xero_date(xero_credit_note.get("DueDate"))
        xero_updated_at = CreditNoteTransformer._parse_xero_date(
            xero_credit_note.get("UpdatedDateUTC")
        )

        # Parse amounts
        subtotal = Decimal(str(xero_credit_note.get("SubTotal", "0")))
        tax_amount = Decimal(str(xero_credit_note.get("TotalTax", "0")))
        total_amount = Decimal(str(xero_credit_note.get("Total", "0")))
        remaining_credit = Decimal(str(xero_credit_note.get("RemainingCredit", "0")))

        # Extract contact
        contact = xero_credit_note.get("Contact", {})
        xero_contact_id = contact.get("ContactID")

        # Transform line items
        line_items = CreditNoteTransformer._transform_line_items(
            xero_credit_note.get("LineItems", [])
        )

        return {
            "xero_credit_note_id": xero_credit_note["CreditNoteID"],
            "xero_contact_id": xero_contact_id,
            "credit_note_number": xero_credit_note.get("CreditNoteNumber"),
            "credit_note_type": credit_note_type,
            "status": status,
            "issue_date": issue_date or datetime.now(),
            "due_date": due_date,
            "subtotal": subtotal,
            "tax_amount": tax_amount,
            "total_amount": total_amount,
            "remaining_credit": remaining_credit,
            "currency": xero_credit_note.get("CurrencyCode", "AUD"),
            "line_items": line_items if line_items else None,
            "xero_updated_at": xero_updated_at,
        }

    @staticmethod
    def _transform_line_items(line_items: list[dict]) -> list[dict[str, Any]]:
        """Transform Xero line items to simplified format."""
        result = []
        for item in line_items:
            result.append(
                {
                    "line_item_id": item.get("LineItemID"),
                    "description": item.get("Description"),
                    "quantity": float(item.get("Quantity", 0)),
                    "unit_amount": float(item.get("UnitAmount", 0)),
                    "line_amount": float(item.get("LineAmount", 0)),
                    "account_code": item.get("AccountCode"),
                    "tax_type": item.get("TaxType"),
                    "tax_amount": float(item.get("TaxAmount", 0)),
                }
            )
        return result

    @staticmethod
    def _parse_xero_date(date_str: str | None) -> datetime | None:
        """Parse Xero date string to datetime."""
        if not date_str:
            return None
        try:
            if date_str.startswith("/Date("):
                # .NET JSON date format: /Date(1234567890000)/
                ms = int(date_str.replace("/Date(", "").replace(")/", "").split("+")[0])
                return datetime.fromtimestamp(ms / 1000)
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None


class CreditNoteAllocationTransformer:
    """Transforms Xero CreditNote Allocations to XeroCreditNoteAllocation format."""

    @staticmethod
    def transform(
        allocation: dict[str, Any],
        credit_note_id: str,
    ) -> dict[str, Any]:
        """Transform a credit note allocation.

        Args:
            allocation: Allocation data from Xero API.
            credit_note_id: Parent credit note ID.

        Returns:
            Dict suitable for XeroCreditNoteAllocation model.
        """
        # Get invoice info
        invoice = allocation.get("Invoice", {})
        applied_at = CreditNoteTransformer._parse_xero_date(allocation.get("Date"))

        return {
            "xero_allocation_id": allocation.get("AllocationID") or "",
            "xero_credit_note_id": credit_note_id,
            "xero_invoice_id": invoice.get("InvoiceID"),
            "amount": Decimal(str(allocation.get("Amount", "0"))),
            "applied_at": applied_at,
        }


class PaymentTransformer:
    """Transforms Xero Payment API response to XeroPayment format."""

    @staticmethod
    def transform(xero_payment: dict[str, Any]) -> dict[str, Any]:
        """Transform a Xero payment to XeroPayment data.

        Args:
            xero_payment: Payment data from Xero API.

        Returns:
            Dict suitable for XeroPayment model.
        """
        # Map payment type
        type_str = xero_payment.get("PaymentType", "ACCRECPAYMENT")
        try:
            payment_type = XeroPaymentType(type_str)
        except ValueError:
            payment_type = XeroPaymentType.ACCRECPAYMENT

        # Map status
        status_str = xero_payment.get("Status", "AUTHORISED")
        try:
            status = XeroPaymentStatus(status_str)
        except ValueError:
            status = XeroPaymentStatus.AUTHORISED

        # Parse dates
        payment_date = PaymentTransformer._parse_xero_date(xero_payment.get("Date"))
        xero_updated_at = PaymentTransformer._parse_xero_date(xero_payment.get("UpdatedDateUTC"))

        # Parse amounts
        amount = Decimal(str(xero_payment.get("Amount", "0")))
        bank_amount = xero_payment.get("BankAmount")
        if bank_amount:
            bank_amount = Decimal(str(bank_amount))
        currency_rate = xero_payment.get("CurrencyRate")
        if currency_rate:
            currency_rate = Decimal(str(currency_rate))

        # Extract related entities
        invoice = xero_payment.get("Invoice", {})
        account = xero_payment.get("Account", {})

        return {
            "xero_payment_id": xero_payment["PaymentID"],
            "xero_invoice_id": invoice.get("InvoiceID"),
            "xero_account_id": account.get("AccountID"),
            "payment_type": payment_type,
            "status": status,
            "payment_date": payment_date or datetime.now(),
            "amount": amount,
            "currency_rate": currency_rate,
            "reference": xero_payment.get("Reference"),
            "is_reconciled": xero_payment.get("IsReconciled", False),
            "xero_updated_at": xero_updated_at,
        }

    @staticmethod
    def _parse_xero_date(date_str: str | None) -> datetime | None:
        """Parse Xero date string to datetime."""
        if not date_str:
            return None
        try:
            if date_str.startswith("/Date("):
                ms = int(date_str.replace("/Date(", "").replace(")/", "").split("+")[0])
                return datetime.fromtimestamp(ms / 1000)
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None


class OverpaymentTransformer:
    """Transforms Xero Overpayment API response to XeroOverpayment format."""

    @staticmethod
    def transform(xero_overpayment: dict[str, Any]) -> dict[str, Any]:
        """Transform a Xero overpayment to XeroOverpayment data.

        Args:
            xero_overpayment: Overpayment data from Xero API.

        Returns:
            Dict suitable for XeroOverpayment model.
        """
        # Map status
        status_str = xero_overpayment.get("Status", "AUTHORISED")
        try:
            status = XeroOverpaymentStatus(status_str)
        except ValueError:
            status = XeroOverpaymentStatus.AUTHORISED

        # Parse dates
        overpayment_date = OverpaymentTransformer._parse_xero_date(xero_overpayment.get("Date"))
        xero_updated_at = OverpaymentTransformer._parse_xero_date(
            xero_overpayment.get("UpdatedDateUTC")
        )

        # Parse amounts
        subtotal = Decimal(str(xero_overpayment.get("SubTotal", "0")))
        tax_amount = Decimal(str(xero_overpayment.get("TotalTax", "0")))
        total_amount = Decimal(str(xero_overpayment.get("Total", "0")))
        remaining_credit = Decimal(str(xero_overpayment.get("RemainingCredit", "0")))

        # Extract contact
        contact = xero_overpayment.get("Contact", {})

        # Transform line items and allocations
        line_items = OverpaymentTransformer._transform_line_items(
            xero_overpayment.get("LineItems", [])
        )
        allocations = OverpaymentTransformer._transform_allocations(
            xero_overpayment.get("Allocations", [])
        )

        return {
            "xero_overpayment_id": xero_overpayment["OverpaymentID"],
            "xero_contact_id": contact.get("ContactID"),
            "status": status,
            "overpayment_date": overpayment_date or datetime.now(),
            "subtotal": subtotal,
            "tax_amount": tax_amount,
            "total_amount": total_amount,
            "remaining_credit": remaining_credit,
            "currency": xero_overpayment.get("CurrencyCode", "AUD"),
            "line_items": line_items if line_items else None,
            "xero_updated_at": xero_updated_at,
        }

    @staticmethod
    def _transform_line_items(line_items: list[dict]) -> list[dict[str, Any]]:
        """Transform Xero line items."""
        result = []
        for item in line_items:
            result.append(
                {
                    "description": item.get("Description"),
                    "quantity": float(item.get("Quantity", 0)),
                    "unit_amount": float(item.get("UnitAmount", 0)),
                    "line_amount": float(item.get("LineAmount", 0)),
                    "account_code": item.get("AccountCode"),
                    "tax_type": item.get("TaxType"),
                    "tax_amount": float(item.get("TaxAmount", 0)),
                }
            )
        return result

    @staticmethod
    def _transform_allocations(allocations: list[dict]) -> list[dict[str, Any]]:
        """Transform allocations."""
        result = []
        for alloc in allocations:
            invoice = alloc.get("Invoice", {})
            result.append(
                {
                    "invoice_id": invoice.get("InvoiceID"),
                    "amount": float(alloc.get("Amount", 0)),
                    "date": alloc.get("Date"),
                }
            )
        return result

    @staticmethod
    def _parse_xero_date(date_str: str | None) -> datetime | None:
        """Parse Xero date string to datetime."""
        if not date_str:
            return None
        try:
            if date_str.startswith("/Date("):
                ms = int(date_str.replace("/Date(", "").replace(")/", "").split("+")[0])
                return datetime.fromtimestamp(ms / 1000)
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None


class PrepaymentTransformer:
    """Transforms Xero Prepayment API response to XeroPrepayment format."""

    @staticmethod
    def transform(xero_prepayment: dict[str, Any]) -> dict[str, Any]:
        """Transform a Xero prepayment to XeroPrepayment data.

        Args:
            xero_prepayment: Prepayment data from Xero API.

        Returns:
            Dict suitable for XeroPrepayment model.
        """
        # Map status
        status_str = xero_prepayment.get("Status", "AUTHORISED")
        try:
            status = XeroPrepaymentStatus(status_str)
        except ValueError:
            status = XeroPrepaymentStatus.AUTHORISED

        # Parse dates
        prepayment_date = PrepaymentTransformer._parse_xero_date(xero_prepayment.get("Date"))
        xero_updated_at = PrepaymentTransformer._parse_xero_date(
            xero_prepayment.get("UpdatedDateUTC")
        )

        # Parse amounts
        subtotal = Decimal(str(xero_prepayment.get("SubTotal", "0")))
        tax_amount = Decimal(str(xero_prepayment.get("TotalTax", "0")))
        total_amount = Decimal(str(xero_prepayment.get("Total", "0")))
        remaining_credit = Decimal(str(xero_prepayment.get("RemainingCredit", "0")))

        # Extract contact
        contact = xero_prepayment.get("Contact", {})

        # Transform line items and allocations
        line_items = PrepaymentTransformer._transform_line_items(
            xero_prepayment.get("LineItems", [])
        )
        allocations = PrepaymentTransformer._transform_allocations(
            xero_prepayment.get("Allocations", [])
        )

        return {
            "xero_prepayment_id": xero_prepayment["PrepaymentID"],
            "xero_contact_id": contact.get("ContactID"),
            "status": status,
            "prepayment_date": prepayment_date or datetime.now(),
            "subtotal": subtotal,
            "tax_amount": tax_amount,
            "total_amount": total_amount,
            "remaining_credit": remaining_credit,
            "currency": xero_prepayment.get("CurrencyCode", "AUD"),
            "line_items": line_items if line_items else None,
            "xero_updated_at": xero_updated_at,
        }

    @staticmethod
    def _transform_line_items(line_items: list[dict]) -> list[dict[str, Any]]:
        """Transform Xero line items."""
        result = []
        for item in line_items:
            result.append(
                {
                    "description": item.get("Description"),
                    "quantity": float(item.get("Quantity", 0)),
                    "unit_amount": float(item.get("UnitAmount", 0)),
                    "line_amount": float(item.get("LineAmount", 0)),
                    "account_code": item.get("AccountCode"),
                    "tax_type": item.get("TaxType"),
                    "tax_amount": float(item.get("TaxAmount", 0)),
                }
            )
        return result

    @staticmethod
    def _transform_allocations(allocations: list[dict]) -> list[dict[str, Any]]:
        """Transform allocations."""
        result = []
        for alloc in allocations:
            invoice = alloc.get("Invoice", {})
            result.append(
                {
                    "invoice_id": invoice.get("InvoiceID"),
                    "amount": float(alloc.get("Amount", 0)),
                    "date": alloc.get("Date"),
                }
            )
        return result

    @staticmethod
    def _parse_xero_date(date_str: str | None) -> datetime | None:
        """Parse Xero date string to datetime."""
        if not date_str:
            return None
        try:
            if date_str.startswith("/Date("):
                ms = int(date_str.replace("/Date(", "").replace(")/", "").split("+")[0])
                return datetime.fromtimestamp(ms / 1000)
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None


class JournalTransformer:
    """Transforms Xero Journal API response to XeroJournal format."""

    @staticmethod
    def transform(xero_journal: dict[str, Any]) -> dict[str, Any]:
        """Transform a Xero journal to XeroJournal data.

        Args:
            xero_journal: Journal data from Xero API.

        Returns:
            Dict suitable for XeroJournal model.
        """
        # Map source type
        source_type_str = xero_journal.get("SourceType", "UNKNOWN")
        try:
            source_type = XeroJournalSourceType(source_type_str)
        except ValueError:
            source_type = XeroJournalSourceType.UNKNOWN

        # Parse dates
        journal_date = JournalTransformer._parse_xero_date(xero_journal.get("JournalDate"))
        created_date_utc = JournalTransformer._parse_xero_date(xero_journal.get("CreatedDateUTC"))

        # Transform journal lines
        journal_lines = JournalTransformer._transform_journal_lines(
            xero_journal.get("JournalLines", [])
        )

        return {
            "xero_journal_id": xero_journal["JournalID"],
            "journal_number": xero_journal.get("JournalNumber", 0),
            "journal_date": journal_date or datetime.now(),
            "source_id": xero_journal.get("SourceID"),
            "source_type": source_type,
            "reference": xero_journal.get("Reference"),
            "xero_created_at": created_date_utc,
            "journal_lines": journal_lines if journal_lines else None,
        }

    @staticmethod
    def _transform_journal_lines(lines: list[dict]) -> list[dict[str, Any]]:
        """Transform journal lines."""
        result = []
        for line in lines:
            result.append(
                {
                    "journal_line_id": line.get("JournalLineID"),
                    "account_id": line.get("AccountID"),
                    "account_code": line.get("AccountCode"),
                    "account_name": line.get("AccountName"),
                    "account_type": line.get("AccountType"),
                    "description": line.get("Description"),
                    "net_amount": float(line.get("NetAmount", 0)),
                    "gross_amount": float(line.get("GrossAmount", 0)),
                    "tax_amount": float(line.get("TaxAmount", 0)),
                    "tax_type": line.get("TaxType"),
                    "tax_name": line.get("TaxName"),
                }
            )
        return result

    @staticmethod
    def _parse_xero_date(date_str: str | None) -> datetime | None:
        """Parse Xero date string to datetime."""
        if not date_str:
            return None
        try:
            if date_str.startswith("/Date("):
                ms = int(date_str.replace("/Date(", "").replace(")/", "").split("+")[0])
                return datetime.fromtimestamp(ms / 1000)
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None


class ManualJournalTransformer:
    """Transforms Xero ManualJournal API response to XeroManualJournal format."""

    @staticmethod
    def transform(xero_manual_journal: dict[str, Any]) -> dict[str, Any]:
        """Transform a Xero manual journal to XeroManualJournal data.

        Args:
            xero_manual_journal: Manual journal data from Xero API.

        Returns:
            Dict suitable for XeroManualJournal model.
        """
        # Map status
        status_str = xero_manual_journal.get("Status", "DRAFT")
        try:
            status = XeroManualJournalStatus(status_str)
        except ValueError:
            status = XeroManualJournalStatus.DRAFT

        # Parse dates
        journal_date = ManualJournalTransformer._parse_xero_date(xero_manual_journal.get("Date"))
        xero_updated_at = ManualJournalTransformer._parse_xero_date(
            xero_manual_journal.get("UpdatedDateUTC")
        )

        # Transform journal lines
        journal_lines = ManualJournalTransformer._transform_journal_lines(
            xero_manual_journal.get("JournalLines", [])
        )

        return {
            "xero_manual_journal_id": xero_manual_journal["ManualJournalID"],
            "narration": xero_manual_journal.get("Narration"),
            "status": status,
            "journal_date": journal_date or datetime.now(),
            "line_amount_types": xero_manual_journal.get("LineAmountTypes"),
            "show_on_cash_basis": xero_manual_journal.get("ShowOnCashBasisReports", True),
            "journal_lines": journal_lines if journal_lines else None,
            "xero_updated_at": xero_updated_at,
        }

    @staticmethod
    def _transform_journal_lines(lines: list[dict]) -> list[dict[str, Any]]:
        """Transform manual journal lines."""
        result = []
        for line in lines:
            result.append(
                {
                    "line_amount": float(line.get("LineAmount", 0)),
                    "account_id": line.get("AccountID"),
                    "account_code": line.get("AccountCode"),
                    "description": line.get("Description"),
                    "tax_type": line.get("TaxType"),
                    "tax_amount": float(line.get("TaxAmount", 0))
                    if line.get("TaxAmount")
                    else None,
                    "is_blank": line.get("IsBlank", False),
                }
            )
        return result

    @staticmethod
    def _parse_xero_date(date_str: str | None) -> datetime | None:
        """Parse Xero date string to datetime."""
        if not date_str:
            return None
        try:
            if date_str.startswith("/Date("):
                ms = int(date_str.replace("/Date(", "").replace(")/", "").split("+")[0])
                return datetime.fromtimestamp(ms / 1000)
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None


class AssetTypeTransformer:
    """Transforms Xero AssetType API response to XeroAssetType format."""

    @staticmethod
    def transform(xero_asset_type: dict[str, Any]) -> dict[str, Any]:
        """Transform a Xero asset type to XeroAssetType data.

        Args:
            xero_asset_type: Asset type data from Xero Assets API.

        Returns:
            Dict suitable for XeroAssetType model.
        """
        # Extract book depreciation settings
        book_settings = xero_asset_type.get("bookDepreciationSetting", {})
        tax_settings = xero_asset_type.get("taxDepreciationSetting", {})

        return {
            "xero_asset_type_id": xero_asset_type["assetTypeId"],
            "asset_type_name": xero_asset_type.get("assetTypeName", "Unknown"),
            "fixed_asset_account_id": xero_asset_type.get("fixedAssetAccountId"),
            "depreciation_expense_account_id": xero_asset_type.get("depreciationExpenseAccountId"),
            "accumulated_depreciation_account_id": xero_asset_type.get(
                "accumulatedDepreciationAccountId"
            ),
            "depreciation_method": book_settings.get("depreciationMethod", "StraightLine"),
            "averaging_method": book_settings.get("averagingMethod", "FullMonth"),
            "depreciation_rate": AssetTypeTransformer._to_decimal(
                book_settings.get("depreciationRate")
            ),
            "effective_life_years": book_settings.get("effectiveLifeYears"),
            "calculation_method": book_settings.get("depreciationCalculationMethod", "Rate"),
            "locks": xero_asset_type.get("locks", 0),
        }

    @staticmethod
    def _to_decimal(value: Any) -> Decimal | None:
        """Convert value to Decimal if present."""
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None

    @staticmethod
    def _parse_date(date_str: str | None) -> date | None:
        """Parse ISO date string to date."""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
        except (ValueError, TypeError):
            return None


class AssetTransformer:
    """Transforms Xero Asset API response to XeroAsset format."""

    @staticmethod
    def transform(xero_asset: dict[str, Any]) -> dict[str, Any]:
        """Transform a Xero asset to XeroAsset data.

        Args:
            xero_asset: Asset data from Xero Assets API.

        Returns:
            Dict suitable for XeroAsset model.
        """
        # Extract depreciation settings
        book_settings = xero_asset.get("bookDepreciationSetting", {})
        book_details = xero_asset.get("bookDepreciationDetail", {})
        tax_settings = xero_asset.get("taxDepreciationSetting", {})
        tax_details = xero_asset.get("taxDepreciationDetail", {})

        return {
            "xero_asset_id": xero_asset["assetId"],
            "asset_name": xero_asset.get("assetName", "Unknown"),
            "asset_number": xero_asset.get("assetNumber"),
            "purchase_date": AssetTransformer._parse_date(xero_asset.get("purchaseDate"))
            or date.today(),
            "purchase_price": AssetTransformer._to_decimal(xero_asset.get("purchasePrice"))
            or Decimal("0"),
            "status": xero_asset.get("assetStatus", "Draft"),
            "book_value": AssetTransformer._to_decimal(xero_asset.get("bookValue")) or Decimal("0"),
            "serial_number": xero_asset.get("serialNumber"),
            "warranty_expiry": AssetTransformer._parse_date(xero_asset.get("warrantyExpiryDate")),
            # Book depreciation settings
            "book_depreciation_method": book_settings.get("depreciationMethod"),
            "book_depreciation_rate": AssetTransformer._to_decimal(
                book_settings.get("depreciationRate")
            ),
            "book_effective_life_years": book_settings.get("effectiveLifeYears"),
            "book_depreciation_start_date": AssetTransformer._parse_date(
                book_settings.get("depreciationStartDate")
            ),
            "book_cost_limit": AssetTransformer._to_decimal(book_settings.get("costLimit")),
            "book_residual_value": AssetTransformer._to_decimal(book_settings.get("residualValue")),
            # Book depreciation details
            "book_prior_accum_depreciation": AssetTransformer._to_decimal(
                book_details.get("priorAccumDepreciationAmount")
            ),
            "book_current_accum_depreciation": AssetTransformer._to_decimal(
                book_details.get("currentAccumDepreciationAmount")
            ),
            "book_current_capital_gain": AssetTransformer._to_decimal(
                book_details.get("currentCapitalGain")
            ),
            "book_current_gain_loss": AssetTransformer._to_decimal(
                book_details.get("currentGainLoss")
            ),
            # Tax depreciation settings
            "tax_depreciation_method": tax_settings.get("depreciationMethod"),
            "tax_depreciation_rate": AssetTransformer._to_decimal(
                tax_settings.get("depreciationRate")
            ),
            "tax_effective_life_years": tax_settings.get("effectiveLifeYears"),
            "tax_depreciation_start_date": AssetTransformer._parse_date(
                tax_settings.get("depreciationStartDate")
            ),
            "tax_cost_limit": AssetTransformer._to_decimal(tax_settings.get("costLimit")),
            "tax_residual_value": AssetTransformer._to_decimal(tax_settings.get("residualValue")),
            # Tax depreciation details
            "tax_prior_accum_depreciation": AssetTransformer._to_decimal(
                tax_details.get("priorAccumDepreciationAmount")
            ),
            "tax_current_accum_depreciation": AssetTransformer._to_decimal(
                tax_details.get("currentAccumDepreciationAmount")
            ),
            "tax_current_capital_gain": AssetTransformer._to_decimal(
                tax_details.get("currentCapitalGain")
            ),
            "tax_current_gain_loss": AssetTransformer._to_decimal(
                tax_details.get("currentGainLoss")
            ),
            # Disposal info
            "disposal_date": AssetTransformer._parse_date(xero_asset.get("disposalDate")),
            "disposal_price": AssetTransformer._to_decimal(xero_asset.get("disposalPrice")),
            "is_billed": xero_asset.get("canRollback", False),
        }

    @staticmethod
    def _to_decimal(value: Any) -> Decimal | None:
        """Convert value to Decimal if present."""
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None

    @staticmethod
    def _parse_date(date_str: str | None) -> date | None:
        """Parse ISO date string to date."""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
        except (ValueError, TypeError):
            return None


# =============================================================================
# Spec 025: Purchase Orders, Repeating Invoices, Tracking, Quotes
# =============================================================================


class PurchaseOrderTransformer:
    """Transformer for Xero purchase orders."""

    @staticmethod
    def transform(
        xero_po: dict[str, Any],
        tenant_id: UUID,
        connection_id: UUID,
    ) -> dict[str, Any]:
        """Transform Xero purchase order to database format."""
        # Transform line items to JSONB
        line_items = []
        for item in xero_po.get("LineItems", []):
            line_items.append(
                {
                    "description": item.get("Description"),
                    "quantity": float(item.get("Quantity", 0)),
                    "unit_amount": float(item.get("UnitAmount", 0)),
                    "account_code": item.get("AccountCode"),
                    "tax_type": item.get("TaxType"),
                    "line_amount": float(item.get("LineAmount", 0)),
                    "tax_amount": float(item.get("TaxAmount", 0)),
                    "item_code": item.get("ItemCode"),
                }
            )

        return {
            "tenant_id": tenant_id,
            "connection_id": connection_id,
            "xero_purchase_order_id": xero_po.get("PurchaseOrderID"),
            "purchase_order_number": xero_po.get("PurchaseOrderNumber"),
            "contact_id": xero_po.get("Contact", {}).get("ContactID"),
            "contact_name": xero_po.get("Contact", {}).get("Name"),
            "reference": xero_po.get("Reference"),
            "date": PurchaseOrderTransformer._parse_date(xero_po.get("Date")),
            "delivery_date": PurchaseOrderTransformer._parse_date(xero_po.get("DeliveryDate")),
            "expected_arrival_date": PurchaseOrderTransformer._parse_date(
                xero_po.get("ExpectedArrivalDate")
            ),
            "status": xero_po.get("Status"),
            "sub_total": PurchaseOrderTransformer._to_decimal(xero_po.get("SubTotal", 0)),
            "total_tax": PurchaseOrderTransformer._to_decimal(xero_po.get("TotalTax", 0)),
            "total": PurchaseOrderTransformer._to_decimal(xero_po.get("Total", 0)),
            "currency_code": xero_po.get("CurrencyCode", "AUD"),
            "line_items": line_items,
            "sent_to_contact": xero_po.get("SentToContact", False),
            "xero_updated_at": PurchaseOrderTransformer._parse_datetime(
                xero_po.get("UpdatedDateUTC")
            ),
        }

    @staticmethod
    def _to_decimal(value: Any) -> Decimal:
        """Convert value to Decimal."""
        if value is None:
            return Decimal(0)
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return Decimal(0)

    @staticmethod
    def _parse_date(date_str: str | None) -> date | None:
        """Parse Xero date string."""
        if not date_str:
            return None
        try:
            # Handle /Date(...)/ format
            if "/Date(" in date_str:
                import re

                match = re.search(r"/Date\((\d+)", date_str)
                if match:
                    ts = int(match.group(1)) / 1000
                    return datetime.utcfromtimestamp(ts).date()
            return datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_datetime(date_str: str | None) -> datetime | None:
        """Parse Xero datetime string."""
        if not date_str:
            return None
        try:
            if "/Date(" in date_str:
                import re

                match = re.search(r"/Date\((\d+)", date_str)
                if match:
                    ts = int(match.group(1)) / 1000
                    return datetime.utcfromtimestamp(ts)
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None


class RepeatingInvoiceTransformer:
    """Transformer for Xero repeating invoices."""

    @staticmethod
    def transform(
        xero_ri: dict[str, Any],
        tenant_id: UUID,
        connection_id: UUID,
    ) -> dict[str, Any]:
        """Transform Xero repeating invoice to database format."""
        schedule = xero_ri.get("Schedule", {})

        # Transform line items to JSONB
        line_items = []
        for item in xero_ri.get("LineItems", []):
            line_items.append(
                {
                    "description": item.get("Description"),
                    "quantity": float(item.get("Quantity", 0)),
                    "unit_amount": float(item.get("UnitAmount", 0)),
                    "account_code": item.get("AccountCode"),
                    "tax_type": item.get("TaxType"),
                    "line_amount": float(item.get("LineAmount", 0)),
                    "item_code": item.get("ItemCode"),
                }
            )

        return {
            "tenant_id": tenant_id,
            "connection_id": connection_id,
            "xero_repeating_invoice_id": xero_ri.get("RepeatingInvoiceID"),
            "type": xero_ri.get("Type"),
            "contact_id": xero_ri.get("Contact", {}).get("ContactID"),
            "contact_name": xero_ri.get("Contact", {}).get("Name"),
            "status": xero_ri.get("Status"),
            "schedule_unit": schedule.get("Unit"),
            "schedule_period": schedule.get("Period", 1),
            "schedule_due_date": schedule.get("DueDate"),
            "schedule_due_date_type": schedule.get("DueDateType"),
            "schedule_start_date": RepeatingInvoiceTransformer._parse_date(
                schedule.get("StartDate")
            ),
            "schedule_end_date": RepeatingInvoiceTransformer._parse_date(schedule.get("EndDate")),
            "schedule_next_scheduled_date": RepeatingInvoiceTransformer._parse_date(
                schedule.get("NextScheduledDate")
            ),
            "reference": xero_ri.get("Reference"),
            "currency_code": xero_ri.get("CurrencyCode", "AUD"),
            "sub_total": RepeatingInvoiceTransformer._to_decimal(xero_ri.get("SubTotal", 0)),
            "total_tax": RepeatingInvoiceTransformer._to_decimal(xero_ri.get("TotalTax", 0)),
            "total": RepeatingInvoiceTransformer._to_decimal(xero_ri.get("Total", 0)),
            "line_items": line_items,
        }

    @staticmethod
    def _to_decimal(value: Any) -> Decimal:
        if value is None:
            return Decimal(0)
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return Decimal(0)

    @staticmethod
    def _parse_date(date_str: str | None) -> date | None:
        if not date_str:
            return None
        try:
            if "/Date(" in date_str:
                import re

                match = re.search(r"/Date\((\d+)", date_str)
                if match:
                    ts = int(match.group(1)) / 1000
                    return datetime.utcfromtimestamp(ts).date()
            return datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
        except (ValueError, TypeError):
            return None


class TrackingCategoryTransformer:
    """Transformer for Xero tracking categories."""

    @staticmethod
    def transform(
        xero_tc: dict[str, Any],
        tenant_id: UUID,
        connection_id: UUID,
    ) -> dict[str, Any]:
        """Transform Xero tracking category to database format."""
        return {
            "tenant_id": tenant_id,
            "connection_id": connection_id,
            "xero_tracking_category_id": xero_tc.get("TrackingCategoryID"),
            "name": xero_tc.get("Name"),
            "status": xero_tc.get("Status", "ACTIVE"),
            "option_count": len(xero_tc.get("Options", [])),
        }


class TrackingOptionTransformer:
    """Transformer for Xero tracking options."""

    @staticmethod
    def transform(
        xero_opt: dict[str, Any],
        tracking_category_id: UUID,
    ) -> dict[str, Any]:
        """Transform Xero tracking option to database format."""
        return {
            "tracking_category_id": tracking_category_id,
            "xero_tracking_option_id": xero_opt.get("TrackingOptionID"),
            "name": xero_opt.get("Name"),
            "status": xero_opt.get("Status", "ACTIVE"),
            "is_active": xero_opt.get("IsActive", True),
            "is_deleted": xero_opt.get("IsDeleted", False),
            "is_archived": xero_opt.get("IsArchived", False),
        }


class QuoteTransformer:
    """Transformer for Xero quotes."""

    @staticmethod
    def transform(
        xero_quote: dict[str, Any],
        tenant_id: UUID,
        connection_id: UUID,
    ) -> dict[str, Any]:
        """Transform Xero quote to database format."""
        return {
            "tenant_id": tenant_id,
            "connection_id": connection_id,
            "xero_quote_id": xero_quote.get("QuoteID"),
            "quote_number": xero_quote.get("QuoteNumber"),
            "contact_name": xero_quote.get("Contact", {}).get("Name"),
            "reference": xero_quote.get("Reference"),
            "date": QuoteTransformer._parse_date(xero_quote.get("Date")),
            "expiry_date": QuoteTransformer._parse_date(xero_quote.get("ExpiryDate")),
            "status": xero_quote.get("Status"),
            "title": xero_quote.get("Title"),
            "summary": xero_quote.get("Summary"),
            "sub_total": QuoteTransformer._to_decimal(xero_quote.get("SubTotal", 0)),
            "total_tax": QuoteTransformer._to_decimal(xero_quote.get("TotalTax", 0)),
            "total": QuoteTransformer._to_decimal(xero_quote.get("Total", 0)),
            "total_discount": QuoteTransformer._to_decimal(xero_quote.get("TotalDiscount")),
            "currency_code": xero_quote.get("CurrencyCode"),
            "branding_theme_id": xero_quote.get("BrandingThemeID"),
            "updated_date_utc": QuoteTransformer._parse_datetime(xero_quote.get("UpdatedDateUTC")),
        }

    @staticmethod
    def _to_decimal(value: Any) -> Decimal | None:
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None

    @staticmethod
    def _parse_date(date_str: str | None) -> date | None:
        if not date_str:
            return None
        try:
            if "/Date(" in date_str:
                import re

                match = re.search(r"/Date\((\d+)", date_str)
                if match:
                    ts = int(match.group(1)) / 1000
                    return datetime.utcfromtimestamp(ts).date()
            return datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_datetime(date_str: str | None) -> datetime | None:
        if not date_str:
            return None
        try:
            if "/Date(" in date_str:
                import re

                match = re.search(r"/Date\((\d+)", date_str)
                if match:
                    ts = int(match.group(1)) / 1000
                    return datetime.utcfromtimestamp(ts)
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
