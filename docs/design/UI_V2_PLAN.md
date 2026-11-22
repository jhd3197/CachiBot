# CachiBot UI v2 — Implementation Plan

Status: **Phase C2 (views 12–15: where everything lives) implemented** on top of
Phase A shell + Phase B Workspace + Phase C chat (not committed).
Authoritative design bundle: [`docs/design/cachibot-v2-final-views/`](./cachibot-v2-final-views/)
(`index.html` gallery, `screens/` PNGs, `source/` HTML). The bundle is copied unmodified
from Juan's final-views export — including provider/product names that appear in the
reference artwork; those names are design references only, not commitments.

## Design intent (from the bundle README)

Calm, dark, bot-first. One sidebar lists bots. The chat header is just the bot.
No split view: anything the bot browses, runs or builds would open on its own
"computer" (Mini Vela), shown as a small live preview next to the chat and full
window when opened. Files is its own sheet.

## Design tokens (extracted from `source/*.html`)

All v2 chrome is scoped under a `.ui-v2` class and exposed as CSS custom
properties in `frontend/src/styles/v2/tokens.less` so legacy panels are untouched.
Dark values are the design's exact values; light-theme equivalents are provided
so the existing theme preference keeps working.

| Token | Dark value | Use |
|---|---|---|
| `--v2-bg-main` | `#0b0c0e` | Main canvas, chat background |
| `--v2-bg-sidebar` | `#0e0f11` | Sidebar background |
| `--v2-bg-panel` | `#121315` | Cards / sheets (design also uses `#131417`) |
| `--v2-bg-button` | `#1a1b1e` | Secondary buttons, bubbles, chips row hover |
| `--v2-bg-hover` | `#1d1e21` | Hover states, status chip, icon tile |
| `--v2-bg-selected` | `#17181b` | Selected bot row, active Workspace button |
| `--v2-border` | `#232428` | All hairline borders |
| `--v2-text` | `#ececec` | Primary text |
| `--v2-text-secondary` | `#a3a3a3` | Secondary text, icons |
| `--v2-text-tertiary` | `#8b8b8b` | Timestamps, previews, placeholders |
| `--v2-green` | `#4ade80` | Links, accent (hover `#86efac`) |
| `--v2-eye` | `#0b0c0e` | Avatar eye dots (always dark on colored circle) |

Typography: Inter (already loaded app-wide) / system-ui sans; JetBrains Mono for
code. Base sizes: chat/message text 15px/1.55–1.6; row name 14px/600; preview
13px; chip & timestamps 12px; chat header name 16px/600; page H1 24px/700.

Geometry: sidebar **300px** at 1440 viewport; sidebar padding 14px 10px, column
gap 10px; bot rows 12px radius, 10px padding, 12px inner gap; **avatar 40px**
circle (32px "needs you" card, 30px chat header, 22px inline message, 88px
settings); **search 40px** tall, 12px radius; icon buttons 32px, 8px radius;
**Workspace button 44px**, 10px radius, 32px icon tile; chat header 64px;
composer pill 26px radius with 36px circular attach/send; primary button is
white (`#ececec` bg, `#0b0c0e` text), 32–42px tall, 9–10px radius.

## View → code mapping (25 views, design bundle v2b)

The design bundle was updated (v2b): views were renumbered (Runs 12→16,
Routine editor 13→17, Bot settings 14→18) and new views were added: side
tasks (11a–11c), where-things-moved (12), rooms + account menu (13), chat More
menu (14), voice mode (15), app settings (19), activity log (20).

