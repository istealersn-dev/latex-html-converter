"""
Path utilities for handling deep directory structures and path resolution.

This module provides utilities for:
- Breadth-first directory traversal
- Symbolic link cycle detection
- Path normalization and validation
- Recursive path discovery
- Path depth management
"""

import os
from collections import deque
from pathlib import Path
from typing import Any

from loguru import logger


class PathDepthError(Exception):
    """Raised when path depth exceeds configured limits."""

    def __init__(self, path: Path, depth: int, max_depth: int):
        self.path = path
        self.depth = depth
        self.max_depth = max_depth
        super().__init__(
            f"Path depth {depth} exceeds maximum {max_depth}: {path}"
        )


class PathCycleError(Exception):
    """Raised when a symbolic link cycle is detected."""

    def __init__(self, path: Path, cycle_path: list[Path]):
        self.path = path
        self.cycle_path = cycle_path
        super().__init__(
            f"Symbolic link cycle detected at {path}: {' -> '.join(str(p) for p in cycle_path)}"
        )


def normalize_path(path: Path, base_path: Path | None = None) -> Path:
    """
    Normalize a path, resolving symlinks and relative paths.
    
    Args:
        path: Path to normalize
        base_path: Base path for resolving relative paths
        
    Returns:
        Normalized absolute path
        
    Raises:
        PathDepthError: If path depth exceeds limits
        PathCycleError: If symbolic link cycle detected
    """
    try:
        if base_path and not path.is_absolute():
            path = base_path / path
        
        # Resolve symlinks with cycle detection
        resolved = _resolve_path_with_cycle_detection(path)
        
        return resolved.resolve()
    except (OSError, ValueError) as exc:
        logger.warning(f"Failed to normalize path {path}: {exc}")
        return path.resolve() if path.is_absolute() else path


def _resolve_path_with_cycle_detection(path: Path) -> Path:
    """
    Resolve path with symbolic link cycle detection.
    
    Args:
        path: Path to resolve
        
    Returns:
        Resolved path
        
    Raises:
        PathCycleError: If cycle detected
    """
    visited = set()
    current = path.resolve() if path.is_absolute() else path
    
    while current.is_symlink():
        target = current.readlink()
        
        # Check for cycle
        if current in visited:
            cycle = list(visited) + [current]
            raise PathCycleError(current, cycle)
        
        visited.add(current)
        
        if target.is_absolute():
            current = target
        else:
            current = current.parent / target
    
    return current


def find_files_bfs(
    root_dir: Path,
    pattern: str,
    max_depth: int | None = None,
    follow_symlinks: bool = False,
) -> list[Path]:
    """
    Find files using breadth-first search to avoid recursion limits.
    
    Args:
        root_dir: Root directory to search
        pattern: File pattern to match (e.g., "*.cls", "*.tex")
        max_depth: Maximum depth to search (None = unlimited)
        follow_symlinks: Whether to follow symbolic links
        
    Returns:
        List of matching file paths
        
    Raises:
        PathDepthError: If max_depth exceeded
    """
    if not root_dir.exists() or not root_dir.is_dir():
        return []
    
    matches = []
    queue = deque([(root_dir, 0)])  # (path, depth)
    visited_dirs = set()
    
    # Normalize root for cycle detection
    try:
        root_normalized = normalize_path(root_dir)
        visited_dirs.add(root_normalized)
    except (PathCycleError, PathDepthError):
        logger.warning(f"Could not normalize root directory: {root_dir}")
        visited_dirs.add(root_dir.resolve())
    
    while queue:
        current_dir, depth = queue.popleft()
        
        # Check depth limit
        if max_depth is not None and depth > max_depth:
            continue
        
        try:
            # Get directory entries
            entries = list(current_dir.iterdir())
            
            # Process files first (breadth-first)
            for entry in entries:
                if entry.is_file():
                    if entry.match(pattern):
                        matches.append(entry)
                elif entry.is_dir():
                    # Check if we should follow this directory
                    if entry.is_symlink() and not follow_symlinks:
                        continue
                    
                    # Cycle detection for symlinks
                    try:
                        normalized = normalize_path(entry, current_dir)
                        if normalized in visited_dirs:
                            logger.debug(f"Skipping already visited directory: {entry}")
                            continue
                        visited_dirs.add(normalized)
                    except PathCycleError as exc:
                        logger.warning(f"Skipping directory with cycle: {exc}")
                        continue
                    except (OSError, ValueError):
                        # If normalization fails, use original path
                        if entry.resolve() in visited_dirs:
                            continue
                        visited_dirs.add(entry.resolve())
                    
                    # Add to queue for next level
                    queue.append((entry, depth + 1))
        
        except (OSError, PermissionError) as exc:
            logger.debug(f"Cannot access directory {current_dir}: {exc}")
            continue
    
    return matches


