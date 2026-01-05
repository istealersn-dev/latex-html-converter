"""
LaTeXML service for TeX to XML/HTML conversion.

This module provides the LaTeXMLService class for converting LaTeX documents
to XML/HTML using LaTeXML with proper error handling and configuration.
"""

import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from loguru import logger

from app.configs.latexml import LaTeXMLConversionOptions, LaTeXMLSettings
from app.utils.fs import ensure_directory, get_file_info
from app.utils.shell import run_command_safely


class LaTeXMLError(Exception):
    """Base exception for LaTeXML-related errors."""

    def __init__(
        self,
        message: str,
        error_type: str = "LATEXML_ERROR",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.error_type = error_type
        self.details = details or {}


class LaTeXMLTimeoutError(LaTeXMLError):
    """Raised when LaTeXML conversion times out."""

    def __init__(self, timeout_seconds: int):
        super().__init__(
            f"LaTeXML conversion timed out after {timeout_seconds} seconds",
            "TIMEOUT_ERROR",
            {"timeout_seconds": timeout_seconds},
        )


class LaTeXMLFileError(LaTeXMLError):
    """Raised when there are file-related errors."""

    def __init__(self, message: str, file_path: str):
        super().__init__(message, "FILE_ERROR", {"file_path": file_path})


class LaTeXMLConversionError(LaTeXMLError):
    """Raised when LaTeXML conversion fails."""

    def __init__(
        self,
        message: str,
        error_type: str = "CONVERSION_ERROR",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, error_type, details)


class LaTeXMLSecurityError(LaTeXMLError):
    """Raised when security validation fails."""

    def __init__(self, message: str, violation: str):
        super().__init__(message, "SECURITY_ERROR", {"violation": violation})


class LaTeXMLService:
    """Service for LaTeXML TeX to XML/HTML conversion."""

    def __init__(self, settings: LaTeXMLSettings | None = None):
        """
        Initialize LaTeXML service.

        Args:
            settings: LaTeXML configuration settings
        """
        self.settings = settings or LaTeXMLSettings()
        self._verify_latexml_installation()

    def _verify_latexml_installation(self) -> None:
        """Verify LaTeXML is installed and accessible."""
        try:
            result = run_command_safely(
                [self.settings.latexml_path, "--help"], timeout=10
            )
            if result.returncode != 0:
                raise LaTeXMLFileError(
                    f"LaTeXML not found or not working: {self.settings.latexml_path}",
                    self.settings.latexml_path,
                )
            logger.info("LaTeXML verified: %s", self.settings.latexml_path)
        except Exception as exc:
            raise LaTeXMLFileError(
                f"Failed to verify LaTeXML installation: {exc}",
                self.settings.latexml_path,
            ) from exc

    def convert_tex_to_html(
        self,
        input_file: Path,
        output_dir: Path,
        options: LaTeXMLConversionOptions | None = None,
        project_dir: Path | None = None,
    ) -> dict[str, Any]:
        """
        Convert TeX file to HTML using LaTeXML.

        Args:
            input_file: Path to input TeX file
            output_dir: Directory for output files
            options: Conversion options
            project_dir: Project directory with custom classes and styles

        Returns:
            Dict containing conversion results and metadata

        Raises:
            LaTeXMLFileError: If input file issues
            LaTeXMLSecurityError: If security validation fails
            LaTeXMLConversionError: If conversion fails
            LaTeXMLTimeoutError: If conversion times out
        """
        # Validate input file
        self._validate_input_file(input_file)

        # Apply options to settings
        settings = (
            options.to_latexml_settings() if options else self.settings
        )

        # Ensure output directory exists
        try:
            ensure_directory(output_dir)
        except Exception as exc:
            raise LaTeXMLFileError(
                f"Failed to create output directory: {exc}", str(output_dir)
            ) from exc

        # Generate output file path
        output_file = output_dir / f"{input_file.stem}.{settings.output_format}"

        # Create temporary directory for LaTeXML processing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Handle custom preamble/postamble
            preamble_file = None
            postamble_file = None

            if options and options.custom_preamble:
                preamble_file = temp_path / "custom_preamble.tex"
                preamble_file.write_text(options.custom_preamble, encoding="utf-8")
                settings.preamble_file = preamble_file

            if options and options.custom_postamble:
                postamble_file = temp_path / "custom_postamble.tex"
                postamble_file.write_text(options.custom_postamble, encoding="utf-8")
                settings.postamble_file = postamble_file

            # Build LaTeXML command
            cmd = settings.get_latexml_command(input_file, output_file)

            # Add project directory paths if provided
            if project_dir and project_dir.exists():
                from app.config import settings
                from app.utils.path_utils import (
                    discover_directories_recursive,
                    normalize_path_for_os,
                )

                # Use a set to track added paths for O(1) lookup
                added_paths = set()
                
                # Add main project directory
                try:
                    normalized_project = normalize_path_for_os(project_dir)
                    project_str = str(normalized_project)
                    if project_str not in added_paths:
                        added_paths.add(project_str)
                        cmd.extend(["--path", project_str])
                except ValueError as exc:
                    logger.warning(f"Could not normalize project directory: {exc}")
                    # Fallback to original path
                    project_str = str(project_dir)
                    if project_str not in added_paths:
                        added_paths.add(project_str)
                        cmd.extend(["--path", project_str])

                # Discover all subdirectories recursively (up to max depth)
                # This ensures LaTeXML can find files in deeply nested structures
                try:
                    all_dirs = discover_directories_recursive(
                        project_dir,
                        max_depth=settings.MAX_PATH_DEPTH,
                        include_hidden=False,
                    )
                    
                    # Add all discovered directories to LaTeXML path
                    for dir_path in all_dirs:
                        try:
                            normalized = normalize_path_for_os(dir_path)
                            dir_str = str(normalized)
                            if dir_str not in added_paths:
                                added_paths.add(dir_str)
                                cmd.extend(["--path", dir_str])
                        except ValueError:
                            # Skip paths that exceed limits
                            logger.debug(f"Skipping path that exceeds limits: {dir_path}")
                            continue
                    
                    logger.info(
                        f"Added {len(all_dirs)} directories recursively for path discovery"
                    )
                except Exception as exc:
                    logger.warning(
                        f"Failed to discover directories recursively: {exc}. "
                        "Falling back to common subdirectories."
                    )
                    # Fallback: Add common subdirectories
                    for subdir in ["doc", "graphic", "styles", "figures", "images"]:
                        subdir_path = project_dir / subdir
                        if subdir_path.exists():
                            subdir_str = str(subdir_path)
                            if subdir_str not in added_paths:
                                added_paths.add(subdir_str)
                                cmd.extend(["--path", subdir_str])
                
                # Also add parent directories (up to reasonable depth)
                # This helps when class files are in parent directories
                parent_paths_added = []
                current_dir = project_dir
                max_parent_levels = 5  # Increased from 2 to 5 for better discovery
                for _ in range(max_parent_levels):
                    if current_dir.parent.exists() and current_dir.parent != current_dir:
                        try:
                            parent_normalized = normalize_path_for_os(current_dir.parent)
                            parent_str = str(parent_normalized)
                            if parent_str not in added_paths:
                                added_paths.add(parent_str)
                                parent_paths_added.append(parent_str)
                                cmd.extend(["--path", parent_str])
                        except ValueError:
                            # Stop if parent path exceeds limits
                            break
                        current_dir = current_dir.parent
                    else:
                        break

                logger.info(f"Added project directory paths: {project_dir}")
                if parent_paths_added:
                    logger.debug(
                        f"Added {len(parent_paths_added)} parent directory paths: "
                        f"{parent_paths_added[:3]}{'...' if len(parent_paths_added) > 3 else ''}"
                    )

            env_vars = settings.get_environment_vars()

            logger.info(
                "Converting TeX to %s: %s -> %s",
                settings.output_format.upper(),
                input_file,
                output_file,
            )
            logger.debug("LaTeXML command: %s", " ".join(cmd))

            try:
                # Run LaTeXML conversion
                result = run_command_safely(
                    cmd,
                    cwd=input_file.parent,
                    timeout=settings.conversion_timeout,
                    env=env_vars,
                )

                if result.returncode != 0:
                    error_info = self._parse_conversion_error(
                        result.stderr, result.stdout
                    )
                    
                    # Enhance error details with file information
                    error_info["details"]["input_file"] = str(input_file)
                    error_info["details"]["output_file"] = str(output_file)
                    error_info["details"]["command"] = " ".join(cmd)
                    error_info["details"]["return_code"] = result.returncode
                    
                    # Extract specific error lines for better diagnostics
                    if result.stderr:
                        error_lines = [
                            line.strip()
                            for line in result.stderr.split("\n")
                            if line.strip() and any(
                                keyword in line.lower()
                                for keyword in ["error", "fatal", "undefined", "missing"]
                            )
                        ]
                        if error_lines:
                            error_info["details"]["key_errors"] = error_lines[:10]
                    
                    logger.error(
                        "LaTeXML conversion failed: %s",
                        error_info["message"],
                        extra={"error_details": error_info["details"]},
                    )
                    raise LaTeXMLConversionError(
                        error_info["message"],
                        error_info["error_type"],
                        error_info["details"],
                    )

                # Parse conversion results
                conversion_result = self._parse_conversion_result(
                    input_file, output_file, result.stdout, result.stderr, settings
                )

                # Validate output file was created
                if not output_file.exists():
                    raise LaTeXMLFileError(
                        "Conversion completed but no output file was created",
                        str(output_file),
                    )

                logger.info("Conversion successful: %s", output_file)
                return conversion_result

            except subprocess.TimeoutExpired:
                raise LaTeXMLTimeoutError(settings.conversion_timeout) from None
            except LaTeXMLConversionError:
                # Re-raise our custom errors
                raise
            except Exception as exc:
                logger.error("Unexpected conversion error: %s", exc)
                raise LaTeXMLConversionError(
                    f"Unexpected conversion error: {exc}", "UNKNOWN_ERROR"
                ) from exc

    def _validate_input_file(self, input_file: Path) -> None:
        """
        Validate input file for security and format.

        Args:
            input_file: Path to input file

        Raises:
            LaTeXMLFileError: If file validation fails
            LaTeXMLSecurityError: If security validation fails
        """
        if not input_file.exists():
            raise LaTeXMLFileError(
                f"Input file not found: {input_file}", str(input_file)
            )

        if not input_file.is_file():
            raise LaTeXMLFileError(
                f"Input path is not a file: {input_file}", str(input_file)
            )

        # Check file extension
        if input_file.suffix.lower() not in self.settings.allowed_extensions:
            raise LaTeXMLSecurityError(
                f"File extension not allowed: {input_file.suffix}",
                f"extension_{input_file.suffix}",
            )

        # Check file size
        try:
            file_info = get_file_info(input_file)
            if file_info["size"] > self.settings.max_file_size:
                max_size = self.settings.max_file_size
                raise LaTeXMLSecurityError(
                    f"File too large: {file_info['size']} bytes "
                    f"(max: {max_size})",
                    "file_size_exceeded",
                )
        except Exception as exc:
            raise LaTeXMLFileError(
                f"Failed to get file info: {exc}", str(input_file)
            ) from exc

        # Check for dangerous patterns in filename
        dangerous_patterns = ["..", "/", "\\", "~", "$", "`"]
        filename = input_file.name.lower()
        for pattern in dangerous_patterns:
            if pattern in filename:
                raise LaTeXMLSecurityError(
                    f"Dangerous pattern in filename: {pattern}",
                    f"dangerous_pattern_{pattern}",
                )

    def _parse_conversion_error(self, stderr: str, stdout: str) -> dict[str, Any]:
        """
        Parse LaTeXML error output to categorize errors.

        Args:
            stderr: Standard error output
            stdout: Standard output

        Returns:
            Dict with error information including suggestions
        """
        error_lines = stderr.strip().split("\n") if stderr else []
        suggestions = []

        # Common LaTeXML error patterns with suggestions
        if any("Fatal error" in line for line in error_lines):
            suggestions.append(
                "Check LaTeX syntax and ensure all required packages are installed"
            )
            return {
                "message": "LaTeXML fatal error occurred",
                "error_type": "FATAL_ERROR",
                "details": {"stderr": stderr, "stdout": stdout},
                "suggestions": suggestions,
            }

        if any("Undefined control sequence" in line for line in error_lines):
            # Extract the undefined command if possible
            undefined_cmd = None
            for line in error_lines:
                match = re.search(r"Undefined control sequence.*?\\?(\w+)", line)
                if match:
                    undefined_cmd = match.group(1)
                    break
            
            suggestions.append(
                f"Missing LaTeX command or package: {undefined_cmd or 'unknown'}"
            )
            suggestions.append(
                "Try adding the required package with \\usepackage{<package>}"
            )
            return {
                "message": f"Undefined LaTeX control sequence: {undefined_cmd or 'unknown'}",
                "error_type": "UNDEFINED_CONTROL",
                "details": {
                    "stderr": stderr,
                    "stdout": stdout,
                    "undefined_command": undefined_cmd,
                },
                "suggestions": suggestions,
            }

        if any("File not found" in line or "not found" in line.lower() for line in error_lines):
            # Extract missing file if possible
            missing_file = None
            for line in error_lines:
                match = re.search(r"File.*?not found.*?([^\s]+)", line, re.IGNORECASE)
                if match:
                    missing_file = match.group(1)
                    break
            
            suggestions.append(f"Missing file: {missing_file or 'unknown'}")
            suggestions.append("Ensure all referenced files are included in the archive")
            return {
                "message": f"Required file not found: {missing_file or 'unknown'}",
                "error_type": "FILE_NOT_FOUND",
                "details": {
                    "stderr": stderr,
                    "stdout": stdout,
                    "missing_file": missing_file,
                },
                "suggestions": suggestions,
            }

        if any("Emergency stop" in line for line in error_lines):
            suggestions.append("Check LaTeX syntax for errors before the emergency stop")
            suggestions.append("Review the error log for specific line numbers")
            return {
                "message": "LaTeX emergency stop",
                "error_type": "EMERGENCY_STOP",
                "details": {"stderr": stderr, "stdout": stdout},
                "suggestions": suggestions,
            }

        # Check for missing packages
        if any("package" in line.lower() and "not found" in line.lower() for line in error_lines):
            suggestions.append("Install missing LaTeX packages using tlmgr or apt")
            return {
                "message": "Missing LaTeX package",
                "error_type": "MISSING_PACKAGE",
                "details": {"stderr": stderr, "stdout": stdout},
                "suggestions": suggestions,
            }

        # Generic error
        error_message = error_lines[-1] if error_lines else "Unknown LaTeXML error"
        suggestions.append("Review LaTeXML error output for specific issues")
        suggestions.append("Check that input file is valid LaTeX")
        return {
            "message": error_message,
            "error_type": "CONVERSION_ERROR",
            "details": {"stderr": stderr, "stdout": stdout},
            "suggestions": suggestions,
        }

    def _parse_conversion_result(
        self,
        input_file: Path,
        output_file: Path,
        stdout: str,
        stderr: str,
        settings: LaTeXMLSettings,
    ) -> dict[str, Any]:
        """
        Parse LaTeXML conversion results.

        Args:
            input_file: Input file path
            output_file: Output file path
            stdout: Standard output
            stderr: Standard error

        Returns:
            Dict with conversion results
        """
        # Get output file info
        output_info = get_file_info(output_file) if output_file.exists() else {}

        # Extract warnings and info from stderr
        warnings = self._extract_warnings(stderr)
        info_messages = self._extract_info_messages(stdout)

        return {
            "success": True,
            "input_file": str(input_file),
            "output_file": str(output_file),
            "output_size": output_info.get("size", 0),
            "warnings": warnings,
            "info_messages": info_messages,
            "conversion_time": None,  # Could be added with timing
            "format": settings.output_format,
            "mathml_included": settings.include_mathml,
            "css_included": settings.include_css,
            "javascript_included": settings.include_javascript,
        }

    def _extract_warnings(self, stderr: str) -> list[str]:
        """Extract warning messages from stderr."""
        if not stderr:
            return []

        warnings = []
        for line in stderr.split("\n"):
            line = line.strip()
            if "warning" in line.lower() and line:
                warnings.append(line)

        return warnings

    def _extract_info_messages(self, stdout: str) -> list[str]:
        """Extract info messages from stdout."""
        if not stdout:
            return []

        info_messages = []
        for line in stdout.split("\n"):
            line = line.strip()
            if line and not line.startswith("["):  # Skip LaTeXML progress indicators
                info_messages.append(line)

        return info_messages

    def get_supported_formats(self) -> list[str]:
        """Get list of supported output formats."""
        return ["html", "xml", "tex", "box"]

    def get_version_info(self) -> dict[str, str]:
        """Get LaTeXML version information."""
        try:
            result = run_command_safely(
                [self.settings.latexml_path, "--help"], timeout=10
            )
            # Extract version from help output
            for line in result.stdout.split("\n"):
                if "LaTeXML version" in line:
                    version = line.split("LaTeXML version")[1].strip()
                    return {
                        "version": version,
                        "executable": self.settings.latexml_path,
                    }

            return {"version": "unknown", "executable": self.settings.latexml_path}
        except Exception as exc:
            logger.warning("Failed to get LaTeXML version: %s", exc)
            return {"version": "unknown", "executable": self.settings.latexml_path}
