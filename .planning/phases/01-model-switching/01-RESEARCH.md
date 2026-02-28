# Phase 1: Model Switching - Research

**Researched:** 2026-02-28
**Domain:** Per-message model override — frontend state, WebSocket protocol, backend agent factory
**Confidence:** HIGH

---

## Summary

Phase 1 adds per-message model selection: a dropdown in the chat input lets the user pick any available model before sending, the choice travels over the existing WebSocket protocol, the backend uses it for that response, and the model name is stored in message metadata so the chat bubble can display it.

The codebase already has most of the infrastructure in place. `ModelSelect.tsx` is a complete, production-quality component ready to embed. The WebSocket `sendChat()` call already accepts a `model` field. The backend's `bot_models["default"]` override path in `build_bot_agent` already wires into the agent factory. `MessageMetadata` already has a `model` field, and `MessageBubble.tsx` already renders `message.metadata.model` in the info panel. The missing pieces are wiring them together: exposing the dropdown in `ChatView.tsx`, passing the selection through `wsSendMessage`, and writing the model into the assistant `BotMessage` metadata on the backend at save time.

**Primary recommendation:** Embed `ModelSelect` into `ChatView.tsx`'s input area with a `useState` hook initialized to `getBotDefaultModel(activeBot)`, pass it as `modelOverride` into `wsSendMessage`, route it through the WS payload as an updated `bot_models.default`, and after the agent completes write `model` into the assistant `BotMessage.metadata` before calling `save_bot_message`.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| MODL-01 | User can select a model from a dropdown in the chat input area before sending a message | `ModelSelect.tsx` is ready; needs embedding in `ChatView.tsx` input section |
| MODL-02 | Selected model override is sent with the WebSocket chat message and used for that response | `wsClient.sendChat()` already has `model` + `models` fields; backend `build_bot_agent` already reads `bot_models["default"]` |
| MODL-03 | Model used for each message is stored in message metadata and displayed in the chat bubble | `BotMessage.metadata` / `MessageMetadata.model` exists; `MessageBubble` renders it; backend save path needs to populate it |
| MODL-04 | Model selector defaults to the bot's configured default model | `getBotDefaultModel(bot)` helper exists in `bots.ts`; `bot.models.default` or `bot.model` |
</phase_requirements>

---

## Standard Stack

### Core (no new dependencies needed)

| Component | Location | Purpose | Status |
|-----------|----------|---------|--------|
| `ModelSelect.tsx` | `frontend/src/components/common/ModelSelect.tsx` | Full-featured model dropdown with search, grouping, manual entry | Exists, production-ready |
| `useModelsStore` | `frontend/src/stores/models.ts` | Fetches and groups available models from backend | Exists, used by ModelSelect |
| `useChatStore` | `frontend/src/stores/bots.ts` | Message store with `updateLastAssistantMessageMetadata` | Exists |
| `wsClient.sendChat()` | `frontend/src/api/websocket.ts` | Already accepts `model?: string` and `models?: BotModels` | Exists |
| `build_bot_agent()` | `cachibot/services/agent_factory.py` | Already reads `bot_models["default"]` → `effective_model` → `agent_config.agent.model` | Exists |
| `BotMessage.metadata` | `cachibot/storage/models/message.py` | JSON column `meta` persisted in `bot_messages` table | Exists |
| `MessageMetadata.model` | `frontend/src/types/index.ts` | `model?: string` field in `MessageMetadata` interface | Exists |
| `MessageBubble.tsx` | `frontend/src/components/chat/MessageBubble.tsx` | Already renders `message.metadata.model` in info panel | Exists |

### No new npm packages or pip packages needed

All required infrastructure is already installed and in use.

---

## Architecture Patterns

### How model override flows today (without this feature)

