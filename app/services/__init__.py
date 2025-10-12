"""
Services package for the LaTeX → HTML5 Converter.

This package contains service modules for external tool integration.
"""

from .html_post import (
    HTMLCleaningError,
    HTMLPostProcessingError,
    HTMLPostProcessor,
    HTMLValidationError,
)
from .latexml import (
    LaTeXMLConversionError,
    LaTeXMLError,
    LaTeXMLFileError,
    LaTeXMLSecurityError,
    LaTeXMLService,
    LaTeXMLTimeoutError,
)
from .orchestrator import (
    ConversionOrchestrator,
    JobNotFoundError,
    OrchestrationError,
    ResourceLimitError,
    get_orchestrator,
    shutdown_orchestrator,
)
from .pipeline import (
    ConversionPipeline,
    ConversionPipelineError,
    PipelineResourceError,
    PipelineTimeoutError,
)
from .tectonic import (
    TectonicCompilationError,
    TectonicFileError,
    TectonicSecurityError,
    TectonicService,
    TectonicTimeoutError,
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
