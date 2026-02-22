# Per-Bot Environment Variable System — Complete Architecture

**Date**: 2026-02-16
**Status**: Implemented (Phase 1 — no Prompture/Tukuy changes needed)
**Scope**: CachiBotV2, Prompture, Tukuy, CachiBot Website

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current State Analysis](#2-current-state-analysis)
   - 2.1 [CachiBotV2 Config Architecture](#21-cachibotv2-config-architecture)
   - 2.2 [Prompture Provider Configuration](#22-prompture-provider-configuration)
   - 2.3 [Tukuy Skills and Config Handling](#23-tukuy-skills-and-config-handling)
3. [Architecture Design](#3-architecture-design)
   - 3.1 [Scope Layers](#31-scope-layers)
   - 3.2 [Database Schema](#32-database-schema)
   - 3.3 [Config Resolution Service](#33-config-resolution-service)
   - 3.4 [Prompture Integration](#34-prompture-integration)
   - 3.5 [Tukuy Integration](#35-tukuy-integration)
   - 3.6 [API Design](#36-api-design)
   - 3.7 [Admin/User UI](#37-adminuser-ui)
4. [Security Design](#4-security-design)
   - 4.1 [Current Vulnerability Audit](#41-current-vulnerability-audit)
   - 4.2 [Encryption Design](#42-encryption-design)
   - 4.3 [Access Control](#43-access-control)
   - 4.4 [Isolation Design](#44-isolation-design)
   - 4.5 [Inheritance Security](#45-inheritance-security)
   - 4.6 [Multi-Tenant Patterns](#46-multi-tenant-patterns-industry-research)
   - 4.7 [Key Rotation and Backup](#47-key-rotation-and-backup)
   - 4.8 [Logging and Audit](#48-logging-and-audit)
5. [Integration Design](#5-integration-design)
   - 5.1 [Request Lifecycle](#51-full-request-lifecycle-with-per-bot-env)
   - 5.2 [Error Scenarios](#52-error-scenarios)
   - 5.3 [Concurrency and Isolation](#53-concurrency--isolation)
   - 5.4 [Hot Reload](#54-hot-reload)
   - 5.5 [Tier System Integration](#55-tier-system-integration)
   - 5.6 [Adapter Registry Integration](#56-adapter-registry-integration)
   - 5.7 [Discovery Per-Bot](#57-discovery-per-bot)
   - 5.8 [Sequence Diagrams](#58-sequence-diagrams)
6. [Implementation Plan](#6-implementation-plan)
   - 6.1 [Prompture Changes](#61-prompture-changes)
   - 6.2 [Tukuy Changes](#62-tukuy-changes)
   - 6.3 [CachiBotV2 Changes](#63-cachibotv2-changes)
   - 6.4 [CachiBot Website Changes](#64-cachibot-website-changes)
   - 6.5 [Dependency Order](#65-dependency-order)
   - 6.6 [Migration Plan](#66-migration-plan)
7. [Summary](#7-summary)

---

## 1. Executive Summary

This document defines a complete per-bot environment variable system for the CachiBot ecosystem. Currently, all bots share the same global API keys and configuration from a single `.env` file. This architecture enables each bot to have its own isolated environment — its own API keys, model preferences, temperature settings, and skill configurations — while maintaining backward compatibility.

**Key findings:**

- **Prompture and Tukuy need ZERO changes for v1** — CachiBotV2 can use existing injection points (`AsyncAgent(driver=...)` and `SkillContext.config`) to wire everything up.
- **Tukuy is 80% ready** — `ConfigParam(scope=ConfigScope.PER_BOT)` metadata, `SkillContext.config`, and `contextvars`-based security context are all in place.
- **Prompture drivers are stateless** — each driver instance has its own `api_key`, so per-bot drivers already work via direct construction.
- **The only major work is in CachiBotV2** — database tables, encryption service, environment resolution, and API endpoints.

---

## 2. Current State Analysis

### 2.1 CachiBotV2 Config Architecture

#### Environment Loading

**No python-dotenv is used in the Python backend.** The `.env` file is only loaded by:
- The desktop Electron app (via `dotenv` npm package)
- Docker Compose's implicit `.env` file loading for `${VAR:-}` substitution

The Python backend reads environment variables via `os.getenv()` only. API keys are loaded into `os.environ` in two ways:
1. **From the `.env` file directly** by the providers API endpoint (`/api/providers`), which reads the `.env` file with `_read_env_file()` and sets `os.environ[key] = value` when listing providers (`cachibot/api/routes/providers.py:124-125`)
2. **From the process environment** — whatever the OS/Docker/Electron sets

The providers endpoint also **writes** directly to the `.env` file via `_set_env_value()` when a user updates an API key through the UI.

**Critical: `ENV_PATH = Path.cwd() / ".env"` is defined at module level** — this is always relative to CWD.

#### Configuration Loading Chain

The `Config` class (dataclass) loads in this order (later overrides earlier):
1. **Defaults** (hardcoded in dataclasses) — e.g., model defaults to `"moonshot/kimi-k2.5"`
2. **Environment variables** (`_load_from_env()`) — `CACHIBOT_MODEL`, `CACHIBOT_TEMPERATURE`, etc.
3. **User config** (`~/.cachibot.toml`)
4. **Workspace config** (`./cachibot.toml`)
5. **Explicit config file** (CLI `--config` flag)

#### Bot Model / Database Schema

The Bot table (`storage/models/bot.py`) has these fields:
- `id` (str, PK)
- `name` (str)
- `description` (text, nullable)
- `icon` (str, nullable)
- `color` (str, nullable)
- `model` (str) — e.g., "moonshot/kimi-k2.5"
- `system_prompt` (text) — custom system prompt
- `capabilities` (JSON) — dict of capability toggles like `{"fileOperations": true}`
- `models` (JSON, nullable) — multi-model slot config: `{"default": "...", "image": "...", "audio": "..."}`
- `created_at`, `updated_at`

The `BotOwnership` table links bots to users (one owner per bot).

#### API Key Sharing — ALL BOTS SHARE THE SAME KEYS

**This is the central problem.** The key flow:
1. API keys are stored in the single `.env` file and/or process environment
2. The `PROVIDERS` dict maps provider names to env var names: `"openai" -> "OPENAI_API_KEY"`, etc.
3. When a user sets a key via the UI (`PUT /api/providers/{name}`), it writes to `.env` and `os.environ`
4. Prompture reads these env vars directly from `os.environ`
5. **There is NO per-bot key storage whatsoever**

#### Bot Settings Isolation — What's Isolated vs Shared

**PER-BOT (already isolated):**
- `model` — each bot can have a different model
- `models` — multi-model slots (default, image, audio, structured)
- `system_prompt` — each bot has its own personality/instructions
- `capabilities` — each bot's tool toggles
- `name`, `description`, `icon`, `color` — identity
- Platform connections (`bot_connections` table) — each bot has its own Telegram/Discord/etc. connections with per-bot tokens
- Skills — each bot can activate different skills
- Knowledge base — documents and instructions are per-bot
- Chat history — per-bot, per-chat
- Contacts — per-bot

**SHARED GLOBALLY (single instance):**
- ALL provider API keys (OPENAI_API_KEY, CLAUDE_API_KEY, GROQ_API_KEY, MOONSHOT_API_KEY, GOOGLE_API_KEY, GROK_API_KEY, OPENROUTER_API_KEY, STABILITY_API_KEY, ELEVENLABS_API_KEY, AZURE_API_KEY, MODELSCOPE_API_KEY, ZHIPU_API_KEY)
- Temperature (global `config.agent.temperature`)
- Max tokens (global `config.agent.max_tokens`)
- Max iterations (global `config.agent.max_iterations`)
- Max depth (global `config.agent.max_depth`)
- Sandbox config (allowed_imports, timeout)
- Local provider endpoints (OLLAMA_ENDPOINT, LMSTUDIO_ENDPOINT, LOCAL_HTTP_ENDPOINT)
- Azure extras (AZURE_API_ENDPOINT, AZURE_DEPLOYMENT_ID)

#### Request Resolution Flow

**WebSocket path (main frontend flow):**
1. Client sends `{ type: "chat", payload: { message, systemPrompt, botId, model, models, capabilities, toolConfigs, enabledSkills } }` over WS
2. `websocket.py` extracts all per-bot fields from the payload
3. Model resolution: `bot_models.default` > `bot_model` > global `config.agent.model`
4. If a per-bot model override exists, `config` is `copy.deepcopy()`'d and `agent_config.agent.model` is set
5. A **new `CachibotAgent`** is created per-message with the overridden config

**Platform message path (Telegram/Discord):**
1. Message arrives at adapter -> `PlatformManager._handle_message()` -> `MessageProcessor.process_message()`
2. Fetches the bot record from DB
3. Model resolution: if `bot.models["default"]` exists, `copy.deepcopy(config)` and override model
4. Creates `CachibotAgent` with bot's system_prompt, capabilities, bot_id

**Key insight: A new agent is created per-request** (not cached). Temperature and max_tokens are NOT overridden per-bot.

#### Platform Connection Secrets

Connection tokens are stored per-bot in the `bot_connections` table in the `config_encrypted` JSON column. However:

**Encryption is NOT implemented yet** — the code has `# TODO: Add actual encryption` comments. Connection config is stored as **plaintext JSON** despite the column being named `config_encrypted`.

#### Config Classification

**TRULY GLOBAL (should remain global):**
- `DATABASE_URL` / `CACHIBOT_DATABASE_URL`
- `CACHIBOT_JWT_SECRET`, `CACHIBOT_JWT_ALGORITHM`
- `CACHIBOT_DEPLOY_MODE`
- `CACHIBOT_WEBSITE_JWT_SECRET`, `CACHIBOT_WEBSITE_URL`
- Server host/port
- Telemetry settings
- Knowledge base embedding model/config
- Sandbox allowed_imports list

**SHOULD BE PER-BOT (currently global):**
- All provider API keys (12+ providers)
- Temperature, max_tokens, max_iterations, max_depth
- Local provider endpoints
- Azure extras

---

### 2.2 Prompture Provider Configuration

#### API Key Reception

Prompture receives API keys through three layers, checked in order:

**Layer 1 — Settings singleton** (`prompture/infra/settings.py`):
- A pydantic `BaseSettings` class loads from environment variables and `.env` file at module import time
- `settings = Settings()` is a **module-level singleton** created once when Prompture is first imported
- All keys have `Optional[str] = None` defaults

**Layer 2 — Driver constructor fallback**:
- Each driver's `__init__` does: `self.api_key = api_key or os.getenv("OPENAI_API_KEY")`

**Layer 3 — `load_dotenv()`**:
- Called in `__init__.py` at import, populates `os.environ` from `.env` file

**Critical**: The `settings` singleton is constructed ONCE at import time and does NOT re-read environment variables after initialization.

#### Multi-Instance Support

**Singleton settings, but multi-instance drivers are possible.**

The driver registry uses factory lambdas that close over the `settings` singleton:
```python
register_driver(
    "openai",
    lambda model=None: OpenAIDriver(api_key=settings.openai_api_key, model=model or settings.openai_model),
)
```

However, drivers themselves are **stateless instances** — you CAN create multiple drivers with different keys:
```python
driver_a = OpenAIDriver(api_key="key-for-bot-a", model="gpt-4o")
driver_b = OpenAIDriver(api_key="key-for-bot-b", model="gpt-4o-mini")
```

The problem: **registry factories are hard-wired to the single `settings` object**. `get_driver_for_model("openai/gpt-4o")` always uses `settings.openai_api_key`.

#### Per-Request Overrides

**Partially supported at the Conversation/Agent level, NOT at the registry level.**

- `Conversation.__init__` accepts a `driver: Driver | None` parameter
- `Agent.__init__` also accepts `driver: Driver | None`
- When `driver` is passed, the registry is bypassed entirely

**The bypass pattern that works today:**
```python
driver = OpenAIDriver(api_key="bot-specific-key", model="gpt-4o")
conv = Conversation(driver=driver)
agent = Agent("", driver=driver)
```

#### Discovery

`get_available_models()` checks each provider's key from the **singleton `settings`** object. Results are cached module-level with 5-minute TTL. Discovery cannot return different model lists for different bots.

#### Required Changes for Per-Bot Environments

**Gap Analysis:**

1. **New concept needed**: `ProviderEnvironment` dataclass bundling all provider keys for one consumer
2. **`get_driver_for_model()`** needs optional `env: ProviderEnvironment` parameter
3. **`get_available_models()`** needs optional `env` parameter for per-bot discovery
4. **Agent/Conversation** should accept optional `env` and auto-build the correct driver
5. **Backward compatible**: if no `env` passed, falls back to global settings singleton

**Architectural advantage**: Drivers are already stateless instances with per-instance `api_key` — the hard part is done. The gap is only in the registry factories and discovery system.

---

### 2.3 Tukuy Skills and Config Handling

#### Skill/Tool Definition Architecture

Tukuy has a dual system: **Transformers** (class-based data pipelines) and **Skills** (function-based tools for LLM agents).

Skills are defined via the `@skill` decorator, which attaches a `Skill` dataclass to the function. Plugins are subclasses of `TransformerPlugin` exposing `transformers`, `skills`, and `manifest` properties.

#### ConfigParam System (Per-Bot Config Infrastructure)

Skills declare configurable parameters via `config_params` in the `@skill` decorator:

```python
@skill(
    name="http_request",
    config_params=[
        ConfigParam(name="base_url", type="url", scope=ConfigScope.PER_BOT),
        ConfigParam(name="timeout", type="number", default=30),
        ConfigParam(name="auth_token", type="secret"),
    ],
)
```

**Crucially, `ConfigScope` has three values:**
- `ConfigScope.GLOBAL` — shared across all bots
- `ConfigScope.PER_BOT` — can differ per bot (**DEFAULT**)
- `ConfigScope.PER_INVOCATION` — can change per call

The system was **designed with per-bot configuration in mind** at the metadata level.

#### Current State vs Per-Bot Ready

| Aspect | Current State | Per-Bot Ready? |
|--------|--------------|---------------|
| Skill definition | `@skill` decorator + `SkillDescriptor` | Yes (immutable metadata) |
| ConfigParam with PER_BOT scope | Declared in metadata | Metadata only, not enforced at runtime |
| SkillContext.config | Exists, supports child scopes | Ready but unused by skills |
| SafetyPolicy | Global via contextvars | Ready (contextvars = async-safe) |
| SecurityContext | Global via contextvars | Ready (contextvars = async-safe) |
| Skill availability filtering | `get_available_skills()` | Ready (accepts per-bot policy) |
| Bridge dispatch with context | No context parameter | Needs adding |
| Skills reading config | Use function params only | Need refactoring |
| Prompture integration | Zero coupling | N/A (CachiBot bridges) |

#### Prompture Integration

**Tukuy has ZERO direct Prompture imports or dependencies.** They are completely decoupled. CachiBot bridges them:
```python
def plugins_to_registry(plugins):
    registry = ToolRegistry()
    for plugin in plugins:
        for name, skill_obj in plugin.skills.items():
            registry.register(skill_obj.fn)
    return registry
```

API keys for LLM providers are entirely a Prompture concern, not Tukuy's.

---

## 3. Architecture Design

### 3.1 Scope Layers

Five configuration layers, resolved in ascending priority (later wins):

#### Layer 1: Global (Instance-Wide Defaults)
**Source**: `.env` file + `os.environ` + `~/.cachibot.toml`
**Contains**: All provider API keys, default model, agent defaults, infrastructure config
**Who sets it**: Instance admin

#### Layer 2: Platform (Per-Platform Defaults)
**Source**: `platform_environments` DB table
**Contains**: Default model per platform, default temperature/max_tokens per platform
**Who sets it**: Admin via platform settings UI

#### Layer 3: Bot (Per-Bot Overrides)
**Source**: `bot_environments` DB table
**Contains**: Per-bot API keys, per-bot model override, per-bot temperature/max_tokens
**Who sets it**: Bot owner via bot settings UI

#### Layer 4: Skill (Per-Bot-Skill Config)
**Source**: `bot_skill_configs` DB table
**Contains**: Skill-specific config values, per-bot overrides of Tukuy `ConfigParam` values
**Who sets it**: Bot owner via skill configuration UI

#### Layer 5: Request (Per-Message Overrides)
**Source**: In-memory, from WebSocket/API payload
**Contains**: Model override, tool_configs, transient overrides
**Who sets it**: End user via UI controls or programmatic API callers

#### Resolution Order
```
Request > Skill > Bot > Platform > Global
```
For any given key, the highest-priority layer that defines it wins. Missing keys fall through.

---

### 3.2 Database Schema

#### Table: `bot_environments`

Stores per-bot environment variable overrides (Layer 3).

```sql
CREATE TABLE bot_environments (
    id          TEXT PRIMARY KEY,
    bot_id      TEXT NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
    key         TEXT NOT NULL,
    value_encrypted TEXT NOT NULL,
    nonce       TEXT NOT NULL,
    salt        TEXT NOT NULL,
    source      TEXT NOT NULL DEFAULT 'user',
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by  TEXT REFERENCES users(id),
    UNIQUE(bot_id, key)
);
CREATE INDEX idx_bot_env_bot ON bot_environments(bot_id);
```

#### Table: `platform_environments`

Stores per-platform defaults (Layer 2).

```sql
CREATE TABLE platform_environments (
    id          TEXT PRIMARY KEY,
    platform    TEXT NOT NULL,
    key         TEXT NOT NULL,
    value_encrypted TEXT NOT NULL,
    nonce       TEXT NOT NULL,
    salt        TEXT NOT NULL,
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by  TEXT REFERENCES users(id),
    UNIQUE(platform, key)
);
CREATE INDEX idx_platform_env_platform ON platform_environments(platform);
```

#### Table: `bot_skill_configs`

Stores per-bot skill configuration overrides (Layer 4).

```sql
CREATE TABLE bot_skill_configs (
    id          TEXT PRIMARY KEY,
    bot_id      TEXT NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
    skill_name  TEXT NOT NULL,
    config_json TEXT NOT NULL,
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(bot_id, skill_name)
);
CREATE INDEX idx_bot_skill_config_bot ON bot_skill_configs(bot_id);
```

#### Table: `env_audit_log`

Audit trail for all environment variable operations.

```sql
CREATE TABLE env_audit_log (
    id          TEXT PRIMARY KEY,
    bot_id      TEXT,
    user_id     TEXT REFERENCES users(id),
    action      TEXT NOT NULL,
    key_name    TEXT NOT NULL,
    source      TEXT NOT NULL,
    timestamp   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    ip_address  TEXT,
    details     JSONB DEFAULT '{}'
);
CREATE INDEX idx_env_audit_bot ON env_audit_log(bot_id);
CREATE INDEX idx_env_audit_time ON env_audit_log(timestamp);
```

#### Encryption Approach

AES-256-GCM with HKDF per-bot key derivation:

```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

def derive_bot_key(master_key: bytes, bot_id: str, salt: bytes) -> bytes:
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=f"cachibot-bot-env-{bot_id}".encode(),
    )
    return hkdf.derive(master_key)

def encrypt_key(plaintext: str, master_key: bytes, bot_id: str) -> tuple[bytes, bytes, bytes]:
    salt = os.urandom(32)
    derived = derive_bot_key(master_key, bot_id, salt)
    nonce = os.urandom(12)
    aesgcm = AESGCM(derived)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), bot_id.encode())
    return ciphertext, nonce, salt

def decrypt_key(ciphertext: bytes, nonce: bytes, salt: bytes, master_key: bytes, bot_id: str) -> str:
    derived = derive_bot_key(master_key, bot_id, salt)
    aesgcm = AESGCM(derived)
    plaintext = aesgcm.decrypt(nonce, ciphertext, bot_id.encode())
    return plaintext.decode()
```

Master key: `CACHIBOT_MASTER_KEY` env var (32-byte hex). Generate with: `python -c "import secrets; print(secrets.token_hex(32))"`

#### Relationship to Existing Tables

- `bot_environments` has FK to `bots.id` — cascade delete on bot deletion
- `bot_connections.config_encrypted` remains for platform tokens — should be migrated to use real encryption with the same scheme
- `bot.model` and `bot.models` continue to store model selection

---

### 3.3 Config Resolution Service

```python
@dataclass
class ResolvedEnvironment:
    """The fully-resolved configuration for a specific bot + request."""
    provider_keys: dict[str, str]       # {"openai": "sk-...", "claude": "sk-..."}
    model: str
    temperature: float
    max_tokens: int
    max_iterations: int
    utility_model: str
    skill_configs: dict[str, dict[str, Any]]  # skill_name -> config dict
    sources: dict[str, str]             # {"openai_api_key": "bot", "temperature": "global"}


class BotEnvironmentService:
    """Resolves the effective environment for a bot by merging all 5 layers."""

    def __init__(self, db_session, encryption_service):
        self._db = db_session
        self._encryption = encryption_service

    async def resolve(
        self,
        bot_id: str,
        platform: str = "web",
        request_overrides: dict[str, Any] | None = None,
    ) -> ResolvedEnvironment:
        """Resolve the full environment for a bot."""
        # Layer 1: Global (from os.environ / Prompture settings)
        env = self._load_global_defaults()
        # Layer 2: Platform defaults
        platform_overrides = await self._load_platform_env(platform)
        env = self._merge(env, platform_overrides, source="platform")
        # Layer 3: Bot overrides
        bot_overrides = await self._load_bot_env(bot_id)
        env = self._merge(env, bot_overrides, source="bot")
        # Layer 4: Skill configs
        env.skill_configs = await self._load_skill_configs(bot_id)
        # Layer 5: Request overrides
        if request_overrides:
            env = self._apply_request_overrides(env, request_overrides)
        return env

    def invalidate(self, bot_id: str):
        """Invalidate cache when admin updates a bot's environment."""
        pass  # v1: no cache, per-request DB lookup
```

**v1 design: Per-request DB lookup (no cache).** The `bot_environments` query is a simple primary key lookup (<2ms). Compare to LLM API calls (200-5000ms). The overhead is <0.5%.

**v2 enhancement**: TTL-based cache (60s) with explicit invalidation on API updates.

**v3 enhancement**: PostgreSQL LISTEN/NOTIFY or Redis pub/sub for event-driven invalidation.

---

### 3.4 Prompture Integration

#### Phase 1 — No Prompture Changes Needed

The cleanest v1 approach: CachiBotV2 creates the Prompture driver directly with the resolved API key, and passes it to `AsyncAgent(driver=...)`.

The `AsyncAgent.__init__` already accepts `driver`, and `_build_conversation()` already checks:
```python
if self._driver is not None:
    kwargs["driver"] = self._driver
```

**CachiBotV2 driver construction:**

```python
DRIVER_MAP = {
    "openai": ("prompture.drivers.async_openai_driver", "AsyncOpenAIDriver"),
    "claude": ("prompture.drivers.async_claude_driver", "AsyncClaudeDriver"),
    "google": ("prompture.drivers.async_google_driver", "AsyncGoogleDriver"),
    "groq": ("prompture.drivers.async_groq_driver", "AsyncGroqDriver"),
    "grok": ("prompture.drivers.async_grok_driver", "AsyncGrokDriver"),
    "openrouter": ("prompture.drivers.async_openrouter_driver", "AsyncOpenRouterDriver"),
    "moonshot": ("prompture.drivers.async_moonshot_driver", "AsyncMoonshotDriver"),
}

def build_driver_with_key(model_str: str, api_key: str | None = None):
    if api_key is None:
        return get_async_driver_for_model(model_str)
    provider, model_id = model_str.split("/", 1)
    module_path, class_name = DRIVER_MAP[provider.lower()]
    module = importlib.import_module(module_path)
    driver_cls = getattr(module, class_name)
    return driver_cls(api_key=api_key, model=model_id)
```

#### Phase 2 — Prompture Enhancement

Add `ProviderEnvironment` dataclass and env-aware factory:
```python
def get_async_driver_for_model(model_str: str, *, env: ProviderEnvironment | None = None):
```

When `env is None`, behavior is identical to today. When provided, resolves keys from env first, then settings.

---

### 3.5 Tukuy Integration

#### Phase 1 — No Tukuy Changes Needed

`SkillContext.config` already exists and is the right mechanism. CachiBotV2 populates it from `resolved_env.skill_configs`:

```python
merged_tool_configs = dict(resolved_env.skill_configs)
if request_tool_configs:
    for k, v in request_tool_configs.items():
        merged_tool_configs.setdefault(k, {}).update(v)

agent = CachibotAgent(
    config=agent_config,
    tool_configs=merged_tool_configs,
    ...
)
```

#### Phase 2 — Tukuy Enhancement

Add `context` parameter to bridge dispatch functions:
```python
def dispatch_openai(tool_call: dict, skills: Dict[str, Any], *, context: SkillContext | None = None):
```

And optionally add `SkillContext.env` property for environment variable passthrough.

---

### 3.6 API Design

#### Bot Environment CRUD

```
GET    /api/bots/{bot_id}/environment              -- List per-bot env vars (masked)
PUT    /api/bots/{bot_id}/environment/{key}         -- Set/update per-bot env var
DELETE /api/bots/{bot_id}/environment/{key}         -- Delete override (fall back)
GET    /api/bots/{bot_id}/environment/resolved      -- Full resolved config (all layers)
```

**GET /api/bots/{bot_id}/environment** response:
```json
{
  "variables": [
    {
      "key": "OPENAI_API_KEY",
      "masked_value": "****************************1234",
      "source": "bot",
      "updated_at": "2026-02-16T10:00:00Z"
    }
  ]
}
```

**GET /api/bots/{bot_id}/environment/resolved** response:
```json
{
  "resolved": {
    "OPENAI_API_KEY": { "masked_value": "****1234", "source": "bot" },
    "CLAUDE_API_KEY": { "masked_value": "****5678", "source": "global" },
    "model": { "value": "openai/gpt-4o", "source": "bot" },
    "temperature": { "value": 0.7, "source": "platform" },
    "max_tokens": { "value": 4096, "source": "global" }
  },
  "skill_configs": {
    "shell_execute": {
      "timeout_seconds": { "value": 60, "source": "bot" }
    }
  }
}
```

#### Platform Environment CRUD (Admin Only)

```
GET    /api/platforms/{platform}/environment         -- List platform defaults
PUT    /api/platforms/{platform}/environment/{key}   -- Set platform default
DELETE /api/platforms/{platform}/environment/{key}   -- Delete platform default
```

#### Skill Config CRUD

```
GET    /api/bots/{bot_id}/skills/{skill_name}/config    -- Get skill config
PUT    /api/bots/{bot_id}/skills/{skill_name}/config    -- Set skill config
DELETE /api/bots/{bot_id}/skills/{skill_name}/config    -- Delete skill config
```

#### Permission Model

| Action | Admin | Bot Owner | User |
|--------|-------|-----------|------|
| Set global env (providers API) | Yes | No | No |
| Set platform env | Yes | No | No |
| Set bot env (API keys) | Yes | Yes (own bots) | No |
| Set bot env (model, temp) | Yes | Yes (own bots) | No |
| Set skill configs | Yes | Yes (own bots) | No |
| View resolved config | Yes | Yes (own bots) | No |
| Request-level overrides | Yes | Yes | Yes (if enabled) |

---

### 3.7 Admin/User UI

#### Per-Bot Settings Page Layout

```
Bot Settings > Environment
+-- Provider Keys
|   +-- OpenAI API Key    [****1234] [Inherited: Global] [Override] [Remove]
|   +-- Claude API Key    [Not Set]  [Inherited: Global] [Override]
|   +-- Google API Key    [****5678] [Custom]            [Edit]     [Remove]
|   +-- + Add Provider Key
|
+-- Model & Behavior
|   +-- Default Model     [openai/gpt-4o]  [Inherited: Global] [Override]
|   +-- Temperature       [0.7]            [Custom]             [Edit] [Remove]
|   +-- Max Tokens        [4096]           [Inherited: Global]  [Override]
|   +-- Max Iterations    [20]             [Inherited: Global]  [Override]
|
+-- Skill Configurations
|   +-- shell_execute
|   |   +-- timeout_seconds  [30] [Default] [Override]
|   |   +-- allowed_commands [...] [Default]
|   +-- file_ops
|   |   +-- max_file_size    [10MB] [Custom] [Edit] [Remove]
|   +-- (other enabled skills with config_params...)
|
+-- Danger Zone
    +-- [Reset All to Defaults]
```

#### Key Display Rules

1. **API Keys**: Show only last 4 characters: `****************************1234`
2. **Endpoints/URLs**: Show full value
3. **Numbers/Booleans**: Show full value
4. **Inheritance indicator**: Badge showing source layer:
   - "Global" (gray), "Platform" (blue), "Custom" (green), "Default" (light gray)

#### Config Param UI Auto-Generation

Tukuy's `ConfigParam` declares type, min/max, options, placeholder, etc. The frontend reads these from the skill manifest and auto-generates the appropriate input:

| ConfigParam.type | UI Control |
|:---|:---|
| "string" | Text input |
| "number" | Number input with min/max/step |
| "boolean" | Toggle switch |
| "select" | Dropdown |
| "secret" | Password input (masked) |
| "text" | Textarea |
| "path" | File/directory picker |
| "code" | Code editor |
| "map" | Key-value pair list |
| "string[]" | Tag input / chip list |

---

## 4. Security Design

### 4.1 Current Vulnerability Audit

#### Secrets in Plaintext (CRITICAL)

**`.env` file on disk** (`providers.py:53`):
- All API keys stored as plaintext in CWD-relative `.env` file
- Any process with filesystem access to CWD can read all keys

**Connection tokens in DB** (`repository.py:926`):
- `config_encrypted=connection.config, # TODO: Add actual encryption`
- Telegram bot tokens, Discord tokens, WhatsApp app_secrets stored as **plaintext JSON**

**`os.environ` is process-wide**:
- Every driver reads keys from `os.environ`
- Any code in the same process (including sandbox, plugins) can call `os.environ`

#### Secret Exposure Vectors

**Correctly handled:**
- `ConnectionResponse` model explicitly excludes tokens
- `_mask_value()` masks API keys in provider endpoint responses

**Risk areas:**
- Exception messages in logs could contain tokens in tracebacks
- No systematic secret masking in logging
- `name_generator.py:84-94` extracts raw `api_key` from driver objects

**Tukuy env plugin risk:**
- `env_read(path, mask=False)` can read ANY `.env` file
- `env_write()` writes directly to process-wide `os.environ`

**Tukuy shell plugin risk:**
- `shell_execute(command)` could execute `env` or `printenv` to dump environment variables

#### SQL Injection Assessment
- SQLAlchemy ORM with parameterized queries throughout. **Risk is LOW.**

#### Sandbox Security — Confirmed Safe (with caveats)

`ALWAYS_BLOCKED_IMPORTS` includes `os`, `subprocess`, `sys`, `pathlib`, `ctypes`, `importlib`, `builtins`, `inspect`, `pickle`, `io`, `socket`, `asyncio` — all blocked. Safe builtins exclude `exec`, `eval`, `compile`, `globals`, `locals`, `getattr`, `__import__`. **The sandbox adequately prevents env var leakage.**

---

### 4.2 Encryption Design

#### AES-256-GCM with Per-Bot Key Derivation

```
Master Key (CACHIBOT_MASTER_KEY env var, 32 bytes)
    |
    v
HKDF (SHA-256) + salt = bot_id
    |
    v
Per-Bot Derived Key (32 bytes)
    |
    v
AES-256-GCM encrypt(plaintext, nonce)
    |
    v
Stored in DB: (ciphertext, nonce, salt) all base64 encoded
```

**Why per-bot key derivation:**
- If a single bot's data is compromised AND the master key leaks, only that bot's data is at risk
- HKDF is deterministic — same master key + bot_id always produces same derived key
- No need to store derived keys

#### Master Key Storage

**Self-hosted**: `CACHIBOT_MASTER_KEY` environment variable, loaded once at startup, held in memory

**Cloud/production**: AWS KMS / GCP Cloud KMS / Azure Key Vault (upgrade path)

#### Key Rotation Strategy

**Master key rotation:**
1. Set `CACHIBOT_MASTER_KEY_NEW` alongside `CACHIBOT_MASTER_KEY`
2. Run migration: decrypt all with old key, re-encrypt with new key
3. Replace old key with new, remove `_NEW`
4. Can be done in batches per-bot

---

### 4.3 Access Control

#### API Endpoint Permissions

| Endpoint | Admin | Bot Owner | Other Users |
|---|---|---|---|
| GET /api/bots/{id}/env | All keys (masked) + source | Own keys (masked) + "inherited" | 403 |
| PUT /api/bots/{id}/env/{key} | Any key, any bot | Own bot only | 403 |
| DELETE /api/bots/{id}/env/{key} | Any override | Own override | 403 |
| GET /api/platform/env | All platform keys (masked) | 403 | 403 |
| PUT /api/platform/env/{key} | Set platform key | 403 | 403 |
| GET /api/bots/{id}/env/{key}/test | Test any key | Test own key | 403 |

#### Key Visibility Rules

- **Platform keys (inherited)**: Bot owner sees `{"source": "platform", "configured": true}` — NO value, not even masked
- **Bot custom keys**: Bot owner sees `{"source": "custom", "masked_value": "****cF4x"}` — last 4 chars only
- **Admin**: Sees masked values for both. Never raw values in any API response.
- **Raw values**: NEVER returned by any endpoint.

#### Plugin/Skill Access Control

- Skills NEVER get direct access to env vars
- `env_read` must be restricted: blocked from reading `.env` in bot context
- `shell_execute` must block `env`, `printenv`, `set` commands via SecurityContext

---

### 4.4 Isolation Design

#### Per-Request Scoped Key Loading

```python
class BotEnvironment:
    """Scoped environment for a single bot request."""

    def __init__(self, bot_id: str, env_service):
        self.bot_id = bot_id
        self._resolved: dict[str, str] = {}

    async def __aenter__(self):
        custom_keys = await self._load_and_decrypt_bot_keys()
        platform_keys = await self._load_platform_defaults()
        self._resolved = {**platform_keys, **custom_keys}
        return self

    async def __aexit__(self, *args):
        self._resolved.clear()  # Clear from memory

    def get(self, key: str) -> str | None:
        return self._resolved.get(key)
```

#### Key Rules

1. **NEVER put per-bot keys in `os.environ`**
2. Keys loaded from encrypted DB per-request
3. Keys passed to driver constructors explicitly
4. After request, `BotEnvironment` context clears its dict
5. Two simultaneous requests get separate `BotEnvironment` instances
6. Use `contextvars` (already used by Tukuy) for the current `BotEnvironment`

---

### 4.5 Inheritance Security

| Scenario | Behavior |
|---|---|
| Bot A inherits platform key | Can USE it, never SEE the value. API returns `{source: "platform", configured: true}` |
| Admin rotates platform key | All inheriting bots get new key on next request automatically |
| Bot A sets custom key | Uses own key; platform key not accessible to Bot A |
| Bot A deletes custom override | Falls back to platform key automatically |
| Bot A exports config | Export shows `{"OPENAI_API_KEY": {"source": "custom", "present": true}}`, never the value |

#### Tier-Based Access

| Tier | Custom keys? | Platform keys? | Max custom keys |
|---|---|---|---|
| Free | No | Yes (rate-limited) | 0 |
| Pro | Yes | Yes | 5-20 |
| Enterprise | Yes | Yes | Unlimited |

---

### 4.6 Multi-Tenant Patterns (Industry Research)

**Vercel**: Env vars encrypted at rest (AES-256), scoped per-project AND per-environment, role-based access

**Heroku**: Config vars encrypted at rest (AES-256, AWS-managed), per-app scoping, atomic updates

**Railway**: Per-service env vars with project-level shared variables, write-only sensitive vars

**Supabase**: Vault extension for encrypted secrets, per-project encryption with rotating keys

**Key takeaways:**
1. Per-entity scoping is standard
2. Write-only secrets (can set, cannot read back) is the norm
3. Inheritance with override is universal
4. AES-256 at rest is the standard
5. Role-based visibility is expected

---

### 4.7 Key Rotation and Backup

#### Platform Key Rotation
1. Admin updates key → encrypted and stored
2. Old value kept in rotation history for 30 days
3. All inheriting bots get new value on next request automatically

#### Master Key Loss Recovery
- **CRITICAL**: If master key is lost, ALL encrypted env vars are permanently unrecoverable
- Mitigation: Document setup prominently, recommend password manager or KMS
- Consider key escrow: encrypt master key with recovery passphrase
- Regularly test decryption with a sentinel value

#### Backup Strategy
- DB backups include encrypted env vars (useless without master key)
- Master key is NOT in DB
- Both needed for recovery

---

### 4.8 Logging and Audit

#### Secret Masking in Logs

```python
class SecretMaskingFilter(logging.Filter):
    PATTERNS = [
        re.compile(r'sk-[a-zA-Z0-9]{20,}'),        # OpenAI
        re.compile(r'sk-ant-[a-zA-Z0-9]{20,}'),     # Anthropic
        re.compile(r'gsk_[a-zA-Z0-9]{20,}'),        # Groq
        re.compile(r'AIza[a-zA-Z0-9_-]{35}'),       # Google
        re.compile(r'[0-9]+:[A-Za-z0-9_-]{35}'),    # Telegram bot tokens
    ]
```

#### Audit Trail

**What to log:** Key created/updated/deleted (who, when, which key name), key accessed for execution, failed access attempts

**What NEVER to log:** Actual key values, decrypted key material, master encryption key

---

## 5. Integration Design

### 5.1 Full Request Lifecycle with Per-Bot Env

#### A. WebSocket (Frontend Chat)

```
User types message
    |
    v
Frontend sends WS: {type:"chat", botId:"bot-123", model:"openai/gpt-4o", ...}
    |
    v
websocket.py receives data
    |
    v
[NEW] BotEnvironmentService.load(bot_id="bot-123")
    |   - Queries bot_environments table
    |   - Decrypts provider keys using CACHIBOT_MASTER_KEY
    |   - Returns ResolvedEnvironment
    |
    v
[NEW] Build driver with per-bot key:
    |   provider, model_id = effective_model.split("/", 1)
    |   api_key = resolved_env.provider_keys.get(provider)
    |   driver = build_driver_with_key(effective_model, api_key=api_key)
    |
    v
CachibotAgent(config=agent_config, driver=driver, provider_environment=env, ...)
    |
    v
PromptureAgent(driver=self._driver)  -- bypasses global registry
    |
    v
agent.run_stream(message) -> response streamed back via WS
    |
    v
env garbage collected (no cleanup needed)
```

#### B. Platform Adapter (Telegram/Discord)

```
User sends Telegram message
    |
    v
TelegramAdapter.handle_message() -> PlatformManager._handle_message()
    |
    v
MessageProcessor.process_message(bot_id, ...)
    |   - Gets bot from DB (model, capabilities, system_prompt)
    |
    v
[NEW] BotEnvironmentService.load(bot_id) -> ResolvedEnvironment
    |
    v
[NEW] Build driver with per-bot key
    |
    v
CachibotAgent(driver=driver, provider_environment=env, ...)
    |
    v
result = await agent.run(message) -> response sent via adapter
```

#### C. API Endpoint (Programmatic)

Same pattern: load env, build driver, create agent with `driver=`.

---

### 5.2 Error Scenarios

#### Bot's custom key is invalid but platform key works

**Design: Explicit failure, no silent fallback (v1).**

```
1. Driver raises AuthenticationError (401)
2. Return error: "API key for OpenAI is invalid. Using your custom key. Please update it."
3. Log to audit: {bot_id, provider, error: "invalid_key"}
```

Optional v2: configurable `fallback_policy` per bot ("none" | "platform").

#### Bot's key hits rate limit

**Design: Return rate limit error, do NOT fall back to platform key.** Rate limits are the bot owner's responsibility.

#### Platform key is expired/invalid

**Design: Health check on startup + periodic validation (every 6 hours).** Failed check sends WebSocket notification to admin dashboard.

#### Master key missing at startup

**Design: Start server but disable per-bot key features.** Bots fall back to platform (global) keys only. Dashboard shows warning.

#### DB is unreachable

**Design: Fail open with global keys.** Log warning, use `os.environ` fallback (current behavior). When DB returns, next request picks up per-bot keys.

---

### 5.3 Concurrency / Isolation

```
Bot A msg arrives              Bot B msg arrives
    |                              |
    v                              v
env_a = BotEnvService.load    env_b = BotEnvService.load
    -> ProviderEnvironment(        -> ProviderEnvironment(
         openai_key="sk-AAA")           openai_key="sk-BBB")
    |                              |
    v                              v
driver_a = AsyncOpenAIDriver(  driver_b = AsyncOpenAIDriver(
    api_key="sk-AAA")              api_key="sk-BBB")
    |                              |
    v                              v
Completely separate agents,    Completely separate agents,
separate drivers               separate drivers
```

**Isolation guarantees:**
1. **Memory**: Each request creates its own `ProviderEnvironment` dataclass (no shared state)
2. **Driver**: Each `AsyncOpenAIDriver` has its own `api_key` attribute
3. **SecurityContext**: `contextvars.ContextVar` scoped per `asyncio.Task`
4. **No os.environ mutation**: Keys flow as constructor params only

---

### 5.4 Hot Reload

**v1: Per-request DB lookup (no cache).** Admin updates key → next request uses it immediately. DB lookup adds <2ms vs 200-5000ms LLM call. No cache invalidation bugs.

**v2**: TTL-based cache (60s) with explicit invalidation on API updates.

**v3**: PostgreSQL LISTEN/NOTIFY for event-driven invalidation.

---

### 5.5 Tier System Integration

| Tier | Custom keys? | Platform keys? | Max custom keys |
|---|---|---|---|
| Free | No | Yes (rate-limited) | 0 |
| Pro | Yes | Yes | 5 |
| Enterprise | Yes | Yes | Unlimited |

**Enforced at:**
1. API endpoint validation (primary)
2. UI restriction (defense in depth)
3. Runtime enforcement in `BotEnvironmentService.load()`

---

### 5.6 Adapter Registry Integration

**No changes needed.** Adapter tokens are already per-bot via `bot_connections.config`. Each `TelegramAdapter` instance gets its own token from its `BotConnection`. The per-bot environment system is orthogonal — it manages provider API keys, not adapter tokens.

---

### 5.7 Discovery Per-Bot

**New endpoint: `GET /api/bots/{id}/available-models`**

```python
@router.get("/bots/{bot_id}/available-models")
async def get_bot_available_models(bot_id: str):
    env = await env_service.load(bot_id)
    available = []
    for provider, key_field in PROVIDER_KEY_MAP.items():
        bot_key = env.get_key(provider)
        platform_key = getattr(settings, key_field, None)
        if bot_key or platform_key:
            models = get_models_for_provider(provider)
            for model_id in models:
                available.append({
                    "model": f"{provider}/{model_id}",
                    "provider": provider,
                    "source": "custom" if bot_key else "platform",
                })
    return {"models": available}
```

Models tagged with `source: "custom" | "platform"` for UI badges.

---

### 5.8 Sequence Diagrams

#### Normal Request (Happy Path)

```
User      Frontend    WS Handler     BotEnvSvc    DB       Agent      OpenAI
 |            |           |              |         |          |          |
 |--"Hello"-->|           |              |         |          |          |
 |            |--WS{chat}>|              |         |          |          |
 |            |           |--load(bot)-->|         |          |          |
 |            |           |              |--SELECT>|          |          |
 |            |           |              |<--row---|          |          |
 |            |           |              | decrypt |          |          |
 |            |           |<-ProvEnv-----|         |          |          |
 |            |           | build_driver           |          |          |
 |            |           |--Agent(driver=d)------>|          |          |
 |            |           |                        |--API---->|
 |            |           |                        |  (sk-AA) |
 |            |           |                        |<-resp----|
 |            |           |<-----stream events-----|          |
 |            |<--WS------|                        |          |
 |<--render---|           |                        |          |
```

#### Admin Updates Bot Key

```
Admin     Dashboard    API Server     DB        Bot (next request)
 |            |            |          |              |
 |--Update    |            |          |              |
 |  key------>|            |          |              |
 |            |--PUT /env->|          |              |
 |            |            | encrypt  |              |
 |            |            |--UPSERT->|              |
 |            |            |<--OK-----|              |
 |            |            | audit_log|              |
 |            |<--200------|          |              |
 |<--Updated--|            |          |              |
 |            |            |          |              |
 |            | [Later, message arrives]             |
 |            |            | load(bot)|              |
 |            |            |--SELECT->|              |
 |            |            |<-NEW row-|              |
 |            |            | decrypt  |              |
 |            |            | build_driver(NEW key)   |
 |            |            |--Agent(driver)--------->|
```

---

## 6. Implementation Plan

### 6.1 Prompture Changes

#### Files to Change

| File | Change | Risk |
|------|--------|------|
| NEW: `prompture/infra/provider_env.py` | `ProviderEnvironment` dataclass | Low |
| `prompture/drivers/__init__.py` | `get_driver_for_model(env=)` param | Medium |
| `prompture/drivers/async_registry.py` | `get_async_driver_for_model(env=)` param | Medium |
| `prompture/infra/discovery.py` | `get_available_models(env=)` param | Medium |
| `prompture/__init__.py` | Export `ProviderEnvironment` | Low |

**NOTE: These changes are NOT needed for Phase 1.** CachiBotV2 can use direct driver construction.

**Backward compatibility**: Every new parameter defaults to `None`. When `None`, behavior is identical to today.

**Effort: Medium | Risk: Low-Medium**

---

### 6.2 Tukuy Changes

#### Files to Change

| File | Change | Risk |
|------|--------|------|
| `tukuy/bridges.py` | Add `context=` param to 4 dispatch functions | Low |

Add `context: SkillContext | None = None` to:
- `dispatch_openai`
- `dispatch_anthropic`
- `async_dispatch_openai`
- `async_dispatch_anthropic`

Pass `context=context` to `skill_obj.invoke()` / `skill_obj.ainvoke()`.

**NOTE: Not needed for Phase 1.** CachiBotV2 can populate `SkillContext.config` through existing `tool_configs` flow.

**Effort: Small | Risk: Low**

---

### 6.3 CachiBotV2 Changes

| File | Change | Type |
|------|--------|------|
| NEW: `storage/alembic/versions/003_per_bot_environment.py` | DB migration (3 tables) | New |
| NEW: `storage/models/env_var.py` | SQLAlchemy models | New |
| NEW: `services/encryption.py` | AES-256-GCM + HKDF | New |
| NEW: `services/bot_environment.py` | BotEnvironmentService | New |
| NEW: `services/driver_factory.py` | `build_driver_with_key()` | New |
| NEW: `api/routes/bot_env.py` | CRUD endpoints | New |
| `agent.py` | Add `driver`, `provider_environment` params | Modified |
| `services/message_processor.py` | Load env, build driver | Modified |
| `api/websocket.py` | Load env, build driver | Modified |
| `api/routes/providers.py` | Deprecation path | Modified |
| `storage/repository.py` | Encrypt config_encrypted | Modified |

**Effort: Large | Risk: Medium**

---

### 6.4 CachiBot Website Changes

The CachiBot website (`cachibot.ai`) needs **no changes for Phase 1**. Per-bot env is managed in the CachiBotV2 web frontend.

**CachiBotV2 web frontend** (Phase 4):
- New "Environment Variables" tab on bot settings page
- Per-provider key input fields with masked display
- Model selector calls `/api/bots/{id}/available-models`

**Effort: Small (v2 UI) | Risk: Low**

---

### 6.5 Dependency Order

```
Phase 1: Library Prep (parallel, can start immediately)
    Prompture: ProviderEnvironment + env= params (optional)
    Tukuy: context= on dispatch functions (optional)

Phase 2: Core Infrastructure (CachiBotV2)
    CACHIBOT_MASTER_KEY + EncryptionService
    DB migration (3 new tables)
    BotEnvironmentService
    Encrypt existing config_encrypted column

Phase 3: API + Integration (CachiBotV2)
    Bot env CRUD endpoints
    Platform env CRUD endpoints
    CachibotAgent + MessageProcessor integration
    Per-bot discovery endpoint

Phase 4: UI + Migration
    Bot settings env tab (V2 web UI)
    Migrate existing .env keys to platform_env_vars
    Deprecate direct .env writing

Phase 5: Security Hardening (can overlap with Phase 4)
    Block .env access via SecurityContext
    Block env/printenv commands
    Secret masking in logs
    Audit trail integration
```

**Critical path**: DB migration -> EncryptionService -> BotEnvironmentService -> Agent integration

---

### 6.6 Migration Plan

#### Step 1: Add Master Key
- User sets `CACHIBOT_MASTER_KEY` env var
- If not set, auto-generate on first run

#### Step 2: Run DB Migration
- `alembic upgrade` creates new tables
- No existing tables modified

#### Step 3: Seed Platform Env Vars from `.env`
- One-time migration script reads `PROVIDERS` keys from `.env`
- Encrypts each and inserts into `platform_env_vars`
- Does NOT delete from `.env` (dual-read period)

#### Step 4: Dual-Read Period
- `BotEnvironment.get()` checks: `bot_env_vars` -> `platform_env_vars` -> `os.environ`
- Existing `.env` keys still work as fallback
- Zero downtime

#### Step 5: Deprecate `.env` Provider Writes
- Mark old endpoints as deprecated
- `.env` still read as lowest-priority fallback

#### Rollback Plan
- `.env` fallback remains active during migration
- Standard Alembic downgrade drops new tables only
- Feature flag `CACHIBOT_PER_BOT_ENV=0` reverts all bots to shared global keys

---

## 7. Summary

### Files Changed

| Codebase | Modified | New | Effort |
|----------|----------|-----|--------|
| CachiBotV2 | 4-5 | 5-6 | Large |
| Prompture | 0 (v1) / 4-5 (v3) | 0 (v1) / 1 (v3) | None -> Medium |
| Tukuy | 0 (v1) / 1 (v3) | 0 | None -> Small |
| CachiBot website | 0 | 0 | None (v1) |
| CachiBotV2 Web UI | 1-2 | 1 | Medium |

### Immediate Security Fixes (Before Per-Bot Work)

1. Implement actual encryption for `config_encrypted` column
2. Add secret masking log filter
3. Block `.env` access from bot agents via SecurityContext.blocked_paths
4. Block `env`/`printenv`/`set` commands via SecurityContext.allowed_commands

### Design Principles

1. **Zero os.environ mutation**: Keys flow as constructor params, never pollute the process environment
2. **Per-request lifecycle**: Decrypted keys exist only for the duration of a single request
3. **Library-zero changes (v1)**: Prompture and Tukuy need NO modifications
4. **Graceful degradation**: If per-bot env fails, falls back to global keys
5. **Defense in depth**: Tier enforcement at API + UI + runtime levels
6. **Audit everything**: All key operations logged with timestamps and context