```
ChatView.tsx
  → wsSendMessage(message, { models: activeBot.models, model: activeBot.model })
  → wsClient.sendChat() → WS payload: { type:"chat", payload: { models, model, ... } }
  → websocket.py: bot_models = payload.get("models")
  → build_bot_agent(bot_models=bot_models)
  → agent_factory.py step 2: effective_model = bot_models["default"]
  → agent_config.agent.model = effective_model
  → CachibotAgent._create_agent(): agent_kwargs["model"] = config.agent.model
```

### How model override will flow (after this feature)

```
ChatView.tsx
  [new] selectedModel: string (state, defaults to getBotDefaultModel(activeBot))
  [new] <ModelSelect value={selectedModel} onChange={setSelectedModel} />
  → wsSendMessage(message, {
      models: { ...activeBot.models, default: selectedModel || activeBot.models.default },
      ...
    })
  → (everything downstream unchanged — backend already handles it)

Backend (assistant message save):
  run_agent() → agent_result → response_text
  [new] actual_model = first key in run_usage["per_model"], or agent_config.agent.model
  → BotMessage(metadata={"model": actual_model, ...})
  → repo.save_bot_message(assistant_msg)

Frontend (usage handler in useWebSocket.ts):
  case 'usage': already writes metadata.model = first perModel key
  → updateLastAssistantMessageMetadata(chatId, { model, ... })
  → MessageBubble renders it in info panel (already works)
```

### Pattern: Merge override into bot_models dict

The cleanest approach is to merge the selected model into the `models` dict before sending, rather than adding a new top-level field. The backend already reads `bot_models["default"]`.

```typescript
// In ChatView.tsx handleSend:
const effectiveModels = {
  ...(activeBot?.models || {}),
  default: selectedModel || getBotDefaultModel(activeBot!) || '',
}
wsSendMessage(trimmedInput, {
  ...existingOptions,
  models: effectiveModels,
})
```

This touches nothing in the backend — `bot_models["default"]` is already the override path.

### Pattern: Model state initialization and sync

The selector must re-initialize when the active bot changes:

```typescript
const [selectedModel, setSelectedModel] = useState(() => getBotDefaultModel(activeBot!))

useEffect(() => {
  setSelectedModel(getBotDefaultModel(activeBot!))
}, [activeBotId]) // reset on bot switch
```

### Pattern: Actual model from usage payload

The backend sends the actual model used via the `usage` WS message's `perModel` breakdown. `useWebSocket.ts` already extracts it:

```typescript
const perModelKeys = Object.keys(payload.perModel || {})
const model = perModelKeys.length > 0 ? perModelKeys[0] : getBotDefaultModel(currentBot)
updateLastAssistantMessageMetadata(chatId, { model, ... })
```

This means MODL-03 (display model in bubble) is **already almost working** — the metadata is written by the existing `usage` handler. The only backend change needed is to also write model into the persisted `BotMessage.metadata` so the information survives a page refresh.

### Anti-Patterns to Avoid

- **Adding a new WS message type for model selection** — unnecessary. The existing `chat` message payload already carries `models` and `model`.
- **Storing selected model in Zustand** — keep it as local React state in `ChatView.tsx`. It's ephemeral UI state, not persistent app state.
- **Adding a new backend parameter `model_override`** — the `bot_models["default"]` path is already the correct override mechanism.
- **Duplicating ModelSelect** — do not create a new simplified dropdown. `ModelSelect.tsx` already handles search, grouping, manual entry, and loading states.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Model dropdown UI | Custom `<select>` or new dropdown | `ModelSelect.tsx` | Already handles search, grouping by provider, context window display, vision/tools badges, manual entry, portal rendering |
| Available model list | Custom fetch | `useModelsStore` (used by ModelSelect internally) | Already fetches, caches, groups models |
| Model display in bubble | New UI component | Existing `message.metadata.model` → existing `MessageBubble` info panel | The `hasMetadata` check + info panel already renders `Model: <value>` |
| Default model resolution | Re-implement fallback | `getBotDefaultModel(bot)` from `bots.ts` | Already handles `bot.models.default || bot.model || ''` |

---

## Common Pitfalls

### Pitfall 1: Model not displayed on page refresh

