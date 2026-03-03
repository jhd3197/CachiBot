"""
HTML Preview — live HTML/CSS/JS preview plugin.

Returns HTML artifacts that render in a sandboxed iframe
alongside the chat.
"""

from .html_preview import HtmlPreviewPlugin

__all__ = ["HtmlPreviewPlugin"]
