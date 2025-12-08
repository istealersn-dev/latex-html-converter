"""
Shared validation utilities for the LaTeX to HTML5 Converter.

This module provides common validation functions to avoid duplication
across different configuration and model classes.
"""


class ValidationUtils:
    """Shared validation utilities for common validation patterns."""

    @staticmethod
    def validate_file_size(size: int, max_size: int = 500 * 1024 * 1024) -> int:
        """
        Validate file size with common logic.

        Args:
            size: File size in bytes
            max_size: Maximum allowed file size in bytes

        Returns:
            Validated file size

        Raises:
            ValueError: If file size is invalid
        """
        if size <= 0:
            raise ValueError("File size must be positive")
        if size > max_size:
            raise ValueError(f"File size cannot exceed {max_size} bytes")
        return size

    @staticmethod
    def validate_output_format(format_str: str, allowed_formats: list[str]) -> str:
        """
        Validate output format with common logic.

        Args:
            format_str: Output format string
            allowed_formats: List of allowed formats

        Returns:
            Validated and normalized format string

        Raises:
            ValueError: If format is not allowed
        """
        if format_str.lower() not in allowed_formats:
            raise ValueError(f"Output format must be one of: {allowed_formats}")
        return format_str.lower()

    @staticmethod
    def validate_timeout(timeout: int, max_timeout: int = 3600) -> int:
        """
        Validate timeout value with common logic.

        Args:
            timeout: Timeout in seconds
            max_timeout: Maximum allowed timeout in seconds

        Returns:
            Validated timeout

        Raises:
            ValueError: If timeout is invalid
        """
        if timeout <= 0:
            raise ValueError("Timeout must be positive")
        if timeout > max_timeout:
            raise ValueError(f"Timeout cannot exceed {max_timeout} seconds")
        return timeout

    @staticmethod
    def validate_extensions(extensions: list[str]) -> list[str]:
        """
        Validate file extensions with common logic.

        Args:
            extensions: List of file extensions

        Returns:
            Normalized extensions (ensuring they start with dot)

        Raises:
            ValueError: If extensions are invalid
        """
        if not extensions:
            raise ValueError("At least one extension must be allowed")
        # Ensure extensions start with dot
        return [ext if ext.startswith(".") else f".{ext}" for ext in extensions]

    @staticmethod
    def validate_positive_integer(value: int, field_name: str) -> int:
        """
        Validate positive integer with common logic.

        Args:
            value: Integer value to validate
            field_name: Name of the field for error messages

        Returns:
            Validated integer

        Raises:
            ValueError: If value is not positive
        """
        if value <= 0:
            raise ValueError(f"{field_name} must be positive")
        return value
