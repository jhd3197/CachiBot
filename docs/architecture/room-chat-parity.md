# Room ↔ Chat Feature Parity

## The Problem

`MessageBubble` is shared between Chat and Rooms — it already renders tool actions, Info popover (model/tokens/cost/time/speed), Copy, Reply, and the Tools button. But Rooms were missing the **data flow** to populate these features:

| Feature | Chat (before) | Rooms (before) |
|---------|--------------|----------------|
| Live tool calls with spinners | `toolCalls` in ChatStore → `ToolCallList` | Tracked in `activeToolCalls` but **nothing rendered** them |
| Thinking indicator | `thinking` string → `ThinkingIndicator` | Backend sent `bot_thinking` with **no content**, no component |
| Instruction deltas | Streamed via callback | WebSocket handler was a **no-op** |
| "Tools (N)" button during execution | Active tool calls fed to MessageBubble | Only appeared **after** `finalizeToolCalls` |
| Info popover (model/tokens/cost) | Metadata on message → MessageBubble | Data arrived via `room_usage` but **same path** — already worked |

After a bot finished, everything showed correctly (finalized tool calls, metadata). The gap was the **live execution experience**.

---

## What Changed

### Store (`frontend/src/stores/rooms.ts`)

Added two transient state slices (not persisted, like `activeToolCalls`):

```
thinkingContent:    Record<roomId, Record<botId, string>>
instructionDeltas:  Record<roomId, Record<toolId, string>>
```

New actions:
- **`setBotThinking(roomId, botId, content)`** — appends thinking text (accumulates deltas)
- **`clearBotThinking(roomId, botId)`** — removes on tool start or bot done
- **`appendInstructionDelta(roomId, toolId, text)`** — accumulates instruction LLM output
- **`finalizeToolCalls`** — now also cleans up instruction deltas for finalized tools

### WebSocket Hook (`frontend/src/hooks/useRoomWebSocket.ts`)

Wired three previously inert events:

| Event | Before | After |
|-------|--------|-------|
| `room_bot_thinking` | Set bot state only | + `setBotThinking` if `payload.content` present |
| `room_bot_tool_start` | Add tool call | + `clearBotThinking` (model decided on action) |
| `room_bot_instruction_delta` | No-op comment | `appendInstructionDelta(roomId, toolId, text)` |
| `room_bot_done` | Finalize + idle | + `clearBotThinking` |

### RoomPanel (`frontend/src/components/rooms/RoomPanel.tsx`)

Renders `ToolCallList` and `ThinkingIndicator` **inside** `RoomMessageList` as children (so they live in the scrollable area and auto-scroll into view):

```tsx
<RoomMessageList messages={roomMessages} roomId={roomId}>
  {allActiveToolCalls.length > 0 && (
    <ToolCallList toolCalls={allActiveToolCalls} instructionDeltas={roomInstructionDeltas} />
  )}
  {showThinking && thinkingBots.map(([botId, text]) => (
    <ThinkingIndicator content={text} label={`${botName} is thinking...`} />
  ))}
</RoomMessageList>
```

All hooks (`useMemo`) are above early returns to satisfy Rules of Hooks.

### RoomMessageList (`frontend/src/components/chat/MessageList.tsx`)

- Accepts optional `roomId` and `children` props
- Subscribes to `activeToolCalls[roomId]` from the room store
- Merges active tool calls into each bot message: `msg.toolCalls ?? activeToolCalls[roomId]?.[msg.id]`
- This makes the "Tools (N)" button appear in MessageBubble **during** execution, not just after
- Scroll key includes active tool call count so new calls trigger auto-scroll

### ToolCallList (`frontend/src/components/chat/ToolCallList.tsx`)

- Accepts optional `instructionDeltas?: Record<string, string>` prop
- Each `ToolCallItem` receives `instructionText={instructionDeltas?.[call.id]}`
- When a tool is in-progress and has instruction text, renders it below the args preview
- Backward compatible — Chat doesn't pass this prop

### ThinkingIndicator (`frontend/src/components/chat/ThinkingIndicator.tsx`)

- Accepts optional `label` prop (defaults to `"Thinking..."`)
- Rooms pass `label={`${botName} is thinking...`}` for multi-bot context

### Backend Model (`cachibot/models/room_websocket.py`)

`bot_thinking()` now accepts optional `content: str | None = None`:

```python
@classmethod
def bot_thinking(cls, room_id, bot_id, bot_name, content=None):
    payload = {"roomId": room_id, "botId": bot_id, "botName": bot_name}
    if content is not None:
        payload["content"] = content
    return cls(type=ROOM_BOT_THINKING, payload=payload)
```

### Backend Handler (`cachibot/api/room_websocket.py`)

In `run_room_bot`, added `has_tool_calls` flag (mirrors the chat pattern in `websocket.py`):

- On `StreamEventType.tool_call`: sets `has_tool_calls = True`
- On `StreamEventType.text_delta` when `has_tool_calls`: sends an additional `bot_thinking` with `content=event.data`

This makes text deltas *after* tool calls appear as thinking content (the model is reasoning about tool results before its next action).

### CSS (`frontend/src/styles/components/chat.less`)

Added `.tool-call__instruction` — monospace, secondary color, 8rem max-height with scroll overflow.

---

## Data Flow Summary

### During Execution

```
Backend stream event
  → room_bot_tool_start   → addToolCall()        → ToolCallList (spinners)
  → room_bot_tool_end     → completeToolCall()    → ToolCallList (checkmarks)
  → room_bot_thinking     → setBotThinking()      → ThinkingIndicator
  → room_bot_instr_delta  → appendInstrDelta()    → ToolCallItem inline text
  → room_bot_tool_start   → clearBotThinking()    → ThinkingIndicator removed
```

Active tool calls also merge into MessageBubble → "Tools (N)" button visible during execution.

### After Bot Done

```
room_bot_done
  → clearBotThinking()     → ThinkingIndicator removed
  → finalizeToolCalls()    → activeToolCalls → msg.toolCalls (persisted)
                           → instructionDeltas cleaned up
  → setBotState('idle')    → Status bar updated
```

MessageBubble now renders finalized tool calls with Copy/Info/Tools buttons.

### On Reload

Messages loaded from REST include `metadata.toolCalls` — MessageBubble renders them as before. Transient state (thinking, instruction deltas, active tool calls) is gone, which is correct.

---

## What Stays the Same

- **MessageBubble** — zero changes, shared between Chat and Rooms
- **ToolCallList** — same component, just accepts an optional new prop
- **ThinkingIndicator** — same component, just accepts an optional label
- **Backend tool call / tool result / usage events** — already existed, no changes
- **Metadata flow** (`room_usage` → `updateMessageMetadata` → MessageBubble info popover) — already worked
