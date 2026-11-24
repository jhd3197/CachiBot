"""Repository for bot computers: one Vela container row per bot."""

from datetime import datetime, timezone

from sqlalchemy import select

from cachibot.models.computer import ComputerRecord, ComputerState
from cachibot.storage.base import BaseRepository
from cachibot.storage.models.computer import BotComputer as BotComputerModel
from cachibot.storage.models.computer import ensure_aware


class ComputerRepository(BaseRepository[BotComputerModel, ComputerRecord]):
    """Repository for per-bot computer rows."""

    _model = BotComputerModel

    def _row_to_entity(self, row: BotComputerModel) -> ComputerRecord:
        return ComputerRecord(
            bot_id=row.bot_id,
            state=ComputerState(row.state),
            container_name=row.container_name,
            host_port=row.host_port,
            image_tag=row.image_tag,
            vela_version=row.vela_version,
            last_active_at=ensure_aware(row.last_active_at),
            last_error=row.last_error,
            created_at=ensure_aware(row.created_at) or datetime.now(timezone.utc),
            updated_at=ensure_aware(row.updated_at) or datetime.now(timezone.utc),
        )

    async def get_for_bot(self, bot_id: str) -> ComputerRecord | None:
        """Fetch the computer row for a bot (bot_id is the primary key)."""
        return await self._fetch_one(select(self._model).where(self._model.bot_id == bot_id))

    async def list_all(self) -> list[ComputerRecord]:
        """Fetch all computer rows (idle loop and startup reconcile)."""
        return await self._fetch_all(select(self._model))

    async def list_with_state(self, state: ComputerState) -> list[ComputerRecord]:
        """Fetch all rows in the given state."""
        return await self._fetch_all(select(self._model).where(self._model.state == state.value))

    async def upsert(self, record: ComputerRecord) -> None:
        """Insert or update the row for ``record.bot_id``."""
        async with self._session() as session:
            row = await session.get(self._model, record.bot_id)
            if row is None:
                session.add(
                    BotComputerModel(
                        bot_id=record.bot_id,
                        state=record.state.value,
                        container_name=record.container_name,
                        host_port=record.host_port,
                        image_tag=record.image_tag,
                        vela_version=record.vela_version,
                        last_active_at=record.last_active_at,
                        last_error=record.last_error,
                        created_at=record.created_at,
                        updated_at=record.updated_at,
                    )
                )
            else:
                row.state = record.state.value
                row.container_name = record.container_name
                row.host_port = record.host_port
                row.image_tag = record.image_tag
                row.vela_version = record.vela_version
                row.last_active_at = record.last_active_at
                row.last_error = record.last_error
                row.updated_at = datetime.now(timezone.utc)
            await session.commit()
