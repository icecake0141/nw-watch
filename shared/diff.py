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


def generate_side_by_side_diff(
    text_a: str,
    text_b: str,
    label_a: str = "A",
    label_b: str = "B",
    context: bool = False,
    numlines: int = 0,
) -> str:
    """Generate HTML side-by-side diff between two texts.
    
    Args:
        text_a: First text
        text_b: Second text
        label_a: Label for first text
        label_b: Label for second text
        context: Show contextual lines only (like unified diff)
        numlines: Number of context lines when context=True
    
    Returns:
        HTML table representing side-by-side diff. Empty string when texts match.
    """
    if text_a == text_b:
        return ""

    html_diff = difflib.HtmlDiff(wrapcolumn=80)
    return html_diff.make_table(
        text_a.splitlines(),
        text_b.splitlines(),
        fromdesc=label_a,
        todesc=label_b,
        context=context,
        numlines=numlines,
    )
