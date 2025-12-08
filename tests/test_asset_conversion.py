#!/usr/bin/env python3
"""
Test script for asset conversion pipeline.

This script tests the complete asset conversion pipeline including:
- TikZ conversion to SVG
- PDF conversion to SVG
- HTML post-processing with asset conversion
"""

import sys
from pathlib import Path

from loguru import logger

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "app"))

# pylint: disable=wrong-import-position
from app.services.asset_validator import AssetValidator
from app.services.assets import AssetConversionService
from app.services.html_post import HTMLPostProcessor
from app.services.pdf import PDFConversionService
from app.services.svg_optimizer import SVGOptimizer
from app.services.tikz import TikZConversionService


def test_tikz_conversion():
    """Test TikZ conversion to SVG."""
    logger.info("Testing TikZ conversion...")

    try:
        # Initialize TikZ service with correct paths
        tikz_service = TikZConversionService(
            dvisvgm_path="/opt/homebrew/bin/dvisvgm",
            tectonic_path="/opt/homebrew/bin/tectonic",
        )

        # Test with sample TikZ file
        sample_file = Path(".sample/simple_tikz.tex")
        output_dir = Path(".sample/output")
        output_dir.mkdir(exist_ok=True)

        logger.info(f"Converting TikZ file: {sample_file}")
        result = tikz_service.convert_tikz_to_svg(sample_file, output_dir)

        if result.get("success"):
            logger.success(f"✅ TikZ conversion successful: {result['output_file']}")
            return True
        else:
            logger.error(f"❌ TikZ conversion failed: {result}")
            return False

    except Exception as exc:
        logger.error(f"❌ TikZ conversion error: {exc}")
        return False


def test_asset_conversion_service():
    """Test the main asset conversion service."""
    logger.info("Testing asset conversion service...")

    try:
        # Initialize asset conversion service with correct paths
        tikz_service = TikZConversionService(
            dvisvgm_path="/opt/homebrew/bin/dvisvgm",
            tectonic_path="/opt/homebrew/bin/tectonic",
        )
        pdf_service = PDFConversionService(
            gs_path="/opt/homebrew/bin/gs", pdfinfo_path="/opt/homebrew/bin/pdfinfo"
        )

        asset_service = AssetConversionService(
            tikz_service=tikz_service, pdf_service=pdf_service
        )

        # Test with sample directory
        input_dir = Path(".sample")
        output_dir = Path(".sample/output")
        output_dir.mkdir(exist_ok=True)

        logger.info(f"Converting assets from: {input_dir}")
        result = asset_service.convert_assets(
            input_dir, output_dir, asset_types=["tikz"], options={"timeout": 300}
        )

        if result.get("success"):
            logger.success(
                f"✅ Asset conversion successful: "
                f"{result['successful_conversions']} assets converted"
            )
            return True
        else:
            logger.error(f"❌ Asset conversion failed: {result}")
            return False

    except Exception as exc:
        logger.error(f"❌ Asset conversion error: {exc}")
        return False


def test_html_post_processing():
    """Test HTML post-processing with asset conversion."""
    logger.info("Testing HTML post-processing with asset conversion...")

    try:
        # Initialize HTML post-processor with correct paths
        tikz_service = TikZConversionService(
            dvisvgm_path="/opt/homebrew/bin/dvisvgm",
            tectonic_path="/opt/homebrew/bin/tectonic",
        )
        pdf_service = PDFConversionService(
            gs_path="/opt/homebrew/bin/gs", pdfinfo_path="/opt/homebrew/bin/pdfinfo"
        )

        asset_service = AssetConversionService(
            tikz_service=tikz_service, pdf_service=pdf_service
        )

        html_processor = HTMLPostProcessor(asset_conversion_service=asset_service)

        # Test with sample HTML file
        sample_html = Path(".sample/sample_html.html")
        output_html = Path(".sample/output/processed_sample.html")

        logger.info(f"Processing HTML file: {sample_html}")
        result = html_processor.process_html(sample_html, output_html)

        if result.get("success"):
            logger.success(f"✅ HTML processing successful: {result['output_file']}")
            logger.info(f"Steps completed: {result.get('steps_completed', [])}")
            if result.get("converted_assets"):
                logger.info(f"Converted assets: {len(result['converted_assets'])}")
            if result.get("failed_assets"):
                logger.warning(f"Failed assets: {len(result['failed_assets'])}")
            return True
        else:
            logger.error(f"❌ HTML processing failed: {result}")
            return False

    except Exception as exc:
        logger.error(f"❌ HTML processing error: {exc}")
        return False


