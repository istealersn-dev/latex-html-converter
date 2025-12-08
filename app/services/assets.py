"""
Asset conversion service for the LaTeX → HTML5 Converter.

This service orchestrates the conversion of TikZ diagrams and PDF figures to SVG format.
"""

import time
from pathlib import Path
from typing import Any

from loguru import logger

from app.exceptions import BaseServiceError, ServiceFileError, ServiceTimeoutError
from app.services.pdf import PDFConversionError, PDFConversionService
from app.services.svg_optimizer import SVGOptimizer
from app.services.tikz import TikZConversionError, TikZConversionService
from app.utils.fs import cleanup_directory, ensure_directory


class AssetConversionError(BaseServiceError):
    """Base exception for asset conversion errors."""

    def __init__(
        self, message: str, asset_type: str, details: dict[str, Any] | None = None
    ):
        super().__init__(message, "ASSET_CONVERSION_ERROR", details)
        self.asset_type = asset_type


class AssetConversionTimeoutError(AssetConversionError, ServiceTimeoutError):
    """Raised when asset conversion times out."""

    def __init__(self, timeout: int, asset_type: str):
        super().__init__(
            f"Asset conversion timed out after {timeout} seconds",
            asset_type,
            {"timeout": timeout},
        )


class AssetConversionFileError(AssetConversionError, ServiceFileError):
    """Raised when asset file operations fail."""

    def __init__(self, message: str, asset_type: str, file_path: str):
        super().__init__(message, asset_type, {"file_path": file_path})


