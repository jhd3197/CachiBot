"""Rooms API Routes.

Endpoints for managing multi-agent rooms, membership, bots, and transcripts.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from cachibot.api.auth import get_current_user
from cachibot.api.helpers import require_found
from cachibot.models.auth import User
from cachibot.models.room import (
    ALLOWED_EMOJIS,
    VALID_ACTION_TYPES,
    VALID_TRIGGER_TYPES,
    AddBotRequest,
    AddReactionRequest,
    CreateRoomAutomationRequest,
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
    UpdateRoomAutomationRequest,
    UpdateRoomRequest,
)
from cachibot.storage.repository import BotRepository
from cachibot.storage.room_repository import (
    RoomAutomationRepository,
    RoomBookmarkRepository,
    RoomBotRepository,
    RoomMemberRepository,
    RoomMessageRepository,
    RoomPinRepository,
    RoomReactionRepository,
    RoomRepository,
)
from cachibot.storage.user_repository import UserRepository

router = APIRouter(prefix="/api/rooms", tags=["rooms"])

room_repo = RoomRepository()
member_repo = RoomMemberRepository()
bot_repo = RoomBotRepository()
message_repo = RoomMessageRepository()
reaction_repo = RoomReactionRepository()
pin_repo = RoomPinRepository()
bookmark_repo = RoomBookmarkRepository()
automation_repo = RoomAutomationRepository()
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
        require_found(await backend_bot_repo.get_bot(bid), f"Bot {bid}")

    now = datetime.now(timezone.utc)
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
    room = require_found(await room_repo.get_room(room_id), "Room")

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
    room = require_found(await room_repo.get_room(room_id), "Room")

    role = await member_repo.get_member_role(room_id, user.id)
    if role != RoomMemberRole.CREATOR:
        raise HTTPException(status_code=403, detail="Only the room creator can update settings")

    updated = await room_repo.update_room(
        room_id,
        title=data.title,
        description=data.description,
        settings=data.settings,
    )
    require_found(updated, "Room")

    # Sync live orchestrator with new settings
    if data.settings:
        from cachibot.services.room_orchestrator import get_room_orchestrator

        orch = get_room_orchestrator(room_id)
        if orch:
            orch.cooldown_seconds = data.settings.cooldown_seconds
            orch.auto_relevance = data.settings.auto_relevance
            orch.response_mode = data.settings.response_mode
            orch.room_system_prompt = data.settings.system_prompt
            orch.room_variables = dict(data.settings.variables)

        # Broadcast variable updates to connected clients
        if data.settings.variables:
            from cachibot.api.room_websocket import room_manager
            from cachibot.models.room_websocket import RoomWSMessage

            await room_manager.broadcast_to_room(
                room_id,
                RoomWSMessage.variable_update(room_id, data.settings.variables),
            )

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
    room = require_found(await room_repo.get_room(room_id), "Room")

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
    room = require_found(await room_repo.get_room(room_id), "Room")

    role = await member_repo.get_member_role(room_id, user.id)
    if role != RoomMemberRole.CREATOR:
        raise HTTPException(status_code=403, detail="Only the creator can invite members")

    # Look up user by username
    target_user = require_found(await user_repo.get_user_by_username(data.username), "User")

    # Check not already a member
    if await member_repo.is_member(room_id, target_user.id):
        raise HTTPException(status_code=409, detail="User is already a member")

    member = RoomMember(
        room_id=room_id,
        user_id=target_user.id,
        username=target_user.username,
        role=RoomMemberRole.MEMBER,
        joined_at=datetime.now(timezone.utc),
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
    room = require_found(await room_repo.get_room(room_id), "Room")

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
    room = require_found(await room_repo.get_room(room_id), "Room")

    if not await member_repo.is_member(room_id, user.id):
        raise HTTPException(status_code=403, detail="Not a room member")

    current_count = await bot_repo.get_bot_count(room_id)
    if current_count >= 4:
        raise HTTPException(status_code=400, detail="Maximum of 4 bots per room")

    bot = require_found(await backend_bot_repo.get_bot(data.bot_id), "Bot")

    rb = RoomBot(
        room_id=room_id,
        bot_id=data.bot_id,
        bot_name=bot.name,
        added_at=datetime.now(timezone.utc),
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
    room = require_found(await room_repo.get_room(room_id), "Room")

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
    room = require_found(await room_repo.get_room(room_id), "Room")

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

    require_found(await bot_repo.update_bot_role(room_id, bot_id, data.role), "Bot in room")

    return {"botId": bot_id, "role": data.role}


# =============================================================================
# MESSAGES / TRANSCRIPT
# =============================================================================


@router.post("/{room_id}/clear-messages", status_code=200)
async def clear_room_messages(
    room_id: str,
    user: User = Depends(get_current_user),
) -> dict[str, int]:
    """Delete all messages in a room (members only)."""
    room = require_found(await room_repo.get_room(room_id), "Room")

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
    room = require_found(await room_repo.get_room(room_id), "Room")

    if not await member_repo.is_member(room_id, user.id):
        raise HTTPException(status_code=403, detail="Not a room member")

    messages = await message_repo.get_messages(room_id, limit=limit, before=before)

    # Bulk-load reactions for all messages
    msg_ids = [m.id for m in messages]
    reactions_map = await reaction_repo.get_reactions_bulk(msg_ids)

    return [
        RoomMessageResponse.from_message(m, reactions=reactions_map.get(m.id, [])) for m in messages
    ]


# =============================================================================
# REACTIONS
# =============================================================================


@router.post("/{room_id}/messages/{message_id}/reactions", status_code=201)
async def add_reaction(
    room_id: str,
    message_id: str,
    data: AddReactionRequest,
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Add an emoji reaction to a message."""
    if data.emoji not in ALLOWED_EMOJIS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid emoji. Allowed: {', '.join(ALLOWED_EMOJIS)}",
        )

    if not await member_repo.is_member(room_id, user.id):
        raise HTTPException(status_code=403, detail="Not a room member")

    reaction_id = str(uuid.uuid4())
    added = await reaction_repo.add_reaction(reaction_id, room_id, message_id, user.id, data.emoji)
    if not added:
        raise HTTPException(status_code=409, detail="Reaction already exists")

    # Broadcast via WS
    from cachibot.api.room_websocket import room_manager
    from cachibot.models.room_websocket import RoomWSMessage

    await room_manager.broadcast_to_room(
        room_id,
        RoomWSMessage.reaction_add(room_id, message_id, user.id, data.emoji),
    )

    return {"id": reaction_id, "emoji": data.emoji}


