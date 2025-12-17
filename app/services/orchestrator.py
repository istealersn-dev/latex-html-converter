"""
Conversion orchestrator service for the LaTeX → HTML5 Converter.

This service manages the overall conversion workflow, job scheduling,
resource management, and coordination between different services.
"""

import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from loguru import logger

from app.config import settings
from app.models.conversion import (
    ConversionJob,
    ConversionOptions,
    ConversionProgress,
    ConversionResult,
    ConversionStatus,
)
from app.services.pipeline import ConversionPipeline


class OrchestrationError(Exception):
    """Base exception for orchestration errors."""


class JobNotFoundError(OrchestrationError):
    """Raised when a job is not found."""


class ResourceLimitError(OrchestrationError):
    """Raised when resource limits are exceeded."""


class ConversionOrchestrator:
    """Main conversion orchestrator service."""

    def __init__(
        self,
        max_concurrent_jobs: int = 5,
        max_job_duration: int = 600,
        cleanup_interval: int = 3600,
    ):
        """
        Initialize the conversion orchestrator.

        Args:
            max_concurrent_jobs: Maximum number of concurrent jobs
            max_job_duration: Maximum job duration in seconds
            cleanup_interval: Cleanup interval in seconds
        """
        self.max_concurrent_jobs = max_concurrent_jobs
        self.max_job_duration = max_job_duration
        self.cleanup_interval = cleanup_interval

        # Job management
        self._jobs: dict[str, ConversionJob] = {}
        self._job_lock = threading.RLock()
        self._active_job_ids: set[str] = set()

        # Pipeline
        self._pipeline = ConversionPipeline()

        # Background tasks
        self._cleanup_thread: threading.Thread | None = None
        self._monitor_thread: threading.Thread | None = None
        self._shutdown_event = threading.Event()

        # Statistics
        self._stats = {
            "total_jobs": 0,
            "completed_jobs": 0,
            "failed_jobs": 0,
            "cancelled_jobs": 0,
            "total_processing_time": 0.0,
        }

        # Start background tasks
        self._start_background_tasks()

        logger.info("Conversion orchestrator initialized")

    def start_conversion(
        self,
        input_file: Path,
        output_dir: Path,
        options: ConversionOptions | None = None,
        job_id: str | None = None,
    ) -> str:
        """
        Start a new conversion job.

        Args:
            input_file: Path to input LaTeX file
            output_dir: Path to output directory
            options: Conversion options
            job_id: Optional job ID

        Returns:
            str: Job ID

        Raises:
            ResourceLimitError: If resource limits are exceeded
            OrchestrationError: If job creation fails
        """
        with self._job_lock:
            # Check resource limits
            if len(self._active_job_ids) >= self.max_concurrent_jobs:
                raise ResourceLimitError(
                    f"Maximum concurrent jobs ({self.max_concurrent_jobs}) exceeded"
                )

            job_created_id = None
            try:
                # Generate or validate job ID
                requested_job_id = job_id or str(uuid4())

                # Check for duplicate job ID
                if requested_job_id in self._jobs:
                    raise OrchestrationError(
                        f"Job ID {requested_job_id} already exists. "
                        f"Cannot create duplicate job."
                    )

                # Create job
                job = self._pipeline.create_conversion_job(
                    input_file=input_file,
                    output_dir=output_dir,
                    options=options,
                    job_id=requested_job_id,
                )
                job_created_id = job.job_id

                # Store job and mark as active atomically
                self._jobs[job.job_id] = job
                self._active_job_ids.add(job.job_id)
                self._stats["total_jobs"] += 1

                # Start conversion in background
                self._start_conversion_task(job)

                logger.info(f"Started conversion job: {job.job_id}")
                return job.job_id

            except Exception as exc:
                # Cleanup on failure: remove from active jobs if it was added
                if job_created_id and job_created_id in self._active_job_ids:
                    self._active_job_ids.discard(job_created_id)
                    # Also remove from jobs dict if it was added
                    self._jobs.pop(job_created_id, None)

                logger.exception(f"Failed to start conversion: {exc}")
                raise OrchestrationError(f"Failed to start conversion: {exc}") from exc

    def get_job_status(self, job_id: str) -> ConversionStatus | None:
        """
        Get the status of a conversion job.

        Args:
            job_id: Job identifier

        Returns:
            ConversionStatus: Job status or None if not found
        """
        with self._job_lock:
            # First check orchestrator's _jobs
            job = self._jobs.get(job_id)
            if job:
                return job.status
            
            # If not found, check pipeline's _active_jobs (where jobs are during execution)
            with self._pipeline._job_lock:
                pipeline_job = self._pipeline._active_jobs.get(job_id)
                if pipeline_job:
                    return pipeline_job.status
            
            return None

    def get_job_progress(self, job_id: str) -> ConversionProgress | None:
        """
        Get progress information for a conversion job.

        Args:
            job_id: Job identifier

        Returns:
            ConversionProgress: Progress information or None if not found
        """
        with self._job_lock:
            # First try to get progress from pipeline (it has the most up-to-date job state)
            pipeline_progress = self._pipeline.get_job_progress(job_id)
            if pipeline_progress:
                return pipeline_progress
            
            # If pipeline doesn't have it, try to get job from orchestrator's _jobs
            job = self._jobs.get(job_id)
            if job:
                # Calculate progress from the job directly
                return self._calculate_progress_from_job(job)
            
            # Job not found in either location
            return None

    def _calculate_progress_from_job(self, job: ConversionJob) -> ConversionProgress:
        """Calculate progress from a job object."""
        from datetime import datetime
        
        # Calculate basic progress from job stages
        total_stages = len(job.stages) if job.stages else 4
        completed_stages = sum(
            1 for stage in job.stages 
            if stage.status == ConversionStatus.COMPLETED
        ) if job.stages else 0
        
        base_progress = (
            (completed_stages / total_stages * 100) if total_stages > 0 else 0.0
        )
        
        # Estimate progress for running stage
        current_stage_progress = 0.0
        if job.stages:
            current_stage = job.stages[-1]
            if current_stage.status == ConversionStatus.RUNNING and current_stage.started_at:
                stage_elapsed = (datetime.utcnow() - current_stage.started_at).total_seconds()
                job_timeout = job.metadata.get("timeout_seconds", 600)
                
                if current_stage.name == "LaTeXML Conversion":
                    stage_timeout = job_timeout * 0.7
                elif current_stage.name == "Tectonic Compilation":
                    stage_timeout = job_timeout * 0.2
                elif current_stage.name == "HTML Post-Processing":
                    stage_timeout = job_timeout * 0.05
                else:
                    stage_timeout = job_timeout * 0.05
                
                if stage_timeout > 0:
                    estimated_progress = min(95.0, (stage_elapsed / stage_timeout) * 100)
                    current_stage_progress = max(0.0, estimated_progress)
            else:
                current_stage_progress = current_stage.progress_percentage if job.stages else 0.0
        
        progress_percentage = base_progress + (current_stage_progress / total_stages) if total_stages > 0 else 0.0
        progress_percentage = min(99.0, progress_percentage)
        
        elapsed_seconds = None
        if job.started_at:
            elapsed_seconds = (datetime.utcnow() - job.started_at).total_seconds()
        
        # Get stage message
        message = "Processing"
        if job.current_stage:
            stage_name = job.current_stage.value.replace("_", " ").title()
            message = f"Processing {stage_name.lower()}"
        
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
            message=message,
            warnings=[],
            updated_at=datetime.utcnow(),
        )

    def get_job_result(self, job_id: str) -> ConversionResult | None:
        """
        Get the result of a completed conversion job.

        Args:
            job_id: Job identifier

        Returns:
            ConversionResult: Conversion result or None if not found/not completed
        """
        with self._job_lock:
            job = self._jobs.get(job_id)
            if not job or job.status not in [
                ConversionStatus.COMPLETED,
                ConversionStatus.FAILED,
            ]:
                return None

            return self._pipeline.create_conversion_result(job)

    def get_job_diagnostics(self, job_id: str) -> dict[str, Any] | None:
        """
        Get detailed diagnostics for a conversion job.

        Args:
            job_id: Job identifier

        Returns:
            Dict with diagnostic information or None if job not found
        """
        with self._job_lock:
            job = self._jobs.get(job_id)
            if not job:
                return None

            # Get diagnostics from job metadata if available
            if "diagnostics" in job.metadata:
                return job.metadata["diagnostics"]
            
            # Otherwise collect diagnostics from pipeline
            return self._pipeline._collect_conversion_diagnostics(job)

    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a running conversion job.

        Args:
            job_id: Job identifier

        Returns:
            bool: True if job was cancelled, False if not found or not cancellable
        """
        with self._job_lock:
            job = self._jobs.get(job_id)
            if not job:
                return False

            if job.status not in [ConversionStatus.PENDING, ConversionStatus.RUNNING]:
                return False

            # Cancel the job
            success = self._pipeline.cancel_job(job_id)
            if success:
                self._stats["cancelled_jobs"] += 1
                self._active_job_ids.discard(job_id)
                logger.info(f"Cancelled job: {job_id}")

            return success

    def list_jobs(
        self,
        status_filter: ConversionStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ConversionJob]:
        """
        List conversion jobs with optional filtering and pagination.

        Args:
            status_filter: Optional status filter
            limit: Maximum number of jobs to return (default: 100)
            offset: Number of jobs to skip (default: 0)

        Returns:
            List[ConversionJob]: List of jobs

        Example:
            # Get first page (10 jobs)
            jobs = orchestrator.list_jobs(limit=10, offset=0)

            # Get second page (next 10 jobs)
            jobs = orchestrator.list_jobs(limit=10, offset=10)
        """
        with self._job_lock:
            jobs = list(self._jobs.values())

            if status_filter:
                jobs = [job for job in jobs if job.status == status_filter]

            # Sort by creation time (newest first)
            jobs.sort(key=lambda x: x.created_at, reverse=True)

            # Apply pagination
            start_idx = offset
            end_idx = offset + limit
            return jobs[start_idx:end_idx]

    def count_jobs(self, status_filter: ConversionStatus | None = None) -> int:
        """
        Count total number of jobs matching filter.

        Args:
            status_filter: Optional status filter

        Returns:
            int: Total count of matching jobs
        """
        with self._job_lock:
            if status_filter:
                return sum(
                    1 for job in self._jobs.values() if job.status == status_filter
                )
            return len(self._jobs)

    def get_statistics(self) -> dict[str, Any]:
        """
        Get orchestrator statistics.

        Returns:
            Dict[str, Any]: Statistics dictionary
        """
        with self._job_lock:
            active_jobs = len(self._active_job_ids)
            total_jobs = len(self._jobs)

            return {
                **self._stats,
                "active_jobs": active_jobs,
                "total_jobs_stored": total_jobs,
                "max_concurrent_jobs": self.max_concurrent_jobs,
                "max_job_duration": self.max_job_duration,
                "uptime_seconds": time.time()
                - getattr(self, "_start_time", time.time()),
            }

    def cleanup_completed_jobs(self, older_than_hours: int = 24) -> int:
        """
        Clean up completed jobs older than specified hours.

        Args:
            older_than_hours: Clean up jobs older than this many hours

        Returns:
            int: Number of jobs cleaned up
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=older_than_hours)
        cleaned_count = 0

        with self._job_lock:
            jobs_to_remove = []

            for job_id, job in self._jobs.items():
                if (
                    job.status
                    in [
                        ConversionStatus.COMPLETED,
                        ConversionStatus.FAILED,
                        ConversionStatus.CANCELLED,
                    ]
                    and job.completed_at
                    and job.completed_at < cutoff_time
                ):
                    jobs_to_remove.append(job_id)

            for job_id in jobs_to_remove:
                job = self._jobs.pop(job_id, None)
                if job:
                    # Clean up job resources
                    self._pipeline.cleanup_job(job_id)
                    cleaned_count += 1
                    logger.info(f"Cleaned up old job: {job_id}")

        logger.info(f"Cleaned up {cleaned_count} old jobs")
        return cleaned_count

    def shutdown(self) -> None:
        """Shutdown the orchestrator and clean up resources."""
        logger.info("Shutting down conversion orchestrator...")

        # Signal shutdown
        self._shutdown_event.set()

        # Wait for background threads
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5.0)

        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5.0)

        # Cancel all active jobs
        with self._job_lock:
            for job_id in list(self._active_job_ids):
                self.cancel_job(job_id)

        logger.info("Conversion orchestrator shutdown complete")

    def _start_conversion_task(self, job: ConversionJob) -> None:
        """Start a conversion task in a background thread."""

        def _run_conversion():
            try:
                logger.info(f"Starting conversion task for job: {job.job_id}")

                # Execute pipeline
                self._pipeline.execute_pipeline(job)

                # Update statistics and cleanup - always happens
                with self._job_lock:
                    if job.status == ConversionStatus.COMPLETED:
                        self._stats["completed_jobs"] += 1
                    elif job.status == ConversionStatus.FAILED:
                        self._stats["failed_jobs"] += 1

                    if job.total_duration_seconds:
                        self._stats["total_processing_time"] += (
                            job.total_duration_seconds
                        )

                    # Always remove from active jobs when done
                    self._active_job_ids.discard(job.job_id)

                logger.info(f"Conversion task completed for job: {job.job_id}")

            except Exception as exc:
                # Catch all exceptions to ensure job cleanup and status update
                logger.exception(f"Conversion task failed for job {job.job_id}: {exc}")

                with self._job_lock:
                    job.status = ConversionStatus.FAILED
                    job.completed_at = datetime.utcnow()
                    job.error_message = str(exc)
                    self._stats["failed_jobs"] += 1
                    # Ensure immediate cleanup on failure
                    self._active_job_ids.discard(job.job_id)

        try:
            # Start background thread
            thread = threading.Thread(
                target=_run_conversion, name=f"conversion-{job.job_id}", daemon=True
            )
            thread.start()

            # Verify thread started successfully
            if not thread.is_alive():
                # Thread failed to start - clean up immediately
                logger.error(f"Failed to start background thread for job {job.job_id}")
                with self._job_lock:
                    job.status = ConversionStatus.FAILED
                    job.completed_at = datetime.utcnow()
                    job.error_message = "Failed to start background conversion thread"
                    self._stats["failed_jobs"] += 1
                    self._active_job_ids.discard(job.job_id)

        except Exception as exc:
            # Thread creation failed - clean up immediately
            # Catch all exceptions to ensure proper cleanup on thread creation failure
            logger.exception(
                f"Failed to create background thread for job {job.job_id}: {exc}"
            )
            with self._job_lock:
                job.status = ConversionStatus.FAILED
                job.completed_at = datetime.utcnow()
                job.error_message = f"Failed to create background thread: {exc}"
                self._stats["failed_jobs"] += 1
                self._active_job_ids.discard(job.job_id)

    def _start_background_tasks(self) -> None:
        """Start background monitoring and cleanup tasks."""
        self._start_time = time.time()

        # Start cleanup thread
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop, name="orchestrator-cleanup", daemon=True
        )
        self._cleanup_thread.start()

        # Start monitor thread
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, name="orchestrator-monitor", daemon=True
        )
        self._monitor_thread.start()

        logger.info("Started background tasks")

    def _cleanup_loop(self) -> None:
        """Background cleanup loop."""
        while not self._shutdown_event.is_set():
            try:
                # Clean up old jobs (using same retention period as conversion storage)
                self.cleanup_completed_jobs(
                    older_than_hours=settings.CONVERSION_RETENTION_HOURS
                )

                # Wait for next cleanup cycle
                self._shutdown_event.wait(self.cleanup_interval)

            except Exception as exc:
                # Catch all exceptions to prevent cleanup loop from crashing
                logger.exception(f"Cleanup loop error: {exc}")
                time.sleep(60)  # Wait before retrying

    def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        while not self._shutdown_event.is_set():
            try:
                # Check for stuck jobs
                self._check_stuck_jobs()

                # Wait for next monitoring cycle
                self._shutdown_event.wait(30)

            except Exception as exc:
                # Catch all exceptions to prevent monitor loop from crashing
                logger.exception(f"Monitor loop error: {exc}")
                time.sleep(30)  # Wait before retrying

    def _check_stuck_jobs(self) -> None:
        """Check for and handle stuck jobs."""
        current_time = datetime.utcnow()
        stuck_jobs = []

        with self._job_lock:
            for job_id, job in self._jobs.items():
                if (
                    job.status == ConversionStatus.RUNNING
                    and job.started_at
                    and (current_time - job.started_at).total_seconds()
                    > self.max_job_duration
                ):
                    stuck_jobs.append(job_id)

        for job_id in stuck_jobs:
            logger.warning(f"Job {job_id} appears to be stuck, cancelling")
            self.cancel_job(job_id)


