# Contributing to CachiBot

Thank you for your interest in contributing to CachiBot!

## Prerequisites

| Tool | Version | Check |
|------|---------|-------|
| Python | 3.10+ | `python --version` |
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |
| Git | any | `git --version` |

## Development Setup

### 1. Clone the repository

```bash
git clone https://github.com/jhd3197/CachiBot.git
cd CachiBot
```

### 2. Backend (Python / FastAPI)

```bash
# Create and activate a virtual environment
python -m venv venv

# Windows PowerShell
.\venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# Install in dev mode with all dependencies
pip install -e ".[dev]"
```

### 3. Frontend (React / TypeScript)

```bash
cd frontend
npm install
cd ..
```

### 4. Desktop (Electron) — optional

Only needed if you're working on the Electron shell.

```bash
cd desktop
npm install
cd ..
```

### 5. Configure API keys

You can set API keys from the dashboard UI, or via environment variables:

```bash
# Windows PowerShell
$env:OPENAI_API_KEY = "your-key"
$env:ANTHROPIC_API_KEY = "your-key"

# macOS / Linux
export OPENAI_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"
```

## Running in Development

Use the dev script to start everything with a single command:

### Windows (PowerShell)

```powershell
.\dev.ps1                  # backend + frontend (browser)
.\dev.ps1 backend          # backend only
.\dev.ps1 frontend         # frontend only (Vite dev server)
.\dev.ps1 desktop          # backend + frontend + Electron
.\dev.ps1 all              # backend + frontend + Electron
.\dev.ps1 watch-lint       # watch Python + TS files, lint on changes
```

### macOS / Linux

```bash
bash dev.sh                # backend + frontend (browser)
bash dev.sh backend        # backend only
bash dev.sh frontend       # frontend only (Vite dev server)
bash dev.sh desktop        # backend + frontend + Electron
bash dev.sh all            # backend + frontend + Electron
bash dev.sh watch-lint     # watch Python + TS files, lint on changes
```

### Running services individually

If you prefer to run things in separate terminals:

```bash
# Terminal 1 — Backend (port 5870)
cachibot server --port 5870 --reload

# Terminal 2 — Frontend (port 5173, proxies API to backend)
cd frontend && npm run dev

# Terminal 3 — Electron (optional, loads from Vite for hot reload)
cd desktop && set ELECTRON_DEV_URL=http://localhost:5173 && npx electron .
```

### What each mode does

| Mode | Backend (5870) | Vite (5173) | Electron | Use case |
|------|:-:|:-:|:-:|------|
| `browser` | x | x | | Frontend/backend work, open browser to localhost:5173 |
| `backend` | x | | | API-only work, testing endpoints |
| `frontend` | | x | | UI-only work (needs backend running separately) |
| `desktop` | x | x | x | Electron shell work with hot reload |
| `all` | x | x | x | Full stack with browser + Electron |
| `watch-lint` | | | | Watches Python + TypeScript files, runs ruff + ESLint on changes |

## Project Structure

```
CachiBot/
├── cachibot/          # Python backend (FastAPI)
│   ├── agent.py           #   Core agent with tool registration
│   ├── cli.py             #   CLI entry point (cachibot / cachi)
│   ├── api/               #   REST + WebSocket endpoints
│   ├── models/            #   Pydantic schemas
│   └── storage/           #   SQLite async data layer
├── frontend/              # React + TypeScript frontend
│   └── src/
│       ├── api/           #   REST client + WebSocket
│       ├── components/    #   UI components
│       └── stores/        #   Zustand state management
├── desktop/               # Electron shell
│   ├── main.js            #   Main process
│   └── preload.js         #   Preload script (IPC bridge)
├── dev.ps1                # Dev launcher (Windows)
├── dev.sh                 # Dev launcher (macOS/Linux)
└── pyproject.toml         # Python project config
```

## Development Workflow

### Tests

```bash
pytest                     # Run all tests
pytest -v                  # Verbose output
pytest tests/test_agent.py # Run a specific file
```

### Linting & Formatting

```bash
# Python
ruff check src/            # Lint
ruff format src/           # Format

# TypeScript
cd frontend && npm run lint

# Type checking
mypy cachibot
```

## Code Style

### Python

- [Ruff](https://github.com/astral-sh/ruff) for linting and formatting (line length: 100)
- Type hints required for all public functions
- Google-style docstrings

```python
def process_file(path: str, encoding: str = "utf-8") -> str:
    """Process a file and return its contents.

    Args:
        path: Path to the file to process.
        encoding: File encoding (default: utf-8).

    Returns:
        The processed file contents.

    Raises:
        FileNotFoundError: If the file doesn't exist.
    """
    ...
```

### TypeScript

- Strict mode enabled
- ESLint with React Hooks and React Refresh plugins
- Path alias: `@/*` maps to `src/*`

## Adding New Tools

Tools are the actions CachiBot can take. To add a new tool:

1. Create a new file in `cachibot/tools/`
2. Inherit from `BaseTool`
3. Implement the `execute` method
4. Register in `agent.py`

```python
from cachibot.tools import BaseTool, ToolResult

class MyTool(BaseTool):
    name = "my_tool"
    description = "Does something useful"

    def execute(self, param1: str, **kwargs) -> ToolResult:
        try:
            # Do something
            return ToolResult.ok("Success!")
        except Exception as e:
            return ToolResult.fail(str(e))
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and linting
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to your fork (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### PR Guidelines

- Keep PRs focused on a single feature or fix
- Update documentation if needed
- Add tests for new functionality
- Follow existing code style

## Reporting Issues

When reporting issues, please include:

- Python version and OS
- Node.js version (if frontend related)
- Steps to reproduce
- Expected vs actual behavior
- Any error messages or logs

## Questions?

Feel free to open an issue or join the [Discord](https://discord.gg/Xzw45fGhqq).

---

Made with care by [Juan Denis](https://juandenis.com)
