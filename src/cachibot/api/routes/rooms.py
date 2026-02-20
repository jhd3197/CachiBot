"""Rooms API Routes.

Endpoints for managing multi-agent rooms, membership, bots, and transcripts.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from cachibot.api.auth import get_current_user
from cachibot.models.auth import User
from cachibot.models.room import (
    AddBotRequest,
    CreateRoomRequest,
    InviteMemberRequest,
    Room,
    RoomBot,
    RoomBotRole,
    RoomMember,
    RoomMemberRole,
    RoomMessageResponse,
    RoomResponse,
    UpdateBotRoleRequest,
    UpdateRoomRequest,
)
from cachibot.storage.repository import BotRepository
from cachibot.storage.room_repository import (
    RoomBotRepository,
    RoomMemberRepository,
    RoomMessageRepository,
    RoomRepository,
)
from cachibot.storage.user_repository import UserRepository

router = APIRouter(prefix="/api/rooms", tags=["rooms"])

room_repo = RoomRepository()
member_repo = RoomMemberRepository()
bot_repo = RoomBotRepository()
message_repo = RoomMessageRepository()
user_repo = UserRepository()
backend_bot_repo = BotRepository()


@router.post("", status_code=201)
async def create_room(
    data: CreateRoomRequest,
    user: User = Depends(get_current_user),
) -> RoomResponse:
    """Create a new room. Creator is auto-added as a member."""
    # Validate bot count
    if len(data.bot_ids) < 2 or len(data.bot_ids) > 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rooms require 2-4 bots",
        )

    # Validate bots exist
    for bid in data.bot_ids:
        bot = await backend_bot_repo.get_bot(bid)
        if bot is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bot {bid} not found",
            )

    now = datetime.utcnow()
    room = Room(
        id=str(uuid.uuid4()),
        title=data.title,
        description=data.description,
        creator_id=user.id,
        max_bots=max(len(data.bot_ids), 2),
        settings=data.settings,
        created_at=now,
        updated_at=now,
    )
    await room_repo.create_room(room)

    # Add creator as member
    creator_member = RoomMember(
        room_id=room.id,
        user_id=user.id,
        username=user.username,
        role=RoomMemberRole.CREATOR,
        joined_at=now,
    )
    await member_repo.add_member(creator_member)

    # Add bots
    room_bots = []
    for bid in data.bot_ids:
        bot = await backend_bot_repo.get_bot(bid)
        rb = RoomBot(
            room_id=room.id,
            bot_id=bid,
            bot_name=bot.name if bot else "",
            added_at=now,
        )
        await bot_repo.add_bot(rb)
        room_bots.append(rb)

    members = await member_repo.get_members(room.id)
    return RoomResponse.from_room(room, members, room_bots, message_count=0)


@router.get("")
async def list_rooms(
    user: User = Depends(get_current_user),
) -> list[RoomResponse]:
    """List all rooms the current user is a member of."""
    rooms = await room_repo.get_rooms_for_user(user.id)
    result = []
    for room in rooms:
        members = await member_repo.get_members(room.id)
        bots = await bot_repo.get_bots(room.id)
        count = await message_repo.get_message_count(room.id)
        result.append(RoomResponse.from_room(room, members, bots, count))
    return result


@router.get("/{room_id}")
async def get_room(
    room_id: str,
    user: User = Depends(get_current_user),
) -> RoomResponse:
    """Get room details."""
    room = await room_repo.get_room(room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")

    if not await member_repo.is_member(room_id, user.id):
        raise HTTPException(status_code=403, detail="Not a room member")

    members = await member_repo.get_members(room_id)
    bots = await bot_repo.get_bots(room_id)
    count = await message_repo.get_message_count(room_id)
    return RoomResponse.from_room(room, members, bots, count)


@router.patch("/{room_id}")
async def update_room(
    room_id: str,
    data: UpdateRoomRequest,
    user: User = Depends(get_current_user),
) -> RoomResponse:
    """Update room details (creator only)."""
    room = await room_repo.get_room(room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")

    role = await member_repo.get_member_role(room_id, user.id)
    if role != RoomMemberRole.CREATOR:
        raise HTTPException(status_code=403, detail="Only the room creator can update settings")

    updated = await room_repo.update_room(
        room_id,
        title=data.title,
        description=data.description,
        settings=data.settings,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Room not found")

    # Sync live orchestrator with new settings
    if data.settings:
        from cachibot.services.room_orchestrator import get_room_orchestrator

        orch = get_room_orchestrator(room_id)
        if orch:
            orch.cooldown_seconds = data.settings.cooldown_seconds
            orch.auto_relevance = data.settings.auto_relevance
            orch.response_mode = data.settings.response_mode

    members = await member_repo.get_members(room_id)
    bots = await bot_repo.get_bots(room_id)
    count = await message_repo.get_message_count(room_id)
    return RoomResponse.from_room(updated, members, bots, count)


@router.delete("/{room_id}", status_code=204)
async def delete_room(
    room_id: str,
    user: User = Depends(get_current_user),
) -> None:
    """Delete a room (creator only)."""
    room = await room_repo.get_room(room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")

    role = await member_repo.get_member_role(room_id, user.id)
    if role != RoomMemberRole.CREATOR:
        raise HTTPException(status_code=403, detail="Only the room creator can delete the room")

    await room_repo.delete_room(room_id)


# =============================================================================
# MEMBERS
# =============================================================================


@router.post("/{room_id}/members")
async def invite_member(
    room_id: str,
    data: InviteMemberRequest,
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Invite a user to the room by username (creator only)."""
    room = await room_repo.get_room(room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")

    role = await member_repo.get_member_role(room_id, user.id)
    if role != RoomMemberRole.CREATOR:
        raise HTTPException(status_code=403, detail="Only the creator can invite members")

    # Look up user by username
    target_user = await user_repo.get_user_by_username(data.username)
    if target_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Check not already a member
    if await member_repo.is_member(room_id, target_user.id):
        raise HTTPException(status_code=409, detail="User is already a member")

    member = RoomMember(
        room_id=room_id,
        user_id=target_user.id,
        username=target_user.username,
        role=RoomMemberRole.MEMBER,
        joined_at=datetime.utcnow(),
    )
    await member_repo.add_member(member)

    return {"userId": target_user.id, "username": target_user.username}


@router.delete("/{room_id}/members/{target_user_id}", status_code=204)
async def remove_member(
    room_id: str,
    target_user_id: str,
    user: User = Depends(get_current_user),
) -> None:
    """Remove a member from the room (creator only, or self-leave)."""
    room = await room_repo.get_room(room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")

    # Allow self-leave or creator removal
    is_self = user.id == target_user_id
    role = await member_repo.get_member_role(room_id, user.id)

    if not is_self and role != RoomMemberRole.CREATOR:
        raise HTTPException(status_code=403, detail="Only the creator can remove members")

    # Prevent creator from removing themselves
    if is_self and role == RoomMemberRole.CREATOR:
        raise HTTPException(status_code=400, detail="Room creator cannot leave. Delete the room.")

    await member_repo.remove_member(room_id, target_user_id)


# =============================================================================
# BOTS
# =============================================================================


@router.post("/{room_id}/bots")
async def add_bot(
    room_id: str,
    data: AddBotRequest,
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Add a bot to the room (enforces max 4)."""
    room = await room_repo.get_room(room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")

    if not await member_repo.is_member(room_id, user.id):
        raise HTTPException(status_code=403, detail="Not a room member")

    current_count = await bot_repo.get_bot_count(room_id)
    if current_count >= 4:
        raise HTTPException(status_code=400, detail="Maximum of 4 bots per room")

    bot = await backend_bot_repo.get_bot(data.bot_id)
    if bot is None:
        raise HTTPException(status_code=404, detail="Bot not found")

    rb = RoomBot(
        room_id=room_id,
        bot_id=data.bot_id,
        bot_name=bot.name,
        added_at=datetime.utcnow(),
    )
    await bot_repo.add_bot(rb)

    return {"botId": data.bot_id, "botName": bot.name}


@router.delete("/{room_id}/bots/{bot_id}", status_code=204)
async def remove_bot(
    room_id: str,
    bot_id: str,
    user: User = Depends(get_current_user),
) -> None:
    """Remove a bot from the room (enforces min 2)."""
    room = await room_repo.get_room(room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")

    if not await member_repo.is_member(room_id, user.id):
        raise HTTPException(status_code=403, detail="Not a room member")

    current_count = await bot_repo.get_bot_count(room_id)
    if current_count <= 2:
        raise HTTPException(status_code=400, detail="Rooms must have at least 2 bots")

    await bot_repo.remove_bot(room_id, bot_id)


@router.patch("/{room_id}/bots/{bot_id}/role")
async def update_bot_role(
    room_id: str,
    bot_id: str,
    data: UpdateBotRoleRequest,
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Update a bot's role in the room (creator only)."""
    room = await room_repo.get_room(room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")

    role = await member_repo.get_member_role(room_id, user.id)
    if role != RoomMemberRole.CREATOR:
        raise HTTPException(status_code=403, detail="Only the room creator can update bot roles")

    # Validate role value
    valid_roles = {r.value for r in RoomBotRole}
    if data.role not in valid_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}",
        )

    updated = await bot_repo.update_bot_role(room_id, bot_id, data.role)
    if not updated:
        raise HTTPException(status_code=404, detail="Bot not found in room")

    return {"botId": bot_id, "role": data.role}


# =============================================================================
# MESSAGES / TRANSCRIPT
# =============================================================================


@router.post("/{room_id}/messages/_clear", status_code=200)
async def clear_room_messages(
    room_id: str,
    user: User = Depends(get_current_user),
) -> dict[str, int]:
    """Delete all messages in a room (members only)."""
    room = await room_repo.get_room(room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")

    if not await member_repo.is_member(room_id, user.id):
        raise HTTPException(status_code=403, detail="Not a room member")

    deleted = await message_repo.delete_messages(room_id)
    return {"deleted": deleted}


@router.get("/{room_id}/messages")
async def get_room_messages(
    room_id: str,
    limit: int = 50,
    before: str | None = None,
    user: User = Depends(get_current_user),
) -> list[RoomMessageResponse]:
    """Get paginated room transcript."""
    room = await room_repo.get_room(room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")

    if not await member_repo.is_member(room_id, user.id):
        raise HTTPException(status_code=403, detail="Not a room member")

    messages = await message_repo.get_messages(room_id, limit=limit, before=before)
    return [RoomMessageResponse.from_message(m) for m in messages]
