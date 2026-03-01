# Tool Skills

Skills are the functions your plugin exposes to the LLM. When a bot has your plugin enabled, the LLM can call your skills as tools during a conversation.

## The `@skill()` Decorator

Skills are created using the `@skill()` decorator from `tukuy.skills`. The decorator inspects your function's signature and docstring to auto-generate a JSON Schema that the LLM uses to understand what arguments to pass.

```python
from tukuy.skills import skill

@skill(
    name="translate",
    description="Translate text to another language.",
    category="language",
    tags=["translation", "i18n"],
)
async def translate(text: str, target_language: str = "es") -> str:
    """Translate text to the target language.

    Args:
        text: The text to translate.
        target_language: ISO language code (default: "es" for Spanish).
    """
    # Your implementation here
    return translated_text
```

### Decorator Parameters

| Parameter              | Type          | Default          | Description                                        |
|------------------------|---------------|------------------|----------------------------------------------------|
| `name`                 | `str`         | function name    | Tool name visible to the LLM                      |
| `description`          | `str`         | docstring        | Description the LLM reads to decide when to use it |
| `version`              | `str`         | `"0.1.0"`        | Skill version                                      |
| `category`             | `str`         | `"general"`      | Grouping category                                  |
| `tags`                 | `list[str]`   | `[]`             | Discovery tags                                     |
| `input_schema`         | `dict\|None`  | auto-inferred    | Explicit JSON Schema for inputs                    |
| `output_schema`        | `dict\|None`  | auto-inferred    | Explicit JSON Schema for outputs                   |
| `side_effects`         | `bool`        | `False`          | Whether the skill mutates state                    |
| `idempotent`           | `bool`        | `False`          | Whether repeated calls are safe                    |
| `requires_network`     | `bool`        | `False`          | Whether the skill needs network access             |
| `requires_filesystem`  | `bool`        | `False`          | Whether the skill needs file access                |
| `display_name`         | `str\|None`   | humanized `name` | UI display name                                    |
| `icon`                 | `str\|None`   | `None`           | Lucide icon name                                   |
| `risk_level`           | `RiskLevel`   | `AUTO`           | `SAFE`, `MODERATE`, `DANGEROUS`, `CRITICAL`, `AUTO` |
| `hidden`               | `bool`        | `False`          | Hide from the tools panel (still callable)         |
| `config_params`        | `list`        | `[]`             | User-configurable parameters (see below)           |

### Risk Levels

When `risk_level` is `AUTO` (the default), it is derived from safety flags:

- `idempotent=True` and `side_effects=False` --> `SAFE`
- `side_effects=True` --> `MODERATE`
- `side_effects=True` and (`requires_filesystem` or `requires_network`) --> `DANGEROUS`

## Schema Inference

The decorator automatically generates a JSON Schema from your function's type annotations and Google-style docstring. You rarely need to provide `input_schema` manually.

```python
@skill(name="search", description="Search documents.")
async def search(
    query: str,
    limit: int = 10,
    include_archived: bool = False,
) -> list[dict]:
    """Search the knowledge base.

    Args:
        query: Search query string.
        limit: Maximum results to return.
        include_archived: Whether to include archived documents.
    """
    ...
```

This produces the following JSON Schema automatically:

```json
{
  "type": "object",
  "properties": {
    "query": { "type": "string", "description": "Search query string." },
    "limit": { "type": "integer", "description": "Maximum results to return." },
    "include_archived": { "type": "boolean", "description": "Whether to include archived documents." }
  },
  "required": ["query"]
}
```

### Supported Type Annotations

| Python Type     | JSON Schema Type |
|-----------------|------------------|
| `str`           | `string`         |
| `int`           | `integer`        |
| `float`         | `number`         |
| `bool`          | `boolean`        |
| `list`          | `array`          |
| `list[str]`     | `array` of `string` |
| `dict`          | `object`         |
| `X \| None`     | schema of `X`    |
| Pydantic model  | full object schema |

Parameters with default values are optional. Parameters without defaults are `required`.

## Wiring Skills into Your Plugin

The `CachibotPlugin` base class requires a `skills` property that returns a `dict[str, Skill]`. The standard pattern is to build skills in a `_build_skills()` method and capture the `Skill` object via `fn.__skill__`:

```python
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
        ctx = self.ctx  # Capture context for closures

        @skill(name="my_tool", description="Does something.")
        async def my_tool(input: str) -> str:
            """Process input.

            Args:
                input: The input to process.
            """
            # You can access ctx.config, ctx.sandbox, etc.
            return f"Processed: {input}"

        return {"my_tool": my_tool.__skill__}
```

