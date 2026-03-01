# CachiBot Plugin System

Build plugins that give your bots new capabilities -- tool skills, artifact renderers, and embedded views -- in minutes.

## Quick Start: Your First Plugin in 5 Minutes

### 1. Create the plugin directory

```
~/.cachibot/plugins/my_plugin/
    __init__.py
    my_plugin.py
    plugin.toml
```

### 2. Write the manifest

```toml
# plugin.toml
[plugin]
name = "my_plugin"
display_name = "My Plugin"
description = "Does something useful"
version = "0.1.0"
author = "You"
type = "tool"

[plugin.ui]
icon = "sparkles"
color = "#22c55e"
group = "Custom"

[plugin.scope]
contexts = ["chat", "room"]

[plugin.requires]
python = ">=3.10"
filesystem = false
network = false
imports = []

[plugin.permissions]
allow_env_vars = []
allow_paths = []
```

### 3. Write the plugin class

```python
# my_plugin.py
from __future__ import annotations

from tukuy.skills import Skill, skill
from cachibot.plugins.base import CachibotPlugin, PluginContext


class MyPlugin(CachibotPlugin):
    def __init__(self, ctx: PluginContext) -> None:
        super().__init__("my_plugin", ctx)
        self._skills_map = self._build_skills()

    @property
    def skills(self) -> dict[str, Skill]:
        return self._skills_map

    def _build_skills(self) -> dict[str, Skill]:
        @skill(
            name="greet",
            description="Say hello to someone.",
            category="general",
            tags=["greeting"],
        )
        async def greet(name: str = "World") -> str:
            """Generate a greeting.

            Args:
                name: Who to greet.
            """
            return f"Hello, {name}!"

        return {"greet": greet.__skill__}
```

### 4. Write the package init

```python
# __init__.py
from .my_plugin import MyPlugin

__all__ = ["MyPlugin"]
```

### 5. Restart CachiBot

The plugin loader scans `~/.cachibot/plugins/` on startup. Your plugin will appear in the Plugins panel and can be enabled per-bot.

## How It Works

1. **Discovery** -- On startup, CachiBot scans `~/.cachibot/plugins/` for directories containing a `plugin.toml`.
2. **Validation** -- The manifest is parsed and validated. Requirements (`imports`, `python` version) are checked.
3. **Loading** -- The Python module is imported. CachiBot finds the `CachibotPlugin` subclass automatically.
4. **Registration** -- The plugin's skills are injected into the bot's tool registry under the capability key `ext_<name>`.
5. **Execution** -- When the LLM calls a tool provided by your plugin, CachiBot invokes the corresponding skill function.

## Plugin Types

| Type   | Purpose                                 | Entry Point                |
|--------|-----------------------------------------|----------------------------|
| `tool` | Provides tool skills the LLM can call   | `skills` property          |
| `view` | Embeds an iframe view in the sidebar    | `static/index.html`        |

## Documentation Index

- **[Manifest Reference](manifest.md)** -- Complete `plugin.toml` specification
- **[Tool Skills](skills.md)** -- How to create tool skills with the `@skill()` decorator
- **[Artifacts](artifacts.md)** -- How to emit artifacts (code, HTML, diagrams) from skills
- **[Views](views.md)** -- How to build view-type plugins with embedded UIs
- **[Lifecycle Hooks](lifecycle.md)** -- Lifecycle hooks and the `PluginContext`
- **[Examples](examples.md)** -- Walkthrough of the reference plugins in `examples/plugins/`

## Installation Methods

### Manual (copy directory)

Copy your plugin folder to `~/.cachibot/plugins/<name>/` and restart CachiBot.

### Archive upload (via API or UI)

Upload a `.zip` or `.tar.gz` archive through the Plugins panel or via:

```
POST /api/plugins/install
Content-Type: multipart/form-data
```

The archive must contain a `plugin.toml` at the root or inside a single top-level directory.

### Hot reload

After adding or modifying plugins, reload without restarting:

```
POST /api/plugins/reload
```

Or use the Reload button in the Plugins panel.
