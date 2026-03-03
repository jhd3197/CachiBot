# Example Plugins Walkthrough

CachiBot ships with five reference plugins in `examples/plugins/`. Each demonstrates a different pattern. Copy any of them to `~/.cachibot/plugins/<name>/` to install.

## hello_world -- Minimal Template

**Location:** `examples/plugins/hello_world/`

The simplest possible plugin. One skill, no dependencies, no artifacts, no config.

### Manifest

```toml
[plugin]
name = "hello_world"
display_name = "Hello World"
description = "Minimal template plugin -- one skill, no dependencies"
version = "0.1.0"
author = "CachiBot Team"
type = "tool"

[plugin.ui]
icon = "sparkles"
color = "#22c55e"
group = "Examples"

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

### Plugin Class

```python
class HelloWorldPlugin(CachibotPlugin):
    def __init__(self, ctx: PluginContext) -> None:
        super().__init__("hello_world", ctx)
        self._skills_map = self._build_skills()

    @property
    def skills(self) -> dict[str, Skill]:
        return self._skills_map

    def _build_skills(self) -> dict[str, Skill]:
        @skill(
            name="hello",
            description="Say hello with a friendly greeting.",
            category="examples",
            tags=["greeting", "demo"],
        )
        async def hello(name: str = "World") -> str:
            """Generate a friendly greeting.

            Args:
                name: Who to greet (default: "World").
            """
            return f"Hello, {name}! Welcome to CachiBot plugins."

        return {"hello": hello.__skill__}
```

### Key Takeaways

- The `__init__.py` re-exports the plugin class so the loader finds it.
- The skill function is `async` even though it does nothing async -- this is the recommended default.
- The `name` passed to `super().__init__()` must match the `name` in `plugin.toml`.
- Return a plain string from the skill -- it appears as the tool result in the chat.

---

## code_canvas -- Code Artifacts

**Location:** `examples/plugins/code_canvas/`

Demonstrates creating and updating code artifacts. The LLM generates code that appears in an editable side panel with syntax highlighting.

### Skills

| Skill          | Description                         | Returns           |
|----------------|-------------------------------------|-------------------|
| `create_code`  | Create a new code artifact          | `code_artifact()` |
| `update_code`  | Update an existing code artifact    | `artifact_update()` |

### Pattern: Create + Update Pair

This is the standard pattern for artifact-emitting plugins -- a "create" skill and an "update" skill:

```python
from cachibot.plugins.sdk import artifact_update, code_artifact

@skill(name="create_code", description="Create a code artifact.")
async def create_code(language: str, title: str, content: str) -> dict:
    return code_artifact(title=title, content=content, language=language)

@skill(name="update_code", description="Update an existing code artifact.")
async def update_code(artifact_id: str, content: str, version: int = 2) -> dict:
    return artifact_update(artifact_id=artifact_id, content=content, version=version)
```

The LLM calls `create_code` first, receives the artifact ID in the response, then calls `update_code` with that ID when the user asks for changes.

### Key Takeaways

- Import SDK helpers from `cachibot.plugins.sdk`.
- Return a `dict` (not a string) when emitting artifacts.
- The `version` parameter should increment on updates so the frontend can track changes.
- The artifact `type` is set automatically by the helper (`"code"` for `code_artifact()`).

---

## html_preview -- HTML Artifacts

**Location:** `examples/plugins/html_preview/`

Live HTML/CSS/JS preview in a sandboxed iframe. Identical structure to `code_canvas` but uses `html_artifact()` instead.

### Skills

| Skill            | Description                       | Returns            |
|------------------|-----------------------------------|--------------------|
| `preview_html`   | Create an HTML preview artifact   | `html_artifact()`  |
| `update_preview` | Update an existing HTML preview   | `artifact_update()` |

### Pattern: HTML Content

```python
from cachibot.plugins.sdk import html_artifact

@skill(name="preview_html", description="Create a live HTML preview.")
async def preview_html(title: str, html_content: str) -> dict:
    return html_artifact(title=title, content=html_content)
```

The `content` should be a complete HTML document (including `<html>`, `<head>`, `<body>`) since it renders in an isolated iframe.

---

## doc_writer -- Markdown Artifacts

**Location:** `examples/plugins/doc_writer/`

Claude Artifacts-style document editing. Creates markdown artifacts that render as rich formatted documents.

### Skills

| Skill              | Description                        | Returns                |
|--------------------|------------------------------------|------------------------|
| `create_document`  | Create a markdown document         | `markdown_artifact()`  |
| `update_document`  | Update an existing document        | `artifact_update()`    |

### Pattern: Structured Content

```python
from cachibot.plugins.sdk import markdown_artifact

@skill(
    name="create_document",
    description=(
        "Create a rich markdown document in the side panel. "
        "Use this for writing reports, articles, documentation, "
        "or any structured text content."
    ),
    category="creative",
    tags=["document", "markdown", "artifact", "writing"],
)
async def create_document(title: str, content: str) -> dict:
    return markdown_artifact(title=title, content=content)
```

### Key Takeaway

The `description` in the `@skill()` decorator is critical -- it tells the LLM *when* to use this tool. Write it as if instructing an assistant: "Use this for X, Y, Z."

---

## website_builder -- Complex Real-World Plugin

**Location:** `examples/plugins/website_builder/`

A full-featured plugin that integrates an external library (AgentSite) to generate complete websites using a multi-agent pipeline. This is the most complex reference plugin and demonstrates advanced patterns.

### Manifest Highlights

```toml
[plugin.requires]
python = ">=3.10"
filesystem = true              # Writes generated websites to disk
network = true                 # Calls LLM APIs
imports = ["agentsite"]        # External dependency

