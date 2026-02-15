"""
Repository classes for room data access.

Provides async CRUD operations using SQLAlchemy ORM with AsyncSession.
Migrated from raw aiosqlite queries to PostgreSQL via SQLAlchemy 2.0.
"""

from datetime import datetime, timezone

from sqlalchemy import delete, func, select, update

from cachibot.models.room import (
    Room,
    RoomBot,
    RoomMember,
    RoomMemberRole,
    RoomMessage,
    RoomSenderType,
    RoomSettings,
)
from cachibot.storage.db import async_session_maker
from cachibot.storage.models.bot import Bot as BotModel
from cachibot.storage.models.room import (
    Room as RoomModel,
    RoomBot as RoomBotModel,
    RoomMember as RoomMemberModel,
    RoomMessage as RoomMessageModel,
)
from cachibot.storage.models.user import User as UserModel


class RoomRepository:
    """Repository for rooms."""

    async def create_room(self, room: Room) -> None:
        """Create a new room."""
        async with async_session_maker() as session:
            obj = RoomModel(
                id=room.id,
                title=room.title,
                description=room.description,
                creator_id=room.creator_id,
                max_bots=room.max_bots,
                settings=room.settings.model_dump(),
                created_at=room.created_at,
                updated_at=room.updated_at,
            )
            session.add(obj)
            await session.commit()

    async def get_room(self, room_id: str) -> Room | None:
        """Get a room by ID."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(RoomModel).where(RoomModel.id == room_id)
            )
            row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._row_to_room(row)

    async def get_rooms_for_user(self, user_id: str) -> list[Room]:
        """Get all rooms a user is a member of."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(RoomModel)
                .join(RoomMemberModel, RoomModel.id == RoomMemberModel.room_id)
                .where(RoomMemberModel.user_id == user_id)
                .order_by(RoomModel.updated_at.desc())
            )
            rows = result.scalars().all()
        return [self._row_to_room(row) for row in rows]

    async def update_room(
        self,
        room_id: str,
        title: str | None = None,
        description: str | None = None,
        settings: RoomSettings | None = None,
    ) -> Room | None:
        """Update room details."""
        now = datetime.now(timezone.utc)
        values: dict = {"updated_at": now}

        if title is not None:
            values["title"] = title
        if description is not None:
            values["description"] = description
        if settings is not None:
            values["settings"] = settings.model_dump()

        async with async_session_maker() as session:
            result = await session.execute(
                update(RoomModel)
                .where(RoomModel.id == room_id)
                .values(**values)
            )
            await session.commit()

        if result.rowcount == 0:
            return None
        return await self.get_room(room_id)

    async def delete_room(self, room_id: str) -> bool:
        """Delete a room (cascades to members, bots, messages)."""
        async with async_session_maker() as session:
            result = await session.execute(
                delete(RoomModel).where(RoomModel.id == room_id)
            )
            await session.commit()
            return result.rowcount > 0

    def _row_to_room(self, row: RoomModel) -> Room:
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
        async with async_session_maker() as session:
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
        async with async_session_maker() as session:
            result = await session.execute(
                delete(RoomMemberModel).where(
                    RoomMemberModel.room_id == room_id,
                    RoomMemberModel.user_id == user_id,
                )
            )
            await session.commit()
            return result.rowcount > 0

    async def get_members(self, room_id: str) -> list[RoomMember]:
        """Get all members of a room."""
        async with async_session_maker() as session:
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
        async with async_session_maker() as session:
            result = await session.execute(
                select(RoomMemberModel.room_id).where(
                    RoomMemberModel.room_id == room_id,
                    RoomMemberModel.user_id == user_id,
                )
            )
            return result.scalar_one_or_none() is not None

    async def get_member_role(self, room_id: str, user_id: str) -> RoomMemberRole | None:
        """Get a user's role in a room."""
        async with async_session_maker() as session:
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
        async with async_session_maker() as session:
            obj = RoomBotModel(
                room_id=room_bot.room_id,
                bot_id=room_bot.bot_id,
                added_at=room_bot.added_at,
            )
            session.add(obj)
            await session.commit()

    async def remove_bot(self, room_id: str, bot_id: str) -> bool:
        """Remove a bot from a room."""
        async with async_session_maker() as session:
            result = await session.execute(
                delete(RoomBotModel).where(
                    RoomBotModel.room_id == room_id,
                    RoomBotModel.bot_id == bot_id,
                )
            )
            await session.commit()
            return result.rowcount > 0

    async def get_bots(self, room_id: str) -> list[RoomBot]:
        """Get all bots in a room."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(
                    RoomBotModel.room_id,
                    RoomBotModel.bot_id,
                    RoomBotModel.added_at,
                    BotModel.name,
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
                added_at=row[2],
            )
            for row in rows
        ]

    async def get_bot_count(self, room_id: str) -> int:
        """Get the number of bots in a room."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(func.count())
                .select_from(RoomBotModel)
                .where(RoomBotModel.room_id == room_id)
            )
            return result.scalar_one()


class RoomMessageRepository:
    """Repository for room messages."""

    async def save_message(self, message: RoomMessage) -> None:
        """Save a message to the room."""
        async with async_session_maker() as session:
            obj = RoomMessageModel(
                id=message.id,
                room_id=message.room_id,
                sender_type=message.sender_type.value,
                sender_id=message.sender_id,
                sender_name=message.sender_name,
                content=message.content,
                meta=message.metadata,
                timestamp=message.timestamp,
            )
            session.add(obj)
            await session.commit()

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

        async with async_session_maker() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()

        return [self._row_to_message(row) for row in reversed(rows)]

    async def get_message_count(self, room_id: str) -> int:
        """Get the number of messages in a room."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(func.count())
                .select_from(RoomMessageModel)
                .where(RoomMessageModel.room_id == room_id)
            )
            return result.scalar_one()

    async def delete_messages(self, room_id: str) -> int:
        """Delete all messages in a room."""
        async with async_session_maker() as session:
            result = await session.execute(
                delete(RoomMessageModel).where(RoomMessageModel.room_id == room_id)
            )
            await session.commit()
            return result.rowcount

    def _row_to_message(self, row: RoomMessageModel) -> RoomMessage:
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
