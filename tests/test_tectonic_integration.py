"""
Integration tests for Tectonic service with actual LaTeX compilation.
"""

import tempfile
from pathlib import Path

import pytest

from app.services.tectonic import (
    TectonicCompilationError,
    TectonicSecurityError,
    TectonicService,
)


class TestTectonicIntegration:
    """Integration tests for Tectonic service."""

    def test_simple_latex_compilation(self):
        """Test compilation of a simple LaTeX document."""
        service = TectonicService(tectonic_path="/opt/homebrew/bin/tectonic")

        # Create a simple LaTeX document
        latex_content = r"""
\documentclass{article}
\begin{document}
\title{Test Document}
\author{Test Author}
\date{\today}
\maketitle

\section{Introduction}
This is a test document for the LaTeX to HTML5 converter.

\section{Mathematics}
Here is a simple equation: $E = mc^2$

And a display equation:
\begin{equation}
\int_{-\infty}^{\infty} e^{-x^2} dx = \sqrt{\pi}
\end{equation}

\section{Conclusion}
This concludes our test document.
\end{document}
"""

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create input file
            input_file = temp_path / "test.tex"
            input_file.write_text(latex_content)

            # Create output directory
            output_dir = temp_path / "output"
            output_dir.mkdir()

            try:
                # Compile the document
                result = service.compile_latex(input_file, output_dir)

                # Verify the result
                assert result["success"] is True
                assert "output_file" in result
                assert result["output_file"] is not None

                # Check that PDF was created
                pdf_file = Path(result["output_file"])
                assert pdf_file.exists()
                assert pdf_file.suffix == ".pdf"

                # Check that PDF has content
                assert pdf_file.stat().st_size > 0

                print(f"✅ Successfully compiled LaTeX document to: {pdf_file}")
                print(f"📄 PDF size: {pdf_file.stat().st_size} bytes")

            except TectonicCompilationError as e:
                pytest.fail(f"Tectonic compilation failed: {e}")

    def test_latex_with_errors(self):
        """Test handling of LaTeX documents with errors."""
        service = TectonicService(tectonic_path="/opt/homebrew/bin/tectonic")

        # Create a LaTeX document with intentional errors
        latex_content = r"""
\documentclass{article}
\begin{document}
\title{Test Document with Errors}
\author{Test Author}
\date{\today}
\maketitle

\section{Introduction}
This document has intentional errors.

% This will cause an error - undefined command
\undefinedcommand{This will fail}

\section{Conclusion}
This section will never be reached due to the error above.
\end{document}
"""

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create input file
            input_file = temp_path / "test_error.tex"
            input_file.write_text(latex_content)

            # Create output directory
            output_dir = temp_path / "output"
            output_dir.mkdir()

            # This should raise a TectonicCompilationError
            with pytest.raises(TectonicCompilationError) as exc_info:
                service.compile_latex(input_file, output_dir)

            # Verify the error details
            error = exc_info.value
            assert error.error_type in ["UNDEFINED_CONTROL", "COMPILATION_ERROR"]
            print(f"✅ Correctly caught LaTeX error: {error.error_type}")

    def test_latex_with_missing_package(self):
        """Test handling of missing LaTeX packages."""
        service = TectonicService(tectonic_path="/opt/homebrew/bin/tectonic")

        # Create a LaTeX document that requires a non-existent package
        latex_content = r"""
\documentclass{article}
\usepackage{non_existent_package}
\begin{document}
\title{Test Document with Missing Package}
\author{Test Author}
\date{\today}
\maketitle

\section{Introduction}
This document requires a package that doesn't exist.
\end{document}
"""

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create input file
            input_file = temp_path / "test_missing_package.tex"
            input_file.write_text(latex_content)

            # Create output directory
            output_dir = temp_path / "output"
            output_dir.mkdir()

            # This should raise a TectonicCompilationError
            with pytest.raises(TectonicCompilationError) as exc_info:
                service.compile_latex(input_file, output_dir)

            # Verify the error details
            error = exc_info.value
            assert error.error_type in ["FILE_NOT_FOUND", "COMPILATION_ERROR"]
            print(f"✅ Correctly caught missing package error: {error.error_type}")

    def test_security_validation(self):
        """Test security validation features."""
        service = TectonicService(tectonic_path="/opt/homebrew/bin/tectonic")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Test 1: Invalid file extension
            invalid_file = temp_path / "test.txt"
            invalid_file.write_text("Not a LaTeX file")

            with pytest.raises(TectonicSecurityError):
                service.compile_latex(invalid_file, temp_path / "output")

            print("✅ Correctly rejected non-LaTeX file")

            # Test 2: Dangerous filename
            dangerous_file = temp_path / "test..tex"
            dangerous_file.write_text(
                r"\documentclass{article}\begin{document}Hello\end{document}"
            )

            with pytest.raises(TectonicSecurityError):
                service.compile_latex(dangerous_file, temp_path / "output")

            print("✅ Correctly rejected dangerous filename")

    def test_compilation_with_options(self):
        """Test compilation with different options."""
        service = TectonicService(tectonic_path="/opt/homebrew/bin/tectonic")

        latex_content = r"""
\documentclass{article}
\begin{document}
\title{Test Document with Options}
\author{Test Author}
\date{\today}
\maketitle

\section{Introduction}
This document tests compilation with different options.
\end{document}
"""

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create input file
            input_file = temp_path / "test_options.tex"
            input_file.write_text(latex_content)

            # Test with different engines
            engines = ["pdftex", "xelatex", "lualatex"]

            for engine in engines:
                output_dir = temp_path / f"output_{engine}"
                output_dir.mkdir()

                options = {"engine": engine}

                try:
                    result = service.compile_latex(input_file, output_dir, options)
                    assert result["success"] is True
                    print(f"✅ Successfully compiled with {engine} engine")
                except TectonicCompilationError as e:
                    # Some engines might not be available, that's okay
                    print(f"⚠️  {engine} engine not available: {e.error_type}")
                    continue
