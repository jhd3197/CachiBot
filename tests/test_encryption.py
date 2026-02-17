"""Tests for the EncryptionService — AES-256-GCM with HKDF per-bot key derivation.

Covers:
- Encrypt -> store -> decrypt roundtrip
- Different bot_ids produce different ciphertexts for the same plaintext
- Invalid master key fails to decrypt
- Master key auto-generation when not set
- Platform-level (bot_id=None) encryption
- Connection config encryption/decryption
"""

import os
import secrets
from unittest.mock import patch

import pytest
from cryptography.exceptions import InvalidTag

from cachibot.services.encryption import EncryptionService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _random_master_key() -> bytes:
    """Generate a fresh random 32-byte master key."""
    return secrets.token_bytes(32)


# ---------------------------------------------------------------------------
# Roundtrip Tests
# ---------------------------------------------------------------------------


class TestEncryptionRoundtrip:
    """Encrypt a value, then decrypt it — should match the original."""

    def test_roundtrip_basic(self):
        master = _random_master_key()
        svc = EncryptionService(master_key=master)
        original = "sk-test-key-1234567890abcdef"
        ct, nonce, salt = svc.encrypt_value(original, bot_id="bot-1")
        decrypted = svc.decrypt_value(ct, nonce, salt, bot_id="bot-1")
        assert decrypted == original

    def test_roundtrip_empty_string(self):
        master = _random_master_key()
        svc = EncryptionService(master_key=master)
        ct, nonce, salt = svc.encrypt_value("", bot_id="bot-1")
        assert svc.decrypt_value(ct, nonce, salt, bot_id="bot-1") == ""

    def test_roundtrip_unicode(self):
        master = _random_master_key()
        svc = EncryptionService(master_key=master)
        original = "clave-secreta-\u00e9special-\U0001f510"
        ct, nonce, salt = svc.encrypt_value(original, bot_id="bot-1")
        assert svc.decrypt_value(ct, nonce, salt, bot_id="bot-1") == original

    def test_roundtrip_long_value(self):
        master = _random_master_key()
        svc = EncryptionService(master_key=master)
        original = "A" * 10_000
        ct, nonce, salt = svc.encrypt_value(original, bot_id="bot-1")
        assert svc.decrypt_value(ct, nonce, salt, bot_id="bot-1") == original

    def test_roundtrip_platform_level(self):
        """Platform-level encryption (bot_id=None) should roundtrip correctly."""
        master = _random_master_key()
        svc = EncryptionService(master_key=master)
        original = "sk-platform-global-key"
        ct, nonce, salt = svc.encrypt_value(original, bot_id=None)
        assert svc.decrypt_value(ct, nonce, salt, bot_id=None) == original


# ---------------------------------------------------------------------------
# Per-Bot Isolation Tests
# ---------------------------------------------------------------------------


class TestPerBotIsolation:
    """Different bot_ids must produce different ciphertexts for the same plaintext."""

    def test_different_bots_different_ciphertext(self):
        master = _random_master_key()
        svc = EncryptionService(master_key=master)
        plaintext = "sk-shared-key-value"

        ct_a, nonce_a, salt_a = svc.encrypt_value(plaintext, bot_id="bot-a")
        ct_b, nonce_b, salt_b = svc.encrypt_value(plaintext, bot_id="bot-b")

        # Ciphertexts must differ (different salt + derived key + nonce)
        assert ct_a != ct_b

    def test_cross_bot_decrypt_fails(self):
        """Ciphertext encrypted for bot-a cannot be decrypted with bot-b's context."""
        master = _random_master_key()
        svc = EncryptionService(master_key=master)
        plaintext = "sk-secret-value"

        ct, nonce, salt = svc.encrypt_value(plaintext, bot_id="bot-a")

        with pytest.raises(InvalidTag):
            svc.decrypt_value(ct, nonce, salt, bot_id="bot-b")

    def test_bot_vs_platform_decrypt_fails(self):
        """Ciphertext encrypted for a bot cannot be decrypted at platform level."""
        master = _random_master_key()
        svc = EncryptionService(master_key=master)
        plaintext = "sk-secret-value"

        ct, nonce, salt = svc.encrypt_value(plaintext, bot_id="bot-x")

        with pytest.raises(InvalidTag):
            svc.decrypt_value(ct, nonce, salt, bot_id=None)


