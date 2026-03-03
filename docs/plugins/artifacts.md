# Artifacts

Artifacts are rich content blocks that render in a side panel alongside the chat. They enable Canvas-style editing, live HTML previews, diagrams, and any other interactive content.

## How Artifacts Work

1. A skill returns a `dict` containing `"__artifact__": True`.
2. The WebSocket handler auto-detects this marker.
3. The frontend receives an `ARTIFACT` message and opens the side panel with the appropriate renderer.

You never need to call the WebSocket layer directly. Just return the right dict from your skill.

## SDK Helpers

The `cachibot.plugins.sdk` module provides convenience functions that build the correct artifact dict for each type.

```python
from cachibot.plugins.sdk import (
    artifact,           # Generic artifact (any type)
    artifact_update,    # Update an existing artifact
    code_artifact,      # Code with syntax highlighting
    html_artifact,      # Live HTML preview in iframe
    markdown_artifact,  # Rich markdown document
    svg_artifact,       # Inline SVG rendering
    mermaid_artifact,   # Mermaid diagram
    react_artifact,     # React/JSX component preview
    image_artifact,     # Image (data URI or URL)
    custom_artifact,    # Plugin-rendered custom content
)
```

## Artifact Types

### Code

Renders source code with syntax highlighting in an editable panel.

```python
from cachibot.plugins.sdk import code_artifact

@skill(name="create_code", description="Create a code artifact.")
async def create_code(language: str, title: str, content: str) -> dict:
    """Create a code artifact.

    Args:
        language: Programming language (python, typescript, etc.).
        title: Display title.
        content: The source code.
    """
    return code_artifact(
        title=title,          # "main.py"
        content=content,      # The source code
        language=language,    # "python"
        editable=True,        # User can edit in the panel
    )
```

**Parameters:**
| Name          | Type   | Default  | Description                           |
|---------------|--------|----------|---------------------------------------|
| `title`       | `str`  | required | Panel header title                    |
| `content`     | `str`  | required | Source code                           |
| `language`    | `str`  | `"text"` | Language for syntax highlighting      |
| `editable`    | `bool` | `True`   | Whether the user can edit the code    |
| `artifact_id` | `str`  | auto     | Explicit ID (auto-generated if None)  |
| `version`     | `int`  | `1`      | Version number                        |

### HTML

Renders a live HTML preview in a sandboxed iframe. Supports CSS and JavaScript.

```python
from cachibot.plugins.sdk import html_artifact

@skill(name="preview_html", description="Preview HTML in a live iframe.")
async def preview_html(title: str, html_content: str) -> dict:
    """Create an HTML preview.

    Args:
        title: Display title.
        html_content: Complete HTML document.
    """
    return html_artifact(title=title, content=html_content)
```

### Markdown

Renders a rich markdown document with full formatting support.

```python
from cachibot.plugins.sdk import markdown_artifact

@skill(name="create_document", description="Create a markdown document.")
async def create_document(title: str, content: str) -> dict:
    """Create a document artifact.

    Args:
        title: Document title.
        content: Markdown content.
    """
    return markdown_artifact(title=title, content=content)
```

### SVG

Renders SVG graphics inline in the panel.

```python
from cachibot.plugins.sdk import svg_artifact

return svg_artifact(title="Diagram", content="<svg>...</svg>")
```

### Mermaid

Renders Mermaid diagrams (flowcharts, sequence diagrams, etc.).

```python
from cachibot.plugins.sdk import mermaid_artifact

return mermaid_artifact(
    title="Architecture",
    content="""
    graph TD
        A[Client] --> B[API Server]
        B --> C[Database]
        B --> D[Cache]
    """,
)
```

### React

Renders a React/JSX component in a live preview.

```python
from cachibot.plugins.sdk import react_artifact

return react_artifact(
    title="Counter Component",
    content="""
    export default function Counter() {
        const [count, setCount] = React.useState(0);
        return <button onClick={() => setCount(c => c + 1)}>Count: {count}</button>;
    }
    """,
)
```

### Image

Displays an image from a data URI or URL.

```python
from cachibot.plugins.sdk import image_artifact

return image_artifact(
    title="Generated Image",
    content="data:image/png;base64,...",
    metadata={"width": 512, "height": 512, "format": "png"},
)
```

### Custom

Custom artifacts are rendered by a plugin-provided iframe renderer. Use this when none of the built-in types fit.

```python
from cachibot.plugins.sdk import custom_artifact

return custom_artifact(
    title="3D Model",
    content=model_data,
    plugin="my_3d_viewer",  # Plugin name providing the renderer
    metadata={"format": "gltf"},
)
```

## Updating Artifacts

Use `artifact_update()` to modify an existing artifact without replacing it entirely. The user sees the update reflected in the already-open panel.

```python
from cachibot.plugins.sdk import artifact_update

@skill(name="update_code", description="Update existing code.")
async def update_code(artifact_id: str, content: str, version: int = 2) -> dict:
    """Update an existing code artifact.

    Args:
        artifact_id: ID of the artifact to update.
        content: Updated source code.
        version: New version number (should increment).
    """
    return artifact_update(
        artifact_id=artifact_id,
        content=content,
        version=version,
    )
```

The update dict uses the marker `"__artifact_update__": True` (detected automatically by the WebSocket handler).

**Parameters:**
| Name          | Type          | Description                              |
|---------------|---------------|------------------------------------------|
| `artifact_id` | `str`        | ID of the existing artifact              |
| `content`     | `str\|None`  | New content (replaces existing)          |
| `title`       | `str\|None`  | New title                                |
| `metadata`    | `dict\|None` | Metadata to merge with existing          |
| `version`     | `int\|None`  | New version number                       |

Only provided fields are updated. Omitted fields remain unchanged.

## The Generic `artifact()` Function

All the typed helpers (`code_artifact`, `html_artifact`, etc.) are thin wrappers around the generic `artifact()` function. Use it directly when you need full control:

```python
from cachibot.plugins.sdk import artifact

return artifact(
    type="code",                    # Any ArtifactType value
    title="My Artifact",
    content="...",
    language="python",              # Optional, for code artifacts
    metadata={"editable": True},    # Type-specific metadata
    plugin="my_plugin",             # For custom artifacts
    artifact_id="custom-id-123",    # Optional explicit ID
    version=1,
)
```

## Artifact Dict Structure

For reference, the dict returned by SDK helpers has this shape:

```python
{
    "__artifact__": True,       # Marker for WS handler detection
    "id": "uuid-string",       # Auto-generated or explicit
    "type": "code",            # Artifact type
    "title": "main.py",        # Panel header title
    "content": "print('hi')",  # The content
    "language": "python",      # Optional
    "metadata": {},            # Optional
    "plugin": None,            # Optional (for custom types)
    "version": 1,              # Version number
}
```

Update dicts have a similar shape but use `"__artifact_update__": True` and only include changed fields.

## Artifact Model

On the backend, artifacts are also represented as Pydantic models (`cachibot.models.artifact.Artifact` and `ArtifactUpdate`) for validation and database storage. The SDK helpers produce plain dicts for simplicity, but they are validated against the same schema before being sent over the WebSocket.

### Supported Types (enum)

```
code | html | markdown | svg | mermaid | react | image | custom
```