@router.delete("/{room_id}/messages/{message_id}/reactions", status_code=204)
async def remove_reaction(
    room_id: str,
    message_id: str,
    emoji: str,
    user: User = Depends(get_current_user),
) -> None:
    """Remove an emoji reaction from a message."""
    if not await member_repo.is_member(room_id, user.id):
        raise HTTPException(status_code=403, detail="Not a room member")

    require_found(await reaction_repo.remove_reaction(room_id, message_id, user.id, emoji), "Reaction")

    # Broadcast via WS
    from cachibot.api.room_websocket import room_manager
    from cachibot.models.room_websocket import RoomWSMessage

    await room_manager.broadcast_to_room(
        room_id,
        RoomWSMessage.reaction_remove(room_id, message_id, user.id, emoji),
    )


# =============================================================================
# PINNED MESSAGES
# =============================================================================


@router.post("/{room_id}/pins/{message_id}", status_code=201)
async def pin_message(
    room_id: str,
    message_id: str,
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Pin a message in the room."""
    if not await member_repo.is_member(room_id, user.id):
        raise HTTPException(status_code=403, detail="Not a room member")

    pin_id = str(uuid.uuid4())
    pinned = await pin_repo.pin_message(pin_id, room_id, message_id, user.id)
    if not pinned:
        raise HTTPException(status_code=409, detail="Message already pinned")

    # Broadcast via WS
    from cachibot.api.room_websocket import room_manager
    from cachibot.models.room_websocket import RoomWSMessage

    await room_manager.broadcast_to_room(
        room_id,
        RoomWSMessage.pin_add(room_id, message_id, user.id),
    )

    return {"id": pin_id, "messageId": message_id}


@router.delete("/{room_id}/pins/{message_id}", status_code=204)
async def unpin_message(
    room_id: str,
    message_id: str,
    user: User = Depends(get_current_user),
) -> None:
    """Unpin a message from the room."""
    if not await member_repo.is_member(room_id, user.id):
        raise HTTPException(status_code=403, detail="Not a room member")

    require_found(await pin_repo.unpin_message(room_id, message_id), "Pin")

    # Broadcast via WS
    from cachibot.api.room_websocket import room_manager
    from cachibot.models.room_websocket import RoomWSMessage

    await room_manager.broadcast_to_room(
        room_id,
        RoomWSMessage.pin_remove(room_id, message_id),
    )


@router.get("/{room_id}/pins")
async def get_pinned_messages(
    room_id: str,
    user: User = Depends(get_current_user),
) -> list[dict[str, str]]:
    """Get all pinned messages for a room."""
    if not await member_repo.is_member(room_id, user.id):
        raise HTTPException(status_code=403, detail="Not a room member")

    pins = await pin_repo.get_pinned_messages(room_id)
    return [pin.model_dump() for pin in pins]


# =============================================================================
# BOOKMARKS
# =============================================================================


@router.post("/{room_id}/bookmarks/{message_id}", status_code=201)
async def add_bookmark(
    room_id: str,
    message_id: str,
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Bookmark a message (personal, not shared)."""
    if not await member_repo.is_member(room_id, user.id):
        raise HTTPException(status_code=403, detail="Not a room member")

    bookmark_id = str(uuid.uuid4())
    added = await bookmark_repo.add_bookmark(bookmark_id, room_id, message_id, user.id)
    if not added:
        raise HTTPException(status_code=409, detail="Already bookmarked")

    return {"id": bookmark_id, "messageId": message_id}


@router.delete("/{room_id}/bookmarks/{message_id}", status_code=204)
async def remove_bookmark(
    room_id: str,
    message_id: str,
    user: User = Depends(get_current_user),
) -> None:
    """Remove a bookmark."""
    require_found(await bookmark_repo.remove_bookmark(user.id, message_id), "Bookmark")


@router.get("/bookmarks")
async def get_bookmarks(
    room_id: str | None = None,
    user: User = Depends(get_current_user),
) -> list[dict[str, str]]:
    """Get all bookmarks for the current user."""
    bookmarks = await bookmark_repo.get_bookmarks(user.id, room_id=room_id)
    return [bm.model_dump() for bm in bookmarks]


# =============================================================================
# AUTOMATIONS
# =============================================================================


@router.get("/{room_id}/automations")
async def get_automations(
    room_id: str,
    user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Get all automations for a room."""
    if not await member_repo.is_member(room_id, user.id):
        raise HTTPException(status_code=403, detail="Not a room member")
    automations = await automation_repo.get_automations(room_id)
    return [a.model_dump() for a in automations]


@router.post("/{room_id}/automations", status_code=201)
async def create_automation(
    room_id: str,
    req: CreateRoomAutomationRequest,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Create a new automation for a room."""
    room = require_found(await room_repo.get_room(room_id), "Room")
    if room.creator_id != user.id:
        raise HTTPException(status_code=403, detail="Only the room creator can manage automations")
    if req.trigger_type not in VALID_TRIGGER_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid trigger_type. Must be one of: {VALID_TRIGGER_TYPES}",
        )
    if req.action_type not in VALID_ACTION_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action_type. Must be one of: {VALID_ACTION_TYPES}",
        )

    auto = await automation_repo.create(
        automation_id=str(uuid.uuid4()),
        room_id=room_id,
        name=req.name,
        trigger_type=req.trigger_type,
        trigger_config=req.trigger_config,
        action_type=req.action_type,
        action_config=req.action_config,
        created_by=user.id,
    )
    return auto.model_dump()