[plugin.permissions]
allow_env_vars = ["OPENAI_API_KEY"]
allow_paths = ["~/.cachibot/websites"]

[[plugin.config]]
name = "model"
display_name = "Model"
type = "text"
default = ""

[[plugin.config]]
name = "maxCost"
display_name = "Max Cost"
type = "number"
default = 0
```

### Skills

| Skill              | Description                                  |
|--------------------|----------------------------------------------|
| `build_website`    | Generate a complete website from a prompt     |
| `iterate_website`  | Iterate on a previously generated website     |
| `list_websites`    | List all generated website projects           |
| `load_website`     | Load a project's full state                   |
| `cancel_website`   | Cancel a running generation                   |
| `delete_website`   | Delete a project from disk                    |

### Pattern: Config Params with Rich Types

```python
from tukuy.skill import ConfigParam, RiskLevel

@skill(
    name="build_website",
    description="Generate a complete website.",
    side_effects=True,
    requires_network=True,
    risk_level=RiskLevel.MODERATE,
    config_params=[
        ConfigParam(
            name="model",
            display_name="Model",
            type="text",
            default="",
        ),
        ConfigParam(
            name="maxCost",
            display_name="Max Cost",
            type="number",
            default=0,
            min=0, max=50, step=0.5,
            unit="USD",
        ),
        ConfigParam(
            name="budgetPolicy",
            display_name="Budget Policy",
            type="select",
            default="",
            options=["", "hard_stop", "warn_and_continue", "degrade"],
        ),
    ],
)
async def build_website(prompt: str, ...) -> str:
    ...
```

### Pattern: Streaming Progress

The website builder uses `on_tool_output` to stream real-time progress events to the chat while the multi-agent pipeline runs:

```python
def _build_progress_emitter(ctx: PluginContext):
    if not ctx.on_tool_output:
        return None

    from prompture.integrations.tukuy_bridge import current_tool_call_id

    tool_id = current_tool_call_id.get()
    if not tool_id:
        return None

    on_output = ctx.on_tool_output

    async def _emit(text: str) -> None:
        await on_output(tool_id, text)

    return _emit
```

Then in the skill:

```python
emit = _build_progress_emitter(ctx)
if emit:
    await emit("Starting website generation pipeline...")

# ... run pipeline with event callbacks ...

async def on_event(event):
    if emit:
        msg = _format_event(event)
        if msg:
            await emit(msg)
```

### Pattern: Graceful Dependency Handling

External dependencies are imported inside the skill function, not at module level. This lets the plugin load even when the dependency is missing (the error is reported when the skill is actually called):

```python
async def build_website(prompt: str, ...) -> str:
    try:
        from agentsite.engine.component import generate_website
    except ImportError:
        return (
            "Error: AgentSite is not installed. "
            "Install it with: pip install -e path/to/AgentSite"
        )
    # ... proceed with generation ...
```

### Pattern: Reading Tool Config at Runtime

```python
tool_cfg = ctx.tool_configs.get("build_website", {})
model = tool_cfg.get("model", "") or ""
if not model and ctx.bot_models:
    model = ctx.bot_models.get("default", "")
if not model:
    model = "openai/gpt-4o"  # Final fallback
```

### Pattern: Cancellation Support

```python
cancel_event = asyncio.Event()
gen_id = f"build-{id(cancel_event)}"
WebsiteBuilderPlugin._active_generations[gen_id] = cancel_event

# Pass to the pipeline
config = GenerationConfig(..., cancel_event=cancel_event)

# Separate skill to cancel
@skill(name="cancel_website", description="Cancel a running generation.")
async def cancel_website(generation_id: str) -> str:
    cancel_event = WebsiteBuilderPlugin._active_generations.get(generation_id)
    if cancel_event is None:
        return "No active generation found."
    cancel_event.set()
    return "Cancellation requested."
```

### Key Takeaways

- Declare all external dependencies in `[plugin.requires].imports` so the loader can check them at startup.
- Use `[plugin.permissions]` to declare which env vars and paths you need.
- Use `[[plugin.config]]` in the manifest and `config_params` on the `@skill()` decorator to expose user-configurable settings.
- Stream progress for any operation that takes more than a few seconds.
- Handle missing dependencies gracefully with try/except inside skill functions.
- Use `asyncio.Event` for cancellation of long-running tasks.

---

## Common Patterns Summary

| Pattern                    | Example Plugin     | Description                              |
|----------------------------|--------------------|------------------------------------------|
| Single skill, no deps     | `hello_world`      | Simplest starting point                  |
| Create + Update artifacts  | `code_canvas`      | Standard artifact lifecycle              |
| HTML iframe preview        | `html_preview`     | Sandboxed live preview                   |
| Markdown documents         | `doc_writer`       | Rich text editing                        |
| External dependencies      | `website_builder`  | Import gating and graceful errors        |
| Config params              | `website_builder`  | User-configurable settings               |
| Progress streaming         | `website_builder`  | Real-time status updates                 |
| Cancellation               | `website_builder`  | Async cancellation of long tasks         |
