# Rooms

Rooms are multi-agent collaborative spaces where 2-4 bots work together in real time. Unlike regular one-on-one chats, rooms let you orchestrate multiple bots with different roles, response patterns, and interaction styles — all in a single conversation.

---

## Table of Contents

- [Creating a Room](#creating-a-room)
- [Response Modes](#response-modes)
  - [Parallel](#parallel)
  - [Sequential](#sequential)
  - [Chain](#chain)
  - [Router](#router)
  - [Debate](#debate)
  - [Waterfall](#waterfall)
- [Bot Roles](#bot-roles)
- [Room Settings](#room-settings)
- [@Mentions](#mentions)
- [Multi-User Collaboration](#multi-user-collaboration)
- [Real-Time Features](#real-time-features)
- [Room Marketplace](#room-marketplace)
- [Permissions & Access Control](#permissions--access-control)
- [Message Management](#message-management)

---

## Creating a Room

Rooms are created through a 3-step wizard:

1. **Room Details** — Title and optional description.
2. **Invite Bots** — Select 2-4 bots from your existing bots. At least 2 are required.
3. **Response Behavior** — Choose a response mode and configure mode-specific settings.

Once created, the room is immediately available for conversation.

---

## Response Modes

Every room has a configurable response mode that controls how bots coordinate their responses. You can change the mode at any time from the room settings.

### Parallel

All bots respond to every message simultaneously. This is the default mode — fastest execution, no waiting between bots.

**Best for:** Getting multiple perspectives at once, brainstorming, comparing approaches.

### Sequential

Bots take turns responding one by one. Each bot sees the previous bots' responses before crafting its own.

**Best for:** Building on ideas iteratively, structured review passes, knowledge accumulation.

### Chain

Output of bot N becomes input for bot N+1. Each bot in the chain builds on the previous bot's work, and the user sees the evolving response as it passes through each step.

The UI shows a **chain step indicator** ("Step 1 of 3 — BotName") so you can track progress.

**Best for:** Processing pipelines (Draft → Review → Polish), multi-stage analysis, progressive refinement.

### Router

An LLM-powered router analyzes each message and dispatches it to the single most relevant bot. Only one bot responds per message.

**Routing strategies:**
- **LLM** (default) — Claude picks the best bot based on bot descriptions and the message content.
- **Keyword** — Match the message against per-bot keyword lists you define.
- **Round Robin** — Rotate through bots in order.

The UI shows a **route decision indicator** explaining which bot was selected and why.

Observer-role bots are excluded from routing.

**Best for:** Help desks, multi-domain expert panels, topic-based dispatching.

### Debate

Bots argue positions on the user's prompt across multiple rounds. Each bot sees the others' arguments and formulates counter-arguments.

**Configurable settings:**
- **Rounds** — 1 to 5 rounds of debate (default: 2).
- **Positions** — Assign each bot a position: FOR, AGAINST, NEUTRAL, DEVILS_ADVOCATE, PRAGMATIST, or a custom position.
- **Judge** — Optionally designate one bot as judge. The judge evaluates all arguments after the final round and renders a verdict.

The UI shows **debate lifecycle indicators**: round start/end, judge evaluation, and debate completion.

**Best for:** Exploring both sides of a decision, stress-testing ideas, structured argumentation.

### Waterfall

Bots respond one at a time with conditional stopping. Each bot has a **waterfall condition**:

- **always_continue** — Always pass to the next bot regardless of the response.
- **resolved** — If this bot resolves the issue, skip remaining bots.

The UI shows **waterfall step tracking** including which bots were skipped and why.

**Best for:** Tiered support (general → specialist → escalation), progressive troubleshooting, fallback chains.

---

## Bot Roles

Each bot in a room can be assigned a role that affects how it participates:

| Role | Behavior |
|------|----------|
| **Default** | Responds normally based on the active response mode. |
| **Lead** | Prioritized in auto-selection. Guides the conversation direction. |
| **Reviewer** | Critically evaluates other bots' outputs and provides feedback. |
| **Specialist** | Domain expert. Responds to messages matching its expertise. |
| **Observer** | Only responds when explicitly @mentioned. Excluded from auto-selection and routing. |

Roles can be changed at any time from the room settings (creator only).

---

## Room Settings

| Setting | Default | Description |
|---------|---------|-------------|
| **Response Mode** | Parallel | How bots coordinate responses (see above). |
| **Cooldown** | 5 seconds | Minimum time between bot responses to prevent spam. |
| **Auto Relevance** | On | Automatically select which bots should respond when no @mention is used. |

### Mode-Specific Settings

**Debate mode:**
- `debate_rounds` — Number of argument rounds (1-5).
- `debate_positions` — Map of bot ID to position string.
- `debate_judge_bot_id` — Which bot judges (optional).

**Router mode:**
- `routing_strategy` — `llm`, `keyword`, or `round_robin`.
- `bot_keywords` — Map of bot ID to keyword list (for keyword strategy).

**Waterfall mode:**
- `waterfall_conditions` — Map of bot ID to condition (`always_continue` or `resolved`).

---

## @Mentions

Target specific bots using @mentions in your messages:

- **`@BotName`** — Direct a message to a specific bot. Only that bot responds.
- **`@all`** — All bots in the room respond, regardless of the current mode.
- **No @mention** — The response mode and auto-relevance setting determine which bots respond.

@mentions override the active response mode. If you @mention a specific bot in Router mode, that bot responds instead of the router deciding.

---

## Multi-User Collaboration

Rooms support multiple human participants:

- **Invite members** by username (creator only).
- **Remove members** — the creator can remove anyone; members can leave on their own.
- All members see the same conversation in real time.
- Each member can send messages and @mention bots.
- **Online presence** — see who's currently connected to the room.

---

## Real-Time Features

Rooms provide rich real-time feedback during bot execution:

### Typing Indicators
When a user is typing, other members see a typing indicator with their username.

### Bot Thinking
When a bot is processing, you see a thinking indicator with the bot's name ("CodeBot is thinking..."). If the model produces thinking content (e.g., extended thinking from Claude), it's displayed in real time.

### Live Tool Execution
When a bot uses a tool:
1. **Tool start** — Shows the tool name and arguments as the bot invokes it.
2. **Instruction deltas** — Streams the tool's output incrementally as it executes.
3. **Tool end** — Shows the final result with a success/failure indicator.

The "Tools (N)" button appears on the message bubble during execution, not just after completion.

### Mode-Specific Indicators
- **Chain:** "Step 1 of 3 — BotName" progress indicator.
- **Router:** "Router picked BotName because: [reason]" decision display.
- **Debate:** Round start/end markers, judge evaluation status, debate completion.
- **Waterfall:** Step progress, skip reasons ("Resolved by BotName"), stop indicators.

### Usage Stats
After each bot response, you can see token usage, cost, latency, and model information in the message info popover.

---

## Room Marketplace

The marketplace provides pre-built room templates you can install with one click.

### Browsing Templates

Templates are organized by category:

| Category | Example Templates |
|----------|-------------------|
| **Coding** | Code Review Panel (chain), Smart Help Desk (router), Bug Triage (waterfall), Full Stack Review (router) |
| **Creative** | Debate Club (debate), Writing Workshop (debate), Content Pipeline (waterfall) |
| **Productivity** | Research Team (sequential), Meeting Prep (sequential) |
| **Data** | Data Analysis Pipeline (chain) |
| **Learning** | Learning Lab (parallel) |
| **Marketing** | Marketing War Room (debate), SEO Content Pipeline (chain) |
| **Health** | Wellness Dashboard (parallel) |
| **Finance** | Financial Review (sequential) |

You can browse by category or search by name.

### Installing Templates

When you install a template:
1. Any bots required by the template that you don't already have are created automatically.
2. A new room is created with the template's configured response mode, bot roles, and settings.
3. The room is immediately ready to use.

Each template specifies the bots it needs (with roles, keywords, waterfall conditions, or debate positions as applicable), the response mode, and default settings.

---

## Permissions & Access Control

### Creator Permissions
Only the room creator can:
- Update room title, description, and settings.
- Change the response mode and mode-specific configuration.
- Invite and remove members.
- Update bot roles.
- Delete the room.

The creator cannot leave the room — they must delete it.

### Member Permissions
Any room member can:
- Send messages and @mention bots.
- View the full message transcript.
- Add or remove bots (within the 2-4 bot limit).
- Clear all messages.
- Leave the room.

### Access Enforcement
- Room membership is required to connect via WebSocket.
- Membership is verified on every API call (fetch room, messages, etc.).
- Bots that are deleted externally are detected as stale when a member connects.

---

## Message Management

### Transcript
Messages are persisted and loaded via cursor-based pagination. When you open a room, the most recent messages load first, and you can scroll up to load older ones.

### Clearing Messages
Any member can clear all messages in a room. This removes the entire transcript permanently.

### Optimistic Rendering
When you send a message, it appears in your view immediately (before the server confirms). The backend then rebroadcasts it to other members. If you're the sender, the duplicate is skipped.

### Message Metadata
Each message stores:
- Sender type (user, bot, or system).
- Sender name and ID.
- Timestamp.
- Tool calls (if the bot used tools during the response).
- Thinking content (if the bot produced thinking output).
- Usage metadata (tokens, cost, latency, model).
