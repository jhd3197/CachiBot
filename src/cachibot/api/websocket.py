"""
WebSocket Handler for Cachibot

Handles real-time streaming of agent events to clients.
"""

import asyncio
import copy
import logging
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from prompture import StreamEventType

from cachibot.agent import CachibotAgent
from cachibot.api.auth import get_user_from_token
from cachibot.config import Config
from cachibot.models.auth import User
from cachibot.models.knowledge import BotMessage
from cachibot.models.websocket import WSMessage, WSMessageType
from cachibot.services.context_builder import get_context_builder
from cachibot.storage.repository import KnowledgeRepository, SkillsRepository

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.pending_approvals: dict[str, asyncio.Event] = {}
        self.approval_results: dict[str, bool] = {}

    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str) -> None:
        """Remove a WebSocket connection."""
        self.active_connections.pop(client_id, None)
        # Clean up any pending approvals
        self.pending_approvals.pop(client_id, None)

    async def send(self, client_id: str, message: WSMessage) -> None:
        """Send a message to a specific client."""
        if websocket := self.active_connections.get(client_id):
            await websocket.send_json(message.model_dump())

    async def broadcast(self, message: WSMessage) -> None:
        """Send a message to all connected clients."""
        for websocket in self.active_connections.values():
            await websocket.send_json(message.model_dump())


manager = ConnectionManager()


def get_ws_manager() -> ConnectionManager:
    """Get the WebSocket connection manager singleton."""
    return manager


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str | None = Query(default=None),
):
    """
    WebSocket endpoint for real-time agent communication.

    Protocol:
    - Client connects with token query parameter: /ws?token=xxx
    - Client sends: { type: "chat", payload: { message: "..." } }
    - Server sends: thinking, tool_start, tool_end, message, done events

    Authentication:
    - Requires valid JWT token as query parameter
    - Connection closes with code 4001 if token is invalid or missing
    """
    # Authenticate user via token
    user: User | None = None
    if token:
        user = await get_user_from_token(token)

    if user is None:
        await websocket.close(code=4001, reason="Authentication required")
        return

    client_id = str(uuid.uuid4())
    await manager.connect(websocket, client_id)

    # Get workspace from app state
    workspace = websocket.app.state.workspace

    config = Config.load(workspace=workspace)

    async def on_approval(tool_name: str, action: str, details: dict) -> bool:
        """Handle approval request - sends to client and waits for response."""
        approval_id = str(uuid.uuid4())
        event = asyncio.Event()
        manager.pending_approvals[approval_id] = event
        manager.approval_results[approval_id] = False
        await manager.send(
            client_id,
            WSMessage.approval_needed(approval_id, tool_name, action, details),
        )
        try:
            await asyncio.wait_for(event.wait(), timeout=300)
            return manager.approval_results.pop(approval_id, False)
        except asyncio.TimeoutError:
            return not config.agent.approve_actions
        finally:
            manager.pending_approvals.pop(approval_id, None)

    agent: CachibotAgent | None = None
    current_task: asyncio.Task | None = None

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            payload = data.get("payload", {})

            if msg_type == WSMessageType.CHAT:
                # Handle chat message
                message = payload.get("message", "")
                system_prompt = payload.get("systemPrompt")
                bot_id = payload.get("botId")
                chat_id = payload.get("chatId")
                bot_model = payload.get("model")  # Per-bot model override
                bot_models = payload.get("models")  # Multi-model slots dict
                capabilities = payload.get("capabilities")  # Optional dict
                tool_configs = payload.get("toolConfigs")  # Optional dict with per-tool settings
                enabled_skill_ids = payload.get("enabledSkills")  # Optional list of skill IDs
                if not message:
                    await manager.send(client_id, WSMessage.error("Empty message"))
                    continue

                # Cancel any existing task
                if current_task and not current_task.done():
                    current_task.cancel()

                # Fetch enabled skill definitions for this bot
                enabled_skills = []
                if bot_id:
                    try:
                        skills_repo = SkillsRepository()
                        if enabled_skill_ids is not None:
                            # Use provided skill IDs
                            for sid in enabled_skill_ids:
                                skill = await skills_repo.get_skill(sid)
                                if skill:
                                    enabled_skills.append(skill)
                        else:
                            # Auto-fetch from bot's activated skills
                            enabled_skills = await skills_repo.get_bot_skill_definitions(bot_id)
                    except Exception as e:
                        logger.warning(f"Failed to fetch skills: {e}")

                # Enhance system prompt with knowledge context if bot_id provided
                enhanced_prompt = system_prompt
                if bot_id:
                    try:
                        context_builder = get_context_builder()
                        # Check if contacts capability is enabled
                        include_contacts = (
                            capabilities.get("contacts", False) if capabilities else False
                        )
                        # Pass skill IDs for context building
                        skill_ids = [s.id for s in enabled_skills] if enabled_skills else None
                        enhanced_prompt = await context_builder.build_enhanced_system_prompt(
                            base_prompt=system_prompt,
                            bot_id=bot_id,
                            user_message=message,
                            chat_id=chat_id,
                            include_contacts=include_contacts,
                            enabled_skills=skill_ids,
                        )
                    except Exception as e:
                        # Log but don't fail - use base prompt if context building fails
                        logger.warning(f"Context building failed: {e}")
                        enhanced_prompt = system_prompt

                # Merge tool_configs
                merged_tool_configs = dict(tool_configs) if tool_configs else {}

                # Apply per-bot model override: resolve from models.default or model field
                effective_model = None
                if bot_models and bot_models.get("default"):
                    effective_model = bot_models["default"]
                elif bot_model:
                    effective_model = bot_model

                agent_config = config
                if effective_model:
                    # Copy config to avoid mutating the shared instance
                    agent_config = copy.deepcopy(config)
                    agent_config.agent.model = effective_model

                # Create fresh agent with current systemPrompt
                # Capabilities are passed directly; the plugin system
                # handles mapping capabilities to tools.
                agent = CachibotAgent(
                    config=agent_config,
                    system_prompt_override=enhanced_prompt,
                    capabilities=capabilities,
                    bot_id=bot_id,
                    bot_models=bot_models,
                    tool_configs=merged_tool_configs,
                    on_approval_needed=on_approval,
                )

                # Run agent in background task
                current_task = asyncio.create_task(
                    run_agent(agent, message, client_id, bot_id, chat_id)
                )

            elif msg_type == WSMessageType.CANCEL:
                # Cancel current operation
                if current_task and not current_task.done():
                    current_task.cancel()
                    await manager.send(client_id, WSMessage.error("Cancelled by user"))

            elif msg_type == WSMessageType.APPROVAL:
                # Handle approval response
                approval_id = payload.get("id")
                approved = payload.get("approved", False)

                if approval_id in manager.pending_approvals:
                    manager.approval_results[approval_id] = approved
                    manager.pending_approvals[approval_id].set()

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}")
        await manager.send(client_id, WSMessage.error("An internal error occurred"))
    finally:
        # Cancel any running task
        if current_task and not current_task.done():
            current_task.cancel()
        manager.disconnect(client_id)


