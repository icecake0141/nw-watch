"""Tests for diff functionality."""
import pytest
from shared.diff import generate_diff, generate_side_by_side_diff, generate_inline_char_diff


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


def test_generate_inline_char_diff_identical():
    """Test character-level diff with identical texts."""
    text = "Hello World"
    
    result_a, result_b = generate_inline_char_diff(text, text)
    
    # No highlighting for identical text
    assert "char-diff-" not in result_a
    assert "char-diff-" not in result_b
    assert "Hello World" in result_a
    assert "Hello World" in result_b


def test_generate_inline_char_diff_simple_change():
    """Test character-level diff with simple text change."""
    text_a = "Hello World"
    text_b = "Hello Earth"
    
    result_a, result_b = generate_inline_char_diff(text_a, text_b)
    
    # Should have "Hello " unchanged and "World"/"Earth" highlighted
    assert "Hello " in result_a
    assert "Hello " in result_b
    assert "char-diff-remove" in result_a
    assert "char-diff-add" in result_b
    # Words are highlighted so they may be split by HTML tags
    assert "Wo" in result_a or "World" in result_a
    assert "Ea" in result_b or "Earth" in result_b


def test_generate_inline_char_diff_insertion():
    """Test character-level diff with insertion."""
    text_a = "Hello"
    text_b = "Hello World"
    
    result_a, result_b = generate_inline_char_diff(text_a, text_b)
    
    # Should have insertion in text_b only
    assert "char-diff-add" in result_b
    assert " World" in result_b
    assert "Hello" in result_a


def test_generate_inline_char_diff_deletion():
    """Test character-level diff with deletion."""
    text_a = "Hello World"
    text_b = "Hello"
    
    result_a, result_b = generate_inline_char_diff(text_a, text_b)
    
    # Should have deletion in text_a only
    assert "char-diff-remove" in result_a
    assert " World" in result_a
    assert "Hello" in result_b


def test_generate_inline_char_diff_multiline():
    """Test character-level diff with multiline text."""
    text_a = "line1\nline2\nline3"
    text_b = "line1\nline2 modified\nline3"
    
    result_a, result_b = generate_inline_char_diff(text_a, text_b)
    
    # Should preserve newlines and highlight the difference
    assert "line1" in result_a
    assert "line1" in result_b
    assert "char-diff-remove" in result_a or "char-diff-add" in result_b
    assert "line2" in result_a
    # Check that modified text is present (may be split by HTML tags)
    assert "modified" in result_b


def test_generate_inline_char_diff_html_escape():
    """Test that HTML characters are properly escaped."""
    text_a = "<script>alert('xss')</script>"
    text_b = "<script>alert('safe')</script>"
    
    result_a, result_b = generate_inline_char_diff(text_a, text_b)
    
    # HTML should be escaped
    assert "&lt;" in result_a
    assert "&gt;" in result_a
    assert "&lt;" in result_b
    assert "&gt;" in result_b
    assert "<script>" not in result_a or "char-diff-" in result_a
    assert "<script>" not in result_b or "char-diff-" in result_b
