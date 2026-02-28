# Requirements: CachiBot High Priority UX & Reliability

**Defined:** 2026-02-28
**Core Value:** Users can interact with AI agents reliably and flexibly

## v1 Requirements

### Model Switching

- [ ] **MODL-01**: User can select a model from a dropdown in the chat input area before sending a message
- [x] **MODL-02**: Selected model override is sent with the WebSocket chat message and used for that response
- [x] **MODL-03**: Model used for each message is stored in message metadata and displayed in the chat bubble
- [ ] **MODL-04**: Model selector defaults to the bot's configured default model

### Bot Marketplace

- [ ] **MKTB-01**: User can browse bot templates with categories, search, and previews from the bot creation flow
- [ ] **MKTB-02**: User can create a new bot from a marketplace template with one click
- [ ] **MKTB-03**: "Browse Templates" option is available alongside "AI Assisted" and "Blank" in bot creation

### Error Resilience

- [ ] **ERRR-01**: React ErrorBoundary wraps the application and shows a recovery UI on component crashes
- [ ] **ERRR-02**: API errors trigger toast notifications with error details and optional retry
- [ ] **ERRR-03**: Network connectivity loss is detected and shown as a persistent banner
- [ ] **ERRR-04**: User can retry failed operations from the error notification

### WebSocket Reliability

- [ ] **WSRL-01**: Client sends ping messages every 30 seconds to detect connection loss
- [ ] **WSRL-02**: Server responds to ping with pong to confirm connection is alive
- [ ] **WSRL-03**: Client automatically reconnects with exponential backoff when connection drops
- [ ] **WSRL-04**: Reconnection state is shown to the user (connecting, connected, disconnected)

## v2 Requirements

### Model Switching Enhancements

- **MODL-05**: User can set a per-chat default model that persists across sessions
- **MODL-06**: Model usage costs are shown per-message in the chat

### Error Resilience Enhancements

- **ERRR-05**: Failed messages are queued for retry when connection is restored
- **ERRR-06**: Error telemetry is collected for debugging

## Out of Scope

| Feature | Reason |
|---------|--------|
| Per-bot usage/cost tracking UI | Medium priority, separate milestone |
| Zustand store refactoring | Separate tech debt milestone |
| Bot advanced settings (temp, tokens) | Medium priority, not in this milestone |
| Room templates / export-import | Medium priority, separate feature |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| MODL-01 | Phase 1 | Pending |
| MODL-02 | Phase 1 | Complete |
| MODL-03 | Phase 1 | Complete |
| MODL-04 | Phase 1 | Pending |
| MKTB-01 | Phase 2 | Pending |
| MKTB-02 | Phase 2 | Pending |
| MKTB-03 | Phase 2 | Pending |
| ERRR-01 | Phase 3 | Pending |
| ERRR-02 | Phase 3 | Pending |
| ERRR-03 | Phase 3 | Pending |
| ERRR-04 | Phase 3 | Pending |
| WSRL-01 | Phase 4 | Pending |
| WSRL-02 | Phase 4 | Pending |
| WSRL-03 | Phase 4 | Pending |
| WSRL-04 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 15 total
- Mapped to phases: 15
- Unmapped: 0

---
*Requirements defined: 2026-02-28*
*Last updated: 2026-02-28 after initial definition*
