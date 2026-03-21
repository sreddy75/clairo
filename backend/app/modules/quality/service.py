"""Service for quality scoring operations."""

import logging
import time
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.integrations.xero.repository import XeroConnectionRepository
from app.modules.quality.calculator import (
    DIMENSION_WEIGHTS,
    CategorizationCalculator,
    CompletenessCalculator,
    FreshnessCalculator,
    PaygReadinessCalculator,
    QualityScoreAggregator,
    ReconciliationCalculator,
)
from app.modules.quality.issue_detector import IssueDetector
from app.modules.quality.models import IssueCode, IssueSeverity, QualityScore
from app.modules.quality.repository import QualityRepository
from app.modules.quality.schemas import (
    DashboardQualitySummary,
    DismissIssueResponse,
    IssueCounts,
    QualityDimensionResponse,
    QualityDimensionsResponse,
    QualityIssueResponse,
    QualityIssuesListResponse,
    QualityRecalculateResponse,
    QualityScoreResponse,
)

logger = logging.getLogger(__name__)


def get_quarter_dates(quarter: int, fy_year: int) -> tuple[datetime, datetime]:
    """Get start and end dates for an Australian financial year quarter.

    Australian FY runs July 1 to June 30.
    - Q1: July 1 - September 30
    - Q2: October 1 - December 31
    - Q3: January 1 - March 31
    - Q4: April 1 - June 30
    """
    if quarter == 1:
        # July 1 - September 30
        start = datetime(fy_year - 1, 7, 1, tzinfo=UTC)
        end = datetime(fy_year - 1, 9, 30, 23, 59, 59, tzinfo=UTC)
    elif quarter == 2:
        # October 1 - December 31
        start = datetime(fy_year - 1, 10, 1, tzinfo=UTC)
        end = datetime(fy_year - 1, 12, 31, 23, 59, 59, tzinfo=UTC)
    elif quarter == 3:
        # January 1 - March 31
        start = datetime(fy_year, 1, 1, tzinfo=UTC)
        end = datetime(fy_year, 3, 31, 23, 59, 59, tzinfo=UTC)
    else:  # Q4
        # April 1 - June 30
        start = datetime(fy_year, 4, 1, tzinfo=UTC)
        end = datetime(fy_year, 6, 30, 23, 59, 59, tzinfo=UTC)

    return start, end


def get_current_quarter() -> tuple[int, int]:
    """Get current Australian financial year quarter and year."""
    now = datetime.now(UTC)
    month = now.month

    # Determine FY year (FY starts July 1)
    fy_year = now.year + 1 if month >= 7 else now.year

    # Determine quarter
    if month in (7, 8, 9):
        quarter = 1
    elif month in (10, 11, 12):
        quarter = 2
    elif month in (1, 2, 3):
        quarter = 3
    else:
        quarter = 4

    return quarter, fy_year


