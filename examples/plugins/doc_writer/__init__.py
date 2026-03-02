"""
Document Writer — Claude Artifacts-style document editing plugin.

Returns markdown artifacts that render as rich documents
in the side panel. Users can ask the agent to revise sections.
"""

from .doc_writer import DocWriterPlugin

__all__ = ["DocWriterPlugin"]
