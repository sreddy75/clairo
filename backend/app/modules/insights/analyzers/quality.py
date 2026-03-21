"""Quality analyzer for detecting data quality insights.

Detects:
- Unreconciled transactions (count > threshold)
- Uncoded GST transactions
- Bank reconciliation gaps
"""

import logging
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.insights.analyzers.base import BaseAnalyzer
from app.modules.insights.models import InsightCategory, InsightPriority
from app.modules.insights.schemas import InsightCreate, SuggestedAction
from app.modules.quality.models import IssueCode, QualityIssue, QualityScore

logger = logging.getLogger(__name__)

# Thresholds
UNRECONCILED_WARNING = 10
UNRECONCILED_CRITICAL = 25
UNCODED_GST_WARNING = 5
STALE_RECONCILIATION_DAYS = 14


class QualityAnalyzer(BaseAnalyzer):
    """Analyzer for data quality insights."""

    def __init__(self, db: AsyncSession):
        super().__init__(db)

    @property
    def category(self) -> InsightCategory:
        return InsightCategory.QUALITY

    async def analyze_client(
        self,
        tenant_id: UUID,  # noqa: ARG002 - Required by interface
        client_id: UUID,
    ) -> list[InsightCreate]:
        """Analyze a client for quality issues."""
        insights: list[InsightCreate] = []

        # Get current quality score
        score = await self._get_latest_quality_score(client_id)

        # Get quality issues
        issues = await self._get_active_issues(client_id)

        # Check unreconciled transactions
        unreconciled_insight = await self._check_unreconciled(client_id, issues)
        if unreconciled_insight:
            insights.append(unreconciled_insight)

        # Check uncoded GST transactions
        uncoded_insight = await self._check_uncoded_gst(client_id, issues)
        if uncoded_insight:
            insights.append(uncoded_insight)

        # Check reconciliation freshness
        recon_insight = await self._check_reconciliation_freshness(client_id, score)
        if recon_insight:
            insights.append(recon_insight)

        # Check overall quality score
        score_insight = self._check_overall_score(client_id, score)
        if score_insight:
            insights.append(score_insight)

        return insights

    async def _get_latest_quality_score(self, client_id: UUID) -> QualityScore | None:
        """Get the latest quality score for a client."""
        result = await self.db.execute(
            select(QualityScore)
            .where(QualityScore.connection_id == client_id)
            .order_by(QualityScore.calculated_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_active_issues(self, client_id: UUID) -> list[QualityIssue]:
        """Get all active (unresolved) quality issues."""
        result = await self.db.execute(
            select(QualityIssue).where(
                QualityIssue.connection_id == client_id,
                QualityIssue.resolved_at.is_(None),
            )
        )
        return list(result.scalars().all())

    async def _check_unreconciled(
        self,
        client_id: UUID,
        issues: list[QualityIssue],
    ) -> InsightCreate | None:
        """Check for unreconciled transaction issues."""
        # Count unreconciled issues - using 'code' field from the model
        unreconciled_issues = [i for i in issues if i.code == IssueCode.UNRECONCILED_TXN.value]

        if not unreconciled_issues:
            return None

        # Sum affected_count across all unreconciled issues
        count = sum(i.affected_count or 0 for i in unreconciled_issues)
        if count < UNRECONCILED_WARNING:
            return None

        # We don't have total amount in the model, so just use count
        total_amount = Decimal(0)

        if count >= UNRECONCILED_CRITICAL:
            priority = InsightPriority.HIGH
            title = f"{count} Unreconciled Transactions"
            summary = f"Critical: {count} transactions need reconciliation."
        else:
            priority = InsightPriority.MEDIUM
            title = f"{count} Unreconciled Transactions"
            summary = f"{count} transactions pending reconciliation."

        if total_amount > 0:
            summary += f" Total: ${total_amount:,.2f}"

        return InsightCreate(
            category=InsightCategory.QUALITY,
            insight_type="unreconciled_transactions",
            priority=priority,
            title=title,
            summary=summary,
            detail=self._unreconciled_detail(count, total_amount, unreconciled_issues[:5]),
            suggested_actions=[
                SuggestedAction(
                    label="Review Transactions", url=f"/clients/{client_id}/reconciliation"
                ),
                SuggestedAction(label="View in Xero", action="open_xero"),
            ],
            related_url=f"/clients/{client_id}/reconciliation",
            confidence=0.95,
            data_snapshot={
                "count": count,
                "total_amount": float(total_amount),
            },
        )

    def _unreconciled_detail(
        self,
        count: int,
        total: Decimal,  # noqa: ARG002 - kept for future use
        sample_issues: list[QualityIssue],
    ) -> str:
        """Generate detailed unreconciled analysis."""
        detail = f"""## Unreconciled Transactions

**Total Count**: {count} transactions

### Issues Found

"""
        for issue in sample_issues:
            detail += f"- {issue.title}: {issue.affected_count} items\n"

        detail += """
### Recommended Actions

1. Review each transaction in Xero
2. Match with corresponding bank entries
3. Create adjustment entries if needed
4. Flag any suspicious transactions for review
"""
        return detail

    async def _check_uncoded_gst(
        self,
        client_id: UUID,
        issues: list[QualityIssue],
    ) -> InsightCreate | None:
        """Check for transactions missing GST codes."""
        uncoded_issues = [i for i in issues if i.code == IssueCode.MISSING_GST_CODE.value]

        if not uncoded_issues:
            return None

        # Sum affected_count across all uncoded GST issues
        count = sum(i.affected_count or 0 for i in uncoded_issues)
        if count < UNCODED_GST_WARNING:
            return None

        priority = InsightPriority.MEDIUM
        title = f"{count} Transactions Missing GST Codes"
        summary = f"{count} transactions need GST coding before BAS."

        return InsightCreate(
            category=InsightCategory.QUALITY,
            insight_type="uncoded_gst_transactions",
            priority=priority,
            title=title,
            summary=summary,
            suggested_actions=[
                SuggestedAction(
                    label="Review GST Coding", url=f"/clients/{client_id}/transactions"
                ),
            ],
            related_url=f"/clients/{client_id}/transactions",
            confidence=0.90,
            data_snapshot={"count": count},
        )

    async def _check_reconciliation_freshness(
        self,
        client_id: UUID,
        score: QualityScore | None,
    ) -> InsightCreate | None:
        """Check when bank reconciliation was last performed."""
        if not score:
            return None

        # Check freshness score as a proxy for reconciliation status
        if score.freshness_score and score.freshness_score < 50:
            return InsightCreate(
                category=InsightCategory.QUALITY,
                insight_type="stale_reconciliation",
                priority=InsightPriority.MEDIUM,
                title="Bank Reconciliation Overdue",
                summary=f"Data may be stale. Last quality check: {score.calculated_at.strftime('%d %b')}.",
                suggested_actions=[
                    SuggestedAction(label="Sync Now", action="trigger_sync"),
                    SuggestedAction(label="View Quality", url=f"/clients/{client_id}/quality"),
                ],
                related_url=f"/clients/{client_id}/quality",
                confidence=0.75,
                data_snapshot={
                    "freshness_score": float(score.freshness_score),
                    "calculated_at": score.calculated_at.isoformat(),
                },
            )

        return None

    def _check_overall_score(
        self,
        client_id: UUID,
        score: QualityScore | None,
    ) -> InsightCreate | None:
        """Check if overall quality score is low."""
        if not score:
            return None

        if score.overall_score >= 70:
            return None  # Score is acceptable

        if score.overall_score < 50:
            priority = InsightPriority.HIGH
            title = "Critical Data Quality Issues"
            summary = f"Quality score {score.overall_score:.0f}% - requires immediate attention."
        else:
            priority = InsightPriority.MEDIUM
            title = "Data Quality Needs Attention"
            summary = f"Quality score {score.overall_score:.0f}% - review recommended."

        return InsightCreate(
            category=InsightCategory.QUALITY,
            insight_type="low_quality_score",
            priority=priority,
            title=title,
            summary=summary,
            detail=self._quality_score_detail(score),
            suggested_actions=[
                SuggestedAction(label="Review Issues", url=f"/clients/{client_id}/quality"),
            ],
            related_url=f"/clients/{client_id}/quality",
            confidence=0.90,
            data_snapshot={
                "overall_score": float(score.overall_score),
                "freshness_score": float(score.freshness_score),
                "reconciliation_score": float(score.reconciliation_score),
                "categorization_score": float(score.categorization_score),
            },
        )

    def _quality_score_detail(self, score: QualityScore) -> str:
        """Generate detailed quality score breakdown."""
        return f"""## Data Quality Analysis

**Overall Score**: {score.overall_score:.0f}%

### Dimension Breakdown

| Dimension | Score |
|-----------|-------|
| Freshness | {score.freshness_score:.0f}% |
| Reconciliation | {score.reconciliation_score:.0f}% |
| Categorization | {score.categorization_score:.0f}% |
| Completeness | {score.completeness_score:.0f}% |
{f"| PAYG | {score.payg_score:.0f}% |" if score.payg_score else ""}

### Priority Actions

Focus on the lowest-scoring dimensions first to improve overall data quality.
"""
