---
phase: 01-model-switching
plan: "02"
subsystem: api
tags: [websocket, pydantic, sqlite, metadata, model-tracking]

# Dependency graph
requires: []
provides:
  - "Assistant BotMessage.metadata persisted with actual model ID used for each response"
  - "Model info survives page refresh via DB-backed metadata dict"
affects: [frontend, chat-history, model-switching]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Extract first key from run_usage[per_model] to identify primary model used"
    - "Fallback chain: per_model first key -> agent.config.agent.model"

key-files:
  created: []
  modified:
    - cachibot/api/websocket.py

key-decisions:
  - "Use first key of per_model dict as actual_model; first key is the primary model used in a response"
  - "Fallback to agent.config.agent.model when per_model is empty (edge case with no usage stats)"

patterns-established:
  - "Model metadata pattern: metadata={'model': actual_model} on every assistant BotMessage save"

requirements-completed:
  - MODL-02
  - MODL-03

# Metrics
duration: 2min
completed: 2026-02-28
---

# Phase 1 Plan 02: Model Switching — Persist Model Metadata Summary

**Assistant BotMessage saves now include metadata={"model": actual_model} derived from run_usage["per_model"], fixing the page-refresh gap where model info was lost from frontend memory**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-28T13:11:53Z
- **Completed:** 2026-02-28T13:13:00Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Assistant messages now saved to DB with `metadata={"model": "<actual_model_id>"}` instead of empty `{}`
- `actual_model` is derived from `run_usage["per_model"]` (first key = primary model used), with fallback to `agent.config.agent.model`
- Model information now persists across page refresh — the existing `MessageBubble` info panel already renders it

## Task Commits

Each task was committed atomically:

1. **Task 1: Persist actual model in assistant BotMessage metadata** - `a3405d0` (feat)

**Plan metadata:** (pending docs commit)

## Files Created/Modified

- `cachibot/api/websocket.py` - Added `actual_model` extraction from `run_usage["per_model"]` and `metadata={"model": actual_model}` in assistant BotMessage constructor

## Decisions Made

- Used `next(iter(per_model), None)` to get the first key of the `per_model` dict — this is the primary model used, matching the existing usage reporting convention in `WSMessage.usage`
- Fallback to `agent.config.agent.model` when `per_model` is empty ensures the field is never `None`
- No changes to `BotMessage` model, repository, or `MessageBubble` — they already support this pattern

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Model metadata is now persisted and the frontend can display it on page reload
- The `MessageBubble` component already reads `message.metadata.model` — no frontend changes needed for this fix
- Next plans can build on model-switching UX knowing the persistence layer is solid

---
*Phase: 01-model-switching*
*Completed: 2026-02-28*
