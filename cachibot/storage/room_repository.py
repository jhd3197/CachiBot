"""
Repository classes for room data access.

Provides async CRUD operations using SQLAlchemy ORM with AsyncSession.
Migrated from raw aiosqlite queries to PostgreSQL via SQLAlchemy 2.0.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select, update

from cachibot.models.room import (
    BookmarkedMessage,
    PinnedMessage,
    ReactionSummary,
    Room,
    RoomAutomationResponse,
    RoomBot,
    RoomMember,
    RoomMemberRole,
    RoomMessage,
    RoomSenderType,
    RoomSettings,
)
from cachibot.storage import db
from cachibot.storage.base import BaseRepository
from cachibot.storage.models.bot import Bot as BotModel
from cachibot.storage.models.room import (
    Room as RoomModel,
)
from cachibot.storage.models.room import (
    RoomAutomation as RoomAutomationModel,
)
from cachibot.storage.models.room import (
    RoomBookmark as RoomBookmarkModel,
)
from cachibot.storage.models.room import (
    RoomBot as RoomBotModel,
)
from cachibot.storage.models.room import (
    RoomMember as RoomMemberModel,
)
from cachibot.storage.models.room import (
    RoomMessage as RoomMessageModel,
)
from cachibot.storage.models.room import (
    RoomMessageReaction as RoomMessageReactionModel,
)
from cachibot.storage.models.room import (
    RoomPinnedMessage as RoomPinnedMessageModel,
)
from cachibot.storage.models.user import User as UserModel


class RoomRepository(BaseRepository[RoomModel, Room]):
    """Repository for rooms."""

    _model = RoomModel

    async def create_room(self, room: Room) -> None:
        """Create a new room."""
        await self._add(
            RoomModel(
                id=room.id,
                title=room.title,
                description=room.description,
                creator_id=room.creator_id,
                max_bots=room.max_bots,
                settings=room.settings.model_dump(),
                created_at=room.created_at,
                updated_at=room.updated_at,
            )
        )

    async def get_room(self, room_id: str) -> Room | None:
        """Get a room by ID."""
        return await self.get_by_id(room_id)

    async def get_rooms_for_user(self, user_id: str) -> list[Room]:
        """Get all rooms a user is a member of."""
        return await self._fetch_all(
            select(RoomModel)
            .join(RoomMemberModel, RoomModel.id == RoomMemberModel.room_id)
            .where(RoomMemberModel.user_id == user_id)
            .order_by(RoomModel.updated_at.desc())
        )

    async def update_room(
        self,
        room_id: str,
        title: str | None = None,
        description: str | None = None,
        settings: RoomSettings | None = None,
    ) -> Room | None:
        """Update room details."""
        now = datetime.now(timezone.utc)
        values: dict[str, Any] = {"updated_at": now}

        if title is not None:
            values["title"] = title
        if description is not None:
            values["description"] = description
        if settings is not None:
            values["settings"] = settings.model_dump()

        count = await self._update(
            update(RoomModel).where(RoomModel.id == room_id).values(**values)
        )

        if count == 0:
            return None
        return await self.get_room(room_id)

    async def delete_room(self, room_id: str) -> bool:
        """Delete a room (cascades to members, bots, messages)."""
        return await self.delete_by_id(room_id)

    def _row_to_entity(self, row: RoomModel) -> Room:
        """Convert a database row to a Room."""
        settings_raw = row.settings if row.settings else {}
        return Room(
            id=row.id,
            title=row.title,
            description=row.description,
            creator_id=row.creator_id,
            max_bots=row.max_bots,
            settings=RoomSettings(**settings_raw),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


class RoomMemberRepository:
    """Repository for room members."""

    async def add_member(self, member: RoomMember) -> None:
        """Add a member to a room."""
        async with db.ensure_initialized()() as session:
            obj = RoomMemberModel(
                room_id=member.room_id,
                user_id=member.user_id,
                role=member.role.value,
                joined_at=member.joined_at,
            )
            session.add(obj)
            await session.commit()

    async def remove_member(self, room_id: str, user_id: str) -> bool:
        """Remove a member from a room."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                delete(RoomMemberModel).where(
                    RoomMemberModel.room_id == room_id,
                    RoomMemberModel.user_id == user_id,
                )
            )
            await session.commit()
            return bool(result.rowcount > 0)  # type: ignore[attr-defined]

    async def get_members(self, room_id: str) -> list[RoomMember]:
        """Get all members of a room."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(
                    RoomMemberModel.room_id,
                    RoomMemberModel.user_id,
                    RoomMemberModel.role,
                    RoomMemberModel.joined_at,
                    UserModel.username,
                )
                .outerjoin(UserModel, RoomMemberModel.user_id == UserModel.id)
                .where(RoomMemberModel.room_id == room_id)
                .order_by(RoomMemberModel.joined_at)
            )
            rows = result.all()
        return [
            RoomMember(
                room_id=row[0],
                user_id=row[1],
                username=row[4] or "",
                role=RoomMemberRole(row[2]),
                joined_at=row[3],
            )
            for row in rows
        ]

    async def is_member(self, room_id: str, user_id: str) -> bool:
        """Check if a user is a member of a room."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(RoomMemberModel.room_id).where(
                    RoomMemberModel.room_id == room_id,
                    RoomMemberModel.user_id == user_id,
                )
            )
            return result.scalar_one_or_none() is not None

    async def get_member_role(self, room_id: str, user_id: str) -> RoomMemberRole | None:
        """Get a user's role in a room."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(RoomMemberModel.role).where(
                    RoomMemberModel.room_id == room_id,
                    RoomMemberModel.user_id == user_id,
                )
            )
            row = result.scalar_one_or_none()
        if row is None:
            return None
        return RoomMemberRole(row)


class RoomBotRepository:
    """Repository for room bots."""

    async def add_bot(self, room_bot: RoomBot) -> None:
        """Add a bot to a room."""
        async with db.ensure_initialized()() as session:
            obj = RoomBotModel(
                room_id=room_bot.room_id,
                bot_id=room_bot.bot_id,
                added_at=room_bot.added_at,
            )
            session.add(obj)
            await session.commit()

    async def remove_bot(self, room_id: str, bot_id: str) -> bool:
        """Remove a bot from a room."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                delete(RoomBotModel).where(
                    RoomBotModel.room_id == room_id,
                    RoomBotModel.bot_id == bot_id,
                )
            )
            await session.commit()
            return bool(result.rowcount > 0)  # type: ignore[attr-defined]

    async def get_bots(self, room_id: str) -> list[RoomBot]:
        """Get all bots in a room."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(
                    RoomBotModel.room_id,
                    RoomBotModel.bot_id,
                    RoomBotModel.added_at,
                    BotModel.name,
                    RoomBotModel.role,
                )
                .outerjoin(BotModel, RoomBotModel.bot_id == BotModel.id)
                .where(RoomBotModel.room_id == room_id)
                .order_by(RoomBotModel.added_at)
            )
            rows = result.all()
        return [
            RoomBot(
                room_id=row[0],
                bot_id=row[1],
                bot_name=row[3] or "",
                role=row[4],
                added_at=row[2],
            )
            for row in rows
        ]

    async def update_bot_role(self, room_id: str, bot_id: str, role: str) -> bool:
        """Update a bot's role in a room."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                update(RoomBotModel)
                .where(
                    RoomBotModel.room_id == room_id,
                    RoomBotModel.bot_id == bot_id,
                )
                .values(role=role)
            )
            await session.commit()
            return bool(result.rowcount > 0)  # type: ignore[attr-defined]

    async def get_bot_count(self, room_id: str) -> int:
        """Get the number of bots in a room."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(func.count())
                .select_from(RoomBotModel)
                .where(RoomBotModel.room_id == room_id)
            )
            return result.scalar_one()


class RoomMessageRepository(BaseRepository[RoomMessageModel, RoomMessage]):
    """Repository for room messages."""

    _model = RoomMessageModel

    async def save_message(self, message: RoomMessage) -> None:
        """Save a message to the room."""
        await self._add(
            RoomMessageModel(
                id=message.id,
                room_id=message.room_id,
                sender_type=message.sender_type.value,
                sender_id=message.sender_id,
                sender_name=message.sender_name,
                content=message.content,
                meta=message.metadata,
                timestamp=message.timestamp,
            )
        )

    async def get_messages(
        self,
        room_id: str,
        limit: int = 50,
        before: str | datetime | None = None,
    ) -> list[RoomMessage]:
        """Get messages for a room with optional cursor pagination."""
        stmt = select(RoomMessageModel).where(RoomMessageModel.room_id == room_id)

        if before:
            if isinstance(before, str):
                before = datetime.fromisoformat(before)
            stmt = stmt.where(RoomMessageModel.timestamp < before)

        stmt = stmt.order_by(RoomMessageModel.timestamp.desc()).limit(limit)

        async with self._session() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()

        return [self._row_to_entity(row) for row in reversed(rows)]

    async def get_message_count(self, room_id: str) -> int:
        """Get the number of messages in a room."""
        result = await self._scalar(
            select(func.count())
            .select_from(RoomMessageModel)
            .where(RoomMessageModel.room_id == room_id)
        )
        return result or 0

    async def delete_messages(self, room_id: str) -> int:
        """Delete all messages in a room."""
        return await self._delete(
            delete(RoomMessageModel).where(RoomMessageModel.room_id == room_id)
        )

    def _row_to_entity(self, row: RoomMessageModel) -> RoomMessage:
        """Convert a database row to a RoomMessage."""
        return RoomMessage(
            id=row.id,
            room_id=row.room_id,
            sender_type=RoomSenderType(row.sender_type),
            sender_id=row.sender_id,
            sender_name=row.sender_name,
            content=row.content,
            metadata=row.meta if row.meta else {},
            timestamp=row.timestamp,
        )


class RoomReactionRepository:
    """Repository for message reactions."""

    async def add_reaction(
        self, reaction_id: str, room_id: str, message_id: str, user_id: str, emoji: str
    ) -> bool:
        """Add a reaction. Returns False if already exists."""
        async with db.ensure_initialized()() as session:
            # Check for existing
            existing = await session.execute(
                select(RoomMessageReactionModel.id).where(
                    RoomMessageReactionModel.room_id == room_id,
                    RoomMessageReactionModel.message_id == message_id,
                    RoomMessageReactionModel.user_id == user_id,
                    RoomMessageReactionModel.emoji == emoji,
                )
            )
            if existing.scalar_one_or_none() is not None:
                return False
            obj = RoomMessageReactionModel(
                id=reaction_id,
                room_id=room_id,
                message_id=message_id,
                user_id=user_id,
                emoji=emoji,
            )
            session.add(obj)
            await session.commit()
            return True

    async def remove_reaction(
        self, room_id: str, message_id: str, user_id: str, emoji: str
    ) -> bool:
        """Remove a reaction. Returns True if deleted."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                delete(RoomMessageReactionModel).where(
                    RoomMessageReactionModel.room_id == room_id,
                    RoomMessageReactionModel.message_id == message_id,
                    RoomMessageReactionModel.user_id == user_id,
                    RoomMessageReactionModel.emoji == emoji,
                )
            )
            await session.commit()
            return bool(result.rowcount > 0)  # type: ignore[attr-defined]

    async def get_reactions_bulk(self, message_ids: list[str]) -> dict[str, list[ReactionSummary]]:
        """Get reactions for multiple messages, grouped by message ID.

        Returns a dict of messageId -> list[ReactionSummary].
        """
        if not message_ids:
            return {}

        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(
                    RoomMessageReactionModel.message_id,
                    RoomMessageReactionModel.emoji,
                    RoomMessageReactionModel.user_id,
                )
                .where(RoomMessageReactionModel.message_id.in_(message_ids))
                .order_by(RoomMessageReactionModel.created_at)
            )
            rows = result.all()

        # Group by (message_id, emoji)
        grouped: dict[str, dict[str, list[str]]] = {}
        for msg_id, emoji, uid in rows:
            if msg_id not in grouped:
                grouped[msg_id] = {}
            if emoji not in grouped[msg_id]:
                grouped[msg_id][emoji] = []
            grouped[msg_id][emoji].append(uid)

        out: dict[str, list[ReactionSummary]] = {}
        for msg_id, emoji_map in grouped.items():
            out[msg_id] = [
                ReactionSummary(emoji=emoji, count=len(uids), userIds=uids)
                for emoji, uids in emoji_map.items()
            ]
        return out


