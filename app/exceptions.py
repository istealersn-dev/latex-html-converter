"""
Base exception classes for the LaTeX to HTML5 Converter.

This module provides common exception patterns to reduce duplication
across different service modules.
"""

from typing import Any


class BaseServiceError(Exception):
    """Base exception for all service errors."""

    def __init__(self, message: str, error_type: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.error_type = error_type
        self.details = details or {}


class ServiceTimeoutError(BaseServiceError):
    """Raised when service operations timeout."""

    def __init__(self, timeout_seconds: int):
        super().__init__(
            f"Service operation timed out after {timeout_seconds} seconds",
            "TIMEOUT_ERROR",
            {"timeout_seconds": timeout_seconds}
        )


class ServiceFileError(BaseServiceError):
    """Raised when there are file-related errors."""

    def __init__(self, message: str, file_path: str):
        super().__init__(message, "FILE_ERROR", {"file_path": file_path})


class ServiceSecurityError(BaseServiceError):
    """Raised when security validation fails."""

    def __init__(self, message: str, violation: str):
        super().__init__(message, "SECURITY_ERROR", {"violation": violation})


class ServiceConversionError(BaseServiceError):
    """Raised when conversion operations fail."""

    def __init__(self, message: str, error_type: str = "CONVERSION_ERROR", details: dict[str, Any] | None = None):
        super().__init__(message, error_type, details)


# Common error types for consistency
class ErrorTypes:
    """Common error type constants."""

    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    FILE_ERROR = "FILE_ERROR"
    SECURITY_ERROR = "SECURITY_ERROR"
    CONVERSION_ERROR = "CONVERSION_ERROR"
    FATAL_ERROR = "FATAL_ERROR"
    UNDEFINED_CONTROL = "UNDEFINED_CONTROL"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    INVALID_EXTENSION = "INVALID_EXTENSION"
    DANGEROUS_FILENAME = "DANGEROUS_FILENAME"
    FILE_SIZE_EXCEEDED = "FILE_SIZE_EXCEEDED"