## Accessing PluginContext from Skills

Since skills are defined as closures inside `_build_skills()`, they can capture `self.ctx` (or alias it as `ctx`). This gives access to:

- `ctx.config` -- CachiBot configuration
- `ctx.sandbox` -- Python sandbox for safe code execution
- `ctx.bot_id` -- Current bot ID
- `ctx.chat_id` -- Current chat ID
- `ctx.tool_configs` -- Per-tool configuration values set by the user
- `ctx.bot_models` -- Model slot configuration for the bot
- `ctx.on_tool_output` -- Callback to stream intermediate output to the chat
- `ctx.on_artifact` -- Callback to emit artifacts

```python
def _build_skills(self) -> dict[str, Skill]:
    ctx = self.ctx

    @skill(name="generate", description="Generate with a specific model.")
    async def generate(prompt: str) -> str:
        """Generate text.

        Args:
            prompt: The prompt to generate from.
        """
        # Read per-tool config
        tool_cfg = ctx.tool_configs.get("generate", {})
        model = tool_cfg.get("model", "default")

        # Stream progress to the chat
        if ctx.on_tool_output:
            from prompture.integrations.tukuy_bridge import current_tool_call_id
            tool_id = current_tool_call_id.get()
            if tool_id:
                await ctx.on_tool_output(tool_id, "Generating...")

        return f"Generated with {model}: {prompt}"

    return {"generate": generate.__skill__}
```

## Config Parameters

Skills can declare configurable parameters that appear in the bot's tool settings UI. Users can adjust these per-bot without editing code.

```python
from tukuy.skill import ConfigParam, RiskLevel

@skill(
    name="build_website",
    description="Generate a website.",
    config_params=[
        ConfigParam(
            name="model",
            display_name="Model",
            description="LLM model for generation.",
            type="text",
            default="",
        ),
        ConfigParam(
            name="maxCost",
            display_name="Max Cost",
            description="Maximum cost in USD.",
            type="number",
            default=0,
            min=0,
            max=50,
            step=0.5,
            unit="USD",
        ),
        ConfigParam(
            name="quality",
            display_name="Quality",
            description="Output quality level.",
            type="select",
            default="standard",
            options=["draft", "standard", "high"],
        ),
    ],
)
async def build_website(prompt: str) -> str:
    ...
```

At runtime, read the user's config values from `ctx.tool_configs`:

```python
tool_cfg = ctx.tool_configs.get("build_website", {})
model = tool_cfg.get("model", "")
max_cost = tool_cfg.get("maxCost", 0)
```

### ConfigParam Fields

| Field              | Type            | Description                              |
|--------------------|-----------------|------------------------------------------|
| `name`             | `str`           | Parameter key                            |
| `display_name`     | `str\|None`     | UI label                                 |
| `description`      | `str\|None`     | Help text                                |
| `type`             | `str`           | `"string"`, `"number"`, `"boolean"`, `"select"`, `"text"`, `"secret"`, `"path"`, `"url"`, `"code"` |
| `default`          | `Any`           | Default value                            |
| `min` / `max`      | `float\|None`   | Bounds for number inputs                 |
| `step`             | `float\|None`   | Step increment for number inputs         |
| `options`          | `list[str]\|None` | Choices for select/multiselect         |
| `unit`             | `str\|None`     | Unit label (e.g., "USD", "seconds")      |
| `placeholder`      | `str\|None`     | Placeholder text for text inputs         |

## Multiple Skills per Plugin

A plugin can expose any number of skills:

```python
def _build_skills(self) -> dict[str, Skill]:
    @skill(name="create_code", description="Create a code artifact.")
    async def create_code(language: str, title: str, content: str) -> dict:
        ...

    @skill(name="update_code", description="Update an existing code artifact.")
    async def update_code(artifact_id: str, content: str, version: int = 2) -> dict:
        ...

    return {
        "create_code": create_code.__skill__,
        "update_code": update_code.__skill__,
    }
```

## Return Values

Skills can return:

- **`str`** -- Displayed as the tool result in the chat
- **`dict`** -- Serialized as JSON; if it contains `__artifact__: True`, the WebSocket handler auto-detects it and renders an artifact panel (see [Artifacts](artifacts.md))
- **Any serializable value** -- Converted to string for the LLM
