"""Service for computing client AI context aggregations.

Computes financial summaries from synced Xero data for use in
AI chat context injection.
"""

import logging
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.integrations.xero.models import (
    XeroBankTransaction,
    XeroBankTransactionType,
    XeroEmployee,
    XeroEmployeeStatus,
    XeroInvoice,
    XeroInvoiceStatus,
    XeroInvoiceType,
    XeroPayRun,
    XeroPayRunStatus,
)
from app.modules.knowledge.aggregation_models import (
    PeriodType,
    RevenueBracket,
)
from app.modules.knowledge.aggregation_repository import AggregationRepository

logger = logging.getLogger(__name__)


class AggregationService:
    """Service for computing client financial aggregations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AggregationRepository(db)

    async def compute_all_for_connection(
        self,
        connection_id: UUID,
        tenant_id: UUID,
    ) -> dict[str, int]:
        """Compute all aggregations for a connection (organization).

        Called after Xero sync completes. Computes organization-level aggregations:
        - Client profiles (organization profile)
        - Expense summaries (current quarter + year)
        - AR/AP aging (current date)
        - GST summaries (current + prior quarters)
        - Monthly trends (last 12 months)
        - Compliance summaries (current quarter)

        NOTE: Aggregations are computed at the organization level (XeroConnection),
        not per-contact (XeroClient), because financial data belongs to the org.

        Returns:
            Dict with counts of records computed per type.
        """
        logger.info(f"Computing aggregations for connection/organization {connection_id}")
        stats = defaultdict(int)

        try:
            # Compute all summaries for this connection/organization
            await self._compute_connection_aggregations(
                tenant_id=tenant_id,
                connection_id=connection_id,
                stats=stats,
            )
        except Exception as e:
            logger.error(f"Error computing aggregations for connection {connection_id}: {e}")
            stats["errors"] += 1

        logger.info(f"Aggregation complete: {dict(stats)}")
        return dict(stats)

    async def _compute_connection_aggregations(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        stats: dict[str, int],
    ) -> None:
        """Compute all aggregations for a connection/organization.

        All financial data is aggregated at the organization level (XeroConnection).
        """
        today = date.today()
        current_year = today.year
        current_month = today.month

        # Compute profile (organization-level)
        await self.compute_connection_profile(tenant_id, connection_id)
        stats["profiles"] += 1

        # Compute AR/AP aging for today
        await self.compute_ar_aging(tenant_id, connection_id, today)
        stats["ar_aging"] += 1
        await self.compute_ap_aging(tenant_id, connection_id, today)
        stats["ap_aging"] += 1

        # Compute current quarter expense summary
        quarter_start = self._get_quarter_start(today)
        quarter_end = self._get_quarter_end(today)
        await self.compute_expense_summary(
            tenant_id, connection_id, PeriodType.QUARTER, quarter_start, quarter_end
        )
        stats["expense_summaries"] += 1

        # Compute GST summaries for current + prior quarter
        await self.compute_gst_summary(
            tenant_id, connection_id, PeriodType.QUARTER, quarter_start, quarter_end
        )
        stats["gst_summaries"] += 1

        prior_quarter_start = self._get_prior_quarter_start(quarter_start)
        prior_quarter_end = quarter_start - timedelta(days=1)
        await self.compute_gst_summary(
            tenant_id, connection_id, PeriodType.QUARTER, prior_quarter_start, prior_quarter_end
        )
        stats["gst_summaries"] += 1

        # Compute monthly trends for last 12 months
        for i in range(12):
            month = current_month - i
            year = current_year
            while month <= 0:
                month += 12
                year -= 1
            await self.compute_monthly_trend(tenant_id, connection_id, year, month)
            stats["monthly_trends"] += 1

        # Compute compliance summary for current quarter
        await self.compute_compliance_summary(
            tenant_id, connection_id, PeriodType.QUARTER, quarter_start, quarter_end
        )
        stats["compliance_summaries"] += 1

    async def _compute_client_aggregations(
        self,
        tenant_id: UUID,
        client_id: UUID,
        connection_id: UUID,
        stats: dict[str, int],
    ) -> None:
        """Legacy method - redirects to connection-level aggregation."""
        # For backward compatibility with compute_single_client task
        await self._compute_connection_aggregations(tenant_id, connection_id, stats)

    async def compute_connection_profile(
        self,
        tenant_id: UUID,
        connection_id: UUID,
    ) -> None:
        """Compute and store organization AI profile.

        Uses connection_id (XeroConnection/organization) for all queries.
        """
        # Get annual revenue to determine bracket
        year_start = date(date.today().year, 1, 1)
        year_end = date.today()

        result = await self.db.execute(
            select(func.sum(XeroInvoice.total_amount)).where(
                XeroInvoice.connection_id == connection_id,
                XeroInvoice.invoice_type == XeroInvoiceType.ACCREC,
                XeroInvoice.status.in_(
                    [
                        XeroInvoiceStatus.AUTHORISED,
                        XeroInvoiceStatus.PAID,
                    ]
                ),
                XeroInvoice.issue_date >= year_start,
                XeroInvoice.issue_date <= year_end,
            )
        )
        annual_revenue = result.scalar() or Decimal("0")
        revenue_bracket = self._determine_revenue_bracket(annual_revenue)

        # Check for GST registration
        # First, preserve the Xero Organisation API value if already set —
        # that source (TaxNumber + SalesTaxBasis) is authoritative.
        # Only fall back to invoice heuristic if no profile exists yet.
        existing_profile = await self.repo.get_profile_by_connection(connection_id)
        if existing_profile and existing_profile.gst_registered:
            gst_registered = True
        else:
            gst_result = await self.db.execute(
                select(func.count()).where(
                    XeroInvoice.connection_id == connection_id,
                    XeroInvoice.tax_amount > 0,
                )
            )
            gst_count = gst_result.scalar() or 0
            gst_registered = gst_count > 0

        # Count employees from pay runs
        employee_result = await self.db.execute(
            select(func.count(XeroEmployee.id)).where(
                XeroEmployee.connection_id == connection_id,
                XeroEmployee.status == XeroEmployeeStatus.ACTIVE,
            )
        )
        employee_count = employee_result.scalar() or 0

        await self.repo.upsert_client_profile(
            tenant_id=tenant_id,
            connection_id=connection_id,
            client_id=None,  # Organization-level profile, not contact-specific
            gst_registered=gst_registered,
            revenue_bracket=revenue_bracket,
            employee_count=employee_count,
            computed_at=datetime.now(UTC),
        )

    async def compute_client_profile(
        self,
        tenant_id: UUID,
        client_id: UUID,
        connection_id: UUID,
    ) -> None:
        """Legacy method - redirects to connection-level profile."""
        await self.compute_connection_profile(tenant_id, connection_id)

    async def compute_expense_summary(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        period_type: PeriodType,
        period_start: date,
        period_end: date,
    ) -> None:
        """Compute expense summary from invoices and bank transactions.

        Uses connection_id (XeroConnection/organization) for all queries.
        """
        # Get ACCPAY invoices (bills)
        result = await self.db.execute(
            select(
                XeroInvoice.subtotal,
                XeroInvoice.tax_amount,
                XeroInvoice.line_items,
            ).where(
                XeroInvoice.connection_id == connection_id,
                XeroInvoice.invoice_type == XeroInvoiceType.ACCPAY,
                XeroInvoice.status.in_(
                    [
                        XeroInvoiceStatus.AUTHORISED,
                        XeroInvoiceStatus.PAID,
                    ]
                ),
                XeroInvoice.issue_date >= period_start,
                XeroInvoice.issue_date <= period_end,
            )
        )
        invoices = result.all()

        # Get SPEND bank transactions
        txn_result = await self.db.execute(
            select(
                XeroBankTransaction.subtotal,
                XeroBankTransaction.tax_amount,
                XeroBankTransaction.line_items,
            ).where(
                XeroBankTransaction.connection_id == connection_id,
                XeroBankTransaction.transaction_type == XeroBankTransactionType.SPEND,
                XeroBankTransaction.transaction_date
                >= datetime.combine(period_start, datetime.min.time()),
                XeroBankTransaction.transaction_date
                <= datetime.combine(period_end, datetime.max.time()),
            )
        )
        transactions = txn_result.all()

        # Aggregate by account code
        by_account = defaultdict(lambda: {"amount": Decimal("0"), "gst": Decimal("0"), "count": 0})
        total_expenses = Decimal("0")
        total_gst = Decimal("0")
        transaction_count = 0

        for inv in invoices:
            total_expenses += inv.subtotal or Decimal("0")
            total_gst += inv.tax_amount or Decimal("0")
            transaction_count += 1
            if inv.line_items:
                for item in inv.line_items:
                    code = item.get("account_code", "unknown")
                    by_account[code]["amount"] += Decimal(str(item.get("line_amount", 0)))
                    by_account[code]["gst"] += Decimal(str(item.get("tax_amount", 0)))
                    by_account[code]["count"] += 1

        for txn in transactions:
            total_expenses += txn.subtotal or Decimal("0")
            total_gst += txn.tax_amount or Decimal("0")
            transaction_count += 1
            if txn.line_items:
                for item in txn.line_items:
                    code = item.get("account_code", "unknown")
                    by_account[code]["amount"] += Decimal(str(item.get("line_amount", 0)))
                    by_account[code]["gst"] += Decimal(str(item.get("tax_amount", 0)))
                    by_account[code]["count"] += 1

        # Convert to serializable format
        by_account_json = {
            k: {"amount": float(v["amount"]), "gst": float(v["gst"]), "count": v["count"]}
            for k, v in by_account.items()
        }

        await self.repo.upsert_expense_summary(
            tenant_id=tenant_id,
            connection_id=connection_id,
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
            by_account_code=by_account_json,
            by_category={},  # Future: map account codes to categories
            total_expenses=total_expenses,
            total_gst=total_gst,
            transaction_count=transaction_count,
            computed_at=datetime.now(UTC),
        )

    async def compute_ar_aging(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        as_of_date: date,
    ) -> None:
        """Compute accounts receivable aging buckets.

        Uses connection_id (XeroConnection/organization) for all queries.
        """
        # Get unpaid ACCREC invoices
        result = await self.db.execute(
            select(XeroInvoice).where(
                XeroInvoice.connection_id == connection_id,
                XeroInvoice.invoice_type == XeroInvoiceType.ACCREC,
                XeroInvoice.status.in_(
                    [
                        XeroInvoiceStatus.AUTHORISED,
                        XeroInvoiceStatus.SUBMITTED,
                    ]
                ),
            )
        )
        invoices = result.scalars().all()

        buckets = {
            "current": Decimal("0"),
            "days_31_60": Decimal("0"),
            "days_61_90": Decimal("0"),
            "over_90": Decimal("0"),
        }
        debtors = defaultdict(Decimal)

        for inv in invoices:
            amount = inv.total_amount or Decimal("0")
            due = inv.due_date.date() if inv.due_date else inv.issue_date.date()
            days_overdue = (as_of_date - due).days

            if days_overdue <= 0:
                buckets["current"] += amount
            elif days_overdue <= 60:
                buckets["days_31_60"] += amount
            elif days_overdue <= 90:
                buckets["days_61_90"] += amount
            else:
                buckets["over_90"] += amount

            # Track for top debtors (use invoice number as debtor name for now)
            debtor_name = inv.invoice_number or f"Invoice {inv.id}"
            debtors[debtor_name] += amount

        total = sum(buckets.values())

        # Top 5 debtors
        top_debtors = sorted(
            [{"name": k, "amount": float(v)} for k, v in debtors.items()],
            key=lambda x: x["amount"],
            reverse=True,
        )[:5]

        await self.repo.upsert_ar_aging(
            tenant_id=tenant_id,
            connection_id=connection_id,
            as_of_date=as_of_date,
            current_amount=buckets["current"],
            days_31_60=buckets["days_31_60"],
            days_61_90=buckets["days_61_90"],
            over_90_days=buckets["over_90"],
            total_outstanding=total,
            top_debtors=top_debtors,
            computed_at=datetime.now(UTC),
        )

    async def compute_ap_aging(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        as_of_date: date,
    ) -> None:
        """Compute accounts payable aging buckets.

        Uses connection_id (XeroConnection/organization) for all queries.
        """
        # Get unpaid ACCPAY invoices
        result = await self.db.execute(
            select(XeroInvoice).where(
                XeroInvoice.connection_id == connection_id,
                XeroInvoice.invoice_type == XeroInvoiceType.ACCPAY,
                XeroInvoice.status.in_(
                    [
                        XeroInvoiceStatus.AUTHORISED,
                        XeroInvoiceStatus.SUBMITTED,
                    ]
                ),
            )
        )
        invoices = result.scalars().all()

        buckets = {
            "current": Decimal("0"),
            "days_31_60": Decimal("0"),
            "days_61_90": Decimal("0"),
            "over_90": Decimal("0"),
        }
        creditors = defaultdict(Decimal)

        for inv in invoices:
            amount = inv.total_amount or Decimal("0")
            due = inv.due_date.date() if inv.due_date else inv.issue_date.date()
            days_overdue = (as_of_date - due).days

            if days_overdue <= 0:
                buckets["current"] += amount
            elif days_overdue <= 60:
                buckets["days_31_60"] += amount
            elif days_overdue <= 90:
                buckets["days_61_90"] += amount
            else:
                buckets["over_90"] += amount

            creditor_name = inv.invoice_number or f"Bill {inv.id}"
            creditors[creditor_name] += amount

        total = sum(buckets.values())

        top_creditors = sorted(
            [{"name": k, "amount": float(v)} for k, v in creditors.items()],
            key=lambda x: x["amount"],
            reverse=True,
        )[:5]

        await self.repo.upsert_ap_aging(
            tenant_id=tenant_id,
            connection_id=connection_id,
            as_of_date=as_of_date,
            current_amount=buckets["current"],
            days_31_60=buckets["days_31_60"],
            days_61_90=buckets["days_61_90"],
            over_90_days=buckets["over_90"],
            total_outstanding=total,
            top_creditors=top_creditors,
            computed_at=datetime.now(UTC),
        )

    async def compute_gst_summary(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        period_type: PeriodType,
        period_start: date,
        period_end: date,
    ) -> None:
        """Compute GST summary for BAS period.

        Uses connection_id (XeroConnection/organization) for all queries.
        """
        # GST on sales from ACCREC invoices
        sales_result = await self.db.execute(
            select(
                func.sum(XeroInvoice.subtotal),
                func.sum(XeroInvoice.tax_amount),
            ).where(
                XeroInvoice.connection_id == connection_id,
                XeroInvoice.invoice_type == XeroInvoiceType.ACCREC,
                XeroInvoice.status.in_(
                    [
                        XeroInvoiceStatus.AUTHORISED,
                        XeroInvoiceStatus.PAID,
                    ]
                ),
                XeroInvoice.issue_date >= period_start,
                XeroInvoice.issue_date <= period_end,
            )
        )
        sales_row = sales_result.one()
        total_sales = sales_row[0] or Decimal("0")
        gst_on_sales = sales_row[1] or Decimal("0")

        # GST on purchases from ACCPAY invoices
        purchases_result = await self.db.execute(
            select(
                func.sum(XeroInvoice.subtotal),
                func.sum(XeroInvoice.tax_amount),
            ).where(
                XeroInvoice.connection_id == connection_id,
                XeroInvoice.invoice_type == XeroInvoiceType.ACCPAY,
                XeroInvoice.status.in_(
                    [
                        XeroInvoiceStatus.AUTHORISED,
                        XeroInvoiceStatus.PAID,
                    ]
                ),
                XeroInvoice.issue_date >= period_start,
                XeroInvoice.issue_date <= period_end,
            )
        )
        purchases_row = purchases_result.one()
        total_purchases = purchases_row[0] or Decimal("0")
        gst_on_purchases = purchases_row[1] or Decimal("0")

        # Also include GST from bank transactions
        spend_gst_result = await self.db.execute(
            select(func.sum(XeroBankTransaction.tax_amount)).where(
                XeroBankTransaction.connection_id == connection_id,
                XeroBankTransaction.transaction_type == XeroBankTransactionType.SPEND,
                XeroBankTransaction.transaction_date
                >= datetime.combine(period_start, datetime.min.time()),
                XeroBankTransaction.transaction_date
                <= datetime.combine(period_end, datetime.max.time()),
            )
        )
        spend_gst = spend_gst_result.scalar() or Decimal("0")
        gst_on_purchases += spend_gst

        net_gst = gst_on_sales - gst_on_purchases

        await self.repo.upsert_gst_summary(
            tenant_id=tenant_id,
            connection_id=connection_id,
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
            gst_on_sales_1a=gst_on_sales,
            gst_on_purchases_1b=gst_on_purchases,
            net_gst=net_gst,
            total_sales=total_sales,
            total_purchases=total_purchases,
            adjustments={},
            computed_at=datetime.now(UTC),
        )

    async def compute_monthly_trend(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        year: int,
        month: int,
    ) -> None:
        """Compute monthly financial trend.

        Uses connection_id (XeroConnection/organization) for all queries.
        """
        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)

        # Revenue from ACCREC invoices
        revenue_result = await self.db.execute(
            select(func.sum(XeroInvoice.subtotal)).where(
                XeroInvoice.connection_id == connection_id,
                XeroInvoice.invoice_type == XeroInvoiceType.ACCREC,
                XeroInvoice.status.in_(
                    [
                        XeroInvoiceStatus.AUTHORISED,
                        XeroInvoiceStatus.PAID,
                    ]
                ),
                XeroInvoice.issue_date >= month_start,
                XeroInvoice.issue_date <= month_end,
            )
        )
        revenue = revenue_result.scalar() or Decimal("0")

        # Expenses from ACCPAY invoices (Bills)
        expense_result = await self.db.execute(
            select(func.sum(XeroInvoice.subtotal)).where(
                XeroInvoice.connection_id == connection_id,
                XeroInvoice.invoice_type == XeroInvoiceType.ACCPAY,
                XeroInvoice.status.in_(
                    [
                        XeroInvoiceStatus.AUTHORISED,
                        XeroInvoiceStatus.PAID,
                    ]
                ),
                XeroInvoice.issue_date >= month_start,
                XeroInvoice.issue_date <= month_end,
            )
        )
        bill_expenses = expense_result.scalar() or Decimal("0")

        # Net cashflow and bank-spend expenses from bank transactions.
        #
        # Many small businesses record spending as Spend Money bank
        # transactions without creating Bills (ACCPAY invoices).  To capture
        # true expenses we also sum Spend transactions coded to expense-class
        # accounts.
        #
        # We exclude transactions coded to non-operating accounts (assets,
        # liabilities, equity) such as director loans, owner drawings, and
        # inter-entity transfers from both cashflow and expense totals.
        from sqlalchemy import text

        date_start = datetime.combine(month_start, datetime.min.time())
        date_end = datetime.combine(month_end, datetime.max.time())
        operating_sql = text("""
            SELECT
                SUM(CASE WHEN t.transaction_type = 'receive'
                         AND (a.account_class IN ('revenue', 'expense') OR a.account_class IS NULL)
                    THEN t.total_amount ELSE 0 END) AS cash_in,
                SUM(CASE WHEN t.transaction_type = 'spend'
                         AND (a.account_class IN ('revenue', 'expense') OR a.account_class IS NULL)
                    THEN t.total_amount ELSE 0 END) AS cash_out,
                SUM(CASE WHEN t.transaction_type = 'spend'
                         AND a.account_class = 'expense'
                    THEN t.total_amount ELSE 0 END) AS bank_expenses
            FROM xero_bank_transactions t
            LEFT JOIN LATERAL (
                SELECT je.value ->> 'account_code' AS acct_code
                FROM jsonb_array_elements(t.line_items) je
                LIMIT 1
            ) li ON true
            LEFT JOIN xero_accounts a
                ON a.account_code = li.acct_code
               AND a.connection_id = t.connection_id
            WHERE t.connection_id = :connection_id
              AND t.transaction_date >= :date_start
              AND t.transaction_date <= :date_end
        """)

        cf_result = await self.db.execute(
            operating_sql,
            {
                "connection_id": str(connection_id),
                "date_start": date_start,
                "date_end": date_end,
            },
        )
        row = cf_result.one()
        cash_in = Decimal(str(row.cash_in or 0))
        cash_out = Decimal(str(row.cash_out or 0))
        bank_expenses = Decimal(str(row.bank_expenses or 0))

        # Total expenses = Bills (ACCPAY) + bank Spend transactions to expense accounts.
        # This handles both businesses that use Bills and those that pay directly.
        expenses = bill_expenses + bank_expenses

        net_cashflow = cash_in - cash_out
        gross_profit = revenue - expenses

        await self.repo.upsert_monthly_trend(
            tenant_id=tenant_id,
            connection_id=connection_id,
            year=year,
            month=month,
            revenue=revenue,
            expenses=expenses,
            gross_profit=gross_profit,
            net_cashflow=net_cashflow,
            computed_at=datetime.now(UTC),
        )

    async def compute_compliance_summary(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        period_type: PeriodType,
        period_start: date,
        period_end: date,
    ) -> None:
        """Compute compliance summary from payroll data.

        Uses connection_id (XeroConnection/organization) for all queries.
        """
        # Get pay runs for the period
        pay_runs_result = await self.db.execute(
            select(XeroPayRun).where(
                XeroPayRun.connection_id == connection_id,
                XeroPayRun.pay_run_status == XeroPayRunStatus.POSTED,
                XeroPayRun.period_start >= datetime.combine(period_start, datetime.min.time()),
                XeroPayRun.period_end <= datetime.combine(period_end, datetime.max.time()),
            )
        )
        pay_runs = pay_runs_result.scalars().all()

        total_wages = Decimal("0")
        total_payg = Decimal("0")
        total_super = Decimal("0")
        employee_count = 0

        for pr in pay_runs:
            total_wages += pr.total_wages or Decimal("0")
            total_payg += pr.total_tax or Decimal("0")
            total_super += pr.total_super or Decimal("0")
            employee_count = max(employee_count, pr.employee_count or 0)

        await self.repo.upsert_compliance_summary(
            tenant_id=tenant_id,
            connection_id=connection_id,
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
            total_wages=total_wages,
            total_payg_withheld=total_payg,
            total_super=total_super,
            employee_count=employee_count,
            contractor_payments=Decimal("0"),  # Future: identify contractor payments
            contractor_count=0,
            computed_at=datetime.now(UTC),
        )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _determine_revenue_bracket(self, annual_revenue: Decimal) -> RevenueBracket | None:
        """Determine revenue bracket from annual revenue."""
        if annual_revenue < 75000:
            return RevenueBracket.MICRO
        elif annual_revenue < 500000:
            return RevenueBracket.SMALL
        elif annual_revenue < 2000000:
            return RevenueBracket.MEDIUM
        elif annual_revenue < 10000000:
            return RevenueBracket.LARGE
        else:
            return RevenueBracket.ENTERPRISE

    def _get_quarter_start(self, d: date) -> date:
        """Get the start date of the quarter containing the given date."""
        quarter = (d.month - 1) // 3
        return date(d.year, quarter * 3 + 1, 1)

    def _get_quarter_end(self, d: date) -> date:
        """Get the end date of the quarter containing the given date."""
        quarter_start = self._get_quarter_start(d)
        if quarter_start.month == 10:
            return date(quarter_start.year + 1, 1, 1) - timedelta(days=1)
        else:
            return date(quarter_start.year, quarter_start.month + 3, 1) - timedelta(days=1)

    def _get_prior_quarter_start(self, quarter_start: date) -> date:
        """Get the start of the prior quarter."""
        if quarter_start.month == 1:
            return date(quarter_start.year - 1, 10, 1)
        else:
            return date(quarter_start.year, quarter_start.month - 3, 1)
