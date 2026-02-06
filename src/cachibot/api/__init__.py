"""
Cachibot API Server

FastAPI backend with WebSocket support for real-time streaming.
"""

from cachibot.api.server import create_app, run_server

__all__ = ["create_app", "run_server"]
