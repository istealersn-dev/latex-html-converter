"""
TikZ conversion service for the LaTeX → HTML5 Converter.

This service handles the conversion of TikZ diagrams to SVG format.
"""

import logging
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from app.exceptions import BaseServiceError, ServiceFileError, ServiceTimeoutError
from app.utils.fs import cleanup_directory, ensure_directory, get_file_info
from app.utils.shell import run_command_safely


class TikZConversionError(BaseServiceError):
    """Base exception for TikZ conversion errors."""

    def __init__(self, message: str, tikz_file: str, details: Dict[str, Any] | None = None):
        super().__init__(message, "TIKZ_CONVERSION_ERROR", details)
        self.tikz_file = tikz_file


class TikZConversionTimeoutError(TikZConversionError, ServiceTimeoutError):
    """Raised when TikZ conversion times out."""

    def __init__(self, timeout: int, tikz_file: str):
        super().__init__(
            f"TikZ conversion timed out after {timeout} seconds",
            tikz_file,
            {"timeout": timeout}
        )


class TikZConversionFileError(TikZConversionError, ServiceFileError):
    """Raised when TikZ file operations fail."""

    def __init__(self, message: str, tikz_file: str):
        super().__init__(message, tikz_file, {"file_path": tikz_file})


class TikZConversionService:
    """Service for converting TikZ diagrams to SVG format."""

    def __init__(self, dvisvgm_path: str = "dvisvgm"):
        """
        Initialize the TikZ conversion service.

        Args:
            dvisvgm_path: Path to dvisvgm executable
        """
        self.dvisvgm_path = dvisvgm_path
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
                    f"dvisvgm not working properly: {result.stderr}",
                    "system"
                )
            logger.info(f"dvisvgm verified: {result.stdout.strip()}")
        except Exception as exc:
            raise TikZConversionError(
                f"dvisvgm not found or not working: {exc}",
                "system"
            )

    def convert_tikz_to_svg(
        self,
        tikz_file: Path,
        output_dir: Path,
        options: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
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
                
                # Step 1: Compile TikZ to DVI using tectonic
                dvi_file = self._compile_tikz_to_dvi(tikz_file, temp_path, options)
                
                # Step 2: Convert DVI to SVG using dvisvgm
                svg_file = self._convert_dvi_to_svg(dvi_file, output_dir, options)
                
                # Step 3: Optimize SVG
                optimized_svg = self._optimize_svg(svg_file, options)
                
                # Get file information
                file_info = get_file_info(optimized_svg)
                
                result = {
                    "success": True,
                    "output_file": str(optimized_svg),
                    "conversion_time": time.time(),
                    "file_size": file_info.get("size", 0),
                    "optimization_ratio": self._calculate_optimization_ratio(svg_file, optimized_svg),
                    "source_file": str(tikz_file),
                    "output_directory": str(output_dir)
                }

                logger.info(f"TikZ conversion successful: {optimized_svg}")
                return result

        except TikZConversionError:
            # Re-raise our custom errors
            raise
        except Exception as exc:
            logger.error(f"Unexpected TikZ conversion error: {exc}")
            raise TikZConversionError(f"Unexpected TikZ conversion error: {exc}", str(tikz_file))

    def _validate_tikz_file(self, tikz_file: Path) -> None:
        """Validate the TikZ input file."""
        if not tikz_file.exists():
            raise TikZConversionFileError(f"TikZ file not found: {tikz_file}", str(tikz_file))

        if not tikz_file.is_file():
            raise TikZConversionFileError(f"TikZ path is not a file: {tikz_file}", str(tikz_file))

        # Check file size
        file_size = tikz_file.stat().st_size
        if file_size > self.max_file_size:
            raise TikZConversionFileError(
                f"TikZ file too large: {file_size} bytes (max: {self.max_file_size})",
                str(tikz_file)
            )

        # Check if file contains TikZ content
        try:
            with open(tikz_file, encoding="utf-8") as f:
                content = f.read()
                if "tikz" not in content.lower() and "\\begin{tikzpicture}" not in content:
                    logger.warning(f"File {tikz_file} may not contain TikZ content")
        except Exception as exc:
            raise TikZConversionFileError(f"Cannot read TikZ file: {exc}", str(tikz_file))

    def _compile_tikz_to_dvi(
        self,
        tikz_file: Path,
        temp_dir: Path,
        options: Dict[str, Any]
    ) -> Path:
        """Compile TikZ file to DVI format using tectonic."""
        try:
            # Create a minimal LaTeX document wrapper if needed
            latex_file = self._create_latex_wrapper(tikz_file, temp_dir)
            
            # Compile using tectonic
            dvi_file = temp_dir / f"{tikz_file.stem}.dvi"
            
            cmd = [
                "tectonic",
                "--untrusted",
                "--keep-logs",
                "--keep-intermediates",
                str(latex_file)
            ]
            
            logger.debug(f"Compiling TikZ with tectonic: {' '.join(cmd)}")
            
            result = run_command_safely(
                cmd,
                cwd=temp_dir,
                timeout=options.get("timeout", self.default_timeout)
            )
            
            if result.returncode != 0:
                raise TikZConversionError(
                    f"Tectonic compilation failed: {result.stderr}",
                    str(tikz_file),
                    {"stdout": result.stdout, "stderr": result.stderr}
                )
            
            if not dvi_file.exists():
                raise TikZConversionError(
                    "DVI file not created after compilation",
                    str(tikz_file)
                )
            
            logger.info(f"TikZ compiled to DVI: {dvi_file}")
            return dvi_file
            
        except Exception as exc:
            if isinstance(exc, TikZConversionError):
                raise
            raise TikZConversionError(f"TikZ compilation failed: {exc}", str(tikz_file))

    def _create_latex_wrapper(self, tikz_file: Path, temp_dir: Path) -> Path:
        """Create a minimal LaTeX document wrapper for TikZ content."""
        try:
            # Read the TikZ file content
            with open(tikz_file, encoding="utf-8") as f:
                tikz_content = f.read()
            
            # Create a minimal LaTeX document
            latex_content = f"""\\documentclass{{standalone}}
\\usepackage{{tikz}}
\\usepackage{{pgfplots}}
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
            raise TikZConversionError(f"Failed to create LaTeX wrapper: {exc}", str(tikz_file))

    def _convert_dvi_to_svg(
        self,
        dvi_file: Path,
        output_dir: Path,
        options: Dict[str, Any]
    ) -> Path:
        """Convert DVI file to SVG using dvisvgm."""
        try:
            # Generate output SVG filename
            svg_file = output_dir / f"{dvi_file.stem}.svg"
            
            # Build dvisvgm command
            cmd = [
                self.dvisvgm_path,
                "--output=" + str(svg_file),
                "--no-fonts",  # Don't embed fonts
                "--exact",      # Exact bounding box
                "--zoom=1.0",   # No zoom
                str(dvi_file)
            ]
            
            # Add additional options
            if options.get("no_fonts", True):
                cmd.append("--no-fonts")
            
            if options.get("exact", True):
                cmd.append("--exact")
            
            logger.debug(f"Converting DVI to SVG: {' '.join(cmd)}")
            
            result = run_command_safely(
                cmd,
                cwd=dvi_file.parent,
                timeout=options.get("timeout", self.default_timeout)
            )
            
            if result.returncode != 0:
                raise TikZConversionError(
                    f"dvisvgm conversion failed: {result.stderr}",
                    str(dvi_file),
                    {"stdout": result.stdout, "stderr": result.stderr}
                )
            
            if not svg_file.exists():
                raise TikZConversionError(
                    "SVG file not created after conversion",
                    str(dvi_file)
                )
            
            logger.info(f"DVI converted to SVG: {svg_file}")
            return svg_file
            
        except Exception as exc:
            if isinstance(exc, TikZConversionError):
                raise
            raise TikZConversionError(f"DVI to SVG conversion failed: {exc}", str(dvi_file))

    def _optimize_svg(self, svg_file: Path, options: Dict[str, Any]) -> Path:
        """Optimize the SVG file."""
        try:
            # For now, just return the original file
            # TODO: Implement SVG optimization
            logger.debug(f"SVG optimization placeholder: {svg_file}")
            return svg_file
            
        except Exception as exc:
            logger.warning(f"SVG optimization failed: {exc}")
            return svg_file

    def _calculate_optimization_ratio(self, original_file: Path, optimized_file: Path) -> float:
        """Calculate the optimization ratio."""
        try:
            original_size = original_file.stat().st_size
            optimized_size = optimized_file.stat().st_size
            
            if original_size == 0:
                return 1.0
            
            return optimized_size / original_size
            
        except Exception:
            return 1.0

    def batch_convert_tikz(
        self,
        tikz_files: List[Path],
        output_dir: Path,
        options: Dict[str, Any] | None = None
    ) -> List[Dict[str, Any]]:
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
                results.append({
                    "success": False,
                    "error": str(exc),
                    "tikz_file": str(tikz_file)
                })
        
        return results

    def get_conversion_info(self, tikz_file: Path) -> Dict[str, Any]:
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
                "estimated_conversion_time": self._estimate_conversion_time(content)
            }
            
            return tikz_info
            
        except Exception as exc:
            logger.error(f"Error analyzing TikZ file {tikz_file}: {exc}")
            return {
                "file_path": str(tikz_file),
                "error": str(exc)
            }

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
