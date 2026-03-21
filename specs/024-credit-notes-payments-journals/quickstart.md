# Quickstart: Credit Notes, Payments & Journals

**Feature**: 024-credit-notes-payments-journals
**Date**: 2026-01-01

This guide helps developers implement the credit notes, payments, and journals sync feature.

---

## Prerequisites

1. **Xero OAuth Connection**: Client must have valid Xero connection (Spec 003)
2. **Existing Sync Infrastructure**: Invoices sync working (Spec 004)
3. **Database Migrations**: Run before starting implementation

---

## Quick Implementation Guide

### Step 1: Add Database Models

```python
# backend/app/modules/integrations/xero/models.py

from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey, Enum, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum

class CreditNoteType(str, enum.Enum):
    ACCPAYCREDIT = "ACCPAYCREDIT"  # From supplier
    ACCRECCREDIT = "ACCRECCREDIT"  # To customer

class CreditNoteStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    AUTHORISED = "AUTHORISED"
    PAID = "PAID"
    VOIDED = "VOIDED"

class XeroCreditNote(TenantBase):
    __tablename__ = "xero_credit_notes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    connection_id = Column(UUID(as_uuid=True), ForeignKey("xero_connections.id"), nullable=False)
    xero_credit_note_id = Column(UUID(as_uuid=True), nullable=False, unique=True)
    credit_note_number = Column(String(255))
    type = Column(Enum(CreditNoteType), nullable=False)
    contact_id = Column(UUID(as_uuid=True), ForeignKey("xero_contacts.id"))
    date = Column(DateTime(timezone=True), nullable=False)
    due_date = Column(DateTime(timezone=True))
    status = Column(Enum(CreditNoteStatus), nullable=False)
    line_amount_types = Column(String(50))
    sub_total = Column(Numeric(15, 2), default=0)
    total_tax = Column(Numeric(15, 2), default=0)
    total = Column(Numeric(15, 2), default=0)
    remaining_credit = Column(Numeric(15, 2), default=0)
    currency_code = Column(String(3), default="AUD")
    currency_rate = Column(Numeric(15, 6), default=1)
    line_items = Column(JSONB, default=list)
    xero_updated_at = Column(DateTime(timezone=True))

    # Relationships
    connection = relationship("XeroConnection", back_populates="credit_notes")
    contact = relationship("XeroContact")
    allocations = relationship("XeroCreditNoteAllocation", back_populates="credit_note")
```

### Step 2: Extend XeroClient

```python
# backend/app/modules/integrations/xero/client.py

class XeroClient:
    # ... existing methods ...

    async def get_credit_notes(
        self,
        access_token: str,
        tenant_id: str,
        modified_since: datetime | None = None,
        page: int = 1,
    ) -> dict:
        """Fetch credit notes from Xero."""
        headers = self._auth_headers(access_token, tenant_id)
        if modified_since:
            headers["If-Modified-Since"] = modified_since.strftime("%Y-%m-%dT%H:%M:%S")

        params = {"page": page}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/CreditNotes",
                headers=headers,
                params=params,
            )
            response.raise_for_status()
            return response.json()

    async def get_credit_note_allocations(
        self,
        access_token: str,
        tenant_id: str,
        credit_note_id: str,
    ) -> list[dict]:
        """Fetch allocations for a credit note."""
        headers = self._auth_headers(access_token, tenant_id)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/CreditNotes/{credit_note_id}/Allocations",
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("Allocations", [])

    async def get_payments(
        self,
        access_token: str,
        tenant_id: str,
        modified_since: datetime | None = None,
        page: int = 1,
    ) -> dict:
        """Fetch payments from Xero."""
        headers = self._auth_headers(access_token, tenant_id)
        if modified_since:
            headers["If-Modified-Since"] = modified_since.strftime("%Y-%m-%dT%H:%M:%S")

        params = {"page": page}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/Payments",
                headers=headers,
                params=params,
            )
            response.raise_for_status()
            return response.json()

    async def get_journals(
        self,
        access_token: str,
        tenant_id: str,
        modified_since: datetime | None = None,
        offset: int = 0,
    ) -> dict:
        """Fetch journals from Xero."""
        headers = self._auth_headers(access_token, tenant_id)
        if modified_since:
            headers["If-Modified-Since"] = modified_since.strftime("%Y-%m-%dT%H:%M:%S")

        params = {"offset": offset}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/Journals",
                headers=headers,
                params=params,
            )
            response.raise_for_status()
            return response.json()

    async def get_manual_journals(
        self,
        access_token: str,
        tenant_id: str,
        modified_since: datetime | None = None,
        page: int = 1,
    ) -> dict:
        """Fetch manual journals from Xero."""
        headers = self._auth_headers(access_token, tenant_id)
        if modified_since:
            headers["If-Modified-Since"] = modified_since.strftime("%Y-%m-%dT%H:%M:%S")

        params = {"page": page}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/ManualJournals",
                headers=headers,
                params=params,
            )
            response.raise_for_status()
            return response.json()
```

