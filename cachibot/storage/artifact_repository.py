"""Repository for the server-side artifact store."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from cachibot.models.artifact import Artifact, ArtifactType
from cachibot.storage.base import BaseRepository
from cachibot.storage.models.artifact import Artifact as ArtifactModel


class ArtifactRepository(BaseRepository[ArtifactModel, Artifact]):
    """Repository for artifact CRUD operations."""

    _model = ArtifactModel

    async def get(self, artifact_id: str) -> Artifact | None:
        """Get an artifact by ID."""
        return await self.get_by_id(artifact_id)

    async def list_for_bot(
        self,
        bot_id: str,
        chat_id: str | None = None,
        *,
        artifact_type: str | None = None,
        limit: int = 200,
    ) -> list[Artifact]:
        """List a bot's artifacts (optionally one chat's), recently updated first."""
        stmt = select(ArtifactModel).where(ArtifactModel.bot_id == bot_id)
        if chat_id is not None:
            stmt = stmt.where(ArtifactModel.chat_id == chat_id)
        if artifact_type is not None:
            stmt = stmt.where(ArtifactModel.type == artifact_type)
        stmt = stmt.order_by(ArtifactModel.updated_at.desc()).limit(limit)
        return await self._fetch_all(stmt)

    async def upsert(self, artifact: Artifact) -> Artifact:
        """Create or replace a row, storing the entity's fields as given.

        Used when the agent (re)emits an artifact: the agent's version is
        authoritative, but the stored version never decreases. ``bot_id`` is
        required; chat/message ids and plugin are kept when the new entity
        leaves them empty.
        """
        if not artifact.bot_id:
            raise ValueError("bot_id is required to persist an artifact")
        now = datetime.now(timezone.utc)
        async with self._session() as session:
            row = await session.get(ArtifactModel, artifact.id)
            if row is None:
                row = ArtifactModel(
                    id=artifact.id,
                    bot_id=artifact.bot_id,
                    chat_id=artifact.chat_id,
                    message_id=artifact.message_id,
                    type=artifact.type.value,
                    title=artifact.title,
                    content=artifact.content,
                    language=artifact.language,
                    plugin=artifact.plugin,
                    version=max(artifact.version, 1),
                    metadata_json=artifact.metadata or {},
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
            else:
                row.chat_id = artifact.chat_id or row.chat_id
                row.message_id = artifact.message_id or row.message_id
                row.type = artifact.type.value
                row.title = artifact.title
                row.content = artifact.content
                row.language = artifact.language
                row.plugin = artifact.plugin or row.plugin
                row.version = max(row.version, artifact.version)
                row.metadata_json = artifact.metadata or row.metadata_json
                row.updated_at = now
            await session.commit()
            return self._row_to_entity(row)

    async def save_edited(self, candidate: Artifact) -> Artifact:
        """Create or replace a row with the manual-edit version policy.

        An existing row's version is bumped by exactly 1 (the client's
        version is never used as the new version, and the stored version
        never decreases). A missing row is upserted — artifacts created
        before the server store only live in the browser — seeded at
        ``candidate.version + 1``.
        """
        if not candidate.bot_id:
            raise ValueError("bot_id is required to persist an artifact")
        now = datetime.now(timezone.utc)
        async with self._session() as session:
            row = await session.get(ArtifactModel, candidate.id)
            if row is None:
                row = ArtifactModel(
                    id=candidate.id,
                    bot_id=candidate.bot_id,
                    chat_id=candidate.chat_id,
                    message_id=candidate.message_id,
                    type=candidate.type.value,
                    title=candidate.title,
                    content=candidate.content,
                    language=candidate.language,
                    plugin=candidate.plugin,
                    version=max(candidate.version, 0) + 1,
                    metadata_json=candidate.metadata or {},
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
            else:
                row.chat_id = candidate.chat_id or row.chat_id
                row.message_id = candidate.message_id or row.message_id
                row.type = candidate.type.value
                row.title = candidate.title
                row.content = candidate.content
                row.language = candidate.language
                row.plugin = candidate.plugin or row.plugin
                row.metadata_json = candidate.metadata or row.metadata_json
                row.version = row.version + 1
                row.updated_at = now
            await session.commit()
            return self._row_to_entity(row)

    async def apply_update(
        self,
        artifact_id: str,
        *,
        content: str | None = None,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
        version: int | None = None,
    ) -> Artifact | None:
        """Apply a partial agent update; None when the row does not exist.

        Mirrors the client's artifact_update handling: metadata is merged,
        an explicit version is honored but never lowers the stored one, and
        a content change without an explicit version bumps the stored one.
        """
        async with self._session() as session:
            row = await session.get(ArtifactModel, artifact_id)
            if row is None:
                return None
            if content is not None:
                row.content = content
                row.version = max(row.version, version) if version is not None else row.version + 1
            elif version is not None:
                row.version = max(row.version, version)
            if title is not None:
                row.title = title
            if metadata is not None:
                row.metadata_json = {**row.metadata_json, **metadata}
            row.updated_at = datetime.now(timezone.utc)
            await session.commit()
            return self._row_to_entity(row)

    def _row_to_entity(self, row: ArtifactModel) -> Artifact:
        """Convert a database row to an Artifact entity."""
        try:
            artifact_type = ArtifactType(row.type)
        except ValueError:
            # Rows written from free-form plugin types stay readable.
            artifact_type = ArtifactType.CUSTOM
        return Artifact(
            id=row.id,
            type=artifact_type,
            title=row.title,
            content=row.content,
            language=row.language,
            metadata=row.metadata_json if row.metadata_json else {},
            plugin=row.plugin,
            version=row.version,
            bot_id=row.bot_id,
            chat_id=row.chat_id,
            message_id=row.message_id,
        )