| 01 | Workspace: your bots | `/dashboard` (`WorkspaceView`) | **Done (Phase B)**. "Needs you / Bots / This week" + quick links, all from real data — source table below. Old dashboard kept at `/dashboard/usage`. |
| 02 | Chat, bot-first | `/:botId/chats/:chatId` (`ChatView`) | **Done (Phase C)**. Centered 820px column, day separators from real timestamps, #1a1b1e bubbles, bot turns with 22px BotAvatar + name label, collapsed tool-activity line, v2 composer (26px pill, 36px round +/send, model pill in footer). |
| 03 | Chat cards (turn endings, ask/secret/approval cards, message actions, queued messages, run summaries, artifacts) | `ChatView` + `MessageBubbleV2` + `ChatCards.tsx` | **Done (Phase C, backed subset)** — see "Phase C" below for exactly which cards shipped and which have no real source yet. |
| 04 | Chat + computer preview | `/:botId/chats/:chatId` | **Backend not built** (no Mini Vela/computer API). Phase D; defer. |
| 05 | Computer full window | — | **Backend not built.** Phase D. |
| 06 | Bot-built web page on its computer | Artifacts (`ArtifactsView`/`ArtifactPanel`, `/api/assets`) | Partial analog today: artifacts render in a side panel. Full "runs on its computer" needs the computer backend. Phase D. |
| 07 | Computer terminal / coding agent diff | coding agent tools (`coding_agent` capability, `getCodingAgents`) | CLI runs exist; streamed terminal/diff view on a computer needs backend. Phase D. |
| 08 | Take-over (yellow ring) | — | Needs computer backend. Phase D. |
| 09 | Computer off / turn on | — | Needs computer backend. Phase D. |
| 10 | Files sheet | `AssetsView`, `/api/assets`, artifact files | **Phase D4**: modal sheet from a Files button in the chat header. |
| 11 | Mini Vela spec (states) | — | Reference-only; needs the computer backend. |
| 11a–c | Side tasks | — | **New feature (principle 9)**, not UI-only. Proposed as phase E after D. |
| 12 | Where the old icons went | sidebar icon row → homes | **Done (Phase C2)**. Icon row removed; each entry moved per view 12 (see Phase C2 below). |
| 13 | Rooms + account menu | `RoomsView`, `/settings`, `/admin/logs`, `/users` | **Done (Phase C2)**. Rooms group in the sidebar; account menu at the bottom; room header/composer restyled. |
| 14 | Chat More menu | chat header | **Done (Phase C2)**. Bot settings/Runs/Routines/Knowledge + plugin pages + Export/Clear; Files reserved for D4. |
| 15 | Voice mode | `VoiceView` → chat | **Done (Phase C2)**. Mic in the composer switches the same chat to voice; `/:botId/voice` redirects to `?voice=1`. |
| 16 | Runs | `/runs` (new) + `/:botId/work` | **Phase D1**. Work merges into Runs. |
| 17 | Routine editor | `/:botId/automations` | **Phase D2**. Automations become Routines. |
| 18 | Bot settings | `/:botId/settings` | **Phase D3**: General, Knowledge, Skills, What it can use, Connections, Computer (hidden until backend), Advanced. |
| 19 | App settings | `/settings` | **Phase D5**: General, Appearance, Models, Data, People, Advanced, About. |
| 20 | Activity log | `/admin/logs` | **Phase D5**: admins only, linked from Runs. |

## Phase A scope (this branch)

- `docs/design/cachibot-v2-final-views/` copied verbatim; this plan.
- `frontend/src/styles/v2/tokens.less` — v2 tokens (`.ui-v2` scope, dark + light).
- `frontend/src/components/common/Avatar.tsx` — `BotAvatar`: custom image if the
  bot has one, otherwise a colored circle (`bot.color`, deterministic) with two
  dark eye dots. No initials, no emoji, no hardcoded names/data.
- `frontend/src/components/layout/BotListSidebar.tsx` — ONE bot-first sidebar
  replacing `BotRail` + `BotSidebar`:
  - `+` opens the existing creation wizard (`setCreateBotOpen`).
  - Search filters real bots (name/description).
  - Rows: real bot name, description chip, latest-chat preview/timestamp when a
    chat exists. Selected bot highlighted while in its chat.
  - Clicking a bot opens its most recent real chat (else the chats route).
  - Bottom: compact workspace menu (access-filtered, old gear/rail destinations:
    Rooms, Voice, Work, Automations, Tools, Plugins, Developer, Bot Settings,
    Global search, Exec logs, App settings, GitHub) + **Workspace** button →
    `/dashboard`.
  - Notifications icon: **omitted** (no notifications backend/behavior exists).
