"""Repository for dashboard data aggregations.

CRITICAL: In Clairo, "client" = XeroConnection = one business = one BAS to lodge.
Dashboard shows one row per XeroConnection (Xero organization), NOT per XeroClient (contact).
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.dashboard.schemas import BASStatus
from app.modules.integrations.xero.models import (
    XeroBankTransaction,
    XeroConnection,
    XeroConnectionStatus,
    XeroInvoice,
    XeroInvoiceStatus,
    XeroInvoiceType,
)


class DashboardRepository:
    """Repository for dashboard aggregate queries.

    All queries aggregate by XeroConnection (client business), not XeroClient (contact).
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_aggregated_summary(
        self,
        tenant_id: UUID,
        quarter_start: date,
        quarter_end: date,
    ) -> dict[str, Any]:
        """Get aggregated summary metrics for the dashboard.

        Aggregates data across all XeroConnections (client businesses) for the tenant.

        Returns a dict with:
        - total_clients: Total number of active connections (businesses)
        - active_clients: Connections with activity in the quarter
        - total_sales: Sum of ACCREC invoice totals across all connections
        - total_purchases: Sum of ACCPAY invoice totals across all connections
        - gst_collected: Sum of tax from ACCREC invoices
        - gst_paid: Sum of tax from ACCPAY invoices
        - last_sync_at: Most recent sync timestamp
        """
        valid_statuses = [XeroInvoiceStatus.AUTHORISED, XeroInvoiceStatus.PAID]

        # Subquery for invoice aggregates per connection
        invoice_subq = (
            select(
                XeroInvoice.connection_id,
                func.sum(
                    case(
                        (
                            XeroInvoice.invoice_type == XeroInvoiceType.ACCREC,
                            XeroInvoice.total_amount,
                        ),
                        else_=Decimal("0"),
                    )
                ).label("sales"),
                func.sum(
                    case(
                        (
                            XeroInvoice.invoice_type == XeroInvoiceType.ACCPAY,
                            XeroInvoice.total_amount,
                        ),
                        else_=Decimal("0"),
                    )
                ).label("purchases"),
                func.sum(
                    case(
                        (
                            XeroInvoice.invoice_type == XeroInvoiceType.ACCREC,
                            XeroInvoice.tax_amount,
                        ),
                        else_=Decimal("0"),
                    )
                ).label("gst_collected"),
                func.sum(
                    case(
                        (
                            XeroInvoice.invoice_type == XeroInvoiceType.ACCPAY,
                            XeroInvoice.tax_amount,
                        ),
                        else_=Decimal("0"),
                    )
                ).label("gst_paid"),
                func.count(XeroInvoice.id).label("invoice_count"),
            )
            .where(
                and_(
                    XeroInvoice.issue_date >= quarter_start,
                    XeroInvoice.issue_date <= quarter_end,
                    XeroInvoice.status.in_(valid_statuses),
                )
            )
            .group_by(XeroInvoice.connection_id)
            .subquery()
        )

        # Subquery for transaction counts per connection
        txn_subq = (
            select(
                XeroBankTransaction.connection_id,
                func.count(XeroBankTransaction.id).label("txn_count"),
            )
            .where(
                and_(
                    XeroBankTransaction.transaction_date >= quarter_start,
                    XeroBankTransaction.transaction_date <= quarter_end,
                )
            )
            .group_by(XeroBankTransaction.connection_id)
            .subquery()
        )

        # Main query: count connections and aggregate financials
        query = (
            select(
                func.count(XeroConnection.id).label("total_clients"),
                func.count(
                    case(
                        (
                            or_(
                                invoice_subq.c.invoice_count > 0,
                                txn_subq.c.txn_count > 0,
                            ),
                            XeroConnection.id,
                        ),
                        else_=None,
                    )
                ).label("active_clients"),
                func.coalesce(func.sum(invoice_subq.c.sales), Decimal("0")).label("total_sales"),
                func.coalesce(func.sum(invoice_subq.c.purchases), Decimal("0")).label(
                    "total_purchases"
                ),
                func.coalesce(func.sum(invoice_subq.c.gst_collected), Decimal("0")).label(
                    "gst_collected"
                ),
                func.coalesce(func.sum(invoice_subq.c.gst_paid), Decimal("0")).label("gst_paid"),
                func.max(XeroConnection.last_full_sync_at).label("last_sync_at"),
            )
            .select_from(XeroConnection)
            .outerjoin(invoice_subq, XeroConnection.id == invoice_subq.c.connection_id)
            .outerjoin(txn_subq, XeroConnection.id == txn_subq.c.connection_id)
            .where(
                and_(
                    XeroConnection.tenant_id == tenant_id,
                    XeroConnection.status == XeroConnectionStatus.ACTIVE,
                )
            )
        )

        result = await self.db.execute(query)
        row = result.one()

        return {
            "total_clients": row.total_clients or 0,
            "active_clients": row.active_clients or 0,
            "total_sales": row.total_sales or Decimal("0"),
            "total_purchases": row.total_purchases or Decimal("0"),
            "gst_collected": row.gst_collected or Decimal("0"),
            "gst_paid": row.gst_paid or Decimal("0"),
            "last_sync_at": row.last_sync_at,
        }

    async def list_connections_with_financials(
        self,
        tenant_id: UUID,
        quarter_start: date,
        quarter_end: date,
        status: str | None = None,
        search: str | None = None,
        sort_by: str = "organization_name",
        sort_order: str = "asc",
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """List client businesses (connections) with their financial summaries.

        Each row = one XeroConnection = one business = one BAS to lodge.

        Returns tuple of (connections_list, total_count).
        """
        valid_statuses = [XeroInvoiceStatus.AUTHORISED, XeroInvoiceStatus.PAID]
        freshness_threshold = datetime.now(UTC) - timedelta(hours=24)

        # Invoice aggregates per connection
        invoice_subq = (
            select(
                XeroInvoice.connection_id,
                func.sum(
                    case(
                        (
                            XeroInvoice.invoice_type == XeroInvoiceType.ACCREC,
                            XeroInvoice.total_amount,
                        ),
                        else_=Decimal("0"),
                    )
                ).label("sales"),
                func.sum(
                    case(
                        (
                            XeroInvoice.invoice_type == XeroInvoiceType.ACCPAY,
                            XeroInvoice.total_amount,
                        ),
                        else_=Decimal("0"),
                    )
                ).label("purchases"),
                func.sum(
                    case(
                        (
                            XeroInvoice.invoice_type == XeroInvoiceType.ACCREC,
                            XeroInvoice.tax_amount,
                        ),
                        else_=Decimal("0"),
                    )
                ).label("gst_collected"),
                func.sum(
                    case(
                        (
                            XeroInvoice.invoice_type == XeroInvoiceType.ACCPAY,
                            XeroInvoice.tax_amount,
                        ),
                        else_=Decimal("0"),
                    )
                ).label("gst_paid"),
                func.count(XeroInvoice.id).label("invoice_count"),
            )
            .where(
                and_(
                    XeroInvoice.issue_date >= quarter_start,
                    XeroInvoice.issue_date <= quarter_end,
                    XeroInvoice.status.in_(valid_statuses),
                )
            )
            .group_by(XeroInvoice.connection_id)
            .subquery()
        )

        # Transaction counts per connection
        txn_subq = (
            select(
                XeroBankTransaction.connection_id,
                func.count(XeroBankTransaction.id).label("txn_count"),
            )
            .where(
                and_(
                    XeroBankTransaction.transaction_date >= quarter_start,
                    XeroBankTransaction.transaction_date <= quarter_end,
                )
            )
            .group_by(XeroBankTransaction.connection_id)
            .subquery()
        )

        # Build base query - one row per connection
        base_query = (
            select(
                XeroConnection.id,
                XeroConnection.organization_name,
                XeroConnection.last_full_sync_at,
                func.coalesce(invoice_subq.c.sales, Decimal("0")).label("total_sales"),
                func.coalesce(invoice_subq.c.purchases, Decimal("0")).label("total_purchases"),
                func.coalesce(invoice_subq.c.gst_collected, Decimal("0")).label("gst_collected"),
                func.coalesce(invoice_subq.c.gst_paid, Decimal("0")).label("gst_paid"),
                func.coalesce(invoice_subq.c.invoice_count, 0).label("invoice_count"),
                func.coalesce(txn_subq.c.txn_count, 0).label("transaction_count"),
            )
            .select_from(XeroConnection)
            .outerjoin(invoice_subq, XeroConnection.id == invoice_subq.c.connection_id)
            .outerjoin(txn_subq, XeroConnection.id == txn_subq.c.connection_id)
        )

        # Build filter conditions — include NEEDS_REAUTH so clients remain visible
        # with a reauth prompt, rather than silently disappearing from the list
        filters = [
            XeroConnection.tenant_id == tenant_id,
            XeroConnection.status.in_([
                XeroConnectionStatus.ACTIVE,
                XeroConnectionStatus.NEEDS_REAUTH,
            ]),
        ]

        if search:
            search_pattern = f"%{search}%"
            filters.append(XeroConnection.organization_name.ilike(search_pattern))

        base_query = base_query.where(and_(*filters))

        # Execute count query first (before status filter which is done in Python)
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await self.db.execute(count_query)
        total_count = total_result.scalar() or 0

        # Add sorting
        sort_columns = {
            "organization_name": XeroConnection.organization_name,
            "total_sales": invoice_subq.c.sales,
            "total_purchases": invoice_subq.c.purchases,
            "net_gst": (
                func.coalesce(invoice_subq.c.gst_collected, Decimal("0"))
                - func.coalesce(invoice_subq.c.gst_paid, Decimal("0"))
            ),
            "activity_count": (
                func.coalesce(invoice_subq.c.invoice_count, 0)
                + func.coalesce(txn_subq.c.txn_count, 0)
            ),
        }

        sort_col = sort_columns.get(sort_by, XeroConnection.organization_name)
        if sort_order == "desc":
            sort_col = sort_col.desc()

        # Add pagination
        query = base_query.order_by(sort_col).limit(limit).offset(offset)

        result = await self.db.execute(query)
        rows = result.all()

        # Process results and calculate BAS status per connection
        connections = []
        for row in rows:
            invoice_count = row.invoice_count or 0
            transaction_count = row.transaction_count or 0
            has_invoices = invoice_count > 0
            has_transactions = transaction_count > 0
            is_fresh = (
                row.last_full_sync_at is not None and row.last_full_sync_at > freshness_threshold
            )

            # Calculate BAS status for this business
            if not has_invoices and not has_transactions:
                bas_status = BASStatus.NO_ACTIVITY
            elif has_invoices != has_transactions:  # XOR - one but not both
                bas_status = BASStatus.MISSING_DATA
            elif is_fresh:
                bas_status = BASStatus.READY
            else:
                bas_status = BASStatus.NEEDS_REVIEW

            # Apply status filter if specified
            if status and bas_status.value != status:
                continue

            net_gst = (row.gst_collected or Decimal("0")) - (row.gst_paid or Decimal("0"))

            connections.append(
                {
                    "id": row.id,
                    "organization_name": row.organization_name,
                    "total_sales": row.total_sales or Decimal("0"),
                    "total_purchases": row.total_purchases or Decimal("0"),
                    "gst_collected": row.gst_collected or Decimal("0"),
                    "gst_paid": row.gst_paid or Decimal("0"),
                    "net_gst": net_gst,
                    "invoice_count": invoice_count,
                    "transaction_count": transaction_count,
                    "activity_count": invoice_count + transaction_count,
                    "bas_status": bas_status,
                    "last_synced_at": row.last_full_sync_at,
                }
            )

        return connections, total_count

    async def get_status_counts(
        self,
        tenant_id: UUID,
        quarter_start: date,
        quarter_end: date,
    ) -> dict[str, int]:
        """Get count of client businesses by BAS status.

        Returns count of connections (businesses) in each status category.
        """
        connections, _ = await self.list_connections_with_financials(
            tenant_id=tenant_id,
            quarter_start=quarter_start,
            quarter_end=quarter_end,
            limit=1000,  # High limit to get all connections
            offset=0,
        )

        counts = {
            "ready": 0,
            "needs_review": 0,
            "no_activity": 0,
            "missing_data": 0,
        }

        for conn in connections:
            status_key = conn["bas_status"].value
            counts[status_key] = counts.get(status_key, 0) + 1

        return counts
