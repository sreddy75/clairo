"""AI Usage Logging for Cost Tracking and Analytics.

This module provides lightweight AI usage logging before the full
observability spec is implemented. Logs are written to structured
logs and can be aggregated for cost analysis.

Usage:
    from app.core.ai_usage import log_ai_usage, AIUsageContext

    # Log an AI call
    await log_ai_usage(
        context=AIUsageContext(
            tenant_id=tenant_id,
            user_id=user_id,
            action_type="chat",
            client_id=client_id,
        ),
        model="claude-sonnet-4-20250514",
        input_tokens=1500,
        output_tokens=800,
        latency_ms=2400,
    )
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID

from app.core.logging import get_logger

logger = get_logger(__name__)


# Claude pricing as of Jan 2026 (per million tokens)
# https://www.anthropic.com/pricing
CLAUDE_PRICING = {
    # Claude 4 models
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-opus-4-20250514": {"input": 15.00, "output": 75.00},
    # Claude 3.5 models
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
    # Claude 3 models (legacy)
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
    "claude-3-sonnet-20240229": {"input": 3.00, "output": 15.00},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
}

# Default to Sonnet pricing for unknown models
DEFAULT_PRICING = {"input": 3.00, "output": 15.00}


ActionType = Literal[
    "chat",  # Client-context chat
    "insight",  # Insight generation
    "magic_zone",  # Magic Zone multi-agent
    "knowledge",  # Knowledge base RAG
    "trigger",  # Trigger evaluation
    "analyzer",  # AI analyzer
]


@dataclass
class AIUsageContext:
    """Context for an AI usage event."""

    tenant_id: UUID
    action_type: ActionType
    user_id: UUID | None = None
    client_id: UUID | None = None
    session_id: UUID | None = None
    metadata: dict = field(default_factory=dict)


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate the cost of an AI call in USD.

    Args:
        model: The model identifier (e.g., "claude-sonnet-4-20250514")
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Cost in USD (e.g., 0.012 for 1.2 cents)
    """
    pricing = CLAUDE_PRICING.get(model, DEFAULT_PRICING)

    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]

    return round(input_cost + output_cost, 6)


async def log_ai_usage(
    context: AIUsageContext,
    model: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
    success: bool = True,
    error: str | None = None,
) -> None:
    """Log an AI usage event for cost tracking and analytics.

    This is a lightweight logging function that writes to structured logs.
    The full observability spec will add database persistence and dashboards.

    Args:
        context: The usage context (tenant, user, action type, etc.)
        model: The AI model used
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        latency_ms: Request latency in milliseconds
        success: Whether the request succeeded
        error: Error message if failed
    """
    cost_usd = calculate_cost(model, input_tokens, output_tokens)
    total_tokens = input_tokens + output_tokens

    log_data = {
        # Context
        "tenant_id": str(context.tenant_id),
        "user_id": str(context.user_id) if context.user_id else None,
        "client_id": str(context.client_id) if context.client_id else None,
        "session_id": str(context.session_id) if context.session_id else None,
        "action_type": context.action_type,
        # Model details
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        # Cost
        "cost_usd": cost_usd,
        # Performance
        "latency_ms": latency_ms,
        "tokens_per_second": round(output_tokens / (latency_ms / 1000), 2) if latency_ms > 0 else 0,
        # Status
        "success": success,
        "error": error,
        # Timestamp
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Add any additional metadata
    if context.metadata:
        log_data["metadata"] = context.metadata

    # Log with structured data for aggregation
    if success:
        logger.info(
            "AI usage logged",
            event_type="ai_usage",
            **log_data,
        )
    else:
        logger.warning(
            "AI usage logged (failed)",
            event_type="ai_usage",
            **log_data,
        )


class AIUsageTracker:
    """Context manager for tracking AI usage with automatic logging.

    Usage:
        async with AIUsageTracker(context, model="claude-sonnet-4-20250514") as tracker:
            response = await anthropic.messages.create(...)
            tracker.set_tokens(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )
    """

    def __init__(
        self,
        context: AIUsageContext,
        model: str,
    ):
        self.context = context
        self.model = model
        self.input_tokens = 0
        self.output_tokens = 0
        self.start_time: float | None = None
        self.success = True
        self.error: str | None = None

    def set_tokens(self, input_tokens: int, output_tokens: int) -> None:
        """Set the token counts after the API call."""
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens

    def set_error(self, error: str) -> None:
        """Mark the request as failed with an error."""
        self.success = False
        self.error = error

    async def __aenter__(self) -> "AIUsageTracker":
        import time

        self.start_time = time.time()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        import time

        if self.start_time is None:
            return

        latency_ms = int((time.time() - self.start_time) * 1000)

        # If an exception occurred, mark as failed
        if exc_type is not None:
            self.success = False
            self.error = str(exc_val) if exc_val else str(exc_type)

        # Log the usage
        await log_ai_usage(
            context=self.context,
            model=self.model,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            latency_ms=latency_ms,
            success=self.success,
            error=self.error,
        )