class RoomPinRepository:
    """Repository for pinned messages."""

    async def pin_message(self, pin_id: str, room_id: str, message_id: str, pinned_by: str) -> bool:
        """Pin a message. Returns False if already pinned."""
        async with db.ensure_initialized()() as session:
            existing = await session.execute(
                select(RoomPinnedMessageModel.id).where(
                    RoomPinnedMessageModel.room_id == room_id,
                    RoomPinnedMessageModel.message_id == message_id,
                )
            )
            if existing.scalar_one_or_none() is not None:
                return False
            obj = RoomPinnedMessageModel(
                id=pin_id,
                room_id=room_id,
                message_id=message_id,
                pinned_by=pinned_by,
            )
            session.add(obj)
            await session.commit()
            return True

    async def unpin_message(self, room_id: str, message_id: str) -> bool:
        """Unpin a message. Returns True if deleted."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                delete(RoomPinnedMessageModel).where(
                    RoomPinnedMessageModel.room_id == room_id,
                    RoomPinnedMessageModel.message_id == message_id,
                )
            )
            await session.commit()
            return bool(result.rowcount > 0)  # type: ignore[attr-defined]

    async def get_pinned_messages(self, room_id: str) -> list[PinnedMessage]:
        """Get all pinned messages for a room with message details."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(
                    RoomPinnedMessageModel.id,
                    RoomPinnedMessageModel.room_id,
                    RoomPinnedMessageModel.message_id,
                    RoomPinnedMessageModel.pinned_by,
                    RoomPinnedMessageModel.pinned_at,
                    RoomMessageModel.sender_name,
                    RoomMessageModel.content,
                    RoomMessageModel.timestamp,
                )
                .outerjoin(
                    RoomMessageModel,
                    RoomPinnedMessageModel.message_id == RoomMessageModel.id,
                )
                .where(RoomPinnedMessageModel.room_id == room_id)
                .order_by(RoomPinnedMessageModel.pinned_at.desc())
            )
            rows = result.all()

        return [
            PinnedMessage(
                id=row[0],
                roomId=row[1],
                messageId=row[2],
                pinnedBy=row[3],
                pinnedAt=row[4].isoformat() if row[4] else "",
                senderName=row[5] or "",
                content=(row[6] or "")[:200],
                timestamp=row[7].isoformat() if row[7] else "",
            )
            for row in rows
        ]


