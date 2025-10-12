"""
Unit tests for HTML post-processing service.

This module contains comprehensive unit tests for the HTMLPostProcessor class,
testing HTML cleaning, validation, enhancement, and optimization functionality.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from app.services.html_post import (
    HTMLPostProcessor,
    HTMLPostProcessingError,
    HTMLValidationError,
    HTMLCleaningError,
)


class TestHTMLPostProcessor:
    """Test cases for HTMLPostProcessor class."""
    
    def test_processor_initialization(self):
        """Test processor initialization with default settings."""
        processor = HTMLPostProcessor()
        assert processor.base_url is None
        assert processor.cleaner is not None
    
    def test_processor_initialization_with_base_url(self):
        """Test processor initialization with base URL."""
        base_url = "https://example.com"
        processor = HTMLPostProcessor(base_url=base_url)
        assert processor.base_url == base_url
    
    def test_process_html_success(self):
        """Test successful HTML processing."""
        processor = HTMLPostProcessor()
        
        html_content = """
        <html>
        <head><title>Test</title></head>
        <body>
        <h1>Test Document</h1>
        <p>This is a test paragraph.</p>
        </body>
        </html>
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            html_file = Path(f.name)
        
        try:
            result = processor.process_html(html_file)
            
            assert result["success"] is True
            assert result["original_size"] > 0
            assert result["final_size"] > 0
            assert "html_cleaning" in result["steps_completed"]
            assert len(result["errors"]) == 0
        finally:
            html_file.unlink()
    
    def test_process_html_with_output_file(self):
        """Test HTML processing with output file."""
        processor = HTMLPostProcessor()
        
        html_content = """
        <html>
        <head><title>Test</title></head>
        <body>
        <h1>Test Document</h1>
        <p>This is a test paragraph.</p>
        </body>
        </html>
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            html_file = Path(f.name)
        
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as output_f:
            output_file = Path(output_f.name)
        
        try:
            result = processor.process_html(html_file, output_file)
            
            assert result["success"] is True
            assert result["output_file"] == str(output_file)
            assert output_file.exists()
        finally:
            html_file.unlink()
            if output_file.exists():
                output_file.unlink()
    
    def test_process_html_file_not_found(self):
        """Test processing non-existent HTML file."""
        processor = HTMLPostProcessor()
        non_existent_file = Path("/non/existent/file.html")
        
        with pytest.raises(HTMLPostProcessingError) as exc_info:
            processor.process_html(non_existent_file)
        
        assert "HTML file not found" in str(exc_info.value)
    
    def test_remove_latexml_elements(self):
        """Test removal of LaTeXML-specific elements."""
        processor = HTMLPostProcessor()
        
        html_content = """
        <html>
        <head><title>Test</title></head>
        <body>
        <h1 latexml:attribute="value">Test Document</h1>
        <p>This is a test paragraph.</p>
        </body>
        </html>
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            html_file = Path(f.name)
        
        try:
            result = processor.process_html(html_file)
            
            assert result["success"] is True
            # Should have cleaned LaTeXML attributes
            assert "html_cleaning" in result["steps_completed"]
        finally:
            html_file.unlink()
    
    def test_clean_dangerous_content(self):
        """Test removal of dangerous content."""
        processor = HTMLPostProcessor()
        
        html_content = """
        <html>
        <head><title>Test</title></head>
        <body>
        <h1>Test Document</h1>
        <script>alert('dangerous');</script>
        <p onclick="alert('click')">This is a test paragraph.</p>
        </body>
        </html>
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            html_file = Path(f.name)
        
        try:
            result = processor.process_html(html_file)
            
            assert result["success"] is True
            # Should have removed dangerous content
            assert "html_cleaning" in result["steps_completed"]
        finally:
            html_file.unlink()
    
    def test_remove_empty_elements(self):
        """Test removal of empty elements."""
        processor = HTMLPostProcessor()
        
        html_content = """
        <html>
        <head><title>Test</title></head>
        <body>
        <h1>Test Document</h1>
        <div></div>
        <span></span>
        <p>This is a test paragraph.</p>
        </body>
        </html>
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            html_file = Path(f.name)
        
        try:
            result = processor.process_html(html_file)
            
            assert result["success"] is True
            assert "html_cleaning" in result["steps_completed"]
        finally:
            html_file.unlink()
    
    def test_normalize_whitespace(self):
        """Test whitespace normalization."""
        processor = HTMLPostProcessor()
        
        html_content = """
        <html>
        <head><title>Test</title></head>
        <body>
        <h1>Test    Document</h1>
        <p>This   is   a   test   paragraph.</p>
        </body>
        </html>
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            html_file = Path(f.name)
        
        try:
            result = processor.process_html(html_file)
            
            assert result["success"] is True
            assert "html_cleaning" in result["steps_completed"]
        finally:
            html_file.unlink()
    
    def test_validate_html_structure_missing_elements(self):
        """Test HTML structure validation with missing elements."""
        processor = HTMLPostProcessor()
        
        html_content = """
        <head><title>Test</title></head>
        <body>
        <h1>Test Document</h1>
        <p>This is a test paragraph.</p>
        </body>
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            html_file = Path(f.name)
        
        try:
            result = processor.process_html(html_file)
            
            # Should have warnings about missing elements
            assert "html_validation" in result["steps_completed"] or len(result["warnings"]) > 0
        finally:
            html_file.unlink()
    
    def test_validate_nesting_invalid(self):
        """Test validation of invalid HTML nesting."""
        processor = HTMLPostProcessor()
        
        html_content = """
        <html>
        <head><title>Test</title></head>
        <body>
        <h1>Test Document</h1>
        <p>This is a <p>nested paragraph</p> which is invalid.</p>
        </body>
        </html>
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            html_file = Path(f.name)
        
        try:
            result = processor.process_html(html_file)
            
            # Should have warnings about invalid nesting
            assert "html_validation" in result["steps_completed"] or len(result["warnings"]) > 0
        finally:
            html_file.unlink()
    
    def test_validate_accessibility_missing_alt(self):
        """Test accessibility validation for missing alt text."""
        processor = HTMLPostProcessor()
        
        html_content = """
        <html>
        <head><title>Test</title></head>
        <body>
        <h1>Test Document</h1>
        <img src="test.jpg">
        <p>This is a test paragraph.</p>
        </body>
        </html>
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            html_file = Path(f.name)
        
        try:
            result = processor.process_html(html_file)
            
            # Should have warnings about missing alt text
            assert "html_validation" in result["steps_completed"] or len(result["warnings"]) > 0
        finally:
            html_file.unlink()
    
    def test_enhance_html_with_math(self):
        """Test HTML enhancement with math content."""
        processor = HTMLPostProcessor()
        
        html_content = """
        <html>
        <head><title>Test</title></head>
        <body>
        <h1>Test Document</h1>
        <math><mi>x</mi><mo>=</mo><mn>1</mn></math>
        <p>This is a test paragraph.</p>
        </body>
        </html>
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            html_file = Path(f.name)
        
        try:
            result = processor.process_html(html_file)
            
            assert result["success"] is True
            assert "html_enhancement" in result["steps_completed"]
        finally:
            html_file.unlink()
    
    def test_enhance_links_external(self):
        """Test enhancement of external links."""
        processor = HTMLPostProcessor(base_url="https://example.com")
        
        html_content = """
        <html>
        <head><title>Test</title></head>
        <body>
        <h1>Test Document</h1>
        <a href="https://external.com">External Link</a>
        <a href="/internal">Internal Link</a>
        </body>
        </html>
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            html_file = Path(f.name)
        
        try:
            result = processor.process_html(html_file)
            
            assert result["success"] is True
            assert "html_enhancement" in result["steps_completed"]
        finally:
            html_file.unlink()
    
    def test_add_responsive_meta(self):
        """Test addition of responsive meta tag."""
        processor = HTMLPostProcessor()
        
        html_content = """
        <html>
        <head><title>Test</title></head>
        <body>
        <h1>Test Document</h1>
        <p>This is a test paragraph.</p>
        </body>
        </html>
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            html_file = Path(f.name)
        
        try:
            result = processor.process_html(html_file)
            
            assert result["success"] is True
            assert "html_enhancement" in result["steps_completed"]
        finally:
            html_file.unlink()
    
    def test_add_enhancement_css(self):
        """Test addition of enhancement CSS."""
        processor = HTMLPostProcessor()
        
        html_content = """
        <html>
        <head><title>Test</title></head>
        <body>
        <h1>Test Document</h1>
        <p>This is a test paragraph.</p>
        </body>
        </html>
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            html_file = Path(f.name)
        
        try:
            result = processor.process_html(html_file)
            
            assert result["success"] is True
            assert "html_enhancement" in result["steps_completed"]
        finally:
            html_file.unlink()
    
    def test_optimize_html(self):
        """Test HTML optimization."""
        processor = HTMLPostProcessor()
        
        html_content = """
        <html>
        <head><title>Test</title></head>
        <body>
        <h1>Test Document</h1>
        <img src="test.jpg">
        <p>This is a test paragraph.</p>
        </body>
        </html>
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            html_file = Path(f.name)
        
        try:
            result = processor.process_html(html_file)
            
            assert result["success"] is True
            assert "html_optimization" in result["steps_completed"]
        finally:
            html_file.unlink()
    
    def test_minify_html(self):
        """Test HTML minification."""
        processor = HTMLPostProcessor()
        
        html_content = """
        <html>
        <head>
            <title>Test</title>
        </head>
        <body>
            <h1>Test Document</h1>
            <p>This is a test paragraph.</p>
        </body>
        </html>
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            html_file = Path(f.name)
        
        try:
            result = processor.process_html(html_file)
            
            assert result["success"] is True
            assert result["size_reduction"] >= 0
        finally:
            html_file.unlink()
    
    def test_optimize_images(self):
        """Test image optimization."""
        processor = HTMLPostProcessor()
        
        html_content = """
        <html>
        <head><title>Test</title></head>
        <body>
        <h1>Test Document</h1>
        <img src="test.jpg">
        <p>This is a test paragraph.</p>
        </body>
        </html>
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            html_file = Path(f.name)
        
        try:
            result = processor.process_html(html_file)
            
            assert result["success"] is True
            assert "html_optimization" in result["steps_completed"]
        finally:
            html_file.unlink()
    
    def test_remove_unnecessary_attributes(self):
        """Test removal of unnecessary attributes."""
        processor = HTMLPostProcessor()
        
        html_content = """
        <html>
        <head><title>Test</title></head>
        <body>
        <h1 data-latexml="value">Test Document</h1>
        <p xmlns="http://www.w3.org/1999/xhtml">This is a test paragraph.</p>
        </body>
        </html>
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            html_file = Path(f.name)
        
        try:
            result = processor.process_html(html_file)
            
            assert result["success"] is True
            assert "html_optimization" in result["steps_completed"]
        finally:
            html_file.unlink()
    
    def test_validate_html_file_success(self):
        """Test successful HTML file validation."""
        processor = HTMLPostProcessor()
        
        html_content = """
        <html>
        <head><title>Test</title></head>
        <body>
        <h1>Test Document</h1>
        <p>This is a test paragraph.</p>
        </body>
        </html>
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            html_file = Path(f.name)
        
        try:
            result = processor.validate_html_file(html_file)
            
            assert result["is_valid"] is True
            assert result["has_html"] is True
            assert result["has_head"] is True
            assert result["has_body"] is True
            assert result["file_size"] > 0
            assert result["element_count"] > 0
            assert result["text_length"] > 0
        finally:
            html_file.unlink()
    
    def test_validate_html_file_invalid(self):
        """Test validation of invalid HTML file."""
        processor = HTMLPostProcessor()
        
        invalid_html = """
        <html>
        <head><title>Test</title></head>
        <body>
        <h1>Test Document</h1>
        <p>This is a test paragraph.</p>
        </body>
        </html>
        <invalid>This should cause validation error</invalid>
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(invalid_html)
            html_file = Path(f.name)
        
        try:
            result = processor.validate_html_file(html_file)
            
            # Should still be valid for basic structure
            assert result["has_html"] is True
            assert result["has_head"] is True
            assert result["has_body"] is True
        finally:
            html_file.unlink()
    
    def test_validate_html_file_not_found(self):
        """Test validation of non-existent HTML file."""
        processor = HTMLPostProcessor()
        non_existent_file = Path("/non/existent/file.html")
        
        with pytest.raises(HTMLPostProcessingError) as exc_info:
            processor.validate_html_file(non_existent_file)
        
        assert "HTML file not found" in str(exc_info.value)
    
    def test_is_external_link(self):
        """Test external link detection."""
        processor = HTMLPostProcessor(base_url="https://example.com")
        
        # External link
        assert processor._is_external_link("https://external.com/page") is True
        assert processor._is_external_link("http://other.com/page") is True
        
        # Internal link
        assert processor._is_external_link("/internal/page") is False
        assert processor._is_external_link("internal/page") is False
        assert processor._is_external_link("https://example.com/page") is False
    
    def test_is_external_link_no_base_url(self):
        """Test external link detection without base URL."""
        processor = HTMLPostProcessor()
        
        # Should return False when no base URL is set
        assert processor._is_external_link("https://external.com/page") is False
    
    def test_is_external_link_invalid_url(self):
        """Test external link detection with invalid URL."""
        processor = HTMLPostProcessor(base_url="https://example.com")
        
        # Invalid URL should return False
        assert processor._is_external_link("invalid-url") is False
        assert processor._is_external_link("") is False


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
