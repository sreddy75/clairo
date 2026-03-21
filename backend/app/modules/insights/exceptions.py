"""Custom exceptions for the insights module."""


class InsightError(Exception):
    """Base exception for insight errors."""

    pass


class InsightNotFoundError(InsightError):
    """Raised when an insight is not found."""

    pass


class InsightGenerationError(InsightError):
    """Raised when insight generation fails."""

    pass


class AnalyzerError(InsightError):
    """Raised when an analyzer encounters an error."""

    def __init__(self, analyzer_name: str, message: str):
        self.analyzer_name = analyzer_name
        super().__init__(f"Analyzer '{analyzer_name}' failed: {message}")
