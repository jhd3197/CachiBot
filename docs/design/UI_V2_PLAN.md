# CachiBot UI v2 — Implementation Plan

Status: **Phase D3 (Bot settings, design view 18) implemented** — Phases A/B merged;
Phase D3 changes are uncommitted (user commits).
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

## View → code mapping (all 14 views)

| # | View | Maps to today | Notes |
|---|---|---|---|
| 01 | Workspace: your bots | `/dashboard` (`WorkspaceView`) | **Done (Phase B)**. "Needs you / Bots / This week" + quick links, all from real data — source table below. Old dashboard kept at `/dashboard/usage`. |
| 02 | Chat, bot-first | `/:botId/chats/:chatId` (`ChatView`) | **Phase A**: new bot-first sidebar; chat header = bot + "Earlier chats". Design's question card ("Claude Code needs you to sign in") is Phase C (`approval_needed` WS payload exists; `ApprovalDialog` is the current modal). |
| 03 | Chat cards (turn endings, ask/secret/approval cards, message actions, queued messages, run summaries, artifacts) | `ChatView` + `MessageBubble` + `ApprovalDialog` | **Phase C**: card renderer driven by existing WS payloads (`approval_needed`, `scheduled_notification`, `job_update`, `artifact`). Hover actions (copy/regenerate/fork/pin) extend `MessageBubble`. |
| 04 | Chat + computer preview | `/:botId/chats/:chatId` | **Backend not built** (no Mini Vela/computer API). Phase D; defer. |
| 05 | Computer full window | — | **Backend not built.** Phase D. |
| 06 | Bot-built web page on its computer | Artifacts (`ArtifactsView`/`ArtifactPanel`, `/api/assets`) | Partial analog today: artifacts render in a side panel. Full "runs on its computer" needs the computer backend. Phase D. |
| 07 | Computer terminal / coding agent diff | coding agent tools (`coding_agent` capability, `getCodingAgents`) | CLI runs exist; streamed terminal/diff view on a computer needs backend. Phase D. |
| 08 | Take-over (yellow ring) | — | Needs computer backend. Phase D. |
| 09 | Computer off / turn on | — | Needs computer backend. Phase D. |
| 10 | Files sheet | `AssetsView`, `/api/assets`, artifact files | **Phase C**: open assets as a modal sheet from chat header (sheet styling lands with tokens in Phase A). |
| 11 | Mini Vela spec (states) | — | Reference-only; states materialize with Phase D backend. |
| 12 | Runs | `/:botId/work` (`WorkView` history) + automations run log (`automations` API) | **Phase B/C**: day-grouped run list can be composed from existing work job APIs (`/api/work`, jobs in `bots` store). |
| 13 | Routine editor | `/:botId/automations` (`AutomationsView`, `ScriptEditorView`, schedules API) | **Phase C**: plain-words editor over existing `Schedule`/`BotFunction` APIs. |
| 18 | Bot settings | `/:botId/settings` (`BotSettingsView`) | **Done (Phase D3)**. Anchored one-column layout (max 640px) per v2b `source/18-bot-settings.html`; sections General/Knowledge/Skills/What it can use/Connections/Advanced, all from real APIs; Computer section omitted (no backend). |

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

## Phase D3 scope (Bot settings, view 18)

New `frontend/src/components/views/BotSettingsView.tsx` (+ `styles/v2/bot-settings.less`)
at `/:botId/settings`, styled with phase A tokens/`BotAvatar`. Centered 640px column
(exact values from the v2b bundle `source/18-bot-settings.html`: column `max-width: 640px`,
page padding `32px 24px 64px`, column gap 24px), a 30px pill nav, then anchored
sections (`#general` `#knowledge` `#skills` `#what-it-can-use` `#connections`
`#advanced`) so other pages can deep-link (`/:botId/settings#knowledge`), then:

### Built

- **Header**: back button → the bot's chat (`/{botId}/chats`), centered 16px/600
  "Name settings" title, close button → back in history when there is any, else the
  bot's chat. **Role gating (design view 12)**: settings is Editor+ — `useBotAccess`
  users without `canEdit` are redirected to the bot's chat; nothing is greyed out.
- **General**: 72px `BotAvatar` + 28px pencil → popover with the existing icon/color
  picker (`AppearanceSection`); Name / Title / Instructions fields and a Model picker
  (`ModelSelect`, "Use the default from Settings") on one form; Save at the bottom
  keeps the legacy behavior — `updateBot` (bot store → `PUT /api/bots/{id}`),
  capabilities excluded (they toggle live), 2s "Saved!".
