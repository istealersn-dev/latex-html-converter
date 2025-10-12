"""
Unit tests for LaTeXML service.

This module contains comprehensive unit tests for the LaTeXMLService class,
testing all major functionality including conversion, error handling, and configuration.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from app.configs.latexml import LaTeXMLConversionOptions, LaTeXMLSettings
from app.services.latexml import (
    LaTeXMLConversionError,
    LaTeXMLFileError,
    LaTeXMLSecurityError,
    LaTeXMLService,
    LaTeXMLTimeoutError,
)


class TestLaTeXMLService:
    """Test cases for LaTeXMLService class."""

    def test_service_initialization(self):
        """Test service initialization with default settings."""
        service = LaTeXMLService()
        assert service.settings is not None
        assert isinstance(service.settings, LaTeXMLSettings)

    def test_service_initialization_with_custom_settings(self):
        """Test service initialization with custom settings."""
        custom_settings = LaTeXMLSettings(
            latexml_path="/custom/path/latexml",
            output_format="xml",
            strict_mode=True
        )
        service = LaTeXMLService(settings=custom_settings)
        assert service.settings == custom_settings
        assert service.settings.latexml_path == "/custom/path/latexml"
        assert service.settings.output_format == "xml"
        assert service.settings.strict_mode is True

    @patch('app.services.latexml.run_command_safely')
    def test_verify_latexml_installation_success(self, mock_run_command):
        """Test successful LaTeXML installation verification."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_run_command.return_value = mock_result

        service = LaTeXMLService()
        # Should not raise any exception
        assert service is not None

    @patch('app.services.latexml.run_command_safely')
    def test_verify_latexml_installation_failure(self, mock_run_command):
        """Test LaTeXML installation verification failure."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_run_command.return_value = mock_result

        with pytest.raises(LaTeXMLFileError) as exc_info:
            LaTeXMLService()

        assert "LaTeXML not found or not working" in str(exc_info.value)

    def test_validate_input_file_not_found(self):
        """Test input file validation when file doesn't exist."""
        service = LaTeXMLService()
        non_existent_file = Path("/non/existent/file.tex")

        with pytest.raises(LaTeXMLFileError) as exc_info:
            service._validate_input_file(non_existent_file)

        assert "Input file not found" in str(exc_info.value)

    def test_validate_input_file_not_a_file(self):
        """Test input file validation when path is not a file."""
        service = LaTeXMLService()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            with pytest.raises(LaTeXMLFileError) as exc_info:
                service._validate_input_file(temp_path)

            assert "Input path is not a file" in str(exc_info.value)

    def test_validate_input_file_invalid_extension(self):
        """Test input file validation with invalid extension."""
        service = LaTeXMLService()

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            temp_file = Path(f.name)

        try:
            with pytest.raises(LaTeXMLSecurityError) as exc_info:
                service._validate_input_file(temp_file)

            assert "File extension not allowed" in str(exc_info.value)
        finally:
            temp_file.unlink()

    def test_validate_input_file_too_large(self):
        """Test input file validation when file is too large."""
        # Create a service with very small max file size
        settings = LaTeXMLSettings(max_file_size=100)  # 100 bytes
        service = LaTeXMLService(settings=settings)

        with tempfile.NamedTemporaryFile(suffix=".tex", delete=False) as f:
            # Write content larger than 100 bytes
            f.write(b"x" * 200)
            temp_file = Path(f.name)

        try:
            with pytest.raises(LaTeXMLSecurityError) as exc_info:
                service._validate_input_file(temp_file)

            assert "File too large" in str(exc_info.value)
        finally:
            temp_file.unlink()

    def test_validate_input_file_dangerous_filename(self):
        """Test input file validation with dangerous filename patterns."""
        service = LaTeXMLService()

        with tempfile.NamedTemporaryFile(suffix=".tex", delete=False) as f:
            temp_file = Path(f.name)
            # Rename to include dangerous pattern
            dangerous_file = temp_file.parent / "test..tex"
            temp_file.rename(dangerous_file)

        try:
            with pytest.raises(LaTeXMLSecurityError) as exc_info:
                service._validate_input_file(dangerous_file)

            assert "Dangerous pattern in filename" in str(exc_info.value)
        finally:
            if dangerous_file.exists():
                dangerous_file.unlink()

    def test_parse_conversion_error_fatal_error(self):
        """Test parsing fatal error from LaTeXML output."""
        service = LaTeXMLService()

        stderr = "Fatal error: Something went wrong"
        stdout = "Some output"

        result = service._parse_conversion_error(stderr, stdout)

        assert result["error_type"] == "FATAL_ERROR"
        assert "fatal error" in result["message"].lower()
        assert result["details"]["stderr"] == stderr

    def test_parse_conversion_error_undefined_control(self):
        """Test parsing undefined control sequence error."""
        service = LaTeXMLService()

        stderr = "Undefined control sequence \\undefinedcommand"
        stdout = ""

        result = service._parse_conversion_error(stderr, stdout)

        assert result["error_type"] == "UNDEFINED_CONTROL"
        assert "undefined" in result["message"].lower()

    def test_parse_conversion_error_file_not_found(self):
        """Test parsing file not found error."""
        service = LaTeXMLService()

        stderr = "File not found: missing.tex"
        stdout = ""

        result = service._parse_conversion_error(stderr, stdout)

        assert result["error_type"] == "FILE_NOT_FOUND"
        assert "file not found" in result["message"].lower()

    def test_parse_conversion_error_emergency_stop(self):
        """Test parsing emergency stop error."""
        service = LaTeXMLService()

        stderr = "Emergency stop"
        stdout = ""

        result = service._parse_conversion_error(stderr, stdout)

        assert result["error_type"] == "EMERGENCY_STOP"
        assert "emergency stop" in result["message"].lower()

    def test_parse_conversion_error_generic(self):
        """Test parsing generic error."""
        service = LaTeXMLService()

        stderr = "Some random error message"
        stdout = ""

        result = service._parse_conversion_error(stderr, stdout)

        assert result["error_type"] == "CONVERSION_ERROR"
        assert result["message"] == "Some random error message"

    def test_parse_conversion_result_success(self):
        """Test parsing successful conversion result."""
        service = LaTeXMLService()

        with tempfile.NamedTemporaryFile(suffix=".tex", delete=False) as input_file:
            input_path = Path(input_file.name)

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as output_file:
            output_path = Path(output_file.name)
            output_path.write_text("<html><body>Test</body></html>")

        try:
            stdout = "Conversion successful"
            stderr = ""

            result = service._parse_conversion_result(input_path, output_path, stdout, stderr)

            assert result["success"] is True
            assert result["input_file"] == str(input_path)
            assert result["output_file"] == str(output_path)
            assert result["output_size"] > 0
            assert result["format"] == service.settings.output_format
        finally:
            input_path.unlink()
            output_path.unlink()

    def test_extract_warnings(self):
        """Test extracting warnings from stderr."""
        service = LaTeXMLService()

        stderr = """
        Some normal output
        Warning: This is a warning
        More output
        Warning: Another warning
        """

        warnings = service._extract_warnings(stderr)

        assert len(warnings) == 2
        assert "This is a warning" in warnings[0]
        assert "Another warning" in warnings[1]

    def test_extract_info_messages(self):
        """Test extracting info messages from stdout."""
        service = LaTeXMLService()

        stdout = """
        [LaTeXML] Processing...
        [LaTeXML] Converting...
        Info: This is an info message
        [LaTeXML] Done
        Another info message
        """

        info_messages = service._extract_info_messages(stdout)

        # Should exclude LaTeXML progress indicators
        assert len(info_messages) == 2
        assert "This is an info message" in info_messages
        assert "Another info message" in info_messages

    def test_get_supported_formats(self):
        """Test getting supported output formats."""
        service = LaTeXMLService()

        formats = service.get_supported_formats()

        assert "html" in formats
        assert "xml" in formats
        assert "tex" in formats
        assert "box" in formats

    @patch('app.services.latexml.run_command_safely')
    def test_get_version_info_success(self, mock_run_command):
        """Test getting version info successfully."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "latexml (LaTeXML version 0.8.8)"
        mock_run_command.return_value = mock_result

        service = LaTeXMLService()
        version_info = service.get_version_info()

        assert version_info["version"] == "0.8.8"
        assert version_info["executable"] == service.settings.latexml_path

    @patch('app.services.latexml.run_command_safely')
    def test_get_version_info_failure(self, mock_run_command):
        """Test getting version info when command fails."""
        mock_run_command.side_effect = Exception("Command failed")

        service = LaTeXMLService()
        version_info = service.get_version_info()

        assert version_info["version"] == "unknown"
        assert version_info["executable"] == service.settings.latexml_path

    @patch('app.services.latexml.run_command_safely')
    def test_convert_tex_to_html_success(self, mock_run_command):
        """Test successful TeX to HTML conversion."""
        # Mock successful command execution
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Conversion successful"
        mock_result.stderr = ""
        mock_run_command.return_value = mock_result

        service = LaTeXMLService()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_file = temp_path / "test.tex"
            input_file.write_text("\\documentclass{article}\\begin{document}Hello\\end{document}")

            output_dir = temp_path / "output"
            output_dir.mkdir()

            # Mock the output file creation
            with patch('pathlib.Path.exists', return_value=True):
                with patch('app.services.latexml.get_file_info', return_value={'size': 1024}):
                    result = service.convert_tex_to_html(input_file, output_dir)

            assert result["success"] is True
            assert result["input_file"] == str(input_file)
            assert result["format"] == "html"

    @patch('app.services.latexml.run_command_safely')
    def test_convert_tex_to_html_timeout(self, mock_run_command):
        """Test TeX to HTML conversion timeout."""
        import subprocess
        mock_run_command.side_effect = subprocess.TimeoutExpired("latexml", 300)

        service = LaTeXMLService()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_file = temp_path / "test.tex"
            input_file.write_text("\\documentclass{article}\\begin{document}Hello\\end{document}")

            output_dir = temp_path / "output"
            output_dir.mkdir()

            with pytest.raises(LaTeXMLTimeoutError) as exc_info:
                service.convert_tex_to_html(input_file, output_dir)

            assert "timed out" in str(exc_info.value)

    @patch('app.services.latexml.run_command_safely')
    def test_convert_tex_to_html_conversion_error(self, mock_run_command):
        """Test TeX to HTML conversion with conversion error."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Fatal error: Conversion failed"
        mock_run_command.return_value = mock_result

        service = LaTeXMLService()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_file = temp_path / "test.tex"
            input_file.write_text("\\documentclass{article}\\begin{document}Hello\\end{document}")

            output_dir = temp_path / "output"
            output_dir.mkdir()

            with pytest.raises(LaTeXMLConversionError) as exc_info:
                service.convert_tex_to_html(input_file, output_dir)

            assert "fatal error" in str(exc_info.value).lower()

    def test_convert_tex_to_html_with_options(self):
        """Test conversion with custom options."""
        service = LaTeXMLService()

        options = LaTeXMLConversionOptions(
            output_format="xml",
            strict_mode=True,
            verbose=True,
            preload_modules=["amsmath", "graphicx"]
        )

        # Test that options are properly converted to settings
        settings = options.to_latexml_settings()

        assert settings.output_format == "xml"
        assert settings.strict_mode is True
        assert settings.verbose_output is True
        assert settings.preload_modules == ["amsmath", "graphicx"]


