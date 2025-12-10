"""
HTML optimization utilities for LaTeXML output.
"""

from typing import Any

from bs4 import BeautifulSoup, NavigableString
from loguru import logger


def optimize_html(
    soup: BeautifulSoup, results: dict[str, Any]
) -> BeautifulSoup:
    """Optimize HTML for better performance."""
    try:
        # Minify HTML (basic)
        minify_html(soup)

        # Optimize images
        optimize_images(soup)

        # Remove unnecessary attributes
        remove_unnecessary_attributes(soup)

        results["steps_completed"].append("html_optimization")
        return soup

    except Exception as exc:
        error_msg = f"HTML optimization failed: {exc}"
        results["errors"].append(error_msg)
        logger.error(error_msg)
        return soup


def minify_html(soup: BeautifulSoup) -> None:
    """Basic HTML minification."""
    # Remove unnecessary whitespace
    for text_node in soup.find_all(string=True):
        if isinstance(text_node, NavigableString):
            # Remove leading/trailing whitespace
            text_node.replace_with(text_node.strip())


def optimize_images(soup: BeautifulSoup) -> None:
    """Optimize image tags."""
    for img in soup.find_all("img"):
        # Add loading="lazy" for performance
        if not img.get("loading"):
            img["loading"] = "lazy"


def remove_unnecessary_attributes(soup: BeautifulSoup) -> None:
    """Remove unnecessary attributes while preserving namespace declarations."""
    # Only remove LaTeXML-specific attributes, preserve XML namespaces
    latexml_attrs = ["data-latexml"]

    for tag in soup.find_all():
        if tag.attrs:
            # Remove LaTeXML-specific attributes
            for attr in latexml_attrs:
                if attr in tag.attrs:
                    del tag.attrs[attr]

            # Only remove xml:space if it's not in MathML/SVG context
            if (
                "xml:space" in tag.attrs
                and tag.name
                not in [
                    "math",
                    "m:math",
                    "svg",
                    "g",
                    "path",
                    "circle",
                    "rect",
                ]
            ):
                del tag.attrs["xml:space"]