- `frontend/src/components/chat/ChatsSheet.tsx` — "Earlier chats" sheet from the
  chat header preserving multi-chat UX: new chat, platform chats, pin, export,
  clear/archive, delete.
- `MainLayout` rewired to the single sidebar; mobile drawer (hamburger, overlay,
  Escape-to-close, closes on navigate, works ≤375px); Electron `TitleBar`
  untouched.
- Chat header: `BotAvatar` + bot name + "Earlier chats" button.

## Phase B scope (Workspace, view 01)

New `frontend/src/components/views/WorkspaceView.tsx` (+ `styles/v2/workspace.less`)
at `/dashboard`, styled with phase A tokens/`BotAvatar`. Centered 760px column
(exact values from `source/01-workspace.html`: `max-width: 760px`, main padding
`40px 32px 64px`, header row space-between with "New bot" pinned right), then:
"Your bots" H1 + white **New bot** button (existing create wizard), then:

### Data source per element (all real; nothing placeholder)

| Element | Source | Notes |
|---|---|---|
| Needs you · pending approvals | `approval_needed` WS payload → `stores/approvals.ts` (in-memory, per tab) | Item: bot avatar, action text, **Open chat** → that bot/chat. Approvals only exist while the agent run's WebSocket is connected, so entries are live state, cleared on answer/run end/disconnect. |
| Needs you · stuck runs | `GET /api/bots/{id}/executions/running`, `startedAt` older than 1h | Aggregated "Runs" item: "N runs have been stuck since <date>". **Clear them** cancels each via existing `POST /api/bots/{id}/executions/{execId}/cancel`. |
| Needs you · failed runs | `GET /api/bots/{id}/executions?status=error&from_date=<7d>` | One item per bot with count; **Open runs** → `/{botId}/automations`. |
| Needs you · connection errors | `GET /api/bots/{id}/connections`, `status === 'error'` | **Open connections** → `/{botId}/settings` (Connections section). |
| Needs you (empty) | — | Section hidden entirely when there are no items. |
| Bots row · name/description/avatar | bot store + `BotAvatar` | Row click opens the bot's latest chat (same rule as sidebar); chevron. |
| Bots row · status | approvals store (Waiting on you) › running executions or in-flight chat run via `activeRun` prop (Running) › Idle | "Idle" only claimed when the executions API answered; otherwise the word is omitted. |
| Bots row · next routine | `GET /api/bots/{id}/schedules` (enabled, earliest future `nextRunAt`) | "Name at 8:00 AM"; omitted when no upcoming routine. |
| Bots row · messages this week | local chat store (`stores/bots.ts`), messages with `timestamp` in last 7 days | The chat store is the UI's own message history; count is computed client-side. |
| Bots row · routines | `GET /api/bots/{id}/schedules`, enabled count | Hidden when the API can't be reached (never faked as 0). |
| This week · Messages | chat store 7d total | Same computation as per-bot rows. |
| This week · Tokens / Cost | `stores/connections.ts` usage store, `daily` slice of last 7 days | Store is fed by real `usage` WS payloads (tokens + cost in USD). |
| This week · Usage details | route `/dashboard/usage` → existing `DashboardView` | Old dashboard preserved, not deleted. |
| Quick links | Routines → `/{bot}/automations`; Runs → `/{bot}/work`; Connections → `/{bot}/settings` (connections section); Knowledge → `/{bot}/settings` (knowledge section); Settings → `/settings` (app settings) | `bot` = active bot, else first bot; bot-dependent pills hidden when no bots exist. |

Per-bot API failures resolve to `null` per figure, so uncomputable values are
hidden instead of displayed as zeros. No backend changes were needed in Phase B.

### Supporting changes

