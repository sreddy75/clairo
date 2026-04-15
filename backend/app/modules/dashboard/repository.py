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

from app.modules.clients.models import (
    ClientQuarterExclusion,
    PracticeClient,
)
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
                    XeroConnection.status.in_(
                        [
                            XeroConnectionStatus.ACTIVE,
                            XeroConnectionStatus.NEEDS_REAUTH,
                        ]
                    ),
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
        assigned_user_id: UUID | None = None,
        show_excluded: bool = False,
        software: str | None = None,
        quarter: int | None = None,
        fy_year: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """List practice clients with their financial summaries.

        Drives from practice_clients, LEFT JOINs xero_connections for
        financial data. Non-Xero clients appear with zero financials.

        Returns tuple of (clients_list, total_count).
        """
        from app.modules.auth.models import PracticeUser

        valid_statuses = [XeroInvoiceStatus.AUTHORISED, XeroInvoiceStatus.PAID]
        freshness_threshold = datetime.now(UTC) - timedelta(hours=24)
        unreconciled_threshold = 5

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

        # Unreconciled transaction counts per connection
        unrec_subq = (
            select(
                XeroBankTransaction.connection_id,
                func.count(XeroBankTransaction.id).label("unrec_count"),
            )
            .where(
                and_(
                    XeroBankTransaction.transaction_date >= quarter_start,
                    XeroBankTransaction.transaction_date <= quarter_end,
                    XeroBankTransaction.is_reconciled.is_(False),
                )
            )
            .group_by(XeroBankTransaction.connection_id)
            .subquery()
        )

        # Exclusion subquery for the selected quarter
        exclusion_subq = (
            select(
                ClientQuarterExclusion.client_id,
                ClientQuarterExclusion.id.label("exclusion_id"),
                ClientQuarterExclusion.reason.label("exclusion_reason"),
                ClientQuarterExclusion.excluded_at,
                ClientQuarterExclusion.excluded_by,
            )
            .where(
                and_(
                    ClientQuarterExclusion.reversed_at.is_(None),
                    *([ClientQuarterExclusion.quarter == quarter] if quarter else []),
                    *([ClientQuarterExclusion.fy_year == fy_year] if fy_year else []),
                )
            )
            .subquery()
        )

        # Assignee alias for join
        assignee = select(
            PracticeUser.id.label("pu_id"),
            PracticeUser.display_name.label("pu_display_name"),
            PracticeUser.user_id.label("pu_user_id"),
        ).subquery()

        # Build base query — one row per PracticeClient
        base_query = (
            select(
                PracticeClient.id,
                PracticeClient.name.label("organization_name"),
                PracticeClient.assigned_user_id,
                PracticeClient.accounting_software,
                PracticeClient.xero_connection_id,
                PracticeClient.notes,
                PracticeClient.manual_status,
                XeroConnection.last_full_sync_at,
                func.coalesce(invoice_subq.c.sales, Decimal("0")).label("total_sales"),
                func.coalesce(invoice_subq.c.purchases, Decimal("0")).label("total_purchases"),
                func.coalesce(invoice_subq.c.gst_collected, Decimal("0")).label("gst_collected"),
                func.coalesce(invoice_subq.c.gst_paid, Decimal("0")).label("gst_paid"),
                func.coalesce(invoice_subq.c.invoice_count, 0).label("invoice_count"),
                func.coalesce(txn_subq.c.txn_count, 0).label("transaction_count"),
                func.coalesce(unrec_subq.c.unrec_count, 0).label("unreconciled_count"),
                assignee.c.pu_display_name.label("assigned_user_display_name"),
                exclusion_subq.c.exclusion_id,
                exclusion_subq.c.exclusion_reason,
                exclusion_subq.c.excluded_at,
            )
            .select_from(PracticeClient)
            .outerjoin(
                XeroConnection,
                PracticeClient.xero_connection_id == XeroConnection.id,
            )
            .outerjoin(
                invoice_subq,
                XeroConnection.id == invoice_subq.c.connection_id,
            )
            .outerjoin(
                txn_subq,
                XeroConnection.id == txn_subq.c.connection_id,
            )
            .outerjoin(
                unrec_subq,
                XeroConnection.id == unrec_subq.c.connection_id,
            )
            .outerjoin(
                assignee,
                PracticeClient.assigned_user_id == assignee.c.pu_id,
            )
            .outerjoin(
                exclusion_subq,
                PracticeClient.id == exclusion_subq.c.client_id,
            )
        )

        # Build filter conditions
        filters: list = [PracticeClient.tenant_id == tenant_id]

        # For Xero clients, only show active/needs_reauth connections
        # For non-Xero clients (xero_connection_id IS NULL), always show
        filters.append(
            or_(
                PracticeClient.xero_connection_id.is_(None),
                XeroConnection.status.in_([
                    XeroConnectionStatus.ACTIVE,
                    XeroConnectionStatus.NEEDS_REAUTH,
                ]),
            )
        )

        # Exclusion filter
        if show_excluded:
            filters.append(exclusion_subq.c.exclusion_id.isnot(None))
        else:
            filters.append(exclusion_subq.c.exclusion_id.is_(None))

        # Assigned user filter
        if assigned_user_id is not None:
            filters.append(PracticeClient.assigned_user_id == assigned_user_id)

        # Software filter
        if software:
            filters.append(PracticeClient.accounting_software == software)

        if search:
            search_pattern = f"%{search}%"
            filters.append(PracticeClient.name.ilike(search_pattern))

        base_query = base_query.where(and_(*filters))

        # Execute count query first (before status filter which is done in Python)
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await self.db.execute(count_query)
        total_count = total_result.scalar() or 0

        # Add sorting
        sort_columns = {
            "organization_name": PracticeClient.name,
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

        sort_col = sort_columns.get(sort_by, PracticeClient.name)
        if sort_order == "desc":
            sort_col = sort_col.desc()

        # Add pagination
        query = base_query.order_by(sort_col).limit(limit).offset(offset)

        result = await self.db.execute(query)
        rows = result.all()

        # Process results and calculate BAS status per client
        connections = []
        for row in rows:
            has_xero = row.xero_connection_id is not None
            invoice_count = row.invoice_count or 0
            transaction_count = row.transaction_count or 0
            unreconciled_count = row.unreconciled_count or 0

            # BAS status derivation
            if not has_xero:
                # Non-Xero clients use manual status
                manual = row.manual_status or "not_started"
                manual_to_bas = {
                    "not_started": BASStatus.NO_ACTIVITY,
                    "in_progress": BASStatus.NEEDS_REVIEW,
                    "completed": BASStatus.READY,
                    "lodged": BASStatus.READY,
                }
                bas_status = manual_to_bas.get(manual, BASStatus.NO_ACTIVITY)
            else:
                has_invoices = invoice_count > 0
                has_transactions = transaction_count > 0
                is_fresh = (
                    row.last_full_sync_at is not None
                    and row.last_full_sync_at > freshness_threshold
                )

                if not has_invoices and not has_transactions:
                    bas_status = BASStatus.NO_ACTIVITY
                elif has_invoices != has_transactions:
                    bas_status = BASStatus.MISSING_DATA
                elif is_fresh:
                    # Check unreconciled threshold (Spec 058 - US5)
                    if unreconciled_count > unreconciled_threshold:
                        bas_status = BASStatus.NEEDS_REVIEW
                    else:
                        bas_status = BASStatus.READY
                else:
                    bas_status = BASStatus.NEEDS_REVIEW

            # Apply status filter if specified
            if status and bas_status.value != status:
                continue

            net_gst = (row.gst_collected or Decimal("0")) - (row.gst_paid or Decimal("0"))

            # Get assignee name
            assigned_name = row.assigned_user_display_name
            # Fallback: email will be resolved by the service layer if needed

            # Notes preview
            notes_text = row.notes or ""
            notes_preview = (notes_text[:100] + "...") if len(notes_text) > 100 else (notes_text or None)

            client_dict: dict[str, Any] = {
                "id": row.id,
                "organization_name": row.organization_name,
                "assigned_user_id": row.assigned_user_id,
                "assigned_user_name": assigned_name,
                "accounting_software": row.accounting_software,
                "has_xero_connection": has_xero,
                "notes_preview": notes_preview if notes_preview else None,
                "unreconciled_count": unreconciled_count,
                "manual_status": row.manual_status,
                "total_sales": row.total_sales or Decimal("0"),
                "total_purchases": row.total_purchases or Decimal("0"),
                "gst_collected": row.gst_collected or Decimal("0"),
                "gst_paid": row.gst_paid or Decimal("0"),
                "net_gst": net_gst,
                "invoice_count": invoice_count,
                "transaction_count": transaction_count,
                "activity_count": invoice_count + transaction_count,
                "bas_status": bas_status,
                "last_synced_at": row.last_full_sync_at if has_xero else None,
                "exclusion": None,
            }

            # Add exclusion data if showing excluded
            if show_excluded and row.exclusion_id:
                client_dict["exclusion"] = {
                    "id": row.exclusion_id,
                    "reason": row.exclusion_reason,
                    "excluded_by_name": None,  # Resolved in service layer
                    "excluded_at": row.excluded_at,
                }

            connections.append(client_dict)

        return connections, total_count

    async def get_status_counts(
        self,
        tenant_id: UUID,
        quarter_start: date,
        quarter_end: date,
        assigned_user_id: UUID | None = None,
        quarter: int | None = None,
        fy_year: str | None = None,
    ) -> dict[str, int]:
        """Get count of clients by BAS status.

        Returns count of practice clients in each status category,
        excluding excluded clients.
        """
        connections, _ = await self.list_connections_with_financials(
            tenant_id=tenant_id,
            quarter_start=quarter_start,
            quarter_end=quarter_end,
            assigned_user_id=assigned_user_id,
            quarter=quarter,
            fy_year=fy_year,
            limit=1000,
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

    async def get_excluded_count(
        self,
        tenant_id: UUID,
        quarter: int | None = None,
        fy_year: str | None = None,
    ) -> int:
        """Get count of excluded clients for a quarter."""
        filters = [
            ClientQuarterExclusion.tenant_id == tenant_id,
            ClientQuarterExclusion.reversed_at.is_(None),
        ]
        if quarter:
            filters.append(ClientQuarterExclusion.quarter == quarter)
        if fy_year:
            filters.append(ClientQuarterExclusion.fy_year == fy_year)

        result = await self.db.execute(
            select(func.count()).select_from(
                select(ClientQuarterExclusion.id).where(and_(*filters)).subquery()
            )
        )
        return result.scalar() or 0
