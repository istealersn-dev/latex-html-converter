"""
Conversion pipeline service for the LaTeX → HTML5 Converter.

This service orchestrates the complete conversion workflow:
Tectonic → LaTeXML → HTML Post-Processing
"""

import shutil
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from app.config import settings
from app.configs.latexml import LaTeXMLConversionOptions, LaTeXMLSettings
from app.models.conversion import (
    ConversionJob,
    ConversionOptions,
    ConversionProgress,
    ConversionResult,
    ConversionStage,
    ConversionStatus,
    PipelineStage,
)
from app.services.assets import AssetConversionService
from app.services.file_discovery import (
    FileDiscoveryService,
    LatexDependencies,
    ProjectStructure,
)
from app.services.html_post import HTMLPostProcessingError, HTMLPostProcessor
from app.services.latex_preprocessor import LaTeXPreprocessor
from app.services.latexml import LaTeXMLError, LaTeXMLService
from app.services.package_manager import PackageManagerService
from app.services.pdflatex import PDFLaTeXCompilationError, PDFLaTeXService
from app.services.tectonic import TectonicService
from app.utils.fs import cleanup_directory, ensure_directory, get_file_info


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
        tectonic_service: PDFLaTeXService | TectonicService | None = None,
        latexml_service: LaTeXMLService | None = None,
        html_processor: HTMLPostProcessor | None = None,
        file_discovery: FileDiscoveryService | None = None,
        package_manager: PackageManagerService | None = None,
    ):
        """
        Initialize the conversion pipeline.

        Args:
            tectonic_service: Tectonic service instance (can be PDFLaTeX or Tectonic)
            latexml_service: LaTeXML service instance
            html_processor: HTML post-processor instance
            file_discovery: File discovery service instance
            package_manager: Package manager service instance
        """
        if tectonic_service:
            self.tectonic_service = tectonic_service
        elif settings.COMPILATION_ENGINE == "tectonic":
            self.tectonic_service = TectonicService(
                tectonic_path=settings.TECTONIC_PATH
            )
            logger.info("Using Tectonic compilation engine")
        else:
            self.tectonic_service = PDFLaTeXService(
                pdflatex_path=settings.PDFLATEX_PATH
            )
            logger.info("Using PDFLaTeX compilation engine")

        # Use LaTeXMLSettings() to pick up environment variables
        self.latexml_service = latexml_service or LaTeXMLService(
            settings=LaTeXMLSettings()
        )

        # Initialize asset conversion service for PDF -> PNG conversion
        asset_service = AssetConversionService()
        self.html_processor = html_processor or HTMLPostProcessor(
            asset_conversion_service=asset_service
        )

        self.file_discovery = file_discovery or FileDiscoveryService()
        self.package_manager = package_manager or PackageManagerService()
        self.latex_preprocessor = LaTeXPreprocessor()

        # Pipeline configuration
        self.max_concurrent_jobs = 5
        self.default_timeout = 600  # 10 minutes
        self.max_timeout = 14400  # 4 hours maximum (for very large files up to 100MB)
        self.cleanup_delay = 3600  # 1 hour

        # Active jobs tracking
        self._active_jobs: dict[str, ConversionJob] = {}
        self._job_lock = threading.RLock()  # Thread-safe access to active jobs
        
        # File metadata cache for timeout calculation optimization
        # Cache: {file_path: (size, file_count, timestamp)}
        self._file_metadata_cache: dict[str, tuple[int, int, float]] = {}
        self._cache_ttl = 300  # 5 minutes cache TTL

    def _calculate_adaptive_timeout(self, input_file: Path) -> int:
        """
        Calculate adaptive timeout based on file size and complexity.
        
        Args:
            input_file: Path to input file or directory
            
        Returns:
            Timeout in seconds
        """
        base_timeout = self.default_timeout
        
        try:
            import os
            from time import time
            
            # Check cache first (optimization)
            cache_key = str(input_file.resolve())
            current_time = time()
            
            if cache_key in self._file_metadata_cache:
                cached_size, cached_count, cache_time = self._file_metadata_cache[cache_key]
                # Use cached value if still valid
                if current_time - cache_time < self._cache_ttl:
                    total_size = cached_size
                    file_count = cached_count
                    logger.debug(
                        f"Using cached file metadata for {input_file.name} "
                        f"(size: {total_size / (1024*1024):.1f}MB, files: {file_count})"
                    )
                else:
                    # Cache expired, recalculate
                    total_size = 0
                    file_count = 0
            else:
                total_size = 0
                file_count = 0
            
            # Calculate if not cached or cache expired
            if total_size == 0 and file_count == 0:
                if input_file.is_file():
                    total_size = input_file.stat().st_size
                    file_count = 1
                elif input_file.is_dir():
                    # Use os.walk for better performance on large directories
                    for root, dirs, files in os.walk(input_file):
                        for file_name in files:
                            file_path = Path(root) / file_name
                            try:
                                total_size += file_path.stat().st_size
                                file_count += 1
                            except OSError:
                                continue
                
                # Cache the result
                self._file_metadata_cache[cache_key] = (total_size, file_count, current_time)
            
            # Adaptive timeout calculation for files up to 100MB:
            # Base: 10 minutes (600s)
            # + 30 seconds per MB for files up to 20MB
            # + 60 seconds per MB for files 20-50MB  
            # + 90 seconds per MB for files 50-100MB
            # + 1 second per file (complexity factor)
            # This ensures 100MB files get ~2.1 hours (7600s), with max of 4 hours
            
            size_mb = total_size / (1024 * 1024)
            
            if size_mb <= 20:
                size_factor = size_mb * 30  # 30 seconds per MB
            elif size_mb <= 50:
                size_factor = 600 + (size_mb - 20) * 60  # 60 seconds per MB above 20MB
            elif size_mb <= 100:
                size_factor = 2400 + (size_mb - 50) * 90  # 90 seconds per MB above 50MB
            else:
                # For files > 100MB, use maximum timeout (4 hours)
                size_factor = 6900  # ~2 hours base for 100MB+ files
            
            file_factor = file_count * 1.0  # 1 second per file
            
            calculated_timeout = int(base_timeout + size_factor + file_factor)
            
            # Cap at maximum timeout (4 hours for very large/complex files up to 100MB)
            timeout = min(calculated_timeout, self.max_timeout)
            
            logger.debug(
                f"Calculated adaptive timeout: {timeout}s "
                f"(size: {size_mb:.1f}MB, files: {file_count})"
            )
            
            return timeout
            
        except Exception as exc:
            logger.warning(f"Failed to calculate adaptive timeout: {exc}, using default")
            return base_timeout

    def create_conversion_job(
        self,
        input_file: Path,
        output_dir: Path,
        options: ConversionOptions | None = None,
        job_id: str | None = None,
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
                    f"Input file not found: {input_file}", "initialization"
                )

            if not input_file.is_file():
                raise ConversionPipelineError(
                    f"Input path is not a file: {input_file}", "initialization"
                )

            # Ensure output directory exists
            ensure_directory(output_dir)

            # Create job with UUID-based ID for consistency
            # Use provided job_id or generate a new UUID
            job = ConversionJob(
                job_id=job_id or str(uuid.uuid4()),
                input_file=input_file,
                output_dir=output_dir,
                options=options.model_dump() if options else {},
                status=ConversionStatus.PENDING,
                started_at=None,
                completed_at=None,
                total_duration_seconds=None,
                quality_score=None,
                error_message=None,
            )

            # Initialize pipeline stages
            self._initialize_pipeline_stages(job)

            # Calculate adaptive timeout based on input file size/complexity
            calculated_timeout = self._calculate_adaptive_timeout(input_file)
            # Store timeout in job metadata for reference
            job.metadata["calculated_timeout"] = calculated_timeout
            # Use timeout from options if provided, otherwise use calculated
            job_timeout = (
                options.max_processing_time
                if options and hasattr(options, "max_processing_time")
                else calculated_timeout
            )
            job.metadata["timeout_seconds"] = job_timeout

            # Register job in active jobs tracking (thread-safe)
            with self._job_lock:
                self._active_jobs[job.job_id] = job

            logger.info(
                f"Created conversion job: {job.job_id} "
                f"(timeout: {job_timeout}s)"
            )
            return job

        except Exception as exc:
            # Catch all exceptions during job creation to provide proper error handling
            logger.exception(f"Failed to create conversion job: {exc}")
            raise ConversionPipelineError(
                f"Failed to create conversion job: {exc}", "initialization"
            ) from exc

    def execute_pipeline(self, job: ConversionJob) -> ConversionResult:
        """
        Execute the complete conversion pipeline.

        Args:
            job: Conversion job to execute

        Returns:
            ConversionResult: Final conversion result

        Raises:
            ConversionPipelineError: If pipeline execution fails
            PipelineTimeoutError: If pipeline execution exceeds timeout
        """
        # Ensure job is in active_jobs for progress tracking
        # Note: The job is already added to _active_jobs by create_conversion_job() (line 277),
        # but we ensure it's here as a safety measure in case execute_pipeline is called
        # directly or the job was removed. Both orchestrator._jobs and pipeline._active_jobs
        # reference the same job object (passed by reference) to maintain consistency.
        # This ensures modifications to the job object are visible in both locations.
        with self._job_lock:
            if job.job_id not in self._active_jobs:
                self._active_jobs[job.job_id] = job
                logger.debug(f"Added job {job.job_id} to _active_jobs for progress tracking")
            # Note: We don't check for different object references here because:
            # 1. The job is created once in create_conversion_job() and passed by reference
            # 2. If different instances exist, that's a bug in job creation, not here
            # 3. Checking here would only detect the symptom, not prevent the root cause
        
        job.status = ConversionStatus.RUNNING
        job.started_at = datetime.utcnow()

        # Get timeout from job metadata or use default
        timeout_seconds = job.metadata.get("timeout_seconds", self.default_timeout)

        try:
            logger.info(
                f"Starting pipeline execution for job: {job.job_id} "
                f"(timeout: {timeout_seconds}s)"
            )

            # Stage 1: Tectonic Compilation
            self._check_timeout(job, timeout_seconds)
            self._execute_tectonic_stage(job)

            # Stage 2: LaTeXML Conversion
            self._check_timeout(job, timeout_seconds)
            self._execute_latexml_stage(job)

            # Stage 3: HTML Post-Processing
            self._check_timeout(job, timeout_seconds)
            self._execute_post_processing_stage(job)

            # Stage 4: Validation
            self._check_timeout(job, timeout_seconds)
            self._execute_validation_stage(job)

            # Complete job
            job.status = ConversionStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.current_stage = ConversionStage.COMPLETED

            if job.started_at:
                job.total_duration_seconds = (
                    job.completed_at - job.started_at
                ).total_seconds()

            logger.info(f"Pipeline execution completed for job: {job.job_id}")

            return self.create_conversion_result(job)

        except PipelineTimeoutError:
            # Collect diagnostics before re-raising
            diagnostics = self._collect_conversion_diagnostics(job)
            job.metadata["diagnostics"] = diagnostics
            logger.error(
                f"Pipeline timeout for job {job.job_id}",
                extra={"diagnostics": diagnostics},
            )
            raise
        except Exception as exc:  # pylint: disable=broad-except
            # Catch all exceptions during pipeline execution to ensure proper cleanup
            # Collect diagnostics for debugging
            diagnostics = self._collect_conversion_diagnostics(job)
            job.metadata["diagnostics"] = diagnostics
            
            logger.exception(
                f"Pipeline execution failed for job {job.job_id}: {exc}",
                extra={"diagnostics": diagnostics},
            )
            job.status = ConversionStatus.FAILED
            job.completed_at = datetime.utcnow()
            job.error_message = str(exc)
            raise ConversionPipelineError(
                f"Pipeline execution failed: {exc}", job.current_stage.value, diagnostics
            ) from exc

    def _check_timeout(self, job: ConversionJob, timeout_seconds: int) -> None:
        """
        Check if job has exceeded timeout and raise error if so.

        Args:
            job: Conversion job to check
            timeout_seconds: Maximum allowed time in seconds

        Raises:
            PipelineTimeoutError: If timeout exceeded
        """
        if not job.started_at:
            return

        elapsed = (datetime.utcnow() - job.started_at).total_seconds()
        if elapsed > timeout_seconds:
            raise PipelineTimeoutError(
                f"Pipeline execution exceeded timeout of {timeout_seconds}s "
                f"(elapsed: {elapsed:.1f}s)",
                job.current_stage.value,
                {"timeout_seconds": timeout_seconds, "elapsed_seconds": elapsed},
            )

    def get_job_status(self, job_id: str) -> ConversionStatus | None:
        """
        Get the status of a conversion job.

        Args:
            job_id: Job identifier

        Returns:
            ConversionStatus: Job status or None if not found
        """
        with self._job_lock:
            job = self._active_jobs.get(job_id)
            if job:
                return job.status
        return None

    def get_job_progress(self, job_id: str) -> ConversionProgress | None:
        """
        Get progress information for a conversion job.

        Args:
            job_id: Job identifier

        Returns:
            ConversionProgress: Progress information or None if job not found
        """
        with self._job_lock:
            job = self._active_jobs.get(job_id)
            if not job:
                return None

        # Calculate overall progress
        # Use max() to enforce minimum of 1 to prevent division by zero
        # This handles edge case where job.stages might be empty
        total_stages = max(len(job.stages) if job.stages else 4, 1)
        completed_stages = sum(
            1 for stage in job.stages if stage.status == ConversionStatus.COMPLETED
        ) if job.stages else 0
        
        # Calculate base progress from completed stages
        # Division is safe because total_stages is set to at least 1 via max() above to prevent division by zero
        base_progress = (completed_stages / total_stages * 100)
        
        # Estimate progress for currently running stage based on elapsed time
        current_stage_progress = 0.0
        if job.stages:
            current_stage = job.stages[-1]
            if current_stage.status == ConversionStatus.RUNNING:
                # Estimate progress based on elapsed time vs expected duration
                if current_stage.started_at:
                    stage_elapsed = (
                        datetime.utcnow() - current_stage.started_at
                    ).total_seconds()
                    
                    # Get timeout for current stage from job metadata
                    job_timeout = job.metadata.get("timeout_seconds", self.default_timeout)
                    
                    # Estimate stage timeout based on stage type
                    if current_stage.name == "LaTeXML Conversion":
                        # LaTeXML gets 70% of total timeout
                        stage_timeout = job_timeout * 0.7
                    elif current_stage.name == "Tectonic Compilation":
                        # Tectonic gets 20% of total timeout
                        stage_timeout = job_timeout * 0.2
                    elif current_stage.name == "HTML Post-Processing":
                        # HTML post-processing gets 5% of total timeout
                        stage_timeout = job_timeout * 0.05
                    else:
                        # Other stages get 5% of total timeout
                        stage_timeout = job_timeout * 0.05
                    
                    # Estimate progress: min(95%, elapsed / expected * 100)
                    # Cap at 95% to avoid showing 100% before completion
                    if stage_timeout > 0:
                        estimated_progress = min(95.0, (stage_elapsed / stage_timeout) * 100)
                        current_stage_progress = max(0.0, estimated_progress)
                    else:
                        current_stage_progress = 0.0
                else:
                    current_stage_progress = current_stage.progress_percentage
            else:
                current_stage_progress = current_stage.progress_percentage
        
        # Overall progress = base progress + (current stage progress / total stages)
        # Division is safe because total_stages is set to at least 1 via max() above to prevent division by zero
        progress_percentage = base_progress + (current_stage_progress / total_stages)
        progress_percentage = min(99.0, progress_percentage)  # Cap at 99% until fully complete

        # Calculate elapsed time
        elapsed_seconds = None
        if job.started_at:
            elapsed_seconds = (datetime.utcnow() - job.started_at).total_seconds()

        return ConversionProgress(
            job_id=job.job_id,
            status=job.status,
            current_stage=job.current_stage,
            progress_percentage=progress_percentage,
            current_stage_progress=current_stage_progress,
            stages_completed=completed_stages,
            total_stages=total_stages,
            elapsed_seconds=elapsed_seconds,
            estimated_remaining_seconds=None,
            message=self._get_stage_message(job),
            warnings=self._collect_warnings(job),
            updated_at=datetime.utcnow(),
        )

    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a running conversion job.

        Args:
            job_id: Job identifier

        Returns:
            bool: True if job was cancelled, False if not found
        """
        with self._job_lock:
            job = self._active_jobs.get(job_id)
            if not job:
                return False

            if job.status in [
                ConversionStatus.COMPLETED,
                ConversionStatus.FAILED,
                ConversionStatus.CANCELLED,
            ]:
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
        with self._job_lock:
            job = self._active_jobs.get(job_id)
            if not job:
                return False

        try:
            # Clean up temporary files
            if job.output_dir.exists():
                cleanup_directory(job.output_dir)

            # Remove from active jobs (thread-safe)
            with self._job_lock:
                self._active_jobs.pop(job_id, None)

            logger.info(f"Cleaned up job: {job_id}")
            return True

        except (OSError, ValueError) as exc:
            # Catch file system and path validation errors to prevent cleanup
            # failure from crashing the service
            logger.exception(f"Failed to cleanup job {job_id}: {exc}")
            return False

    def _initialize_pipeline_stages(self, job: ConversionJob) -> None:
        """Initialize pipeline stages for a job."""
        stages = [
            PipelineStage(
                name="Tectonic Compilation",
                status=ConversionStatus.PENDING,
                started_at=None,
                completed_at=None,
                duration_seconds=None,
                progress_percentage=0.0,
                error_message=None,
                metadata={"service": "tectonic"},
            ),
            PipelineStage(
                name="LaTeXML Conversion",
                status=ConversionStatus.PENDING,
                started_at=None,
                completed_at=None,
                duration_seconds=None,
                progress_percentage=0.0,
                error_message=None,
                metadata={"service": "latexml"},
            ),
            PipelineStage(
                name="HTML Post-Processing",
                status=ConversionStatus.PENDING,
                started_at=None,
                completed_at=None,
                duration_seconds=None,
                progress_percentage=0.0,
                error_message=None,
                metadata={"service": "html_post"},
            ),
            PipelineStage(
                name="Output Validation",
                status=ConversionStatus.PENDING,
                started_at=None,
                completed_at=None,
                duration_seconds=None,
                progress_percentage=0.0,
                error_message=None,
                metadata={"service": "validation"},
            ),
        ]

        job.stages = stages

    def _validate_latex_syntax(self, tex_file: Path) -> dict[str, Any]:
        """
        Perform basic LaTeX syntax validation.

        Args:
            tex_file: Path to the main .tex file

        Returns:
            Dict with validation results
        """
        validation_result = {
            "valid": True,
            "warnings": [],
            "errors": [],
        }

        try:
            if not tex_file.exists():
                validation_result["valid"] = False
                validation_result["errors"].append("Main .tex file not found")
                return validation_result

            # Read file content
            with open(tex_file, encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # Check for basic LaTeX structure
            if "\\documentclass" not in content and "\\begin{document}" not in content:
                validation_result["warnings"].append(
                    "Missing \\documentclass or \\begin{document} - "
                    "may not be a valid LaTeX file"
                )

            # Check for balanced braces
            brace_count = content.count("{") - content.count("}")
            if brace_count != 0:
                brace_type = "extra opening" if brace_count > 0 else "extra closing"
                validation_result["warnings"].append(
                    f"Unbalanced braces detected: {abs(brace_count)} "
                    f"{brace_type} braces"
                )

            # Check for balanced environments
            begin_count = content.count("\\begin{")
            end_count = content.count("\\end{")
            if begin_count != end_count:
                validation_result["warnings"].append(
                    f"Unbalanced environments: {begin_count} \\begin vs "
                    f"{end_count} \\end"
                )

            # Check for common syntax errors
            if "\\end{document" in content and "\\end{document}" not in content:
                validation_result["errors"].append(
                    "Malformed \\end{document} - missing closing brace"
                )
                validation_result["valid"] = False

            # File is too short - likely corrupted or empty
            if len(content.strip()) < 50:
                validation_result["warnings"].append(
                    f"LaTeX file is very short ({len(content)} chars) - "
                    f"may be incomplete"
                )

        except OSError as exc:
            validation_result["valid"] = False
            validation_result["errors"].append(f"Failed to read LaTeX file: {exc}")

        return validation_result

    def _execute_tectonic_stage(self, job: ConversionJob) -> None:
        """Execute Tectonic compilation stage with enhanced file discovery
        and package management."""
        stage = job.stages[0]
        stage.status = ConversionStatus.RUNNING
        stage.started_at = datetime.utcnow()
        job.current_stage = ConversionStage.TECTONIC_COMPILING

        try:
            logger.info(f"Starting Tectonic compilation for job: {job.job_id}")

            # Step 1: Discover and prepare all project files
            logger.info("Discovering project files...")

            # Check if input file is a ZIP file or already extracted
            if job.input_file.suffix.lower() == ".zip":
                # Input is a ZIP file, extract it
                project_structure = self.file_discovery.extract_project_files(
                    job.input_file, job.output_dir
                )
            else:
                # Input is already extracted, create a minimal project structure
                logger.info(
                    "Input file is already extracted, creating project structure..."
                )
                project_structure = ProjectStructure(
                    main_tex_file=job.input_file,
                    all_tex_files=[job.input_file],
                    supporting_files={},
                    dependencies=LatexDependencies(),
                    project_dir=job.input_file.parent,
                    extracted_files=[job.input_file],
                )

            # Store project structure in job metadata
            job.metadata["project_structure"] = {
                "main_tex_file": str(project_structure.main_tex_file),
                "project_dir": str(
                    project_structure.project_dir
                ),  # Store actual project directory
                "files_discovered": len(project_structure.extracted_files),
                "custom_classes": project_structure.dependencies.custom_classes,
                "packages_required": len(project_structure.dependencies.packages),
            }

            # Step 2: Detect required packages
            logger.info("Detecting required packages...")
            required_packages = self.package_manager.detect_required_packages(
                project_structure.main_tex_file
            )

            # Step 3: Check and install missing packages
            if required_packages:
                logger.info(
                    f"Checking availability of {len(required_packages)} packages..."
                )
                missing_packages = []
                availability = self.package_manager.check_package_availability(
                    required_packages
                )

                for package, available in availability.items():
                    if not available:
                        missing_packages.append(package)

                if missing_packages:
                    logger.info(
                        f"Attempting to install {len(missing_packages)} "
                        f"missing packages: {missing_packages}"
                    )
                    install_result = self.package_manager.install_missing_packages(
                        missing_packages
                    )

                    if install_result.installed_packages:
                        logger.info(
                            f"Successfully installed "
                            f"{len(install_result.installed_packages)} packages"
                        )

                    if install_result.failed_packages:
                        failed_count = len(install_result.failed_packages)

                        # Get critical packages from centralized configuration
                        critical_packages = set(
                            settings.CRITICAL_LATEX_PACKAGES
                        )

                        # Check if any critical packages failed
                        failed_critical = [
                            pkg
                            for pkg in install_result.failed_packages
                            if pkg in critical_packages
                        ]

                        if failed_critical:
                            logger.warning(
                                f"Failed to install {len(failed_critical)} "
                                f"CRITICAL packages: {failed_critical}. "
                                f"Compilation may fail."
                            )
                            job.metadata["failed_critical_packages"] = failed_critical
                        else:
                            logger.debug(
                                f"Could not install {failed_count} packages: "
                                f"{install_result.failed_packages} "
                                f"(likely not critical)"
                            )

                        # Store all failed packages in metadata for debugging
                        job.metadata["failed_packages"] = (
                            install_result.failed_packages
                        )

            # Step 4: Compile with Tectonic
            logger.info("Starting Tectonic compilation...")

            # Catch Tectonic-specific errors if using Tectonic
            try:
                result = self.tectonic_service.compile_latex(
                    input_file=project_structure.main_tex_file,
                    output_dir=job.output_dir / "tectonic",
                    options=job.options.get("tectonic_options", {}),
                )
            except Exception as exc:
                # Wrap Tectonic errors if they aren't already wrapped in something pipeline understands
                # but let PDFLaTeXCompilationError pass through as it's caught below
                if isinstance(exc, PDFLaTeXCompilationError):
                    raise
                # Import here to avoid circular imports or early import issues
                from app.services.tectonic import TectonicCompilationError
                if isinstance(exc, TectonicCompilationError):
                    # Re-raise as is, or wrap if needed.
                    # The existing catch block handles PDFLaTeXCompilationError,
                    # we should probably catch TectonicCompilationError there too.
                    raise
                raise

            # Update stage
            stage.status = ConversionStatus.COMPLETED
            stage.completed_at = datetime.utcnow()
            stage.duration_seconds = (
                stage.completed_at - stage.started_at
            ).total_seconds()
            stage.progress_percentage = 100.0
            stage.metadata.update(result)

            job.current_stage = ConversionStage.TECTONIC_COMPLETED

            logger.info(f"Tectonic compilation completed for job: {job.job_id}")

        except (PDFLaTeXCompilationError, FileNotFoundError, Exception) as exc:
            # Check for TectonicCompilationError by name to avoid importing it if not needed
            is_tectonic_error = type(exc).__name__ == "TectonicCompilationError"

            # If it's not one of our expected errors and not TectonicError, re-raise
            if not isinstance(exc, (PDFLaTeXCompilationError, FileNotFoundError)) and not is_tectonic_error:
                raise exc

            # Log detailed error but continue with LaTeXML-only conversion
            error_details = {
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "fallback_available": True,
            }
            
            # Add file information if available
            if "project_structure" in job.metadata:
                error_details["main_tex_file"] = job.metadata["project_structure"].get(
                    "main_tex_file"
                )
            
            logger.warning(
                f"Tectonic compilation failed: {exc}",
                extra={"error_details": error_details},
            )
            logger.info("Falling back to LaTeXML-only conversion")

            stage.status = ConversionStatus.SKIPPED
            stage.completed_at = datetime.utcnow()
            stage.duration_seconds = (
                stage.completed_at - stage.started_at
            ).total_seconds()
            stage.metadata["fallback_reason"] = str(exc)
            stage.metadata["fallback_used"] = True
            stage.metadata["error_details"] = error_details

            # Update job metadata for fallback
            job.metadata["tectonic_failed"] = True
            job.metadata["fallback_reason"] = str(exc)
            job.metadata["tectonic_error"] = error_details

            # Validate LaTeX syntax before continuing to LaTeXML
            if "project_structure" in job.metadata:
                main_tex_file = Path(
                    job.metadata["project_structure"]["main_tex_file"]
                )
                validation = self._validate_latex_syntax(main_tex_file)

                if not validation["valid"]:
                    logger.error(
                        f"LaTeX validation failed after Tectonic failure. "
                        f"Errors: {validation['errors']}"
                    )
                    # Store validation errors in metadata
                    job.metadata["latex_validation_errors"] = validation["errors"]
                    # Still continue to LaTeXML, but warn that it may also fail
                    logger.warning(
                        "LaTeX has syntax errors - LaTeXML may also fail. "
                        "Continuing anyway..."
                    )

                if validation["warnings"]:
                    logger.warning(
                        f"LaTeX validation warnings: {validation['warnings']}"
                    )
                    job.metadata["latex_validation_warnings"] = validation["warnings"]

            # Don't raise - allow pipeline to continue with LaTeXML-only
            logger.info("Continuing with LaTeXML-only conversion")

    def _collect_conversion_diagnostics(self, job: ConversionJob) -> dict[str, Any]:
        """
        Collect detailed diagnostics for conversion failures.
        
        Args:
            job: Conversion job to analyze
            
        Returns:
            Dict with diagnostic information
        """
        diagnostics = {
            "job_id": job.job_id,
            "status": job.status.value if hasattr(job.status, "value") else str(job.status),
            "current_stage": job.current_stage.value if hasattr(job.current_stage, "value") else str(job.current_stage),
            "error_message": job.error_message,
        }
        
        # Add file information
        if "project_structure" in job.metadata:
            diagnostics["main_tex_file"] = job.metadata["project_structure"].get("main_tex_file")
            diagnostics["project_dir"] = job.metadata["project_structure"].get("project_dir")
            diagnostics["files_discovered"] = job.metadata["project_structure"].get("files_discovered", 0)
        
        # Add stage information
        diagnostics["stages"] = []
        for stage in job.stages:
            stage_info = {
                "name": stage.name,
                "status": stage.status.value if hasattr(stage.status, "value") else str(stage.status),
                "error_message": stage.error_message,
            }
            if "error_details" in stage.metadata:
                stage_info["error_details"] = stage.metadata["error_details"]
            diagnostics["stages"].append(stage_info)
        
        # Add timeout information
        if "timeout_seconds" in job.metadata:
            diagnostics["timeout_seconds"] = job.metadata["timeout_seconds"]
            if job.started_at:
                elapsed = (datetime.utcnow() - job.started_at).total_seconds()
                diagnostics["elapsed_seconds"] = elapsed
                diagnostics["timeout_remaining"] = job.metadata["timeout_seconds"] - elapsed
        
        # Add error information from metadata
        if "conversion_error" in job.metadata:
            diagnostics["conversion_error"] = job.metadata["conversion_error"]
        if "tectonic_error" in job.metadata:
            diagnostics["tectonic_error"] = job.metadata["tectonic_error"]
        
        return diagnostics

    def _execute_latexml_stage(self, job: ConversionJob) -> None:
        """Execute LaTeXML conversion stage with project structure support."""
        stage = job.stages[1]
        stage.status = ConversionStatus.RUNNING
        stage.started_at = datetime.utcnow()
        job.current_stage = ConversionStage.LATEXML_CONVERTING

        try:
            logger.info(f"Starting LaTeXML conversion for job: {job.job_id}")

            # Get project structure from metadata or discover it
            project_structure = None
            if "project_structure" in job.metadata:
                # Use already discovered project structure
                main_tex_path = job.metadata["project_structure"]["main_tex_file"]
                tex_file = Path(main_tex_path)
                # Use stored project_dir if available,
                # otherwise fall back to tex_file parent
                if "project_dir" in job.metadata["project_structure"]:
                    project_dir = Path(job.metadata["project_structure"]["project_dir"])
                else:
                    # Fallback for old metadata format: use the directory
                    # containing the main tex file
                    project_dir = tex_file.parent
                    logger.warning(
                        f"project_dir not in metadata, using tex_file "
                        f"parent: {project_dir}"
                    )
            else:
                # Fallback: discover project structure now
                logger.info("Project structure not found, discovering now...")
                # Check if input is a ZIP file or already extracted
                if job.input_file.suffix.lower() == ".zip":
                    project_structure = self.file_discovery.extract_project_files(
                        job.input_file, job.output_dir
                    )
                else:
                    # Input is already extracted, use its parent directory
                    # as project_dir
                    project_structure = ProjectStructure(
                        main_tex_file=job.input_file,
                        all_tex_files=[job.input_file],
                        supporting_files={},
                        dependencies=LatexDependencies(),
                        project_dir=job.input_file.parent,
                        extracted_files=[job.input_file],
                    )
                tex_file = project_structure.main_tex_file
                project_dir = project_structure.project_dir

            # Detect custom document class and find supporting files
            custom_class_info = None
            try:
                custom_class_info = self.latex_preprocessor.detect_custom_class(
                    tex_file, project_dir
                )
                if custom_class_info:
                    logger.info(
                        f"Detected custom class '{custom_class_info['class_name']}', "
                        f"class file: {custom_class_info.get('cls_file')}"
                    )
                    # Add class file directory to project_dir paths if found
                    if custom_class_info.get("cls_file"):
                        cls_file_dir = custom_class_info["cls_file"].parent
                        if cls_file_dir not in [Path(d) for d in custom_class_info.get("search_dirs", [])]:
                            # Ensure this directory is in the path for LaTeXML
                            if project_dir != cls_file_dir:
                                logger.info(
                                    f"Adding class file directory to search path: {cls_file_dir}"
                                )
            except Exception as preprocess_exc:
                logger.warning(
                    f"Custom class detection failed: {preprocess_exc}"
                )

            # Convert with LaTeXML
            latexml_options_dict = job.options.get("latexml_options", {})
            
            # If custom class detected, ensure its directory is in the path
            # LaTeXML should be able to find and use the class file via --path
            # We don't need to replace the class - just make sure LaTeXML can find it
            
            # Use adaptive timeout from job if not specified in options
            if "conversion_timeout" not in latexml_options_dict:
                job_timeout = job.metadata.get("timeout_seconds", self.default_timeout)
                # Allocate 70% of total timeout to LaTeXML (most time-consuming stage)
                # Increased from 60% to 70% for better handling of large files
                latexml_timeout = int(job_timeout * 0.7)
                latexml_options_dict["conversion_timeout"] = latexml_timeout
                logger.info(
                    f"Using adaptive LaTeXML timeout: {latexml_timeout}s "
                    f"(from job timeout: {job_timeout}s, max: {self.max_timeout * 0.7:.0f}s)"
                )
            
            latexml_options = LaTeXMLConversionOptions(**latexml_options_dict)

            # Pass project directory for custom classes and styles
            # If custom class detected, ensure its directory is accessible
            # The --path option in LaTeXML should allow it to find the class file
            result = self.latexml_service.convert_tex_to_html(
                input_file=tex_file,
                output_dir=job.output_dir / "latexml",
                options=latexml_options,
                project_dir=project_dir,
            )

            # Update stage
            stage.status = ConversionStatus.COMPLETED
            stage.completed_at = datetime.utcnow()
            stage.duration_seconds = (
                stage.completed_at - stage.started_at
            ).total_seconds()
            stage.progress_percentage = 100.0
            stage.metadata.update(result)
            
            # Store custom class info in metadata if detected
            if custom_class_info:
                stage.metadata["custom_class"] = custom_class_info

            job.current_stage = ConversionStage.LATEXML_COMPLETED

            logger.info(f"LaTeXML conversion completed for job: {job.job_id}")

        except LaTeXMLError as exc:
            stage.status = ConversionStatus.FAILED
            stage.error_message = str(exc)
            stage.completed_at = datetime.utcnow()
            
            # Collect detailed error information for debugging
            error_details = {
                "error_type": getattr(exc, "error_type", "UNKNOWN_ERROR"),
                "error_message": str(exc),
                "details": getattr(exc, "details", {}),
            }
            
            # Add file information if available
            if "project_structure" in job.metadata:
                error_details["main_tex_file"] = job.metadata["project_structure"].get(
                    "main_tex_file"
                )
                error_details["project_dir"] = job.metadata["project_structure"].get(
                    "project_dir"
                )
            
            stage.metadata["error_details"] = error_details
            job.metadata["conversion_error"] = error_details
            
            logger.error(
                f"LaTeXML conversion failed for job {job.job_id}: {exc}",
                extra={"error_details": error_details},
            )
            
            raise ConversionPipelineError(
                f"LaTeXML conversion failed: {exc}", "latexml_conversion", error_details
            ) from exc

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
                    "No HTML files found in LaTeXML output", "post_processing"
                )

            html_file = html_files[0]  # Use the first HTML file

            # Process HTML
            result = self.html_processor.process_html(
                html_file=html_file,
                output_file=job.output_dir / "final.html",
                options=job.options.get("post_processing_options", {}),
            )

            # Copy figures and assets from project directory to output
            self._copy_project_assets(job)

            # Update stage
            stage.status = ConversionStatus.COMPLETED
            stage.completed_at = datetime.utcnow()
            stage.duration_seconds = (
                stage.completed_at - stage.started_at
            ).total_seconds()
            stage.progress_percentage = 100.0
            stage.metadata.update(result)

            job.current_stage = ConversionStage.POST_PROCESSING_COMPLETED

            logger.info(f"HTML post-processing completed for job: {job.job_id}")

        except HTMLPostProcessingError as exc:
            stage.status = ConversionStatus.FAILED
            stage.error_message = str(exc)
            stage.completed_at = datetime.utcnow()
            raise ConversionPipelineError(
                f"HTML post-processing failed: {exc}", "post_processing"
            ) from exc

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
                    "Final HTML output file not found", "validation"
                )

            # Basic validation checks
            file_info = get_file_info(output_file)
            if file_info["size"] == 0:
                raise ConversionPipelineError(
                    "Final HTML output file is empty", "validation"
                )

            # Update job with output files
            job.output_files = [output_file]
            job.assets = list(job.output_dir.glob("*.svg")) + list(
                job.output_dir.glob("*.png")
            )

            # Content verification and diff report features removed - pending Greptile review
            # TODO: Re-enable after PR #18 is properly reviewed
            # main_tex_file = self._find_main_tex_file(job)
            # if main_tex_file and main_tex_file.exists():
            #     logger.info("Running content verification...")
            #     ... (content verification code commented out)
            
            # Fall back to simplified quality score
            job.quality_score = self._calculate_quality_score(job)

            # Update stage
            stage.status = ConversionStatus.COMPLETED
            stage.completed_at = datetime.utcnow()
            stage.duration_seconds = (
                stage.completed_at - stage.started_at
            ).total_seconds()
            stage.progress_percentage = 100.0

            job.current_stage = ConversionStage.COMPLETED

            logger.info(f"Output validation completed for job: {job.job_id}")

        except Exception as exc:
            # Catch all exceptions during output validation to mark stage as failed
            stage.status = ConversionStatus.FAILED
            stage.error_message = str(exc)
            stage.completed_at = datetime.utcnow()
            raise ConversionPipelineError(
                f"Output validation failed: {exc}", "validation"
            ) from exc

    def _copy_project_assets(self, job: ConversionJob) -> None:
        """Copy figures, images, and CSS from project directory to output."""
        try:
            # Get project directory from metadata
            if (
                "project_structure" in job.metadata
                and "project_dir" in job.metadata["project_structure"]
            ):
                project_dir = Path(job.metadata["project_structure"]["project_dir"])
            else:
                # Fallback: use input file parent
                project_dir = (
                    job.input_file.parent
                    if job.input_file.is_file()
                    else job.input_file
                )

            if not project_dir.exists():
                logger.warning(f"Project directory not found: {project_dir}")
                return

            # Get asset patterns from config
            asset_patterns = settings.ASSET_PATTERNS
            assets_copied = 0

            # Copy all image files from project directory
            for pattern in asset_patterns:
                for asset_file in project_dir.rglob(pattern):
                    # Skip hidden directories and __MACOSX
                    if any(
                        part.startswith(".") or part == "__MACOSX"
                        for part in asset_file.parts
                    ):
                        continue

                    # Handle filename collisions by preserving relative path
                    # from project root
                    dest_file = job.output_dir / asset_file.name
                    if dest_file.exists():
                        # If collision, preserve subdirectory structure
                        try:
                            rel_path = asset_file.relative_to(project_dir)
                            dest_file = job.output_dir / rel_path
                            dest_file.parent.mkdir(parents=True, exist_ok=True)
                        except ValueError:
                            # File is outside project_dir, use counter suffix
                            counter = 1
                            stem, suffix = asset_file.stem, asset_file.suffix
                            while dest_file.exists():
                                dest_file = job.output_dir / f"{stem}_{counter}{suffix}"
                                counter += 1

                    shutil.copy2(asset_file, dest_file)
                    assets_copied += 1
                    relative_path = dest_file.relative_to(job.output_dir)
                    logger.debug(
                        f"Copied asset: {asset_file.name} -> "
                        f"{relative_path}"
                    )

            # Copy CSS files from latexml output to root
            latexml_dir = job.output_dir / "latexml"
            if latexml_dir.exists():
                for css_file in latexml_dir.glob("*.css"):
                    dest_file = job.output_dir / css_file.name
                    if not dest_file.exists():
                        shutil.copy2(css_file, dest_file)
                        logger.debug(f"Copied CSS: {css_file.name}")

            logger.info(f"Copied {assets_copied} assets to output directory")

        except (OSError, ValueError) as exc:
            # Catch file system and path validation exceptions to prevent
            # asset copying failure from failing conversion
            logger.warning(
                f"Failed to copy project assets: {exc}"
            )
            # Don't fail the conversion if asset copying fails

    # Method disabled - part of PR #18 content verification feature (pending review)
    def _add_diff_report_link_to_html(self, html_file: Path, diff_report_path: Path) -> None:
        """Add a link to the diff report in the verification banner."""
        # Method disabled - PR #18 feature pending Greptile review
        logger.debug("Diff report link feature disabled - PR #18 pending review")
        return

    def _find_main_tex_file(self, job: ConversionJob) -> Path | None:
        """Find the main .tex file from job metadata or input file."""
        # Try to get from project structure metadata
        if "project_structure" in job.metadata:
            main_tex = job.metadata["project_structure"].get("main_tex_file")
            if main_tex:
                return Path(main_tex)

        # If input file is a .tex file, use that
        if job.input_file.suffix == ".tex":
            return job.input_file

        # Search for .tex files in the project directory
        project_dir = job.input_file.parent if job.input_file.is_file() else job.input_file
        tex_files = list(project_dir.glob("*.tex"))

        if tex_files:
            # Prefer files named main.tex, document.tex, etc.
            for preferred_name in ["main.tex", "document.tex", "paper.tex", "manuscript.tex"]:
                for tex_file in tex_files:
                    if tex_file.name.lower() == preferred_name:
                        return tex_file

            # Return the first .tex file found
            return tex_files[0]

        return None

    def _calculate_quality_score(self, job: ConversionJob) -> float:
        """Calculate quality score for the conversion."""
        # Simplified quality scoring
        score = 85.0  # Base score

        # Adjust based on file sizes and content
        if job.output_files:
            output_file = job.output_files[0]
            file_info = get_file_info(output_file)

            # Adjust score based on file size
            # (larger files might indicate better conversion)
            if file_info["size"] > 10000:  # 10KB
                score += 5.0
            elif file_info["size"] < 1000:  # 1KB
                score -= 10.0

        # Adjust based on number of assets
        if len(job.assets) > 0:
            score += min(len(job.assets) * 2, 10.0)

        return min(max(score, 0.0), 100.0)

    def create_conversion_result(self, job: ConversionJob) -> ConversionResult:
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
            stages_completed=[
                stage.name
                for stage in job.stages
                if stage.status == ConversionStatus.COMPLETED
            ],
            warnings=self._collect_warnings(job),
            errors=[stage.error_message for stage in job.stages if stage.error_message],
            created_at=job.created_at,
            completed_at=job.completed_at or datetime.utcnow(),
            metadata=job.metadata,
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
