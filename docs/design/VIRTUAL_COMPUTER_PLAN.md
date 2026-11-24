# The bot's computer (Mini Vela): built on Vela

Design: `docs/design/cachibot-v2-final-views/` views 04–09 (the computer in the
chat) and 11 (what Mini Vela is). UI plan: `docs/design/UI_V2_PLAN.md` rows
04–09/11, the hidden Bot settings › Computer section, the hand-off/take-over
card and the Files sheet "Open on computer".

**Direction (Juan, Nov 23, 2026):** the bot's computer is a **Vela** instance,
not a new desktop stack. CachiBot reuses what Vela already has (desktops,
windows, an agent browser with site policy and approvals, watching and take
over, files, containers) and adds only what is missing. Some of the missing
pieces belong in Vela itself, and each of those is planned as its own PR into
Vela's `dev` branch.

Reviewed read-only: `jhd3197/Vela` `dev` at `38796d0` (latest release
v0.1.21), `jhd3197/serverkit-vela` `main` at `5e47800`, plus `vela-contracts`,
`vela-sdk`, `vela-companion` and `vela-templates`.

## 1. Scope: what the views need from a backend

### View by view

| View | Data the backend must provide | Actions the backend must support |
|---|---|---|
| 04 Chat + computer preview | Live 16:10 frame of the desktop; one activity line ("Clicking 'Re-run failed jobs'"); list of open windows (app + title, e.g. Browser → github.com/…/actions); state badge (working / needs you / asleep); whether a computer exists and its on/off state | Open (goes full window — UI only); Stop the current activity (operator+); Wake when asleep |
| 05 Computer open | Full desktop stream; who is driving ("CachiBot is driving" / "You're driving"); same open-windows/activity data | Take over / Hand back (driver switch); Stop; close is UI-only; chat keeps working (existing WS) |
| 06 Bot-built web page | A dev server running on the computer (Terminal: `npm run dev`, Browser: `localhost:5173`); the page reachable from the bot's computer only; "Running on its computer · localhost:5173" card data (URL, process) | Stop the process; open the page full size (stream focus — UI); the port must resolve inside the computer, not the user's machine |
| 07 Computer terminal / coding agent | The coding agent's terminal session visible live; run meta for the chat card ("finished · 1:12", files changed +6 −3) | The coding agent must run *inside* the computer's terminal; the diff data already exists in chat/tool output |
| 08 Take over | Yellow ring + Needs you tag on preview; that window brought to front; "You took over at 10:02 AM" line; top bar "You're driving · CachiBot waits" | Driver lock: user input goes to the desktop, agent paused; Hand back; **Skip this step** (answer a take-over request with "skip"); needs_you reason surfaced to the chat card |
| 09 Computer off / turn on | First-use explainer facts: runs on ("This PC · Docker"), can reach ("the internet, not your network"), keeps ("/workspace between runs"), sleeps ("after 10 min idle") | Turn on (wake); "Use a cloud computer instead" — explicitly an alternative, see §2 |
| 11 Mini Vela spec | States Closed / Open / Needs you / Asleep; app set Browser, Terminal, Files, Editor — no store, no settings (the bot cannot change its own computer) | Sleep after 10 min idle (files in /workspace survive); Wake is explicit ("a stray click never wakes it") |
| Bot settings › Computer (view 18) | Section rows: computer on/off, where it runs, what it can reach, sleep delay; "Change in bot settings" from view 09 | Per-bot enable/disable and sleep-delay setting |
| Files sheet "Open on computer" (view 10) | A file on the bot's /workspace openable in its desktop (Editor) | Open-in-editor request routed to the computer |

Out of scope: fake frames or placeholder windows (without a real computer
every view stays hidden, as today); an app store or OS settings on the bot's
desktop; a cloud computer (later, see §4).

## 2. What Vela already provides