**What goes wrong:** The `usage` WS message writes `model` to the in-memory message metadata, but the backend `save_bot_message` call saves the assistant message *before* usage is computed. On page refresh, messages load from DB with empty `metadata`, so model is gone.

**Why it happens:** The `run_agent()` function in `websocket.py` saves the assistant `BotMessage` at line ~419-430, then sends the `usage` WS message afterward. The save uses an empty `metadata={}` — the model is not written at save time.

**How to avoid:** After `agent_result` is captured (the `StreamEventType.output` event), extract the actual model from `run_usage["per_model"]` and include it in the `BotMessage.metadata` dict before calling `repo.save_bot_message`. The data is available at that point because `run_usage` is populated from `agent_result.run_usage`.

**Code location:** `/mnt/c/Users/Juan/Documents/GitHub/CachiBot/cachibot/api/websocket.py`, `run_agent()` function, around line 418-430.

### Pitfall 2: ModelSelect dropdown positioned off-screen in compact input

**What goes wrong:** `ModelSelect.tsx` uses `createPortal` with absolute positioning calculated from `triggerRef.current.getBoundingClientRect()`. In the `ChatView.tsx` input area (which is at the bottom of the viewport), the dropdown may render below the viewport edge.

**Why it happens:** The dropdown renders `top: rect.bottom + 4` — it opens downward. At the bottom of the screen, there's no room.

**How to avoid:** Pass a CSS class or use the existing position calculation to detect when to flip upward. Alternatively, wrap `ModelSelect` in a container that flips the dropdown. Simplest: add a `dropdownDirection="up"` prop to `ModelSelect` or use the `top` calculation to render `bottom: window.innerHeight - rect.top + 4` when near the bottom.

This is a UI concern that affects the component. Check actual rendering position when implementing.

### Pitfall 3: Model selector width too wide for input bar

**What goes wrong:** `ModelSelect.tsx` renders the trigger button full-width. In the `ChatView.tsx` input area's bottom bar, this might crowd the existing "Connected" indicator and model label.

**Why it happens:** The current `InputArea.tsx` status bar shows `{model && <span className="chat-status-bar__model">{model}</span>}` as a static label. Replacing this with a clickable `ModelSelect` changes the interaction pattern.

**How to avoid:** Embed `ModelSelect` with a `className` that constrains its width (e.g., `max-w-[200px]`). The component accepts a `className` prop. The trigger can be compact — just the model name + chevron.

### Pitfall 4: selectedModel not reset on bot switch

**What goes wrong:** User switches from Bot A (GPT-4) to Bot B (Claude 3 Opus) but the model selector still shows GPT-4 from the previous bot.

**Why it happens:** `selectedModel` is local state in `ChatView.tsx` that doesn't react to `activeBotId` changes without an explicit `useEffect`.

**How to avoid:** Add `useEffect(() => { setSelectedModel(getBotDefaultModel(activeBot!)) }, [activeBotId])`.

### Pitfall 5: Stale model in `wsSendMessage` when no override selected

**What goes wrong:** User opens the selector, sees GPT-4 as the default, doesn't change anything, sends a message. The selector sends `bot_models.default = ""` because the initial state was `""`.

**Why it happens:** If `selectedModel` initializes to `''` (empty string means "system default" in `ModelSelect`), the merged `effectiveModels.default` becomes `""`, which the backend treats as "no model".

**How to avoid:** When merging, preserve the bot's configured model as fallback:
```typescript
const effectiveModels = {
  ...(activeBot?.models || {}),
  default: selectedModel || getBotDefaultModel(activeBot!) || '',
}
```
An empty `selectedModel` means "use bot's default", so fall through to `getBotDefaultModel`.

---

## Code Examples

### Embedding ModelSelect in ChatView.tsx

