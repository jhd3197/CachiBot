"""Bot name generation service using Prompture."""

import logging

from prompture import extract_with_model
from pydantic import BaseModel, Field

from cachibot.config import Config

logger = logging.getLogger(__name__)

# Default model for name generation - use a reliable model for structured output
DEFAULT_MODEL = "anthropic/claude-3-5-haiku-20241022"

# Fallback names if generation fails (2 human names + 2 creative)
FALLBACK_NAMES = [
    ("Carlos", "Spanish origin meaning 'free man' - a warm, approachable companion"),
    ("Sophie", "Greek origin meaning 'wisdom' - knowledgeable and thoughtful"),
    ("Nova", "Latin for 'new' - a bright star that appears suddenly in the sky"),
    ("Sage", "A wise person; also an herb used for purification and healing"),
]


class NameWithMeaning(BaseModel):
    """A bot name with its meaning."""

    name: str = Field(description="The bot name (1-2 words)")
    meaning: str = Field(description="The meaning or origin of this name, explaining why it's suitable for an AI assistant")


class BotNameSuggestions(BaseModel):
    """Structured output for bot name suggestions."""

    names: list[str] = Field(
        description="A list of creative, memorable bot names. Each should be 1-2 words, catchy, and suitable for an AI assistant."
    )


class BotNamesWithMeanings(BaseModel):
    """Structured output for bot name suggestions with meanings."""

    names: list[NameWithMeaning] = Field(
        description="A list of creative bot names with their meanings and significance"
    )


async def generate_bot_names(
    count: int = 4,
    exclude: list[str] | None = None,
    model: str | None = None,
) -> list[str]:
    """
    Generate creative bot name suggestions using AI.

    Args:
        count: Number of names to generate (default 4)
        exclude: List of names to avoid (existing bot names)
        model: Model to use for generation (default from config)

    Returns:
        List of creative bot name suggestions
    """
    if model is None:
        try:
            config = Config.load()
            model = config.agent.model
        except Exception:
            model = DEFAULT_MODEL

    exclude_set = set(name.lower() for name in (exclude or []))

    exclude_clause = ""
    if exclude:
        exclude_clause = f"\n\nDO NOT use these names (already taken): {', '.join(exclude)}"

    human_count = count // 2
    creative_count = count - human_count

    prompt_text = f"""Generate {count} names for a personal AI assistant.

Requirements:
- {human_count} should be REAL HUMAN FIRST NAMES (like Carlos, Emma, James, Sofia)
- {creative_count} should be CREATIVE but not generic tech names
- Avoid overused AI names like Nova, Echo, Pixel, Vector, Atlas, Iris
- Names should feel warm and approachable
{exclude_clause}

Good examples: Carlos, Sophie, Max, Aria, Chef, Scout, Sage, Coach"""

    instruction = (
        f"Generate exactly {count} names "
        f"({human_count} human + {creative_count} creative). Names only, no explanations:"
    )

    fallback_names = [n for n, _ in FALLBACK_NAMES if n.lower() not in exclude_set][:count]

    result = extract_with_model(
        BotNameSuggestions,
        prompt_text,
        model,
        instruction_template=instruction,
        max_retries=3,
        fallback=BotNameSuggestions(names=fallback_names),
    )
    return result.model.names[:count]


async def generate_bot_names_with_meanings(
    count: int = 4,
    exclude: list[str] | None = None,
    purpose: str | None = None,
    personality: str | None = None,
    model: str | None = None,
) -> list[NameWithMeaning]:
    """
    Generate creative bot name suggestions with meanings using AI.

    Args:
        count: Number of names to generate (default 4)
        exclude: List of names to avoid (existing bot names)
        purpose: Optional purpose/category of the bot for context
        personality: Optional personality style for context
        model: Model to use for generation (default from config)

    Returns:
        List of creative bot names with their meanings
    """
    if model is None:
        try:
            config = Config.load()
            model = config.agent.model
        except Exception:
            model = DEFAULT_MODEL

    exclude_set = set(name.lower() for name in (exclude or []))

    exclude_clause = ""
    if exclude:
        exclude_clause = f"\n\nDO NOT use these names (already taken): {', '.join(exclude)}"

    context_clause = ""
    if purpose:
        context_clause = f"\n\n## What this bot does:\n{purpose}\n"
    if personality:
        context_clause += f"\n## Personality style: {personality}\n"

    human_count = count // 2
    creative_count = count - human_count

    prompt_text = f"""Generate {count} names for a personal AI assistant, each with a brief explanation.
{context_clause}
## IMPORTANT - Name Types Required:
1. Generate {human_count} REAL HUMAN FIRST NAMES (like Carlos, Emma, James, Sofia, Marcus, Lucia)
   - Choose names that feel warm and approachable
   - Pick names from different cultures that match the bot's purpose
   - These should be actual names people have, not made-up words

2. Generate {creative_count} CREATIVE NAMES related to what the bot does
   - These should relate to the bot's purpose (e.g., a cooking bot could be "Chef", "Basil", "Saffron")
   - Avoid generic tech names like "Nova", "Echo", "Pixel", "Vector", "Atlas"
   - Think of words related to the domain: tools, concepts, or playful references
{exclude_clause}

## Examples by purpose:
- Cooking bot: "Carlos" (friendly chef), "Miso" (Japanese ingredient), "Julia" (like Julia Child)
- Fitness bot: "Marcus" (strong Roman name), "Coach", "Rocky"
- Coding bot: "Ada" (Ada Lovelace), "Linus" (Linus Torvalds), "Bug" (playful)
- Writing bot: "Ernest" (Hemingway), "Quill", "Maya" (Angelou)

Keep meanings SHORT (1 sentence max). Focus on why the name fits THIS specific bot."""

    instruction = (
        f"Generate exactly {count} names "
        f"({human_count} real human names + {creative_count} creative/domain names). "
        "Keep meanings brief:"
    )

    fallback_names = [
        NameWithMeaning(name=name, meaning=meaning)
        for name, meaning in FALLBACK_NAMES
        if name.lower() not in exclude_set
    ][:count]

    result = extract_with_model(
        BotNamesWithMeanings,
        prompt_text,
        model,
        instruction_template=instruction,
        max_retries=3,
        fallback=BotNamesWithMeanings(names=fallback_names),
    )
    return result.model.names[:count]
