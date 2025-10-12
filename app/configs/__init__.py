"""
Configuration package for LaTeX to HTML5 converter.

This package contains configuration modules for different services
and components of the application.
"""

from .latexml import LaTeXMLConversionOptions, LaTeXMLSettings

__all__ = [
    "LaTeXMLSettings",
    "LaTeXMLConversionOptions",
]
