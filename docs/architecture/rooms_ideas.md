# Rooms Feature Ideas & Roadmap

> A comprehensive study of what CachiBot rooms can become — leveraging Prompture's
> multi-agent primitives, Tukuy's skill/transformation engine, and creative UI concepts.

---

## Table of Contents

1. [Response Orchestration Modes](#1-response-orchestration-modes)
2. [Bot Interaction Patterns](#2-bot-interaction-patterns)
3. [Room Automations & Workflows](#3-room-automations--workflows)
4. [Per-Room Customization System](#4-per-room-customization-system)
5. [Visual Room Experiences](#5-visual-room-experiences)
6. [Skill & Plugin Integration](#6-skill--plugin-integration)
7. [Social & Collaborative Features](#7-social--collaborative-features)
8. [Room Templates & Presets](#8-room-templates--presets)
9. [Analytics & Observability](#9-analytics--observability)
10. [Implementation Priority Matrix](#10-implementation-priority-matrix)

---

## 1. Response Orchestration Modes

We already have **parallel** (all bots at once) and **sequential** (one by one). Here's every
other orchestration pattern worth building:

### 1.1 Chain Mode

Bots respond in a defined order where **each bot's output becomes the next bot's input**.
The user sees the evolving response as it passes through the chain.

```
User message
  → Bot A processes → output_a
  → Bot B receives output_a → output_b
  → Bot C receives output_b → output_c (final)
```

**Prompture primitive:** `SkillPipeline` with `share_conversation=True` or `SequentialGroup`
with state passing between steps.

**Settings:**
- Chain order (drag-to-reorder in UI)
- Show intermediate outputs vs. only final
- Per-step timeout
- "Pass-through" option: each bot gets original message + all previous outputs

**Use cases:**
- Draft → Review → Polish writing pipeline
- Research → Analyze → Summarize knowledge pipeline
- Code → Test → Document dev pipeline

---

### 1.2 Debate Mode

Two or more bots argue opposing positions on the user's prompt. Each bot sees the other's
response and formulates a counter-argument. Configurable number of rounds.

```
User: "Should we use microservices?"
  Round 1: Bot A (pro) → Bot B (con)
  Round 2: Bot A (rebuttal) → Bot B (rebuttal)
  Final:   Bot C (judge) summarizes
```

**Prompture primitive:** `LoopGroup` with round counter + `SequentialGroup` per round.

**Settings:**
- Number of rounds (1-5)
- Assign positions (pro/con/neutral) or let bots self-assign
- Optional judge bot for final summary
- Auto-stop when consensus reached

---

### 1.3 Router Mode (Smart Dispatch)

An LLM-powered router analyzes each user message and dispatches it to the single most
relevant bot based on expertise. Only one bot responds per message.

```
User: "Fix this SQL query"
  Router → dispatches to DatabaseBot
User: "Write a poem"
  Router → dispatches to CreativeBot
```

**Prompture primitive:** `RouterAgent` with bot descriptions as routing context.
Fuzzy name matching already built in.

**Settings:**
- Routing strategy: auto (LLM decides) / keyword-based / round-robin fallback
- Bot expertise descriptions (used for routing prompt)
- Show routing decision to user (transparency toggle)
- Fallback bot when routing is ambiguous

---

### 1.4 Consensus Mode

All bots respond independently (hidden from user), then a synthesis step merges their
answers into a single high-quality response. Optionally show individual responses too.

```
User: "What's the best approach for caching?"
  Bot A → answer_a (hidden)
  Bot B → answer_b (hidden)
  Bot C → answer_c (hidden)
  Synthesizer → merged answer (shown)
```

**Prompture primitive:** `ConsensusExtraction` with strategies: majority_vote, unanimous,
highest_confidence, weighted_average.

**Settings:**
- Synthesis strategy (merge all / majority vote / best-of-N)
- Show individual responses alongside synthesis
- Confidence threshold to include/exclude answers
- Which bot acts as synthesizer (or use a dedicated model)

---

### 1.5 Relay Mode

Bots take turns responding to the conversation in a fixed rotation. Each message goes to
the "next" bot in the cycle. Like a round-robin but the user doesn't choose — it cycles
automatically.

```
Message 1 → Bot A
Message 2 → Bot B
Message 3 → Bot C
Message 4 → Bot A (loops)
```

**Settings:**
- Rotation order
- Skip bots that are on cooldown
- Allow user to @mention to override rotation

---

### 1.6 Waterfall Mode

Bots respond one at a time, but the **next bot only responds if the previous one couldn't
fully answer** (indicated by a confidence signal or explicit "I don't know").

```
User: "How do I deploy to K8s?"
  Bot A (general) → "I'm not sure about K8s specifics"
  Bot B (devops)  → full answer (stops here)
  Bot C (senior)  → never called
```

**Prompture primitive:** `SequentialGroup` with condition callbacks checking output content.

**Settings:**
- Escalation order (drag-to-reorder)
- Confidence threshold (what counts as "I can't answer")
- Max escalation depth
- Show escalation trail to user

---

### 1.7 Interview Mode

One bot acts as the **interviewer**, asking the user clarifying questions. Other bots
listen silently. Once the interviewer gathers enough context, it signals the specialist
bots to produce their responses.

```
Interviewer Bot: "What's your budget?"
User: "$500"
Interviewer Bot: "What timeline?"
User: "2 weeks"
Interviewer Bot: "Got it. Let me hand off to the team."
  → Bot B (design) responds with context
  → Bot C (dev) responds with context
```

**Settings:**
- Which bot is interviewer
- Max questions before handoff
- Handoff trigger (manual / auto after N questions / keyword)

---

## 2. Bot Interaction Patterns

Beyond orchestration modes, these are specific **interaction mechanics** between bots.

### 2.1 Bot-to-Bot Delegation (@mention chains)

Already partially implemented (depth-limited @mention chains). Extend with:

- **Delegation context**: When Bot A @mentions Bot B, include a structured handoff
  ("I need Bot B to review this code for security issues")
- **Return results**: Bot B's response gets injected back into Bot A's context for a
  final synthesis
- **Delegation limits per room**: Configurable max chain depth (currently hardcoded to 3)

**Prompture primitive:** `agent.as_tool()` — wrap Bot B as a callable tool for Bot A.

### 2.2 Bot Roles

Assign explicit roles to bots within a room that affect their behavior:

| Role | Behavior |
|------|----------|
| **Lead** | Responds first, can delegate to others |
| **Reviewer** | Only responds after another bot, provides feedback |
| **Observer** | Listens but doesn't respond unless @mentioned |
| **Judge** | Only responds to summarize/evaluate other bots' outputs |
| **Specialist** | Only responds to messages matching its expertise |

**Settings:**
- Role assignment per bot in room settings
- Role-specific system prompt injections
- Visual role badges in UI

### 2.3 Bot Memory Sharing

Bots in a room can share a persistent memory/context that survives across messages:

- **Shared scratchpad**: A text buffer all bots can read/write
- **Shared variables**: Key-value store accessible to all bots
- **Decision log**: Track what was decided and by whom

**Tukuy primitive:** `SkillContext` with namespaced scoping and snapshot/merge.

### 2.4 Bot Voting

For decisions, bots can cast votes. The room displays a vote tally:

```
User: "Should we use React or Vue?"
  Bot A: React ✓
  Bot B: Vue ✓
  Bot C: React ✓
  Result: React wins (2-1)
```

**Prompture primitive:** `ConsensusExtraction` with `majority_vote` strategy.

---

## 3. Room Automations & Workflows

User-configurable automations that trigger on events within the room.

### 3.1 Trigger System

Define triggers that fire automations:

| Trigger | Description |
|---------|-------------|
| `on_message` | Any new message in the room |
| `on_keyword` | Message contains specific keywords |
| `on_mention` | A specific bot is @mentioned |
| `on_join` | A user joins the room |
| `on_idle` | No messages for N minutes |
| `on_schedule` | Cron-like time triggers |
| `on_bot_done` | A bot finishes responding |
| `on_tool_call` | A bot uses a specific tool |
| `on_error` | A bot encounters an error |

### 3.2 Action System

Actions that triggers can fire:

| Action | Description |
|--------|-------------|
| `send_message` | Post a message as system/bot |
| `run_chain` | Execute a bot chain |
| `summarize` | Auto-summarize conversation |
| `notify` | Send notification to user |
| `set_variable` | Update room variable |
| `change_mode` | Switch orchestration mode |
| `pin_message` | Pin a message |
| `export` | Export conversation to file |
| `run_skill` | Execute a Tukuy skill |
| `transform` | Apply a Tukuy transformer chain |

### 3.3 Workflow Builder

Visual node-based editor for building multi-step automations:

```
[Trigger: on_message]
  → [Condition: contains "help"]
    → YES: [Action: route to SupportBot]
    → NO:  [Condition: contains code block]
      → YES: [Action: run chain CodeBot → ReviewBot]
      → NO:  [Action: auto-relevance default]
```

**Prompture primitive:** `SkillPipeline` with conditional steps + `Branch` composition.
**Tukuy primitive:** `Chain` + `Branch` + `Parallel` composition primitives.

### 3.4 Scheduled Messages

Bots can post on a schedule:

- Daily standup prompt at 9 AM
- Weekly summary every Friday
- Periodic check-ins ("How's the project going?")
- Reminder messages

### 3.5 Auto-Summary

Configurable auto-summarization:

- After every N messages, generate a summary
- Pin summaries for quick reference
- Collapsible summary sections in chat
- "Catch up" button that summarizes everything since last visit

---

## 4. Per-Room Customization System

Every room should feel unique. Here's what users can customize:

### 4.1 Room Personality

- **Room tone**: Professional / Casual / Fun / Technical / Creative
- **Language style**: Formal / Informal / Concise / Verbose
- **Room-wide system prompt**: Additional context injected into all bots
- **Room rules**: Displayed to users, enforced by bots (e.g., "No off-topic")

### 4.2 Bot Overrides Per Room

The same bot can behave differently in different rooms:

- **Override system prompt**: Append room-specific instructions
- **Override temperature**: More/less creative per room
- **Override model**: Use different model in this room
- **Override tools**: Enable/disable specific tools per room
- **Override persona traits**: Add room-specific personality traits

**Prompture primitive:** `Persona.extend()` and `Persona.with_constraints()` for per-room
prompt composition. Trait system for reusable prompt fragments.

### 4.3 Room Themes

Visual customization:

- **Color scheme**: Accent color per room
- **Avatar/icon**: Room icon (emoji or image)
- **Background**: Subtle background pattern or color
- **Message style**: Bubble vs. flat, compact vs. comfortable
- **Bot avatars**: Per-room bot avatar overrides

### 4.4 Room Capabilities

Toggle features per room:

| Capability | Description |
|------------|-------------|
| `tool_use` | Bots can use tools |
| `code_execution` | Bots can run code |
| `file_access` | Bots can read/write files |
| `web_access` | Bots can fetch URLs |
| `image_generation` | Bots can generate images |
| `bot_chaining` | Bots can @mention each other |
| `auto_summary` | Auto-summarize after N messages |
| `message_reactions` | Users can react to messages |
| `message_threads` | Reply threads on messages |
| `pinned_messages` | Pin important messages |

**Tukuy primitive:** `SafetyPolicy` per room — `restrictive()`, `permissive()`,
`network_only()`, `filesystem_only()`. `SecurityContext` for fine-grained restrictions.

### 4.5 Room Variables

User-defined variables accessible to all bots:

```
project_name = "CachiBot"
tech_stack = "Python, React, FastAPI"
deadline = "2026-03-01"
```

Bots can reference these in their responses. Users can set/update via `/set` command
or settings UI.

---

## 5. Visual Room Experiences

### 5.1 Mini 2D Office View

A top-down 2D view of a virtual office where bots are represented as characters at desks.
When a bot is thinking/responding, its character shows an animation.

```
┌────────────────────────────────────────────┐
│              🏢 Room: Dev Team             │
│                                            │
│   ┌─────┐        ┌─────┐                  │
│   │ 🤖A │ ···    │ 🤖B │ 💭thinking       │
│   │ CodeBot      │ReviewBot               │
│   └──┬──┘        └──┬──┘                  │
│      │              │                      │
│   ┌──┴──────────────┴──┐                  │
│   │   📋 Shared Board   │                  │
│   └─────────────────────┘                  │
│                                            │
│   ┌─────┐        ┌─────┐                  │
│   │ 🤖C │ 😴idle │ 👤  │ ← You           │
│   │ DocBot       │ Juan │                  │
│   └─────┘        └─────┘                  │
└────────────────────────────────────────────┘
```

**Features:**
- Bots move between "stations" based on what they're doing
- Thought bubbles show current bot activity
- Lines/arrows show delegation flows (A → B)
- Click a bot to see its current context/state
- Drag bots to rearrange room layout
- Ambient animations (typing, thinking, idle)

**Implementation:**
- Canvas-based rendering (HTML5 Canvas or a lightweight lib like Pixi.js)
- Positions stored in room settings
- WebSocket events drive animations (thinking/responding/idle/tool_use)
- Toggleable overlay on top of the normal chat view

### 5.2 Flow Diagram View

A live-updating node graph showing how bots interact:

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│  User    │────▶│  Router  │────▶│ CodeBot  │
│  Input   │     │  (auto)  │     │ ██████░░ │ ← progress bar
└──────────┘     └────┬─────┘     └────┬─────┘
                      │                │
                      │           ┌────▼─────┐
                      │           │ReviewBot │
                      │           │ waiting  │
                      └──────────▶└──────────┘
```

**Prompture primitive:** All group/pipeline primitives emit callbacks (`on_step`,
`on_iteration`) that can drive the visualization.

**Features:**
- Live edge highlighting as data flows between bots
- Node colors reflect state (green=active, gray=idle, red=error)
- Click node to expand details (current prompt, tokens used, etc.)
- Zoom in/out for complex chains
- Export as image/Mermaid

**Tukuy primitive:** `mermaid` plugin can generate flowchart/sequence diagrams from
room workflow definitions.

### 5.3 Timeline View

Horizontal timeline showing bot responses over time:

```
0s        5s        10s       15s       20s
├─────────┼─────────┼─────────┼─────────┤
│ CodeBot ████████░░│         │         │
│ Review  │    │████████████░░│         │
│ DocBot  │         │    │████████████░░│
│ User    ▲         ▲                   │
│         msg1      msg2                │
```

**Features:**
- Shows parallel vs. sequential execution visually
- Highlights bottlenecks (long-running bots)
- Click to jump to that point in conversation
- Token usage overlay (thicker bars = more tokens)

### 5.4 Dashboard Cards View

Instead of a single chat stream, show each bot as a card with its own response area:

```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ 🤖 CodeBot      │  │ 🤖 ReviewBot    │  │ 🤖 DocBot       │
│ ─────────────── │  │ ─────────────── │  │ ─────────────── │
│ Here's the fix  │  │ LGTM, but add   │  │ Updated docs:   │
│ for the login   │  │ error handling   │  │ ## Login Flow   │
│ bug:            │  │ on line 42.     │  │ The login...    │
│ ```python       │  │                 │  │                 │
│ def login():    │  │ Severity: Low   │  │ [View full →]   │
│ ...             │  │                 │  │                 │
│ ─────────────── │  │ ─────────────── │  │ ─────────────── │
│ 🔧 1 tool call  │  │ ✅ No issues    │  │ 📝 3 sections   │
│ 💰 $0.02       │  │ 💰 $0.01       │  │ 💰 $0.01       │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

**Features:**
- Side-by-side comparison of bot responses
- Collapsible/expandable cards
- Pin specific cards
- Drag to reorder
- Grid or column layout options

### 5.5 Kanban / Task Board View

For project-oriented rooms, a kanban board where bots move tasks between columns:

```
┌── To Do ──────┐  ┌── In Progress ─┐  ┌── Done ─────────┐
│ Fix login bug │  │ 🤖 CodeBot     │  │ ✅ Add tests    │
│ Add caching   │  │ working on:    │  │ ✅ Update docs  │
│               │  │ "Fix login"    │  │                  │
│               │  │ ██████░░ 75%   │  │                  │
└───────────────┘  └────────────────┘  └──────────────────┘
```

---

## 6. Skill & Plugin Integration

### 6.1 Room Skill Packs

Pre-bundled skill sets that can be enabled per room:

| Pack | Skills Included | Use Case |
|------|----------------|----------|
| **Data Analysis** | csv, xlsx, statistics, quickchart, json | Data-focused rooms |
| **Web Research** | http, web scraping, url_shortener, wayback | Research rooms |
| **DevOps** | git, shell, file_ops, environment | Engineering rooms |
| **Content** | markdown, text, translate, profanity | Writing rooms |
| **Finance** | finnhub, coingecko, currency, math_eval | Finance rooms |
| **Travel** | amadeus, open_meteo, geocoding, google_maps | Travel planning |
| **Support** | feedback, prompt, validation | Customer support |
| **Creative** | mermaid, qrcode, image, color | Design rooms |

**Tukuy primitive:** Instruction packs (14 categories already built: Analysis, Business,
Creative, Customer Support, Data, Developer, Education, Finance, HR, Legal, Marketing,
Product, Sales, Writing).

### 6.2 Per-Bot Skill Config

Each bot in a room can have skills configured differently:

```
Room: "Code Review"
  CodeBot:
    - python_execute: enabled, timeout=30s
    - file_read: enabled
    - shell: disabled
  ReviewBot:
    - python_execute: disabled
    - file_read: enabled
    - diff: enabled
    - profanity: enabled
```

**Tukuy primitive:** `ConfigParam` system auto-generates settings UI (sliders, toggles,
selects) per skill. Scope can be `per_bot` or `per_invocation`.

### 6.3 Transformer Chains on Messages

Apply Tukuy transformer chains to messages before/after bot processing:

**Pre-processing chain** (user message → transformed input):
```
user_message
  → strip_html_tags
  → normalize_whitespace
  → detect_language
  → (if not English) translate_to_english
  → inject_into_bot_prompt
```

**Post-processing chain** (bot output → transformed display):
```
bot_response
  → extract_code_blocks → syntax highlight
  → extract_json → validate_schema → pretty_print
  → strip_think_tags
  → profanity_filter
  → display_to_user
```

**Tukuy primitive:** `Chain`, `Branch`, `Parallel` composition primitives.

### 6.4 Custom Room Skills

Users can create room-specific skills using the Tukuy `@skill` decorator or by
writing `@instruction`-based LLM tools:

```python
# Room skill: summarize thread
@skill(risk=RiskLevel.SAFE)
async def summarize_thread(messages: list[str], max_length: int = 200) -> str:
    """Summarize the recent conversation thread."""
    ...
```

Or via instruction (LLM-powered, no code):
```yaml
name: extract_action_items
instruction: |
  Extract all action items from the following conversation.
  Format as a numbered list with assignee if mentioned.
input: conversation_text
```

---

## 7. Social & Collaborative Features

### 7.1 Message Reactions

Users and bots can react to messages with emoji:

- 👍 👎 ❤️ 😂 🤔 🎉
- Custom room-specific reactions
- Reaction counts displayed on messages
- Bots can react too (e.g., ReviewBot adds ✅ or ❌)

### 7.2 Message Threads

Reply to specific messages to create threaded conversations:

- Thread indicator on parent message
- Expandable thread view
- Bots respond in-thread when replying to a specific message
- Thread summary collapse

### 7.3 Pinned Messages

Pin important messages/decisions:

- Pin button on any message
- Pinned messages sidebar/header
- Auto-pin bot synthesis/summary messages
- Unpin with confirmation

### 7.4 Bookmarks & Favorites

Users can bookmark messages for personal reference:

- Star/bookmark toggle on messages
- Bookmarks panel in sidebar
- Search within bookmarks
- Export bookmarked messages

### 7.5 Room Presence Enhancements

- **Status indicators**: Online / Away / Do Not Disturb
- **Last seen**: "Juan was last active 5 min ago"
- **Activity feed**: "CodeBot is using python_execute..."
- **Typing indicators with preview**: See first few chars of what someone is typing

### 7.6 Shared Whiteboard

A collaborative canvas within the room:

- Draw diagrams, flowcharts, wireframes
- Bots can render Mermaid diagrams directly onto it
- Users annotate bot outputs
- Export as image

**Tukuy primitive:** `mermaid` plugin generates diagrams that could render on the canvas.

---

## 8. Room Templates & Presets

Pre-configured room templates that set up everything in one click:

### 8.1 Template Library

| Template | Bots | Mode | Skills | Description |
|----------|------|------|--------|-------------|
| **Code Review** | CodeBot + ReviewBot | Chain | git, diff, file_ops | Submit code, get structured review |
| **Brainstorm** | 3 creative bots | Debate (2 rounds) | prompt, text | Generate and challenge ideas |
| **Research Desk** | ResearchBot + AnalystBot + WriterBot | Chain | http, web, text | Research → Analyze → Write |
| **Study Group** | TutorBot + QuizBot | Relay | prompt | Learn with Q&A and quizzes |
| **War Room** | 4 specialist bots | Router | all enabled | Incident response, auto-route by expertise |
| **Writing Room** | DrafterBot + EditorBot + FactCheckerBot | Chain | text, web | Draft → Edit → Verify |
| **Data Lab** | AnalystBot + VizBot | Sequential | csv, quickchart, statistics | Analyze data, generate charts |
| **Customer Support** | TriageBot + SupportBot + EscalationBot | Waterfall | feedback, validation | Triage → Support → Escalate |
| **Daily Standup** | StandupBot | Scheduled | prompt | Daily automated standup prompts |
| **Debate Arena** | 2 debater bots + JudgeBot | Debate | text | Structured argumentation |

### 8.2 Template Customization

- Start from template, modify everything
- Save custom templates for reuse
- Share templates with other users
- Import/export template JSON

### 8.3 Quick Room Wizard

Step-by-step room creation:

```
Step 1: What's this room for? [Code Review / Research / Writing / Custom]
Step 2: Pick your bots (suggested based on purpose)
Step 3: Choose response mode (suggested based on purpose)
Step 4: Enable features (suggested based on purpose)
Step 5: Review & Create
```

---

## 9. Analytics & Observability

### 9.1 Room Dashboard

Per-room analytics panel:

- **Message volume**: Messages per day/week chart
- **Bot activity**: Which bots respond most
- **Response times**: Average time per bot
- **Token usage**: Tokens consumed per bot per day
- **Cost tracking**: Running cost total with breakdown
- **Most active hours**: Heatmap of activity

**Tukuy primitive:** `quickchart` plugin for generating chart URLs from room data.

### 9.2 Bot Performance Cards

Per-bot metrics within a room:

- Average response time
- Average tokens per response
- Tool usage breakdown
- Error rate
- User satisfaction (based on reactions)

### 9.3 Conversation Health

- **Topic drift detector**: Alert when conversation goes off-track
- **Redundancy detector**: Flag when bots repeat each other
- **Quality scorer**: Rate responses based on length, specificity, tool usage
- **Engagement tracker**: Track user interaction patterns

### 9.4 Cost Controls

- **Room budget**: Maximum spend per day/week/month
- **Per-bot budget**: Cap individual bot costs
- **Budget alerts**: Notify when approaching limit
- **Auto-throttle**: Switch to cheaper models when budget is low

**Prompture primitive:** `ModelRouter` with `cost_optimized` strategy and
`max_cost_per_call` constraints.

---

## 10. Implementation Priority Matrix

### Phase 1: Core Orchestration (High Impact, Medium Effort)

| Feature | Effort | Impact | Dependencies |
|---------|--------|--------|-------------|
| Chain mode | Medium | High | SkillPipeline from Prompture |
| Router mode | Medium | High | RouterAgent from Prompture |
| Bot roles (Lead/Observer/Reviewer) | Low | Medium | System prompt injection |
| Room variables | Low | Medium | Key-value store in room settings |
| Room-wide system prompt | Low | Medium | Settings UI + prompt injection |

### Phase 2: Interaction & Customization (High Impact, Medium Effort)

| Feature | Effort | Impact | Dependencies |
|---------|--------|--------|-------------|
| Debate mode | Medium | High | LoopGroup from Prompture |
| Consensus mode | Medium | High | ConsensusExtraction from Prompture |
| Per-bot skill config | Medium | High | SafetyPolicy from Tukuy |
| Message reactions | Low | Medium | New WS event + DB column |
| Pinned messages | Low | Medium | DB flag + UI component |
| Room templates | Medium | High | Template JSON schema + wizard UI |

### Phase 3: Workflows & Automation (Medium Impact, High Effort)

| Feature | Effort | Impact | Dependencies |
|---------|--------|--------|-------------|
| Trigger system | High | High | Event bus + rule engine |
| Workflow builder (visual) | High | High | Node editor library |
| Waterfall mode | Medium | Medium | SequentialGroup + conditions |
| Auto-summary | Medium | Medium | Scheduled task + summarizer bot |
| Room skill packs | Medium | Medium | Tukuy plugin loading per room |
| Transformer chains | Medium | Medium | Tukuy Chain composition |

### Phase 4: Visual Experiences (High Impact, High Effort)

| Feature | Effort | Impact | Dependencies |
|---------|--------|--------|-------------|
| Dashboard cards view | Medium | High | CSS grid layout + state |
| Timeline view | Medium | Medium | Canvas or SVG rendering |
| Flow diagram view | High | High | D3.js or React Flow |
| Mini 2D office | High | Very High | Pixi.js or Canvas + sprite system |
| Kanban board view | Medium | Medium | Drag-and-drop library |
| Shared whiteboard | Very High | High | Canvas + CRDT for collaboration |

### Phase 5: Social & Analytics (Medium Impact, Medium Effort)

| Feature | Effort | Impact | Dependencies |
|---------|--------|--------|-------------|
| Message threads | Medium | Medium | Thread model + UI |
| Room analytics dashboard | Medium | Medium | quickchart + data aggregation |
| Cost controls & budgets | Medium | High | Budget model + enforcement |
| Bot performance cards | Low | Medium | Aggregation queries |
| Bookmarks | Low | Low | User-message relation |
| Presence enhancements | Low | Low | WS presence events |

---

## Appendix A: Prompture Primitives Quick Reference

| Primitive | What It Does | Room Feature |
|-----------|-------------|--------------|
| `SkillPipeline` | Sequential steps with state passing | Chain mode |
| `SequentialGroup` | Execute agents in order | Sequential / Waterfall |
| `ParallelGroup` | Execute agents concurrently | Parallel mode (enhanced) |
| `LoopGroup` | Repeat with conditions | Debate mode |
| `RouterAgent` | LLM-driven dispatch | Router mode |
| `GroupAsAgent` | Wrap group as single agent | Nested workflows |
| `ConsensusExtraction` | Multi-model voting | Consensus mode |
| `agent.as_tool()` | Agent becomes a callable tool | Bot delegation |
| `Persona.extend()` | Compose system prompts | Per-room bot overrides |
| `ModelRouter` | Complexity-based model selection | Cost optimization |
| `AgentCallbacks` | Step/tool/thinking hooks | Live visualization |

## Appendix B: Tukuy Primitives Quick Reference

| Primitive | What It Does | Room Feature |
|-----------|-------------|--------------|
| `Chain` | Sequential transformation | Message pre/post processing |
| `Branch` | Conditional routing | Workflow conditions |
| `Parallel` | Fan-out/fan-in | Multi-skill execution |
| `SkillContext` | Shared state bag | Room variables / bot memory |
| `SafetyPolicy` | Capability gating | Per-room security |
| `SecurityContext` | Fine-grained restrictions | Per-bot file/network access |
| `ConfigParam` | Auto-generated settings UI | Per-bot skill config |
| `mermaid` plugin | Diagram generation | Flow visualization |
| `quickchart` plugin | Chart rendering | Analytics dashboards |
| Instruction packs | Domain skill bundles | Room skill packs |

## Appendix C: WebSocket Event Extensions Needed

New events to support advanced features:

| Event | Direction | Purpose |
|-------|-----------|---------|
| `room_chain_step` | server→client | Chain mode step progress |
| `room_route_decision` | server→client | Router mode shows which bot was selected |
| `room_debate_round` | server→client | Debate mode round indicator |
| `room_consensus_vote` | server→client | Individual bot votes before synthesis |
| `room_automation_trigger` | server→client | Automation fired notification |
| `room_reaction` | both | Message reaction add/remove |
| `room_pin` | both | Pin/unpin message |
| `room_thread_message` | both | Message in a thread |
| `room_variable_update` | server→client | Room variable changed |
| `room_bot_delegating` | server→client | Bot A is handing off to Bot B |
| `room_view_change` | client→server | User switched view mode |