```typescript
// Source: existing ModelSelect.tsx pattern + ChatView.tsx handleSend context

// State (near top of ChatView component):
const [selectedModel, setSelectedModel] = useState(() =>
  getBotDefaultModel(useBotStore.getState().getActiveBot()!)
)

// Sync on bot switch:
useEffect(() => {
  setSelectedModel(getBotDefaultModel(activeBot!))
}, [activeBotId])

// In JSX (inside the input area, before the textarea or in the status bar):
<ModelSelect
  value={selectedModel}
  onChange={setSelectedModel}
  placeholder={getBotDefaultModel(activeBot!) || 'System Default'}
  className="chat-input__model-select"
/>

// In handleSend (merging override before wsSendMessage):
const effectiveModels: BotModels = {
  ...(activeBot?.models || {}),
  default: selectedModel || getBotDefaultModel(activeBot!) || '',
}
wsSendMessage(trimmedInput, {
  systemPrompt: activeBot?.systemPrompt,
  botId: activeBot?.id,
  chatId: chatIdToUse ?? undefined,
  models: effectiveModels,
  capabilities: activeBot?.capabilities || defaultCapabilities,
  toolConfigs: activeBot?.toolConfigs,
  replyToId: replyToMessage?.id,
})
```

### Persisting model in BotMessage metadata (backend)

```python
# Source: cachibot/api/websocket.py run_agent() function

# After: agent_result = event.data (StreamEventType.output)
run_usage = agent_result.run_usage if agent_result else {}

# NEW: Extract actual model used
per_model = run_usage.get("per_model", {})
actual_model = next(iter(per_model), None) or agent_config.agent.model

# In the assistant BotMessage save:
assistant_msg = BotMessage(
    id=str(uuid.uuid4()),
    bot_id=bot_id,
    chat_id=chat_id,
    role="assistant",
    content=response_text,
    timestamp=datetime.now(timezone.utc),
    reply_to_id=bot_reply_to,
    metadata={"model": actual_model},  # NEW: persist model for page-refresh display
)
await repo.save_bot_message(assistant_msg)
```

Note: `run_agent()` needs access to the agent's effective model. The `CachibotAgent` has `agent.config.agent.model` as the configured model. Pass the `agent` object (already in scope) or derive it from `run_usage["per_model"]`.

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| `bot.model` (single string) | `bot.models.default` (multi-slot dict) | Already migrated; `bot.model` is now a deprecated property that reads from `models.default` |
| No model override per message | `bot_models["default"]` override in WS payload | Infrastructure exists; just need the UI to send it per-message |
| Model shown only in usage overlay | `message.metadata.model` in info panel | Already renders; needs backend persistence |

---

## Key File Locations (absolute paths)

| File | Role in This Phase |
|------|--------------------|
| `/mnt/c/Users/Juan/Documents/GitHub/CachiBot/frontend/src/components/views/ChatView.tsx` | Main chat UI — add `selectedModel` state, embed `ModelSelect`, update `wsSendMessage` call |
| `/mnt/c/Users/Juan/Documents/GitHub/CachiBot/frontend/src/components/common/ModelSelect.tsx` | Reuse as-is — no changes needed |
| `/mnt/c/Users/Juan/Documents/GitHub/CachiBot/frontend/src/api/websocket.ts` | `sendChat()` already accepts `model` + `models` — no changes needed |
| `/mnt/c/Users/Juan/Documents/GitHub/CachiBot/frontend/src/hooks/useWebSocket.ts` | `usage` handler already writes `metadata.model` — no changes needed |
| `/mnt/c/Users/Juan/Documents/GitHub/CachiBot/frontend/src/components/chat/MessageBubble.tsx` | Already renders `message.metadata.model` — no changes needed |
| `/mnt/c/Users/Juan/Documents/GitHub/CachiBot/frontend/src/stores/bots.ts` | `getBotDefaultModel()` helper — import and use, no changes needed |
| `/mnt/c/Users/Juan/Documents/GitHub/CachiBot/cachibot/api/websocket.py` | `run_agent()` — add `metadata={"model": actual_model}` to assistant `BotMessage` save |
| `/mnt/c/Users/Juan/Documents/GitHub/CachiBot/cachibot/services/agent_factory.py` | `build_bot_agent()` already handles `bot_models["default"]` — no changes needed |
| `/mnt/c/Users/Juan/Documents/GitHub/CachiBot/cachibot/models/knowledge.py` | `BotMessage.metadata` field exists — no changes needed |
| `/mnt/c/Users/Juan/Documents/GitHub/CachiBot/cachibot/storage/models/message.py` | `BotMessage.meta` JSON column exists — no changes needed |

