"""
Circuit Breaker — auto-pause automations after consecutive failures.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


@dataclass
class CircuitBreakerConfig:
    """Configuration for the automation circuit breaker."""

    max_consecutive_failures: int = 5
    cooldown_seconds: int = 3600  # 1 hour


class AutomationCircuitBreaker:
    """Tracks consecutive failures and auto-pauses automations."""

    def __init__(
        self, config: CircuitBreakerConfig | None = None
    ) -> None:
        self._config = config or CircuitBreakerConfig()
        # In-memory tracking: automation_id -> consecutive failure count
        self._failure_counts: dict[str, int] = {}
        # Cooldown tracking: automation_id -> paused_until
        self._cooldowns: dict[str, datetime] = {}

    async def record_outcome(
        self, automation_id: str, success: bool
    ) -> None:
        """Record the outcome of an automation execution.

        On failure: increment counter, auto-pause if threshold reached.
        On success: reset counter.
        """
        if success:
            self._failure_counts.pop(automation_id, None)
            self._cooldowns.pop(automation_id, None)
            return

        count = self._failure_counts.get(automation_id, 0) + 1
        self._failure_counts[automation_id] = count

        if count >= self._config.max_consecutive_failures:
            await self._pause_automation(automation_id, count)

    def is_paused(self, automation_id: str) -> bool:
        """Check if an automation is in cooldown."""
        paused_until = self._cooldowns.get(automation_id)
        if paused_until is None:
            return False
        if datetime.now(timezone.utc) >= paused_until:
            # Cooldown expired
            self._cooldowns.pop(automation_id, None)
            self._failure_counts.pop(automation_id, None)
            return False
        return True

    def get_failure_count(self, automation_id: str) -> int:
        """Get the current consecutive failure count."""
        return self._failure_counts.get(automation_id, 0)

    def reset(self, automation_id: str) -> None:
        """Manually reset the circuit breaker for an automation."""
        self._failure_counts.pop(automation_id, None)
        self._cooldowns.pop(automation_id, None)

    async def _pause_automation(
        self, automation_id: str, failure_count: int
    ) -> None:
        """Auto-pause an automation after too many failures."""
        cooldown_until = datetime.now(timezone.utc) + timedelta(
            seconds=self._config.cooldown_seconds
        )
        self._cooldowns[automation_id] = cooldown_until

        logger.warning(
            "Auto-paused automation %s after %d consecutive failures "
            "(cooldown until %s)",
            automation_id,
            failure_count,
            cooldown_until.isoformat(),
        )

        # Notify via WebSocket
        try:
            from cachibot.api.websocket import get_ws_manager
            from cachibot.models.websocket import WSMessage

            ws = get_ws_manager()
            msg = WSMessage.error(
                f"Automation auto-paused: {failure_count} consecutive failures",
                code="circuit_breaker",
            )
            await ws.broadcast(msg)
        except Exception:
            logger.debug("Could not broadcast circuit breaker notification")


# Singleton
_circuit_breaker: AutomationCircuitBreaker | None = None


def get_circuit_breaker() -> AutomationCircuitBreaker:
    """Get the singleton circuit breaker."""
    global _circuit_breaker
    if _circuit_breaker is None:
        _circuit_breaker = AutomationCircuitBreaker()
    return _circuit_breaker
