# Lifecycle Hooks and Plugin Context

## PluginContext

Every plugin receives a `PluginContext` at construction time. This dataclass carries everything a plugin's skills need to operate.

```python
from cachibot.plugins.base import PluginContext

@dataclass
class PluginContext:
    config: Config                                    # CachiBot global configuration
    sandbox: PythonSandbox                            # Sandboxed Python execution environment
    bot_id: str | None = None                         # Current bot ID (set at runtime)
    chat_id: str | None = None                        # Current chat/room ID (set at runtime)
    tool_configs: dict[str, Any] = field(...)         # Per-tool config values from the user
    bot_models: dict[str, Any] | None = None          # Model slot configuration for the bot
    on_tool_output: Callable[[str, str], Any] | None  # Stream intermediate output
    on_artifact: Callable[[Artifact], Any] | None     # Emit artifact directly
```

### Field Reference

#### `config`

The global CachiBot `Config` object. Provides access to API keys, workspace paths, server settings, and all configuration from `cachibot.toml`.

```python
workspace = ctx.config.workspace_dir
```

#### `sandbox`

A `tukuy.PythonSandbox` instance scoped to the current workspace. Use it to execute Python code safely with import restrictions and timeout limits.

```python
result = await ctx.sandbox.execute("print(2 + 2)")
```

#### `bot_id` / `chat_id`

The current bot and chat/room identifiers. These are `None` during plugin loading and set at runtime when a skill is invoked in the context of a conversation.

```python
if ctx.bot_id:
    # We're running inside a bot conversation
    ...
```

#### `tool_configs`

A dict of per-tool configuration values. These are the settings the user has configured for each skill through the bot's tool settings panel. The key is the skill name, the value is a dict of config parameter values.

```python
cfg = ctx.tool_configs.get("build_website", {})
model = cfg.get("model", "gpt-4o")
max_cost = cfg.get("maxCost", 0)
```

#### `bot_models`

Model slot configuration for the bot. Contains the model assignments for different purposes (e.g., `"default"`, `"fast"`, `"reasoning"`).

```python
if ctx.bot_models:
    default_model = ctx.bot_models.get("default", "")
```

#### `on_tool_output`

Callback to stream intermediate output to the chat while a skill is executing. The first argument is the tool call ID, the second is the text to display. This enables progress reporting for long-running operations.

```python
if ctx.on_tool_output:
    from prompture.integrations.tukuy_bridge import current_tool_call_id

    tool_id = current_tool_call_id.get()
    if tool_id:
        await ctx.on_tool_output(tool_id, "Processing step 1 of 3...")
        # ... do work ...
        await ctx.on_tool_output(tool_id, "Processing step 2 of 3...")
```

#### `on_artifact`

Callback to emit an artifact directly (bypassing the return-value detection). Most plugins should use the SDK helpers and return artifact dicts from skills instead. This callback is available for edge cases where you need to emit an artifact outside of a skill's return value.

## Lifecycle Hooks

The `CachibotPlugin` base class provides four lifecycle hooks. Override them in your plugin to run code at specific points in the plugin's lifecycle.

```python
from cachibot.plugins.base import CachibotPlugin, PluginContext


class MyPlugin(CachibotPlugin):
    def __init__(self, ctx: PluginContext) -> None:
        super().__init__("my_plugin", ctx)
        self._skills_map = self._build_skills()

    async def on_install(self) -> None:
        """Called once when the plugin is first installed."""
        # Set up initial state, create directories, etc.
        pass

    async def on_uninstall(self) -> None:
        """Called before the plugin directory is removed from disk."""
        # Clean up external resources, files, database entries, etc.
        pass

    async def on_enable(self, bot_id: str) -> None:
        """Called when the plugin is enabled on a specific bot."""
        # Initialize per-bot state, register webhooks, etc.
        pass

    async def on_disable(self, bot_id: str) -> None:
        """Called when the plugin is disabled on a specific bot."""
        # Clean up per-bot state, unregister webhooks, etc.
        pass
```

### Hook Reference

| Hook            | When                                           | Arguments           |
|-----------------|-------------------------------------------------|---------------------|
| `on_install`    | Plugin archive is extracted and loaded           | (none)              |
| `on_uninstall`  | Before plugin directory is deleted               | (none)              |
| `on_enable`     | User enables the plugin on a bot                 | `bot_id: str`       |
| `on_disable`    | User disables the plugin on a bot                | `bot_id: str`       |

All hooks are async and called with best-effort semantics -- exceptions are caught and logged but do not prevent the operation from completing.

### Hook Execution Context

Lifecycle hooks run with a minimal `PluginContext`. During `on_install` and `on_uninstall`, `bot_id` and `chat_id` are `None`. During `on_enable` and `on_disable`, the `bot_id` argument tells you which bot is being configured, but `ctx.bot_id` may still be `None` since no conversation is active.

## Plugin Base Class

The `CachibotPlugin` class extends Tukuy's `TransformerPlugin` but disables transformers (CachiBot uses Prompture's ToolRegistry instead).

```python
class CachibotPlugin(TransformerPlugin):
    def __init__(self, name: str, ctx: PluginContext) -> None:
        super().__init__(name)
        self.ctx = ctx

    @property
    def transformers(self) -> dict[str, Callable[..., Any]]:
        """CachiBot plugins don't provide transformers."""
        return {}

    @property
    def skills(self) -> dict[str, Skill]:
        """Override this to return your plugin's skills."""
        raise NotImplementedError
```

### What You Must Implement

| Member   | Type                   | Description                           |
|----------|------------------------|---------------------------------------|
| `skills` | `dict[str, Skill]`     | Property returning all skill objects   |

### What You May Override

| Member         | Type                   | Description                      |
|----------------|------------------------|----------------------------------|
| `on_install`   | `async def`            | First-install setup              |
| `on_uninstall` | `async def`            | Pre-removal cleanup              |
| `on_enable`    | `async def(bot_id)`    | Per-bot enable logic             |
| `on_disable`   | `async def(bot_id)`    | Per-bot disable logic            |

## Streaming Progress

For long-running skills, stream progress to the user via `on_tool_output`:

```python
def _build_skills(self) -> dict[str, Skill]:
    ctx = self.ctx

    @skill(name="long_task", description="A task that takes a while.")
    async def long_task(input: str) -> str:
        """Run a long task.

        Args:
            input: Task input.
        """
        emit = _build_emitter(ctx)

        if emit:
            await emit("Starting...")

        # Phase 1
        result_1 = await do_phase_1(input)
        if emit:
            await emit(f"Phase 1 complete: {result_1}")

        # Phase 2
        result_2 = await do_phase_2(result_1)
        if emit:
            await emit(f"Phase 2 complete: {result_2}")

        return f"Done: {result_2}"

    return {"long_task": long_task.__skill__}


def _build_emitter(ctx: PluginContext):
    """Build an async emitter for streaming progress."""
    if not ctx.on_tool_output:
        return None

    from prompture.integrations.tukuy_bridge import current_tool_call_id

    tool_id = current_tool_call_id.get()
    if not tool_id:
        return None

    on_output = ctx.on_tool_output

    async def emit(text: str) -> None:
        await on_output(tool_id, text)

    return emit
```
