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
    from lxml.html.clean import Cleaner
    from lxml.etree import XMLSyntaxError
except ImportError:
    # Fallback for systems without lxml
    etree = None
    html = None
    Cleaner = None
    XMLSyntaxError = Exception

from app.services.assets import AssetConversionService
from app.services.asset_validator import AssetValidator


class HTMLPostProcessingError(Exception):
    """Base exception for HTML post-processing errors."""

    def __init__(self, message: str, error_type: str = "HTML_PROCESSING_ERROR", details: dict[str, Any] | None = None):
        super().__init__(message)
        self.error_type = error_type
        self.details = details or {}


class HTMLValidationError(HTMLPostProcessingError):
    """Raised when HTML validation fails."""

    def __init__(self, message: str, validation_errors: list[str]):
        super().__init__(message, "VALIDATION_ERROR", {"validation_errors": validation_errors})


class HTMLCleaningError(HTMLPostProcessingError):
    """Raised when HTML cleaning fails."""

    def __init__(self, message: str, cleaning_errors: list[str]):
        super().__init__(message, "CLEANING_ERROR", {"cleaning_errors": cleaning_errors})


class HTMLPostProcessor:
    """Service for post-processing LaTeXML HTML output."""

    def __init__(
        self, 
        base_url: str | None = None,
        asset_conversion_service: AssetConversionService | None = None,
        asset_validator: AssetValidator | None = None
    ):
        """
        Initialize HTML post-processor.
        
        Args:
            base_url: Base URL for resolving relative links
            asset_conversion_service: Service for converting assets to SVG
            asset_validator: Service for validating converted assets
        """
        self.base_url = base_url
        self.asset_conversion_service = asset_conversion_service or AssetConversionService()
        self.asset_validator = asset_validator or AssetValidator()
        self._setup_cleaner()

    def _setup_cleaner(self) -> None:
        """Set up HTML cleaner with appropriate settings."""
        if Cleaner is not None:
            self.cleaner = Cleaner(
                scripts=True,  # Remove script tags
                javascript=True,  # Remove javascript
                comments=True,  # Remove comments
                style=True,  # Remove style tags
                links=True,  # Remove links
                meta=True,  # Remove meta tags
                page_structure=True,  # Remove page structure elements
                processing_instructions=True,  # Remove processing instructions
                embedded=True,  # Remove embedded content
                frames=True,  # Remove frames
                forms=True,  # Remove forms
                annoying_tags=True,  # Remove annoying tags
                safe_attrs_only=True,  # Only keep safe attributes
                remove_unknown_tags=True,  # Remove unknown tags
            )
        else:
            self.cleaner = None

    def process_html(
        self,
        html_file: Path,
        output_file: Path | None = None,
        options: dict[str, Any] | None = None
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
            # Load HTML content
            with open(html_file, encoding='utf-8') as f:
                html_content = f.read()

            # Parse with BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')

            # Apply processing steps
            processing_results = {
                "original_size": len(html_content),
                "steps_completed": [],
                "errors": [],
                "warnings": []
            }

            # Step 1: Clean HTML
            cleaned_soup = self._clean_html(soup, processing_results)

            # Step 2: Validate HTML structure
            self._validate_html_structure(cleaned_soup, processing_results)

            # Step 3: Convert assets to SVG
            asset_converted_soup = self._convert_assets_to_svg(cleaned_soup, html_file.parent, processing_results)

            # Step 4: Enhance HTML
            enhanced_soup = self._enhance_html(asset_converted_soup, processing_results)

            # Step 5: Optimize HTML
            optimized_soup = self._optimize_html(enhanced_soup, processing_results)

            # Generate output
            if output_file:
                self._write_html(optimized_soup, output_file)
                processing_results["output_file"] = str(output_file)

            # Final statistics
            final_html = str(optimized_soup)
            processing_results.update({
                "final_size": len(final_html),
                "size_reduction": processing_results["original_size"] - len(final_html),
                "success": len(processing_results["errors"]) == 0
            })

            return processing_results

        except Exception as exc:
            logger.error("HTML post-processing failed: %s", exc)
            raise HTMLPostProcessingError(f"HTML post-processing failed: {exc}")

    def _clean_html(self, soup: BeautifulSoup, results: dict[str, Any]) -> BeautifulSoup:
        """Clean HTML content."""
        try:
            # Remove LaTeXML-specific elements
            self._remove_latexml_elements(soup)

            # Clean dangerous content
            self._clean_dangerous_content(soup)

            # Remove empty elements
            self._remove_empty_elements(soup)

            # Normalize whitespace
            self._normalize_whitespace(soup)

            results["steps_completed"].append("html_cleaning")
            return soup

        except Exception as exc:
            error_msg = f"HTML cleaning failed: {exc}"
            results["errors"].append(error_msg)
            logger.error(error_msg)
            return soup

    def _remove_latexml_elements(self, soup: BeautifulSoup) -> None:
        """Remove LaTeXML-specific elements."""
        # Remove LaTeXML processing instructions
        for pi in soup.find_all(string=lambda text: isinstance(text, NavigableString) and text.strip().startswith('<?')):
            pi.extract()

        # Remove LaTeXML-specific attributes
        for tag in soup.find_all():
            if tag.attrs:
                # Remove LaTeXML-specific attributes
                latexml_attrs = [attr for attr in tag.attrs.keys() if attr.startswith('latexml')]
                for attr in latexml_attrs:
                    del tag.attrs[attr]

    def _clean_dangerous_content(self, soup: BeautifulSoup) -> None:
        """Remove potentially dangerous content."""
        # Remove script tags
        for script in soup.find_all('script'):
            script.decompose()

        # Remove style tags with potentially dangerous content
        for style in soup.find_all('style'):
            if 'javascript:' in str(style.string).lower():
                style.decompose()

        # Remove onclick and similar event handlers
        for tag in soup.find_all():
            if tag.attrs:
                dangerous_attrs = ['onclick', 'onload', 'onerror', 'onmouseover', 'onfocus']
                for attr in dangerous_attrs:
                    if attr in tag.attrs:
                        del tag.attrs[attr]

    def _remove_empty_elements(self, soup: BeautifulSoup) -> None:
        """Remove empty elements that don't add value."""
        empty_tags = ['span', 'div', 'p']

        for tag_name in empty_tags:
            for tag in soup.find_all(tag_name):
                if not tag.get_text(strip=True) and not tag.find_all():
                    tag.decompose()

    def _normalize_whitespace(self, soup: BeautifulSoup) -> None:
        """Normalize whitespace in text content while preserving meaningful formatting."""
        for text_node in soup.find_all(string=True):
            if isinstance(text_node, NavigableString):
                # Skip whitespace normalization in contexts where it's significant
                parent = text_node.parent
                if parent and parent.name in ['pre', 'code', 'textarea', 'script', 'style']:
                    continue

                # Skip if this is whitespace between inline elements (preserves word separation)
                if text_node.strip() == '' and parent and parent.name in ['p', 'div', 'span', 'em', 'strong', 'a']:
                    # Only collapse multiple spaces/tabs to single space, don't strip
                    normalized = re.sub(r'[ \t]+', ' ', text_node)
                    if normalized != text_node:
                        text_node.replace_with(normalized)
                    continue

                # For other text nodes, normalize but preserve word boundaries
                if text_node.strip():  # Only process non-empty text nodes
                    # Collapse multiple whitespace to single space, but preserve leading/trailing if meaningful
                    normalized = re.sub(r'[ \t\n\r]+', ' ', text_node)
                    # Only strip if the original was mostly whitespace
                    if len(text_node.strip()) / len(text_node) < 0.3:  # Less than 30% actual content
                        normalized = normalized.strip()
                    text_node.replace_with(normalized)

    def _validate_html_structure(self, soup: BeautifulSoup, results: dict[str, Any]) -> None:
        """Validate HTML structure."""
        try:
            validation_errors = []

            # Check for required elements
            if not soup.find('html'):
                validation_errors.append("Missing <html> element")

            if not soup.find('head'):
                validation_errors.append("Missing <head> element")

            if not soup.find('body'):
                validation_errors.append("Missing <body> element")

            # Check for proper nesting
            self._validate_nesting(soup, validation_errors)

            # Check for accessibility issues
            self._validate_accessibility(soup, validation_errors)

            if validation_errors:
                results["warnings"].extend(validation_errors)
            else:
                results["steps_completed"].append("html_validation")

        except Exception as exc:
            error_msg = f"HTML validation failed: {exc}"
            results["errors"].append(error_msg)

    def _validate_nesting(self, soup: BeautifulSoup, errors: list[str]) -> None:
        """Validate proper HTML nesting."""
        # Check for invalid nesting (e.g., <p> inside <p>)
        for p_tag in soup.find_all('p'):
            if p_tag.find('p'):
                errors.append("Invalid nesting: <p> inside <p>")

    def _validate_accessibility(self, soup: BeautifulSoup, errors: list[str]) -> None:
        """Validate accessibility features."""
        # Check for images without alt text
        for img in soup.find_all('img'):
            if not img.get('alt'):
                errors.append(f"Image missing alt text: {img.get('src', 'unknown')}")

        # Check for headings structure
        headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        if headings:
            # Check for proper heading hierarchy
            prev_level = 0
            for heading in headings:
                level = int(heading.name[1])
                if level > prev_level + 1:
                    errors.append(f"Invalid heading hierarchy: {heading.name} after h{prev_level}")
                prev_level = level

    def _enhance_html(self, soup: BeautifulSoup, results: dict[str, Any]) -> BeautifulSoup:
        """Enhance HTML with additional features."""
        try:
            # Process mathematical expressions for MathJax compatibility
            self._process_math_expressions(soup)
            
            # Add MathJax support if math is present
            if soup.find(['math', 'm:math']) or soup.find_all(['span', 'div'], class_=['math', 'math-display']):
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

    def _add_mathjax_support(self, soup: BeautifulSoup) -> None:
        """Add MathJax support for math rendering."""
        head = soup.find('head')
        if head:
            # Add MathJax 3.x configuration
            mathjax_config = soup.new_tag('script', attrs={'type': 'text/x-mathjax-config'})
            mathjax_config.string = '''
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
            '''
            head.append(mathjax_config)

            # Add MathJax 3.x script
            mathjax_script = soup.new_tag('script', attrs={'src': 'https://polyfill.io/v3/polyfill.min.js?features=es6'})
            head.append(mathjax_script)
            
            mathjax_main = soup.new_tag('script', attrs={'id': 'MathJax-script', 'async': True, 'src': 'https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js'})
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
            if '$' not in text:
                continue
                
            parts = text.split('$')
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
                    math_span = soup.new_tag('span', attrs={'class': 'math'})
                    math_span.string = f'${part}$'
                    new_content.append(math_span)
        return new_content

    def _process_display_math(self, soup: BeautifulSoup) -> None:
        """Process display math expressions ($$...$$)."""
        for p in soup.find_all('p'):
            text = p.get_text()
            if '$$' not in text:
                continue
                
            parts = text.split('$$')
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
                    math_div = soup.new_tag('div', attrs={'class': 'math-display'})
                    math_div.string = f'$${part}$$'
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
        for link in soup.find_all('a'):
            href = link.get('href')
            if href:
                # Add target="_blank" for external links
                if self._is_external_link(href):
                    link['target'] = '_blank'
                    link['rel'] = 'noopener noreferrer'

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
        head = soup.find('head')
        if head and not head.find('meta', attrs={'name': 'viewport'}):
            viewport_meta = soup.new_tag('meta', attrs={'name': 'viewport', 'content': 'width=device-width, initial-scale=1.0'})
            head.append(viewport_meta)

    def _add_enhancement_css(self, soup: BeautifulSoup) -> None:
        """Add CSS for better styling."""
        head = soup.find('head')
        if head:
            style = soup.new_tag('style', attrs={'type': 'text/css'})
            style.string = '''
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
            .math { font-family: "Times New Roman", serif; }
            img { max-width: 100%; height: auto; }
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            '''
            head.append(style)

    def _optimize_html(self, soup: BeautifulSoup, results: dict[str, Any]) -> BeautifulSoup:
        """Optimize HTML for better performance."""
        try:
            # Minify HTML (basic)
            self._minify_html(soup)

            # Optimize images
            self._optimize_images(soup)

            # Remove unnecessary attributes
            self._remove_unnecessary_attributes(soup)

            results["steps_completed"].append("html_optimization")
            return soup

        except Exception as exc:
            error_msg = f"HTML optimization failed: {exc}"
            results["errors"].append(error_msg)
            logger.error(error_msg)
            return soup

    def _minify_html(self, soup: BeautifulSoup) -> None:
        """Basic HTML minification."""
        # Remove unnecessary whitespace
        for text_node in soup.find_all(string=True):
            if isinstance(text_node, NavigableString):
                # Remove leading/trailing whitespace
                text_node.replace_with(text_node.strip())

    def _optimize_images(self, soup: BeautifulSoup) -> None:
        """Optimize image tags."""
        for img in soup.find_all('img'):
            # Add loading="lazy" for performance
            if not img.get('loading'):
                img['loading'] = 'lazy'

    def _convert_assets_to_svg(self, soup: BeautifulSoup, html_dir: Path, results: dict[str, Any]) -> BeautifulSoup:
        """Convert assets (TikZ, PDF) to SVG format."""
        try:
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
        for tikz in soup.find_all('div', class_='tikzpicture'):
            tikz_diagrams.append({
                'element': tikz,
                'type': 'tikz',
                'content': tikz.get_text(),
                'id': tikz.get('id', ''),
                'class': tikz.get('class', [])
            })
        
        # Look for LaTeX tikz environments
        for tikz in soup.find_all('div', attrs={'data-latexml': True}):
            if 'tikz' in str(tikz.get('class', [])).lower():
                tikz_diagrams.append({
                    'element': tikz,
                    'type': 'tikz',
                    'content': tikz.get_text(),
                    'id': tikz.get('id', ''),
                    'class': tikz.get('class', [])
                })
        
        return tikz_diagrams

    def _find_pdf_figures(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """Find PDF figures in the HTML."""
        pdf_figures = []
        
        # Look for PDF links
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            if href.lower().endswith('.pdf'):
                pdf_figures.append({
                    'element': link,
                    'type': 'pdf',
                    'href': href,
                    'id': link.get('id', ''),
                    'class': link.get('class', [])
                })
        
        # Look for embedded PDF objects
        for obj in soup.find_all('object', attrs={'data': True}):
            data = obj.get('data', '')
            if data.lower().endswith('.pdf'):
                pdf_figures.append({
                    'element': obj,
                    'type': 'pdf',
                    'href': data,
                    'id': obj.get('id', ''),
                    'class': obj.get('class', [])
                })
        
        return pdf_figures

    def _find_image_assets(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """Find image assets that could be converted to SVG."""
        image_assets = []
        
        # Look for images
        for img in soup.find_all('img', src=True):
            src = img.get('src', '')
            # Only convert certain image types
            if src.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                image_assets.append({
                    'element': img,
                    'type': 'image',
                    'src': src,
                    'id': img.get('id', ''),
                    'class': img.get('class', [])
                })
        
        return image_assets

    def _convert_tikz_diagrams(self, tikz_diagrams: list[dict[str, Any]], assets_dir: Path, results: dict[str, Any]) -> None:
        """Convert TikZ diagrams to SVG."""
        try:
            for i, tikz in enumerate(tikz_diagrams):
                # Create temporary TikZ file
                tikz_file = assets_dir / f"tikz_diagram_{i}.tex"
                with open(tikz_file, 'w', encoding='utf-8') as f:
                    f.write(f"\\documentclass{{standalone}}\n\\usepackage{{tikz}}\n\\begin{{document}}\n{tikz['content']}\n\\end{{document}}")
                
                # Convert to SVG
                conversion_result = self.asset_conversion_service.convert_assets(
                    assets_dir,
                    assets_dir,
                    asset_types=["tikz"],
                    options={"timeout": 300}
                )
                
                if conversion_result.get("success"):
                    # Get the actual output file from conversion result
                    output_file = conversion_result.get("output_file")
                    if output_file and Path(output_file).exists():
                        svg_file = Path(output_file)
                        self._replace_element_with_svg(tikz['element'], svg_file)
                        results.setdefault("converted_assets", []).append({
                            "type": "tikz",
                            "original": tikz['id'],
                            "svg_file": str(svg_file),
                            "success": True
                        })
                    else:
                        # Fallback: try the expected filename pattern with _wrapper suffix
                        svg_file = assets_dir / f"tikz_diagram_{i}_wrapper.svg"
                        if svg_file.exists():
                            self._replace_element_with_svg(tikz['element'], svg_file)
                            results.setdefault("converted_assets", []).append({
                                "type": "tikz",
                                "original": tikz['id'],
                                "svg_file": str(svg_file),
                                "success": True
                            })
                else:
                    results.setdefault("failed_assets", []).append({
                        "type": "tikz",
                        "original": tikz['id'],
                        "error": "Conversion failed"
                    })
                    
        except Exception as exc:
            logger.error("TikZ conversion failed: %s", exc)
            results.setdefault("failed_assets", []).append({
                "type": "tikz",
                "error": str(exc)
            })

    def _convert_pdf_figures(self, pdf_figures: list[dict[str, Any]], assets_dir: Path, results: dict[str, Any]) -> None:
        """Convert PDF figures to SVG."""
        try:
            for i, pdf in enumerate(pdf_figures):
                # Download or copy PDF file
                pdf_file = assets_dir / f"pdf_figure_{i}.pdf"
                # TODO: Implement PDF file handling
                
                # Convert to SVG
                conversion_result = self.asset_conversion_service.convert_assets(
                    assets_dir,
                    assets_dir,
                    asset_types=["pdf"],
                    options={"timeout": 300}
                )
                
                if conversion_result.get("success"):
                    # Replace PDF element with SVG
                    svg_file = assets_dir / f"pdf_figure_{i}.svg"
                    if svg_file.exists():
                        self._replace_element_with_svg(pdf['element'], svg_file)
                        results.setdefault("converted_assets", []).append({
                            "type": "pdf",
                            "original": pdf['id'],
                            "svg_file": str(svg_file),
                            "success": True
                        })
                else:
                    results.setdefault("failed_assets", []).append({
                        "type": "pdf",
                        "original": pdf['id'],
                        "error": "Conversion failed"
                    })
                    
        except Exception as exc:
            logger.error("PDF conversion failed: %s", exc)
            results.setdefault("failed_assets", []).append({
                "type": "pdf",
                "error": str(exc)
            })

    def _convert_image_assets(self, image_assets: list[dict[str, Any]], assets_dir: Path, results: dict[str, Any]) -> None:
        """Convert image assets to SVG (placeholder for future implementation)."""
        # TODO: Implement image to SVG conversion
        logger.info("Image to SVG conversion not yet implemented for %d assets", len(image_assets))

    def _replace_element_with_svg(self, element, svg_file: Path) -> None:
        """Replace an HTML element with an SVG element."""
        try:
            # Read SVG content
            with open(svg_file, 'r', encoding='utf-8') as f:
                svg_content = f.read()
            
            # Create new SVG element
            new_svg = BeautifulSoup(svg_content, 'html.parser').find('svg')
            if new_svg:
                # Preserve original attributes
                for attr in ['id', 'class', 'style']:
                    if element.get(attr):
                        new_svg[attr] = element.get(attr)
                
                # Replace the element
                element.replace_with(new_svg)
                
        except Exception as exc:
            logger.error("Failed to replace element with SVG: %s", exc)

    def _remove_unnecessary_attributes(self, soup: BeautifulSoup) -> None:
        """Remove unnecessary attributes while preserving namespace declarations."""
        # Only remove LaTeXML-specific attributes, preserve XML namespaces
        latexml_attrs = ['data-latexml']

        for tag in soup.find_all():
            if tag.attrs:
                # Remove LaTeXML-specific attributes
                for attr in latexml_attrs:
                    if attr in tag.attrs:
                        del tag.attrs[attr]

                # Only remove xml:space if it's not in MathML/SVG context
                if 'xml:space' in tag.attrs:
                    # Check if this is a MathML or SVG element that needs xml:space
                    if tag.name not in ['math', 'm:math', 'svg', 'g', 'path', 'circle', 'rect']:
                        del tag.attrs['xml:space']

    def _write_html(self, soup: BeautifulSoup, output_file: Path) -> None:
        """Write HTML to file."""
        try:
            output_file.parent.mkdir(parents=True, exist_ok=True)

            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(str(soup.prettify()))

        except Exception as exc:
            raise HTMLPostProcessingError(f"Failed to write HTML file: {exc}")

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
            with open(html_file, encoding='utf-8') as f:
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
            soup = BeautifulSoup(html_content, 'html.parser')

            # Check for required elements
            has_html = bool(soup.find('html'))
            has_head = bool(soup.find('head'))
            has_body = bool(soup.find('body'))

            return {
                "is_valid": is_valid,
                "validation_errors": validation_errors,
                "has_html": has_html,
                "has_head": has_head,
                "has_body": has_body,
                "file_size": len(html_content),
                "element_count": len(soup.find_all()),
                "text_length": len(soup.get_text())
            }

        except Exception as exc:
            raise HTMLPostProcessingError(f"HTML validation failed: {exc}")
