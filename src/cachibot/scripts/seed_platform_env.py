"""Seed platform_environments table from current .env / os.environ.

Reads all PROVIDERS keys defined in the providers route, encrypts them
using the EncryptionService, and inserts into platform_environments.

Idempotent: skips keys that already exist in the table.

Usage:
    python -m cachibot.scripts.seed_platform_env
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid

from sqlalchemy import select

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Provider env var names (from providers.py PROVIDERS dict)
PROVIDER_ENV_KEYS: list[str] = [
    "OPENAI_API_KEY",
    "CLAUDE_API_KEY",
    "GOOGLE_API_KEY",
    "GROQ_API_KEY",
    "GROK_API_KEY",
    "OPENROUTER_API_KEY",
    "MOONSHOT_API_KEY",
    "ZHIPU_API_KEY",
    "MODELSCOPE_API_KEY",
    "STABILITY_API_KEY",
    "ELEVENLABS_API_KEY",
    "AZURE_API_KEY",
    "AZURE_API_ENDPOINT",
    "AZURE_DEPLOYMENT_ID",
    "OLLAMA_ENDPOINT",
    "LMSTUDIO_ENDPOINT",
    "LOCAL_HTTP_ENDPOINT",
]


async def seed_platform_env() -> None:
    """Read provider keys from environment and seed into platform_environments."""
    from cachibot.services.encryption import get_encryption_service
    from cachibot.storage.db import get_session, init_db
    from cachibot.storage.models.env_var import PlatformEnvironment

    await init_db()
    enc = get_encryption_service()

    async for session in get_session():
        # Load existing keys to skip
        result = await session.execute(
            select(PlatformEnvironment.key).where(PlatformEnvironment.platform == "global")
        )
        existing_keys = {row[0] for row in result.all()}

        inserted = 0
        skipped = 0
        for env_key in PROVIDER_ENV_KEYS:
            value = os.environ.get(env_key)
            if not value:
                continue

            if env_key in existing_keys:
                logger.info("SKIP %s (already exists)", env_key)
                skipped += 1
                continue

            ct, nonce, salt = enc.encrypt_value(value)
            row = PlatformEnvironment(
                id=str(uuid.uuid4()),
                platform="global",
                key=env_key,
                value_encrypted=ct,
                nonce=nonce,
                salt=salt,
            )
            session.add(row)
            logger.info("INSERT %s", env_key)
            inserted += 1

        await session.commit()
        logger.info(
            "Seed complete: %d inserted, %d skipped, %d total env vars checked",
            inserted,
            skipped,
            len(PROVIDER_ENV_KEYS),
        )


def main() -> None:
    asyncio.run(seed_platform_env())


if __name__ == "__main__":
    main()
