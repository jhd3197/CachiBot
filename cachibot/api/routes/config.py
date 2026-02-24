"""Configuration endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request

from cachibot.api.auth import get_current_user
from cachibot.config import Config
from cachibot.models.auth import User
from cachibot.models.config import (
    AgentConfigResponse,
    ConfigResponse,
    ConfigUpdate,
    DisplayConfigResponse,
    KnowledgeConfigResponse,
    SandboxConfigResponse,
)

router = APIRouter()

# Runtime config storage (in-memory, reset on restart)
_runtime_config: Config | None = None


def get_config(request: Request) -> Config:
    """Get or create the current configuration."""
    global _runtime_config
    if _runtime_config is None:
        workspace = request.app.state.workspace
        _runtime_config = Config.load(workspace=workspace)
    return _runtime_config


@router.get("/config", response_model=ConfigResponse)
async def get_configuration(
    request: Request,
    user: User = Depends(get_current_user),
) -> ConfigResponse:
    """Get current configuration."""
    config = get_config(request)

    return ConfigResponse(
        agent=AgentConfigResponse(
            model=config.agent.model,
            max_iterations=config.agent.max_iterations,
            approve_actions=config.agent.approve_actions,
            temperature=config.agent.temperature,
        ),
        sandbox=SandboxConfigResponse(
            allowed_imports=config.sandbox.allowed_imports,
            timeout_seconds=config.sandbox.timeout_seconds,
            max_output_length=config.sandbox.max_output_length,
        ),
        display=DisplayConfigResponse(
            show_thinking=config.display.show_thinking,
            show_cost=config.display.show_cost,
            style=config.display.style,
        ),
        knowledge=KnowledgeConfigResponse(
            embedding_model=config.knowledge.embedding_model,
        ),
        workspace_path=str(config.workspace_path),
        timezone=config.timezone,
    )


@router.put("/config", response_model=ConfigResponse)
async def update_configuration(
    request: Request,
    update: ConfigUpdate,
    user: User = Depends(get_current_user),
) -> ConfigResponse:
    """Update configuration settings."""
    config = get_config(request)

    # Apply updates
    if update.model is not None:
        config.agent.model = update.model
    if update.max_iterations is not None:
        config.agent.max_iterations = update.max_iterations
    if update.approve_actions is not None:
        config.agent.approve_actions = update.approve_actions
    if update.temperature is not None:
        config.agent.temperature = update.temperature
    if update.show_thinking is not None:
        config.display.show_thinking = update.show_thinking
    if update.show_cost is not None:
        config.display.show_cost = update.show_cost
    if update.embedding_model is not None:
        config.knowledge.embedding_model = update.embedding_model
        # Reset vector store singleton so it picks up the new model
        import cachibot.services.vector_store as vs_module

        vs_module._vector_store = None
    if update.timezone is not None:
        from zoneinfo import ZoneInfo

        try:
            ZoneInfo(update.timezone)
        except (KeyError, Exception):
            raise HTTPException(status_code=400, detail=f"Invalid timezone: {update.timezone}")
        config.timezone = update.timezone

    return await get_configuration(request)
