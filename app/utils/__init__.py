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

__all__ = [
    "run_command_safely", "run_command_with_retry", "check_command_available",
    "get_command_version", "CommandResult",
    "ensure_directory", "cleanup_directory", "safe_copy_file", "safe_move_file",
    "get_file_info", "find_files", "create_temp_directory"
]
