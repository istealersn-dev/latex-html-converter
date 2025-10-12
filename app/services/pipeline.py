"""
Conversion pipeline service for the LaTeX → HTML5 Converter.

This service orchestrates the complete conversion workflow:
Tectonic → LaTeXML → HTML Post-Processing
"""

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from app.models.conversion import (
    ConversionJob,
    ConversionOptions,
    ConversionProgress,
    ConversionResult,
    ConversionStage,
    ConversionStatus,
    PipelineStage,
)
from app.services.html_post import HTMLPostProcessingError, HTMLPostProcessor
from app.services.latexml import LaTeXMLError, LaTeXMLService
from app.services.tectonic import TectonicCompilationError, TectonicService
from app.utils.fs import cleanup_directory, ensure_directory, get_file_info

logger = logging.getLogger(__name__)


class ConversionPipelineError(Exception):
    """Base exception for conversion pipeline errors."""

    def __init__(self, message: str, stage: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.stage = stage
        self.details = details or {}


class PipelineTimeoutError(ConversionPipelineError):
    """Raised when pipeline processing times out."""


class PipelineResourceError(ConversionPipelineError):
    """Raised when pipeline exceeds resource limits."""


class ConversionPipeline:
    """Main conversion pipeline orchestrator."""

    def __init__(
        self,
        tectonic_service: TectonicService | None = None,
        latexml_service: LaTeXMLService | None = None,
        html_processor: HTMLPostProcessor | None = None
    ):
        """
        Initialize the conversion pipeline.

        Args:
            tectonic_service: Tectonic service instance
            latexml_service: LaTeXML service instance
            html_processor: HTML post-processor instance
        """
        self.tectonic_service = tectonic_service or TectonicService()
        self.latexml_service = latexml_service or LaTeXMLService()
        self.html_processor = html_processor or HTMLPostProcessor()

        # Pipeline configuration
        self.max_concurrent_jobs = 5
        self.default_timeout = 600  # 10 minutes
        self.cleanup_delay = 3600  # 1 hour

        # Active jobs tracking
        self._active_jobs: dict[str, ConversionJob] = {}
        self._job_lock = None  # Will be set up with threading if needed

    def create_conversion_job(
        self,
        input_file: Path,
        output_dir: Path,
        options: ConversionOptions | None = None,
        job_id: str | None = None
    ) -> ConversionJob:
        """
        Create a new conversion job.

        Args:
            input_file: Path to input LaTeX file
            output_dir: Path to output directory
            options: Conversion options
            job_id: Optional job ID (generated if not provided)

        Returns:
            ConversionJob: Created conversion job

        Raises:
            ConversionPipelineError: If job creation fails
        """
        try:
            # Validate input file
            if not input_file.exists():
                raise ConversionPipelineError(
                    f"Input file not found: {input_file}",
                    "initialization"
                )

            if not input_file.is_file():
                raise ConversionPipelineError(
                    f"Input path is not a file: {input_file}",
                    "initialization"
                )

            # Ensure output directory exists
            ensure_directory(output_dir)

            # Create job
            job = ConversionJob(
                job_id=job_id or f"job_{int(time.time())}_{hash(str(input_file))}",
                input_file=input_file,
                output_dir=output_dir,
                options=options.model_dump() if options else {},
                status=ConversionStatus.PENDING
            )

            # Initialize pipeline stages
            self._initialize_pipeline_stages(job)

            logger.info(f"Created conversion job: {job.job_id}")
            return job

        except Exception as exc:
            logger.exception(f"Failed to create conversion job: {exc}")
            raise ConversionPipelineError(
                f"Failed to create conversion job: {exc}",
                "initialization"
            )

    def execute_pipeline(self, job: ConversionJob) -> ConversionResult:
        """
        Execute the complete conversion pipeline.

        Args:
            job: Conversion job to execute

        Returns:
            ConversionResult: Final conversion result

        Raises:
            ConversionPipelineError: If pipeline execution fails
        """
        job.status = ConversionStatus.RUNNING
        job.started_at = datetime.utcnow()

        try:
            logger.info(f"Starting pipeline execution for job: {job.job_id}")

            # Stage 1: Tectonic Compilation
            self._execute_tectonic_stage(job)

            # Stage 2: LaTeXML Conversion
            self._execute_latexml_stage(job)

            # Stage 3: HTML Post-Processing
            self._execute_post_processing_stage(job)

            # Stage 4: Validation
            self._execute_validation_stage(job)

            # Complete job
            job.status = ConversionStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.current_stage = ConversionStage.COMPLETED

            if job.started_at:
                job.total_duration_seconds = (job.completed_at - job.started_at).total_seconds()

            logger.info(f"Pipeline execution completed for job: {job.job_id}")

            return self._create_conversion_result(job)

        except Exception as exc:
            logger.exception(f"Pipeline execution failed for job {job.job_id}: {exc}")
            job.status = ConversionStatus.FAILED
            job.completed_at = datetime.utcnow()
            job.error_message = str(exc)
            raise ConversionPipelineError(
                f"Pipeline execution failed: {exc}",
                job.current_stage.value
            )

    def get_job_progress(self, job_id: str) -> ConversionProgress | None:
        """
        Get progress information for a conversion job.

        Args:
            job_id: Job identifier

        Returns:
            ConversionProgress: Progress information or None if job not found
        """
        job = self._active_jobs.get(job_id)
        if not job:
            return None

        # Calculate overall progress
        total_stages = len(job.stages)
        completed_stages = sum(1 for stage in job.stages if stage.status == ConversionStatus.COMPLETED)
        progress_percentage = (completed_stages / total_stages * 100) if total_stages > 0 else 0.0

        # Calculate elapsed time
        elapsed_seconds = None
        if job.started_at:
            elapsed_seconds = (datetime.utcnow() - job.started_at).total_seconds()

        return ConversionProgress(
            job_id=job.job_id,
            status=job.status,
            current_stage=job.current_stage,
            progress_percentage=progress_percentage,
            current_stage_progress=job.stages[-1].progress_percentage if job.stages else 0.0,
            stages_completed=completed_stages,
            total_stages=total_stages,
            elapsed_seconds=elapsed_seconds,
            message=self._get_stage_message(job),
            warnings=self._collect_warnings(job),
            updated_at=datetime.utcnow()
        )

    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a running conversion job.

        Args:
            job_id: Job identifier

        Returns:
            bool: True if job was cancelled, False if not found
        """
        job = self._active_jobs.get(job_id)
        if not job:
            return False

        if job.status in [ConversionStatus.COMPLETED, ConversionStatus.FAILED, ConversionStatus.CANCELLED]:
            return False

        job.status = ConversionStatus.CANCELLED
        job.completed_at = datetime.utcnow()
        job.current_stage = ConversionStage.CANCELLED

        logger.info(f"Cancelled job: {job_id}")
        return True

    def cleanup_job(self, job_id: str) -> bool:
        """
        Clean up resources for a completed job.

        Args:
            job_id: Job identifier

        Returns:
            bool: True if cleanup was successful, False if job not found
        """
        job = self._active_jobs.get(job_id)
        if not job:
            return False

        try:
            # Clean up temporary files
            if job.output_dir.exists():
                cleanup_directory(job.output_dir)

            # Remove from active jobs
            self._active_jobs.pop(job_id, None)

            logger.info(f"Cleaned up job: {job_id}")
            return True

        except Exception as exc:
            logger.exception(f"Failed to cleanup job {job_id}: {exc}")
            return False

    def _initialize_pipeline_stages(self, job: ConversionJob) -> None:
        """Initialize pipeline stages for a job."""
        stages = [
            PipelineStage(
                name="Tectonic Compilation",
                status=ConversionStatus.PENDING,
                metadata={"service": "tectonic"}
            ),
            PipelineStage(
                name="LaTeXML Conversion",
                status=ConversionStatus.PENDING,
                metadata={"service": "latexml"}
            ),
            PipelineStage(
                name="HTML Post-Processing",
                status=ConversionStatus.PENDING,
                metadata={"service": "html_post"}
            ),
            PipelineStage(
                name="Output Validation",
                status=ConversionStatus.PENDING,
                metadata={"service": "validation"}
            )
        ]

        job.stages = stages

    def _execute_tectonic_stage(self, job: ConversionJob) -> None:
        """Execute Tectonic compilation stage."""
        stage = job.stages[0]
        stage.status = ConversionStatus.RUNNING
        stage.started_at = datetime.utcnow()
        job.current_stage = ConversionStage.TECTONIC_COMPILING

        try:
            logger.info(f"Starting Tectonic compilation for job: {job.job_id}")

            # Compile LaTeX with Tectonic
            result = self.tectonic_service.compile_latex(
                input_file=job.input_file,
                output_dir=job.output_dir / "tectonic",
                options=job.options.get("tectonic_options", {})
            )

            # Update stage
            stage.status = ConversionStatus.COMPLETED
            stage.completed_at = datetime.utcnow()
            stage.duration_seconds = (stage.completed_at - stage.started_at).total_seconds()
            stage.progress_percentage = 100.0
            stage.metadata.update(result)

            job.current_stage = ConversionStage.TECTONIC_COMPLETED

            logger.info(f"Tectonic compilation completed for job: {job.job_id}")

        except TectonicCompilationError as exc:
            stage.status = ConversionStatus.FAILED
            stage.error_message = str(exc)
            stage.completed_at = datetime.utcnow()
            raise ConversionPipelineError(
                f"Tectonic compilation failed: {exc}",
                "tectonic_compilation"
            )

    def _execute_latexml_stage(self, job: ConversionJob) -> None:
        """Execute LaTeXML conversion stage."""
        stage = job.stages[1]
        stage.status = ConversionStatus.RUNNING
        stage.started_at = datetime.utcnow()
        job.current_stage = ConversionStage.LATEXML_CONVERTING

        try:
            logger.info(f"Starting LaTeXML conversion for job: {job.job_id}")

            # Find the main TeX file (assuming it's the input file)
            tex_file = job.input_file

            # Convert with LaTeXML
            result = self.latexml_service.convert_tex_to_html(
                input_file=tex_file,
                output_dir=job.output_dir / "latexml",
                options=job.options.get("latexml_options", {})
            )

            # Update stage
            stage.status = ConversionStatus.COMPLETED
            stage.completed_at = datetime.utcnow()
            stage.duration_seconds = (stage.completed_at - stage.started_at).total_seconds()
            stage.progress_percentage = 100.0
            stage.metadata.update(result)

            job.current_stage = ConversionStage.LATEXML_COMPLETED

            logger.info(f"LaTeXML conversion completed for job: {job.job_id}")

        except LaTeXMLError as exc:
            stage.status = ConversionStatus.FAILED
            stage.error_message = str(exc)
            stage.completed_at = datetime.utcnow()
            raise ConversionPipelineError(
                f"LaTeXML conversion failed: {exc}",
                "latexml_conversion"
            )

    def _execute_post_processing_stage(self, job: ConversionJob) -> None:
        """Execute HTML post-processing stage."""
        stage = job.stages[2]
        stage.status = ConversionStatus.RUNNING
        stage.started_at = datetime.utcnow()
        job.current_stage = ConversionStage.POST_PROCESSING

        try:
            logger.info(f"Starting HTML post-processing for job: {job.job_id}")

            # Find the HTML file from LaTeXML output
            latexml_output = job.output_dir / "latexml"
            html_files = list(latexml_output.glob("*.html"))

            if not html_files:
                raise ConversionPipelineError(
                    "No HTML files found in LaTeXML output",
                    "post_processing"
                )

            html_file = html_files[0]  # Use the first HTML file

            # Process HTML
            result = self.html_processor.process_html(
                html_file=html_file,
                output_file=job.output_dir / "final.html",
                options=job.options.get("post_processing_options", {})
            )

            # Update stage
            stage.status = ConversionStatus.COMPLETED
            stage.completed_at = datetime.utcnow()
            stage.duration_seconds = (stage.completed_at - stage.started_at).total_seconds()
            stage.progress_percentage = 100.0
            stage.metadata.update(result)

            job.current_stage = ConversionStage.POST_PROCESSING_COMPLETED

            logger.info(f"HTML post-processing completed for job: {job.job_id}")

        except HTMLPostProcessingError as exc:
            stage.status = ConversionStatus.FAILED
            stage.error_message = str(exc)
            stage.completed_at = datetime.utcnow()
            raise ConversionPipelineError(
                f"HTML post-processing failed: {exc}",
                "post_processing"
            )

    def _execute_validation_stage(self, job: ConversionJob) -> None:
        """Execute output validation stage."""
        stage = job.stages[3]
        stage.status = ConversionStatus.RUNNING
        stage.started_at = datetime.utcnow()
        job.current_stage = ConversionStage.VALIDATION

        try:
            logger.info(f"Starting output validation for job: {job.job_id}")

            # Validate output files
            output_file = job.output_dir / "final.html"
            if not output_file.exists():
                raise ConversionPipelineError(
                    "Final HTML output file not found",
                    "validation"
                )

            # Basic validation checks
            file_info = get_file_info(output_file)
            if file_info["size"] == 0:
                raise ConversionPipelineError(
                    "Final HTML output file is empty",
                    "validation"
                )

            # Update job with output files
            job.output_files = [output_file]
            job.assets = list(job.output_dir.glob("*.svg")) + list(job.output_dir.glob("*.png"))

            # Calculate quality score (simplified)
            job.quality_score = self._calculate_quality_score(job)

            # Update stage
            stage.status = ConversionStatus.COMPLETED
            stage.completed_at = datetime.utcnow()
            stage.duration_seconds = (stage.completed_at - stage.started_at).total_seconds()
            stage.progress_percentage = 100.0

            job.current_stage = ConversionStage.COMPLETED

            logger.info(f"Output validation completed for job: {job.job_id}")

        except Exception as exc:
            stage.status = ConversionStatus.FAILED
            stage.error_message = str(exc)
            stage.completed_at = datetime.utcnow()
            raise ConversionPipelineError(
                f"Output validation failed: {exc}",
                "validation"
            )

    def _calculate_quality_score(self, job: ConversionJob) -> float:
        """Calculate quality score for the conversion."""
        # Simplified quality scoring
        score = 85.0  # Base score

        # Adjust based on file sizes and content
        if job.output_files:
            output_file = job.output_files[0]
            file_info = get_file_info(output_file)

            # Adjust score based on file size (larger files might indicate better conversion)
            if file_info["size"] > 10000:  # 10KB
                score += 5.0
            elif file_info["size"] < 1000:  # 1KB
                score -= 10.0

        # Adjust based on number of assets
        if len(job.assets) > 0:
            score += min(len(job.assets) * 2, 10.0)

        return min(max(score, 0.0), 100.0)

    def _create_conversion_result(self, job: ConversionJob) -> ConversionResult:
        """Create conversion result from job."""
        return ConversionResult(
            job_id=job.job_id,
            status=job.status,
            success=job.status == ConversionStatus.COMPLETED,
            output_files=job.output_files,
            assets=job.assets,
            main_html_file=job.output_files[0] if job.output_files else None,
            quality_score=job.quality_score,
            quality_metrics={"overall_score": job.quality_score},
            total_duration_seconds=job.total_duration_seconds,
            stages_completed=[stage.name for stage in job.stages if stage.status == ConversionStatus.COMPLETED],
            warnings=self._collect_warnings(job),
            errors=[stage.error_message for stage in job.stages if stage.error_message],
            created_at=job.created_at,
            completed_at=job.completed_at or datetime.utcnow(),
            metadata=job.metadata
        )

    def _get_stage_message(self, job: ConversionJob) -> str:
        """Get current stage message."""
        if job.status == ConversionStatus.COMPLETED:
            return "Conversion completed successfully"
        elif job.status == ConversionStatus.FAILED:
            return f"Conversion failed at {job.current_stage.value}"
        elif job.status == ConversionStatus.RUNNING:
            return f"Processing {job.current_stage.value.replace('_', ' ')}"
        else:
            return f"Status: {job.status.value}"

    def _collect_warnings(self, job: ConversionJob) -> list[str]:
        """Collect warnings from all stages."""
        warnings = []
        for stage in job.stages:
            if stage.metadata.get("warnings"):
                warnings.extend(stage.metadata["warnings"])
        return warnings
