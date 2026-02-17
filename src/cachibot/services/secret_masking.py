"""
Secret Masking Filter for Logging

Prevents accidental leakage of API keys and tokens in log output.
Registered on the root logger at application startup.
"""

import logging
import re

# Patterns for known secret formats
_SECRET_PATTERNS = [
    re.compile(r"sk-(?:proj-|svcacct-)?[a-zA-Z0-9_-]{20,}"),  # OpenAI (sk-, sk-proj-, sk-svcacct-)
    re.compile(r"sk-ant-[a-zA-Z0-9_-]{20,}"),  # Anthropic
    re.compile(r"gsk_[a-zA-Z0-9]{20,}"),  # Groq
    re.compile(r"AIza[a-zA-Z0-9_-]{30,}"),  # Google
    re.compile(r"[0-9]{6,}:[A-Za-z0-9_-]{30,}"),  # Telegram bot tokens
]

_REPLACEMENT = "***REDACTED***"


class SecretMaskingFilter(logging.Filter):
    """Logging filter that masks known secret patterns in log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _mask(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: _mask(v) if isinstance(v, str) else v for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(_mask(a) if isinstance(a, str) else a for a in record.args)
        return True


def _mask(text: str) -> str:
    """Replace all known secret patterns in text."""
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(_REPLACEMENT, text)
    return text


def install_secret_masking() -> None:
    """Install the SecretMaskingFilter on the root logger."""
    root = logging.getLogger()
    # Avoid duplicate installation
    if not any(isinstance(f, SecretMaskingFilter) for f in root.filters):
        root.addFilter(SecretMaskingFilter())
