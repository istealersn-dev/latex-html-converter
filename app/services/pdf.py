"""
PDF conversion service for the LaTeX → HTML5 Converter.

This service handles the conversion of PDF figures to SVG format.
"""

import tempfile
import time
from pathlib import Path
from typing import Any

from loguru import logger

from app.exceptions import BaseServiceError, ServiceFileError, ServiceTimeoutError
from app.utils.fs import ensure_directory, get_file_info
from app.utils.shell import run_command_safely
from app.utils.svg_utils import calculate_optimization_ratio, optimize_svg


class PDFConversionError(BaseServiceError):
    """Base exception for PDF conversion errors."""

    def __init__(
        self, message: str, pdf_file: str, details: dict[str, Any] | None = None
    ):
        super().__init__(message, "PDF_CONVERSION_ERROR", details)
        self.pdf_file = pdf_file


class PDFConversionTimeoutError(PDFConversionError, ServiceTimeoutError):
    """Raised when PDF conversion times out."""

    def __init__(self, timeout: int, pdf_file: str):
        super().__init__(
            f"PDF conversion timed out after {timeout} seconds",
            pdf_file,
            {"timeout": timeout},
        )


class PDFConversionFileError(PDFConversionError, ServiceFileError):
    """Raised when PDF file operations fail."""

    def __init__(self, message: str, pdf_file: str):
        super().__init__(message, pdf_file, {"file_path": pdf_file})


