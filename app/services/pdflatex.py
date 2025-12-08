"""
PDFLaTeX compilation service.

This module provides LaTeX compilation using pdflatex with a
Tectonic-compatible interface.
It adapts Tectonic-specific flags and options to work with traditional pdflatex.
"""

import subprocess
from pathlib import Path
from typing import Any

from loguru import logger

from app.utils.fs import ensure_directory
from app.utils.shell import run_command_safely


class PDFLaTeXCompilationError(Exception):
    """Raised when PDFLaTeX compilation fails."""

    def __init__(
        self,
        message: str,
        error_type: str = "COMPILATION_ERROR",
        details: dict | None = None,
    ):
        super().__init__(message)
        self.error_type = error_type
        self.details = details or {}


class PDFLaTeXTimeoutError(PDFLaTeXCompilationError):
    """Raised when PDFLaTeX compilation times out."""

    def __init__(self, message: str, timeout_seconds: int):
        super().__init__(message, "TIMEOUT_ERROR", {"timeout_seconds": timeout_seconds})


class PDFLaTeXSecurityError(PDFLaTeXCompilationError):
    """Raised when PDFLaTeX compilation has security issues."""

    def __init__(self, message: str, security_issue: str):
        super().__init__(message, "SECURITY_ERROR", {"security_issue": security_issue})


class PDFLaTeXService:
    """
    Service for LaTeX compilation using pdflatex with Tectonic-compatible interface.

    This service adapts Tectonic-specific flags and options to work
    with traditional pdflatex.
    """

    def __init__(self, pdflatex_path: str = "pdflatex"):
        """
        Initialize PDFLaTeX service.

        Args:
            pdflatex_path: Path to pdflatex executable
        """
        self.pdflatex_path = pdflatex_path
        self._verify_pdflatex()

    def _verify_pdflatex(self) -> None:
        """Verify that pdflatex is available and working."""
        try:
            result = run_command_safely([self.pdflatex_path, "--version"])
            if result.returncode != 0:
                raise PDFLaTeXCompilationError(f"pdflatex not working: {result.stderr}")
            logger.info(f"PDFLaTeX verified: {result.stdout.strip()}")
        except FileNotFoundError:
            raise PDFLaTeXCompilationError(
                f"pdflatex not found at: {self.pdflatex_path}"
            ) from None
        except Exception as exc:
            raise PDFLaTeXCompilationError(f"Failed to verify pdflatex: {exc}") from exc

    def compile_latex(
        self, input_file: Path, output_dir: Path, options: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Compile LaTeX file using pdflatex with Tectonic-compatible interface.

        Args:
            input_file: Input LaTeX file path
            output_dir: Output directory for compiled files
            options: Compilation options (Tectonic-compatible)

        Returns:
            Dictionary with compilation results

        Raises:
            PDFLaTeXCompilationError: If compilation fails
        """
        try:
            # Ensure output directory exists
            ensure_directory(output_dir)

            # Build pdflatex command
            cmd = self._build_command(input_file, output_dir, options)

            logger.info(f"Compiling LaTeX with pdflatex: {input_file}")
            logger.debug(f"Command: {' '.join(cmd)}")

            # Run compilation
            result = run_command_safely(
                cmd,
                cwd=input_file.parent,
                timeout=options.get("timeout", 300) if options else 300,
            )

            # Parse results
            compilation_result = self._parse_compilation_result(
                input_file, output_dir, result.stdout, result.stderr
            )

            if result.returncode != 0:
                raise PDFLaTeXCompilationError(
                    f"pdflatex compilation failed: {result.stderr}",
                    "COMPILATION_ERROR",
                    {"stdout": result.stdout, "stderr": result.stderr},
                )

            logger.info(f"LaTeX compilation completed: {input_file}")
            return compilation_result

        except PDFLaTeXCompilationError:
            raise
        except subprocess.TimeoutExpired as exc:
            raise PDFLaTeXTimeoutError(
                f"pdflatex compilation timed out after {exc.timeout} seconds",
                exc.timeout,
            ) from exc
        except Exception as exc:
            logger.error(f"Unexpected compilation error: {exc}")
            raise PDFLaTeXCompilationError(
                f"Unexpected compilation error: {exc}", "UNKNOWN_ERROR"
            ) from exc

    def _build_command(
        self, input_file: Path, output_dir: Path, options: dict[str, Any] | None
    ) -> list[str]:
        """
        Build pdflatex command with Tectonic-compatible options.

        Args:
            input_file: Input LaTeX file
            output_dir: Output directory
            options: Compilation options (Tectonic-compatible)

        Returns:
            Command list for subprocess execution
        """
        cmd = [self.pdflatex_path]

        # Map Tectonic flags to pdflatex equivalents
        # --untrusted -> --no-shell-escape (security)
        cmd.append("--no-shell-escape")

        # --halt-on-error (stop on first error)
        cmd.append("--halt-on-error")

        # --interaction=nonstopmode (don't stop for user input)
        cmd.append("--interaction=nonstopmode")

        # Output directory (pdflatex uses -output-directory)
        cmd.extend(["-output-directory", str(output_dir)])

        # Add custom options if provided
        if options:
            # Map engine options (pdflatex doesn't support engine
            # switching like Tectonic)
            if options.get("engine", "").lower() in ["xelatex", "lualatex"]:
                logger.warning(
                    f"Engine '{options.get('engine')}' not supported by "
                    f"pdflatex, using pdflatex"
                )

            # Add custom arguments
            if "extra_args" in options:
                cmd.extend(options["extra_args"])

        # Input file (must be last)
        cmd.append(str(input_file))

        return cmd

    def _parse_compilation_result(
        self, input_file: Path, output_dir: Path, stdout: str, stderr: str
    ) -> dict[str, Any]:
        """
        Parse pdflatex compilation results.

        Args:
            input_file: Input LaTeX file
            output_dir: Output directory
            stdout: Standard output from compilation
            stderr: Standard error from compilation

        Returns:
            Dictionary with compilation results
        """
        # Find the generated PDF file
        pdf_file = output_dir / f"{input_file.stem}.pdf"

        result = {
            "success": pdf_file.exists(),
            "pdf_file": str(pdf_file) if pdf_file.exists() else None,
            "output_dir": str(output_dir),
            "stdout": stdout,
            "stderr": stderr,
            "warnings": [],
            "errors": [],
        }

        # Parse output for warnings and errors
        if stderr:
            # Common LaTeX warnings and errors
            lines = stderr.split("\n")
            for line in lines:
                if "Warning:" in line:
                    result["warnings"].append(line.strip())
                elif "Error:" in line or "!" in line:
                    result["errors"].append(line.strip())

        return result
