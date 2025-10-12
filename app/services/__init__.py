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

from .latexml import (
    LaTeXMLService,
    LaTeXMLError,
    LaTeXMLTimeoutError,
    LaTeXMLFileError,
    LaTeXMLConversionError,
    LaTeXMLSecurityError,
)

from .html_post import (
    HTMLPostProcessor,
    HTMLPostProcessingError,
    HTMLValidationError,
    HTMLCleaningError,
)

__all__ = [
    # Tectonic services
    "TectonicService",
    "TectonicCompilationError",
    "TectonicTimeoutError",
    "TectonicFileError",
    "TectonicSecurityError",
    # LaTeXML services
    "LaTeXMLService",
    "LaTeXMLError",
    "LaTeXMLTimeoutError",
    "LaTeXMLFileError",
    "LaTeXMLConversionError",
    "LaTeXMLSecurityError",
    # HTML post-processing services
    "HTMLPostProcessor",
    "HTMLPostProcessingError",
    "HTMLValidationError",
    "HTMLCleaningError",
]
