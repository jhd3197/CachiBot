"""Room-specific WebSocket message models."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RoomWSMessageType(str, Enum):
    """WebSocket message types for room communication."""

    # Client -> Server
    ROOM_CHAT = "room_chat"
    ROOM_TYPING = "room_typing"
    ROOM_CANCEL = "room_cancel"

    # Server -> Client
    ROOM_MESSAGE = "room_message"
    ROOM_BOT_THINKING = "room_bot_thinking"
    ROOM_BOT_TOOL_START = "room_bot_tool_start"
    ROOM_BOT_TOOL_END = "room_bot_tool_end"
    ROOM_BOT_INSTRUCTION_DELTA = "room_bot_instruction_delta"
    ROOM_BOT_DONE = "room_bot_done"
    ROOM_TYPING_INDICATOR = "room_typing_indicator"
    ROOM_PRESENCE = "room_presence"
    ROOM_ERROR = "room_error"
    ROOM_USAGE = "room_usage"
    ROOM_CHAIN_STEP = "room_chain_step"
    ROOM_ROUTE_DECISION = "room_route_decision"

    # Debate lifecycle
    ROOM_DEBATE_ROUND_START = "room_debate_round_start"
    ROOM_DEBATE_ROUND_END = "room_debate_round_end"
    ROOM_DEBATE_JUDGE_START = "room_debate_judge_start"
    ROOM_DEBATE_COMPLETE = "room_debate_complete"

    # Waterfall lifecycle
    ROOM_WATERFALL_STEP = "room_waterfall_step"
    ROOM_WATERFALL_SKIPPED = "room_waterfall_skipped"
    ROOM_WATERFALL_STOPPED = "room_waterfall_stopped"

    # Social features
    ROOM_REACTION_ADD = "room_reaction_add"
    ROOM_REACTION_REMOVE = "room_reaction_remove"
    ROOM_PIN_ADD = "room_pin_add"
    ROOM_PIN_REMOVE = "room_pin_remove"
    ROOM_VARIABLE_UPDATE = "room_variable_update"

    # New response modes
    ROOM_CONSENSUS_SYNTHESIZING = "room_consensus_synthesizing"
    ROOM_CONSENSUS_COMPLETE = "room_consensus_complete"
    ROOM_INTERVIEW_QUESTION = "room_interview_question"
    ROOM_INTERVIEW_HANDOFF = "room_interview_handoff"

    # Automations
    ROOM_AUTOMATION_TRIGGERED = "room_automation_triggered"


class RoomWSMessage(BaseModel):
    """Generic room WebSocket message wrapper."""

    type: RoomWSMessageType = Field(description="Message type")
    payload: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def room_message(
        cls,
        room_id: str,
        sender_type: str,
        sender_id: str,
        sender_name: str,
        content: str,
        message_id: str | None = None,
    ) -> "RoomWSMessage":
        """Create a room message."""
        return cls(
            type=RoomWSMessageType.ROOM_MESSAGE,
            payload={
                "roomId": room_id,
                "senderType": sender_type,
                "senderId": sender_id,
                "senderName": sender_name,
                "content": content,
                "messageId": message_id,
            },
        )

    @classmethod
    def bot_thinking(
        cls, room_id: str, bot_id: str, bot_name: str, content: str | None = None
    ) -> "RoomWSMessage":
        """Create a bot thinking indicator, optionally with thinking text content."""
        payload: dict[str, Any] = {"roomId": room_id, "botId": bot_id, "botName": bot_name}
        if content is not None:
            payload["content"] = content
        return cls(
            type=RoomWSMessageType.ROOM_BOT_THINKING,
            payload=payload,
        )

    @classmethod
    def bot_tool_start(
        cls,
        room_id: str,
        bot_id: str,
        bot_name: str,
        tool_id: str,
        tool_name: str,
        args: dict[str, Any],
        message_id: str = "",
    ) -> "RoomWSMessage":
        """Create a bot tool start message."""
        return cls(
            type=RoomWSMessageType.ROOM_BOT_TOOL_START,
            payload={
                "roomId": room_id,
                "botId": bot_id,
                "botName": bot_name,
                "toolId": tool_id,
                "toolName": tool_name,
                "args": args,
                "messageId": message_id,
            },
        )

    @classmethod
    def bot_tool_end(
        cls,
        room_id: str,
        bot_id: str,
        bot_name: str,
        tool_id: str,
        result: Any,
        success: bool = True,
        message_id: str = "",
    ) -> "RoomWSMessage":
        """Create a bot tool end message."""
        return cls(
            type=RoomWSMessageType.ROOM_BOT_TOOL_END,
            payload={
                "roomId": room_id,
                "botId": bot_id,
                "botName": bot_name,
                "toolId": tool_id,
                "result": result,
                "success": success,
                "messageId": message_id,
            },
        )

    @classmethod
    def bot_instruction_delta(
        cls,
        room_id: str,
        bot_id: str,
        bot_name: str,
        tool_id: str,
        text: str,
    ) -> "RoomWSMessage":
        """Incremental text from a bot's instruction LLM execution."""
        return cls(
            type=RoomWSMessageType.ROOM_BOT_INSTRUCTION_DELTA,
            payload={
                "roomId": room_id,
                "botId": bot_id,
                "botName": bot_name,
                "toolId": tool_id,
                "text": text,
            },
        )

    @classmethod
    def bot_done(
        cls,
        room_id: str,
        bot_id: str,
        bot_name: str,
        message_id: str = "",
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> "RoomWSMessage":
        """Create a bot done message, optionally carrying accumulated tool calls."""
        payload: dict[str, Any] = {
            "roomId": room_id,
            "botId": bot_id,
            "botName": bot_name,
            "messageId": message_id,
        }
        if tool_calls:
            payload["toolCalls"] = tool_calls
        return cls(
            type=RoomWSMessageType.ROOM_BOT_DONE,
            payload=payload,
        )

    @classmethod
    def typing_indicator(
        cls, room_id: str, user_id: str, username: str, is_typing: bool
    ) -> "RoomWSMessage":
        """Create a typing indicator."""
        return cls(
            type=RoomWSMessageType.ROOM_TYPING_INDICATOR,
            payload={
                "roomId": room_id,
                "userId": user_id,
                "username": username,
                "isTyping": is_typing,
            },
        )

    @classmethod
    def presence(cls, room_id: str, user_id: str, username: str, status: str) -> "RoomWSMessage":
        """Create a presence update (online/offline)."""
        return cls(
            type=RoomWSMessageType.ROOM_PRESENCE,
            payload={
                "roomId": room_id,
                "userId": user_id,
                "username": username,
                "status": status,
            },
        )

    @classmethod
    def error(cls, room_id: str, message: str, bot_id: str | None = None) -> "RoomWSMessage":
        """Create a room error message."""
        payload: dict[str, Any] = {"roomId": room_id, "message": message}
        if bot_id:
            payload["botId"] = bot_id
        return cls(type=RoomWSMessageType.ROOM_ERROR, payload=payload)

    @classmethod
    def usage(
        cls,
        room_id: str,
        bot_id: str,
        message_id: str = "",
        tokens: int = 0,
        cost: float = 0.0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        elapsed_ms: float = 0.0,
        tokens_per_second: float = 0.0,
        model: str = "",
    ) -> "RoomWSMessage":
        """Create a usage stats message."""
        return cls(
            type=RoomWSMessageType.ROOM_USAGE,
            payload={
                "roomId": room_id,
                "botId": bot_id,
                "messageId": message_id,
                "totalTokens": tokens,
                "totalCost": cost,
                "promptTokens": prompt_tokens,
                "completionTokens": completion_tokens,
                "elapsedMs": elapsed_ms,
                "tokensPerSecond": tokens_per_second,
                "model": model,
            },
        )

    @classmethod
    def chain_step(
        cls,
        room_id: str,
        step: int,
        total_steps: int,
        bot_id: str,
        bot_name: str,
    ) -> "RoomWSMessage":
        """Create a chain step progress indicator."""
        return cls(
            type=RoomWSMessageType.ROOM_CHAIN_STEP,
            payload={
                "roomId": room_id,
                "step": step,
                "totalSteps": total_steps,
                "botId": bot_id,
                "botName": bot_name,
            },
        )

    @classmethod
    def route_decision(
        cls,
        room_id: str,
        bot_id: str,
        bot_name: str,
        reason: str,
        confidence: float = 0.0,
        strategy: str = "llm",
    ) -> "RoomWSMessage":
        """Create a route decision message."""
        return cls(
            type=RoomWSMessageType.ROOM_ROUTE_DECISION,
            payload={
                "roomId": room_id,
                "botId": bot_id,
                "botName": bot_name,
                "reason": reason,
                "confidence": confidence,
                "strategy": strategy,
            },
        )

    # ----- Debate lifecycle -----

    @classmethod
    def debate_round_start(cls, room_id: str, round_num: int, total_rounds: int) -> "RoomWSMessage":
        return cls(
            type=RoomWSMessageType.ROOM_DEBATE_ROUND_START,
            payload={"roomId": room_id, "round": round_num, "totalRounds": total_rounds},
        )

    @classmethod
    def debate_round_end(cls, room_id: str, round_num: int) -> "RoomWSMessage":
        return cls(
            type=RoomWSMessageType.ROOM_DEBATE_ROUND_END,
            payload={"roomId": room_id, "round": round_num},
        )

    @classmethod
    def debate_judge_start(
        cls, room_id: str, judge_bot_id: str, judge_bot_name: str
    ) -> "RoomWSMessage":
        return cls(
            type=RoomWSMessageType.ROOM_DEBATE_JUDGE_START,
            payload={"roomId": room_id, "botId": judge_bot_id, "botName": judge_bot_name},
        )

    @classmethod
    def debate_complete(
        cls, room_id: str, rounds_completed: int, has_verdict: bool
    ) -> "RoomWSMessage":
        return cls(
            type=RoomWSMessageType.ROOM_DEBATE_COMPLETE,
            payload={
                "roomId": room_id,
                "roundsCompleted": rounds_completed,
                "hasVerdict": has_verdict,
            },
        )

    # ----- Waterfall lifecycle -----

    @classmethod
    def waterfall_step(
        cls, room_id: str, step: int, total_steps: int, bot_id: str, bot_name: str
    ) -> "RoomWSMessage":
        return cls(
            type=RoomWSMessageType.ROOM_WATERFALL_STEP,
            payload={
                "roomId": room_id,
                "step": step,
                "totalSteps": total_steps,
                "botId": bot_id,
                "botName": bot_name,
            },
        )

    @classmethod
    def waterfall_skipped(
        cls, room_id: str, bot_id: str, bot_name: str, reason: str
    ) -> "RoomWSMessage":
        return cls(
            type=RoomWSMessageType.ROOM_WATERFALL_SKIPPED,
            payload={"roomId": room_id, "botId": bot_id, "botName": bot_name, "reason": reason},
        )

    @classmethod
    def waterfall_stopped(cls, room_id: str, stopped_at_bot_name: str) -> "RoomWSMessage":
        return cls(
            type=RoomWSMessageType.ROOM_WATERFALL_STOPPED,
            payload={"roomId": room_id, "stoppedAtBotName": stopped_at_bot_name},
        )

    # ----- Social features -----

    @classmethod
    def reaction_add(
        cls,
        room_id: str,
        message_id: str,
        user_id: str,
        emoji: str,
    ) -> "RoomWSMessage":
        return cls(
            type=RoomWSMessageType.ROOM_REACTION_ADD,
            payload={
                "roomId": room_id,
                "messageId": message_id,
                "userId": user_id,
                "emoji": emoji,
            },
        )

    @classmethod
    def reaction_remove(
        cls,
        room_id: str,
        message_id: str,
        user_id: str,
        emoji: str,
    ) -> "RoomWSMessage":
        return cls(
            type=RoomWSMessageType.ROOM_REACTION_REMOVE,
            payload={
                "roomId": room_id,
                "messageId": message_id,
                "userId": user_id,
                "emoji": emoji,
            },
        )

    @classmethod
    def pin_add(
        cls,
        room_id: str,
        message_id: str,
        pinned_by: str,
    ) -> "RoomWSMessage":
        return cls(
            type=RoomWSMessageType.ROOM_PIN_ADD,
            payload={
                "roomId": room_id,
                "messageId": message_id,
                "pinnedBy": pinned_by,
            },
        )

    @classmethod
    def pin_remove(
        cls,
        room_id: str,
        message_id: str,
    ) -> "RoomWSMessage":
        return cls(
            type=RoomWSMessageType.ROOM_PIN_REMOVE,
            payload={
                "roomId": room_id,
                "messageId": message_id,
            },
        )

    @classmethod
    def variable_update(cls, room_id: str, variables: dict[str, str]) -> "RoomWSMessage":
        return cls(
            type=RoomWSMessageType.ROOM_VARIABLE_UPDATE,
            payload={"roomId": room_id, "variables": variables},
        )

    # ----- Consensus mode -----

    @classmethod
    def consensus_synthesizing(
        cls, room_id: str, bot_id: str, bot_name: str, response_count: int
    ) -> "RoomWSMessage":
        return cls(
            type=RoomWSMessageType.ROOM_CONSENSUS_SYNTHESIZING,
            payload={
                "roomId": room_id,
                "botId": bot_id,
                "botName": bot_name,
                "responseCount": response_count,
            },
        )

    @classmethod
    def consensus_complete(cls, room_id: str, response_count: int) -> "RoomWSMessage":
        return cls(
            type=RoomWSMessageType.ROOM_CONSENSUS_COMPLETE,
            payload={"roomId": room_id, "responseCount": response_count},
        )

    # ----- Interview mode -----

    @classmethod
    def interview_question(
        cls, room_id: str, question_num: int, max_questions: int
    ) -> "RoomWSMessage":
        return cls(
            type=RoomWSMessageType.ROOM_INTERVIEW_QUESTION,
            payload={
                "roomId": room_id,
                "questionNum": question_num,
                "maxQuestions": max_questions,
            },
        )

    @classmethod
    def interview_handoff(cls, room_id: str, reason: str) -> "RoomWSMessage":
        return cls(
            type=RoomWSMessageType.ROOM_INTERVIEW_HANDOFF,
            payload={"roomId": room_id, "reason": reason},
        )

    # ----- Automations -----

    @classmethod
    def automation_triggered(
        cls, room_id: str, automation_name: str, trigger_type: str
    ) -> "RoomWSMessage":
        return cls(
            type=RoomWSMessageType.ROOM_AUTOMATION_TRIGGERED,
            payload={
                "roomId": room_id,
                "automationName": automation_name,
                "triggerType": trigger_type,
            },
        )
