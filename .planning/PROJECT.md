# CachiBot — High Priority UX & Reliability

## What This Is

CachiBot is a security-focused AI agent platform with a Python/FastAPI backend and React+TypeScript frontend. This milestone focuses on the 4 highest-impact user-facing improvements identified in the deep analysis review: mid-chat model switching, bot marketplace browsing, error resilience, and WebSocket reliability.

## Core Value

Users can interact with AI agents reliably and flexibly — switching models on the fly, discovering pre-built bots, recovering gracefully from errors, and maintaining stable real-time connections.

## Requirements

### Validated

- ✓ BaseRepository generic class — existing (refactored 13 repos)
- ✓ HTTPException helpers (require_found, require_member, require_room_ownership, require_role) — existing
- ✓ API client marketplace cache + SSE dedup — existing (partial)
- ✓ Database indexes on FK columns — existing
- ✓ Bot.model deprecated in favor of models.default — existing
- ✓ WebSocket pendingChatId moved to Zustand — existing

### Active

- [ ] Mid-chat model switching — dropdown in chat input to pick model per-message
- [ ] Bot marketplace browser — template browsing experience for bot creation
- [ ] Error boundary + network error UI — React ErrorBoundary, toasts, retry buttons
- [ ] WebSocket reconnection / heartbeat — ping/pong keep-alive, exponential backoff reconnect

### Out of Scope

- Zustand store refactoring (#5-7) — separate milestone, lower priority
- Prompture/Tukuy library changes (#24-29) — separate work
- Room templates/export (#13) — medium priority, not in this milestone
- Per-bot usage tracking (#14) — medium priority, not in this milestone

## Context

- **Backend:** FastAPI with WebSocket streaming, SQLite async with repository pattern
- **Frontend:** React + TypeScript, Zustand state management, Vite dev server
- **Agent system:** Prompture-based with tool registration, Python sandbox
- **Existing infrastructure:**
  - `model_override` partially supported in WebSocket chat messages via `request_overrides`
  - `MarketplaceBrowser` component already has `'bots'` tab support
  - Backend marketplace API exists with 20+ templates
  - No `<ErrorBoundary>` component currently exists
  - WebSocket has no keep-alive or reconnection logic

## Constraints

- **Tech stack:** Must use existing React/TypeScript frontend and FastAPI backend
- **Compatibility:** Must not break existing chat, room, or bot functionality
- **Performance:** Model selector must not add latency to message sending
- **UX:** Error recovery must be non-intrusive (toasts, not blocking modals)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Per-message model override (not per-chat) | More flexible, matches ChatGPT/Claude UX | — Pending |
| Toast-based error notifications | Non-intrusive, industry standard | — Pending |
| 30s ping/pong heartbeat interval | Balances keep-alive with bandwidth | — Pending |

---
*Last updated: 2026-02-28 after initialization*