@router.patch("/{room_id}/automations/{automation_id}")
async def update_automation(
    room_id: str,
    automation_id: str,
    req: UpdateRoomAutomationRequest,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Update an automation."""
    room = require_found(await room_repo.get_room(room_id), "Room")
    if room.creator_id != user.id:
        raise HTTPException(status_code=403, detail="Only the room creator can manage automations")

    if req.trigger_type and req.trigger_type not in VALID_TRIGGER_TYPES:
        raise HTTPException(status_code=400, detail="Invalid trigger_type")
    if req.action_type and req.action_type not in VALID_ACTION_TYPES:
        raise HTTPException(status_code=400, detail="Invalid action_type")

    updated = await automation_repo.update(
        automation_id,
        name=req.name,
        enabled=req.enabled,
        trigger_type=req.trigger_type,
        trigger_config=req.trigger_config,
        action_type=req.action_type,
        action_config=req.action_config,
    )
    require_found(updated, "Automation")
    return updated.model_dump()


@router.delete("/{room_id}/automations/{automation_id}", status_code=204)
async def delete_automation(
    room_id: str,
    automation_id: str,
    user: User = Depends(get_current_user),
) -> None:
    """Delete an automation."""
    room = require_found(await room_repo.get_room(room_id), "Room")
    if room.creator_id != user.id:
        raise HTTPException(status_code=403, detail="Only the room creator can manage automations")
    require_found(await automation_repo.delete(automation_id), "Automation")
