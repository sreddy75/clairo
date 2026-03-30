"""Domain exceptions for the Tax Planning module."""

from uuid import UUID

from app.core.exceptions import (
    ConflictError,
    DomainError,
    ExternalServiceError,
    NotFoundError,
    ValidationError,
)


class TaxPlanNotFoundError(NotFoundError):
    """Raised when a tax plan does not exist."""

    def __init__(self, plan_id: UUID | str) -> None:
        super().__init__("TaxPlan", str(plan_id))


class TaxPlanExistsError(ConflictError):
    """Raised when a plan already exists for the same client+FY."""

    def __init__(self, existing_plan_id: UUID | str) -> None:
        super().__init__(
            message="Tax plan already exists for this client and financial year",
            resource_type="TaxPlan",
            conflict_field="xpm_client_id+financial_year",
        )
        self.details["existing_plan_id"] = str(existing_plan_id)


class TaxScenarioNotFoundError(NotFoundError):
    """Raised when a tax scenario does not exist."""

    def __init__(self, scenario_id: UUID | str) -> None:
        super().__init__("TaxScenario", str(scenario_id))


class InvalidEntityTypeError(ValidationError):
    """Raised when an unsupported entity type is provided."""

    def __init__(self, entity_type: str) -> None:
        super().__init__(
            message=f"Invalid entity type: {entity_type}",
            field="entity_type",
        )


class NoXeroConnectionError(ValidationError):
    """Raised when Xero data is requested but client has no connection."""

    def __init__(self) -> None:
        super().__init__(
            message="Client has no connected Xero organisation",
            field="xero_connection_id",
        )


class TaxRateConfigNotFoundError(NotFoundError):
    """Raised when tax rate config is missing for a financial year."""

    def __init__(self, financial_year: str, rate_type: str | None = None) -> None:
        detail = f"financial year {financial_year}"
        if rate_type:
            detail += f", rate type {rate_type}"
        super().__init__("TaxRateConfig", detail)


class XeroPullError(ExternalServiceError):
    """Raised when pulling data from Xero fails."""

    def __init__(self, original_error: str | None = None) -> None:
        super().__init__(
            service="Xero",
            message="Failed to fetch data from Xero",
            original_error=original_error,
        )


class TaxPlanExportError(DomainError):
    """Raised when a tax plan cannot be exported."""

    def __init__(self, message: str = "Tax plan has no calculated tax position") -> None:
        super().__init__(
            message=message,
            code="TAX_PLAN_EXPORT_ERROR",
            status_code=400,
        )