| Need | What Vela has today | Where | Reuse |
|---|---|---|---|
| A desktop with windows | Desktops with views (app windows and site windows), layouts, split panes, a selected view, a rail | `vela/desktops/` (`service.py`, `store.py`, `models.py`), `web/src/desktops/` | **Yes.** The bot's computer is one Vela desktop. The "open windows" list in view 04 is the desktop's views. |
| A browser the agent drives | Agent desktops: a supervised Node worker running Playwright Chromium, one browser context per desktop, typed tools (observe, open site, open app, click, type, key, scroll, wait, attach file, needs person, finish) | `vela/desktops/runtime.py`, `vela/agent_runs/tools.py`, `scripts/browser-worker/` | **Yes.** This is the Browser app of Mini Vela. |
| Safety around the browser | Per-desktop site policy (read only, or ask before sending), held requests shown for approval, "outcome unknown" handling, network policy in the worker, sign-in never automated | `vela/desktops/site_policy.py`, `vela/agent_runs/approvals.py`, `browser-worker/src/network-policy.mjs` | **Yes.** Covers view 08's sign-in wall and "stops to ask you". |
| Watching | Per-window frames served through the authenticated API (`/views/{id}/frame`, ~1 fps watching, ~3 fps controlling); several watchers share one capture | `vela/agent_runs/viewer.py`, `web/src/desktops/RemoteView.jsx` | **Yes**, proxied through CachiBot. Vela deliberately never captures the whole desktop; the full-desktop preview is added only for controller mode (VP6, §6 Q4). |
| Take over / hand back | Control leases: taking over stops the agent's dispatch, bumps the control epoch, then grants a lease; input (click, type, allowed keys, scroll) is checked against the lease, view, epoch and frame age; "Carry on" | `vela/agent_runs/control.py`, `viewer.py`, `POST /api/desktops/{id}/takeover` and `/takeover/{lease}/input` | **Yes.** This is view 08. |
| Needs you | `task_needs_person`, held approvals, queue holds after a failed or unknown run, `GET /api/desktops/attention` | `vela/agent_runs/`, `vela/desktops/api.py` | **Yes**, mapped to CachiBot's needs-you card. |
| Files | Shares with strict path resolution, trash, upload caps and audit; agent files staged per desktop with size limits and expiry | `vela/files.py`, `vela/agent_runs/artifacts.py` | **Partly.** A share pointed at `/workspace` gives the Files app; the bot's own file access still goes through CachiBot's file tools on the same volume. |
| A container | `Dockerfile` (Python server and dashboard), `python -m vela.container` (password + HTTPS proxy mode), `serverkit.yaml` with a `/data` disk | repo root, `vela/container.py` | **Partly.** The image has no Node runtime or browser worker, so agent desktops cannot run in it yet, and container mode requires an HTTPS origin and a password. |
| Named instances on servers | serverkit-vela creates Vela instances (own container, data disk, domain, login) through ServerKit's manifest apply; API under `/api/v1/vela` | `serverkit-vela/backend/` | **Later**, for the cloud computer option. |
| Native Windows/macOS/Linux | Vela Server ships for all three with per-platform runners | `vela/runners/` | Not used for the bot's computer (that runs in Docker), but the Vela code paths are already cross-platform. |

