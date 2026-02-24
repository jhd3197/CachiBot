"""Mobile device pairing via one-time tokens."""

import logging
import os
import secrets
import socket
import subprocess
import sys
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from cachibot.api.auth import get_current_user
from cachibot.models.auth import LoginResponse, User, UserInDB
from cachibot.services.auth_service import get_auth_service
from cachibot.storage.user_repository import UserRepository

router = APIRouter(prefix="/auth")

# In-memory store for pairing tokens: token -> {user_id, created_at, used}
_pairing_tokens: dict[str, dict[str, Any]] = {}
_TOKEN_TTL = 60  # seconds
_CLEANUP_INTERVAL = 120  # seconds
_last_cleanup = 0.0

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def _cleanup_expired() -> None:
    """Remove expired pairing tokens."""
    global _last_cleanup
    now = time.monotonic()
    if now - _last_cleanup < _CLEANUP_INTERVAL:
        return
    _last_cleanup = now
    expired = [
        token
        for token, data in _pairing_tokens.items()
        if now - data["created_at"] > _TOKEN_TTL or data["used"]
    ]
    for token in expired:
        del _pairing_tokens[token]


def _get_lan_ips() -> list[str]:
    """Return all non-loopback IPv4 addresses on this machine."""
    ips: list[str] = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            addr = str(info[4][0])
            if addr not in _LOCAL_HOSTS:
                ips.append(addr)
    except OSError:
        pass
    # Fallback: UDP trick to find the primary LAN IP
    if not ips:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ips.append(s.getsockname()[0])
            s.close()
        except OSError:
            pass
    # Deduplicate while preserving order
    return list(dict.fromkeys(ips))


# ---- Request / Response models ----


class PairTokenResponse(BaseModel):
    """Response containing a one-time pairing token."""

    token: str
    url: str
    urls: list[str]
    expires: float


class RedeemTokenRequest(BaseModel):
    """Request to redeem a pairing token for auth tokens."""

    token: str


# ---- Endpoints ----


@router.post("/mobile-pair", response_model=PairTokenResponse)
async def create_pairing_token(
    request: Request,
    current_user: UserInDB = Depends(get_current_user),
) -> PairTokenResponse:
    """
    Generate a one-time pairing token for mobile device setup.

    The token is valid for 60 seconds and can be redeemed once
    to obtain access and refresh tokens.  Returns all LAN URLs
    so the mobile app can probe for reachability.
    """
    _cleanup_expired()

    token = secrets.token_urlsafe(32)
    now = time.monotonic()

    _pairing_tokens[token] = {
        "user_id": current_user.id,
        "created_at": now,
        "used": False,
    }

    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", ""))
    port = host.split(":")[1] if ":" in host else ""

    # Build a URL for every LAN interface
    lan_ips = _get_lan_ips()
    urls: list[str] = []
    for ip in lan_ips:
        urls.append(f"{scheme}://{ip}:{port}" if port else f"{scheme}://{ip}")

    # Primary URL: first LAN IP, or original host as fallback
    primary = urls[0] if urls else f"{scheme}://{host}"

    return PairTokenResponse(
        token=token,
        url=primary,
        urls=urls,
        expires=_TOKEN_TTL,
    )


@router.post("/mobile-pair/redeem", response_model=LoginResponse)
async def redeem_pairing_token(body: RedeemTokenRequest) -> LoginResponse:
    """
    Redeem a one-time pairing token for access and refresh tokens.

    The token must not be expired or already used.
    """
    _cleanup_expired()

    data = _pairing_tokens.get(body.token)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired pairing token",
        )

    now = time.monotonic()
    if now - data["created_at"] > _TOKEN_TTL:
        del _pairing_tokens[body.token]
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Pairing token has expired",
        )

    if data["used"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Pairing token has already been used",
        )

    # Mark as consumed
    data["used"] = True

    # Look up user and generate tokens
    repo = UserRepository()
    user = await repo.get_user_by_id(data["user_id"])

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is not available",
        )

    auth_service = get_auth_service()
    access_token = auth_service.create_access_token(user.id, user.role.value)
    refresh_token = auth_service.create_refresh_token(user.id)

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=User(
            id=user.id,
            email=user.email,
            username=user.username,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            created_by=user.created_by,
            last_login=user.last_login,
        ),
    )


# ---- Firewall helpers (Windows only) ----

_RULE_NAME_PREFIX = "CachiBot Server"
_log = logging.getLogger("cachibot.firewall")


def _firewall_rule_name() -> str:
    port = os.environ.get("_CACHIBOT_PORT", "5870")
    return f"{_RULE_NAME_PREFIX} (port {port})"


def _check_firewall_rule() -> bool | None:
    """Check if the firewall rule exists. Returns None on non-Windows."""
    if sys.platform != "win32":
        return None
    try:
        result = subprocess.run(
            ["netsh", "advfirewall", "firewall", "show", "rule", f"name={_firewall_rule_name()}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _create_firewall_rule() -> tuple[bool, str]:
    """Create the firewall rule via UAC elevation. Returns (success, message)."""
    port = os.environ.get("_CACHIBOT_PORT", "5870")
    name = _firewall_rule_name()
    netsh_args = (
        f"advfirewall firewall add rule "
        f'name="{name}" dir=in action=allow protocol=TCP localport={port}'
    )
    try:
        # Use PowerShell Start-Process -Verb RunAs to trigger a UAC prompt
        subprocess.run(
            [
                "powershell",
                "-Command",
                f"Start-Process netsh -ArgumentList '{netsh_args}' -Verb RunAs -Wait",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        # Verify the rule was actually created (UAC may have been denied)
        if _check_firewall_rule():
            _log.info("Firewall rule '%s' created for inbound TCP/%s", name, port)
            return True, f"Firewall rule created for port {port}"
        return False, "UAC prompt was declined or rule creation failed"
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)


class FirewallStatus(BaseModel):
    """Firewall rule status."""

    platform: str
    needed: bool
    enabled: bool | None
    port: str


class FirewallActionResult(BaseModel):
    """Result of firewall rule creation."""

    success: bool
    message: str


@router.get("/mobile-pair/firewall", response_model=FirewallStatus)
async def get_firewall_status(
    _current_user: UserInDB = Depends(get_current_user),
) -> FirewallStatus:
    """Check whether the Windows firewall rule for LAN access exists."""
    port = os.environ.get("_CACHIBOT_PORT", "5870")
    enabled = _check_firewall_rule()
    return FirewallStatus(
        platform=sys.platform,
        needed=sys.platform == "win32",
        enabled=enabled,
        port=port,
    )


@router.post("/mobile-pair/firewall", response_model=FirewallActionResult)
async def create_firewall_rule(
    _current_user: UserInDB = Depends(get_current_user),
) -> FirewallActionResult:
    """Create a Windows firewall rule to allow LAN connections."""
    if sys.platform != "win32":
        return FirewallActionResult(success=True, message="Not needed on this platform")

    existing = _check_firewall_rule()
    if existing:
        return FirewallActionResult(success=True, message="Firewall rule already exists")

    success, message = _create_firewall_rule()
    if not success:
        raise HTTPException(status_code=500, detail=message)
    return FirewallActionResult(success=True, message=message)