class PDFConversionService:
    """Service for converting PDF figures to SVG format."""

    def __init__(
        self,
        gs_path: str = "/opt/homebrew/bin/gs",
        pdfinfo_path: str = "/opt/homebrew/bin/pdfinfo",
        pdftoppm_path: str = "/opt/homebrew/bin/pdftoppm",
    ):
        """
        Initialize the PDF conversion service.

        Args:
            gs_path: Path to ghostscript executable
            pdfinfo_path: Path to pdfinfo executable
            pdftoppm_path: Path to pdftoppm executable
        """
        self.gs_path = gs_path
        self.pdfinfo_path = pdfinfo_path
        self.pdftoppm_path = pdftoppm_path
        self.default_timeout = 300  # 5 minutes
        self.max_file_size = 100 * 1024 * 1024  # 100MB

        # Verify tool installations
        self._verify_tool_installations()

        logger.info("PDF conversion service initialized")

    def _verify_tool_installations(self) -> None:
        """Verify that required tools are installed and accessible."""
        tools = [
            (self.gs_path, "ghostscript", "--version"),
            (self.pdfinfo_path, "pdfinfo", "-v"),
            (self.pdftoppm_path, "pdftoppm", "-v"),
        ]

        for tool_path, tool_name, version_flag in tools:
            try:
                result = run_command_safely([tool_path, version_flag], timeout=10)
                if result.returncode != 0:
                    raise PDFConversionError(
                        f"{tool_name} not working properly: {result.stderr}", "system"
                    )
                logger.info(f"{tool_name} verified: {result.stdout.strip()[:50]}...")
            except Exception as exc:
                raise PDFConversionError(
                    f"{tool_name} not found or not working: {exc}", "system"
                ) from exc

    def convert_pdf_to_svg(
        self, pdf_file: Path, output_dir: Path, options: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Convert a PDF file to SVG format.

        Args:
            pdf_file: Path to PDF file
            output_dir: Directory for output SVG file
            options: Conversion options

        Returns:
            Dict containing conversion results and metadata

        Raises:
            PDFConversionError: If conversion fails
        """
        try:
            # Validate input file
            self._validate_pdf_file(pdf_file)

            # Ensure output directory exists
            ensure_directory(output_dir)

            # Set default options
            if options is None:
                options = {}

            logger.info(f"Converting PDF to SVG: {pdf_file} -> {output_dir}")

            # Get PDF information
            pdf_info = self._get_pdf_info(pdf_file)
            logger.debug(f"PDF info: {pdf_info}")

            # Choose conversion method based on PDF characteristics
            if pdf_info.get("pages", 1) == 1 and pdf_info.get(
                "has_vector_content", True
            ):
                # Use ghostscript for vector PDFs
                svg_file = self._convert_pdf_with_ghostscript(
                    pdf_file, output_dir, options
                )
            else:
                # Use pdftoppm + conversion for complex PDFs
                svg_file = self._convert_pdf_with_pdftoppm(
                    pdf_file, output_dir, options
                )

            # Optimize SVG
            optimized_svg = self._optimize_svg(svg_file, options)

            # Get file information
            file_info = get_file_info(optimized_svg)

            result = {
                "success": True,
                "output_file": str(optimized_svg),
                "conversion_time": time.time(),
                "file_size": file_info.get("size", 0),
                "optimization_ratio": self._calculate_optimization_ratio(
                    pdf_file, optimized_svg
                ),
                "source_file": str(pdf_file),
                "output_directory": str(output_dir),
                "pdf_info": pdf_info,
            }

            logger.info(f"PDF conversion successful: {optimized_svg}")
            return result

        except PDFConversionError:
            # Re-raise our custom errors
            raise
        except Exception as exc:
            logger.error(f"Unexpected PDF conversion error: {exc}")
            raise PDFConversionError(
                f"Unexpected PDF conversion error: {exc}", str(pdf_file)
            ) from exc

    def _validate_pdf_file(self, pdf_file: Path) -> None:
        """Validate the PDF input file."""
        if not pdf_file.exists():
            raise PDFConversionFileError(
                f"PDF file not found: {pdf_file}", str(pdf_file)
            )

        if not pdf_file.is_file():
            raise PDFConversionFileError(
                f"PDF path is not a file: {pdf_file}", str(pdf_file)
            )

        # Check file size
        file_size = pdf_file.stat().st_size
        if file_size > self.max_file_size:
            raise PDFConversionFileError(
                f"PDF file too large: {file_size} bytes (max: {self.max_file_size})",
                str(pdf_file),
            )

        # Check if file is a valid PDF
        try:
            result = run_command_safely([self.pdfinfo_path, str(pdf_file)], timeout=10)
            if result.returncode != 0:
                raise PDFConversionFileError(
                    f"Invalid PDF file: {result.stderr}", str(pdf_file)
                )
        except Exception as exc:
            raise PDFConversionFileError(
                f"Cannot validate PDF file: {exc}", str(pdf_file)
            ) from exc

    def _get_pdf_info(self, pdf_file: Path) -> dict[str, Any]:
        """Get information about the PDF file."""
        try:
            # Get basic PDF info
            result = run_command_safely([self.pdfinfo_path, str(pdf_file)], timeout=30)
            if result.returncode != 0:
                raise PDFConversionError(
                    f"Failed to get PDF info: {result.stderr}", str(pdf_file)
                )

            # Parse PDF info
            info = {}
            for line in result.stdout.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip().lower().replace(" ", "_")
                    value = value.strip()

                    if key == "pages":
                        info["pages"] = int(value)
                    elif key == "page_size":
                        info["page_size"] = value
                    elif key == "file_size":
                        info["file_size"] = int(value.split()[0])
                    else:
                        info[key] = value

            # Determine if PDF has vector content
            info["has_vector_content"] = self._has_vector_content(pdf_file)

            return info

        except Exception as exc:
            logger.warning(f"Could not get PDF info: {exc}")
            return {"pages": 1, "has_vector_content": True}

    def _has_vector_content(self, pdf_file: Path) -> bool:
        """Check if PDF has vector content (simplified check)."""
        try:
            # Use ghostscript to check for vector content
            cmd = [
                self.gs_path,
                "-dNOPAUSE",
                "-dBATCH",
                "-dQUIET",
                "-sDEVICE=nullpage",
                "-sOutputFile=/dev/null",
                str(pdf_file),
            ]

            result = run_command_safely(cmd, timeout=30)
            # If ghostscript can process it without errors, it likely has vector content
            return result.returncode == 0

        except Exception:
            return True  # Assume vector content if we can't determine

    def _convert_pdf_with_ghostscript(
        self, pdf_file: Path, output_dir: Path, options: dict[str, Any]
    ) -> Path:
        """Convert PDF to SVG using ghostscript."""
        try:
            # Generate output SVG filename
            svg_file = output_dir / f"{pdf_file.stem}.svg"

            # Build ghostscript command
            cmd = [
                self.gs_path,
                "-dNOPAUSE",
                "-dBATCH",
                "-dQUIET",
                "-sDEVICE=svg",
                f"-sOutputFile={svg_file}",
                "-dTextAlphaBits=4",
                "-dGraphicsAlphaBits=4",
                str(pdf_file),
            ]

            # Add additional options
            if options.get("dpi", 300) != 300:
                cmd.extend(["-r", str(options["dpi"])])

            logger.debug(f"Converting PDF with ghostscript: {' '.join(cmd)}")

            result = run_command_safely(
                cmd, timeout=options.get("timeout", self.default_timeout)
            )

            if result.returncode != 0:
                raise PDFConversionError(
                    f"Ghostscript conversion failed: {result.stderr}",
                    str(pdf_file),
                    {"stdout": result.stdout, "stderr": result.stderr},
                )

            if not svg_file.exists():
                raise PDFConversionError(
                    "SVG file not created after ghostscript conversion", str(pdf_file)
                )

            logger.info(f"PDF converted to SVG with ghostscript: {svg_file}")
            return svg_file

        except Exception as exc:
            if isinstance(exc, PDFConversionError):
                raise
            raise PDFConversionError(
                f"Ghostscript conversion failed: {exc}", str(pdf_file)
            ) from exc

    def _convert_pdf_with_pdftoppm(
        self, pdf_file: Path, output_dir: Path, options: dict[str, Any]
    ) -> Path:
        """Convert PDF to SVG using pdftoppm + imagemagick."""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Convert PDF to high-resolution images
                dpi = options.get("dpi", 300)
                cmd = [
                    self.pdftoppm_path,
                    "-png",
                    "-r",
                    str(dpi),
                    str(pdf_file),
                    str(temp_path / "page"),
                ]

                logger.debug(f"Converting PDF to images: {' '.join(cmd)}")

                result = run_command_safely(
                    cmd, timeout=options.get("timeout", self.default_timeout)
                )

                if result.returncode != 0:
                    raise PDFConversionError(
                        f"pdftoppm conversion failed: {result.stderr}",
                        str(pdf_file),
                        {"stdout": result.stdout, "stderr": result.stderr},
                    )

                # Find the generated image files
                image_files = list(temp_path.glob("page-*.png"))
                if not image_files:
                    raise PDFConversionError(
                        "No images generated from PDF", str(pdf_file)
                    )

                # Convert images to SVG using imagemagick
                svg_file = output_dir / f"{pdf_file.stem}.svg"

                if len(image_files) == 1:
                    # Single page - direct conversion
                    cmd = ["convert", str(image_files[0]), str(svg_file)]
                else:
                    # Multiple pages - create combined SVG
                    # For now, just convert the first page
                    cmd = ["convert", str(image_files[0]), str(svg_file)]

                logger.debug(f"Converting images to SVG: {' '.join(cmd)}")

                result = run_command_safely(
                    cmd, timeout=options.get("timeout", self.default_timeout)
                )

                if result.returncode != 0:
                    raise PDFConversionError(
                        f"Image to SVG conversion failed: {result.stderr}",
                        str(pdf_file),
                        {"stdout": result.stdout, "stderr": result.stderr},
                    )

                if not svg_file.exists():
                    raise PDFConversionError(
                        "SVG file not created after image conversion", str(pdf_file)
                    )

                logger.info(f"PDF converted to SVG with pdftoppm: {svg_file}")
                return svg_file

        except Exception as exc:
            if isinstance(exc, PDFConversionError):
                raise
            raise PDFConversionError(
                f"pdftoppm conversion failed: {exc}", str(pdf_file)
            ) from exc

    def _optimize_svg(self, svg_file: Path, options: dict[str, Any]) -> Path:
        """Optimize the SVG file."""
        return optimize_svg(svg_file, options)

    def _calculate_optimization_ratio(
        self, original_file: Path, optimized_file: Path
    ) -> float:
        """Calculate the optimization ratio."""
        return calculate_optimization_ratio(original_file, optimized_file)

    def batch_convert_pdf(
        self,
        pdf_files: list[Path],
        output_dir: Path,
        options: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Convert multiple PDF files to SVG.

        Args:
            pdf_files: List of PDF files to convert
            output_dir: Directory for output SVG files
            options: Conversion options

        Returns:
            List of conversion results
        """
        results = []

        for pdf_file in pdf_files:
            try:
                result = self.convert_pdf_to_svg(pdf_file, output_dir, options)
                results.append(result)
            except PDFConversionError as exc:
                results.append(
                    {"success": False, "error": str(exc), "pdf_file": str(pdf_file)}
                )

        return results

    def get_pdf_info(self, pdf_file: Path) -> dict[str, Any]:
        """
        Get detailed information about a PDF file.

        Args:
            pdf_file: Path to PDF file

        Returns:
            Dict containing PDF information
        """
        try:
            file_info = get_file_info(pdf_file)
            pdf_info = self._get_pdf_info(pdf_file)

            return {
                "file_path": str(pdf_file),
                "file_size": file_info.get("size", 0),
                "pdf_info": pdf_info,
                "estimated_conversion_time": self._estimate_conversion_time(pdf_info),
            }

        except Exception as exc:
            logger.error(f"Error analyzing PDF file {pdf_file}: {exc}")
            return {"file_path": str(pdf_file), "error": str(exc)}

    def _estimate_conversion_time(self, pdf_info: dict[str, Any]) -> float:
        """Estimate conversion time based on PDF characteristics."""
        pages = pdf_info.get("pages", 1)
        file_size = pdf_info.get("file_size", 0)

        # Base time per page + size factor
        base_time_per_page = 2.0  # seconds
        size_factor = file_size / (1024 * 1024) * 0.1  # 0.1 seconds per MB

        return pages * base_time_per_page + size_factor
