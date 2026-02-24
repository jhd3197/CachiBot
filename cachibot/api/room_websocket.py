"""Room WebSocket Handler.

Handles real-time multi-user, multi-bot room communication.
"""

import asyncio
import copy
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from prompture import StreamEventType
from prompture.exceptions import BudgetExceededError

from cachibot.agent import CachibotAgent, load_disabled_capabilities
from cachibot.api.auth import get_user_from_token
from cachibot.config import Config
from cachibot.models.auth import User
from cachibot.models.room import RoomMessage, RoomSenderType
from cachibot.models.room_websocket import RoomWSMessage, RoomWSMessageType
from cachibot.services.room_orchestrator import (
    DebateTranscriptEntry,
    create_room_orchestrator,
    get_room_orchestrator,
    keyword_route,
    remove_room_orchestrator,
    round_robin_route,
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
            routing_strategy=room.settings.routing_strategy,
            bot_keywords=room.settings.bot_keywords,
            room_system_prompt=room.settings.system_prompt,
            room_variables=room.settings.variables,
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
                    timestamp=datetime.now(timezone.utc),
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

                # Router mode: pick the best bot (unless explicit @mentions)
                mentioned_ids = orchestrator.parse_mentions(message_text)
                if (
                    orchestrator.response_mode == "router"
                    and not mentioned_ids
                    and len(orchestrator.bot_configs) > 1
                ):
                    try:
                        strategy = orchestrator.routing_strategy
                        if strategy == "keyword":
                            chosen_id, reason, confidence = keyword_route(
                                orchestrator, message_text
                            )
                        elif strategy == "round_robin":
                            chosen_id, reason, confidence = round_robin_route(orchestrator)
                        else:  # "llm"
                            chosen_id, reason = await route_message(
                                orchestrator, message_text, config
                            )
                            confidence = 0.8
                        chosen_bot = orchestrator.bot_configs.get(chosen_id)
                        if chosen_bot:
                            await room_manager.send_to_room(
                                room_id,
                                RoomWSMessage.route_decision(
                                    room_id,
                                    chosen_id,
                                    chosen_bot.name,
                                    reason,
                                    confidence=confidence,
                                    strategy=strategy,
                                ),
                            )
                            respondents = [chosen_id]
                    except Exception as route_err:
                        logger.error("Router failed in room %s: %s", room_id, route_err)
                        # Fall through to normal respondent selection

                if orchestrator.response_mode == "chain" and len(respondents) > 1:
                    # Chain mode: sequential with state passing
                    async def _run_chain(bots_to_run: list[str], msg: str, cfg: Config) -> None:
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
                                    bid,
                                    room_id,
                                    chain_err,
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

                    chain_task = asyncio.create_task(_run_chain(respondents, message_text, config))
                    if room_id not in room_manager.bot_tasks:
                        room_manager.bot_tasks[room_id] = {}
                    room_manager.bot_tasks[room_id]["_chain"] = chain_task

                elif orchestrator.response_mode == "debate" and len(respondents) >= 2:
                    # Debate mode: multiple rounds of position-aware arguments + optional judge
                    async def _run_debate(bots_to_run: list[str], msg: str, cfg: Config) -> None:
                        settings = room.settings
                        orchestrator.reset_debate_state()

                        for round_num in range(settings.debate_rounds):
                            await room_manager.send_to_room(
                                room_id,
                                RoomWSMessage.debate_round_start(
                                    room_id, round_num + 1, settings.debate_rounds
                                ),
                            )

                            for bid in bots_to_run:
                                bot = orchestrator.bot_configs.get(bid)
                                if not bot:
                                    continue
                                try:
                                    orchestrator.mark_responding(bid)
                                    await room_manager.send_to_room(
                                        room_id,
                                        RoomWSMessage.bot_thinking(room_id, bid, bot.name),
                                    )
                                    recent = await msg_repo.get_messages(room_id, limit=50)
                                    debate_prompt = orchestrator.build_debate_context(
                                        bid,
                                        msg,
                                        settings.debate_positions,
                                        round_num,
                                        recent,
                                    )
                                    response_text = await run_room_bot(
                                        room_id=room_id,
                                        bot_id=bid,
                                        message=msg,
                                        config=cfg,
                                        system_prompt_override=debate_prompt,
                                    )
                                    if response_text:
                                        orchestrator.debate_transcript.append(
                                            DebateTranscriptEntry(
                                                round=round_num,
                                                bot_id=bid,
                                                bot_name=bot.name,
                                                position=settings.debate_positions.get(bid),
                                                content=response_text,
                                            )
                                        )
                                except Exception as debate_err:
                                    logger.error(
                                        "Debate bot %s failed in room %s: %s",
                                        bid,
                                        room_id,
                                        debate_err,
                                    )
                                    await room_manager.send_to_room(
                                        room_id,
                                        RoomWSMessage.error(
                                            room_id,
                                            f"{bot.name} failed: {debate_err}",
                                            bot_id=bid,
                                        ),
                                    )
                                    orchestrator.mark_done(bid)

                            await room_manager.send_to_room(
                                room_id,
                                RoomWSMessage.debate_round_end(room_id, round_num + 1),
                            )

                        # Judge phase (optional)
                        judge_id = settings.debate_judge_bot_id
                        if judge_id and orchestrator.debate_transcript:
                            judge_bot = orchestrator.bot_configs.get(judge_id)
                            if judge_bot:
                                await room_manager.send_to_room(
                                    room_id,
                                    RoomWSMessage.debate_judge_start(
                                        room_id, judge_id, judge_bot.name
                                    ),
                                )
                                try:
                                    orchestrator.mark_responding(judge_id)
                                    await room_manager.send_to_room(
                                        room_id,
                                        RoomWSMessage.bot_thinking(
                                            room_id, judge_id, judge_bot.name
                                        ),
                                    )
                                    recent = await msg_repo.get_messages(room_id, limit=50)
                                    judge_prompt = orchestrator.build_judge_context(
                                        judge_id, msg, settings.debate_judge_prompt, recent
                                    )
                                    await run_room_bot(
                                        room_id=room_id,
                                        bot_id=judge_id,
                                        message=msg,
                                        config=cfg,
                                        system_prompt_override=judge_prompt,
                                    )
                                except Exception as judge_err:
                                    logger.error(
                                        "Debate judge %s failed in room %s: %s",
                                        judge_id,
                                        room_id,
                                        judge_err,
                                    )
                                    await room_manager.send_to_room(
                                        room_id,
                                        RoomWSMessage.error(
                                            room_id,
                                            f"{judge_bot.name} (judge) failed: {judge_err}",
                                            bot_id=judge_id,
                                        ),
                                    )
                                    orchestrator.mark_done(judge_id)

                        await room_manager.send_to_room(
                            room_id,
                            RoomWSMessage.debate_complete(
                                room_id,
                                settings.debate_rounds,
                                has_verdict=judge_id is not None,
                            ),
                        )

                    debate_task = asyncio.create_task(
                        _run_debate(respondents, message_text, config)
                    )
                    room_manager.bot_tasks.setdefault(room_id, {})["_debate"] = debate_task

                elif orchestrator.response_mode == "waterfall" and len(respondents) > 1:
                    # Waterfall mode: sequential with conditional early stopping
                    async def _run_waterfall(bots_to_run: list[str], msg: str, cfg: Config) -> None:
                        previous_outputs: list[tuple[str, str]] = []
                        total = len(bots_to_run)
                        waterfall_conditions = room.settings.waterfall_conditions

                        for step_idx, bid in enumerate(bots_to_run):
                            bot = orchestrator.bot_configs.get(bid)
                            if not bot:
                                continue

                            await room_manager.send_to_room(
                                room_id,
                                RoomWSMessage.waterfall_step(
                                    room_id, step_idx + 1, total, bid, bot.name
                                ),
                            )
                            try:
                                orchestrator.mark_responding(bid)
                                await room_manager.send_to_room(
                                    room_id,
                                    RoomWSMessage.bot_thinking(room_id, bid, bot.name),
                                )
                                response_text = await run_room_bot(
                                    room_id=room_id,
                                    bot_id=bid,
                                    message=msg,
                                    config=cfg,
                                    chain_context=previous_outputs,
                                )
                            except Exception as wf_err:
                                logger.error(
                                    "Waterfall bot %s failed in room %s: %s",
                                    bid,
                                    room_id,
                                    wf_err,
                                )
                                await room_manager.send_to_room(
                                    room_id,
                                    RoomWSMessage.error(
                                        room_id,
                                        f"{bot.name} failed: {wf_err}",
                                        bot_id=bid,
                                    ),
                                )
                                orchestrator.mark_done(bid)
                                continue

                            if response_text:
                                previous_outputs.append((bot.name, response_text))
                                condition_type = waterfall_conditions.get(bid, "always_continue")
                                should_continue = _evaluate_waterfall_condition(
                                    condition_type, response_text
                                )

                                if not should_continue:
                                    for skip_idx in range(step_idx + 1, len(bots_to_run)):
                                        skip_bid = bots_to_run[skip_idx]
                                        skip_bot = orchestrator.bot_configs.get(skip_bid)
                                        if skip_bot:
                                            await room_manager.send_to_room(
                                                room_id,
                                                RoomWSMessage.waterfall_skipped(
                                                    room_id,
                                                    skip_bid,
                                                    skip_bot.name,
                                                    f"Resolved by {bot.name}",
                                                ),
                                            )
                                    await room_manager.send_to_room(
                                        room_id,
                                        RoomWSMessage.waterfall_stopped(room_id, bot.name),
                                    )
                                    break

                    wf_task = asyncio.create_task(_run_waterfall(respondents, message_text, config))
                    room_manager.bot_tasks.setdefault(room_id, {})["_waterfall"] = wf_task

                elif orchestrator.response_mode == "relay" and not mentioned_ids:
                    # Relay mode: round-robin, single bot per message
                    chosen_id, reason, _confidence = round_robin_route(orchestrator)
                    chosen_bot = orchestrator.bot_configs.get(chosen_id)
                    if chosen_bot:
                        await room_manager.send_to_room(
                            room_id,
                            RoomWSMessage.route_decision(
                                room_id,
                                chosen_id,
                                chosen_bot.name,
                                reason,
                                confidence=1.0,
                                strategy="relay",
                            ),
                        )
                        orchestrator.mark_responding(chosen_id)
                        await room_manager.send_to_room(
                            room_id,
                            RoomWSMessage.bot_thinking(room_id, chosen_id, chosen_bot.name),
                        )
                        task = asyncio.create_task(
                            run_room_bot(
                                room_id=room_id,
                                bot_id=chosen_id,
                                message=message_text,
                                config=config,
                            )
                        )
                        room_manager.bot_tasks.setdefault(room_id, {})[chosen_id] = task

                elif orchestrator.response_mode == "consensus" and len(respondents) >= 2:
                    # Consensus mode: all bots respond hidden, then synthesizer merges
                    async def _run_consensus(bots_to_run: list[str], msg: str, cfg: Config) -> None:
                        settings = room.settings
                        orchestrator.reset_consensus_state()

                        # Phase 1: Collect hidden responses in parallel
                        async def _collect_response(bid: str) -> tuple[str, str, str]:
                            b = orchestrator.bot_configs.get(bid)
                            if not b:
                                return bid, "", ""
                            try:
                                orchestrator.mark_responding(bid)
                                await room_manager.send_to_room(
                                    room_id,
                                    RoomWSMessage.bot_thinking(room_id, bid, b.name),
                                )
                                resp = await run_room_bot(
                                    room_id=room_id,
                                    bot_id=bid,
                                    message=msg,
                                    config=cfg,
                                )
                                return bid, b.name, resp or ""
                            except Exception as consensus_err:
                                logger.error(
                                    "Consensus bot %s failed in room %s: %s",
                                    bid,
                                    room_id,
                                    consensus_err,
                                )
                                await room_manager.send_to_room(
                                    room_id,
                                    RoomWSMessage.error(
                                        room_id,
                                        f"{b.name} failed: {consensus_err}",
                                        bot_id=bid,
                                    ),
                                )
                                orchestrator.mark_done(bid)
                                return bid, b.name, ""

                        # Determine which bots are respondents vs synthesizer
                        synth_id = settings.consensus_synthesizer_bot_id
                        if not synth_id or synth_id not in orchestrator.bot_configs:
                            synth_id = bots_to_run[0]

                        contributor_ids = [bid for bid in bots_to_run if bid != synth_id]
                        if not contributor_ids:
                            # If synth is the only bot, fall back to parallel
                            contributor_ids = bots_to_run

                        # Run contributors in parallel
                        results = await asyncio.gather(
                            *[_collect_response(bid) for bid in contributor_ids]
                        )

                        for bid, bname, resp in results:
                            if resp:
                                orchestrator.add_consensus_response(bid, bname, resp)

                        if not orchestrator._consensus_responses:
                            await room_manager.send_to_room(
                                room_id,
                                RoomWSMessage.error(
                                    room_id, "No responses collected for consensus"
                                ),
                            )
                            return

                        # If not showing individual, delete the messages (they were
                        # already broadcast by run_room_bot — in a future iteration
                        # we could suppress the broadcast)
                        # For now, individual responses are always visible as they stream.

                        # Phase 2: Synthesize
                        synth_bot = orchestrator.bot_configs.get(synth_id)
                        if synth_bot:
                            await room_manager.send_to_room(
                                room_id,
                                RoomWSMessage.consensus_synthesizing(
                                    room_id,
                                    synth_id,
                                    synth_bot.name,
                                    len(orchestrator._consensus_responses),
                                ),
                            )
                            try:
                                orchestrator.mark_responding(synth_id)
                                await room_manager.send_to_room(
                                    room_id,
                                    RoomWSMessage.bot_thinking(room_id, synth_id, synth_bot.name),
                                )
                                msg_repo_c = RoomMessageRepository()
                                recent = await msg_repo_c.get_messages(room_id, limit=50)
                                synth_prompt = orchestrator.build_consensus_synthesis_context(
                                    synth_id, msg, recent
                                )
                                await run_room_bot(
                                    room_id=room_id,
                                    bot_id=synth_id,
                                    message=msg,
                                    config=cfg,
                                    system_prompt_override=synth_prompt,
                                )
                            except Exception as synth_err:
                                logger.error(
                                    "Consensus synthesizer %s failed: %s",
                                    synth_id,
                                    synth_err,
                                )
                                await room_manager.send_to_room(
                                    room_id,
                                    RoomWSMessage.error(
                                        room_id,
                                        f"Synthesizer {synth_bot.name} failed: {synth_err}",
                                        bot_id=synth_id,
                                    ),
                                )
                                orchestrator.mark_done(synth_id)

                        await room_manager.send_to_room(
                            room_id,
                            RoomWSMessage.consensus_complete(
                                room_id, len(orchestrator._consensus_responses)
                            ),
                        )

                    consensus_task = asyncio.create_task(
                        _run_consensus(respondents, message_text, config)
                    )
                    room_manager.bot_tasks.setdefault(room_id, {})["_consensus"] = consensus_task

                elif orchestrator.response_mode == "interview":
                    # Interview mode: interviewer asks questions, then hands off
                    settings = room.settings
                    interview_bot_id: str | None = settings.interview_bot_id
                    if not interview_bot_id or interview_bot_id not in orchestrator.bot_configs:
                        # Default to first non-observer bot
                        for bid in orchestrator.bot_configs:
                            if orchestrator.bot_roles.get(bid) != "observer":
                                interview_bot_id = bid
                                break

                    # Check if user manually triggers handoff
                    manual_handoff = False
                    if settings.interview_handoff_trigger == "manual":
                        lower_msg = message_text.lower().strip()
                        if lower_msg in ("done", "handoff", "/handoff", "/done"):
                            manual_handoff = True
                            orchestrator.interview_handoff_triggered = True

                    if orchestrator.interview_handoff_triggered or manual_handoff:
                        # Handoff: run all specialist bots in parallel
                        await room_manager.send_to_room(
                            room_id,
                            RoomWSMessage.interview_handoff(
                                room_id,
                                "Interview complete, handing off to specialists",
                            ),
                        )
                        specialist_ids = [
                            bid
                            for bid in respondents
                            if bid != interview_bot_id
                            and orchestrator.bot_roles.get(bid) != "observer"
                        ]
                        if not specialist_ids:
                            specialist_ids = respondents

                        for bid in specialist_ids:
                            b = orchestrator.bot_configs.get(bid)
                            if not b:
                                continue
                            orchestrator.mark_responding(bid)
                            await room_manager.send_to_room(
                                room_id,
                                RoomWSMessage.bot_thinking(room_id, bid, b.name),
                            )
                            task = asyncio.create_task(
                                run_room_bot(
                                    room_id=room_id,
                                    bot_id=bid,
                                    message=message_text,
                                    config=config,
                                )
                            )
                            room_manager.bot_tasks.setdefault(room_id, {})[bid] = task
                    else:
                        # Interview phase: only interviewer responds
                        async def _run_interview_step(
                            interviewer_id: str, msg: str, cfg: Config
                        ) -> None:
                            b = orchestrator.bot_configs.get(interviewer_id)
                            if not b:
                                return
                            try:
                                orchestrator.mark_responding(interviewer_id)
                                await room_manager.send_to_room(
                                    room_id,
                                    RoomWSMessage.bot_thinking(room_id, interviewer_id, b.name),
                                )
                                msg_repo_i = RoomMessageRepository()
                                recent = await msg_repo_i.get_messages(room_id, limit=50)
                                interview_prompt = orchestrator.build_interview_context(
                                    interviewer_id,
                                    recent,
                                    settings.interview_max_questions,
                                )
                                response_text = await run_room_bot(
                                    room_id=room_id,
                                    bot_id=interviewer_id,
                                    message=msg,
                                    config=cfg,
                                    system_prompt_override=interview_prompt,
                                )

                                # Send question progress
                                await room_manager.send_to_room(
                                    room_id,
                                    RoomWSMessage.interview_question(
                                        room_id,
                                        orchestrator.interview_question_count,
                                        settings.interview_max_questions,
                                    ),
                                )

                                # Check for handoff
                                if response_text and orchestrator.check_interview_handoff(
                                    response_text,
                                    settings.interview_handoff_trigger,
                                    settings.interview_max_questions,
                                ):
                                    await room_manager.send_to_room(
                                        room_id,
                                        RoomWSMessage.interview_handoff(
                                            room_id,
                                            "Interviewer triggered handoff",
                                        ),
                                    )
                            except Exception as interview_err:
                                logger.error(
                                    "Interview bot %s failed: %s",
                                    interviewer_id,
                                    interview_err,
                                )
                                await room_manager.send_to_room(
                                    room_id,
                                    RoomWSMessage.error(
                                        room_id,
                                        f"{b.name} failed: {interview_err}",
                                        bot_id=interviewer_id,
                                    ),
                                )
                                orchestrator.mark_done(interviewer_id)

                        if interview_bot_id is None:
                            logger.warning("No interview bot available for room %s", room_id)
                            continue
                        interview_task = asyncio.create_task(
                            _run_interview_step(interview_bot_id, message_text, config)
                        )
                        room_manager.bot_tasks.setdefault(room_id, {})["_interview"] = (
                            interview_task
                        )

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
                                    bid,
                                    room_id,
                                    seq_err,
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
                                bot_id,
                                room_id,
                                spawn_err,
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


def _evaluate_waterfall_condition(condition_type: str, output_text: str) -> bool:
    """Returns True to continue to next bot, False to stop (current bot resolved it)."""
    text_lower = output_text.lower()
    if condition_type == "resolved":
        # Continue only if escalation markers found (bot couldn't resolve)
        escalation = ["escalate", "i can't", "i cannot", "need help", "not sure", "unable to"]
        return any(m in text_lower for m in escalation)
    elif condition_type == "confidence_high":
        uncertainty = ["uncertain", "maybe", "not confident", "low confidence", "i'm not sure"]
        return any(m in text_lower for m in uncertainty)
    elif condition_type == "short_response":
        return len(output_text) < 500
    else:  # "always_continue"
        return True


async def run_room_bot(
    room_id: str,
    bot_id: str,
    message: str,
    config: Config,
    chain_depth: int = 0,
    chain_context: list[tuple[str, str]] | None = None,
    system_prompt_override: str | None = None,
) -> str:
    """Run a bot's response in a room.

    Streams the response and broadcasts to all room members.
    When the bot's response contains @mentions, chains to those bots.

    Args:
        chain_depth: Current depth in a bot-to-bot mention chain (0 = user-triggered).
        chain_context: List of (bot_name, response_text) from earlier chain steps.
        system_prompt_override: Full system prompt to use instead of building from context.
    """
    logger.debug("run_room_bot entered: bot_id=%s room_id=%s", bot_id, room_id)
    orchestrator = get_room_orchestrator(room_id)
    if orchestrator is None:
        return ""

    bot = orchestrator.bot_configs.get(bot_id)
    if bot is None:
        return ""

    msg_repo = RoomMessageRepository()

    try:
        # Build enhanced system prompt
        if system_prompt_override is not None:
            enhanced_prompt = (bot.system_prompt or "") + system_prompt_override
        else:
            recent = await msg_repo.get_messages(room_id, limit=50)
            if chain_context is not None:
                room_context = orchestrator.build_chain_context(bot_id, recent, chain_context)
            else:
                room_context = orchestrator.build_room_context(bot_id, recent)
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

        # Resolve per-bot environment for budget enforcement and API keys
        from cachibot.services.agent_factory import resolve_bot_env

        resolved_env, per_bot_driver = await resolve_bot_env(
            bot_id,
            platform="web",
            effective_model=effective_model or agent_config.agent.model,
        )

        # Sync callback for budget-triggered model fallback
        def _model_fallback_sync(old_model: str, new_model: str, _state: Any) -> None:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(
                    room_manager.send_to_room(
                        room_id,
                        RoomWSMessage.error(
                            room_id,
                            f"{bot.name} switched from {old_model} to {new_model} "
                            "(budget threshold reached)",
                            bot_id=bot_id,
                        ),
                    )
                )
            except RuntimeError:
                pass

        # Build tool_configs from resolved environment (mirrors normal chat flow)
        merged_tool_configs: dict[str, Any] = {}
        if resolved_env and resolved_env.skill_configs:
            for skill_name, skill_cfg in resolved_env.skill_configs.items():
                merged_tool_configs.setdefault(skill_name, {}).update(skill_cfg)

        disabled_caps = await load_disabled_capabilities()
        # Empty capabilities dict ({}) means "no capabilities configured" — treat
        # as None so the plugin manager enables all tools (legacy mode).  A non-empty
        # dict means the bot has explicit capability settings from the UI.
        effective_caps = bot.capabilities if bot.capabilities else None
        agent = CachibotAgent(
            config=agent_config,
            system_prompt_override=enhanced_prompt,
            capabilities=effective_caps,
            bot_id=bot_id,
            bot_models=bot.models,
            tool_configs=merged_tool_configs or None,
            driver=per_bot_driver,
            provider_environment=resolved_env,
            disabled_capabilities=disabled_caps,
            on_instruction_delta=_instruction_delta_sender,
            on_model_fallback=_model_fallback_sync,
        )

        # Load custom instructions from DB
        from cachibot.agent import load_dynamic_instructions

        await load_dynamic_instructions(agent)

        # Stream response (with timeout)
        response_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        response_msg_id = str(uuid.uuid4())
        agent_result = None  # Captured from the final output event
        has_tool_calls = False

        # Send an initial empty room_message so the frontend creates the message
        # entry and tracks the bot's message ID BEFORE any tool events arrive.
        # Without this, tool_start events that arrive before any text_delta have
        # no message to attach to.
        await room_manager.send_to_room(
            room_id,
            RoomWSMessage.room_message(
                room_id=room_id,
                sender_type="bot",
                sender_id=bot_id,
                sender_name=bot.name,
                content="",
                message_id=response_msg_id,
            ),
        )

        async with asyncio.timeout(BOT_TIMEOUT_SECONDS):  # type: ignore[attr-defined]
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
                        # After tool calls, text deltas are "thinking" content
                        if has_tool_calls:
                            await room_manager.send_to_room(
                                room_id,
                                RoomWSMessage.bot_thinking(
                                    room_id, bot_id, bot.name, content=event.data
                                ),
                            )
                    case StreamEventType.tool_call:
                        has_tool_calls = True
                        tool_calls.append(
                            {
                                "id": event.data.get("id", ""),
                                "tool": event.data["name"],
                                "args": event.data.get("arguments", {}),
                                "startTime": int(datetime.now(timezone.utc).timestamp() * 1000),
                            }
                        )
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
                                tc["endTime"] = int(datetime.now(timezone.utc).timestamp() * 1000)
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
        if full_response or tool_calls:
            metadata: dict[str, Any] = {}
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
                timestamp=datetime.now(timezone.utc),
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

        # Broadcast done — construct payload directly (bypass classmethod
        # to rule out stale model import)
        done_payload: dict[str, Any] = {
            "roomId": room_id,
            "botId": bot_id,
            "botName": bot.name,
            "messageId": response_msg_id,
        }
        if tool_calls:
            done_payload["toolCalls"] = tool_calls
        done_msg = RoomWSMessage(
            type=RoomWSMessageType.ROOM_BOT_DONE,
            payload=done_payload,
        )
        logger.debug(
            "bot_done: bot_id=%s room_id=%s messageId=%s", bot_id, room_id, response_msg_id
        )
        await room_manager.send_to_room(room_id, done_msg)

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
        logger.debug("Bot %s cancelled in room %s", bot_id, room_id)
        await room_manager.send_to_room(
            room_id,
            RoomWSMessage.error(room_id, f"{bot.name} was cancelled", bot_id=bot_id),
        )
        return ""
    except BudgetExceededError as e:
        logger.warning("Budget exceeded for bot %s in room %s: %s", bot_id, room_id, e)
        await room_manager.send_to_room(
            room_id,
            RoomWSMessage.error(
                room_id,
                f"{bot.name} budget limit reached: {e}",
                bot_id=bot_id,
            ),
        )
        return ""
    except TimeoutError:
        logger.warning(
            "Bot %s timed out in room %s after %ds", bot_id, room_id, BOT_TIMEOUT_SECONDS
        )
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
        logger.exception("Bot %s error in room %s", bot_id, room_id)
        await room_manager.send_to_room(
            room_id,
            RoomWSMessage.error(room_id, f"{bot.name} encountered an error: {e}", bot_id=bot_id),
        )
        return ""
    finally:
        if orchestrator:
            orchestrator.mark_done(bot_id)
