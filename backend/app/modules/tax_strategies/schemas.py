"""Pydantic schemas for the tax_strategies module (Spec 060).

Mirrors specs/060-tax-strategies-kb/contracts/*.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Fixed taxonomy per FR-003 / spec clarification
ALLOWED_CATEGORIES: frozenset[str] = frozenset(
    {
        "Business",
        "Recommendations",
        "Employees",
        "ATO_obligations",
        "Rental_properties",
        "Investors_retirees",
        "Business_structures",
        "SMSF",
    }
)

Status = Literal[
    "stub",
    "researching",
    "drafted",
    "enriched",
    "in_review",
    "approved",
    "published",
    "superseded",
    "archived",
]

Stage = Literal["research", "draft", "enrich", "publish"]

JobStatus = Literal["pending", "running", "succeeded", "failed"]


# ----------------------------------------------------------------------
# List
# ----------------------------------------------------------------------


class TaxStrategyListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    strategy_id: str
    name: str
    categories: list[str]
    status: Status
    tenant_id: str
    version: int
    last_reviewed_at: datetime | None = None
    reviewer_display_name: str | None = None
    updated_at: datetime


class TaxStrategyListResponseMeta(BaseModel):
    page: int
    page_size: int
    total: int


class TaxStrategyListResponse(BaseModel):
    data: list[TaxStrategyListItem]
    meta: TaxStrategyListResponseMeta


# ----------------------------------------------------------------------
# Detail (admin)
# ----------------------------------------------------------------------


class AuthoringJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    strategy_id: str
    stage: Stage
    status: JobStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    input_payload: dict = Field(default_factory=dict)
    output_payload: dict | None = None
    error: str | None = None
    triggered_by: str
    created_at: datetime


class TaxStrategyDetail(TaxStrategyListItem):
    model_config = ConfigDict(from_attributes=True)

    implementation_text: str
    explanation_text: str
    entity_types: list[str]
    income_band_min: int | None = None
    income_band_max: int | None = None
    turnover_band_min: int | None = None
    turnover_band_max: int | None = None
    age_min: int | None = None
    age_max: int | None = None
    industry_triggers: list[str]
    financial_impact_type: list[str]
    keywords: list[str]
    ato_sources: list[str]
    case_refs: list[str]
    fy_applicable_from: date | None = None
    fy_applicable_to: date | None = None
    superseded_by_strategy_id: str | None = None
    source_ref: str | None = Field(
        default=None,
        description=("Admin-only; never included in public hydration responses (FR-008)."),
    )
    authoring_jobs: list[AuthoringJobResponse] = Field(default_factory=list)
    version_history: list[TaxStrategyListItem] = Field(default_factory=list)


# ----------------------------------------------------------------------
# Public hydration (FR-008: strips source_ref)
# ----------------------------------------------------------------------


class PublicTaxStrategy(BaseModel):
    """Hydrated strategy served to tax planning chat UI chip panels.

    MUST NOT include source_ref per FR-008.
    """

    model_config = ConfigDict(from_attributes=True)

    strategy_id: str
    name: str
    categories: list[str]
    implementation_text: str
    explanation_text: str
    ato_sources: list[str]
    case_refs: list[str]
    fy_applicable_from: date | None = None
    fy_applicable_to: date | None = None
    version: int
    is_platform: bool


class PublicHydrationBatchResponse(BaseModel):
    data: list[PublicTaxStrategy]


# ----------------------------------------------------------------------
# Action requests
# ----------------------------------------------------------------------


class RejectPayload(BaseModel):
    reviewer_notes: str = Field(min_length=1, max_length=2000)


class SeedSummaryResponse(BaseModel):
    created: int
    skipped: int
    errors: list[str] = Field(default_factory=list)


class PipelineStatsResponse(BaseModel):
    counts: dict[str, int]
