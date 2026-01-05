"""
Utilities package for the LaTeX → HTML5 Converter.

This package contains utility modules for common operations.
"""

from .fs import (
    cleanup_directory,
    create_temp_directory,
    ensure_directory,
    find_files,
    get_file_info,
    safe_copy_file,
    safe_move_file,
)
from .shell import (
    CommandResult,
    check_command_available,
    get_command_version,
    run_command_safely,
    run_command_with_retry,
)
from .svg_utils import (
    calculate_optimization_ratio,
    optimize_svg,
)
from .validation import ValidationUtils
from .path_utils import (
    PathCycleError,
    PathDepthError,
    discover_directories_recursive,
    find_files_bfs,
    get_path_depth,
    normalize_path,
    normalize_path_for_os,
    validate_path_depth,
)
from .path_cache import PathCache, cache_directory_listing, get_path_cache

__all__ = [
    "run_command_safely",
    "run_command_with_retry",
    "check_command_available",
    "get_command_version",
    "CommandResult",
    "ensure_directory",
    "cleanup_directory",
    "safe_copy_file",
    "safe_move_file",
    "get_file_info",
    "find_files",
    "create_temp_directory",
    "optimize_svg",
    "calculate_optimization_ratio",
    "ValidationUtils",
    # Path utilities
    "find_files_bfs",
    "discover_directories_recursive",
    "normalize_path",
    "normalize_path_for_os",
    "validate_path_depth",
    "get_path_depth",
    "PathDepthError",
    "PathCycleError",
    # Path caching
    "PathCache",
    "get_path_cache",
    "cache_directory_listing",
]
