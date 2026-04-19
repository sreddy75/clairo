"""Environment gate for tax-strategies vector-store writes (Spec 060 R1).

The Pinecone `tax_strategies` namespace is shared across all environments.
Vector writes must only happen in the single designated source-of-truth
environment (production). This module centralises the check so the publish
Celery task can fail loudly rather than silently writing from dev/staging.
"""

from __future__ import annotations

from app.config import get_settings


def vector_writes_enabled() -> bool:
    """Return True when the current environment is authorised to write to
    the shared tax_strategies vector namespace.

    Gated on settings.tax_strategies.vector_write_enabled, which maps to the
    env var TAX_STRATEGIES_VECTOR_WRITE_ENABLED (default False).
    """
    settings = get_settings()
    return settings.tax_strategies.vector_write_enabled
