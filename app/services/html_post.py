"""
HTML post-processing service for LaTeXML output.

This module provides HTML post-processing functionality to clean, validate,
and enhance LaTeXML-generated HTML output.
"""

import re
from concurrent.futures import ThreadPoolExecutor
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
        
        # Pre-compile regex patterns for performance optimization
        self._compile_regex_patterns()

    def _setup_cleaner(self) -> None:
        """Set up HTML cleaner with appropriate settings."""
        self.cleaner = setup_cleaner()

    def _compile_regex_patterns(self) -> None:
        """Pre-compile regex patterns for performance optimization."""
        # Year patterns
        self.year_pattern = re.compile(r"(\d{4}[a-z]?)")
        self.year_only_pattern = re.compile(r"^\s*\(\s*(\d{4}[a-z]?)\s*\)\s*$")
        
        # Author patterns for citation fixing
        self.author_pattern_1 = re.compile(
            r"([A-Z][a-zA-Z\s]+(?:et\s+al\.)?)\s*,\s*\(\s*\)?\s*$"
        )
        self.author_pattern_2 = re.compile(
            r"([A-Z][a-zA-Z\s]+(?:et\s+al\.)?)\s*,\s*\(\s*\)"
        )
        self.author_pattern_3 = re.compile(
            r"([A-Z][a-zA-Z\s]+(?:et\s+al\.)?)\s*,"
        )
        self.author_pattern_4 = re.compile(
            r"([A-Z][a-zA-Z\s]+(?:et\s+al\.)?)\s*,\s*$"
        )
        
        # Citation patterns
        self.citation_pattern = re.compile(r"\([^()]{0,50}?,\s*\d{4}[a-z]?\)")
        
        # Table/equation patterns
        self.equation_table_pattern = re.compile(r"ltx_equation|ltx_eqn_table")
        self.equation_row_pattern = re.compile(r"ltx_equation|ltx_eqn_row")
        
        # Error/warning patterns
        self.error_class_pattern = re.compile(r"ltx_ERROR")
        self.overpic_warning_pattern = re.compile(
            r"Unknown environment.*overpic", re.IGNORECASE
        )
        
        # Whitespace normalization pattern (used frequently)
        self.whitespace_pattern = re.compile(r"\s+")

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

            # Parse with BeautifulSoup - use lxml parser if available for better performance
            # lxml is faster and more memory-efficient than html.parser
            parser = "lxml" if html is not None else "html.parser"
            soup = BeautifulSoup(html_content, parser)

            # Apply processing steps
            processing_results = {
                "original_size": len(html_content),
                "steps_completed": [],
                "errors": [],
                "warnings": [],
                "options": options or {},  # Pass options through for asset conversion
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

            # Step 6: Add content verification report (if verification data exists)
            self._add_content_verification_report(optimized_soup, processing_results)

            # Step 7: Add conversion warnings summary banner (if any warnings exist)
            self._add_conversion_warnings_summary(optimized_soup, processing_results)

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
            # Pass results dict to collect conversion warnings
            self._fix_latexml_artifacts(soup, results)

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

    def _fix_latexml_artifacts(self, soup: BeautifulSoup, results: dict[str, Any]) -> None:
        """
        Fix artifacts from LaTeXML processing custom classes without proper bindings.

        Args:
            soup: BeautifulSoup object to process
            results: Processing results dict to store warnings
        """

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

        # Fix 3: Collect and style LaTeXML error/warning messages
        # Instead of removing them, preserve them so users know about conversion issues
        conversion_warnings = self._collect_and_style_latexml_warnings(soup)

        # Store warnings in results for later reporting
        if conversion_warnings:
            results.setdefault("conversion_warnings", []).extend(conversion_warnings)
            logger.info(f"Collected {len(conversion_warnings)} conversion warnings")

        # Fix 4 & 5: Process all citations in a single pass for efficiency
        # Collect all cite elements once to avoid multiple DOM traversals
        all_cites = soup.find_all("cite")
        
        for cite in all_cites:
            # Fix 4: Remove bold formatting from inside citations
            # Citations should not have bold formatting
            for bold_span in cite.find_all("span", class_="ltx_font_bold"):
                bold_span.unwrap()
                logger.debug("Removed bold formatting from citation")
            
            # Fix 5: Fix misplaced citation tags that wrap too much content
            # LaTeXML sometimes puts the entire text in <cite> instead of just the citation
            cite_text = cite.get_text(strip=True)
            # Citations should be relatively short (author + year, typically < 50 chars)
            if len(cite_text) > 100:
                # This is likely wrapping too much - try to extract just the citation
                # Look for patterns like "(Author, YYYY)" or "Author et al., YYYY"
                citation_match = self.citation_pattern.search(cite_text)
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
        # Cache get_text() results to avoid repeated DOM traversal
        for cite in soup.find_all("cite"):
            # Cache get_text() result - it's expensive for nested elements
            cite_text = cite.get_text(strip=True)
            # Cache normalized version to avoid repeated normalization
            # Use pre-compiled pattern for better performance
            full_cite_text_normalized = self.whitespace_pattern.sub(" ", cite_text)

            # Check if citation structure has author and year separated
            # Pattern 1: Citation has "Author, ( )" with year in a separate link
            # Goal: Wrap the ENTIRE "Author, (Year)" in a single link
            year_link = cite.find("a", class_="ltx_ref")
            if year_link:
                year_text = year_link.get_text(strip=True)
                # Check if year is a 4-digit year or contains year pattern
                year_match = self.year_pattern.search(year_text)
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
                    # Use pre-compiled pattern for better performance
                    before_text = self.whitespace_pattern.sub(" ", before_text)
                    # Use cached normalized cite text instead of calling get_text() again
                    # This avoids expensive DOM traversal
                    full_cite_text = full_cite_text_normalized

                    # Check if we have author before the year link
                    # Pattern: "Author," or "Author et al.,"
                    # possibly followed by "(" or "( )"
                    # Try multiple patterns to catch different text node structures
                    author_match = None

                    # Pattern 1: "Author, ( )" or "Author, (" in before_text
                    # (handle whitespace variations)
                    # Match "Author, ( )" or "Author, (" with any whitespace
                    author_match = self.author_pattern_1.search(before_text)

                    # Pattern 2: Check full citation text for "Author, ( ) Year" pattern
                    if not author_match:
                        full_match = self.author_pattern_2.search(full_cite_text)
                        if full_match:
                            author_match = full_match

                    # Pattern 3: Just "Author," at the start (most permissive)
                    if not author_match:
                        # Look for any author name pattern followed by comma
                        simple_match = self.author_pattern_3.search(before_text)
                        if simple_match:
                            author_match = simple_match

                    # Pattern 4: Check if full citation has
                    # "Author, ( )" pattern anywhere
                    if not author_match:
                        anywhere_match = self.author_pattern_2.search(full_cite_text)
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
            if self.year_only_pattern.match(cite_text):
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
                        author_match = self.author_pattern_4.search(before_text)
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
                                author_match = self.author_pattern_4.search(prev_text)
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
                # Remove extra whitespace using pre-compiled pattern
                combined_text = self.whitespace_pattern.sub(" ", combined_text)

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
            "table", class_=self.equation_table_pattern
        )

        for table in equation_tables:
            tbody = table.find("tbody")
            if not tbody:
                continue

            rows = tbody.find_all("tr", class_=self.equation_row_pattern)

            # If there's only one row, check if it has multiple cells
            # that should be merged
            if len(rows) == 1:
                row = rows[0]
                cells = row.find_all("td")

                # If row has multiple cells but equation content is in one cell, merge
                if len(cells) > 1:
                    # Find the cell with the actual equation (math element)
                    # Optimization: Cache find() results to avoid repeated DOM traversal
                    equation_cell = None
                    for cell in cells:
                        # Check for MathML, MathJax, or math class elements
                        # Cache individual find() results
                        has_mathml = cell.find(["math", "m:math"])
                        has_mathjax_container = cell.find("mjx-container")
                        has_mathjax_math = cell.find("mjx-math")
                        has_math_classes = cell.find_all(["span", "div"], class_=["math", "math-display"])
                        
                        if has_mathml or has_math_classes or has_mathjax_container or has_mathjax_math:
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
                # Optimization: Cache find() results
                main_row = None
                for row in rows:
                    # Cache individual find() results
                    has_mathml = row.find(["math", "m:math"])
                    has_mathjax_container = row.find("mjx-container")
                    has_mathjax_math = row.find("mjx-math")
                    has_math_classes = row.find_all(["span", "div"], class_=["math", "math-display"])
                    
                    if has_mathml or has_math_classes or has_mathjax_container or has_mathjax_math:
                        main_row = row
                        break

                if not main_row:
                    # Use the first row as main
                    main_row = rows[0]

                # Cache main_cell lookup to avoid repeated find() calls
                main_cell = main_row.find("td", class_="ltx_eqn_cell")
                if not main_cell:
                    # Create main cell if it doesn't exist
                    main_cell = soup.new_tag(
                        "td", attrs={"class": "ltx_eqn_cell ltx_align_center"}
                    )
                    main_row.append(main_cell)

                # Merge content from other rows into main row
                for row in rows:
                    if row != main_row:
                        # Move equation content from other rows
                        for cell in row.find_all("td"):
                            # Optimization: Combine multiple find_all() calls
                            # Find all math elements (MathML, MathJax, or math classes)
                            mathml_elements = cell.find_all(["math", "m:math"])
                            mjx_container_elements = cell.find_all("mjx-container")
                            mjx_math_elements = cell.find_all("mjx-math")
                            math_class_elements = cell.find_all(["span", "div"], class_=["math", "math-display"])
                            
                            # Combine all math elements
                            math_elements = (
                                mathml_elements
                                + mjx_container_elements
                                + mjx_math_elements
                                + math_class_elements
                            )
                            
                            if math_elements:
                                # Add to main row (main_cell already cached)
                                for math_elem in math_elements:
                                    main_cell.append(math_elem)
                            
                            # Move any other content too
                            for content in list(cell.children):
                                if content not in math_elements:
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

    def _collect_and_style_latexml_warnings(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """
        Collect and style LaTeXML warning/error messages instead of removing them.

        Returns:
            List of collected warnings with metadata
        """
        collected_warnings = []

        # Collect elements with ltx_ERROR class (LaTeXML errors)
        for error_elem in soup.find_all(class_=self.error_class_pattern):
            error_text = error_elem.get_text(strip=True)
            logger.warning(f"LaTeXML error detected: {error_text[:100]}")

            # Store warning metadata
            collected_warnings.append({
                "type": "error",
                "severity": "high",
                "message": error_text,
                "source": "latexml_error_class",
            })

            # Style the error instead of removing it
            # Remove garish yellow background, use subtle styling
            error_elem["class"] = error_elem.get("class", []) + ["conversion-error"]
            error_elem["style"] = (
                "background-color: #fff3cd; "
                "border-left: 4px solid #ffc107; "
                "padding: 8px; "
                "margin: 8px 0; "
                "font-size: 0.9em; "
                "color: #856404;"
            )
            error_elem["title"] = "LaTeXML conversion error - content may be incomplete"

        # Collect and style elements with specific error/warning patterns
        warning_patterns = [
            "Unknown environment",
            "Missing",
            "Undefined control sequence",
            "Error:",
            "Warning:",
        ]

        # Process spans and divs that contain warning text
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
                logger.warning(f"LaTeXML warning detected: {elem_text[:100]}")

                # Collect warning
                warning_type = "unknown"
                severity = "medium"
                for pattern in warning_patterns:
                    if pattern in elem_text:
                        warning_type = pattern.lower().replace(":", "").replace(" ", "_")
                        if "error" in pattern.lower():
                            severity = "high"
                        break

                collected_warnings.append({
                    "type": warning_type,
                    "severity": severity,
                    "message": elem_text,
                    "source": "latexml_warning_pattern",
                })

                # Style the warning instead of removing it
                elem["class"] = elem.get("class", []) + ["conversion-warning"]
                elem["style"] = (
                    "background-color: #d1ecf1; "
                    "border-left: 4px solid #0c5460; "
                    "padding: 6px; "
                    "margin: 6px 0; "
                    "font-size: 0.85em; "
                    "color: #0c5460;"
                )
                elem["title"] = f"LaTeXML warning: {warning_type}"

        # Specifically handle overpic environment warnings
        # overpic is a LaTeX package for overlaying text on images
        # When missing, preserve warning with context
        for elem in soup.find_all(
            string=self.overpic_warning_pattern
        ):
            parent = elem.parent
            if parent:
                # Try to find a figure nearby that should have been used
                figure_elem = parent.find_next("figure") or parent.find_previous(
                    "figure"
                )
                if figure_elem:
                    # The figure exists, note this in warnings
                    collected_warnings.append({
                        "type": "overpic_unsupported",
                        "severity": "medium",
                        "message": "overpic environment not supported - overlay text may be missing",
                        "source": "overpic_pattern",
                    })
                    # Keep warning visible but styled
                    warning_span = soup.new_tag("span", attrs={"class": "conversion-warning"})
                    warning_span["style"] = (
                        "background-color: #d1ecf1; "
                        "border-left: 4px solid #0c5460; "
                        "padding: 6px; "
                        "margin: 6px 0; "
                        "font-size: 0.85em; "
                        "color: #0c5460; "
                        "display: block;"
                    )
                    warning_span.string = "⚠ Note: overpic overlay text not supported - base figure shown only"
                    elem.replace_with(warning_span)
                    logger.warning("overpic environment not supported, base figure present")
                else:
                    # No figure found - this is a missing graphic
                    collected_warnings.append({
                        "type": "overpic_missing_figure",
                        "severity": "high",
                        "message": "overpic environment not supported and figure is missing",
                        "source": "overpic_pattern",
                    })
                    elem.replace_with(
                        "⚠ Figure unavailable: overpic environment not supported"
                    )
                    logger.error(
                        "overpic environment not supported and figure missing"
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

                    # Add warning note
                    warning_note = soup.new_tag("div", attrs={"class": "conversion-warning"})
                    warning_note["style"] = (
                        "background-color: #d1ecf1; "
                        "padding: 4px; "
                        "margin-top: 4px; "
                        "font-size: 0.8em; "
                        "color: #0c5460;"
                    )
                    warning_note.string = f"⚠ overpic overlay text not shown for {figure_filename}"
                    span.insert_after(warning_note)

                    collected_warnings.append({
                        "type": "overpic_partial_conversion",
                        "severity": "medium",
                        "message": f"overpic overlay text lost for {figure_filename}",
                        "source": "overpic_raw_latex",
                    })

                    logger.warning(
                        f"Converted overpic LaTeX to img tag (overlay text lost): {figure_filename}"
                    )
                else:
                    # Couldn't extract filename
                    span.clear()
                    span.append("⚠ Figure: overpic environment not fully supported")
                    collected_warnings.append({
                        "type": "overpic_unparseable",
                        "severity": "high",
                        "message": f"Could not parse overpic environment: {span_text[:100]}",
                        "source": "overpic_raw_latex",
                    })
                    logger.error(
                        f"Could not extract figure from overpic: {span_text[:100]}"
                    )

        return collected_warnings

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

    def _add_content_verification_report(self, soup: BeautifulSoup, results: dict[str, Any]) -> None:
        """
        Add content verification report banner to show content preservation metrics.

        Args:
            soup: BeautifulSoup object
            results: Processing results containing verification data
        """
        # Check if content verification data exists
        verification = results.get("content_verification")
        if not verification:
            return  # No verification data available

        body = soup.find("body")
        if not body:
            return

        # Determine quality color based on overall score
        score = verification.get("overall_score", 0)
        if score >= 95:
            bg_gradient = "linear-gradient(135deg, #11998e 0%, #38ef7d 100%)"  # Green
            quality_emoji = "✅"
        elif score >= 85:
            bg_gradient = "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)"  # Blue
            quality_emoji = "✓"
        elif score >= 70:
            bg_gradient = "linear-gradient(135deg, #fa709a 0%, #fee140 100%)"  # Yellow/Pink
            quality_emoji = "⚠️"
        else:
            bg_gradient = "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)"  # Red
            quality_emoji = "❌"

        # Create verification report container
        verification_div = soup.new_tag("div", attrs={
            "id": "content-verification-report",
            "class": "verification-report"
        })
        verification_div["style"] = (
            f"background: {bg_gradient}; "
            "color: white; "
            "padding: 20px; "
            "margin: 0 0 20px 0; "
            "border-radius: 8px; "
            "box-shadow: 0 4px 6px rgba(0,0,0,0.1); "
            "font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;"
        )

        # Create header with score
        header = soup.new_tag("h2")
        header["style"] = "margin: 0 0 12px 0; font-size: 1.6em; font-weight: 600;"
        quality_label = verification.get("quality", "good").upper()
        header.string = f"{quality_emoji} Content Preservation: {score:.1f}% ({quality_label})"
        verification_div.append(header)

        # Create summary paragraph
        summary_p = soup.new_tag("p")
        summary_p["style"] = "margin: 0 0 16px 0; font-size: 1em; opacity: 0.95; line-height: 1.5;"
        breakdown = verification.get("breakdown", {})

        # Build summary text
        summary_parts = []
        for content_type, metrics in breakdown.items():
            if content_type == "words":
                continue  # Skip words for summary (too detailed)
            source_count = metrics.get("source", 0)
            if source_count > 0:
                preserved_pct = metrics.get("preserved", "0%")
                summary_parts.append(f"{content_type}: {preserved_pct}")

        if summary_parts:
            summary_p.string = " • ".join(summary_parts)
        else:
            summary_p.string = "Content analysis completed."
        verification_div.append(summary_p)

        # Create buttons container
        buttons_div = soup.new_tag("div")
        buttons_div["style"] = "display: flex; gap: 10px; flex-wrap: wrap;"

        # Create details toggle button
        details_btn = soup.new_tag("button", attrs={
            "onclick": "document.getElementById('verification-details').style.display = "
                      "document.getElementById('verification-details').style.display === 'none' ? 'block' : 'none'",
            "class": "verification-toggle-btn"
        })
        details_btn["style"] = (
            "background: rgba(255,255,255,0.2); "
            "border: 1px solid rgba(255,255,255,0.3); "
            "color: white; "
            "padding: 8px 16px; "
            "border-radius: 4px; "
            "cursor: pointer; "
            "font-size: 0.9em; "
            "font-weight: 500; "
            "transition: all 0.2s;"
        )
        details_btn.string = "📊 View Detailed Breakdown"
        buttons_div.append(details_btn)

        # Note: Diff report button is added later in the pipeline after report generation
        verification_div.append(buttons_div)

        # Create collapsible details section
        details_div = soup.new_tag("div", attrs={"id": "verification-details"})
        details_div["style"] = (
            "display: none; "
            "margin-top: 16px; "
            "padding-top: 16px; "
            "border-top: 1px solid rgba(255,255,255,0.2);"
        )

        # Add breakdown table
        table = soup.new_tag("table")
        table["style"] = (
            "width: 100%; "
            "border-collapse: collapse; "
            "margin: 8px 0;"
        )

        # Table header
        thead = soup.new_tag("thead")
        tr = soup.new_tag("tr")
        for header_text in ["Content Type", "Source", "Output", "Preserved"]:
            th = soup.new_tag("th")
            th["style"] = (
                "text-align: left; "
                "padding: 8px; "
                "border-bottom: 2px solid rgba(255,255,255,0.3); "
                "font-weight: 600;"
            )
            th.string = header_text
            tr.append(th)
        thead.append(tr)
        table.append(thead)

        # Table body
        tbody = soup.new_tag("tbody")
        for content_type, metrics in breakdown.items():
            tr = soup.new_tag("tr")
            tr["style"] = "border-bottom: 1px solid rgba(255,255,255,0.1);"

            # Content type cell
            td_type = soup.new_tag("td")
            td_type["style"] = "padding: 8px; text-transform: capitalize;"
            td_type.string = content_type.replace("_", " ")
            tr.append(td_type)

            # Source count cell
            td_source = soup.new_tag("td")
            td_source["style"] = "padding: 8px;"
            td_source.string = str(metrics.get("source", 0))
            tr.append(td_source)

            # Output count cell
            td_output = soup.new_tag("td")
            td_output["style"] = "padding: 8px;"
            td_output.string = str(metrics.get("output", 0))
            tr.append(td_output)

            # Preserved percentage cell
            td_preserved = soup.new_tag("td")
            td_preserved["style"] = "padding: 8px; font-weight: 600;"
            preserved_str = metrics.get("preserved", "0%")
            td_preserved.string = preserved_str
            tr.append(td_preserved)

            tbody.append(tr)
        table.append(tbody)
        details_div.append(table)

        # Add missing/altered content if present
        missing = verification.get("missing_content", [])
        altered = verification.get("altered_content", [])

        if missing or altered:
            issues_header = soup.new_tag("h3")
            issues_header["style"] = "margin: 16px 0 8px 0; font-size: 1.1em; font-weight: 500;"
            issues_header.string = "Content Issues"
            details_div.append(issues_header)

            if missing:
                missing_header = soup.new_tag("div")
                missing_header["style"] = "margin: 8px 0 4px 0; font-weight: 600;"
                missing_header.string = "Missing Content:"
                details_div.append(missing_header)

                for item in missing:
                    item_div = soup.new_tag("div")
                    item_div["style"] = (
                        "background: rgba(255,255,255,0.1); "
                        "padding: 6px 10px; "
                        "margin: 2px 0; "
                        "border-radius: 4px; "
                        "font-size: 0.9em;"
                    )
                    item_div.string = f"• {item}"
                    details_div.append(item_div)

            if altered:
                altered_header = soup.new_tag("div")
                altered_header["style"] = "margin: 12px 0 4px 0; font-weight: 600;"
                altered_header.string = "Altered Content:"
                details_div.append(altered_header)

                for item in altered:
                    item_div = soup.new_tag("div")
                    item_div["style"] = (
                        "background: rgba(255,255,255,0.1); "
                        "padding: 6px 10px; "
                        "margin: 2px 0; "
                        "border-radius: 4px; "
                        "font-size: 0.9em;"
                    )
                    item_div.string = f"• {item}"
                    details_div.append(item_div)

        verification_div.append(details_div)

        # Insert after the warnings banner (if exists) or at beginning of body
        warnings_banner = soup.find(id="conversion-warnings-summary")
        if warnings_banner:
            warnings_banner.insert_after(verification_div)
        else:
            body.insert(0, verification_div)

        logger.info(f"Added content verification report: {score:.1f}% preservation")

    def _add_conversion_warnings_summary(self, soup: BeautifulSoup, results: dict[str, Any]) -> None:
        """
        Add a conversion warnings summary banner at the top of the HTML.

        Args:
            soup: BeautifulSoup object
            results: Processing results containing warnings
        """
        conversion_warnings = results.get("conversion_warnings", [])
        if not conversion_warnings:
            return  # No warnings to display

        # Count warnings by severity
        high_severity = sum(1 for w in conversion_warnings if w.get("severity") == "high")
        medium_severity = sum(1 for w in conversion_warnings if w.get("severity") == "medium")
        low_severity = sum(1 for w in conversion_warnings if w.get("severity") == "low")

        # Create warnings summary banner
        body = soup.find("body")
        if not body:
            return

        # Create summary container
        summary_div = soup.new_tag("div", attrs={
            "id": "conversion-warnings-summary",
            "class": "conversion-summary"
        })
        summary_div["style"] = (
            "background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); "
            "color: white; "
            "padding: 20px; "
            "margin: 0 0 30px 0; "
            "border-radius: 8px; "
            "box-shadow: 0 4px 6px rgba(0,0,0,0.1); "
            "font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;"
        )

        # Create header
        header = soup.new_tag("h2")
        header["style"] = "margin: 0 0 12px 0; font-size: 1.5em; font-weight: 600;"
        header.string = f"⚠️ Conversion Report: {len(conversion_warnings)} Issue{'s' if len(conversion_warnings) != 1 else ''} Detected"
        summary_div.append(header)

        # Create summary paragraph
        summary_p = soup.new_tag("p")
        summary_p["style"] = "margin: 0 0 16px 0; font-size: 1em; opacity: 0.95;"
        summary_text = (
            f"This document was converted from LaTeX to HTML, but some elements could not be "
            f"fully preserved. "
        )
        if high_severity > 0:
            summary_text += f"{high_severity} critical issue{'s' if high_severity != 1 else ''}, "
        if medium_severity > 0:
            summary_text += f"{medium_severity} warning{'s' if medium_severity != 1 else ''}, "
        if low_severity > 0:
            summary_text += f"{low_severity} informational message{'s' if low_severity != 1 else ''}."
        summary_p.string = summary_text.rstrip(", ") + "."
        summary_div.append(summary_p)

        # Create details toggle button
        details_btn = soup.new_tag("button", attrs={
            "onclick": "document.getElementById('warnings-details').style.display = "
                      "document.getElementById('warnings-details').style.display === 'none' ? 'block' : 'none'",
            "class": "warnings-toggle-btn"
        })
        details_btn["style"] = (
            "background: rgba(255,255,255,0.2); "
            "border: 1px solid rgba(255,255,255,0.3); "
            "color: white; "
            "padding: 8px 16px; "
            "border-radius: 4px; "
            "cursor: pointer; "
            "font-size: 0.9em; "
            "font-weight: 500; "
            "transition: all 0.2s;"
        )
        details_btn.string = "📋 View Details"
        summary_div.append(details_btn)

        # Create collapsible details section
        details_div = soup.new_tag("div", attrs={"id": "warnings-details"})
        details_div["style"] = (
            "display: none; "
            "margin-top: 16px; "
            "padding-top: 16px; "
            "border-top: 1px solid rgba(255,255,255,0.2);"
        )

        # Group warnings by type
        warnings_by_type = {}
        for warning in conversion_warnings:
            warning_type = warning.get("type", "unknown")
            warnings_by_type.setdefault(warning_type, []).append(warning)

        # Add warnings grouped by type
        for warning_type, warnings_list in warnings_by_type.items():
            type_header = soup.new_tag("h3")
            type_header["style"] = "margin: 12px 0 8px 0; font-size: 1.1em; font-weight: 500;"
            type_header.string = f"{warning_type.replace('_', ' ').title()} ({len(warnings_list)})"
            details_div.append(type_header)

            for warning in warnings_list:
                warning_item = soup.new_tag("div")
                warning_item["style"] = (
                    "background: rgba(255,255,255,0.1); "
                    "padding: 8px 12px; "
                    "margin: 4px 0; "
                    "border-radius: 4px; "
                    "font-size: 0.9em;"
                )

                severity_badge = soup.new_tag("span")
                severity = warning.get("severity", "unknown")
                badge_color = {
                    "high": "#dc3545",
                    "medium": "#ffc107",
                    "low": "#17a2b8"
                }.get(severity, "#6c757d")
                severity_badge["style"] = (
                    f"background: {badge_color}; "
                    "color: white; "
                    "padding: 2px 8px; "
                    "border-radius: 3px; "
                    "font-size: 0.8em; "
                    "font-weight: 600; "
                    "margin-right: 8px;"
                )
                severity_badge.string = severity.upper()
                warning_item.append(severity_badge)

                message_span = soup.new_tag("span")
                message_span.string = warning.get("message", "Unknown warning")
                warning_item.append(message_span)

                details_div.append(warning_item)

        summary_div.append(details_div)

        # Insert at the beginning of body
        body.insert(0, summary_div)

        logger.info(f"Added conversion warnings summary banner with {len(conversion_warnings)} warnings")

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
            # Check if asset conversion should be skipped
            skip_assets = results.get("options", {}).get("skip_images", False)
            if skip_assets:
                logger.info("Skipping asset conversion (skip_images option enabled)")
                results["steps_completed"].append("asset_conversion_skipped")
                return soup
            
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

            # Find all assets first
            tikz_diagrams = self._find_tikz_diagrams(soup)
            pdf_figures = self._find_pdf_figures(soup)
            image_assets = self._find_image_assets(soup)
            
            total_assets = len(tikz_diagrams) + len(pdf_figures) + len(image_assets)
            
            if total_assets == 0:
                logger.info("No assets found to convert")
                results["steps_completed"].append("asset_conversion_skipped")
                return soup
            
            logger.info(
                "Found %d assets to convert (%d TikZ, %d PDF, %d images)",
                total_assets,
                len(tikz_diagrams),
                len(pdf_figures),
                len(image_assets),
            )
            
            # Convert assets in parallel for better performance
            # Use ThreadPoolExecutor for I/O-bound operations (file I/O, subprocess calls)
            # Note: Each conversion method writes to different parts of results dict,
            # so thread safety is maintained (no overlapping keys)
            max_workers = min(4, total_assets)  # Limit to 4 concurrent conversions
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                
                # Submit TikZ conversions
                if tikz_diagrams:
                    future = executor.submit(
                        self._convert_tikz_diagrams, tikz_diagrams, assets_dir, results
                    )
                    futures.append(("tikz", future))
                
                # Submit PDF conversions
                if pdf_figures:
                    future = executor.submit(
                        self._convert_pdf_figures, pdf_figures, assets_dir, results
                    )
                    futures.append(("pdf", future))
                
                # Submit image conversions
                if image_assets:
                    future = executor.submit(
                        self._convert_image_assets, image_assets, assets_dir, results
                    )
                    futures.append(("image", future))
                
                # Wait for all conversions to complete
                for asset_type, future in futures:
                    try:
                        future.result(timeout=600)  # 10 minute timeout per asset type
                        logger.debug(f"{asset_type} conversion completed")
                    except Exception as exc:
                        logger.error(f"{asset_type} conversion failed: {exc}")
                        # Thread-safe: each asset type uses different dict keys
                        if "errors" not in results:
                            results["errors"] = []
                        results["errors"].append(f"{asset_type} conversion error: {exc}")

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
