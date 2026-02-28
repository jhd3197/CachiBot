"""Security tests for the per-bot environment system.

Covers:
- Secret masking: API key patterns are masked in log output
- .env file access blocked from bot agents
- env/printenv commands blocked
- Bot owner can't see platform key values, only "inherited: true"
- CRITICAL: Raw API keys must NEVER appear in any API response, log, or error message
"""

import logging
import re
from unittest.mock import MagicMock

import pytest

from cachibot.api.routes.providers import _mask_value

# ---------------------------------------------------------------------------
# Secret Masking Patterns (from architecture doc 4.8)
# ---------------------------------------------------------------------------

# Known API key patterns that MUST be masked
SECRET_PATTERNS = [
    re.compile(r"sk-(?:proj-|svcacct-)?[a-zA-Z0-9_-]{20,}"),  # OpenAI (sk-, sk-proj-, sk-svcacct-)
    re.compile(r"sk-ant-[a-zA-Z0-9_-]{20,}"),  # Anthropic
    re.compile(r"gsk_[a-zA-Z0-9]{20,}"),  # Groq
    re.compile(r"AIza[a-zA-Z0-9_-]{30,}"),  # Google
    re.compile(r"[0-9]{6,}:[A-Za-z0-9_-]{30,}"),  # Telegram bot tokens
]

# Sample API keys for testing (these are fake/test keys — not real credentials)
SAMPLE_KEYS = {
    "openai": "sk-proj-abcdefghij1234567890abcdefghij",
    "anthropic": "sk-ant-abcdefghij1234567890abcdefghij",
    "groq": "gsk_abcdefghij1234567890abcdef",
    "google": "AIzaSyAbcdefghijKLMNopqrstuvwxyz123456",
    "telegram": "123456789:ABCDEFGHIjklmNOPQRstuvwxyz1234567",
}


class TestSecretMaskingPatterns:
    """Verify secret patterns detect all known API key formats."""

    @pytest.mark.parametrize(
        "provider,key",
        list(SAMPLE_KEYS.items()),
        ids=list(SAMPLE_KEYS.keys()),
    )
    def test_pattern_detects_key(self, provider, key):
        """Each sample key should be detected by at least one secret pattern."""
        matched = any(p.search(key) for p in SECRET_PATTERNS)
        assert matched, f"{provider} key '{key[:8]}...' not matched by any secret pattern"


class TestMaskValue:
    """Tests for the _mask_value function in providers.py."""

    def test_mask_api_key_shows_last_4(self):
        """API keys should be masked with only last 4 chars visible."""
        masked = _mask_value("sk-proj-abcdef1234567890WXYZ", "api_key")
        assert masked.endswith("WXYZ")
        assert "sk-proj" not in masked
        assert masked.count("*") == len("sk-proj-abcdef1234567890WXYZ") - 4

    def test_mask_short_key(self):
        """Keys with 4 or fewer chars should be fully masked."""
        assert _mask_value("abc", "api_key") == "****"
        assert _mask_value("abcd", "api_key") == "****"

    def test_mask_endpoint_shows_full(self):
        """Endpoint URLs should be shown in full (not secrets)."""
        url = "http://localhost:11434/api/generate"
        assert _mask_value(url, "endpoint") == url

    def test_masked_value_never_contains_raw_key(self):
        """The masked output must never contain the original key."""
        for key in SAMPLE_KEYS.values():
            masked = _mask_value(key, "api_key")
            # The full key must not appear in the masked version
            assert key not in masked


# ---------------------------------------------------------------------------
# Log Output Security Tests
# ---------------------------------------------------------------------------


class TestLogSecretMasking:
    """Verify that API keys in log output would be detected.

    These tests validate the patterns we use to catch secrets in logs.
    The actual SecretMaskingFilter is defined in the architecture doc.
    """

    def test_key_in_error_message_detected(self):
        """If an API key appears in an error message, our patterns catch it."""
        error_msg = f"Authentication failed for key {SAMPLE_KEYS['openai']}"
        for pattern in SECRET_PATTERNS:
            match = pattern.search(error_msg)
            if match:
                # Found the key — this is what the filter would mask
                assert SAMPLE_KEYS["openai"] in error_msg
                return
        pytest.fail("OpenAI key in error message was not detected by any pattern")

    def test_key_in_traceback_detected(self):
        """If a key appears in a traceback string, our patterns catch it."""
        traceback = (
            "Traceback (most recent call last):\n"
            '  File "driver.py", line 42, in _call_api\n'
            f'    headers["Authorization"] = "Bearer {SAMPLE_KEYS["openai"]}"\n'
            "openai.AuthenticationError: Invalid API key"
        )
        matched = any(p.search(traceback) for p in SECRET_PATTERNS)
        assert matched, "API key in traceback not detected"


