# View-Type Plugins

View plugins embed a custom UI as an iframe in CachiBot's sidebar. Unlike tool plugins (which provide skills for the LLM to call), view plugins provide a standalone web interface that the user navigates to directly.

## When to Use Views

- Custom dashboards or analytics
- Settings panels with complex UIs
- Embedded third-party tools
- Interactive editors that don't fit the artifact model

## Directory Structure

```
~/.cachibot/plugins/my_view/
    __init__.py
    my_view.py
    plugin.toml
    static/
        index.html      <-- Required: the view's entry point
        style.css       <-- Optional: additional assets
        app.js          <-- Optional: additional assets
```

The `static/index.html` file is served by CachiBot at `/api/plugins/<name>/view`.

## Manifest

Set `type = "view"` and add a `[plugin.view]` section:

```toml
[plugin]
name = "my_dashboard"
display_name = "Dashboard"
description = "Custom analytics dashboard"
version = "0.1.0"
type = "view"

[plugin.ui]
icon = "bar-chart"
color = "#8b5cf6"
group = "Analytics"

[plugin.scope]
contexts = ["chat"]

[plugin.view]
route = "dashboard"           # URL: /api/plugins/my_dashboard/view
nav_label = "Dashboard"       # Sidebar navigation label
nav_icon = "bar-chart"        # Lucide icon for the nav item

[plugin.requires]
python = ">=3.10"
filesystem = false
network = false
imports = []

[plugin.permissions]
allow_env_vars = []
allow_paths = []
```

### View Config Fields

| Field       | Type     | Required | Description                              |
|-------------|----------|----------|------------------------------------------|
| `route`     | `string` | Yes      | URL path segment for the view            |
| `nav_label` | `string` | Yes      | Text label in the sidebar navigation     |
| `nav_icon`  | `string` | No       | Lucide icon name (default: `"puzzle"`)   |

## The HTML Entry Point

`static/index.html` is a self-contained HTML page rendered inside a sandboxed iframe. It has no access to the parent page's DOM.

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>My Dashboard</title>
    <style>
        body {
            margin: 0;
            padding: 16px;
            font-family: system-ui, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
        }
        h1 { font-size: 1.25rem; margin-bottom: 1rem; }
    </style>
</head>
<body>
    <h1>Dashboard</h1>
    <div id="app"></div>

    <script>
        // Your application code here
        const app = document.getElementById('app');
        app.textContent = 'Hello from the dashboard plugin!';
    </script>
</body>
</html>
```

## Hybrid Plugins (Tool + View)

A view plugin can also provide tool skills. Set `type = "view"` in the manifest and implement the `skills` property as usual. The plugin will appear both as a navigable view and as a tool provider.

```python
from tukuy.skills import Skill, skill
from cachibot.plugins.base import CachibotPlugin, PluginContext


class DashboardPlugin(CachibotPlugin):
    def __init__(self, ctx: PluginContext) -> None:
        super().__init__("my_dashboard", ctx)
        self._skills_map = self._build_skills()

    @property
    def skills(self) -> dict[str, Skill]:
        return self._skills_map

    def _build_skills(self) -> dict[str, Skill]:
        @skill(name="get_stats", description="Get dashboard statistics.")
        async def get_stats() -> str:
            """Return current statistics."""
            return "Active users: 42, Requests today: 1,337"

        return {"get_stats": get_stats.__skill__}
```

## Communication Between View and Host

The iframe is sandboxed, so direct DOM access to the parent is not possible. If you need to communicate with CachiBot's frontend, use `postMessage`:

```javascript
// Inside your view's index.html
window.parent.postMessage({
    type: 'plugin_event',
    plugin: 'my_dashboard',
    data: { action: 'navigate', target: 'settings' }
}, '*');
```

## Static Asset Serving

All files in the `static/` directory are served relative to the view's endpoint. Reference them with relative paths in your HTML:

```html
<link rel="stylesheet" href="style.css" />
<script src="app.js"></script>
```

Note: Only `index.html` is served through the API endpoint in the current implementation. For additional static assets, inline them in `index.html` or use CDN links.