class QualityService:
    """Service for quality scoring and issue management."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = QualityRepository(session)
        self.connection_repo = XeroConnectionRepository(session)

    # =========================================================================
    # Quality Calculation
    # =========================================================================

    async def calculate_quality(
        self,
        connection_id: UUID,
        quarter: int | None = None,
        fy_year: int | None = None,
        trigger_reason: str = "manual",
    ) -> QualityRecalculateResponse:
        """Calculate quality score for a connection.

        Args:
            connection_id: The connection to calculate quality for.
            quarter: Quarter number (1-4). Defaults to current quarter.
            fy_year: Financial year (e.g., 2025). Defaults to current FY.
            trigger_reason: Why the calculation was triggered.

        Returns:
            QualityRecalculateResponse with the new score and issues.
        """
        start_time = time.time()

        # Get connection
        connection = await self.connection_repo.get_by_id(connection_id)
        if not connection:
            raise ValueError(f"Connection {connection_id} not found")

        # Default to current quarter
        if quarter is None or fy_year is None:
            curr_quarter, curr_fy_year = get_current_quarter()
            quarter = quarter or curr_quarter
            fy_year = fy_year or curr_fy_year

        # Get quarter date range
        quarter_start, quarter_end = get_quarter_dates(quarter, fy_year)

        # Initialize calculators
        aggregator = QualityScoreAggregator()

        # Calculate each dimension
        calculators = [
            FreshnessCalculator(self.session),
            ReconciliationCalculator(self.session),
            CategorizationCalculator(self.session),
            CompletenessCalculator(self.session),
            PaygReadinessCalculator(self.session),
        ]

        for calc in calculators:
            result = await calc.calculate(connection, quarter_start, quarter_end)
            aggregator.add_result(calc.name, result)

        # Calculate overall score
        overall_score = aggregator.calculate_overall_score()

        # Detect issues
        detector = IssueDetector(self.session)
        detected_issues = await detector.detect_all(connection, quarter_start, quarter_end)

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Get dimension results for storage
        dimension_results = aggregator.dimension_results

        # Save score
        await self.repo.upsert_score(
            tenant_id=connection.tenant_id,
            connection_id=connection_id,
            quarter=quarter,
            fy_year=fy_year,
            overall_score=overall_score,
            freshness_score=dimension_results["freshness"].score,
            reconciliation_score=dimension_results["reconciliation"].score,
            categorization_score=dimension_results["categorization"].score,
            completeness_score=dimension_results["completeness"].score,
            payg_score=dimension_results["payg_readiness"].score
            if dimension_results["payg_readiness"].is_applicable
            else None,
            calculation_duration_ms=duration_ms,
            trigger_reason=trigger_reason,
        )

        # Save issues
        await self.repo.upsert_issues(
            tenant_id=connection.tenant_id,
            connection_id=connection_id,
            quarter=quarter,
            fy_year=fy_year,
            detected_issues=detected_issues,
        )

        await self.session.commit()

        logger.info(
            f"Quality calculated for connection {connection_id}: "
            f"score={overall_score}%, issues={len(detected_issues)}, "
            f"duration={duration_ms}ms"
        )

        return QualityRecalculateResponse(
            overall_score=overall_score,
            issues_found=len(detected_issues),
            calculated_at=datetime.now(UTC),
        )

    # =========================================================================
    # Quality Retrieval
    # =========================================================================

    async def get_quality_summary(
        self,
        connection_id: UUID,
        quarter: int | None = None,
        fy_year: int | None = None,
    ) -> QualityScoreResponse:
        """Get quality score summary for a connection."""
        # Default to current quarter
        if quarter is None or fy_year is None:
            curr_quarter, curr_fy_year = get_current_quarter()
            quarter = quarter or curr_quarter
            fy_year = fy_year or curr_fy_year

        # Get score
        score = await self.repo.get_score(connection_id, quarter, fy_year)

        if not score:
            # No score calculated yet - return zeros
            return self._empty_quality_response()

        # Get issue counts
        issue_counts = await self.repo.get_issue_counts(connection_id, quarter, fy_year)

        # Build response
        return QualityScoreResponse(
            overall_score=score.overall_score,
            dimensions=self._build_dimensions_response(score),
            issue_counts=IssueCounts(**issue_counts),
            last_checked_at=score.calculated_at,
            trend=None,  # TODO: Calculate trend from history
            has_score=True,
        )

    async def get_issues(
        self,
        connection_id: UUID,
        quarter: int | None = None,
        fy_year: int | None = None,
        severity: str | None = None,
        issue_type: str | None = None,
        include_dismissed: bool = False,
    ) -> QualityIssuesListResponse:
        """Get quality issues for a connection."""
        # Default to current quarter
        if quarter is None or fy_year is None:
            curr_quarter, curr_fy_year = get_current_quarter()
            quarter = quarter or curr_quarter
            fy_year = fy_year or curr_fy_year

        # Parse filters
        severity_enum = IssueSeverity(severity) if severity else None
        issue_code = IssueCode(issue_type) if issue_type else None

        # Get issues
        issues = await self.repo.get_issues(
            connection_id=connection_id,
            quarter=quarter,
            fy_year=fy_year,
            severity=severity_enum,
            issue_code=issue_code,
            include_dismissed=include_dismissed,
        )

        # Build response
        issue_responses = [
            QualityIssueResponse(
                id=issue.id,
                code=issue.code,
                severity=issue.severity,
                title=issue.title,
                description=issue.description,
                affected_entity_type=issue.affected_entity_type,
                affected_count=issue.affected_count,
                affected_ids=[str(id) for id in (issue.affected_ids or [])],
                suggested_action=issue.suggested_action,
                first_detected_at=issue.first_detected_at,
                dismissed=issue.dismissed,
                dismissed_by=issue.dismissed_by,
                dismissed_at=issue.dismissed_at,
                dismissed_reason=issue.dismissed_reason,
            )
            for issue in issues
        ]

        return QualityIssuesListResponse(
            issues=issue_responses,
            total=len(issue_responses),
        )

    async def dismiss_issue(
        self,
        issue_id: UUID,
        user_id: UUID,
        reason: str,
    ) -> DismissIssueResponse:
        """Dismiss a quality issue."""
        issue = await self.repo.dismiss_issue(issue_id, user_id, reason)

        if not issue:
            raise ValueError(f"Issue {issue_id} not found")

        await self.session.commit()

        return DismissIssueResponse(
            success=True,
            issue_id=issue_id,
            dismissed_at=issue.dismissed_at,
        )

    # =========================================================================
    # Dashboard Integration
    # =========================================================================

    async def get_portfolio_quality_summary(
        self,
        tenant_id: UUID,
        quarter: int | None = None,
        fy_year: int | None = None,
    ) -> DashboardQualitySummary:
        """Get quality summary across all connections for dashboard."""
        # Default to current quarter
        if quarter is None or fy_year is None:
            curr_quarter, curr_fy_year = get_current_quarter()
            quarter = quarter or curr_quarter
            fy_year = fy_year or curr_fy_year

        # Get portfolio summary
        summary = await self.repo.get_portfolio_summary(tenant_id, quarter, fy_year)

        # Get total critical issues
        total_critical = await self.repo.get_total_critical_issues(tenant_id, quarter, fy_year)

        return DashboardQualitySummary(
            avg_score=summary["avg_score"],
            good_count=summary["good_count"],
            fair_count=summary["fair_count"],
            poor_count=summary["poor_count"],
            total_critical_issues=total_critical,
        )

    async def get_quality_for_connections(
        self,
        connection_ids: list[UUID],
        quarter: int | None = None,
        fy_year: int | None = None,
    ) -> dict[UUID, dict[str, Any]]:
        """Get quality scores for multiple connections (for dashboard table)."""
        if not connection_ids:
            return {}

        # Default to current quarter
        if quarter is None or fy_year is None:
            curr_quarter, curr_fy_year = get_current_quarter()
            quarter = quarter or curr_quarter
            fy_year = fy_year or curr_fy_year

        # Get scores
        scores = await self.repo.get_scores_for_connections(connection_ids, quarter, fy_year)

        # Build response with issue counts
        result: dict[UUID, dict[str, Any]] = {}

        for connection_id in connection_ids:
            score = scores.get(connection_id)

            if score:
                issue_counts = await self.repo.get_issue_counts(connection_id, quarter, fy_year)
                result[connection_id] = {
                    "quality_score": float(score.overall_score),
                    "critical_issues": issue_counts["critical"],
                }
            else:
                result[connection_id] = {
                    "quality_score": None,
                    "critical_issues": 0,
                }

        return result

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _empty_quality_response(self) -> QualityScoreResponse:
        """Return empty quality response when no score exists."""
        return QualityScoreResponse(
            overall_score=Decimal("0"),
            dimensions=QualityDimensionsResponse(
                freshness=QualityDimensionResponse(
                    name="freshness",
                    score=Decimal("0"),
                    weight=DIMENSION_WEIGHTS["freshness"],
                    details="Not calculated",
                    applicable=True,
                ),
                reconciliation=QualityDimensionResponse(
                    name="reconciliation",
                    score=Decimal("0"),
                    weight=DIMENSION_WEIGHTS["reconciliation"],
                    details="Not calculated",
                    applicable=True,
                ),
                categorization=QualityDimensionResponse(
                    name="categorization",
                    score=Decimal("0"),
                    weight=DIMENSION_WEIGHTS["categorization"],
                    details="Not calculated",
                    applicable=True,
                ),
                completeness=QualityDimensionResponse(
                    name="completeness",
                    score=Decimal("0"),
                    weight=DIMENSION_WEIGHTS["completeness"],
                    details="Not calculated",
                    applicable=True,
                ),
                payg_readiness=QualityDimensionResponse(
                    name="payg_readiness",
                    score=Decimal("0"),
                    weight=DIMENSION_WEIGHTS["payg_readiness"],
                    details="Not calculated",
                    applicable=False,
                ),
            ),
            issue_counts=IssueCounts(),
            last_checked_at=None,
            trend=None,
            has_score=False,
        )

    def _build_dimensions_response(self, score: QualityScore) -> QualityDimensionsResponse:
        """Build dimensions response from a stored score."""
        return QualityDimensionsResponse(
            freshness=QualityDimensionResponse(
                name="freshness",
                score=score.freshness_score,
                weight=DIMENSION_WEIGHTS["freshness"],
                details="Data freshness based on last sync",
                applicable=True,
            ),
            reconciliation=QualityDimensionResponse(
                name="reconciliation",
                score=score.reconciliation_score,
                weight=DIMENSION_WEIGHTS["reconciliation"],
                details="Percentage of reconciled transactions",
                applicable=True,
            ),
            categorization=QualityDimensionResponse(
                name="categorization",
                score=score.categorization_score,
                weight=DIMENSION_WEIGHTS["categorization"],
                details="Percentage with valid GST codes",
                applicable=True,
            ),
            completeness=QualityDimensionResponse(
                name="completeness",
                score=score.completeness_score,
                weight=DIMENSION_WEIGHTS["completeness"],
                details="Presence of required data types",
                applicable=True,
            ),
            payg_readiness=QualityDimensionResponse(
                name="payg_readiness",
                score=score.payg_score or Decimal("0"),
                weight=DIMENSION_WEIGHTS["payg_readiness"],
                details="Payroll data completeness"
                if score.payg_score is not None
                else "Payroll not enabled",
                applicable=score.payg_score is not None,
            ),
        )
