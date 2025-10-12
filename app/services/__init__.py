"""
Services package for the LaTeX → HTML5 Converter.

This package contains service modules for external tool integration.
"""

from .tectonic import (
    TectonicCompilationError,
    TectonicFileError,
    TectonicSecurityError,
    TectonicService,
    TectonicTimeoutError,
)

__all__ = [
    "TectonicService",
    "TectonicCompilationError",
    "TectonicTimeoutError",
    "TectonicFileError",
    "TectonicSecurityError",
]
