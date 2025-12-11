"""
SVG utility functions for optimization and processing.

This module provides shared utilities for SVG file optimization
and processing across different services.
"""

from pathlib import Path
from typing import Any

from loguru import logger


def optimize_svg(svg_file: Path, options: dict[str, Any]) -> Path:
    """
    Optimize the SVG file using the SVGOptimizer service.

    Args:
        svg_file: Path to SVG file to optimize
        options: Optimization options

    Returns:
        Path to optimized SVG file
    """
    try:
        # Import here to avoid circular imports
        from app.services.svg_optimizer import SVGOptimizer

        # Initialize optimizer
        optimizer = SVGOptimizer()

        # Create output file path (in-place optimization by default)
        output_file = options.get("output_file")
        if output_file is None:
            # Optimize in-place by overwriting the original
            output_file = svg_file

        # Perform optimization
        logger.debug(f"Optimizing SVG: {svg_file}")
        result = optimizer.optimize_svg(svg_file, output_file, options)

        if result.get("success"):
            logger.debug(
                f"SVG optimization successful: "
                f"{result.get('size_reduction_percent', 0):.1f}% size reduction"
            )
            return Path(result["optimized_file"])
        else:
            logger.warning(f"SVG optimization failed, returning original: {svg_file}")
            return svg_file

    except Exception as exc:
        logger.warning(f"SVG optimization failed: {exc}, returning original file")
        return svg_file


def calculate_optimization_ratio(original_file: Path, optimized_file: Path) -> float:
    """
    Calculate the optimization ratio.

    Args:
        original_file: Path to original file
        optimized_file: Path to optimized file

    Returns:
        Optimization ratio (0.0 to 1.0)
    """
    try:
        original_size = original_file.stat().st_size
        optimized_size = optimized_file.stat().st_size

        if original_size == 0:
            return 1.0

        return optimized_size / original_size

    except Exception:
        return 1.0
