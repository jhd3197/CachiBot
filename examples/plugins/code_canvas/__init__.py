"""
Code Canvas — ChatGPT Canvas-style code editing plugin.

Returns code artifacts that render in an editable side panel
with syntax highlighting. Users can edit directly and ask
the agent to iterate.
"""

from .code_canvas import CodeCanvasPlugin

__all__ = ["CodeCanvasPlugin"]
