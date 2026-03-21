"""Structured logging configuration using structlog.

Provides consistent, structured logging across the application with:
- JSON output for production (machine-readable)
- Console output for development (human-readable)
- Automatic sensitive data masking
- Request context injection

Usage:
    from app.core.logging import get_logger

    logger = get_logger(__name__)
    logger.info("Processing request", user_id=user.id, action="create")
"""

import logging
import re
import sys
from typing import Any

import structlog

from app.config import get_settings

# Patterns for sensitive data that should be masked
SENSITIVE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("password", re.compile(r"password", re.IGNORECASE)),
    ("secret", re.compile(r"secret", re.IGNORECASE)),
    ("token", re.compile(r"token", re.IGNORECASE)),
    ("api_key", re.compile(r"api[_-]?key", re.IGNORECASE)),
    ("authorization", re.compile(r"authorization", re.IGNORECASE)),
    ("bearer", re.compile(r"bearer\s+\S+", re.IGNORECASE)),
    ("credit_card", re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b")),
]

MASK_VALUE = "***REDACTED***"


def mask_sensitive(_logger: Any, _method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Processor to mask sensitive data in log entries.

    Masks values for keys that match sensitive patterns (password, secret, etc.)
    and values that look like credit card numbers.
    """

    def should_mask_key(key: str) -> bool:
        """Check if a key name indicates sensitive data."""
        key_lower = key.lower()
        return any(
            pattern.search(key_lower)
            for name, pattern in SENSITIVE_PATTERNS
            if name in ("password", "secret", "token", "api_key", "authorization")
        )

    def mask_value(value: Any) -> Any:
        """Mask a value if it contains sensitive patterns."""
        if not isinstance(value, str):
            return value

        # Check for bearer tokens and credit cards in the value itself
        for name, pattern in SENSITIVE_PATTERNS:
            if name in ("bearer", "credit_card") and pattern.search(value):
                return MASK_VALUE

        return value

    def process_dict(d: dict[str, Any]) -> dict[str, Any]:
        """Recursively process a dictionary, masking sensitive values."""
        result: dict[str, Any] = {}
        for key, value in d.items():
            if should_mask_key(key):
                result[key] = MASK_VALUE
            elif isinstance(value, dict):
                result[key] = process_dict(value)
            elif isinstance(value, list):
                result[key] = [
                    process_dict(item) if isinstance(item, dict) else mask_value(item)
                    for item in value
                ]
            else:
                result[key] = mask_value(value)
        return result

    return process_dict(event_dict)


def add_app_context(_logger: Any, _method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Add application context to log entries."""
    settings = get_settings()
    event_dict["app"] = settings.app_name
    event_dict["environment"] = settings.environment
    return event_dict


def setup_logging() -> None:
    """Configure structured logging for the application.

    Should be called once during application startup.
    Configures both structlog and the standard library logging.
    """
    settings = get_settings()

    # Determine log level
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Common processors for all environments
    shared_processors: list[Any] = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.contextvars.merge_contextvars,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        add_app_context,
        mask_sensitive,
    ]

    if settings.log_format == "json":
        # Production: JSON output
        processors = [
            *shared_processors,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: Console output with colors
        processors = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Set levels for noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.DEBUG if settings.database.echo else logging.WARNING
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name (typically __name__ of the calling module).

    Returns:
        A configured structlog logger.

    Usage:
        logger = get_logger(__name__)
        logger.info("User logged in", user_id=user.id)
        logger.warning("Rate limit approaching", requests=98, limit=100)
        logger.error("Database connection failed", error=str(e))
    """
    return structlog.stdlib.get_logger(name)


def bind_context(**kwargs: Any) -> None:
    """Bind context variables to all subsequent log entries in this context.

    Useful for adding request-scoped context like request_id, user_id, etc.

    Args:
        **kwargs: Key-value pairs to add to log context.

    Usage:
        bind_context(request_id=request_id, user_id=current_user.id)
        logger.info("Processing request")  # Will include request_id and user_id
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """Clear all bound context variables.

    Should be called at the end of a request to prevent context leaking.
    """
    structlog.contextvars.clear_contextvars()