# ---------------------------------------------------------------------------
# Invalid Key Tests
# ---------------------------------------------------------------------------


class TestInvalidMasterKey:
    """An invalid or different master key must fail to decrypt."""

    def test_wrong_master_key_fails(self):
        key_a = _random_master_key()
        key_b = _random_master_key()
        svc_a = EncryptionService(master_key=key_a)
        svc_b = EncryptionService(master_key=key_b)

        ct, nonce, salt = svc_a.encrypt_value("secret-data", bot_id="bot-1")

        with pytest.raises(InvalidTag):
            svc_b.decrypt_value(ct, nonce, salt, bot_id="bot-1")

    def test_tampered_ciphertext_fails(self):
        master = _random_master_key()
        svc = EncryptionService(master_key=master)

        ct, nonce, salt = svc.encrypt_value("secret", bot_id="bot-1")

        # Tamper with ciphertext by flipping a character
        import base64

        raw = bytearray(base64.b64decode(ct))
        raw[0] ^= 0xFF
        tampered_ct = base64.b64encode(bytes(raw)).decode()

        with pytest.raises(InvalidTag):
            svc.decrypt_value(tampered_ct, nonce, salt, bot_id="bot-1")


# ---------------------------------------------------------------------------
# Master Key Auto-Generation Tests
# ---------------------------------------------------------------------------


class TestMasterKeyAutoGeneration:
    """When no CACHIBOT_MASTER_KEY is set, the service auto-generates one."""

    def test_auto_generate_creates_key_file(self, tmp_path):
        """If no env var and no key file, a new master key is auto-generated."""
        key_file = tmp_path / "master.key"

        with (
            patch.dict(os.environ, {}, clear=False),
            patch("cachibot.services.encryption._MASTER_KEY_FILE", key_file),
            patch("cachibot.services.encryption._MASTER_KEY_DIR", tmp_path),
        ):
            # Ensure the env var is NOT set
            os.environ.pop("CACHIBOT_MASTER_KEY", None)

            svc = EncryptionService()

            # Key file should now exist
            assert key_file.exists()

            # Should be a valid 32-byte hex string (64 hex chars)
            hex_content = key_file.read_text().strip()
            assert len(hex_content) == 64
            bytes.fromhex(hex_content)  # Should not raise

            # Service should be functional
            ct, nonce, salt = svc.encrypt_value("test", bot_id="bot-1")
            assert svc.decrypt_value(ct, nonce, salt, bot_id="bot-1") == "test"

    def test_loads_existing_key_file(self, tmp_path):
        """If a key file already exists, loads from it."""
        key_file = tmp_path / "master.key"
        known_key = secrets.token_hex(32)
        key_file.write_text(known_key)

        with (
            patch.dict(os.environ, {}, clear=False),
            patch("cachibot.services.encryption._MASTER_KEY_FILE", key_file),
            patch("cachibot.services.encryption._MASTER_KEY_DIR", tmp_path),
        ):
            os.environ.pop("CACHIBOT_MASTER_KEY", None)

            svc = EncryptionService()

            # Encrypt and decrypt should work using the known key
            ct, nonce, salt = svc.encrypt_value("secret", bot_id="bot-1")
            decrypted = svc.decrypt_value(ct, nonce, salt, bot_id="bot-1")
            assert decrypted == "secret"

            # A second instance with the same file should produce compatible results
            svc2 = EncryptionService()
            assert svc2.decrypt_value(ct, nonce, salt, bot_id="bot-1") == "secret"

    def test_env_var_takes_precedence(self, tmp_path):
        """CACHIBOT_MASTER_KEY env var overrides file."""
        key_file = tmp_path / "master.key"
        file_key = secrets.token_hex(32)
        key_file.write_text(file_key)

        env_key = secrets.token_hex(32)

        with (
            patch.dict(os.environ, {"CACHIBOT_MASTER_KEY": env_key}),
            patch("cachibot.services.encryption._MASTER_KEY_FILE", key_file),
        ):
            svc = EncryptionService()

            # Verify the env var key is used (not the file key)
            ct, nonce, salt = svc.encrypt_value("test", bot_id="bot-1")

            # Should decrypt with env key service
            svc_env = EncryptionService(master_key=bytes.fromhex(env_key))
            assert svc_env.decrypt_value(ct, nonce, salt, bot_id="bot-1") == "test"

            # Should NOT decrypt with file key service
            svc_file = EncryptionService(master_key=bytes.fromhex(file_key))
            with pytest.raises(InvalidTag):
                svc_file.decrypt_value(ct, nonce, salt, bot_id="bot-1")