class RoomBookmarkRepository:
    """Repository for user bookmarks."""

    async def add_bookmark(
        self, bookmark_id: str, room_id: str, message_id: str, user_id: str
    ) -> bool:
        """Add a bookmark. Returns False if already bookmarked."""
        async with db.ensure_initialized()() as session:
            existing = await session.execute(
                select(RoomBookmarkModel.id).where(
                    RoomBookmarkModel.user_id == user_id,
                    RoomBookmarkModel.message_id == message_id,
                )
            )
            if existing.scalar_one_or_none() is not None:
                return False
            obj = RoomBookmarkModel(
                id=bookmark_id,
                room_id=room_id,
                message_id=message_id,
                user_id=user_id,
            )
            session.add(obj)
            await session.commit()
            return True

    async def remove_bookmark(self, user_id: str, message_id: str) -> bool:
        """Remove a bookmark. Returns True if deleted."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                delete(RoomBookmarkModel).where(
                    RoomBookmarkModel.user_id == user_id,
                    RoomBookmarkModel.message_id == message_id,
                )
            )
            await session.commit()
            return bool(result.rowcount > 0)  # type: ignore[attr-defined]

    async def get_bookmarks(
        self, user_id: str, room_id: str | None = None
    ) -> list[BookmarkedMessage]:
        """Get bookmarks for a user, optionally filtered by room."""
        async with db.ensure_initialized()() as session:
            stmt = (
                select(
                    RoomBookmarkModel.id,
                    RoomBookmarkModel.room_id,
                    RoomBookmarkModel.message_id,
                    RoomBookmarkModel.created_at,
                    RoomMessageModel.sender_name,
                    RoomMessageModel.content,
                    RoomMessageModel.timestamp,
                )
                .outerjoin(
                    RoomMessageModel,
                    RoomBookmarkModel.message_id == RoomMessageModel.id,
                )
                .where(RoomBookmarkModel.user_id == user_id)
            )
            if room_id:
                stmt = stmt.where(RoomBookmarkModel.room_id == room_id)
            stmt = stmt.order_by(RoomBookmarkModel.created_at.desc())

            result = await session.execute(stmt)
            rows = result.all()

        return [
            BookmarkedMessage(
                id=row[0],
                roomId=row[1],
                messageId=row[2],
                createdAt=row[3].isoformat() if row[3] else "",
                senderName=row[4] or "",
                content=(row[5] or "")[:200],
                timestamp=row[6].isoformat() if row[6] else "",
            )
            for row in rows
        ]


# =============================================================================
# AUTOMATIONS
# =============================================================================


class RoomAutomationRepository(BaseRepository[RoomAutomationModel, RoomAutomationResponse]):
    """Repository for room automations (trigger + action rules)."""

    _model = RoomAutomationModel

    async def create(
        self,
        automation_id: str,
        room_id: str,
        name: str,
        trigger_type: str,
        trigger_config: dict[str, Any],
        action_type: str,
        action_config: dict[str, Any],
        created_by: str,
    ) -> RoomAutomationResponse:
        """Create a new automation."""
        async with self._session() as session:
            obj = RoomAutomationModel(
                id=automation_id,
                room_id=room_id,
                name=name,
                trigger_type=trigger_type,
                trigger_config=trigger_config,
                action_type=action_type,
                action_config=action_config,
                created_by=created_by,
            )
            session.add(obj)
            await session.commit()
            await session.refresh(obj)
            return self._row_to_entity(obj)

    async def get_automations(self, room_id: str) -> list[RoomAutomationResponse]:
        """Get all automations for a room."""
        return await self._fetch_all(
            select(RoomAutomationModel)
            .where(RoomAutomationModel.room_id == room_id)
            .order_by(RoomAutomationModel.created_at)
        )

    async def get_automation(self, automation_id: str) -> RoomAutomationResponse | None:
        """Get a single automation by ID."""
        return await self.get_by_id(automation_id)

    async def update(
        self,
        automation_id: str,
        **kwargs: Any,
    ) -> RoomAutomationResponse | None:
        """Update automation fields."""
        fields: dict[str, Any] = {}
        for key in (
            "name",
            "enabled",
            "trigger_type",
            "trigger_config",
            "action_type",
            "action_config",
        ):
            if key in kwargs and kwargs[key] is not None:
                fields[key] = kwargs[key]
        if not fields:
            return await self.get_automation(automation_id)
        fields["updated_at"] = datetime.now(tz=timezone.utc)
        await self._update(
            update(RoomAutomationModel)
            .where(RoomAutomationModel.id == automation_id)
            .values(**fields)
        )
        return await self.get_automation(automation_id)

    async def delete(self, automation_id: str) -> bool:
        """Delete an automation. Returns True if deleted."""
        return await self.delete_by_id(automation_id)

    async def increment_trigger_count(self, automation_id: str) -> None:
        """Increment the trigger count for an automation."""
        await self._update(
            update(RoomAutomationModel)
            .where(RoomAutomationModel.id == automation_id)
            .values(
                trigger_count=RoomAutomationModel.trigger_count + 1,
                updated_at=datetime.now(tz=timezone.utc),
            )
        )

    async def get_enabled_by_trigger(
        self, trigger_type: str, room_id: str | None = None
    ) -> list[RoomAutomationResponse]:
        """Get enabled automations by trigger type."""
        stmt = select(RoomAutomationModel).where(
            RoomAutomationModel.enabled.is_(True),
            RoomAutomationModel.trigger_type == trigger_type,
        )
        if room_id:
            stmt = stmt.where(RoomAutomationModel.room_id == room_id)
        return await self._fetch_all(stmt)

    def _row_to_entity(self, row: RoomAutomationModel) -> RoomAutomationResponse:
        """Convert a database row to a RoomAutomationResponse."""
        return RoomAutomationResponse(
            id=row.id,
            roomId=row.room_id,
            name=row.name,
            enabled=row.enabled,
            triggerType=row.trigger_type,
            triggerConfig=row.trigger_config,
            actionType=row.action_type,
            actionConfig=row.action_config,
            createdBy=row.created_by,
            triggerCount=row.trigger_count,
            createdAt=row.created_at.isoformat() if row.created_at else "",
            updatedAt=row.updated_at.isoformat() if row.updated_at else "",
        )
