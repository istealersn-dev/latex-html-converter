"""
Conversion API endpoints for the LaTeX → HTML5 Converter application.

This module provides endpoints for file upload and conversion processing.
"""

import json
import os
import shutil
import tempfile
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from loguru import logger

from app.config import settings
from app.models.conversion import ConversionOptions
from app.models.conversion import ConversionStatus as ConversionStatusEnum
from app.models.response import ConversionResponse, ConversionStatus, ConversionStatusResponse
from app.services.orchestrator import OrchestrationError, ResourceLimitError, get_orchestrator
from app.utils.fs import ensure_sufficient_disk_space

router = APIRouter()

# In-memory storage for conversion tracking
# In production, this should be replaced with a proper database
_conversion_storage: dict[str, dict[str, Any]] = {}
_storage_lock = threading.RLock()  # Reentrant lock for thread safety
_cleanup_thread: threading.Thread | None = None
_shutdown_event = threading.Event()


# Helper functions (defined before use)

def _safe_get_conversion(conversion_id: str) -> dict[str, Any] | None:
    """
    Thread-safe get conversion data.

    Args:
        conversion_id: Conversion ID to retrieve

    Returns:
        Conversion data or None if not found
    """
    with _storage_lock:
        return _conversion_storage.get(conversion_id)


def _safe_set_conversion(conversion_id: str, data: dict[str, Any]) -> None:
    """
    Thread-safe set conversion data.

    Args:
        conversion_id: Conversion ID to store
        data: Conversion data to store
    """
    with _storage_lock:
        _conversion_storage[conversion_id] = data


def _safe_remove_conversion(conversion_id: str) -> dict[str, Any] | None:
    """
    Thread-safe remove conversion data.

    Args:
        conversion_id: Conversion ID to remove

    Returns:
        Removed conversion data or None if not found
    """
    with _storage_lock:
        return _conversion_storage.pop(conversion_id, None)


def _safe_update_conversion(conversion_id: str, updates: dict[str, Any]) -> bool:
    """
    Thread-safe update conversion data.

    Args:
        conversion_id: Conversion ID to update
        updates: Updates to apply

    Returns:
        True if conversion existed and was updated, False otherwise
    """
    with _storage_lock:
        if conversion_id in _conversion_storage:
            _conversion_storage[conversion_id].update(updates)
            return True
        return False


def _cleanup_old_conversions() -> int:
    """
    Clean up old conversion entries from storage.

    Returns:
        Number of entries cleaned up
    """
    cutoff_time = datetime.utcnow() - timedelta(hours=24)
    cleaned_count = 0

    with _storage_lock:
        conversions_to_remove = []
        orchestrator = get_orchestrator()

        for conv_id, conv_data in _conversion_storage.items():
            # Get job status from orchestrator
            status = orchestrator.get_job_status(conv_id)

            # Remove if job is completed/failed and old, or if job no longer exists
            if status is None or status in [ConversionStatusEnum.COMPLETED, ConversionStatusEnum.FAILED, ConversionStatusEnum.CANCELLED]:
                # Check if we have a timestamp
                created_at_str = conv_data.get('created_at')
                if created_at_str:
                    try:
                        created_at = datetime.fromisoformat(created_at_str) if isinstance(created_at_str, str) else created_at_str
                        if created_at < cutoff_time:
                            conversions_to_remove.append(conv_id)
                    except (ValueError, TypeError):
                        # If timestamp parsing fails, remove it anyway
                        conversions_to_remove.append(conv_id)
                else:
                    # No timestamp, remove it
                    conversions_to_remove.append(conv_id)

        for conv_id in conversions_to_remove:
            conv_data = _conversion_storage.pop(conv_id, None)
            if conv_data:
                # Clean up directories
                for dir_key in ['upload_dir', 'output_dir', 'temp_dir']:
                    if dir_key in conv_data:
                        dir_path = Path(conv_data[dir_key])
                        if dir_path.exists():
                            try:
                                shutil.rmtree(dir_path, ignore_errors=True)
                                logger.debug(f"Cleaned up directory: {dir_path}")
                            except Exception as exc:
                                logger.warning(f"Failed to clean up directory {dir_path}: {exc}")
                cleaned_count += 1

    if cleaned_count > 0:
        logger.info(f"Cleaned up {cleaned_count} old conversion entries")

    return cleaned_count


