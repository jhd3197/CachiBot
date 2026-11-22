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

### E3, bot-started helpers (about 1–1.5 days)
- A `start_helpers` tool (one helper per item, e.g. per Python version) creates a helper group; the queue enforces the limit of 4.
- A side task's own helpers run as in-process Prompture sub-agents and show as steps (the workspace_progress checklist), not as more chats, which keeps it to one level.
- Detect "do this on the side" phrasing via the tool description (the model decides), not regex.

### E4, UI (about 2–3 days)
- Side-task card and helpers group card in the parent chat with every 11c state; a yellow border while it needs you.
- Side-task chat view (11b): "Bot / Task name" header with Stop, the sub-line (child of …, its files `side/…`, reports back when done).
- Sidebar tree under the bot (one level, status labels), Runs grouped under the parent, Workspace › Needs you items.
- Start points: More › Do this on the side (message actions), + › Side task (composer), plus bot-started.

### Estimate
**About 7–10 working days** (E1 2, E2 2–3, E3 1–1.5, E4 2–3), as 4–5 PRs into dev, each green on its own. E2 builds on the decisions above (worktrees only, automatic merge with conflict → needs_you). Computer-related parts of 11c (labeled windows, preview counts) stay out until the computer backend exists.
