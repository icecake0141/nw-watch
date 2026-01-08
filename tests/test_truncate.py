"""Tests for output truncation."""
import pytest
from shared.filters import truncate_output


def test_truncate_output_no_truncation_needed():
    """Test truncation when output is within limit."""
    text = "line1\nline2\nline3"
    result, is_truncated, line_count = truncate_output(text, max_lines=10)
    
    assert result == text
    assert is_truncated is False
    assert line_count == 3


def test_truncate_output_exact_limit():
    """Test truncation when output is exactly at limit."""
    lines = [f"line{i}" for i in range(10)]
    text = "\n".join(lines)
    
    result, is_truncated, line_count = truncate_output(text, max_lines=10)
    
    assert result == text
    assert is_truncated is False
    assert line_count == 10


def test_truncate_output_exceeds_limit():
    """Test truncation when output exceeds limit."""
    lines = [f"line{i}" for i in range(100)]
    text = "\n".join(lines)
    
    result, is_truncated, line_count = truncate_output(text, max_lines=50)
    
    assert is_truncated is True
    assert line_count == 100
    assert "truncated" in result.lower()
    assert "showing first 50 lines of 100" in result


def test_truncate_output_preserves_first_lines():
    """Test that truncation preserves first N lines."""
    lines = [f"line{i}" for i in range(100)]
    text = "\n".join(lines)
    
    result, is_truncated, line_count = truncate_output(text, max_lines=10)
    
    # Check that first 10 lines are present
    for i in range(10):
        assert f"line{i}" in result
    
    # Check that later lines are not present (except in truncation message)
    result_lines = result.split('\n')
    # Remove the truncation message lines to check actual content
    content_lines = [l for l in result_lines if 'truncated' not in l.lower() and l.strip()]
    assert len(content_lines) == 10


def test_truncate_output_empty_text():
    """Test truncation with empty text."""
    result, is_truncated, line_count = truncate_output("", max_lines=500)
    
    assert result == ""
    assert is_truncated is False
    assert line_count == 0  # Empty string splitlines() returns empty list


def test_truncate_output_single_line():
    """Test truncation with single line."""
    text = "single line"
    result, is_truncated, line_count = truncate_output(text, max_lines=500)
    
    assert result == text
    assert is_truncated is False
    assert line_count == 1


def test_truncate_output_message_format():
    """Test that truncation message has correct format."""
    lines = [f"line{i}" for i in range(600)]
    text = "\n".join(lines)
    
    result, is_truncated, line_count = truncate_output(text, max_lines=500)
    
    assert "...(truncated: showing first 500 lines of 600)" in result


def test_truncate_output_custom_max_lines():
    """Test truncation with custom max_lines values."""
    lines = [f"line{i}" for i in range(200)]
    text = "\n".join(lines)
    
    # Test with 100 lines
    result, is_truncated, line_count = truncate_output(text, max_lines=100)
    assert is_truncated is True
    assert line_count == 200
    assert "showing first 100 lines of 200" in result
    
    # Test with 150 lines
    result, is_truncated, line_count = truncate_output(text, max_lines=150)
    assert is_truncated is True
    assert line_count == 200
    assert "showing first 150 lines of 200" in result
