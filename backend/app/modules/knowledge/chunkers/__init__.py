"""Structure-aware chunkers for legal content.

Registry maps content types to appropriate chunker implementations.

Importing this package automatically registers all built-in chunkers:
- ``"legislation"`` -- :class:`LegislationChunker`
- ``"ruling"`` -- :class:`RulingChunker`
- ``"case_law"`` -- :class:`CaseLawChunker`
"""

from app.modules.knowledge.chunkers.base import BaseStructuredChunker, ChunkResult

__all__ = ["BaseStructuredChunker", "ChunkResult", "get_chunker"]

# Chunker registry - populated by imports
_CHUNKER_REGISTRY: dict[str, type["BaseStructuredChunker"]] = {}


def register_chunker(content_type: str, chunker_class: type["BaseStructuredChunker"]) -> None:
    """Register a chunker for a content type."""
    _CHUNKER_REGISTRY[content_type] = chunker_class


def get_chunker(content_type: str) -> "BaseStructuredChunker | None":
    """Get a chunker instance for a content type."""
    chunker_class = _CHUNKER_REGISTRY.get(content_type)
    if chunker_class:
        return chunker_class()
    return None


# Import chunker modules to trigger their self-registration.
# Each module calls register_chunker() at module level.
import app.modules.knowledge.chunkers.case_law as _case_law_chunker  # noqa: E402, F401
import app.modules.knowledge.chunkers.legislation as _legislation_chunker  # noqa: E402, F401
import app.modules.knowledge.chunkers.ruling as _ruling_chunker  # noqa: E402, F401
