"""Base class for insight analyzers."""

import logging
from abc import ABC, abstractmethod
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.insights.models import InsightCategory
from app.modules.insights.schemas import InsightCreate
from app.modules.integrations.xero.models import XeroConnection

logger = logging.getLogger(__name__)


class BaseAnalyzer(ABC):
    """Abstract base class for insight analyzers.

    Each analyzer is responsible for detecting insights in a specific category
    (compliance, quality, cash_flow, tax, strategic).

    Subclasses must implement:
    - category property: The InsightCategory this analyzer handles
    - analyze_client(): Analyze a single client and return insights
    """

    def __init__(self, db: AsyncSession):
        """Initialize the analyzer with database session.

        Args:
            db: Async database session for queries.
        """
        self.db = db

    @property
    @abstractmethod
    def category(self) -> InsightCategory:
        """The category of insights this analyzer produces."""
        ...

    @abstractmethod
    async def analyze_client(
        self,
        tenant_id: UUID,
        client_id: UUID,
    ) -> list[InsightCreate]:
        """Analyze a single client and return insights.

        Args:
            tenant_id: The tenant ID for RLS filtering.
            client_id: The client (XeroConnection) ID to analyze.

        Returns:
            List of InsightCreate objects for any detected issues.
        """
        ...

    async def analyze_tenant(
        self,
        tenant_id: UUID,
    ) -> list[InsightCreate]:
        """Analyze all clients for a tenant.

        Default implementation iterates over all active clients.
        Override if you need cross-client analysis.

        Args:
            tenant_id: The tenant ID to analyze.

        Returns:
            List of InsightCreate objects for all detected issues.
        """
        clients = await self._get_active_clients(tenant_id)
        insights: list[InsightCreate] = []

        for client in clients:
            try:
                client_insights = await self.analyze_client(tenant_id, client.id)
                insights.extend(client_insights)
            except Exception as e:
                logger.error(
                    f"Analyzer {self.__class__.__name__} failed for client {client.id}: {e}"
                )

        return insights

    async def _get_active_clients(self, tenant_id: UUID) -> list[XeroConnection]:
        """Get all active Xero connections for a tenant.

        Args:
            tenant_id: The tenant ID.

        Returns:
            List of active XeroConnection objects.
        """
        result = await self.db.execute(
            select(XeroConnection).where(
                XeroConnection.tenant_id == tenant_id,
                XeroConnection.status == "active",
            )
        )
        return list(result.scalars().all())

    async def _get_client(self, client_id: UUID) -> XeroConnection | None:
        """Get a single client by ID.

        Args:
            client_id: The XeroConnection ID.

        Returns:
            XeroConnection or None if not found.
        """
        result = await self.db.execute(select(XeroConnection).where(XeroConnection.id == client_id))
        return result.scalar_one_or_none()
