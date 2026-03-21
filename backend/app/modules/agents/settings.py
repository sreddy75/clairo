"""Configuration settings for the agents module."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    """Settings for the multi-perspective agent system."""

    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        env_file=".env",
        extra="ignore",
    )

    # LLM Model
    model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Claude model to use for agent responses",
    )

    # Token budgets
    max_context_tokens: int = Field(
        default=12000,
        description="Maximum tokens for context (client data + knowledge base)",
    )
    max_response_tokens: int = Field(
        default=4000,
        description="Maximum tokens for response generation",
    )

    # Confidence thresholds
    confidence_escalation_threshold: float = Field(
        default=0.4,
        description="Confidence below this requires mandatory escalation",
    )
    confidence_review_threshold: float = Field(
        default=0.6,
        description="Confidence below this flags for optional review",
    )

    # Performance
    request_timeout_seconds: float = Field(
        default=30.0,
        description="Timeout for LLM request",
    )

    # Perspective settings
    default_perspectives: list[str] = Field(
        default=["compliance"],
        description="Perspectives to use when no specific match is found",
    )
    max_perspectives: int = Field(
        default=4,
        description="Maximum perspectives to include in a single query",
    )

    # Cost tracking
    cost_warning_threshold: float = Field(
        default=0.20,
        description="Log warning if query cost exceeds this (USD)",
    )

    # Complex scenario keywords that trigger escalation
    escalation_keywords: list[str] = Field(
        default=[
            "trust",
            "international",
            "restructure",
            "penalty",
            "fraud",
            "audit",
            "ato investigation",
            "bankruptcy",
            "liquidation",
        ],
        description="Keywords that trigger automatic escalation",
    )


# Singleton instance
agent_settings = AgentSettings()