def _cleanup_loop() -> None:
    """Background cleanup loop for old conversions."""
    while not _shutdown_event.is_set():
        try:
            _cleanup_old_conversions()
            # Wait for 1 hour or until shutdown
            _shutdown_event.wait(3600)
        except Exception as exc:
            logger.error(f"Error in cleanup loop: {exc}")
            _shutdown_event.wait(60)  # Wait 1 minute before retrying


def start_cleanup_thread() -> None:
    """Start the background cleanup thread."""
    global _cleanup_thread

    if _cleanup_thread is None or not _cleanup_thread.is_alive():
        _cleanup_thread = threading.Thread(
            target=_cleanup_loop,
            name="conversion-storage-cleanup",
            daemon=True
        )
        _cleanup_thread.start()
        logger.info("Started conversion storage cleanup thread")


def stop_cleanup_thread() -> None:
    """Stop the background cleanup thread."""
    global _cleanup_thread

    _shutdown_event.set()

    if _cleanup_thread and _cleanup_thread.is_alive():
        _cleanup_thread.join(timeout=5.0)
        logger.info("Stopped conversion storage cleanup thread")


def _create_result_zip(output_dir: Path, output_zip: Path) -> None:
    """
    Create a ZIP file containing the conversion results.

    Args:
        output_dir: Output directory containing results
        output_zip: Path for the output ZIP file
    """
    import zipfile

    try:
        with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add HTML file - check for final.html first, then look in latexml subdirectory
            html_file = output_dir / "final.html"
            html_in_latexml = False
            if not html_file.exists():
                # Check in latexml subdirectory
                latexml_html = output_dir / "latexml" / "main.html"
                if latexml_html.exists():
                    html_file = latexml_html
                    html_in_latexml = True
            
            if html_file.exists():
                # Preserve directory structure: if HTML is in latexml/, add it as latexml/main.html
                # This ensures image paths in the HTML (like figures/fig.svg) match the ZIP structure
                if html_in_latexml:
                    zipf.write(html_file, html_file.relative_to(output_dir))
                else:
                    # final.html goes to root of ZIP
                    zipf.write(html_file, html_file.name)

            # Add assets from output directory and subdirectories
            # Preserve relative paths to maintain directory structure
            for asset_file in output_dir.rglob("*.svg"):
                if asset_file != output_zip and asset_file != html_file:  # Don't include the zip file itself or the HTML file
                    zipf.write(asset_file, asset_file.relative_to(output_dir))
            
            for asset_file in output_dir.rglob("*.png"):
                if asset_file != output_zip and asset_file != html_file:
                    zipf.write(asset_file, asset_file.relative_to(output_dir))

        logger.info(f"Created result ZIP: {output_zip}")
    except Exception as exc:
        logger.error(f"Failed to create result ZIP: {exc}")
        raise


def _cleanup_temp_directory(temp_dir: Path) -> None:
    """
    Clean up temporary directory.

    Args:
        temp_dir: Temporary directory to clean up
    """
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.info(f"Cleaned up temporary directory: {temp_dir}")
    except Exception as exc:
        logger.error(f"Failed to clean up temporary directory {temp_dir}: {exc}")


