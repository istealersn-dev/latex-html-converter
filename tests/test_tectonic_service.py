"""
Test the Tectonic service functionality.
"""

import tempfile
from pathlib import Path

import pytest

from app.services.tectonic import (
    TectonicCompilationError,
    TectonicFileError,
    TectonicSecurityError,
    TectonicService,
    TectonicTimeoutError,
)


class TestTectonicService:
    """Test Tectonic service functionality."""

    def test_service_initialization(self):
        """Test that the service initializes correctly."""
        service = TectonicService(tectonic_path="/opt/homebrew/bin/tectonic")
        assert service.tectonic_path == "/opt/homebrew/bin/tectonic"

    def test_service_with_custom_path(self):
        """Test service with custom tectonic path."""
        service = TectonicService(tectonic_path="/usr/bin/tectonic")
        assert service.tectonic_path == "/usr/bin/tectonic"

    def test_verify_tectonic_success(self):
        """Test successful Tectonic verification."""
        service = TectonicService(tectonic_path="/opt/homebrew/bin/tectonic")
        # This should not raise an exception if Tectonic is installed
        service._verify_tectonic()

    def test_validate_input_file_security_valid(self):
        """Test security validation with valid file."""
        service = TectonicService(tectonic_path="/opt/homebrew/bin/tectonic")
        
        # Create a temporary .tex file
        with tempfile.NamedTemporaryFile(suffix='.tex', delete=False) as f:
            f.write(b'\\documentclass{article}\\begin{document}Hello\\end{document}')
            temp_file = Path(f.name)
        
        try:
            # This should not raise an exception
            service._validate_input_file_security(temp_file)
        finally:
            temp_file.unlink()

    def test_validate_input_file_security_invalid_extension(self):
        """Test security validation with invalid file extension."""
        service = TectonicService(tectonic_path="/opt/homebrew/bin/tectonic")
        
        # Create a temporary file with wrong extension
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            f.write(b'Some content')
            temp_file = Path(f.name)
        
        try:
            with pytest.raises(TectonicSecurityError) as exc_info:
                service._validate_input_file_security(temp_file)
            assert exc_info.value.error_type == "INVALID_EXTENSION"
        finally:
            temp_file.unlink()

    def test_validate_input_file_security_dangerous_filename(self):
        """Test security validation with dangerous filename."""
        service = TectonicService(tectonic_path="/opt/homebrew/bin/tectonic")
        
        # Create a temporary file with dangerous characters
        with tempfile.NamedTemporaryFile(suffix='.tex', prefix='dangerous..', delete=False) as f:
            f.write(b'\\documentclass{article}\\begin{document}Hello\\end{document}')
            temp_file = Path(f.name)
        
        try:
            with pytest.raises(TectonicSecurityError) as exc_info:
                service._validate_input_file_security(temp_file)
            assert exc_info.value.error_type == "DANGEROUS_FILENAME"
        finally:
            temp_file.unlink()

    def test_parse_compilation_error_emergency_stop(self):
        """Test parsing emergency stop error."""
        service = TectonicService(tectonic_path="/opt/homebrew/bin/tectonic")
        
        stderr = "! Emergency stop. Some error occurred."
        stdout = ""
        
        error_info = service._parse_compilation_error(stderr, stdout)
        
        assert error_info["error_type"] == "EMERGENCY_STOP"
        assert "emergency" in error_info["message"].lower()

    def test_parse_compilation_error_undefined_control(self):
        """Test parsing undefined control sequence error."""
        service = TectonicService(tectonic_path="/opt/homebrew/bin/tectonic")
        
        stderr = "! Undefined control sequence. \\undefinedcommand"
        stdout = ""
        
        error_info = service._parse_compilation_error(stderr, stdout)
        
        assert error_info["error_type"] == "UNDEFINED_CONTROL"
        assert "undefined" in error_info["message"].lower()

    def test_parse_compilation_error_file_not_found(self):
        """Test parsing file not found error."""
        service = TectonicService(tectonic_path="/opt/homebrew/bin/tectonic")
        
        stderr = "! LaTeX Error: File `missing.sty' not found."
        stdout = ""
        
        error_info = service._parse_compilation_error(stderr, stdout)
        
        assert error_info["error_type"] == "FILE_NOT_FOUND"
        assert "file not found" in error_info["message"].lower()

    def test_build_command_basic(self):
        """Test basic command building."""
        service = TectonicService(tectonic_path="/opt/homebrew/bin/tectonic")
        
        input_file = Path("test.tex")
        output_dir = Path("output")
        options = None
        
        cmd = service._build_command(input_file, output_dir, options)
        
        assert cmd[0] == "/opt/homebrew/bin/tectonic"
        assert "--keep-logs" in cmd
        assert "--keep-intermediates" in cmd
        assert "--untrusted" in cmd
        assert "--outdir" in cmd
        assert str(output_dir) in cmd
        assert str(input_file) in cmd

    def test_build_command_with_options(self):
        """Test command building with options."""
        service = TectonicService(tectonic_path="/opt/homebrew/bin/tectonic")
        
        input_file = Path("test.tex")
        output_dir = Path("output")
        options = {
            "engine": "xelatex",
            "format": "latex",
            "extra_args": ["--verbose"]
        }
        
        cmd = service._build_command(input_file, output_dir, options)
        
        assert "--engine=xelatex" in cmd
        assert "--format=latex" in cmd
        assert "--verbose" in cmd

    def test_cleanup_auxiliary_files(self):
        """Test auxiliary file cleanup."""
        service = TectonicService(tectonic_path="/opt/homebrew/bin/tectonic")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create some auxiliary files
            aux_files = [
                "test.aux",
                "test.log",
                "test.toc",
                "test.bbl",
                "test.blg"
            ]
            
            for aux_file in aux_files:
                (temp_path / aux_file).write_text("dummy content")
            
            # Also create a non-auxiliary file
            (temp_path / "test.pdf").write_text("dummy content")
            
            # Run cleanup
            service.cleanup_auxiliary_files(temp_path)
            
            # Check that auxiliary files are gone
            for aux_file in aux_files:
                assert not (temp_path / aux_file).exists()
            
            # Check that non-auxiliary file remains
            assert (temp_path / "test.pdf").exists()

    def test_get_compilation_info(self):
        """Test compilation info retrieval."""
        service = TectonicService(tectonic_path="/opt/homebrew/bin/tectonic")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create some test files
            (temp_path / "output.pdf").write_text("PDF content")
            (temp_path / "output.log").write_text("Log content")
            
            info = service.get_compilation_info(temp_path)
            
            assert info["output_dir"] == str(temp_path)
            assert len(info["files"]) == 2
            assert info["total_size"] > 0
            
            # Check file info
            file_names = [f["name"] for f in info["files"]]
            assert "output.pdf" in file_names
            assert "output.log" in file_names
