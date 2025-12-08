"""
TikZ conversion service for the LaTeX → HTML5 Converter.

This service handles the conversion of TikZ diagrams to SVG format.
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


class TikZConversionError(BaseServiceError):
    """Base exception for TikZ conversion errors."""

    def __init__(
        self, message: str, tikz_file: str, details: dict[str, Any] | None = None
    ):
        super().__init__(message, "TIKZ_CONVERSION_ERROR", details)
        self.tikz_file = tikz_file


class TikZConversionTimeoutError(TikZConversionError, ServiceTimeoutError):
    """Raised when TikZ conversion times out."""

    def __init__(self, timeout: int, tikz_file: str):
        super().__init__(
            f"TikZ conversion timed out after {timeout} seconds",
            tikz_file,
            {"timeout": timeout},
        )


class TikZConversionFileError(TikZConversionError, ServiceFileError):
    """Raised when TikZ file operations fail."""

    def __init__(self, message: str, tikz_file: str):
        super().__init__(message, tikz_file, {"file_path": tikz_file})


class TikZConversionService:
    """Service for converting TikZ diagrams to SVG format."""

    def __init__(self, dvisvgm_path: str = "dvisvgm", tectonic_path: str = "pdflatex"):
        """
        Initialize the TikZ conversion service.

        Args:
            dvisvgm_path: Path to dvisvgm executable
            tectonic_path: Path to tectonic executable
        """
        self.dvisvgm_path = dvisvgm_path
        self.tectonic_path = tectonic_path
        self.default_timeout = 300  # 5 minutes
        self.max_file_size = 50 * 1024 * 1024  # 50MB

        # Verify dvisvgm installation
        self._verify_dvisvgm_installation()

        logger.info("TikZ conversion service initialized")

    def _verify_dvisvgm_installation(self) -> None:
        """Verify that dvisvgm is installed and accessible."""
        try:
            result = run_command_safely([self.dvisvgm_path, "--version"], timeout=10)
            if result.returncode != 0:
                raise TikZConversionError(
                    f"dvisvgm not working properly: {result.stderr}", "system"
                )
            logger.info(f"dvisvgm verified: {result.stdout.strip()}")
        except Exception as exc:
            raise TikZConversionError(
                f"dvisvgm not found or not working: {exc}", "system"
            ) from exc

    def convert_tikz_to_svg(
        self, tikz_file: Path, output_dir: Path, options: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Convert a TikZ diagram to SVG format.

        Args:
            tikz_file: Path to TikZ LaTeX file
            output_dir: Directory for output SVG file
            options: Conversion options

        Returns:
            Dict containing conversion results and metadata

        Raises:
            TikZConversionError: If conversion fails
        """
        try:
            # Validate input file
            self._validate_tikz_file(tikz_file)

            # Ensure output directory exists
            ensure_directory(output_dir)

            # Set default options
            if options is None:
                options = {}

            logger.info(f"Converting TikZ to SVG: {tikz_file} -> {output_dir}")

            # Create temporary directory for intermediate files
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Step 1: Compile TikZ to PDF using tectonic
                pdf_file = self._compile_tikz_to_pdf(tikz_file, temp_path, options)

                # Step 2: Convert PDF to SVG using dvisvgm
                svg_file = self._convert_pdf_to_svg(pdf_file, output_dir, options)

                # Step 3: Optimize SVG
                optimized_svg = self._optimize_svg(svg_file, options)

                # Get file information
                file_info = get_file_info(optimized_svg)

                result = {
                    "success": True,
                    "output_file": str(optimized_svg),
                    "conversion_time": time.time(),
                    "file_size": file_info.get("size", 0),
                    "optimization_ratio": self._calculate_optimization_ratio(
                        svg_file, optimized_svg
                    ),
                    "source_file": str(tikz_file),
                    "output_directory": str(output_dir),
                }

                logger.info(f"TikZ conversion successful: {optimized_svg}")
                return result

        except TikZConversionError:
            # Re-raise our custom errors
            raise
        except Exception as exc:
            logger.error(f"Unexpected TikZ conversion error: {exc}")
            raise TikZConversionError(
                f"Unexpected TikZ conversion error: {exc}", str(tikz_file)
            ) from exc

    def _validate_tikz_file(self, tikz_file: Path) -> None:
        """Validate the TikZ input file."""
        if not tikz_file.exists():
            raise TikZConversionFileError(
                f"TikZ file not found: {tikz_file}", str(tikz_file)
            )

        if not tikz_file.is_file():
            raise TikZConversionFileError(
                f"TikZ path is not a file: {tikz_file}", str(tikz_file)
            )

        # Check file size
        file_size = tikz_file.stat().st_size
        if file_size > self.max_file_size:
            raise TikZConversionFileError(
                f"TikZ file too large: {file_size} bytes (max: {self.max_file_size})",
                str(tikz_file),
            )

        # Check if file contains TikZ content
        try:
            with open(tikz_file, encoding="utf-8") as f:
                content = f.read()
                if (
                    "tikz" not in content.lower()
                    and "\\begin{tikzpicture}" not in content
                ):
                    logger.warning(f"File {tikz_file} may not contain TikZ content")
        except Exception as exc:
            raise TikZConversionFileError(
                f"Cannot read TikZ file: {exc}", str(tikz_file)
            ) from exc

    def _compile_tikz_to_pdf(
        self, tikz_file: Path, temp_dir: Path, options: dict[str, Any]
    ) -> Path:
        """Compile TikZ file to PDF format using tectonic."""
        try:
            # Create a minimal LaTeX document wrapper if needed
            latex_file = self._create_latex_wrapper(tikz_file, temp_dir)

            # Compile using tectonic (creates PDF by default)
            # Tectonic creates PDF with the wrapper filename
            pdf_file = temp_dir / f"{latex_file.stem}.pdf"

            cmd = [
                self.tectonic_path,  # This is now pdflatex
                "--no-shell-escape",
                "--halt-on-error",
                "--interaction=nonstopmode",
                "-output-directory",
                str(temp_dir),
                str(latex_file),
            ]

            logger.debug(f"Compiling TikZ with pdflatex: {' '.join(cmd)}")

            result = run_command_safely(
                cmd, cwd=temp_dir, timeout=options.get("timeout", self.default_timeout)
            )

            if result.returncode != 0:
                raise TikZConversionError(
                    f"Tectonic compilation failed: {result.stderr}",
                    str(tikz_file),
                    {"stdout": result.stdout, "stderr": result.stderr},
                )

            # Check for PDF output (Tectonic creates PDF by default)
            if pdf_file.exists():
                logger.info(f"TikZ compiled to PDF: {pdf_file}")
                return pdf_file
            else:
                raise TikZConversionError(
                    "PDF file not created after compilation", str(tikz_file)
                )

        except Exception as exc:
            if isinstance(exc, TikZConversionError):
                raise
            raise TikZConversionError(
                f"TikZ compilation failed: {exc}", str(tikz_file)
            ) from exc

    def _create_latex_wrapper(self, tikz_file: Path, temp_dir: Path) -> Path:
        """Create a minimal LaTeX document wrapper for TikZ content."""
        try:
            # Read the TikZ file content
            with open(tikz_file, encoding="utf-8") as f:
                tikz_content = f.read()

            # Check if the file already has a document structure
            if (
                "\\documentclass" in tikz_content
                and "\\begin{document}" in tikz_content
            ):
                # File already has document structure, use as-is
                latex_content = tikz_content
            else:
                # Create a minimal LaTeX document wrapper with all necessary packages
                latex_content = f"""\\documentclass{{standalone}}
\\usepackage{{tikz}}
\\usepackage{{pgfplots}}
\\usepackage{{pgfplotstable}}
\\usepackage{{amsmath}}
\\usepackage{{amsfonts}}
\\usepackage{{amssymb}}
\\pgfplotsset{{compat=1.18}}

\\begin{{document}}
{tikz_content}
\\end{{document}}"""

            # Write the wrapper
            wrapper_file = temp_dir / f"{tikz_file.stem}_wrapper.tex"
            with open(wrapper_file, "w", encoding="utf-8") as f:
                f.write(latex_content)

            logger.debug(f"Created LaTeX wrapper: {wrapper_file}")
            return wrapper_file

        except Exception as exc:
            raise TikZConversionError(
                f"Failed to create LaTeX wrapper: {exc}", str(tikz_file)
            ) from exc

    def _convert_pdf_to_svg(
        self, pdf_file: Path, output_dir: Path, options: dict[str, Any]
    ) -> Path:
        """Convert PDF file to SVG using dvisvgm."""
        try:
            # Generate output SVG filename
            svg_file = output_dir / f"{pdf_file.stem}.svg"

            # Build dvisvgm command for PDF files
            cmd = [
                self.dvisvgm_path,
                "--pdf",  # Tell dvisvgm this is a PDF file
                "--output=" + str(svg_file),
                "--no-fonts",  # Don't embed fonts
                "--exact",  # Exact bounding box
                "--zoom=1.0",  # No zoom
                str(pdf_file),
            ]

            logger.info(f"Converting PDF to SVG: {pdf_file}")

            # Add additional options
            if options.get("no_fonts", True):
                cmd.append("--no-fonts")

            if options.get("exact", True):
                cmd.append("--exact")

            logger.debug(f"Converting DVI to SVG: {' '.join(cmd)}")

            result = run_command_safely(
                cmd,
                cwd=pdf_file.parent,
                timeout=options.get("timeout", self.default_timeout),
            )

            if result.returncode != 0:
                raise TikZConversionError(
                    f"dvisvgm conversion failed: {result.stderr}",
                    str(pdf_file),
                    {"stdout": result.stdout, "stderr": result.stderr},
                )

            if not svg_file.exists():
                raise TikZConversionError(
                    "SVG file not created after conversion", str(pdf_file)
                )

            logger.info(f"DVI converted to SVG: {svg_file}")
            return svg_file

        except Exception as exc:
            if isinstance(exc, TikZConversionError):
                raise
            raise TikZConversionError(
                f"DVI to SVG conversion failed: {exc}", str(pdf_file)
            ) from exc

    def _optimize_svg(self, svg_file: Path, options: dict[str, Any]) -> Path:
        """Optimize the SVG file."""
        return optimize_svg(svg_file, options)

    def _calculate_optimization_ratio(
        self, original_file: Path, optimized_file: Path
    ) -> float:
        """Calculate the optimization ratio."""
        return calculate_optimization_ratio(original_file, optimized_file)

    def batch_convert_tikz(
        self,
        tikz_files: list[Path],
        output_dir: Path,
        options: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Convert multiple TikZ files to SVG.

        Args:
            tikz_files: List of TikZ files to convert
            output_dir: Directory for output SVG files
            options: Conversion options

        Returns:
            List of conversion results
        """
        results = []

        for tikz_file in tikz_files:
            try:
                result = self.convert_tikz_to_svg(tikz_file, output_dir, options)
                results.append(result)
            except TikZConversionError as exc:
                results.append(
                    {"success": False, "error": str(exc), "tikz_file": str(tikz_file)}
                )

        return results

    def get_conversion_info(self, tikz_file: Path) -> dict[str, Any]:
        """
        Get information about a TikZ file for conversion planning.

        Args:
            tikz_file: Path to TikZ file

        Returns:
            Dict containing file information
        """
        try:
            file_info = get_file_info(tikz_file)

            # Analyze TikZ content
            with open(tikz_file, encoding="utf-8") as f:
                content = f.read()

            tikz_info = {
                "file_path": str(tikz_file),
                "file_size": file_info.get("size", 0),
                "has_tikzpicture": "\\begin{tikzpicture}" in content,
                "has_pgfplots": "\\begin{axis}" in content or "pgfplots" in content,
                "complexity_score": self._calculate_complexity_score(content),
                "estimated_conversion_time": self._estimate_conversion_time(content),
            }

            return tikz_info

        except Exception as exc:
            logger.error(f"Error analyzing TikZ file {tikz_file}: {exc}")
            return {"file_path": str(tikz_file), "error": str(exc)}

    def _calculate_complexity_score(self, content: str) -> int:
        """Calculate a complexity score for the TikZ content."""
        score = 0

        # Count various TikZ elements
        score += content.count("\\node") * 2
        score += content.count("\\draw") * 3
        score += content.count("\\path") * 2
        score += content.count("\\fill") * 2
        score += content.count("\\begin{axis}") * 10
        score += content.count("\\addplot") * 5

        return score

    def _estimate_conversion_time(self, content: str) -> float:
        """Estimate conversion time based on content complexity."""
        complexity = self._calculate_complexity_score(content)

        # Base time + complexity factor
        base_time = 5.0  # seconds
        complexity_factor = complexity * 0.1  # 0.1 seconds per complexity point

        return base_time + complexity_factor
