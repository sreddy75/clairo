"""Exceptions for the agents module."""

from app.core.exceptions import DomainError


class AgentError(DomainError):
    """Base exception for agent-related errors."""

    pass


class PerspectiveDetectionError(AgentError):
    """Error detecting perspectives for a query."""

    def __init__(self, query: str, reason: str):
        self.query = query
        self.reason = reason
        super().__init__(f"Failed to detect perspectives for query: {reason}")


class ContextBuildError(AgentError):
    """Error building context for perspectives."""

    def __init__(self, perspective: str, reason: str):
        self.perspective = perspective
        self.reason = reason
        super().__init__(f"Failed to build context for {perspective}: {reason}")


class OrchestratorError(AgentError):
    """Error in the orchestrator processing."""

    def __init__(self, reason: str, correlation_id: str | None = None):
        self.reason = reason
        self.correlation_id = correlation_id
        super().__init__(f"Orchestrator error: {reason}")


class ResponseParseError(AgentError):
    """Error parsing LLM response into perspectives."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Failed to parse response: {reason}")


class EscalationRequiredError(AgentError):
    """Query requires human escalation due to low confidence or complexity."""

    def __init__(self, reason: str, confidence: float, correlation_id: str):
        self.reason = reason
        self.confidence = confidence
        self.correlation_id = correlation_id
        super().__init__(f"Escalation required: {reason} (confidence: {confidence:.2f})")
