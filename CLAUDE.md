# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CachiBot is a security-focused AI agent that uses the Prompture library for structured LLM interactions. It features a Python backend (FastAPI) with WebSocket streaming and a React+TypeScript frontend.

## Common Commands

### Backend Development
```bash
pip install -e ".[dev]"          # Install with dev dependencies
cachibot server                   # Start API server (port 6392)
cachibot "your prompt"            # Run single prompt via CLI
cachibot -i                       # Interactive mode
pytest                            # Run all tests
pytest -v                         # Verbose test output
ruff check .                      # Lint Python code
ruff format .                     # Format Python code
mypy src/cachibot                 # Type check
```

### Frontend Development
```bash
cd frontend
npm install                       # Install dependencies
npm run dev                       # Start Vite dev server (port 5173)
npm run build                     # Production build
npm run lint                      # ESLint
```

The frontend dev server proxies `/api` and `/ws` to `http://127.0.0.1:6392`.

## Architecture

### Backend (`src/cachibot/`)
- **agent.py**: Core `CachibotAgent` dataclass wrapping Prompture's Agent with callbacks, tool registration, and Python sandbox
- **cli.py**: Typer-based CLI with `cachibot` and `cachi` entry points
- **api/server.py**: FastAPI app with lifespan management
- **api/websocket.py**: WebSocket streaming for real-time agent responses
- **api/routes/**: REST endpoints (chat, config, health, models)
- **models/**: Pydantic schemas for chat, config, jobs, websocket messages
- **storage/**: SQLite async database layer with repository pattern

### Frontend (`frontend/src/`)
- **stores/**: Zustand state management with localStorage persistence
  - `bots.ts`: Bot/Chat/Jobs/Tasks stores
  - `ui.ts`: UI state (sidebar, themes)
  - `connections.ts`: API connection state
- **api/**: REST client and WebSocket management
- **components/**: React components organized by feature (chat/, common/, dialogs/, layout/, views/)

### Agent Tool System
Built-in tools registered in `agent.py`:
- `python_execute`: Sandboxed Python execution with AST risk analysis
- `file_read`, `file_write`, `file_list`, `file_edit`: Workspace file operations
- `task_complete`: Signal task completion

### Configuration
Supports TOML config files (`~/.cachibot.toml` or `./cachibot.toml`) with environment variable overrides. See `cachibot.example.toml` for all options.

## Owned Dependencies: Prompture & Tukuy

CachiBot depends on two libraries that we own and maintain: **Prompture** and **Tukuy**. These libraries were built primarily to support CachiBot at a monolithic-repo level.

When a bug or issue is encountered in Prompture or Tukuy while working on CachiBot:

1. **Fix it at the source.** Do NOT work around bugs in CachiBot — fix the actual library code.
2. We own both repos — just go fix it directly, no contribution barriers.
3. After fixing the source library, verify the fix works in CachiBot.

Treat all three repos (CachiBot, Prompture, Tukuy) as a single cohesive codebase.

## Code Style

### Python
- Google-style docstrings
- Type hints required (mypy strict)
- Ruff formatter with line length 100

### TypeScript
- Strict mode enabled
- Path alias: `@/*` maps to `src/*`
- ESLint with React Hooks and React Refresh plugins
