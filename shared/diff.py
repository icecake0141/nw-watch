"""Diff generation utilities."""
import difflib
from typing import List


def generate_diff(old_text: str, new_text: str) -> str:
    """Generate unified diff between two texts.
    
    Args:
        old_text: Previous version of text
        new_text: Current version of text
    
    Returns:
        Unified diff as string
    """
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile='previous',
        tofile='latest',
        lineterm='\n'
    )
    
    return ''.join(diff)


def generate_side_by_side_diff(text_a: str, text_b: str, label_a: str = "A", 
                                label_b: str = "B") -> str:
    """Generate side-by-side diff between two texts.
    
    Args:
        text_a: First text
        text_b: Second text
        label_a: Label for first text
        label_b: Label for second text
    
    Returns:
        Side-by-side diff as string
    """
    lines_a = text_a.splitlines()
    lines_b = text_b.splitlines()
    
    diff = difflib.unified_diff(
        lines_a,
        lines_b,
        fromfile=label_a,
        tofile=label_b,
        lineterm=''
    )
    
    return '\n'.join(diff)
