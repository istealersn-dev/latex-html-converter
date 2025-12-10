"""
HTML cleaning utilities for LaTeXML output.
"""

import re
from typing import Any

from bs4 import BeautifulSoup, NavigableString
from loguru import logger

try:
    from lxml.html.clean import Cleaner
except ImportError:
    Cleaner = None


def setup_cleaner():
    """Set up HTML cleaner with appropriate settings."""
    if Cleaner is not None:
        # Conservative settings: only remove truly dangerous content
        # DO NOT remove scripts/styles as we need to add MathJax later
        return Cleaner(
            scripts=False,  # Keep scripts - we add MathJax scripts
            javascript=False,  # Keep javascript URLs - needed for MathJax
            comments=True,  # Remove HTML comments
            style=False,  # Keep style tags - needed for math rendering
            links=False,  # Keep links - needed for stylesheets
            meta=False,  # Keep meta tags - needed for charset, viewport
            page_structure=False,  # Keep page structure
            processing_instructions=True,  # Remove XML processing instructions
            embedded=True,  # Remove embedded objects (for security)
            frames=True,  # Remove frames (security risk)
            forms=True,  # Remove forms (not needed for LaTeX output)
            annoying_tags=False,  # Keep tags - some might be needed
            safe_attrs_only=False,  # Keep all attributes for MathML/MathJax
            # Keep unknown tags - might be LaTeXML specific
            remove_unknown_tags=False,
        )
    return None


def clean_html(soup: BeautifulSoup, results: dict[str, Any]) -> BeautifulSoup:
    """Clean HTML content."""
    try:
        # Remove LaTeXML-specific elements
        remove_latexml_elements(soup)

        # Clean dangerous content
        clean_dangerous_content(soup)

        # Remove empty elements
        remove_empty_elements(soup)

        # Normalize whitespace
        normalize_whitespace(soup)

        results["steps_completed"].append("html_cleaning")
        return soup

    except Exception as exc:
        error_msg = f"HTML cleaning failed: {exc}"
        results["errors"].append(error_msg)
        logger.error(error_msg)
        return soup


def remove_latexml_elements(soup: BeautifulSoup) -> None:
    """Remove LaTeXML-specific elements."""
    # Remove LaTeXML processing instructions
    for pi in soup.find_all(
        string=lambda text: isinstance(text, NavigableString)
        and text.strip().startswith("<?")
    ):
        pi.extract()

    # Remove LaTeXML-specific attributes
    for tag in soup.find_all():
        if tag.attrs:
            # Remove LaTeXML-specific attributes
            latexml_attrs = [
                attr for attr in tag.attrs if attr.startswith("latexml")
            ]
            for attr in latexml_attrs:
                del tag.attrs[attr]


def clean_dangerous_content(soup: BeautifulSoup) -> None:
    """Remove potentially dangerous content while preserving safe scripts."""
    # Remove only inline scripts and scripts with suspicious content
    # Preserve scripts from trusted CDNs (MathJax, etc.)
    trusted_script_sources = [
        "cdn.jsdelivr.net",
        "cdnjs.cloudflare.com",
        "polyfill.io",
        "mathjax",
    ]

    for script in soup.find_all("script"):
        # Check if script has a src attribute
        src = script.get("src", "")
        script_content = script.string or ""

        # Remove if:
        # 1. Inline script with content (no src)
        # 2. External script from untrusted source
        # 3. Script contains suspicious patterns
        is_trusted = any(domain in src.lower() for domain in trusted_script_sources)
        has_inline_content = not src and script_content.strip()
        has_suspicious_content = any(
            pattern in script_content.lower()
            for pattern in ["eval(", "document.write", "innerHTML", "fromCharCode"]
        )

        if has_inline_content or (src and not is_trusted) or has_suspicious_content:
            logger.debug(
                f"Removing potentially dangerous script: {src or 'inline'}"
            )
            script.decompose()

    # Remove style tags with potentially dangerous content
    for style in soup.find_all("style"):
        style_content = str(style.string or "")
        if (
            "javascript:" in style_content.lower()
            or "expression(" in style_content.lower()
        ):
            logger.debug("Removing style tag with dangerous content")
            style.decompose()

    # Remove onclick and similar event handlers
    for tag in soup.find_all():
        if tag.attrs:
            dangerous_attrs = [
                "onclick",
                "onload",
                "onerror",
                "onmouseover",
                "onfocus",
                "onblur",
            ]
            for attr in dangerous_attrs:
                if attr in tag.attrs:
                    del tag.attrs[attr]


def remove_empty_elements(soup: BeautifulSoup) -> None:
    """Remove empty elements that don't add value."""
    empty_tags = ["span", "div", "p"]

    for tag_name in empty_tags:
        for tag in soup.find_all(tag_name):
            if not tag.get_text(strip=True) and not tag.find_all():
                tag.decompose()


def normalize_whitespace(soup: BeautifulSoup) -> None:
    """Normalize whitespace in text content while preserving
    meaningful formatting."""
    for text_node in soup.find_all(string=True):
        if isinstance(text_node, NavigableString):
            # Skip whitespace normalization in contexts where it's significant
            parent = text_node.parent
            if parent and parent.name in [
                "pre",
                "code",
                "textarea",
                "script",
                "style",
            ]:
                continue

            # Skip if this is whitespace between inline elements
            # (preserves word separation)
            if (
                text_node.strip() == ""
                and parent
                and parent.name in ["p", "div", "span", "em", "strong", "a"]
            ):
                # Only collapse multiple spaces/tabs to single space, don't strip
                normalized = re.sub(r"[ \t]+", " ", text_node)
                if normalized != text_node:
                    text_node.replace_with(normalized)
                continue

            # For other text nodes, normalize but preserve word boundaries
            if text_node.strip():  # Only process non-empty text nodes
                # Collapse multiple whitespace to single space,
                # but preserve leading/trailing if meaningful
                normalized = re.sub(r"[ \t\n\r]+", " ", text_node)
                # Only strip if the original was mostly whitespace
                if (
                    len(text_node.strip()) / len(text_node) < 0.3
                ):  # Less than 30% actual content
                    normalized = normalized.strip()
                text_node.replace_with(normalized)
