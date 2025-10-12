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

    def __init__(self, message: str, error_type: str = "COMPILATION_ERROR", details: dict | None = None):
        super().__init__(message)
        self.error_type = error_type
        self.details = details or {}


class TectonicTimeoutError(TectonicCompilationError):
    """Raised when Tectonic compilation times out."""

    def __init__(self, timeout_seconds: int):
        super().__init__(
            f"Tectonic compilation timed out after {timeout_seconds} seconds",
            "TIMEOUT_ERROR",
            {"timeout_seconds": timeout_seconds}
        )


class TectonicFileError(TectonicCompilationError):
    """Raised when there are file-related issues with Tectonic compilation."""

    def __init__(self, message: str, file_path: str | None = None):
        super().__init__(message, "FILE_ERROR", {"file_path": file_path})


class TectonicSecurityError(TectonicCompilationError):
    """Raised when security issues are detected in Tectonic compilation."""

    def __init__(self, message: str, security_issue: str):
        super().__init__(message, "SECURITY_ERROR", {"security_issue": security_issue})


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
        # Enhanced error handling and validation
        if not input_file.exists():
            raise TectonicFileError(f"Input file not found: {input_file}", str(input_file))

        if not input_file.is_file():
            raise TectonicFileError(f"Input path is not a file: {input_file}", str(input_file))

        # Security: Check for dangerous file patterns
        self._validate_input_file_security(input_file)

        # Ensure output directory exists
        try:
            ensure_directory(output_dir)
        except Exception as exc:
            raise TectonicFileError(f"Failed to create output directory: {exc}", str(output_dir))

        # Build Tectonic command
        cmd = self._build_command(input_file, output_dir, options)

        logger.info(f"Compiling LaTeX: {input_file} -> {output_dir}")
        logger.debug(f"Tectonic command: {' '.join(cmd)}")

        try:
            # Run Tectonic compilation with enhanced error handling
            result = run_command_safely(cmd, cwd=input_file.parent, timeout=300)  # 5 minute timeout

            if result.returncode != 0:
                # Parse and categorize the error
                error_info = self._parse_compilation_error(result.stderr, result.stdout)
                logger.error(f"Tectonic compilation failed: {error_info['message']}")
                raise TectonicCompilationError(
                    error_info['message'],
                    error_info['error_type'],
                    error_info['details']
                )

            # Parse compilation results
            compilation_result = self._parse_compilation_result(
                input_file, output_dir, result.stdout, result.stderr
            )

            # Validate output file was created
            if not compilation_result.get('output_file') or not Path(compilation_result['output_file']).exists():
                raise TectonicFileError("Compilation completed but no output file was created")

            logger.info(f"Compilation successful: {compilation_result['output_file']}")
            return compilation_result

        except subprocess.TimeoutExpired:
            raise TectonicTimeoutError(300)
        except TectonicCompilationError:
            # Re-raise our custom errors
            raise
        except Exception as exc:
            logger.error(f"Unexpected compilation error: {exc}")
            raise TectonicCompilationError(f"Unexpected compilation error: {exc}", "UNKNOWN_ERROR")

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

        # Security: Keep logs and intermediates for debugging
        cmd.extend([
            "--keep-logs",
            "--keep-intermediates"
        ])

        # Security: Use untrusted mode to disable insecure features
        cmd.append("--untrusted")

        # Note: Tectonic doesn't support --no-shell-escape, --no-interaction, or --halt-on-error
        # The --untrusted flag provides the security we need

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

    def _validate_input_file_security(self, input_file: Path) -> None:
        """
        Validate input file for security issues.
        
        Args:
            input_file: Input file to validate
            
        Raises:
            TectonicSecurityError: If security issues are detected
        """
        # Check file extension
        if input_file.suffix.lower() not in ['.tex', '.latex']:
            raise TectonicSecurityError(
                f"Invalid file extension: {input_file.suffix}",
                "INVALID_EXTENSION"
            )

        # Check for dangerous patterns in filename
        dangerous_patterns = ['..', '/', '\\', '~', '$', '`', '|', '&', ';']
        filename = str(input_file.name)
        for pattern in dangerous_patterns:
            if pattern in filename:
                raise TectonicSecurityError(
                    f"Dangerous pattern in filename: {pattern}",
                    "DANGEROUS_FILENAME"
                )

        # Check file size (prevent extremely large files)
        try:
            file_size = input_file.stat().st_size
            if file_size > 50 * 1024 * 1024:  # 50MB limit
                raise TectonicSecurityError(
                    f"File too large: {file_size} bytes",
                    "FILE_TOO_LARGE"
                )
        except OSError as exc:
            raise TectonicSecurityError(
                f"Cannot access file: {exc}",
                "FILE_ACCESS_ERROR"
            )

    def _parse_compilation_error(self, stderr: str, stdout: str) -> dict[str, Any]:
        """
        Parse and categorize compilation errors.
        
        Args:
            stderr: Standard error output
            stdout: Standard output
            
        Returns:
            Dictionary with error information
        """
        error_info = {
            "message": "Compilation failed",
            "error_type": "COMPILATION_ERROR",
            "details": {
                "stderr": stderr,
                "stdout": stdout,
                "error_lines": []
            }
        }

        # Parse common LaTeX errors
        stderr_lower = stderr.lower()

        if "emergency stop" in stderr_lower:
            error_info["error_type"] = "EMERGENCY_STOP"
            error_info["message"] = "LaTeX compilation stopped due to emergency"
        elif "undefined control sequence" in stderr_lower:
            error_info["error_type"] = "UNDEFINED_CONTROL"
            error_info["message"] = "Undefined LaTeX command or control sequence"
        elif "missing" in stderr_lower and "begin" in stderr_lower:
            error_info["error_type"] = "MISSING_BEGIN"
            error_info["message"] = "Missing \\begin{document} or environment"
        elif "file not found" in stderr_lower:
            error_info["error_type"] = "FILE_NOT_FOUND"
            error_info["message"] = "Required LaTeX file or package not found"
        elif "overfull" in stderr_lower or "underfull" in stderr_lower:
            error_info["error_type"] = "TYPESETTING_WARNING"
            error_info["message"] = "Typesetting issues detected (overfull/underfull boxes)"
        elif "error" in stderr_lower:
            error_info["error_type"] = "GENERAL_ERROR"
            error_info["message"] = "General LaTeX compilation error"

        # Extract error lines
        error_lines = []
        for line in stderr.split('\n'):
            if any(keyword in line.lower() for keyword in ['error', 'emergency', 'undefined', 'missing']):
                error_lines.append(line.strip())

        error_info["details"]["error_lines"] = error_lines

        return error_info
