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
    route_message,
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

    def __init__(self) -> None:
        # room_id -> {user_id -> WebSocket}
        self.rooms: dict[str, dict[str, WebSocket]] = {}
        # room_id -> {bot_id -> asyncio.Task}
        self.bot_tasks: dict[str, dict[str, asyncio.Task]] = {}  # type: ignore[type-arg]

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
) -> None:
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
            response_mode=room.settings.response_mode,
        )

    # Always (re-)load bots — handles both fresh init and late-added bots
    bot_repo_ws = RoomBotRepository()
    backend_bot_repo_ws = BotRepository()
    room_bots = await bot_repo_ws.get_bots(room_id)
    failed_bots: list[str] = []
    for rb in room_bots:
        if rb.bot_id in orchestrator.bot_configs:
            continue  # Already registered
        bot = await backend_bot_repo_ws.get_bot(rb.bot_id)
        if bot:
            orchestrator.register_bot(bot)
            orchestrator.set_bot_role(rb.bot_id, rb.role)
        else:
            logger.warning(
                "Room %s: bot %s (%s) not found in bots table — skipped",
                room_id,
                rb.bot_id,
                rb.bot_name,
            )
            failed_bots.append(rb.bot_name or rb.bot_id)

    if failed_bots:
        await room_manager.send_to_user(
            room_id,
            user.id,
            RoomWSMessage.error(
                room_id,
                f"Could not load bot(s): {', '.join(failed_bots)}. "
                "They may need to be re-synced from bot settings.",
            ),
        )

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

                # Save user message (use client-provided ID for optimistic rendering)
                msg_repo = RoomMessageRepository()
                user_msg = RoomMessage(
                    id=payload.get("messageId") or str(uuid.uuid4()),
                    room_id=room_id,
                    sender_type=RoomSenderType.USER,
                    sender_id=user.id,
                    sender_name=user.username,
                    content=message_text,
                    timestamp=datetime.utcnow(),
                )
                await msg_repo.save_message(user_msg)

                # Broadcast user message to other users (sender already has it
                # via optimistic rendering — sending it back causes duplicates)
                await room_manager.broadcast_to_room(
                    room_id,
                    RoomWSMessage.room_message(
                        room_id=room_id,
                        sender_type="user",
                        sender_id=user.id,
                        sender_name=user.username,
                        content=message_text,
                        message_id=user_msg.id,
                    ),
                    exclude_user_id=user.id,
                )

                # Ask orchestrator which bots should respond
                respondents = orchestrator.select_respondents(message_text, "user")

                # Router mode: LLM picks the best bot (unless explicit @mentions)
                mentioned_ids = orchestrator.parse_mentions(message_text)
                if (
                    orchestrator.response_mode == "router"
                    and not mentioned_ids
                    and len(orchestrator.bot_configs) > 1
                ):
                    try:
                        chosen_id, reason = await route_message(
                            orchestrator, message_text, config
                        )
                        chosen_bot = orchestrator.bot_configs.get(chosen_id)
                        if chosen_bot:
                            await room_manager.send_to_room(
                                room_id,
                                RoomWSMessage.route_decision(
                                    room_id, chosen_id, chosen_bot.name, reason
                                ),
                            )
                            respondents = [chosen_id]
                    except Exception as route_err:
                        logger.error(
                            "Router failed in room %s: %s", room_id, route_err
                        )
                        # Fall through to normal respondent selection

                if orchestrator.response_mode == "chain" and len(respondents) > 1:
                    # Chain mode: sequential with state passing
                    async def _run_chain(
                        bots_to_run: list[str], msg: str, cfg: Config
                    ) -> None:
                        previous_outputs: list[tuple[str, str]] = []
                        total = len(bots_to_run)
                        for step_idx, bid in enumerate(bots_to_run):
                            b = orchestrator.bot_configs.get(bid)
                            if not b:
                                continue
                            try:
                                # Send chain step indicator
                                await room_manager.send_to_room(
                                    room_id,
                                    RoomWSMessage.chain_step(
                                        room_id, step_idx + 1, total, bid, b.name
                                    ),
                                )
                                orchestrator.mark_responding(bid)
                                await room_manager.send_to_room(
                                    room_id,
                                    RoomWSMessage.bot_thinking(room_id, bid, b.name),
                                )
                                response_text = await run_room_bot(
                                    room_id=room_id,
                                    bot_id=bid,
                                    message=msg,
                                    config=cfg,
                                    chain_context=previous_outputs,
                                )
                                if response_text:
                                    previous_outputs.append((b.name, response_text))
                            except Exception as chain_err:
                                logger.error(
                                    "Chain bot %s failed in room %s: %s",
                                    bid, room_id, chain_err,
                                )
                                await room_manager.send_to_room(
                                    room_id,
                                    RoomWSMessage.error(
                                        room_id,
                                        f"{b.name} failed: {chain_err}",
                                        bot_id=bid,
                                    ),
                                )
                                orchestrator.mark_done(bid)

                    chain_task = asyncio.create_task(
                        _run_chain(respondents, message_text, config)
                    )
                    if room_id not in room_manager.bot_tasks:
                        room_manager.bot_tasks[room_id] = {}
                    room_manager.bot_tasks[room_id]["_chain"] = chain_task

                elif orchestrator.response_mode == "sequential" and len(respondents) > 1:
                    # Sequential: run bots one-by-one in a wrapper task
                    async def _run_sequential(
                        bots_to_run: list[str], msg: str, cfg: Config
                    ) -> None:
                        for bid in bots_to_run:
                            b = orchestrator.bot_configs.get(bid)
                            if not b:
                                continue
                            try:
                                orchestrator.mark_responding(bid)
                                await room_manager.send_to_room(
                                    room_id,
                                    RoomWSMessage.bot_thinking(room_id, bid, b.name),
                                )
                                await run_room_bot(
                                    room_id=room_id,
                                    bot_id=bid,
                                    message=msg,
                                    config=cfg,
                                )
                            except Exception as seq_err:
                                logger.error(
                                    "Sequential bot %s failed in room %s: %s",
                                    bid, room_id, seq_err,
                                )
                                await room_manager.send_to_room(
                                    room_id,
                                    RoomWSMessage.error(
                                        room_id,
                                        f"{b.name} failed: {seq_err}",
                                        bot_id=bid,
                                    ),
                                )
                                orchestrator.mark_done(bid)

                    seq_task = asyncio.create_task(
                        _run_sequential(respondents, message_text, config)
                    )
                    if room_id not in room_manager.bot_tasks:
                        room_manager.bot_tasks[room_id] = {}
                    room_manager.bot_tasks[room_id]["_sequential"] = seq_task
                else:
                    # Parallel (default): spawn all bot tasks concurrently
                    for bot_id in respondents:
                        bot = orchestrator.bot_configs.get(bot_id)
                        if not bot:
                            continue

                        try:
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
                        except Exception as spawn_err:
                            logger.error(
                                "Failed to spawn bot %s in room %s: %s",
                                bot_id, room_id, spawn_err,
                            )
                            await room_manager.send_to_room(
                                room_id,
                                RoomWSMessage.error(
                                    room_id,
                                    f"{bot.name} failed to start: {spawn_err}",
                                    bot_id=bot_id,
                                ),
                            )
                            orchestrator.mark_done(bot_id)

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
                    cancel_task = room_manager.bot_tasks[room_id].get(target_bot_id)
                    if cancel_task and not cancel_task.done():
                        cancel_task.cancel()

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


