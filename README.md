<div align="center">
  <img src="assets/hero.png" alt="CachiBot" width="800" />

  <h1>CachiBot</h1>

  <p><strong>The Armored AI Agent</strong></p>
  <p><em>Visual. Transparent. Secure.</em></p>

  <p>
    <a href="https://cachibot.ai">Website</a> ·
    <a href="docs/README.es.md">Español</a> ·
    <a href="docs/README.zh-CN.md">中文版</a> ·
    <a href="docs/README.pt.md">Português</a>
  </p>

  <p>
    <img src="https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white" alt="Windows" />
    <img src="https://img.shields.io/badge/macOS-000000?style=for-the-badge&logo=apple&logoColor=white" alt="macOS" />
    <img src="https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black" alt="Linux" />
  </p>

  <p>
    <a href="https://pypi.org/project/cachibot"><img src="https://img.shields.io/pypi/v/cachibot.svg" alt="PyPI" /></a>
    <a href="https://pypi.org/project/cachibot"><img src="https://img.shields.io/pypi/dm/cachibot.svg" alt="Downloads" /></a>
    <a href="https://github.com/jhd3197/CachiBot/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License" /></a>
    <a href="https://python.org"><img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python" /></a>
    <a href="https://react.dev"><img src="https://img.shields.io/badge/React-18+-61DAFB.svg" alt="React" /></a>
    <a href="https://github.com/jhd3197/CachiBot/stargazers"><img src="https://img.shields.io/github/stars/jhd3197/CachiBot?style=social" alt="Stars" /></a>
    <a href="https://discord.gg/V9bKwYVJ"><img src="https://img.shields.io/discord/1470624345188732992?label=Discord&logo=discord&logoColor=white&color=5865F2" alt="Discord" /></a>
  </p>

  <p>
    A visual AI agent platform with full transparency. Named after the Venezuelan <em>cachicamo</em> (armadillo) — built to be armored, auditable, and yours to control.
  </p>

  <p>
    <a href="#-install">Install</a> ·
    <a href="#-features">Features</a> ·
    <a href="#-architecture">Architecture</a> ·
    <a href="#-security">Security</a> ·
    <a href="#-contributing">Contributing</a> ·
    <a href="https://discord.gg/V9bKwYVJ">Discord</a>
  </p>

</div>

---

## Why CachiBot?

Most AI platforms force you to choose: chatbot UIs with no automation, workflow builders with no conversational AI, or developer frameworks that take weeks to ship.

**CachiBot gives you all three.** Build specialized bots, deploy them to any messaging platform, run them in collaborative rooms, and automate workflows — all from a visual dashboard with full transparency into what your agents are doing.