---

## Open Questions

1. **Where exactly in the ChatView input area should ModelSelect live?**
   - What we know: `ChatView.tsx` has its own inline input (not `InputArea.tsx` from `ChatPanel.tsx`). The status bar has `{model && <span>...}`. The `InputArea.tsx` component (used in `ChatPanel.tsx`) also has a `model` prop but it's a read-only label.
   - What's unclear: Should the dropdown replace the existing `model` label in the status bar, or appear as a separate control above/left of the textarea?
   - Recommendation: Replace the existing static model label in the `ChatView.tsx` bottom status area with `ModelSelect`. Keep it compact (max 200px wide) with the current model ID as placeholder.

2. **Should `InputArea.tsx` also get a model selector?**
   - What we know: `InputArea.tsx` is used in `ChatPanel.tsx` (a simpler route). It currently has a read-only `model` prop.
   - What's unclear: Is `ChatPanel.tsx` used in production, or is `ChatView.tsx` the primary chat UI?
   - Recommendation: Focus on `ChatView.tsx` first (it's the primary chat UI with full WebSocket wiring). `InputArea.tsx` can be updated in a follow-up if needed.

3. **Should the model selection persist across messages in a session?**
   - What we know: Requirements say per-message override (MODL-02). MODL-05 (per-chat persistence) is v2.
   - Recommendation: Local `useState` that survives within a single chat session but resets on bot switch. Not persisted to localStorage.

---

## Sources

### Primary (HIGH confidence — direct code inspection)

All findings are based on direct reading of the codebase. No external library research required — this phase is entirely an integration of existing infrastructure.

- `/mnt/c/Users/Juan/Documents/GitHub/CachiBot/cachibot/api/websocket.py` — WS message parsing, `run_agent()` save path
- `/mnt/c/Users/Juan/Documents/GitHub/CachiBot/cachibot/services/agent_factory.py` — `build_bot_agent()` model override logic (step 2)
- `/mnt/c/Users/Juan/Documents/GitHub/CachiBot/frontend/src/components/common/ModelSelect.tsx` — component API and rendering
- `/mnt/c/Users/Juan/Documents/GitHub/CachiBot/frontend/src/components/views/ChatView.tsx` — `wsSendMessage` call site, input area structure
- `/mnt/c/Users/Juan/Documents/GitHub/CachiBot/frontend/src/hooks/useWebSocket.ts` — `usage` handler, `sendMessage` options
- `/mnt/c/Users/Juan/Documents/GitHub/CachiBot/frontend/src/api/websocket.ts` — `sendChat()` signature
- `/mnt/c/Users/Juan/Documents/GitHub/CachiBot/frontend/src/types/index.ts` — `MessageMetadata`, `ChatMessage` interfaces
- `/mnt/c/Users/Juan/Documents/GitHub/CachiBot/frontend/src/stores/bots.ts` — `getBotDefaultModel()`, `getEffectiveModels()`
- `/mnt/c/Users/Juan/Documents/GitHub/CachiBot/cachibot/storage/repository.py` — `save_bot_message()` implementation
- `/mnt/c/Users/Juan/Documents/GitHub/CachiBot/cachibot/storage/models/message.py` — `BotMessage` ORM model, `meta` JSON column

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all components are in the codebase, directly inspected
- Architecture: HIGH — data flow traced end-to-end through actual code
- Pitfalls: HIGH — identified from actual code gaps (e.g., metadata not written at save time)

**Research date:** 2026-02-28
**Valid until:** This research is based on internal codebase state. Valid until any of the listed files change significantly. No external library versions to expire.
