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
from app.services.latexml import LaTeXMLError, LaTeXMLService
from app.services.package_manager import PackageManagerService
from app.services.pdflatex import PDFLaTeXCompilationError, PDFLaTeXService
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
        tectonic_service: PDFLaTeXService | None = None,
        latexml_service: LaTeXMLService | None = None,
        html_processor: HTMLPostProcessor | None = None,
        file_discovery: FileDiscoveryService | None = None,
        package_manager: PackageManagerService | None = None,
    ):
        """
        Initialize the conversion pipeline.

        Args:
            tectonic_service: Tectonic service instance
            latexml_service: LaTeXML service instance
            html_processor: HTML post-processor instance
            file_discovery: File discovery service instance
            package_manager: Package manager service instance
        """
        self.tectonic_service = tectonic_service or PDFLaTeXService(
            pdflatex_path=settings.PDFLATEX_PATH
        )
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

        # Pipeline configuration
        self.max_concurrent_jobs = 5
        self.default_timeout = 600  # 10 minutes
        self.cleanup_delay = 3600  # 1 hour

        # Active jobs tracking
        self._active_jobs: dict[str, ConversionJob] = {}
        self._job_lock = threading.RLock()  # Thread-safe access to active jobs

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

            # Register job in active jobs tracking (thread-safe)
            with self._job_lock:
                self._active_jobs[job.job_id] = job

            logger.info(f"Created conversion job: {job.job_id}")
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
                job.total_duration_seconds = (
                    job.completed_at - job.started_at
                ).total_seconds()

            logger.info(f"Pipeline execution completed for job: {job.job_id}")

            return self.create_conversion_result(job)

        except Exception as exc:
            # Catch all exceptions during pipeline execution to ensure proper cleanup
            logger.exception(f"Pipeline execution failed for job {job.job_id}: {exc}")
            job.status = ConversionStatus.FAILED
            job.completed_at = datetime.utcnow()
            job.error_message = str(exc)
            raise ConversionPipelineError(
                f"Pipeline execution failed: {exc}", job.current_stage.value
            ) from exc

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
        total_stages = len(job.stages)
        completed_stages = sum(
            1 for stage in job.stages if stage.status == ConversionStatus.COMPLETED
        )
        progress_percentage = (
            (completed_stages / total_stages * 100) if total_stages > 0 else 0.0
        )

        # Calculate elapsed time
        elapsed_seconds = None
        if job.started_at:
            elapsed_seconds = (datetime.utcnow() - job.started_at).total_seconds()

        return ConversionProgress(
            job_id=job.job_id,
            status=job.status,
            current_stage=job.current_stage,
            progress_percentage=progress_percentage,
            current_stage_progress=job.stages[-1].progress_percentage
            if job.stages
            else 0.0,
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
            result = self.tectonic_service.compile_latex(
                input_file=project_structure.main_tex_file,
                output_dir=job.output_dir / "tectonic",
                options=job.options.get("tectonic_options", {}),
            )

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

        except (PDFLaTeXCompilationError, FileNotFoundError) as exc:
            # Log detailed error but continue with LaTeXML-only conversion
            logger.warning(f"Tectonic compilation failed: {exc}")
            logger.info("Falling back to LaTeXML-only conversion")

            stage.status = ConversionStatus.SKIPPED
            stage.completed_at = datetime.utcnow()
            stage.duration_seconds = (
                stage.completed_at - stage.started_at
            ).total_seconds()
            stage.metadata["fallback_reason"] = str(exc)
            stage.metadata["fallback_used"] = True

            # Update job metadata for fallback
            job.metadata["tectonic_failed"] = True
            job.metadata["fallback_reason"] = str(exc)

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

            # Convert with LaTeXML
            latexml_options = LaTeXMLConversionOptions(
                **job.options.get("latexml_options", {})
            )

            # Pass project directory for custom classes and styles
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

            job.current_stage = ConversionStage.LATEXML_COMPLETED

            logger.info(f"LaTeXML conversion completed for job: {job.job_id}")

        except LaTeXMLError as exc:
            stage.status = ConversionStatus.FAILED
            stage.error_message = str(exc)
            stage.completed_at = datetime.utcnow()
            raise ConversionPipelineError(
                f"LaTeXML conversion failed: {exc}", "latexml_conversion"
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

            # Calculate quality score (simplified)
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
