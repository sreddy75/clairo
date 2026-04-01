"""Re-export from shared core module for backwards compatibility."""

from app.core.file_processor import (  # noqa: F401
    ProcessedFile,
    build_content_blocks_from_metadata,
    process_chat_attachment,
)

__all__ = ["ProcessedFile", "build_content_blocks_from_metadata", "process_chat_attachment"]