### Step 3: Update GST Calculator

```python
# backend/app/modules/bas/calculator.py

class GSTCalculator:
    async def calculate_gst(
        self,
        client_id: UUID,
        period_start: date,
        period_end: date,
    ) -> GSTCalculation:
        """Calculate GST including credit note adjustments."""

        # Get invoices (existing)
        sales_invoices = await self.invoice_repo.get_sales_invoices(
            client_id, period_start, period_end
        )
        purchase_bills = await self.invoice_repo.get_purchase_bills(
            client_id, period_start, period_end
        )

        # Get credit notes (NEW)
        sales_credit_notes = await self.credit_note_repo.get_by_type_and_period(
            client_id, CreditNoteType.ACCRECCREDIT, period_start, period_end
        )
        purchase_credit_notes = await self.credit_note_repo.get_by_type_and_period(
            client_id, CreditNoteType.ACCPAYCREDIT, period_start, period_end
        )

        # Calculate output GST (what we owe)
        sales_invoice_gst = sum(inv.total_tax for inv in sales_invoices)
        sales_credit_note_gst = sum(cn.total_tax for cn in sales_credit_notes)
        output_gst = sales_invoice_gst - sales_credit_note_gst

        # Calculate input GST (what we can claim)
        purchase_bill_gst = sum(bill.total_tax for bill in purchase_bills)
        purchase_credit_note_gst = sum(cn.total_tax for cn in purchase_credit_notes)
        input_gst = purchase_bill_gst - purchase_credit_note_gst

        # Net GST payable
        net_gst = output_gst - input_gst

        return GSTCalculation(
            period_start=period_start,
            period_end=period_end,
            sales_invoice_gst=sales_invoice_gst,
            sales_credit_note_gst=sales_credit_note_gst,
            output_gst=output_gst,
            purchase_bill_gst=purchase_bill_gst,
            purchase_credit_note_gst=purchase_credit_note_gst,
            input_gst=input_gst,
            net_gst=net_gst,
        )
```

### Step 4: Add Sync Service Methods

```python
# backend/app/modules/integrations/xero/service.py

class XeroSyncService:
    async def sync_credit_notes(self, connection_id: UUID) -> SyncResult:
        """Sync credit notes from Xero."""
        connection = await self.connection_repo.get(connection_id)
        access_token = await self._get_valid_token(connection)

        last_sync = await self.sync_job_repo.get_last_successful(
            connection_id, "credit_notes"
        )
        modified_since = last_sync.completed_at if last_sync else None

        total_synced = 0
        page = 1

        while True:
            data = await self.client.get_credit_notes(
                access_token,
                connection.xero_tenant_id,
                modified_since,
                page,
            )

            credit_notes = data.get("CreditNotes", [])
            if not credit_notes:
                break

            for cn_data in credit_notes:
                # Fetch allocations
                allocations = await self.client.get_credit_note_allocations(
                    access_token,
                    connection.xero_tenant_id,
                    cn_data["CreditNoteID"],
                )

                # Transform and upsert
                credit_note = self._transform_credit_note(cn_data, connection_id)
                await self.credit_note_repo.upsert(credit_note)

                # Upsert allocations
                for alloc_data in allocations:
                    allocation = self._transform_allocation(alloc_data, credit_note.id)
                    await self.allocation_repo.upsert(allocation)

                total_synced += 1

            page += 1

            # Rate limiting
            await asyncio.sleep(1)

        return SyncResult(entity_type="credit_notes", count=total_synced)

    async def sync_payments(self, connection_id: UUID) -> SyncResult:
        """Sync payments from Xero."""
        # Similar pattern to sync_credit_notes
        ...

    async def sync_journals(self, connection_id: UUID) -> SyncResult:
        """Sync journals from Xero."""
        # Similar pattern, uses offset instead of page
        ...
```

---

## Test Scenarios

### Credit Note GST Calculation

```python
# tests/unit/modules/bas/test_gst_calculator.py

async def test_gst_with_credit_notes():
    """Credit notes should reduce GST liability."""
    # Setup: $10,000 GST from sales, $500 credit note GST
    calculator = GSTCalculator(...)

    result = await calculator.calculate_gst(
        client_id=client_id,
        period_start=date(2025, 10, 1),
        period_end=date(2025, 12, 31),
    )

    assert result.sales_invoice_gst == Decimal("10000.00")
    assert result.sales_credit_note_gst == Decimal("500.00")
    assert result.output_gst == Decimal("9500.00")  # Net of credit notes
```

