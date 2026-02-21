"""
Repository classes for Developer API key and webhook data access.

Provides async CRUD operations following the existing repository pattern.
"""

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select, update

from cachibot.storage import db
from cachibot.storage.models.developer import BotApiKey, BotWebhook


class ApiKeyRepository:
    """Repository for bot API key operations."""

    async def create_key(
        self,
        *,
        id: str,
        bot_id: str,
        name: str,
        key_prefix: str,
        key_hash: str,
        created_by: str,
        expires_at: datetime | None = None,
    ) -> None:
        """Create a new API key record (store only the hash)."""
        async with db.ensure_initialized()() as session:
            obj = BotApiKey(
                id=id,
                bot_id=bot_id,
                name=name,
                key_prefix=key_prefix,
                key_hash=key_hash,
                created_by=created_by,
                expires_at=expires_at,
            )
            session.add(obj)
            await session.commit()

    async def get_key_by_hash(self, key_hash: str) -> BotApiKey | None:
        """Look up an API key by its SHA-256 hash."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(select(BotApiKey).where(BotApiKey.key_hash == key_hash))
            return result.scalar_one_or_none()

    async def get_keys_for_bot(self, bot_id: str) -> list[BotApiKey]:
        """Get all API keys for a bot (prefix only, no hash exposed)."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(BotApiKey)
                .where(BotApiKey.bot_id == bot_id)
                .order_by(BotApiKey.created_at.desc())
            )
            return list(result.scalars().all())

    async def revoke_key(self, key_id: str) -> bool:
        """Revoke an API key. Returns True if found."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                update(BotApiKey).where(BotApiKey.id == key_id).values(is_revoked=True)
            )
            await session.commit()
            return bool(result.rowcount > 0)  # type: ignore[attr-defined]

    async def delete_key(self, key_id: str) -> bool:
        """Permanently delete an API key. Returns True if found."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(delete(BotApiKey).where(BotApiKey.id == key_id))
            await session.commit()
            return bool(result.rowcount > 0)  # type: ignore[attr-defined]

    async def record_usage(self, key_id: str) -> None:
        """Increment usage count and update last_used_at timestamp."""
        async with db.ensure_initialized()() as session:
            await session.execute(
                update(BotApiKey)
                .where(BotApiKey.id == key_id)
                .values(
                    usage_count=BotApiKey.usage_count + 1,
                    last_used_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()


class WebhookRepository:
    """Repository for bot webhook operations."""

    async def create_webhook(
        self,
        *,
        id: str,
        bot_id: str,
        name: str,
        url: str,
        secret: str | None = None,
        events: list[str] | None = None,
        created_by: str,
    ) -> None:
        """Create a new webhook."""
        async with db.ensure_initialized()() as session:
            obj = BotWebhook(
                id=id,
                bot_id=bot_id,
                name=name,
                url=url,
                secret=secret,
                events=json.dumps(events or []),
                created_by=created_by,
            )
            session.add(obj)
            await session.commit()

    async def get_webhooks_for_bot(self, bot_id: str) -> list[BotWebhook]:
        """Get all webhooks for a bot."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(BotWebhook)
                .where(BotWebhook.bot_id == bot_id)
                .order_by(BotWebhook.created_at.desc())
            )
            return list(result.scalars().all())

    async def get_webhook(self, webhook_id: str) -> BotWebhook | None:
        """Get a single webhook by ID."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(select(BotWebhook).where(BotWebhook.id == webhook_id))
            return result.scalar_one_or_none()

    async def update_webhook(
        self,
        webhook_id: str,
        *,
        name: str | None = None,
        url: str | None = None,
        secret: str | None = None,
        events: list[str] | None = None,
        is_active: bool | None = None,
    ) -> bool:
        """Update webhook fields. Returns True if found."""
        values: dict[str, Any] = {}
        if name is not None:
            values["name"] = name
        if url is not None:
            values["url"] = url
        if secret is not None:
            values["secret"] = secret
        if events is not None:
            values["events"] = json.dumps(events)
        if is_active is not None:
            values["is_active"] = is_active

        if not values:
            return True

        async with db.ensure_initialized()() as session:
            result = await session.execute(
                update(BotWebhook).where(BotWebhook.id == webhook_id).values(**values)
            )
            await session.commit()
            return bool(result.rowcount > 0)  # type: ignore[attr-defined]

    async def delete_webhook(self, webhook_id: str) -> bool:
        """Delete a webhook. Returns True if found."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(delete(BotWebhook).where(BotWebhook.id == webhook_id))
            await session.commit()
            return bool(result.rowcount > 0)  # type: ignore[attr-defined]

    async def get_active_webhooks_for_event(self, bot_id: str, event: str) -> list[BotWebhook]:
        """Get all active webhooks for a bot that subscribe to a specific event."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(BotWebhook).where(
                    BotWebhook.bot_id == bot_id,
                    BotWebhook.is_active.is_(True),
                    BotWebhook.failure_count < 10,
                )
            )
            rows = list(result.scalars().all())

        # Filter by event subscription (events stored as JSON list)
        matching = []
        for wh in rows:
            try:
                subscribed = json.loads(wh.events) if wh.events else []
            except (json.JSONDecodeError, TypeError):
                subscribed = []
            if event in subscribed:
                matching.append(wh)
        return matching

    async def record_failure(self, webhook_id: str) -> None:
        """Increment failure count for a webhook."""
        async with db.ensure_initialized()() as session:
            await session.execute(
                update(BotWebhook)
                .where(BotWebhook.id == webhook_id)
                .values(failure_count=BotWebhook.failure_count + 1)
            )
            await session.commit()

    async def record_success(self, webhook_id: str) -> None:
        """Reset failure count and update last_triggered_at on successful delivery."""
        async with db.ensure_initialized()() as session:
            await session.execute(
                update(BotWebhook)
                .where(BotWebhook.id == webhook_id)
                .values(
                    failure_count=0,
                    last_triggered_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()