What Vela does **not** have: a terminal or any shell (agent desktops forbid
one by design), an editor, a way for an outside agent to drive a desktop step
by step (runs are driven by Vela's own model loop), a non-HTTPS controller
access mode for a container that only a local process talks to, an image with
the browser runtime in it, touch input in take-over, and a count of who is
watching.

## 3. Architecture

**One Vela container per bot, managed by CachiBot, with CachiBot as the
brain.**

```
CachiBot server ──(Docker CLI: build, run, stop)──▶ vela-computer image
      │                                              one container per bot
      │  loopback port + controller token              ├─ Vela server (desktop, views, policy)
      ├──────────────────────────────────────────────▶ ├─ browser worker (Chromium)
      │  drive tools, frames, take-over, events         ├─ terminal (new, Vela PR)
      │                                                 └─ volumes: /data (Vela), /workspace (bot)
      ▼
CachiBot UI (web, desktop, mobile): views 04–09, 11 — frames and input are proxied
through CachiBot with its own auth and bot-access rules; the Vela port is never
exposed to users.
```

- **Image:** built locally on first use from a pinned Vela release (a new
  `computer` target in Vela's Dockerfile). CachiBot runs the build through the
  Docker CLI and streams progress.
- **Per bot:** a container `cachibot-computer-<bot>` with two named volumes:
  `/data` (Vela's own state: the desktop, policy, kept sign-ins) and
  `/workspace` (the bot's files and anything it installs). The port is
  published on `127.0.0.1` only.
- **Access:** CachiBot generates a controller token per bot, passes it to the
  container as a secret, and calls the Vela API with it. Users never talk to
  Vela directly; CachiBot proxies frames and input and checks bot access first.
- **Brain:** CachiBot's agent calls Vela's tools one step at a time through a
  new driver API (Vela PR VP3). Vela still enforces its site policy, approvals,
  effects and leases on every step, so a CachiBot bot gets the same safety
  Vela's own agent has.
- **Sleep:** CachiBot stops the container (volumes kept) after 10 minutes with
  no tool activity, no one driving and no one watching. A browser session does
  not survive a stop; Vela already reports the run as interrupted, and the
  kept-sign-ins setting covers re-login.
- **Docker absent:** CachiBot reports `available: false` and every computer
  surface stays hidden.

Alternatives considered:

1. **One shared Vela with an agent desktop per bot.** Cheaper (one process),
   but Vela caps agent desktops at two per server, all bots would share one
   data dir and one browser process, and per-bot workspaces would be folders
   inside one container. It doesn't match "each bot gets its own workspace" as
   cleanly. Dropped (§6 Q1).
2. **Delegate whole tasks to Vela's own agent loop** (`POST /tasks` with Vela's
   model). No driver API needed, but the bot would hand its work to a second
   agent with a different model, and CachiBot's chat, tools, budget and Runs
   would see only the outcome. Rejected (§6 Q3).
3. **The from-scratch Docker stack** (Xvfb + noVNC) in the previous version of
   this plan. It duplicates what Vela already does well, and has none of Vela's
   approval and sign-in safety. Dropped.

## 4. Juan's decisions, mapped onto Vela

| # | Decision | How it lands |
|---|---|---|
| 1 | Docker optional; cloud later | CachiBot probes Docker; absent means `available: false`, UI hidden. The cloud option later uses serverkit-vela instances on a ServerKit server with the same controller API (VP7, later). |
| 2 | Each bot gets its own workspace | One container per bot with its own `/workspace` and `/data` volumes. CachiBot's file tools for that bot point at the same volume (per-run config pattern from side tasks). Vela's Files share in that container is `/workspace` only. |
| 3 | Build the image locally on first use | CachiBot builds `vela-computer:<vela-version>-<hash>` from a pinned Vela release on the first wake, caches it, and rebuilds only when the pin changes. Progress and failure (with log tail and Retry) show in the computer state. Nothing is pulled from a registry. |
| 4 | Windows/macOS via Docker Desktop | CachiBot uses the Docker CLI, so Docker Desktop contexts, the macOS socket and the Windows named pipe work without CachiBot code per platform. A probe explains what's missing. Named volumes avoid Windows path and macOS file-sharing issues. The image is Linux (amd64 and arm64 for Apple Silicon). |
| 5 | Watching keeps it awake | Frames go through CachiBot's proxy, so CachiBot counts watchers itself. Vela PR VP6 also reports watchers in `GET /viewer` so the count is right even for a direct viewer. |
| 6 | Mobile: full desktop | CachiBot's mobile viewer shows the selected window full screen with a window switcher, pinch-zoom and pan, and take-over with touch: tap = click, long-press = right click, drag = scroll, keyboard toggle = type. VP6 adds right click and touch-scroll to Vela's input. |
| 7 | Bot installs tools into /workspace | The image stays lean (no node/npm/python toolchains for the bot). The terminal (VP4) starts with `HOME`, `PREFIX`, `PATH`, the npm prefix and the pip user base under `/workspace/.local`, so what the bot installs survives sleep. |

## 5. Gap list

### Vela already provides (reuse as is)

- Desktops, views, layouts and the window list.
- The agent browser (Playwright Chromium worker) and its typed tools.
- Site policy, request approvals, sign-in walls, outcome-unknown handling and
  the network policy.
- Per-window frames, shared captures, control leases, take-over input and
  Carry on.
- Agent files (staging, downloads, limits, expiry) and the Files shares.
- Run records, attention and queue holds.
- The Dockerfile base and the `/data` layout; serverkit-vela for later remote
  instances.

### Vela patches (each its own PR into Vela `dev`)

| PR | What | Why CachiBot needs it | Estimate |
|---|---|---|---|
| **VP1 Controller access mode** | `python -m vela.computer` entry: listens on the container port with a single controller bearer token (from a mounted secret file), no password, no HTTPS origin requirement, owner-equivalent API access, refuses everything else. Docs and tests. | Container mode today needs an HTTPS public origin and a password; a local controller needs neither, and the port is only on host loopback. | 1–2 days |
| **VP2 `computer` image target** | Dockerfile target adding the pinned Node runtime, the browser worker and Playwright Chromium, a non-root user, `/workspace` volume, healthcheck; amd64 + arm64; build args for the Vela version. | Agent desktops can't run in the current image (no Node or browser). Built locally by CachiBot, so it must build reliably with only Docker. | 1–2 days |
| **VP3 Driver API** | Let a controller drive an agent desktop step by step: open a driven run (no Vela model), `POST …/runs/{id}/steps` with one tool call, get the observation back, and `finish` or `needs_person`. Every step goes through the same validation, policy, approvals, effects and leases as Vela's own loop. Events stream for activity. | CachiBot's agent is the brain; Vela only runs its own model loop today. | 3–4 days |
| **VP4 Terminal** | A terminal view kind backed by a PTY, available **only** in computer mode (inside the container, which is the sandbox); frames for watching, input under the same lease rules, agent tools `terminal_run` / `terminal_read` with output caps and timeouts; environment rooted at `/workspace`. | Views 06 and 07 (dev server, coding agent in the terminal). Vela forbids a shell in agent desktops on the host, which stays true outside computer mode (§6 Q2). | 4–5 days |
| **VP5 Workspace files + editor** | In computer mode, a built-in `/workspace` share and a plain-text editor view (open, edit, save, through the same path rules); "open file in editor" API. | Mini Vela's Files and Editor apps, and "Open on computer" from the Files sheet. | 2–3 days |
| **VP6 Viewer additions + full-desktop capture** | Watcher reporting in `GET /viewer` (viewer heartbeats), right click and drag-scroll in take-over input, a lightweight "activity" field per desktop, and an opt-in full-desktop frame (`GET /api/desktops/{id}/frame`) enabled only in controller mode and only for the controller token. | Decisions 5 and 6; the activity line and full-desktop preview in view 04 (§6 Q4). | 2–3 days |
| Later | serverkit-vela: create instances from the `computer` target with the controller mode and an API-key write scope for a CachiBot controller. | The cloud computer option. Not in this plan's estimate. | later |

Vela total for VP1–VP6: about **13–19 working days**, 6 PRs.

### CachiBot adds

- **Docker probe and image build:** detect Docker (CLI, context, Desktop),
  build the pinned Vela `computer` image on first use with progress and
  caching.
- **`ComputerService`:** one container and two volumes per bot; wake, sleep,
  stop; restart-safe states (`unavailable | off | building | starting | awake
  | asleep | needs_you`); idle sleep counting tool activity, drivers and
  watchers; migration 016 (`bot_computers`).
- **Vela client:** a controller-token HTTP client for the driver API, frames,
  take-over, events and the terminal.
- **API and WS:** `GET /api/bots/{id}/computer`, wake, sleep, stop, take-over,
  release, needs-you respond, a frame proxy and an input proxy, all under bot
  access rules (viewer to watch, operator+ to control); `computer_update` WS
  events.
- **`computer` plugin for the bot:** browser, terminal and file tools mapped
  onto VP3/VP4/VP5. The coding-agent tool runs in the computer's terminal when
  the computer is on. Every step writes execution logs (Runs, Activity log).
- **Per-bot workspace:** CachiBot's file tools for a bot with a computer point
  at the bot's `/workspace` volume.
- **UI:** views 04–09 and 11, Bot settings › Computer, the first-wake build
  progress, "Open on computer", the mobile full desktop with touch take-over.
  All hidden while `available` is false.

## 6. Decisions on the Vela approach (Juan, Nov 23, 2026)

| # | Question | Decision | What it changes |
|---|---|---|---|
| 1 | Containers | **One Vela container per bot.** | As in §3. The shared-Vela fallback is dropped. |
| 2 | Terminal in Vela | **Yes, add a terminal only in CachiBot's container mode.** | VP4 is gated on the controller mode from VP1. Vela's "no shell" rule for agent desktops is unchanged everywhere else, and its docs say so. |
| 3 | Who drives | **CachiBot's agent drives each step.** | VP3's driver API is the only path CachiBot uses; Vela's own model loop is not involved for CachiBot bots. |
| 4 | Chat preview | **Patch Vela to allow a full-desktop preview.** | New in VP6: an opt-in full-desktop capture, available **only** in the token-only controller mode (VP1) and only to the controller token. Vela's default (never capture the whole desktop) stays everywhere else. In computer mode the owner's approval prompts are answered in CachiBot, not on the Vela desktop, so the capture does not show an approval control to the bot's side. |
| 5 | Vela release | **Release Vela after VP1–VP3 land.** | CachiBot C1 pins that release; VP4–VP6 ship in the following Vela release, which C3/C4 then pin. The version and tag are reported before tagging. |

## 7. Phases and estimates

Vela PRs go into Vela `dev`; CachiBot PRs go into CachiBot `dev`. CachiBot
tests use a fake Vela client and a fake Docker runner (no image builds and no
containers in tests or CI). Docker integration tests are marked and skip
without Docker.

| Phase | Repo | What | Depends on | Estimate |
|---|---|---|---|---|
| VP1 | Vela | Controller access mode | — | 1–2 days |
| VP2 | Vela | `computer` image target | VP1 | 1–2 days |
| **C1** | CachiBot | Docker probe, local image build with progress, `ComputerService`, per-bot volumes and workspace, migration 016, `GET /computer` + wake/sleep/stop, `computer_update` | VP1, VP2 | 3–4 days |
| VP3 | Vela | Driver API | VP1 | 3–4 days |
| VP6 | Vela | Viewer additions (watchers, right click, drag-scroll, activity) and the controller-only full-desktop capture | VP1 | 2–3 days |
| **C2** | CachiBot | Frame and input proxy, watchers keep it awake, needs-you mapping, take-over and hand back | VP3, VP6 | 2–3 days |
| VP4 | Vela | Terminal (computer mode only) | VP1 | 4–5 days |
| VP5 | Vela | Workspace share + editor | VP1 | 2–3 days |
| **C3** | CachiBot | `computer` plugin (browser, terminal, files), coding agent in the terminal, dev servers, execution logs | VP3, VP4, VP5 | 3–4 days |
| **C4** | CachiBot | UI: views 04–09 and 11, Bot settings › Computer, build progress, Open on computer, mobile full desktop with touch | C2, C3 | 4–6 days |
| **C5** | CachiBot | Hardening: Docker Desktop on Windows/macOS, resource caps (`--memory`, `--cpus`, `--pids-limit`), container egress rules, recovery when a container dies, docs | C4 | 2–3 days |

**Total: about 28–39 working days (roughly 5.5–8 weeks): 6 Vela PRs and 5
CachiBot PRs.** Vela is released after VP1–VP3 (§6 Q5). Vela work and CachiBot work overlap after VP1/VP2, so the
calendar time is shorter than the sum.

Compared with the from-scratch plan (19–27 days), this is larger because it
adds things that plan didn't have: Vela's approval, sign-in and site-policy
safety now covers the bot's browser, and the terminal, editor and driver API
become part of Vela that its own users get too. Reuse saves the browser
control, viewer and take-over work. Deferring the terminal (VP4 and the
terminal part of C3) would cut about a week, but views 06 and 07 would stay
hidden.

### Status

- **C1 (this repo, branch `feat/virtual-computer-c1`): implemented.** Docker
  probe (CLI discovery + daemon check, cached), pinned local image build
  (`cachibot-vela-computer:0.3.0`, single-flight, plain progress), the
  `ComputerService` (per-bot container `cachibot-computer-<id>` with named
  `/data` + `/workspace` volumes, 127.0.0.1-only port, per-bot controller
  token file mounted read-only, wake/sleep/stop, 10-minute idle sleep via
  `touch`, restart-safe startup reconcile), migration 016 (`bot_computers`),
  `GET /api/bots/{id}/computer` + wake/sleep/stop, `GET /api/computer/status`
  and `computer_update` WS events. Tests use a fake Docker runner and a fake
  Vela client (no Docker/network/containers; the one integration test skips
  without Docker). Left for C2+: frame/input proxy and watchers-keep-awake
  wiring onto the `touch` hook, driver client, computer plugin, UI views.
- **C2 (this repo, branch `feat/virtual-computer-c2`): implemented.** The
  live surface, backend plus frontend plumbing (no computer views yet — those
  are C4/C5):
  - **Vela client** (`services/computer/vela_client.py`): the controller-token
    async client for desktops (list/create — the bot's desktop is picked, or
    created once on a fresh container), viewer read, per-window frames, the
    full-desktop frame with ETag/If-None-Match passthrough, viewer
    heartbeats, take-over/input/release, the events stream (polled with a
    numbered cursor, bounded 200-event pages) and the needs-you answers
    (approval resolve, task control). Timeouts on every call; the token only
    travels in the `Authorization` header and is never logged.
  - **Feature detection and degradation:** everything is gated on
    `GET /api/controller` (protocol + `features`), cached at wake. The
    minimum controller protocol is 5 (`MIN_VELA_PROTOCOL`): wake refuses an
    older container with a plain reason, and a container left over from an
    older pinned image is replaced on wake (`docker rm` of the container
    only — the `/data` and `/workspace` volumes always survive) and
    recreated from the new image. Optional features stay feature-detected:
    the desktop frame is advertised only when its opt-in is on, so with it
    off the preview falls back to the focused/top window's frame (its
    content digest is the ETag). Nothing is faked: what Vela does not offer
    is reported as absent (404/409 with a plain reason).
  - **Container env:** `docker run` now passes
    `VELA_CONTROLLER_DESKTOP_FRAME=1` (the documented opt-in for the
    controller-only full-desktop frame; a plain flag, not a secret — the
    token rules are unchanged: mounted file only, never in argv/env). The
    image pin is 0.3.0 (`VELA_VERSION` in `build.py`), the Vela release
    that carries VP4–VP6 (controller protocol 5).
  - **API** (all under bot access rules — viewer to watch, operator+ to
    control): `GET .../computer/preview` (image bytes, ETag/304,
    `Cache-Control: no-store`, 409 with a plain reason when not awake — a
    preview never wakes), `GET .../computer/views` (windows app+title +
    activity line) and `GET .../computer/views/{viewId}/frame`,
    `POST .../computer/watch` (viewer+ heartbeat, ~30 s TTL),
    `POST .../computer/takeover` / `handback` / `input` (operator+; input
    only while the caller holds the take-over, bounds-validated and passed
    through as click/right click/scroll/type/key), and
    `POST .../computer/needs-you/respond` `{action: takeover|skip}`.
  - **Watching keeps it awake:** every watch heartbeat and every
    preview/frame fetch calls `touch(bot_id, "watching")` and counts a live
    watcher (30 s TTL); heartbeats are forwarded to Vela (throttled 10 s per
    viewer, protocol ≥ 5 only) so its watcher count is right. The idle loop
    now also sweeps `needs_you` computers — an unwatched, undriven needs-you
    is idle like any other, and the paused run survives the sleep.
  - **Take-over:** the driver (user id/name, since) is mirrored from Vela's
    control lease with the same 180 s TTL, refreshed by input, so a take-over
    by a user who disconnects or loses access expires cleanly (swept in the
    events tick; Vela's own `control.expired` event does the same).
    `ComputerService.driver_for(bot_id)` is the check C3's bot driving makes
    before every step — while a person drives, the bot waits. Hand back
    releases the lease (and, as in Vela, never resumes the run by itself).
  - **Needs-you mapping:** a per-bot events poller maps `task.attention` →
    `needs_you` with the detail as the reason, `approval.waiting` →
    `needs_you` with the approval headline; cleared on `approval.resolved`,
    run resume/end, take-over and hand back. Respond maps `takeover` to the
    lease flow; `skip` is the documented closest refusal — **Vela has no
    "skip this step"**, so an approval is denied
    (`POST .../approvals/{id} {"decision": "deny"}`) and a needs-person pause
    stops the run (`POST .../tasks/{id}/control {"action": "stop"}`).
  - **WS `computer_update`** now carries `activity`, `windowsCount`,
    `watchers`, `driver`, `needsYou` (reason) and `previewRevision` (clients
    refetch the preview only when it changes; revisions broadcast
    unthrottled, other live fields throttled at 1 s as in C1).
  - **Frontend plumbing (no views):** `api/computer.ts` functions for every
    new route (raw-bytes frame fetches with ETag/304), store fields for
    activity/windows/driver/needs-you/preview revision, and
    `hooks/useComputerPreview.ts` — refetches the preview by revision and
    sends watch heartbeats while mounted, stopping when hidden/unmounted.
  - **Tests:** fake Vela client + fake Docker runner throughout (no network,
    no containers): feature detection and fallback, ETag/304, not-awake
    refusals, no-wake-on-preview, access levels, input-without-take-over,
    bounds validation, watcher TTL vs idle sleep (injected clock), take-over /
    hand back / TTL expiry, needs-you from fake events + respond, WS payloads,
    and the run argv now carrying `VELA_CONTROLLER_DESKTOP_FRAME=1` with
    still no token anywhere.
  - **Vela 0.3.0 (VP4–VP6) is released and pinned:** the desktop-frame
    preview, watcher heartbeats/activity (protocol 5) and the
    terminal/editor surface are available (the window fallback remains for
    when the desktop-frame opt-in is off). Take-over on a fresh desktop
    still needs C3's agent setup (policy + enable-agent) before Vela will
    issue a lease; C2 surfaces Vela's plain refusal until then.