![arepa-war](https://github.com/user-attachments/assets/5996fc02-0c4c-4a61-a998-f007189494fd)

<p align="center">
  <a href="https://youtu.be/G8JEhkcRxD8">
    <img src="https://img.shields.io/badge/YouTube-Watch_Demo-red?style=for-the-badge&logo=youtube&logoColor=white" alt="Watch on YouTube" />
  </a>
  <a href="https://cachibot.ai/marketplace/rooms/great-arepa-war?utm_source=github&utm_medium=readme&utm_campaign=arepa_war_room">
    <img src="https://img.shields.io/badge/CachiBot-View_Room-blue?style=for-the-badge&logo=google-chrome&logoColor=white" alt="View the Chat on CachiBot" />
  </a>
  <a href="https://dev.to/juandenis/ai-settles-the-ultimate-venezuelan-vs-colombian-arepa-debate-2ngm">
    <img src="https://img.shields.io/badge/Dev.to-Read_Article-0A0A0A?style=for-the-badge&logo=devdotto&logoColor=white" alt="Read on Dev.to" />
  </a>
</p>

## Install

### Linux / macOS

```bash
curl -fsSL cachibot.ai/install.sh | bash
```

Sets up Python, a virtual environment, and a systemd service — everything you need in one command.

### Windows

```powershell
irm cachibot.ai/install.ps1 | iex
```

### pip

```bash
pip install cachibot
```

Then start the server:

```bash
cachibot server
```

Open **http://localhost:5870** — the frontend is bundled and served automatically. No separate build step.

### Configure your API keys

You can set API keys directly from the dashboard UI — no environment variables required. Just open the settings panel and add your keys there.

If you prefer environment variables, those work too:

```bash
export OPENAI_API_KEY="your-key"       # OpenAI / GPT-4
export ANTHROPIC_API_KEY="your-key"    # Claude
export MOONSHOT_API_KEY="your-key"     # Kimi
# or use Ollama locally (no key needed)
```

### CLI Usage

```bash
cachibot server                    # Start the dashboard
cachibot "summarize this project"  # Run a single task
cachibot                           # Interactive mode
cachi server                       # Short alias
```

## Features

### Multi-Agent Platform

- **Unlimited Specialized Bots** — Create bots with custom system prompts, tool selections, and model routing
- **Collaborative Rooms** — Run 2-4 bots together in real-time to solve complex tasks
- **Bot Marketplace** — Pre-built templates for common use cases (code review, data analysis, writing, support)

### Platform Integrations

Deploy bots to **7 messaging platforms** with built-in adapters:

Telegram · Discord · Slack · Microsoft Teams · WhatsApp · Viber · LINE

### Multimodal AI

- **Voice Conversations** — Talk to your bots with real-time speech-to-text and text-to-speech
- **Image Generation** — DALL-E, Google Imagen, Stability AI, Grok
- **Audio Synthesis** — OpenAI TTS, ElevenLabs
- **12+ LLM Providers** — Claude, GPT-4, Kimi, Gemini, Ollama, Groq, and more

### 50+ Built-in Tools

Powered by [Tukuy](https://github.com/jhd3197/Tukuy) plugins:

- File operations, sandboxed Python execution, web search
- Knowledge base with vector search and document upload
- Task management, scheduling (cron, interval, event-triggered), background jobs
- Git operations, HTTP requests, SQL queries
- Reusable functions with step-level dependencies and retries

### Security & Control

- **Visual Approval Flows** — Approve or reject risky operations before they execute
- **Sandboxed Execution** — Python runs in isolation with AST-based risk analysis
- **Workspace Isolation** — All file access scoped to the workspace
- **Full Audit Trail** — Every action logged and visible in the dashboard

## What Can You Build?

- **Customer Support Bot** — Deploy to Telegram with a knowledge base of your docs, auto-answer FAQs
- **Data Analysis Room** — 3 bots (SQL specialist + Python analyst + report writer) collaborating on insights
- **Voice Assistant** — Talk to a bot with STT/TTS, manage tasks and reminders hands-free
- **Content Pipeline** — Research bot + writer bot + image generator producing blog posts end-to-end
- **DevOps Agent** — Monitor repos, run sandboxed scripts, send alerts to Slack on schedule

## Architecture

```mermaid
graph TB
    subgraph Frontend["React Dashboard"]
        Bots[Bots & Rooms]
        Chats[Chats & Voice]
        Work[Jobs, Tasks & Schedules]
        KB[Knowledge Base]
        Market[Marketplace]
    end

    subgraph Backend["FastAPI Backend"]
        Agent["Prompture Agent"]
        Plugins["Tukuy Plugin System"]
        Sandbox["Python Sandbox"]
        Auth["Auth & RBAC"]
        Scheduler["Scheduler Service"]
    end

    subgraph Providers["AI Providers"]
        LLM["LLMs (Claude, GPT-4, Kimi, Ollama, Groq, ...)"]
        ImgGen["Image Gen (DALL-E, Imagen, Stability)"]
        Audio["Audio (Whisper, ElevenLabs)"]
    end

    subgraph Platforms["Platform Integrations"]
        TG[Telegram]
        DC[Discord]
        SL[Slack]
        TM[Teams]
        WA[WhatsApp]
        VB[Viber]
        LN[LINE]
    end

    Frontend -- "WebSocket / REST" --> Backend
    Backend --> Providers
    Backend --> Platforms
```

## Supported Providers

CachiBot uses [Prompture](https://github.com/jhd3197/Prompture) for model management with auto-discovery — set an API key and available models appear automatically.

| Provider | Example Models | Environment Variable |
|----------|---------------|---------------------|
| OpenAI | GPT-4o, GPT-4, o1 | `OPENAI_API_KEY` |
| Anthropic | Claude Sonnet, Opus, Haiku | `ANTHROPIC_API_KEY` |
| Moonshot | Kimi K2.5 | `MOONSHOT_API_KEY` |
| Google | Gemini Pro, Flash | `GOOGLE_API_KEY` |
| Groq | Llama 3, Mixtral | `GROQ_API_KEY` |
| Grok/xAI | Grok-2 | `GROK_API_KEY` |
| Ollama | Any local model | *(no key needed)* |

All keys can also be configured from the dashboard UI without touching environment variables.

## Security

CachiBot is built with security as a core principle. **Visibility is security** — the biggest risk with AI agents is not knowing what they're doing.

### Sandboxed Execution

Python code runs in a restricted environment:

- **Import Restrictions** — Only safe modules allowed (json, math, datetime, etc.)
- **Path Restrictions** — File access limited to the workspace via SecurityContext
- **Execution Timeout** — Code killed after timeout (default: 30s)
- **Risk Analysis** — AST-based scoring (SAFE / MODERATE / DANGEROUS) before execution
- **Approval Flow** — Dangerous operations require explicit approval through the dashboard

### Always Blocked

These are never allowed regardless of configuration: `subprocess`, `os.system`, `ctypes`, `socket`, `ssl`, `importlib`, `eval`, `exec`, `pickle`, `marshal`.

## Roadmap

- [x] Visual dashboard with real-time monitoring
- [x] Multi-bot management with marketplace templates
- [x] Sandboxed Python execution with AST risk analysis
- [x] Multi-provider LLM support (12+ providers)
- [x] Knowledge base with vector search and document upload
- [x] 7 platform integrations (Telegram, Discord, Slack, Teams, WhatsApp, Viber, LINE)
- [x] Plugin system with 50+ tools (via Tukuy)
- [x] Multi-agent collaborative rooms
- [x] Voice conversations (STT/TTS)
- [x] Image and audio generation
- [x] Background jobs with cron/interval/event scheduling
- [x] Work management (tasks, todos, functions)
- [x] Authentication and role-based access control
- [ ] Mobile companion app

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide. Quick start:

```bash
git clone https://github.com/jhd3197/CachiBot.git
cd CachiBot

# Backend
python -m venv venv && source venv/bin/activate  # or .\venv\Scripts\activate on Windows
pip install -e ".[dev]"

# Frontend
cd frontend && npm install && cd ..

# Desktop (optional — only if working on the Electron shell)
cd desktop && npm install && cd ..

# Run everything
bash dev.sh              # or .\dev.ps1 on Windows
bash dev.sh desktop      # with Electron
bash dev.sh watch-lint   # lint watcher (ruff + ESLint on save)
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for all dev script modes, project structure, testing, and code style guidelines.

## Community

<p align="center">
  <a href="https://cachibot.ai">
    <img src="https://img.shields.io/badge/Website-cachibot.ai-blue?style=for-the-badge&logo=google-chrome&logoColor=white" alt="Website" />
  </a>
  <a href="https://discord.gg/V9bKwYVJ">
    <img src="https://img.shields.io/badge/Discord-Join_the_community-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord" />
  </a>
  <a href="https://github.com/jhd3197/CachiBot/issues">
    <img src="https://img.shields.io/badge/Issues-Report_a_bug-red?style=for-the-badge&logo=github&logoColor=white" alt="Issues" />
  </a>
</p>

## License

MIT License — see [LICENSE](LICENSE) for details.

## Credits

- Built with [Prompture](https://github.com/jhd3197/Prompture) for structured LLM interaction and multimodal drivers
- Plugin system powered by [Tukuy](https://github.com/jhd3197/Tukuy)
- Named after the Venezuelan *cachicamo* (armadillo)

---

<p align="center">
  Made with care by <a href="https://juandenis.com">Juan Denis</a>
</p>
