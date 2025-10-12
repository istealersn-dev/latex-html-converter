"""
Conversion API endpoints for the LaTeX → HTML5 Converter application.

This module provides endpoints for file upload and conversion processing.
"""

import json
import os
import shutil
import tempfile
import threading
import time
import uuid
from datetime import datetime
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

router = APIRouter()

# In-memory storage for conversion tracking
# In production, this should be replaced with a proper database
_conversion_storage: dict[str, dict[str, Any]] = {}
_storage_lock = threading.RLock()  # Reentrant lock for thread safety


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


def _schedule_delayed_cleanup(conversion_id: str, cleanup_time: datetime) -> None:
    """
    Schedule delayed cleanup for a conversion using threading.

    Args:
        conversion_id: Conversion ID to clean up
        cleanup_time: When to perform cleanup
    """
    def _delayed_cleanup() -> None:
        """Thread function for delayed cleanup."""
        try:
            # Wait until cleanup time
            now = datetime.utcnow()
            if cleanup_time > now:
                wait_seconds = (cleanup_time - now).total_seconds()
                time.sleep(wait_seconds)

            # Check if conversion still exists and hasn't been accessed recently
            conversion_data = _safe_get_conversion(conversion_id)
            if conversion_data and not conversion_data.get("cleanup_scheduled", False):
                # Mark as scheduled to prevent multiple cleanups
                if _safe_update_conversion(conversion_id, {"cleanup_scheduled": True}):
                    # Clean up the files
                    temp_dir = Path(conversion_data["temp_dir"])
                    _cleanup_temp_directory(temp_dir)

                    # Remove from storage
                    _safe_remove_conversion(conversion_id)
                    logger.info(f"Scheduled cleanup completed for conversion {conversion_id}")
        except Exception as exc:
            logger.error(f"Cleanup thread failed for conversion {conversion_id}: {exc}")

    # Start cleanup thread
    cleanup_thread = threading.Thread(
        target=_delayed_cleanup,
        name=f"cleanup-{conversion_id}",
        daemon=True  # Don't prevent app shutdown
    )
    cleanup_thread.start()
    logger.info(f"Started cleanup thread for conversion {conversion_id}")


def _create_result_zip(temp_dir: Path, output_zip: Path) -> None:
    """
    Create a ZIP file containing the conversion results.

    Args:
        temp_dir: Temporary directory containing results
        output_zip: Path for the output ZIP file
    """
    import zipfile

    try:
        with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add HTML file
            html_file = temp_dir / "output" / "index.html"
            if html_file.exists():
                zipf.write(html_file, "index.html")

            # Add assets
            output_dir = temp_dir / "output"
            for asset_file in output_dir.glob("*.svg"):
                zipf.write(asset_file, asset_file.name)

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

        # Create temporary directory for processing
        temp_dir = Path(tempfile.mkdtemp(prefix=f"conversion_{uuid.uuid4()}_"))

        try:
            # Save uploaded file
            input_file = temp_dir / f"input{file_ext}"
            with open(input_file, "wb") as f:
                f.write(file_content)

            # Extract archive if needed
            extracted_dir = _extract_archive(input_file, temp_dir)
            logger.info(f"Extracted archive to: {extracted_dir}")

            # Find main LaTeX file
            main_tex_file = _find_main_tex_file(extracted_dir)
            if not main_tex_file:
                raise HTTPException(
                    status_code=400,
                    detail="No main LaTeX file found in archive"
                )

            # Create output directory
            output_dir = temp_dir / "output"
            output_dir.mkdir(exist_ok=True)

            # Get orchestrator and start conversion
            orchestrator = get_orchestrator()

            try:
                job_id = orchestrator.start_conversion(
                    input_file=main_tex_file,
                    output_dir=output_dir,
                    options=conversion_options
                )

                logger.info(f"Started conversion job: {job_id}")

                # For now, return a pending response
                # In a real implementation, this would be handled asynchronously
                response = ConversionResponse(
                    conversion_id=job_id,
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
                raise HTTPException(
                    status_code=503,
                    detail=f"Service temporarily unavailable: {exc}"
                )
            except OrchestrationError as exc:
                raise HTTPException(
                    status_code=500,
                    detail=f"Conversion failed: {exc}"
                )

        except Exception:
            # Cleanup on error
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Conversion failed: {exc}")
        raise HTTPException(status_code=500, detail="Conversion failed")


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

        return ConversionStatusResponse(
            conversion_id=conversion_id,
            status=api_status,
            progress=int(progress_percentage),
            message=message,
            created_at=datetime.utcnow(),  # TODO: Get actual creation time from job
            updated_at=datetime.utcnow()
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Status check failed for {conversion_id}: {exc}")
        raise HTTPException(status_code=500, detail="Status check failed")


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

        # Check if files still exist
        temp_dir = Path(conversion_data["temp_dir"])
        if not temp_dir.exists():
            raise HTTPException(
                status_code=410,
                detail="Conversion files have been cleaned up"
            )

        # Create a ZIP file with the conversion results
        output_zip = temp_dir / f"{conversion_id}_result.zip"
        _create_result_zip(temp_dir, output_zip)

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


def _extract_archive(input_file: Path, temp_dir: Path) -> Path:
    """
    Extract archive file to temporary directory.

    Args:
        input_file: Path to input archive file
        temp_dir: Temporary directory for extraction

    Returns:
        Path: Path to extracted directory
    """
    extracted_dir = temp_dir / "extracted"
    extracted_dir.mkdir(exist_ok=True)

    # TODO: Implement actual archive extraction
    # For now, just create a mock structure
    mock_tex_file = extracted_dir / "main.tex"
    with open(mock_tex_file, "w", encoding="utf-8") as f:
        f.write("\\documentclass{article}\n\\begin{document}\nHello World!\n\\end{document}")

    return extracted_dir


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

    # Look in subdirectories
    for subdir in extracted_dir.iterdir():
        if subdir.is_dir():
            subdir_tex_files = list(subdir.glob("*.tex"))
            if subdir_tex_files:
                return subdir_tex_files[0]

    return None


def _create_mock_html(filename: str) -> str:
    """
    Create mock HTML content.

    Args:
        filename: Original filename

    Returns:
        str: Mock HTML content
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Converted from {filename}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .header {{ color: #333; border-bottom: 2px solid #eee; padding-bottom: 10px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>LaTeX to HTML5 Conversion</h1>
        <p>Converted from: {filename}</p>
    </div>
    <div class="content">
        <h2>Sample Content</h2>
        <p>This is a mock conversion result. The actual conversion logic will be implemented in future phases.</p>
        <p>Mathematical expressions: $E = mc^2$ and $$\\int_{{-\\infty}}^{{\\infty}} e^{{-x^2}} dx = \\sqrt{{\\pi}}$$</p>
    </div>
</body>
</html>"""


def _create_mock_assets(output_dir: Path) -> list[Path]:
    """
    Create mock asset files.

    Args:
        output_dir: Output directory for assets

    Returns:
        list[Path]: List of created asset files
    """
    assets = []

    # Create mock SVG files
    for i in range(2):
        svg_file = output_dir / f"figure_{i+1}.svg"
        with open(svg_file, "w", encoding="utf-8") as f:
            f.write(f"""<svg width="200" height="100" xmlns="http://www.w3.org/2000/svg">
    <rect width="200" height="100" fill="#f0f0f0" stroke="#333" stroke-width="2"/>
    <text x="100" y="50" text-anchor="middle" font-family="Arial" font-size="14">
        Mock Figure {i+1}
    </text>
</svg>""")
        assets.append(svg_file)

    return assets
