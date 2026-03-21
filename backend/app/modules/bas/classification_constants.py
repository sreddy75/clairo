"""
Category taxonomy and receipt flag rules for client transaction classification.

Clients classify transactions using plain-English categories. The AI then maps
these to BAS tax codes. Clients never see tax codes directly.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

# ---------------------------------------------------------------------------
# Category Taxonomy
# ---------------------------------------------------------------------------
# Each category has:
#   id: stable identifier (used in DB, API, and frontend)
#   label: what the client sees
#   group: "expense" | "income" | "special"
#   typical_tax_type: most common BAS tax type (guidance for AI, not deterministic)
#   receipt_always: whether this category ALWAYS requires a receipt

EXPENSE_CATEGORIES: list[dict[str, Any]] = [
    {
        "id": "office_supplies",
        "label": "Office supplies & stationery",
        "group": "expense",
        "typical_tax_type": "GST on Expenses",
        "receipt_always": False,
    },
    {
        "id": "computer_it",
        "label": "Computer & IT equipment",
        "group": "expense",
        "typical_tax_type": "GST on Expenses",
        "receipt_always": True,
    },
    {
        "id": "tools_equipment",
        "label": "Tools & equipment",
        "group": "expense",
        "typical_tax_type": "GST on Expenses",
        "receipt_always": True,
    },
    {
        "id": "travel_transport",
        "label": "Travel & transport",
        "group": "expense",
        "typical_tax_type": "GST on Expenses",
        "receipt_always": False,
    },
    {
        "id": "fuel_vehicle",
        "label": "Fuel & vehicle expenses",
        "group": "expense",
        "typical_tax_type": "GST on Expenses",
        "receipt_always": False,
    },
    {
        "id": "meals_entertainment",
        "label": "Meals & entertainment",
        "group": "expense",
        "typical_tax_type": "GST on Expenses",
        "receipt_always": True,
    },
    {
        "id": "advertising_marketing",
        "label": "Advertising & marketing",
        "group": "expense",
        "typical_tax_type": "GST on Expenses",
        "receipt_always": False,
    },
    {
        "id": "professional_services",
        "label": "Professional services (legal, accounting)",
        "group": "expense",
        "typical_tax_type": "GST on Expenses",
        "receipt_always": False,
    },
    {
        "id": "insurance",
        "label": "Insurance",
        "group": "expense",
        "typical_tax_type": "GST Free Expenses",
        "receipt_always": False,
    },
    {
        "id": "rent_property",
        "label": "Rent & property",
        "group": "expense",
        "typical_tax_type": "GST on Expenses",
        "receipt_always": False,
    },
    {
        "id": "phone_internet",
        "label": "Phone & internet",
        "group": "expense",
        "typical_tax_type": "GST on Expenses",
        "receipt_always": False,
    },
    {
        "id": "subscriptions_software",
        "label": "Subscriptions & software",
        "group": "expense",
        "typical_tax_type": "GST on Expenses",
        "receipt_always": False,
    },
    {
        "id": "stock_inventory",
        "label": "Stock & inventory",
        "group": "expense",
        "typical_tax_type": "GST on Expenses",
        "receipt_always": False,
    },
    {
        "id": "subcontractor",
        "label": "Subcontractor payment",
        "group": "expense",
        "typical_tax_type": "GST on Expenses",
        "receipt_always": True,
    },
    {
        "id": "bank_fees",
        "label": "Bank fees & charges",
        "group": "expense",
        "typical_tax_type": "GST Free Expenses",
        "receipt_always": False,
    },
    {
        "id": "government_fees",
        "label": "Government fees & charges",
        "group": "expense",
        "typical_tax_type": "GST Free Expenses",
        "receipt_always": False,
    },
    {
        "id": "training_education",
        "label": "Training & education",
        "group": "expense",
        "typical_tax_type": "GST on Expenses",
        "receipt_always": False,
    },
    {
        "id": "donations_gifts",
        "label": "Donations & gifts",
        "group": "expense",
        "typical_tax_type": "GST Free Expenses",
        "receipt_always": False,
    },
]

INCOME_CATEGORIES: list[dict[str, Any]] = [
    {
        "id": "sale_of_goods",
        "label": "Sale of goods",
        "group": "income",
        "typical_tax_type": "GST on Income",
        "receipt_always": False,
    },
    {
        "id": "service_income",
        "label": "Service income",
        "group": "income",
        "typical_tax_type": "GST on Income",
        "receipt_always": False,
    },
    {
        "id": "rental_income",
        "label": "Rental income",
        "group": "income",
        "typical_tax_type": "GST on Income",
        "receipt_always": False,
    },
    {
        "id": "interest_received",
        "label": "Interest received",
        "group": "income",
        "typical_tax_type": "GST Free Income",
        "receipt_always": False,
    },
    {
        "id": "government_grant",
        "label": "Government grant",
        "group": "income",
        "typical_tax_type": "GST Free Income",
        "receipt_always": False,
    },
]

SPECIAL_CATEGORIES: list[dict[str, Any]] = [
    {
        "id": "personal",
        "label": "Personal expense — not business",
        "group": "special",
        "typical_tax_type": "BASEXCLUDED",
        "receipt_always": False,
    },
    {
        "id": "dont_know",
        "label": "I don't know — my accountant can decide",
        "group": "special",
        "typical_tax_type": None,
        "receipt_always": False,
    },
    {
        "id": "other",
        "label": "Other (please describe)",
        "group": "special",
        "typical_tax_type": None,
        "receipt_always": False,
    },
]

CLASSIFICATION_CATEGORIES: list[dict[str, Any]] = (
    EXPENSE_CATEGORIES + INCOME_CATEGORIES + SPECIAL_CATEGORIES
)

CATEGORY_BY_ID: dict[str, dict[str, Any]] = {cat["id"]: cat for cat in CLASSIFICATION_CATEGORIES}

VALID_CATEGORY_IDS: set[str] = {cat["id"] for cat in CLASSIFICATION_CATEGORIES}


# ---------------------------------------------------------------------------
# Receipt Flag Rules
# ---------------------------------------------------------------------------

# ATO requires a valid tax invoice for GST credit claims > $82.50
GST_CREDIT_RECEIPT_THRESHOLD = Decimal("82.50")

# Categories that ALWAYS require a receipt regardless of amount
RECEIPT_ALWAYS_CATEGORY_IDS: set[str] = {
    cat["id"] for cat in CLASSIFICATION_CATEGORIES if cat["receipt_always"]
}

# Receipt reasons by rule
RECEIPT_REASON_GST_THRESHOLD = "GST credit claim over $82.50 — tax invoice required"
RECEIPT_REASON_CAPITAL = "Capital purchase — evidence required for asset write-off"
RECEIPT_REASON_ENTERTAINMENT = "Entertainment expense — documentation required for FBT"
RECEIPT_REASON_SUBCONTRACTOR = "Subcontractor payment — invoice and ABN required for TPAR"
RECEIPT_REASON_VAGUE = "Unclear bank description — receipt needed to verify transaction"

# Category-specific receipt reasons (override the generic "always" reason)
RECEIPT_REASON_BY_CATEGORY: dict[str, str] = {
    "computer_it": RECEIPT_REASON_CAPITAL,
    "tools_equipment": RECEIPT_REASON_CAPITAL,
    "meals_entertainment": RECEIPT_REASON_ENTERTAINMENT,
    "subcontractor": RECEIPT_REASON_SUBCONTRACTOR,
}

# ---------------------------------------------------------------------------
# Vague Description Patterns
# ---------------------------------------------------------------------------
# Bank descriptions matching these patterns provide insufficient audit trail
# and should be flagged for receipt upload.

VAGUE_DESCRIPTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^TRANSFER\b", re.IGNORECASE),
    re.compile(r"^PAYMENT\b", re.IGNORECASE),
    re.compile(r"^DIRECT DEBIT\b", re.IGNORECASE),
    re.compile(r"^ATM\b", re.IGNORECASE),
    re.compile(r"^EFT\b", re.IGNORECASE),
    re.compile(r"^EFTPOS\b", re.IGNORECASE),
    re.compile(r"^DD\b", re.IGNORECASE),
    re.compile(r"^TFR\b", re.IGNORECASE),
    re.compile(r"^BPAY\b", re.IGNORECASE),
    re.compile(r"^PAY\b", re.IGNORECASE),
]

# Descriptions shorter than this are considered vague
VAGUE_DESCRIPTION_MIN_LENGTH = 5