@router.post("/convert", response_model=ConversionResponse)
async def convert_latex_to_html(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    options: str | None = Form(None)
) -> ConversionResponse:
    """
    Convert LaTeX project to HTML5 using the conversion orchestrator.

    Args:
        background_tasks: FastAPI background tasks for async processing
        file: Uploaded LaTeX project file (zip/tar.gz)
        options: Optional conversion options as JSON string

    Returns:
        ConversionResponse: Conversion result with HTML and assets
    """
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")

        # Check file extension
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"File type not supported. Allowed: {settings.ALLOWED_EXTENSIONS}"
            )

        # Read file content
        file_content = await file.read()

        # Check file size
        if len(file_content) > settings.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size: {settings.MAX_FILE_SIZE} bytes"
            )

        # Validate file content (basic security check)
        if not _validate_file_content(file_content, file_ext):
            raise HTTPException(
                status_code=400,
                detail="Invalid file content or potential security risk"
            )

        # Parse conversion options
        request_options = _parse_conversion_options(options)

        # Convert to orchestrator options
        conversion_options = None
        if request_options:
            conversion_options = ConversionOptions(
                tectonic_options=request_options.model_dump(),
                latexml_options=request_options.model_dump(),
                post_processing_options=request_options.model_dump()
            )

        # Check disk space before processing
        # Estimate required space: 3x file size for extraction + processing
        required_space_mb = (len(file_content) * 3) / (1024 * 1024)
        required_space_mb = max(required_space_mb, 100)  # Minimum 100 MB

        try:
            ensure_sufficient_disk_space(Path.cwd(), int(required_space_mb))
        except OSError as exc:
            raise HTTPException(
                status_code=507,  # Insufficient Storage
                detail=f"Insufficient disk space: {exc}"
            )

        # Create organized directory structure
        project_root = Path.cwd()
        uploads_dir = project_root / "uploads"
        outputs_dir = project_root / "outputs"

        # Create base directories if they don't exist
        uploads_dir.mkdir(exist_ok=True)
        outputs_dir.mkdir(exist_ok=True)

        # Generate unique job ID and create job-specific directories
        job_id = str(uuid.uuid4())
        zip_name = file.filename.rsplit('.', 1)[0]  # Remove extension

        # Create job directories
        job_upload_dir = uploads_dir / job_id
        job_output_dir = outputs_dir / f"{zip_name}_{job_id}"

        job_upload_dir.mkdir(exist_ok=True)
        job_output_dir.mkdir(exist_ok=True)

        try:
            # Save uploaded file to uploads/job_id/
            input_file = job_upload_dir / file.filename
            with open(input_file, "wb") as f:
                f.write(file_content)

            logger.info(f"Saved upload to: {input_file}")

            # Extract archive in upload directory
            extracted_dir = _extract_archive(input_file, job_upload_dir)
            logger.info(f"Extracted archive to: {extracted_dir}")

            # Find main LaTeX file
            main_tex_file = _find_main_tex_file(extracted_dir)
            if not main_tex_file:
                raise HTTPException(
                    status_code=400,
                    detail="No main LaTeX file found in archive"
                )

            # Output goes to outputs/zip_name_job_id/
            output_dir = job_output_dir
            logger.info(f"Output will be saved to: {output_dir}")

            # Get orchestrator and start conversion
            logger.info("Getting orchestrator...")
            orchestrator = get_orchestrator()
            logger.info("Orchestrator obtained successfully")

            try:
                logger.info(f"Starting conversion: {main_tex_file} -> {output_dir}")
                conversion_job_id = orchestrator.start_conversion(
                    input_file=main_tex_file,
                    output_dir=output_dir,
                    options=conversion_options,
                    job_id=job_id  # Use the same job_id for folder naming and conversion tracking
                )

                # Initialize conversion storage entry with directory paths for later retrieval
                _safe_set_conversion(conversion_job_id, {
                    "upload_dir": str(job_upload_dir),
                    "output_dir": str(job_output_dir),
                    "zip_name": zip_name,
                    "created_at": datetime.utcnow().isoformat()
                })

                logger.info(f"Started conversion job: {conversion_job_id}")

                # For now, return a pending response
                # In a real implementation, this would be handled asynchronously
                response = ConversionResponse(
                    conversion_id=conversion_job_id,
                    status=ConversionStatus.PENDING,
                    html_file="",  # Will be populated when conversion completes
                    assets=[],     # Will be populated when conversion completes
                    report={
                        "score": 0.0,
                        "missing_macros": [],
                        "packages_used": [],
                        "conversion_time": 0.0,
                        "timestamp": datetime.utcnow().isoformat(),
                        "options": conversion_options.model_dump() if conversion_options else {}
                    }
                )

                return response

            except ResourceLimitError as exc:
                # Cleanup storage entry on resource limit error
                _safe_remove_conversion(conversion_job_id)
                raise HTTPException(
                    status_code=503,
                    detail=f"Service temporarily unavailable: {exc}"
                )
            except OrchestrationError as exc:
                # Cleanup storage entry on orchestration error
                _safe_remove_conversion(conversion_job_id)
                raise HTTPException(
                    status_code=500,
                    detail=f"Conversion failed: {exc}"
                )

        except Exception as exc:
            # Cleanup on error - remove job directories
            logger.error(f"Error during conversion setup: {exc}")
            shutil.rmtree(job_upload_dir, ignore_errors=True)
            shutil.rmtree(job_output_dir, ignore_errors=True)
            raise

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Conversion failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Conversion failed: {str(exc)}")


