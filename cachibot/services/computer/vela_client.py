"""Minimal async client for a Vela computer's controller endpoints.

C1 only needs ``GET /api/health`` (open) and ``GET /api/controller`` (bearer
token, reports the controller protocol version). The full driver API client
lands with C3.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import httpx


class VelaClientError(Exception):
    """The computer did not answer as a Vela controller."""


@runtime_checkable
class VelaComputerClient(Protocol):
    """What the ComputerService needs from a Vela client (fakes implement this)."""

    async def health(self) -> bool:
        """True when /api/health answers 200."""
        ...

    async def controller_info(self) -> dict[str, Any]:
        """GET /api/controller with the bearer token; raises on any failure."""
        ...


class VelaClient:
    """httpx-based client pointed at one container's loopback port."""

    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: float = 5.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout, transport=transport)
        self._token = token

    async def health(self) -> bool:
        """True when /api/health answers 200 (it is open — no token)."""
        try:
            response = await self._client.get("/api/health")
        except httpx.HTTPError:
            return False
        return response.status_code == 200

    async def controller_info(self) -> dict[str, Any]:
        """Return /api/controller's JSON, raising :class:`VelaClientError` otherwise."""
        try:
            response = await self._client.get(
                "/api/controller",
                headers={"Authorization": f"Bearer {self._token}"},
            )
        except httpx.HTTPError as exc:
            raise VelaClientError(f"controller check failed: {exc}") from exc
        if response.status_code in (401, 403):
            raise VelaClientError("controller rejected the token")
        if response.status_code != 200:
            raise VelaClientError(f"controller check returned HTTP {response.status_code}")
        try:
            data = response.json()
        except ValueError as exc:
            raise VelaClientError("controller returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise VelaClientError("controller returned an unexpected payload")
        return data

    async def aclose(self) -> None:
        """Close the underlying connection pool."""
        await self._client.aclose()
