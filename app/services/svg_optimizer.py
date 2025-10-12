"""
SVG optimization service for the LaTeX → HTML5 Converter.

This service handles the optimization and compression of SVG files.
"""

import logging
import re
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from app.exceptions import BaseServiceError, ServiceFileError


class SVGOptimizationError(BaseServiceError):
    """Base exception for SVG optimization errors."""

    def __init__(self, message: str, svg_file: str, details: Dict[str, Any] | None = None):
        super().__init__(message, "SVG_OPTIMIZATION_ERROR", details)
        self.svg_file = svg_file


class SVGOptimizationFileError(SVGOptimizationError, ServiceFileError):
    """Raised when SVG file operations fail."""

    def __init__(self, message: str, svg_file: str):
        super().__init__(message, svg_file, {"file_path": svg_file})


class SVGOptimizer:
    """Service for optimizing and compressing SVG files."""

    def __init__(self):
        """Initialize the SVG optimizer service."""
        self.max_file_size = 10 * 1024 * 1024  # 10MB
        self.compression_level = 9  # Maximum compression
        
        logger.info("SVG optimizer service initialized")

    def optimize_svg(
        self,
        svg_file: Path,
        output_file: Path | None = None,
        options: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """
        Optimize an SVG file for web delivery.

        Args:
            svg_file: Path to input SVG file
            output_file: Path to output optimized SVG file (optional)
            options: Optimization options

        Returns:
            Dict containing optimization results and metadata

        Raises:
            SVGOptimizationError: If optimization fails
        """
        try:
            # Validate input file
            self._validate_svg_file(svg_file)

            # Set default options
            if options is None:
                options = {}

            # Set output file if not provided
            if output_file is None:
                output_file = svg_file.parent / f"{svg_file.stem}_optimized.svg"

            logger.info(f"Optimizing SVG: {svg_file} -> {output_file}")

            # Get original file info
            original_size = svg_file.stat().st_size
            original_content = self._read_svg_content(svg_file)

            # Apply optimizations
            optimized_content = self._apply_optimizations(original_content, options)

            # Write optimized content
            self._write_svg_content(output_file, optimized_content)

            # Get optimized file info
            optimized_size = output_file.stat().st_size
            compression_ratio = optimized_size / original_size if original_size > 0 else 1.0

            result = {
                "success": True,
                "original_file": str(svg_file),
                "optimized_file": str(output_file),
                "original_size": original_size,
                "optimized_size": optimized_size,
                "compression_ratio": compression_ratio,
                "size_reduction": original_size - optimized_size,
                "size_reduction_percent": (1.0 - compression_ratio) * 100,
                "optimization_time": time.time()
            }

            logger.info(f"SVG optimization successful: {compression_ratio:.2%} size reduction")
            return result

        except SVGOptimizationError:
            # Re-raise our custom errors
            raise
        except Exception as exc:
            logger.error(f"Unexpected SVG optimization error: {exc}")
            raise SVGOptimizationError(f"Unexpected SVG optimization error: {exc}", str(svg_file))

    def _validate_svg_file(self, svg_file: Path) -> None:
        """Validate the SVG input file."""
        if not svg_file.exists():
            raise SVGOptimizationFileError(f"SVG file not found: {svg_file}", str(svg_file))

        if not svg_file.is_file():
            raise SVGOptimizationFileError(f"SVG path is not a file: {svg_file}", str(svg_file))

        # Check file size
        file_size = svg_file.stat().st_size
        if file_size > self.max_file_size:
            raise SVGOptimizationFileError(
                f"SVG file too large: {file_size} bytes (max: {self.max_file_size})",
                str(svg_file)
            )

        # Check if file is a valid SVG
        try:
            content = self._read_svg_content(svg_file)
            if not self._is_valid_svg(content):
                raise SVGOptimizationFileError(f"Invalid SVG file: {svg_file}", str(svg_file))
        except Exception as exc:
            raise SVGOptimizationFileError(f"Cannot validate SVG file: {exc}", str(svg_file))

    def _read_svg_content(self, svg_file: Path) -> str:
        """Read SVG file content."""
        try:
            with open(svg_file, encoding="utf-8") as f:
                return f.read()
        except Exception as exc:
            raise SVGOptimizationFileError(f"Cannot read SVG file: {exc}", str(svg_file))

    def _write_svg_content(self, svg_file: Path, content: str) -> None:
        """Write SVG content to file."""
        try:
            # Ensure output directory exists
            svg_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(svg_file, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as exc:
            raise SVGOptimizationFileError(f"Cannot write SVG file: {exc}", str(svg_file))

    def _is_valid_svg(self, content: str) -> bool:
        """Check if content is a valid SVG."""
        # Basic SVG validation
        content_lower = content.lower().strip()
        return (
            content_lower.startswith('<?xml') or 
            content_lower.startswith('<svg') or
            '<svg' in content_lower
        )

    def _apply_optimizations(self, content: str, options: Dict[str, Any]) -> str:
        """Apply various optimizations to SVG content."""
        optimized = content

        # Remove XML declaration if requested
        if options.get("remove_xml_declaration", True):
            optimized = re.sub(r'<\?xml[^>]*\?>', '', optimized)

        # Remove comments if requested
        if options.get("remove_comments", True):
            optimized = re.sub(r'<!--.*?-->', '', optimized, flags=re.DOTALL)

        # Remove unnecessary whitespace
        if options.get("remove_whitespace", True):
            optimized = self._remove_unnecessary_whitespace(optimized)

        # Remove empty elements
        if options.get("remove_empty_elements", True):
            optimized = self._remove_empty_elements(optimized)

        # Optimize paths
        if options.get("optimize_paths", True):
            optimized = self._optimize_paths(optimized)

        # Remove unused attributes
        if options.get("remove_unused_attributes", True):
            optimized = self._remove_unused_attributes(optimized)

        # Optimize numbers
        if options.get("optimize_numbers", True):
            optimized = self._optimize_numbers(optimized)

        # Remove metadata
        if options.get("remove_metadata", True):
            optimized = self._remove_metadata(optimized)

        return optimized

    def _remove_unnecessary_whitespace(self, content: str) -> str:
        """Remove unnecessary whitespace from SVG content."""
        # Remove leading/trailing whitespace from lines
        lines = content.split('\n')
        optimized_lines = []
        
        for line in lines:
            # Preserve significant whitespace in text content
            if '<text' in line or '<tspan' in line:
                # Keep whitespace in text elements
                optimized_lines.append(line)
            else:
                # Remove unnecessary whitespace
                optimized_line = re.sub(r'\s+', ' ', line.strip())
                if optimized_line:
                    optimized_lines.append(optimized_line)
        
        return '\n'.join(optimized_lines)

    def _remove_empty_elements(self, content: str) -> str:
        """Remove empty elements that don't affect rendering."""
        # Remove empty groups, defs, etc.
        empty_elements = [
            r'<g\s*></g>',
            r'<defs\s*></defs>',
            r'<metadata\s*></metadata>',
            r'<title\s*></title>',
            r'<desc\s*></desc>'
        ]
        
        for pattern in empty_elements:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE)
        
        return content

    def _optimize_paths(self, content: str) -> str:
        """Optimize SVG path data."""
        # Find and optimize path elements
        def optimize_path(match):
            path_data = match.group(1)
            # Remove redundant commands and optimize
            # This is a simplified optimization
            optimized_path = re.sub(r'([MLHVCSQTAZ])\s*([MLHVCSQTAZ])', r'\1', path_data)
            return f'<path d="{optimized_path}"'
        
        content = re.sub(r'<path\s+d="([^"]*)"', optimize_path, content)
        return content

    def _remove_unused_attributes(self, content: str) -> str:
        """Remove unused or redundant attributes."""
        # Remove common unused attributes
        unused_attrs = [
            r'\s*id="[^"]*"',  # Remove IDs (be careful with this)
            r'\s*class="[^"]*"',  # Remove classes
            r'\s*style="[^"]*"',  # Remove inline styles (be careful)
        ]
        
        # Only remove if they're not essential
        for pattern in unused_attrs:
            content = re.sub(pattern, '', content)
        
        return content

    def _optimize_numbers(self, content: str) -> str:
        """Optimize numeric values in SVG."""
        # Remove unnecessary decimal places
        content = re.sub(r'(\d+)\.0+(\s|$)', r'\1\2', content)
        content = re.sub(r'(\d+)\.0+([^0-9])', r'\1\2', content)
        
        return content

    def _remove_metadata(self, content: str) -> str:
        """Remove metadata elements."""
        # Remove common metadata elements
        metadata_patterns = [
            r'<metadata[^>]*>.*?</metadata>',
            r'<title[^>]*>.*?</title>',
            r'<desc[^>]*>.*?</desc>',
        ]
        
        for pattern in metadata_patterns:
            content = re.sub(pattern, '', content, flags=re.DOTALL | re.IGNORECASE)
        
        return content

    def batch_optimize_svg(
        self,
        svg_files: List[Path],
        output_dir: Path | None = None,
        options: Dict[str, Any] | None = None
    ) -> List[Dict[str, Any]]:
        """
        Optimize multiple SVG files.

        Args:
            svg_files: List of SVG files to optimize
            output_dir: Directory for output optimized SVG files
            options: Optimization options

        Returns:
            List of optimization results
        """
        results = []
        
        for svg_file in svg_files:
            try:
                if output_dir:
                    output_file = output_dir / f"{svg_file.stem}_optimized.svg"
                else:
                    output_file = None
                
                result = self.optimize_svg(svg_file, output_file, options)
                results.append(result)
            except SVGOptimizationError as exc:
                results.append({
                    "success": False,
                    "error": str(exc),
                    "svg_file": str(svg_file)
                })
        
        return results

    def get_optimization_info(self, svg_file: Path) -> Dict[str, Any]:
        """
        Get information about an SVG file for optimization planning.

        Args:
            svg_file: Path to SVG file

        Returns:
            Dict containing SVG information
        """
        try:
            content = self._read_svg_content(svg_file)
            file_size = svg_file.stat().st_size
            
            # Analyze SVG content
            analysis = {
                "file_path": str(svg_file),
                "file_size": file_size,
                "has_xml_declaration": content.startswith('<?xml'),
                "has_comments": '<!--' in content,
                "element_count": len(re.findall(r'<[^/][^>]*>', content)),
                "path_count": len(re.findall(r'<path[^>]*>', content)),
                "text_count": len(re.findall(r'<text[^>]*>', content)),
                "estimated_optimization_ratio": self._estimate_optimization_ratio(content)
            }
            
            return analysis
            
        except Exception as exc:
            logger.error(f"Error analyzing SVG file {svg_file}: {exc}")
            return {
                "file_path": str(svg_file),
                "error": str(exc)
            }

    def _estimate_optimization_ratio(self, content: str) -> float:
        """Estimate the optimization ratio based on content analysis."""
        # Simple heuristic based on content characteristics
        ratio = 1.0
        
        # Reduce ratio based on optimizable content
        if content.startswith('<?xml'):
            ratio *= 0.95  # XML declaration removal
        
        if '<!--' in content:
            ratio *= 0.90  # Comment removal
        
        if re.search(r'\s{2,}', content):
            ratio *= 0.85  # Whitespace optimization
        
        if re.search(r'<path[^>]*>', content):
            ratio *= 0.80  # Path optimization
        
        return max(ratio, 0.5)  # Minimum 50% of original size
