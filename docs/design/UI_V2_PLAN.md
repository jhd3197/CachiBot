# CachiBot UI v2 — Implementation Plan

Status: **Phase B (Workspace "Your bots") implemented** on branch `feat/ui-v2-workspace`
(Phase A app shell + Phase B; not committed).
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
| 12→16 | Runs (v2b: view 16; Work/Automations-timeline/Exec-logs moved in per view 12) | `/runs` (`RunsView`) | **Done (Phase D1)**. Cross-bot, day-grouped run list composed from the per-bot executions APIs, plus quick-tasks checklist and Automations timeline; operator+; Activity log link for admins. |
| 13 | Routine editor | `/:botId/automations` (`AutomationsView`, `ScriptEditorView`, schedules API) | **Phase C**: plain-words editor over existing `Schedule`/`BotFunction` APIs. |
| 14 | Bot settings | `/:botId/settings` (`SettingsView`) | **Phase C**: narrow one-column layout (max 600px) reusing existing settings panels; Connections rows already exist in `BotConnectionsPanel`. |

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

## Later phases

- **Phase C — Chat cards, files sheet, routine editor, bot settings layout**
  (views 03, 10, 13, 14) on existing APIs.
- **Phase D1 — Runs page (view 12)** on existing executions APIs. (Done — see below.)
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
