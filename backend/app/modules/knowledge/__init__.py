"""Knowledge Base module for Clairo.

This module provides the AI knowledge infrastructure including:
- Qdrant collection management for 6 knowledge domains
- Content ingestion pipeline (ATO, AustLII, Business.gov.au)
- Semantic chunking and embedding
- Vector search with metadata filtering

Collections:
- compliance_knowledge: ATO rules, legislation, tax compliance
- strategic_advisory: Tax optimization, entity structuring
- industry_knowledge: Industry-specific deductions and practices
- business_fundamentals: Starting/running business guides
- financial_management: Cash flow, debtor management, KPIs
- people_operations: HR, hiring, employment basics
"""

from app.modules.knowledge.collections import COLLECTIONS, CollectionManager

__all__ = [
    "COLLECTIONS",
    "CollectionManager",
]
