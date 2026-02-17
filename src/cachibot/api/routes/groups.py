"""
Groups API Routes

CRUD endpoints for user groups and group membership.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from cachibot.api.auth import get_current_user, get_manager_or_admin_user
from cachibot.models.auth import User, UserRole
from cachibot.models.group import (
    AddMemberRequest,
    CreateGroupRequest,
    GroupRole,
    GroupWithMembers,
    UpdateGroupRequest,
)
from cachibot.models.group import (
    Group as GroupResponse,
)
from cachibot.models.group import (
    GroupMember as GroupMemberResponse,
)
from cachibot.storage.group_repository import GroupRepository
from cachibot.storage.user_repository import UserRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/groups", tags=["groups"])

group_repo = GroupRepository()
user_repo = UserRepository()


@router.get("")
async def list_groups(
    user: User = Depends(get_current_user),
) -> list[GroupResponse]:
    """List groups. Admins see all; others see only their groups."""
    if user.role == UserRole.ADMIN:
        rows = await group_repo.get_all_groups()
    else:
        rows = await group_repo.get_groups_for_user(user.id)

    return [
        GroupResponse(
            id=g.id,
            name=g.name,
            description=g.description,
            created_by=g.created_by,
            created_at=g.created_at,
            updated_at=g.updated_at,
            member_count=count,
        )
        for g, count in rows
    ]


@router.post("", status_code=201)
async def create_group(
    body: CreateGroupRequest,
    user: User = Depends(get_manager_or_admin_user),
) -> GroupResponse:
    """Create a new group. Requires manager or admin role."""
    group = await group_repo.create_group(
        name=body.name,
        created_by=user.id,
        description=body.description,
    )
    return GroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        created_by=group.created_by,
        created_at=group.created_at,
        updated_at=group.updated_at,
        member_count=1,  # Creator is auto-added
    )


@router.get("/{group_id}")
async def get_group(
    group_id: str,
    user: User = Depends(get_current_user),
) -> GroupWithMembers:
    """Get a group with its members. Must be a member or admin."""
    group = await group_repo.get_group_by_id(group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")

    # Access check: must be member or admin
    if user.role != UserRole.ADMIN:
        is_member = await group_repo.is_member(group_id, user.id)
        if not is_member:
            raise HTTPException(status_code=403, detail="Not a member of this group")

    members_data = await group_repo.get_members(group_id)
    members = [
        GroupMemberResponse(
            user_id=member.user_id,
            username=u.username,
            email=u.email,
            role=GroupRole(member.role),
            joined_at=member.joined_at,
        )
        for member, u in members_data
    ]

    return GroupWithMembers(
        id=group.id,
        name=group.name,
        description=group.description,
        created_by=group.created_by,
        created_at=group.created_at,
        updated_at=group.updated_at,
        member_count=len(members),
        members=members,
    )


@router.put("/{group_id}")
async def update_group(
    group_id: str,
    body: UpdateGroupRequest,
    user: User = Depends(get_current_user),
) -> GroupResponse:
    """Update a group. Must be group owner or admin."""
    group = await group_repo.get_group_by_id(group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")

    await _require_group_admin(group_id, user)

    await group_repo.update_group(
        group_id,
        name=body.name,
        description=body.description,
    )

    updated = await group_repo.get_group_by_id(group_id)
    members_data = await group_repo.get_members(group_id)

    return GroupResponse(
        id=updated.id,
        name=updated.name,
        description=updated.description,
        created_by=updated.created_by,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
        member_count=len(members_data),
    )


@router.delete("/{group_id}", status_code=204)
async def delete_group(
    group_id: str,
    user: User = Depends(get_current_user),
) -> None:
    """Delete a group. Must be group owner or admin."""
    group = await group_repo.get_group_by_id(group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")

    await _require_group_admin(group_id, user)

    await group_repo.delete_group(group_id)


@router.post("/{group_id}/members", status_code=201)
async def add_member(
    group_id: str,
    body: AddMemberRequest,
    user: User = Depends(get_current_user),
) -> GroupMemberResponse:
    """Add a member to a group. Must be group owner or admin."""
    group = await group_repo.get_group_by_id(group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")

    await _require_group_admin(group_id, user)

    # Verify user exists
    target_user = await user_repo.get_user_by_id(body.user_id)
    if target_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    added = await group_repo.add_member(group_id, body.user_id, body.role)
    if not added:
        raise HTTPException(status_code=409, detail="User is already a member")

    return GroupMemberResponse(
        user_id=target_user.id,
        username=target_user.username,
        email=target_user.email,
        role=body.role,
        joined_at=target_user.created_at,  # approximate; actual joined_at set by DB
    )


@router.delete("/{group_id}/members/{user_id}", status_code=204)
async def remove_member(
    group_id: str,
    user_id: str,
    user: User = Depends(get_current_user),
) -> None:
    """Remove a member from a group. Must be group owner or admin."""
    group = await group_repo.get_group_by_id(group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")

    await _require_group_admin(group_id, user)

    removed = await group_repo.remove_member(group_id, user_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Member not found")


async def _require_group_admin(group_id: str, user: User) -> None:
    """Helper: require user is group owner or system admin."""
    if user.role == UserRole.ADMIN:
        return

    role = await group_repo.get_member_role(group_id, user.id)
    if role != GroupRole.OWNER:
        raise HTTPException(
            status_code=403,
            detail="Only group owners or admins can perform this action",
        )