class AssetConversionService:
    """Main asset conversion orchestrator service."""

    def __init__(
        self,
        tikz_service: TikZConversionService | None = None,
        pdf_service: PDFConversionService | None = None,
        svg_optimizer: SVGOptimizer | None = None,
    ):
        """
        Initialize the asset conversion service.

        Args:
            tikz_service: TikZ conversion service instance
            pdf_service: PDF conversion service instance
            svg_optimizer: SVG optimization service instance
        """
        from app.config import settings

        self.tikz_service = tikz_service or TikZConversionService(
            dvisvgm_path=settings.DVISVGM_PATH, tectonic_path=settings.PDFLATEX_PATH
        )
        self.pdf_service = pdf_service or PDFConversionService(
            gs_path="/usr/bin/gs",  # Docker path for ghostscript
            pdfinfo_path="/usr/bin/pdfinfo",  # Docker path for pdfinfo
            pdftoppm_path="/usr/bin/pdftoppm",  # Docker path for pdftoppm
        )
        self.svg_optimizer = svg_optimizer or SVGOptimizer()

        # Configuration
        self.max_concurrent_conversions = 3
        self.default_timeout = 300  # 5 minutes
        self.cleanup_delay = 3600  # 1 hour

        # Active conversions tracking
        self._active_conversions: dict[str, dict[str, Any]] = {}

        logger.info("Asset conversion service initialized")

    def convert_assets(
        self,
        input_dir: Path,
        output_dir: Path,
        asset_types: list[str] | None = None,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Convert all assets in the input directory to SVG format.

        Args:
            input_dir: Directory containing source assets
            output_dir: Directory for converted SVG assets
            asset_types: Types of assets to convert (tikz, pdf, etc.)
            options: Conversion options

        Returns:
            Dict containing conversion results and metadata

        Raises:
            AssetConversionError: If conversion fails
        """
        try:
            # Validate input directory
            if not input_dir.exists():
                raise AssetConversionFileError(
                    f"Input directory not found: {input_dir}",
                    "directory",
                    str(input_dir),
                )

            if not input_dir.is_dir():
                raise AssetConversionFileError(
                    f"Input path is not a directory: {input_dir}",
                    "directory",
                    str(input_dir),
                )

            # Ensure output directory exists
            ensure_directory(output_dir)

            # Set default asset types if not specified
            if asset_types is None:
                asset_types = ["tikz", "pdf"]

            # Set default options
            if options is None:
                options = {}

            logger.info(f"Starting asset conversion: {input_dir} -> {output_dir}")
            logger.debug(f"Asset types: {asset_types}")
            logger.debug(f"Options: {options}")

            # Discover assets
            assets = self._discover_assets(input_dir, asset_types)
            logger.info(f"Found {len(assets)} assets to convert")

            if not assets:
                logger.warning("No assets found for conversion")
                return {
                    "success": True,
                    "converted_assets": [],
                    "total_assets": 0,
                    "conversion_time": 0.0,
                    "output_directory": str(output_dir),
                }

            # Convert assets
            start_time = time.time()
            conversion_results = self._convert_assets_batch(assets, output_dir, options)
            conversion_time = time.time() - start_time

            # Generate summary
            successful_conversions = [
                r for r in conversion_results if r.get("success", False)
            ]
            failed_conversions = [
                r for r in conversion_results if not r.get("success", False)
            ]

            result = {
                "success": len(failed_conversions) == 0,
                "converted_assets": successful_conversions,
                "failed_assets": failed_conversions,
                "total_assets": len(assets),
                "successful_conversions": len(successful_conversions),
                "failed_conversions": len(failed_conversions),
                "conversion_time": conversion_time,
                "output_directory": str(output_dir),
            }

            logger.info(
                f"Asset conversion completed: "
                f"{len(successful_conversions)}/{len(assets)} successful"
            )
            if failed_conversions:
                logger.warning(f"Failed conversions: {len(failed_conversions)}")

            return result

        except AssetConversionError:
            # Re-raise our custom errors
            raise
        except Exception as exc:
            logger.error(f"Unexpected asset conversion error: {exc}")
            raise AssetConversionError(
                f"Unexpected asset conversion error: {exc}", "unknown"
            ) from exc

    def _discover_assets(
        self, input_dir: Path, asset_types: list[str]
    ) -> list[dict[str, Any]]:
        """
        Discover assets in the input directory.

        Args:
            input_dir: Directory to search for assets
            asset_types: Types of assets to look for

        Returns:
            List of discovered assets with metadata
        """
        assets = []

        for asset_type in asset_types:
            if asset_type == "tikz":
                tikz_assets = self._discover_tikz_assets(input_dir)
                assets.extend(tikz_assets)
            elif asset_type == "pdf":
                pdf_assets = self._discover_pdf_assets(input_dir)
                assets.extend(pdf_assets)

        return assets

    def _discover_tikz_assets(self, input_dir: Path) -> list[dict[str, Any]]:
        """Discover TikZ assets in the input directory."""
        tikz_assets = []

        # Look for .tex files that might contain TikZ
        for tex_file in input_dir.rglob("*.tex"):
            try:
                with open(tex_file, encoding="utf-8") as f:
                    content = f.read()
                    if "\\begin{tikzpicture}" in content or "tikz" in content.lower():
                        tikz_assets.append(
                            {
                                "type": "tikz",
                                "source_file": tex_file,
                                "relative_path": tex_file.relative_to(input_dir),
                                "size": tex_file.stat().st_size,
                                "modified": tex_file.stat().st_mtime,
                            }
                        )
            except Exception as exc:
                logger.warning(f"Could not read TikZ file {tex_file}: {exc}")

        return tikz_assets

    def _discover_pdf_assets(self, input_dir: Path) -> list[dict[str, Any]]:
        """Discover PDF assets in the input directory."""
        pdf_assets = []

        # Look for .pdf files
        for pdf_file in input_dir.rglob("*.pdf"):
            try:
                pdf_assets.append(
                    {
                        "type": "pdf",
                        "source_file": pdf_file,
                        "relative_path": pdf_file.relative_to(input_dir),
                        "size": pdf_file.stat().st_size,
                        "modified": pdf_file.stat().st_mtime,
                    }
                )
            except Exception as exc:
                logger.warning(f"Could not read PDF file {pdf_file}: {exc}")

        return pdf_assets

    def _convert_assets_batch(
        self, assets: list[dict[str, Any]], output_dir: Path, options: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Convert a batch of assets to SVG.

        Args:
            assets: List of assets to convert
            output_dir: Output directory for SVG files
            options: Conversion options

        Returns:
            List of conversion results
        """
        results = []

        for asset in assets:
            try:
                logger.info(f"Converting {asset['type']} asset: {asset['source_file']}")

                if asset["type"] == "tikz":
                    result = self._convert_tikz_asset(asset, output_dir, options)
                elif asset["type"] == "pdf":
                    result = self._convert_pdf_asset(asset, output_dir, options)
                else:
                    result = {
                        "success": False,
                        "error": f"Unknown asset type: {asset['type']}",
                        "asset": asset,
                    }

                results.append(result)

            except Exception as exc:
                logger.error(f"Error converting asset {asset['source_file']}: {exc}")
                results.append({"success": False, "error": str(exc), "asset": asset})

        return results

    def _convert_tikz_asset(
        self, asset: dict[str, Any], output_dir: Path, options: dict[str, Any]
    ) -> dict[str, Any]:
        """Convert a TikZ asset to SVG."""
        try:
            # Use TikZ service to convert
            result = self.tikz_service.convert_tikz_to_svg(
                asset["source_file"], output_dir, options
            )

            return {
                "success": True,
                "asset": asset,
                "output_file": result.get("output_file"),
                "conversion_time": result.get("conversion_time", 0.0),
                "file_size": result.get("file_size", 0),
                "optimization_ratio": result.get("optimization_ratio", 1.0),
            }

        except TikZConversionError as exc:
            return {
                "success": False,
                "error": str(exc),
                "asset": asset,
                "error_type": "tikz_conversion",
            }

    def _convert_pdf_asset(
        self, asset: dict[str, Any], output_dir: Path, options: dict[str, Any]
    ) -> dict[str, Any]:
        """Convert a PDF asset to SVG."""
        try:
            # Use PDF service to convert
            result = self.pdf_service.convert_pdf_to_svg(
                asset["source_file"], output_dir, options
            )

            return {
                "success": True,
                "asset": asset,
                "output_file": result.get("output_file"),
                "conversion_time": result.get("conversion_time", 0.0),
                "file_size": result.get("file_size", 0),
                "optimization_ratio": result.get("optimization_ratio", 1.0),
            }

        except PDFConversionError as exc:
            return {
                "success": False,
                "error": str(exc),
                "asset": asset,
                "error_type": "pdf_conversion",
            }

    def get_conversion_status(self, conversion_id: str) -> dict[str, Any] | None:
        """
        Get the status of a specific conversion.

        Args:
            conversion_id: ID of the conversion to check

        Returns:
            Dict containing conversion status or None if not found
        """
        return self._active_conversions.get(conversion_id)

    def cleanup_conversion(self, conversion_id: str) -> bool:
        """
        Clean up resources for a specific conversion.

        Args:
            conversion_id: ID of the conversion to clean up

        Returns:
            True if cleanup was successful, False otherwise
        """
        try:
            if conversion_id in self._active_conversions:
                conversion = self._active_conversions[conversion_id]

                # Clean up temporary files
                if "temp_dir" in conversion:
                    cleanup_directory(Path(conversion["temp_dir"]))

                # Remove from active conversions
                del self._active_conversions[conversion_id]

                logger.info(f"Cleaned up conversion {conversion_id}")
                return True

            return False

        except Exception as exc:
            logger.error(f"Error cleaning up conversion {conversion_id}: {exc}")
            return False

    def get_statistics(self) -> dict[str, Any]:
        """
        Get conversion statistics.

        Returns:
            Dict containing conversion statistics
        """
        return {
            "active_conversions": len(self._active_conversions),
            "max_concurrent": self.max_concurrent_conversions,
            "default_timeout": self.default_timeout,
            "cleanup_delay": self.cleanup_delay,
        }
