"""System templates for document requests.

Pre-built templates for common document request scenarios.
These templates are available to all tenants and cannot be modified.

Spec: 030-client-portal-document-requests
"""

from dataclasses import dataclass
from uuid import UUID, uuid5

from app.modules.portal.enums import RequestPriority

# Namespace for generating deterministic UUIDs for system templates
SYSTEM_TEMPLATE_NAMESPACE = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


@dataclass(frozen=True)
class SystemTemplate:
    """System template definition."""

    id: UUID
    name: str
    description_template: str
    expected_document_types: list[str]
    icon: str
    default_priority: RequestPriority
    default_due_days: int

    def to_dict(self) -> dict:
        """Convert to dictionary for database seeding."""
        return {
            "id": self.id,
            "name": self.name,
            "description_template": self.description_template,
            "expected_document_types": self.expected_document_types,
            "icon": self.icon,
            "default_priority": self.default_priority.value,
            "default_due_days": self.default_due_days,
            "is_system": True,
            "is_active": True,
            "tenant_id": None,
            "created_by": None,
        }


def _make_template_id(name: str) -> UUID:
    """Generate deterministic UUID for system template."""
    return uuid5(SYSTEM_TEMPLATE_NAMESPACE, name)


# =============================================================================
# System Templates
# =============================================================================

