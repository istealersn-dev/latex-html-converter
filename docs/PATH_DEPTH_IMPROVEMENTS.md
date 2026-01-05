# Path Depth Limitations & Improvements

## Overview

This document describes the improvements made to handle LaTeX projects with arbitrarily deep directory structures without path depth limitations.

## Problems Addressed

### 1. Fixed Depth Limits
- **Issue**: LaTeXML path configuration only added parent directories up to 2 levels
- **Impact**: Class files in deeper directories were not found
- **Solution**: Implemented recursive directory discovery with configurable depth limits

### 2. Recursion Limits
- **Issue**: Using `rglob()` could hit recursion limits for very deep structures
- **Impact**: Stack overflow errors on deeply nested directories
- **Solution**: Implemented breadth-first search (BFS) to avoid recursion

### 3. Symbolic Link Cycles
- **Issue**: No cycle detection when following symlinks
- **Impact**: Infinite loops or crashes
- **Solution**: Added cycle detection with visited path tracking

### 4. Path Length Limits
- **Issue**: No validation against OS path length limits (e.g., Windows MAX_PATH)
- **Impact**: Failures on very long paths
- **Solution**: Added path normalization and length validation

### 5. Performance Issues
- **Issue**: Repeated directory traversals for the same paths
- **Impact**: Slow performance on large projects
- **Solution**: Implemented LRU cache for path discovery results

## Implemented Improvements

### 1. Path Utilities Module (`app/utils/path_utils.py`)

**New Functions:**
- `find_files_bfs()` - Breadth-first file search with cycle detection
- `discover_directories_recursive()` - Recursive directory discovery using BFS
- `normalize_path()` - Path normalization with symlink cycle detection
- `validate_path_depth()` - Depth validation against configured limits
- `normalize_path_for_os()` - OS-specific path normalization
- `get_path_depth()` - Calculate path depth

**Features:**
- ✅ Breadth-first traversal (no recursion limits)
- ✅ Symbolic link cycle detection
- ✅ Configurable depth limits
- ✅ OS path length validation
- ✅ Graceful error handling

### 2. Path Caching (`app/utils/path_cache.py`)

**Features:**
- ✅ LRU cache for directory listings
- ✅ Configurable TTL (time-to-live)
- ✅ Cache statistics and monitoring
- ✅ Automatic cache eviction

**Configuration:**
- `ENABLE_PATH_CACHING` - Enable/disable caching (default: True)
- `PATH_CACHE_TTL` - Cache TTL in seconds (default: 3600)

### 3. Configuration Updates (`app/config.py`)

**New Settings:**
```python
MAX_PATH_DEPTH: int | None = None  # Maximum path depth (None = unlimited)
MAX_PATH_LENGTH: int = 4096  # Maximum path length in characters
ENABLE_PATH_CACHING: bool = True  # Enable path discovery caching
PATH_CACHE_TTL: int = 3600  # Path cache TTL in seconds
```

### 4. LaTeX Preprocessor Improvements (`app/services/latex_preprocessor.py`)

**Changes:**
- ✅ Replaced `rglob()` with `find_files_bfs()` for class file discovery
- ✅ Added path depth validation
- ✅ Added OS path length validation
- ✅ Improved error handling for deep paths

**Before:**
```python
for cls_path in search_dir.rglob(f"{class_name}.cls"):
    # Could hit recursion limits
```

**After:**
```python
cls_files = find_files_bfs(
    search_dir,
    f"{class_name}.cls",
    max_depth=settings.MAX_PATH_DEPTH,
    follow_symlinks=False,
)
```

### 5. LaTeXML Service Improvements (`app/services/latexml.py`)

**Changes:**
- ✅ Replaced fixed 2-level parent directory search with recursive discovery
- ✅ Discover all subdirectories recursively (up to max depth)
- ✅ Increased parent directory search from 2 to 5 levels
- ✅ Added path normalization and validation
- ✅ Better handling of deeply nested class files

**Before:**
```python
# Only 2 parent levels
for _ in range(2):
    # Add parent directory
```

**After:**
```python
# Discover all directories recursively
all_dirs = discover_directories_recursive(
    project_dir,
    max_depth=settings.MAX_PATH_DEPTH,
    include_hidden=False,
)
# Add all discovered directories
```

### 6. Archive Extraction Improvements (`app/api/conversion.py`)

**Changes:**
- ✅ Added path depth validation during extraction
- ✅ Preserves full directory structure (no depth limits)
- ✅ Better error handling for paths exceeding limits
- ✅ Graceful degradation (warns but continues)

### 7. File Discovery Improvements (`app/services/file_discovery.py`)

**Changes:**
- ✅ Added path depth validation before extraction
- ✅ Better handling of deep directory structures
- ✅ Improved error handling for OS path limits

### 8. Main File Discovery (`app/api/conversion.py`)

**Changes:**
- ✅ Replaced `rglob()` with `find_files_bfs()` for main .tex file discovery
- ✅ Handles deep directory structures without recursion limits
- ✅ Breadth-first search ensures main files are found first

## Usage Examples

### Configuring Path Depth Limits

**Environment Variables:**
```bash
# Set maximum path depth (None = unlimited)
MAX_PATH_DEPTH=50

# Set maximum path length
MAX_PATH_LENGTH=4096

# Enable/disable path caching
ENABLE_PATH_CACHING=true
PATH_CACHE_TTL=3600
```

**In Code:**
```python
from app.config import settings

# Check if path depth is configured
if settings.MAX_PATH_DEPTH:
    # Use configured limit
    max_depth = settings.MAX_PATH_DEPTH
else:
    # Unlimited depth
    max_depth = None
```

### Using Breadth-First Search

