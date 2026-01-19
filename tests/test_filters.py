"""Tests for filtering functionality."""

import pytest
from nw_watch.shared.filters import (
    apply_line_filters,
    check_output_filtered,
    process_output,
)


def test_apply_line_filters_empty_exclusions():
    """Test filter with no exclusions."""
    text = "line1\nline2\nline3"
    result = apply_line_filters(text, [])
    assert result == text


def test_apply_line_filters_single_exclusion():
    """Test filter with single exclusion."""
    text = "line1\nTemperature: 50C\nline3"
    result = apply_line_filters(text, ["Temperature"])
    assert result == "line1\nline3"


def test_apply_line_filters_multiple_exclusions():
    """Test filter with multiple exclusions."""
    text = "line1\nTemperature: 50C\nLast input: 00:00:00\nline4"
    result = apply_line_filters(text, ["Temperature", "Last input"])
    assert result == "line1\nline4"


def test_apply_line_filters_substring_matching():
    """Test that exclusions work with substring matching."""
    text = "prefix Temperature suffix\nnormal line"
    result = apply_line_filters(text, ["Temperature"])
    assert result == "normal line"


def test_apply_line_filters_no_matches():
    """Test filter when no lines match exclusions."""
    text = "line1\nline2\nline3"
    result = apply_line_filters(text, ["notfound"])
    assert result == text


def test_check_output_filtered_empty():
    """Test output filter check with no exclusions."""
    text = "some output"
    result = check_output_filtered(text, [])
    assert result is False


def test_check_output_filtered_match():
    """Test output filter check with matching exclusion."""
    text = "% Invalid command"
    result = check_output_filtered(text, ["% Invalid"])
    assert result is True


def test_check_output_filtered_no_match():
    """Test output filter check with no match."""
    text = "valid output"
    result = check_output_filtered(text, ["% Invalid"])
    assert result is False


def test_check_output_filtered_multiple():
    """Test output filter check with multiple exclusions."""
    text = "% Ambiguous command"
    result = check_output_filtered(text, ["% Invalid", "% Ambiguous"])
    assert result is True


def test_process_output_no_filtering():
    """Test process output with no filters."""
    text = "line1\nline2\nline3"
    result, is_filtered, is_truncated, line_count = process_output(
        text, line_exclusions=None, output_exclusions=None, max_lines=500
    )
    assert result == text
    assert is_filtered is False
    assert is_truncated is False
    assert line_count == 3


def test_process_output_with_line_filtering():
    """Test process output with line filtering."""
    text = "line1\nTemperature: 50C\nline3"
    result, is_filtered, is_truncated, line_count = process_output(
        text, line_exclusions=["Temperature"], output_exclusions=None, max_lines=500
    )
    assert "Temperature" not in result
    assert "line1" in result
    assert "line3" in result
    assert is_filtered is False


def test_process_output_filtered_output():
    """Test process output with output exclusion match."""
    text = "% Invalid command"
    result, is_filtered, is_truncated, line_count = process_output(
        text, line_exclusions=None, output_exclusions=["% Invalid"], max_lines=500
    )
    assert is_filtered is True


def test_process_output_truncated():
    """Test process output with truncation."""
    lines = [f"line{i}" for i in range(600)]
    text = "\n".join(lines)

    result, is_filtered, is_truncated, line_count = process_output(
        text, line_exclusions=None, output_exclusions=None, max_lines=500
    )

    assert is_truncated is True
    assert line_count == 600
    assert "truncated" in result.lower()
    assert "showing first 500 lines of 600" in result


def test_process_output_combined():
    """Test process output with filtering and truncation."""
    lines = [f"line{i}" for i in range(600)]
    lines[10] = "Temperature: 50C"
    text = "\n".join(lines)

    result, is_filtered, is_truncated, line_count = process_output(
        text, line_exclusions=["Temperature"], output_exclusions=None, max_lines=500
    )

    assert "Temperature" not in result
    assert is_truncated is True
