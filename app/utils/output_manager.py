"""
Output management utilities for copying conversion results to mounted directories.
"""

import shutil
from pathlib import Path
from typing import Any, Dict

from loguru import logger


def copy_conversion_results_to_output(
    temp_output_dir: Path,
    mounted_output_dir: Path,
    job_id: str
) -> Dict[str, Any]:
    """
    Copy conversion results from temporary directory to mounted output directory.
    
    Args:
        temp_output_dir: Temporary directory containing conversion results
        mounted_output_dir: Mounted output directory accessible from host
        job_id: Conversion job ID for organizing files
        
    Returns:
        Dict containing paths to copied files and metadata
    """
    try:
        # Create job-specific directory in mounted output
        job_output_dir = mounted_output_dir / job_id
        job_output_dir.mkdir(parents=True, exist_ok=True)
        
        copied_files = []
        
        # Copy all files from temp output directory
        if temp_output_dir.exists():
            for item in temp_output_dir.rglob("*"):
                if item.is_file():
                    # Calculate relative path from temp_output_dir
                    rel_path = item.relative_to(temp_output_dir)
                    dest_path = job_output_dir / rel_path
                    
                    # Create parent directories if needed
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Copy file
                    shutil.copy2(item, dest_path)
                    copied_files.append(str(dest_path))
                    
                    logger.debug(f"Copied {item} -> {dest_path}")
        
        # Find the main HTML file
        html_files = list(job_output_dir.rglob("*.html"))
        main_html_file = None
        if html_files:
            # Prefer final.html, otherwise use the first HTML file
            final_html = job_output_dir / "final.html"
            if final_html.exists():
                main_html_file = str(final_html)
            else:
                main_html_file = str(html_files[0])
        
        # Find SVG assets
        svg_files = list(job_output_dir.rglob("*.svg"))
        assets = [str(f) for f in svg_files]
        
        result = {
            "success": True,
            "job_output_dir": str(job_output_dir),
            "html_file": main_html_file,
            "assets": assets,
            "copied_files": copied_files,
            "total_files": len(copied_files)
        }
        
        logger.info(f"Copied {len(copied_files)} files to mounted output directory: {job_output_dir}")
        return result
        
    except Exception as exc:
        logger.error(f"Failed to copy conversion results: {exc}")
        return {
            "success": False,
            "error": str(exc),
            "job_output_dir": str(job_output_dir),
            "html_file": None,
            "assets": [],
            "copied_files": [],
            "total_files": 0
        }


def get_conversion_output_path(job_id: str, mounted_output_dir: Path) -> Path:
    """
    Get the output path for a specific conversion job.
    
    Args:
        job_id: Conversion job ID
        mounted_output_dir: Mounted output directory
        
    Returns:
        Path to the job's output directory
    """
    return mounted_output_dir / job_id