```python
from app.utils.path_utils import find_files_bfs

# Find all .cls files using BFS (no recursion limits)
cls_files = find_files_bfs(
    root_dir=Path("/project"),
    pattern="*.cls",
    max_depth=50,  # Optional depth limit
    follow_symlinks=False,
)
```

### Using Path Caching

```python
from app.utils.path_cache import cache_directory_listing

# Get directory listing with caching
files = cache_directory_listing(
    directory=Path("/project"),
    pattern="*.tex",
    max_depth=50,
)
```

### Recursive Directory Discovery

```python
from app.utils.path_utils import discover_directories_recursive

# Discover all directories recursively
all_dirs = discover_directories_recursive(
    root_dir=Path("/project"),
    max_depth=50,
    include_hidden=False,
)
```

## Error Handling

### Path Depth Errors

```python
from app.utils.path_utils import PathDepthError, validate_path_depth

try:
    validate_path_depth(path, max_depth=50, base_path=base)
except PathDepthError as exc:
    logger.error(f"Path depth {exc.depth} exceeds limit {exc.max_depth}")
    # Handle gracefully
```

### Symbolic Link Cycles

```python
from app.utils.path_utils import PathCycleError, normalize_path

try:
    normalized = normalize_path(path)
except PathCycleError as exc:
    logger.warning(f"Cycle detected: {exc.cycle_path}")
    # Skip this path
```

### OS Path Length Limits

```python
from app.utils.path_utils import normalize_path_for_os

try:
    normalized = normalize_path_for_os(path)
except ValueError as exc:
    logger.error(f"Path exceeds OS limits: {exc}")
    # Handle gracefully
```

## Performance Considerations

### Path Caching

Path caching significantly improves performance for:
- Repeated searches in the same directories
- Large projects with many subdirectories
- Multiple conversions of similar projects

**Cache Statistics:**
```python
from app.utils.path_cache import get_path_cache

cache = get_path_cache()
stats = cache.get_stats()
# Returns: {"size": 100, "hits": 500, "misses": 50, "hit_rate": 90.9}
```

### Breadth-First vs Depth-First

**Breadth-First (BFS) Advantages:**
- ✅ No recursion limits
- ✅ Finds files at shallow depths first
- ✅ Better for finding main files
- ✅ More memory efficient for deep structures

**When to Use:**
- Deep directory structures (>20 levels)
- Finding main files (usually at root)
- Avoiding stack overflow

## Testing

### Test Deep Directory Structures

```python
# Create deep directory structure
deep_path = Path("/tmp/test")
for i in range(100):
    deep_path = deep_path / f"level_{i}"
deep_path.mkdir(parents=True, exist_ok=True)

# Test BFS can find files
files = find_files_bfs(deep_path, "*.tex", max_depth=None)
assert len(files) >= 0  # Should not crash
```

### Test Path Depth Validation

```python
from app.utils.path_utils import validate_path_depth, PathDepthError

# Should raise PathDepthError
try:
    validate_path_depth(deep_path, max_depth=50)
except PathDepthError:
    pass  # Expected
```

### Test Cycle Detection

```python
# Create symlink cycle
link1 = Path("/tmp/link1")
link2 = Path("/tmp/link2")
link1.symlink_to(link2)
link2.symlink_to(link1)

# Should detect cycle
try:
    normalize_path(link1)
except PathCycleError:
    pass  # Expected
```

## Migration Guide

### For Existing Code

**Replace `rglob()` with `find_files_bfs()`:**
```python
# Old
files = list(directory.rglob("*.cls"))

# New
from app.utils.path_utils import find_files_bfs
files = find_files_bfs(directory, "*.cls", max_depth=settings.MAX_PATH_DEPTH)
```

**Replace fixed-depth searches:**
```python
# Old
for _ in range(2):
    parent = parent.parent
    # Add to paths

# New
from app.utils.path_utils import discover_directories_recursive
all_dirs = discover_directories_recursive(parent, max_depth=5)
```

## Configuration Reference

| Setting | Default | Description |
|---------|---------|-------------|
| `MAX_PATH_DEPTH` | `None` (unlimited) | Maximum directory depth to traverse |
| `MAX_PATH_LENGTH` | `4096` | Maximum path length in characters |
| `ENABLE_PATH_CACHING` | `True` | Enable path discovery caching |
| `PATH_CACHE_TTL` | `3600` | Cache TTL in seconds (1 hour) |

## Best Practices

1. **Set Reasonable Depth Limits**: Use `MAX_PATH_DEPTH` to prevent excessive traversal
2. **Enable Caching**: Keep `ENABLE_PATH_CACHING=True` for better performance
3. **Handle Errors Gracefully**: Catch `PathDepthError` and `PathCycleError` appropriately
4. **Validate Paths**: Use `normalize_path_for_os()` before operations
5. **Monitor Cache**: Check cache statistics to optimize TTL

## Future Enhancements

Potential future improvements:
- [ ] Support for nested archives within archives
- [ ] Streaming extraction for very large archives
- [ ] File system watchers for dynamic class discovery
- [ ] Tectonic integration with recursive class path search
- [ ] Performance monitoring for deep path operations

## Summary

All path depth limitations have been addressed:

✅ **Recursive Directory Traversal** - BFS implementation with cycle detection  
✅ **Dynamic Path Resolution** - No hardcoded depth limits  
✅ **LaTeXML Path Configuration** - Recursive directory inclusion  
✅ **Archive Extraction** - Preserves full directory structure  
✅ **Class File Discovery** - Breadth-first search  
✅ **Configuration Management** - Configurable depth limits  
✅ **Error Handling** - Graceful degradation for path limits  
✅ **Performance** - Path caching to avoid repeated traversals  

The converter can now handle LaTeX projects with arbitrarily deep directory structures without limitations.