- **Knowledge**: one row per document (real filename, size/chunks/"added" date,
  processing/failed status, Remove with confirm → knowledge API), a Notes row
  (real count from `listNotes`) opening a sheet with the existing Notes manager
  (+ stats, search tester, custom instructions editor), and "Add documents" opening
  a sheet with the existing uploader + full document list (chunks dialog included).
- **Skills**: one switch row per skill (real `skillsApi` activate/deactivate,
  active-first sort), Delete for local/installed skills, "New skill" (existing
  install dialog) and Refresh.
- **What it can use**: per-bot capability switches (Files/Code/Git/Web/Data/This
  PC/Work/Contacts) via live `updateBot({capabilities})`, hidden when the platform
  globally disables the capability (old rule); a "Manage individual tools" link
  keeps the old per-tool manager reachable at `/:botId/tools`; then Plugins: one
  row per external plugin (real version/type/loaded state) with Configure opening
  the extracted `PluginDetailPanel` in a sheet (config params, enable/disable,
  uninstall), plus "Add plugin" (archive install) and Reload.
- **Connections**: platform connections with live status (same
  `connection-status-change` WS event as the management panel), unconnected
  platform adapters ("Not connected" → Connect, from the real platform registry),
  coding agents when the capability is on (Installed/Not installed → scroll to
  Advanced), configured provider keys (app-wide; "Key added" → `/settings/keys`),
  and "Add connection". Manage/Connect open the existing `BotConnectionsPanel` in a
  sheet. Section hidden when every source is empty/unreachable.
- **Advanced**: grouped by 13px/600 subheads — **Model** (utility/image/audio
  models, generation toggles, voice settings, coding agents panel via
  `ModelsCapabilitiesSection`, `showDefault={false}` since General owns the default
  model), **Environment** (`BotEnvironmentPanel`), **API & webhooks**
  (`DeveloperPanel`), **Danger zone** (export → `exportBot` download, clear all
  chats → real `POST /api/bots/{id}/chats/_clear` with confirm, delete → confirm
  modal → `deleteBot`, hidden for the default bot), plus "Reset to default
  settings". Embedded legacy panels are re-scoped to v2 in
  `styles/v2/bot-settings.less` (sections become simple groups with 13px/600
  headings; bordered cards keep 16px padding; form fields and the model-picker
  trigger match the main column; delete/reset modals get the legacy modal styles
  re-scoped under `.bot-settings`).
- **Deep links**: sections have stable ids; `/:botId/settings#<section>` scrolls to
  the section (Workspace "Connections"/"Knowledge" quick links use this; the old
  `settingsSection` store mechanism is no longer used by this view).

### Behavior changes

- `/:botId/settings` renders the new anchored one-column view instead of the old
  section-per-page `SettingsView` (which still serves the legacy `developer` view).
- `/:botId/plugins` redirects to `/:botId/settings#what-it-can-use` (plugins are
  managed there); `/:botId/plugins/:pluginName` (plugin pages) and `/:botId/tools`
  (per-tool manager) keep working.
- Capability switches and skill/plugin toggles apply immediately (live `updateBot` /
  API calls); only General fields wait for Save.

### Phase D3 - not backed yet (hidden from the design)

- **Computer section** — the computer backend (Mini Vela) does not exist; the
  section and its nav chip are omitted entirely, and the "Computer" capability
  switch is not listed under What it can use.
- **Notifications toggle** — no per-bot notification setting exists anywhere in the
  backend or stores; the row is omitted (same decision as the Phase A sidebar
  notifications icon).
- **Avatar image upload** — the `Bot` model has `icon` + `color` only (no avatar
  image field); the pencil opens the existing icon/color picker. `BotAvatar`'s `src`
  prop stays unused for bots.
- **Coding agent "sign in"** — agents have no sign-in state; rows show real
  installed/not-installed availability from `getCodingAgents()` and Manage scrolls
  to the coding agents panel in Advanced.

## Later phases

- **Phase C — Chat cards, files sheet, routine editor, bot settings layout**
  (views 03, 10, 13, 14) on existing APIs.
- **Phase D — The bot's computer** (views 04–09, 11): requires a new backend
  (Mini Vela desktop streaming, take-over, power state). Not started; no
  pretend/disabled controls ship in the meantime.

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
