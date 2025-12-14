#!/usr/bin/env python3
"""
Test script for sample files from GitHub issues.

This script tests conversions using the sample files from issues #11, #12, #13, and #14.
"""

import json
import sys
import time
from pathlib import Path

import requests

# Base URL for the API
BASE_URL = "http://localhost:8000/api/v1"

# Sample files to test
SAMPLE_FILES = {
    "issue-11-12": {
        "file": ".sample/issue-11-12-geo-2025-1177-1.zip",
        "description": "Issue #11 & #12: Display equations and citations",
        "expected_fixes": [
            "Equations should not be split across multiple MathJax containers",
            "Citations should have author and year together in single link",
        ],
    },
    "issue-13": {
        "file": ".sample/issue-13-geo-2025-1015-2.zip",
        "description": "Issue #13: SEG input conversion failure",
        "expected_fixes": [
            "Should provide detailed error diagnostics if conversion fails",
            "Error messages should include actionable suggestions",
        ],
    },
    "issue-14": {
        "file": ".sample/issue-14-eLife-VOR-RA-2024-105138.zip",
        "description": "Issue #14: Conversion timeout",
        "expected_fixes": [
            "Should use adaptive timeout based on file size",
            "Should complete within reasonable time (not timeout)",
        ],
    },
}


def check_server_health() -> bool:
    """Check if the server is running and healthy."""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Server is running and healthy")
            return True
        else:
            print(f"❌ Server returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Server is not running. Please start the server first.")
        print("   Run: poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000")
        return False
    except Exception as e:
        print(f"❌ Error checking server health: {e}")
        return False


def submit_conversion(file_path: Path, description: str) -> dict | None:
    """Submit a conversion job and return the conversion ID."""
    print(f"\n📤 Submitting conversion: {description}")
    print(f"   File: {file_path.name}")

    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return None

    try:
        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f, "application/zip")}
            response = requests.post(
                f"{BASE_URL}/convert",
                files=files,
                timeout=30,
            )

        if response.status_code == 200:
            result = response.json()
            conversion_id = result.get("conversion_id")
            print(f"✅ Conversion submitted: {conversion_id}")
            return result
        else:
            print(f"❌ Failed to submit conversion: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error submitting conversion: {e}")
        return None


def check_conversion_status(conversion_id: str, max_wait: int = 1800) -> dict | None:
    """Check conversion status and wait for completion."""
    print(f"\n⏳ Checking status for conversion: {conversion_id}")
    start_time = time.time()

    while True:
        try:
            response = requests.get(
                f"{BASE_URL}/convert/{conversion_id}",
                timeout=10,
            )

            if response.status_code == 200:
                result = response.json()
                status = result.get("status", "unknown")
                progress = result.get("progress", 0)
                message = result.get("message", "")

                elapsed = int(time.time() - start_time)
                print(
                    f"   Status: {status} | Progress: {progress}% | "
                    f"Elapsed: {elapsed}s | {message}"
                )

                if status == "completed":
                    print(f"✅ Conversion completed in {elapsed}s")
                    return result
                elif status == "failed":
                    error_msg = result.get("error_message", "Unknown error")
                    diagnostics = result.get("diagnostics", {})
                    print(f"❌ Conversion failed: {error_msg}")
                    if diagnostics:
                        print(f"   Diagnostics available: {json.dumps(diagnostics, indent=2)}")
                    return result
                elif elapsed > max_wait:
                    print(f"⏱️  Timeout after {max_wait}s")
                    return result

                time.sleep(5)  # Check every 5 seconds
            else:
                print(f"❌ Failed to check status: {response.status_code}")
                return None

        except Exception as e:
            print(f"❌ Error checking status: {e}")
            return None


def verify_fixes(conversion_id: str, expected_fixes: list[str]) -> None:
    """Verify that the expected fixes are working."""
    print(f"\n🔍 Verifying fixes for conversion: {conversion_id}")

    # Get conversion result
    try:
        response = requests.get(
            f"{BASE_URL}/convert/{conversion_id}/result",
            timeout=10,
        )

        if response.status_code == 200:
            result = response.json()
            html_file = result.get("html_file", "")

            print(f"✅ HTML file generated: {html_file}")

            # Check if HTML file exists and read it
            if html_file:
                html_path = Path(html_file)
                if html_path.exists():
                    html_content = html_path.read_text(encoding="utf-8")

                    # Check for fixes
                    for fix in expected_fixes:
                        if "MathJax" in fix and "mjx-container" in html_content:
                            # Count MathJax containers in equation tables
                            # This is a basic check - full verification would need HTML parsing
                            print(f"   ✓ MathJax containers found in output")
                        elif "citation" in fix.lower() and "cite" in html_content:
                            print(f"   ✓ Citation elements found in output")
                        else:
                            print(f"   ? Fix verification: {fix}")

            print(f"   Note: Full verification requires manual HTML inspection")
        else:
            print(f"⚠️  Could not retrieve result: {response.status_code}")

    except Exception as e:
        print(f"⚠️  Error verifying fixes: {e}")


def main():
    """Main test function."""
    print("=" * 70)
    print("Testing Sample Files from GitHub Issues")
    print("=" * 70)

    # Check server health
    if not check_server_health():
        sys.exit(1)

    results = {}

    # Test each sample file
    for test_name, test_info in SAMPLE_FILES.items():
        print("\n" + "=" * 70)
        print(f"Testing: {test_name.upper()}")
        print("=" * 70)

        file_path = Path(test_info["file"])
        description = test_info["description"]
        expected_fixes = test_info["expected_fixes"]

        # Submit conversion
        conversion_result = submit_conversion(file_path, description)
        if not conversion_result:
            results[test_name] = {"status": "failed", "error": "Submission failed"}
            continue

        conversion_id = conversion_result.get("conversion_id")
        if not conversion_id:
            results[test_name] = {"status": "failed", "error": "No conversion ID"}
            continue

        # Wait for completion
        status_result = check_conversion_status(conversion_id)
        if not status_result:
            results[test_name] = {"status": "unknown", "conversion_id": conversion_id}
            continue

        # Verify fixes
        if status_result.get("status") == "completed":
            verify_fixes(conversion_id, expected_fixes)

        results[test_name] = {
            "status": status_result.get("status"),
            "conversion_id": conversion_id,
            "error_message": status_result.get("error_message"),
            "diagnostics": status_result.get("diagnostics"),
        }

    # Print summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)

    for test_name, result in results.items():
        status = result.get("status", "unknown")
        status_icon = "✅" if status == "completed" else "❌" if status == "failed" else "⚠️"
        print(f"{status_icon} {test_name}: {status}")
        if result.get("error_message"):
            print(f"   Error: {result['error_message']}")

    print("\n" + "=" * 70)
    print("Testing complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
