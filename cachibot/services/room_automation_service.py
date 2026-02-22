"""Room Automation Engine.

Evaluates trigger conditions and dispatches actions for room automations.
"""

import logging
from typing import Any

from cachibot.models.room import RoomAutomationResponse
from cachibot.storage.room_repository import RoomAutomationRepository

logger = logging.getLogger(__name__)

automation_repo = RoomAutomationRepository()


class RoomAutomationEngine:
    """Evaluates automation triggers and dispatches actions."""

    async def on_message(
        self, room_id: str, message: str, sender_type: str
    ) -> list[tuple[RoomAutomationResponse, str]]:
        """Evaluate on_message and on_keyword triggers for a new message.

        Returns list of (automation, action_type) that should fire.
        Only user messages trigger automations.
        """
        if sender_type != "user":
            return []

        fired: list[tuple[RoomAutomationResponse, str]] = []

        # Check on_message triggers
        on_msg = await automation_repo.get_enabled_by_trigger("on_message", room_id)
        for auto in on_msg:
            fired.append((auto, auto.actionType))
            await automation_repo.increment_trigger_count(auto.id)

        # Check on_keyword triggers
        on_kw = await automation_repo.get_enabled_by_trigger("on_keyword", room_id)
        msg_lower = message.lower()
        for auto in on_kw:
            keywords = auto.triggerConfig.get("keywords", [])
            if any(kw.lower() in msg_lower for kw in keywords):
                fired.append((auto, auto.actionType))
                await automation_repo.increment_trigger_count(auto.id)

        return fired

    def build_action_context(
        self,
        automation: RoomAutomationResponse,
        message: str | None = None,
    ) -> dict[str, Any]:
        """Build context dict for action execution.

        The caller (WS handler) uses this to dispatch the actual action.
        """
        config = automation.actionConfig
        action = automation.actionType

        if action == "send_message":
            return {
                "action": "send_message",
                "bot_id": config.get("bot_id", ""),
                "message": config.get("message", ""),
            }
        elif action == "summarize":
            return {
                "action": "summarize",
                "bot_id": config.get("bot_id", ""),
                "message_count": config.get("message_count", 50),
            }
        elif action == "pin_message":
            return {
                "action": "pin_message",
            }
        else:
            logger.warning(
                "Unknown action type %s in automation %s",
                action,
                automation.id,
            )
            return {"action": "unknown"}


# Module-level singleton
_engine: RoomAutomationEngine | None = None


def get_automation_engine() -> RoomAutomationEngine:
    """Get or create the automation engine singleton."""
    global _engine
    if _engine is None:
        _engine = RoomAutomationEngine()
    return _engine
