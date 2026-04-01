"""Pydantic request/response schemas for the Tax Planning module."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.tax_planning.models import (
    DataSource,
    EntityType,
    RiskRating,
    TaxPlanStatus,
)

# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class TaxPlanCreate(BaseModel):
    xero_connection_id: uuid.UUID
    financial_year: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    entity_type: EntityType
    data_source: DataSource
    replace_existing: bool = False


class TaxPlanUpdate(BaseModel):
    status: TaxPlanStatus | None = None
    notes: str | None = None
    entity_type: EntityType | None = None


class IncomeBreakdownItem(BaseModel):
    category: str
    amount: Decimal


class ExpenseBreakdownItem(BaseModel):
    category: str
    amount: Decimal


class AdjustmentItem(BaseModel):
    description: str
    amount: Decimal
    type: str = Field(default="add_back", pattern=r"^(add_back|deduction)$")


class FinancialsInput(BaseModel):
    income: dict = Field(
        ...,
        description="Income data: revenue, other_income, optional breakdown",
    )
    expenses: dict = Field(
        ...,
        description="Expenses: cost_of_sales, operating_expenses, optional breakdown",
    )
    credits: dict = Field(
        default_factory=lambda: {
            "payg_instalments": 0,
            "payg_withholding": 0,
            "franking_credits": 0,
        },
    )
    adjustments: list[AdjustmentItem] = Field(default_factory=list)
    turnover: Decimal = Decimal("0")
    has_help_debt: bool = False


class XeroPullRequest(BaseModel):
    force_refresh: bool = False


class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class TaxScenarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tax_plan_id: uuid.UUID
    title: str
    description: str
    assumptions: dict
    impact_data: dict
    risk_rating: RiskRating
    compliance_notes: str | None
    cash_flow_impact: Decimal | None
    sort_order: int
    created_at: datetime


class TaxScenarioListResponse(BaseModel):
    items: list[TaxScenarioResponse]
    total: int


VerificationStatus = Literal["verified", "partially_verified", "unverified", "no_citations"]


class SourceChunkRef(BaseModel):
    """Reference to a knowledge base chunk used in RAG retrieval."""

    chunk_id: str
    source_type: str
    title: str
    ruling_number: str | None = None
    section_ref: str | None = None
    relevance_score: float


class CitationVerificationResult(BaseModel):
    """Result of verifying citations in an AI response."""

    total_citations: int
    verified_count: int
    unverified_count: int
    verification_rate: float
    status: VerificationStatus


class ChatAttachmentInfo(BaseModel):
    """Attachment metadata returned in chat message responses."""

    filename: str
    media_type: str
    category: str
    size_bytes: int


class TaxPlanMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    scenario_ids: list[uuid.UUID]
    created_at: datetime
    source_chunks_used: list[SourceChunkRef] | None = None
    citation_verification: CitationVerificationResult | None = None
    attachment: ChatAttachmentInfo | None = None

    @model_validator(mode="before")
    @classmethod
    def extract_attachment(cls, data: Any) -> Any:
        """Extract attachment info from metadata_ JSONB."""
        if hasattr(data, "metadata_"):
            metadata = data.metadata_ or {}
            att = metadata.get("attachment")
            if att and not getattr(data, "attachment", None):
                # Set as a dict so Pydantic can parse it
                if hasattr(data, "__dict__"):
                    data.__dict__["attachment"] = att
        return data


class MessageListResponse(BaseModel):
    items: list[TaxPlanMessageResponse]
    total: int
    page: int
    page_size: int


class TaxPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    xero_connection_id: uuid.UUID
    client_name: str = ""
    financial_year: str
    entity_type: EntityType
    status: TaxPlanStatus
    data_source: DataSource
    financials_data: dict | None
    tax_position: dict | None
    notes: str | None
    xero_report_fetched_at: datetime | None
    created_at: datetime
    updated_at: datetime
    scenarios: list[TaxScenarioResponse] = Field(default_factory=list)
    scenario_count: int = 0
    message_count: int = 0


class TaxPlanListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    xero_connection_id: uuid.UUID
    client_name: str = ""
    financial_year: str
    entity_type: EntityType
    status: TaxPlanStatus
    data_source: DataSource
    scenario_count: int = 0
    net_position: Decimal | None = None
    updated_at: datetime


class TaxPlanListResponse(BaseModel):
    items: list[TaxPlanListItem]
    total: int
    page: int
    page_size: int


class FinancialsPullResponse(BaseModel):
    financials_data: dict
    tax_position: dict
    data_freshness: dict | None = None


class ChatResponse(BaseModel):
    message: TaxPlanMessageResponse
    scenarios_created: list[TaxScenarioResponse] = Field(default_factory=list)
    updated_tax_position: dict | None = None


class TaxRateConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rate_type: str
    rates_data: dict
    effective_from: datetime


class TaxRatesResponse(BaseModel):
    financial_year: str
    rates: list[TaxRateConfigResponse]
