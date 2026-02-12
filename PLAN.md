# Multi-Platform Bot Adapters — Implementation Plan

## Overview

CachiBot already has a clean, extensible adapter pattern with `BasePlatformAdapter` and working Telegram + Discord implementations. Adding new platforms (Slack, MS Teams, WhatsApp, Messenger, Matrix, Email) requires implementing the same 3-method interface (`connect`, `disconnect`, `send_message`) per platform, plus wiring them into the existing factory and enum.

The frontend already defines metadata for 7 platforms (WhatsApp, Telegram, Discord, Slack, Messenger, Matrix, Email) in `frontend/src/stores/connections.ts`. Only Telegram and Discord have backend adapters.

---

## Phase 1: Slack Adapter

### Files to create
- `src/cachibot/services/adapters/slack.py` — `SlackAdapter(BasePlatformAdapter)`

### Files to modify
- `src/cachibot/models/connection.py` — Add `slack = "slack"` to `ConnectionPlatform` enum
- `src/cachibot/services/platform_manager.py` — Add Slack case to `_create_adapter()` factory, import `SlackAdapter`
- `src/cachibot/api/routes/connections.py` — Add Slack config validation (requires `bot_token` + `app_token` for Socket Mode)
- `pyproject.toml` — Add `slack-bolt>=1.18.0` to optional deps (new `[slack]` extra)

