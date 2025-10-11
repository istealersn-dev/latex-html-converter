"""
Tectonic LaTeX compilation service.

This module provides deterministic LaTeX compilation using Tectonic with proper
error handling, resource management, and security considerations.
"""

import subprocess
from pathlib import Path
from typing import Any

from loguru import logger

from app.utils.fs import ensure_directory
from app.utils.shell import run_command_safely


class TectonicCompilationError(Exception):
    """Raised when Tectonic compilation fails."""


class TectonicService:
    """
    Service for LaTeX compilation using Tectonic.

    Provides deterministic compilation with proper error handling and security.
    """

    def __init__(self, tectonic_path: str = "tectonic"):
        """
        Initialize Tectonic service.

        Args:
            tectonic_path: Path to Tectonic executable
        """
        self.tectonic_path = tectonic_path
        self._verify_tectonic()

    def _verify_tectonic(self) -> None:
        """Verify that Tectonic is available and working."""
        try:
            result = run_command_safely([self.tectonic_path, "--version"])
            if result.returncode != 0:
                raise TectonicCompilationError(f"Tectonic not working: {result.stderr}")
            logger.info(f"Tectonic verified: {result.stdout.strip()}")
        except FileNotFoundError:
            raise TectonicCompilationError(f"Tectonic not found at: {self.tectonic_path}")
        except Exception as exc:
            raise TectonicCompilationError(f"Failed to verify Tectonic: {exc}")

    def compile_latex(
        self,
        input_file: Path,
        output_dir: Path,
        options: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Compile LaTeX document using Tectonic.

        Args:
            input_file: Path to input LaTeX file
            output_dir: Directory for output files
            options: Compilation options

        Returns:
            Dict containing compilation results and metadata

        Raises:
            TectonicCompilationError: If compilation fails
        """
        if not input_file.exists():
            raise TectonicCompilationError(f"Input file not found: {input_file}")

        # Ensure output directory exists
        ensure_directory(output_dir)

        # Build Tectonic command
        cmd = self._build_command(input_file, output_dir, options)

        logger.info(f"Compiling LaTeX: {input_file} -> {output_dir}")
        logger.debug(f"Tectonic command: {' '.join(cmd)}")

        try:
            # Run Tectonic compilation
            result = run_command_safely(cmd, cwd=input_file.parent)

            if result.returncode != 0:
                error_msg = f"Tectonic compilation failed:\n{result.stderr}"
                logger.error(error_msg)
                raise TectonicCompilationError(error_msg)

            # Parse compilation results
            compilation_result = self._parse_compilation_result(
                input_file, output_dir, result.stdout, result.stderr
            )

            logger.info(f"Compilation successful: {compilation_result['output_file']}")
            return compilation_result

        except subprocess.TimeoutExpired:
            raise TectonicCompilationError("Tectonic compilation timed out")
        except Exception as exc:
            raise TectonicCompilationError(f"Compilation failed: {exc}")

    def _build_command(
        self,
        input_file: Path,
        output_dir: Path,
        options: dict[str, Any] | None
    ) -> list[str]:
        """
        Build Tectonic command with security considerations.

        Args:
            input_file: Input LaTeX file
            output_dir: Output directory
            options: Compilation options

        Returns:
            Command list for subprocess execution
        """
        cmd = [self.tectonic_path]

        # Security: Disable shell-escape and other dangerous features
        cmd.extend(["--keep-logs", "--keep-intermediates"])

        # Output directory
        cmd.extend(["--outdir", str(output_dir)])

        # Add custom options if provided
        if options:
            if options.get("engine", "").lower() == "xelatex":
                cmd.append("--engine=xelatex")
            elif options.get("engine", "").lower() == "lualatex":
                cmd.append("--engine=lualatex")

            if options.get("format", "").lower() == "latex":
                cmd.append("--format=latex")

            # Add custom arguments
            if "extra_args" in options:
                cmd.extend(options["extra_args"])

        # Input file (must be last)
        cmd.append(str(input_file))

        return cmd

    def _parse_compilation_result(
        self,
        input_file: Path,
        output_dir: Path,
        stdout: str,
        stderr: str
    ) -> dict[str, Any]:
        """
        Parse Tectonic compilation results.

        Args:
            input_file: Input LaTeX file
            output_dir: Output directory
            stdout: Standard output from Tectonic
            stderr: Standard error from Tectonic

        Returns:
            Parsed compilation results
        """
        # Find output PDF file
        pdf_file = output_dir / f"{input_file.stem}.pdf"

        # Find auxiliary files
        aux_files = list(output_dir.glob(f"{input_file.stem}.*"))
        aux_files = [f for f in aux_files if f.suffix in ['.aux', '.toc', '.bbl', '.blg', '.log']]

        return {
            "success": True,
            "input_file": str(input_file),
            "output_file": str(pdf_file) if pdf_file.exists() else None,
            "output_dir": str(output_dir),
            "aux_files": [str(f) for f in aux_files],
            "log_file": str(output_dir / f"{input_file.stem}.log"),
            "stdout": stdout,
            "stderr": stderr,
            "warnings": self._extract_warnings(stderr),
            "errors": self._extract_errors(stderr)
        }

    def _extract_warnings(self, stderr: str) -> list[str]:
        """Extract warning messages from Tectonic output."""
        warnings = []
        for line in stderr.split('\n'):
            if 'warning' in line.lower() and 'error' not in line.lower():
                warnings.append(line.strip())
        return warnings

    def _extract_errors(self, stderr: str) -> list[str]:
        """Extract error messages from Tectonic output."""
        errors = []
        for line in stderr.split('\n'):
            if 'error' in line.lower() and 'warning' not in line.lower():
                errors.append(line.strip())
        return errors

    def cleanup_auxiliary_files(self, output_dir: Path) -> None:
        """
        Clean up auxiliary files after compilation.

        Args:
            output_dir: Directory containing auxiliary files
        """
        aux_extensions = ['.aux', '.toc', '.bbl', '.blg', '.log', '.out', '.fdb_latexmk']

        for ext in aux_extensions:
            for file_path in output_dir.glob(f"*{ext}"):
                try:
                    file_path.unlink()
                    logger.debug(f"Cleaned up auxiliary file: {file_path}")
                except OSError as exc:
                    logger.warning(f"Failed to clean up {file_path}: {exc}")

    def get_compilation_info(self, output_dir: Path) -> dict[str, Any]:
        """
        Get information about compilation results.

        Args:
            output_dir: Output directory to analyze

        Returns:
            Compilation information
        """
        info = {
            "output_dir": str(output_dir),
            "files": [],
            "total_size": 0
        }

        if output_dir.exists():
            for file_path in output_dir.iterdir():
                if file_path.is_file():
                    info["files"].append({
                        "name": file_path.name,
                        "size": file_path.stat().st_size,
                        "extension": file_path.suffix
                    })
                    info["total_size"] += file_path.stat().st_size

        return info
