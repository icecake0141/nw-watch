"""Diff generation utilities."""
import difflib
import html
from typing import List, Tuple


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
        context: Show contextual lines only (like unified diff). Defaults to False to
            include all lines.
        numlines: Number of context lines when context=True. Ignored when context is False.
    
    Returns:
        HTML table representing side-by-side diff. Empty string when texts match.
    
    Note:
        Context/numlines are provided for callers that want trimmed output;
        current API usage renders full diffs by default.
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


def generate_inline_char_diff(text_a: str, text_b: str) -> Tuple[str, str]:
    """Generate character-level inline diff highlighting for two texts.
    
    This function compares two texts character-by-character and returns HTML
    strings with inline highlighting of differences. Unchanged parts are shown
    normally, while changes are highlighted with <span> tags.
    
    Args:
        text_a: First text
        text_b: Second text
    
    Returns:
        Tuple of (highlighted_a, highlighted_b) where each is an HTML string
        with character-level diff highlighting
    """
    # Use SequenceMatcher for character-level diff
    matcher = difflib.SequenceMatcher(None, text_a, text_b)
    
    result_a = []
    result_b = []
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        text_a_part = text_a[i1:i2]
        text_b_part = text_b[j1:j2]
        
        if tag == 'equal':
            # Both sides are the same
            result_a.append(html.escape(text_a_part))
            result_b.append(html.escape(text_b_part))
        elif tag == 'replace':
            # Text was replaced
            result_a.append(f'<span class="char-diff-remove">{html.escape(text_a_part)}</span>')
            result_b.append(f'<span class="char-diff-add">{html.escape(text_b_part)}</span>')
        elif tag == 'delete':
            # Text only in A
            result_a.append(f'<span class="char-diff-remove">{html.escape(text_a_part)}</span>')
        elif tag == 'insert':
            # Text only in B
            result_b.append(f'<span class="char-diff-add">{html.escape(text_b_part)}</span>')
    
    return ''.join(result_a), ''.join(result_b)
