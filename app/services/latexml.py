"""
LaTeXML service for TeX to XML/HTML conversion.

This module provides the LaTeXMLService class for converting LaTeX documents
to XML/HTML using LaTeXML with proper error handling and configuration.
"""

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.config.latexml import LaTeXMLSettings, LaTeXMLConversionOptions
from app.utils.shell import run_command_safely, CommandResult
from app.utils.fs import ensure_directory, cleanup_directory, get_file_info

logger = logging.getLogger(__name__)


class LaTeXMLError(Exception):
    """Base exception for LaTeXML-related errors."""
    
    def __init__(self, message: str, error_type: str = "LATEXML_ERROR", details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.error_type = error_type
        self.details = details or {}


class LaTeXMLTimeoutError(LaTeXMLError):
    """Raised when LaTeXML conversion times out."""
    
    def __init__(self, timeout_seconds: int):
        super().__init__(
            f"LaTeXML conversion timed out after {timeout_seconds} seconds",
            "TIMEOUT_ERROR",
            {"timeout_seconds": timeout_seconds}
        )


class LaTeXMLFileError(LaTeXMLError):
    """Raised when there are file-related errors."""
    
    def __init__(self, message: str, file_path: str):
        super().__init__(message, "FILE_ERROR", {"file_path": file_path})


class LaTeXMLConversionError(LaTeXMLError):
    """Raised when LaTeXML conversion fails."""
    
    def __init__(self, message: str, error_type: str = "CONVERSION_ERROR", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_type, details)


class LaTeXMLSecurityError(LaTeXMLError):
    """Raised when security validation fails."""
    
    def __init__(self, message: str, violation: str):
        super().__init__(message, "SECURITY_ERROR", {"violation": violation})


class LaTeXMLService:
    """Service for LaTeXML TeX to XML/HTML conversion."""
    
    def __init__(self, settings: Optional[LaTeXMLSettings] = None):
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
            result = run_command_safely([self.settings.latexml_path, "--help"], timeout=10)
            if result.returncode != 0:
                raise LaTeXMLFileError(
                    f"LaTeXML not found or not working: {self.settings.latexml_path}",
                    self.settings.latexml_path
                )
            logger.info("LaTeXML verified: %s", self.settings.latexml_path)
        except Exception as exc:
            raise LaTeXMLFileError(
                f"Failed to verify LaTeXML installation: {exc}",
                self.settings.latexml_path
            )
    
    def convert_tex_to_html(
        self,
        input_file: Path,
        output_dir: Path,
        options: Optional[LaTeXMLConversionOptions] = None
    ) -> Dict[str, Any]:
        """
        Convert TeX file to HTML using LaTeXML.
        
        Args:
            input_file: Path to input TeX file
            output_dir: Directory for output files
            options: Conversion options
            
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
        if options:
            settings = options.to_latexml_settings()
        else:
            settings = self.settings
        
        # Ensure output directory exists
        try:
            ensure_directory(output_dir)
        except Exception as exc:
            raise LaTeXMLFileError(f"Failed to create output directory: {exc}", str(output_dir))
        
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
            env_vars = settings.get_environment_vars()
            
            logger.info("Converting TeX to %s: %s -> %s", settings.output_format.upper(), input_file, output_file)
            logger.debug("LaTeXML command: %s", ' '.join(cmd))
            
            try:
                # Run LaTeXML conversion
                result = run_command_safely(
                    cmd,
                    cwd=input_file.parent,
                    timeout=settings.conversion_timeout,
                    env=env_vars
                )
                
                if result.returncode != 0:
                    error_info = self._parse_conversion_error(result.stderr, result.stdout)
                    logger.error("LaTeXML conversion failed: %s", error_info['message'])
                    raise LaTeXMLConversionError(
                        error_info['message'],
                        error_info['error_type'],
                        error_info['details']
                    )
                
                # Parse conversion results
                conversion_result = self._parse_conversion_result(
                    input_file, output_file, result.stdout, result.stderr
                )
                
                # Validate output file was created
                if not output_file.exists():
                    raise LaTeXMLFileError("Conversion completed but no output file was created", str(output_file))
                
                logger.info("Conversion successful: %s", output_file)
                return conversion_result
                
            except subprocess.TimeoutExpired as exc:
                raise LaTeXMLTimeoutError(settings.conversion_timeout)
            except LaTeXMLConversionError:
                # Re-raise our custom errors
                raise
            except Exception as exc:
                logger.error("Unexpected conversion error: %s", exc)
                raise LaTeXMLConversionError(f"Unexpected conversion error: {exc}", "UNKNOWN_ERROR")
    
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
            raise LaTeXMLFileError(f"Input file not found: {input_file}", str(input_file))
        
        if not input_file.is_file():
            raise LaTeXMLFileError(f"Input path is not a file: {input_file}", str(input_file))
        
        # Check file extension
        if input_file.suffix.lower() not in self.settings.allowed_extensions:
            raise LaTeXMLSecurityError(
                f"File extension not allowed: {input_file.suffix}",
                f"extension_{input_file.suffix}"
            )
        
        # Check file size
        try:
            file_info = get_file_info(input_file)
            if file_info['size'] > self.settings.max_file_size:
                raise LaTeXMLSecurityError(
                    f"File too large: {file_info['size']} bytes (max: {self.settings.max_file_size})",
                    "file_size_exceeded"
                )
        except Exception as exc:
            raise LaTeXMLFileError(f"Failed to get file info: {exc}", str(input_file))
        
        # Check for dangerous patterns in filename
        dangerous_patterns = ['..', '/', '\\', '~', '$', '`']
        filename = input_file.name.lower()
        for pattern in dangerous_patterns:
            if pattern in filename:
                raise LaTeXMLSecurityError(
                    f"Dangerous pattern in filename: {pattern}",
                    f"dangerous_pattern_{pattern}"
                )
    
    def _parse_conversion_error(self, stderr: str, stdout: str) -> Dict[str, Any]:
        """
        Parse LaTeXML error output to categorize errors.
        
        Args:
            stderr: Standard error output
            stdout: Standard output
            
        Returns:
            Dict with error information
        """
        error_lines = stderr.strip().split('\n') if stderr else []
        output_lines = stdout.strip().split('\n') if stdout else []
        
        # Common LaTeXML error patterns
        if any("Fatal error" in line for line in error_lines):
            return {
                "message": "LaTeXML fatal error occurred",
                "error_type": "FATAL_ERROR",
                "details": {"stderr": stderr, "stdout": stdout}
            }
        
        if any("Undefined control sequence" in line for line in error_lines):
            return {
                "message": "Undefined LaTeX control sequence",
                "error_type": "UNDEFINED_CONTROL",
                "details": {"stderr": stderr, "stdout": stdout}
            }
        
        if any("File not found" in line for line in error_lines):
            return {
                "message": "Required file not found",
                "error_type": "FILE_NOT_FOUND",
                "details": {"stderr": stderr, "stdout": stdout}
            }
        
        if any("Emergency stop" in line for line in error_lines):
            return {
                "message": "LaTeX emergency stop",
                "error_type": "EMERGENCY_STOP",
                "details": {"stderr": stderr, "stdout": stdout}
            }
        
        # Generic error
        error_message = error_lines[-1] if error_lines else "Unknown LaTeXML error"
        return {
            "message": error_message,
            "error_type": "CONVERSION_ERROR",
            "details": {"stderr": stderr, "stdout": stdout}
        }
    
    def _parse_conversion_result(
        self,
        input_file: Path,
        output_file: Path,
        stdout: str,
        stderr: str
    ) -> Dict[str, Any]:
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
            "output_size": output_info.get('size', 0),
            "warnings": warnings,
            "info_messages": info_messages,
            "conversion_time": None,  # Could be added with timing
            "format": self.settings.output_format,
            "mathml_included": self.settings.include_mathml,
            "css_included": self.settings.include_css,
            "javascript_included": self.settings.include_javascript,
        }
    
    def _extract_warnings(self, stderr: str) -> List[str]:
        """Extract warning messages from stderr."""
        if not stderr:
            return []
        
        warnings = []
        for line in stderr.split('\n'):
            line = line.strip()
            if 'warning' in line.lower() and line:
                warnings.append(line)
        
        return warnings
    
    def _extract_info_messages(self, stdout: str) -> List[str]:
        """Extract info messages from stdout."""
        if not stdout:
            return []
        
        info_messages = []
        for line in stdout.split('\n'):
            line = line.strip()
            if line and not line.startswith('['):  # Skip LaTeXML progress indicators
                info_messages.append(line)
        
        return info_messages
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported output formats."""
        return ["html", "xml", "tex", "box"]
    
    def get_version_info(self) -> Dict[str, str]:
        """Get LaTeXML version information."""
        try:
            result = run_command_safely([self.settings.latexml_path, "--help"], timeout=10)
            # Extract version from help output
            for line in result.stdout.split('\n'):
                if 'LaTeXML version' in line:
                    version = line.split('LaTeXML version')[1].strip()
                    return {"version": version, "executable": self.settings.latexml_path}
            
            return {"version": "unknown", "executable": self.settings.latexml_path}
        except Exception as exc:
            logger.warning("Failed to get LaTeXML version: %s", exc)
            return {"version": "unknown", "executable": self.settings.latexml_path}
