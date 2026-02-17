"""Anonymous telemetry for CachiBot (opt-in, disabled by default)."""

from cachibot.telemetry.collector import collect_telemetry
from cachibot.telemetry.sender import send_telemetry

__all__ = ["collect_telemetry", "send_telemetry"]
