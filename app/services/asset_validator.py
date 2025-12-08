"""
Asset validation service for the LaTeX → HTML5 Converter.

This service handles validation and quality checks for converted assets.
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from loguru import logger

from app.exceptions import BaseServiceError, ServiceFileError


class AssetValidationError(BaseServiceError):
    """Base exception for asset validation errors."""

    def __init__(
        self, message: str, asset_file: str, details: dict[str, Any] | None = None
    ):
        super().__init__(message, "ASSET_VALIDATION_ERROR", details)
        self.asset_file = asset_file


class AssetValidationFileError(AssetValidationError, ServiceFileError):
    """Raised when asset file operations fail."""

    def __init__(self, message: str, asset_file: str):
        super().__init__(message, asset_file, {"file_path": asset_file})


class AssetValidator:
    """Service for validating and quality-checking converted assets."""

    def __init__(self):
        """Initialize the asset validator service."""
        self.max_svg_size = 5 * 1024 * 1024  # 5MB
        self.min_svg_size = 100  # 100 bytes
        self.max_dimensions = 10000  # 10000px

        logger.info("Asset validator service initialized")

    def validate_svg(
        self, svg_file: Path, options: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Validate an SVG file for quality and compliance.

        Args:
            svg_file: Path to SVG file to validate
            options: Validation options

        Returns:
            Dict containing validation results and quality metrics

        Raises:
            AssetValidationError: If validation fails
        """
        try:
            # Validate file exists and is readable
            self._validate_svg_file(svg_file)

            # Set default options
            if options is None:
                options = {}

            logger.info(f"Validating SVG: {svg_file}")

            # Read SVG content
            content = self._read_svg_content(svg_file)

            # Perform various validations
            validation_results = {
                "file_path": str(svg_file),
                "file_size": svg_file.stat().st_size,
                "validation_time": 0.0,
                "is_valid": True,
                "errors": [],
                "warnings": [],
                "quality_score": 0.0,
                "recommendations": [],
            }

            # Basic structure validation
            structure_validation = self._validate_svg_structure(content)
            validation_results.update(structure_validation)

            # Syntax validation
            syntax_validation = self._validate_svg_syntax(content)
            validation_results.update(syntax_validation)

            # Quality validation
            quality_validation = self._validate_svg_quality(content, svg_file)
            validation_results.update(quality_validation)

            # Accessibility validation
            accessibility_validation = self._validate_svg_accessibility(content)
            validation_results.update(accessibility_validation)

            # Calculate overall quality score
            validation_results["quality_score"] = self._calculate_quality_score(
                validation_results
            )

            # Determine if SVG is valid
            validation_results["is_valid"] = (
                len(validation_results["errors"]) == 0
                and validation_results["quality_score"] >= 0.7
            )

            logger.info(f"SVG validation completed: {validation_results['is_valid']}")
            return validation_results

        except AssetValidationError:
            # Re-raise our custom errors
            raise
        except Exception as exc:
            logger.error(f"Unexpected SVG validation error: {exc}")
            raise AssetValidationError(
                f"Unexpected SVG validation error: {exc}", str(svg_file)
            ) from exc

    def _validate_svg_file(self, svg_file: Path) -> None:
        """Validate the SVG input file."""
        if not svg_file.exists():
            raise AssetValidationFileError(
                f"SVG file not found: {svg_file}", str(svg_file)
            )

        if not svg_file.is_file():
            raise AssetValidationFileError(
                f"SVG path is not a file: {svg_file}", str(svg_file)
            )

        # Check file size
        file_size = svg_file.stat().st_size
        if file_size > self.max_svg_size:
            raise AssetValidationFileError(
                f"SVG file too large: {file_size} bytes (max: {self.max_svg_size})",
                str(svg_file),
            )

        if file_size < self.min_svg_size:
            raise AssetValidationFileError(
                f"SVG file too small: {file_size} bytes (min: {self.min_svg_size})",
                str(svg_file),
            )

    def _read_svg_content(self, svg_file: Path) -> str:
        """Read SVG file content."""
        try:
            with open(svg_file, encoding="utf-8") as f:
                return f.read()
        except Exception as exc:
            raise AssetValidationFileError(
                f"Cannot read SVG file: {exc}", str(svg_file)
            ) from exc

    def _validate_svg_structure(self, content: str) -> dict[str, Any]:
        """Validate SVG structure and basic requirements."""
        results = {"structure_errors": [], "structure_warnings": []}

        # Check for SVG root element
        if not re.search(r"<svg[^>]*>", content, re.IGNORECASE):
            results["structure_errors"].append("Missing SVG root element")

        # Check for proper namespace
        if "xmlns=" not in content and "xmlns:" not in content:
            results["structure_warnings"].append("Missing SVG namespace declaration")

        # Check for viewBox or width/height
        has_viewbox = "viewBox=" in content
        has_dimensions = "width=" in content and "height=" in content

        if not has_viewbox and not has_dimensions:
            results["structure_warnings"].append(
                "Missing viewBox or width/height attributes"
            )

        # Check for proper closing tags
        open_tags = re.findall(r"<([^/][^>]*?)>", content)
        close_tags = re.findall(r"</([^>]*?)>", content)

        # Simple tag balance check
        if len(open_tags) != len(close_tags):
            results["structure_warnings"].append("Potential tag imbalance")

        return results

    def _validate_svg_syntax(self, content: str) -> dict[str, Any]:
        """Validate SVG syntax and XML compliance."""
        results = {"syntax_errors": [], "syntax_warnings": []}

        try:
            # Try to parse as XML
            ET.fromstring(content)
        except ET.ParseError as exc:
            results["syntax_errors"].append(f"XML parsing error: {exc}")

        # Check for common syntax issues
        if "&" in content and "&amp;" not in content:
            results["syntax_warnings"].append("Unescaped ampersands found")

        if "<" in content and not content.startswith("<"):
            results["syntax_warnings"].append("Content before root element")

        # Check for malformed attributes
        malformed_attrs = re.findall(r'(\w+)\s*=\s*"[^"]*$', content)
        if malformed_attrs:
            results["syntax_errors"].append(f"Malformed attributes: {malformed_attrs}")

        return results

    def _validate_svg_quality(self, content: str, svg_file: Path) -> dict[str, Any]:
        """Validate SVG quality and optimization."""
        results = {"quality_errors": [], "quality_warnings": [], "quality_metrics": {}}

        # File size analysis
        file_size = svg_file.stat().st_size
        results["quality_metrics"]["file_size"] = file_size

        # Content analysis
        element_count = len(re.findall(r"<[^/][^>]*>", content))
        results["quality_metrics"]["element_count"] = element_count

        # Path analysis
        path_count = len(re.findall(r"<path[^>]*>", content))
        results["quality_metrics"]["path_count"] = path_count

        # Text analysis
        text_count = len(re.findall(r"<text[^>]*>", content))
        results["quality_metrics"]["text_count"] = text_count

        # Image analysis
        image_count = len(re.findall(r"<image[^>]*>", content))
        results["quality_metrics"]["image_count"] = image_count

        # Check for optimization opportunities
        if "<!--" in content:
            results["quality_warnings"].append(
                "Contains comments that could be removed"
            )

        if re.search(r"\s{2,}", content):
            results["quality_warnings"].append("Contains excessive whitespace")

        if "<?xml" in content:
            results["quality_warnings"].append(
                "Contains XML declaration (may be unnecessary)"
            )

        # Check for large file size
        if file_size > 1024 * 1024:  # 1MB
            results["quality_warnings"].append("Large file size may impact performance")

        # Check for complex paths
        if path_count > 100:
            results["quality_warnings"].append(
                "High number of paths may impact rendering"
            )

        return results

    def _validate_svg_accessibility(self, content: str) -> dict[str, Any]:
        """Validate SVG accessibility features."""
        results = {
            "accessibility_errors": [],
            "accessibility_warnings": [],
            "accessibility_metrics": {},
        }

        # Check for title element
        has_title = "<title>" in content
        results["accessibility_metrics"]["has_title"] = has_title
        if not has_title:
            results["accessibility_warnings"].append(
                "Missing title element for accessibility"
            )

        # Check for desc element
        has_desc = "<desc>" in content
        results["accessibility_metrics"]["has_desc"] = has_desc
        if not has_desc:
            results["accessibility_warnings"].append(
                "Missing description element for accessibility"
            )

        # Check for alt text on images
        images_without_alt = re.findall(r"<image[^>]*(?!.*alt=)[^>]*>", content)
        if images_without_alt:
            results["accessibility_warnings"].append(
                f"Images without alt text: {len(images_without_alt)}"
            )

        # Check for aria labels
        has_aria = "aria-" in content
        results["accessibility_metrics"]["has_aria"] = has_aria

        # Check for role attributes
        has_role = "role=" in content
        results["accessibility_metrics"]["has_role"] = has_role

        return results

    def _calculate_quality_score(self, validation_results: dict[str, Any]) -> float:
        """Calculate overall quality score (0.0 to 1.0)."""
        score = 1.0

        # Deduct for errors
        error_count = (
            len(validation_results.get("structure_errors", []))
            + len(validation_results.get("syntax_errors", []))
            + len(validation_results.get("quality_errors", []))
            + len(validation_results.get("accessibility_errors", []))
        )
        score -= error_count * 0.2

        # Deduct for warnings
        warning_count = (
            len(validation_results.get("structure_warnings", []))
            + len(validation_results.get("syntax_warnings", []))
            + len(validation_results.get("quality_warnings", []))
            + len(validation_results.get("accessibility_warnings", []))
        )
        score -= warning_count * 0.05

        # Bonus for good practices
        if validation_results.get("accessibility_metrics", {}).get("has_title"):
            score += 0.1
        if validation_results.get("accessibility_metrics", {}).get("has_desc"):
            score += 0.1

        return max(0.0, min(1.0, score))

    def batch_validate_svg(
        self, svg_files: list[Path], options: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        Validate multiple SVG files.

        Args:
            svg_files: List of SVG files to validate
            options: Validation options

        Returns:
            List of validation results
        """
        results = []

        for svg_file in svg_files:
            try:
                result = self.validate_svg(svg_file, options)
                results.append(result)
            except AssetValidationError as exc:
                results.append(
                    {"file_path": str(svg_file), "is_valid": False, "error": str(exc)}
                )

        return results

    def get_validation_summary(
        self, validation_results: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Get a summary of validation results.

        Args:
            validation_results: List of validation results

        Returns:
            Dict containing validation summary
        """
        total_files = len(validation_results)
        valid_files = sum(1 for r in validation_results if r.get("is_valid", False))

        total_errors = sum(
            len(r.get("structure_errors", []))
            + len(r.get("syntax_errors", []))
            + len(r.get("quality_errors", []))
            + len(r.get("accessibility_errors", []))
            for r in validation_results
        )

        total_warnings = sum(
            len(r.get("structure_warnings", []))
            + len(r.get("syntax_warnings", []))
            + len(r.get("quality_warnings", []))
            + len(r.get("accessibility_warnings", []))
            for r in validation_results
        )

        avg_quality_score = (
            sum(r.get("quality_score", 0) for r in validation_results) / total_files
            if total_files > 0
            else 0
        )

        return {
            "total_files": total_files,
            "valid_files": valid_files,
            "invalid_files": total_files - valid_files,
            "success_rate": valid_files / total_files if total_files > 0 else 0,
            "total_errors": total_errors,
            "total_warnings": total_warnings,
            "average_quality_score": avg_quality_score,
        }
