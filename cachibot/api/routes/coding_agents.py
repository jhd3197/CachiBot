"""Coding agent discovery endpoint."""

import shutil

from fastapi import APIRouter, Request

from cachibot.config import Config
from cachibot.models.coding_agents import CodingAgentInfo, CodingAgentsResponse
from cachibot.plugins.coding_agent import CodingCLI

router = APIRouter()

_CLI_DISPLAY_NAMES: dict[CodingCLI, str] = {
    CodingCLI.CLAUDE: "Claude Code",
    CodingCLI.CODEX: "Codex CLI",
    CodingCLI.GEMINI: "Gemini CLI",
}


@router.get("/coding-agents", response_model=CodingAgentsResponse)
async def get_coding_agents(request: Request) -> CodingAgentsResponse:
    """Return which coding agent CLIs are installed and available."""
    workspace = getattr(request.app.state, "workspace", None)
    config = Config.load(workspace=workspace)
    ca = config.coding_agents

    path_map = {
        CodingCLI.CLAUDE: ca.claude_path,
        CodingCLI.CODEX: ca.codex_path,
        CodingCLI.GEMINI: ca.gemini_path,
    }

    agents: list[CodingAgentInfo] = []
    for cli in CodingCLI:
        custom_path = path_map.get(cli, "")
        binary = custom_path or cli.value
        available = shutil.which(binary) is not None

        agents.append(
            CodingAgentInfo(
                id=cli.value,
                name=_CLI_DISPLAY_NAMES.get(cli, cli.value),
                available=available,
                binary=shutil.which(binary) or binary,
                custom_path=bool(custom_path),
            )
        )

    return CodingAgentsResponse(agents=agents, default_agent=ca.default_agent)