# ============================================================================
# GLOBAL STATE - Singleton Orchestrator Instance
# ============================================================================
# NOTE: This global variable implements the Singleton pattern for the orchestrator.
# This is acceptable and intentional for the following reasons:
# 1. Single Source of Truth: Ensures all API requests use the same orchestrator
# 2. Resource Management: Centralized management of concurrent jobs and cleanup
# 3. Thread-Safety: Protected by lock in get_orchestrator() for initialization
# 4. Lifecycle: Properly initialized on first access and shut down on app shutdown
#
# The orchestrator itself is thread-safe:
# - All internal operations use self._job_lock
# - Background threads are properly managed
# - Supports graceful shutdown
# ============================================================================

_orchestrator: ConversionOrchestrator | None = None  # Singleton instance


def get_orchestrator() -> ConversionOrchestrator:
    """
    Get the global orchestrator instance.

    Returns:
        ConversionOrchestrator: Global orchestrator instance
    """
    global _orchestrator

    if _orchestrator is None:
        _orchestrator = ConversionOrchestrator(
            max_concurrent_jobs=settings.MAX_CONCURRENT_CONVERSIONS,
            max_job_duration=settings.CONVERSION_TIMEOUT,
            cleanup_interval=3600,  # 1 hour
        )

    return _orchestrator


def shutdown_orchestrator() -> None:
    """Shutdown the global orchestrator."""
    global _orchestrator

    if _orchestrator:
        _orchestrator.shutdown()
        _orchestrator = None
