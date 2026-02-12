"""
Repository Classes for User and Bot Ownership Data Access

Provides async CRUD operations for users and bot ownership.
"""

from datetime import datetime

from cachibot.models.auth import BotOwnership, User, UserInDB, UserRole
from cachibot.storage.database import get_db


class UserRepository:
    """Repository for user operations."""

    async def create_user(self, user: UserInDB) -> None:
        """Create a new user."""
        db = await get_db()
        await db.execute(
            """
            INSERT INTO users (id, email, username, password_hash, role, is_active,
                created_at, created_by, last_login)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user.id,
                user.email,
                user.username,
                user.password_hash,
                user.role.value,
                1 if user.is_active else 0,
                user.created_at.isoformat(),
                user.created_by,
                user.last_login.isoformat() if user.last_login else None,
            ),
        )
        await db.commit()

    async def get_user_by_id(self, user_id: str) -> UserInDB | None:
        """Get a user by ID."""
        db = await get_db()
        async with db.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None

        return self._row_to_user(row)

    async def get_user_by_email(self, email: str) -> UserInDB | None:
        """Get a user by email."""
        db = await get_db()
        async with db.execute(
            "SELECT * FROM users WHERE email = ?",
            (email.lower(),),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None

        return self._row_to_user(row)

    async def get_user_by_username(self, username: str) -> UserInDB | None:
        """Get a user by username."""
        db = await get_db()
        async with db.execute(
            "SELECT * FROM users WHERE username = ?",
            (username.lower(),),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None

        return self._row_to_user(row)

    async def get_user_by_identifier(self, identifier: str) -> UserInDB | None:
        """Get a user by email or username."""
        # Try email first
        user = await self.get_user_by_email(identifier)
        if user:
            return user
        # Try username
        return await self.get_user_by_username(identifier)

    async def get_all_users(self, limit: int = 100, offset: int = 0) -> list[User]:
        """Get all users with pagination."""
        db = await get_db()
        async with db.execute(
            """
            SELECT id, email, username, role, is_active, created_at, created_by, last_login
            FROM users
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ) as cursor:
            rows = await cursor.fetchall()

        return [
            User(
                id=row["id"],
                email=row["email"],
                username=row["username"],
                role=UserRole(row["role"]),
                is_active=bool(row["is_active"]),
                created_at=datetime.fromisoformat(row["created_at"]),
                created_by=row["created_by"],
                last_login=datetime.fromisoformat(row["last_login"]) if row["last_login"] else None,
            )
            for row in rows
        ]

    async def get_user_count(self) -> int:
        """Get total user count."""
        db = await get_db()
        async with db.execute("SELECT COUNT(*) as count FROM users") as cursor:
            row = await cursor.fetchone()
        return row["count"] if row else 0

    async def update_user(
        self,
        user_id: str,
        email: str | None = None,
        username: str | None = None,
        role: UserRole | None = None,
        is_active: bool | None = None,
    ) -> bool:
        """Update user fields. Returns True if user was found and updated."""
        db = await get_db()

        # Build dynamic update query
        updates = []
        params = []

        if email is not None:
            updates.append("email = ?")
            params.append(email.lower())
        if username is not None:
            updates.append("username = ?")
            params.append(username.lower())
        if role is not None:
            updates.append("role = ?")
            params.append(role.value)
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if is_active else 0)

        if not updates:
            return True  # Nothing to update

        params.append(user_id)
        query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"  # nosec B608

        cursor = await db.execute(query, params)
        await db.commit()
        return cursor.rowcount > 0

    async def update_password(self, user_id: str, password_hash: str) -> bool:
        """Update user password. Returns True if user was found and updated."""
        db = await get_db()
        cursor = await db.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (password_hash, user_id),
        )
        await db.commit()
        return cursor.rowcount > 0

    async def update_last_login(self, user_id: str) -> None:
        """Update user's last login timestamp."""
        db = await get_db()
        await db.execute(
            "UPDATE users SET last_login = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), user_id),
        )
        await db.commit()

    async def deactivate_user(self, user_id: str) -> bool:
        """Deactivate a user (soft delete). Returns True if user was found."""
        return await self.update_user(user_id, is_active=False)

    async def email_exists(self, email: str, exclude_user_id: str | None = None) -> bool:
        """Check if email already exists."""
        db = await get_db()
        if exclude_user_id:
            async with db.execute(
                "SELECT 1 FROM users WHERE email = ? AND id != ?",
                (email.lower(), exclude_user_id),
            ) as cursor:
                return await cursor.fetchone() is not None
        else:
            async with db.execute(
                "SELECT 1 FROM users WHERE email = ?",
                (email.lower(),),
            ) as cursor:
                return await cursor.fetchone() is not None

    async def username_exists(self, username: str, exclude_user_id: str | None = None) -> bool:
        """Check if username already exists."""
        db = await get_db()
        if exclude_user_id:
            async with db.execute(
                "SELECT 1 FROM users WHERE username = ? AND id != ?",
                (username.lower(), exclude_user_id),
            ) as cursor:
                return await cursor.fetchone() is not None
        else:
            async with db.execute(
                "SELECT 1 FROM users WHERE username = ?",
                (username.lower(),),
            ) as cursor:
                return await cursor.fetchone() is not None

    def _row_to_user(self, row) -> UserInDB:
        """Convert a database row to UserInDB object."""
        last_login = row["last_login"]
        return UserInDB(
            id=row["id"],
            email=row["email"],
            username=row["username"],
            password_hash=row["password_hash"],
            role=UserRole(row["role"]),
            is_active=bool(row["is_active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            created_by=row["created_by"],
            last_login=datetime.fromisoformat(last_login) if last_login else None,
        )


class OwnershipRepository:
    """Repository for bot ownership tracking."""

    async def assign_bot_owner(self, ownership: BotOwnership) -> None:
        """Assign a bot to a user."""
        db = await get_db()
        await db.execute(
            """
            INSERT INTO bot_ownership (id, bot_id, user_id, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                ownership.id,
                ownership.bot_id,
                ownership.user_id,
                ownership.created_at.isoformat(),
            ),
        )
        await db.commit()

    async def get_bot_owner(self, bot_id: str) -> str | None:
        """Get the owner user_id for a bot."""
        db = await get_db()
        async with db.execute(
            "SELECT user_id FROM bot_ownership WHERE bot_id = ?",
            (bot_id,),
        ) as cursor:
            row = await cursor.fetchone()

        return row["user_id"] if row else None

    async def get_user_bots(self, user_id: str) -> list[str]:
        """Get all bot IDs owned by a user."""
        db = await get_db()
        async with db.execute(
            "SELECT bot_id FROM bot_ownership WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ) as cursor:
            rows = await cursor.fetchall()

        return [row["bot_id"] for row in rows]

    async def user_owns_bot(self, user_id: str, bot_id: str) -> bool:
        """Check if a user owns a specific bot."""
        db = await get_db()
        async with db.execute(
            "SELECT 1 FROM bot_ownership WHERE user_id = ? AND bot_id = ?",
            (user_id, bot_id),
        ) as cursor:
            return await cursor.fetchone() is not None

    async def transfer_bot(self, bot_id: str, new_owner_id: str) -> bool:
        """Transfer bot ownership to a new user. Returns True if bot was found."""
        db = await get_db()
        cursor = await db.execute(
            "UPDATE bot_ownership SET user_id = ? WHERE bot_id = ?",
            (new_owner_id, bot_id),
        )
        await db.commit()
        return cursor.rowcount > 0

    async def delete_bot_ownership(self, bot_id: str) -> bool:
        """Delete ownership record for a bot. Returns True if record was found."""
        db = await get_db()
        cursor = await db.execute(
            "DELETE FROM bot_ownership WHERE bot_id = ?",
            (bot_id,),
        )
        await db.commit()
        return cursor.rowcount > 0

    async def get_ownership(self, bot_id: str) -> BotOwnership | None:
        """Get the ownership record for a bot."""
        db = await get_db()
        async with db.execute(
            "SELECT * FROM bot_ownership WHERE bot_id = ?",
            (bot_id,),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None

        return BotOwnership(
            id=row["id"],
            bot_id=row["bot_id"],
            user_id=row["user_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
