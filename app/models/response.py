"""
Response models for the LaTeX → HTML5 Converter API.

This module defines Pydantic models for API response formatting.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class ConversionStatus(str, Enum):
    """Enumeration of conversion status values."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ConversionResponse(BaseModel):
    """
    Response model for LaTeX to HTML5 conversion.

    This model defines the structure of conversion responses
    including the result files and metadata.
    """

    # Conversion identification
    conversion_id: str = Field(..., description="Unique conversion identifier")
    status: ConversionStatus = Field(..., description="Current conversion status")

    # Output files
    html_file: str = Field(..., description="Main HTML output file")
    assets: list[str] = Field(default=[], description="List of generated asset files")

    # Conversion metadata
    report: dict[str, Any] = Field(..., description="Conversion report and metrics")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = Field(default=None)

    # Error information
    error_message: str | None = Field(
        default=None, description="Error message if conversion failed"
    )

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class ConversionStatusResponse(BaseModel):
    """
    Response model for conversion status checks.

    This model provides status information for ongoing
    or completed conversions.
    """

    conversion_id: str = Field(..., description="Unique conversion identifier")
    job_id: str = Field(..., description="Job identifier (same as conversion_id)")
    status: ConversionStatus = Field(..., description="Current conversion status")
    progress: int = Field(..., description="Progress percentage (0-100)")
    message: str = Field(..., description="Status message")

    # Timing information
    created_at: datetime = Field(..., description="Conversion start time")
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    estimated_completion: datetime | None = Field(default=None)

    # Error information
    error_message: str | None = Field(default=None)
    diagnostics: dict[str, Any] | None = Field(
        default=None, description="Detailed diagnostics for failed conversions"
    )

    @model_validator(mode="after")
    def set_job_id(self) -> "ConversionStatusResponse":
        """Set job_id to match conversion_id if not explicitly set."""
        if not hasattr(self, "job_id") or self.job_id != self.conversion_id:
            self.job_id = self.conversion_id
        return self

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class HealthResponse(BaseModel):
    """
    Response model for health check endpoints.

    This model provides system health and status information.
    """

    status: str = Field(..., description="Service status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    environment: str = Field(..., description="Environment name")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Optional system information
    system: dict[str, Any] | None = Field(default=None)
    metrics: dict[str, Any] | None = Field(default=None)
    dependencies: dict[str, bool] | None = Field(default=None)


class ErrorResponse(BaseModel):
    """
    Response model for error responses.

    This model provides consistent error response formatting.
    """

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    request_id: str | None = Field(default=None, description="Request identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Optional error details
    details: dict[str, Any] | None = Field(default=None)
    code: str | None = Field(default=None, description="Error code")


class ConversionReport(BaseModel):
    """
    Detailed conversion report model.

    This model provides comprehensive information about
    the conversion process and results.
    """

    # Fidelity metrics
    score: float = Field(..., description="Overall fidelity score (0-100)")
    structure_score: float = Field(..., description="Structure fidelity score")
    math_score: float = Field(..., description="Math rendering score")
    asset_score: float = Field(..., description="Asset conversion score")
    completeness_score: float = Field(..., description="Completeness score")

    # Conversion details
    packages_used: list[str] = Field(default=[], description="LaTeX packages detected")
    missing_macros: list[str] = Field(default=[], description="Unsupported macros")
    warnings: list[str] = Field(default=[], description="Conversion warnings")

    # Performance metrics
    conversion_time: float = Field(..., description="Total conversion time in seconds")
    file_size: int = Field(..., description="Output file size in bytes")
    asset_count: int = Field(..., description="Number of generated assets")

    # Quality indicators
    math_errors: int = Field(default=0, description="Number of math rendering errors")
    broken_links: int = Field(default=0, description="Number of broken internal links")
    missing_figures: int = Field(default=0, description="Number of missing figures")

    # Timestamps
    started_at: datetime = Field(..., description="Conversion start time")
    completed_at: datetime = Field(..., description="Conversion completion time")

    class Config:
        """Pydantic configuration."""

        json_encoders = {datetime: lambda v: v.isoformat()}


class ConversionWarning(BaseModel):
    """Model for a single conversion warning."""

    type: str = Field(..., description="Warning type (error, warning, info)")
    severity: str = Field(..., description="Severity level (high, medium, low)")
    message: str = Field(..., description="Warning message")
    source: str = Field(..., description="Source of the warning")
    location: str | None = Field(default=None, description="Location in document")
    suggestion: str | None = Field(default=None, description="Suggested fix")


class ContentMetrics(BaseModel):
    """Model for content metrics (LaTeX or HTML)."""

    sections: int = Field(default=0, description="Number of sections")
    figures: int = Field(default=0, description="Number of figures")
    tables: int = Field(default=0, description="Number of tables")
    equations: int = Field(default=0, description="Number of equations")
    citations: int = Field(default=0, description="Number of citations")
    word_count: int = Field(default=0, description="Word count")


class ContentVerificationMetrics(BaseModel):
    """Model for content verification metrics."""

    preservation_score: float = Field(
        ..., ge=0.0, le=100.0, description="Overall preservation score (0-100)"
    )
    quality_assessment: str = Field(
        ..., description="Quality assessment (excellent, good, fair, poor)"
    )

    # Preservation percentages
    sections_preserved: float = Field(
        ..., ge=0.0, le=100.0, description="Sections preserved (%)"
    )
    figures_preserved: float = Field(
        ..., ge=0.0, le=100.0, description="Figures preserved (%)"
    )
    tables_preserved: float = Field(
        ..., ge=0.0, le=100.0, description="Tables preserved (%)"
    )
    equations_preserved: float = Field(
        ..., ge=0.0, le=100.0, description="Equations preserved (%)"
    )
    citations_preserved: float = Field(
        ..., ge=0.0, le=100.0, description="Citations preserved (%)"
    )
    words_preserved: float = Field(
        ..., ge=0.0, le=100.0, description="Words preserved (%)"
    )

    # Content counts
    latex_metrics: ContentMetrics = Field(..., description="LaTeX content metrics")
    html_metrics: ContentMetrics = Field(..., description="HTML content metrics")

    # Missing content
    missing_content: list[str] = Field(
        default=[], description="List of missing content items"
    )


class SectionDiffSummary(BaseModel):
    """Model for section diff summary."""

    section_title: str = Field(..., description="Section title")
    preservation_score: float = Field(
        ..., ge=0.0, le=100.0, description="Section preservation score"
    )
    latex_word_count: int = Field(..., description="LaTeX word count")
    html_word_count: int = Field(..., description="HTML word count")
    status: str = Field(
        ..., description="Status (preserved, partial, missing, added)"
    )


class DiffReportSummary(BaseModel):
    """Model for content diff report summary."""

    overall_preservation: float = Field(
        ..., ge=0.0, le=100.0, description="Overall preservation score"
    )
    total_sections: int = Field(..., description="Total number of sections")
    sections_preserved: int = Field(..., description="Number of preserved sections")
    sections_partial: int = Field(
        ..., description="Number of partially preserved sections"
    )
    sections_missing: int = Field(..., description="Number of missing sections")
    sections_added: int = Field(..., description="Number of added sections in HTML")

    # Top-level section summaries
    section_summaries: list[SectionDiffSummary] = Field(
        default=[], description="Summary of each section"
    )

    # Report file path
    report_file: str | None = Field(
        default=None, description="Path to detailed HTML diff report"
    )


class ConversionSummaryResponse(BaseModel):
    """
    UI-friendly conversion summary response.

    This model provides a comprehensive summary of conversion results
    optimized for display in user interfaces.
    """

    # Basic information
    conversion_id: str = Field(..., description="Unique conversion identifier")
    status: ConversionStatus = Field(..., description="Conversion status")
    created_at: datetime = Field(..., description="Creation time")
    completed_at: datetime | None = Field(default=None, description="Completion time")
    conversion_time: float | None = Field(
        default=None, description="Total conversion time in seconds"
    )

    # Quality metrics
    quality_score: float | None = Field(
        default=None, ge=0.0, le=100.0, description="Overall quality score"
    )
    quality_assessment: str | None = Field(
        default=None, description="Quality assessment text"
    )

    # Warnings and errors
    total_warnings: int = Field(default=0, description="Total number of warnings")
    warnings_by_severity: dict[str, int] = Field(
        default_factory=dict, description="Warning counts by severity"
    )
    warnings: list[ConversionWarning] = Field(
        default=[], description="List of all warnings"
    )
    error_message: str | None = Field(default=None, description="Error message if failed")

    # Content verification (if available)
    content_verification: ContentVerificationMetrics | None = Field(
        default=None, description="Content verification metrics"
    )

    # Diff report (if available)
    diff_report: DiffReportSummary | None = Field(
        default=None, description="Content diff report summary"
    )

    # Output files
    html_file: str | None = Field(default=None, description="Main HTML output file")
    asset_count: int = Field(default=0, description="Number of generated assets")

    # Additional metadata
    packages_used: list[str] = Field(
        default=[], description="LaTeX packages detected"
    )
    stages_completed: list[str] = Field(
        default=[], description="Completed pipeline stages"
    )

    class Config:
        """Pydantic configuration."""

        use_enum_values = True
        json_encoders = {datetime: lambda v: v.isoformat()}
