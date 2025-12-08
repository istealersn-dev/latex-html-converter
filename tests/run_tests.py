#!/usr/bin/env python3
"""
Simple test runner for Tectonic service tests.
"""

import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest  # noqa: E402


def run_tests():
    """Run all tests."""
    print("🧪 Running LaTeX to HTML5 Converter Tests...")
    print("=" * 50)

    # Run the tests
    test_files = [
        "tests/test_tectonic_service.py",
        "tests/test_tectonic_integration.py",
        "tests/test_latexml_service.py",
        "tests/test_latexml_integration.py",
        "tests/test_html_post_processor.py",
    ]

    for test_file in test_files:
        print(f"\n📁 Running {test_file}...")
        result = pytest.main([test_file, "-v", "--tb=short"])
        if result != 0:
            print(f"❌ Tests in {test_file} failed")
            return False

    print("\n✅ All tests completed successfully!")
    return True


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
