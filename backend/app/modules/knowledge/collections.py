"""Pinecone index and namespace configuration.

This module defines the knowledge base namespaces and provides
a manager class for initializing, resetting, and querying the index.

With Pinecone Serverless, we use a SINGLE index with multiple namespaces
(more cost-effective than multiple indexes).

Namespaces are configured for:
- 1024-dimension vectors (voyage-3.5-lite)
- Cosine similarity metric

Environment Isolation:
- Dev namespaces: compliance_knowledge_dev, strategic_advisory_dev, etc.
- Prod namespaces: compliance_knowledge_prod, strategic_advisory_prod, etc.
- This ensures dev/prod data never mixes in the shared Pinecone index.
"""

import logging
import os
from dataclasses import dataclass
from typing import Any

from app.core.pinecone_service import PineconeService

logger = logging.getLogger(__name__)

# The single Pinecone index name for all knowledge
INDEX_NAME = "clairo-knowledge"

# Vector dimensions for voyage-3.5-lite
VECTOR_DIMENSION = 1024


def get_environment() -> str:
    """Get current environment name for namespace prefixing.

    Returns:
        Environment string: 'dev', 'staging', or 'prod'
    """
    env = os.getenv("ENVIRONMENT", "development").lower()
    if env in ("production", "prod"):
        return "prod"
    elif env in ("staging", "stage"):
        return "staging"
    return "dev"


def get_namespace_with_env(base_name: str) -> str:
    """Get the full namespace name, adding environment suffix only for non-shared namespaces.

    Knowledge namespaces (compliance_knowledge, strategic_advisory, etc.) are shared
    across environments — tax legislation is the same regardless of dev/prod.
    Tenant-specific namespaces (insight_dedup) get an environment suffix.

    Args:
        base_name: Base namespace name (e.g., 'compliance_knowledge')

    Returns:
        Namespace name, with or without environment suffix.
    """
    config = NAMESPACES.get(base_name)
    if config and config.shared:
        return base_name
    env = get_environment()
    return f"{base_name}_{env}"


def get_base_namespace(full_name: str) -> str:
    """Extract base namespace name from full name with env suffix.

    Handles both shared namespaces (no suffix) and env-specific ones.

    Args:
        full_name: Full namespace name (e.g., 'compliance_knowledge_dev' or 'compliance_knowledge')

    Returns:
        Base namespace name (e.g., 'compliance_knowledge')
    """
    # If it's already a known base name, return as-is
    if full_name in NAMESPACES:
        return full_name
    for suffix in ("_dev", "_staging", "_prod"):
        if full_name.endswith(suffix):
            return full_name[: -len(suffix)]
    return full_name


@dataclass
class NamespaceConfig:
    """Configuration for a Pinecone namespace."""

    name: str
    description: str
    # Metadata fields that will be indexed for filtering
    filterable_fields: list[str] | None = None
    # If True, namespace is shared across environments (no _dev/_prod suffix).
    # Knowledge content (legislation, rulings) is the same regardless of env.
    shared: bool = False


# =============================================================================
# Namespace Definitions (replacing Qdrant collections)
# =============================================================================

NAMESPACES: dict[str, NamespaceConfig] = {
    "compliance_knowledge": NamespaceConfig(
        name="compliance_knowledge",
        description="ATO rules, legislation, tax compliance guidance",
        filterable_fields=[
            "source_type",
            "entity_types",
            "industries",
            "effective_date",
            "ruling_number",
            "is_superseded",
        ],
        shared=True,
    ),
    "strategic_advisory": NamespaceConfig(
        name="strategic_advisory",
        description="Tax optimization, entity structuring, growth strategies",
        filterable_fields=[
            "source_type",
            "entity_types",
            "industries",
            "revenue_brackets",
        ],
        shared=True,
    ),
    "industry_knowledge": NamespaceConfig(
        name="industry_knowledge",
        description="Industry-specific deductions, benchmarks, practices",
        filterable_fields=[
            "source_type",
            "industries",
            "entity_types",
            "anzsic_code",
        ],
        shared=True,
    ),
    "business_fundamentals": NamespaceConfig(
        name="business_fundamentals",
        description="Starting business, ABN, planning, legal basics",
        filterable_fields=[
            "source_type",
            "entity_types",
        ],
        shared=True,
    ),
    "financial_management": NamespaceConfig(
        name="financial_management",
        description="Cash flow, debtor management, pricing, KPIs",
        filterable_fields=[
            "source_type",
            "revenue_brackets",
        ],
        shared=True,
    ),
    "people_operations": NamespaceConfig(
        name="people_operations",
        description="Hiring, employment, payroll basics, WHS",
        filterable_fields=[
            "source_type",
            "entity_types",
        ],
        shared=True,
    ),
    "insight_dedup": NamespaceConfig(
        name="insight_dedup",
        description="Semantic deduplication vectors for insights",
        filterable_fields=["client_id", "tenant_id"],
        shared=False,
    ),
    # Spec 060: Tax strategies knowledge base. Shared across all envs; vector
    # writes gated on TAX_STRATEGIES_VECTOR_WRITE_ENABLED. ~415 entries at
    # full coverage × 2 chunks each = ~830 vectors.
    "tax_strategies": NamespaceConfig(
        name="tax_strategies",
        description=(
            "Clairo-authored Australian tax planning strategies. "
            "415 entries across 8 categories. Platform-baseline; "
            "private overlays filtered via metadata tenant_id."
        ),
        filterable_fields=[
            "tenant_id",
            "strategy_id",
            "categories",
            "chunk_section",
            "entity_types",
            "industry_triggers",
            "income_band_min",
            "income_band_max",
            "turnover_band_min",
            "turnover_band_max",
            "age_min",
            "age_max",
            "financial_impact_type",
            "fy_applicable_from",
            "fy_applicable_to",
            "is_superseded",
        ],
        shared=True,
    ),
}


