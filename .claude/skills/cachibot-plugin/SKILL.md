---
name: cachibot-plugin
description: Create new CachiBot agent plugins (tools) following the project's capability-gated plugin architecture. Use this skill when adding a new tool, capability, or plugin to the CachiBot agent system — e.g., "add a translate tool", "create a web scraping plugin", "add a new capability".
metadata:
  author: cachibot
  version: "1.0"
---

# CachiBot Plugin Creation

Create new plugins that expose tools to the CachiBot agent. Plugins are capability-gated, meaning they're only loaded when a bot has the corresponding capability enabled.

## Architecture Overview

- **Base class**: `CachibotPlugin` extends Tukuy's `TransformerPlugin`
- **Context**: `PluginContext` carries config, sandbox, bot_id, tool_configs, bot_models
- **Skills**: Each plugin exposes tools via Tukuy's `@skill` decorator
- **Registry**: `PluginManager` bridges plugin skills to Prompture's `ToolRegistry`

## Step-by-Step Process

### 1. Create the Plugin File

Create `cachibot/plugins/<your_plugin>.py`:

```python
"""
<Description> plugin — <tool_name> tool.

<What it does and what external services it uses.>
"""

import logging

from tukuy.manifest import PluginManifest, PluginRequirements
from tukuy.skill import ConfigParam, RiskLevel, Skill, skill

from cachibot.plugins.base import CachibotPlugin, PluginContext

logger = logging.getLogger(__name__)


class YourPlugin(CachibotPlugin):
    """Provides the <tool_name> tool for <purpose>."""

    def __init__(self, ctx: PluginContext) -> None:
        super().__init__("<plugin_name>", ctx)
        self._skills_map = self._build_skills()

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="<plugin_name>",
            display_name="<Display Name>",
            icon="<lucide-icon-name>",
            group="<group>",  # e.g. "Creative", "Utility", "Integration"
            requires=PluginRequirements(network=True),  # set True if network needed
        )

    def _build_skills(self) -> dict[str, Skill]:
        ctx = self.ctx

        @skill(
            name="<tool_name>",
            description="<Clear description of what the tool does for the LLM>",
            category="<category>",
            tags=["<tag1>", "<tag2>"],
            side_effects=False,  # True if it modifies external state
            requires_network=True,  # True if it makes network calls
            display_name="<Display Name>",
            icon="<icon>",
            risk_level=RiskLevel.MODERATE,  # SAFE, MODERATE, DANGEROUS, CRITICAL
            config_params=[
                ConfigParam(
                    name="<param_name>",
                    display_name="<Param Display Name>",
                    description="<What this config does>",
                    type="<type>",  # "string", "number", "select", "boolean"
                    default=<default_value>,
                    # For select: options=["opt1", "opt2"]
                    # For number: min=0, max=100, step=1, unit="seconds"
                ),
            ],
        )
        async def your_tool(arg1: str, arg2: str = "") -> str:
            """Tool function docstring (shown in API docs).

            Args:
                arg1: Description of arg1.
                arg2: Description of arg2. Defaults to plugin config.

            Returns:
                Human-readable result string.
            """
            # Access per-tool config
            tool_cfg = ctx.tool_configs.get("<tool_name>", {})
            effective_arg2 = arg2 or tool_cfg.get("<param_name>", "<default>")

            # Access bot model slots (if tool uses a specific model)
            model = ""
            if ctx.bot_models:
                model = ctx.bot_models.get("<slot>", "")  # "image", "audio", etc.

            try:
                # Implementation here
                result = "..."
                return result
            except Exception as exc:
                logger.error("<tool_name> failed: %s", exc, exc_info=True)
                return f"Error: <tool_name> failed: {exc}"

        return {"<tool_name>": your_tool.__skill__}

    @property
    def skills(self) -> dict[str, Skill]:
        return self._skills_map
```

### 2. Export from `__init__.py`

Add to `cachibot/plugins/__init__.py`:

```python
from cachibot.plugins.your_plugin import YourPlugin

# Add to CACHIBOT_PLUGINS dict:
CACHIBOT_PLUGINS: dict[...] = {
    # ... existing entries ...
    "your_plugin": YourPlugin,
}

# Add to __all__:
__all__ = [
    # ... existing entries ...
    "YourPlugin",
]
```

### 3. Register in Plugin Manager

Edit `cachibot/services/plugin_manager.py`:

**Option A — Gate under a NEW capability:**

```python
from cachibot.plugins import YourPlugin

CAPABILITY_PLUGINS: dict[str, list[PluginClass]] = {
    # ... existing mappings ...
    "yourCapability": [YourPlugin],
}
```

Then add the capability to the frontend types (Step 5).

**Option B — Gate under an EXISTING capability:**

```python
CAPABILITY_PLUGINS: dict[str, list[PluginClass]] = {
    "webAccess": [WebPlugin, HttpPlugin, YourPlugin],  # append to existing
}
```

**Option C — Always enabled (no capability gate):**

```python
ALWAYS_ENABLED: list[PluginClass] = [TaskPlugin, NotesPlugin, YourPlugin]
```

### 4. Add Frontend Capability (if new capability)

Edit `frontend/src/types/index.ts` — add to `BotCapabilities`:

```typescript
export interface BotCapabilities {
  // ... existing capabilities ...
  yourCapability: boolean
}
```

### 5. Add Frontend Capability Toggle (if new capability)

In the bot settings view (`frontend/src/components/views/SettingsView.tsx`), add a toggle for the new capability so users can enable/disable it per bot.

## Key Patterns

### Returning Media
For tools that produce images or audio, return markdown data URIs:

```python
# Image
return f"![Generated Image](data:image/png;base64,{base64_data})"

# Audio
return f"![Generated Audio](data:audio/mpeg;base64,{base64_data})"
```

The frontend's `MarkdownRenderer` auto-detects these and renders `<img>` or `<audio>` elements.

### Config Params
Config params defined in `@skill(config_params=[...])` become per-tool settings in the bot's `toolConfigs`. Access them via:

```python
cfg = ctx.tool_configs.get("tool_name", {})
value = cfg.get("param_name", default_value)
```

### Risk Levels
- `SAFE` — No side effects, read-only
- `MODERATE` — External API calls, generates content
- `DANGEROUS` — Writes files, executes code, sends messages
- `CRITICAL` — Destructive operations, shell access

### Bot Model Slots
If the tool uses an AI model (image gen, audio gen, etc.), read from `ctx.bot_models`:

```python
model = ctx.bot_models.get("image", "") if ctx.bot_models else ""
```

Available slots: `default`, `image`, `audio`, `structured`.

## Checklist

- [ ] Plugin file created in `cachibot/plugins/`
- [ ] Plugin extends `CachibotPlugin` with proper `__init__`, `manifest`, `_build_skills`, `skills`
- [ ] Skills use `@skill` decorator with description, risk_level, config_params
- [ ] Plugin exported in `cachibot/plugins/__init__.py`
- [ ] Plugin registered in `cachibot/services/plugin_manager.py`
- [ ] If new capability: added to `BotCapabilities` in frontend types
- [ ] If new capability: toggle added to settings view
- [ ] Tool returns human-readable strings (not raw JSON)
- [ ] Errors caught and returned as `"Error: ..."` strings (never raise)