### Credit Note Period Allocation

```python
async def test_credit_note_applies_to_issue_period():
    """Credit note GST applies to period when credit note issued."""
    # Invoice in October, Credit Note in November
    # Credit note should affect November GST, not October

    oct_result = await calculator.calculate_gst(
        client_id, date(2025, 10, 1), date(2025, 10, 31)
    )
    nov_result = await calculator.calculate_gst(
        client_id, date(2025, 11, 1), date(2025, 11, 30)
    )

    assert oct_result.sales_credit_note_gst == Decimal("0.00")
    assert nov_result.sales_credit_note_gst == Decimal("500.00")
```

### Voided Credit Note Handling

```python
async def test_voided_credit_note_excluded():
    """Voided credit notes should not affect GST calculation."""
    # Create credit note, then mark as voided
    # GST calculation should exclude it

    result = await calculator.calculate_gst(...)

    # Voided credit note's GST should not be counted
    assert result.sales_credit_note_gst == Decimal("0.00")
```

---

## API Usage Examples

### List Credit Notes

```bash
# Get credit notes for a client
curl -X GET "http://localhost:8000/api/v1/clients/{client_id}/credit-notes" \
  -H "Authorization: Bearer {token}"

# Filter by type
curl -X GET "http://localhost:8000/api/v1/clients/{client_id}/credit-notes?type=ACCRECCREDIT" \
  -H "Authorization: Bearer {token}"

# Filter by date range
curl -X GET "http://localhost:8000/api/v1/clients/{client_id}/credit-notes?from_date=2025-10-01&to_date=2025-12-31" \
  -H "Authorization: Bearer {token}"
```

### Get Credit Note with Allocations

```bash
curl -X GET "http://localhost:8000/api/v1/clients/{client_id}/credit-notes/{credit_note_id}" \
  -H "Authorization: Bearer {token}"

# Response:
{
  "id": "...",
  "credit_note_number": "CN-0001",
  "type": "ACCRECCREDIT",
  "contact_name": "Customer ABC",
  "total": 1100.00,
  "total_tax": 100.00,
  "status": "AUTHORISED",
  "allocations": [
    {
      "invoice_number": "INV-001",
      "amount": 500.00,
      "date": "2025-12-20"
    }
  ],
  "remaining_credit": 600.00
}
```

### Trigger Transactions Sync

```bash
# Sync all transaction types
curl -X POST "http://localhost:8000/api/v1/clients/{client_id}/transactions/sync" \
  -H "Authorization: Bearer {token}"

# Response:
{
  "credit_notes_job_id": "...",
  "payments_job_id": "...",
  "journals_job_id": "...",
  "status": "started"
}
```

### Check Sync Status

```bash
curl -X GET "http://localhost:8000/api/v1/clients/{client_id}/transactions/sync" \
  -H "Authorization: Bearer {token}"

# Response:
{
  "credit_notes": {
    "last_sync_at": "2025-12-31T10:00:00Z",
    "status": "synced",
    "record_count": 45
  },
  "payments": {
    "last_sync_at": "2025-12-31T10:00:00Z",
    "status": "synced",
    "record_count": 230
  },
  ...
}
```

---

## Implementation Checklist

### Backend

- [ ] Add credit note models and enums
- [ ] Add payment models (including overpayment, prepayment)
- [ ] Add journal models (system and manual)
- [ ] Create Alembic migration
- [ ] Add XeroClient methods for each endpoint
- [ ] Create repositories for each entity
- [ ] Add sync service methods
- [ ] Update GST calculator with credit note logic
- [ ] Add API endpoints
- [ ] Write unit tests
- [ ] Write integration tests

### Frontend

- [ ] Create CreditNotesList component
- [ ] Create CreditNoteDetail component
- [ ] Create PaymentsList component
- [ ] Create JournalsList component
- [ ] Add transaction pages to client view
- [ ] Update GST display to show credit note adjustments

---

## Key Implementation Notes

1. **Sync Order**: Always sync in this order:
   - Invoices (existing)
   - Credit Notes (reference invoices)
   - Payments (reference invoices/credit notes)
   - Journals (after all source transactions)

2. **Rate Limiting**: Xero allows 60 requests/minute. Use 1-second delay between paginated calls.

3. **Voided Transactions**: Use soft delete. Update status to VOIDED, don't hard delete.

4. **GST Timing**: Credit note GST applies to the period when the credit note was **issued**, not when the original invoice was created.

5. **Multi-currency**: Store both original currency amount and base currency (AUD) equivalent using Xero's currency rate.

---

*End of Quickstart Guide*
