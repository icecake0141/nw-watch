"""Output filtering and truncation utilities."""
from typing import List, Optional, Tuple


def apply_line_filters(text: str, exclusions: List[str]) -> str:
    """Filter out lines containing any of the exclusion substrings.
    
    Args:
        text: Input text
        exclusions: List of substrings to exclude
    
    Returns:
        Filtered text with excluded lines removed
    """
    if not exclusions:
        return text
    
    lines = text.splitlines()
    filtered_lines = [
        line for line in lines
        if not any(excl in line for excl in exclusions)
    ]
    
    return '\n'.join(filtered_lines)


def check_output_filtered(text: str, output_exclusions: List[str]) -> bool:
    """Check if output should be marked as filtered.
    
    Args:
        text: Output text to check
        output_exclusions: List of substrings that indicate filtered output
    
    Returns:
        True if output contains any exclusion substring
    """
    if not output_exclusions:
        return False
    
    return any(excl in text for excl in output_exclusions)


def truncate_output(text: str, max_lines: int) -> Tuple[str, bool, int]:
    """Truncate output to maximum number of lines.
    
    Args:
        text: Input text
        max_lines: Maximum number of lines to keep
    
    Returns:
        Tuple of (truncated_text, is_truncated, original_line_count)
    """
    lines = text.splitlines()
    original_count = len(lines)
    
    if original_count <= max_lines:
        return text, False, original_count
    
    truncated_lines = lines[:max_lines]
    truncated_text = '\n'.join(truncated_lines)
    truncated_text += f'\n\n...(truncated: showing first {max_lines} lines of {original_count})'
    
    return truncated_text, True, original_count


def process_output(text: str, line_exclusions: Optional[List[str]] = None,
                   output_exclusions: Optional[List[str]] = None,
                   max_lines: int = 500) -> Tuple[str, bool, bool, int]:
    """Process output with filtering and truncation.
    
    Args:
        text: Raw output text
        line_exclusions: Substrings to filter out from lines
        output_exclusions: Substrings indicating filtered output
        max_lines: Maximum number of lines to keep
    
    Returns:
        Tuple of (processed_text, is_filtered, is_truncated, original_line_count)
    """
    # Apply line filtering
    if line_exclusions:
        text = apply_line_filters(text, line_exclusions)
    
    # Check if output is filtered
    is_filtered = check_output_filtered(text, output_exclusions or [])
    
    # Truncate output
    text, is_truncated, original_line_count = truncate_output(text, max_lines)
    
    return text, is_filtered, is_truncated, original_line_count
