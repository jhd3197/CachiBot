"""Server-side artifact store routes.

Artifacts used to live only in the browser (zustand/localStorage), so the
agent's next turn and the Website Builder never saw manual click-to-edit
saves. These routes make the store durable: the client lists artifacts when
a chat opens and PUTs edited content back; website_builder artifacts are
additionally written through to the project's ``index.html`` on disk.

Access: viewers can read; saving requires operator-or-higher (same idea as
the other write-ish bot routes).
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from cachibot.api.auth import require_bot_access, require_bot_access_level
from cachibot.models.artifact import Artifact, ArtifactType
from cachibot.models.auth import User
from cachibot.models.group import BotAccessLevel
from cachibot.services import website_files
from cachibot.storage.artifact_repository import ArtifactRepository

router = APIRouter(tags=["artifacts"])


class ArtifactSaveRequest(BaseModel):
    """Body for saving (edited) artifact content."""

    content: str = Field(description="The full current artifact content")
    title: str | None = None
    type: ArtifactType | None = None
    language: str | None = None
    plugin: str | None = None
    metadata: dict[str, Any] | None = None
    chatId: str | None = None
    messageId: str | None = None
    version: int | None = Field(
        default=None, description="The client's current version (informational only)"
    )


def _artifact_payload(artifact: Artifact) -> dict[str, Any]:
    """Wire shape: camelCase ids matching the frontend Artifact type."""
    return {
        "id": artifact.id,
        "type": artifact.type.value,
        "title": artifact.title,
        "content": artifact.content,
        "language": artifact.language,
        "metadata": artifact.metadata,
        "plugin": artifact.plugin,
        "version": artifact.version,
        "botId": artifact.bot_id,
        "chatId": artifact.chat_id,
        "messageId": artifact.message_id,
    }


@router.get("/api/bots/{bot_id}/artifacts")
async def list_artifacts(
    bot_id: str,
    chat_id: str | None = Query(default=None, alias="chatId"),
    user: User = Depends(require_bot_access),
) -> list[dict[str, Any]]:
    """List the bot's artifacts, optionally scoped to one chat (viewer+)."""
    artifacts = await ArtifactRepository().list_for_bot(bot_id, chat_id=chat_id)
    return [_artifact_payload(a) for a in artifacts]


@router.get("/api/bots/{bot_id}/artifacts/{artifact_id}")
async def get_artifact(
    bot_id: str,
    artifact_id: str,
    user: User = Depends(require_bot_access),
) -> dict[str, Any]:
    """Fetch one artifact (viewer+); 404 when missing or owned by another bot."""
    artifact = await ArtifactRepository().get(artifact_id)
    if artifact is None or artifact.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return _artifact_payload(artifact)


@router.put("/api/bots/{bot_id}/artifacts/{artifact_id}")
async def save_artifact(
    bot_id: str,
    artifact_id: str,
    body: ArtifactSaveRequest,
    user: User = Depends(require_bot_access_level(BotAccessLevel.OPERATOR)),
) -> dict[str, Any]:
    """Save edited artifact content (operator+), bumping the stored version.

    A missing row is upserted: artifacts created before the server store
    only exist in the browser, and their first manual save creates the row.
    The response carries the saved artifact (with the new version) and
    whether a Website Builder file was overwritten.
    """
    repo = ArtifactRepository()
    existing = await repo.get(artifact_id)
    if existing is not None and existing.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Artifact not found")

    candidate = Artifact(
        id=artifact_id,
        bot_id=bot_id,
        chat_id=body.chatId or (existing.chat_id if existing else None),
        message_id=body.messageId or (existing.message_id if existing else None),
        type=body.type or (existing.type if existing else ArtifactType.HTML),
        title=body.title or (existing.title if existing else "Untitled"),
        content=body.content,
        language=body.language
        if body.language is not None
        else (existing.language if existing else None),
        plugin=body.plugin or (existing.plugin if existing else None),
        metadata=body.metadata
        if body.metadata is not None
        else (existing.metadata if existing else {}),
        version=body.version if body.version is not None else (existing.version if existing else 1),
    )
    saved = await repo.save_edited(candidate)

    website_written = website_files.write_edited_html(
        plugin=saved.plugin,
        metadata=saved.metadata,
        content=saved.content,
    )
    return {**_artifact_payload(saved), "websiteWritten": website_written}
