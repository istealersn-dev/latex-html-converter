"""
HTML post-processing service for LaTeXML output.

This module provides HTML post-processing functionality to clean, validate,
and enhance LaTeXML-generated HTML output.
"""

import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup, NavigableString
from loguru import logger

try:
    from lxml import etree, html
    from lxml.etree import XMLSyntaxError
    from lxml.html.clean import Cleaner
except ImportError:
    # Fallback for systems without lxml
    etree = None
    html = None
    Cleaner = None
    XMLSyntaxError = Exception

from app.services.asset_validator import AssetValidator
from app.services.assets import AssetConversionService
from app.services.html_cleaner import clean_html, setup_cleaner
from app.services.html_validator import validate_html_structure
from app.services.html_optimizer import optimize_html
from app.services.html_post_exceptions import (
    HTMLCleaningError,
    HTMLPostProcessingError,
    HTMLValidationError,
)


class HTMLPostProcessor:
    """Service for post-processing LaTeXML HTML output."""

    def __init__(
        self,
        base_url: str | None = None,
        asset_conversion_service: AssetConversionService | None = None,
        asset_validator: AssetValidator | None = None,
    ):
        """
        Initialize HTML post-processor.

        Args:
            base_url: Base URL for resolving relative links
            asset_conversion_service: Service for converting assets to SVG
            asset_validator: Service for validating converted assets
        """
        self.base_url = base_url
        self.asset_conversion_service = asset_conversion_service
        self.asset_validator = asset_validator or AssetValidator()
        self._html_file_path: Path | None = None
        self._output_file_path: Path | None = None
        self._setup_cleaner()

    def _setup_cleaner(self) -> None:
        """Set up HTML cleaner with appropriate settings."""
        self.cleaner = setup_cleaner()

    def process_html(
        self,
        html_file: Path,
        output_file: Path | None = None,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Process HTML file with cleaning, validation, and enhancement.

        Args:
            html_file: Path to input HTML file
            output_file: Path to output file (optional)
            options: Processing options

        Returns:
            Dict with processing results

        Raises:
            HTMLPostProcessingError: If processing fails
        """
        if not html_file.exists():
            raise HTMLPostProcessingError(f"HTML file not found: {html_file}")

        try:
            # Store file paths for path resolution
            self._html_file_path = html_file
            self._output_file_path = output_file

            # Load HTML content
            with open(html_file, encoding="utf-8") as f:
                html_content = f.read()

            # Parse with BeautifulSoup
            soup = BeautifulSoup(html_content, "html.parser")

            # Apply processing steps
            processing_results = {
                "original_size": len(html_content),
                "steps_completed": [],
                "errors": [],
                "warnings": [],
            }

            # Step 1: Clean HTML
            cleaned_soup = self._clean_html(soup, processing_results)

            # Step 2: Validate HTML structure
            validate_html_structure(cleaned_soup, processing_results)

            # Step 3: Convert assets to SVG
            asset_converted_soup = self._convert_assets_to_svg(
                cleaned_soup, html_file.parent, processing_results
            )

            # Step 4: Enhance HTML
            enhanced_soup = self._enhance_html(asset_converted_soup, processing_results)

            # Step 5: Optimize HTML
            optimized_soup = optimize_html(enhanced_soup, processing_results)

            # Generate output
            if output_file:
                self._write_html(optimized_soup, output_file)
                processing_results["output_file"] = str(output_file)

            # Final statistics
            final_html = str(optimized_soup)
            processing_results.update(
                {
                    "final_size": len(final_html),
                    "size_reduction": processing_results["original_size"]
                    - len(final_html),
                    "success": len(processing_results["errors"]) == 0,
                }
            )

            return processing_results

        except Exception as exc:
            logger.error("HTML post-processing failed: %s", exc)
            raise HTMLPostProcessingError(
                f"HTML post-processing failed: {exc}"
            ) from exc

    def _clean_html(
        self, soup: BeautifulSoup, results: dict[str, Any]
    ) -> BeautifulSoup:
        """Clean HTML content."""
        return clean_html(soup, results)


    def _enhance_html(
        self, soup: BeautifulSoup, results: dict[str, Any]
    ) -> BeautifulSoup:
        """Enhance HTML with additional features."""
        try:
            # Fix LaTeXML artifacts from missing custom class
            self._fix_latexml_artifacts(soup)

            # Fix image paths to point to correct location
            self._fix_image_paths(soup)

            # Process mathematical expressions for MathJax compatibility
            self._process_math_expressions(soup)

            # Add MathJax support if math is present
            if soup.find(["math", "m:math"]) or soup.find_all(
                ["span", "div"], class_=["math", "math-display"]
            ):
                self._add_mathjax_support(soup)

            # Enhance links
            self._enhance_links(soup)

            # Add responsive meta tag
            self._add_responsive_meta(soup)

            # Add CSS for better styling
            self._add_enhancement_css(soup)

            results["steps_completed"].append("html_enhancement")
            return soup

        except Exception as exc:
            error_msg = f"HTML enhancement failed: {exc}"
            results["errors"].append(error_msg)
            logger.error(error_msg)
            return soup

    def _fix_latexml_artifacts(self, soup: BeautifulSoup) -> None:
        """Fix artifacts from LaTeXML processing custom classes
        without proper bindings."""

        # Fix 1: Remove '12pt', '0pt', '11pt' etc. from beginning of headings and titles
        # These come from \fontsize commands that LaTeXML doesn't process properly
        for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            if heading.string:
                # Remove leading font size declarations
                cleaned_text = re.sub(r"^\d+pt\s*", "", heading.string)
                if cleaned_text != heading.string:
                    heading.string.replace_with(cleaned_text)
                    logger.debug(f"Cleaned heading: {heading.string} -> {cleaned_text}")
            else:
                # Handle headings with child elements
                for text_node in heading.find_all(string=True, recursive=False):
                    if isinstance(text_node, NavigableString):
                        cleaned_text = re.sub(r"^\d+pt\s*", "", str(text_node))
                        if cleaned_text != str(text_node):
                            text_node.replace_with(cleaned_text)
                            logger.debug(
                                f"Cleaned heading text: {text_node} -> {cleaned_text}"
                            )

        # Fix 2: Unwrap excessive bold formatting
        # (ltx_text ltx_font_bold wrapping entire paragraphs)
        # LaTeXML sometimes wraps entire sections in bold
        # when it should only be headings
        for p in soup.find_all("p"):
            # Find all bold spans that are direct children of the paragraph
            bold_spans = p.find_all(
                "span", class_="ltx_text ltx_font_bold", recursive=False
            )

            # Strategy 1: Single bold span wrapping entire paragraph
            if len(bold_spans) == 1:
                span = bold_spans[0]
                if len(list(p.children)) == 1 and span.get_text(
                    strip=True
                ) == p.get_text(strip=True):
                    # This is likely incorrect - unwrap it
                    span["class"] = [
                        c for c in span.get("class", []) if c not in ["ltx_font_bold"]
                    ]
                    if not span.get("class"):
                        span.unwrap()
                    logger.debug("Unwrapped paragraph-level bold formatting")

            # Strategy 2: Multiple bold spans covering most of paragraph
            # (likely incorrect)
            elif len(bold_spans) > 0:
                # Calculate what percentage of paragraph is bold
                total_text = p.get_text(strip=True)
                bold_text = "".join(span.get_text(strip=True) for span in bold_spans)

                # If more than 80% of paragraph is bold, it's likely a formatting error
                if len(total_text) > 0 and len(bold_text) / len(total_text) > 0.8:
                    for span in bold_spans:
                        # Check if this span has citations or other important elements
                        if not span.find(["cite", "a", "em", "strong"]):
                            span["class"] = [
                                c
                                for c in span.get("class", [])
                                if c not in ["ltx_font_bold"]
                            ]
                            if not span.get("class"):
                                span.unwrap()
                    percentage = len(bold_text) / len(total_text) * 100
                    logger.debug(
                        f"Unwrapped excessive bold formatting "
                        f"covering {percentage:.0f}% of paragraph"
                    )

        # Fix 3: Remove LaTeXML error/warning messages from HTML
        # Remove yellow "Unknown environment" warnings and other LaTeXML artifacts
        self._remove_latexml_warnings(soup)

        # Fix 4: Remove bold formatting from inside citations
        # Citations should not have bold formatting
        for cite in soup.find_all("cite"):
            # Remove all bold spans inside citations
            for bold_span in cite.find_all("span", class_="ltx_font_bold"):
                bold_span.unwrap()
                logger.debug("Removed bold formatting from citation")

        # Fix 5: Fix misplaced citation tags that wrap too much content
        # LaTeXML sometimes puts the entire text in <cite> instead of just the citation
        for cite in soup.find_all("cite"):
            # Check if cite contains too much text (likely incorrect)
            cite_text = cite.get_text(strip=True)
            # Citations should be relatively short (author + year, typically < 50 chars)
            if len(cite_text) > 100:
                # This is likely wrapping too much - try to extract just the citation
                # Look for patterns like "(Author, YYYY)" or "Author et al., YYYY"
                citation_match = re.search(
                    r"\([^()]{0,50}?,\s*\d{4}[a-z]?\)", cite_text
                )
                if citation_match:
                    # Found a likely citation - keep only that part in cite
                    citation_str = citation_match.group()
                    # Split content: before citation, citation, after citation
                    before = cite_text[: citation_match.start()]
                    after = cite_text[citation_match.end() :]

                    # Create new structure
                    parent = cite.parent
                    if parent:
                        # Insert before text
                        if before.strip():
                            parent.insert(parent.index(cite), before)
                        # Update cite to contain only the citation
                        cite.clear()
                        cite.string = citation_str
                        # Insert after text
                        if after.strip():
                            parent.insert(parent.index(cite) + 1, after)
                        logger.debug(
                            f"Fixed oversized citation tag: {cite_text[:50]}..."
                        )
                else:
                    # No clear citation pattern - unwrap the cite tag entirely
                    logger.debug(f"Unwrapping malformed cite tag: {cite_text[:50]}...")
                    cite.unwrap()

        # Fix 6: Ensure citations include Author + Year together
        # Citations should be "Author, (Year)" not just "(Year)"
        self._fix_citation_format(soup)

        # Fix 7: Ensure equations stay in single rows (1x1 table maximum)
        # Equations should not be split across multiple table rows
        self._fix_equation_tables(soup)

    def _fix_citation_format(self, soup: BeautifulSoup) -> None:
        """
        Fix citation format to ensure Author + Year are together.

        LaTeXML sometimes splits citations or only links the year.
        This method ensures citations are in the format "Author, (Year)"
        with the ENTIRE citation wrapped in a single link (not just the year).

        Handles multiple patterns:
        - "Author, ( ) <a>Year</a>" -> "<a>Author, (Year)</a>"
        - "Author, (Year)" with only year linked -> "<a>Author, (Year)</a>"
        - "(Year)" with author in previous text -> "<a>Author, (Year)</a>"
        - Multiple text nodes in citation -> merged into single link

        Original structure: "Author, ( ) <a>Year</a>" or
        "Author, (Year)" with only year linked
        Desired structure: "<a>Author, (Year)</a>" - entire citation linked
        """
        # Process all cite elements, including those without class
        for cite in soup.find_all("cite"):
            cite_text = cite.get_text(strip=True)

            # Check if citation structure has author and year separated
            # Pattern 1: Citation has "Author, ( )" with year in a separate link
            # Goal: Wrap the ENTIRE "Author, (Year)" in a single link
            year_link = cite.find("a", class_="ltx_ref")
            if year_link:
                year_text = year_link.get_text(strip=True)
                # Check if year is a 4-digit year or contains year pattern
                year_match = re.search(r"(\d{4}[a-z]?)", year_text)
                if year_match:
                    year = year_match.group(1)

                    # Get all text in cite before the link
                    before_link_parts = []
                    for elem in cite.children:
                        if elem == year_link:
                            break
                        if isinstance(elem, NavigableString):
                            before_link_parts.append(str(elem).strip())
                        elif hasattr(elem, "get_text"):
                            before_link_parts.append(elem.get_text(strip=True))

                    before_text = " ".join(
                        before_link_parts
                    ).strip()  # Normalize whitespace
                    # Normalize whitespace: collapse multiple spaces/newlines
                    before_text = re.sub(r"\s+", " ", before_text)
                    # Also check the full cite text for author pattern
                    full_cite_text = cite.get_text(strip=True)
                    full_cite_text = re.sub(
                        r"\s+", " ", full_cite_text
                    )  # Normalize whitespace

                    # Check if we have author before the year link
                    # Pattern: "Author," or "Author et al.,"
                    # possibly followed by "(" or "( )"
                    # Try multiple patterns to catch different text node structures
                    author_match = None

                    # Pattern 1: "Author, ( )" or "Author, (" in before_text
                    # (handle whitespace variations)
                    # Match "Author, ( )" or "Author, (" with any whitespace
                    author_match = re.search(
                        r"([A-Z][a-zA-Z\s]+(?:et\s+al\.)?)\s*,\s*\(\s*\)?\s*$",
                        before_text,
                    )

                    # Pattern 2: Check full citation text for "Author, ( ) Year" pattern
                    if not author_match:
                        full_match = re.search(
                            r"([A-Z][a-zA-Z\s]+(?:et\s+al\.)?)\s*,\s*\(\s*\)",
                            full_cite_text,
                        )
                        if full_match:
                            author_match = full_match

                    # Pattern 3: Just "Author," at the start (most permissive)
                    if not author_match:
                        # Look for any author name pattern followed by comma
                        simple_match = re.search(
                            r"([A-Z][a-zA-Z\s]+(?:et\s+al\.)?)\s*,", before_text
                        )
                        if simple_match:
                            author_match = simple_match

                    # Pattern 4: Check if full citation has
                    # "Author, ( )" pattern anywhere
                    if not author_match:
                        anywhere_match = re.search(
                            r"([A-Z][a-zA-Z\s]+(?:et\s+al\.)?)\s*,\s*\(\s*\)",
                            full_cite_text,
                        )
                        if anywhere_match:
                            author_match = anywhere_match

                    if author_match:
                        author = author_match.group(1).strip()

                        # Reconstruct citation properly: "Author, (Year)"
                        # Wrap the ENTIRE citation in a single link
                        # (not just the year)
                        # This ensures the full "Author, (Year)" is
                        # cited/linked together
                        cite.clear()

                        # Create a new link that wraps the entire citation
                        # Use the year link's href as the base
                        full_citation_link = soup.new_tag(
                            "a",
                            attrs={
                                "class": "ltx_ref",
                                "href": year_link.get("href", ""),
                                "title": year_link.get("title", ""),
                            },
                        )
                        full_citation_link.string = f"{author}, ({year})"

                        cite.append(full_citation_link)
                        logger.debug(
                            f"Fixed citation format: '{cite_text}' -> "
                            f"'{author}, ({year})' (entire citation linked)"
                        )

            # Pattern 2: Citation only has year in parentheses (missing author)
            year_only_pattern = re.compile(r"^\s*\(\s*(\d{4}[a-z]?)\s*\)\s*$")
            if year_only_pattern.match(cite_text):
                # This citation only has the year, need to find the author
                # Look for author name before the citation in parent
                # or previous siblings
                parent = cite.parent
                if parent:
                    # Get all text before the citation
                    all_text = parent.get_text()
                    cite_index = all_text.find(cite_text)
                    if cite_index > 0:
                        # Look backwards for author name (typically ends with comma)
                        before_text = all_text[:cite_index].strip()
                        # Try to find author pattern: "Author," or "Author et al.,"
                        author_match = re.search(
                            r"([A-Z][a-zA-Z\s]+(?:et\s+al\.)?)\s*,\s*$", before_text
                        )
                        if author_match:
                            author = author_match.group(1).strip()
                            # Reconstruct citation with author
                            year = year_only_pattern.match(cite_text).group(1)

                            # Update the cite element to include author
                            # Wrap the ENTIRE citation in a single link
                            cite.clear()
                            full_citation_link = soup.new_tag(
                                "a",
                                attrs={
                                    "class": "ltx_ref",
                                    "href": f"#bib.bib{year}",
                                    "title": "",
                                },
                            )
                            full_citation_link.string = f"{author}, ({year})"
                            cite.append(full_citation_link)
                            logger.debug(
                                f"Fixed citation format: '{cite_text}' -> "
                                f"'{author}, ({year})' (entire citation linked)"
                            )
                        else:
                            # Check if author is in a previous sibling
                            prev_sibling = cite.find_previous_sibling()
                            if prev_sibling:
                                prev_text = prev_sibling.get_text(strip=True)
                                # Check if previous sibling ends with
                                # author name pattern
                                author_match = re.search(
                                    r"([A-Z][a-zA-Z\s]+(?:et\s+al\.)?)\s*,\s*$",
                                    prev_text,
                                )
                                if author_match:
                                    author = author_match.group(1).strip()
                                    year = year_only_pattern.match(cite_text).group(1)

                                    # Wrap the ENTIRE citation in a single link
                                    cite.clear()
                                    full_citation_link = soup.new_tag(
                                        "a",
                                        attrs={
                                            "class": "ltx_ref",
                                            "href": f"#bib.bib{year}",
                                            "title": "",
                                        },
                                    )
                                    full_citation_link.string = f"{author}, ({year})"
                                    cite.append(full_citation_link)
                                    logger.debug(
                                        f"Fixed citation format by merging "
                                        f"sibling: '{cite_text}' -> "
                                        f"'{author}, ({year})' "
                                        f"(entire citation linked)"
                                    )

            # Pattern 3: Ensure citation is a single cohesive unit
            # If citation has multiple separate text nodes, combine them
            text_nodes = [
                node
                for node in cite.children
                if isinstance(node, NavigableString) and node.strip()
            ]
            if len(text_nodes) > 1:
                # Combine text nodes
                combined_text = " ".join(
                    node.strip() for node in text_nodes if node.strip()
                )
                # Remove extra whitespace
                combined_text = re.sub(r"\s+", " ", combined_text)

                # Replace text nodes with single combined text
                for node in text_nodes:
                    node.extract()
                if combined_text:
                    cite.insert(0, combined_text)
                    logger.debug(f"Combined citation text nodes: '{combined_text}'")

    def _fix_equation_tables(self, soup: BeautifulSoup) -> None:
        """
        Fix equation tables to ensure equations stay in single rows.

        LaTeXML sometimes splits equations across multiple table rows or cells.
        MathJax may also split equations into multiple <mjx-container> elements.
        This method ensures each equation is in a maximum 1x1 table structure
        with all math content merged into a single element.
        """
        # Find all equation tables
        equation_tables = soup.find_all(
            "table", class_=re.compile(r"ltx_equation|ltx_eqn_table")
        )

        for table in equation_tables:
            tbody = table.find("tbody")
            if not tbody:
                continue

            rows = tbody.find_all("tr", class_=re.compile(r"ltx_equation|ltx_eqn_row"))

            # If there's only one row, check if it has multiple cells
            # that should be merged
            if len(rows) == 1:
                row = rows[0]
                cells = row.find_all("td")

                # If row has multiple cells but equation content is in one cell, merge
                if len(cells) > 1:
                    # Find the cell with the actual equation (math element)
                    equation_cell = None
                    for cell in cells:
                        # Check for MathML, MathJax, or math class elements
                        if (
                            cell.find(["math", "m:math"])
                            or cell.find_all(["span", "div"], class_=["math", "math-display"])
                            or cell.find("mjx-container")
                            or cell.find("mjx-math")
                        ):
                            equation_cell = cell
                            break

                    if equation_cell:
                        # Merge all cells into the equation cell
                        for cell in cells:
                            if cell != equation_cell:
                                # Move any content from other cells
                                for content in list(cell.children):
                                    if content != equation_cell:
                                        equation_cell.append(content)
                                cell.decompose()

                        # Ensure the row only has one cell now
                        if len(row.find_all("td")) > 1:
                            # Create a new single-cell structure
                            new_cell = soup.new_tag(
                                "td", attrs={"class": "ltx_eqn_cell ltx_align_center"}
                            )
                            for content in list(row.children):
                                new_cell.append(content)
                            row.clear()
                            row.append(new_cell)
                            logger.debug("Merged equation table cells into single cell")
                    
                    # Also merge multiple MathJax containers in the same cell
                    if equation_cell:
                        self._merge_mathjax_containers(equation_cell)

            # If there are multiple rows, merge them into a single row
            elif len(rows) > 1:
                # Find the row with the main equation content
                main_row = None
                for row in rows:
                    if (
                        row.find(["math", "m:math"])
                        or row.find_all(["span", "div"], class_=["math", "math-display"])
                        or row.find("mjx-container")
                        or row.find("mjx-math")
                    ):
                        main_row = row
                        break

                if not main_row:
                    # Use the first row as main
                    main_row = rows[0]

                # Merge content from other rows into main row
                for row in rows:
                    if row != main_row:
                        # Move equation content from other rows
                        for cell in row.find_all("td"):
                            # Find all math elements (MathML, MathJax, or math classes)
                            math_elements = (
                                cell.find_all(["math", "m:math"])
                                + cell.find_all("mjx-container")
                                + cell.find_all("mjx-math")
                                + cell.find_all(["span", "div"], class_=["math", "math-display"])
                            )
                            if math_elements:
                                # Add to main row
                                main_cell = main_row.find("td", class_="ltx_eqn_cell")
                                if not main_cell:
                                    # Create main cell if it doesn't exist
                                    main_cell = soup.new_tag(
                                        "td", attrs={"class": "ltx_eqn_cell ltx_align_center"}
                                    )
                                    main_row.append(main_cell)
                                for math_elem in math_elements:
                                    main_cell.append(math_elem)
                            # Move any other content too
                            for content in list(cell.children):
                                if content not in math_elements:
                                    main_cell = main_row.find("td", class_="ltx_eqn_cell")
                                    if main_cell:
                                        main_cell.append(content)
                            cell.decompose()
                        row.decompose()

                # Ensure main row has single cell structure
                cells = main_row.find_all("td")
                if len(cells) > 1:
                    # Merge cells
                    main_cell = cells[0]
                    for cell in cells[1:]:
                        for content in list(cell.children):
                            main_cell.append(content)
                        cell.decompose()

                # Merge MathJax containers in the merged row
                if main_row:
                    main_cell = main_row.find("td")
                    if main_cell:
                        self._merge_mathjax_containers(main_cell)

                logger.debug(f"Merged {len(rows)} equation rows into single row")

            # Ensure table structure is clean: single row, single cell
            final_rows = tbody.find_all("tr")
            if len(final_rows) == 1:
                final_cells = final_rows[0].find_all("td")
                if len(final_cells) > 1:
                    # Keep only the cell with equation content
                    equation_cell = None
                    for cell in final_cells:
                        if cell.find(["math", "m:math"]) or cell.get_text(strip=True):
                            if not equation_cell:
                                equation_cell = cell
                            else:
                                # Merge into equation cell
                                for content in list(cell.children):
                                    equation_cell.append(content)
                                cell.decompose()

                    # If still multiple cells, merge all
                    remaining_cells = final_rows[0].find_all("td")
                    if len(remaining_cells) > 1:
                        first_cell = remaining_cells[0]
                        for cell in remaining_cells[1:]:
                            for content in list(cell.children):
                                first_cell.append(content)
                            cell.decompose()
                    
                    # Merge MathJax containers in the final cell
                    if equation_cell:
                        self._merge_mathjax_containers(equation_cell)
                    elif final_rows[0].find("td"):
                        self._merge_mathjax_containers(final_rows[0].find("td"))

    def _merge_mathjax_containers(self, container) -> None:
        """
        Merge multiple MathJax containers into a single container.
        
        MathJax 3.x outputs <mjx-container> elements that may be split
        across multiple elements. This method merges them into one.
        """
        # Find all MathJax containers in this element
        mjx_containers = container.find_all("mjx-container")
        
        if len(mjx_containers) <= 1:
            return  # Nothing to merge
        
        # Find the first container to use as the base
        first_container = mjx_containers[0]
        first_math = first_container.find("mjx-math")
        
        # Merge all other containers into the first one
        for mjx_container in mjx_containers[1:]:
            mjx_math = mjx_container.find("mjx-math")
            if mjx_math and first_math:
                # Merge the math content
                for child in list(mjx_math.children):
                    first_math.append(child)
            # Move any other content from the container
            for child in list(mjx_container.children):
                if child != mjx_math:
                    first_container.append(child)
            # Remove the merged container
            mjx_container.decompose()
        
        logger.debug(f"Merged {len(mjx_containers)} MathJax containers into one")

    def _remove_latexml_warnings(self, soup: BeautifulSoup) -> None:
        """Remove LaTeXML warning and error messages from HTML output."""

        # Remove elements with ltx_ERROR class (LaTeXML errors)
        for error_elem in soup.find_all(class_=re.compile(r"ltx_ERROR")):
            logger.debug(f"Removing LaTeXML error: {error_elem.get_text()[:100]}")
            error_elem.decompose()

        # Remove elements with specific error/warning patterns
        warning_patterns = [
            "Unknown environment",
            "Missing",
            "Undefined control sequence",
            "Error:",
            "Warning:",
        ]

        # Remove spans and divs that contain warning text
        for elem in soup.find_all(["span", "div"]):
            elem_text = elem.get_text(strip=True)
            # Check if element has yellow/orange background (typical for warnings)
            style = elem.get("style", "")
            has_warning_color = any(
                color in style.lower() for color in ["yellow", "orange", "#ff", "#f0"]
            )

            # Check if text matches warning patterns
            has_warning_text = any(pattern in elem_text for pattern in warning_patterns)

            if (has_warning_color and has_warning_text) or (
                has_warning_text and len(elem_text) < 200 and elem.name == "span"
            ):
                logger.debug(f"Removing warning element: {elem_text[:100]}")
                # Replace with empty span to preserve document structure
                elem.decompose()

        # Specifically handle overpic environment warnings
        # overpic is a LaTeX package for overlaying text on images
        # When missing, replace the warning with the underlying figure if available
        for elem in soup.find_all(
            string=re.compile(r"Unknown environment.*overpic", re.IGNORECASE)
        ):
            parent = elem.parent
            if parent:
                # Try to find a figure nearby that should have been used
                figure_elem = parent.find_next("figure") or parent.find_previous(
                    "figure"
                )
                if figure_elem:
                    # The figure exists, just remove the warning
                    elem.extract()
                    logger.debug("Removed overpic warning, figure present")
                else:
                    # No figure found - this is a missing graphic
                    # Replace with a placeholder or remove entirely
                    elem.replace_with(
                        "[Figure unavailable: overpic environment not supported]"
                    )
                    logger.warning(
                        "overpic environment not supported, placeholder inserted"
                    )

        # Handle raw LaTeX overpic code that LaTeXML couldn't process
        # These appear as text inside ltx_picture spans
        for span in soup.find_all("span", class_="ltx_picture"):
            span_text = span.get_text(strip=True)
            # Check if this span contains raw overpic LaTeX code
            if "\\begin{overpic}" in span_text:
                # Extract the figure filename from the overpic command
                # Pattern: \begin{overpic}[...]{FigureX.pdf}
                figure_match = re.search(
                    r"\\begin\{overpic\}[^{]*\{([^}]+)\}", span_text
                )
                if figure_match:
                    figure_filename = figure_match.group(1)
                    # Create an img tag to replace the raw LaTeX
                    img_tag = soup.new_tag(
                        "img", src=figure_filename, alt=f"Figure: {figure_filename}"
                    )
                    img_tag["loading"] = "lazy"
                    img_tag["style"] = "max-width: 100%; height: auto;"
                    span.clear()
                    span.append(img_tag)
                    logger.debug(
                        f"Converted overpic LaTeX to img tag: {figure_filename}"
                    )
                else:
                    # Couldn't extract filename, remove the raw LaTeX
                    span.clear()
                    span.append("[Figure: overpic environment not fully supported]")
                    logger.warning(
                        f"Could not extract figure from overpic: {span_text[:100]}"
                    )

    def _fix_image_paths(self, soup: BeautifulSoup) -> None:
        """Fix image paths to point to correct location relative to output file."""
        if not self._html_file_path or not self._output_file_path:
            return

        # Determine the relative path from output file to latexml directory
        # If HTML is in latexml/ and output is in root, we need to adjust paths
        html_dir = self._html_file_path.parent
        output_dir = self._output_file_path.parent

        # Check if HTML is in a latexml subdirectory
        if html_dir.name == "latexml" and output_dir != html_dir:
            # Images are in latexml/figures/, but final HTML is in root
            # So paths like "figures/figure-1.png" need to become
            # "latexml/figures/figure-1.png"
            for img in soup.find_all("img", src=True):
                src = img.get("src", "")
                if not src:
                    continue

                # Skip absolute URLs and data URIs
                if src.startswith(("http://", "https://", "data:", "/")):
                    continue

                # If path starts with "figures/", update to "latexml/figures/"
                if src.startswith("figures/"):
                    new_src = f"latexml/{src}"
                    img["src"] = new_src
                    logger.debug(f"Updated image path: {src} -> {new_src}")
                # If it's a relative path that might be in latexml/, check if it exists
                elif not src.startswith("latexml/"):
                    # Check if the file exists in latexml directory
                    potential_path = html_dir / src
                    if potential_path.exists():
                        # Update to include latexml/ prefix
                        new_src = f"latexml/{src}"
                        img["src"] = new_src
                        logger.debug(f"Updated image path: {src} -> {new_src}")

    def _add_mathjax_support(self, soup: BeautifulSoup) -> None:
        """Add MathJax support for math rendering."""
        head = soup.find("head")
        if head:
            # Add MathJax 3.x configuration
            mathjax_config = soup.new_tag(
                "script", attrs={"type": "text/x-mathjax-config"}
            )
            mathjax_config.string = """
            window.MathJax = {
                tex: {
                    inlineMath: [['$','$'], ['\\(','\\)']],
                    displayMath: [['$$','$$'], ['\\[','\\]']],
                    processEscapes: true,
                    processEnvironments: true
                },
                options: {
                    skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre']
                },
                svg: {
                    fontCache: 'global'
                }
            };
            """
            head.append(mathjax_config)

            # Add MathJax 3.x script
            mathjax_script = soup.new_tag(
                "script",
                attrs={"src": "https://polyfill.io/v3/polyfill.min.js?features=es6"},
            )
            head.append(mathjax_script)

            mathjax_main = soup.new_tag(
                "script",
                attrs={
                    "id": "MathJax-script",
                    "async": "",
                    "src": "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js",
                },
            )
            head.append(mathjax_main)

    def _process_math_expressions(self, soup: BeautifulSoup) -> None:
        """Process mathematical expressions for MathJax compatibility."""
        try:
            self._process_inline_math(soup)
            self._process_display_math(soup)
            logger.info("Mathematical expressions processed for MathJax compatibility")

        except Exception as exc:
            logger.error("Error processing mathematical expressions: %s", exc)

    def _process_inline_math(self, soup: BeautifulSoup) -> None:
        """Process inline math expressions ($...$)."""
        for text_node in soup.find_all(string=True):
            if not isinstance(text_node, NavigableString):
                continue

            text = str(text_node)
            if "$" not in text:
                continue

            parts = text.split("$")
            if len(parts) <= 1:
                continue

            new_content = self._build_inline_math_content(soup, parts)
            if len(new_content) > 1:
                text_node.replace_with(*new_content)

    def _build_inline_math_content(self, soup: BeautifulSoup, parts: list) -> list:
        """Build content for inline math expressions."""
        new_content = []
        for i, part in enumerate(parts):
            if i % 2 == 0:  # Even indices are regular text
                new_content.append(part)
            else:  # Odd indices are math expressions
                if part.strip():  # Only process non-empty math
                    math_span = soup.new_tag("span", attrs={"class": "math"})
                    math_span.string = f"${part}$"
                    new_content.append(math_span)
        return new_content

    def _process_display_math(self, soup: BeautifulSoup) -> None:
        """Process display math expressions ($$...$$)."""
        for p in soup.find_all("p"):
            text = p.get_text()
            if "$$" not in text:
                continue

            parts = text.split("$$")
            if len(parts) <= 1:
                continue

            new_content = self._build_display_math_content(soup, parts)
            if len(new_content) > 1:
                self._replace_paragraph_content(p, new_content)

    def _build_display_math_content(self, soup: BeautifulSoup, parts: list) -> list:
        """Build content for display math expressions."""
        new_content = []
        for i, part in enumerate(parts):
            if i % 2 == 0:  # Even indices are regular text
                if part.strip():
                    new_content.append(part)
            else:  # Odd indices are display math
                if part.strip():  # Only process non-empty math
                    math_div = soup.new_tag("div", attrs={"class": "math-display"})
                    math_div.string = f"$${part}$$"
                    new_content.append(math_div)
        return new_content

    def _replace_paragraph_content(self, p, new_content: list) -> None:
        """Replace paragraph content with new content."""
        p.clear()
        for content in new_content:
            if isinstance(content, str):
                p.append(content)
            else:
                p.append(content)

    def _enhance_links(self, soup: BeautifulSoup) -> None:
        """Enhance links with proper attributes."""
        for link in soup.find_all("a"):
            href = link.get("href")
            if href and self._is_external_link(href):
                # Add target="_blank" for external links
                link["target"] = "_blank"
                link["rel"] = "noopener noreferrer"

    def _is_external_link(self, href: str) -> bool:
        """Check if link is external."""
        if not self.base_url:
            return False

        try:
            parsed_href = urlparse(href)
            parsed_base = urlparse(self.base_url)
            return parsed_href.netloc and parsed_href.netloc != parsed_base.netloc
        except Exception:
            return False

    def _add_responsive_meta(self, soup: BeautifulSoup) -> None:
        """Add responsive meta tag."""
        head = soup.find("head")
        if head and not head.find("meta", attrs={"name": "viewport"}):
            viewport_meta = soup.new_tag(
                "meta",
                attrs={
                    "name": "viewport",
                    "content": "width=device-width, initial-scale=1.0",
                },
            )
            head.append(viewport_meta)

    def _add_enhancement_css(self, soup: BeautifulSoup) -> None:
        """Add CSS for better styling."""
        head = soup.find("head")
        if head:
            style = soup.new_tag("style", attrs={"type": "text/css"})
            style.string = """
            /* Base typography */
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
                    Roboto, sans-serif;
                line-height: 1.6;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
            }
            .math { font-family: "Times New Roman", serif; }

            /* Images - responsive and centered */
            img {
                max-width: 100%;
                height: auto;
                display: block;
                margin: 0 auto;
            }
            .ltx_graphics {
                max-width: 100%;
                height: auto;
            }

            /* Figures - centered with proper spacing */
            figure.ltx_figure {
                margin: 2em auto;
                text-align: center;
                page-break-inside: avoid;
            }
            figure.ltx_figure_panel {
                display: inline-block;
                margin: 0.5em;
                vertical-align: top;
            }

            /* Multi-panel figures - flexbox layout */
            .ltx_flex_figure {
                display: flex;
                justify-content: center;
                align-items: flex-start;
                flex-wrap: wrap;
                gap: 1em;
                margin: 1em 0;
            }
            .ltx_flex_cell {
                flex: 1;
                min-width: 200px;
                max-width: 400px;
            }

            /* Figure captions */
            figcaption {
                margin-top: 0.5em;
                font-size: 0.9em;
                color: #333;
                text-align: center;
            }
            figcaption .ltx_tag_figure {
                font-weight: bold;
            }

            /* Tables */
            table {
                border-collapse: collapse;
                width: 100%;
                margin: 1.5em auto;
                max-width: 100%;
            }
            th, td {
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
            }
            th {
                background-color: #f5f5f5;
                font-weight: bold;
            }
            .ltx_table {
                margin: 2em auto;
                text-align: center;
            }

            /* Equation tables - remove borders */
            table.ltx_equation,
            table.ltx_equationgroup,
            table.ltx_eqn_table {
                border: none !important;
                border-collapse: collapse;
            }
            table.ltx_equation td,
            table.ltx_equationgroup td,
            table.ltx_eqn_table td,
            table.ltx_equation th,
            table.ltx_equationgroup th,
            table.ltx_eqn_table th {
                border: none !important;
                padding: 0;
                background: transparent;
            }
            table.ltx_equation tr,
            table.ltx_equationgroup tr,
            table.ltx_eqn_table tr {
                border: none !important;
            }

            /* Alignment utilities */
            .ltx_align_center {
                text-align: center;
                margin-left: auto;
                margin-right: auto;
            }
            .ltx_centering {
                text-align: center;
            }

            /* Landscape images */
            .ltx_img_landscape {
                width: auto;
                max-width: 100%;
            }

            /* Float wrappers */
            .ltx_float {
                margin: 1.5em auto;
                padding: 1em;
            }
            .ltx_float.ltx_framed {
                border: 1px solid #ddd;
                background: #fafafa;
            }

            /* Responsive design */
            @media (max-width: 768px) {
                .ltx_flex_figure {
                    flex-direction: column;
                }
                .ltx_flex_cell {
                    max-width: 100%;
                }
            }
            """
            head.append(style)


    def _convert_assets_to_svg(
        self, soup: BeautifulSoup, html_dir: Path, results: dict[str, Any]
    ) -> BeautifulSoup:
        """Convert assets (TikZ, PDF) to SVG format."""
        try:
            # Skip asset conversion if service is not available
            if self.asset_conversion_service is None:
                logger.info(
                    "Asset conversion service not available, skipping asset conversion"
                )
                results["steps_completed"].append("asset_conversion_skipped")
                return soup

            # Create assets directory
            assets_dir = html_dir / "assets"
            assets_dir.mkdir(exist_ok=True)

            # Find and convert TikZ diagrams
            tikz_diagrams = self._find_tikz_diagrams(soup)
            if tikz_diagrams:
                logger.info("Found %d TikZ diagrams to convert", len(tikz_diagrams))
                self._convert_tikz_diagrams(tikz_diagrams, assets_dir, results)

            # Find and convert PDF figures
            pdf_figures = self._find_pdf_figures(soup)
            if pdf_figures:
                logger.info("Found %d PDF figures to convert", len(pdf_figures))
                self._convert_pdf_figures(pdf_figures, assets_dir, results)

            # Find and convert image assets
            image_assets = self._find_image_assets(soup)
            if image_assets:
                logger.info("Found %d image assets to convert", len(image_assets))
                self._convert_image_assets(image_assets, assets_dir, results)

            results["steps_completed"].append("asset_conversion")
            return soup

        except Exception as exc:
            error_msg = f"Asset conversion failed: {exc}"
            results["errors"].append(error_msg)
            logger.error(error_msg)
            return soup

    def _find_tikz_diagrams(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """Find TikZ diagrams in the HTML."""
        tikz_diagrams = []

        # Look for tikzpicture environments
        for tikz in soup.find_all("div", class_="tikzpicture"):
            tikz_diagrams.append(
                {
                    "element": tikz,
                    "type": "tikz",
                    "content": tikz.get_text(),
                    "id": tikz.get("id", ""),
                    "class": tikz.get("class", []),
                }
            )

        # Look for LaTeX tikz environments
        for tikz in soup.find_all("div", attrs={"data-latexml": True}):
            if "tikz" in str(tikz.get("class", [])).lower():
                tikz_diagrams.append(
                    {
                        "element": tikz,
                        "type": "tikz",
                        "content": tikz.get_text(),
                        "id": tikz.get("id", ""),
                        "class": tikz.get("class", []),
                    }
                )

        return tikz_diagrams

    def _find_pdf_figures(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """Find PDF figures in the HTML."""
        pdf_figures = []

        # Look for PDF links
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if href.lower().endswith(".pdf"):
                pdf_figures.append(
                    {
                        "element": link,
                        "type": "pdf",
                        "href": href,
                        "id": link.get("id", ""),
                        "class": link.get("class", []),
                    }
                )

        # Look for embedded PDF objects
        for obj in soup.find_all("object", attrs={"data": True}):
            data = obj.get("data", "")
            if data.lower().endswith(".pdf"):
                pdf_figures.append(
                    {
                        "element": obj,
                        "type": "pdf",
                        "href": data,
                        "id": obj.get("id", ""),
                        "class": obj.get("class", []),
                    }
                )

        return pdf_figures

    def _find_image_assets(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """Find image assets that could be converted to SVG."""
        image_assets = []

        # Look for images
        for img in soup.find_all("img", src=True):
            src = img.get("src", "")
            # Convert PDF images to SVG, skip other raster formats
            if src.lower().endswith(".pdf"):
                image_assets.append(
                    {
                        "element": img,
                        "type": "pdf_image",
                        "src": src,
                        "id": img.get("id", ""),
                        "class": img.get("class", []),
                    }
                )

        return image_assets

    def _convert_tikz_diagrams(
        self,
        tikz_diagrams: list[dict[str, Any]],
        assets_dir: Path,
        results: dict[str, Any],
    ) -> None:
        """Convert TikZ diagrams to SVG."""
        try:
            for i, tikz in enumerate(tikz_diagrams):
                # Create temporary TikZ file
                tikz_file = assets_dir / f"tikz_diagram_{i}.tex"
                with open(tikz_file, "w", encoding="utf-8") as f:
                    f.write(
                        f"\\documentclass{{standalone}}\n\\usepackage{{tikz}}\n\\begin{{document}}\n{tikz['content']}\n\\end{{document}}"
                    )

                # Convert to SVG
                conversion_result = self.asset_conversion_service.convert_assets(
                    assets_dir,
                    assets_dir,
                    asset_types=["tikz"],
                    options={"timeout": 300},
                )

                if conversion_result.get("success"):
                    # Get the actual output file from conversion result
                    output_file = conversion_result.get("output_file")
                    if output_file and Path(output_file).exists():
                        svg_file = Path(output_file)
                        self._replace_element_with_svg(tikz["element"], svg_file)
                        results.setdefault("converted_assets", []).append(
                            {
                                "type": "tikz",
                                "original": tikz["id"],
                                "svg_file": str(svg_file),
                                "success": True,
                            }
                        )
                    else:
                        # Fallback: try the expected filename pattern
                        # with _wrapper suffix
                        svg_file = assets_dir / f"tikz_diagram_{i}_wrapper.svg"
                        if svg_file.exists():
                            self._replace_element_with_svg(tikz["element"], svg_file)
                            results.setdefault("converted_assets", []).append(
                                {
                                    "type": "tikz",
                                    "original": tikz["id"],
                                    "svg_file": str(svg_file),
                                    "success": True,
                                }
                            )
                else:
                    results.setdefault("failed_assets", []).append(
                        {
                            "type": "tikz",
                            "original": tikz["id"],
                            "error": "Conversion failed",
                        }
                    )

        except Exception as exc:
            logger.error("TikZ conversion failed: %s", exc)
            results.setdefault("failed_assets", []).append(
                {"type": "tikz", "error": str(exc)}
            )

    def _convert_pdf_figures(
        self,
        pdf_figures: list[dict[str, Any]],
        assets_dir: Path,
        results: dict[str, Any],
    ) -> None:
        """Convert PDF figures to SVG."""
        import shutil
        from urllib.parse import unquote

        try:
            for i, pdf in enumerate(pdf_figures):
                # Get PDF file path from href or data attribute
                pdf_path_str = pdf.get("href", "")
                if not pdf_path_str:
                    logger.warning(f"PDF figure {i} has no href/data attribute")
                    results.setdefault("failed_assets", []).append(
                        {
                            "type": "pdf",
                            "original": pdf.get("id", f"pdf_{i}"),
                            "error": "No href/data attribute found",
                        }
                    )
                    continue

                # Parse and decode URL-encoded paths
                pdf_path_str = unquote(pdf_path_str)

                # Handle both absolute and relative paths
                if pdf_path_str.startswith(("http://", "https://")):
                    # External URL - skip for now (could implement download later)
                    logger.warning(f"External PDF URLs not supported: {pdf_path_str}")
                    results.setdefault("failed_assets", []).append(
                        {
                            "type": "pdf",
                            "original": pdf.get("id", f"pdf_{i}"),
                            "error": "External URLs not supported",
                        }
                    )
                    continue

                # Resolve relative path
                # Assume PDF is relative to the assets directory or current HTML file
                pdf_source = assets_dir / pdf_path_str
                if not pdf_source.exists():
                    # Try looking in parent directory
                    pdf_source = assets_dir.parent / pdf_path_str
                    if not pdf_source.exists():
                        logger.warning(f"PDF file not found: {pdf_path_str}")
                        results.setdefault("failed_assets", []).append(
                            {
                                "type": "pdf",
                                "original": pdf.get("id", f"pdf_{i}"),
                                "error": f"File not found: {pdf_path_str}",
                            }
                        )
                        continue

                # Copy PDF to assets directory if not already there
                pdf_dest = assets_dir / f"pdf_figure_{i}.pdf"
                if pdf_source != pdf_dest:
                    shutil.copy2(pdf_source, pdf_dest)
                    logger.debug(f"Copied PDF: {pdf_source} -> {pdf_dest}")

                # Convert specific PDF file to SVG using PDF service directly
                # This avoids processing all PDFs in the directory
                from app.config import settings

                pdf_service = self.asset_conversion_service.pdf_service
                conversion_result = pdf_service.convert_pdf_to_svg(
                    pdf_dest,
                    assets_dir,
                    options={"timeout": settings.CONVERSION_TIMEOUT},
                )

                if conversion_result.get("success"):
                    # Get the output SVG file from conversion result
                    svg_file = Path(conversion_result.get("output_file", ""))
                    if not svg_file.is_file():
                        # Fallback: try expected filename
                        svg_file = assets_dir / f"pdf_figure_{i}.svg"

                    if svg_file.is_file():
                        self._replace_element_with_svg(pdf["element"], svg_file)
                        results.setdefault("converted_assets", []).append(
                            {
                                "type": "pdf",
                                "original": pdf.get("id", f"pdf_{i}"),
                                "svg_file": str(svg_file),
                                "success": True,
                            }
                        )
                    else:
                        results.setdefault("failed_assets", []).append(
                            {
                                "type": "pdf",
                                "original": pdf.get("id", f"pdf_{i}"),
                                "error": "SVG file not found after conversion",
                            }
                        )
                else:
                    error_msg = conversion_result.get("error", "Conversion failed")
                    results.setdefault("failed_assets", []).append(
                        {
                            "type": "pdf",
                            "original": pdf.get("id", f"pdf_{i}"),
                            "error": error_msg,
                        }
                    )

        except Exception as exc:
            logger.error("PDF conversion failed: %s", exc)
            results.setdefault("failed_assets", []).append(
                {"type": "pdf", "error": str(exc)}
            )

    def _convert_image_assets(
        self,
        image_assets: list[dict[str, Any]],
        assets_dir: Path,
        results: dict[str, Any],
    ) -> None:
        """Convert PDF image assets to SVG."""
        try:
            for img_asset in image_assets:
                if img_asset["type"] != "pdf_image":
                    continue

                # Get the source PDF path
                src = img_asset["src"]
                pdf_path = (
                    self._html_file_path.parent / src
                    if self._html_file_path
                    else Path(src)
                )

                if not pdf_path.exists():
                    logger.warning(f"PDF image not found: {pdf_path}")
                    results.setdefault("failed_assets", []).append(
                        {
                            "type": "pdf_image",
                            "original": src,
                            "error": "File not found",
                        }
                    )
                    continue

                try:
                    # Convert PDF to SVG
                    conversion_result = (
                        self.asset_conversion_service.pdf_service.convert_pdf_to_svg(
                            pdf_file=pdf_path,
                            output_dir=assets_dir,
                            options={"timeout": 60},
                        )
                    )

                    if conversion_result.get("success"):
                        svg_file = Path(conversion_result["output_file"])
                        if svg_file.exists():
                            # Update img src to point to SVG
                            relative_svg_path = svg_file.relative_to(
                                self._html_file_path.parent
                                if self._html_file_path
                                else Path.cwd()
                            )
                            img_asset["element"]["src"] = str(relative_svg_path)

                            results.setdefault("converted_assets", []).append(
                                {
                                    "type": "pdf_image",
                                    "original": src,
                                    "svg_file": str(svg_file),
                                    "success": True,
                                }
                            )
                            logger.info(
                                f"Converted PDF image to SVG: {src} -> "
                                f"{relative_svg_path}"
                            )
                        else:
                            raise RuntimeError("SVG file not created")
                    else:
                        raise RuntimeError("Conversion failed")

                except Exception as exc:
                    logger.error(f"Failed to convert PDF image {src}: {exc}")
                    results.setdefault("failed_assets", []).append(
                        {"type": "pdf_image", "original": src, "error": str(exc)}
                    )

        except Exception as exc:
            logger.error("Image asset conversion failed: %s", exc)
            results.setdefault("failed_assets", []).append(
                {"type": "image", "error": str(exc)}
            )

    def _replace_element_with_svg(self, element, svg_file: Path) -> None:
        """Replace an HTML element with an SVG element."""
        try:
            # Read SVG content
            with open(svg_file, encoding="utf-8") as f:
                svg_content = f.read()

            # Create new SVG element
            new_svg = BeautifulSoup(svg_content, "html.parser").find("svg")
            if new_svg:
                # Preserve original attributes
                for attr in ["id", "class", "style"]:
                    if element.get(attr):
                        new_svg[attr] = element.get(attr)

                # Replace the element
                element.replace_with(new_svg)

        except Exception as exc:
            logger.error("Failed to replace element with SVG: %s", exc)

    def _write_html(self, soup: BeautifulSoup, output_file: Path) -> None:
        """Write HTML to file."""
        try:
            output_file.parent.mkdir(parents=True, exist_ok=True)

            with open(output_file, "w", encoding="utf-8") as f:
                f.write(str(soup.prettify()))

        except Exception as exc:
            raise HTMLPostProcessingError(f"Failed to write HTML file: {exc}") from exc

    def validate_html_file(self, html_file: Path) -> dict[str, Any]:
        """
        Validate HTML file structure and content.

        Args:
            html_file: Path to HTML file

        Returns:
            Dict with validation results
        """
        if not html_file.exists():
            raise HTMLPostProcessingError(f"HTML file not found: {html_file}")

        try:
            with open(html_file, encoding="utf-8") as f:
                html_content = f.read()

            # Parse with lxml for validation
            try:
                html.fromstring(html_content)
                is_valid = True
                validation_errors = []
            except XMLSyntaxError as exc:
                is_valid = False
                validation_errors = [str(exc)]

            # Additional checks with BeautifulSoup
            soup = BeautifulSoup(html_content, "html.parser")

            # Check for required elements
            has_html = bool(soup.find("html"))
            has_head = bool(soup.find("head"))
            has_body = bool(soup.find("body"))

            return {
                "is_valid": is_valid,
                "validation_errors": validation_errors,
                "has_html": has_html,
                "has_head": has_head,
                "has_body": has_body,
                "file_size": len(html_content),
                "element_count": len(soup.find_all()),
                "text_length": len(soup.get_text()),
            }

        except Exception as exc:
            raise HTMLPostProcessingError(f"HTML validation failed: {exc}") from exc