MAX_CHAIN_DEPTH = 3
"""Maximum bot-to-bot mention chain depth to prevent infinite loops."""

BOT_TIMEOUT_SECONDS = 120
"""Maximum seconds a single bot execution may run before being timed out."""


async def run_room_bot(
    room_id: str,
    bot_id: str,
    message: str,
    config: Config,
    chain_depth: int = 0,
    chain_context: list[tuple[str, str]] | None = None,
) -> str:
    """Run a bot's response in a room.

    Streams the response and broadcasts to all room members.
    When the bot's response contains @mentions, chains to those bots.

    Args:
        chain_depth: Current depth in a bot-to-bot mention chain (0 = user-triggered).
        chain_context: List of (bot_name, response_text) from earlier chain steps.
    """
    orchestrator = get_room_orchestrator(room_id)
    if orchestrator is None:
        return ""

    bot = orchestrator.bot_configs.get(bot_id)
    if bot is None:
        return ""

    msg_repo = RoomMessageRepository()

    try:
        # Get recent messages for context
        recent = await msg_repo.get_messages(room_id, limit=50)
        if chain_context is not None:
            room_context = orchestrator.build_chain_context(bot_id, recent, chain_context)
        else:
            room_context = orchestrator.build_room_context(bot_id, recent)

        # Build enhanced system prompt
        enhanced_prompt = (bot.system_prompt or "") + room_context

        # Create agent with bot config
        agent_config = copy.deepcopy(config)
        # Use bot's model if available
        effective_model = bot.model
        if effective_model:
            agent_config.agent.model = effective_model

        # Build instruction delta sender for streaming instruction
        # LLM output to all room members in real time.
        async def _instruction_delta_sender(tool_call_id: str, text: str) -> None:
            await room_manager.send_to_room(
                room_id,
                RoomWSMessage.bot_instruction_delta(
                    room_id=room_id,
                    bot_id=bot_id,
                    bot_name=bot.name,
                    tool_id=tool_call_id,
                    text=text,
                ),
            )

        disabled_caps = await load_disabled_capabilities()
        agent = CachibotAgent(
            config=agent_config,
            system_prompt_override=enhanced_prompt,
            bot_id=bot_id,
            disabled_capabilities=disabled_caps,
            on_instruction_delta=_instruction_delta_sender,
        )

        # Load custom instructions from DB
        from cachibot.agent import load_dynamic_instructions

        await load_dynamic_instructions(agent)

        # Stream response (with timeout)
        response_parts: list[str] = []
        tool_calls: list[dict] = []
        response_msg_id = str(uuid.uuid4())
        agent_result = None  # Captured from the final output event

        async with asyncio.timeout(BOT_TIMEOUT_SECONDS):
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
                        tool_calls.append({
                            "id": event.data.get("id", ""),
                            "tool": event.data["name"],
                            "args": event.data.get("arguments", {}),
                            "startTime": int(datetime.utcnow().timestamp() * 1000),
                        })
                        await room_manager.send_to_room(
                            room_id,
                            RoomWSMessage.bot_tool_start(
                                room_id=room_id,
                                bot_id=bot_id,
                                bot_name=bot.name,
                                tool_id=event.data.get("id", ""),
                                tool_name=event.data["name"],
                                args=event.data.get("arguments", {}),
                                message_id=response_msg_id,
                            ),
                        )
                    case StreamEventType.tool_result:
                        # Update the matching tool call entry
                        tool_id = event.data.get("id", "")
                        for tc in tool_calls:
                            if tc["id"] == tool_id:
                                tc["result"] = str(event.data.get("result", ""))
                                tc["success"] = event.data.get("success", True)
                                tc["endTime"] = int(datetime.utcnow().timestamp() * 1000)
                                break
                        await room_manager.send_to_room(
                            room_id,
                            RoomWSMessage.bot_tool_end(
                                room_id=room_id,
                                bot_id=bot_id,
                                bot_name=bot.name,
                                tool_id=tool_id,
                                result=str(event.data.get("result", "")),
                                message_id=response_msg_id,
                            ),
                        )
                    case StreamEventType.output:
                        agent_result = event.data  # AgentResult

        # Save bot response (include tool calls in metadata)
        full_response = "".join(response_parts)
        if full_response:
            metadata: dict = {}
            if tool_calls:
                metadata["toolCalls"] = tool_calls
            bot_msg = RoomMessage(
                id=response_msg_id,
                room_id=room_id,
                sender_type=RoomSenderType.BOT,
                sender_id=bot_id,
                sender_name=bot.name,
                content=full_response,
                metadata=metadata,
                timestamp=datetime.utcnow(),
            )
            await msg_repo.save_message(bot_msg)

        # Send usage stats from AgentResult
        if agent_result:
            run_usage = agent_result.run_usage
            await room_manager.send_to_room(
                room_id,
                RoomWSMessage.usage(
                    room_id=room_id,
                    bot_id=bot_id,
                    message_id=response_msg_id,
                    model=effective_model or "",
                    tokens=run_usage.get("total_tokens", 0),
                    cost=run_usage.get("cost", 0.0),
                    prompt_tokens=run_usage.get("prompt_tokens", 0),
                    completion_tokens=run_usage.get("completion_tokens", 0),
                    elapsed_ms=run_usage.get("total_elapsed_ms", 0.0),
                    tokens_per_second=run_usage.get("tokens_per_second", 0.0),
                ),
            )

        # Broadcast done
        await room_manager.send_to_room(
            room_id,
            RoomWSMessage.bot_done(room_id, bot_id, bot.name),
        )

        # Bot-to-bot mention chaining: parse the bot's response for @mentions
        if full_response and chain_depth < MAX_CHAIN_DEPTH:
            chained = orchestrator.select_respondents(full_response, "bot", exclude_bot_id=bot_id)
            for next_bot_id in chained:
                next_bot = orchestrator.bot_configs.get(next_bot_id)
                if not next_bot:
                    continue

                orchestrator.mark_responding(next_bot_id)

                await room_manager.send_to_room(
                    room_id,
                    RoomWSMessage.bot_thinking(room_id, next_bot_id, next_bot.name),
                )

                task = asyncio.create_task(
                    run_room_bot(
                        room_id=room_id,
                        bot_id=next_bot_id,
                        message=full_response,
                        config=config,
                        chain_depth=chain_depth + 1,
                    )
                )
                if room_id not in room_manager.bot_tasks:
                    room_manager.bot_tasks[room_id] = {}
                room_manager.bot_tasks[room_id][next_bot_id] = task

        return full_response

    except asyncio.CancelledError:
        await room_manager.send_to_room(
            room_id,
            RoomWSMessage.error(room_id, f"{bot.name} was cancelled", bot_id=bot_id),
        )
        return ""
    except TimeoutError:
        logger.warning("Bot %s timed out in room %s after %ds", bot_id, room_id, BOT_TIMEOUT_SECONDS)
        await room_manager.send_to_room(
            room_id,
            RoomWSMessage.error(
                room_id,
                f"{bot.name} timed out after {BOT_TIMEOUT_SECONDS}s",
                bot_id=bot_id,
            ),
        )
        return ""
    except Exception as e:
        logger.error(f"Bot {bot_id} error in room {room_id}: {e}", exc_info=True)
        await room_manager.send_to_room(
            room_id,
            RoomWSMessage.error(room_id, f"{bot.name} encountered an error: {e}", bot_id=bot_id),
        )
        return ""
    finally:
        if orchestrator:
            orchestrator.mark_done(bot_id)
