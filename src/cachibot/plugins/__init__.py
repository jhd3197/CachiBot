"""
CachiBot Plugin System

All available plugins and their capability mappings.
Includes both CachiBot custom plugins and Tukuy's built-in plugins.
"""

from tukuy.plugins.base import TransformerPlugin
from tukuy.plugins.compression import CompressionPlugin
from tukuy.plugins.git import GitPlugin
from tukuy.plugins.http import HttpPlugin
from tukuy.plugins.shell import ShellPlugin
from tukuy.plugins.sql import SqlPlugin
from tukuy.plugins.web import WebPlugin

from cachibot.plugins.base import CachibotPlugin, PluginContext
from cachibot.plugins.file_ops import FileOpsPlugin
from cachibot.plugins.platform import PlatformPlugin
from cachibot.plugins.python_sandbox import PythonSandboxPlugin
from cachibot.plugins.task import TaskPlugin
from cachibot.plugins.work_management import WorkManagementPlugin

# All plugins keyed by name (CachiBot custom + Tukuy built-in)
CACHIBOT_PLUGINS: dict[str, type[CachibotPlugin] | type[TransformerPlugin]] = {
    # CachiBot custom plugins
    "task": TaskPlugin,
    "file_ops": FileOpsPlugin,
    "python_sandbox": PythonSandboxPlugin,
    "platform": PlatformPlugin,
    "work_management": WorkManagementPlugin,
    # Tukuy built-in plugins (scoped via SecurityContext)
    "git": GitPlugin,
    "shell": ShellPlugin,
    "web": WebPlugin,
    "http": HttpPlugin,
    "sql": SqlPlugin,
    "compression": CompressionPlugin,
}

__all__ = [
    "CachibotPlugin",
    "PluginContext",
    "CACHIBOT_PLUGINS",
    "TaskPlugin",
    "FileOpsPlugin",
    "PythonSandboxPlugin",
    "PlatformPlugin",
    "WorkManagementPlugin",
    "GitPlugin",
    "ShellPlugin",
    "WebPlugin",
    "HttpPlugin",
    "SqlPlugin",
    "CompressionPlugin",
]
