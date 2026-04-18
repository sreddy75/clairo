"""Audit event type definitions for the tax_strategies module (Spec 060).

Emission points:
- tax_strategy.created:          seed_from_csv per-row, single-row create
- tax_strategy.status_changed:   TaxStrategyService._transition_status
- tax_strategy.approved:         _transition_status on in_review → approved
- tax_strategy.published:        publish_strategy Celery task on upsert success
- tax_strategy.superseded:       supersede_strategy on new version creation
- tax_strategy.seed_executed:    seed_from_csv summary (one per run)
"""

TAX_STRATEGY_CREATED = "tax_strategy.created"
TAX_STRATEGY_STATUS_CHANGED = "tax_strategy.status_changed"
TAX_STRATEGY_APPROVED = "tax_strategy.approved"
TAX_STRATEGY_PUBLISHED = "tax_strategy.published"
TAX_STRATEGY_SUPERSEDED = "tax_strategy.superseded"
TAX_STRATEGY_SEED_EXECUTED = "tax_strategy.seed_executed"

TAX_STRATEGIES_AUDIT_EVENTS: dict[str, dict[str, str]] = {
    TAX_STRATEGY_CREATED: {
        "category": "data",
        "description": "Tax strategy stub created (per-row seed or single create)",
        "retention": "7y",
    },
    TAX_STRATEGY_STATUS_CHANGED: {
        "category": "data",
        "description": "Tax strategy lifecycle status transition",
        "retention": "7y",
    },
    TAX_STRATEGY_APPROVED: {
        "category": "compliance",
        "description": "Reviewer approved a strategy for publication",
        "retention": "7y",
    },
    TAX_STRATEGY_PUBLISHED: {
        "category": "compliance",
        "description": "Strategy published — chunks embedded and upserted to vector store",
        "retention": "7y",
    },
    TAX_STRATEGY_SUPERSEDED: {
        "category": "data",
        "description": "Replacement version published; prior version flagged superseded",
        "retention": "7y",
    },
    TAX_STRATEGY_SEED_EXECUTED: {
        "category": "data",
        "description": "Bulk seed-from-CSV action executed",
        "retention": "7y",
    },
}
