<p align="center">
  <img width="800"  alt="CachiBot" src="https://github.com/user-attachments/assets/0855ecf4-c0ec-4d81-ad2a-3887d3688cb1" />
</p>

<h1 align="center">CachiBot</h1>

<p align="center">
  <strong>The Armored AI Agent</strong>
</p>

<p align="center">
  <em>Visual. Transparent. Secure.</em>
</p>

<p align="center">
  <a href="https://github.com/jhd3197/cachibot/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License"></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python"></a>
  <a href="https://react.dev"><img src="https://img.shields.io/badge/React-18+-61DAFB.svg" alt="React"></a>
</p>

---

**CachiBot** is a visual AI agent platform with full transparency. Named after the Venezuelan *cachicamo* (armadillo), it's built to be armored, auditable, and yours to control.

## Why Visual?

Most AI agent tools run in terminals where you can't see what's happening. That's a security nightmare.

**The problem with CLI-based agents:**
- You can't see what the agent is doing in real-time
- No visibility into running tasks or jobs
- No way to monitor multiple bots simultaneously
- Actions happen in a black box

**CachiBot gives you full visibility:**
- Watch your bots work in real-time through the dashboard
- See every task, job, and chat in a clean interface
- Monitor connections to Telegram, Discord, and other platforms
- Approve or reject actions before they execute
- Full audit trail of everything your bots do

## Features

- **Visual Dashboard** — See all your bots, their status, and activity at a glance
- **Real-time Monitoring** — Watch tasks and jobs execute with live updates
- **Multi-Bot Management** — Create and manage multiple specialized bots
- **Platform Connections** — Connect bots to Telegram, Discord, and more
- **Knowledge Base** — Upload documents to give bots specialized knowledge
- **Secure Sandbox** — Code runs in isolated environment with restricted imports
- **Approval Flow** — Visual approval for risky operations before they execute
- **Multi-Provider** — Kimi K2.5, Claude, OpenAI, and more

## Quick Start

### 1. Clone and Install

```bash
git clone https://github.com/jhd3197/CachiBot.git
cd CachiBot

# Install backend
pip install -e ".[dev]"

# Install frontend
cd frontend && npm install
```

### 2. Set your API key

```bash
# For Moonshot/Kimi (default)
export MOONSHOT_API_KEY="your-api-key"

# Or for Claude
export ANTHROPIC_API_KEY="your-api-key"

# Or for OpenAI
export OPENAI_API_KEY="your-api-key"
```

### 3. Run CachiBot

```bash
# Terminal 1: Start the backend server
cachibot-server

# Terminal 2: Start the frontend
cd frontend && npm run dev
```

Open **http://localhost:5173** in your browser.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         CachiBot                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  React Dashboard                         │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │    │
│  │  │   Bots   │  │  Chats   │  │   Jobs   │  │ Tasks  │  │    │
│  │  └──────────┘  └──────────┘  └──────────┘  └────────┘  │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │    │
│  │  │ Settings │  │Knowledge │  │    Connections       │  │    │
│  │  └──────────┘  └──────────┘  └──────────────────────┘  │    │
│  └────────────────────────┬────────────────────────────────┘    │
│                           │ WebSocket / REST                     │
│  ┌────────────────────────▼────────────────────────────────┐    │
│  │              FastAPI Backend                             │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐   │    │
│  │  │Prompture │  │  Tools   │  │   Sandbox Executor   │   │    │
│  │  │  Agent   │  │ Registry │  │  (Isolated Python)   │   │    │
│  │  └──────────┘  └──────────┘  └──────────────────────┘   │    │
│  └────────────────────────┬────────────────────────────────┘    │
│                           │                                      │
│  ┌────────────────────────▼────────────────────────────────┐    │
│  │             LLM Providers (via Prompture)                │    │
│  │   Moonshot  │  Claude  │  OpenAI  │  Ollama  │  Groq    │    │
│  └──────────────────────────────────────────────────────────┘    │
│                           │                                      │
│  ┌────────────────────────▼────────────────────────────────┐    │
│  │              Platform Connections                        │    │
│  │         Telegram  │  Discord  │  (more coming)          │    │
│  └──────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## Security

CachiBot is built with security as a core principle:

### Visibility = Security

The biggest security risk with AI agents is not knowing what they're doing. CachiBot solves this by making everything visible:

- **See every action** before it executes
- **Approve or reject** risky operations
- **Full audit trail** of all bot activity
- **Real-time monitoring** of running tasks

### Sandboxed Execution

Python code runs in a **sandboxed environment**:

- **Import Restrictions** — Only safe modules allowed (json, math, datetime, etc.)
- **Path Restrictions** — Can only access files in the workspace
- **Execution Timeout** — Code killed after timeout (default: 30s)
- **Risk Analysis** — AST-based detection of dangerous operations

### Always Blocked

These are never allowed regardless of configuration:
- `subprocess`, `os.system`, `ctypes`
- `socket`, `ssl`, raw network access
- `importlib`, `eval`, `exec` (dynamic code)
- `pickle`, `marshal` (unsafe serialization)

## Supported Models

| Provider | Model | Environment Variable |
|----------|-------|---------------------|
| Moonshot | `moonshot/kimi-k2.5` | `MOONSHOT_API_KEY` |
| Claude | `anthropic/claude-sonnet-4-20250514` | `ANTHROPIC_API_KEY` |
| OpenAI | `openai/gpt-4o` | `OPENAI_API_KEY` |
| Ollama | `ollama/llama3.1:8b` | (local, no key) |
| Groq | `groq/llama-3.1-70b` | `GROQ_API_KEY` |

## Contributing

Contributions are welcome!

```bash
# Clone the repo
git clone https://github.com/jhd3197/CachiBot.git
cd CachiBot

# Install backend in development mode
pip install -e ".[dev]"

# Install frontend dependencies
cd frontend && npm install

# Run tests
pytest

# Lint
ruff check src/
cd frontend && npm run lint
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Credits

- Built with [Prompture](https://github.com/jhd3197/Prompture) for structured LLM interaction
- Named after the Venezuelan *cachicamo* (armadillo)

---

<p align="center">
  Made with care by <a href="https://juandenis.com">Juan Denis</a>
</p>
