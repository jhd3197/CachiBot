"""
CachiBot Plugin System

All available plugins and their capability mappings.
Includes both CachiBot custom plugins, Tukuy's built-in plugins,
and Tukuy instruction packs.
"""

from tukuy.plugins.base import TransformerPlugin
from tukuy.plugins.compression import CompressionPlugin
from tukuy.plugins.git import GitPlugin
from tukuy.plugins.http import HttpPlugin
from tukuy.plugins.instructions import (
    AnalysisInstructionPack,
    DeveloperInstructionPack,
    WritingInstructionPack,
)
from tukuy.plugins.shell import ShellPlugin
from tukuy.plugins.sql import SqlPlugin
from tukuy.plugins.web import WebPlugin

from cachibot.plugins.audio_generation import AudioGenerationPlugin
from cachibot.plugins.base import CachibotPlugin, PluginContext
from cachibot.plugins.file_ops import FileOpsPlugin
from cachibot.plugins.image_generation import ImageGenerationPlugin
from cachibot.plugins.instruction_management import InstructionManagementPlugin
from cachibot.plugins.job_tools import JobToolsPlugin
from cachibot.plugins.knowledge import KnowledgePlugin
from cachibot.plugins.notes import NotesPlugin
from cachibot.plugins.platform import PlatformPlugin
from cachibot.plugins.python_sandbox import PythonSandboxPlugin
from cachibot.plugins.task import TaskPlugin
from cachibot.plugins.work_management import WorkManagementPlugin

# All plugins keyed by name (CachiBot custom + Tukuy built-in + Instruction packs)
CACHIBOT_PLUGINS: dict[str, type[CachibotPlugin] | type[TransformerPlugin]] = {
    # CachiBot custom plugins
    "task": TaskPlugin,
    "notes": NotesPlugin,
    "knowledge": KnowledgePlugin,
    "file_ops": FileOpsPlugin,
    "python_sandbox": PythonSandboxPlugin,
    "platform": PlatformPlugin,
    "work_management": WorkManagementPlugin,
    "job_tools": JobToolsPlugin,
    "image_generation": ImageGenerationPlugin,
    "audio_generation": AudioGenerationPlugin,
    # Tukuy built-in plugins (scoped via SecurityContext)
    "git": GitPlugin,
    "shell": ShellPlugin,
    "web": WebPlugin,
    "http": HttpPlugin,
    "sql": SqlPlugin,
    "compression": CompressionPlugin,
    # Tukuy instruction packs (LLM-powered tools)
    "instructions_analysis": AnalysisInstructionPack,
    "instructions_writing": WritingInstructionPack,
    "instructions_developer": DeveloperInstructionPack,
    # Instruction management (CRUD for custom instructions)
    "instruction_management": InstructionManagementPlugin,
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
    "JobToolsPlugin",
    "GitPlugin",
    "ShellPlugin",
    "WebPlugin",
    "HttpPlugin",
    "SqlPlugin",
    "CompressionPlugin",
    "AnalysisInstructionPack",
    "WritingInstructionPack",
    "DeveloperInstructionPack",
    "InstructionManagementPlugin",
]
