# Plugin Manifest Reference (`plugin.toml`)

Every plugin requires a `plugin.toml` file at its root. This file declares the plugin's identity, requirements, permissions, UI presentation, and configurable parameters.

## Full Annotated Example

```toml
# ─── Identity ───────────────────────────────────────────────
[plugin]
name = "website_builder"             # Unique identifier (snake_case, required)
display_name = "Website Builder"     # Human-readable name for the UI
description = "Generate websites via multi-agent pipeline"
version = "0.1.0"                    # Semver string
author = "CachiBot Team"
type = "tool"                        # "tool" or "view"

# ─── UI Presentation ────────────────────────────────────────
[plugin.ui]
icon = "globe"                       # Lucide icon name
color = "#3b82f6"                    # Hex color for the plugin badge
group = "Creative"                   # Grouping in the Plugins panel

# ─── Scope ──────────────────────────────────────────────────
[plugin.scope]
contexts = ["chat", "room"]          # Where the plugin is available
allow_late_activation = false         # Can the user toggle this on mid-chat?

# ─── Requirements ───────────────────────────────────────────
[plugin.requires]
python = ">=3.10"                    # Python version constraint
filesystem = true                    # Whether the plugin needs file access
network = true                       # Whether the plugin needs network access
imports = ["agentsite"]              # Python packages that must be importable

# ─── Permissions ────────────────────────────────────────────
[plugin.permissions]
allow_env_vars = ["OPENAI_API_KEY"]  # Environment variables the plugin may read
allow_paths = ["~/.cachibot/websites"]  # Filesystem paths the plugin may access

# ─── View Config (view-type plugins only) ───────────────────
# [plugin.view]
# route = "my-view"                  # URL path segment: /plugins/<route>
# nav_label = "My View"              # Sidebar navigation label
# nav_icon = "puzzle"                # Lucide icon for the nav item

# ─── Configurable Parameters ────────────────────────────────
[[plugin.config]]
name = "model"
display_name = "Model"
type = "text"
default = ""
description = "LLM model for the generation pipeline"

[[plugin.config]]
name = "maxCost"
display_name = "Max Cost"
type = "number"
default = 0
description = "Maximum cost in USD (0 = no limit)"
```

## Section Reference

### `[plugin]` -- Identity

| Field          | Type     | Required | Default   | Description                              |
|----------------|----------|----------|-----------|------------------------------------------|
| `name`         | `string` | Yes      | --        | Unique plugin identifier (snake_case)    |
| `display_name` | `string` | No       | `name`    | Human-readable name shown in the UI      |
| `description`  | `string` | No       | `""`      | Short description                        |
| `version`      | `string` | No       | `"0.1.0"` | Semver version string                    |
| `author`       | `string` | No       | `""`      | Plugin author                            |
| `type`         | `string` | No       | `"tool"`  | Plugin type: `"tool"` or `"view"`        |

The `name` field must be unique across all installed plugins and must not conflict with built-in plugin names.

### `[plugin.ui]` -- UI Presentation

| Field   | Type     | Default     | Description                                   |
|---------|----------|-------------|-----------------------------------------------|
| `icon`  | `string` | `"puzzle"`  | Icon name from [Lucide Icons](https://lucide.dev) |
| `color` | `string` | `"#6b7280"` | Hex color for the plugin badge/accent         |
| `group` | `string` | `"External"` | Category group in the Plugins panel          |

### `[plugin.scope]` -- Availability

| Field                    | Type       | Default    | Description                                                        |
|--------------------------|------------|------------|--------------------------------------------------------------------|
| `contexts`               | `string[]` | `["chat"]` | Where the plugin is available: `"chat"`, `"room"`, or both         |
| `allow_late_activation`  | `bool`     | `false`    | Whether the plugin can be toggled on after the chat has started     |

#### Late activation behavior

By default, plugins must be enabled **before** the first message is sent. Once a chat is active, only plugins that were already toggled on are shown in the input area — this prevents users from accidentally opting into a heavy plugin (e.g. Website Builder) mid-conversation.

Set `allow_late_activation = true` for lightweight plugins that make sense to add at any point during a chat. When `false` (the default), the plugin chip is hidden from the input bar once the conversation has messages, unless it was already active.

### `[plugin.requires]` -- Runtime Requirements

| Field        | Type       | Default    | Description                                         |
|--------------|------------|------------|-----------------------------------------------------|
| `python`     | `string`   | `">=3.10"` | Python version constraint (PEP 440)                 |
| `filesystem` | `bool`     | `false`    | Whether the plugin needs filesystem access           |
| `network`    | `bool`     | `false`    | Whether the plugin needs network access              |
| `imports`    | `string[]` | `[]`       | Python packages that must be importable at load time |

If any package in `imports` is not installed, the plugin is marked as errored but still visible in the UI (so the user knows what to install).

### `[plugin.permissions]` -- Security Declarations

| Field            | Type       | Default | Description                                       |
|------------------|------------|---------|---------------------------------------------------|
| `allow_env_vars` | `string[]` | `[]`    | Environment variables the plugin may read          |
| `allow_paths`    | `string[]` | `[]`    | Filesystem paths the plugin may access             |

System-level environment variables (`PATH`, `HOME`, `USERPROFILE`, `SYSTEMROOT`, `COMSPEC`) are always blocked.

### `[plugin.view]` -- View Configuration

Only used when `type = "view"`. Tells the frontend how to mount the plugin's iframe.

| Field       | Type     | Default    | Description                              |
|-------------|----------|------------|------------------------------------------|
| `route`     | `string` | (required) | URL path segment for the view            |
| `nav_label` | `string` | (required) | Label shown in the sidebar navigation    |
| `nav_icon`  | `string` | `"puzzle"` | Lucide icon for the navigation item      |

### `[[plugin.config]]` -- Configurable Parameters

Use TOML's array-of-tables syntax (`[[plugin.config]]`) to declare user-configurable parameters. Each entry creates a settings field in the plugin's configuration panel.

| Field          | Type                       | Default | Description                        |
|----------------|----------------------------|---------|------------------------------------|
| `name`         | `string`                   | --      | Parameter identifier               |
| `display_name` | `string`                   | `""`    | Label shown in the settings UI     |
| `type`         | `string`                   | `"text"` | Input type (see table below)      |
| `default`      | `string\|int\|float\|bool` | `null`  | Default value                      |
| `description`  | `string`                   | `""`    | Help text shown below the input    |

#### Supported config `type` values

| Type       | UI Element  | Value Type     |
|------------|-------------|----------------|
| `text`     | Text input  | `string`       |
| `number`   | Number input | `int\|float`  |
| `boolean`  | Toggle      | `bool`         |
| `select`   | Dropdown    | `string`       |
| `secret`   | Password    | `string`       |
| `path`     | Path picker | `string`       |
| `url`      | URL input   | `string`       |

## Capability Key

Every external plugin gets an auto-generated capability key: `ext_<name>`. This key is used internally to gate plugin access per-bot. For example, a plugin named `website_builder` gets the capability key `ext_website_builder`.

## Minimal Manifest

The absolute minimum `plugin.toml`:

```toml
[plugin]
name = "my_plugin"
```

All other fields have sensible defaults. However, for production plugins, specifying at least `display_name`, `description`, `type`, and `[plugin.requires]` is recommended.
