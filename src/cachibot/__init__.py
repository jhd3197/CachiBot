"""
Cachibot - The Armored AI Agent

A cross-platform AI agent with visual security.
Powered by Prompture for structured LLM interaction.
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

from cachibot.agent import Agent, CachibotAgent
from cachibot.config import Config


def _get_version() -> str:
    """Get version from installed package metadata, VERSION file, or fallback."""
    try:
        return _pkg_version("cachibot")
    except PackageNotFoundError:
        pass
    # Fallback: read VERSION file from repo root
    from pathlib import Path

    for candidate in [
        Path(__file__).parent / "VERSION",  # bundled in package
        Path(__file__).parent.parent.parent.parent / "VERSION",  # repo root (editable)
    ]:
        if candidate.exists():
            return candidate.read_text().strip()
    return "0.0.0-unknown"


__version__ = _get_version()
__author__ = "jhd3197"

__all__ = ["CachibotAgent", "Agent", "Config", "__version__"]


def run_server(host: str = "127.0.0.1", port: int = 6392) -> None:
    """Run the Cachibot API server."""
    from cachibot.api.server import run_server as _run_server

    _run_server(host=host, port=port)
