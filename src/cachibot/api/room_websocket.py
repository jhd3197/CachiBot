"""Room WebSocket Handler.

Handles real-time multi-user, multi-bot room communication.
"""

import asyncio
import copy
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from prompture import StreamEventType

from cachibot.agent import CachibotAgent, load_disabled_capabilities
from cachibot.api.auth import get_user_from_token
from cachibot.config import Config
from cachibot.models.auth import User
from cachibot.models.room import RoomMessage, RoomSenderType
from cachibot.models.room_websocket import RoomWSMessage, RoomWSMessageType
from cachibot.services.room_orchestrator import (
    create_room_orchestrator,
    get_room_orchestrator,
    remove_room_orchestrator,
)
from cachibot.storage.repository import BotRepository
from cachibot.storage.room_repository import (
    RoomBotRepository,
    RoomMemberRepository,
    RoomMessageRepository,
    RoomRepository,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class RoomConnectionManager:
    """Manages WebSocket connections for rooms."""

    def __init__(self):
        # room_id -> {user_id -> WebSocket}
        self.rooms: dict[str, dict[str, WebSocket]] = {}
        # room_id -> {bot_id -> asyncio.Task}
        self.bot_tasks: dict[str, dict[str, asyncio.Task]] = {}

    async def connect(self, room_id: str, user_id: str, websocket: WebSocket) -> None:
        """Accept and register a WebSocket connection for a room."""
        await websocket.accept()
        if room_id not in self.rooms:
            self.rooms[room_id] = {}
        self.rooms[room_id][user_id] = websocket

    def disconnect(self, room_id: str, user_id: str) -> None:
        """Remove a WebSocket connection."""
        if room_id in self.rooms:
            self.rooms[room_id].pop(user_id, None)
            if not self.rooms[room_id]:
                del self.rooms[room_id]
                # Cancel bot tasks and clean up orchestrator
                if room_id in self.bot_tasks:
                    for task in self.bot_tasks[room_id].values():
                        if not task.done():
                            task.cancel()
                    del self.bot_tasks[room_id]
                remove_room_orchestrator(room_id)

    async def broadcast_to_room(
        self, room_id: str, message: RoomWSMessage, exclude_user_id: str | None = None
    ) -> None:
        """Send a message to all users in a room."""
        connections = self.rooms.get(room_id, {})
        data = message.model_dump()
        for uid, ws in list(connections.items()):
            if uid == exclude_user_id:
                continue
            try:
                await ws.send_json(data)
            except Exception:
                logger.warning(f"Failed to send to user {uid} in room {room_id}")

    async def send_to_room(self, room_id: str, message: RoomWSMessage) -> None:
        """Send a message to ALL users in a room (no exclusions)."""
        connections = self.rooms.get(room_id, {})
        data = message.model_dump()
        for uid, ws in list(connections.items()):
            try:
                await ws.send_json(data)
            except Exception:
                logger.warning(f"Failed to send to user {uid} in room {room_id}")

    async def send_to_user(self, room_id: str, user_id: str, message: RoomWSMessage) -> None:
        """Send a message to a specific user in a room."""
        ws = self.rooms.get(room_id, {}).get(user_id)
        if ws:
            try:
                await ws.send_json(message.model_dump())
            except Exception:
                logger.warning(f"Failed to send to user {user_id} in room {room_id}")

    def get_online_users(self, room_id: str) -> list[str]:
        """Get list of online user IDs in a room."""
        return list(self.rooms.get(room_id, {}).keys())


room_manager = RoomConnectionManager()


@router.websocket("/ws/room")
async def room_websocket_endpoint(
    websocket: WebSocket,
    token: str | None = Query(default=None),
    room_id: str | None = Query(default=None),
):
    """WebSocket endpoint for room communication.

    Connect with: /ws/room?token=<jwt>&room_id=<room_id>
    """
    # Auth
    user: User | None = None
    if token:
        user = await get_user_from_token(token)
    if user is None:
        await websocket.close(code=4001, reason="Authentication required")
        return

    if not room_id:
        await websocket.close(code=4002, reason="room_id required")
        return

    # Verify room exists and user is a member
    room_repo = RoomRepository()
    member_repo = RoomMemberRepository()

    room = await room_repo.get_room(room_id)
    if room is None:
        await websocket.close(code=4003, reason="Room not found")
        return

    if not await member_repo.is_member(room_id, user.id):
        await websocket.close(code=4004, reason="Not a room member")
        return

    # Connect
    await room_manager.connect(room_id, user.id, websocket)

    # Initialize orchestrator if first connection
    orchestrator = get_room_orchestrator(room_id)
    if orchestrator is None:
        orchestrator = create_room_orchestrator(
            room_id=room_id,
            cooldown_seconds=room.settings.cooldown_seconds,
            auto_relevance=room.settings.auto_relevance,
        )
        # Load room bots into orchestrator
        bot_repo = RoomBotRepository()
        backend_bot_repo = BotRepository()
        room_bots = await bot_repo.get_bots(room_id)
        for rb in room_bots:
            bot = await backend_bot_repo.get_bot(rb.bot_id)
            if bot:
                orchestrator.register_bot(bot)

    # Broadcast presence
    await room_manager.broadcast_to_room(
        room_id,
        RoomWSMessage.presence(room_id, user.id, user.username, "online"),
        exclude_user_id=user.id,
    )

    # Send current online users to the newly connected client
    online_users = room_manager.get_online_users(room_id)
    for uid in online_users:
        if uid != user.id:
            # Fetch username for each online user
            from cachibot.storage.user_repository import UserRepository

            u_repo = UserRepository()
            u = await u_repo.get_user_by_id(uid)
            if u:
                await room_manager.send_to_user(
                    room_id,
                    user.id,
                    RoomWSMessage.presence(room_id, uid, u.username, "online"),
                )

    # Get workspace and config
    workspace = websocket.app.state.workspace
    config = Config.load(workspace=workspace)

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            payload = data.get("payload", {})

            if msg_type == RoomWSMessageType.ROOM_CHAT:
                message_text = payload.get("message", "")
                if not message_text:
                    continue

                # Save user message
                msg_repo = RoomMessageRepository()
                user_msg = RoomMessage(
                    id=str(uuid.uuid4()),
                    room_id=room_id,
                    sender_type=RoomSenderType.USER,
                    sender_id=user.id,
                    sender_name=user.username,
                    content=message_text,
                    timestamp=datetime.utcnow(),
                )
                await msg_repo.save_message(user_msg)

                # Broadcast user message to all
                await room_manager.send_to_room(
                    room_id,
                    RoomWSMessage.room_message(
                        room_id=room_id,
                        sender_type="user",
                        sender_id=user.id,
                        sender_name=user.username,
                        content=message_text,
                        message_id=user_msg.id,
                    ),
                )

                # Ask orchestrator which bots should respond
                respondents = orchestrator.select_respondents(message_text, "user")
                for bot_id in respondents:
                    bot = orchestrator.bot_configs.get(bot_id)
                    if not bot:
                        continue

                    orchestrator.mark_responding(bot_id)

                    # Broadcast thinking
                    await room_manager.send_to_room(
                        room_id,
                        RoomWSMessage.bot_thinking(room_id, bot_id, bot.name),
                    )

                    # Spawn bot response task
                    task = asyncio.create_task(
                        run_room_bot(
                            room_id=room_id,
                            bot_id=bot_id,
                            message=message_text,
                            config=config,
                        )
                    )
                    if room_id not in room_manager.bot_tasks:
                        room_manager.bot_tasks[room_id] = {}
                    room_manager.bot_tasks[room_id][bot_id] = task

            elif msg_type == RoomWSMessageType.ROOM_TYPING:
                is_typing = payload.get("isTyping", False)
                await room_manager.broadcast_to_room(
                    room_id,
                    RoomWSMessage.typing_indicator(room_id, user.id, user.username, is_typing),
                    exclude_user_id=user.id,
                )

            elif msg_type == RoomWSMessageType.ROOM_CANCEL:
                target_bot_id = payload.get("botId")
                if target_bot_id and room_id in room_manager.bot_tasks:
                    task = room_manager.bot_tasks[room_id].get(target_bot_id)
                    if task and not task.done():
                        task.cancel()

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Room WS error for user {user.id} in room {room_id}: {e}")
    finally:
        # Broadcast offline presence
        try:
            await room_manager.broadcast_to_room(
                room_id,
                RoomWSMessage.presence(room_id, user.id, user.username, "offline"),
                exclude_user_id=user.id,
            )
        except Exception:
            pass
        room_manager.disconnect(room_id, user.id)


async def run_room_bot(
    room_id: str,
    bot_id: str,
    message: str,
    config: Config,
) -> None:
    """Run a bot's response in a room.

    Streams the response and broadcasts to all room members.
    """
    orchestrator = get_room_orchestrator(room_id)
    if orchestrator is None:
        return

    bot = orchestrator.bot_configs.get(bot_id)
    if bot is None:
        return

    msg_repo = RoomMessageRepository()

    try:
        # Get recent messages for context
        recent = await msg_repo.get_messages(room_id, limit=50)
        room_context = orchestrator.build_room_context(bot_id, recent)

        # Build enhanced system prompt
        enhanced_prompt = (bot.system_prompt or "") + room_context

        # Create agent with bot config
        agent_config = copy.deepcopy(config)
        # Use bot's model if available
        effective_model = bot.model
        if effective_model:
            agent_config.agent.model = effective_model

        disabled_caps = await load_disabled_capabilities()
        agent = CachibotAgent(
            config=agent_config,
            system_prompt_override=enhanced_prompt,
            bot_id=bot_id,
            disabled_capabilities=disabled_caps,
        )

        # Stream response
        response_parts: list[str] = []
        response_msg_id = str(uuid.uuid4())

        async for event in agent.run_stream(message):
            match event.event_type:
                case StreamEventType.text_delta:
                    response_parts.append(event.data)
                    await room_manager.send_to_room(
                        room_id,
                        RoomWSMessage.room_message(
                            room_id=room_id,
                            sender_type="bot",
                            sender_id=bot_id,
                            sender_name=bot.name,
                            content=event.data,
                            message_id=response_msg_id,
                        ),
                    )
                case StreamEventType.tool_call:
                    await room_manager.send_to_room(
                        room_id,
                        RoomWSMessage.bot_tool_start(
                            room_id=room_id,
                            bot_id=bot_id,
                            bot_name=bot.name,
                            tool_id=event.data.get("id", ""),
                            tool_name=event.data["name"],
                            args=event.data.get("arguments", {}),
                        ),
                    )
                case StreamEventType.tool_result:
                    await room_manager.send_to_room(
                        room_id,
                        RoomWSMessage.bot_tool_end(
                            room_id=room_id,
                            bot_id=bot_id,
                            bot_name=bot.name,
                            tool_id=event.data.get("id", ""),
                            result=str(event.data.get("result", "")),
                        ),
                    )
                case StreamEventType.output:
                    pass  # Final result captured via response_parts

        # Save bot response
        full_response = "".join(response_parts)
        if full_response:
            bot_msg = RoomMessage(
                id=response_msg_id,
                room_id=room_id,
                sender_type=RoomSenderType.BOT,
                sender_id=bot_id,
                sender_name=bot.name,
                content=full_response,
                timestamp=datetime.utcnow(),
            )
            await msg_repo.save_message(bot_msg)

        # Broadcast done
        await room_manager.send_to_room(
            room_id,
            RoomWSMessage.bot_done(room_id, bot_id, bot.name),
        )

    except asyncio.CancelledError:
        await room_manager.send_to_room(
            room_id,
            RoomWSMessage.error(room_id, f"{bot.name} was cancelled", bot_id=bot_id),
        )
    except Exception as e:
        logger.error(f"Bot {bot_id} error in room {room_id}: {e}", exc_info=True)
        await room_manager.send_to_room(
            room_id,
            RoomWSMessage.error(room_id, f"{bot.name} encountered an error: {e}", bot_id=bot_id),
        )
    finally:
        if orchestrator:
            orchestrator.mark_done(bot_id)