# Common payload fields for all namespaces
COMMON_PAYLOAD_FIELDS = [
    "chunk_id",  # UUID string
    "source_id",  # UUID string - link to KnowledgeSource
    "source_url",  # Original URL
    "title",  # Document title
    "text",  # Original text content
    "chunk_index",  # Position in source document
    "scraped_at",  # ISO datetime
    "confidence_level",  # high, medium, low
]

# For backwards compatibility with existing code
COLLECTIONS = NAMESPACES


class CollectionManager:
    """Manager for Pinecone knowledge base index and namespaces.

    Provides methods to initialize, reset, and query namespace status.
    """

    def __init__(self, pinecone: PineconeService) -> None:
        """Initialize collection manager.

        Args:
            pinecone: Pinecone service instance.
        """
        self._pinecone = pinecone

    async def initialize_all(self) -> dict[str, bool]:
        """Initialize the Pinecone index.

        Creates the index if it doesn't exist. Namespaces are created
        automatically when vectors are upserted.

        Returns:
            Dict with index creation status.
        """
        results: dict[str, bool] = {}
        env = get_environment()

        # Create the main index if it doesn't exist
        created = await self._pinecone.create_index(
            name=INDEX_NAME,
            dimension=VECTOR_DIMENSION,
            metric="cosine",
        )

        if created:
            logger.info(f"Created Pinecone index: {INDEX_NAME}")
        else:
            logger.debug(f"Pinecone index already exists: {INDEX_NAME}")

        # Mark all namespaces as initialized (they're created on upsert)
        for name in NAMESPACES:
            full_name = get_namespace_with_env(name)
            results[full_name] = created

        logger.info(f"Initialized namespaces for environment: {env}")
        return results

    async def reset_collection(self, name: str) -> bool:
        """Delete all vectors in a specific namespace.

        Args:
            name: Base namespace name (must be one of the defined namespaces).
                  Environment suffix will be added automatically.

        Returns:
            True if reset successful.

        Raises:
            ValueError: If namespace name is not valid.
        """
        # Get base name if full name was provided
        base_name = get_base_namespace(name)

        if base_name not in NAMESPACES:
            raise ValueError(
                f"Unknown namespace: {base_name}. Valid namespaces: {list(NAMESPACES.keys())}"
            )

        # Get full namespace name with environment suffix
        full_name = get_namespace_with_env(base_name)

        # Delete all vectors in the namespace
        try:
            # Pinecone's delete with delete_all=True clears the namespace
            await self._pinecone.delete_vectors(
                index_name=INDEX_NAME,
                ids=[],  # Empty list with delete_all
                namespace=full_name,
            )
            logger.info(f"Reset namespace: {full_name}")
            return True
        except Exception as e:
            logger.warning(f"Failed to reset namespace {full_name}: {e}")
            # If namespace doesn't exist, that's fine
            return True

    async def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics for all namespaces in current environment.

        Returns:
            Dict mapping base namespace name to stats dict with:
            - exists: bool
            - vectors_count: int
            - description: str
            - full_name: str (with environment suffix)
            - environment: str
        """
        stats: dict[str, dict[str, Any]] = {}
        env = get_environment()

        try:
            # Get index info which includes namespace stats
            index_info = await self._pinecone.get_index_info(INDEX_NAME)
            namespace_counts = index_info.get("namespaces", {})

            for base_name, config in NAMESPACES.items():
                full_name = get_namespace_with_env(base_name)
                ns_stats = namespace_counts.get(full_name, {})
                vector_count = ns_stats.get("vector_count", 0) if ns_stats else 0

                stats[base_name] = {
                    "exists": vector_count > 0,
                    "description": config.description,
                    "name": base_name,
                    "full_name": full_name,
                    "environment": env,
                    "vectors_count": vector_count,
                    "status": "ready" if vector_count > 0 else "empty",
                }

        except Exception as e:
            logger.warning(f"Failed to get index stats: {e}")
            # Return empty stats for all namespaces
            for base_name, config in NAMESPACES.items():
                full_name = get_namespace_with_env(base_name)
                stats[base_name] = {
                    "exists": False,
                    "description": config.description,
                    "name": base_name,
                    "full_name": full_name,
                    "environment": env,
                    "vectors_count": 0,
                    "status": "unknown",
                }

        return stats

    async def get_collection_stats(self, name: str) -> dict[str, Any]:
        """Get statistics for a specific namespace.

        Args:
            name: Base namespace name.

        Returns:
            Stats dict with exists, vectors_count, status, etc.
        """
        base_name = get_base_namespace(name)

        if base_name not in NAMESPACES:
            raise ValueError(f"Unknown namespace: {base_name}")

        all_stats = await self.get_all_stats()
        return all_stats.get(
            base_name,
            {
                "exists": False,
                "description": NAMESPACES[base_name].description,
                "full_name": get_namespace_with_env(base_name),
                "vectors_count": 0,
            },
        )

    @staticmethod
    def get_collection_names() -> list[str]:
        """Get list of all namespace names.

        Returns:
            List of namespace names.
        """
        return list(NAMESPACES.keys())

    @staticmethod
    def get_collection_config(name: str) -> NamespaceConfig:
        """Get configuration for a specific namespace.

        Args:
            name: Namespace name.

        Returns:
            NamespaceConfig for the namespace.

        Raises:
            ValueError: If namespace name is not valid.
        """
        if name not in NAMESPACES:
            raise ValueError(f"Unknown namespace: {name}")
        return NAMESPACES[name]

    @staticmethod
    def get_index_name() -> str:
        """Get the Pinecone index name.

        Returns:
            The index name.
        """
        return INDEX_NAME
