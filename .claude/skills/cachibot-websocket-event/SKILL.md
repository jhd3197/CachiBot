---
name: cachibot-websocket-event
description: Add new WebSocket message types and event handlers to CachiBot's real-time streaming system. Use this skill when adding new real-time events, live updates, or bidirectional WebSocket communication — e.g., "add live progress events", "stream file upload status", "add approval request events".
metadata:
  author: cachibot
  version: "1.0"
---

# CachiBot WebSocket Event Creation

Add new real-time WebSocket events spanning the backend server, frontend hook, and store integration.

## Architecture Overview

```
Backend (Python)                    Frontend (TypeScript)
─────────────────                   ─────────────────────
websocket.py                        api/websocket.ts
  ├── ConnectionManager               └── WebSocketClient
  ├── WSMessage model                      ├── send(type, payload)
  └── run_agent() handler                  └── onMessage(handler)

models/websocket.py                 hooks/useWebSocket.ts
  ├── WSMessageType enum               └── message handler switch
  └── Payload models                       └── store actions

                                    stores/bots.ts
                                      └── state + actions
```

## Step 1: Backend — Add Message Type

Edit `cachibot/models/websocket.py`:

```python
class WSMessageType(str, Enum):
    # ... existing types ...
    YOUR_EVENT = "your_event"      # Server -> Client
    YOUR_REQUEST = "your_request"  # Client -> Server (if bidirectional)
```

Add payload model (if it carries data):

```python
class YourEventPayload(BaseModel):
    """Payload for your_event messages."""

    item_id: str
    status: str
    data: dict = {}
```

Add a factory method to `WSMessage`:

```python
class WSMessage(BaseModel):
    type: WSMessageType
    payload: dict = {}

    # ... existing factory methods ...

    @classmethod
    def your_event(cls, item_id: str, status: str, data: dict | None = None) -> "WSMessage":
        return cls(
            type=WSMessageType.YOUR_EVENT,
            payload={"item_id": item_id, "status": status, "data": data or {}},
        )
```

## Step 2: Backend — Send the Event

In the relevant handler (e.g., `websocket.py` or a service), send the event:

```python
from cachibot.api.websocket import manager

# Send to a specific client
await manager.send(client_id, WSMessage.your_event(
    item_id="abc",
    status="completed",
    data={"result": "..."},
))

# Or broadcast to all clients of a bot
await manager.broadcast(bot_id, WSMessage.your_event(...))
```

### Sending from `run_agent()` in websocket.py

If the event is triggered during agent execution, add it to the streaming loop:

```python
async def run_agent(client_id: str, ...):
    async for event in agent.run_stream(message):
        match event.event_type:
            # ... existing handlers ...
            case StreamEventType.your_event:
                await manager.send(
                    client_id,
                    WSMessage.your_event(event.data["item_id"], event.data["status"]),
                )
```

### Handling Client -> Server Messages

If adding a new client-initiated message type, add a handler in the WebSocket connection loop:

```python
# In websocket.py, inside the message handling loop:
elif msg_type == WSMessageType.YOUR_REQUEST:
    payload = data.get("payload", {})
    # Process the request
    result = await process_your_request(payload)
    # Optionally send a response event back
    await manager.send(client_id, WSMessage.your_event(...))
```

## Step 3: Frontend — Add TypeScript Types

Edit `frontend/src/types/index.ts`:

```typescript
// Add to WSMessageType (or wherever message types are defined)
export type WSMessageType =
  | 'chat'
  | 'cancel'
  | 'thinking'
  | 'tool_start'
  | 'tool_end'
  | 'message'
  | 'usage'
  | 'error'
  | 'done'
  | 'your_event'     // new
  | 'your_request'   // new (if client -> server)

// Add payload interface
export interface YourEventPayload {
  item_id: string
  status: string
  data: Record<string, unknown>
}
```

## Step 4: Frontend — Handle in useWebSocket Hook

Edit `frontend/src/hooks/useWebSocket.ts`:

```typescript
// Import store actions
import { useYourStore } from '../stores/your-store'

// Inside the message handler switch:
case 'your_event': {
  const payload = msg.payload as YourEventPayload
  // Update store with the event data
  useYourStore.getState().handleYourEvent(payload)
  break
}
```

## Step 5: Frontend — Send from Client (if bidirectional)

Add a send method to the WebSocket client or expose through the hook:

```typescript
// In api/websocket.ts — add to WebSocketClient class:
sendYourRequest(data: YourRequestPayload): void {
  this.send('your_request', data)
}

// In hooks/useWebSocket.ts — expose in the hook return:
const sendYourRequest = useCallback((data: YourRequestPayload) => {
  wsClient.sendYourRequest(data)
}, [])

return { ..., sendYourRequest }
```

## Step 6: Frontend — Store Integration

Add handling in the relevant Zustand store:

```typescript
// In your store:
interface YourState {
  // ... existing state ...
  handleYourEvent: (payload: YourEventPayload) => void
}

export const useYourStore = create<YourState>()(
  (set) => ({
    // ... existing state ...
    handleYourEvent: (payload) => set((state) => {
      // Update state based on the event
      return {
        items: state.items.map((item) =>
          item.id === payload.item_id
            ? { ...item, status: payload.status }
            : item
        ),
      }
    }),
  })
)
```

## Existing Event Types Reference

### Server -> Client
| Type | Payload | Purpose |
|------|---------|---------|
| `thinking` | `{ content }` | LLM reasoning content |
| `tool_start` | `{ id, tool, args }` | Tool execution begins |
| `tool_end` | `{ id, result, success }` | Tool execution completes |
| `message` | `{ role, content, messageId, replyToId }` | Streaming text content |
| `usage` | `{ totalTokens, promptTokens, completionTokens, totalCost, ... }` | Token/cost stats |
| `error` | `{ message, code }` | Error occurred |
| `done` | `{ replyToId }` | Response complete |
| `platform_message` | `{ botId, chatId, role, content, ... }` | External platform message |
| `approval_needed` | `{ id, tool, args, risk_level, ... }` | Tool needs user approval |

### Client -> Server
| Type | Payload | Purpose |
|------|---------|---------|
| `chat` | `{ message, systemPrompt, botId, chatId, model, ... }` | Send a message |
| `cancel` | `{}` | Cancel current generation |
| `approval` | `{ id, approved }` | Respond to approval request |

## Checklist

- [ ] `WSMessageType` enum extended in `cachibot/models/websocket.py`
- [ ] Payload model defined (if structured data)
- [ ] Factory method added to `WSMessage` class
- [ ] Event sent from the appropriate backend handler
- [ ] TypeScript types added in `frontend/src/types/index.ts`
- [ ] Handler added in `frontend/src/hooks/useWebSocket.ts`
- [ ] Store action created to process the event
- [ ] If bidirectional: send method added to WebSocket client
