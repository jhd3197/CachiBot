"""Platform adapters for messaging integrations."""

# Import adapter modules so @register decorators execute
import cachibot.services.adapters.discord  # noqa: F401
import cachibot.services.adapters.line  # noqa: F401
import cachibot.services.adapters.slack  # noqa: F401
import cachibot.services.adapters.teams  # noqa: F401
import cachibot.services.adapters.telegram  # noqa: F401
import cachibot.services.adapters.viber  # noqa: F401
import cachibot.services.adapters.whatsapp  # noqa: F401
from cachibot.services.adapters.base import BasePlatformAdapter
from cachibot.services.adapters.registry import AdapterRegistry

__all__ = ["BasePlatformAdapter", "AdapterRegistry"]