- **App-level WebSocket** (`useWebSocket()` now mounted in `MainLayout`, passed
  to `ChatView` as props): the agent connection outlives the chat view, so runs
  and their approvals stay alive while navigating to Workspace — required for
  "Waiting on you" and approval items to be real. Run-scoped events (message,
  usage, thinking, tool calls, done/error, approval_needed) are attributed via a
  run-context ref instead of the active-chat ref, so background runs land in the
  right chat even after navigation. `ChatView` gates typing/thinking/tool UI to
  the run's chat. Behavior change: leaving a chat no longer cancels the run
  (use the cancel button, or send another message, as before).
- **Approval dialog fixed**: `ApprovalDialog` previously received a no-op
  `onApprove` (scaffold bug); it now sends `wsClient.sendApproval` and clears
  the pending state, so approvals are answerable from any view.
- **Mobile top bar**: shows `BotAvatar` + bot name on bot routes (tapping opens
  the bot's chat) or the app-view name (Workspace/Settings/Exec logs) on app
  routes; the letter-avatar block is gone. `chat-header__bot-info` is hidden
  below 1024px so the chat no longer duplicates the bot title (the header row
  stays for the "Earlier chats" button).

## Phase C scope (bot-first Chat + chat cards, views 02/03)

`ChatView` restyled to the design with a new `MessageBubbleV2`, `ChatCards`,
`FindInChatBar` (all under `frontend/src/components/chat/`) and
`styles/v2/chat.less` (scoped to `.ui-v2`, dark values from
`source/02-chat.html` / `03-chat-cards.html`, light via the existing v2
token equivalents). Rooms and other legacy panels still use the original
`MessageBubble` and keep their look.

### Chat per design 02

- Centered 820px column (messages + composer); bubbles measure ~70% ≈ 584px.
- Day/time separators from real message timestamps: "Today 9:14 AM",
  "Yesterday", "Mon, Nov 17".
- User bubbles right-aligned `#1a1b1e` pill (10px 16px, 18px radius, 15px/1.55);
  bot turns: 22px `BotAvatar` + 13px/600 name label, then the bubble (15px/1.6).
- Tool activity collapsed into one muted line under the bot name
  ("✓ Read 3 files · ran code 2 times"), built from the turn's real
  `toolCalls` (verb map over the actual backend tool names); expands to the
  existing per-call details (`MessageToolCallItem`). Streaming tool calls are
  restyled to the same quiet line style.
- Composer: 26px-radius pill (`#0e0f11`, border `#232428`, padding 7px) with a
  36px round "+" that attaches a file through the real chat-assets API
  (`POST /api/bots/{id}/chats/{chatId}/assets`, upload status shown under the
  composer), "Message <BotName>" placeholder, and a 36px round send button
  (white `#ececec`; stop square while a run is active). Model pill, slash
  commands, @agent mentions, workspace selector and reply bar all stay —
  the model pill sits in the footer row under the composer.
- Chat header: `BotAvatar` + name + "Earlier chats" (unchanged). Mobile
  (<1024px): the chat header row is hidden entirely and the app top bar shows
  hamburger + `BotAvatar` + name + history button (opens the same
  `ChatsSheet`) — one bar, no duplicate header.

### Cards per design 03 (backed subset only)

| Card | Real source | Actions |
|---|---|---|
| Approval | `approval_needed` WS payload, answered inline in the chat (never blocks; typing continues) | "Allow once" / "Deny" via `wsClient.sendApproval`; clears the module pending state and the Workspace "Needs you" entry (`stores/approvals.ts`). `ApprovalDialog` stays mounted as the fallback for approvals belonging to other/background chats (it suppresses itself for the visible chat). |
| Failed / error | real WS `error` event — `chatStore.error` is now `{message, code, chatId}` attributed to the run's chat (previously set but never rendered) | "Try again" resends the last user message; "Change the model" opens the model pill selector. |
| Stopped | user pressed stop in this chat | Muted "You stopped this." line + "Continue" that resends the interrupted message. |
| Routine result | `scheduled_notification` payload (flagged on the message as `metadata.scheduled`) | Clock-icon muted line + the bubble. |
| Message actions | hover icons per design | Bot: Copy / Regenerate (resends the preceding user message) / Tools / Thinking / Info. User: Edit (inline edit-and-resend with Cancel/Send per design, Escape cancels) / Copy. Actions float over the turn boundary (zero layout space when hidden), reveal on hover/focus and stay inline-visible on touch devices. |
| Code block | markdown rendering | Header per design: language + Copy button. |
| Find in chat | purely client-side over the loaded messages | Ctrl/Cmd+F bar with "2 of 5" count and up/down (Enter / Shift+Enter), Escape closes; matches the actual rendered text with mark highlights (current match stronger and scrolled into view). |
| Jump to latest | client-side scroll state | Pill appears when scrolled up with new messages ("3 new messages") or while the bot works; auto-scroll now only follows the stream when pinned to the bottom. |
| File | artifacts already produced by runs | Existing `ArtifactCard`s restyled to the v2 file-card look inside the chat. |

### Behavior changes

- User bubbles are added locally on send (and the matching server echo is
  swallowed), so a send always shows exactly one user message — even when the
  run errors out before the server's own echo (previously the bubble silently
  depended on that echo).