async def run_agent(
    agent: CachibotAgent,
    message: str,
    client_id: str,
    bot_id: str | None = None,
    chat_id: str | None = None,
) -> None:
    """Run the agent with streaming and send results to WebSocket client."""
    repo = KnowledgeRepository()

    try:
        # Send user message echo
        await manager.send(client_id, WSMessage.message("user", message))

        # Save user message to history
        if bot_id and chat_id:
            user_msg = BotMessage(
                id=str(uuid.uuid4()),
                bot_id=bot_id,
                chat_id=chat_id,
                role="user",
                content=message,
                timestamp=datetime.utcnow(),
            )
            await repo.save_bot_message(user_msg)

        # Stream agent response
        response_msg_id = str(uuid.uuid4())
        has_tool_calls = False
        agent_result = None  # Captured from the final output event

        async for event in agent.run_stream(message):
            match event.event_type:
                case StreamEventType.text_delta:
                    await manager.send(
                        client_id,
                        WSMessage.message(
                            "assistant", event.data, message_id=response_msg_id
                        ),
                    )
                    # Send thinking events for text between tool calls
                    if has_tool_calls:
                        await manager.send(
                            client_id, WSMessage.thinking(event.data)
                        )
                case StreamEventType.tool_call:
                    has_tool_calls = True
                    # New message ID for text after this tool sequence
                    response_msg_id = str(uuid.uuid4())
                    await manager.send(
                        client_id,
                        WSMessage.tool_start(
                            event.data.get("id", ""),
                            event.data["name"],
                            event.data.get("arguments", {}),
                        ),
                    )
                case StreamEventType.tool_result:
                    await manager.send(
                        client_id,
                        WSMessage.tool_end(
                            event.data.get("id", ""),
                            str(event.data.get("result", "")),
                        ),
                    )
                case StreamEventType.output:
                    agent_result = event.data  # AgentResult

        # Extract response text and usage from the AgentResult
        response_text = (agent_result.output_text or "") if agent_result else ""
        run_usage = agent_result.run_usage if agent_result else {}

        # Save full assistant response to history
        if response_text and bot_id and chat_id:
            assistant_msg = BotMessage(
                id=str(uuid.uuid4()),
                bot_id=bot_id,
                chat_id=chat_id,
                role="assistant",
                content=response_text,
                timestamp=datetime.utcnow(),
            )
            await repo.save_bot_message(assistant_msg)

        # Send usage stats from AgentResult.run_usage
        await manager.send(
            client_id,
            WSMessage.usage(
                tokens=run_usage.get("total_tokens", 0),
                cost=run_usage.get("cost", 0.0),
                iterations=len(agent_result.steps) if agent_result else 0,
                prompt_tokens=run_usage.get("prompt_tokens", 0),
                completion_tokens=run_usage.get("completion_tokens", 0),
                elapsed_ms=run_usage.get("total_elapsed_ms", 0.0),
                tokens_per_second=run_usage.get("tokens_per_second", 0.0),
                call_count=run_usage.get("call_count", 0),
                errors=run_usage.get("errors", 0),
                per_model=run_usage.get("per_model", {}),
                latency_stats=run_usage.get("latency_stats", {}),
            ),
        )

        # Send done signal
        await manager.send(client_id, WSMessage.done())

    except asyncio.CancelledError:
        await manager.send(client_id, WSMessage.error("Operation cancelled"))
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}")
        await manager.send(client_id, WSMessage.error("An internal error occurred"))
