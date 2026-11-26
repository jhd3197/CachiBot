# Side tasks (principle 9): backend review and phase E plan

Design: `docs/design/cachibot-v2-final-views/` views 11a (side tasks in the chat), 11b (a side task opened) and 11c (how they work).

## What a side task needs, from the design

| Need | From the design |
|---|---|
| A child chat of a parent chat, same bot, its own messages and a short name | 11a/11b header "CachiBot / Update the changelog" |
| Its own copy of the files: a git worktree on a `side/<name>` branch (git is required — a non-git workspace can't start a side task); nothing reaches the parent until it's merged back | 11b sub-line, 11c Files |
| Reports back: one card in the parent chat with the states running / needs you / done (Bring in, View changes, Discard) / brought in | 11c States |
| Helpers: bot-started side tasks shown as one group card ("3 helpers · 1 of 3 done", "Waiting for a slot") | 11a, 11c |
| Four ways to start: More › Do this on the side, + › Side task, saying it, or the bot deciding | 11c |
| Limits: one level in the sidebar (a side task's own helpers are steps inside it), at most 4 running at once (others queue), stopping the parent stops its side tasks | 11c Limits |
| Shows in the sidebar under the bot, in Runs under its parent, and in Workspace › Needs you | 11c Where it shows |

## What the backend already has

| Piece | Where | Reusable for side tasks? |
|---|---|---|
| **Work / Task / Job model** with `parent_work_id`, `WorkRepository.get_children()`, task `depends_on`, statuses (pending, ready, blocked, running, done, failed, cancelled), `chat_id` on Work/Task/Job | `cachibot/models/work.py`, `storage/work_repository.py` | **Yes, as the backbone.** A side task can be a Work row with `parent_work_id` (the parent run) and its own `chat_id`. The status machine and progress already exist. |
| **Job runner**: background loop, runs tasks through the agent, max 5 concurrent jobs, `cancel_job` / `cancel_work`, broadcasts `job_update` over WebSocket, writes execution logs and the timeline | `services/job_runner.py` | **Partly.** It's the right execution engine for "runs in the background and reports back". It needs: a per-parent limit of 4, cascading cancel (parent → children), and streaming chat output into the side task's own chat instead of only a job result. |
| **Execution logs / Runs page** (D1): per-bot executions, running/stuck/failed, cancel | `api/routes/executions.py`, `RunsView` | **Yes.** Side tasks show up in Runs if their jobs write execution logs with a parent reference (add `parent_execution_id` or reuse `work_id`). |
| **Chat WebSocket**: one in-flight agent run per socket (`current_task`, new message cancels the previous), approvals over the socket | `api/websocket.py` | **Not enough by itself.** Side tasks must run independently of the socket (the job runner, not `current_task`), and their approvals and questions need to reach the user even when that chat isn't open (Workspace › Needs you already listens for `approval_needed`). |
| **Prompture sub-agents**: `DeepAgent(subagents=[SubAgentSpec…])` with a built-in `task` tool, and `ParallelGroup` / `SequentialGroup` for fan-out | prompture 1.19 `agents/deep/subagents.py`, `groups/` | **Yes, for "the bot decides" and helpers.** The bot can call a `start_side_task` / `start_helpers` tool. A side task's own helpers can stay in-process Prompture sub-agents shown as steps, which is exactly the "one level only" rule. |
| **Work-management plugin**: `work_create`, `todo_create`, … tools the bot already uses | `plugins/work_management.py` | **Yes.** Add `side_task_start` next to them. |
| **Workspace progress plugin**: `plan_tasks` / `update_task` emit a checklist into the chat | `plugins/workspace_progress.py` | **Yes**, for showing helpers' steps inside a side task. |
| **Coding-agent dispatcher**: runs Claude Code / Codex / Gemini CLIs as subprocesses in the workspace and streams output | `services/coding_agent_dispatcher.py` | Useful later. It runs in the single shared workspace today. |
| **Workspace / files** | `config.workspace_path`: **one global folder** for all bots and chats | **Missing.** There is no per-task copy, no git worktree support and no "bring in" (merge) step. This is the biggest new piece. |
| **Rooms orchestrator** (multi-bot turn-taking) | `services/room_orchestrator.py` | Not relevant: side tasks are the same bot, not several bots. |
| **Chats** | `chats` table | **Missing a parent link.** No `parent_chat_id`, no side-task title or status on the chat. |

## Decisions (decided)

1. **File isolation: git worktrees only.** A side task gets `git worktree add -b side/<slug>`; there is no plain-copy fallback. Git is required: if the workspace isn't a git repo, starting a side task fails with a clear error.
2. **Bring-back: automatic merge.** When a side task finishes, its changes merge back automatically (no review gate). If the merge conflicts, nothing is lost: the branch/worktree stays, the side task becomes `needs_you` with reason "merge conflict", and the merge result (files changed, merge commit sha) is always recorded on the record so the card can show it.
3. **Concurrency: 4 running per parent chat.** At most 4 side tasks run at once per main task (parent chat); the rest queue in `waiting_for_slot` and are promoted FIFO when a slot frees.
4. **Restart: resume.** Side tasks survive a server restart: running ones are re-queued and resumed from their persisted chat history when the server comes back, queued ones stay queued, and the per-parent limit still applies.

## Phase E plan

### E1, backend model and runner (about 2 days)
- Migration: `chats.parent_chat_id` and a `side_tasks` table (id, bot_id, parent_chat_id, chat_id, title, prompt, kind, group_id, status, needs_you_reason, started_by, worktree/branch/base_commit placeholders for E2, merged_commit/merged_files for E2, error, timestamps, work_id link to a Work row).
- `SideTaskService`: start (from a message, a composer prompt or a bot tool), at most 4 running per parent chat with a waiting queue (new `waiting_for_slot` state, promoted FIFO), stop (cascades from the parent's cancel), states running / needs_you / done (E2 adds merged / needs_you-on-conflict), and restart resume.
- Git is required from E1 on: `start` fails with a clear error when the workspace isn't a git repo (the worktree itself arrives in E2).
- Run each side task through the agent in the background, independent of any WebSocket: output persists into the side task's own chat (same persistence the WebSocket turn uses); approvals reuse the existing `approval_needed` broadcast path; every state change broadcasts a `side_task_update` WebSocket event with the full record.
- Parent stop → all its side tasks stop (extend the WS `cancel` handler).
- On startup, side tasks in `running` are re-queued and resumed from persisted chat history; `waiting_for_slot` ones stay queued; the limit of 4 per parent still applies.
- Tests that run without PostgreSQL (SQLite in a tmp dir, agent run mocked, real git in tmp dirs), like the schedule fix.

### E2, files: worktree and automatic bring-back (about 2–3 days) — BUILT
- A side task gets `git worktree add -b side/<slug>-<short id>` (from `.cachibot/side/<id>`) when it starts — no folder-copy fallback; git is enforced in E1. Fill `worktree_path`, `branch`, `base_commit` on the record.
- Point the tools (`file_ops`, `python_execute`, coding agents) at the side task's worktree through `PluginContext`/config. Today they read the global `config.workspace_path`, so this touches several plugins.
- On finish, merge the `side/<slug>` branch back automatically: record `merged_files` and the `merged_commit` sha, and mark the side task `merged`. On merge conflict, do not lose work: keep the branch/worktree, mark the side task `needs_you` with reason "merge conflict", and surface it.
- "View changes": diff against the base commit. "Discard": remove the worktree and delete the side branch.
- This is the riskiest part: path isolation must be enforced or a side task could write into the parent's files.

What was built (E2):
- **Worktrees** (`services/side_task_worktrees.py`): on the record's first move to `running`, the service creates `git worktree add -b side/<slug>-<short id>` from the workspace HEAD and records `worktree_path` (under `~/.cachibot/worktrees/<side task id>`, outside the user's repo), `branch` and `base_commit`. Worktrees survive restarts: on resume the existing worktree is reused; it is recreated from the recorded branch only when the dir is missing (and the branch still exists). Not a git repo / branch gone -> clear error, the side task lands on `failed` with the reason.
- **Path isolation**: `_execute_turn` builds a per-run copy of the global config with `workspace_path` pointed at the worktree (the global config is never mutated). Every tool resolves paths against `config.workspace_path` and the sandbox only allows paths inside it, so nothing a side task does can write to the parent workspace.
- **Automatic merge back** (in `_run`, after a successful turn): all changes are committed in the worktree ("Side task: <title>"; repo identity, `-c` fallback to CachiBot/cachibot@localhost only when none is set). No changes -> `done`, `merged_files []`, worktree removed, branch deleted. Otherwise `git merge --no-ff` into the parent branch, serialized per repo with a lock: success -> `merged` with `merged_commit` and `merged_files` (paths vs `base_commit` as added/modified/deleted), worktree removed, branch deleted with `-d`. Conflict, or git refusing because the parent tree has local changes in the same files -> `git merge --abort` (parent tree ends exactly as before), branch/worktree kept, `needs_you` with reason `merge_conflict` and the new `conflict_files` JSON field (migration 013; 012 was already published in dev builds so it is unchanged). Service-created commits and merges run with `--no-verify` so user git hooks can never run or hang; identity comes from the repo config, with a `-c` fallback to the local service identity only when none is set. Never: force-deleted branches, parent tree reset/clean, worktrees with uncommitted or unmerged changes removed. A finish interrupted mid-merge is recovered on the next run (branch already merged -> recorded as `merged`, not `done`).
- **API** (`api/routes/side_tasks.py`): `POST .../retry-merge` (operator+; commits pending worktree changes and merges again; stays `needs_you` with updated `conflict_files` on another conflict) and `POST .../discard` (operator+; only stopped/failed/needs_you; removes the worktree and force-deletes the branch — the only `-D` — and marks it `stopped`). GET returns the new fields (`branch`, `mergedCommit`, `mergedFiles`, `conflictFiles`).
- **Tests** (`tests/test_side_tasks.py`, real git in tmp dirs, SQLite, no PostgreSQL): worktree created on the right branch outside the repo; file-tool writes land in the worktree (parent writes refused); clean merge records the merge commit and file statuses and cleans up; no-change case; content conflict and dirty-parent refusal both leave the parent untouched and keep branch/worktree with `conflict_files`; retry-merge after resolving (and conflict-again); discard; resume/restart reuse the worktree, recreate it only when missing. The test fixture now points the service at a real git repo in a tmp dir so none of this touches the developer's repository.

### E3, bot-started side tasks and helpers (about 1–1.5 days) — BUILT
- A `start_helpers` tool (one helper per item, e.g. per Python version) creates a helper group; the queue enforces the limit of 4.

What was built (E3):
- **Bot tools** (`plugins/side_tasks.py`, `SideTaskToolsPlugin` under the `workManagement` capability next to the work-management tools): `side_task_start(title, prompt)` starts one side task (`started_by='bot'`, `kind='side'`) for the current chat and returns its id/title/status/chat id; `start_helpers(items, group_title)` starts one helper per item (`kind='helper'`, one new shared `group_id`, `started_by='bot'`) and returns the group id plus each helper's id/title/status. The tool descriptions tell the model when to use them (user says "do this on the side", work that can run in parallel, e.g. one helper per Python version) and that each runs in its own git worktree and merges back automatically. The model decides from the description — no phrasing detection. The per-parent limit of 4 still applies: extra helpers queue in `waiting_for_slot` and promote FIFO.
- **One level only, enforced twice**: `build_bot_agent` excludes both tools from the agent's registry when the chat is itself a side task (`parent_chat_id` set), so the model never sees them inside a side task or helper; and the service still rejects `start`/`start_helpers` from a side chat with `SideTaskStartError` (HTTP 400 / tool error) as a second layer. A side task's own sub-steps stay in-process steps via the existing `plan_tasks`/`update_task` checklist (workspace_progress) — not more chats.
- **Helper groups**: `group_title` is stored on the records (new `group_title` column, migration 014 — 012/013 were already published in dev builds so they are unchanged) and `SideTaskService.start_helpers` / `group_summary` create and aggregate groups from the real records. New endpoint `GET /api/bots/{bot_id}/side-task-groups/{group_id}` returns `{groupId, title, total, done, failed, running, waiting, needsYou, items}` — `done` counts `done` + `merged`, `waiting` is `waiting_for_slot`, `needsYou` is `needs_you`; a `stopped` helper stays visible through `items` only (its parent was stopped, so the group settles with the parent). The list/start endpoints carry `groupTitle` too.
- **Parent chat learns about it**: `side_task_update` already broadcast every state change. ~~E3's short system note~~ → replaced in E5 by the persisted thread reply (see E5 below): one assistant reply per side task (and one per helper group), created when it settles and updated in place after — for user-started and bot-started side tasks alike, with no duplicate note.
- **Tests** (`tests/test_side_tasks_e3.py`, real git in tmp dirs, SQLite, no PostgreSQL): tools registered only for main chats (registry, per-chat exclusion, end-to-end `build_bot_agent`), `side_task_start`/`start_helpers` create the right records, group summary counts across every bucket, one-level enforcement (hidden tools + service/tool rejection), the limit of 4 applying to helpers with FIFO promotion, and the parent-chat note for merged/done/failed/needs_you (bot-started only, parent only, note again after retry-merge).

### E4, UI (about 2–3 days)
- Side-task card and helpers group card in the parent chat with every 11c state; a yellow border while it needs you.
- Side-task chat view (11b): "Bot / Task name" header with Stop, the sub-line (child of …, its files `side/…`, reports back when done).
- Sidebar tree under the bot (one level, status labels), Runs grouped under the parent, Workspace › Needs you items.
- Start points: More › Do this on the side (message actions), + › Side task (composer), plus bot-started.

### E5, side-task replies: thread-reply model (about 2 days) — BUILT

Juan's reaction to the E4 card stack ("humans reply to threads"): the parent
chat renders side tasks as thread replies, not cards.

What was built (E5):
- **Source message** (migration 015, `side_tasks.source_message_id`): "More ›
  Do this on the side" passes it explicitly (`sourceMessageId` on the start
  request; validated to belong to the parent chat, else 400). "+ › Side
  task" and the bot tools have no message reference — the agent/tool context
  carries no current-message id — so the backend uses the documented
  fallback: the latest user message in the parent chat (the message the
  current turn is answering). No user message at all → `null`, and the UI
  renders the reply without a quoted snippet. `side_tasks.reply_message_id`
  records the single parent-chat reply.
- **One reply per side task, updated in place**: on the first qualifying
  transition (`needs_you` / `done` / `merged` / `failed` / `stopped`) the
  backend persists one assistant message in the parent chat — `reply_to_id`
  = source, content = the side chat's last assistant message trimmed (or a
  record-derived line), metadata `{kind: "side_task_reply", sideTaskId,
  title, chatId, status, replyTo, mergedFiles?, mergedCommit?, error?,
  needsYouReason?, conflictFiles?}`. Retry merge / discard / resume rewrite
  that same message (same id) — a settled side task never leaves a stale
  amber reply offering actions, and there is never a duplicate (the E3
  system note was removed; user-started and bot-started behave the same).
  A serialized reply lock keeps concurrent helper finishes from creating two
  messages; `reply_message_id` is sticky in the repository so stale
  in-memory records can't clobber the group stamp.
