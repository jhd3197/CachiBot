"""Platform adapters for messaging integrations."""

from cachibot.services.adapters.base import BasePlatformAdapter
from cachibot.services.adapters.telegram import TelegramAdapter
from cachibot.services.adapters.discord import DiscordAdapter

__all__ = ["BasePlatformAdapter", "TelegramAdapter", "DiscordAdapter"]
