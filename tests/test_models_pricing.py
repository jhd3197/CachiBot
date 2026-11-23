"""Regression tests for model pricing on the /models route.

The route used to import ``get_model_rates`` from ``prompture.model_rates``,
which no longer exists in prompture 1.19, so pricing was silently never
attached to the response. These tests pin the import to
``prompture.infra.model_rates`` and verify the route attaches pricing.
No network and no database: discovery and rates are monkeypatched, and the
public-id mapping helper is replaced with an empty mapping.
"""

from datetime import datetime, timezone

import prompture.infra
import prompture.infra.model_rates
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from cachibot.api.auth import get_current_user
from cachibot.api.routes import models as models_routes
from cachibot.models.auth import User, UserRole

_ENRICHED = [
    {
        "provider": "openai",
        "model_id": "gpt-4o",
        "capabilities": {
            "context_window": 128000,
            "supports_tool_use": True,
            "modalities_input": ["text"],
            "modalities_output": ["text"],
        },
    },
    {
        "provider": "acme",
        "model_id": "unpriced-model",
        "capabilities": {},
    },
]

_FAKE_RATES = {"input": 2.5, "output": 10.0, "cache_read": 1.25}


def _fake_rates(provider: str, model_id: str):
    return _FAKE_RATES if model_id == "gpt-4o" else None


def _user() -> User:
    return User(
        id="user-1",
        email="tester@example.com",
        username="tester",
        role=UserRole.USER,
        created_at=datetime.now(timezone.utc),
    )


def test_get_model_rates_import_resolves_offline():
    """The rates helper must import from its current location and work offline."""
    from prompture.infra.model_rates import get_model_rates

    rates = get_model_rates("openai", "gpt-4o")
    assert rates is not None
    assert {"input", "output"} <= set(rates)
    assert rates["input"] > 0
    assert rates["output"] > 0
    assert get_model_rates("openai", "no-such-model-anywhere") is None


def test_models_route_rates_import_resolves():
    """The route's rates helper must resolve at its current location."""
    import importlib

    module = importlib.import_module("prompture.infra.model_rates")
    assert callable(module.get_model_rates)


@pytest.fixture
async def client(monkeypatch):
    app = FastAPI()
    app.include_router(models_routes.router, prefix="/api")

    monkeypatch.setattr(
        prompture.infra, "get_available_models", lambda include_capabilities=False: _ENRICHED
    )
    monkeypatch.setattr(prompture.infra, "get_available_image_gen_models", lambda: [])
    monkeypatch.setattr(prompture.infra, "get_available_audio_models", lambda: [])
    monkeypatch.setattr(prompture.infra, "get_available_embedding_models", lambda: [])
    monkeypatch.setattr(prompture.infra.model_rates, "get_model_rates", _fake_rates)

    async def _no_public_ids() -> dict[str, str]:
        return {}

    monkeypatch.setattr(models_routes, "_load_public_id_map", _no_public_ids)

    app.dependency_overrides[get_current_user] = _user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_models_route_includes_pricing(client):
    response = await client.get("/api/models")
    assert response.status_code == 200

    groups = response.json()["groups"]
    by_id = {m["id"]: m for models in groups.values() for m in models}

    priced = by_id["openai/gpt-4o"]
    assert priced["pricing"] == {"input": 2.5, "output": 10.0}

    unpriced = by_id["acme/unpriced-model"]
    assert unpriced["pricing"] is None
