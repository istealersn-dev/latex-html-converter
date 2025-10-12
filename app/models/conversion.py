"""
Conversion models for the LaTeX → HTML5 Converter application.

This module defines Pydantic models for conversion pipeline data structures,
including conversion jobs, pipeline stages, and processing results.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ConversionStage(str, Enum):
    """Enumeration of conversion pipeline stages."""

    INITIALIZED = "initialized"
    TECTONIC_COMPILING = "tectonic_compiling"
    TECTONIC_COMPLETED = "tectonic_completed"
    LATEXML_CONVERTING = "latexml_converting"
    LATEXML_COMPLETED = "latexml_completed"
    POST_PROCESSING = "post_processing"
    POST_PROCESSING_COMPLETED = "post_processing_completed"
    VALIDATION = "validation"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ConversionStatus(str, Enum):
    """Enumeration of conversion job statuses."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PipelineStage(BaseModel):
    """Model representing a single pipeline stage."""

    name: str = Field(..., description="Stage name")
    status: ConversionStatus = Field(..., description="Stage status")
    started_at: datetime | None = Field(None, description="Stage start time")
    completed_at: datetime | None = Field(None, description="Stage completion time")
    duration_seconds: float | None = Field(None, description="Stage duration in seconds")
    progress_percentage: float = Field(0.0, ge=0.0, le=100.0, description="Stage progress percentage")
    error_message: str | None = Field(None, description="Error message if stage failed")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Stage-specific metadata")

    @field_validator("duration_seconds")
    @classmethod
    def validate_duration(cls, v: float | None) -> float | None:
        """Validate duration is non-negative."""
        if v is not None and v < 0:
            raise ValueError("Duration must be non-negative")
        return v


class ConversionJob(BaseModel):
    """Model representing a complete conversion job."""

    job_id: str = Field(..., description="Unique job identifier")
    input_file: Path = Field(..., description="Input LaTeX file path")
    output_dir: Path = Field(..., description="Output directory path")
    status: ConversionStatus = Field(default=ConversionStatus.PENDING, description="Job status")
    current_stage: ConversionStage = Field(default=ConversionStage.INITIALIZED, description="Current pipeline stage")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Job creation time")
    started_at: datetime | None = Field(None, description="Job start time")
    completed_at: datetime | None = Field(None, description="Job completion time")
    total_duration_seconds: float | None = Field(None, description="Total job duration in seconds")

    # Pipeline stages
    stages: list[PipelineStage] = Field(default_factory=list, description="Pipeline stages")

    # Results
    output_files: list[Path] = Field(default_factory=list, description="Generated output files")
    assets: list[Path] = Field(default_factory=list, description="Generated asset files")
    quality_score: float | None = Field(None, ge=0.0, le=100.0, description="Output quality score")

    # Error handling
    error_message: str | None = Field(None, description="Error message if job failed")
    retry_count: int = Field(default=0, ge=0, description="Number of retry attempts")
    max_retries: int = Field(default=3, ge=0, description="Maximum retry attempts")

    # Configuration
    options: dict[str, Any] = Field(default_factory=dict, description="Conversion options")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Job metadata")

    @field_validator("total_duration_seconds")
    @classmethod
    def validate_total_duration(cls, v: float | None) -> float | None:
        """Validate total duration is non-negative."""
        if v is not None and v < 0:
            raise ValueError("Total duration must be non-negative")
        return v

    @field_validator("quality_score")
    @classmethod
    def validate_quality_score(cls, v: float | None) -> float | None:
        """Validate quality score is within valid range."""
        if v is not None and not 0.0 <= v <= 100.0:
            raise ValueError("Quality score must be between 0.0 and 100.0")
        return v