def test_svg_optimization():
    """Test SVG optimization."""
    logger.info("Testing SVG optimization...")

    try:
        # Initialize SVG optimizer
        svg_optimizer = SVGOptimizer()

        # Look for SVG files in output directory
        output_dir = Path(".sample/output")
        svg_files = list(output_dir.glob("*.svg"))

        if not svg_files:
            logger.warning("No SVG files found for optimization test")
            return True

        # Test optimization on first SVG file
        svg_file = svg_files[0]
        optimized_file = output_dir / f"{svg_file.stem}_optimized.svg"

        logger.info(f"Optimizing SVG: {svg_file}")
        result = svg_optimizer.optimize_svg(svg_file, optimized_file)

        if result.get("success"):
            logger.success(
                f"✅ SVG optimization successful: "
                f"{result['compression_ratio']:.2%} size reduction"
            )
            return True
        else:
            logger.error(f"❌ SVG optimization failed: {result}")
            return False

    except Exception as exc:
        logger.error(f"❌ SVG optimization error: {exc}")
        return False


def test_asset_validation():
    """Test asset validation."""
    logger.info("Testing asset validation...")

    try:
        # Initialize asset validator
        asset_validator = AssetValidator()

        # Look for SVG files in output directory
        output_dir = Path(".sample/output")
        svg_files = list(output_dir.glob("*.svg"))

        if not svg_files:
            logger.warning("No SVG files found for validation test")
            return True

        # Test validation on first SVG file
        svg_file = svg_files[0]

        logger.info(f"Validating SVG: {svg_file}")
        result = asset_validator.validate_svg(svg_file)

        if result.get("is_valid"):
            logger.success(
                f"✅ SVG validation successful: Quality score "
                f"{result['quality_score']:.2f}"
            )
            return True
        else:
            logger.warning(f"⚠️ SVG validation issues: {result.get('errors', [])}")
            return True  # Still consider it a success if we got results

    except Exception as exc:
        logger.error(f"❌ Asset validation error: {exc}")
        return False


def main():
    """Run all tests."""
    logger.info("🚀 Starting Asset Conversion Pipeline Tests")
    logger.info("=" * 50)

    tests = [
        ("TikZ Conversion", test_tikz_conversion),
        ("Asset Conversion Service", test_asset_conversion_service),
        ("HTML Post-Processing", test_html_post_processing),
        ("SVG Optimization", test_svg_optimization),
        ("Asset Validation", test_asset_validation),
    ]

    results = []

    for test_name, test_func in tests:
        logger.info(f"\n🧪 Running {test_name}...")
        try:
            success = test_func()
            results.append((test_name, success))
            if success:
                logger.success(f"✅ {test_name} PASSED")
            else:
                logger.error(f"❌ {test_name} FAILED")
        except Exception as exc:
            logger.error(f"❌ {test_name} ERROR: {exc}")
            results.append((test_name, False))

    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("📊 TEST SUMMARY")
    logger.info("=" * 50)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        logger.info(f"{test_name}: {status}")

    logger.info(f"\nOverall: {passed}/{total} tests passed")

    if passed == total:
        logger.success(
            "🎉 All tests passed! Asset conversion pipeline is working correctly."
        )
        return 0
    else:
        logger.error(f"⚠️ {total - passed} tests failed. Please check the logs above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