def discover_directories_recursive(
    root_dir: Path,
    max_depth: int | None = None,
    include_hidden: bool = False,
) -> list[Path]:
    """
    Discover all directories recursively using breadth-first search.
    
    Args:
        root_dir: Root directory to search
        max_depth: Maximum depth to search (None = unlimited)
        include_hidden: Whether to include hidden directories
        
    Returns:
        List of discovered directory paths
    """
    if not root_dir.exists() or not root_dir.is_dir():
        return []
    
    directories = [root_dir]
    queue = deque([(root_dir, 0)])  # (path, depth)
    visited = set()
    visited.add(root_dir.resolve())
    
    while queue:
        current_dir, depth = queue.popleft()
        
        # Check depth limit
        if max_depth is not None and depth >= max_depth:
            continue
        
        try:
            for entry in current_dir.iterdir():
                # Skip hidden directories if not including them
                if not include_hidden and entry.name.startswith("."):
                    continue
                
                if entry.is_dir():
                    # Resolve symlinks
                    try:
                        resolved = normalize_path(entry, current_dir)
                        if resolved in visited:
                            continue
                        visited.add(resolved)
                    except (PathCycleError, OSError, ValueError):
                        # Skip if we can't resolve or cycle detected
                        continue
                    
                    directories.append(entry)
                    queue.append((entry, depth + 1))
        
        except (OSError, PermissionError) as exc:
            logger.debug(f"Cannot access directory {current_dir}: {exc}")
            continue
    
    return directories


def get_path_depth(path: Path, base_path: Path | None = None) -> int:
    """
    Calculate the depth of a path relative to a base path.
    
    Args:
        path: Path to measure
        base_path: Base path (defaults to path root)
        
    Returns:
        Depth of the path
    """
    try:
        if base_path:
            try:
                relative = path.relative_to(base_path)
                return len(relative.parts)
            except ValueError:
                # Path is not relative to base, calculate from root
                return len(path.parts)
        else:
            # Calculate depth from filesystem root
            resolved = path.resolve()
            return len([p for p in resolved.parts if p])
    except Exception:
        # Fallback: count path components
        return len(path.parts)


def validate_path_depth(
    path: Path,
    max_depth: int | None = None,
    base_path: Path | None = None,
) -> None:
    """
    Validate that a path doesn't exceed maximum depth.
    
    Args:
        path: Path to validate
        max_depth: Maximum allowed depth (None = no limit)
        base_path: Base path for relative depth calculation
        
    Raises:
        PathDepthError: If depth exceeds limit
    """
    if max_depth is None:
        return
    
    depth = get_path_depth(path, base_path)
    if depth > max_depth:
        raise PathDepthError(path, depth, max_depth)


def normalize_path_for_os(path: Path) -> Path:
    """
    Normalize path according to OS limits (e.g., Windows MAX_PATH).
    
    Args:
        path: Path to normalize
        
    Returns:
        Normalized path
        
    Raises:
        ValueError: If path exceeds OS limits
    """
    # Windows MAX_PATH is 260 characters, but can be extended with \\?\
    # Linux/POSIX typically allows much longer paths
    max_path_length = 4096  # Conservative limit for most systems
    
    resolved = path.resolve()
    path_str = str(resolved)
    
    if len(path_str) > max_path_length:
        raise ValueError(
            f"Path length {len(path_str)} exceeds maximum {max_path_length}: {path_str[:100]}..."
        )
    
    return resolved

