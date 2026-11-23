# The bot's computer (Mini Vela): backend review and phase V plan

Design: `docs/design/cachibot-v2-final-views/` views 04–09 (the computer in the
chat) and 11 (what Mini Vela is). UI plan: `docs/design/UI_V2_PLAN.md` rows
04–09/11, the hidden Bot settings › Computer section, the hand-off/take-over
card (Phase C "not backed yet") and Files sheet "Open on computer".

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

### What is out of scope (for this plan)

- Anything the bot "runs" that has no real source: no fake preview frames, no
  placeholder windows. If the computer backend is absent, every view stays
  hidden, exactly as today (UI_V2_PLAN rows 04–09/11).
- Installing apps / a store / OS settings on the desktop (the design forbids
  it: "the bot can't change its own computer").
- Voice, rooms and side-task UI changes. Side tasks may later *use* the
  computer (11c's window labels), but that is a consumer of this backend.
- Windows/macOS without Docker Desktop, and a cloud computer backend (both
  later options, see §5).

## 2. Approach

### What the backend already has

| Piece | Where | Reusable for the computer? |
|---|---|---|
| **Config / workspace** | `config.workspace_path`: **one global folder for all bots** (`config.py`, confirmed by SIDE_TASKS_PLAN) | **Missing.** Mini Vela says each bot has its own `/workspace` that persists between runs. A per-bot workspace is new. |
| **Path isolation pattern** | Side tasks build a per-run copy of the config with `workspace_path` pointed at the worktree; every tool resolves against it (`services/side_task_worktrees.py`, `_execute_turn`) | **Yes — the template.** Computer file tools point at the bot's volume path the same way; the global config is never mutated. |
| **File tools** | `plugins/file_ops.py` (read/write/list/edit/info), `config.is_path_allowed` | **Yes**, once `workspace_path` is the bot's volume. |
| **Code execution** | `plugins/python_sandbox.py` (tukuy sandbox, AST risk analysis, `ApprovalRequired`), `services/script_sandbox.py` (automation limits) | **Partly.** In-computer execution replaces the need for the in-process sandbox for bot turns that use the computer. |
| **Coding agents** | `plugins/coding_agent.py` spawns coding-agent CLI subprocesses in `workspace_path`, streams lines via `on_tool_output` | **Yes, relocated.** View 07 wants the CLI *in the computer's terminal*: run it in a container PTY instead of a host subprocess. |
| **Chat WebSocket + access scoping** | `api/websocket.py`: token auth, `broadcast_to_bot` (same rule as REST bot access), `approval_needed` request/response | **Yes.** `computer_update` events broadcast with the same scoping; take-over requests can reuse the approval flow's shape. |
| **Job runner** | `services/job_runner.py`: background execution, execution logs, timeline, `job_update` | **Yes.** Computer-tool runs write execution logs (Runs + admin Activity log) exactly like jobs do. |
| **Bot access levels** | `api/auth.py`: `require_bot_access_level`, viewer/operator/editor/owner/admin | **Yes.** Viewing the computer/stream = bot access; controlling it (wake/stop/take-over) = operator+, matching Runs. |
| **Docker** | `docker-compose.yml`, root `Dockerfile` ship already | Host needs a Docker socket only; the image itself is new. |

### Recommended approach

**One Docker container per bot ("Mini Vela"), driven by a `ComputerService`.**

- **Image** (`mini-vela`, built once, e.g. from Debian slim): Xvfb (headless
  X server at 1440×900, the design's desktop size) + a minimal window manager
  (Openbox) + Chromium driven over CDP/Playwright + a PTY terminal server
  (tmux or node-pty) + x11vnc/noVNC/websockify for the live stream. Four apps
  only: Browser, Terminal, Files, Editor — no store, no settings app. Nothing
  bot-specific is baked in.
- **Per bot**: a named volume mounted at `/workspace` (persists across sleep —
  "files in /workspace stay") and a per-bot workspace dir on the host that is
  the volume's backing store, so the existing file tools work against it via
  the side-task per-run-config pattern.
- **Live view**: noVNC/websockify inside the container, proxied through the
  CachiBot server behind the same token auth and bot-access scoping as the
  REST/WS APIs (short-lived stream tickets, not raw container ports). **Cheap
  first step for view 04**: periodic screenshots (CDP `Page.captureScreenshot`
  or X framebuffer grab) served from a preview endpoint — the preview column
  needs only ~1 fps; full noVNC lands with the open view (V2).
- **Agent computer tools** (new plugin, `computer` capability): browser
  actions (navigate/click/type/read via CDP), terminal exec (via the PTY),
  files (existing tools re-pointed at the bot volume). They execute **inside
  the container** (browser/terminal through the container's control socket;
  files via the mounted volume path on the host). Tool runs write execution
  logs and feed the activity line + open-windows list.
- **Driver lock**: the `ComputerService` holds one driver per bot — `bot`,
  `user:<id>`, or `none`. Take over acquires the lock, pauses the agent's
  in-flight computer tools (they wait or error with "user is driving"), and
  routes input to the desktop; Hand back releases it. Needs-you is a state +
  reason set by the agent (e.g. sign-in wall), broadcast like
  `side_task_update`, cleared by take-over or Skip.
- **Sleep**: after 10 min with no agent tool activity and no user driving or
  watching, stop the container, keep the volume. Wake restarts it. A
  server-restart-safe record distinguishes off / asleep.
- **Docker optional**: on boot the server probes the Docker socket; if Docker
  is absent the feature reports `unavailable` and every computer surface
  stays hidden — never faked.

### Alternatives considered

1. **Host-process sandbox (no containers).** Xvfb + Chromium + PTY on the
   host under a restricted user. Cheapest to build, but the isolation story
   is weak: the file tools already run on the host, a bot prompt could steer
   the browser at host-internal addresses, and "the internet, not your
   network" (view 09) is hard to guarantee. The design's own copy commits to
   Docker ("Runs on: This PC · Docker"). **Rejected as the default**; the
   backend is shaped behind a `ComputerBackend` interface so a host backend
   could be added, but it is not planned.
2. **Remote/cloud desktop provider** (view 09's "Use a cloud computer
   instead"): no host Docker requirement, but per-bot cost, an external
   dependency, bot files/secrets leave the machine, and added latency.
   **Rejected for V1**; the provider idea survives as a possible second
   backend behind the same interface, behind an explicit per-bot choice.
3. **Opt-in host control.** The agent drives the user's real browser/terminal
   with approvals. Simplest of all and worst aligned with the design: "a
   private sandbox that only I use" — and approvals already exist for that
   shape without a computer backend. **Rejected.**

**Recommendation: alternative 0 — per-bot Docker containers — matching the
expected direction; the code supports it** (path-isolation pattern, access
scoping, execution logs all reuse cleanly) **with one real gap: the workspace
is global per server today, so a per-bot workspace is genuinely new work.**

## 3. Data model, API, WS events (sketch)

### Migration

Latest published migration is `015_side_task_source_message.py`, so this is
**migration 016**: a `bot_computers` table —

- `bot_id` (PK, FK to bots), `state` (`unavailable | off | building | starting | awake | asleep |
  needs_you`), `driver` (`bot | user:<user_id> | NULL`), `activity` (one
  line, NULL when idle), `open_windows` (JSON: `[{app, title, focused}]`),
  `needs_you_reason` (nullable), `build_progress` (nullable line/percent while the image builds), `last_watched_at`, `volume` (name/host path), `container_id`
  (nullable), `enabled` + `sleep_after_minutes` (bot settings), `asleep_at`,
  `last_active_at`, `updated_at`.
- No history table: history is the existing execution logs (every computer
  tool run and control action logs there).

### REST (all under `/api/bots/{bot_id}/computer…`, token auth)

| Endpoint | Access | Purpose |
|---|---|---|
| `GET /computer` | bot viewer+ | State record (state, driver, activity, windows, needs_you_reason, enabled, `available` when Docker missing) |
| `POST /computer/wake` | operator+ | Off/asleep → awake |
| `POST /computer/sleep` | operator+ | Awake → asleep (container stopped, volume kept) |
| `POST /computer/stop` | operator+ | → off (container removed; /workspace kept unless delete is requested) |
| `POST /computer/take-over` | operator+ | Acquire driver lock; agent computer tools pause |
| `POST /computer/release` | operator+ | Hand back → driver `bot` (or `none` if no run) |
| `POST /computer/needs-you/respond` | operator+ | Answer a needs-you request: `{take_over: true}` or `{skip: true}` (view 08's Skip this step) |
| `GET /computer/preview.png` | bot viewer+ | Latest screenshot (cheap preview path, ~1 fps) |
| `GET /computer/stream-ticket` | bot viewer+ | Short-lived one-time ticket for the WS stream below |
| `WS /computer/stream?ticket=…` | ticket | Proxied noVNC/websockify RFB stream (full window, view 05) |

### WS events

- `computer_update {botId, computer}` — full record on every change, sent
  with the same `broadcast_to_bot` scoping as `side_task_update`. The chat
  preview (04), open view top bar (05), sidebar and Workspace needs-you all
  consume this one event.
- Needs-you surfaces in chat as a card through the existing
  `approval_needed`-style flow (or a dedicated payload); settled by take-over
  / skip / run end.

## 4. Security & resources

- **Isolation**: container is the trust boundary. Non-root user in the image;
  the Docker socket is never mounted into anything the bot touches; no host
  mounts except the bot's own workspace volume (one volume per bot, owned by
  that bot — bots never see each other's files or the global workspace).
- **Network**: outbound-only, and "the internet, not your network" (view 09):
  drop RFC1918/link-local destinations so the bot's browser/terminal cannot
  reach the host's LAN or the CachiBot server itself. No published ports; the
  only entry point is the server's proxied stream.
- **Resources**: `--memory 2g --cpus 1.5 --pids-limit 256`, disk quota on the
  volume, hard kill on stop; sleep-after-10-minutes bounds total runtime.
  Preview frames capped (e.g. 1 fps, ≤ 960px wide) so a room of watchers
  cannot melt the host.
- **Secrets**: never in the image; nothing bot-specific is baked in. Provider
  keys stay on the host in the existing config; computer tools receive only
  what `PluginContext` already carries. The design's sign-in flow exists so
  credentials are typed by the human during take-over — the bot's browser
  must never see a password manager.
- **Authorization**: viewing state/preview/stream requires bot access
  (viewer+); wake/sleep/stop/take-over/release require operator+, matching
  Runs. Admins see everything, per existing rules. The driver lock is
  per-bot; a second take-over while a user drives is rejected with the
  current driver's name.
- **Audit**: wake/sleep/stop/take-over/release/skip and every agent computer
  tool run write execution logs (Runs page + admin Activity log), reusing
  `ExecutionLogRepository` exactly as the job runner does.

## 5. Decisions (Juan, Nov 23, 2026)

| # | Question | Decision | What it changes |
|---|---|---|---|
| 1 | Docker required? | **Docker optional; a cloud computer is a later option.** | Without Docker the server reports `available: false` and every computer surface stays hidden. The `ComputerBackend` interface keeps room for a cloud backend; it is not in V1–V6. |
| 2 | Workspace | **Each bot gets its own workspace.** | A per-bot workspace dir under the data dir backs the bot's `/workspace` volume; computer tools and file tools resolve against it via the per-run config pattern. Bots never see each other's files or the global workspace. |
| 3 | Image delivery | **Build the image locally on first use**, no registry pull and no prebuilt download. | V1 ships the Dockerfile in the package and builds it through the Docker API on first wake. The build is cached (image tag carries a hash of the Dockerfile; rebuilt only when it changes). Build progress streams to the UI (`computer_update` with `state: building` and a progress line/percent), and a failed build is shown with its last log lines and a Retry. |
| 4 | Windows/macOS | **Support Windows and macOS through Docker Desktop in the first version.** | Docker detection covers `DOCKER_HOST`, the Docker context, the Unix socket (`/var/run/docker.sock`, `~/.docker/run/docker.sock` on macOS) and the Windows named pipe (`npipe:////./pipe/docker_engine`). Volumes are Docker named volumes (not host bind mounts), which avoids Windows path translation and macOS file-sharing settings; the host-side workspace view goes through the container where needed. CI runs the detection logic on Linux, Windows and macOS runners with mocks. |
| 5 | Idle sleep | **Watching keeps it awake.** | An open live view (preview or full window, any user) counts as activity, tracked by stream/preview heartbeats; sleep only after 10 minutes with no agent tool activity, no driver and no watcher. |
| 6 | Mobile | **Full desktop on mobile**, including take over. | The stream viewer must work in the mobile app and mobile web: scaled view with pinch-zoom/pan, touch mapped to pointer events (tap = click, long-press = right click, two-finger drag = scroll) and an on-screen keyboard toggle for typing while driving. |
| 7 | Dev tools | **No toolchains in the image; the bot installs what it needs into `/workspace`.** | The image stays lean (desktop stack, Chromium, terminal, basic shell tools). The terminal's environment points installs at the persistent volume (e.g. `PREFIX`/`PATH` under `/workspace/.local`, npm prefix and pip user base there) so what the bot installs survives sleep. |

## 6. Phases (each a PR into dev, tests green without Docker)

Tests follow the side-task pattern: a `ComputerBackend` interface with a fake
in tests (SQLite in a tmp dir, no Docker, no real repo/HOME touches; Docker
integration tests are marked and skip when Docker is absent). Python 3.10 is
supported (e.g. catch `asyncio.TimeoutError`, not the builtin).

- **V1 — Lifecycle + image (≈4–6 days).** Lean `mini-vela` Dockerfile
  (Xvfb, Openbox, Chromium, terminal server, screenshot endpoint) shipped in
  the package; **local build on first use** with cached, hash-tagged image and
  build progress/failure in the state record; Docker availability probe for
  Linux, macOS and Windows (socket, context, named pipe); `ComputerService`
  (wake/sleep/stop, restart-safe states, per-bot named volume and per-bot
  workspace dir); migration 016; `GET /computer` + control endpoints;
  `computer_update` WS. Fake backend + tests; no image is built in CI.
- **V2 — Live preview (≈2–3 days).** Screenshot pipeline → `preview.png`;
  activity line + open-windows feed (from window manager/CDP); stream ticket
  + proxied noVNC for the full window; **viewer heartbeats keep the computer
  awake**; Docker-marked integration test.
- **V3 — Computer tools (≈4–5 days).** `computer` capability plugin: browser
  tools over CDP, terminal exec over the PTY, files via the bot volume;
  coding-agent tool relocated into the computer terminal (view 07); dev
  servers reachable on the computer (view 06); **install prefixes under
  `/workspace` so bot-installed tools persist**; execution-log + audit writes.
- **V4 — Take-over / needs-you (≈2–3 days).** Driver lock, input routing,
  hand back, needs-you state + Skip; chat card; yellow-ring broadcast.
- **V5 — UI (≈4–6 days).** Views 04–09 + 11 (including the build-progress
  state on first wake), Bot settings › Computer section, Files sheet "Open on
  computer", all fed by the real API — hidden when `available` is false;
  **full desktop on mobile with touch take-over** (pinch/pan, tap/long-press,
  scroll, on-screen keyboard).
- **V6 — Hardening (≈3–4 days).** Network policy, resource caps, stream rate
  limits, audit completeness, failure recovery (container dies mid-run),
  **Docker Desktop checks on Windows/macOS** (named pipe, volumes, resource
  limits), docs.

**Total: ≈19–27 working days (~4–5.5 weeks), 6 PRs.** The decisions add about
3–5 days over the first estimate: the local build with progress (V1), Docker
Desktop support (V1, V6) and the full mobile desktop with touch (V5).

## 7. Open questions for Juan (answered — see §5)

1. **Is Docker a hard requirement for the feature?** Proposal: optional —
  without Docker the server reports `unavailable` and all computer UI stays
  hidden (never faked). Confirm the cloud-computer alternative stays a
  later choice, not V1 scope.
2. **The workspace is global per server today; Mini Vela is per bot.** Move
  to a per-bot workspace dir on the host (e.g. under the data dir), or keep
  mounting the shared workspace into every bot's computer? The design says
  "a private sandbox that only I use" — that points to per-bot.
3. **Image size/hosting**: the image (Chromium + desktop stack) is ~1–2 GB.
  Build locally on first use, ship a prebuilt image, or pull from a registry?
4. **Windows/macOS hosts**: Docker Desktop requirement is acceptable for V1,
  or Linux-only until the cloud backend exists?
5. **Idle definition for sleep**: no agent tool activity and no user driving —
  does an open full-window viewer count as "watching" and keep it awake?
6. **Mobile app**: preview-only, or the full desktop too (stream bandwidth)?
7. **Node/toolchains in the image**: view 06 runs `npm run dev` — include
  node/npm/python in the image, or let the bot install what it needs into
  `/workspace`?