class TestLaTeXMLConversionOptions:
    """Test cases for LaTeXMLConversionOptions class."""

    def test_default_options(self):
        """Test default conversion options."""
        options = LaTeXMLConversionOptions()

        assert options.output_format == "html"
        assert options.include_mathml is True
        assert options.include_css is True
        assert options.include_javascript is True
        assert options.strict_mode is False
        assert options.verbose is False
        assert "amsmath" in options.preload_modules

    def test_custom_options(self):
        """Test custom conversion options."""
        options = LaTeXMLConversionOptions(
            output_format="xml",
            include_mathml=False,
            strict_mode=True,
            verbose=True,
            preload_modules=["graphicx", "amsmath"]
        )

        assert options.output_format == "xml"
        assert options.include_mathml is False
        assert options.strict_mode is True
        assert options.verbose is True
        assert options.preload_modules == ["graphicx", "amsmath"]

    def test_validate_output_format(self):
        """Test output format validation."""
        # Valid formats
        for format_name in ["html", "xml", "tex", "box"]:
            options = LaTeXMLConversionOptions(output_format=format_name)
            assert options.output_format == format_name.lower()

        # Invalid format
        with pytest.raises(ValueError) as exc_info:
            LaTeXMLConversionOptions(output_format="invalid")

        assert "Output format must be one of" in str(exc_info.value)

    def test_to_latexml_settings(self):
        """Test conversion to LaTeXMLSettings."""
        options = LaTeXMLConversionOptions(
            output_format="xml",
            strict_mode=True,
            verbose=True,
            preload_modules=["graphicx"]
        )

        settings = options.to_latexml_settings()

        assert settings.output_format == "xml"
        assert settings.strict_mode is True
        assert settings.verbose_output is True
        assert settings.preload_modules == ["graphicx"]


