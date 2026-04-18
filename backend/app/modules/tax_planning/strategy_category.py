"""Strategy category taxonomy for tax planning scenarios.

Closed enumeration of strategy types a scenario can represent. The enum is the
authoritative policy for which strategies structurally require the group tax
model — this flag is derived from the category in code, never from LLM output.

Spec 059 FR-017.
"""

from enum import Enum


class StrategyCategory(str, Enum):
    """Closed set of recognised strategy categories.

    The LLM is instructed to emit one of these values per scenario. Invalid
    categories are rejected by the modeller tool-validation step and retried
    once before falling back to OTHER.
    """

    PREPAYMENT = "prepayment"
    CAPEX_DEDUCTION = "capex_deduction"
    SUPER_CONTRIBUTION = "super_contribution"
    DIRECTOR_SALARY = "director_salary"
    TRUST_DISTRIBUTION = "trust_distribution"
    DIVIDEND_TIMING = "dividend_timing"
    SPOUSE_CONTRIBUTION = "spouse_contribution"
    MULTI_ENTITY_RESTRUCTURE = "multi_entity_restructure"
    OTHER = "other"


REQUIRES_GROUP_MODEL: frozenset[StrategyCategory] = frozenset(
    {
        StrategyCategory.DIRECTOR_SALARY,
        StrategyCategory.TRUST_DISTRIBUTION,
        StrategyCategory.DIVIDEND_TIMING,
        StrategyCategory.SPOUSE_CONTRIBUTION,
        StrategyCategory.MULTI_ENTITY_RESTRUCTURE,
    }
)


def requires_group_model(category: StrategyCategory) -> bool:
    """Return True when the category's benefit cannot be computed on a single entity."""
    return category in REQUIRES_GROUP_MODEL
