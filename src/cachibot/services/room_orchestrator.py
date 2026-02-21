"""Room orchestrator for multi-agent turn logic.

Manages bot response selection, cooldowns, and @mention parsing.
One instance per active room.
"""

import logging
import re
import time
from dataclasses import dataclass, field

from cachibot.config import Config
from cachibot.models.bot import Bot
from cachibot.models.room import RoomMessage

logger = logging.getLogger(__name__)


@dataclass
class BotCooldownState:
    """Tracks cooldown and response state for a bot in a room."""

    last_response_time: float = 0.0
    is_responding: bool = False


@dataclass
class RoomOrchestrator:
    """Manages turn logic for a single room."""

    room_id: str
    bot_configs: dict[str, Bot] = field(default_factory=dict)
    cooldowns: dict[str, BotCooldownState] = field(default_factory=dict)
    cooldown_seconds: float = 5.0
    auto_relevance: bool = True
    response_mode: str = "parallel"  # "parallel", "sequential", "chain", or "router"
    bot_roles: dict[str, str] = field(default_factory=dict)

    def register_bot(self, bot: Bot) -> None:
        """Register a bot in this room."""
        self.bot_configs[bot.id] = bot
        if bot.id not in self.cooldowns:
            self.cooldowns[bot.id] = BotCooldownState()

    def remove_bot(self, bot_id: str) -> None:
        """Remove a bot from this room."""
        self.bot_configs.pop(bot_id, None)
        self.cooldowns.pop(bot_id, None)

    def set_bot_role(self, bot_id: str, role: str) -> None:
        """Set a bot's role in this room."""
        self.bot_roles[bot_id] = role

    def parse_mentions(self, message: str) -> list[str]:
        """Extract @BotName mentions and match to registered bot IDs.

        Case-insensitive matching against bot names.
        Supports @all to target every bot in the room.
        """
        msg_lower = message.lower()

        # Check for @all — return all bots in the room
        if re.search(r"@all\b", msg_lower):
            logger.debug(
                "Room %s: @all detected, returning all %d bots",
                self.room_id,
                len(self.bot_configs),
            )
            return list(self.bot_configs.keys())

        # Match against known bot names directly (handles multi-word names
        # and avoids the greedy-regex problem where "@Bot rest of sentence"
        # captured the whole tail instead of just the name).
        matched_bot_ids = []
        for bot_id, bot in self.bot_configs.items():
            pattern = re.compile(r"@" + re.escape(bot.name) + r"\b", re.IGNORECASE)
            if pattern.search(message):
                matched_bot_ids.append(bot_id)
                logger.debug(
                    "Room %s: mention matched bot %s (%s)",
                    self.room_id,
                    bot_id,
                    bot.name,
                )

        if not matched_bot_ids:
            logger.debug(
                "Room %s: no mentions matched. Registered bots: %s",
                self.room_id,
                [b.name for b in self.bot_configs.values()],
            )
        return matched_bot_ids

    def is_on_cooldown(self, bot_id: str) -> bool:
        """Check if a bot is still in its cooldown window."""
        state = self.cooldowns.get(bot_id)
        if state is None:
            return False
        if state.is_responding:
            return True
        elapsed = time.time() - state.last_response_time
        return elapsed < self.cooldown_seconds

    def mark_responding(self, bot_id: str) -> None:
        """Mark a bot as currently responding."""
        if bot_id not in self.cooldowns:
            self.cooldowns[bot_id] = BotCooldownState()
        self.cooldowns[bot_id].is_responding = True

    def mark_done(self, bot_id: str) -> None:
        """Mark a bot as done responding and start cooldown."""
        if bot_id not in self.cooldowns:
            self.cooldowns[bot_id] = BotCooldownState()
        self.cooldowns[bot_id].is_responding = False
        self.cooldowns[bot_id].last_response_time = time.time()

    def select_respondents(
        self,
        message: str,
        sender_type: str,
        exclude_bot_id: str | None = None,
    ) -> list[str]:
        """Select which bots should respond to a message.

        Rules:
        1. System messages -> no response
        2. @mentions found -> those bots respond (bypass cooldown)
        3. No mentions + auto_relevance -> first available bot not on cooldown

        Args:
            exclude_bot_id: Bot ID to exclude (prevents a bot from triggering itself).
        """
        if sender_type == "system":
            return []

        logger.debug(
            "Room %s: select_respondents — sender_type=%s, registered bots: %s",
            self.room_id,
            sender_type,
            [b.name for b in self.bot_configs.values()],
        )

        # Check for @mentions
        mentioned_ids = self.parse_mentions(message)
        if mentioned_ids:
            # @mentioned bots respond regardless of cooldown, exclude sender
            respondents = [bid for bid in mentioned_ids if bid != exclude_bot_id]
            logger.debug("Room %s: selected respondents (mentions): %s", self.room_id, respondents)
            return respondents

        if not self.auto_relevance:
            logger.debug("Room %s: auto_relevance disabled, no respondents", self.room_id)
            return []

        # Auto-select: all bots not on cooldown (excluding observers)
        available = []
        for bot_id in self.bot_configs:
            if bot_id == exclude_bot_id:
                continue
            if self.bot_roles.get(bot_id) == "observer":
                continue
            if not self.is_on_cooldown(bot_id):
                available.append(bot_id)

        # Sort: leads first for sequential/chain benefit
        available.sort(key=lambda bid: (0 if self.bot_roles.get(bid) == "lead" else 1))

        if available:
            logger.debug("Room %s: auto-selected respondent: %s", self.room_id, available[0])
            return [available[0]]

        logger.debug("Room %s: all bots on cooldown, no respondents", self.room_id)
        return []

    def build_room_context(self, bot_id: str, recent_messages: list[RoomMessage]) -> str:
        """Build a transcript context string for a bot.

        Formats the last N messages as "sender: content" lines.
        """
        bot = self.bot_configs.get(bot_id)
        if not bot:
            return ""

        # Build participant list
        bot_names = [b.name for b in self.bot_configs.values()]
        participants_str = ", ".join(bot_names)

        lines = []
        for msg in recent_messages[-50:]:
            lines.append(f"{msg.sender_name}: {msg.content}")

        transcript = "\n".join(lines)

        # Role-specific instructions
        role = self.bot_roles.get(bot_id, "default")
        role_instructions = {
            "lead": "\nYou are the LEAD. Guide the conversation and synthesize conclusions.",
            "reviewer": "\nYou are a REVIEWER. Critically evaluate and suggest improvements.",
            "observer": "\nYou are an OBSERVER. Only respond when explicitly addressed.",
            "specialist": "\nYou are a SPECIALIST. Focus on your area of expertise.",
        }
        role_line = role_instructions.get(role, "")

        return (
            f"\n\n--- ROOM CONTEXT ---\n"
            f"You are {bot.name} in a collaborative room.\n"
            f"Other bots in the room: {participants_str}\n"
            f"Respond naturally as yourself. Do not impersonate other participants.\n"
            f"You can mention other bots with @BotName to bring them into the conversation "
            f"(e.g. @{bot_names[0] if bot_names else 'BotName'}). "
            f"Use @all to address everyone.\n"
            f"{role_line}\n"
            f"\nRecent conversation:\n{transcript}\n"
            f"--- END ROOM CONTEXT ---"
        )

    def build_chain_context(
        self,
        bot_id: str,
        recent_messages: list[RoomMessage],
        previous_outputs: list[tuple[str, str]],
    ) -> str:
        """Build context for chain mode including previous bots' outputs.

        Args:
            previous_outputs: List of (bot_name, response_text) from earlier chain steps.
        """
        base = self.build_room_context(bot_id, recent_messages)

        if not previous_outputs:
            return base

        chain_lines = []
        for name, output in previous_outputs:
            # Truncate each output to ~2000 chars
            truncated = output[:2000] + ("..." if len(output) > 2000 else "")
            chain_lines.append(f"{name}:\n{truncated}")

        chain_section = "\n\n".join(chain_lines)

        return (
            f"{base}\n\n"
            f"--- CHAIN CONTEXT ---\n"
            f"Previous bots in this chain have already responded:\n\n"
            f"{chain_section}\n\n"
            f"Build on their work. Do not repeat what they said.\n"
            f"--- END CHAIN CONTEXT ---"
        )


