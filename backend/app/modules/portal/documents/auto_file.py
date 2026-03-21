"""Auto-filing service for portal documents.

Automatically categorizes and files uploaded documents based on:
- Document type detection (bank statements, invoices, receipts, etc.)
- Request template context (BAS, payroll, annual return)
- Client folder organization

Spec: 030-client-portal-document-requests
"""

import re
from datetime import date
from typing import Any
from uuid import UUID

from app.core.logging import get_logger
from app.modules.portal.models import PortalDocument

logger = get_logger(__name__)


# Document type patterns for classification
DOCUMENT_PATTERNS: dict[str, list[str]] = {
    "bank_statement": [
        r"bank.?statement",
        r"account.?statement",
        r"transaction.?history",
        r"statement\s+of\s+account",
    ],
    "invoice": [
        r"\binvoice\b",
        r"tax\s+invoice",
        r"proforma",
        r"inv[-_\s]?\d+",
    ],
    "receipt": [
        r"\breceipt\b",
        r"purchase.?confirmation",
        r"payment.?receipt",
    ],
    "payslip": [
        r"pay\s*slip",
        r"payroll\s+advice",
        r"salary\s+statement",
        r"wages\s+summary",
    ],
    "bas_statement": [
        r"\bbas\b",
        r"activity\s+statement",
        r"gst\s+return",
        r"business\s+activity",
    ],
    "superannuation": [
        r"\bsuper\b",
        r"superannuation",
        r"contribution\s+statement",
        r"member\s+statement",
    ],
    "tax_return": [
        r"tax\s+return",
        r"income\s+tax",
        r"ato\s+notice",
        r"assessment\s+notice",
    ],
    "contract": [
        r"\bcontract\b",
        r"\bagreement\b",
        r"terms\s+and\s+conditions",
        r"service\s+agreement",
    ],
    "insurance": [
        r"\binsurance\b",
        r"policy\s+document",
        r"certificate\s+of\s+currency",
        r"coc\b",
    ],
    "financial_report": [
        r"profit\s+and\s+loss",
        r"balance\s+sheet",
        r"p&l",
        r"financial\s+statement",
        r"trial\s+balance",
    ],
}

# Period patterns for date extraction
PERIOD_PATTERNS: list[tuple[str, str]] = [
    # FY format: FY23, FY2023, FY 23, FY 2023
    (r"fy\s*(\d{2,4})", "financial_year"),
    # Quarter format: Q1 2023, Q2 FY23, Q3-2023
    (r"q([1-4])\s*[-/]?\s*(?:fy\s*)?(\d{2,4})", "quarter"),
    # Month-Year format: Jan 2023, January 2023, 01/2023
    (
        r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|"
        r"dec(?:ember)?)\s*[-/]?\s*(\d{2,4})",
        "month_year",
    ),
    # Date range: 01/07/2023 - 30/09/2023
    (
        r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})\s*[-–to]+\s*"
        r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})",
        "date_range",
    ),
    # Year only: 2023, 2024
    (r"\b(20\d{2})\b", "year"),
]


