"""
HTML post-processing exceptions.
"""

from typing import Any


class HTMLPostProcessingError(Exception):
    """Base exception for HTML post-processing errors."""

    def __init__(
        self,
        message: str,
        error_type: str = "HTML_PROCESSING_ERROR",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.error_type = error_type
        self.details = details or {}


class HTMLValidationError(HTMLPostProcessingError):
    """Raised when HTML validation fails."""

    def __init__(self, message: str, validation_errors: list[str]):
        super().__init__(
            message, "VALIDATION_ERROR", {"validation_errors": validation_errors}
        )


class HTMLCleaningError(HTMLPostProcessingError):
    """Raised when HTML cleaning fails."""

    def __init__(self, message: str, cleaning_errors: list[str]):
        super().__init__(
            message, "CLEANING_ERROR", {"cleaning_errors": cleaning_errors}
        )
