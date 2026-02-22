"""Shared .env file read/write utilities for API routes."""

from __future__ import annotations

import os
import re

from cachibot.api.env import get_env_path


def read_env_file() -> str:
    """Read the .env file contents, return empty string if missing."""
    env_path = get_env_path()
    if env_path.exists():
        return env_path.read_text(encoding="utf-8")
    return ""


def write_env_file(content: str) -> None:
    """Write content to the .env file."""
    get_env_path().write_text(content, encoding="utf-8")


def set_env_value(key: str, value: str) -> None:
    """Set a key=value in the .env file, preserving comments and formatting."""
    content = read_env_file()
    pattern = re.compile(rf"^#?\s*{re.escape(key)}\s*=.*$", re.MULTILINE)
    replacement = f"{key}={value}"

    if pattern.search(content):
        content = pattern.sub(replacement, content, count=1)
    else:
        if content and not content.endswith("\n"):
            content += "\n"
        content += f"{replacement}\n"

    write_env_file(content)
    os.environ[key] = value


def remove_env_value(key: str) -> None:
    """Comment out a key in the .env file and remove from os.environ."""
    content = read_env_file()
    pattern = re.compile(rf"^{re.escape(key)}\s*=.*$", re.MULTILINE)
    content = pattern.sub(f"# {key}=", content)
    write_env_file(content)
    os.environ.pop(key, None)