class AutoFileService:
    """Service for automatically categorizing and filing documents."""

    def __init__(self):
        """Initialize the auto-filing service."""
        self._compiled_patterns: dict[str, list[re.Pattern]] = {}
        self._compiled_period_patterns: list[tuple[re.Pattern, str]] = []
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for performance."""
        for doc_type, patterns in DOCUMENT_PATTERNS.items():
            self._compiled_patterns[doc_type] = [re.compile(p, re.IGNORECASE) for p in patterns]

        self._compiled_period_patterns = [
            (re.compile(p, re.IGNORECASE), period_type) for p, period_type in PERIOD_PATTERNS
        ]

    def classify_document(
        self,
        filename: str,
        content_type: str | None = None,
        file_content: bytes | None = None,
    ) -> dict[str, Any]:
        """Classify a document based on filename and optionally content.

        Args:
            filename: The document filename.
            content_type: MIME type of the document.
            file_content: Raw file content for deeper analysis (future).

        Returns:
            Classification result with:
            - document_type: Detected type or "other"
            - confidence: Confidence score (0.0-1.0)
            - period: Detected period if any
            - suggested_folder: Suggested folder path
        """
        # Normalize filename for matching
        normalized = filename.lower().replace("_", " ").replace("-", " ")

        # Detect document type
        doc_type = "other"
        confidence = 0.0
        matches = []

        for dtype, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(normalized):
                    matches.append(dtype)
                    break

        if matches:
            # Use the most specific match (longest type name)
            doc_type = max(matches, key=len)
            confidence = 0.8 if len(matches) == 1 else 0.6

        # Detect period
        period = self._detect_period(filename)

        # Suggest folder based on type and period
        suggested_folder = self._suggest_folder(doc_type, period)

        logger.debug(
            "Classified document",
            filename=filename,
            document_type=doc_type,
            confidence=confidence,
            period=period,
        )

        return {
            "document_type": doc_type,
            "confidence": confidence,
            "period": period,
            "suggested_folder": suggested_folder,
            "matches": matches,
        }

    def _detect_period(self, filename: str) -> dict[str, Any] | None:
        """Detect financial period from filename."""
        for pattern, period_type in self._compiled_period_patterns:
            match = pattern.search(filename)
            if match:
                return self._parse_period_match(match, period_type)
        return None

    def _parse_period_match(
        self,
        match: re.Match,
        period_type: str,
    ) -> dict[str, Any]:
        """Parse a period regex match into structured data."""
        groups = match.groups()

        if period_type == "financial_year":
            year = int(groups[0])
            if year < 100:
                year += 2000
            return {
                "type": "financial_year",
                "year": year,
                "display": f"FY{year}",
            }

        elif period_type == "quarter":
            quarter = int(groups[0])
            year = int(groups[1])
            if year < 100:
                year += 2000
            return {
                "type": "quarter",
                "quarter": quarter,
                "year": year,
                "display": f"Q{quarter} FY{year}",
            }

        elif period_type == "month_year":
            month_str = groups[0][:3].lower()
            year = int(groups[1])
            if year < 100:
                year += 2000
            month_map = {
                "jan": 1,
                "feb": 2,
                "mar": 3,
                "apr": 4,
                "may": 5,
                "jun": 6,
                "jul": 7,
                "aug": 8,
                "sep": 9,
                "oct": 10,
                "nov": 11,
                "dec": 12,
            }
            month = month_map.get(month_str, 1)
            return {
                "type": "month",
                "month": month,
                "year": year,
                "display": f"{month_str.title()} {year}",
            }

        elif period_type == "year":
            year = int(groups[0])
            return {
                "type": "year",
                "year": year,
                "display": str(year),
            }

        return {"type": period_type, "raw": match.group(0)}

    def _suggest_folder(
        self,
        doc_type: str,
        period: dict[str, Any] | None,
    ) -> str:
        """Suggest a folder path based on document type and period."""
        # Base folder mapping
        folder_map = {
            "bank_statement": "Bank Statements",
            "invoice": "Invoices",
            "receipt": "Receipts",
            "payslip": "Payroll/Payslips",
            "bas_statement": "BAS",
            "superannuation": "Superannuation",
            "tax_return": "Tax Returns",
            "contract": "Contracts",
            "insurance": "Insurance",
            "financial_report": "Financial Reports",
            "other": "Documents",
        }

        base_folder = folder_map.get(doc_type, "Documents")

        if period:
            if period["type"] == "financial_year":
                return f"{base_folder}/FY{period['year']}"
            elif period["type"] == "quarter":
                return f"{base_folder}/FY{period['year']}/Q{period['quarter']}"
            elif period["type"] == "year":
                return f"{base_folder}/{period['year']}"

        # Default to current financial year
        today = date.today()
        fy = today.year if today.month >= 7 else today.year - 1
        return f"{base_folder}/FY{fy}"

    def auto_file_document(
        self,
        document: PortalDocument,
        tenant_id: UUID,
        connection_id: UUID,
    ) -> dict[str, Any]:
        """Automatically file a document.

        Args:
            document: The document to file.
            tenant_id: The tenant ID.
            connection_id: The client connection ID.

        Returns:
            Filing result with folder path and metadata.
        """
        classification = self.classify_document(
            filename=document.original_filename,
            content_type=document.content_type,
        )

        # Build full folder path with client context
        folder_path = f"clients/{connection_id}/{classification['suggested_folder']}"

        # Update document metadata
        metadata = {
            "auto_filed": True,
            "document_type": classification["document_type"],
            "confidence": classification["confidence"],
            "folder_path": folder_path,
        }

        if classification["period"]:
            metadata["period"] = classification["period"]

        logger.info(
            "Auto-filed document",
            document_id=str(document.id),
            folder_path=folder_path,
            document_type=classification["document_type"],
        )

        return {
            "folder_path": folder_path,
            "classification": classification,
            "metadata": metadata,
        }


# Singleton instance
_auto_file_service: AutoFileService | None = None


def get_auto_file_service() -> AutoFileService:
    """Get the auto-file service singleton."""
    global _auto_file_service
    if _auto_file_service is None:
        _auto_file_service = AutoFileService()
    return _auto_file_service
