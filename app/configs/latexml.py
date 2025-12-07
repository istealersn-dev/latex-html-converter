"""
LaTeXML configuration and settings.

This module provides configuration management for LaTeXML integration,
including default settings, validation, and environment-specific configurations.
"""

from pathlib import Path

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings


class LaTeXMLSettings(BaseSettings):
    """LaTeXML configuration settings."""

    # LaTeXML executable path
    latexml_path: str = Field(default="/usr/bin/latexmlc", description="Path to LaTeXML executable (Docker default, override with env var)")

    # Output format settings
    output_format: str = Field(default="html", description="Output format (html, xml)")
    include_mathml: bool = Field(default=True, description="Include MathML in output")
    include_css: bool = Field(default=True, description="Include CSS styling")
    include_javascript: bool = Field(default=True, description="Include JavaScript")

    # Processing options
    strict_mode: bool = Field(default=False, description="Enable strict error handling")
    verbose_output: bool = Field(default=False, description="Enable verbose output")
    include_comments: bool = Field(default=False, description="Include comments in output")
    parallel_processing: bool = Field(default=True, description="Enable parallel processing")
    cache_bindings: bool = Field(default=True, description="Cache LaTeXML bindings for faster processing")

    # Path settings
    temp_dir: Path | None = Field(default=None, description="Temporary directory for processing")
    output_dir: Path | None = Field(default=None, description="Output directory for results")

    # Timeout settings
    conversion_timeout: int = Field(default=300, description="Conversion timeout in seconds")

    # Security settings
    allowed_extensions: list[str] = Field(
        default=[".tex", ".latex", ".ltx"],
        description="Allowed input file extensions"
    )
    max_file_size: int = Field(
        default=50 * 1024 * 1024,  # 50MB
        description="Maximum input file size in bytes"
    )

    # LaTeXML-specific options
    preload_modules: list[str] = Field(
        default=["amsmath", "amssymb", "graphicx", "overpic"],
        description="LaTeXML modules to preload"
    )
    preamble_file: Path | None = Field(
        default=None,
        description="Optional preamble file to prepend"
    )
    postamble_file: Path | None = Field(
        default=None,
        description="Optional postamble file to append"
    )
    
    # Package management
    auto_install_packages: bool = Field(default=True, description="Automatically install missing packages")
    package_install_timeout: int = Field(default=300, description="Package installation timeout in seconds")
    
    # Fallback behavior
    enable_tectonic_fallback: bool = Field(default=True, description="Enable fallback to LaTeXML-only when Tectonic fails")
    continue_on_tectonic_failure: bool = Field(default=True, description="Continue conversion when Tectonic fails")
    
    # Custom paths
    custom_class_paths: list[str] = Field(default_factory=list, description="Custom paths for document classes")

    class Config:
        env_prefix = "LATEXML_"
        case_sensitive = False

    @field_validator("output_format")
    @classmethod
    def validate_output_format(cls, v: str) -> str:
        """Validate output format."""
        allowed_formats = ["html", "xml", "tex", "box"]
        if v.lower() not in allowed_formats:
            raise ValueError(f"Output format must be one of: {allowed_formats}")
        return v.lower()

    @field_validator("conversion_timeout")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        """Validate conversion timeout."""
        if v <= 0:
            raise ValueError("Conversion timeout must be positive")
        if v > 3600:  # 1 hour max
            raise ValueError("Conversion timeout cannot exceed 1 hour")
        return v

    @field_validator("max_file_size")
    @classmethod
    def validate_max_file_size(cls, v: int) -> int:
        """Validate maximum file size."""
        if v <= 0:
            raise ValueError("Maximum file size must be positive")
        if v > 500 * 1024 * 1024:  # 500MB max
            raise ValueError("Maximum file size cannot exceed 500MB")
        return v

    @field_validator("allowed_extensions")
    @classmethod
    def validate_extensions(cls, v: list[str]) -> list[str]:
        """Validate allowed extensions."""
        if not v:
            raise ValueError("At least one extension must be allowed")
        # Ensure extensions start with dot
        return [ext if ext.startswith('.') else f'.{ext}' for ext in v]

    def get_latexml_command(self, input_file: Path, output_file: Path) -> list[str]:
        """
        Generate LaTeXML command with current settings.
        
        Args:
            input_file: Path to input TeX file
            output_file: Path to output file
            
        Returns:
            List of command arguments
        """
        # Use latexml for XML output, latexmlc for HTML output
        if self.output_format == "xml":
            # Convert latexmlc path to latexml path
            latexml_path = str(self.latexml_path).replace("latexmlc", "latexml")
            cmd = [latexml_path]
        else:
            cmd = [str(self.latexml_path)]

        # Output settings
        cmd.extend(["--destination", str(output_file)])

        if self.output_format == "xml":
            cmd.append("--xml")
        elif self.output_format == "tex":
            cmd.append("--tex")
        elif self.output_format == "box":
            cmd.append("--box")

        # Processing options
        if self.strict_mode:
            cmd.append("--strict")

        if self.verbose_output:
            cmd.append("--verbose")

        if not self.include_comments:
            cmd.append("--nocomments")

        # Performance optimizations
        if self.parallel_processing:
            cmd.append("--parallel")

        # Disable unnecessary features for faster processing
        cmd.append("--nodefaultresources")  # Don't load default CSS/JS, we'll add our own
        cmd.append("--timestamp=0")  # Disable timestamp generation

        # Preload modules
        for module in self.preload_modules:
            cmd.extend(["--preload", module])

        # Preamble and postamble
        if self.preamble_file is not None:
            preamble_path = Path(self.preamble_file)
            if preamble_path.exists():
                cmd.extend(["--preamble", str(preamble_path)])

        if self.postamble_file is not None:
            postamble_path = Path(self.postamble_file)
            if postamble_path.exists():
                cmd.extend(["--postamble", str(postamble_path)])

        # Custom class paths
        for class_path in self.custom_class_paths:
            cmd.extend(["--path", class_path])

        # Input file (must be last)
        cmd.append(str(input_file))

        return cmd

    def get_environment_vars(self) -> dict[str, str]:
        """
        Get environment variables for LaTeXML execution.
        
        Returns:
            Dictionary of environment variables
        """
        env = {
            "LATEXML_STRICT": str(self.strict_mode).lower(),
            "LATEXML_VERBOSE": str(self.verbose_output).lower(),
        }

        if self.temp_dir:
            env["TMPDIR"] = str(self.temp_dir)

        return env


