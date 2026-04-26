"""Domain exceptions for the tax_strategies module.

Service layer raises these; router converts to HTTPException per
constitution §VI.
"""

from __future__ import annotations

from app.core.exceptions import DomainError


class StrategyNotFoundError(DomainError):
    """Raised when a strategy is looked up by identifier but does not exist."""

    def __init__(self, strategy_id: str) -> None:
        super().__init__(f"Tax strategy {strategy_id!r} not found")
        self.strategy_id = strategy_id


class InvalidStatusTransitionError(DomainError):
    """Raised when a status transition is not permitted by the state machine."""

    def __init__(self, strategy_id: str, from_status: str, to_status: str) -> None:
        super().__init__(
            f"Invalid status transition for {strategy_id}: {from_status!r} → {to_status!r}"
        )
        self.strategy_id = strategy_id
        self.from_status = from_status
        self.to_status = to_status


class VectorWriteDisabledError(DomainError):
    """Raised by the publish task when vector writes are disabled in the
    current environment (TAX_STRATEGIES_VECTOR_WRITE_ENABLED=false).

    This is the fixed error code `vector_write_disabled_in_this_environment`
    surfaced in the authoring job row. The strategy stays in `approved`
    status per FR-011.
    """

    code = "vector_write_disabled_in_this_environment"

    def __init__(self, strategy_id: str) -> None:
        super().__init__(
            "Vector writes are disabled in this environment. "
            f"Strategy {strategy_id} remains approved; retry from a "
            "writer-enabled environment."
        )
        self.strategy_id = strategy_id


class DuplicateStrategyIdError(DomainError):
    """Raised when seeding would create a strategy with an existing ID."""

    def __init__(self, strategy_id: str) -> None:
        super().__init__(f"Strategy {strategy_id!r} already exists")
        self.strategy_id = strategy_id


class InvalidCategoryError(DomainError):
    """Raised when a category is not in the fixed taxonomy of 8."""

    def __init__(self, category: str) -> None:
        super().__init__(f"Invalid category {category!r}")
        self.category = category


class SeedValidationError(DomainError):
    """Raised when the seed CSV contains invalid rows; whole run is aborted."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__(f"Seed CSV invalid: {len(errors)} errors")
        self.errors = errors