@router.get("/convert/{conversion_id}", response_model=ConversionStatusResponse)
async def get_conversion_status(conversion_id: str) -> ConversionStatusResponse:
    """
    Get the status of a conversion job using the orchestrator.

    Args:
        conversion_id: Unique conversion identifier

    Returns:
        ConversionStatusResponse: Conversion status and progress
    """
    try:
        orchestrator = get_orchestrator()

        # Get job status
        status = orchestrator.get_job_status(conversion_id)
        if not status:
            raise HTTPException(status_code=404, detail="Conversion not found")

        # Get progress information
        progress = orchestrator.get_job_progress(conversion_id)
        
        # Get job details for timestamps
        job_result = orchestrator.get_job_result(conversion_id)
        created_at = datetime.utcnow()
        if job_result:
            created_at = job_result.created_at

        # Map orchestrator status to API status
        status_mapping = {
            ConversionStatusEnum.PENDING: ConversionStatus.PENDING,
            ConversionStatusEnum.RUNNING: ConversionStatus.PROCESSING,
            ConversionStatusEnum.COMPLETED: ConversionStatus.COMPLETED,
            ConversionStatusEnum.FAILED: ConversionStatus.FAILED,
            ConversionStatusEnum.CANCELLED: ConversionStatus.CANCELLED,
        }
        api_status = status_mapping.get(status, ConversionStatus.PENDING)
        progress_percentage = progress.progress_percentage if progress else 0.0
        message = progress.message if progress and progress.message else f"Status: {status.value}"
        
        # Get error message if failed
        error_message = None
        if status == ConversionStatusEnum.FAILED and job_result and job_result.errors:
            error_message = "; ".join(job_result.errors)

        return ConversionStatusResponse(
            conversion_id=conversion_id,
            job_id=conversion_id,  # job_id is the same as conversion_id
            status=api_status,
            progress=int(progress_percentage),
            message=message,
            created_at=created_at,
            updated_at=datetime.utcnow(),
            error_message=error_message
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Status check failed for {conversion_id}: {exc}")
        raise HTTPException(status_code=500, detail="Status check failed")


@router.get("/convert/{conversion_id}/result", response_model=ConversionResponse)
async def get_conversion_result(conversion_id: str) -> ConversionResponse:
    """
    Get the full conversion result including HTML file and assets.

    Args:
        conversion_id: Unique conversion identifier

    Returns:
        ConversionResponse: Full conversion result with HTML file and assets
    """
    try:
        orchestrator = get_orchestrator()

        # Get job status first
        status = orchestrator.get_job_status(conversion_id)
        if not status:
            raise HTTPException(status_code=404, detail="Conversion not found")

        # Get conversion result from orchestrator
        result = orchestrator.get_job_result(conversion_id)
        
        # Get conversion data from storage for directory paths
        conversion_data = _safe_get_conversion(conversion_id)
        output_dir = None
        if conversion_data and "output_dir" in conversion_data:
            output_dir = Path(conversion_data["output_dir"])

        # If conversion is completed, get the actual files
        html_file_path = ""
        assets_list = []
        report_data = {
            "score": 0.0,
            "missing_macros": [],
            "packages_used": [],
            "conversion_time": 0.0,
            "timestamp": datetime.utcnow().isoformat(),
            "options": {}
        }

        if status == ConversionStatusEnum.COMPLETED and result:
            # Get HTML file path - use getattr to avoid type checker issues with Pydantic
            main_html = getattr(result, 'main_html_file', None)
            if main_html is not None and isinstance(main_html, Path) and main_html.exists():
                html_file_path = str(main_html)
            elif output_dir:
                # Fallback: look for final.html in output directory
                final_html = output_dir / "final.html"
                if final_html.exists():
                    html_file_path = str(final_html)

            # Get assets
            if result.assets:
                assets_list = [str(asset) for asset in result.assets if asset.exists()]
            elif output_dir:
                # Fallback: find assets in output directory
                assets_list = [
                    str(f) for f in 
                    list(output_dir.glob("*.svg")) + list(output_dir.glob("*.png")) + list(output_dir.glob("*.jpg"))
                ]

            # Build report from result - use getattr to avoid type checker issues with Pydantic
            metadata_dict = getattr(result, 'metadata', {})
            if not isinstance(metadata_dict, dict):
                metadata_dict = {}
            completed_at_dt = getattr(result, 'completed_at', None)
            if not isinstance(completed_at_dt, datetime):
                completed_at_dt = None
            
            report_data = {
                "score": result.quality_score or 0.0,
                "missing_macros": result.errors or [],
                "packages_used": metadata_dict.get("packages_used", []),
                "conversion_time": result.total_duration_seconds or 0.0,
                "timestamp": completed_at_dt.isoformat() if completed_at_dt else datetime.utcnow().isoformat(),
                "options": metadata_dict.get("options", {}),
                "warnings": result.warnings or [],
                "stages_completed": result.stages_completed or []
            }

        # Map orchestrator status to API status
        status_mapping = {
            ConversionStatusEnum.PENDING: ConversionStatus.PENDING,
            ConversionStatusEnum.RUNNING: ConversionStatus.PROCESSING,
            ConversionStatusEnum.COMPLETED: ConversionStatus.COMPLETED,
            ConversionStatusEnum.FAILED: ConversionStatus.FAILED,
            ConversionStatusEnum.CANCELLED: ConversionStatus.CANCELLED,
        }
        api_status = status_mapping.get(status, ConversionStatus.PENDING)

        # Get creation and completion times
        created_at = datetime.utcnow()
        completed_at = None
        error_message = None

        if result:
            created_at = getattr(result, 'created_at', datetime.utcnow())
            if not isinstance(created_at, datetime):
                created_at = datetime.utcnow()
            completed_at = getattr(result, 'completed_at', None)
            if not isinstance(completed_at, datetime) and completed_at is not None:
                completed_at = None
            if status == ConversionStatusEnum.FAILED:
                errors = getattr(result, 'errors', [])
                if errors:
                    error_message = "; ".join(errors)

        return ConversionResponse(
            conversion_id=conversion_id,
            status=api_status,
            html_file=html_file_path,
            assets=assets_list,
            report=report_data,
            created_at=created_at,
            completed_at=completed_at,
            error_message=error_message
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to get conversion result for {conversion_id}: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to get conversion result: {str(exc)}")


@router.get("/convert/{conversion_id}/download")
async def download_conversion_result(conversion_id: str) -> FileResponse:
    """
    Download the result of a conversion job.

    Args:
        conversion_id: Unique conversion identifier

    Returns:
        FileResponse: ZIP file containing HTML and assets
    """
    try:
        # Check if conversion exists in storage
        conversion_data = _safe_get_conversion(conversion_id)
        if not conversion_data:
            raise HTTPException(status_code=404, detail="Conversion not found")

        # Get output directory from storage
        output_dir = None
        if "output_dir" in conversion_data:
            output_dir = Path(conversion_data["output_dir"])
        elif "temp_dir" in conversion_data:
            # Fallback for old format
            output_dir = Path(conversion_data["temp_dir"])

        if not output_dir or not output_dir.exists():
            raise HTTPException(
                status_code=410,
                detail="Conversion files have been cleaned up"
            )

        # Create a ZIP file with the conversion results
        output_zip = output_dir / f"{conversion_id}_result.zip"
        _create_result_zip(output_dir, output_zip)

        if not output_zip.exists():
            raise HTTPException(
                status_code=500,
                detail="Failed to create download package"
            )

        return FileResponse(
            path=str(output_zip),
            filename=f"conversion_{conversion_id}.zip",
            media_type="application/zip"
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Download failed for {conversion_id}: {exc}")
        raise HTTPException(status_code=500, detail="Download failed")


# Helper functions

def _validate_file_content(file_content: bytes, file_ext: str) -> bool:
    """
    Validate file content for security and format.

    Args:
        file_content: File content as bytes
        file_ext: File extension

    Returns:
        bool: True if file is valid, False otherwise
    """
    # Basic security checks
    if len(file_content) == 0:
        return False

    # Check for suspicious patterns
    suspicious_patterns = [
        b'<script',
        b'javascript:',
        b'vbscript:',
        b'data:text/html',
        b'<iframe',
        b'<object',
        b'<embed'
    ]

    content_lower = file_content.lower()
    for pattern in suspicious_patterns:
        if pattern in content_lower:
            logger.warning(f"Suspicious pattern found in uploaded file: {pattern!r}")
            return False

    # File-specific validation
    if file_ext == '.zip':
        # Check ZIP file signature
        return file_content.startswith(b'PK')
    elif file_ext in ['.tar', '.tar.gz']:
        # Basic tar file validation
        return len(file_content) > 512  # Minimum tar file size

    return True


def _parse_conversion_options(options: str | None) -> ConversionOptions | None:
    """
    Parse conversion options from JSON string.

    Args:
        options: JSON string of conversion options

    Returns:
        ConversionOptions: Parsed options or None
    """
    if not options:
        return None

    try:
        options_dict = json.loads(options)
        return ConversionOptions(**options_dict)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning(f"Invalid conversion options: {exc}")
        return None


def _extract_archive(input_file: Path, temp_dir: Path, timeout: int = 300) -> Path:
    """
    Extract archive file to temporary directory with security checks and timeout.

    Args:
        input_file: Path to input archive file
        temp_dir: Temporary directory for extraction
        timeout: Maximum time in seconds for extraction (default: 5 minutes)

    Returns:
        Path: Path to extracted directory

    Raises:
        HTTPException: If extraction fails, times out, or archive is malicious
    """
    import zipfile
    import tarfile
    import signal
    from contextlib import contextmanager

    @contextmanager
    def time_limit(seconds: int):
        """Context manager to enforce time limit on operations."""
        def signal_handler(signum, frame):
            raise TimeoutError(f"Archive extraction timed out after {seconds} seconds")

        # Set the signal handler and alarm
        old_handler = signal.signal(signal.SIGALRM, signal_handler)
        signal.alarm(seconds)
        try:
            yield
        finally:
            # Restore old handler and disable alarm
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

    extracted_dir = temp_dir / "extracted"
    extracted_dir.mkdir(exist_ok=True)

    def is_safe_path(base_path: Path, target_path: Path) -> bool:
        """Check if target_path is within base_path (prevents zip slip)."""
        try:
            # Resolve to absolute paths
            base_abs = base_path.resolve()
            target_abs = target_path.resolve()

            # Check if target is within base
            return str(target_abs).startswith(str(base_abs))
        except Exception:
            return False

    try:
        with time_limit(timeout):
            if input_file.suffix.lower() == '.zip':
                with zipfile.ZipFile(input_file, 'r') as zip_ref:
                    # Validate all paths before extraction
                    for member in zip_ref.namelist():
                        member_path = extracted_dir / member
                        if not is_safe_path(extracted_dir, member_path):
                            raise HTTPException(
                                status_code=400,
                                detail=f"Archive contains unsafe path: {member} (potential zip slip attack)"
                            )

                    # Safe to extract
                    zip_ref.extractall(extracted_dir)

            elif input_file.suffix.lower() in ['.tar', '.gz'] or input_file.name.endswith('.tar.gz'):
                with tarfile.open(input_file, 'r:*') as tar_ref:
                    # Validate all paths before extraction
                    for member in tar_ref.getmembers():
                        member_path = extracted_dir / member.name
                        if not is_safe_path(extracted_dir, member_path):
                            raise HTTPException(
                                status_code=400,
                                detail=f"Archive contains unsafe path: {member.name} (potential zip slip attack)"
                            )

                        # Additional security: check for absolute paths
                        if member.name.startswith('/') or member.name.startswith('..'):
                            raise HTTPException(
                                status_code=400,
                                detail=f"Archive contains absolute or parent path: {member.name}"
                            )

                    # Safe to extract
                    tar_ref.extractall(extracted_dir)
            else:
                raise ValueError(f"Unsupported archive format: {input_file.suffix}")

        logger.info(f"Successfully extracted archive to: {extracted_dir}")
        return extracted_dir

    except TimeoutError as exc:
        logger.error(f"Archive extraction timed out: {exc}")
        raise HTTPException(
            status_code=408,  # Request Timeout
            detail=str(exc)
        )
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as exc:
        logger.error(f"Failed to extract archive {input_file}: {exc}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to extract archive: {exc}"
        )


def _find_main_tex_file(extracted_dir: Path) -> Path | None:
    """
    Find the main LaTeX file in the extracted directory.

    Args:
        extracted_dir: Path to extracted directory

    Returns:
        Path: Path to main LaTeX file or None if not found
    """
    # Look for common LaTeX file names
    main_candidates = [
        "main.tex",
        "document.tex",
        "paper.tex",
        "article.tex",
        "thesis.tex",
        "report.tex"
    ]

    # Check for main candidates first
    for candidate in main_candidates:
        candidate_path = extracted_dir / candidate
        if candidate_path.exists():
            return candidate_path

    # If no main candidate found, look for any .tex file
    tex_files = list(extracted_dir.glob("*.tex"))
    if tex_files:
        # Return the first .tex file found
        return tex_files[0]

    # Look in subdirectories recursively
    for tex_file in extracted_dir.rglob("*.tex"):
        return tex_file

    return None
