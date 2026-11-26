# CachiBot UI v2 — Implementation Plan

Status: phases A, B, C, C2 and D1 merged into dev; D3 (bot settings) in this branch.
Authoritative design bundle: [`docs/design/cachibot-v2-final-views/`](./cachibot-v2-final-views/)
(`index.html` gallery, `screens/` PNGs, `source/` HTML). **Updated v2b bundle**
(20 views, Runs = view 16, destinations map = view 12) lives outside the repo
at `/workspace/design-v2/v2b/cachibot-v2-final-views/` and is referenced but
not copied. The in-repo bundle is copied unmodified from Juan's final-views
export — including provider/product names that appear in the reference
artwork; those names are design references only, not commitments.

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
| 04 | Chat + computer preview | `/:botId/chats/:chatId` + `BotInspectorPanel` › Computer | **Done (C4)**. The inspector's Computer block is the design's aside: 16:10 live state card, one real activity line, open windows (app + title); all gated on the Docker probe. |
| 05 | Computer full window | `/:botId/computer` (`ComputerOpenView`) | **Done (C4)**. Desktop preview or the selected window's frame full size; top bar with real driver state, Take over / Hand back (operator+), Stop; chat keeps working on the existing WS. |
| 06 | Bot-built web page on its computer | `/:botId/computer?view=<id>` | **Done (C4, presentation)**. A browser window's real frame shown full size; hidden when there is no such window (never a faked page). The chat-page card ("Running on its computer · localhost:5173") has no real chat-content source — not rendered. |
| 07 | Computer terminal / coding agent | `/:botId/computer?view=<id>` | **Done (C4, presentation)**. A terminal window's real frame full size when one exists. Run meta (duration, files changed) stays in chat/tool output; nothing is invented. |
| 08 | Take-over (yellow ring) | `ComputerOpenView` + `ChatCards` (`ComputerNeedsYouCard` / `ComputerDrivingLine`) | **Done (C4)**. Amber ring + Needs you tag on the real needs-you state with its reason; Take over / Hand back (operator+; hidden for viewers); Skip this step via `needs-you/respond {action: skip}`; input (click/right click/scroll/type/key) on a selected window's frame only while this user holds the lease. |
| 09 | Computer off / turn on | `BotInspectorPanel` › Computer + `BotSettingsComputerSection` | **Done (C4)**. Off/asleep cards with Turn on / Wake (a stray watch never wakes it); the true facts (This PC · Docker · internet-not-your-network · keeps /workspace · sleeps after 10 min idle). "Use a cloud computer instead" does not exist — no cloud backend. |
| 10 | Files sheet | `FilesSheet`, chat assets + artifacts stores | **Done (Phase D4)**. Modal sheet from a Files pill in the chat header (Files in the More menu on mobile); room header Files icon opens the same sheet in room mode. C4 adds the "On its computer" /workspace section with Open on computer (operator+, awake-only). |
| 11 | Mini Vela spec (states) | the computer UI itself | **Done (C4)**. Closed/Open/Needs you/Asleep are the real states of the Computer card — no marketing spec screen. |
| 11a–c | Side tasks | `ChatView` + `SideTaskReply` + `SideTaskChatView` + `stores/side-tasks` | **Done (Phases E4 + E5 "Side-task replies")**. Backend E1–E5 (`/side-tasks` REST, `side_task_update` + `message_update` WS, `chats.parent_chat_id`, thread replies); see "Side-task replies" below. |
| 12 | Where the old icons went | sidebar icon row → homes | **Done (Phase C2)**. Icon row removed; each entry moved per view 12 (see Phase C2 below). |
| 13 | Rooms + account menu | `RoomsView`, `/settings`, `/admin/logs`, `/users` | **Done (Phase C2)**. Rooms group in the sidebar; account menu at the bottom; room header/composer restyled. |
| 14 | Chat More menu | chat header | **Done (Phase C2)**. Bot settings/Runs/Routines/Knowledge + plugin pages + Export/Clear; Files reserved for D4. |
| 15 | Voice mode | `VoiceView` → chat | **Done (Phase C2)**. Mic in the composer switches the same chat to voice; `/:botId/voice` redirects to `?voice=1`. |
| 16 | Runs | `/runs` (new) + `/:botId/work` | **Done (Phase D1)**. Cross-bot run list, quick-tasks checklist and automations timeline; operator+; Activity log link for admins. |
| 17 | Routine editor | `/:botId/automations` | **Done (Phase D2)**. Routines list (plain-words rows) + `RoutineEditorView` over the Schedule API; scripts/functions under Advanced; `/automations` redirects. |
| 18 | Bot settings | `/:botId/settings` | **Done (Phase D3)**. One column with General / Knowledge / Skills / What it can use / Connections / Computer (C4, probe-gated) / Advanced, all from real APIs. |
| 19 | App settings | `/settings` | **Done (Phase D5)**. General, Appearance, Models, Data, People, Advanced, About in one 640px column. |
| 20 | Activity log | `/admin/logs` | **Done (Phase D5)**. Admins only; grid of every run with filters and expandable real error/output. |

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

## Phase D1 scope (Runs, views 16 + "where things moved" map 12)

New `frontend/src/components/views/RunsView.tsx` (+ `styles/v2/runs.less`) at
`/runs`, styled with the phase A tokens/`BotAvatar` and the exact values from
`source/16-runs.html` (760px column, padding 32px 32px 64px, 26px H1, 32px
chips with 16px radius, 32px row avatars, expanded card at margin-left 58px).
There is no non-admin cross-bot executions endpoint, so the page fans out the
existing per-bot APIs over the user's bots and merges/dedupes client-side.

Per the v2b "where things moved" map: **Work merged into Runs** (its runs are
the "work"-typed rows with real status; Needs you / Running / Failed
filters), **quick tasks became a checklist in Runs** (real todos API), the
**Automations timeline went into Runs**, and **Exec logs → Activity log**
(linked from Runs, admins only). Runs is **operator+** — viewers get an
explanation state instead of data, and Workspace entry points hide.

### Data source per element (all real; nothing placeholder)

