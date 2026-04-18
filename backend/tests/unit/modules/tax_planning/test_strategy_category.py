"""Unit tests for the strategy category enum and group-model mapping.

Covers spec 059 FR-017 — the closed-set enum and the policy mapping of which
categories require the group tax model (multi-entity).
"""

import pytest

from app.modules.tax_planning.strategy_category import (
    REQUIRES_GROUP_MODEL,
    StrategyCategory,
    requires_group_model,
)


class TestStrategyCategoryEnum:
    def test_enum_has_expected_members(self) -> None:
        expected = {
            "prepayment",
            "capex_deduction",
            "super_contribution",
            "director_salary",
            "trust_distribution",
            "dividend_timing",
            "spouse_contribution",
            "multi_entity_restructure",
            "other",
        }
        assert {c.value for c in StrategyCategory} == expected

    def test_enum_values_are_string_typed(self) -> None:
        for category in StrategyCategory:
            assert isinstance(category.value, str)
            assert category.value == category.value.lower()
            assert " " not in category.value

    def test_parsing_from_string_value_round_trips(self) -> None:
        for category in StrategyCategory:
            parsed = StrategyCategory(category.value)
            assert parsed is category


class TestRequiresGroupModel:
    @pytest.mark.parametrize(
        "category",
        [
            StrategyCategory.DIRECTOR_SALARY,
            StrategyCategory.TRUST_DISTRIBUTION,
            StrategyCategory.DIVIDEND_TIMING,
            StrategyCategory.SPOUSE_CONTRIBUTION,
            StrategyCategory.MULTI_ENTITY_RESTRUCTURE,
        ],
    )
    def test_multi_entity_categories_require_group_model(
        self,
        category: StrategyCategory,
    ) -> None:
        assert requires_group_model(category) is True
        assert category in REQUIRES_GROUP_MODEL

    @pytest.mark.parametrize(
        "category",
        [
            StrategyCategory.PREPAYMENT,
            StrategyCategory.CAPEX_DEDUCTION,
            StrategyCategory.SUPER_CONTRIBUTION,
            StrategyCategory.OTHER,
        ],
    )
    def test_single_entity_categories_do_not_require_group_model(
        self,
        category: StrategyCategory,
    ) -> None:
        assert requires_group_model(category) is False
        assert category not in REQUIRES_GROUP_MODEL

    def test_requires_group_model_set_is_frozen(self) -> None:
        with pytest.raises(AttributeError):
            REQUIRES_GROUP_MODEL.add(StrategyCategory.OTHER)  # type: ignore[attr-defined]

    def test_requires_group_model_set_size_matches_spec(self) -> None:
        # FR-017 names exactly five categories that require the group model.
        assert len(REQUIRES_GROUP_MODEL) == 5
