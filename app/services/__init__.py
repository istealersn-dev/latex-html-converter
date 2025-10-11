"""
Services package for the LaTeX → HTML5 Converter.

This package contains service modules for external tool integration.
"""

from .tectonic import TectonicCompilationError, TectonicService

__all__ = ["TectonicService", "TectonicCompilationError"]