- The chat no longer force-scrolls on every token: it follows only while the
  viewport is near the bottom; scrolling up shows the "Jump to latest" pill.
- Typing is allowed while a run is active (send stays a stop button until the
  run ends) — previously the textarea was disabled during runs.
- WS `error` payloads are now shown in the chat that owned the failed run
  (they were stored but never rendered).
- Answering an approval inline clears it from the Workspace "Needs you" list,
  same as the dialog.
- `scheduled_notification` messages no longer carry the `[Scheduled]` text
  prefix (it became the clock-icon line).

### Phase C — not backed yet (design 03 cards NOT built, no real source)

- **Question card** (ask_user with options/free text) — no `ask_user` WS event
  or payload exists.
- **Secret card** (secret_request) — no such payload; secrets are configured
  in bot settings, not requested mid-run.
- **CLI sign-in / install cards** (setup_required, cli_login/cli_missing) —
  no setup-required payload from the backend.
- **Connection card** — `connection_status` events exist but carry no
  reconnect action/skip flow.
- **Hand-off card / take-over** — needs the computer backend (Phase D).
- **Voice note card** — voice messages are not part of the chat message model.
- **Check back later** line — no follow-up/deferred-run payload.
- **Run summary card** — `job_update` exists but carries no per-step tool
  summary to render (job detail lives in WorkView).
- **Budget failure card** — the `error` code is not specialized
  (`budget_exceeded` not emitted).
- **Approval "Always allow for this bot"** — the WS `approval` message only
  supports `{id, approved}`; no always-allow backend.
- **Message actions: Read aloud / Fork / Pin / More** — no TTS, fork, or
  per-chat pin backend (room pin is rooms-only).
- **Queued "Send now" row** — the WS protocol has one run per connection; no
  queue/steering.
- **Unread divider / pinned header icon** — no read-cursor or chat-pin store.

Views 10 (Files sheet) and 13→18/19 (routine editor, bot settings layout,
app settings) remain open for Phase D.

## Phase C2 scope (views 12–15: where everything lives)

Sidebar (`BotListSidebar` + `styles/v2/shell.less`), chat header
(`ChatMoreMenu`), voice (`VoiceMode`), room header/composer (`RoomPanel`,
`InputArea`), one small backend addition. Exact values from
`source/12-where-things-moved.html`, `13-rooms-and-account.html`,
`14-more-menu.html`, `15-voice-mode.html`.

### Sidebar (view 13)

- "Bots" heading row (15px/600) with a search icon and a + new-bot icon
  (existing create wizard). The Phase A inline search field was replaced by
  the search icon → `GlobalSearchDialog` (which now also searches bots by
  name/description, preserving that filter capability) and **Ctrl/Cmd+K
  anywhere** (mounted in `MainLayout`). Notifications bell stays **omitted**
  — no notifications source exists.
- Bot rows unchanged.
- **Rooms group** under the bots: 28px heading row (12px/600, tertiary) + "+"
  (existing `CreateRoomDialog`, kept reachable even with zero rooms). Rows:
  stacked 22px `BotAvatar`s (-10px overlap, sidebar-colored ring), room name,
  and a real subtitle — `lastMessage` (`"<sender>: <content>"`) from the new
  `GET /api/rooms` field, else `"N bots"`. Clicking opens the existing room
  view (`/{botId}/rooms/{roomId}`).
