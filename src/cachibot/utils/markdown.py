"""
Markdown utilities for platform message formatting.
"""

import re


def strip_markdown(text: str) -> str:
    """
    Strip markdown formatting from text for platforms that don't handle it well.

    Converts:
    - **bold** or __bold__ → bold
    - *italic* or _italic_ → italic
    - ~~strikethrough~~ → strikethrough
    - `code` → code
    - ```code blocks``` → code blocks
    - [link text](url) → link text (url)
    - # Headers → Headers
    - > Blockquotes → Blockquotes (indented)
    - Lists (- or *) → preserved with dash

    Args:
        text: The markdown text to strip

    Returns:
        Plain text with markdown formatting removed
    """
    if not text:
        return text

    result = text

    # Code blocks (``` ... ```) - extract content only
    result = re.sub(r'```(?:\w+)?\n?(.*?)```', r'\1', result, flags=re.DOTALL)

    # Inline code (`code`) - just remove backticks
    result = re.sub(r'`([^`]+)`', r'\1', result)

    # Images ![alt](url) → alt
    result = re.sub(r'!\[([^\]]*)\]\([^)]+\)', r'\1', result)

    # Links [text](url) → text (url)
    result = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 (\2)', result)

    # Bold **text** or __text__
    result = re.sub(r'\*\*([^*]+)\*\*', r'\1', result)
    result = re.sub(r'__([^_]+)__', r'\1', result)

    # Italic *text* or _text_ (but not inside words like some_var)
    result = re.sub(r'(?<!\w)\*([^*]+)\*(?!\w)', r'\1', result)
    result = re.sub(r'(?<!\w)_([^_]+)_(?!\w)', r'\1', result)

    # Strikethrough ~~text~~
    result = re.sub(r'~~([^~]+)~~', r'\1', result)

    # Headers (# Header) - just remove the # symbols
    result = re.sub(r'^#{1,6}\s+', '', result, flags=re.MULTILINE)

    # Blockquotes (> quote) - remove > but keep text
    result = re.sub(r'^>\s?', '  ', result, flags=re.MULTILINE)

    # Horizontal rules (---, ***, ___) - replace with dashes
    result = re.sub(r'^[-*_]{3,}$', '---', result, flags=re.MULTILINE)

    # Clean up any double spaces
    result = re.sub(r'  +', ' ', result)

    return result.strip()