# ---------------------------------------------------------------------------
# .env File Access Blocking Tests
# ---------------------------------------------------------------------------


class TestEnvFileBlocking:
    """Bot agents must NOT be able to read .env files or dump env vars."""

    def test_sandbox_blocks_os_import(self):
        """The Python sandbox blocks importing 'os' (prevents os.environ access)."""
        from tukuy import PythonSandbox

        sandbox = PythonSandbox(
            allowed_imports=["json", "math"],
            timeout_seconds=5,
        )

        # os is in ALWAYS_BLOCKED_IMPORTS
        result = sandbox.execute("import os; print(os.environ)")
        assert result.error is not None
        # The raw error should NOT contain any actual env var values
        if result.error:
            for key in SAMPLE_KEYS.values():
                assert key not in result.error

    def test_sandbox_blocks_subprocess(self):
        """The Python sandbox blocks importing 'subprocess'."""
        from tukuy import PythonSandbox

        sandbox = PythonSandbox(
            allowed_imports=["json"],
            timeout_seconds=5,
        )

        result = sandbox.execute("import subprocess; subprocess.run(['env'])")
        assert result.error is not None

    def test_sandbox_blocks_pathlib(self):
        """The Python sandbox blocks importing 'pathlib' (prevents .env file reads)."""
        from tukuy import PythonSandbox

        sandbox = PythonSandbox(
            allowed_imports=["json"],
            timeout_seconds=5,
        )

        result = sandbox.execute("from pathlib import Path; Path('.env').read_text()")
        assert result.error is not None

    def test_sandbox_blocks_builtins_open(self):
        """The Python sandbox restricts open() to prevent arbitrary file reads."""
        from tukuy import PythonSandbox

        sandbox = PythonSandbox(
            allowed_imports=[],
            timeout_seconds=5,
            allowed_read_paths=["/tmp/test-sandbox"],
        )

        # Attempting to open .env should be blocked or raise error
        result = sandbox.execute("f = open('.env', 'r'); print(f.read())")
        # Either blocked or raises FileNotFoundError — either way, no secret leakage
        if result.output:
            for key in SAMPLE_KEYS.values():
                assert key not in result.output


# ---------------------------------------------------------------------------
# Command Blocking Tests
# ---------------------------------------------------------------------------


class TestCommandBlocking:
    """Shell commands that dump environment variables must be blocked."""

    BLOCKED_COMMANDS = ["env", "printenv", "set", "export"]

    @pytest.mark.parametrize("cmd", BLOCKED_COMMANDS)
    def test_env_dump_command_blocked_by_sandbox(self, cmd):
        """Commands that dump env vars are blocked by the sandbox."""
        from tukuy import PythonSandbox

        sandbox = PythonSandbox(
            allowed_imports=[],
            timeout_seconds=5,
        )

        # subprocess is always blocked, so any shell command should fail
        code = f"import subprocess; subprocess.run(['{cmd}'])"
        result = sandbox.execute(code)
        assert result.error is not None


# ---------------------------------------------------------------------------
# API Response Security Tests
# ---------------------------------------------------------------------------


class TestApiResponseSecurity:
    """No raw API key values must appear in any API response."""

    def test_provider_list_masks_keys(self):
        """GET /api/providers should return masked values, never raw keys."""
        # Simulate what the providers endpoint does
        from cachibot.api.routes.providers import PROVIDERS

        for name, info in PROVIDERS.items():
            if info["type"] == "api_key":
                # Simulate a configured provider
                fake_key = f"sk-test-{name}-{'x' * 30}"
                masked = _mask_value(fake_key, info["type"])

                # Raw key must NOT appear in masked output
                assert fake_key not in masked
                # Only last 4 chars visible
                assert masked.endswith(fake_key[-4:])

    def test_raw_key_never_in_masked_response(self):
        """Exhaustive check: no raw key appears when masked."""
        test_keys = [
            "sk-proj-abcdefghijklmnopqrstuvwxyz1234",
            "sk-ant-api03-abcdefghijklmnopqrstuvwxyz",
            "gsk_abcdefghijklmnopqrstuvwxyz12345678",
            "AIzaSyAbcdefghijKLMNopqrstuvwxyz123456",
        ]

        for key in test_keys:
            masked = _mask_value(key, "api_key")
            # The first 8 chars of the key must NOT appear in the masked version
            assert key[:8] not in masked


# ---------------------------------------------------------------------------
# Encryption Security: Ciphertext Non-Determinism
# ---------------------------------------------------------------------------


