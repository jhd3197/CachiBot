"""Room orchestrator for multi-agent turn logic.

Manages bot response selection, cooldowns, and @mention parsing.
One instance per active room.
"""

import logging
import re
import time
from dataclasses import dataclass, field

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

    def register_bot(self, bot: Bot) -> None:
        """Register a bot in this room."""
        self.bot_configs[bot.id] = bot
        if bot.id not in self.cooldowns:
            self.cooldowns[bot.id] = BotCooldownState()

    def remove_bot(self, bot_id: str) -> None:
        """Remove a bot from this room."""
        self.bot_configs.pop(bot_id, None)
        self.cooldowns.pop(bot_id, None)

    def parse_mentions(self, message: str) -> list[str]:
        """Extract @BotName mentions and match to registered bot IDs.

        Case-insensitive matching against bot names.
        """
        # Find all @mentions in the message
        mention_pattern = re.compile(r"@(\w+(?:\s+\w+)*)")
        raw_mentions = mention_pattern.findall(message)

        if not raw_mentions:
            return []

        matched_bot_ids = []
        for mention in raw_mentions:
            mention_lower = mention.lower().strip()
            for bot_id, bot in self.bot_configs.items():
                if bot.name.lower() == mention_lower:
                    matched_bot_ids.append(bot_id)
                    break

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

    def select_respondents(self, message: str, sender_type: str) -> list[str]:
        """Select which bots should respond to a message.

        Rules:
        1. System messages -> no response
        2. @mentions found -> those bots respond (bypass cooldown)
        3. No mentions + auto_relevance -> first available bot not on cooldown
        """
        if sender_type == "system":
            return []

        # Check for @mentions
        mentioned_ids = self.parse_mentions(message)
        if mentioned_ids:
            # @mentioned bots respond regardless of cooldown
            return mentioned_ids

        if not self.auto_relevance:
            return []

        # Auto-select first available bot not on cooldown
        for bot_id in self.bot_configs:
            if not self.is_on_cooldown(bot_id):
                return [bot_id]

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

        return (
            f"\n\n--- ROOM CONTEXT ---\n"
            f"You are {bot.name} in a collaborative room.\n"
            f"Other bots in the room: {participants_str}\n"
            f"Respond naturally as yourself. Do not impersonate other participants.\n"
            f"\nRecent conversation:\n{transcript}\n"
            f"--- END ROOM CONTEXT ---"
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
) -> RoomOrchestrator:
    """Create and register an orchestrator for a room."""
    orchestrator = RoomOrchestrator(
        room_id=room_id,
        cooldown_seconds=cooldown_seconds,
        auto_relevance=auto_relevance,
    )
    _active_orchestrators[room_id] = orchestrator
    return orchestrator


def remove_room_orchestrator(room_id: str) -> None:
    """Remove an orchestrator when a room is no longer active."""
    _active_orchestrators.pop(room_id, None)
