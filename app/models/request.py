"""
Request models for the LaTeX → HTML5 Converter API.

This module defines Pydantic models for API request validation.
"""
# pylint: disable=no-self-argument

from pydantic import BaseModel, Field, validator


class ConversionRequest(BaseModel):
    """
    Request model for LaTeX to HTML5 conversion.

    This model defines the structure and validation rules
    for conversion requests.
    """

    # File information
    filename: str = Field(..., description="Name of the uploaded file")
    file_size: int = Field(..., description="Size of the file in bytes")
    file_type: str = Field(..., description="MIME type of the file")

    # Conversion options
    math_rendering: str = Field(
        default="mathjax", description="Math rendering method (mathjax, mathml, svg)"
    )
    figure_conversion: str = Field(
        default="svg", description="Figure conversion format (svg, png, pdf)"
    )
    output_format: str = Field(
        default="html5", description="Output format (html5, xhtml)"
    )

    # Advanced options
    include_source: bool = Field(
        default=False, description="Include LaTeX source in output"
    )
    preserve_structure: bool = Field(
        default=True, description="Preserve document structure"
    )
    custom_css: str | None = Field(default=None, description="Custom CSS for styling")

    # Processing options
    timeout: int | None = Field(
        default=None, description="Conversion timeout in seconds"
    )
    max_retries: int = Field(default=3, description="Maximum number of retry attempts")

    @validator("math_rendering")
    def validate_math_rendering(self, v: str) -> str:
        """Validate math rendering option."""
        allowed = ["mathjax", "mathml", "svg"]
        if v not in allowed:
            raise ValueError(f"math_rendering must be one of {allowed}")
        return v

    @validator("figure_conversion")
    def validate_figure_conversion(self, v: str) -> str:
        """Validate figure conversion option."""
        allowed = ["svg", "png", "pdf"]
        if v not in allowed:
            raise ValueError(f"figure_conversion must be one of {allowed}")
        return v

    @validator("output_format")
    def validate_output_format(self, v: str) -> str:
        """Validate output format option."""
        allowed = ["html5", "xhtml"]
        if v not in allowed:
            raise ValueError(f"output_format must be one of {allowed}")
        return v

    @validator("file_size")
    def validate_file_size(self, v: int) -> int:
        """Validate file size."""
        if v <= 0:
            raise ValueError("file_size must be positive")
        if v > 500 * 1024 * 1024:  # 500MB
            raise ValueError("file_size cannot exceed 500MB")
        return v

    @validator("timeout")
    def validate_timeout(self, v: int | None) -> int | None:
        """Validate timeout value."""
        if v is not None and v <= 0:
            raise ValueError("timeout must be positive")
        return v

    @validator("max_retries")
    def validate_max_retries(self, v: int) -> int:
        """Validate max retries value."""
        if v < 0 or v > 10:
            raise ValueError("max_retries must be between 0 and 10")
        return v


class ConversionOptions(BaseModel):
    """
    Conversion options model.

    This model defines optional parameters for conversion
    that can be passed as JSON in the request.
    """

    # Math options
    math_rendering: str = "mathjax"
    math_font: str = "TeX"
    math_display: str = "block"

    # Figure options
    figure_conversion: str = "svg"
    figure_quality: int = 90
    figure_dpi: int = 300

    # Output options
    output_format: str = "html5"
    include_toc: bool = True
    include_bibliography: bool = True
    include_metadata: bool = True

    # Styling options
    custom_css: str | None = None
    theme: str = "default"
    responsive: bool = True

    # Processing options
    timeout: int | None = None
    max_retries: int = 3
    parallel_processing: bool = True

    @validator("figure_quality")
    def validate_figure_quality(self, v: int) -> int:
        """Validate figure quality."""
        if v < 1 or v > 100:
            raise ValueError("figure_quality must be between 1 and 100")
        return v

    @validator("figure_dpi")
    def validate_figure_dpi(self, v: int) -> int:
        """Validate figure DPI."""
        if v < 72 or v > 600:
            raise ValueError("figure_dpi must be between 72 and 600")
        return v
