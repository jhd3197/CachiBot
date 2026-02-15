"""
Repository Classes for User and Bot Ownership Data Access

Provides async CRUD operations using SQLAlchemy ORM with AsyncSession.
Migrated from raw aiosqlite queries to PostgreSQL via SQLAlchemy 2.0.
"""

from datetime import datetime, timezone

from sqlalchemy import delete, func, select, update

from cachibot.models.auth import BotOwnership, User, UserInDB, UserRole
from cachibot.storage import db
from cachibot.storage.models.bot import BotOwnership as BotOwnershipModel
from cachibot.storage.models.user import User as UserModel


class UserRepository:
    """Repository for user operations."""

    async def create_user(self, user: UserInDB) -> None:
        """Create a new user."""
        async with db.async_session_maker() as session:
            obj = UserModel(
                id=user.id,
                email=user.email,
                username=user.username,
                password_hash=user.password_hash,
                role=user.role.value,
                is_active=user.is_active,
                is_verified=user.is_verified,
                tier=user.tier,
                credit_balance=user.credit_balance,
                website_user_id=user.website_user_id,
                created_at=user.created_at,
                created_by=user.created_by,
                last_login=user.last_login,
            )
            session.add(obj)
            await session.commit()

    async def get_user_by_id(self, user_id: str) -> UserInDB | None:
        """Get a user by ID."""
        async with db.async_session_maker() as session:
            result = await session.execute(select(UserModel).where(UserModel.id == user_id))
            row = result.scalar_one_or_none()

        if row is None:
            return None

        return self._row_to_user(row)

    async def get_user_by_email(self, email: str) -> UserInDB | None:
        """Get a user by email."""
        async with db.async_session_maker() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.email == email.lower())
            )
            row = result.scalar_one_or_none()

        if row is None:
            return None

        return self._row_to_user(row)

    async def get_user_by_username(self, username: str) -> UserInDB | None:
        """Get a user by username."""
        async with db.async_session_maker() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.username == username.lower())
            )
            row = result.scalar_one_or_none()

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
        async with db.async_session_maker() as session:
            result = await session.execute(
                select(UserModel).order_by(UserModel.created_at.desc()).limit(limit).offset(offset)
            )
            rows = result.scalars().all()

        return [
            User(
                id=row.id,
                email=row.email,
                username=row.username,
                role=UserRole(row.role),
                is_active=row.is_active,
                created_at=row.created_at,
                created_by=row.created_by,
                last_login=row.last_login,
                website_user_id=row.website_user_id,
                tier=row.tier,
                credit_balance=row.credit_balance,
                is_verified=row.is_verified,
            )
            for row in rows
        ]

    async def get_user_count(self) -> int:
        """Get total user count."""
        async with db.async_session_maker() as session:
            result = await session.execute(select(func.count()).select_from(UserModel))
            return result.scalar_one()

    async def update_user(
        self,
        user_id: str,
        email: str | None = None,
        username: str | None = None,
        role: UserRole | None = None,
        is_active: bool | None = None,
    ) -> bool:
        """Update user fields. Returns True if user was found and updated."""
        values: dict = {}

        if email is not None:
            values["email"] = email.lower()
        if username is not None:
            values["username"] = username.lower()
        if role is not None:
            values["role"] = role.value
        if is_active is not None:
            values["is_active"] = is_active

        if not values:
            return True  # Nothing to update

        async with db.async_session_maker() as session:
            result = await session.execute(
                update(UserModel).where(UserModel.id == user_id).values(**values)
            )
            await session.commit()
            return result.rowcount > 0

    async def update_password(self, user_id: str, password_hash: str) -> bool:
        """Update user password. Returns True if user was found and updated."""
        async with db.async_session_maker() as session:
            result = await session.execute(
                update(UserModel).where(UserModel.id == user_id).values(password_hash=password_hash)
            )
            await session.commit()
            return result.rowcount > 0

    async def update_last_login(self, user_id: str) -> None:
        """Update user's last login timestamp."""
        async with db.async_session_maker() as session:
            await session.execute(
                update(UserModel)
                .where(UserModel.id == user_id)
                .values(last_login=datetime.now(timezone.utc))
            )
            await session.commit()

    async def deactivate_user(self, user_id: str) -> bool:
        """Deactivate a user (soft delete). Returns True if user was found."""
        return await self.update_user(user_id, is_active=False)

    async def email_exists(self, email: str, exclude_user_id: str | None = None) -> bool:
        """Check if email already exists."""
        stmt = select(UserModel.id).where(UserModel.email == email.lower())
        if exclude_user_id:
            stmt = stmt.where(UserModel.id != exclude_user_id)

        async with db.async_session_maker() as session:
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None

    async def username_exists(self, username: str, exclude_user_id: str | None = None) -> bool:
        """Check if username already exists."""
        stmt = select(UserModel.id).where(UserModel.username == username.lower())
        if exclude_user_id:
            stmt = stmt.where(UserModel.id != exclude_user_id)

        async with db.async_session_maker() as session:
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None

    async def get_user_by_website_id(self, website_user_id: int) -> UserInDB | None:
        """Get a user by their website INT user ID."""
        async with db.async_session_maker() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.website_user_id == website_user_id)
            )
            row = result.scalar_one_or_none()

        if row is None:
            return None

        return self._row_to_user(row)

    async def update_website_fields(
        self,
        user_id: str,
        *,
        website_user_id: int | None = None,
        tier: str | None = None,
        credit_balance: float | None = None,
    ) -> bool:
        """Update website-synced fields. Returns True if user was found and updated."""
        values: dict = {}

        if website_user_id is not None:
            values["website_user_id"] = website_user_id
        if tier is not None:
            values["tier"] = tier
        if credit_balance is not None:
            values["credit_balance"] = credit_balance

        if not values:
            return True

        async with db.async_session_maker() as session:
            result = await session.execute(
                update(UserModel).where(UserModel.id == user_id).values(**values)
            )
            await session.commit()
            return result.rowcount > 0

    def _row_to_user(self, row: UserModel) -> UserInDB:
        """Convert a database row to UserInDB object."""
        return UserInDB(
            id=row.id,
            email=row.email,
            username=row.username,
            password_hash=row.password_hash,
            role=UserRole(row.role),
            is_active=row.is_active,
            created_at=row.created_at,
            created_by=row.created_by,
            last_login=row.last_login,
            website_user_id=row.website_user_id,
            tier=row.tier,
            credit_balance=row.credit_balance,
            is_verified=row.is_verified,
        )


