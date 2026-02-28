"""
Developer API Routes

API key management and webhook CRUD for per-bot developer access.
"""

import hashlib
import json
import secrets
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from cachibot.api.auth import require_bot_access_level
from cachibot.api.helpers import require_found
from cachibot.models.auth import User
from cachibot.models.group import BotAccessLevel
from cachibot.storage.developer_repository import ApiKeyRepository, WebhookRepository
from cachibot.storage.models.developer import BotWebhook

router = APIRouter(prefix="/api/bots/{bot_id}/developer", tags=["developer"])

key_repo = ApiKeyRepository()
wh_repo = WebhookRepository()


# =============================================================================
# Request / Response Models
# =============================================================================


class CreateApiKeyRequest(BaseModel):
    name: str
    expires_in_days: int | None = None


class ApiKeyResponse(BaseModel):
    id: str
    bot_id: str
    name: str
    key_prefix: str
    created_at: str
    last_used_at: str | None
    usage_count: int
    expires_at: str | None
    is_revoked: bool


class ApiKeyCreatedResponse(ApiKeyResponse):
    """Returned only at creation time — includes the full key."""

    key: str


class CreateWebhookRequest(BaseModel):
    name: str
    url: str
    events: list[str] = []
    secret: str | None = None


class UpdateWebhookRequest(BaseModel):
    name: str | None = None
    url: str | None = None
    events: list[str] | None = None
    secret: str | None = None
    is_active: bool | None = None


class WebhookResponse(BaseModel):
    id: str
    bot_id: str
    name: str
    url: str
    events: list[str]
    is_active: bool
    last_triggered_at: str | None
    failure_count: int
    created_at: str
    updated_at: str | None


# =============================================================================
# API Key Endpoints
# =============================================================================


@router.post(
    "/api-keys",
    response_model=ApiKeyCreatedResponse,
    dependencies=[Depends(require_bot_access_level(BotAccessLevel.EDITOR))],
)
async def create_api_key(
    bot_id: str,
    body: CreateApiKeyRequest,
    user: User = Depends(require_bot_access_level(BotAccessLevel.EDITOR)),
) -> ApiKeyCreatedResponse:
    """Create a new API key for this bot. The full key is returned only once."""
    from datetime import datetime, timedelta, timezone

    raw_key = "cb-" + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    expires_at = None
    if body.expires_in_days:
        expires_at = now + timedelta(days=body.expires_in_days)

    await key_repo.create_key(
        id=key_id,
        bot_id=bot_id,
        name=body.name,
        key_prefix=raw_key[:12],
        key_hash=key_hash,
        created_by=user.id,
        expires_at=expires_at,
    )

    return ApiKeyCreatedResponse(
        id=key_id,
        bot_id=bot_id,
        name=body.name,
        key_prefix=raw_key[:12],
        key=raw_key,
        created_at=now.isoformat(),
        last_used_at=None,
        usage_count=0,
        expires_at=expires_at.isoformat() if expires_at else None,
        is_revoked=False,
    )


@router.get(
    "/api-keys",
    response_model=list[ApiKeyResponse],
    dependencies=[Depends(require_bot_access_level(BotAccessLevel.EDITOR))],
)
async def list_api_keys(bot_id: str) -> list[ApiKeyResponse]:
    """List all API keys for this bot (prefix only, no secrets)."""
    keys = await key_repo.get_keys_for_bot(bot_id)
    return [
        ApiKeyResponse(
            id=k.id,
            bot_id=k.bot_id,
            name=k.name,
            key_prefix=k.key_prefix,
            created_at=k.created_at.isoformat() if k.created_at else "",
            last_used_at=k.last_used_at.isoformat() if k.last_used_at else None,
            usage_count=k.usage_count,
            expires_at=k.expires_at.isoformat() if k.expires_at else None,
            is_revoked=k.is_revoked,
        )
        for k in keys
    ]


@router.delete(
    "/api-keys/{key_id}",
    dependencies=[Depends(require_bot_access_level(BotAccessLevel.EDITOR))],
)
async def revoke_api_key(bot_id: str, key_id: str) -> dict[str, str]:
    """Revoke an API key."""
    require_found(await key_repo.revoke_key(key_id), "API key")
    return {"status": "revoked"}


