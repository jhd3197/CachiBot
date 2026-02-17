"""Send telemetry to Matomo via HTTP Tracking API.

All network calls are wrapped in try/except — telemetry must NEVER
break the application. Failures are logged at DEBUG and silently ignored.
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


async def send_telemetry(payload: dict) -> bool:
    """Format and send telemetry payload to Matomo.

    Uses Matomo's HTTP Tracking API with bulk tracking format.
    Returns True if sent successfully, False otherwise.
    Always silent on failure — never raises.
    """
    try:
        from cachibot.config import Config

        config = Config.load()

        # Respect env var override
        if os.getenv("CACHIBOT_TELEMETRY_DISABLED", "").lower() in ("1", "true", "yes"):
            logger.debug("Telemetry disabled via environment variable")
            return False

        if not config.telemetry.enabled:
            logger.debug("Telemetry not enabled")
            return False

        # Ensure we have an install ID
        if not config.telemetry.install_id:
            config.telemetry.install_id = uuid.uuid4().hex
            config.save_telemetry_config()

        install_id = config.telemetry.install_id
        matomo_url = config.telemetry.matomo_url
        site_id = config.telemetry.matomo_site_id

        # Build Matomo tracking request parameters
        # Use first 16 hex chars of install_id as visitor ID
        visitor_id = install_id[:16]

        params = {
            "idsite": site_id,
            "rec": "1",
            "send_image": "0",
            "_id": visitor_id,
            "cip": "0.0.0.0",  # Anonymize IP completely
            "url": "app://cachibot/telemetry",
            "action_name": "Telemetry Report",
            # Custom dimensions for app metadata
            "dimension1": payload.get("os_type", ""),
            "dimension2": payload.get("python_version", ""),
            "dimension3": payload.get("app_version", ""),
            "dimension4": payload.get("db_type", ""),
            # Custom variables for aggregate counts
            "cvar": _build_custom_vars(payload),
        }

        url = f"{matomo_url}?{urlencode(params)}"

        import httpx

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()

        # Update last_sent timestamp
        config.telemetry.last_sent = datetime.now(timezone.utc).isoformat()
        config.save_telemetry_config()

        logger.debug("Telemetry sent successfully")
        return True

    except Exception as exc:
        logger.debug("Telemetry send failed (silent): %s", exc)
        return False


def _build_custom_vars(payload: dict) -> str:
    """Build Matomo custom variables JSON string from payload counts."""
    import json

    cvars = {}
    slot = 1
    for key in ("bot_count", "message_count", "user_count", "active_connections", "uptime_seconds"):
        if key in payload:
            cvars[str(slot)] = [key, str(payload[key])]
            slot += 1
            if slot > 5:
                break  # Matomo supports max 5 custom variables

    return json.dumps(cvars) if cvars else "{}"
