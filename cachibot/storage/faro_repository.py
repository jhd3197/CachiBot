"""Repository for bot Faro connections: one opt-in row per bot."""

from datetime import datetime, timezone

from sqlalchemy import select

from cachibot.storage.base import BaseRepository
from cachibot.storage.models.faro import BotFaroConnection as BotFaroConnectionModel


class FaroRepository(BaseRepository[BotFaroConnectionModel, bool]):
    """Repository for the per-bot Faro connection flag.

    The only persisted state is the non-secret ``connected`` boolean, so the
    entity type is the bool itself.
    """

    _model = BotFaroConnectionModel

    def _row_to_entity(self, row: BotFaroConnectionModel) -> bool:
        return bool(row.connected)

    async def is_connected(self, bot_id: str) -> bool:
        """Whether the bot's Faro connection is enabled (False when no row)."""
        return bool(await self._fetch_one(select(self._model).where(self._model.bot_id == bot_id)))

    async def list_connected(self) -> list[str]:
        """All bot ids with the connection enabled (service warm-start)."""
        async with self._session() as session:
            result = await session.execute(select(self._model.bot_id).where(self._model.connected))
            return [str(bot_id) for bot_id in result.scalars().all()]

    async def set_connected(self, bot_id: str, connected: bool) -> None:
        """Insert or update the bot's connection flag."""
        async with self._session() as session:
            row = await session.get(self._model, bot_id)
            if row is None:
                session.add(
                    BotFaroConnectionModel(
                        bot_id=bot_id,
                        connected=connected,
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                    )
                )
            else:
                row.connected = connected
                row.updated_at = datetime.now(timezone.utc)
            await session.commit()