- **Helper groups**: ONE `side_task_group_reply` message per group
  (`{kind, groupId, title, status, total, done, failed, running, waiting,
  needsYou, items[{id,title,status,chatId}], replyTo?}`), created at
  `start_helpers` and updated in place on every helper transition.
- **Live updates**: every create/update is pushed over a new scoped
  `message_update` WS event (`{chatId, message}`), same bot-access scoping
  as `side_task_update`. The frontend upserts it into the chat store; on
  chat open it also merges any missed reply messages from the server, so
  replies survive reloads.
- **UI** (`SideTaskReply.tsx`, ChatView): quoted-reply bubble (snippet of
  the source message scrolls to it; summary; files/commit or error/reason
  in small text; "View thread" opens the child chat; needs-you gets the
  amber accent + Retry merge / Discard for operator+). Helpers group reply
  expands per-helper rows. While side tasks only wait or run, a quiet
  one-line indicator sits under the source message (several collapse into
  one line + popover). The big card stack is gone from the parent chat; the
  sidebar tree shows only active + needs-you + failed rows plus a muted "N
  finished" row, amber as the only accent. Start endpoints return the new
  fields (`sourceMessageId`, `replyMessageId`).
- **Test hermeticity fix**: side-task tests had leaked real worktrees and
  `side/*` branches into the developer's own checkout when a background turn
  outlived its test. `SideTaskService.shutdown()` now cancels and awaits
  in-flight turns (used on app shutdown and in every side-task test
  fixture's teardown, before monkeypatches unwind), and an autouse
  `hermetic_side_task_git` conftest fixture roots worktrees in the system
  temp dir and refuses any side-task git operation on a repo outside it.
- **Tests** (`tests/test_side_task_replies.py`, SQLite + real git in tmp
  dirs, mocked agent): source stored/validated/fallback, migration 015
  up/down through real alembic on a stamped SQLite, exactly one reply per
  terminal state with in-place updates (retry-merge, discard, resume), no
  duplicate with the old note, group reply created once and updated across
  concurrent settles, `message_update` scoped by bot access.

### E6, reply inside a side task, "View changes" and Runs — BUILT
The side-task follow-ups: the opened side task becomes a real conversation,
its changes become inspectable, and its turns show up in Runs.

What was built (E6):
- **Reply inside a side task** (`POST /api/bots/{id}/side-tasks/{sideTaskId}/messages`,
  operator+): the reply is persisted into the side task's own chat and the
  task runs again **in its own worktree** — same tool/file sandboxing as the
  original run (the per-run config copy points at the worktree). The
  4-per-parent limit still applies: a reply on a settled task queues it in
  `waiting_for_slot` when the parent is full (promoted FIFO as before).
  Allowed once settled: `done`/`merged` (the worktree/branch were cleaned up,
  so a **fresh `side/<slug>-<short id>` branch is created from the parent's
  current HEAD** — only new work comes back), `failed`/`stopped`/`needs_you`
  (non-conflict) while the worktree or branch still exists (reused as-is, or
  recreated from the surviving branch). A merge conflict must be resolved
  with retry-merge/discard first (409 with a clear reason otherwise);
  running/waiting tasks reject replies too. When the continued turn settles
  it merges back automatically — only what is not in the parent yet — and
  the SAME parent-chat thread reply is updated in place (`reply_message_id`
  stays sticky). `_execute_turn` now takes its input from the newest user
  message in the side chat: a reply drives the continued turn instead of a
  generic "continue" prompt (the prompt itself is still persisted exactly
  once). The UI composer mirrors the server rules: operator+ only, disabled
  with the reason while the task works or waits on a conflict.
- **"View changes"** (`GET /api/bots/{id}/side-tasks/{sideTaskId}/diff`,
  viewers allowed — read-only): the unified diff + per-file stats. Unmerged
  (running/needs_you/failed/stopped): the worktree against its base commit,
  **including uncommitted changes** — untracked files (invisible to plain
  `git diff`) are rendered individually via `git diff --no-index`; when the
  worktree dir is gone but the branch lives, the committed `base..branch`
  range is used. Merged: the merged commit range (`base..mergedCommit` —
  for a continuation on a fresh branch that is exactly the latest bring-in).
  The diff text is capped at 512 KB (`truncated: true` flags a cut); binary
  files are listed without line stats and never blow up the response. UI: a
  "View changes" action in the side-task chat header and on settled thread
  replies, opening a diff dialog (file list with +/− stats, per-file hunks,
  v2 styling, mobile layout). Hidden whenever the record points at no work
  (no worktree, branch, merge or conflict).
- **Runs**: every side-task turn (first run, resume, continuation) writes one
  execution-log row — `execution_type`/`source_type` "side_task", trigger
  `side_task`, `chat_id` = the parent chat, the side task and side-chat ids
  in the metadata — so the existing executions APIs return them, with output
  lines for the key steps (worktree ready, turn finished, merged back /
  conflict / no changes / stopped / failed). In RunsView side-task rows are
  grouped under their parent chat (title fetched once per chat) — helpers
  under their group — with an "Open side chat" link into the side chat.
- **Follow-up fix**: the per-task `_running` done-callback only drops the
  handle when it is still the same task object, so a resume/reply launched
  before the cancelled previous turn exits can no longer lose its handle
  (Stop then reached the direct-transition fallback and left the record
  `running` while the new turn kept working). Related hardening: `_run`
  wraps its WHOLE body in the cancellation handler (a turn cancelled before
  its first database read still settles the record), and a finish with no
  new commits but unmerged commits on the branch (a stopped/failed turn the
  user continued) merges the branch back instead of reporting "done".
- Also: a successful merge no longer races the branch tip for the diff base
  (the base stays the mainline commit the branch started from; continuations
  branch off fresh from the merge commit, so ranges stay correct naturally),
  and `ExecutionLogRepository.complete()` treats SQLite's naive datetimes as
  UTC so run durations compute on SQLite too.
- **Tests** (`tests/test_side_task_e6.py`, SQLite + real git in tmp dirs,
  mocked agent, hermetic like the rest): reply continues in the worktree and
  re-merges only new changes (same parent reply updated in place), reply on
  a cleaned-up `done` task (fresh branch from current HEAD), reply on
  needs_you keeps the worktree, reply with the worktree dir deleted
  (recreated from the branch), 4-per-parent limit on replies, 409s (running,
  queued, merge conflict), viewer 403, empty-content 422; diff for
  unmerged (committed + uncommitted + untracked), merged (latest range
  only), worktree-gone branch range, truncation, binary, empty; execution
  rows (two turns = two `side_task` rows with the right links and step
  lines, cancelled/error outcomes); the done-callback eviction regression
  (both the deterministic handle-identity case and the end-to-end
  needs_you → resume → stop flow).

### Estimate
**About 7–10 working days** (E1 2, E2 2–3, E3 1–1.5, E4 2–3), as 4–5 PRs into dev, each green on its own. E2 builds on the decisions above (worktrees only, automatic merge with conflict → needs_you). Computer-related parts of 11c (labeled windows, preview counts) stay out until the computer backend exists.
