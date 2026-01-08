"""Tests for diff functionality."""
import pytest
from shared.diff import generate_diff, generate_side_by_side_diff


def test_generate_diff_no_changes():
    """Test diff with identical texts."""
    text = "line1\nline2\nline3"
    diff = generate_diff(text, text)
    assert diff == ""


def test_generate_diff_with_changes():
    """Test diff with actual changes."""
    old_text = "line1\nline2\nline3"
    new_text = "line1\nline2 modified\nline3"
    
    diff = generate_diff(old_text, new_text)
    
    assert "line2" in diff
    assert "line2 modified" in diff
    assert "-line2" in diff or "- line2" in diff
    assert "+line2 modified" in diff or "+ line2 modified" in diff


def test_generate_diff_added_lines():
    """Test diff with added lines."""
    old_text = "line1\nline2"
    new_text = "line1\nline2\nline3"
    
    diff = generate_diff(old_text, new_text)
    
    assert "+line3" in diff or "+ line3" in diff


def test_generate_diff_removed_lines():
    """Test diff with removed lines."""
    old_text = "line1\nline2\nline3"
    new_text = "line1\nline3"
    
    diff = generate_diff(old_text, new_text)
    
    assert "-line2" in diff or "- line2" in diff


def test_generate_diff_empty_texts():
    """Test diff with empty texts."""
    diff = generate_diff("", "")
    assert diff == ""


def test_generate_side_by_side_diff():
    """Test side-by-side diff generation."""
    text_a = "line1\nline2\nline3"
    text_b = "line1\nline2 modified\nline3"
    
    diff = generate_side_by_side_diff(text_a, text_b, "DeviceA", "DeviceB")
    
    assert "<table" in diff
    assert "DeviceA" in diff
    assert "DeviceB" in diff


def test_generate_side_by_side_diff_identical():
    """Test side-by-side diff with identical texts."""
    text = "line1\nline2\nline3"
    
    diff = generate_side_by_side_diff(text, text, "A", "B")
    
    # Identical texts should produce no diff output
    assert diff == ""
