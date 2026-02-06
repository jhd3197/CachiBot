"""Configuration-related Pydantic models."""

from pydantic import BaseModel, Field


class AgentConfigResponse(BaseModel):
    """Agent configuration response."""

    model: str = Field(description="LLM model identifier")
    max_iterations: int = Field(description="Maximum agent iterations")
    approve_actions: bool = Field(description="Require approval for actions")
    temperature: float = Field(description="Model temperature")


class SandboxConfigResponse(BaseModel):
    """Sandbox configuration response."""

    allowed_imports: list[str] = Field(description="Allowed Python imports")
    timeout_seconds: int = Field(description="Execution timeout")
    max_output_length: int = Field(description="Max output length")


class DisplayConfigResponse(BaseModel):
    """Display configuration response."""

    show_thinking: bool = Field(description="Show thinking process")
    show_cost: bool = Field(description="Show cost information")
    style: str = Field(description="Display style (detailed/compact)")


class ConfigResponse(BaseModel):
    """Full configuration response."""

    agent: AgentConfigResponse
    sandbox: SandboxConfigResponse
    display: DisplayConfigResponse
    workspace_path: str = Field(description="Current workspace path")


class ConfigUpdate(BaseModel):
    """Configuration update request."""

    model: str | None = Field(default=None, description="LLM model to use")
    max_iterations: int | None = Field(default=None, ge=1, le=100)
    approve_actions: bool | None = Field(default=None)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    show_thinking: bool | None = Field(default=None)
    show_cost: bool | None = Field(default=None)
