---
phase: 01-model-switching
verified: 2026-02-28T14:00:00Z
status: passed
score: 6/6 must-haves verified
re_verification: false
gaps: []
human_verification:
  - test: "Model dropdown appears in chat status bar and is interactive"
    expected: "ModelSelect renders visibly in the bottom-left of the chat input area with a placeholder showing the bot's default model; clicking it opens a searchable dropdown"
    why_human: "Visual rendering and interaction behavior cannot be verified by static analysis"
  - test: "Selected model label appears in message bubble info panel after reload"
    expected: "After sending a message with a non-default model selected and reloading the page, the message bubble's info panel shows 'Model: <selected-model-id>'"
    why_human: "End-to-end persistence across page reload requires a running app with real LLM call"
---

# Phase 1: Model Switching Verification Report

**Phase Goal:** Users can select which AI model handles each message, with the choice visible in the conversation history
**Verified:** 2026-02-28T14:00:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A model dropdown appears in the chat input status bar and users can change it before sending | VERIFIED | `ModelSelect` imported and rendered at line 1240 of `ChatView.tsx`; `selectedModel` state + `setSelectedModel` wired as `value`/`onChange` |
| 2 | The selected model override is transmitted with the message via the WebSocket models payload | VERIFIED | `effectiveModels: BotModels` constructed at line 761 and passed as `models: effectiveModels` in `wsSendMessage` call at line 770 |
| 3 | The dropdown defaults to the bot's configured default model on load and resets on bot switch | VERIFIED | `useState` initializer calls `getBotDefaultModel(bot)` (line 72); `useEffect` on `activeBotId` resets to `getBotDefaultModel(bot)` (line 157) |
| 4 | The backend uses the model override from the WebSocket payload for that specific response | VERIFIED | `websocket.py` reads `payload.get("models")` (line 142), passes to `build_bot_agent(bot_models=bot_models)` (line 241); `agent_factory.py` applies `bot_models["default"]` to `agent_config.agent.model` (lines 139-144) |
| 5 | The actual model used is persisted in the assistant message metadata and survives page refresh | VERIFIED | `actual_model` extracted from `run_usage["per_model"]` at line 416; `metadata={"model": actual_model}` set in `BotMessage` constructor at line 432; `save_bot_message` persists `message.metadata` as JSON `meta` column |
| 6 | Each chat bubble displays which model produced that response | VERIFIED | `MessageBubble.tsx` line 509 checks `message.metadata?.model !== undefined` and renders `String(message.metadata.model)` at line 512 |

**Score:** 6/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `frontend/src/components/views/ChatView.tsx` | Model selector state, ModelSelect embedding, wsSendMessage override | VERIFIED | 1409 lines; imports `ModelSelect` (line 24) and `getBotDefaultModel` (line 18); `selectedModel` state (line 70); `useEffect` sync on `activeBotId` (lines 154-158); `effectiveModels` (lines 761-764); `wsSendMessage` with `models: effectiveModels` (line 770) |
| `cachibot/api/websocket.py` | Model metadata persistence in assistant BotMessage save | VERIFIED | 481 lines; `per_model` extraction (line 415); `actual_model` with fallback (line 416); `metadata={"model": actual_model}` in `BotMessage` constructor (line 432) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `ChatView.tsx` | `ModelSelect.tsx` | import and render in status bar | WIRED | `import { ModelSelect } from '../common/ModelSelect'` at line 24; rendered at line 1240 in standard chat status bar |
| `ChatView.tsx` | `wsSendMessage` | `effectiveModels` override in `handleSend` | WIRED | `models: effectiveModels` at line 770 inside `wsSendMessage(...)` call; `effectiveModels.default` set to `selectedModel` |
| `ChatView.tsx` | `getBotDefaultModel` | state initialization and bot-switch sync | WIRED | Called in `useState` initializer (line 72) and `useEffect` reset (line 157) and `ModelSelect` placeholder (line 1243) |
| `websocket.py` | `BotMessage metadata` (knowledge.py) | `metadata={"model": actual_model}` in constructor | WIRED | `BotMessage` has `metadata: dict[str, Any] = Field(default_factory=dict)` (knowledge.py line 31); populated with `actual_model` at websocket.py line 432 |
| `websocket.py` | `repository.save_bot_message` | persists metadata to DB | WIRED | `save_bot_message(assistant_msg)` called at line 434; repository maps `message.metadata` to `meta=message.metadata` (repository.py line 215) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| MODL-01 | 01-01-PLAN.md | User can select a model from a dropdown in the chat input area before sending a message | SATISFIED | `ModelSelect` rendered in status bar (ChatView.tsx line 1240); `selectedModel` state controls the selection |
| MODL-02 | 01-02-PLAN.md | Selected model override is sent with the WebSocket chat message and used for that response | SATISFIED | `effectiveModels` wired into `wsSendMessage` (line 770); backend applies `bot_models["default"]` as `agent_config.agent.model` in agent_factory.py |
| MODL-03 | 01-02-PLAN.md | Model used for each message is stored in message metadata and displayed in the chat bubble | SATISFIED | `metadata={"model": actual_model}` persisted in DB; `MessageBubble.tsx` renders it from `message.metadata.model` |
| MODL-04 | 01-01-PLAN.md | Model selector defaults to the bot's configured default model | SATISFIED | `useState` initializer and `useEffect` reset both call `getBotDefaultModel(bot)` which prefers `bot.models.default` over legacy `bot.model` |

No orphaned requirements — all four MODL requirements from REQUIREMENTS.md are claimed in plans and verified in code.

### Anti-Patterns Found

None detected. Both modified files are substantive with no TODO/FIXME stubs, no empty return implementations, and no placeholder content in the added code paths.

### Human Verification Required

#### 1. Model dropdown visual rendering and interaction

**Test:** Open the app, navigate to any bot chat, and inspect the bottom-left status bar of the chat input area.
**Expected:** A `ModelSelect` dropdown widget is visible (not a plain text span); clicking it opens a searchable list of available models; selecting one changes the displayed value.
**Why human:** Visual rendering and interactive dropdown behavior cannot be confirmed by static analysis of TSX source.

#### 2. Per-message model persistence across page reload

**Test:** Select a non-default model from the dropdown, send a message, wait for the assistant response, reload the page, and inspect the message info panel on the assistant bubble.
**Expected:** After reload, the assistant bubble's info panel shows "Model: <the-model-id-that-was-active>" — proving the value came from the DB-persisted metadata rather than frontend memory.
**Why human:** Requires a running app, a live LLM call to populate `run_usage["per_model"]`, and a browser reload to confirm DB-backed persistence.

### Gaps Summary

No gaps found. All six observable truths are verified against the actual codebase. Both commits (`4f92192` and `a3405d0`) exist in git history and match the implementations claimed in the SUMMARY files. The end-to-end data flow from UI selection through WebSocket payload through backend model override through DB persistence through bubble rendering is fully wired and substantive at every step.

---

_Verified: 2026-02-28T14:00:00Z_
_Verifier: Claude (gsd-verifier)_
