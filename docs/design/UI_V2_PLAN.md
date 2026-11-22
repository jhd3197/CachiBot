# CachiBot UI v2 — Implementation Plan

Status: **Phase A (app shell) in progress** on branch `feat/ui-v2-shell`.
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
| 01 | Workspace: your bots | `/dashboard` (`DashboardView`) | **Phase B**: rebuild as "Needs you / Bots / This week" using existing stores (bots, telemetry `UsageStats`, automations). Quick links row (Routines, Runs, Connections, Knowledge, Settings) link to existing routes. |
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

## Later phases

- **Phase B — Workspace**: view 01 rebuilt on `/dashboard`; quick links; "Needs
  you" from real approval/run state; runs list (view 12) from work jobs.
- **Phase C — Chat cards, files sheet, routine editor, bot settings layout**
  (views 03, 10, 13, 14) on existing APIs.
- **Phase D — The bot's computer** (views 04–09, 11): requires a new backend
  (Mini Vela desktop streaming, take-over, power state). Not started; no
  pretend/disabled controls ship in the meantime.

## Known limitations / decisions

- Views 04–09 and 11 need backend infrastructure that does not exist; Phase A
  ships no computer UI at all (no dead buttons).
- Notifications icon omitted until a notifications feature exists.
- Bot groups and rail drag-reorder from v1 have no surface in the v2 shell;
  the rail ordering is still honored when sorting the bot list, and
  `stores/rail.ts` remains for future use.
- The v2 shell is dark-by-design; light mode gets close-equivalent tokens.
  Legacy panels (dashboard, settings, work, rooms, etc.) keep their existing
  look in Phase A to avoid cross-panel regressions.
- Reference HTML/PNGs keep their original artwork (including third-party
  provider names); shipped code contains no fake data.
