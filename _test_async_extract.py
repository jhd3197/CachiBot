"""Test the new name generator."""

import asyncio
import logging

from cachibot.services.name_generator import generate_bot_names_with_meanings

logging.basicConfig(level=logging.INFO)


async def main():
    try:
        names = await generate_bot_names_with_meanings(
            count=4,
            purpose="Cooking & Recipes: Help me cook healthy meals",
        )
        print("SUCCESS! Names:")
        for n in names:
            print(f"  {n.name}: {n.meaning}")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")


asyncio.run(main())
