"""
Encryption Service for Cachibot

AES-256-GCM encryption with HKDF per-bot key derivation.
Master key sourced from CACHIBOT_MASTER_KEY env var or auto-generated.
"""

import base64
import json
import logging
import os
import secrets
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

logger = logging.getLogger(__name__)

_MASTER_KEY_DIR = Path.home() / ".cachibot"
_MASTER_KEY_FILE = _MASTER_KEY_DIR / "master.key"
_PLATFORM_INFO = b"cachibot-platform-env"


class EncryptionService:
    """AES-256-GCM encryption with per-bot HKDF key derivation."""

    def __init__(self, master_key: bytes | None = None) -> None:
        self._master_key = master_key or self._load_master_key()

    @staticmethod
    def _load_master_key() -> bytes:
        """Load master key from env var or auto-generate and persist."""
        hex_key = os.environ.get("CACHIBOT_MASTER_KEY")
        if hex_key:
            return bytes.fromhex(hex_key)

        # Try reading from file
        if _MASTER_KEY_FILE.exists():
            stored = _MASTER_KEY_FILE.read_text().strip()
            logger.info("Loaded master key from %s", _MASTER_KEY_FILE)
            return bytes.fromhex(stored)

        # Auto-generate
        hex_key = secrets.token_hex(32)
        _MASTER_KEY_DIR.mkdir(parents=True, exist_ok=True)
        _MASTER_KEY_FILE.write_text(hex_key)
        _MASTER_KEY_FILE.chmod(0o600)
        logger.warning(
            "No CACHIBOT_MASTER_KEY set. Auto-generated master key saved to %s. "
            "Back up this file — if lost, all encrypted data is unrecoverable.",
            _MASTER_KEY_FILE,
        )
        return bytes.fromhex(hex_key)

    @staticmethod
    def derive_bot_key(master_key: bytes, bot_id: str, salt: bytes) -> bytes:
        """Derive a per-bot encryption key using HKDF-SHA256."""
        info = f"cachibot-bot-env-{bot_id}".encode() if bot_id else _PLATFORM_INFO
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            info=info,
        )
        return hkdf.derive(master_key)

    def encrypt_value(self, plaintext: str, bot_id: str | None = None) -> tuple[str, str, str]:
        """Encrypt a plaintext string.

        Args:
            plaintext: The value to encrypt.
            bot_id: Bot ID for key derivation. None for platform-level.

        Returns:
            Tuple of (ciphertext_b64, nonce_b64, salt_b64) — all base64-encoded strings.
        """
        salt = os.urandom(32)
        derived = self.derive_bot_key(self._master_key, bot_id or "", salt)
        nonce = os.urandom(12)
        aesgcm = AESGCM(derived)
        aad = (bot_id or "platform").encode()
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), aad)
        return (
            base64.b64encode(ciphertext).decode(),
            base64.b64encode(nonce).decode(),
            base64.b64encode(salt).decode(),
        )

    def decrypt_value(
        self,
        ciphertext_b64: str,
        nonce_b64: str,
        salt_b64: str,
        bot_id: str | None = None,
    ) -> str:
        """Decrypt a base64-encoded ciphertext.

        Args:
            ciphertext_b64: Base64-encoded ciphertext.
            nonce_b64: Base64-encoded nonce.
            salt_b64: Base64-encoded salt.
            bot_id: Bot ID for key derivation. None for platform-level.

        Returns:
            The decrypted plaintext string.
        """
        ciphertext = base64.b64decode(ciphertext_b64)
        nonce = base64.b64decode(nonce_b64)
        salt = base64.b64decode(salt_b64)
        derived = self.derive_bot_key(self._master_key, bot_id or "", salt)
        aesgcm = AESGCM(derived)
        aad = (bot_id or "platform").encode()
        plaintext = aesgcm.decrypt(nonce, ciphertext, aad)
        return plaintext.decode()

    def encrypt_connection_config(self, config: dict[str, Any], bot_id: str) -> dict[str, str]:
        """Encrypt a connection config dict for DB storage.

        Returns a dict with keys: _encrypted, _nonce, _salt.
        """
        plaintext = json.dumps(config)
        ct, nonce, salt = self.encrypt_value(plaintext, bot_id)
        return {"_encrypted": ct, "_nonce": nonce, "_salt": salt}

    def decrypt_connection_config(self, stored: dict[str, Any], bot_id: str) -> dict[str, Any]:
        """Decrypt a connection config dict from DB storage.

        Handles legacy plaintext configs gracefully — if the stored value
        doesn't have encryption markers, returns it as-is.
        """
        if not isinstance(stored, dict):
            return stored

        # Check for encryption markers
        if "_encrypted" in stored and "_nonce" in stored and "_salt" in stored:
            plaintext = self.decrypt_value(
                stored["_encrypted"],
                stored["_nonce"],
                stored["_salt"],
                bot_id,
            )
            result: dict[str, Any] = json.loads(plaintext)
            return result

        # Legacy plaintext — return as-is (will be re-encrypted on next write)
        return stored


# Module-level singleton (lazily initialized)
_instance: EncryptionService | None = None


def get_encryption_service() -> EncryptionService:
    """Get or create the global EncryptionService singleton."""
    global _instance
    if _instance is None:
        _instance = EncryptionService()
    return _instance
