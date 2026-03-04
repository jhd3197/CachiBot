"""
Standalone entry point for PyInstaller-bundled CachiBot CLI.

Lean terminal-only binary — no server, database, or platform dependencies.
"""


def main():
    from cachibot.cli import app

    app()


if __name__ == "__main__":
    main()
