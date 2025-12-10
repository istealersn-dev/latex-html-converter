#!/usr/bin/env python3
"""
File length checker to enforce maximum line limits.
"""

import os
import sys
from pathlib import Path


def check_file_lengths(max_lines: int = 500, extensions: tuple = (".py",)) -> bool:
    """
    Check if any files exceed the maximum line limit.

    Args:
        max_lines: Maximum number of lines allowed per file
        extensions: File extensions to check

    Returns:
        True if all files are within limits, False otherwise
    """
    violations = []

    # Check all Python files in the project
    for root, dirs, files in os.walk("."):
        # Skip hidden directories and common ignore patterns
        dirs[:] = [
            d
            for d in dirs
            if not d.startswith(".") and d not in ["__pycache__", "node_modules"]
        ]

        for file in files:
            if file.endswith(extensions):
                file_path = Path(root) / file
                try:
                    with open(file_path, encoding="utf-8") as f:
                        line_count = sum(1 for _ in f)

                    if line_count > max_lines:
                        violations.append(
                            f"{file_path}: {line_count} lines (limit: {max_lines})"
                        )
                except (UnicodeDecodeError, PermissionError):
                    # Skip binary files or files we can't read
                    continue

    if violations:
        print("File length violations found:", file=sys.stderr)
        for violation in violations:
            print(f"  {violation}", file=sys.stderr)
        return False
    else:
        return True


if __name__ == "__main__":
    max_lines = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    success = check_file_lengths(max_lines)
    sys.exit(0 if success else 1)
