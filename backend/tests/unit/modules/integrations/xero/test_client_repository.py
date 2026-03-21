"""Unit tests for Xero client repository methods.

Tests cover:
- XeroClientRepository.list_all_for_tenant
- XeroInvoiceRepository.list_by_client
- XeroInvoiceRepository.calculate_summary
- XeroBankTransactionRepository.list_by_client
- XeroBankTransactionRepository.count_by_client_and_date_range
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import (
    PracticeUser,
    SubscriptionStatus,
    Tenant,
    User,
    UserRole,
    UserType,
)
from app.modules.integrations.xero.models import (
    XeroBankTransaction,
    XeroBankTransactionType,
    XeroClient,
    XeroConnection,
    XeroConnectionStatus,
    XeroContactType,
    XeroInvoice,
    XeroInvoiceStatus,
    XeroInvoiceType,
)
from app.modules.integrations.xero.repository import (
    XeroBankTransactionRepository,
    XeroClientRepository,
    XeroInvoiceRepository,
)


async def set_tenant_context(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    """Set the tenant context for RLS."""
    await session.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))


@pytest.fixture
async def tenant(db_session: AsyncSession) -> Tenant:
    """Create test tenant."""
    tenant = Tenant(
        id=uuid.uuid4(),
        name="Test Practice",
        slug="test-practice",
        subscription_status=SubscriptionStatus.ACTIVE,
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


@pytest.fixture
async def user(db_session: AsyncSession) -> User:
    """Create test user."""
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        user_type=UserType.PRACTICE_USER,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def practice_user(db_session: AsyncSession, tenant: Tenant, user: User) -> PracticeUser:
    """Create practice user."""
    practice_user = PracticeUser(
        id=uuid.uuid4(),
        user_id=user.id,
        tenant_id=tenant.id,
        clerk_id="clerk_test_user",
        role=UserRole.ADMIN,
    )
    db_session.add(practice_user)
    await db_session.flush()
    return practice_user


@pytest.fixture
async def xero_connection(
    db_session: AsyncSession, tenant: Tenant, practice_user: PracticeUser
) -> XeroConnection:
    """Create Xero connection."""
    connection = XeroConnection(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        xero_tenant_id="xero-org-test-123",
        organization_name="Test Organization",
        status=XeroConnectionStatus.ACTIVE,
        access_token="[ENCRYPTED_TOKEN]",
        refresh_token="[ENCRYPTED_REFRESH]",
        token_expires_at=datetime.now(UTC) + timedelta(minutes=30),
        scopes=["openid", "profile", "accounting.transactions"],
        connected_by=practice_user.id,
        connected_at=datetime.now(UTC),
    )
    db_session.add(connection)
    await db_session.flush()
    return connection


@pytest.fixture
async def xero_clients(
    db_session: AsyncSession, tenant: Tenant, xero_connection: XeroConnection
) -> list[XeroClient]:
    """Create test Xero clients."""
    clients = [
        XeroClient(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            connection_id=xero_connection.id,
            xero_contact_id=f"xero-contact-{i}",
            name=f"Client {chr(65 + i)}",  # Client A, B, C, D, E
            email=f"client{chr(97 + i)}@example.com",
            contact_type=XeroContactType.CUSTOMER if i % 2 == 0 else XeroContactType.SUPPLIER,
            is_active=i != 4,  # Client E is inactive
        )
        for i in range(5)
    ]
    for client in clients:
        db_session.add(client)
    await db_session.flush()
    return clients


@pytest.fixture
async def xero_invoices(
    db_session: AsyncSession,
    tenant: Tenant,
    xero_connection: XeroConnection,
    xero_clients: list[XeroClient],
) -> list[XeroInvoice]:
    """Create test invoices for clients."""
    invoices = []
    # Create invoices for first client (Client A)
    client = xero_clients[0]

    # Sales invoice (ACCREC) - PAID
    invoices.append(
        XeroInvoice(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            connection_id=xero_connection.id,
            client_id=client.id,
            xero_invoice_id="INV-001",
            xero_contact_id=client.xero_contact_id,
            invoice_number="INV-001",
            invoice_type=XeroInvoiceType.ACCREC,
            status=XeroInvoiceStatus.PAID,
            issue_date=datetime(2024, 10, 15, tzinfo=UTC),  # Q2 FY25
            total_amount=Decimal("1100.00"),
            tax_amount=Decimal("100.00"),
            subtotal=Decimal("1000.00"),
        )
    )

    # Sales invoice (ACCREC) - AUTHORISED
    invoices.append(
        XeroInvoice(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            connection_id=xero_connection.id,
            client_id=client.id,
            xero_invoice_id="INV-002",
            xero_contact_id=client.xero_contact_id,
            invoice_number="INV-002",
            invoice_type=XeroInvoiceType.ACCREC,
            status=XeroInvoiceStatus.AUTHORISED,
            issue_date=datetime(2024, 11, 20, tzinfo=UTC),  # Q2 FY25
            total_amount=Decimal("550.00"),
            tax_amount=Decimal("50.00"),
            subtotal=Decimal("500.00"),
        )
    )

    # Purchase invoice (ACCPAY) - PAID
    invoices.append(
        XeroInvoice(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            connection_id=xero_connection.id,
            client_id=client.id,
            xero_invoice_id="BILL-001",
            xero_contact_id=client.xero_contact_id,
            invoice_number="BILL-001",
            invoice_type=XeroInvoiceType.ACCPAY,
            status=XeroInvoiceStatus.PAID,
            issue_date=datetime(2024, 10, 25, tzinfo=UTC),  # Q2 FY25
            total_amount=Decimal("330.00"),
            tax_amount=Decimal("30.00"),
            subtotal=Decimal("300.00"),
        )
    )

    # Draft invoice (should be excluded from summary)
    invoices.append(
        XeroInvoice(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            connection_id=xero_connection.id,
            client_id=client.id,
            xero_invoice_id="INV-003",
            xero_contact_id=client.xero_contact_id,
            invoice_number="INV-003",
            invoice_type=XeroInvoiceType.ACCREC,
            status=XeroInvoiceStatus.DRAFT,
            issue_date=datetime(2024, 11, 1, tzinfo=UTC),
            total_amount=Decimal("220.00"),
            tax_amount=Decimal("20.00"),
            subtotal=Decimal("200.00"),
        )
    )

    # Invoice outside Q2 (Q1 FY25)
    invoices.append(
        XeroInvoice(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            connection_id=xero_connection.id,
            client_id=client.id,
            xero_invoice_id="INV-004",
            xero_contact_id=client.xero_contact_id,
            invoice_number="INV-004",
            invoice_type=XeroInvoiceType.ACCREC,
            status=XeroInvoiceStatus.PAID,
            issue_date=datetime(2024, 8, 15, tzinfo=UTC),  # Q1 FY25
            total_amount=Decimal("440.00"),
            tax_amount=Decimal("40.00"),
            subtotal=Decimal("400.00"),
        )
    )

    for invoice in invoices:
        db_session.add(invoice)
    await db_session.flush()
    return invoices


@pytest.fixture
async def xero_transactions(
    db_session: AsyncSession,
    tenant: Tenant,
    xero_connection: XeroConnection,
    xero_clients: list[XeroClient],
) -> list[XeroBankTransaction]:
    """Create test bank transactions."""
    transactions = []
    client = xero_clients[0]

    # Receive transaction in Q2 FY25
    transactions.append(
        XeroBankTransaction(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            connection_id=xero_connection.id,
            client_id=client.id,
            xero_transaction_id="TXN-001",
            xero_contact_id=client.xero_contact_id,
            transaction_type=XeroBankTransactionType.RECEIVE,
            status="AUTHORISED",
            transaction_date=datetime(2024, 10, 20, tzinfo=UTC),
            reference="Payment received",
            total_amount=Decimal("1100.00"),
            tax_amount=Decimal("100.00"),
        )
    )

    # Spend transaction in Q2 FY25
    transactions.append(
        XeroBankTransaction(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            connection_id=xero_connection.id,
            client_id=client.id,
            xero_transaction_id="TXN-002",
            xero_contact_id=client.xero_contact_id,
            transaction_type=XeroBankTransactionType.SPEND,
            status="AUTHORISED",
            transaction_date=datetime(2024, 11, 5, tzinfo=UTC),
            reference="Supplier payment",
            total_amount=Decimal("330.00"),
            tax_amount=Decimal("30.00"),
        )
    )

    # Transaction outside Q2 (Q1 FY25)
    transactions.append(
        XeroBankTransaction(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            connection_id=xero_connection.id,
            client_id=client.id,
            xero_transaction_id="TXN-003",
            xero_contact_id=client.xero_contact_id,
            transaction_type=XeroBankTransactionType.RECEIVE,
            status="AUTHORISED",
            transaction_date=datetime(2024, 8, 10, tzinfo=UTC),  # Q1 FY25
            reference="Old payment",
            total_amount=Decimal("500.00"),
            tax_amount=Decimal("45.45"),
        )
    )

    for txn in transactions:
        db_session.add(txn)
    await db_session.flush()
    return transactions


@pytest.mark.integration
class TestXeroClientRepository:
    """Tests for XeroClientRepository."""

    async def test_list_all_for_tenant_returns_all_clients(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        xero_clients: list[XeroClient],
    ) -> None:
        """Should return all clients for tenant."""
        await db_session.commit()
        await set_tenant_context(db_session, tenant.id)

        repo = XeroClientRepository(db_session)
        clients, total = await repo.list_all_for_tenant()

        assert total == 5
        assert len(clients) == 5

    async def test_list_all_for_tenant_with_search(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        xero_clients: list[XeroClient],
    ) -> None:
        """Should filter clients by search term."""
        await db_session.commit()
        await set_tenant_context(db_session, tenant.id)

        repo = XeroClientRepository(db_session)
        clients, total = await repo.list_all_for_tenant(search="Client A")

        assert total == 1
        assert clients[0].name == "Client A"

    async def test_list_all_for_tenant_with_contact_type_filter(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        xero_clients: list[XeroClient],
    ) -> None:
        """Should filter clients by contact type."""
        await db_session.commit()
        await set_tenant_context(db_session, tenant.id)

        repo = XeroClientRepository(db_session)
        clients, total = await repo.list_all_for_tenant(contact_type="customer")

        # Clients A, C, E are customers (indices 0, 2, 4)
        assert total == 3

    async def test_list_all_for_tenant_with_is_active_filter(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        xero_clients: list[XeroClient],
    ) -> None:
        """Should filter clients by active status."""
        await db_session.commit()
        await set_tenant_context(db_session, tenant.id)

        repo = XeroClientRepository(db_session)
        clients, total = await repo.list_all_for_tenant(is_active=True)

        # 4 clients are active (Client E is inactive)
        assert total == 4

    async def test_list_all_for_tenant_with_pagination(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        xero_clients: list[XeroClient],
    ) -> None:
        """Should paginate results correctly."""
        await db_session.commit()
        await set_tenant_context(db_session, tenant.id)

        repo = XeroClientRepository(db_session)

        # First page
        clients, total = await repo.list_all_for_tenant(limit=2, offset=0)
        assert len(clients) == 2
        assert total == 5

        # Second page
        clients, total = await repo.list_all_for_tenant(limit=2, offset=2)
        assert len(clients) == 2
        assert total == 5


@pytest.mark.integration
class TestXeroInvoiceRepository:
    """Tests for XeroInvoiceRepository."""

    async def test_list_by_client_returns_client_invoices(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        xero_clients: list[XeroClient],
        xero_invoices: list[XeroInvoice],
    ) -> None:
        """Should return invoices for specified client."""
        await db_session.commit()
        await set_tenant_context(db_session, tenant.id)

        repo = XeroInvoiceRepository(db_session)
        client = xero_clients[0]

        invoices, total = await repo.list_by_client(client.id)

        assert total == 5
        assert len(invoices) == 5

    async def test_list_by_client_with_type_filter(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        xero_clients: list[XeroClient],
        xero_invoices: list[XeroInvoice],
    ) -> None:
        """Should filter invoices by type."""
        await db_session.commit()
        await set_tenant_context(db_session, tenant.id)

        repo = XeroInvoiceRepository(db_session)
        client = xero_clients[0]

        invoices, total = await repo.list_by_client(client.id, invoice_type="accrec")

        # 4 ACCREC invoices
        assert total == 4

    async def test_list_by_client_with_date_range(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        xero_clients: list[XeroClient],
        xero_invoices: list[XeroInvoice],
    ) -> None:
        """Should filter invoices by date range."""
        await db_session.commit()
        await set_tenant_context(db_session, tenant.id)

        repo = XeroInvoiceRepository(db_session)
        client = xero_clients[0]

        # Q2 FY25: Oct 1 - Dec 31, 2024
        invoices, total = await repo.list_by_client(
            client.id,
            from_date=date(2024, 10, 1),
            to_date=date(2024, 12, 31),
        )

        # 4 invoices in Q2 (excluding INV-004 from Q1)
        assert total == 4

    async def test_calculate_summary_returns_correct_totals(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        xero_clients: list[XeroClient],
        xero_invoices: list[XeroInvoice],
    ) -> None:
        """Should calculate correct invoice summary for quarter."""
        await db_session.commit()
        await set_tenant_context(db_session, tenant.id)

        repo = XeroInvoiceRepository(db_session)
        client = xero_clients[0]

        # Q2 FY25: Oct 1 - Dec 31, 2024
        summary = await repo.calculate_summary(
            client.id,
            from_date=date(2024, 10, 1),
            to_date=date(2024, 12, 31),
        )

        # Only PAID and AUTHORISED invoices included
        # Sales (ACCREC): INV-001 ($1100) + INV-002 ($550) = $1650
        # Purchases (ACCPAY): BILL-001 ($330) = $330
        # Draft INV-003 excluded
        assert summary["total_sales"] == Decimal("1650.00")
        assert summary["gst_collected"] == Decimal("150.00")  # $100 + $50
        assert summary["total_purchases"] == Decimal("330.00")
        assert summary["gst_paid"] == Decimal("30.00")
        assert summary["sales_invoice_count"] == 2
        assert summary["purchase_invoice_count"] == 1

    async def test_calculate_summary_empty_period(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        xero_clients: list[XeroClient],
        xero_invoices: list[XeroInvoice],
    ) -> None:
        """Should return zeros for period with no invoices."""
        await db_session.commit()
        await set_tenant_context(db_session, tenant.id)

        repo = XeroInvoiceRepository(db_session)
        client = xero_clients[0]

        # Q4 FY25: Apr 1 - Jun 30, 2025 (no invoices)
        summary = await repo.calculate_summary(
            client.id,
            from_date=date(2025, 4, 1),
            to_date=date(2025, 6, 30),
        )

        assert summary["total_sales"] == Decimal("0.00")
        assert summary["gst_collected"] == Decimal("0.00")
        assert summary["total_purchases"] == Decimal("0.00")
        assert summary["gst_paid"] == Decimal("0.00")
        assert summary["sales_invoice_count"] == 0
        assert summary["purchase_invoice_count"] == 0


@pytest.mark.integration
class TestXeroBankTransactionRepository:
    """Tests for XeroBankTransactionRepository."""

    async def test_list_by_client_returns_client_transactions(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        xero_clients: list[XeroClient],
        xero_transactions: list[XeroBankTransaction],
    ) -> None:
        """Should return transactions for specified client."""
        await db_session.commit()
        await set_tenant_context(db_session, tenant.id)

        repo = XeroBankTransactionRepository(db_session)
        client = xero_clients[0]

        transactions, total = await repo.list_by_client(client.id)

        assert total == 3
        assert len(transactions) == 3

    async def test_list_by_client_with_date_range(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        xero_clients: list[XeroClient],
        xero_transactions: list[XeroBankTransaction],
    ) -> None:
        """Should filter transactions by date range."""
        await db_session.commit()
        await set_tenant_context(db_session, tenant.id)

        repo = XeroBankTransactionRepository(db_session)
        client = xero_clients[0]

        # Q2 FY25
        transactions, total = await repo.list_by_client(
            client.id,
            from_date=date(2024, 10, 1),
            to_date=date(2024, 12, 31),
        )

        # 2 transactions in Q2 (excluding TXN-003 from Q1)
        assert total == 2

    async def test_count_by_client_and_date_range(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        xero_clients: list[XeroClient],
        xero_transactions: list[XeroBankTransaction],
    ) -> None:
        """Should count transactions in date range."""
        await db_session.commit()
        await set_tenant_context(db_session, tenant.id)

        repo = XeroBankTransactionRepository(db_session)
        client = xero_clients[0]

        # Q2 FY25
        count = await repo.count_by_client_and_date_range(
            client.id,
            from_date=date(2024, 10, 1),
            to_date=date(2024, 12, 31),
        )

        assert count == 2

    async def test_count_by_client_empty_period(
        self,
        db_session: AsyncSession,
        tenant: Tenant,
        xero_clients: list[XeroClient],
        xero_transactions: list[XeroBankTransaction],
    ) -> None:
        """Should return 0 for period with no transactions."""
        await db_session.commit()
        await set_tenant_context(db_session, tenant.id)

        repo = XeroBankTransactionRepository(db_session)
        client = xero_clients[0]

        # Q4 FY25 (no transactions)
        count = await repo.count_by_client_and_date_range(
            client.id,
            from_date=date(2025, 4, 1),
            to_date=date(2025, 6, 30),
        )

        assert count == 0