# =============================================================================
# MODULE-LEVEL REGISTRY
# =============================================================================

_active_orchestrators: dict[str, RoomOrchestrator] = {}


def get_room_orchestrator(room_id: str) -> RoomOrchestrator | None:
    """Get the orchestrator for an active room."""
    return _active_orchestrators.get(room_id)


def create_room_orchestrator(
    room_id: str,
    cooldown_seconds: float = 5.0,
    auto_relevance: bool = True,
    response_mode: str = "parallel",
) -> RoomOrchestrator:
    """Create and register an orchestrator for a room."""
    orchestrator = RoomOrchestrator(
        room_id=room_id,
        cooldown_seconds=cooldown_seconds,
        auto_relevance=auto_relevance,
        response_mode=response_mode,
    )
    _active_orchestrators[room_id] = orchestrator
    return orchestrator


def remove_room_orchestrator(room_id: str) -> None:
    """Remove an orchestrator when a room is no longer active."""
    _active_orchestrators.pop(room_id, None)


async def route_message(
    orchestrator: RoomOrchestrator,
    message: str,
    config: Config,
) -> tuple[str, str]:
    """Use an LLM to pick the best bot for a message.

    Returns:
        (bot_id, reason) tuple.
    """
    from cachibot.services.name_generator import (
        _chat_completion,
        _extract_json,
        _resolve_utility_model,
    )

    # Build bot descriptions for the prompt
    candidates = []
    for bot_id, bot in orchestrator.bot_configs.items():
        role = orchestrator.bot_roles.get(bot_id, "default")
        if role == "observer":
            continue
        desc = bot.description or "General-purpose assistant"
        candidates.append({"id": bot_id, "name": bot.name, "description": desc})

    if not candidates:
        # Fallback: first bot
        first_id = next(iter(orchestrator.bot_configs))
        return first_id, "No eligible bots for routing"

    if len(candidates) == 1:
        return candidates[0]["id"], "Only one eligible bot"

    bot_list = "\n".join(
        f'- id="{c["id"]}", name="{c["name"]}": {c["description"]}' for c in candidates
    )

    prompt = (
        f"You are a message router. Given a user message and a list of available bots, "
        f"pick the single best bot to respond.\n\n"
        f"Available bots:\n{bot_list}\n\n"
        f"User message: {message[:500]}\n\n"
        f'Respond with ONLY a JSON object: {{"bot_id": "...", "reason": "..."}}'
    )

    try:
        model = _resolve_utility_model()
        response = await _chat_completion(prompt, model)
        data = _extract_json(response)
        chosen_id = data.get("bot_id", "")
        reason = data.get("reason", "Best match")

        # Validate the chosen bot exists
        valid_ids = {c["id"] for c in candidates}
        if chosen_id in valid_ids:
            return chosen_id, reason

        # Fuzzy match by name
        chosen_name = data.get("name", "").lower()
        for c in candidates:
            if c["name"].lower() == chosen_name:
                return c["id"], reason

        # Fallback to first candidate
        logger.warning("Router picked unknown bot_id=%s, falling back", chosen_id)
        return candidates[0]["id"], "Fallback: router picked unknown bot"

    except Exception as e:
        logger.warning("Router LLM failed: %s, falling back to first bot", e)
        return candidates[0]["id"], f"Fallback: {e}"