### Design decisions
- **Library**: `slack-bolt` (official Slack SDK) with **Socket Mode** — no public URL/webhook needed, free tier friendly, matches the existing polling/event-loop pattern used by Telegram and Discord
- **Auth config**: `bot_token` (xoxb-...) + `app_token` (xapp-...) for Socket Mode
- **Message handling**: Listen to `message` events + `app_mention` events (similar to Discord's DM + mention pattern)
- **Media support**: Download files via Slack's `files.info` API, pass as `IncomingMedia` to the existing attachment pipeline
- **Markdown**: Slack uses mrkdwn (not standard Markdown) — add a `slack_format_message()` helper that converts common Markdown to Slack's block kit format, or use the existing `strip_markdown` config option
- **Threading**: Respond in-thread when the message is in a thread, otherwise respond in channel

### Implementation sketch
```python
class SlackAdapter(BasePlatformAdapter):
    platform = ConnectionPlatform.slack

    async def connect(self):
        from slack_bolt.async_app import AsyncApp
        from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

        self._app = AsyncApp(token=bot_token)

        @self._app.event("message")
        async def handle_message(event, say):
            # Extract text, user, channel, thread_ts
            # Download file attachments if any
            # Call self.on_message(connection_id, channel_id, text, metadata)
            # say(response.text, thread_ts=...)

        self._handler = AsyncSocketModeHandler(self._app, app_token)
        await self._handler.connect_async()  # non-blocking

    async def disconnect(self):
        await self._handler.close_async()

    async def send_message(self, chat_id, message):
        await self._app.client.chat_postMessage(channel=chat_id, text=message)
```

---

## Phase 2: Microsoft Teams Adapter

### Files to create
- `src/cachibot/services/adapters/teams.py` — `TeamsAdapter(BasePlatformAdapter)`

### Files to modify
- `src/cachibot/models/connection.py` — Add `teams = "teams"` to `ConnectionPlatform` enum
- `src/cachibot/services/platform_manager.py` — Add Teams case to factory
- `src/cachibot/api/routes/connections.py` — Add Teams config validation (`app_id`, `app_password`, `tenant_id`)
- `pyproject.toml` — Add `botbuilder-core>=4.16.0` and `aiohttp` to optional deps (new `[teams]` extra)
- `frontend/src/stores/connections.ts` — Add Teams platform metadata to `PLATFORMS` array

### Design decisions
- **Library**: `botbuilder-core` + `botbuilder-integration-aiohttp` (official Microsoft Bot Framework SDK for Python)
- **Architecture**: Teams requires an HTTP endpoint (webhook) unlike Telegram/Discord which use polling/websocket. The adapter will spin up a lightweight aiohttp server on a configurable port, or register a sub-route on the existing FastAPI app
- **Approach A (preferred)**: Mount a sub-application at `/api/platforms/teams/{connection_id}/messages` on the existing FastAPI server — avoids needing a separate port, leverages existing HTTPS/reverse-proxy setup
- **Auth config**: `app_id` (Azure Bot registration), `app_password` (client secret), optional `tenant_id` for single-tenant deployments
- **Message handling**: Bot Framework handles turn context — extract activity text, attachments, and conversation reference; call `on_message`; reply via `turn_context.send_activity()`
- **Media**: Teams supports Adaptive Cards for rich responses — initial implementation will send plain text, with a follow-up for card-based responses
- **Proactive messaging**: Store conversation references to enable bot-initiated messages (needed for `send_message`)

### Implementation sketch
```python
class TeamsAdapter(BasePlatformAdapter):
    platform = ConnectionPlatform.teams

    async def connect(self):
        from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings, TurnContext

        settings = BotFrameworkAdapterSettings(app_id, app_password)
        self._bf_adapter = BotFrameworkAdapter(settings)
        self._conversation_refs = {}  # Store for proactive messaging

        async def on_turn(turn_context: TurnContext):
            # Extract message, user info, conversation id
            # Store conversation reference for proactive messaging
            # Call self.on_message(...)
            # Reply via turn_context.send_activity(response.text)

        self._on_turn = on_turn
        # Register webhook route on FastAPI (via platform_manager hook)
        self._running = True

    async def disconnect(self):
        # Unregister webhook route
        self._running = False

    async def send_message(self, chat_id, message):
        # Use stored conversation reference for proactive messaging
        ref = self._conversation_refs.get(chat_id)
        await self._bf_adapter.continue_conversation(ref, callback, app_id)
```

### Additional infrastructure needed
- A mechanism for adapters to register webhook routes on the FastAPI app. Options:
  1. Pass the FastAPI `app` instance into `BasePlatformAdapter` (via `PlatformManager`)
  2. Have `PlatformManager` expose a `register_webhook(path, handler)` method that mounts routes
  3. Pre-register a catch-all route `/api/platforms/{platform}/{connection_id}/webhook` that delegates to the appropriate adapter

  **Recommendation**: Option 3 — add a single generic webhook route in a new `api/routes/platform_webhooks.py` that looks up the adapter and forwards the request. This keeps the adapter interface clean and doesn't require passing FastAPI internals into adapters.

---

## Phase 3: WhatsApp Adapter

### Files to create
- `src/cachibot/services/adapters/whatsapp.py` — `WhatsAppAdapter(BasePlatformAdapter)`

### Files to modify
- Same pattern: enum, factory, route validation, pyproject.toml
- `frontend/src/stores/connections.ts` — Already defined

### Design decisions
- **Library**: WhatsApp Cloud API (official Meta API) via `httpx` — more reliable than unofficial libraries, free for testing
- **Auth config**: `phone_number_id`, `access_token`, `verify_token` (for webhook verification)
- **Architecture**: Webhook-based (like Teams) — uses the generic webhook route from Phase 2
- **Webhook verification**: WhatsApp requires a GET verification endpoint that echoes a challenge token
- **Media**: Download media via WhatsApp Media API, pass as `IncomingMedia`

---

## Phase 4: Additional Platforms (Matrix, Messenger, Email)

Each follows the same pattern:

### Matrix
- **Library**: `matrix-nio` (async Matrix client)
- **Pattern**: Long-polling sync loop (similar to Telegram polling)
- **Config**: `homeserver_url`, `access_token` or `username`/`password`

### Facebook Messenger
- **Library**: Direct HTTP via `httpx` (Messenger Send/Receive API)
- **Pattern**: Webhook-based (like Teams/WhatsApp)
- **Config**: `page_access_token`, `verify_token`, `app_secret`

### Email (IMAP/SMTP)
- **Library**: `aioimaplib` + `aiosmtplib`
- **Pattern**: IMAP IDLE for real-time push, SMTP for sending
- **Config**: `imap_host`, `smtp_host`, `email`, `password`

---

## Phase 5: Shared Infrastructure & Enhancements

### 5a. Generic Webhook Route (needed by Phase 2+)
- **File**: `src/cachibot/api/routes/platform_webhooks.py`
- Catch-all route: `POST /api/platforms/{platform}/{connection_id}/webhook`
- GET variant for webhook verification (WhatsApp, Messenger)
- Delegates to adapter's `handle_webhook(request)` method
- Add `handle_webhook(request) -> Response` as an optional method on `BasePlatformAdapter` (default raises NotImplementedError — only webhook-based adapters override it)

### 5b. Enhanced Base Adapter
- Add optional `async def handle_webhook(self, request: Request) -> Response` method to `BasePlatformAdapter` for webhook-based platforms
- Add `platform_type` property: `"polling"` | `"websocket"` | `"webhook"` — helps the manager decide lifecycle behavior
- Add `async def send_media(self, chat_id, media: MediaItem) -> bool` as an optional method with a default that falls back to sending the filename as text

### 5c. Config Validation Registry
- Instead of per-platform `if/elif` in `connections.py`, create a `PLATFORM_CONFIG_SCHEMA` dict mapping `ConnectionPlatform` → required config fields + validation rules
- Each adapter module can export its config schema
- The connections route validates against this schema generically

### 5d. Rate Limiting
- Add per-platform rate limiting in `PlatformManager` to respect API limits (Slack: 1 msg/sec, Teams: ~50 msg/min, WhatsApp: varies)
- Use `asyncio.Semaphore` or token-bucket algorithm

### 5e. Message Formatting Pipeline
- Add a `format_for_platform(message: str, platform: ConnectionPlatform) -> str` utility
- Handles Markdown → mrkdwn (Slack), Markdown → HTML (Teams/Telegram), plain text (SMS/WhatsApp), etc.
- Each adapter can override `format_outgoing_message()` (already exists on base) to use platform-specific formatting

### 5f. Frontend Updates
- Add MS Teams to `PLATFORMS` array in `frontend/src/stores/connections.ts` with setup steps
- Update `ConnectionPlatform` type in `frontend/src/types/index.ts` with new platforms
- Platform-specific config forms in the connection dialog (different fields per platform)

---

## Implementation Order

| Step | What | Scope | Dependencies |
|------|------|-------|-------------|
| 1 | Slack adapter | New file + 4 modifications | None (Socket Mode = no webhook needed) |
| 2 | Generic webhook route | New route file + base adapter enhancement | None |
| 3 | MS Teams adapter | New file + 5 modifications | Step 2 (needs webhook route) |
| 4 | WhatsApp adapter | New file + standard modifications | Step 2 (needs webhook route) |
| 5 | Config validation registry | Refactor connections.py | Steps 1-4 (benefits from all adapters existing) |
| 6 | Matrix adapter | New file + standard modifications | None (polling-based) |
| 7 | Messenger adapter | New file + standard modifications | Step 2 |
| 8 | Email adapter | New file + standard modifications | None (IMAP IDLE) |
| 9 | Message formatting pipeline | New utility + adapter overrides | All adapters |
| 10 | Rate limiting | Platform manager enhancement | All adapters |
| 11 | Frontend config forms | Component updates | All adapters |

---

## Files Summary

### New files
| File | Purpose |
|------|---------|
| `src/cachibot/services/adapters/slack.py` | Slack adapter (Socket Mode) |
| `src/cachibot/services/adapters/teams.py` | MS Teams adapter (Bot Framework) |
| `src/cachibot/services/adapters/whatsapp.py` | WhatsApp Cloud API adapter |
| `src/cachibot/services/adapters/matrix_adapter.py` | Matrix adapter (nio) |
| `src/cachibot/services/adapters/messenger.py` | Facebook Messenger adapter |
| `src/cachibot/services/adapters/email_adapter.py` | Email IMAP/SMTP adapter |
| `src/cachibot/api/routes/platform_webhooks.py` | Generic webhook route for Teams/WhatsApp/Messenger |

### Modified files
| File | Changes |
|------|---------|
| `src/cachibot/models/connection.py` | Add `slack`, `teams`, `whatsapp`, `matrix`, `messenger`, `email` to `ConnectionPlatform` enum |
| `src/cachibot/services/platform_manager.py` | Add all new adapters to `_create_adapter()` factory |
| `src/cachibot/services/adapters/base.py` | Add optional `handle_webhook()` method, `platform_type` property, `send_media()` |
| `src/cachibot/api/routes/connections.py` | Add config validation for each new platform |
| `src/cachibot/api/server.py` | Register webhook route |
| `pyproject.toml` | Add optional dependencies per platform |
| `frontend/src/stores/connections.ts` | Add Teams platform metadata |
| `frontend/src/types/index.ts` | Add new platform types |

---

## Risk & Considerations

1. **Teams requires a public URL** — unlike Telegram/Discord which use polling/websocket. Users will need a reverse proxy or tunnel (ngrok) for local development. Document this clearly in setup steps.
2. **WhatsApp Cloud API** requires Meta Business verification for production use. Testing is possible with a test phone number.
3. **Dependency bloat** — use optional extras (`pip install cachibot[slack]`, `pip install cachibot[teams]`) so users only install what they need. The lazy `import` pattern already used by Telegram/Discord adapters handles this gracefully.
4. **Token encryption** — already handled by `config_encrypted` in the database. No changes needed.
5. **Concurrent adapters** — the existing `asyncio.Lock` in `PlatformManager` handles this, but webhook-based adapters introduce concurrent HTTP requests that bypass this lock. Each adapter should handle its own concurrency internally.
