"""Repository classes for room data access."""

import json
from datetime import datetime

from cachibot.models.room import (
    Room,
    RoomBot,
    RoomMember,
    RoomMemberRole,
    RoomMessage,
    RoomSenderType,
    RoomSettings,
)
from cachibot.storage.database import get_db


class RoomRepository:
    """Repository for rooms."""

    async def create_room(self, room: Room) -> None:
        """Create a new room."""
        db = await get_db()
        await db.execute(
            """
            INSERT INTO rooms (id, title, description, creator_id, max_bots, settings,
                               created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                room.id,
                room.title,
                room.description,
                room.creator_id,
                room.max_bots,
                json.dumps(room.settings.model_dump()),
                room.created_at.isoformat(),
                room.updated_at.isoformat(),
            ),
        )
        await db.commit()

    async def get_room(self, room_id: str) -> Room | None:
        """Get a room by ID."""
        db = await get_db()
        async with db.execute(
            "SELECT * FROM rooms WHERE id = ?",
            (room_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_room(row)

    async def get_rooms_for_user(self, user_id: str) -> list[Room]:
        """Get all rooms a user is a member of."""
        db = await get_db()
        async with db.execute(
            """
            SELECT r.* FROM rooms r
            INNER JOIN room_members rm ON r.id = rm.room_id
            WHERE rm.user_id = ?
            ORDER BY r.updated_at DESC
            """,
            (user_id,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_room(row) for row in rows]

    async def update_room(
        self,
        room_id: str,
        title: str | None = None,
        description: str | None = None,
        settings: RoomSettings | None = None,
    ) -> Room | None:
        """Update room details."""
        db = await get_db()
        now = datetime.utcnow()

        updates = ["updated_at = ?"]
        params: list = [now.isoformat()]

        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if settings is not None:
            updates.append("settings = ?")
            params.append(json.dumps(settings.model_dump()))

        params.append(room_id)
        set_clause = ", ".join(updates)

        cursor = await db.execute(
            f"UPDATE rooms SET {set_clause} WHERE id = ?",  # nosec B608
            params,
        )
        await db.commit()

        if cursor.rowcount == 0:
            return None
        return await self.get_room(room_id)

    async def delete_room(self, room_id: str) -> bool:
        """Delete a room (cascades to members, bots, messages)."""
        db = await get_db()
        cursor = await db.execute("DELETE FROM rooms WHERE id = ?", (room_id,))
        await db.commit()
        return cursor.rowcount > 0

    def _row_to_room(self, row) -> Room:
        """Convert a database row to a Room."""
        settings_raw = json.loads(row["settings"]) if row["settings"] else {}
        return Room(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            creator_id=row["creator_id"],
            max_bots=row["max_bots"],
            settings=RoomSettings(**settings_raw),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


class RoomMemberRepository:
    """Repository for room members."""

    async def add_member(self, member: RoomMember) -> None:
        """Add a member to a room."""
        db = await get_db()
        await db.execute(
            """
            INSERT INTO room_members (room_id, user_id, role, joined_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                member.room_id,
                member.user_id,
                member.role.value,
                member.joined_at.isoformat(),
            ),
        )
        await db.commit()

    async def remove_member(self, room_id: str, user_id: str) -> bool:
        """Remove a member from a room."""
        db = await get_db()
        cursor = await db.execute(
            "DELETE FROM room_members WHERE room_id = ? AND user_id = ?",
            (room_id, user_id),
        )
        await db.commit()
        return cursor.rowcount > 0

    async def get_members(self, room_id: str) -> list[RoomMember]:
        """Get all members of a room."""
        db = await get_db()
        async with db.execute(
            """
            SELECT rm.room_id, rm.user_id, rm.role, rm.joined_at, u.username
            FROM room_members rm
            LEFT JOIN users u ON rm.user_id = u.id
            WHERE rm.room_id = ?
            ORDER BY rm.joined_at
            """,
            (room_id,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [
            RoomMember(
                room_id=row["room_id"],
                user_id=row["user_id"],
                username=row["username"] or "",
                role=RoomMemberRole(row["role"]),
                joined_at=datetime.fromisoformat(row["joined_at"]),
            )
            for row in rows
        ]

    async def is_member(self, room_id: str, user_id: str) -> bool:
        """Check if a user is a member of a room."""
        db = await get_db()
        async with db.execute(
            "SELECT 1 FROM room_members WHERE room_id = ? AND user_id = ?",
            (room_id, user_id),
        ) as cursor:
            return await cursor.fetchone() is not None

    async def get_member_role(self, room_id: str, user_id: str) -> RoomMemberRole | None:
        """Get a user's role in a room."""
        db = await get_db()
        async with db.execute(
            "SELECT role FROM room_members WHERE room_id = ? AND user_id = ?",
            (room_id, user_id),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return RoomMemberRole(row["role"])


class RoomBotRepository:
    """Repository for room bots."""

    async def add_bot(self, room_bot: RoomBot) -> None:
        """Add a bot to a room."""
        db = await get_db()
        await db.execute(
            "INSERT INTO room_bots (room_id, bot_id, added_at) VALUES (?, ?, ?)",
            (room_bot.room_id, room_bot.bot_id, room_bot.added_at.isoformat()),
        )
        await db.commit()

    async def remove_bot(self, room_id: str, bot_id: str) -> bool:
        """Remove a bot from a room."""
        db = await get_db()
        cursor = await db.execute(
            "DELETE FROM room_bots WHERE room_id = ? AND bot_id = ?",
            (room_id, bot_id),
        )
        await db.commit()
        return cursor.rowcount > 0

    async def get_bots(self, room_id: str) -> list[RoomBot]:
        """Get all bots in a room."""
        db = await get_db()
        async with db.execute(
            """
            SELECT rb.room_id, rb.bot_id, rb.added_at, b.name
            FROM room_bots rb
            LEFT JOIN bots b ON rb.bot_id = b.id
            WHERE rb.room_id = ?
            ORDER BY rb.added_at
            """,
            (room_id,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [
            RoomBot(
                room_id=row["room_id"],
                bot_id=row["bot_id"],
                bot_name=row["name"] or "",
                added_at=datetime.fromisoformat(row["added_at"]),
            )
            for row in rows
        ]

    async def get_bot_count(self, room_id: str) -> int:
        """Get the number of bots in a room."""
        db = await get_db()
        async with db.execute(
            "SELECT COUNT(*) as count FROM room_bots WHERE room_id = ?",
            (room_id,),
        ) as cursor:
            row = await cursor.fetchone()
        return row["count"] if row else 0


class RoomMessageRepository:
    """Repository for room messages."""

    async def save_message(self, message: RoomMessage) -> None:
        """Save a message to the room."""
        db = await get_db()
        await db.execute(
            """
            INSERT INTO room_messages (id, room_id, sender_type, sender_id, sender_name,
                                       content, metadata, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message.id,
                message.room_id,
                message.sender_type.value,
                message.sender_id,
                message.sender_name,
                message.content,
                json.dumps(message.metadata),
                message.timestamp.isoformat(),
            ),
        )
        await db.commit()

    async def get_messages(
        self,
        room_id: str,
        limit: int = 50,
        before: str | None = None,
    ) -> list[RoomMessage]:
        """Get messages for a room with optional cursor pagination."""
        db = await get_db()

        if before:
            async with db.execute(
                """
                SELECT * FROM room_messages
                WHERE room_id = ? AND timestamp < ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (room_id, before, limit),
            ) as cursor:
                rows = await cursor.fetchall()
        else:
            async with db.execute(
                """
                SELECT * FROM room_messages
                WHERE room_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (room_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()

        return [self._row_to_message(row) for row in reversed(rows)]

    async def get_message_count(self, room_id: str) -> int:
        """Get the number of messages in a room."""
        db = await get_db()
        async with db.execute(
            "SELECT COUNT(*) as count FROM room_messages WHERE room_id = ?",
            (room_id,),
        ) as cursor:
            row = await cursor.fetchone()
        return row["count"] if row else 0

    async def delete_messages(self, room_id: str) -> int:
        """Delete all messages in a room."""
        db = await get_db()
        cursor = await db.execute(
            "DELETE FROM room_messages WHERE room_id = ?",
            (room_id,),
        )
        await db.commit()
        return cursor.rowcount

    def _row_to_message(self, row) -> RoomMessage:
        """Convert a database row to a RoomMessage."""
        return RoomMessage(
            id=row["id"],
            room_id=row["room_id"],
            sender_type=RoomSenderType(row["sender_type"]),
            sender_id=row["sender_id"],
            sender_name=row["sender_name"],
            content=row["content"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            timestamp=datetime.fromisoformat(row["timestamp"]),
        )
