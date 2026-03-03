# Roadmap: CachiBot High Priority UX & Reliability

## Overview

Four targeted improvements to CachiBot's chat experience and stability: users gain per-message model control, a template marketplace for bot creation, graceful error recovery, and resilient WebSocket connections that survive network interruptions.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Model Switching** - Per-message model selection in chat input with metadata display (completed 2026-02-28)
- [ ] **Phase 2: Bot Marketplace** - Template browser integrated into bot creation flow
- [ ] **Phase 3: Error Resilience** - ErrorBoundary, toast notifications, and offline detection
- [ ] **Phase 4: WebSocket Reliability** - Heartbeat ping/pong and exponential backoff reconnection

## Phase Details

### Phase 1: Model Switching
**Goal**: Users can select which AI model handles each message, with the choice visible in the conversation history
**Depends on**: Nothing (first phase)
**Requirements**: MODL-01, MODL-02, MODL-03, MODL-04
**Success Criteria** (what must be TRUE):
  1. A model dropdown appears in the chat input area and users can change it before sending
  2. The selected model override is transmitted with the message and the backend uses it for that response
  3. Each chat bubble displays which model produced that response
  4. The dropdown defaults to the bot's configured model on load
**Plans**: 2 plans

Plans:
- [ ] 01-01-PLAN.md — Embed ModelSelect in ChatView status bar and wire override into wsSendMessage
- [ ] 01-02-PLAN.md — Persist actual model in assistant BotMessage metadata for page-refresh display

### Phase 2: Bot Marketplace
**Goal**: Users can browse categorized bot templates and create bots from them in one click
**Depends on**: Nothing (independent of Phase 1)
**Requirements**: MKTB-01, MKTB-02, MKTB-03
**Success Criteria** (what must be TRUE):
  1. Bot creation flow shows a "Browse Templates" option alongside "AI Assisted" and "Blank"
  2. The template browser displays categories, search, and previews of available bots
  3. Clicking a template creates a new bot pre-configured from that template with one action
**Plans**: 1 plan

Plans:
- [ ] 02-01-PLAN.md — Add Browse Templates method card to wizard and verify full install flow

### Phase 3: Error Resilience
**Goal**: Users recover gracefully from crashes and network errors without losing their work context
**Depends on**: Phase 1, Phase 2 (surfaces errors worth recovering from)
**Requirements**: ERRR-01, ERRR-02, ERRR-03, ERRR-04
**Success Criteria** (what must be TRUE):
  1. A component crash shows a recovery UI instead of a blank screen, and the user can reload
  2. API errors appear as toast notifications with a description and optional retry button
  3. Loss of network connectivity triggers a persistent banner indicating the app is offline
  4. Users can trigger a retry from the error notification without navigating away
**Plans**: TBD

Plans:
- [ ] 03-01: React ErrorBoundary component and crash recovery UI
- [ ] 03-02: Toast notification system with API error integration and retry support
- [ ] 03-03: Network connectivity detection and offline banner

### Phase 4: WebSocket Reliability
**Goal**: Real-time connections survive network interruptions and users always know connection status
**Depends on**: Phase 3 (uses toast/banner infrastructure for reconnection state)
**Requirements**: WSRL-01, WSRL-02, WSRL-03, WSRL-04
**Success Criteria** (what must be TRUE):
  1. The client sends a ping every 30 seconds and the server responds with a pong
  2. When the WebSocket drops, the client reconnects automatically with exponential backoff
  3. Connection state (connecting, connected, disconnected) is visible to the user at all times
  4. Reconnection attempts and success are surfaced without interrupting the user's workflow
**Plans**: TBD

Plans:
- [ ] 04-01: Client-side heartbeat and reconnection logic with backoff
- [ ] 04-02: Server-side pong handler and connection state UI indicators

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Model Switching | 2/2 | Complete   | 2026-02-28 |
| 2. Bot Marketplace | 0/1 | Not started | - |
| 3. Error Resilience | 0/3 | Not started | - |
| 4. WebSocket Reliability | 0/2 | Not started | - |
