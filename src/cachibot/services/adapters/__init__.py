"""Platform adapters for messaging integrations."""

from cachibot.services.adapters.base import BasePlatformAdapter
from cachibot.services.adapters.discord import DiscordAdapter
from cachibot.services.adapters.telegram import TelegramAdapter

__all__ = ["BasePlatformAdapter", "TelegramAdapter", "DiscordAdapter"]