SYSTEM_TEMPLATES: list[SystemTemplate] = [
    # Financial Documents
    SystemTemplate(
        id=_make_template_id("bank-statements"),
        name="Bank Statements",
        description_template=(
            "Please provide your bank statements for the period {period_start} to {period_end}.\n\n"
            "We need statements for all business bank accounts including:\n"
            "- Main operating account\n"
            "- Credit card statements\n"
            "- Savings/term deposit accounts\n\n"
            "PDF format is preferred."
        ),
        expected_document_types=["bank_statement", "credit_card_statement"],
        icon="building-columns",
        default_priority=RequestPriority.NORMAL,
        default_due_days=7,
    ),
    SystemTemplate(
        id=_make_template_id("invoices"),
        name="Outstanding Invoices",
        description_template=(
            "Please provide copies of all outstanding invoices as at {period_end}.\n\n"
            "This includes:\n"
            "- Sales invoices issued but not yet paid\n"
            "- Purchase invoices received but not yet paid\n\n"
            "Please ensure all invoices are clearly legible."
        ),
        expected_document_types=["sales_invoice", "purchase_invoice"],
        icon="file-invoice",
        default_priority=RequestPriority.NORMAL,
        default_due_days=7,
    ),
    SystemTemplate(
        id=_make_template_id("receipts"),
        name="Business Receipts",
        description_template=(
            "Please provide receipts for business expenses for the period "
            "{period_start} to {period_end}.\n\n"
            "This includes:\n"
            "- Travel and accommodation\n"
            "- Office supplies\n"
            "- Equipment purchases\n"
            "- Subscriptions and software\n\n"
            "Digital photos of receipts are acceptable."
        ),
        expected_document_types=["receipt", "expense"],
        icon="receipt",
        default_priority=RequestPriority.NORMAL,
        default_due_days=14,
    ),
    # Tax Documents
    SystemTemplate(
        id=_make_template_id("bas-supporting"),
        name="BAS Supporting Documents",
        description_template=(
            "To complete your BAS for {period_start} to {period_end}, "
            "we need the following:\n\n"
            "1. Bank statements for all business accounts\n"
            "2. Reconciled sales and purchases\n"
            "3. Any unusual or large transactions requiring explanation\n"
            "4. Payroll summaries (if applicable)\n\n"
            "Please upload all relevant documents."
        ),
        expected_document_types=[
            "bank_statement",
            "sales_invoice",
            "purchase_invoice",
            "payroll_summary",
        ],
        icon="file-check",
        default_priority=RequestPriority.HIGH,
        default_due_days=5,
    ),
    SystemTemplate(
        id=_make_template_id("payg-summaries"),
        name="PAYG Summaries",
        description_template=(
            "Please provide your PAYG summaries for the period ending {period_end}.\n\n"
            "We need:\n"
            "- PAYG withholding summary\n"
            "- Employee payment summaries\n"
            "- Superannuation payment records\n\n"
            "These are required for your BAS lodgement."
        ),
        expected_document_types=["payg_summary", "payment_summary", "super_statement"],
        icon="users",
        default_priority=RequestPriority.HIGH,
        default_due_days=5,
    ),
    # Payroll Documents
    SystemTemplate(
        id=_make_template_id("payroll-records"),
        name="Payroll Records",
        description_template=(
            "Please provide your payroll records for {period_start} to {period_end}.\n\n"
            "This includes:\n"
            "- Pay run summaries\n"
            "- Employee timesheets (if applicable)\n"
            "- Leave balances\n"
            "- Superannuation payment confirmations\n"
        ),
        expected_document_types=["payroll_summary", "timesheet", "super_statement"],
        icon="calendar-days",
        default_priority=RequestPriority.NORMAL,
        default_due_days=7,
    ),
    SystemTemplate(
        id=_make_template_id("employee-onboarding"),
        name="New Employee Documents",
        description_template=(
            "For your new employee, please provide:\n\n"
            "1. Completed Tax File Number Declaration\n"
            "2. Superannuation Standard Choice form\n"
            "3. Employment contract (optional)\n"
            "4. Bank account details for salary payments\n\n"
            "All forms must be signed and dated."
        ),
        expected_document_types=[
            "tfn_declaration",
            "super_choice",
            "employment_contract",
            "bank_details",
        ],
        icon="user-plus",
        default_priority=RequestPriority.HIGH,
        default_due_days=3,
    ),
    # Asset Documents
    SystemTemplate(
        id=_make_template_id("asset-purchases"),
        name="Asset Purchase Documents",
        description_template=(
            "Please provide documentation for recent asset purchases:\n\n"
            "- Purchase invoice or receipt\n"
            "- Proof of payment\n"
            "- Asset specifications (if applicable)\n"
            "- Installation/delivery confirmation\n\n"
            "This is needed for depreciation calculations and GST claims."
        ),
        expected_document_types=["purchase_invoice", "receipt", "asset_document"],
        icon="box",
        default_priority=RequestPriority.NORMAL,
        default_due_days=14,
    ),
    # Compliance Documents
    SystemTemplate(
        id=_make_template_id("ato-correspondence"),
        name="ATO Correspondence",
        description_template=(
            "Please forward any correspondence received from the ATO:\n\n"
            "- Letters or notices\n"
            "- Assessment notices\n"
            "- Penalty notices\n"
            "- Activity statement reminders\n\n"
            "Please include any documents you've already responded to."
        ),
        expected_document_types=["ato_letter", "tax_assessment", "notice"],
        icon="building-2",
        default_priority=RequestPriority.URGENT,
        default_due_days=2,
    ),
    SystemTemplate(
        id=_make_template_id("contracts"),
        name="Contracts & Agreements",
        description_template=(
            "Please provide copies of any new or updated contracts:\n\n"
            "- Customer/client contracts\n"
            "- Supplier agreements\n"
            "- Lease agreements\n"
            "- Service agreements\n\n"
            "These help us understand your business arrangements for tax purposes."
        ),
        expected_document_types=["contract", "agreement", "lease"],
        icon="file-signature",
        default_priority=RequestPriority.LOW,
        default_due_days=14,
    ),
    # General
    SystemTemplate(
        id=_make_template_id("general-documents"),
        name="General Documents",
        description_template=(
            "Please provide the following documents:\n\n"
            "{custom_description}\n\n"
            "If you have any questions, please don't hesitate to reach out."
        ),
        expected_document_types=["document"],
        icon="file",
        default_priority=RequestPriority.NORMAL,
        default_due_days=7,
    ),
]


def get_system_templates() -> list[SystemTemplate]:
    """Get all system templates.

    Returns:
        List of all system template definitions.
    """
    return SYSTEM_TEMPLATES


def get_system_template_by_id(template_id: UUID) -> SystemTemplate | None:
    """Get a system template by ID.

    Args:
        template_id: The template UUID.

    Returns:
        The template if found, None otherwise.
    """
    for template in SYSTEM_TEMPLATES:
        if template.id == template_id:
            return template
    return None


def get_system_template_by_name(name: str) -> SystemTemplate | None:
    """Get a system template by name.

    Args:
        name: The template name (case-insensitive).

    Returns:
        The template if found, None otherwise.
    """
    name_lower = name.lower()
    for template in SYSTEM_TEMPLATES:
        if template.name.lower() == name_lower:
            return template
    return None
