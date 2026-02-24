"""ntfy push notification service for CachiBot.

Dispatches notifications to a self-hosted ntfy server when the mobile
client's WebSocket connection is not available. The mobile app subscribes
to its user-specific topic via SSE and shows local notifications.

Configuration (cachibot.toml):
    [ntfy]
    server_url = "https://ntfy.example.com"
    # Topic prefix — actual topic is "{prefix}-{user_id}"
    topic_prefix = "cachibot"
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class NtfyService:
    """HTTP client for pushing notifications to an ntfy server."""

    def __init__(self, server_url: str, topic_prefix: str = "cachibot") -> None:
        self.server_url = server_url.rstrip("/")
        self.topic_prefix = topic_prefix
        self._client = httpx.AsyncClient(timeout=10)

    def _topic(self, user_id: str) -> str:
        return f"{self.topic_prefix}-{user_id}"

    async def send(
        self,
        user_id: str,
        message: str,
        *,
        title: str = "CachiBot",
        tags: list[str] | None = None,
        priority: int = 3,
        click_url: str | None = None,
        extras: dict[str, Any] | None = None,
    ) -> bool:
        """Push a notification to the user's ntfy topic.

        Args:
            user_id: Target user ID (determines the topic).
            message: Notification body text.
            title: Notification title.
            tags: ntfy tags (used for emoji and routing on mobile).
            priority: 1 (min) to 5 (max), default 3 (normal).
            click_url: URL to open when the notification is tapped.
            extras: Additional JSON data attached to the message.

        Returns:
            True if the notification was delivered, False otherwise.
        """
        topic = self._topic(user_id)
        url = f"{self.server_url}/{topic}"

        headers: dict[str, str] = {
            "Title": title,
            "Priority": str(priority),
        }
        if tags:
            headers["Tags"] = ",".join(tags)
        if click_url:
            headers["Click"] = click_url

        try:
            response = await self._client.post(
                url,
                content=message,
                headers=headers,
            )
            if response.status_code in (200, 202):
                logger.debug("ntfy sent to %s: %s", topic, title)
                return True

            logger.warning(
                "ntfy returned %d for topic %s: %s",
                response.status_code,
                topic,
                response.text[:200],
            )
            return False

        except httpx.HTTPError as exc:
            logger.error("ntfy send failed for %s: %s", topic, exc)
            return False

    # ---- Convenience methods ----

    async def send_message(
        self,
        user_id: str,
        bot_name: str,
        content: str,
        *,
        chat_route: str | None = None,
    ) -> bool:
        """Notify about a new bot message."""
        return await self.send(
            user_id,
            content[:200] if len(content) > 200 else content,
            title=bot_name,
            tags=["message", "speech_balloon"],
            click_url=chat_route,
        )

    async def send_approval_request(
        self,
        user_id: str,
        tool_name: str,
        risk_level: str = "medium",
    ) -> bool:
        """Notify about a pending approval request."""
        return await self.send(
            user_id,
            f"Bot wants to use: {tool_name} (risk: {risk_level})",
            title="Approval Required",
            tags=["approval", "warning"],
            priority=4,
        )

    async def send_work_update(
        self,
        user_id: str,
        work_title: str,
        status: str,
    ) -> bool:
        """Notify about a work/job status change."""
        return await self.send(
            user_id,
            f"{work_title}: {status}",
            title="Work Update",
            tags=["work", "hammer"],
        )

    async def send_reminder(
        self,
        user_id: str,
        title: str,
        body: str,
    ) -> bool:
        """Send a scheduled reminder notification."""
        return await self.send(
            user_id,
            body,
            title=title,
            tags=["reminder", "bell"],
            priority=4,
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