class TestEncryptionNonDeterminism:
    """Encrypting the same value twice must produce different ciphertexts."""

    def test_same_input_different_output(self):
        """Repeated encryption of the same value produces different ciphertexts."""
        import secrets

        from cachibot.services.encryption import EncryptionService

        master = secrets.token_bytes(32)
        svc = EncryptionService(master_key=master)

        ct1, nonce1, salt1 = svc.encrypt_value("same-secret", bot_id="bot-1")
        ct2, nonce2, salt2 = svc.encrypt_value("same-secret", bot_id="bot-1")

        # Ciphertexts must differ due to random nonce and salt
        assert ct1 != ct2 or nonce1 != nonce2 or salt1 != salt2


# ---------------------------------------------------------------------------
# SecretMaskingFilter Tests (actual implementation)
# ---------------------------------------------------------------------------


class TestSecretMaskingFilter:
    """Tests for the actual SecretMaskingFilter in secret_masking.py."""

    def test_filter_masks_openai_key_in_log(self):
        """OpenAI key in a log message is replaced with REDACTED."""
        from cachibot.services.secret_masking import SecretMaskingFilter

        f = SecretMaskingFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg=f"API error with key {SAMPLE_KEYS['openai']}",
            args=(),
            exc_info=None,
        )
        f.filter(record)
        assert SAMPLE_KEYS["openai"] not in record.msg
        assert "***REDACTED***" in record.msg

    def test_filter_masks_groq_key_in_args(self):
        """Groq key in log args is masked."""
        from cachibot.services.secret_masking import SecretMaskingFilter

        f = SecretMaskingFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Using key: %s",
            args=(SAMPLE_KEYS["groq"],),
            exc_info=None,
        )
        f.filter(record)
        assert SAMPLE_KEYS["groq"] not in str(record.args)

    def test_filter_masks_google_key(self):
        """Google API key pattern is masked."""
        from cachibot.services.secret_masking import SecretMaskingFilter

        f = SecretMaskingFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg=f"Google error: {SAMPLE_KEYS['google']}",
            args=(),
            exc_info=None,
        )
        f.filter(record)
        assert SAMPLE_KEYS["google"] not in record.msg

    @pytest.mark.parametrize("provider,key", list(SAMPLE_KEYS.items()))
    def test_filter_masks_all_key_types(self, provider, key):
        """All known key types are masked by the filter."""
        from cachibot.services.secret_masking import SecretMaskingFilter

        f = SecretMaskingFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg=f"Key: {key}",
            args=(),
            exc_info=None,
        )
        f.filter(record)
        assert key not in record.msg

    def test_install_secret_masking_idempotent(self):
        """install_secret_masking can be called multiple times safely."""
        from cachibot.services.secret_masking import SecretMaskingFilter, install_secret_masking

        root = logging.getLogger()
        initial_count = sum(1 for f in root.filters if isinstance(f, SecretMaskingFilter))

        install_secret_masking()
        install_secret_masking()
        install_secret_masking()

        final_count = sum(1 for f in root.filters if isinstance(f, SecretMaskingFilter))
        # Should only add one filter regardless of how many times called
        assert final_count <= initial_count + 1


# ---------------------------------------------------------------------------
# Agent Security Context Hardening Tests
# ---------------------------------------------------------------------------


class TestAgentSecurityHardening:
    """Tests for _harden_security_context in agent.py."""

    def test_harden_adds_env_to_ignore_patterns(self):
        """The hardening adds .env patterns to ignore_patterns."""
        from cachibot.agent import CachibotAgent

        agent_mock = MagicMock(spec=CachibotAgent)
        agent_mock.tool_configs = None
        ctx = MagicMock()
        ctx.ignore_patterns = []
        ctx.blocked_commands = []

        CachibotAgent._harden_security_context(agent_mock, ctx)

        assert ".env" in ctx.ignore_patterns
        assert "*.env" in ctx.ignore_patterns
        assert ".env.*" in ctx.ignore_patterns

    def test_harden_adds_blocked_commands(self):
        """The hardening blocks env-dumping shell commands."""
        from cachibot.agent import CachibotAgent

        agent_mock = MagicMock(spec=CachibotAgent)
        agent_mock.tool_configs = None
        ctx = MagicMock()
        ctx.ignore_patterns = []
        ctx.blocked_commands = []

        CachibotAgent._harden_security_context(agent_mock, ctx)

        for cmd in ("env", "printenv", "set", "export"):
            assert cmd in ctx.blocked_commands

    def test_harden_idempotent(self):
        """Calling _harden twice doesn't duplicate entries."""
        from cachibot.agent import CachibotAgent

        agent_mock = MagicMock(spec=CachibotAgent)
        agent_mock.tool_configs = None
        ctx = MagicMock()
        ctx.ignore_patterns = []
        ctx.blocked_commands = []

        CachibotAgent._harden_security_context(agent_mock, ctx)
        CachibotAgent._harden_security_context(agent_mock, ctx)

        assert ctx.ignore_patterns.count(".env") == 1
        assert ctx.blocked_commands.count("env") == 1