class LaTeXMLConversionOptions(BaseModel):
    """Options for LaTeXML conversion."""

    output_format: str = Field(default="html", description="Output format")
    include_mathml: bool = Field(default=True, description="Include MathML")
    include_css: bool = Field(default=True, description="Include CSS")
    include_javascript: bool = Field(default=True, description="Include JavaScript")
    strict_mode: bool = Field(default=False, description="Strict error handling")
    verbose: bool = Field(default=False, description="Verbose output")
    preload_modules: list[str] = Field(
        default_factory=lambda: ["amsmath", "amssymb", "graphicx", "overpic"],
        description="Modules to preload"
    )
    custom_preamble: str | None = Field(
        default=None,
        description="Custom preamble content"
    )
    custom_postamble: str | None = Field(
        default=None,
        description="Custom postamble content"
    )

    @field_validator("output_format")
    @classmethod
    def validate_output_format(cls, v: str) -> str:
        """Validate output format."""
        allowed = ["html", "xml", "tex", "box"]
        if v.lower() not in allowed:
            raise ValueError(f"Output format must be one of: {allowed}")
        return v.lower()

    def to_latexml_settings(self) -> LaTeXMLSettings:
        """Convert to LaTeXMLSettings."""
        return LaTeXMLSettings(
            output_format=self.output_format,
            include_mathml=self.include_mathml,
            include_css=self.include_css,
            include_javascript=self.include_javascript,
            strict_mode=self.strict_mode,
            verbose_output=self.verbose,
            preload_modules=self.preload_modules,
        )


# Default settings instance
default_settings = LaTeXMLSettings()
