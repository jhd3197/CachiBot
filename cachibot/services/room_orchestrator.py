"""Room orchestrator for multi-agent turn logic.

Manages bot response selection, cooldowns, and @mention parsing.
One instance per active room.
"""

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

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
class DebateTranscriptEntry:
    """A single entry in a debate transcript."""

    round: int
    bot_id: str
    bot_name: str
    position: str | None
    content: str


@dataclass
class RoomOrchestrator:
    """Manages turn logic for a single room."""

    room_id: str
    bot_configs: dict[str, Bot] = field(default_factory=dict)
    cooldowns: dict[str, BotCooldownState] = field(default_factory=dict)
    cooldown_seconds: float = 5.0
    auto_relevance: bool = True
    # parallel | sequential | chain | router | debate | waterfall | relay | consensus | interview
    response_mode: str = "parallel"
    bot_roles: dict[str, str] = field(default_factory=dict)

    # Router strategy
    routing_strategy: str = "llm"
    bot_keywords: dict[str, list[str]] = field(default_factory=dict)
    _rr_index: int = 0  # round-robin counter

    # Room personality and variables
    room_system_prompt: str = ""
    room_variables: dict[str, str] = field(default_factory=dict)

    # Interview mode state
    interview_question_count: int = 0
    interview_handoff_triggered: bool = False

    # Consensus state
    _consensus_responses: list[tuple[str, str, str]] = field(
        default_factory=list
    )  # (bot_id, bot_name, response)

    # Debate state
    debate_transcript: list[DebateTranscriptEntry] = field(default_factory=list)

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
        available.sort(key=lambda bid: 0 if self.bot_roles.get(bid) == "lead" else 1)

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

        # Room personality injection
        personality_block = ""
        if self.room_system_prompt:
            personality_block = (
                f"\n--- ROOM INSTRUCTIONS ---\n{self.room_system_prompt}\n"
                f"--- END ROOM INSTRUCTIONS ---\n"
            )

        # Room variables injection
        variables_block = ""
        if self.room_variables:
            var_lines = "\n".join(f"  {k} = {v}" for k, v in self.room_variables.items())
            variables_block = f"\n--- ROOM VARIABLES ---\n{var_lines}\n--- END ROOM VARIABLES ---\n"

        return (
            f"\n\n--- ROOM CONTEXT ---\n"
            f"You are {bot.name} in a collaborative room.\n"
            f"Other bots in the room: {participants_str}\n"
            f"Respond naturally as yourself. Do not impersonate other participants.\n"
            f"You can mention other bots with @BotName to bring them into the conversation "
            f"(e.g. @{bot_names[0] if bot_names else 'BotName'}). "
            f"Use @all to address everyone.\n"
            f"{role_line}\n"
            f"{personality_block}"
            f"{variables_block}"
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

    def reset_debate_state(self) -> None:
        """Clear debate transcript for a fresh debate."""
        self.debate_transcript.clear()

    def build_debate_context(
        self,
        bot_id: str,
        topic: str,
        positions: dict[str, str],
        round_num: int,
        recent_messages: list[RoomMessage],
    ) -> str:
        """Build a context prompt for a debate participant.

        Includes room context, the debate topic, this bot's position,
        and a transcript of all prior arguments.
        """
        base = self.build_room_context(bot_id, recent_messages)
        position = positions.get(bot_id)
        position_line = f"Your assigned position is: {position}\n" if position else ""

        # Build transcript of prior entries
        transcript_lines = []
        for entry in self.debate_transcript:
            pos_tag = f" [{entry.position}]" if entry.position else ""
            transcript_lines.append(
                f"Round {entry.round + 1} — {entry.bot_name}{pos_tag}:\n{entry.content}"
            )
        transcript_str = (
            "\n\n".join(transcript_lines) if transcript_lines else "(no prior arguments)"
        )

        return (
            f"{base}\n\n"
            f"--- DEBATE CONTEXT ---\n"
            f"Topic: {topic}\n"
            f"Round: {round_num + 1}\n"
            f"{position_line}"
            f"Argue your position clearly and persuasively.\n\n"
            f"Prior arguments:\n{transcript_str}\n"
            f"--- END DEBATE CONTEXT ---"
        )

    def build_judge_context(
        self,
        bot_id: str,
        topic: str,
        judge_prompt_template: str,
        recent_messages: list[RoomMessage],
    ) -> str:
        """Build a context prompt for the debate judge.

        Substitutes {topic} and {transcript} in the judge prompt template.
        """
        base = self.build_room_context(bot_id, recent_messages)

        transcript_lines = []
        for entry in self.debate_transcript:
            pos_tag = f" [{entry.position}]" if entry.position else ""
            transcript_lines.append(
                f"Round {entry.round + 1} — {entry.bot_name}{pos_tag}:\n{entry.content}"
            )
        transcript_str = "\n\n".join(transcript_lines)

        judge_instruction = judge_prompt_template.replace("{topic}", topic).replace(
            "{transcript}", transcript_str
        )

        return f"{base}\n\n--- JUDGE CONTEXT ---\n{judge_instruction}\n--- END JUDGE CONTEXT ---"

    # -- Consensus helpers --

    def reset_consensus_state(self) -> None:
        """Clear collected consensus responses for a fresh round."""
        self._consensus_responses.clear()

    def add_consensus_response(self, bot_id: str, bot_name: str, response: str) -> None:
        """Record a hidden bot response for later synthesis."""
        self._consensus_responses.append((bot_id, bot_name, response))

    def build_consensus_synthesis_context(
        self,
        synthesizer_bot_id: str,
        topic: str,
        recent_messages: list[RoomMessage],
    ) -> str:
        """Build context for the synthesizer bot to merge consensus responses."""
        base = self.build_room_context(synthesizer_bot_id, recent_messages)

        response_lines = []
        for _bid, bname, resp in self._consensus_responses:
            truncated = resp[:3000] + ("..." if len(resp) > 3000 else "")
            response_lines.append(f"{bname}:\n{truncated}")

        responses_section = "\n\n".join(response_lines)

        return (
            f"{base}\n\n"
            f"--- CONSENSUS SYNTHESIS ---\n"
            f"The user asked: {topic[:500]}\n\n"
            f"The following bots responded independently:\n\n"
            f"{responses_section}\n\n"
            f"Synthesize these responses into a single, coherent answer.\n"
            f"Identify points of agreement and note any significant disagreements.\n"
            f"--- END CONSENSUS SYNTHESIS ---"
        )

    # -- Interview helpers --

    def reset_interview_state(self) -> None:
        """Reset interview mode state for a new session."""
        self.interview_question_count = 0
        self.interview_handoff_triggered = False

    def build_interview_context(
        self,
        interviewer_bot_id: str,
        recent_messages: list[RoomMessage],
        max_questions: int,
    ) -> str:
        """Build context for the interviewer bot."""
        base = self.build_room_context(interviewer_bot_id, recent_messages)
        remaining = max_questions - self.interview_question_count

        return (
            f"{base}\n\n"
            f"--- INTERVIEW MODE ---\n"
            f"You are the interviewer. Ask focused questions to gather context.\n"
            f"Questions asked so far: {self.interview_question_count}/{max_questions}\n"
            f"Questions remaining: {remaining}\n"
            f"When you have enough context or reach the limit, include [HANDOFF] "
            f"in your response to hand off to the specialist bots.\n"
            f"--- END INTERVIEW MODE ---"
        )

    def check_interview_handoff(
        self,
        response_text: str,
        handoff_trigger: str,
        max_questions: int,
    ) -> bool:
        """Check if the interview should hand off to specialists.

        Returns True if handoff should occur.
        """
        if self.interview_handoff_triggered:
            return True

        self.interview_question_count += 1

        if handoff_trigger == "keyword":
            if "[HANDOFF]" in response_text.upper():
                self.interview_handoff_triggered = True
                return True
        elif handoff_trigger == "auto":
            # Auto: hand off if [HANDOFF] detected OR max questions reached
            if "[HANDOFF]" in response_text.upper():
                self.interview_handoff_triggered = True
                return True
            if self.interview_question_count >= max_questions:
                self.interview_handoff_triggered = True
                return True
        # "manual" — only user can trigger by typing "done" or "handoff"
        # (handled in the WS handler, not here)

        return False


# =============================================================================
# MODULE-LEVEL ROUTING FUNCTIONS
# =============================================================================


def keyword_route(orchestrator: RoomOrchestrator, message: str) -> tuple[str, str, float]:
    """Match message tokens against per-bot keyword lists.

    Returns:
        (bot_id, reason, confidence) tuple.
    """
    msg_lower = message.lower()
    best_id = ""
    best_hits = 0
    best_total = 1

    for bot_id, keywords in orchestrator.bot_keywords.items():
        if not keywords:
            continue
        if orchestrator.bot_roles.get(bot_id) == "observer":
            continue
        hits = sum(1 for kw in keywords if kw.lower() in msg_lower)
        if hits > best_hits:
            best_hits = hits
            best_total = len(keywords)
            best_id = bot_id

    if best_id:
        confidence = best_hits / best_total
        return best_id, f"Matched {best_hits} keyword(s)", confidence

    # Fallback: first non-observer bot
    for bot_id in orchestrator.bot_configs:
        if orchestrator.bot_roles.get(bot_id) != "observer":
            return bot_id, "No keyword match, fallback", 0.0
    first_id = next(iter(orchestrator.bot_configs))
    return first_id, "No eligible bots", 0.0


def round_robin_route(orchestrator: RoomOrchestrator) -> tuple[str, str, float]:
    """Rotate through non-observer bots.

    Returns:
        (bot_id, reason, confidence) tuple.
    """
    eligible = [
        bid for bid in orchestrator.bot_configs if orchestrator.bot_roles.get(bid) != "observer"
    ]
    if not eligible:
        first_id = next(iter(orchestrator.bot_configs))
        return first_id, "No eligible bots", 0.0

    idx = orchestrator._rr_index % len(eligible)
    orchestrator._rr_index += 1
    chosen = eligible[idx]
    bot = orchestrator.bot_configs[chosen]
    return chosen, f"Round-robin: {bot.name}'s turn", 1.0


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
    routing_strategy: str = "llm",
    bot_keywords: dict[str, list[str]] | None = None,
    room_system_prompt: str = "",
    room_variables: dict[str, str] | None = None,
) -> RoomOrchestrator:
    """Create and register an orchestrator for a room."""
    orchestrator = RoomOrchestrator(
        room_id=room_id,
        cooldown_seconds=cooldown_seconds,
        auto_relevance=auto_relevance,
        response_mode=response_mode,
        routing_strategy=routing_strategy,
        bot_keywords=bot_keywords or {},
        room_system_prompt=room_system_prompt,
        room_variables=room_variables or {},
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
    bot_models: dict[str, Any] | None = None,
    resolved_env: Any | None = None,
) -> tuple[str, str]:
    """Use an LLM to pick the best bot for a message.

    Args:
        orchestrator: The room orchestrator instance.
        message: The user message to route.
        config: Global config (unused now but kept for backward compat).
        bot_models: Per-bot model slots (checked first for "utility").
        resolved_env: Per-bot resolved environment override.

    Returns:
        (bot_id, reason) tuple.
    """
    from prompture.aio import extract_with_model
    from pydantic import BaseModel as _BaseModel
    from pydantic import Field as _Field

    from cachibot.services.model_resolver import resolve_utility_model

    class _RoutingResult(_BaseModel):
        bot_id: str = _Field(description="The ID of the best bot to handle this message")
        reason: str = _Field(description="Brief reason for this choice")

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
        f"Available bots:\n{bot_list}\n\n"
        f"User message: {message[:500]}"
    )

    try:
        model = resolve_utility_model(bot_models=bot_models, resolved_env=resolved_env)
        data = await extract_with_model(
            _RoutingResult,
            prompt,
            model,
            instruction_template=(
                "You are a message router. Given a user message and a list of available bots, "
                "pick the single best bot to respond."
            ),
        )
        # data["model"] is the Pydantic _RoutingResult instance
        parsed = data["model"]
        chosen_id = parsed.bot_id
        reason = parsed.reason

        # Validate the chosen bot exists
        valid_ids = {c["id"] for c in candidates}
        if chosen_id in valid_ids:
            return chosen_id, reason

        # Fuzzy match by name
        chosen_name = getattr(parsed, "name", "").lower()
        for c in candidates:
            if c["name"].lower() == chosen_name:
                return c["id"], reason

        # Fallback to first candidate
        logger.warning("Router picked unknown bot_id=%s, falling back", chosen_id)
        return candidates[0]["id"], "Fallback: router picked unknown bot"

    except Exception as e:
        logger.warning("Router LLM failed: %s, falling back to first bot", e)
        return candidates[0]["id"], f"Fallback: {e}"