class ConversionResult(BaseModel):
    """Model representing the final conversion result."""

    job_id: str = Field(..., description="Job identifier")
    status: ConversionStatus = Field(..., description="Final job status")
    success: bool = Field(..., description="Whether conversion was successful")

    # Output information
    output_files: list[Path] = Field(default_factory=list, description="Generated output files")
    assets: list[Path] = Field(default_factory=list, description="Generated asset files")
    main_html_file: Path | None = Field(None, description="Main HTML output file")

    # Quality metrics
    quality_score: float | None = Field(None, ge=0.0, le=100.0, description="Output quality score")
    quality_metrics: dict[str, Any] = Field(default_factory=dict, description="Detailed quality metrics")

    # Processing information
    total_duration_seconds: float | None = Field(None, description="Total processing time")
    stages_completed: list[str] = Field(default_factory=list, description="Completed stages")
    warnings: list[str] = Field(default_factory=list, description="Processing warnings")
    errors: list[str] = Field(default_factory=list, description="Processing errors")

    # Metadata
    created_at: datetime = Field(..., description="Job creation time")
    completed_at: datetime = Field(..., description="Job completion time")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class ConversionProgress(BaseModel):
    """Model representing conversion progress information."""

    job_id: str = Field(..., description="Job identifier")
    status: ConversionStatus = Field(..., description="Current job status")
    current_stage: ConversionStage = Field(..., description="Current pipeline stage")
    progress_percentage: float = Field(0.0, ge=0.0, le=100.0, description="Overall progress percentage")

    # Stage information
    current_stage_progress: float = Field(0.0, ge=0.0, le=100.0, description="Current stage progress")
    stages_completed: int = Field(0, ge=0, description="Number of completed stages")
    total_stages: int = Field(0, ge=0, description="Total number of stages")

    # Timing information
    elapsed_seconds: float | None = Field(None, description="Elapsed time in seconds")
    estimated_remaining_seconds: float | None = Field(None, description="Estimated remaining time")

    # Status information
    message: str | None = Field(None, description="Current status message")
    warnings: list[str] = Field(default_factory=list, description="Current warnings")

    # Metadata
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update time")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Progress metadata")


class ConversionOptions(BaseModel):
    """Model for conversion pipeline options."""

    # Tectonic options
    tectonic_options: dict[str, Any] = Field(default_factory=dict, description="Tectonic compilation options")

    # LaTeXML options
    latexml_options: dict[str, Any] = Field(default_factory=dict, description="LaTeXML conversion options")

    # Post-processing options
    post_processing_options: dict[str, Any] = Field(default_factory=dict, description="HTML post-processing options")

    # Quality options
    quality_checks: bool = Field(default=True, description="Enable quality checks")
    quality_threshold: float = Field(default=80.0, ge=0.0, le=100.0, description="Minimum quality threshold")

    # Resource options
    max_processing_time: int = Field(default=600, ge=60, description="Maximum processing time in seconds")
    max_memory_mb: int = Field(default=1024, ge=256, description="Maximum memory usage in MB")

    # Output options
    output_format: str = Field(default="html", description="Output format")
    include_assets: bool = Field(default=True, description="Include generated assets")
    compress_output: bool = Field(default=False, description="Compress output files")

    # Validation options
    validate_html: bool = Field(default=True, description="Validate HTML output")
    validate_mathml: bool = Field(default=True, description="Validate MathML output")
    validate_accessibility: bool = Field(default=True, description="Validate accessibility")

    @field_validator("quality_threshold")
    @classmethod
    def validate_quality_threshold(cls, v: float) -> float:
        """Validate quality threshold is within valid range."""
        if not 0.0 <= v <= 100.0:
            raise ValueError("Quality threshold must be between 0.0 and 100.0")
        return v

    @field_validator("max_processing_time")
    @classmethod
    def validate_max_processing_time(cls, v: int) -> int:
        """Validate maximum processing time is reasonable."""
        if v < 60:
            raise ValueError("Maximum processing time must be at least 60 seconds")
        if v > 3600:  # 1 hour
            raise ValueError("Maximum processing time cannot exceed 3600 seconds")
        return v

    @field_validator("max_memory_mb")
    @classmethod
    def validate_max_memory(cls, v: int) -> int:
        """Validate maximum memory usage is reasonable."""
        if v < 256:
            raise ValueError("Maximum memory must be at least 256 MB")
        if v > 8192:  # 8 GB
            raise ValueError("Maximum memory cannot exceed 8192 MB")
        return v
