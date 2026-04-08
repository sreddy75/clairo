"""Repository for quality scoring database operations."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.quality.issue_detector import DetectedIssue
from app.modules.quality.models import IssueCode, IssueSeverity, QualityIssue, QualityScore


class QualityRepository:
    """Repository for quality score and issue database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # =========================================================================
    # Quality Score Operations
    # =========================================================================

    async def get_score(
        self,
        connection_id: UUID,
        quarter: int,
        fy_year: int,
    ) -> QualityScore | None:
        """Get quality score for a connection and quarter."""
        query = select(QualityScore).where(
            QualityScore.connection_id == connection_id,
            QualityScore.quarter == quarter,
            QualityScore.fy_year == fy_year,
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def upsert_score(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        quarter: int,
        fy_year: int,
        overall_score: Decimal,
        freshness_score: Decimal,
        reconciliation_score: Decimal,
        categorization_score: Decimal,
        completeness_score: Decimal,
        payg_score: Decimal | None,
        calculation_duration_ms: int | None = None,
        trigger_reason: str | None = None,
    ) -> QualityScore:
        """Insert or update a quality score."""
        now = datetime.now(UTC)

        # Use PostgreSQL upsert
        stmt = pg_insert(QualityScore).values(
            tenant_id=tenant_id,
            connection_id=connection_id,
            quarter=quarter,
            fy_year=fy_year,
            overall_score=overall_score,
            freshness_score=freshness_score,
            reconciliation_score=reconciliation_score,
            categorization_score=categorization_score,
            completeness_score=completeness_score,
            payg_score=payg_score,
            calculated_at=now,
            calculation_duration_ms=calculation_duration_ms,
            trigger_reason=trigger_reason,
            created_at=now,
            updated_at=now,
        )

        stmt = stmt.on_conflict_do_update(
            constraint="uq_quality_scores_connection_quarter",
            set_={
                "overall_score": overall_score,
                "freshness_score": freshness_score,
                "reconciliation_score": reconciliation_score,
                "categorization_score": categorization_score,
                "completeness_score": completeness_score,
                "payg_score": payg_score,
                "calculated_at": now,
                "calculation_duration_ms": calculation_duration_ms,
                "trigger_reason": trigger_reason,
                "updated_at": now,
            },
        ).returning(QualityScore)

        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_scores_for_connections(
        self,
        connection_ids: list[UUID],
        quarter: int,
        fy_year: int,
    ) -> dict[UUID, QualityScore]:
        """Get quality scores for multiple connections."""
        if not connection_ids:
            return {}

        query = select(QualityScore).where(
            QualityScore.connection_id.in_(connection_ids),
            QualityScore.quarter == quarter,
            QualityScore.fy_year == fy_year,
        )
        result = await self.session.execute(query)
        scores = result.scalars().all()

        return {score.connection_id: score for score in scores}

    async def get_portfolio_summary(
        self,
        tenant_id: UUID,
        quarter: int,
        fy_year: int,
    ) -> dict:
        """Get quality summary across all connections for a tenant."""
        query = select(
            func.avg(QualityScore.overall_score).label("avg_score"),
            func.count().filter(QualityScore.overall_score > 80).label("good_count"),
            func.count()
            .filter(
                QualityScore.overall_score >= 50,
                QualityScore.overall_score <= 80,
            )
            .label("fair_count"),
            func.count().filter(QualityScore.overall_score < 50).label("poor_count"),
        ).where(
            QualityScore.tenant_id == tenant_id,
            QualityScore.quarter == quarter,
            QualityScore.fy_year == fy_year,
        )

        result = await self.session.execute(query)
        row = result.one()

        return {
            "avg_score": Decimal(str(row.avg_score)) if row.avg_score else Decimal("0"),
            "good_count": row.good_count or 0,
            "fair_count": row.fair_count or 0,
            "poor_count": row.poor_count or 0,
        }

    # =========================================================================
    # Quality Issue Operations
    # =========================================================================

    async def get_issues(
        self,
        connection_id: UUID,
        quarter: int,
        fy_year: int,
        severity: IssueSeverity | None = None,
        issue_code: IssueCode | None = None,
        include_dismissed: bool = False,
    ) -> list[QualityIssue]:
        """Get quality issues for a connection."""
        query = select(QualityIssue).where(
            QualityIssue.connection_id == connection_id,
            QualityIssue.quarter == quarter,
            QualityIssue.fy_year == fy_year,
        )

        if severity:
            query = query.where(QualityIssue.severity == severity.value)

        if issue_code:
            query = query.where(QualityIssue.code == issue_code.value)

        if not include_dismissed:
            query = query.where(QualityIssue.dismissed == False)  # noqa: E712

        # Exclude resolved issues (resolved_at is set when issue no longer detected)
        query = query.where(QualityIssue.resolved_at.is_(None))

        # Order by severity priority (critical first)
        query = query.order_by(
            func.array_position(
                ["critical", "error", "warning", "info"],
                QualityIssue.severity,
            ),
            QualityIssue.first_detected_at.desc(),
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_issue_counts(
        self,
        connection_id: UUID,
        quarter: int,
        fy_year: int,
    ) -> dict[str, int]:
        """Get issue counts by severity."""
        query = select(
            func.count().filter(QualityIssue.severity == "critical").label("critical"),
            func.count().filter(QualityIssue.severity == "error").label("error"),
            func.count().filter(QualityIssue.severity == "warning").label("warning"),
            func.count().filter(QualityIssue.severity == "info").label("info"),
        ).where(
            QualityIssue.connection_id == connection_id,
            QualityIssue.quarter == quarter,
            QualityIssue.fy_year == fy_year,
            QualityIssue.dismissed == False,  # noqa: E712
            QualityIssue.resolved_at.is_(None),
        )

        result = await self.session.execute(query)
        row = result.one()

        return {
            "critical": row.critical or 0,
            "error": row.error or 0,
            "warning": row.warning or 0,
            "info": row.info or 0,
        }

    async def get_total_critical_issues(
        self,
        tenant_id: UUID,
        quarter: int,
        fy_year: int,
    ) -> int:
        """Get total critical issues across all connections for a tenant."""
        query = select(func.count()).where(
            QualityIssue.tenant_id == tenant_id,
            QualityIssue.quarter == quarter,
            QualityIssue.fy_year == fy_year,
            QualityIssue.severity == "critical",
            QualityIssue.dismissed == False,  # noqa: E712
            QualityIssue.resolved_at.is_(None),
        )
        result = await self.session.scalar(query)
        return result or 0

    async def upsert_issues(
        self,
        tenant_id: UUID,
        connection_id: UUID,
        quarter: int,
        fy_year: int,
        detected_issues: list[DetectedIssue],
    ) -> list[QualityIssue]:
        """Upsert detected issues, marking resolved ones."""
        now = datetime.now(UTC)

        # Get existing active issues
        existing_query = select(QualityIssue).where(
            QualityIssue.connection_id == connection_id,
            QualityIssue.quarter == quarter,
            QualityIssue.fy_year == fy_year,
            QualityIssue.resolved_at.is_(None),
        )
        existing_result = await self.session.execute(existing_query)
        existing_issues = {issue.code: issue for issue in existing_result.scalars().all()}

        # Track which issues are still present
        present_codes = set()
        upserted_issues: list[QualityIssue] = []

        for detected in detected_issues:
            present_codes.add(detected.code.value)

            if detected.code.value in existing_issues:
                # Update existing issue
                issue = existing_issues[detected.code.value]
                issue.last_seen_at = now
                issue.affected_count = detected.affected_count
                issue.affected_ids = detected.affected_ids
                issue.description = detected.description
                issue.updated_at = now
                upserted_issues.append(issue)
            else:
                # Create new issue
                issue = QualityIssue(
                    tenant_id=tenant_id,
                    connection_id=connection_id,
                    quarter=quarter,
                    fy_year=fy_year,
                    code=detected.code.value,
                    severity=detected.severity.value,
                    title=detected.title,
                    description=detected.description,
                    affected_entity_type=detected.affected_entity_type,
                    affected_count=detected.affected_count,
                    affected_ids=detected.affected_ids,
                    suggested_action=detected.suggested_action,
                    first_detected_at=now,
                    last_seen_at=now,
                    created_at=now,
                    updated_at=now,
                )
                self.session.add(issue)
                upserted_issues.append(issue)

        # Mark resolved issues (not in detected but were active)
        for code, issue in existing_issues.items():
            if code not in present_codes and not issue.dismissed:
                issue.resolved_at = now
                issue.updated_at = now

        await self.session.flush()
        return upserted_issues

    async def dismiss_issue(
        self,
        issue_id: UUID,
        user_id: UUID,
        reason: str,
        tenant_id: UUID | None = None,
    ) -> QualityIssue | None:
        """Dismiss a quality issue."""
        now = datetime.now(UTC)

        stmt = (
            update(QualityIssue)
            .where(QualityIssue.id == issue_id)
            .values(
                dismissed=True,
                dismissed_by=user_id,
                dismissed_at=now,
                dismissed_reason=reason,
                updated_at=now,
            )
            .returning(QualityIssue)
        )
        if tenant_id is not None:
            stmt = stmt.where(QualityIssue.tenant_id == tenant_id)

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_issue_by_id(
        self, issue_id: UUID, tenant_id: UUID | None = None
    ) -> QualityIssue | None:
        """Get a single issue by ID."""
        query = select(QualityIssue).where(QualityIssue.id == issue_id)
        if tenant_id is not None:
            query = query.where(QualityIssue.tenant_id == tenant_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def delete_issues_for_quarter(
        self,
        connection_id: UUID,
        quarter: int,
        fy_year: int,
    ) -> int:
        """Delete all issues for a quarter (used when recalculating)."""
        stmt = delete(QualityIssue).where(
            QualityIssue.connection_id == connection_id,
            QualityIssue.quarter == quarter,
            QualityIssue.fy_year == fy_year,
        )
        result = await self.session.execute(stmt)
        return result.rowcount

    # =========================================================================
    # Dashboard Integration Methods
    # =========================================================================

    async def get_quality_summary_for_tenant(
        self,
        tenant_id: UUID,
        quarter: int,
        fy_year: int,
    ) -> dict:
        """Get quality summary for dashboard including critical issues count."""
        # Get portfolio summary (avg score and counts by tier)
        portfolio = await self.get_portfolio_summary(tenant_id, quarter, fy_year)

        # Get total critical issues
        critical_issues = await self.get_total_critical_issues(tenant_id, quarter, fy_year)

        return {
            "avg_score": portfolio["avg_score"],
            "good_count": portfolio["good_count"],
            "fair_count": portfolio["fair_count"],
            "poor_count": portfolio["poor_count"],
            "total_critical_issues": critical_issues,
        }

    async def get_quality_scores_for_connections(
        self,
        connection_ids: list[UUID],
        quarter: int,
        fy_year: int,
    ) -> dict[UUID, dict]:
        """Get quality scores and critical issue counts for multiple connections.

        Returns dict mapping connection_id -> {overall_score, critical_issues}
        """
        if not connection_ids:
            return {}

        # Get scores
        scores = await self.get_scores_for_connections(connection_ids, quarter, fy_year)

        # Get critical issue counts per connection
        critical_query = (
            select(
                QualityIssue.connection_id,
                func.count().label("critical_count"),
            )
            .where(
                QualityIssue.connection_id.in_(connection_ids),
                QualityIssue.quarter == quarter,
                QualityIssue.fy_year == fy_year,
                QualityIssue.severity == "critical",
                QualityIssue.dismissed == False,  # noqa: E712
                QualityIssue.resolved_at.is_(None),
            )
            .group_by(QualityIssue.connection_id)
        )
        critical_result = await self.session.execute(critical_query)
        critical_counts = {row.connection_id: row.critical_count for row in critical_result}

        # Build result dict
        result: dict[UUID, dict] = {}
        for conn_id in connection_ids:
            score = scores.get(conn_id)
            result[conn_id] = {
                "overall_score": score.overall_score if score else None,
                "critical_issues": critical_counts.get(conn_id, 0),
            }

        return result
