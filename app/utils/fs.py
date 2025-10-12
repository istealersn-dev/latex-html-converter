"""
Filesystem utilities for safe file operations.

This module provides secure filesystem operations with proper error handling,
path validation, and security considerations.
"""

import shutil
import tempfile
from pathlib import Path

from loguru import logger


def ensure_directory(path: str | Path) -> Path:
    """
    Ensure directory exists, creating it if necessary.

    Args:
        path: Directory path to ensure

    Returns:
        Path object of the directory

    Raises:
        OSError: If directory cannot be created
        ValueError: If path is invalid
    """
    path = Path(path)

    # Security: Validate path
    _validate_path_safety(path)

    try:
        path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Directory ensured: {path}")
        return path
    except OSError as exc:
        logger.error(f"Failed to create directory {path}: {exc}")
        raise


def cleanup_directory(path: str | Path, keep_files: set[str] | None = None) -> None:
    """
    Safely clean up directory contents.

    Args:
        path: Directory to clean up
        keep_files: Set of filenames to keep (optional)

    Raises:
        OSError: If cleanup fails
        ValueError: If path is invalid
    """
    path = Path(path)

    if not path.exists():
        logger.debug(f"Directory does not exist, skipping cleanup: {path}")
        return

    # Security: Validate path
    _validate_path_safety(path)

    if keep_files is None:
        keep_files = set()

    try:
        for item in path.iterdir():
            if item.name not in keep_files:
                if item.is_file():
                    item.unlink()
                    logger.debug(f"Removed file: {item}")
                elif item.is_dir():
                    shutil.rmtree(item)
                    logger.debug(f"Removed directory: {item}")

        logger.info(f"Directory cleaned up: {path}")
    except OSError as exc:
        logger.error(f"Failed to clean up directory {path}: {exc}")
        raise


def safe_copy_file(
    src: str | Path,
    dst: str | Path,
    overwrite: bool = False
) -> Path:
    """
    Safely copy a file with validation.

    Args:
        src: Source file path
        dst: Destination file path
        overwrite: Whether to overwrite existing files

    Returns:
        Path to destination file

    Raises:
        OSError: If copy fails
        ValueError: If paths are invalid
    """
    src = Path(src)
    dst = Path(dst)

    # Security: Validate paths
    _validate_path_safety(src)
    _validate_path_safety(dst)

    if not src.exists():
        raise ValueError(f"Source file does not exist: {src}")

    if dst.exists() and not overwrite:
        raise ValueError(f"Destination file exists and overwrite=False: {dst}")

    # Ensure destination directory exists
    ensure_directory(dst.parent)

    try:
        shutil.copy2(src, dst)
        logger.debug(f"File copied: {src} -> {dst}")
        return dst
    except OSError as exc:
        logger.error(f"Failed to copy file {src} to {dst}: {exc}")
        raise


def safe_move_file(
    src: str | Path,
    dst: str | Path,
    overwrite: bool = False
) -> Path:
    """
    Safely move a file with validation.

    Args:
        src: Source file path
        dst: Destination file path
        overwrite: Whether to overwrite existing files

    Returns:
        Path to destination file

    Raises:
        OSError: If move fails
        ValueError: If paths are invalid
    """
    src = Path(src)
    dst = Path(dst)

    # Security: Validate paths
    _validate_path_safety(src)
    _validate_path_safety(dst)

    if not src.exists():
        raise ValueError(f"Source file does not exist: {src}")

    if dst.exists() and not overwrite:
        raise ValueError(f"Destination file exists and overwrite=False: {dst}")

    # Ensure destination directory exists
    ensure_directory(dst.parent)

    try:
        shutil.move(str(src), str(dst))
        logger.debug(f"File moved: {src} -> {dst}")
        return dst
    except OSError as exc:
        logger.error(f"Failed to move file {src} to {dst}: {exc}")
        raise


def get_file_info(path: str | Path) -> dict:
    """
    Get file information safely.

    Args:
        path: File path

    Returns:
        Dictionary with file information

    Raises:
        OSError: If file access fails
        ValueError: If path is invalid
    """
    path = Path(path)

    # Security: Validate path
    _validate_path_safety(path)

    if not path.exists():
        raise ValueError(f"File does not exist: {path}")

    try:
        stat = path.stat()
        return {
            "path": str(path),
            "name": path.name,
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "is_file": path.is_file(),
            "is_dir": path.is_dir(),
            "extension": path.suffix,
            "stem": path.stem
        }
    except OSError as exc:
        logger.error(f"Failed to get file info for {path}: {exc}")
        raise


def find_files(
    directory: str | Path,
    pattern: str = "*",
    recursive: bool = True
) -> list[Path]:
    """
    Find files matching pattern in directory.

    Args:
        directory: Directory to search
        pattern: File pattern to match
        recursive: Whether to search recursively

    Returns:
        List of matching file paths

    Raises:
        OSError: If directory access fails
        ValueError: If directory is invalid
    """
    directory = Path(directory)

    # Security: Validate path
    _validate_path_safety(directory)

    if not directory.exists():
        raise ValueError(f"Directory does not exist: {directory}")

    if not directory.is_dir():
        raise ValueError(f"Path is not a directory: {directory}")

    try:
        files = list(directory.rglob(pattern)) if recursive else list(directory.glob(pattern))

        # Filter out directories
        files = [f for f in files if f.is_file()]

        logger.debug(f"Found {len(files)} files matching '{pattern}' in {directory}")
        return files
    except OSError as exc:
        logger.error(f"Failed to find files in {directory}: {exc}")
        raise


def create_temp_directory(prefix: str = "temp_") -> Path:
    """
    Create a temporary directory safely.

    Args:
        prefix: Prefix for temporary directory name

    Returns:
        Path to temporary directory
    """
    try:
        temp_dir = Path(tempfile.mkdtemp(prefix=prefix))
        logger.debug(f"Created temporary directory: {temp_dir}")
        return temp_dir
    except OSError as exc:
        logger.error(f"Failed to create temporary directory: {exc}")
        raise


def _validate_path_safety(path: Path) -> None:
    """
    Validate path for security issues.

    Args:
        path: Path to validate

    Raises:
        ValueError: If path is unsafe
    """
    # Convert to absolute path for validation
    try:
        abs_path = path.resolve()
    except OSError:
        raise ValueError(f"Invalid path: {path}")

    # Check for path traversal attempts
    if ".." in str(path):
        raise ValueError(f"Path traversal detected: {path}")

    # Check for dangerous patterns
    dangerous_patterns = ["/etc/", "/sys/", "/proc/", "/dev/", "/root/"]
    path_str = str(abs_path).lower()

    for pattern in dangerous_patterns:
        if pattern in path_str:
            raise ValueError(f"Access to system directory not allowed: {path}")

    # Additional security checks can be added here
    logger.debug(f"Path validated as safe: {path}")
