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

from cachibot.plugins.audio_generation import AudioGenerationPlugin
from cachibot.plugins.base import CachibotPlugin, PluginContext
from cachibot.plugins.file_ops import FileOpsPlugin
from cachibot.plugins.image_generation import ImageGenerationPlugin
from cachibot.plugins.knowledge import KnowledgePlugin
from cachibot.plugins.notes import NotesPlugin
from cachibot.plugins.platform import PlatformPlugin
from cachibot.plugins.python_sandbox import PythonSandboxPlugin
from cachibot.plugins.task import TaskPlugin
from cachibot.plugins.work_management import WorkManagementPlugin

# All plugins keyed by name (CachiBot custom + Tukuy built-in)
CACHIBOT_PLUGINS: dict[str, type[CachibotPlugin] | type[TransformerPlugin]] = {
    # CachiBot custom plugins
    "task": TaskPlugin,
    "notes": NotesPlugin,
    "knowledge": KnowledgePlugin,
    "file_ops": FileOpsPlugin,
    "python_sandbox": PythonSandboxPlugin,
    "platform": PlatformPlugin,
    "work_management": WorkManagementPlugin,
    "image_generation": ImageGenerationPlugin,
    "audio_generation": AudioGenerationPlugin,
    # Tukuy built-in plugins (scoped via SecurityContext)
    "git": GitPlugin,
    "shell": ShellPlugin,
    "web": WebPlugin,
    "http": HttpPlugin,
    "sql": SqlPlugin,
    "compression": CompressionPlugin,
}

__all__ = [
    "AudioGenerationPlugin",
    "CachibotPlugin",
    "PluginContext",
    "CACHIBOT_PLUGINS",
    "KnowledgePlugin",
    "TaskPlugin",
    "NotesPlugin",
    "FileOpsPlugin",
    "PythonSandboxPlugin",
    "PlatformPlugin",
    "WorkManagementPlugin",
    "ImageGenerationPlugin",
    "GitPlugin",
    "ShellPlugin",
    "WebPlugin",
    "HttpPlugin",
    "SqlPlugin",
    "CompressionPlugin",
]
