"""
Path discovery cache to avoid repeated directory traversals.

This module provides caching for path discovery operations to improve
performance when dealing with large directory structures.
"""

import time
from collections import OrderedDict
from pathlib import Path
from typing import Any

from loguru import logger

from app.config import settings


class PathCache:
    """
    LRU cache for path discovery results.
    
    Caches directory listings and file discovery results to avoid
    repeated filesystem traversals.
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        ttl: int | None = None,
    ):
        """
        Initialize path cache.
        
        Args:
            max_size: Maximum number of entries (LRU eviction)
            ttl: Time-to-live in seconds (None = use settings default)
        """
        self.max_size = max_size
        self.ttl = ttl or settings.PATH_CACHE_TTL
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Any | None:
        """
        Get cached value.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        if not settings.ENABLE_PATH_CACHING:
            return None
        
        if key not in self._cache:
            self._misses += 1
            return None
        
        value, timestamp = self._cache[key]
        
        # Check TTL
        if time.time() - timestamp > self.ttl:
            # Expired, remove from cache
            del self._cache[key]
            self._misses += 1
            return None
        
        # Move to end (most recently used)
        self._cache.move_to_end(key)
        self._hits += 1
        return value
    
    def set(self, key: str, value: Any) -> None:
        """
        Set cached value.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        if not settings.ENABLE_PATH_CACHING:
            return
        
        # Remove if exists (will be re-added at end)
        if key in self._cache:
            del self._cache[key]
        
        # Add new entry
        self._cache[key] = (value, time.time())
        
        # Evict oldest if over limit
        if len(self._cache) > self.max_size:
            self._cache.popitem(last=False)  # Remove oldest
    
    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
    
    def get_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0.0
        
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "ttl": self.ttl,
        }


# Global path cache instance
_path_cache = PathCache()


def get_path_cache() -> PathCache:
    """
    Get global path cache instance.
    
    Returns:
        PathCache: Global cache instance
    """
    return _path_cache


def cache_directory_listing(
    directory: Path,
    pattern: str = "*",
    max_depth: int | None = None,
) -> list[Path]:
    """
    Get directory listing with caching.
    
    Args:
        directory: Directory to list
        pattern: File pattern to match
        max_depth: Maximum depth
        
    Returns:
        List of matching paths
    """
    from app.utils.path_utils import find_files_bfs
    
    cache = get_path_cache()
    cache_key = f"dir_listing:{directory}:{pattern}:{max_depth}"
    
    # Try cache first
    cached = cache.get(cache_key)
    if cached is not None:
        logger.debug(f"Cache hit for directory listing: {directory}")
        return cached
    
    # Cache miss - discover files
    files = find_files_bfs(directory, pattern, max_depth=max_depth)
    
    # Cache result
    cache.set(cache_key, files)
    
    return files