- Bottom icon row **removed**. Bottom = **Workspace** button, then the
  **Account** row (user initial in a 32px `#2a2b2f` circle + name + gear)
  opening the account menu (`V2Menu`): Your account → `/settings`, Settings →
  `/settings`, Usage ("this month") → `/dashboard/usage`, an **Admin** section
  (Activity log → `/admin/logs`, People → `/users` with the real count from
  `GET /api/auth/users`) shown only to `role === 'admin'`, About and help →
  `/settings` (About section lives in General; GitHub link is there), Sign out
  (existing store logout → `/login`). Everything is hidden by role, never
  greyed.

### Where the old icons went (view 12)

| Old icon | New home in C2 |
|---|---|
| Chats | The bot's sidebar row; earlier chats behind the history icon (unchanged) |
| Rooms | Sidebar Rooms group |
| Voice | Mic button in the composer (Operator+) → voice mode in the same chat |
| Work | Chat More menu › Runs → `/{bot}/work` (real Runs page is D1) |
| Automations | Chat More menu › Routines → `/{bot}/automations` (D2) |
| Tools / Plugins / Developer | Chat More menu (editor+) → existing pages until Bot settings D3 |
| Bot settings | Bot name in the chat header (editor+) or More › Bot settings |
| Search | Sidebar search icon + Ctrl/Cmd K → `GlobalSearchDialog` |
| Exec logs | Account menu › Activity log (admins) → `/admin/logs` |
| Settings | Account menu → `/settings` |
| GitHub | Settings › About › Documentation link → repo |

Plugin-provided view pages (enabled view plugins) moved from sidebar icons
into the chat More menu under "From plugins" (hidden when none).

### Chat header + More menu (views 02/14)

- The bot name is now a button → Bot settings (`/{botId}/settings`), editor+.
- "..." opens `ChatMoreMenu`: section titled with the bot name; **Bot
  settings** (editor+), **Runs** (operator+; suffix "N needs you" only from
  the real live approvals store count for this bot), **Routines** (operator+;
  suffix = real enabled count from `GET /api/bots/{id}/schedules`, hidden on
  failure), **Knowledge** (editor+ → settings knowledge section); **From
  plugins** section (hidden when no enabled view plugins); then **Export
  chat** (client-side markdown download of the loaded messages — real data,
  no endpoint needed) and **Clear chat** (existing behavior: platform chats
  call the clear API, local chats clear the store; two-step confirm).
- A Files button is reserved in the actions cluster for phase D4 — not built.
  No Computer button/preview (blocked, as before).

### Voice mode (view 15)

- Mic button in the composer (Operator+ only, hidden for viewers) switches
  the **same chat** into voice mode (`VoiceMode` in `components/chat/`).
- Reuses the existing pipeline (`useVoice` → `VoiceClient` WS, VAD, STT →
  agent → TTS) — nothing new server-side. The existing voice backend already
  persists both sides of each turn into the chat when a chat id is sent
  (`save_transcripts`, on by default), so `VoiceMode` creates the chat first
  when none exists and the design's "Everything said is saved here as text"
  is literally true; the saved messages appear in the chat after leaving
  voice mode.
- Per design: 112px `BotAvatar` with two soft rings in the bot color while
  listening/speaking, status line ("<Bot> is talking · tap Interrupt or just
  start speaking" / "Listening · just start speaking" / transcribing /
  thinking), live transcript lines (You 15px muted, <Bot> 18px), bottom pill
  with mute toggle (40px), a waveform driven by the real audio level, the
  saved-as-text note, **Interrupt** (only while the bot is speaking — the
  pipeline supports interruption only then) and **Back to typing**.
- `/:botId/voice` stays reachable: `VoiceView` redirects to the bot's chat
  with `?voice=1`, which `ChatView` picks up to enter voice mode.

### Room view (view 13)