# =============================================================================
# Webhook Endpoints
# =============================================================================


@router.post(
    "/webhooks",
    response_model=WebhookResponse,
    dependencies=[Depends(require_bot_access_level(BotAccessLevel.EDITOR))],
)
async def create_webhook(
    bot_id: str,
    body: CreateWebhookRequest,
    user: User = Depends(require_bot_access_level(BotAccessLevel.EDITOR)),
) -> WebhookResponse:
    """Create a new outbound webhook."""
    from datetime import datetime, timezone

    wh_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    await wh_repo.create_webhook(
        id=wh_id,
        bot_id=bot_id,
        name=body.name,
        url=body.url,
        secret=body.secret,
        events=body.events,
        created_by=user.id,
    )

    return WebhookResponse(
        id=wh_id,
        bot_id=bot_id,
        name=body.name,
        url=body.url,
        events=body.events,
        is_active=True,
        last_triggered_at=None,
        failure_count=0,
        created_at=now.isoformat(),
        updated_at=None,
    )


@router.get(
    "/webhooks",
    response_model=list[WebhookResponse],
    dependencies=[Depends(require_bot_access_level(BotAccessLevel.EDITOR))],
)
async def list_webhooks(bot_id: str) -> list[WebhookResponse]:
    """List all webhooks for this bot."""
    webhooks = await wh_repo.get_webhooks_for_bot(bot_id)
    return [_webhook_to_response(wh) for wh in webhooks]


@router.put(
    "/webhooks/{webhook_id}",
    response_model=WebhookResponse,
    dependencies=[Depends(require_bot_access_level(BotAccessLevel.EDITOR))],
)
async def update_webhook(
    bot_id: str,
    webhook_id: str,
    body: UpdateWebhookRequest,
) -> WebhookResponse:
    """Update a webhook."""
    require_found(
        await wh_repo.update_webhook(
            webhook_id,
            name=body.name,
            url=body.url,
            secret=body.secret,
            events=body.events,
            is_active=body.is_active,
        ),
        "Webhook",
    )

    wh = require_found(await wh_repo.get_webhook(webhook_id), "Webhook")
    return _webhook_to_response(wh)


@router.delete(
    "/webhooks/{webhook_id}",
    dependencies=[Depends(require_bot_access_level(BotAccessLevel.EDITOR))],
)
async def delete_webhook(bot_id: str, webhook_id: str) -> dict[str, str]:
    """Delete a webhook."""
    require_found(await wh_repo.delete_webhook(webhook_id), "Webhook")
    return {"status": "deleted"}


@router.post(
    "/webhooks/{webhook_id}/test",
    dependencies=[Depends(require_bot_access_level(BotAccessLevel.EDITOR))],
)
async def test_webhook(bot_id: str, webhook_id: str) -> dict[str, object]:
    """Send a test payload to a webhook and return the response status."""
    wh = require_found(await wh_repo.get_webhook(webhook_id), "Webhook")

    test_payload = {
        "event": "test",
        "bot_id": bot_id,
        "data": {"message": "This is a test webhook delivery from CachiBot."},
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if wh.secret:
                import hmac as _hmac

                sig = _hmac.new(
                    wh.secret.encode(), json.dumps(test_payload).encode(), hashlib.sha256
                ).hexdigest()
                headers["X-CachiBot-Signature"] = sig

            resp = await client.post(wh.url, json=test_payload, headers=headers)
            return {"status": "delivered", "response_status": resp.status_code}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}


# =============================================================================
# Helpers
# =============================================================================


def _webhook_to_response(wh: BotWebhook) -> WebhookResponse:
    """Convert a BotWebhook ORM object to a WebhookResponse."""
    try:
        events = json.loads(wh.events) if wh.events else []
    except (json.JSONDecodeError, TypeError):
        events = []

    return WebhookResponse(
        id=wh.id,
        bot_id=wh.bot_id,
        name=wh.name,
        url=wh.url,
        events=events,
        is_active=wh.is_active,
        last_triggered_at=wh.last_triggered_at.isoformat() if wh.last_triggered_at else None,
        failure_count=wh.failure_count,
        created_at=wh.created_at.isoformat() if wh.created_at else "",
        updated_at=wh.updated_at.isoformat() if wh.updated_at else None,
    )
