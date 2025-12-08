#!/usr/bin/env python3
"""
Test script to run LaTeX to HTML conversion directly.

This script bypasses the API server and runs the conversion pipeline directly.
"""

import sys
import time
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.orchestrator import get_orchestrator
from app.api.conversion import _extract_archive, _find_main_tex_file
from app.models.conversion import ConversionOptions
from loguru import logger

def main():
    """Run conversion test."""
    # Setup paths
    project_root = Path(__file__).parent
    uploads_dir = project_root / "uploads"
    outputs_dir = project_root / "outputs"
    
    # Ensure output directory exists
    outputs_dir.mkdir(exist_ok=True)
    
    # Find the test file
    test_file = uploads_dir / "geo-2025-1177 1.zip"
    
    if not test_file.exists():
        logger.error(f"Test file not found: {test_file}")
        return 1
    
    logger.info(f"Found test file: {test_file}")
    logger.info(f"File size: {test_file.stat().st_size / 1024 / 1024:.2f} MB")
    
    # Create job directories
    import uuid
    job_id = str(uuid.uuid4())
    job_upload_dir = uploads_dir / job_id
    job_output_dir = outputs_dir / f"geo-2025-1177_{job_id}"
    
    job_upload_dir.mkdir(exist_ok=True)
    job_output_dir.mkdir(exist_ok=True)
    
    try:
        # Copy file to job directory
        input_file = job_upload_dir / test_file.name
        import shutil
        shutil.copy2(test_file, input_file)
        logger.info(f"Copied file to: {input_file}")
        
        # Extract archive
        logger.info("Extracting archive...")
        extracted_dir = _extract_archive(input_file, job_upload_dir)
        logger.info(f"Extracted to: {extracted_dir}")
        
        # Find main LaTeX file
        logger.info("Finding main LaTeX file...")
        main_tex_file = _find_main_tex_file(extracted_dir)
        if not main_tex_file:
            logger.error("No main LaTeX file found in archive")
            return 1
        
        logger.info(f"Found main LaTeX file: {main_tex_file}")
        
        # Get orchestrator
        logger.info("Initializing orchestrator...")
        orchestrator = get_orchestrator()
        
        # Start conversion
        logger.info(f"Starting conversion: {main_tex_file} -> {job_output_dir}")
        conversion_job_id = orchestrator.start_conversion(
            input_file=main_tex_file,
            output_dir=job_output_dir,
            options=None,
            job_id=job_id
        )
        
        logger.info(f"Conversion job started: {conversion_job_id}")
        
        # Wait for completion
        logger.info("Waiting for conversion to complete...")
        max_wait_time = 600  # 10 minutes
        start_time = time.time()
        check_interval = 2  # Check every 2 seconds
        
        while True:
            elapsed = time.time() - start_time
            if elapsed > max_wait_time:
                logger.error(f"Conversion timed out after {max_wait_time} seconds")
                return 1
            
            status = orchestrator.get_job_status(conversion_job_id)
            progress = orchestrator.get_job_progress(conversion_job_id)
            
            if progress:
                logger.info(f"Status: {status.value}, Progress: {progress.progress_percentage:.1f}% - {progress.message}")
            else:
                logger.info(f"Status: {status.value if status else 'Unknown'}")
            
            if status and status.value in ['COMPLETED', 'FAILED', 'CANCELLED']:
                break
            
            time.sleep(check_interval)
        
        # Get result
        result = orchestrator.get_job_result(conversion_job_id)
        
        if status.value == 'COMPLETED' and result:
            logger.info("✓ Conversion completed successfully!")
            logger.info(f"Output directory: {job_output_dir}")
            
            # List output files
            logger.info("\nOutput files:")
            for file in sorted(job_output_dir.rglob("*")):
                if file.is_file():
                    size = file.stat().st_size
                    rel_path = file.relative_to(job_output_dir)
                    logger.info(f"  {rel_path} ({size:,} bytes)")
            
            # Check for HTML file
            html_files = list(job_output_dir.rglob("*.html"))
            if html_files:
                logger.info(f"\n✓ Found {len(html_files)} HTML file(s):")
                for html_file in html_files:
                    logger.info(f"  {html_file.relative_to(job_output_dir)}")
            else:
                logger.warning("⚠ No HTML files found in output")
            
            return 0
        else:
            logger.error(f"✗ Conversion failed: {status.value}")
            if result and result.errors:
                for error in result.errors:
                    logger.error(f"  Error: {error}")
            return 1
            
    except Exception as exc:
        logger.exception(f"Conversion failed with exception: {exc}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