- Room header restyled: stacked 22px bot avatars, room name (16px/600), a
  real members line ("Writer, Researcher and you" — bot names + other member
  usernames + "you"), presence counters (real online/total), **Files** (→ the
  existing room assets view) and **⋯ More** (existing view modes Chat/Cards/
  Timeline/Tasks with active check, Export JSON, Room settings for the
  creator). Nothing was deleted — the old toggle/export/settings all live in
  the More menu.
- Room composer restyled to the v2 pill ("Message the room · type @ to pick
  a bot"); @-mentions and typing indicators unchanged.

### Backend (small, test-covered)

- `GET /api/rooms` and `GET /api/rooms/{room_id}` now include
  `lastMessage` (most recent room message, null when empty) — feeds the
  sidebar Rooms subtitle. Implemented in `RoomResponse.from_room` +
  `routes/rooms.py` via the existing `get_messages(limit=1)`.
- Tests: `tests/test_rooms_api.py` (auth required, lastMessage populated/
  empty, non-member 404). `ruff check`, `ruff format --check`, `mypy
  cachibot` and `pytest -q` all pass; the rooms tests skip in environments
  without PostgreSQL (conftest's designed skip path) and run where the test
  DB exists.

### Behavior changes

- The sidebar no longer has the inline bot-name filter or the bottom icon
  row; bot search lives in Ctrl/Cmd K (now also matching bots).
- Leaving voice mode disconnects the voice channel; transcripts already
  saved to the chat remain as normal messages.
- The chat header name navigates for editors+ instead of being inert.
- Old `VoiceView` UI (connect/PTT/controls page) is replaced by the chat
  voice mode; its route redirects.

### Phase C2 — not backed yet (hidden, no fake data)

- **Notifications bell** (views 13/14) — no notifications backend exists.
- **Files button** in the chat header (view 14) — phase D4; space reserved.
- **Computer button / preview pane** (view 14) — needs the computer backend
  (phase D); deliberately not built.
- **"Needs you" on Runs beyond live approvals** — stuck/failed runs
  aggregation is a D1 Runs-page concern; the menu suffix uses only the live
  per-tab approvals count.
- **Room voice mic** (view 13's room composer shows a mic) — the voice
  pipeline is per bot chat; no room voice exists, so the room composer omits
  the mic.
- **Dedicated "Your account" page** — links to `/settings` until app
  settings D5 gives it a real home.
- **Voice PTT mode / voice settings** — the old VoiceView page carried a
  PTT/VAD toggle; the v2 voice mode uses the saved preference and exposes no
  settings UI (D-phase concern).

## Later phases

- **Phase D** — D1 Runs (16), D2 Routine editor (17), D3 Bot settings (18),
  D4 Files sheet (10), D5 App settings + Activity log (19, 20).
- **Phase E (proposal)** — side tasks (11a–c); needs backend support.
- **The bot's computer** (views 04–09, 11): requires a new backend. Not
  started; the Computer button and preview pane stay hidden.

## Known limitations / decisions

- Views 04–09 and 11 need backend infrastructure that does not exist; Phase A/B
  ship no computer UI at all (no dead buttons).
- The usage store is per-browser (localStorage), so "This week" tokens/cost
  reflect activity seen by this client; messages come from the same local chat
  history the UI renders. Server-side per-bot aggregates can replace this in a
  later phase if cross-device numbers are needed.
- Pending approvals are in-memory per tab by nature (the server holds them only
  while the run's WebSocket is connected); "Needs you" approval items are live
  state, not history.
- Notifications icon omitted until a notifications feature exists.
- Bot groups and rail drag-reorder from v1 have no surface in the v2 shell;
  the rail ordering is still honored when sorting the bot list, and
  `stores/rail.ts` remains for future use.
- The v2 shell is dark-by-design; light mode gets close-equivalent tokens.
  Legacy panels (dashboard, settings, work, rooms, etc.) keep their existing
  look in Phase A to avoid cross-panel regressions.
- Reference HTML/PNGs keep their original artwork (including third-party
  provider names); shipped code contains no fake data.
