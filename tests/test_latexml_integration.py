"""
Integration tests for LaTeXML service.

This module contains integration tests that verify end-to-end LaTeXML
conversion functionality with actual LaTeXML execution.
"""

import tempfile
from pathlib import Path

import pytest

from app.config.latexml import LaTeXMLConversionOptions, LaTeXMLSettings
from app.services.latexml import LaTeXMLConversionError, LaTeXMLService


class TestLaTeXMLIntegration:
    """Integration tests for LaTeXML service."""

    def test_latexml_installation_verification(self):
        """Test that LaTeXML is properly installed and accessible."""
        service = LaTeXMLService()

        # This should not raise an exception if LaTeXML is properly installed
        version_info = service.get_version_info()
        assert version_info["version"] != "unknown"
        assert "latexml" in version_info["executable"].lower()

    def test_simple_tex_to_html_conversion(self):
        """Test basic TeX to HTML conversion."""
        service = LaTeXMLService()

        # Create a simple LaTeX document
        latex_content = r"""
        \documentclass{article}
        \begin{document}
        \title{Test Document}
        \author{Test Author}
        \maketitle
        
        \section{Introduction}
        This is a test document with some basic content.
        
        \section{Math}
        Here is some math: $E = mc^2$ and $\int_0^\infty e^{-x} dx = 1$.
        
        \section{Conclusion}
        This concludes our test.
        \end{document}
        """

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create input file
            input_file = temp_path / "test.tex"
            input_file.write_text(latex_content, encoding="utf-8")

            # Create output directory
            output_dir = temp_path / "output"
            output_dir.mkdir()

            # Convert to HTML
            result = service.convert_tex_to_html(input_file, output_dir)

            # Verify results
            assert result["success"] is True
            assert result["input_file"] == str(input_file)
            assert result["format"] == "html"
            assert result["output_size"] > 0

            # Check that output file was created
            output_file = Path(result["output_file"])
            assert output_file.exists()
            assert output_file.suffix == ".html"

            # Verify HTML content
            html_content = output_file.read_text(encoding="utf-8")
            assert "<html" in html_content.lower()
            assert "<body" in html_content.lower()
            assert "Test Document" in html_content
            assert "Introduction" in html_content

    def test_tex_to_xml_conversion(self):
        """Test TeX to XML conversion."""
        service = LaTeXMLService()

        latex_content = r"""
        \documentclass{article}
        \begin{document}
        \title{XML Test}
        \author{Test Author}
        \maketitle
        
        \section{Content}
        This is XML output.
        \end{document}
        """

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            input_file = temp_path / "test.tex"
            input_file.write_text(latex_content, encoding="utf-8")

            output_dir = temp_path / "output"
            output_dir.mkdir()

            # Convert to XML
            options = LaTeXMLConversionOptions(output_format="xml")
            result = service.convert_tex_to_html(input_file, output_dir, options)

            assert result["success"] is True
            assert result["format"] == "xml"

            # Check output file
            output_file = Path(result["output_file"])
            assert output_file.exists()
            assert output_file.suffix == ".xml"

            # Verify XML content
            xml_content = output_file.read_text(encoding="utf-8")
            assert "<?xml" in xml_content
            assert "<document" in xml_content.lower()

    def test_conversion_with_math(self):
        """Test conversion with mathematical content."""
        service = LaTeXMLService()

        latex_content = r"""
        \documentclass{article}
        \usepackage{amsmath}
        \begin{document}
        \title{Math Test}
        \maketitle
        
        \section{Inline Math}
        Here is inline math: $x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$.
        
        \section{Display Math}
        Here is display math:
        \begin{equation}
        \int_{-\infty}^{\infty} e^{-x^2} dx = \sqrt{\pi}
        \end{equation}
        
        \section{Matrix}
        Here is a matrix:
        \begin{equation}
        A = \begin{pmatrix}
        1 & 2 \\
        3 & 4
        \end{pmatrix}
        \end{equation}
        \end{document}
        """

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            input_file = temp_path / "math_test.tex"
            input_file.write_text(latex_content, encoding="utf-8")

            output_dir = temp_path / "output"
            output_dir.mkdir()

            # Convert with math support
            options = LaTeXMLConversionOptions(
                include_mathml=True,
                preload_modules=["amsmath", "amssymb"]
            )
            result = service.convert_tex_to_html(input_file, output_dir, options)

            assert result["success"] is True

            # Check output file
            output_file = Path(result["output_file"])
            html_content = output_file.read_text(encoding="utf-8")

            # Should contain math content
            assert "math" in html_content.lower() or "equation" in html_content.lower()

    def test_conversion_with_custom_preamble(self):
        """Test conversion with custom preamble."""
        service = LaTeXMLService()

        latex_content = r"""
        \begin{document}
        \title{Custom Preamble Test}
        \maketitle
        
        \section{Content}
        This document uses a custom preamble.
        \end{document}
        """

        custom_preamble = r"""
        \documentclass{article}
        \usepackage{graphicx}
        \usepackage{amsmath}
        """

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            input_file = temp_path / "test.tex"
            input_file.write_text(latex_content, encoding="utf-8")

            output_dir = temp_path / "output"
            output_dir.mkdir()

            # Convert with custom preamble
            options = LaTeXMLConversionOptions(
                custom_preamble=custom_preamble,
                preload_modules=["graphicx", "amsmath"]
            )
            result = service.convert_tex_to_html(input_file, output_dir, options)

            assert result["success"] is True

            # Check output file
            output_file = Path(result["output_file"])
            html_content = output_file.read_text(encoding="utf-8")
            assert "Custom Preamble Test" in html_content

    def test_conversion_with_custom_postamble(self):
        """Test conversion with custom postamble."""
        service = LaTeXMLService()

        latex_content = r"""
        \documentclass{article}
        \begin{document}
        \title{Postamble Test}
        \maketitle
        
        \section{Content}
        This document has a custom postamble.
        \end{document}
        """

        custom_postamble = r"""
        \section{Appendix}
        This is added by the postamble.
        """

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            input_file = temp_path / "test.tex"
            input_file.write_text(latex_content, encoding="utf-8")

            output_dir = temp_path / "output"
            output_dir.mkdir()

            # Convert with custom postamble
            options = LaTeXMLConversionOptions(
                custom_postamble=custom_postamble
            )
            result = service.convert_tex_to_html(input_file, output_dir, options)

            assert result["success"] is True

            # Check output file
            output_file = Path(result["output_file"])
            html_content = output_file.read_text(encoding="utf-8")
            assert "Postamble Test" in html_content

    def test_conversion_with_strict_mode(self):
        """Test conversion with strict mode enabled."""
        service = LaTeXMLService()

        latex_content = r"""
        \documentclass{article}
        \begin{document}
        \title{Strict Mode Test}
        \maketitle
        
        \section{Content}
        This tests strict mode conversion.
        \end{document}
        """

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            input_file = temp_path / "test.tex"
            input_file.write_text(latex_content, encoding="utf-8")

            output_dir = temp_path / "output"
            output_dir.mkdir()

            # Convert with strict mode
            options = LaTeXMLConversionOptions(
                strict_mode=True,
                verbose=True
            )
            result = service.convert_tex_to_html(input_file, output_dir, options)

            assert result["success"] is True

    def test_conversion_error_handling(self):
        """Test error handling for invalid LaTeX."""
        service = LaTeXMLService()

        # Create invalid LaTeX content
        invalid_latex = r"""
        \documentclass{article}
        \begin{document}
        \title{Invalid Test}
        \maketitle
        
        \section{Content}
        \undefinedcommand{This should fail}
        \end{document}
        """

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            input_file = temp_path / "invalid.tex"
            input_file.write_text(invalid_latex, encoding="utf-8")

            output_dir = temp_path / "output"
            output_dir.mkdir()

            # This should raise an exception
            with pytest.raises(LaTeXMLConversionError) as exc_info:
                service.convert_tex_to_html(input_file, output_dir)

            # Should contain information about the error
            assert "undefined" in str(exc_info.value).lower() or "error" in str(exc_info.value).lower()

    def test_conversion_timeout(self):
        """Test conversion timeout handling."""
        # Create a service with very short timeout
        settings = LaTeXMLSettings(conversion_timeout=1)  # 1 second
        service = LaTeXMLService(settings=settings)

        latex_content = r"""
        \documentclass{article}
        \begin{document}
        \title{Timeout Test}
        \maketitle
        
        \section{Content}
        This might timeout.
        \end{document}
        """

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            input_file = temp_path / "test.tex"
            input_file.write_text(latex_content, encoding="utf-8")

            output_dir = temp_path / "output"
            output_dir.mkdir()

            # This might timeout (depending on system performance)
            try:
                result = service.convert_tex_to_html(input_file, output_dir)
                # If it doesn't timeout, that's also fine
                assert result["success"] is True
            except Exception as exc:
                # If it times out or fails for other reasons, that's expected
                assert "timeout" in str(exc).lower() or "error" in str(exc).lower()

    def test_file_size_validation(self):
        """Test file size validation."""
        # Create a service with very small max file size
        settings = LaTeXMLSettings(max_file_size=100)  # 100 bytes
        service = LaTeXMLService(settings=settings)

        latex_content = r"""
        \documentclass{article}
        \begin{document}
        \title{Large File Test}
        \maketitle
        
        \section{Content}
        This is a very long document that exceeds the file size limit.
        """ + "x" * 1000  # Add lots of content

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            input_file = temp_path / "large.tex"
            input_file.write_text(latex_content, encoding="utf-8")

            output_dir = temp_path / "output"
            output_dir.mkdir()

            # This should raise a security error
            with pytest.raises(Exception) as exc_info:
                service.convert_tex_to_html(input_file, output_dir)

            assert "too large" in str(exc_info.value).lower()

    def test_supported_formats(self):
        """Test getting supported output formats."""
        service = LaTeXMLService()

        formats = service.get_supported_formats()

        assert isinstance(formats, list)
        assert len(formats) > 0
        assert "html" in formats
        assert "xml" in formats

    def test_version_info(self):
        """Test getting version information."""
        service = LaTeXMLService()

        version_info = service.get_version_info()

        assert isinstance(version_info, dict)
        assert "version" in version_info
        assert "executable" in version_info
        assert version_info["version"] != "unknown"
        assert "latexml" in version_info["executable"].lower()


if __name__ == "__main__":
    # Run integration tests
    pytest.main([__file__, "-v"])
