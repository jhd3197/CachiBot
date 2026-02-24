"""Coding agent discovery models."""

from pydantic import BaseModel


class CodingAgentInfo(BaseModel):
    """Info about a single coding agent CLI."""

    id: str
    name: str
    available: bool
    binary: str
    custom_path: bool


class CodingAgentsResponse(BaseModel):
    """Response from the coding agents discovery endpoint."""

    agents: list[CodingAgentInfo]
    default_agent: str
