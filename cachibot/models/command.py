"""
Command System Models

Defines the data structures for the BotFather-like command system.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class FlowStepType(str, Enum):
    """Type of input expected for a flow step."""

    text = "text"
    choice = "choice"


@dataclass
class FlowStep:
    """A single step in a multi-step command flow."""

    prompt: str
    field: str
    type: FlowStepType = FlowStepType.text
    choices: list[str] | None = None
    optional: bool = False
    skip_keyword: str = "skip"


@dataclass
class CommandDef:
    """Definition of a command."""

    name: str
    description: str
    flow_steps: list[FlowStep] | None = None
    platform_only: bool = False  # If True, only works on platforms, not web
    web_only: bool = False  # If True, only works on web, not platforms


@dataclass
class FlowState:
    """State for an active multi-step command flow."""

    user_id: str
    chat_id: str
    command: str
    current_step: int = 0
    collected_data: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None

    def is_expired(self) -> bool:
        """Check if the flow has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at


@dataclass
class CommandResult:
    """Result of processing a command."""

    response: str
    is_flow_active: bool = False
    action: str | None = None  # e.g., "open_dialog:create_bot" for web UI
    data: dict[str, Any] | None = None  # Additional data for the action


# Built-in command definitions
COMMANDS: dict[str, CommandDef] = {
    "start": CommandDef(
        name="start",
        description="Welcome message and command hints",
    ),
    "new": CommandDef(
        name="new",
        description="Create a new bot",
        flow_steps=[
            FlowStep(
                prompt="Let's create a new bot! What would you like to name it?",
                field="name",
                type=FlowStepType.text,
            ),
            FlowStep(
                prompt="Great! Add a description for {name}? (or type 'skip')",
                field="description",
                type=FlowStepType.text,
                optional=True,
            ),
            FlowStep(
                prompt=(
                    "Choose a template:\n"
                    "1. General Assistant - Helpful all-purpose bot\n"
                    "2. Code Expert - Specialized in programming help\n"
                    "3. Data Analyst - Data analysis and insights\n"
                    "4. Content Writer - Creative writing assistant\n\n"
                    "Reply with a number (1-4):"
                ),
                field="template",
                type=FlowStepType.choice,
                choices=["General Assistant", "Code Expert", "Data Analyst", "Content Writer"],
            ),
        ],
    ),
    "list": CommandDef(
        name="list",
        description="List all your bots",
    ),
    "help": CommandDef(
        name="help",
        description="Show available commands",
    ),
    "settings": CommandDef(
        name="settings",
        description="Open settings",
        web_only=True,
    ),
    "cancel": CommandDef(
        name="cancel",
        description="Cancel the current operation",
    ),
}


# Bot templates with system prompts
BOT_TEMPLATES: dict[str, dict[str, str]] = {
    "General Assistant": {
        "description": "A helpful all-purpose assistant",
        "system_prompt": (
            "You are a helpful, friendly assistant. You provide clear, accurate, "
            "and concise answers. You're knowledgeable about a wide range of topics "
            "and always aim to be helpful while being honest about your limitations."
        ),
    },
    "Code Expert": {
        "description": "A programming specialist",
        "system_prompt": (
            "You are an expert programmer and software engineer. You help with coding "
            "questions, debugging, code reviews, and software architecture. You write "
            "clean, efficient code and explain your solutions clearly. You're familiar "
            "with multiple programming languages and best practices."
        ),
    },
    "Data Analyst": {
        "description": "A data analysis specialist",
        "system_prompt": (
            "You are a data analysis expert. You help interpret data, create visualizations, "
            "perform statistical analysis, and provide insights. You're skilled with data "
            "tools and can explain complex concepts in simple terms. You focus on actionable "
            "insights from data."
        ),
    },
    "Content Writer": {
        "description": "A creative writing assistant",
        "system_prompt": (
            "You are a creative writing assistant. You help with writing, editing, and "
            "brainstorming content. You can adapt your style to different formats - from "
            "professional documents to creative stories. You provide constructive feedback "
            "and help improve written work."
        ),
    },
}
