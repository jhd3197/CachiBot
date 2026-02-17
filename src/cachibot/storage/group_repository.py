"""
Repository Classes for Group and Bot Access Data Access

Provides async CRUD operations for groups, group membership,
and bot-group access sharing.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select, update

from cachibot.models.group import BotAccessLevel, GroupRole
from cachibot.storage import db
from cachibot.storage.models.group import BotGroupAccess, Group, GroupMember
from cachibot.storage.models.user import User as UserModel


class GroupRepository:
    """Repository for group operations."""

    async def create_group(
        self,
        name: str,
        created_by: str,
        description: str | None = None,
    ) -> Group:
        """Create a new group. Creator is auto-added as owner."""
        group_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        async with db.ensure_initialized()() as session:
            group = Group(
                id=group_id,
                name=name,
                description=description,
                created_by=created_by,
                created_at=now,
                updated_at=now,
            )
            session.add(group)

            # Add creator as owner
            member = GroupMember(
                group_id=group_id,
                user_id=created_by,
                role=GroupRole.OWNER.value,
                joined_at=now,
            )
            session.add(member)
            await session.commit()

        return group

    async def get_group_by_id(self, group_id: str) -> Group | None:
        """Get a group by ID."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(select(Group).where(Group.id == group_id))
            return result.scalar_one_or_none()

    async def get_groups_for_user(self, user_id: str) -> list[tuple[Group, int]]:
        """Get all groups a user belongs to, with member counts."""
        member_count = (
            select(func.count())
            .select_from(GroupMember)
            .where(GroupMember.group_id == Group.id)
            .correlate(Group)
            .scalar_subquery()
        )

        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(Group, member_count)
                .join(GroupMember, GroupMember.group_id == Group.id)
                .where(GroupMember.user_id == user_id)
                .order_by(Group.name)
            )
            return [(row[0], row[1]) for row in result.all()]

    async def get_all_groups(self) -> list[tuple[Group, int]]:
        """Get all groups with member counts (admin view)."""
        member_count = (
            select(func.count())
            .select_from(GroupMember)
            .where(GroupMember.group_id == Group.id)
            .correlate(Group)
            .scalar_subquery()
        )

        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(Group, member_count).order_by(Group.name)
            )
            return [(row[0], row[1]) for row in result.all()]

    async def update_group(
        self,
        group_id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> bool:
        """Update group fields. Returns True if group was found and updated."""
        values: dict = {"updated_at": datetime.now(timezone.utc)}
        if name is not None:
            values["name"] = name
        if description is not None:
            values["description"] = description

        async with db.ensure_initialized()() as session:
            result = await session.execute(
                update(Group).where(Group.id == group_id).values(**values)
            )
            await session.commit()
            return result.rowcount > 0

    async def delete_group(self, group_id: str) -> bool:
        """Delete a group. Returns True if group was found and deleted."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                delete(Group).where(Group.id == group_id)
            )
            await session.commit()
            return result.rowcount > 0

    async def add_member(
        self,
        group_id: str,
        user_id: str,
        role: GroupRole = GroupRole.MEMBER,
    ) -> bool:
        """Add a member to a group. Returns False if already a member."""
        async with db.ensure_initialized()() as session:
            # Check if already a member
            existing = await session.execute(
                select(GroupMember).where(
                    GroupMember.group_id == group_id,
                    GroupMember.user_id == user_id,
                )
            )
            if existing.scalar_one_or_none() is not None:
                return False

            member = GroupMember(
                group_id=group_id,
                user_id=user_id,
                role=role.value,
                joined_at=datetime.now(timezone.utc),
            )
            session.add(member)
            await session.commit()
            return True

    async def remove_member(self, group_id: str, user_id: str) -> bool:
        """Remove a member from a group. Returns True if member was found."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                delete(GroupMember).where(
                    GroupMember.group_id == group_id,
                    GroupMember.user_id == user_id,
                )
            )
            await session.commit()
            return result.rowcount > 0

    async def get_members(self, group_id: str) -> list[tuple[GroupMember, UserModel]]:
        """Get all members of a group with user details."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(GroupMember, UserModel)
                .join(UserModel, UserModel.id == GroupMember.user_id)
                .where(GroupMember.group_id == group_id)
                .order_by(GroupMember.role, UserModel.username)
            )
            return [(row[0], row[1]) for row in result.all()]

    async def is_member(self, group_id: str, user_id: str) -> bool:
        """Check if a user is a member of a group."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(GroupMember.user_id).where(
                    GroupMember.group_id == group_id,
                    GroupMember.user_id == user_id,
                )
            )
            return result.scalar_one_or_none() is not None

    async def get_member_role(self, group_id: str, user_id: str) -> GroupRole | None:
        """Get a user's role in a group, or None if not a member."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(GroupMember.role).where(
                    GroupMember.group_id == group_id,
                    GroupMember.user_id == user_id,
                )
            )
            role_str = result.scalar_one_or_none()
            return GroupRole(role_str) if role_str else None


class BotAccessRepository:
    """Repository for bot-group access operations."""

    async def share_bot(
        self,
        bot_id: str,
        group_id: str,
        access_level: BotAccessLevel,
        granted_by: str,
    ) -> BotGroupAccess:
        """Share a bot with a group."""
        record_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        async with db.ensure_initialized()() as session:
            record = BotGroupAccess(
                id=record_id,
                bot_id=bot_id,
                group_id=group_id,
                access_level=access_level.value,
                granted_by=granted_by,
                granted_at=now,
            )
            session.add(record)
            await session.commit()

        return record

    async def revoke_access(self, bot_id: str, group_id: str) -> bool:
        """Revoke a group's access to a bot. Returns True if record was found."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                delete(BotGroupAccess).where(
                    BotGroupAccess.bot_id == bot_id,
                    BotGroupAccess.group_id == group_id,
                )
            )
            await session.commit()
            return result.rowcount > 0

    async def update_access_level(
        self,
        bot_id: str,
        group_id: str,
        access_level: BotAccessLevel,
    ) -> bool:
        """Update the access level for a bot-group pair. Returns True if found."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                update(BotGroupAccess)
                .where(
                    BotGroupAccess.bot_id == bot_id,
                    BotGroupAccess.group_id == group_id,
                )
                .values(access_level=access_level.value)
            )
            await session.commit()
            return result.rowcount > 0

    async def get_bot_shares(self, bot_id: str) -> list[tuple[BotGroupAccess, Group]]:
        """Get all group access records for a bot."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(BotGroupAccess, Group)
                .join(Group, Group.id == BotGroupAccess.group_id)
                .where(BotGroupAccess.bot_id == bot_id)
                .order_by(Group.name)
            )
            return [(row[0], row[1]) for row in result.all()]

    async def get_user_bot_access_level(
        self, user_id: str, bot_id: str
    ) -> BotAccessLevel | None:
        """Get the highest access level a user has for a bot across all their groups.

        Returns None if the user has no group-based access.
        """
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(BotGroupAccess.access_level)
                .join(GroupMember, GroupMember.group_id == BotGroupAccess.group_id)
                .where(
                    BotGroupAccess.bot_id == bot_id,
                    GroupMember.user_id == user_id,
                )
            )
            levels = [row[0] for row in result.all()]

        if not levels:
            return None

        # Return highest access level
        rank = {"viewer": 1, "operator": 2, "editor": 3}
        best = max(levels, key=lambda lvl: rank.get(lvl, 0))
        return BotAccessLevel(best)

    async def get_accessible_bot_ids(
        self, user_id: str
    ) -> list[tuple[str, BotAccessLevel]]:
        """Get all bot IDs accessible to a user via groups, with their highest access level."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(BotGroupAccess.bot_id, BotGroupAccess.access_level)
                .join(GroupMember, GroupMember.group_id == BotGroupAccess.group_id)
                .where(GroupMember.user_id == user_id)
            )
            rows = result.all()

        # Aggregate: for each bot, keep highest access level
        rank = {"viewer": 1, "operator": 2, "editor": 3}
        best_per_bot: dict[str, str] = {}
        for bot_id, level in rows:
            current = best_per_bot.get(bot_id)
            if current is None or rank.get(level, 0) > rank.get(current, 0):
                best_per_bot[bot_id] = level

        return [(bid, BotAccessLevel(lvl)) for bid, lvl in best_per_bot.items()]
