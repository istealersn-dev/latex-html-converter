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

from .orchestrator import (
    ConversionOrchestrator,
    OrchestrationError,
    JobNotFoundError,
    ResourceLimitError,
    get_orchestrator,
    shutdown_orchestrator,
)

from .pipeline import (
    ConversionPipeline,
    ConversionPipelineError,
    PipelineTimeoutError,
    PipelineResourceError,
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
    # Orchestrator services
    "ConversionOrchestrator",
    "OrchestrationError",
    "JobNotFoundError",
    "ResourceLimitError",
    "get_orchestrator",
    "shutdown_orchestrator",
    # Pipeline services
    "ConversionPipeline",
    "ConversionPipelineError",
    "PipelineTimeoutError",
    "PipelineResourceError",
]
