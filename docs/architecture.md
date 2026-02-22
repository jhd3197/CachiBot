# CachiBot + Prompture + Tukuy — Architecture Guide

How the three libraries work together to deliver a security-focused, plugin-driven AI agent with a fully dynamic frontend.

---

## Stack at a Glance

| Layer | Library | Role |
|-------|---------|------|
| **LLM orchestration** | [Prompture](https://pypi.org/project/prompture/) `>=1.0.15` | `AsyncAgent`, `ToolRegistry`, `PythonSandbox`, `AgentCallbacks`, risk analysis |
| **Plugin framework** | [Tukuy](https://pypi.org/project/tukuy/) `>=0.1.0` | `TransformerPlugin`, `@skill` decorator, `PluginManifest`, `RiskLevel`, `ConfigParam` |
| **Application** | CachiBot | Agent dataclass, capability gating, API server, React frontend |

```
┌──────────────────────────────────────────────────────────────────┐
│                        React Frontend                            │
│  ToolsView ─ ToolConfigDialog ─ ToolIconRenderer ─ ChatView     │
│        ▲             ▲                                           │
│        │  REST       │  WebSocket                                │
├────────┼─────────────┼───────────────────────────────────────────┤
│        │  FastAPI     │                                           │
│  /api/plugins    /ws ──► CachibotAgent                           │
│                          │                                       │
│                   ┌──────┴──────┐                                │
│              Prompture      Plugin Manager                       │
│           AsyncAgent        (capability gate)                    │
│           ToolRegistry           │                               │
│           PythonSandbox    ┌─────┴──────────┐                    │
│           SecurityContext  │  Tukuy Plugins  │                   │
│                            │  @skill()       │                   │
│                            │  PluginManifest │                   │
│                            │  ConfigParam    │                   │
│                            └────────────────┘                    │
└──────────────────────────────────────────────────────────────────┘
```

---

## 1. Tukuy — The Plugin Framework

Tukuy provides the plugin model. Every tool CachiBot exposes — whether custom or built-in — is a Tukuy plugin containing one or more **skills**.

### 1.1 PluginManifest

Each plugin declares identity and requirements via `PluginManifest`:

```python
from tukuy.manifest import PluginManifest

@property
def manifest(self) -> PluginManifest:
    return PluginManifest(
        name="file_ops",
        display_name="File Operations",
        icon="folder",              # Lucide icon name
        group="Core",
        requires_filesystem=True,
    )
```

The manifest is serialized by the `/api/plugins` endpoint and consumed by the frontend to render plugin headers, icons, and groupings — **no hardcoded UI metadata needed**.

### 1.2 @skill Decorator

Individual tools are defined with `@skill()`, which attaches a `SkillDescriptor` to the function:

```python
from tukuy.skill import skill, RiskLevel, ConfigParam

@skill(
    name="python_execute",
    description="Execute Python code in a sandboxed environment",
    category="code",
    tags=["python", "sandbox", "execution"],
    display_name="Execute Python",
    icon="code",
    risk_level=RiskLevel.DANGEROUS,
    side_effects=True,
    requires_filesystem=True,
    config_params=[
        ConfigParam(
            name="timeoutSeconds",
            display_name="Timeout",
            type="number",
            default=30,
            min=5,
            max=120,
            step=5,
            unit="seconds",
            description="Maximum execution time",
        ),
        ConfigParam(
            name="maxOutputLength",
            display_name="Max Output",
            type="number",
            default=10000,
            min=1000,
            max=50000,
            step=1000,
            unit="chars",
        ),
    ],
)
def python_execute(code: str) -> str:
    ...
```

**Key metadata fields:**

| Field | Purpose | Frontend use |
|-------|---------|--------------|
| `display_name` | Human-readable label | Tool card title |
| `icon` | Lucide icon name | `ToolIconRenderer` |
| `risk_level` | `SAFE` / `MODERATE` / `DANGEROUS` / `CRITICAL` | Risk badge color |
| `config_params` | Configurable parameters with validation | `ToolConfigDialog` generic form |
| `category` | Functional grouping | Filter chips |
| `tags` | Searchable keywords | Search |
| `hidden` | Exclude from UI | Filtered out |
| `deprecated` | Deprecation notice | Strike-through + notice |

### 1.3 RiskLevel Enum

```python
class RiskLevel(Enum):
    SAFE      = "safe"       # Read-only, no side effects
    MODERATE  = "moderate"   # Limited side effects
    DANGEROUS = "dangerous"  # Can modify files, execute code
    CRITICAL  = "critical"   # Network access, credentials, system changes
```

Risk levels drive both the UI badge styling and the approval flow — `DANGEROUS` and `CRITICAL` operations can trigger an approval callback before execution.

### 1.4 ConfigParam

`ConfigParam` defines a configurable parameter that the frontend renders dynamically:

```python
ConfigParam(
    name="timeoutSeconds",       # Key in tool_configs dict
    display_name="Timeout",      # Label in UI
    description="Max execution time",
    type="number",               # number | string | boolean | select
    default=30,
    min=5,                       # For number type
    max=120,
    step=5,
    unit="seconds",              # Shown next to value
    options=None,                # For select type
    scope="per_bot",             # global | per_bot | per_call
)
```

The frontend `ToolConfigDialog` renders each param type as:
- **`number`** → Range slider with min/max/step and unit label
- **`boolean`** → Toggle switch
- **`select`** → Dropdown from `options[]`
- **`string`** → Text input

### 1.5 Built-in Tukuy Plugins

Tukuy ships with plugins that CachiBot enables based on capabilities:

| Plugin | Skills | Capability |
|--------|--------|------------|
| `GitPlugin` | git_status, git_diff, git_commit, ... | `gitOperations` |
| `ShellPlugin` | shell_run | `shellAccess` |
| `WebPlugin` | web_search, web_fetch | `webAccess` |
| `HttpPlugin` | http_request | `webAccess` |
| `SqlPlugin` | sqlite_query, sqlite_execute | `dataOperations` |
| `CompressionPlugin` | zip_create, tar_extract, ... | `dataOperations` |

These plugins are scoped to the workspace via Prompture's `SecurityContext` (see section 2.3).

---

## 2. Prompture — LLM Orchestration

Prompture handles the agent loop: model calls, tool dispatch, conversation management, and security enforcement.

### 2.1 ToolRegistry

The central registry that maps tool names to callable functions. The plugin manager bridges Tukuy skills into Prompture:

```python
# plugin_manager.py
def plugins_to_registry(plugins: list[TransformerPlugin]) -> ToolRegistry:
    registry = ToolRegistry()
    for plugin in plugins:
        for skill_obj in plugin.skills.values():
            registry.add_tukuy_skill(skill_obj)  # Preserves Tukuy metadata
    return registry
```

`add_tukuy_skill()` (Prompture 1.0.15+) accepts a Tukuy `Skill` object directly instead of a plain function, preserving all `SkillDescriptor` metadata through the bridge. This is what allows the `/api/plugins` endpoint to introspect skill metadata even though the agent uses Prompture's registry at runtime.

### 2.2 AsyncAgent

Prompture's `AsyncAgent` is the runtime engine:

```python
agent = PromptureAgent(
    model="openai/gpt-4o",           # Provider/model string
    tools=registry,                    # ToolRegistry with all skills
    system_prompt=system_prompt,
    agent_callbacks=callbacks,         # Streaming events
    max_iterations=25,
    persistent_conversation=True,
    security_context=security_ctx,     # Sandbox-derived security
    options={"max_tokens": 8192},
)
```

The agent loop:
1. Sends user message + conversation history to the LLM
2. LLM decides to call a tool or respond
3. If tool call → dispatch through `ToolRegistry` → return result to LLM
4. Repeat until the LLM produces a final text response or hits `max_iterations`

### 2.3 PythonSandbox & SecurityContext

`PythonSandbox` restricts code execution:

```python
sandbox = PythonSandbox(
    allowed_imports=["math", "json", "re", "datetime", ...],
    timeout_seconds=60,
    allowed_read_paths=[workspace_path],
    allowed_write_paths=[workspace_path],
)
```

The sandbox converts to a `SecurityContext` that also scopes Tukuy's built-in plugins:

```python
security_ctx = sandbox.to_security_context()
# Now GitPlugin can only operate within workspace_path
# ShellPlugin commands are restricted to workspace_path
```

### 2.4 AgentCallbacks

Prompture streams events through callbacks that CachiBot forwards over WebSocket:

```python
callbacks = AgentCallbacks(
    on_thinking=lambda text: send_ws("thinking", text),
    on_tool_start=lambda name, args: send_ws("tool_start", {name, args}),
    on_tool_end=lambda name, result: send_ws("tool_end", {name, result}),
    on_message=lambda text: send_ws("message", text),
    on_approval_needed=lambda tool, action, details: prompt_user(tool),
)
```

### 2.5 Risk Analysis (python_execute)

For code execution, Prompture provides AST-based risk analysis:

```python
from prompture import analyze_python

risk = analyze_python(code)
# risk.level: LOW | MODERATE | HIGH | CRITICAL
# risk.reasons: ["Uses subprocess", "Writes to /etc/..."]

if risk.level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
    raise ApprovalRequired(tool="python_execute", details=risk.reasons)
```

This integrates with the `on_approval_needed` callback — the frontend shows a confirmation dialog before the agent proceeds.

---

## 3. CachiBot — The Application Layer

CachiBot ties Prompture and Tukuy together with capability gating, bot-scoped configuration, and a full React UI.

### 3.1 Plugin Context

Every CachiBot plugin receives a `PluginContext` with runtime dependencies:

```python
@dataclass
class PluginContext:
    config: Config                # App configuration
    sandbox: PythonSandbox       # Prompture sandbox instance
    bot_id: str | None           # Active bot identity
    tool_configs: dict           # Per-tool settings from bot config
```

Custom plugins extend `CachibotPlugin(TransformerPlugin)` and receive the context:

```python
class FileOpsPlugin(CachibotPlugin):
    def __init__(self, ctx: PluginContext) -> None:
        super().__init__("file_ops", ctx)
        self._skills_map = self._build_skills()
```

Tukuy built-in plugins (Git, Shell, Web, etc.) don't need the context — they're scoped through Prompture's `SecurityContext`.

### 3.2 Plugin Manager & Capability Gating

The plugin manager maps bot capabilities to plugin classes:

```python
CAPABILITY_PLUGINS = {
    "fileOperations":  [FileOpsPlugin],
    "codeExecution":   [PythonSandboxPlugin],
    "gitOperations":   [GitPlugin],
    "shellAccess":     [ShellPlugin],
    "webAccess":       [WebPlugin, HttpPlugin],
    "dataOperations":  [SqlPlugin, CompressionPlugin],
    "connections":     [PlatformPlugin],
    "workManagement":  [WorkManagementPlugin],
}

ALWAYS_ENABLED = [TaskPlugin]  # Always available
```

When a bot is created or updated, only plugins whose capabilities are enabled get instantiated and registered:

```python
def build_registry(ctx: PluginContext, capabilities: dict | None) -> ToolRegistry:
    plugins = _instantiate_plugins(ctx, capabilities)
    return plugins_to_registry(plugins)
```

### 3.3 CachibotAgent

The agent dataclass orchestrates everything:

```python
@dataclass
class CachibotAgent:
    config: Config
    registry: ToolRegistry
    sandbox: PythonSandbox | None
    capabilities: dict | None
    tool_configs: dict | None
    bot_id: str | None

    # Callbacks for UI streaming
    on_thinking: Callable | None
    on_tool_start: Callable | None
    on_tool_end: Callable | None
    on_message: Callable | None
    on_approval_needed: Callable | None
```

**Initialization sequence:**

```
CachibotAgent.__post_init__()
  ├─ _setup_sandbox()
  │    └─ PythonSandbox(allowed_imports, timeout, paths)
  ├─ _build_registry_from_plugins()
  │    ├─ PluginContext(config, sandbox, bot_id, tool_configs)
  │    └─ build_registry(ctx, capabilities)
  │         ├─ Instantiate enabled plugins
  │         └─ registry.add_tukuy_skill() for each skill
  └─ _create_agent()
       ├─ AgentCallbacks from instance callbacks
       ├─ SecurityContext from sandbox
       └─ PromptureAgent(model, tools, callbacks, security_context)
```

### 3.4 Per-Bot Configuration

Each bot carries its own capabilities and tool configurations:

```typescript
{
  id: "bot-abc",
  name: "Security Analyst",
  capabilities: {
    codeExecution: true,
    fileOperations: true,
    gitOperations: false,
    shellAccess: false,
    webAccess: true,
    dataOperations: false,
    connections: true,
    workManagement: true
  },
  toolConfigs: {
    "python_execute": {
      "timeoutSeconds": 60,
      "maxOutputLength": 20000
    }
  },
  tools: ["task_complete", "file_read", "file_write", "python_execute", ...]
}
```

**Resolution order:**
1. **Capabilities** → enable/disable entire plugin groups
2. **Tool Configs** → configure individual tool parameters (fed into `PluginContext`)
3. **Allowed Tools** → fine-grained whitelist on the registry

---

## 4. Frontend — API-Driven UI

The frontend has **zero hardcoded tool metadata**. Everything is driven by the `/api/plugins` endpoint.

### 4.1 Plugin API Response

```
GET /api/plugins
```

```json
{
  "plugins": [
    {
      "name": "file_ops",
      "class": "FileOpsPlugin",
      "capability": "fileOperations",
      "alwaysEnabled": false,
      "displayName": "File Operations",
      "icon": "folder",
      "color": null,
      "group": "Core",
      "skills": [
        {
          "name": "file_read",
          "description": "Read contents of a file",
          "category": "file",
          "tags": ["file", "read", "workspace"],
          "displayName": "Read File",
          "icon": "file-text",
          "riskLevel": "safe",
          "configParams": [],
          "hidden": false,
          "deprecated": null
        },
        {
          "name": "file_write",
          "description": "Write content to a file",
          "displayName": "Write File",
          "icon": "file-plus",
          "riskLevel": "moderate",
          "configParams": [],
          ...
        }
      ]
    },
    {
      "name": "python_sandbox",
      "displayName": "Code Execution",
      "icon": "code",
      "group": "Core",
      "skills": [
        {
          "name": "python_execute",
          "displayName": "Execute Python",
          "icon": "code",
          "riskLevel": "dangerous",
          "configParams": [
            {
              "name": "timeoutSeconds",
              "displayName": "Timeout",
              "type": "number",
              "default": 30,
              "min": 5,
              "max": 120,
              "step": 5,
              "unit": "seconds"
            },
            {
              "name": "maxOutputLength",
              "displayName": "Max Output",
              "type": "number",
              "default": 10000,
              "min": 1000,
              "max": 50000,
              "step": 1000,
              "unit": "chars"
            }
          ]
        }
      ]
    }
  ]
}
```

### 4.2 ToolIconRenderer

Two-tier icon resolution:

1. **API-driven** — `icon` from `SkillDescriptor` → looked up in `lucideIconMap`
2. **Legacy fallback** — `toolId` → looked up in `toolIconMap`

```tsx
<ToolIconRenderer toolId="python_execute" icon="code" size={20} />
```

The `resolveIconName()` export handles plugin header icons from `PluginManifest.icon`.

### 4.3 ToolsView

Fetches plugins → transforms skills to `Tool[]` → groups by plugin → renders:

- Plugin headers with manifest icon and display name
- Tool cards with skill icon, display name, risk badge, toggle
- Category filter chips derived from skill categories
- Search across skill names, descriptions, and tags
- Configure button only appears for tools with `configParams.length > 0`

### 4.4 ToolConfigDialog

Generic configuration form driven entirely by `ConfigParam[]`:

```tsx
// For each param in tool.configParams:
switch (param.type) {
  case 'number':  // Range slider with min/max/step + unit label
  case 'boolean': // Toggle switch
  case 'select':  // Dropdown from param.options[]
  case 'string':  // Text input
}
```

Values are stored per-bot in `bot.toolConfigs[toolId]` and passed through `PluginContext.tool_configs` on the next agent run.

---

## 5. Security Model

Seven layers from UI to execution:

| # | Layer | Where | What it does |
|---|-------|-------|--------------|
| 1 | **Capability gate** | Plugin Manager | Enable/disable plugin categories per bot |
| 2 | **Tool whitelist** | CachibotAgent | `allowed_tools` set filters the registry |
| 3 | **Sandbox** | Prompture | Restrict imports, paths, and timeout for `python_execute` |
| 4 | **SecurityContext** | Prompture → Tukuy | Scope Git/Shell/Web plugins to workspace directory |
| 5 | **Risk analysis** | Prompture | AST analysis flags dangerous code patterns |
| 6 | **Approval flow** | Agent → WebSocket → UI | User confirms high-risk operations before execution |
| 7 | **Config limits** | PluginContext | Enforce timeouts, output length, and other bounds |

---

## 6. Data Flow — End to End

### Tool Execution

```
User types message
  │
  ▼
Frontend sends over WebSocket (/ws)
  │
  ▼
CachibotAgent.run_stream(message)
  │
  ├─► Prompture AsyncAgent calls LLM
  │     LLM returns tool_call: { name: "python_execute", args: { code: "..." } }
  │
  ├─► ToolRegistry dispatches to skill function
  │     ├─ analyze_python(code) → risk assessment
  │     ├─ If HIGH/CRITICAL → ApprovalRequired → on_approval_needed callback
  │     │   └─ Frontend shows confirmation dialog
  │     ├─ PythonSandbox.execute(code, timeout=tool_configs["timeoutSeconds"])
  │     └─ Returns result string
  │
  ├─► Callbacks fire:
  │     on_tool_start("python_execute", {code: "..."}) → WS "tool_start"
  │     on_tool_end("python_execute", result)           → WS "tool_end"
  │
  ├─► LLM receives result, decides next action or final response
  │
  └─► on_message(response) → WS "message"
        Frontend appends to chat history
```

### Plugin Discovery

```
Frontend mounts ToolsView
  │
  ├─► GET /api/plugins
  │     Backend introspects all plugin classes
  │     Extracts PluginManifest + SkillDescriptor metadata
  │     Returns PluginInfo[] with full metadata
  │
  ├─► Frontend maps skills → Tool[] with icons, risk levels, config params
  │
  └─► Renders:
        Plugin groups with manifest headers
        Tool cards with skill metadata
        Config buttons for tools with ConfigParam[]
        Risk badges from RiskLevel
```

---

## 7. Adding a New Plugin

```python
# cachibot/plugins/my_plugin.py
from tukuy.manifest import PluginManifest
from tukuy.skill import skill, RiskLevel, ConfigParam, Skill
from cachibot.plugins.base import CachibotPlugin, PluginContext


class MyPlugin(CachibotPlugin):
    def __init__(self, ctx: PluginContext) -> None:
        super().__init__("my_plugin", ctx)
        self._skills_map = self._build_skills()

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="my_plugin",
            display_name="My Plugin",
            icon="puzzle",
            group="Custom",
        )

    def _build_skills(self) -> dict[str, Skill]:
        ctx = self.ctx

        @skill(
            name="my_tool",
            description="Does something useful",
            category="custom",
            display_name="My Tool",
            icon="zap",
            risk_level=RiskLevel.SAFE,
            config_params=[
                ConfigParam(
                    name="limit",
                    display_name="Result Limit",
                    type="number",
                    default=10,
                    min=1,
                    max=100,
                ),
            ],
        )
        def my_tool(query: str) -> str:
            limit = ctx.tool_configs.get("my_tool", {}).get("limit", 10)
            return f"Results for '{query}' (limit={limit})"

        return {"my_tool": my_tool.__skill__}

    @property
    def skills(self) -> dict[str, Skill]:
        return self._skills_map
```

Register in the plugin manager:

```python
# plugin_manager.py
CAPABILITY_PLUGINS["customFeature"] = [MyPlugin]
```

That's it. The frontend automatically:
- Shows "My Plugin" with a puzzle icon in the Tools view
- Renders "My Tool" with a zap icon and a "safe" badge
- Offers a "Configure" button with a "Result Limit" slider (1–100)
- Saves config per bot and passes it through on the next agent run

---

## 8. Key Files Reference

| File | What it does |
|------|-------------|
| `cachibot/plugins/base.py` | `PluginContext`, `CachibotPlugin` base class |
| `cachibot/plugins/task.py` | `TaskPlugin` — always-on task completion skill |
| `cachibot/plugins/file_ops.py` | `FileOpsPlugin` — file read/write/list/edit/info |
| `cachibot/plugins/python_sandbox.py` | `PythonSandboxPlugin` — sandboxed code execution |
| `cachibot/plugins/platform.py` | `PlatformPlugin` — Telegram & Discord integration |
| `cachibot/plugins/work_management.py` | `WorkManagementPlugin` — work items & todos |
| `cachibot/services/plugin_manager.py` | Capability mapping, instantiation, registry bridge |
| `cachibot/agent.py` | `CachibotAgent` — orchestrates Prompture + plugins |
| `cachibot/api/routes/plugins.py` | `/api/plugins` introspection endpoint |
| `frontend/src/types/index.ts` | `PluginInfo`, `PluginSkillInfo`, `ConfigParam` types |
| `frontend/src/components/views/ToolsView.tsx` | Tool discovery and management UI |
| `frontend/src/components/dialogs/ToolConfigDialog.tsx` | Generic config form from ConfigParam[] |
| `frontend/src/components/common/ToolIconRenderer.tsx` | API-driven icon resolution |
