# Example Plugins Walkthrough

CachiBot ships with a minimal reference plugin in `examples/plugins/hello_world/`; more examples are in [CachiBot-Plugins](https://github.com/jhd3197/CachiBot-Plugins). Copy any plugin to `~/.cachibot/plugins/<name>/` to install.

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

## More Examples

The `code_canvas`, `html_preview`, `doc_writer` and `website_builder` plugins live in the [CachiBot-Plugins](https://github.com/jhd3197/CachiBot-Plugins) repository.

