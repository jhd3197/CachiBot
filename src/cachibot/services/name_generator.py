"""Bot name generation service using Prompture."""

import json
import logging
import re
from typing import Any

import httpx
from prompture.aio import get_async_driver_for_model
from pydantic import BaseModel, Field

from cachibot.config import Config

logger = logging.getLogger(__name__)

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
    meaning: str = Field(
        description=(
            "The meaning or origin of this name, explaining why it's suitable for an AI assistant"
        )
    )


def _resolve_utility_model() -> str:
    """Resolve the model to use for utility tasks."""
    try:
        config = Config.load()
        return config.agent.utility_model or config.agent.model
    except Exception:
        return "moonshot/kimi-k2.5"


def _extract_json(text: str) -> dict[str, Any]:
    """Extract JSON object from model response text."""
    # Try the whole text first
    try:
        return json.loads(text.strip())  # type: ignore[no-any-return]
    except (json.JSONDecodeError, ValueError):
        pass

    # Try to find JSON in code blocks
    code_block = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if code_block:
        try:
            return json.loads(code_block.group(1).strip())  # type: ignore[no-any-return]
        except (json.JSONDecodeError, ValueError):
            pass

    # Try to find a JSON object with "names" key anywhere
    brace_match = re.search(r'\{[^{}]*"names"\s*:\s*\[.*?\]\s*\}', text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))  # type: ignore[no-any-return]
        except (json.JSONDecodeError, ValueError):
            pass

    # Last resort: find any JSON object
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))  # type: ignore[no-any-return]
        except (json.JSONDecodeError, ValueError):
            pass

    raise ValueError(f"Could not extract JSON from response: {text[:300]}")


async def _chat_completion(prompt: str, model_name: str) -> str:
    """Call the model's chat completion API directly, handling reasoning models properly."""
    driver = get_async_driver_for_model(model_name)

    # Get API credentials from the driver
    api_key = getattr(driver, "api_key", None)
    base_url = getattr(driver, "base_url", None) or getattr(driver, "api_base", None)

    if not api_key or not base_url:
        raise ValueError(f"Cannot get API credentials from driver for {model_name}")

    # Strip provider prefix from model name (e.g. "moonshot/kimi-k2.5" -> "kimi-k2.5")
    bare_model = model_name.split("/", 1)[-1] if "/" in model_name else model_name

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    data: dict[str, Any] = {
        "model": bare_model,
        "messages": [{"role": "user", "content": prompt}],
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json=data,
            timeout=120,
        )
        response.raise_for_status()
        resp = response.json()

    message = resp["choices"][0]["message"]
    content = message.get("content") or ""
    reasoning = message.get("reasoning_content") or ""

    # Prefer content, fall back to reasoning if content is empty
    if content.strip():
        return content
    if reasoning.strip():
        return reasoning

    raise ValueError("Model returned empty response (both content and reasoning_content empty)")


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
        model = _resolve_utility_model()

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

Good examples: Carlos, Sophie, Max, Aria, Chef, Scout, Sage, Coach

Respond with ONLY a JSON object in this exact format, no other text:
{{"names": ["Name1", "Name2", "Name3", "Name4"]}}"""

    fallback_names = [n for n, _ in FALLBACK_NAMES if n.lower() not in exclude_set][:count]

    try:
        response = await _chat_completion(prompt, model)
        data = _extract_json(response)
        names: list[str] = data.get("names", [])
        if names:
            return names[:count]
        logger.warning("No names in response, using fallbacks")
        return fallback_names
    except Exception:
        logger.exception("Name generation failed, using fallbacks")
        return fallback_names


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
        model = _resolve_utility_model()

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
- Coding: "Ada" (Ada Lovelace), "Linus" (Torvalds), "Bug" (playful)

Respond with ONLY a JSON object in this exact format, no other text:
{{"names": [{{"name": "ExampleName", "meaning": "Brief reason this name fits"}}, ...]}}"""

    fallback_names = [
        NameWithMeaning(name=name, meaning=meaning)
        for name, meaning in FALLBACK_NAMES
        if name.lower() not in exclude_set
    ][:count]

    try:
        response = await _chat_completion(prompt, model)
        data = _extract_json(response)
        raw_names = data.get("names", [])
        names = []
        for item in raw_names:
            if isinstance(item, dict) and "name" in item:
                names.append(
                    NameWithMeaning(
                        name=item["name"],
                        meaning=item.get("meaning", "A great name for your bot"),
                    )
                )
        if names:
            return names[:count]
        logger.warning("No names parsed from response, using fallbacks")
        return fallback_names
    except Exception:
        logger.exception("Name generation with meanings failed, using fallbacks")
        return fallback_names
