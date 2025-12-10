"""
HTML validation utilities for LaTeXML output.
"""

from typing import Any

from bs4 import BeautifulSoup
from loguru import logger


def validate_html_structure(
    soup: BeautifulSoup, results: dict[str, Any]
) -> None:
    """Validate HTML structure."""
    try:
        validation_errors = []

        # Check for required elements
        if not soup.find("html"):
            validation_errors.append("Missing <html> element")

        if not soup.find("head"):
            validation_errors.append("Missing <head> element")

        if not soup.find("body"):
            validation_errors.append("Missing <body> element")

        # Check for proper nesting
        validate_nesting(soup, validation_errors)

        # Check for accessibility issues
        validate_accessibility(soup, validation_errors)

        if validation_errors:
            results["warnings"].extend(validation_errors)
        else:
            results["steps_completed"].append("html_validation")

    except Exception as exc:
        error_msg = f"HTML validation failed: {exc}"
        results["errors"].append(error_msg)


def validate_nesting(soup: BeautifulSoup, errors: list[str]) -> None:
    """Validate proper HTML nesting."""
    # Check for invalid nesting (e.g., <p> inside <p>)
    for p_tag in soup.find_all("p"):
        if p_tag.find("p"):
            errors.append("Invalid nesting: <p> inside <p>")


def validate_accessibility(soup: BeautifulSoup, errors: list[str]) -> None:
    """Validate accessibility features."""
    # Check for images without alt text
    for img in soup.find_all("img"):
        if not img.get("alt"):
            errors.append(f"Image missing alt text: {img.get('src', 'unknown')}")

    # Check for headings structure
    headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
    if headings:
        # Check for proper heading hierarchy
        prev_level = 0
        for heading in headings:
            level = int(heading.name[1])
            if level > prev_level + 1:
                errors.append(
                    f"Invalid heading hierarchy: {heading.name} after h{prev_level}"
                )
            prev_level = level
