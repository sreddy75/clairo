"""Repository for client business data access.

CRITICAL: In Clairo, "client" = XeroConnection = one business = one BAS to lodge.
This repository fetches data for individual client businesses.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.clients.schemas import (
    BASStatus,
    ContactType,
    InvoiceStatus,
    InvoiceType,
    TransactionType,
)
from app.modules.integrations.xero.models import (
    XeroBankTransaction,
    XeroBankTransactionType,
    XeroClient,
    XeroConnection,
    XeroContactType,
    XeroInvoice,
    XeroInvoiceStatus,
    XeroInvoiceType,
    XpmClient,
)


class ClientsRepository:
    """Repository for client business data access."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_connection(
        self,
        tenant_id: UUID,
        connection_id: UUID,
    ) -> XeroConnection | None:
        """Get a single connection by ID."""
        query = select(XeroConnection).where(
            and_(
                XeroConnection.tenant_id == tenant_id,
                XeroConnection.id == connection_id,
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_connection_with_financials(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        quarter_start: date,
        quarter_end: date,
    ) -> dict[str, Any] | None:
        """Get connection with financial summary for a quarter."""
        valid_statuses = [XeroInvoiceStatus.AUTHORISED, XeroInvoiceStatus.PAID]
        freshness_threshold = datetime.now(UTC) - timedelta(hours=24)

        # Invoice aggregates
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
                    XeroInvoice.connection_id == connection_id,
                    XeroInvoice.issue_date >= quarter_start,
                    XeroInvoice.issue_date <= quarter_end,
                    XeroInvoice.status.in_(valid_statuses),
                )
            )
            .group_by(XeroInvoice.connection_id)
            .subquery()
        )

        # Transaction count
        txn_subq = (
            select(
                XeroBankTransaction.connection_id,
                func.count(XeroBankTransaction.id).label("txn_count"),
            )
            .where(
                and_(
                    XeroBankTransaction.connection_id == connection_id,
                    XeroBankTransaction.transaction_date >= quarter_start,
                    XeroBankTransaction.transaction_date <= quarter_end,
                )
            )
            .group_by(XeroBankTransaction.connection_id)
            .subquery()
        )

        # Contact count
        contact_count_subq = (
            select(func.count(XeroClient.id).label("contact_count"))
            .where(XeroClient.connection_id == connection_id)
            .scalar_subquery()
        )

        # XPM Client email (linked via xero_connection_id) - fallback source
        xpm_email_subq = (
            select(XpmClient.email)
            .where(XpmClient.xero_connection_id == connection_id)
            .scalar_subquery()
        )

        # Main query
        query = (
            select(
                XeroConnection.id,
                XeroConnection.organization_name,
                XeroConnection.xero_tenant_id,
                XeroConnection.status,
                XeroConnection.last_full_sync_at,
                XeroConnection.has_payroll_access,
                XeroConnection.last_payroll_sync_at,
                func.coalesce(invoice_subq.c.sales, Decimal("0")).label("total_sales"),
                func.coalesce(invoice_subq.c.purchases, Decimal("0")).label("total_purchases"),
                func.coalesce(invoice_subq.c.gst_collected, Decimal("0")).label("gst_collected"),
                func.coalesce(invoice_subq.c.gst_paid, Decimal("0")).label("gst_paid"),
                func.coalesce(invoice_subq.c.invoice_count, 0).label("invoice_count"),
                func.coalesce(txn_subq.c.txn_count, 0).label("transaction_count"),
                func.coalesce(contact_count_subq, 0).label("contact_count"),
                # Use XeroConnection.primary_contact_email first, fallback to XpmClient.email
                func.coalesce(XeroConnection.primary_contact_email, xpm_email_subq).label(
                    "contact_email"
                ),
            )
            .select_from(XeroConnection)
            .outerjoin(invoice_subq, XeroConnection.id == invoice_subq.c.connection_id)
            .outerjoin(txn_subq, XeroConnection.id == txn_subq.c.connection_id)
            .where(
                and_(
                    XeroConnection.tenant_id == tenant_id,
                    XeroConnection.id == connection_id,
                )
            )
        )

        result = await self.db.execute(query)
        row = result.one_or_none()

        if not row:
            return None

        # Calculate BAS status
        invoice_count = row.invoice_count or 0
        transaction_count = row.transaction_count or 0
        has_invoices = invoice_count > 0
        has_transactions = transaction_count > 0
        is_fresh = row.last_full_sync_at is not None and row.last_full_sync_at > freshness_threshold

        if not has_invoices and not has_transactions:
            bas_status = BASStatus.NO_ACTIVITY
        elif has_invoices != has_transactions:
            bas_status = BASStatus.MISSING_DATA
        elif is_fresh:
            bas_status = BASStatus.READY
        else:
            bas_status = BASStatus.NEEDS_REVIEW

        net_gst = (row.gst_collected or Decimal("0")) - (row.gst_paid or Decimal("0"))

        return {
            "id": row.id,
            "organization_name": row.organization_name,
            "xero_tenant_id": row.xero_tenant_id,
            "status": str(row.status),
            "last_full_sync_at": row.last_full_sync_at,
            "has_payroll_access": row.has_payroll_access or False,
            "last_payroll_sync_at": row.last_payroll_sync_at,
            "bas_status": bas_status,
            "total_sales": row.total_sales or Decimal("0"),
            "total_purchases": row.total_purchases or Decimal("0"),
            "gst_collected": row.gst_collected or Decimal("0"),
            "gst_paid": row.gst_paid or Decimal("0"),
            "net_gst": net_gst,
            "invoice_count": invoice_count,
            "transaction_count": transaction_count,
            "contact_count": row.contact_count or 0,
            "contact_email": row.contact_email,
        }

    async def list_contacts(
        self,
        connection_id: UUID,
        contact_type: str | None = None,
        search: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """List contacts for a connection."""
        # Base query
        base_query = select(XeroClient).where(XeroClient.connection_id == connection_id)

        # Apply filters
        if contact_type:
            type_map = {
                "customer": XeroContactType.CUSTOMER,
                "supplier": XeroContactType.SUPPLIER,
                "both": XeroContactType.BOTH,
            }
            if contact_type.lower() in type_map:
                base_query = base_query.where(
                    XeroClient.contact_type == type_map[contact_type.lower()]
                )

        if search:
            search_pattern = f"%{search}%"
            base_query = base_query.where(
                XeroClient.name.ilike(search_pattern) | XeroClient.abn.ilike(search_pattern)
            )

        # Count total
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Fetch paginated results
        query = base_query.order_by(XeroClient.name).limit(limit).offset(offset)
        result = await self.db.execute(query)
        rows = result.scalars().all()

        contacts = []
        for row in rows:
            contacts.append(
                {
                    "id": row.id,
                    "name": row.name,
                    "email": row.email,
                    "contact_number": row.contact_number,
                    "abn": row.abn,
                    "contact_type": ContactType(row.contact_type.value),
                    "is_active": row.is_active,
                    "addresses": row.addresses,
                    "phones": row.phones,
                }
            )

        return contacts, total

    async def list_invoices(
        self,
        connection_id: UUID,
        invoice_type: str | None = None,
        status: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        sort_by: str = "issue_date",
        sort_order: str = "desc",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """List invoices for a connection."""
        # Build base query with contact name join
        contact_subq = (
            select(XeroClient.xero_contact_id, XeroClient.name.label("contact_name"))
            .where(XeroClient.connection_id == connection_id)
            .subquery()
        )

        base_query = (
            select(
                XeroInvoice,
                contact_subq.c.contact_name,
            )
            .outerjoin(contact_subq, XeroInvoice.xero_contact_id == contact_subq.c.xero_contact_id)
            .where(XeroInvoice.connection_id == connection_id)
        )

        # Apply filters
        if invoice_type:
            type_map = {
                "accrec": XeroInvoiceType.ACCREC,
                "accpay": XeroInvoiceType.ACCPAY,
            }
            if invoice_type.lower() in type_map:
                base_query = base_query.where(
                    XeroInvoice.invoice_type == type_map[invoice_type.lower()]
                )

        if status:
            status_map = {
                "draft": XeroInvoiceStatus.DRAFT,
                "submitted": XeroInvoiceStatus.SUBMITTED,
                "authorised": XeroInvoiceStatus.AUTHORISED,
                "paid": XeroInvoiceStatus.PAID,
                "voided": XeroInvoiceStatus.VOIDED,
            }
            if status.lower() in status_map:
                base_query = base_query.where(XeroInvoice.status == status_map[status.lower()])

        if from_date:
            base_query = base_query.where(XeroInvoice.issue_date >= from_date)

        if to_date:
            base_query = base_query.where(XeroInvoice.issue_date <= to_date)

        # Count total
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply sorting
        sort_columns = {
            "issue_date": XeroInvoice.issue_date,
            "due_date": XeroInvoice.due_date,
            "total_amount": XeroInvoice.total_amount,
            "invoice_number": XeroInvoice.invoice_number,
        }
        sort_col = sort_columns.get(sort_by, XeroInvoice.issue_date)
        order_clause = sort_col.desc() if sort_order == "desc" else sort_col.asc()

        query = base_query.order_by(order_clause).limit(limit).offset(offset)
        result = await self.db.execute(query)
        rows = result.all()

        invoices = []
        for row in rows:
            invoice = row[0]  # XeroInvoice object
            contact_name = row[1]  # contact_name from join

            # Parse line items if present
            line_items = None
            if invoice.line_items:
                line_items = [
                    {
                        "description": item.get("description"),
                        "quantity": item.get("quantity"),
                        "unit_amount": item.get("unit_amount"),
                        "account_code": item.get("account_code"),
                        "tax_type": item.get("tax_type"),
                        "line_amount": item.get("line_amount"),
                    }
                    for item in invoice.line_items
                ]

            invoices.append(
                {
                    "id": invoice.id,
                    "invoice_number": invoice.invoice_number,
                    "invoice_type": InvoiceType(invoice.invoice_type.value),
                    "contact_name": contact_name,
                    "status": InvoiceStatus(invoice.status.value),
                    "issue_date": invoice.issue_date,
                    "due_date": invoice.due_date,
                    "subtotal": invoice.subtotal,
                    "tax_amount": invoice.tax_amount,
                    "total_amount": invoice.total_amount,
                    "currency": invoice.currency,
                    "line_items": line_items,
                }
            )

        return invoices, total

    async def list_transactions(
        self,
        connection_id: UUID,
        transaction_type: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        sort_by: str = "transaction_date",
        sort_order: str = "desc",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """List bank transactions for a connection."""
        # Build base query with contact name join
        contact_subq = (
            select(XeroClient.xero_contact_id, XeroClient.name.label("contact_name"))
            .where(XeroClient.connection_id == connection_id)
            .subquery()
        )

        base_query = (
            select(
                XeroBankTransaction,
                contact_subq.c.contact_name,
            )
            .outerjoin(
                contact_subq, XeroBankTransaction.xero_contact_id == contact_subq.c.xero_contact_id
            )
            .where(XeroBankTransaction.connection_id == connection_id)
        )

        # Apply filters
        if transaction_type:
            type_map = {
                "receive": XeroBankTransactionType.RECEIVE,
                "spend": XeroBankTransactionType.SPEND,
            }
            if transaction_type.lower() in type_map:
                base_query = base_query.where(
                    XeroBankTransaction.transaction_type == type_map[transaction_type.lower()]
                )

        if from_date:
            base_query = base_query.where(XeroBankTransaction.transaction_date >= from_date)

        if to_date:
            base_query = base_query.where(XeroBankTransaction.transaction_date <= to_date)

        # Count total
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply sorting
        sort_columns = {
            "transaction_date": XeroBankTransaction.transaction_date,
            "total_amount": XeroBankTransaction.total_amount,
        }
        sort_col = sort_columns.get(sort_by, XeroBankTransaction.transaction_date)
        order_clause = sort_col.desc() if sort_order == "desc" else sort_col.asc()

        query = base_query.order_by(order_clause).limit(limit).offset(offset)
        result = await self.db.execute(query)
        rows = result.all()

        transactions = []
        for row in rows:
            txn = row[0]  # XeroBankTransaction object
            contact_name = row[1]  # contact_name from join

            transactions.append(
                {
                    "id": txn.id,
                    "transaction_type": TransactionType(txn.transaction_type.value),
                    "contact_name": contact_name,
                    "status": txn.status,
                    "transaction_date": txn.transaction_date,
                    "reference": txn.reference,
                    "subtotal": txn.subtotal,
                    "tax_amount": txn.tax_amount,
                    "total_amount": txn.total_amount,
                }
            )

        return transactions, total
