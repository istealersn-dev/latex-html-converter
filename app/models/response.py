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
    error_message: str | None = Field(default=None, description="Error message if conversion failed")

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
    
    @model_validator(mode='after')
    def set_job_id(self) -> 'ConversionStatusResponse':
        """Set job_id to match conversion_id if not explicitly set."""
        if not hasattr(self, 'job_id') or self.job_id != self.conversion_id:
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
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
