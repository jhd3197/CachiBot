"""
Cachibot - The Armored AI Agent

A cross-platform AI agent with visual security.
Powered by Prompture for structured LLM interaction.
"""

__version__ = "0.2.0"
__author__ = "jhd3197"

from cachibot.agent import CachibotAgent, Agent
from cachibot.config import Config

__all__ = ["CachibotAgent", "Agent", "Config", "__version__"]


def run_server(host: str = "127.0.0.1", port: int = 6392) -> None:
    """Run the Cachibot API server."""
    from cachibot.api.server import run_server as _run_server
    _run_server(host=host, port=port)
