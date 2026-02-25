"""Bot name generation service using Prompture."""

import logging
from typing import Any

from prompture.aio import extract_with_model
from pydantic import BaseModel, Field

from cachibot.services.model_resolver import resolve_utility_model

logger = logging.getLogger(__name__)

# Fallback names if generation fails (2 human names + 2 creative)
FALLBACK_NAMES = [
    ("Carlos", "Spanish origin meaning 'free man' - a warm, approachable companion"),
    ("Sophie", "Greek origin meaning 'wisdom' - knowledgeable and thoughtful"),
    ("Ember", "A glowing warmth that keeps the fire going - reliable and steady"),
    ("Sage", "A wise person; also an herb used for purification and healing"),
]


class NameWithMeaning(BaseModel):
    """A bot name with its meaning."""

    name: str = Field(description="The bot name (1-2 words)")
    meaning: str = Field(
        description=(
            "The meaning or origin of this name, explaining why it's suitable for an AI assistant"
        )
    )


class NamesResult(BaseModel):
    """Result of name generation — a list of names."""

    names: list[NameWithMeaning] = Field(description="List of bot name suggestions with meanings")


class SimpleNamesResult(BaseModel):
    """Result of simple name generation — a list of name strings."""

    names: list[str] = Field(description="List of bot name suggestions")


async def generate_bot_names(
    count: int = 4,
    exclude: list[str] | None = None,
    model: str | None = None,
    bot_models: dict[str, Any] | None = None,
    resolved_env: Any | None = None,
) -> list[str]:
    """Generate creative bot name suggestions using AI."""
    if model is None:
        model = resolve_utility_model(bot_models=bot_models, resolved_env=resolved_env)

    exclude_set = set(name.lower() for name in (exclude or []))

    exclude_clause = ""
    if exclude:
        exclude_clause = f"\nDO NOT use these names (already taken): {', '.join(exclude)}"

    human_count = count // 2
    creative_count = count - human_count

    prompt = f"""Generate {count} names for a personal AI assistant.

Requirements:
- {human_count} should be REAL HUMAN FIRST NAMES (like Carlos, Emma, James, Sofia)
- {creative_count} should be CREATIVE but not generic tech names
- Avoid overused AI names like Nova, Echo, Pixel, Vector, Atlas, Iris
- Names should feel warm and approachable
{exclude_clause}

Good examples: Carlos, Sophie, Max, Aria, Chef, Scout, Sage, Coach"""

    fallback_names = [n for n, _ in FALLBACK_NAMES if n.lower() not in exclude_set][:count]

    result = await extract_with_model(
        SimpleNamesResult,
        prompt,
        model,
        instruction_template="Generate bot names based on the requirements below:",
    )
    # result["model"] is the Pydantic SimpleNamesResult instance
    parsed: SimpleNamesResult = result["model"]
    if parsed.names:
        return parsed.names[:count]

    # LLM returned empty — use fallbacks as last resort
    if fallback_names:
        logger.warning("No names in LLM response, using fallback names")
        return fallback_names
    raise RuntimeError("Name generation returned no results and no fallbacks available")


async def generate_bot_names_with_meanings(
    count: int = 4,
    exclude: list[str] | None = None,
    purpose: str | None = None,
    personality: str | None = None,
    model: str | None = None,
    bot_models: dict[str, Any] | None = None,
    resolved_env: Any | None = None,
) -> list[NameWithMeaning]:
    """Generate creative bot name suggestions with meanings using AI."""
    if model is None:
        model = resolve_utility_model(bot_models=bot_models, resolved_env=resolved_env)

    exclude_set = set(name.lower() for name in (exclude or []))

    exclude_clause = ""
    if exclude:
        exclude_clause = f"\nDO NOT use these names (already taken): {', '.join(exclude)}"

    context_clause = ""
    if purpose:
        context_clause += f"\nWhat this bot does: {purpose}"
    if personality:
        context_clause += f"\nPersonality style: {personality}"

    human_count = count // 2
    creative_count = count - human_count

    prompt = f"""Generate {count} names for a personal AI assistant, each with a brief meaning.
{context_clause}

Name types required:
- {human_count} REAL HUMAN FIRST NAMES (warm, approachable, from different cultures)
- {creative_count} CREATIVE NAMES related to the bot's purpose
- Avoid generic tech names like Nova, Echo, Pixel, Vector, Atlas
{exclude_clause}

Examples by purpose:
- Cooking: "Carlos" (friendly chef), "Miso" (Japanese ingredient), "Julia" (Julia Child)
- Fitness: "Marcus" (strong Roman name), "Coach", "Rocky"
- Coding: "Ada" (Ada Lovelace), "Linus" (Torvalds), "Bug" (playful)"""

    fallback_names = [
        NameWithMeaning(name=name, meaning=meaning)
        for name, meaning in FALLBACK_NAMES
        if name.lower() not in exclude_set
    ][:count]

    result = await extract_with_model(
        NamesResult,
        prompt,
        model,
        instruction_template="Generate bot names with meanings based on the requirements below:",
    )
    # result["model"] is the Pydantic NamesResult instance
    parsed: NamesResult = result["model"]
    if parsed.names:
        return list(parsed.names[:count])

    # LLM returned empty — use fallbacks as last resort
    if fallback_names:
        logger.warning("No names parsed from LLM response, using fallback names")
        return fallback_names
    raise RuntimeError("Name generation returned no results and no fallbacks available")