# ---------------------------------------------------------------------------
# Connection Config Encryption Tests
# ---------------------------------------------------------------------------


class TestConnectionConfigEncryption:
    """Tests for encrypt_connection_config / decrypt_connection_config."""

    def test_connection_config_roundtrip(self):
        master = _random_master_key()
        svc = EncryptionService(master_key=master)

        config = {"bot_token": "123456:ABCdefGHIjklmNOPqrsTUVwxyz", "webhook_url": "https://x.com"}
        encrypted = svc.encrypt_connection_config(config, bot_id="bot-1")

        assert "_encrypted" in encrypted
        assert "_nonce" in encrypted
        assert "_salt" in encrypted

        # Raw key must NOT appear in encrypted output
        assert "123456:ABCdefGHIjklmNOPqrsTUVwxyz" not in str(encrypted)

        decrypted = svc.decrypt_connection_config(encrypted, bot_id="bot-1")
        assert decrypted == config

    def test_legacy_plaintext_passthrough(self):
        """Legacy plaintext configs (without encryption markers) are returned as-is."""
        master = _random_master_key()
        svc = EncryptionService(master_key=master)

        legacy_config = {"bot_token": "old-plaintext-token"}
        result = svc.decrypt_connection_config(legacy_config, bot_id="bot-1")
        assert result == legacy_config

    def test_non_dict_passthrough(self):
        """Non-dict values are passed through without error."""
        master = _random_master_key()
        svc = EncryptionService(master_key=master)
        result = svc.decrypt_connection_config("not-a-dict", bot_id="bot-1")
        assert result == "not-a-dict"


# ---------------------------------------------------------------------------
# HKDF Key Derivation Tests
# ---------------------------------------------------------------------------


class TestKeyDerivation:
    """Tests for derive_bot_key determinism and uniqueness."""

    def test_derive_deterministic(self):
        """Same inputs produce the same derived key."""
        master = _random_master_key()
        salt = os.urandom(32)

        key1 = EncryptionService.derive_bot_key(master, "bot-1", salt)
        key2 = EncryptionService.derive_bot_key(master, "bot-1", salt)
        assert key1 == key2

    def test_different_bot_ids_different_keys(self):
        """Different bot_ids produce different derived keys (even with same salt)."""
        master = _random_master_key()
        salt = os.urandom(32)

        key_a = EncryptionService.derive_bot_key(master, "bot-a", salt)
        key_b = EncryptionService.derive_bot_key(master, "bot-b", salt)
        assert key_a != key_b

    def test_different_salts_different_keys(self):
        """Different salts produce different derived keys (same bot_id)."""
        master = _random_master_key()

        key1 = EncryptionService.derive_bot_key(master, "bot-1", os.urandom(32))
        key2 = EncryptionService.derive_bot_key(master, "bot-1", os.urandom(32))
        assert key1 != key2

    def test_derived_key_length(self):
        """Derived key should always be 32 bytes (256 bits)."""
        master = _random_master_key()
        salt = os.urandom(32)
        derived = EncryptionService.derive_bot_key(master, "bot-1", salt)
        assert len(derived) == 32