class TestLaTeXMLSettings:
    """Test cases for LaTeXMLSettings class."""

    def test_default_settings(self):
        """Test default settings values."""
        settings = LaTeXMLSettings()

        assert settings.latexml_path == "latexml"
        assert settings.output_format == "html"
        assert settings.include_mathml is True
        assert settings.strict_mode is False
        assert settings.conversion_timeout == 300
        assert ".tex" in settings.allowed_extensions

    def test_custom_settings(self):
        """Test custom settings values."""
        settings = LaTeXMLSettings(
            latexml_path="/custom/latexml",
            output_format="xml",
            strict_mode=True,
            conversion_timeout=600
        )

        assert settings.latexml_path == "/custom/latexml"
        assert settings.output_format == "xml"
        assert settings.strict_mode is True
        assert settings.conversion_timeout == 600

    def test_validate_output_format(self):
        """Test output format validation."""
        # Valid formats
        for format_name in ["html", "xml", "tex", "box"]:
            settings = LaTeXMLSettings(output_format=format_name)
            assert settings.output_format == format_name.lower()

        # Invalid format
        with pytest.raises(ValueError) as exc_info:
            LaTeXMLSettings(output_format="invalid")

        assert "Output format must be one of" in str(exc_info.value)

    def test_validate_timeout(self):
        """Test timeout validation."""
        # Valid timeout
        settings = LaTeXMLSettings(conversion_timeout=300)
        assert settings.conversion_timeout == 300

        # Invalid timeout (negative)
        with pytest.raises(ValueError) as exc_info:
            LaTeXMLSettings(conversion_timeout=-1)

        assert "must be positive" in str(exc_info.value)

        # Invalid timeout (too large)
        with pytest.raises(ValueError) as exc_info:
            LaTeXMLSettings(conversion_timeout=4000)

        assert "cannot exceed 1 hour" in str(exc_info.value)

    def test_validate_max_file_size(self):
        """Test max file size validation."""
        # Valid size
        settings = LaTeXMLSettings(max_file_size=1024)
        assert settings.max_file_size == 1024

        # Invalid size (negative)
        with pytest.raises(ValueError) as exc_info:
            LaTeXMLSettings(max_file_size=-1)

        assert "must be positive" in str(exc_info.value)

        # Invalid size (too large)
        with pytest.raises(ValueError) as exc_info:
            LaTeXMLSettings(max_file_size=600 * 1024 * 1024)

        assert "cannot exceed 500MB" in str(exc_info.value)

    def test_validate_extensions(self):
        """Test allowed extensions validation."""
        # Valid extensions
        settings = LaTeXMLSettings(allowed_extensions=[".tex", ".latex"])
        assert settings.allowed_extensions == [".tex", ".latex"]

        # Extensions without dots (should be normalized)
        settings = LaTeXMLSettings(allowed_extensions=["tex", "latex"])
        assert settings.allowed_extensions == [".tex", ".latex"]

        # Empty extensions
        with pytest.raises(ValueError) as exc_info:
            LaTeXMLSettings(allowed_extensions=[])

        assert "At least one extension must be allowed" in str(exc_info.value)

    def test_get_latexml_command(self):
        """Test LaTeXML command generation."""
        settings = LaTeXMLSettings(
            output_format="html",
            strict_mode=True,
            verbose_output=True,
            preload_modules=["amsmath", "graphicx"]
        )

        input_file = Path("test.tex")
        output_file = Path("output.html")

        cmd = settings.get_latexml_command(input_file, output_file)

        assert cmd[0] == "latexml"
        assert "--destination" in cmd
        assert str(output_file) in cmd
        assert "--strict" in cmd
        assert "--verbose" in cmd
        assert "--preload" in cmd
        assert "amsmath" in cmd
        assert "graphicx" in cmd
        assert str(input_file) in cmd

    def test_get_environment_vars(self):
        """Test environment variables generation."""
        settings = LaTeXMLSettings(
            strict_mode=True,
            verbose_output=True,
            temp_dir=Path("/tmp")
        )

        env_vars = settings.get_environment_vars()

        assert env_vars["LATEXML_STRICT"] == "true"
        assert env_vars["LATEXML_VERBOSE"] == "true"
        assert env_vars["TMPDIR"] == "/tmp"
