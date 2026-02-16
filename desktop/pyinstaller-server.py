"""
Standalone entry point for PyInstaller-bundled CachiBot server.

This is used instead of the CLI entry point to avoid bundling Typer/Rich
and to keep the binary focused on just the server functionality.
"""

import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="CachiBot Desktop Server")
    parser.add_argument("--port", type=int, default=6392, help="Server port")
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    args = parser.parse_args()

    # Import here so PyInstaller can trace dependencies
    from cachibot.api.server import create_app
    import uvicorn

    app = create_app(workspace=Path.home())

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
