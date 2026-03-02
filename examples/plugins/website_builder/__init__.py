"""
Website Builder — external plugin reference implementation.

To install, copy this entire directory to ~/.cachibot/plugins/website_builder/
and restart CachiBot.  The plugin's capability key is ``ext_website_builder``.
"""

from .website_builder import WebsiteBuilderPlugin

__all__ = ["WebsiteBuilderPlugin"]
