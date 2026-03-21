"""Data threshold trigger evaluator."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, ClassVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.triggers.evaluators.base import BaseTriggerEvaluator
from app.modules.triggers.models import Trigger


class DataThresholdEvaluator(BaseTriggerEvaluator):
    """Evaluator for data threshold triggers.

    Evaluates whether a metric has crossed a threshold, supporting
    various comparison operators and metric types.

    Supported metrics:
    - revenue_ytd: Year-to-date revenue from invoices
    - ar_overdue_total: Total overdue accounts receivable
    - ap_overdue_total: Total overdue accounts payable
    - unreconciled_count: Number of unreconciled bank transactions
    - gst_liability: Current GST liability

    Supported operators:
    - gt: Greater than
    - gte: Greater than or equal
    - lt: Less than
    - lte: Less than or equal
    - eq: Equal to
    """

    OPERATORS: ClassVar[dict[str, Any]] = {
        "gt": lambda a, b: a > b,
        "gte": lambda a, b: a >= b,
        "lt": lambda a, b: a < b,
        "lte": lambda a, b: a <= b,
        "eq": lambda a, b: a == b,
    }

    def __init__(self, db: AsyncSession):
        super().__init__(db)

    async def should_fire(
        self,
        trigger: Trigger,
        client_id: UUID | None = None,
        **kwargs,
    ) -> bool:
        """Check if the threshold condition is met for a client."""
        if not client_id:
            return False

        config = trigger.config
        metric = config.get("metric")
        operator = config.get("operator")
        threshold = config.get("threshold")

        if not all([metric, operator, threshold]):
            return False

        if operator not in self.OPERATORS:
            return False

        # Get the current value for the metric
        current_value = await self._get_metric_value(client_id, metric)
        if current_value is None:
            return False

        # Compare using the specified operator
        compare_fn = self.OPERATORS[operator]
        return compare_fn(current_value, Decimal(str(threshold)))

    async def get_matching_clients(
        self,
        trigger: Trigger,
        tenant_id: UUID,
    ) -> list[UUID]:
        """Get all clients that match the threshold condition."""
        # Import here to avoid circular imports
        from app.modules.integrations.xero.models import XeroConnection

        # Get all active clients for the tenant
        result = await self.db.execute(
            select(XeroConnection.id)
            .where(XeroConnection.tenant_id == tenant_id)
            .where(XeroConnection.is_active.is_(True))
        )
        client_ids = [row[0] for row in result.all()]

        # Check each client against the threshold
        matching = []
        for client_id in client_ids:
            if await self.should_fire(trigger, client_id):
                matching.append(client_id)

        return matching

    async def _get_metric_value(
        self,
        client_id: UUID,
        metric: str,
    ) -> Decimal | None:
        """Get the current value for a metric.

        This queries the client_ai_profiles and related summary tables
        to get the metric value.
        """
        # Import here to avoid circular imports
        from app.modules.clients.models import (
            ClientAIProfile,
            ClientAPAgingSummary,
            ClientARAgingSummary,
            ClientGSTSummary,
        )

        if metric == "revenue_ytd":
            result = await self.db.execute(
                select(ClientAIProfile.revenue_ytd).where(
                    ClientAIProfile.connection_id == client_id
                )
            )
            value = result.scalar_one_or_none()
            return Decimal(str(value)) if value else None

        elif metric == "ar_overdue_total":
            # Sum all overdue buckets (30+, 60+, 90+)
            result = await self.db.execute(
                select(
                    ClientARAgingSummary.bucket_30_60
                    + ClientARAgingSummary.bucket_60_90
                    + ClientARAgingSummary.bucket_90_plus
                )
                .where(ClientARAgingSummary.connection_id == client_id)
                .order_by(ClientARAgingSummary.period_end.desc())
                .limit(1)
            )
            value = result.scalar_one_or_none()
            return Decimal(str(value)) if value else Decimal("0")

        elif metric == "ap_overdue_total":
            # Sum all overdue buckets
            result = await self.db.execute(
                select(
                    ClientAPAgingSummary.bucket_30_60
                    + ClientAPAgingSummary.bucket_60_90
                    + ClientAPAgingSummary.bucket_90_plus
                )
                .where(ClientAPAgingSummary.connection_id == client_id)
                .order_by(ClientAPAgingSummary.period_end.desc())
                .limit(1)
            )
            value = result.scalar_one_or_none()
            return Decimal(str(value)) if value else Decimal("0")

        elif metric == "unreconciled_count":
            # Count unreconciled bank transactions
            from app.modules.integrations.xero.models import XeroBankTransaction

            result = await self.db.execute(
                select(XeroBankTransaction)
                .where(XeroBankTransaction.connection_id == client_id)
                .where(XeroBankTransaction.is_reconciled.is_(False))
            )
            count = len(result.all())
            return Decimal(str(count))

        elif metric == "gst_liability":
            result = await self.db.execute(
                select(ClientGSTSummary.net_gst)
                .where(ClientGSTSummary.connection_id == client_id)
                .order_by(ClientGSTSummary.period_end.desc())
                .limit(1)
            )
            value = result.scalar_one_or_none()
            return Decimal(str(value)) if value else Decimal("0")

        return None
