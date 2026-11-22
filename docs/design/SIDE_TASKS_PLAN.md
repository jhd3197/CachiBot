# Side tasks (principle 9): backend review and phase E plan

Design: `docs/design/cachibot-v2-final-views/` views 11a (side tasks in the chat), 11b (a side task opened) and 11c (how they work).

## What a side task needs, from the design

| Need | From the design |
|---|---|
| A child chat of a parent chat, same bot, its own messages and a short name | 11a/11b header "CachiBot / Update the changelog" |
| Its own copy of the files: a git worktree on a `side/<name>` branch in a repo, else a folder copy; nothing reaches the parent until "Bring into main task" | 11b sub-line, 11c Files |
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

## Phase E plan

### E1, backend model and runner (about 2 days)
- Migration: `chats.parent_chat_id`, `chats.kind` (`main` / `side` / `helper`), `chats.side_status`. Link to a Work row (`work.parent_work_id` = parent chat's run) for status, progress and Runs.
- `SideTaskService`: start (from a message, a composer prompt or a bot tool), at most 4 running per parent with a waiting queue (new `waiting_for_slot` state), stop (cascades to children), and the states running / needs_you / done / brought_in / discarded.
- Run each side task through the job runner with its own chat history: output streams into the child chat; approvals and questions emit `approval_needed` / `side_task_update` WebSocket events that work even when the chat isn't open.
- Parent stop → `cancel_work` on all children (extend the WS `cancel` handler).
- Tests that run without PostgreSQL (service-level with in-memory repos), like the schedule fix.

### E2, files: worktree or copy, then bring in (about 2–3 days)
- Make the workspace per run: the parent uses `workspace_path`. A side task gets `git worktree add -b side/<slug>` when the workspace is a git repo, else a copy of the folder under `.cachibot/side/<id>`.
- Point the tools (`file_ops`, `python_execute`, coding agents) at the side task's workspace through `PluginContext`/config. Today they read the global `config.workspace_path`, so this touches several plugins.
- "View changes": diff (git diff for worktrees, file diff for copies). "Bring into main task": merge the side branch, or copy the changed files back, with conflict reporting. "Discard": remove the worktree or copy.
- This is the riskiest part: path isolation must be enforced or a side task could write into the parent's files.

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
**About 7–10 working days** (E1 2, E2 2–3, E3 1–1.5, E4 2–3), as 4–5 PRs into dev, each green on its own. E2 needs a decision from Juan first (see below). Computer-related parts of 11c (labeled windows, preview counts) stay out until the computer backend exists.

### Decisions for Juan
1. When the workspace isn't a git repo, is a folder copy OK (it can be large), or should side tasks require git?
2. Should "Bring into main task" merge automatically when there are no conflicts, or always show the diff first?
3. Should the limit of 4 be per parent chat or per bot? The design says "up to 4 run at once"; per parent is simpler.
4. Should side tasks keep running when the server restarts? Today stuck runs can't resume (that's the D1 "stuck" banner). Resuming needs persisted chat state per side task.