class OwnershipRepository:
    """Repository for bot ownership tracking."""

    async def assign_bot_owner(self, ownership: BotOwnership) -> None:
        """Assign a bot to a user."""
        async with db.async_session_maker() as session:
            obj = BotOwnershipModel(
                id=ownership.id,
                bot_id=ownership.bot_id,
                user_id=ownership.user_id,
                created_at=ownership.created_at,
            )
            session.add(obj)
            await session.commit()

    async def get_bot_owner(self, bot_id: str) -> str | None:
        """Get the owner user_id for a bot."""
        async with db.async_session_maker() as session:
            result = await session.execute(
                select(BotOwnershipModel.user_id).where(BotOwnershipModel.bot_id == bot_id)
            )
            return result.scalar_one_or_none()

    async def get_user_bots(self, user_id: str) -> list[str]:
        """Get all bot IDs owned by a user."""
        async with db.async_session_maker() as session:
            result = await session.execute(
                select(BotOwnershipModel.bot_id)
                .where(BotOwnershipModel.user_id == user_id)
                .order_by(BotOwnershipModel.created_at.desc())
            )
            return [row[0] for row in result.all()]

    async def user_owns_bot(self, user_id: str, bot_id: str) -> bool:
        """Check if a user owns a specific bot."""
        async with db.async_session_maker() as session:
            result = await session.execute(
                select(BotOwnershipModel.id).where(
                    BotOwnershipModel.user_id == user_id,
                    BotOwnershipModel.bot_id == bot_id,
                )
            )
            return result.scalar_one_or_none() is not None

    async def transfer_bot(self, bot_id: str, new_owner_id: str) -> bool:
        """Transfer bot ownership to a new user. Returns True if bot was found."""
        async with db.async_session_maker() as session:
            result = await session.execute(
                update(BotOwnershipModel)
                .where(BotOwnershipModel.bot_id == bot_id)
                .values(user_id=new_owner_id)
            )
            await session.commit()
            return result.rowcount > 0

    async def delete_bot_ownership(self, bot_id: str) -> bool:
        """Delete ownership record for a bot. Returns True if record was found."""
        async with db.async_session_maker() as session:
            result = await session.execute(
                delete(BotOwnershipModel).where(BotOwnershipModel.bot_id == bot_id)
            )
            await session.commit()
            return result.rowcount > 0

    async def get_ownership(self, bot_id: str) -> BotOwnership | None:
        """Get the ownership record for a bot."""
        async with db.async_session_maker() as session:
            result = await session.execute(
                select(BotOwnershipModel).where(BotOwnershipModel.bot_id == bot_id)
            )
            row = result.scalar_one_or_none()

        if row is None:
            return None

        return BotOwnership(
            id=row.id,
            bot_id=row.bot_id,
            user_id=row.user_id,
            created_at=row.created_at,
        )