| Element | Source | Notes |
|---|---|---|
| Runs list | `GET /api/bots/{id}/executions?from_date=<90d>&limit=200` + `/executions/running` per **operable** bot, merged by id | 90d window = widest retention tier; the server only returns what it kept. A bot whose calls fail is dropped; if every call fails the page shows an error state with retry. |
| Quick tasks checklist | `GET /api/bots/{id}/todos/open` per operable bot | Checking a box calls `POST /todos/{id}/done`, ✕ calls `/dismiss`; the item leaves the list. Hidden when no open todos. Adding new todos is not offered here (a cross-bot page has no natural owner bot; todos are created via chat/API and managed in `/:botId/work` quick tasks). |
| Timeline | `GET /api/bots/{id}/timeline` per operable bot | Events are written by job_runner and the scripts API. Day-grouped like runs, capped at 60, hidden when empty. |
| Operator+ gate | per-bot `access_level` from the bots list (`botAccessRank` in `hooks/useBotAccess.ts`) | Runs only fetches bots the user can operate (rank ≥ 2; admins always). No operable bot → "Runs is available to operators and above." |
| `?bot=<id>` | URL param | Preselects the bot filter (used by Workspace failed-runs items). Unknown ids are ignored. |
| Stuck banner | running executions with `startedAt` older than 1h | Hidden when none. "Clear them" cancels each via `POST /api/bots/{id}/executions/{execId}/cancel`, then reloads. |
| Filter chips | computed from the loaded runs | All / Failed / Running with real counts (` · N` when > 0); Running includes stuck runs. **Needs you is hidden entirely when its count is 0** (the source is real — live pending approvals / `credit_exhausted` — but an always-empty chip is useless). If it disappears while active, the filter falls back to All. |
| Needs you | executions with `status: credit_exhausted`, or still `running` with a pending tool approval in their chat (`stores/approvals.ts`) | Approvals are live WS state per tab; the match is botId + chatId. |
| "All bots" dropdown | bot store | Client-side botId filter. |
| Day groups | `startedAt`/`createdAt` local day via `dayGroup()` | Today / Yesterday / "22 Feb"-style labels, newest first; one group per day for runs and timeline alike. |
| Row meta | `<bot> · <trigger> · <time> · <duration>` | Trigger label from `sourceType` (schedule→"routine", work/job→"work", manual+chatId→"asked in chat"); duration as "4s" / "0:41" / "1:52". |
| Status | `status` + stuck rule | Done / Running / Failed (error+timeout) / Stuck / Cancelled / Needs you, with the design's icon colors. |
| Expanded lines | `GET /api/bots/{id}/executions/{execId}/lines`, falling back to the log's `error`/`output` | Per-line steps are **not backed yet**: nothing in the backend calls the log-line append API, so `/lines` returns empty and the card falls back to `error` (red ✗) / `output` (mono block), which `job_runner` does write. The lines call stays so per-step output appears once the backend writes it. |
| Open in chat | only when `chatId` is set | Navigates to `/{botId}/chats/{chatId}`. |
| Run again | only for script (`POST /scripts/{id}/run`), function (`POST /functions/{id}/run`) and schedule (its `functionId` with the schedule's stored params) sources | Hidden for work/manual/api/job executions — no real re-run endpoint exists for those. |
| Footer retention | `GET /api/bots/{id}/executions/stats` → `retentionDays` | New backend key, same value the log retention service enforces (`get_tier_limits().log_retention_days`). Hidden when the API can't be reached. |
| Export | client-side CSV of the rows currently loaded (respecting the active filters) | Downloads `cachibot-runs.csv`; hidden when there are no rows. |
| Activity log | link to `/admin/logs` | Admins only (`user.role === 'admin'`), per the moved map. |

### Backend change

- `GET /api/bots/{id}/executions/stats` now returns `retentionDays`
  (`cachibot/api/routes/executions.py`), mirroring
  `cachibot/services/log_retention.py`. Covered by the new
  `tests/test_executions_api.py` (stats shape, 422 on bad period, 401 without
  token).

### Behavior changes

- Workspace quick link **Runs** and the Needs-you **failed runs** / **stuck
  runs** items appear only for users who can operate at least one bot
  (operator+), matching the moved map. Failed-runs items deep-link to
  `/runs?bot=<id>`; the stuck item keeps "Clear them" and its text opens
  `/runs`.
- `/:botId/work` **stays reachable** (sidebar Work icon, untouched): Runs
  covers work runs and quick tasks, but not work-item management (create,
  complete/fail/cancel, per-work detail with goal/progress/result) — that
  stays in WorkView until the design moves it.
- `/runs` is linked from the mobile top bar as "Runs".
- **Timestamps**: the backend serializes stored datetimes with a plain ISO
  string (no offset) — the app-wide convention, and SQLite drops tz info on
  write. `parseApiDate` (`frontend/src/lib/utils.ts`) is the single helper
  that treats offset-less API strings as UTC (offset-bearing strings parse
  as-is); RunsView and WorkspaceView (stuck runs, stuck-since date, next
  routine time) use it instead of `new Date(apiString)`. RunsView day-group
  keys and labels derive from the same local-date computation, so one group
  per day.

### Phase D1 - not backed yet

- Stuck-banner explanation sentence from the design ("They lost their worker
  when the server restarted.") — dropped; there is no real source for *why* a
  run is stuck.
- Expanded-card summary paragraph ("The run stopped at step 3 because…") —
  dropped; that would be a generated explanation, not real data.
- Per-line execution steps (see table above) — the backend never appends log
  lines; the card falls back to the real `error`/`output` fields.
- Adding quick tasks from Runs — no owner-bot choice on a cross-bot page;
  creation stays in chat / `/:botId/work` quick tasks.
- Cross-bot server-side aggregation/pagination — the page caps at 200 runs
  per bot (API max) and doesn't page beyond it.

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

- **Notifications toggle** — no per-bot notification setting exists anywhere in the
  backend or stores; the row is omitted (same decision as the Phase A sidebar
  notifications icon).
- **Avatar image upload** — the `Bot` model has `icon` + `color` only (no avatar
  image field); the pencil opens the existing icon/color picker. `BotAvatar`'s `src`
  prop stays unused for bots.
- **Coding agent "sign in"** — agents have no sign-in state; rows show real
  installed/not-installed availability from `getCodingAgents()` and Manage scrolls
  to the coding agents panel in Advanced.

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
- **Hand-off card / take-over** — built in C4 from the real `needs_you` state
  (`ComputerNeedsYouCard` in the chat, the banner in the full-window surface);
  it never invents a reason — no reason, no card.
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
- **Files button** in the chat header (view 14) — built in phase D4.
- **Computer button / preview pane** (view 14) — built in C4: the chat-header
  Computer toggle shows only while the Docker probe is available and drives
  the right-hand inspector's Computer block (see "Phase C4" below).
- **"Needs you" on Runs beyond live approvals** — stuck/failed runs
  aggregation is a D1 Runs-page concern; the menu suffix uses only the live
  per-tab approvals count.
- **Room voice mic** (view 13's room composer shows a mic) — the voice
  pipeline is per bot chat; no room voice exists, so the room composer omits
  the mic.
- **Dedicated "Your account" page** — D5 gives it a real home: the Your
  account block in Settings › General (with change-password), deep-linked
  from the account menu as `/settings/account`.
- **Voice PTT mode / voice settings** — the old VoiceView page carried a
  PTT/VAD toggle; the v2 voice mode uses the saved preference and exposes no
  settings UI (D-phase concern).

## Phase D5 scope (App settings view 19 + Activity log view 20)

### App settings (`AppSettingsView` rewritten, `styles/v2/settings.less`)

One narrow 640px column (exact values from `source/19-app-settings.html`:
padding 32px 24px 64px, top bar 32px back/title/close buttons, 30px section
pills, sections separated by 28px padding + hairline, 48px rows with a right
28px action, 40px bordered select rows, 40x24 switch). Section pills deep-link
to `/settings/<section>`; **legacy deep links keep working via aliases**:
`keys` → models, `users`/`groups` → people, `account` → general (scrolls to
the Your account block). Unknown/unauthorized tabs redirect to `/settings`.
Bare `/settings` no longer auto-scrolls (the header + pills stay visible);
section links scroll smoothly. Old tabs → new sections: everything keeps its
name except keys/users/groups (mapped as above).

Data source per element (all real; nothing placeholder):

| Element | Source | Notes |
|---|---|---|
| Your account (username/email rows) | `useAuthStore().user` | Real profile from the auth API. |
| Change password | `POST /api/auth/change-password` | The API existed but had no UI; the dialog hashes via the existing `api/auth.ts` helper (same as login). |
| Show thinking / Show cost | `useUIStore` + `PUT /api/config` (`show_thinking`/`show_cost`) | Same dual write as the quick settings dialog. |
| Time zone / Workspace rows | `useConfigStore().config` (`timezone`, `workspacePath` from `GET /api/config`) | Read-only — no endpoint changes them, so no fake "Change" control (the old Browse button was a dead no-op and is gone). |
| Start on boot | `window.electronAPI.get/setStartOnBoot` | Electron only; hidden in the browser (as before). |
| Mobile pairing + firewall | `POST /api/mobile/pair-token`, firewall status/enable endpoints | QR modal logic unchanged, restyled row trigger. |
| Setup wizard | existing onboarding store → `/onboarding` | Unchanged behavior. |
| Theme | `useUIStore.setTheme` | Design's exact segmented control (4px padding, 12px radius, 30px options). |
| Accent color / sidebar collapsed | `useUIStore` | Existing palette data; v2 ring styling. |
| Default/utility/embedding models | `useModelsStore` (+ `PUT /api/config` `{model}` for the default, mirroring the quick settings dialog) | `ModelSelect` in the design's 40px box. |
| Providers | `useProvidersStore` (`configured`, `masked_value`, `extra_keys`) + models count from `useModelsStore().groups` | Design rows: name + "Key added"/"No key" (endpoints: "Endpoint set"/"No endpoint"), Add key/Change opens inline edit (save/remove/show, Azure extra keys kept). The big CachiBot.ai promo banner was dropped — its two links live on the CachiBot.ai provider row (Sign up / Dashboard). |
| Keep runs and logs | `GET /api/bots/{id}/executions/stats` → `retentionDays` | Same key Runs uses; row hidden when the API can't be reached (no Change — no endpoint). |
| Export everything / Import | `localStorage` backup (existing export) + new real import | Import restores the exact keys Export writes, then reloads. The old Import button was a dead no-op. |
| Telemetry | `useTelemetryStore` + telemetry preview/reset endpoints | Toggle uses the shared `.v2-switch`; view-report and reset-ID modals kept. |
| Bot data manager | local chat/job/task/usage stores + `clearBotPlatformData` | Component kept as-is (inner markup/classes untouched) inside the Data section. |
| Clear cache / Delete all data | existing electron `clearCache` / localStorage clear | Danger row per design (red title, "Can't be undone"), confirm modals kept. |
| People (manager+) | `GET /api/auth/users` count (admins) + `GET /api/groups` | Users row → `/users` (the full management page stays reachable); Groups row opens the existing groups manager inline (create/delete group, members). Hidden entirely for regular users (pill + section), never greyed. |
| Activity log row (Advanced) | admins only → `/admin/logs` | Per the design's Admins badge. |
| Server row | `window.location.host` | Read-only — no server-switch UI exists, so no "Change". |
| Agent settings | `PUT /api/config` (`approve_actions`, `temperature`, `max_iterations`) + local config store | The old Advanced tab rendered these with no-op handlers (fake controls); they now really persist via the same endpoint the quick settings dialog uses. Sandbox timeout dropped (PUT doesn't accept it). |
| Keyboard shortcuts | static list | Informational, matches real shortcuts. |
| Version / update check | `useUpdateStore` (pip) / `window.electronAPI` (desktop) + `GET /api/health` | "Check again" re-runs the real check; "up to date" only claimed from a real check result. |
| Source code | https://github.com/jhd3197/CachiBot | The old sidebar GitHub link, now the design's Source code row. Build/Python/Platform rows from health info. |

Account menu (`BotListSidebar`) deep links: Your account →
`/settings/account`, Settings → `/settings/general`, Usage →
`/dashboard/usage`, People → `/users` (admins), Activity log → `/admin/logs`
(admins), About and help → `/settings/about`.

### Activity log (`GlobalLogView` rewritten, `styles/v2/activity-log.less`)

Admins only (route already requires admin). 980px column per
`source/20-activity-log.html` (padding 32px 24px 64px, back link to
Settings › Advanced, 26px H1, chips 32px/16px radius, grid table
84px/150px/170px/1fr/76px/56px with a 12px tertiary header, rows 11px 12px
radius 10, expanded card at margin-left 108px). All data from the existing
`admin_executions` API:

| Element | Source | Notes |
|---|---|---|
| Rows | `GET /api/admin/executions?from_date=&limit=200` | Time (HH:MM:SS, tabular), bot (20px `BotAvatar` + name; falls back to the real botId when the local bot store doesn't know the backend id), tool (`executionType`, mono), what (`sourceName`), result, took (`0.4s`/`0:41` formats). |
| Result | `status` | Done / Failed (error+timeout, red) / Running (blue) / Cancelled / Needs you (`credit_exhausted`, amber — same mapping Runs uses). |
| Chips | All / Failed · N / Running · N | Counts from the loaded rows; Failed/Running hidden at 0 (never an always-empty chip); active chip falls back to All when its count hits 0. **Blocked chip: hidden — see "not backed yet".** "Cancel all" appears only while executions are running (real `POST /executions/cancel-all`). |
| Bot filter / period | client-side bot dropdown; Today / 7 days / 30 days → `from_date` | Today = local midnight, matching the design's "Today ▾". |
| Export | `GET /api/admin/executions/export` | Server CSV, respects bot + period. |
| Expanded card | the log's real `error` (pre) / `output` (pre) | The design's "Stopped before running: …" explanation sentence is the blocked-state copy — dropped with the Blocked state. Actions: Open the chat (only when `chatId` is set), Copy details (real JSON of the row), Cancel (running only). |
| Errors section | `GET /api/admin/executions/errors?days=7` | Error spotlight kept from the old dashboard, restyled; hidden when empty. |
| Costs section | `GET /api/admin/executions/costs?days=30` | Per-bot cost table kept from the old dashboard, restyled; hidden when empty. |

### Backend changes

None. Both views use existing endpoints (`/api/config` PUT, auth
change-password, admin executions). No new tests needed.

### Behavior changes

- Settings is a single scrolling column; the old left tab rail is gone.
  Pills jump between sections and are also the deep links.
- The old Advanced tab's sandbox timeout / approval / temperature / max
  iterations controls were non-functional (no-op handlers); approval,
  temperature and max iterations now persist via `PUT /api/config`, the
  sandbox timeout is hidden (no write endpoint).
- The old Data tab's Import button did nothing; Import now restores a real
  export.
- Your account finally has a home (General section) and change-password has
  a UI for the long-existing API.
- Activity log period filter defaults to Today (the design's "Today ▾");
  the old logs/errors/costs tabs became the table + two sections below it.
- Mobile top bar label for `/admin/logs` is "Activity log" (was "Exec logs").

### Phase D5 - not backed yet (hidden, no fake data)

- **Activity log "Blocked" state** (chip, amber status, and the "Stopped
  before running: … / Nothing was read." explanation card) — the
  executions API has no blocked status and no policy-reason fields; nothing
  ever writes them. Failed runs get the same visual treatment with their
  real `error` text instead.
- **Design's General-section controls** Language ("English") and Open on
  start ("Workspace") — no language/locale or start-page setting exists.
  (Time zone is shown read-only from the real server config.)
- **Models "Budget" row** ("$20 · switches to cheaper models at 80%") — no
  budget/limit backend exists.
- **Advanced "Developer mode" toggle** ("Show raw events and IDs") — no
  developer-mode setting exists; the real developer-ish surfaces (platform
  tools dialog) stay where they were (wizard/command palette).
- **About "Licenses" row** — no license inventory endpoint/file exists.
- **Server "Change" action** — no server-switch UI/endpoint (value shown
  read-only), same as the removed dead "Browse" workspace button.
- **User invites** (People) — no invite API exists; user management is the
  real `/users` page (create/edit/deactivate), groups the real groups API.

## Later phases

- **Phase D** — D2 Routine editor (17), D3 Bot settings (18), D4 Files sheet (10).

## Phase D4 scope (Files sheet, view 10)

New `frontend/src/components/chat/FilesSheet.tsx` (+ `styles/v2/files.less`)
— the modal sheet from design `source/10-files.html` (620px dialog on the
`#0e0f11` sidebar surface, 18px radius, 32px pill chips, 30×36 extension
tiles, rows with a right-side action). It opens from:

- a **Files pill** in the chat header, left of "Earlier chats" (desktop
  ≥1024px — the chat header row is hidden below that), and
- the **room header's Files icon** (C2), now in room mode instead of
  switching the panel to the old assets view mode.

On mobile the sheet is **full-screen** (below 640px) and Files sits at the
top of the chat **More menu** (`ChatMoreMenu` gained an optional
`onOpenFiles`) — no new top-bar button, per the phase brief.

### Data source per element (all real; nothing placeholder)

| Element | Source | Notes |
|---|---|---|
| Sheet rows — chat files | `GET /api/bots/{id}/assets` (bot-level listing, new) | One call returns all chat-owned assets of the bot, newest first (default limit 200, max 500). The server matches a chat asset to the bot via the chats table (platform chats) **or** the `bot_id` recorded in the asset metadata at upload/capture time (browser-local chats have no chats row). `ownerId` carries the chat id for per-chat downloads. |
| Row origin (Made by / Sent by you) | `uploadedByBotId` / `uploadedByUserId` on each asset | Written by the real upload path (user) and by the agent's file auto-capture / sandbox document capture (bot). Assets with neither (rare) appear only under All. |
| Row meta "date · size" | `createdAt` (via `parseApiDate`) + `sizeBytes` | Today / Yesterday / weekday (within the week) / "Nov 17" labels; size in B/KB/MB (`49 B`, `908 B`, `4 KB`). Nothing is invented when a field is missing. |
| Download | existing `downloadChatAsset` / `downloadRoomAsset` | Per-row blob download with the original filename. |
| Open rows | artifacts store (`stores/artifacts.ts`) | Artifacts whose `chatId` belongs to one of the bot's chats, minus those already backed by a chat asset (document artifacts carry `metadata.assetId`; same-title-same-chat dedupes too). **Open** closes the sheet and opens the existing artifact panel (`setActive`) — the design's "Open on computer" has no computer backend. |
| Chips | computed from the loaded rows | All / Made by \<Bot\> / Sent by you; a chip that would always be empty is hidden, and an active filter falls back to All. |
| Room mode | `GET /api/rooms/{id}/assets` | Subtitle "Files shared in \<room\>"; chips become All / Made by bots / Sent by you (bot chip hidden when empty, as always). Upload stays in the sheet header and delete on row hover, so the old room assets view loses nothing. |
| Footer ("Files live in the bot's /workspace…", design 10) | — | **Dropped** — no /workspace persistence story exists; it would be fiction. |

### Behavior changes

- Chat header gained the Files pill (desktop); mobile top bar gains Files at
  the top of the More menu. The Files sheet opens over the chat from either.
- Room header Files icon opens the same sheet in room mode. The old `assets`
  view mode stays in code (and `AssetsView` untouched) but is no longer the
  entry point; list/upload/download/delete all remain reachable via the
  sheet. Chat-mode asset delete was already unreachable in the v2 shell
  (only the dead `AssetsView` chat branch offered it) and stays that way.

### Backend change

- `GET /api/bots/{id}/assets` (`cachibot/api/routes/assets.py`, viewer-or-higher
  via `require_bot_access`) returns a bot's chat assets newest-first with a
  `limit` param (default 200, max 500); `AssetRepository.get_by_bot` joins the
  chats table on `bot_id` and also matches assets whose metadata carries the
  bot id (recorded at upload/capture time in the chat upload route, the agent
  file auto-capture and the sandbox document capture — local browser chats
  have no chats row, a plain join alone would lose them). Room assets are
  excluded.
- Tests: `tests/test_bot_assets_api.py` mocks the repository and the auth
  user lookup (no PostgreSQL — runs in CI): 401 without a token, rows
  serialize with `ownerId`/origin fields, `limit` passed through with a 422
  outside 1–500. `ruff`/`ruff format`/`mypy`/`pytest` all pass.

### Phase D4 — not backed yet (hidden, no fake data)

- **"Open on computer"** row action (design 10) — built in C4 as the "On its
  computer" /workspace section (operator+, awake-only); the artifact rows keep
  opening the app's artifact panel.
- **Date on artifact rows** — the artifact model has no timestamp, so those
  rows show no date (size only when the emitter provided
  `metadata.fileSize`, which document artifacts do).
- **Chat assets created before the bot-level listing existed** carry no
  `bot_id` metadata, and browser-local chats from before that change have no
  chats row either — those rows are only matched when their chat is in the
  chats table (platform chats). Rows created after the change are fully
  covered.
- **Open on an artifact whose chat has no loaded messages** — the ChatView
  empty-hero branch returns early without rendering the artifact panel
  (pre-existing layout branch, not introduced here); normal artifact chats
  have messages and work.

## Phase C4 — the bot's computer UI (views 04–09, 11) + the right-hand inspector

The C1–C3 backend (Docker probe, `ComputerService`, frame/input proxy, the
`computer` plugin) meets the v2 shell. Desktop and web only; mobile is
untouched. Full backend notes:
[`VIRTUAL_COMPUTER_PLAN.md`](./VIRTUAL_COMPUTER_PLAN.md) "C4".

### Built

- **One right-hand column** in the shell (`BotInspectorPanel`, toggled from
  the chat-header **Computer** button per design 04 and its own collapse
  button; state persisted in the ui store; hidden below 1200 px and on
  routes without a selected bot — it never covers the left bot list).
- **The Computer block** (design 04's aside) with the real states of view 11:
  off (greyed face + Turn on), asleep (+ Wake), building/starting (the C1
  build progress, real step/total + last line), awake (live preview from
  the C2 hook: refetch by `previewRevision`, watch heartbeats), needs_you
  (amber ring + tag). Under it the one real activity line (with Stop,
  operator+) and the open-windows list (app + title → opens that window).
- **`/:botId/computer`** (view 05): the desktop preview or a selected
  window's frame full size (views 06/07 are the real window frames — never a
  faked page; a gone window falls back to the desktop preview). Top bar:
  who is driving, Take over / Hand back (operator+; hidden for viewers),
  Stop. **Take-over (view 08):** click / right click / scroll / type / named
  keys on a selected window's frame while this user holds the lease (C2
  input API, bounds-validated server-side, `frameAt` attached); the desktop
  preview alone is watch-only with a "pick a window" hint. The needs-you
  reason is a banner with Take over / Skip this step
  (`needs-you/respond {action: skip}`).
- **Chat cards (design 03/08):** the real `needs_you` state renders an
  inline card (reason + Take over / Skip, operator+ only) and, only while
  this user drives, the "You took over at …" line with Hand back.
- **Bot settings › Computer** (`/:botId/settings#computer`): status
  (+ activity / last error / Vela version), the four true facts, and
  Wake/Sleep/Stop (operator+; read-only for viewers). Section + nav chip
  hidden while the probe is unavailable.
- **Files sheet "Open on computer" (view 10):** an "On its computer"
  /workspace section (real `workspace_list` driven listing, folder
  navigation) with per-file Open on computer (operator+, awake-only). New
  backend routes: `GET .../computer/workspace` (viewer+; **browsing never
  boots the computer** — `run_tool_step(..., allow_wake=False)`) and
  `POST .../computer/editor/open` (operator+; path validated to
  workspace-relative, runs the `editor_open` driven step, plain 409s).
- **The right-hand inspector** (Juan's sidebar): bot avatar + name; Activity
  (live computer activity line + recent runs from the executions API) and
  Library (knowledge documents; the tab appears only when there are any);
  Suggested only from real prompts (needs-you, open quick tasks) and hidden
  when empty; the Computer card; Voice/Language from the app's real
  voice-mode settings (read-only; hidden when absent).
- **First-wake build progress** while state is `building` (real step/total
  when known + the last build line; `lastError` on failure).

### Behavior changes

- `MainLayout` fetches the Docker probe at mount; every computer surface
  gates on `status.available` (a failed probe reads as unavailable), so
  there are no dead Computer buttons when Docker is off.
- The chat header gains the Computer toggle (next to Files), visible only
  while the probe is available; it drives the inspector (the design's
  `aria-pressed` state).
- `useComputerPreview(botId, viewId?)` follows one window's frame when a
  viewId is passed (~1 fps ETag poll); the desktop behavior is unchanged.
- The Files sheet gains the workspace section, visible only while the bot's
  computer is awake; the room mode is unchanged.
- `/:botId/computer` is a new bot route; it hides the inspector (it is the
  surface).

### C4 — not backed (hidden, no fake data)

- **"Use a cloud computer instead"** (view 09) — no cloud backend exists;
  the CTA does not appear anywhere (asserted in
  `tests/test_computer_ui_source.py`).
- **View 09's generated explainer sentence** ("I need my own computer to
  open the booking site…") — that text is written per situation by the bot;
  the UI shows the facts + Turn on instead (the real per-chat copy is the
  bot's own message).
- **The view-06/07 chat-page cards** ("Running on its computer ·
  localhost:5173", the diff card with +6 −3) — no chat-content source
  carries those; run meta stays in chat/tool output. The full-window
  surface covers the browser/terminal presentations with real frames.
- **The floating chat box in view 05** — the design's mini composer inside
  the computer window has no send path of its own; the chat keeps working
  in the chat view (existing WS), and the computer view is a surface, not a
  second chat.
- **Per-bot voice settings** — voice/Language rows show the app's real
  voice-mode preference (what the voice pipeline uses); there is no
  per-bot voice setting to edit, so the rows are read-only.
- **Terminal/editor run meta and richer window frames** — arrive with the
  VP4/VP5 Vela pin bump (the UI already lists those windows and opens their
  frames); approving sites beyond the starter origin is C5.
- **Mobile full-desktop touch take-over** — desktop/web only in this pass
  (per the task rules).

### Tests

- `tests/test_computer_workspace_api.py` — the two new backend routes
  (access levels, path-escape 422, asleep-409-with-no-container, step
  payload normalization, refusal passthrough), fake Vela + fake Docker.
- `tests/test_computer_ui_source.py` — hermetic source assertions over the
  frontend (availability gates everywhere, conditional inspector Computer
  card, no cloud CTA, conditional Open-on-computer, the true facts, the
  no-AI-tools rule on the new files).
- Backend `ruff`/`ruff format`/`mypy`/`pytest` pass; the frontend lint/build
  run in CI (no local `node_modules`).

## Later phases

- **Phase D** — D2 Routine editor (17), D3 Bot settings (18),
  D5 App settings + Activity log (19, 20).
- **Phase E** — side tasks (11a–c): backend E1–E3 and UI E4 are in this branch
  (see "Phase E4" above).
- **The bot's computer** (views 04–09, 11): backend C1–C3 merged (Docker probe,
  ComputerService, frame/input proxy, the `computer` plugin); UI shipped in C4 —
  see "Phase C4" below and
  [`VIRTUAL_COMPUTER_PLAN.md`](./VIRTUAL_COMPUTER_PLAN.md).

## Phase D2 — Routines + Routine editor (views 12/17)

Per the updated bundle (`source/12-where-things-moved.html`): **Automations
became Routines** (plain-words editor); scripts and functions are advanced
steps; the Timeline moved into Runs (separate PR at `/runs`).

### Routines list — `RoutinesView` at `/:botId/routines`

Replaces the old `AutomationsView` (deleted). `/:botId/automations` redirects
to `/routines`; `/:botId/automations/:id/edit` (script editor) still works.
Narrow 680px column in the v2 language (`styles/v2/routines.less`):

| Element | Source |
|---|---|
| "Routines" H1 + "Things \<Bot\> does on its own" | bot store (real bot name) |
| New routine button | `/:botId/routines/new` (hidden below Editor — the API requires EDITOR) |
| Routines \| Advanced tabs | `stores/ui` `automationSection` (`'routines' \| 'advanced'`, persisted values from the old union fall through to Routines) |
| "See runs" link | `/runs?bot=<id>` — lands with the Runs PR; in this branch the fallback route catches it |
| Routine row: name | `schedule.name` |
| Routine row: plain-words summary | `describeSchedule()` in `frontend/src/lib/schedules.ts` — parses the real trigger ("Every Monday at 7:30 AM", "Every 30 minutes", "One time · …", `Cron: …`, …) |
| Routine row: Active toggle | `POST /schedules/{id}/toggle` (immediate; hidden below Operator) |
| Routine row: "Last run …" | `schedule.lastRunAt`, relative; hidden when never run |
| Advanced tab | Scripts and Functions as `AutomationCard`s (edit/run/toggle, unchanged behavior) |

The old Timeline tab is dropped here (it lives in Runs now). The old "New
Script" button was removed: it navigated to `/:botId/automations/new`, which
never rendered an editor (no script-create UI exists — pre-existing dead
button, not a lost feature). Search filters the active tab.

### Routine editor — `RoutineEditorView` at `/:botId/routines/new` + `/:botId/routines/:routineId`

The design's single narrow column (max-width 680px, page padding 32px 24px
64px, 24px column gap, exact values from `source/17-routine-editor.html` —
same artwork as the old view 13), styled with phase A tokens. Legacy
`/:botId/schedules[/:scheduleId]` URLs redirect here.

| Element | Source |
|---|---|
| Back / "Routine" / Close | navigate to `/:botId/routines` |
| Active toggle | `POST /schedules/{id}/toggle` (immediate, edit mode only) |
| Delete | `DELETE /schedules/{id}` with `confirm()` (edit mode only) |
| Test run | `POST /api/bots/{bot_id}/schedules/{schedule_id}/run` — fires once without shifting `next_run_at`/`enabled` (edit mode only) |
| Name | `schedule.name` |
| "What should \<Bot\> do?" | `schedule.functionParams.message` (initial value falls back to `description`, which is what the scheduler delivers when no message is set) |
| "When to run · your time zone (\<tz\>)" | shows the **schedule's own timezone** when editing (cron h/m are interpreted in it; PATCH doesn't send `timezone` so it is preserved); new routines default to the browser zone (`Intl.DateTimeFormat().resolvedOptions().timeZone`) and save it |
| Trigger card | `scheduleType` + `cronExpression` / `intervalSeconds` / `runAt` / `eventTrigger`. Kinds: Every day / Weekdays / Weekly (+ day chip) / Hourly (+ minute) / Custom cron / Every N minutes-hours / One time / Event |
| "+ Add trigger" | **hidden** — the schedules table stores exactly one trigger per routine (view 17 shows it because that concept supports many). It appears only as the restore affordance after the trigger card's remove X is clicked; new routines start with a daily 9:00 card and Save requires a trigger |
| Helper text | lists only supported triggers and states "One trigger per routine" |
| Advanced (collapsible) | Description, linked Function, Max concurrent runs, Catch up missed runs, read-only meta (next run / last run / run count / schedule time zone) |
| Save | `POST` (create, lands on the new routine's editor) or `PATCH` (update) |

### Backend changes (split into their own PR — hunks kept unchanged here)

- `POST /schedules/{id}/run` + `SchedulerService.run_schedule_now()` — test run
  (delivery + `record_run`, cadence untouched).
- `compute_next_run()` helper (`scheduler_service.py`) — schedules created or
  edited via the API never got `next_run_at` set (only the LLM plugin did), so
  they would never fire. `create_schedule` and `update_schedule` (whenever a
  trigger field changes) now compute it; invalid cron → 422.
- `UpdateScheduleRequest.scheduleType` — trigger kind can now be changed via PATCH.

### Behavior changes

- `/automations` (incl. the sidebar's Automations icon, left exactly as-is) and
  `WorkspaceView`'s Routines quick link now land on `/routines`; the Workspace
  quick link was updated to point there directly.
- Schedule cards became plain-words routine rows that open the editor (the old
  card click was a no-op); the Timeline tab and the never-working New Script
  button are gone from this page.

### Role gating (view 12: Routines are Operator+)

Gated with the existing `useBotAccess` hook; items are **hidden**, never greyed:

| Role | List (`RoutinesView`) | Editor (`RoutineEditorView`) |
|---|---|---|
| Viewer | rows readable; no New routine button, no Active toggle; empty-state copy points at editors | header + short read-only notice ("view-only access…"); the form is not rendered |
| Operator | toggle shown (toggle/run are Operator+ on the API) | read-only form (all fields disabled) + Active toggle + Test run; Save/Delete hidden; one-line notice that editing needs editor access |
| Editor/Owner/Admin | everything | everything |

The Advanced tab's script/function cards hide Run/Toggle for viewers the same way
(`onRun`/`onToggle` become `undefined`). Levels match the backend: schedules
toggle/run = OPERATOR, create/update/delete = EDITOR; scripts run/activate/disable
= OPERATOR, create/patch/delete = EDITOR.

**No "New script" entry point exists**: `ScriptEditorView` only edits existing
scripts (`getScript`), no UI calls `createScript`, and the old button navigated to
a URL that never rendered an editor — so scripts remain edit-only from the
Advanced tab, as documented above.

### Phase D2 — not backed yet

- **`/runs` route**: "See runs" links to `/runs?bot=<id>`, which ships in the
  Runs PR; until then the app fallback catches it.
- **Multiple triggers per routine**: one `schedule_type` per schedule, so the
  editor models one trigger (see "+ Add trigger" above).
- **Keyword / webhook / new-chat / "when another task finishes" triggers**:
  no backend trigger types for these (only cron/interval/once/event).
- **Event triggers don't fire automatically**: `schedule_type = 'event'` rows are
  creatable and editable but nothing in the backend publishes those events to
  the scheduler.
- **Conditions / fixed steps / retries** (design's Advanced label): those exist
  on Functions/Scripts, not on Schedules. `functionId` can't be cleared once set
  (PATCH ignores `null`, pre-existing API behavior).
- **Script/function creation UI**: scripts and functions can only be created via
  the API or LLM tools; the editor UIs are edit-only.
- Schedule delivery goes through the scheduler's existing message path
  (`functionParams.message` → platform chat / WS broadcast); it is not an
  agent turn with tool access.

## Phase E4 scope (side tasks UI, views 11a–c)

Backend E1–E3 is in this branch: `GET/POST /api/bots/{id}/side-tasks` (list/get,
start on `.../chats/{chatId}/side-tasks`, stop, retry-merge, discard),
`GET /api/bots/{id}/side-task-groups/{groupId}`, `side_task_update` WS events
carrying the full record, and `chats.parent_chat_id` on chat responses.
The UI is built on those contracts only — no fake states anywhere.

New pieces:

- **`frontend/src/stores/side-tasks.ts`** — zustand store (not persisted; the
  server is the source of truth and survives restarts). `ensureForBot` feeds it
  from the list endpoint; every `side_task_update` WS event upserts the full
  record; on WebSocket reconnect, bots whose list was already loaded are
  re-fetched so changes broadcast while offline are picked up. Helpers for
  per-parent selection and for collapsing helpers into groups live here too.
- **`frontend/src/components/side-tasks/SideTaskCard.tsx`** — the parent-chat
  card for every real state (`waiting_for_slot` → "Waiting for a slot",
  `running` → "Working · 0:32" from the real `startedAt`, `needs_you` → amber
  border + the recorded reason, `merge_conflict` lists the real
  `conflictFiles` with Retry merge / Discard, `merged` → files changed + short
  merge commit, `done` → "no changes", `failed` → the recorded error, `stopped`)
  plus the helpers group card ("N helpers · started by \<Bot\> · X of N done",
  one status row per helper). Cards open the side task's chat.
- **`frontend/src/components/side-tasks/SideTaskChatView.tsx`** — design 11b:
  "Bot / Task title" header with Stop (operator+, only while running/waiting),
  the sub-line ("Side task of \<parent title\> · its files on branch
  `side/…` · reports back when done", all from the record), the backend chat
  history rendered with the normal `MessageBubbleV2`, and the state card with
  its actions. While the side task runs, the history polls every 4s so its
  chat streams in.
- **`frontend/src/components/side-tasks/StartSideTaskDialog.tsx`** — the start
  dialog; posts to the real endpoint and surfaces the backend's clear error
  (e.g. the workspace is not a git repo) as an inline message + toast.
- **`styles/v2/side-tasks.less`** — card/group/tree/dialog styling, exact
  values from the 11a–c sources (amber `#fbbf24` needs-you border, `#131417`
  cards, 34px sidebar tree rows with the elbow connector).

### Data source per element (all real; nothing placeholder)

| Element | Source | Notes |
|---|---|---|
| Parent-chat reply bubbles | persisted messages with `metadata.kind` `side_task_reply` / `side_task_group_reply` (+ `message_update` WS for live updates; merged from the server on chat open) | Quoted snippet from `replyToId` (hidden when the source isn't loaded). Amber accent + Retry merge / Discard on needs-you (operator+). |
| Live indicator under a message | side-tasks store (list endpoint + `side_task_update`) | Ungrouped side tasks of that message still `waiting_for_slot` / `running`; several collapse into one line + popover. Grouped helpers use their persisted group reply instead. |
| Helpers group reply | one persisted message per `groupId` | Counts + per-helper rows from the metadata; updates in place via `message_update`. |
| Side-task chat history | `GET /api/bots/{id}/chats/{chatId}/messages` | Loaded on open, refreshed when the record's `updatedAt` changes and polled every 4s while running. |
| Sub-line parent title | `GET /api/bots/{id}/chats/{parentChatId}` | Falls back to plain "the main chat" when the fetch fails. |
| Stop / Retry merge / Discard | `POST .../side-tasks/{id}/stop|retry-merge|discard` | Hidden below operator (the APIs require operator+); errors toast. |
| Side-task chat composer (E6) | `POST .../side-tasks/{id}/messages` | Operator+ only; mirrors the server rules — disabled with the reason while the task works or waits on a merge conflict. The reply continues the turn in the side task's worktree. |
| "View changes" (E6) | `GET .../side-tasks/{id}/diff` | In the side-task chat header and on settled thread replies; diff dialog with file list + hunks. Hidden when the record points at no work. |
| Sidebar tree | side-tasks store via `chats` (bot row = latest chat) | One nested level under the bot's latest-chat row; helpers collapse to one "X of N" row. Clicking opens the side task's chat. |
| Workspace › Needs you | side-tasks store | One item per `needs_you` record ("Side task \"…\" needs you — merge conflict"), opening the side task's chat. |
| Start points | `POST .../chats/{chatId}/side-tasks` | Message hover **More › Do this on the side** prefills the dialog from that message; composer **+ › Side task** prefills from the composer text. Both operator+ only. |

### Behavior changes

- The composer "+" is now a menu: **Attach file** (the old direct behavior) and
  **Side task** (operator+). Bot-started helpers need no UI entry point — the
  bot starts them with its tools.
- Message hover rows gained a **More** menu carrying "Do this on the side".
- The sidebar and Workspace each fetch the side-task list per bot once
  (deduped), then live off `side_task_update`.
- Leaving a chat no longer cancels anything new: side tasks run on the server
  and appear in the parent chat via cards regardless of which view is open.

### Phase E4 - not backed yet (hidden from the design, no fake data)

- **Question card with option buttons** (design 11b) — no `ask_user` WS payload
  or structured question/options exists; `needs_you` carries only a free-text
  reason, which the card shows instead.
- **Computer column on side tasks** (11a right pane: labeled windows, "N things
  running", preview counts) — no computer backend; the pane is not rendered.
- **Interleaving into message history** — done in E5: replies are persisted
  messages (quoted, next to the source via `reply_to_id`); live waiting /
  running states show as the small indicator under the source message.
- **Side-task cards** — replaced by the thread-reply model in E5; the
  state card remains only inside the side task's own chat (design 11b).
- **Parent-chat "brought in" one-liner** — replaced by the E5 thread reply
  (see "Side-task replies" below): one persisted reply per side task, for
  user-started and bot-started alike.
- **Starting from a purely local chat** — the start API requires the parent
  chat to exist on the server; a browser-local chat that never synced fails
  with the backend's clear "Chat … not found" error, shown as a toast.

## Side-task replies (phase E5)

Juan's call on the E4 card stack: "humans reply to threads" — the parent chat
now renders side tasks the way WhatsApp/Slack/iMessage do, not as a stack of
big cards.

Backend (migration 015 + `SideTaskService`):

- Every side task records `source_message_id` — the parent-chat message it
  answers. "More › Do this on the side" passes the message id explicitly
  (`sourceMessageId` on the start request, validated to belong to the parent
  chat, 400 otherwise); "+ › Side task" and the bot tools have no message
  reference, so the backend falls back to the latest user message in the
  parent chat — the message the current turn is answering (documented
  fallback; a parent chat with no user message gets `null` and the reply
  renders without a quote).
- While a side task waits or runs, nothing is persisted; the chat shows a
  quiet one-line indicator derived from `side_task_update` (below).
- When it settles (`merged` / `done` / `failed` / `stopped` / `needs_you`),
  the backend persists ONE assistant reply message in the parent chat:
  `reply_to_id` = source message, content = the side chat's last assistant
  message trimmed (or a record-derived line), metadata
  `{kind: "side_task_reply", sideTaskId, title, chatId, status, replyTo,
  mergedFiles?, mergedCommit?, error?, needsYouReason?, conflictFiles?}`.
  Every later state change (needs_you → merged after Retry merge, discard,
  resume) updates that same message **in place** — never a second reply, and
  a resolved side task leaves no stale amber actions behind.
- Bot-started helpers share ONE `side_task_group_reply` message
  (`{kind, groupId, title, status, total, done, failed, running, waiting,
  needsYou, items[{id,title,status,chatId}], replyTo?}`), created when the
  group starts and updated in place as helpers progress; per-helper detail
  only appears on expand in the UI.
- The old E3 system-note is gone — the reply replaces it for user-started
  and bot-started side tasks alike (no duplicates).
- Each create/update is pushed to clients over a new **`message_update` WS
  event** (`{chatId, message}`), broadcast with the same bot-access scoping
  as `side_task_update`. The record's `replyMessageId` makes the write
  idempotent across restarts.

Frontend (`frontend/src/components/side-tasks/SideTaskReply.tsx` +
`ChatView` + `stores/bots` `upsertMessage`):

- Messages whose metadata kind is a side-task reply render as a compact
  quoted-reply bubble: quoted snippet of the source message on top (click
  scrolls to the original; hidden when the source isn't loaded), the
  summary, files/commit or error/reason in small text, and a **View thread**
  link opening the child chat. Needs-you replies get the amber accent and
  Retry merge / Discard inline (operator+ only, matching the API).
- The helpers group reply updates in place off `message_update`; a chevron
  expands the per-helper rows (each opens that helper's chat).
- While side tasks only wait or run, a small indicator sits under the source
  message ("Update the changelog · Working · 0:32"); several from the same
  message collapse into one line ("3 side tasks · 2 working, 1 waiting")
  that opens a tiny popover listing them. Grouped helpers are covered by
  their persisted group reply instead.
- The big card stack is removed from the parent chat. The sidebar tree goes
  quiet: only active + needs-you + failed rows (amber is the only accent),
  finished ones collapse into a muted "N finished" row. Workspace › Needs
  you is unchanged.
- Reload safety: on chat open the client merges any server-side reply
  messages it missed (only `side_task_reply*` kinds, matched by id) into the
  local history, so replies survive reloads even when the browser was
  offline when they were written.

Test hermeticity (this phase): side-task tests leaked real worktrees and
`side/*` branches into `/home/box/work/CachiBot` and `~/.cachibot/worktrees`
when a test ended while its background turn was still in flight. Fixes:
`SideTaskService.shutdown()` cancels and awaits in-flight turns (used by the
app on shutdown and by every side-task test fixture in teardown, before the
monkeypatches are undone), and an autouse `hermetic_side_task_git` conftest
fixture roots worktrees in the system temp dir and makes every side-task git
helper refuse to run against a repository outside it. The migration test
runs alembic against a tmp SQLite only (`CACHIBOT_DATABASE_URL` env; the
alembic env prefers it over the developer's real config).

## Side-task follow-ups (phase E6)

The opened side task became a real conversation, its changes became
inspectable, and its turns show up in Runs (see SIDE_TASKS_PLAN.md "E6" for
the full backend notes).

Backend:

- `POST /api/bots/{id}/side-tasks/{sideTaskId}/messages` (operator+) replies
  inside the side task's own chat: the message is persisted there and the
  task continues its turn in its own worktree — reusing the worktree,
  recreating it from the surviving branch, or starting a fresh branch from
  the parent's current HEAD when the previous work was already brought back
  (then only new changes merge). The 4-per-parent limit applies (queue when
  full); running/waiting tasks and merge conflicts get a 409 with a clear
  reason. When the continued turn settles, the SAME parent-chat thread reply
  is updated in place.
- `GET /api/bots/{id}/side-tasks/{sideTaskId}/diff` (viewers allowed,
  read-only): unified diff + per-file stats — worktree vs base (incl.
  uncommitted and untracked) while unmerged, the merged commit range after;
  512 KB cap with a `truncated` flag; binary files listed without stats.
- Every side-task turn writes one execution-log row (trigger `side_task`,
  parent chat as `chatId`, side-task/side-chat ids in the metadata) with
  output lines for the key steps, so the existing executions APIs return
  them.
- Fix from the last review: the `_running` done-callback only pops the
  handle when it is still the same task object (a resume/reply landing
  before the cancelled turn exited could evict the fresh handle and lose
  the running turn).

Frontend (`SideTaskChatView` + `SideTaskDiffDialog` + `SideTaskReply` +
`RunsView`):

- The side-task chat has a real composer (design 11b): operator+ only,
  disabled with the reason while the task works or waits on a merge
  conflict; viewers see no composer. Sending persists the reply and the
  chat streams the continued turn (the existing running-poll picks it up).
- "View changes" opens the diff dialog (file list with +/− stats and
  A/M/D badges, per-file hunks with add/del coloring, truncated/binary
  notes, mobile layout with a horizontal file strip). The action lives in
  the side-task chat header and on settled thread replies, and is hidden
  whenever the record points at no work.
- RunsView groups side-task rows under a "Side tasks of \<parent title\>"
  section per parent chat (title fetched once per chat), helpers under a
  "\<group title\> · N helpers" cluster, each with an "Open side chat" link
  into the side chat. Trigger column labels them "side task".

### Behavior changes

- Resumed/continued side tasks answer the newest user message of their chat
  (the reply) instead of a generic "continue" prompt; the prompt is still
  persisted exactly once.
- A merge after a continuation reports only the changes that were not in the
  parent yet; the diff of a merged task shows exactly what the latest
  bring-in added.
- A turn cancelled at any point (even before its first database read)
  settles the record; a finish with unmerged commits on the branch merges
  them back instead of reporting "done" with the work left behind.

## L1: v2 loading primitives

Shared loading pieces, built before the boot-screen restyle. Two proof call
sites only — no mass migration.

### Built

- `Spinner` (`components/common/Spinner.tsx`, `styles/components/spinner.less`)
  — one CSS-ring drawing (no second icon API), sizes `sm`/`md`/`lg` = 12/14/18px,
  ring always `currentColor`. Default color is `--v2-text-tertiary` inside
  `.ui-v2`, `--color-text-secondary` on legacy surfaces; both defaults use
  `:where()` so a utility class still wins via `className` (UpdateDialog's
  `text-accent-500` keeps working). `label` keeps the visually-hidden
  "Loading..." text; pass `label=""` + `aria-hidden` when decorative.
- `Skeleton` (`components/common/Skeleton.tsx`, `styles/v2/loading.less`) —
  variants `line` / `row` / `card` / `list` (list composes rows). Pulses
  between `--v2-bg-hover` and `--v2-bg-inset`; radii from tokens (row 12,
  card 14); no hard-coded colors.
- `PageLoading` (`components/common/PageLoading.tsx`) — centered `Spinner`
  (md) plus optional skeleton children, inside the current panel only. Never
  a full-viewport takeover (`.users-loading` is the anti-pattern). Pass
  `pending` and it appears only after `delayMs` of pending time.
- `StatusLine` (`components/common/StatusLine.tsx`) — React wrapper over
  `.v2-status-line` (`styles/v2/chat.less`): 13px `--v2-text-tertiary` line,
  optional `icon` (defaults to `Spinner sm` while `pending`), optional
  `markColor` dot for L3's bot-colored status mark; children are the status
  text.
- `Button pending` (`components/common/Button.tsx`, `buttons.less`) —
  `pending?: boolean` disables the button, sets `aria-busy="true"`, and
  overlays a `Spinner sm` while the label keeps its layout space, so the
  width never jumps.
- `useDelayedFlag(pending, delayMs = 200)` (`hooks/useDelayedFlag.ts`) —
  false until `pending` has been true for `delayMs`, false again immediately
  when pending drops.
- Reduced motion (`styles/v2/motion.less`, imported after all animated
  components from `styles/index.less`) — `@media (prefers-reduced-motion:
  reduce)` kills the spinner, skeleton pulse, `spin-slow`, `pulse`,
  `typing-bounce`, `runs__spin`, and the app-loader animations. Everything
  holds still; no spin, no pulse.

### Rules

- Spinners on fast operations go through `useDelayedFlag` (default 200ms) or
  a `pending` prop that applies it; skeletons may still show immediately.
- v2 surfaces use `--v2-*` tokens only — no new color literals.

### Proof call sites

- `RoutinesView` loading state: `PageLoading` (replaces the Loader2 in
  `.routines__loading`, whose less block is gone).
- `AppSettingsView` update "Check again" actions (Electron + Pip rows):
  `Spinner sm` with `useDelayedFlag` + `disabled` / `aria-busy`.
- `RunsView` loading spinners: new `Spinner`; the `runs__spinner` class typo
  (the class never existed in `runs.less`) is gone.

### Deferred

- L2 done below: boot screens (`AppLoader`, desktop splash, `index.html`)
  restyled; they still inherit the motion kill-switch.
- L3 done below: chat `TypingIndicator` / `ThinkingIndicator` /
  `ToolCallDisplay` migrated onto `StatusLine`/`Spinner` (see "L3: chat
  status lines").
- Legacy pages: Users, Plugins and the Marketplace migrated in L7 (see "L7:
  remaining spinner migration"); auth keeps its own patterns while sign-in
  work is on hold. Mobile loading is the L5 section below.

## L2: v2 boot screens

The three boot surfaces now share the v2 palette (dark bg `#0b0c0e`, panel
`#131417`, green `#4ade80`; light bg `#f4f4f5`, green `#16a34a`; Inter with
system-ui fallback) and dropped the old `#00E676` / Segoe UI lockup, CRT
scanlines and neon glow.

- `desktop/splash.html` — compact branded card for the 420×340 frameless,
  transparent Electron window ("the desktop app is starting the server and
  may be installing an update"): an opaque v2 card at a 16px radius with the
  wordmark, a quiet two-ring mark on a well disc, and version + progress
  pinned at the bottom. Light/dark via `prefers-color-scheme`, overridable
  with a `?theme=dark|light` query param. The `window.updateStatus` /
  `showDeterminateProgress` / `showIndeterminateProgress` / `updateProgress`
  API used by `main.js` is unchanged, so auto-update determinate progress
  still works. The file carries its own `prefers-reduced-motion` rule that
  turns the animation into a static mark and a still bar.
- `AppLoader` (`components/common/AppLoader.tsx` +
  `styles/components/app-loader.less`) — full-viewport in-app boot after
  React mounts ("the UI is checking the server, session, and config"), a
  deliberately different composition from the splash: mark, wordmark, status
  and progress stacked and centered on the full canvas — no card chrome, no
  version/progress bottom bar. Same palette, themed by the app's `.dark`
  class; the init sequence and status strings are unchanged;
  `styles/v2/motion.less` still kills the animations under reduced motion
  (same class names).
- Warm start: when the first health check succeeds immediately, the loader
  swaps to the app as soon as init finishes — the old forced
  `setTimeout(…, 400)` hold and its mandatory fade are gone. When the server
  had to be waited on, a short fade-out still eases the swap.
- `frontend/index.html` — inline first-paint styles plus a quiet
  AppLoader-like stand-in inside `#root` (dark `#0b0c0e` / light `#f4f4f5`,
  wordmark + ring), so there is no blank flash before React mounts; React
  replaces the stand-in with AppLoader on mount and both use the same hex
  values, so there is no color jump. The Google Fonts stylesheet no longer
  blocks first paint (`media="print"` swap + noscript fallback).

The Electron splash and the in-app AppLoader intentionally stay two
different screens — the splash is a compact card about the desktop app
starting the server / installing an update, AppLoader is the full-canvas
boot checking server, session and config. Update (L8): on Electron the
AppLoader is now suppressed and the splash hands off straight to the app;
AppLoader remains the web boot screen.

## L3: chat status lines

Chat working indicators are now the design's quiet grey status line
(design 03 "Work line") plus a small bot-colored mark — the L1 `StatusLine`
(`pending` spinner + `markColor` dot) — instead of the purple thinking
icon, blue tool spinners and pulsing dots. Desktop and web only; mobile/
untouched, legacy pages untouched.

### What changed

- **Typing / streaming wait** (`ChatView`): the old `TypingIndicator`
  (pulsing bot-colored icon + animated dots, with an invented `#22c55e`
  fallback color) is gone. While a run is loading with no thinking content
  and no tool calls, the chat shows `<StatusLine pending
  markColor={bot.color}>` with the same real text as before
  ("\<Bot\> is working" / "Generating response").
- **Thinking** (`components/chat/ThinkingIndicator.tsx`, shared by
  `ChatView` and rooms): rewritten over `StatusLine` — "\<Bot\> is thinking"
  with the mark in the bot's real color; the streaming thought text renders
  below in `.v2-thinking__content` (13px tertiary italic, still gated by the
  show-thinking preference). ChatView's parallel local copy was deleted.
- **Tool calls in flight** (`ToolCallDisplay` in `ChatView`): the running
  header is now the v2 `Spinner` (sm) + "Running \<tool\> · 0:42" — the
  elapsed time is measured from the call's real `startTime` (stamped by the
  chat store on the WS `tool_start` event) and ticks once per second while
  the call runs. Finished/error states use `Check`/`XCircle` in
  `--v2-green`/`--v2-red` via new `.chat-tool-call__status` classes; the
  expand toggle, args/result body, media auto-expand and model chip are
  unchanged. `aria-expanded` added.
- **Tool calls in history** (`MessageToolCallItem`): same treatment for the
  completed states (`--v2-green`/`--v2-red` status classes replace the
  `text-green-400`/`text-red-400` literals); expand and details unchanged.
- **Streaming wait inside a bubble** (`MessageBubble` + `MessageBubbleV2`):
  the three bouncing dots (`chat-typing-dots`) are replaced by a `StatusLine`
  (pending spinner + bot-colored mark, sr-only text) — in the v2 bubble it
  replaces the empty bubble entirely.
- **Rooms** (still on the legacy bubble, inside the `.ui-v2` shell):
  per-bot thinking uses the shared `ThinkingIndicator` with the bot's real
  color; the bot-status bar, consensus line, active tool calls
  (`ToolCallList`) and the cards-view working badge now use the v2 `Spinner`
  instead of `Loader2`. The workspace task checklist (`TaskProgress`) uses
  the `Spinner` for in-progress steps (its `@blue-500` icon rule is gone).
- **Side tasks**: the running icons in the sidebar tree, the
  under-message indicator, the side-task card/group rows and the
  chat/diff loading lines use the v2 `Spinner` / `StatusLine`; the
  `#60a5fa` running-blue modifiers are gone (needs-you amber and failed
  red stay — they are the design's state colors, not working spinners).
- **Approvals / needs-you**: already the inline `ApprovalCard` (design 03,
  Phase C) — a card, not a spinner line, so nothing was added there.

### Rules kept

- Every line's text comes from real state (chat store `isLoading` /
  `thinking` / `toolCalls`, room `botStates`/`thinkingContent`, side-task
  records). The only durations shown are measured from real start
  timestamps (`ToolCall.startTime`, side-task `startedAt`). The typing and
  thinking lines show no elapsed time — the client store keeps no real
  run-start timestamp for them, and none is faked.
- The mark color is always the bot record's `color`; when no bot is known
  the mark is omitted (the old invented `#22c55e` fallback is gone).
- Accessibility: `StatusLine` carries `role="status"` (polite); its text is
  static per state, and the streaming thinking text sits outside the live
  region, so screen readers are not re-announced per token. Spinners inside
  labelled lines are decorative (`label=""` + `aria-hidden`).
- Reduced motion: no new animations were introduced — the `Spinner` ring is
  already covered by `motion.less`, and the status mark stays static.

### Removed (grep-verified unused first)

- Legacy `.chat-typing`, `.chat-typing-dots` (+ `typing-bounce` keyframes),
  `.chat-thinking` blocks and their v2 overrides; `@keyframes thinking`
  (base.less); the dead `.chat-tool-call--running/success/error` border
  variants; the blue `.task-item--in-progress .task-item__icon` rule; the
  matching dead selectors in `motion.less`.
- `.chat-msg-thinking` (persisted thinking panel) keeps its markup and v2
  override; its legacy purple literals were removed so the v2 token colors
  actually win in dark mode (the `.dark` variants used to tie and win).

## L4: migrate v2 loading call sites

The remaining desktop/web loading states now use the L1 primitives instead of
Lucide `Loader2`/`RefreshCw`/`RotateCcw` spinners and hand-rolled CSS rings.
Scope is desktop and web; legacy pages keep their own patterns until their v2
redesign.

### Primitive evolution

- `Spinner` gained `delayMs?: number` (implemented with `useDelayedFlag`,
  same shape as `PageLoading`'s `pending`/`delayMs`): when set, the ring
  stays hidden — holding its layout space — until it has been mounted for
  `delayMs`, so spinners on fast actions do not flash. Omitting it keeps the
  immediate L1 behavior, so existing call sites (UpdateDialog, Button
  pending, StatusLine) are unchanged.

### What was migrated

- **Views**: RoutineEditorView (initial load → `PageLoading`, Test run →
  delayed `Spinner`), RoomsView + RoomPanel (initial loads → `PageLoading`,
  in-panel, not full-viewport), ToolsView, ScriptEditorView (load →
  `PageLoading`; Save/Run → delayed `Spinner`), SettingsView (skills refresh,
  skill install), GlobalLogView (table load + running rows; the
  `runs__spin` class and its keyframes are gone from `runs.less` and
  `motion.less`), RunsView (`StatusIcon` running row → `Spinner`), and
  AppSettingsView (password/group/member submit Buttons → `pending`; Pair,
  firewall Allow, provider Save rows, QR placeholder, model discovery,
  provider/group loads, data clear → `Spinner`; no `text-accent-500` rings).
- **Settings panels**: DeveloperPanel (loads → `PageLoading`; create/test →
  delayed `Spinner`), BotEnvironmentPanel, BotConnectionsPanel,
  BotSettingsView (skills refresh keeps `RefreshCw` idle, `Spinner` while
  pending).
- **Knowledge**: DocumentUploader's green CSS ring (`border-green-500
  border-t-transparent`) → `Spinner`; DocumentChunksDialog, KnowledgeSearch
  (no more `text-cachi-500`), InstructionsEditor (→ `PageLoading`);
  DocumentList and NotesManager initial loads → `Skeleton variant="list"`;
  KnowledgeStats' one-off `SkeletonCard` → shared `Skeleton variant="card"`;
  re-index/refresh/retry icon buttons keep their idle icon and swap to a
  delayed `Spinner` while pending.
- **Automations**: ScheduleTimeline, TimelineTab (loads → `PageLoading`).
- **Dialogs**: SettingsDialog (platform tools, skills), CreateBotWizard steps
  (NamePicker, Details, Classification, Preview, ProjectDetails,
  ProjectProposal, PromptReview, Setup — generation screens and inline
  placeholders → delayed `Spinner`, no `text-cachi-400` rings),
  OnboardingWizard steps (Database, Smtp, Provider — test/save buttons).
- **Model pickers**: ModelSelect and ModelPill "Discovering models..." rows
  show a `Spinner sm` next to the unchanged copy; `.model-select__loading`
  is now a centered flex row.
- **Skeletons on list layouts (immediate, no delay)**: the Workspace bot
  list renders `Skeleton variant="list"` while bot workspace data loads (the
  `workspace__bots--loading` opacity hook is gone from the TSX and
  `workspace.less`); the Runs day list renders a skeleton list instead of a
  centered spinner; Knowledge documents/notes/stats as above. Skeleton
  shapes are generic — no placeholder counts that look like real data, and
  each is paired with an sr-only status.

### Deliberately left

- Legacy pages keep `Loader2` until their own v2 redesign: UsersView,
  PluginsView, `components/marketplace/*`, `components/auth/*` (Login,
  Setup, Consent, AuthCallback, Upgrade, ProtectedRoute). The
  `motion.less` reduced-motion kill-switch still covers their
  `animate-spin`/`animate-pulse` utilities.
- mobile/ (done in L5 below), virtual-computer views, chat
  Typing/Thinking/ToolCallDisplay (done in L3), AppLoader / desktop splash /
  `index.html` (done in L2).
- Static `RefreshCw`/`RotateCcw` icons that are not loaders (regenerate,
  reset, replace, refresh-preview actions) are unchanged; icon buttons with
  a pending state keep the idle icon and swap to `Spinner` only while
  pending.

## L5: mobile loading

Mobile (mobile/, Flutter + Riverpod + go_router) adopts the L1 primitives
and the L2 quiet boot, replacing the 20+ stock Material progress indicators
and fixing the login-screen flash on cold start (the router redirected to
`/login` before `restoreSession` finished).

### Built

- `mobile/lib/widgets/common/loading.dart` — the shared widgets:
  - `CachiSpinner` — one thin ring (stroke ~2, sizes sm 12 / md 14 / lg 18,
    0.75s linear) defaulting to the AppColors tertiary text tone for the
    current brightness (optional color override). `delayMs` keeps the ring
    hidden-but-space-holding until the delay passes (Timer cancelled in
    dispose); `MediaQuery.disableAnimationsOf` renders a static arc instead
    of spinning; Semantics label "Loading".
  - `CachiPageLoading` — centered `CachiSpinner` (lg) with a 200ms default
    delay and an optional muted status label.
  - `CachiSkeleton` / `CachiSkeletonList` — rounded gray blocks pulsing
    between the AppColors hover/inset tones (static under
    disableAnimations); generic shapes only — no fake counts or labels.
  - `CachiProgressBar` — thin, rounded, real-value bar with the green
    accent from the existing palette (green shade600 in light / shade400 in
    dark — the v2 boot greens); track keeps the old surface tone.
- Migration — every `CircularProgressIndicator` / `LinearProgressIndicator`
  under mobile/lib now goes through these widgets (raw Material indicators
  remain only inside loading.dart): list screens (home, chat list, recent
  chats, knowledge list, work list, todos) show `CachiSkeletonList` on the
  first load; page-level waits (work detail, knowledge search) use
  `CachiPageLoading`; inline button/tool-chip/banner/computer-preview
  spinners (login, QR pair, biometric lock, note editor save, chat send /
  thinking / tool chips / offline banner, message tool chips, computer
  preview) use `CachiSpinner` — an explicit color only where the background
  is fixed (white on the login button and the amber offline banner,
  `white70` on the dark computer preview); the two real work-progress bars
  (work list, work detail) keep their values via `CachiProgressBar`. Only
  the spinner widget changed on the auth screens — no auth behavior.
- Quiet boot — `BootScreen` (mobile/lib/widgets/common/boot_screen.dart):
  "Cachi" + green "Bot" wordmark, a small ring, and an optional status
  line, on the v2 boot background for the current brightness (exact v2
  colors are named constants in `AppColors`: `v2BootBackgroundLight/Dark`,
  `v2BootGreenLight/Dark`). `AuthState.isRestoring` starts true and is set
  false on every `restoreSession` path (success, error, no saved token —
  any error resolves to logged-out), so the router's hold on a `/boot`
  route while restoring can never deadlock and the user never sees the
  login screen flash.
- Native launch screens — Android `launch_background.xml` (base + v21) now
  uses `@color/boot_background` (`#F4F4F5`), with a `drawable-night`
  variant at `@color/boot_background_dark` (`#0B0C0E`); the iOS
  `LaunchScreen.storyboard` background uses the new `BootBackground` color
  asset (light `#F4F4F5`, dark `#0B0C0E` via the dark appearance). The
  existing launch image is kept; no new binary assets.
- `mobile/test/loading_widgets_test.dart` — widget tests for the spinner
  (renders, delay hides then shows), skeletons, and the boot wordmark.
  `tests/test_v2_loading_l5_mobile.py` guards the pass hermetically (no raw
  Material indicators outside widgets/common/loading.dart, boot route +
  `isRestoring` exist, launch backgrounds no longer plain white).

### Rules kept

- No fake data: skeletons are generic shapes, the boot status line is real
  state ("Restoring session..."), spinners carry real Semantics labels,
  and the work progress bars keep their real values.

## L6: loading hardening

Desktop/web consistency pass over the L1–L4 work: one delay rule applied
everywhere, reduced-motion coverage re-verified, leftovers cleaned up.

### The delay rule

- **Fast, user-triggered actions** (save, refresh, test, install, create,
  "Check again", short button clicks): the spinner appears only after 200ms
  so sub-200ms work does not flash — `Spinner delayMs={200}` or
  `useDelayedFlag(pending, 200)`.
- **Ongoing / in-progress states the user is already watching** (chat "is
  working" / "is thinking", a running tool, a running side-task or log row,
  an in-flight document upload): shown immediately — a delay would hide a
  real ongoing state.
- **List skeletons** (Workspace, Runs, Knowledge): immediate, no delay.
- **`PageLoading`**: when `pending` is passed the wrapper delays (default
  200ms via `useDelayedFlag`); the inner `Spinner` never gets its own
  `delayMs`, so the two delays never stack. Callers that omit `pending`
  render a dedicated loading panel and show immediately.
- **`Button pending`**: the button disables immediately (no double-submit)
  and the overlaid spinner appears only after 200ms. One delay only — the
  inner `Spinner delayMs={200}`, not a delayed pending flag on top.

### Reduced motion

- `styles/v2/motion.less` (imported last, so it wins the cascade) still
  kills every loading animation under `prefers-reduced-motion: reduce`:
  `.spinner` (also the Button pending overlay), `.v2-skeleton`,
  `.v2-status-line__mark`, `.app-loader__ring` / `__core-dot` / `__bar`,
  `.reply-highlight`, and the Tailwind `animate-spin` / `animate-pulse`
  utilities the leave-alone pages still use. No loading animation was found
  running outside the kill-switch, so no selectors were added.
- The pre-app boot screens keep their own inline rules because they paint
  before the app CSS: `desktop/splash.html` stills `.ring1` / `.ring2` /
  `.dot` / `.bottom` / `.progress-bar` and drops the status-text transform;
  `frontend/index.html` stills `.boot-first-paint__mark`.
- No motion library was added — CSS only.

### Changed

- `Button` pending: the overlaid `Spinner sm` now has `delayMs={200}`;
  `disabled={disabled || pending}` and `aria-busy` stay immediate and the
  width-lock is unchanged.
- `DashboardCardsView` active-bot mark: the inline
  `color: var(--accent-500)` is gone — the ring falls back to the token
  default (`--v2-text-tertiary` inside `.ui-v2`). It stays immediate: a bot
  that is thinking/responding is an ongoing state.
- `QrCodeDisplay` (AppSettingsView pairing): the placeholder spinner gets
  `delayMs={200}` — `QRCode.toDataURL` resolves in milliseconds, so the
  immediate ring flashed on every open.
- Removed the dead `@keyframes pulse-slow` from `base.less` (grep-verified
  unreferenced: no LESS class animates it, and Tailwind's unused
  `animate-pulse-slow` utility emits its own `pulse` keyframes).

### Left alone

- `UpdateDialog`'s `<Spinner size="lg" className="text-accent-500" />` —
  pre-L1 call site; the Spinner API keeps it working and its color is
  unchanged.
- Legacy pages (Users, Plugins, Marketplace, auth) keep `Loader2`; their
  `animate-spin` / `animate-pulse` stay covered by the kill-switch.
- Ongoing-state spinners stay immediate (chat `StatusLine`, tool-call rows,
  side-task rows, room status lines, running run/log rows, document upload),
  as do the list skeletons and the panel-load spinners that only mount while
  loading.
- AppSettingsView "Check again" keeps its single `useDelayedFlag` — no
  second delay on that Spinner.
- `DocumentList`'s pulsing processing `Clock` is a state icon, not a spinner
  ring; it stays (kill-switch covers it).
- mobile/ is covered by L5; virtual-computer views, the L2 boot screens'
  visuals and the L3 chat treatment are untouched.

## L8: single boot screen on desktop

On Electron the boot used to show two screens back to back: the splash card
while the server started, then the in-app AppLoader once the main window
appeared. There is now one boot screen — the splash — which hands off
straight to the app; AppLoader remains the web boot screen.

- `desktop/preload.js` exposes `appReady()` (sends the `app:ready` IPC) on
  `electronAPI`; typed in `frontend/src/vite-env.d.ts`.
- `desktop/main.js` keeps the main window `show: false` and no longer shows
  it on `ready-to-show` when a splash exists. The renderer's `app:ready`
  triggers the reveal: show the window, close the splash. Reveal is
  idempotent (guards `isDestroyed` / `isVisible`, clears the fallback timer)
  and a ~12s timer after `ready-to-show` reveals the window anyway, so a
  frontend failure never strands the user on the splash; `did-fail-load`
  and `render-process-gone` reveal early for the same reason. With no
  splash (macOS activate re-create) `ready-to-show` shows the window as
  before. The dev-mode path (`ELECTRON_DEV_URL` / Vite) uses the same IPC.
- `AppLoader` renders nothing while initializing when
  `window.electronAPI?.isDesktop` is set (the splash covers the hidden
  window); once `ready` flips, children mount underneath and the effect
  calls `appReady()` directly — the children are already committed and the
  window show triggers the first paint (a `requestAnimationFrame` would
  never fire in the hidden window) — so the window is only shown with the
  real UI on screen, including the setup / legacy-db / login paths, whose
  `finish()` still runs. Web behavior is unchanged. The `index.html`
  first-paint stand-in is irrelevant on desktop (the window is hidden
  then).
- Tests: `tests/test_v2_desktop_single_boot.py` (hermetic source
  assertions).

## L7: remaining spinner migration

The last one-off `Loader2` / `animate-spin` call sites outside auth moved
onto the L1 primitives. Simple swaps only — the legacy pages keep their
layout; no redesign.

### What was migrated

- **Marketplace**: the install buttons in `BotDetailDialog`,
  `BotDetailPanel` and `RoomDetailPanel` (`DialogButton`, not the shared
  `Button`, so no `pending` prop) swap their inline `Loader2` for a delayed
  `Spinner sm` next to the unchanged "Installing..." text;
  `MarketplaceBrowser`'s two 32px grid loaders are now `Spinner lg` inside
  the existing centered `.marketplace__loading` wrapper (the inline color
  style is gone — the ring uses the token default).
- **UsersView** (legacy page, simple swaps): the full-page `text-blue-500`
  loader is `PageLoading` inside the existing `.users-loading` wrapper; the
  create/update submit spinners are `Spinner sm` (`delayMs={200}`, default
  sr-only label so the pending button keeps an accessible name).
- **PluginsView**: the initial-load `Loader2` is `PageLoading`; the reload
  button keeps `RefreshCw` idle and swaps to a delayed `Spinner sm` while
  reloading — the same pattern as SettingsView/KnowledgeStats.
- **ComputerSection**: the activity line's `computer-activity__spin`
  `Loader2` is a `Spinner sm` (decorative — the activity text is the label;
  ongoing state, so immediate).
- **BotInspectorPanel**: the activity line's `inspector__activity-spin`
  `Loader2` is a `Spinner sm`; `RunRow` renders a `Spinner sm` in the icon
  slot when `status === 'running'` and keeps the other status icons
  (success/cancelled/error).

### Removed (grep-verified unused first)

- `computer.less`: `.computer-activity__spin` (the `--v2-blue` rule),
  `@keyframes computer-activity-spin` and its reduced-motion entry.
- `inspector.less`: `.inspector__activity-spin`, the
  `.inspector__run-icon--running` spin rule, `@keyframes inspector-spin` and
  the reduced-motion block that named the two classes.
- Reduced motion for the migrated sites is unchanged: the shared `Spinner`
  is covered by the `motion.less` kill-switch.

### Deliberately left

- `components/auth/*` (Login, Setup, Consent, AuthCallback, Upgrade,
  ProtectedRoute) keep `Loader2` — the sign-in surfaces are on hold and out
  of scope; their `animate-spin` stays covered by the `motion.less`
  kill-switch.
- `desktop/splash.html`, `frontend/index.html` first paint and `AppLoader`
  are the boot screens (L2), not spinners — untouched.
- `motion.less` keeps the `animate-spin` / `animate-pulse` selectors for the
  auth pages.

## HTML artifacts: click-to-edit (htmlstudio)

HTML artifacts (`website_builder`, `html_preview` and `email_template` all
emit `type: 'html'`, rendered by
`frontend/src/components/artifacts/renderers/HtmlRenderer.tsx`) get an Edit
toggle in the artifact toolbar. In edit mode the user clicks an element in
the preview, edits it in a small inspector (text, link href/label, image
src/alt, color/background, font size, bold, text align), and every change is
applied as a typed patch to the artifact's HTML string. Undo/redo (50 steps)
and a Done button round out the mode.

**Dependency.** [`htmlstudio`](https://www.npmjs.com/package/htmlstudio)
`^0.4.1` (MIT), pinned in `frontend/package.json` / `package-lock.json`.
Only the framework-free core entry is used (`tagHtml`,
`applyPatch`, `injectBridge`, `getParent` from the package root, which
resolves to `dist/index.js` and pulls in nothing but `node-html-parser`).
The `htmlstudio/react` entry and `htmlstudio/styles.css` are deliberately
unused — they ship their own `hs-*` styling and phosphor icons that clash
with the v2 UI; the inspector is a native v2 surface
(`components/artifacts/HtmlEditInspector.tsx`, `styles/v2/html-edit.less`).

**How it works.**

- `frontend/src/lib/htmlEdit.ts` wraps the core. `buildEditableDoc` tags the
  clean HTML and injects the postMessage bridge for the edit iframe's
  srcDoc (a full document stays a full document); `applyHtmlPatch` re-tags
  the clean source, applies one typed patch and untags again with our own
  `untag` — a regex that removes exactly the `data-ve-id="p-…"` attributes
  the tagger stamped and nothing else. htmlstudio's `untagHtml` is
  deliberately not used for the stored source: it re-parses without
  comments and would silently drop every HTML comment, including the
  Outlook `<!--[if mso]>` conditionals email templates rely on. Because
  comments survive the round trip, the tree `tagHtml` sees is identical on
  every pass and the positional `data-ve-id`s stay stable across edits,
  undo and redo with no normalization step — the artifact is never
  rewritten on entering edit mode, only by real edits. The bridge/ids never
  reach `artifact.content`: everything is serialized from the string, never
  from the iframe DOM.
- `frontend/src/hooks/useHtmlEdit.ts` owns the round-trip: it listens for
  bridge `message` events (only from the edit iframe's `contentWindow`,
  `channel: 've'`, target origin `window.location.origin` with a `'*'`
  fallback when the origin is the string `'null'`, e.g. file:// desktop),
  turns `select` events into inspector state (fields re-read from the source
  string), turns `dblclick-text` inline edits into `set-text` patches, keeps
  the undo/redo stacks, and persists every accepted patch twice: first
  through `useArtifactsStore.updateArtifact` (optimistic, so the iframe
  stays responsive), then through a PUT to the server-side artifact store
  (`frontend/src/api/artifacts.ts` → `PUT /api/bots/{botId}/artifacts/{id}`).
  Server saves are serialized through a one-slot queue that always carries
  the newest full source, so rapid edits coalesce; Done awaits the in-flight
  save (`flushSave`) before leaving edit mode, re-sending the source if it
  changed since the last PUT. On success the response's content and bumped
  version are adopted into the store (verified by reading it back — that
  read-back plus the PUT result is the Saving/Saved/Not saved status); on
  failure the status is a real error, never a faked save. Without an active
  bot the edit stays browser-local and the status says so.
- **Server-side artifact store.** Artifacts are durable rows
  (`artifacts` table, migration 017) owned by a bot and optionally tied to a
  chat/message; agent-emitted artifacts (`__artifact__` /
  `__artifact_update__` tool results and proactive plugin emissions) are
  written through on the WebSocket path, and Website Builder's markdown
  results (project id + base64 preview) are promoted into a stored html
  artifact with a stable id per bot+project+slug, so its pages enter the
  same edit flow (the original markdown tool_end is still sent — the
  transcript is unchanged). When a chat opens, the client lists the chat's
  stored artifacts and merges them into the localStorage cache (adds ones
  this browser never saw; a server version >= the local one wins).
- **Version policy.** Manual edits bump `artifact.version` — but only via
  the server: the local write touches `content` only, and the PUT response's
  bumped version is what lands in the store. The server increments its
  stored version on every saved edit (a missing row is upserted, seeded from
  the client's version + 1) and never lets the stored version decrease, so a
  stale client can never rewind it. The Edit toggle hides while a run is in
  flight (`useChatStore.isLoading`) because agents replace artifact content
  wholesale; if content still changes underneath edit mode, local history is
  dropped and the editor re-syncs instead of patching stale source.
- **Website write-back.** Saving an artifact whose `plugin` is
  `website_builder` (or whose metadata says so) and whose metadata carries a
  `project_id` overwrites the latest `pages/{slug}/v{N}/index.html` under
  `~/.cachibot/websites/{project_id}/` (slug defaults to `index`), so the
  plugin's own `iterate_website` / `load_website` read the edited HTML on
  the next turn. The project must already exist on disk (`project.json` plus
  a `v{N}` directory); project ids and slugs are validated as single safe
  path segments and the target must resolve inside the project directory —
  anything else saves the artifact without touching disk
  (`websiteWritten: false`).
- **The agent sees the edits.** The system prompt's knowledge context
  includes a "## Current HTML artifacts" section with each html artifact's
  id, title, version, plugin/project and full current source (newest few,
  each capped ~100k chars), with an explicit instruction to start updates
  (`update_preview`, `update_email_template`, `iterate_website`, …) from
  that source rather than regenerating from memory — manual edits may not
  appear in earlier conversation messages.
- Round-trip fidelity: HTML comments (including conditional comments), the
  doctype, text and script/style bodies are preserved byte-for-byte. What
  the `node-html-parser` re-serialization normalizes on the first edit:
  attribute values on tagger-stamped (editable) elements become
  double-quoted, and void-tag closing slashes are dropped (`<br/>` → `<br>`,
  the parser's default form). Rendering is unaffected and the serialized
  form is a fixed point — later edits change nothing but the patched
  element.

**Not backed yet (deliberately).**

- The first edit may still normalize attribute quoting and void-tag slashes
  (frontend htmlstudio applyPatch re-serialization, see above).
- Website write-back is a no-op when the project is not on disk or the
  artifact metadata has no `project_id`: plain `html_preview` /
  `email_template` artifacts have no website files — they live only in the
  (now server-side) artifact store, which is enough for the agent to see
  them.
- Only `HtmlRenderer` is covered — that includes html artifacts from all
  three generator plugins. The HTML preview tab of `code` artifacts does not
  get the toggle (it requires `artifact.type === 'html'`), and no other
  renderer was touched. No mobile work.

## Known limitations / decisions

- Views 04–09 and 11 shipped in C4 on the C1–C3 backend (see
  "Phase C4" below); the chat-page cards of views 06/07 (a dev-server card
  inside the message stream) have no real chat-content source and are not
  rendered — the full-window computer surface covers those presentations.
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
